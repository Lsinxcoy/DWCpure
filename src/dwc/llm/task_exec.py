# -*- coding: utf-8 -*-
"""R209 · LLM 用户任务执行器（独立 agent 的接单能力 — 用户 2026-10-12 拍板）。

★★★ 定位（G1 定位门）: **DWC-AUTO（自我强化）** —— 本模块让 agent 能消费
  用户委托的任务（inbox），是 agent 对外能力面而非记忆底座。

★★★ TRUTH_SOURCE: 本模块**不做判定**（判分永远在 judge — 三分离纪律）;
  它只执行 LLM 给的动作并回传观察。无真值源判定面（G2 语义: 非评分模块）。

★ 执行契约（收敛的 ARSI 路子 — actor 诚实边界④的接单版）:
  LLM 每轮返回 JSON: {"analysis": str, "op": "read|write|run|final", ...}
  · read  {"path"}            读文件（ROOT 内任意）
  · write {"path","content"}  写文件（**只许 var/inbox_work/ 下** — 工作区隔离）
  · run   {"cmd":[argv...]}   跑命令（列表参数非 shell; cwd=ROOT; timeout 60s;
                              危险词黑名单: rm -rf/mkfs/format/del /s 等）
  · final {"answer","artifacts"}  产出结论（终轮）
  多轮循环（默认 ≤4 轮）; 每轮动作结果回喂 LLM。超轮/LLM 失败 ⇒
  status=incomplete 带原因（不静默装完成）。

★ LLMClient 纪律: complete() 不抛异常（失败带 error 返回）——本模块把
  LLM 失败当**正常分支**处理（incomplete + why），不是 try/except 吞。
"""
from __future__ import annotations

import io
import hashlib
import json
import os
import re  # ★ R276c · ask 词边界（platform/transform 误含 rm 曾误拦只读扫描）
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

from dwc.foundation.paths import find_root
from dwc.llm import budget as _budget
from dwc.llm import tool_raw
ROOT = find_root()
WORK = os.path.join(ROOT, "var", "inbox_work")
#: 危险命令黑名单（子串匹配; run 动作的护栏之一 — 不是完备沙箱, 是护栏）
_FORBIDDEN = ("rm -rf", "mkfs", "format ", "del /s", "rd /s",
              "shutdown", "reg delete", ":(){", "dd if=")
#: ★ R220 · ask 级（R218/R220 头部 agent 对标: OpenCode allow/deny/ask 三态）——
#:   不硬拒但**停下来要人工授权**: 外发网络/改动仓库外状态/删单文件/改 git 远端。
#:   形态: 动作拒 + obs 带 ask_required — LLM 换路或 final 说明; 报告留痕。
_ASK = ("git push", "git commit", "curl ", "wget ", "ssh ", "scp ",
        "pip install", "npm install", "del ", "rm ", "rmdir",
        "move ", "copy ", "shutdown", "reboot")
#: ★ R218 · 自我认知（维护者写入, agent 只读 — 结构性: write 白名单写不进 config）
SELF_MD = os.path.join(ROOT, "config", "dwc_self.md")
#: ★ R218 · 会话留痕（头部 agent 的 session 概念最小形态: 每任务一个 jsonl）
SESSIONS = os.path.join(os.environ.get("DWC_VAR_DIR")
                        or os.path.join(ROOT, "var"), "dwc_sessions")   # ★ R264: 跟随隔离 env
# ★ R266A · 任务知识沉淀（用户 2026-10-14: "搜索到的信源/知识/论文是驱动
#   系统进化的重要组成部分" — 实测断路: web_read/web_search 结果此前只进
#   session 死档, 零进化消费）。材料≠真值 — 落 var/ 不碰 anchors。
SOURCES = os.path.join(os.environ.get("DWC_VAR_DIR")
                       or os.path.join(ROOT, "var"), "dwc_sources.jsonl")
READING = os.path.join(os.environ.get("DWC_VAR_DIR")
                       or os.path.join(ROOT, "var"), "dwc_reading_list.jsonl")
_PAIRS_FAIL = 0   # ★ G7: 修订对落盘失败计数（不静默）
PAIRS_PATH = ""   # ★ 测试隔离钩子（空=默认; conftest 设 env 时落到 tmp）


def _ask_level(cmd_joined: str) -> Optional[str]:
    """run 命令的三态分级: 黑名单=None(调用方硬拒); ask 命中=该词; 都无=放行。
    ★ R276c · 词左边界（(?<!\\w): platform/transform 含 rm 不得误拦）。"""
    for w in _ASK:
        if re.search(r"(?<!\w)" + re.escape(w), cmd_joined):
            return w
    return None


class TaskExecError(Exception):
    pass


def _guard_path(path: str, *, write: bool) -> str:
    """路径护栏: 读限 ROOT 内; 写只许 var/inbox_work/。"""
    p = os.path.normpath(os.path.join(ROOT, path) if not os.path.isabs(path)
                         else path)
    if write:
        w = os.path.normpath(WORK)
        if not (p == w or p.startswith(w + os.sep)):
            raise TaskExecError("写只许 var/inbox_work/ 下: %s" % path)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p
    if not os.path.normpath(p).startswith(os.path.normpath(ROOT)):
        raise TaskExecError("读限仓库内: %s" % path)
    return p


def _parse_ddg(html: str) -> list:
    """★ R263 · DDG HTML 结果解析（活体结构 2026-10-14:
    a.result__a href=//duckduckgo.com/l/?uddg=<urlenc> + result__snippet
    — uddg 参数解出真实 URL, rut 是追踪签名丢弃）。"""
    from html.parser import HTMLParser
    import html as _html
    import urllib.parse as _up

    class _P(HTMLParser):
        def __init__(self):
            super().__init__()
            self.items, self._cur, self._cap, self._in_snip = [], None, "", False

        def handle_starttag(self, tag, attrs):
            if tag != "a":
                return
            a = dict(attrs)
            cls = a.get("class") or ""
            if "result__a" in cls and "href" in a:
                # ★ 新 result 起点: 旧的（若 title 已完）先收 — snippet 是
                #   **兄弟**元素（活体结构）, title </a> 不能清 _cur（清了
                #   就丢 snippet — 测试抓到的 bug）
                if self._cur is not None and self._cap != "title":
                    self.items.append(self._cur)
                href = a["href"]
                if "uddg=" in href:         # DDG 重定向 → 真实 URL
                    try:
                        href = _up.unquote(
                            _up.parse_qs(_up.urlparse(href).query)
                            .get("uddg", [href])[0])
                    except Exception:       # noqa: BLE001 — 解链失败保原文
                        pass
                self._cur = {"url": href, "title": "", "snippet": ""}
                self._cap, self._in_snip = "title", False
            elif "result__snippet" in cls and self._cur is not None:
                self._in_snip = True
                self._cap = "snippet"

        def handle_endtag(self, tag):
            if tag == "a" and self._cur is not None and self._cap == "title":
                self._cap = ""              # title 完 — 保留 _cur 收 snippet
            elif tag == "a" and self._in_snip:
                self._in_snip = False

        def handle_data(self, data):
            if self._cur is None:
                return
            if self._cap == "title":
                self._cur["title"] += data
            elif self._in_snip:
                self._cur["snippet"] += data

    p = _P()
    p.feed(html)
    if p._cur is not None:
        p.items.append(p._cur)          # 文档尾残留
    out = []
    for it in p.items:
        it["title"] = _html.unescape(it["title"]).strip()
        it["snippet"] = _html.unescape(it["snippet"]).strip()
        if it["title"] or it["url"]:
            out.append(it)
    return out


def _html_to_text(html: str) -> str:
    """★ R261 · 轻量 html→text（标准库 HTMLParser — 零依赖）。"""
    from html.parser import HTMLParser

    class _T(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self._skip = 0
            self._buf: List[str] = []

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "noscript"):
                self._skip += 1

        def handle_endtag(self, tag):
            if tag in ("script", "style", "noscript") and self._skip:
                self._skip -= 1

        def handle_data(self, data):
            if not self._skip and data.strip():
                self._buf.append(data.strip())

    t = _T()
    try:
        t.feed(html)
    except Exception:                       # noqa: BLE001 — 解析失败退化剥标签
        import re as _re
        return _re.sub(r"<[^>]+>", " ", html)
    return "\n".join(t._buf)


def _args_snapshot(step: Dict[str, Any], limit: int = 200) -> str:
    """★★★ R400 · 留痕参数快照 —— **JSON 必须完整**。

    现场（2026-10-21 00:41 全池，code-locate 5 单灭 4 单）：
      `json.dumps({...})[:160]` 把 JSON **从中间切断** ⇒ 留下非法 JSON
      ⇒ `step_judge.judge_step` 回读时 `json.loads` 抛
        `JSONDecodeError: Unterminated string starting at char 100`
      ⇒ 整个动作被判失败（其实命令已经成功了）⇒ 模型重试同一脚本
      ⇒ 再崩 ⇒ 最后放弃作答。

    修：值可截断，JSON 不许截断；另存 `_h` = 全量参数指纹，
    保证"前 160 字符相同的两条长命令"仍可区分（否则去重会误判重复）。
    """
    d = {k: step.get(k) for k in ("offset", "limit", "cmd")
         if step.get(k) is not None}
    if not d:
        return ""
    raw = json.dumps(d, ensure_ascii=False, sort_keys=True, default=str)
    d["_h"] = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    s = json.dumps(d, ensure_ascii=False, default=str)
    if len(s) <= limit:
        return s
    # 超长 ⇒ 逐值截断，`_h` 保真
    budget = max(24, (limit - 60) // max(1, len(d)))
    d2 = {k: (v if k == "_h" else str(v)[:budget]) for k, v in d.items()}
    s2 = json.dumps(d2, ensure_ascii=False, default=str)
    return s2 if len(s2) <= limit else json.dumps(
        {"_h": d["_h"]}, ensure_ascii=False)


#: ★★★ R407 · 问题在问**标识符**（类名/变量名/文件名/主题名）的判据。
#:   只在这类问题上强制取证 —— 纯知识问答（"什么是闭包"）不受影响。
_IDENT_Q_RE = re.compile(
    r"(叫什么|叫什么名字|叫啥|哪个文件|哪一个|是哪个|哪一套|变量名|类名|"
    r"函数名|方法名|主题名|名称是什么|名字是什么|文件名叫|"
    r"which file|what(?:'s| is) the name)")

#: 代码标识符形态（不是普通英文单词）：
#:   ① UPPER_SNAKE（环境变量开关那种大写下划线形态）
#:   ② CamelCase  ≥2 个驼峰：`MemoryKernel` / `OutcomePredictor`
_UPPER_IDENT = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
_CAMEL_IDENT = re.compile(r"\b[a-zA-Z]+(?:[A-Z][a-z0-9]+)+\b")

_REPO_TEXT_CACHE: Optional[str] = None
_REPO_SKIP_DIRS = {".git", ".cache", "var", "archive", "node_modules",
                   "__pycache__", ".venv", "venv", "build", "dist",
                   # ★★★ R427 · `docs/repos/` 是**外部仓库镜像**（README 转储，
                   #   3.4MB）。它被 search_code 索引后，别的项目的组件名会冒充
                   #   本仓库的文件名 —— 某 code-locate 题 现场：镜像里写着别的项目的
                   #   组件名，模型据此答出一个本仓库根本不存在的路由文件名。
                   #   **外部仓库不是本仓库的语料。**
                   "repos"}
_REPO_EXTS = (".py", ".yaml", ".yml", ".json", ".toml", ".md", ".jsonl")

#: ★★★ R437 · **按文件名找**时不能跳过 `var` / `archive`。
#:   现场（全池 2 轮）：某 code-locate 题问「var 下的运行时文件名」，
#:   `find_files` 返回 `TOTAL 0` —— 文件明明在 `var/`，但
#:   `_REPO_SKIP_DIRS` 把 `var` 排除了。模型据此连续两次给出不存在的
#:   文件名，被幻觉闸拦下，答案变成「未能给出有效答案…」。
#:   内容检索仍要跳过（`var/` 有几万行运行时日志，会淹没代码）；
#:   但**按名找文件**是 O(目录项)，没有噪声问题。
_FIND_SKIP_DIRS = _REPO_SKIP_DIRS - {"var", "archive"}


def _repo_text() -> str:
    """懒加载仓库文本索引（给"这个名字到底存不存在"用）。"""
    global _REPO_TEXT_CACHE
    if _REPO_TEXT_CACHE is not None:
        return _REPO_TEXT_CACHE
    parts = []
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))  # src/dwc/llm -> 仓库根
    for base in ("src", "scripts", "config"):
        for dp, dn, fn in os.walk(os.path.join(root, base)):
            dn[:] = [d for d in dn if d not in _REPO_SKIP_DIRS]
            for f in fn:
                if not f.endswith(_REPO_EXTS):
                    continue
                try:
                    if os.path.getsize(os.path.join(dp, f)) > 8_000_000:
                        continue
                    with open(os.path.join(dp, f), encoding="utf-8",
                              errors="replace") as fh:
                        parts.append(fh.read())
                except OSError:
                    continue
    _REPO_TEXT_CACHE = "\n".join(parts)
    return _REPO_TEXT_CACHE


def _ident_gate(task: str, ans: str, has_ev: bool):
    """★★★ R407 · 标识符类问题 + 零取证 ⇒ 返回打回提示（否则 None）。"""
    if has_ev:
        return None
    if not _IDENT_Q_RE.search(str(task or "")):
        return None
    idents = _UPPER_IDENT.findall(str(ans or "")) + \
        _CAMEL_IDENT.findall(str(ans or ""))
    if not idents:
        return None
    tok = sorted(set(idents))[0]
    return ("任务: %s\n你在**没有做任何取证**的情况下直接给出了一个标识符"
            "（%s）—— 这是凭印象猜的，不予采纳。\n"
            "先调用 search_code(pattern='%s')，从 === DEFINITIONS 段确认，"
            "再 final。" % (task, "、".join(sorted(set(idents))[:3]), tok))


def _ident_used_in_code(tok: str) -> bool:
    """★ R407-b · 该名字是否**真的在代码里被使用**（不只是文档提过）。

    只认 `"NAME"` / `'NAME'` / `NAME=` / `NAME:` 这几种形态。
    动机：这个坑我自己踩了三次 —— 把名字写进注释/文档里，检索就能命中，
    于是"存在性检查"永远通过（自证预言）。判据必须看**用法**。
    """
    pat = (r'(?:["\']%s["\']|\b%s\s*[:=])'
           % (re.escape(tok), re.escape(tok)))
    return re.search(pat, _repo_text()) is not None


_REPO_FILES_CACHE: Optional[set] = None

#: 任务在**问文件名**（才做存在性校验；写文件类任务会提到尚不存在的文件名）
_FILE_Q_RE = re.compile(r"(文件名|哪个文件|什么文件|入口文件|脚本名|叫什么)")
_FILE_TOKEN_RE = re.compile(
    # ★ R437 · 长后缀必须排前面并加 \b：`(?:py|md|json|jsonl…)` 会让
    #   `dwc_pairs.jsonl` 只匹配到 `.json`（尾部 l 被丢掉）⇒ 存在性校验
    #   把真实文件判成幻觉。
    r"[\w\-./\\]+\.(?:jsonl|json|ya?ml|toml|py|md|txt|cfg|ini)\b")


def _repo_files() -> set:
    """仓库里所有文件的**小写基名**集合（懒加载，只收名字不收内容）。"""
    global _REPO_FILES_CACHE
    if _REPO_FILES_CACHE is not None:
        return _REPO_FILES_CACHE
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    names = set()
    for dp, dn, fn in os.walk(root):
        # ★ R437 · 用 `_FIND_SKIP_DIRS`（不排 var/archive）—— 存在性校验要
        #   和 `find_files` 的可见范围一致：agent 能找到的文件，就不能判成
        #   "不存在"。旧实现用 `_REPO_SKIP_DIRS`，把 var/ 下的真实文件判成幻觉。
        dn[:] = [d for d in dn
                 if d not in _FIND_SKIP_DIRS and not d.startswith(".")]
        for f in fn:
            names.add(f.lower())
    _REPO_FILES_CACHE = names
    return names


def _phantom_file_gate(task: str, ans: str):
    """★★★ R417 · 答案里的文件名在仓库里**一个都不存在** ⇒ 打回。

    现场（某 code-locate 题）：问「CLI 入口路由文件叫什么」，模型跑了 find_files、读了
    两个文件（**有取证**，所以 R400-f 不触发），最后仍答了一个
    **仓库里根本不存在的**路由文件名 —— 真实入口是 `cli_main.py`。

    R400-f 拦的是"零取证的文件名断言"；这里补的是**有取证也照样编**：
    文件名是不是真的存在，是**可判定事实**，不该靠模型自觉。

    ★ 只在"任务在问文件名"时启用：写文件类任务会合法地提到尚不存在的文件名。
    ★ 答案里只要有一个文件是真的，就不拦（避免误伤"提到多个文件"的正常答案）。
    """
    if not _FILE_Q_RE.search(str(task or "")):
        return None
    toks = _FILE_TOKEN_RE.findall(str(ans or ""))
    if not toks:
        return None
    files = _repo_files()
    bad = []
    for t in toks:
        base = os.path.basename(t.replace("\\", "/")).lower()
        if base and base not in files:
            bad.append(t)
    if len(bad) < len(toks):        # 至少一个真实存在 ⇒ 不拦
        return None
    return ("任务: %s\n你给出的文件名在仓库里**一个都不存在**：%s\n"
            "这是凭印象编的（不是取证得到的）。请用 find_files 或 "
            "search_code 在仓库里实际确认文件名，再 final。"
            % (task, "、".join(sorted(set(bad))[:3])))


def _fake_ident_gate(ans: str):
    """★★★ R407-b · 答案里的 `DWC_*` 必须**真的在代码里被使用**。

    现场（某 read-fact 题）：模型答了一个全仓 0 命中的开关名；真实开关是另一个。
    只查 `DWC_` 前缀：项目自有的名字，外部概念（HTTP/JSON）不误伤。
    """
    for tok in sorted(set(_UPPER_IDENT.findall(str(ans or "")))):
        if not tok.startswith("DWC_"):
            continue
        if not _ident_used_in_code(tok):
            return ("你给出的 `%s` 在代码里**没有任何使用点**（src/scripts/config "
                    "全仓检索：无引号引用、无赋值、无配置项）。\n"
                    "改搜**问题里的中文概念词**（例如问题问「事前判别」，就 "
                    "search_code(pattern='事前判别')），从命中行里读出真实名字；"
                    "不要搜你猜的那个名字（会搜到你自己的猜测）。" % tok)
    return None



def _ev_excerpt(log, n: int = 2, chars: int = 700) -> str:
    """★★★ R408-b · 把最近 n 条**成功** obs 的原文摘出来，直接贴进提示。

    动机（某 read-fact 题 实测）：打回提示写「请回看上面的 obs」—— 模型**根本不回看**，
    下一轮照旧拒答。把证据原文贴进 prompt 里，它才有可能用上。
    """
    ok = [e for e in (log or [])
          if isinstance(e, dict) and e.get("phase") == "obs" and e.get("ok")]
    if not ok:
        return ""
    out = []
    for e in ok[-n:]:
        body = e.get("obs")
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False, default=str)
        out.append("· %s → %s" % (str(e.get("op", "")),
                                  str(body)[:chars]))
    return "\n".join(out)


def _refusal_gate(task: str, ans: str, has_ev: bool, ev: str = ""):
    """★★★ R408 · 已经拿到证据却拒答 ⇒ 打回，让它从 obs 里摘答案。

    现场（某 read-fact 题）：模型搜索命中、并且读到了正文里写着答案的那个
    文件（甚至读到一个内容就是答案的文件），最后仍答「未检索到任何证据」。
    **证据在手还拒答**，比猜错更冤。

    只拦"拒答话术"，且**必须有取证**：真的搜不到（零 obs）时拒答是
    诚实行为，不拦。
    """
    if not has_ev:
        return None
    if not re.search(r"(无法(?:确定|确证|判断)|不能确定|未(?:能)?(?:检索|找到|发现)"
                     r"到|没有(?:找到|检索到)|无(?:法)?(?:从|在)仓库)", str(ans or "")):
        return None
    return ("任务: %s\n你**已经拿到了取证**（上面有成功的 obs），却仍然拒答 —— "
            "这不可接受。\n"
            "下面是**你已经拿到的证据原文**：\n%s\n"
            "答案就在上面 —— 从中摘出最短的那个，直接 final。\n"
            "只有在**所有证据都确实与问题无关**时才允许拒答，"
            "并在答案里引用你查过的具体路径。" % (task, ev or "（无）"))


def _do_action(op: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """执行一个白名单动作 → 观察（回喂 LLM 的材料）。"""
    try:  # ★ R308-② · 能力开关（关⇒拒收留痕，不静默；默认全开零行为变）
        from dwc.caps.registry import is_enabled as _cap_on
        from dwc.llm.errors import err as _err
        if not _cap_on(op):
            return _err("CAP_DISABLED",
                        "能力 %s 已关闭（config/capabilities.yaml）" % op)
    except Exception:
        # 注册表本身炸⇒fail-open（不能因治理层故障砖掉执行层；G7 非静默：
        # 命名变量＋注释，拒绝原因与此处无关——拒收只走上面的 return）
        _cap_broken = True
    if op == "web_search":
        # ★ R263 · 网页搜索（研究任务的起点是"查 X" — 只能抓已知 URL 就是
        #   死路; DDG HTML 版免 key 零依赖 — 结构 2026-10-14 活体探测:
        #   10×result__a + uddg 重定向链接 + 浏览器 UA 才 200）
        import urllib.request
        import urllib.parse
        query = str(args.get("query", "")).strip()
        if not query:
            return {"ok": False, "error": "web_search 需要 query"}
        try:
            limit = min(10, max(1, int(args.get("limit", 8) or 8)))
        except (TypeError, ValueError):
            limit = 8
        s_url = ("https://html.duckduckgo.com/html/?q="
                 + urllib.parse.quote(query))
        req = urllib.request.Request(s_url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/126.0.0.0 Safari/537.36"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read(2_000_000)
        except Exception as exc:            # noqa: BLE001 — 网络失败如实报
            return {"ok": False, "error": "web_search 失败: %s: %s"
                    % (type(exc).__name__, exc)}
        results = _parse_ddg(raw.decode("utf-8", errors="replace"))[:limit]
        if not results:
            return {"ok": True, "query": query, "n": 0,
                    "content": "(无结果 — 换个更通用的 query 重试)"}
        lines = []
        for i, r in enumerate(results, 1):
            lines.append("%d. %s\n   %s%s" % (
                i, r["title"], r["url"],
                ("\n   " + r["snippet"][:200]) if r["snippet"] else ""))
        return {"ok": True, "query": query, "n": len(results),
                "content": "\n".join(lines) +
                           "\n\n(拿到目标 URL 后用 web_read 抓正文)"}
    if op == "web_read":
        # ★ R261 · 网页抓取（研究类任务最疼的缺口 — urllib 零依赖;
        #   协议白名单 http/https; 超时 20s; 体积 2MB 上限）
        import urllib.request
        url = str(args.get("url", "")).strip()
        if not url.startswith(("http://", "https://")):
            return {"ok": False, "error": "web_read 只接受 http/https URL: %s"
                    % url[:80]}
        req = urllib.request.Request(
            url, headers={"User-Agent": "DWC-Agent/1.0 (+research)"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                raw = resp.read(2_000_000)
                charset = resp.headers.get_content_charset() or "utf-8"
        except Exception as exc:            # noqa: BLE001 — 网络失败如实报
            return {"ok": False, "error": "web_read 失败: %s: %s"
                    % (type(exc).__name__, exc)}
        body = raw.decode(charset, errors="replace")
        text = (_html_to_text(body)
                if "html" in (resp.headers.get_content_type() or "")
                else body)
        return {"ok": True, "url": url, "chars": len(text),
                "content": text[:8000]
                           + ("\n…(截断 — 正文 %d 字符)" % len(text)
                              if len(text) > 8000 else "")}
    if op == "read":
        p = _guard_path(str(args.get("path", "")), write=False)
        if os.path.splitext(p)[1].lower() in (".png", ".jpg", ".jpeg",
                                              ".webp"):
            # ★ R226 · 多模态读图: 路径回传, 循环层经 images 通道给 LLM
            #   （端点不支持视觉 ⇒ LLM 层 4xx 如实报 — 不假装能看）
            return {"ok": True, "image_path": p,
                    "note": "图片已挂到下一轮 LLM 输入（若端点不支持视觉"
                            "会明确报错）"}
        if os.path.splitext(p)[1].lower() == ".pdf":
            # ★ R263 · PDF 读（研究任务高频 — 曾按 utf-8 读二进制=乱码;
            #   抽文本后走**同一** offset/limit 分页 — 零新分页逻辑）
            try:
                import pypdf            # noqa: PLC0415 — 缺依赖时明确报
            except ImportError:
                return {"ok": False, "error": "读 PDF 缺依赖 pypdf — "
                        "安装: pip install pypdf"}
            try:
                reader = pypdf.PdfReader(p)
                if reader.is_encrypted:
                    return {"ok": False, "error": "PDF 已加密: %s"
                            % os.path.relpath(p, ROOT)}
                pages = []
                for i, pg in enumerate(reader.pages, 1):
                    pages.append("--- p.%d ---\n%s"
                                 % (i, (pg.extract_text() or "").strip()))
                txt = "\n".join(pages)
            except Exception as exc:     # noqa: BLE001 — 损坏 PDF 如实报
                return {"ok": False, "error": "PDF 解析失败: %s: %s"
                        % (type(exc).__name__, exc)}
            lines = txt.splitlines()
        else:
            with io.open(p, encoding="utf-8", errors="replace") as fh:
                txt = fh.read()
            lines = txt.splitlines()
        n = len(lines)
        # ★ R247 翻页: offset/limit 行级定位（恒定截断曾致"读后半部分"
        #   无动作可做 — 17:12 实测 4 轮复读同段至上限）
        try:
            off = max(0, int(args.get("offset", 0) or 0))
        except (TypeError, ValueError):
            off = 0
        try:
            # ★★★ R424 · 缺省 **200** 行（原 50）——
            #   现场（某 read-fact 题，R423 全池）：PROGRESS.md 共 137 行，默认 50 行
            #   要读 3 次；模型读到第 100 行就停下，答「剩余 100-137 行
            #   未能读取」并用别处的数字猜。**50 行缺省把一次读变成三次，
            #   模型每次都可能在中途放弃。**
            #   仓库里绝大多数文件 < 200 行 ⇒ 一次读完，翻页只留给大文件。
            _def = read_default_lines()
            lim = min(400, max(1, int(args.get("limit", _def) or _def)))
        except (TypeError, ValueError):
            lim = 0
        seg = lines[off:] if not lim else lines[off:off + lim]
        body = "\n".join(seg)
        truncated = bool(lim) and (off + len(seg)) < n
        if not lim and len(body) > 8000:          # 无 limit 的旧路径
            body, truncated = body[:8000], True
        out = {"ok": True, "n_lines": n, "offset": off,
               "returned_lines": len(seg),
               "truncated": truncated,
               "content": body + ("\n…(截断 — 用 offset=%d 继续)"
                                   % (off + len(seg)) if truncated else "")}
        if truncated and not args.get("offset"):
            out["hint"] = ("文件共 %d 行, 本段只到第 %d 行 — 继续读后面: "
                           "同 path + offset=%d"
                           % (n, off + len(seg), off + len(seg)))
        return out
    if op == "write":
        p = _guard_path(str(args.get("path", "")), write=True)
        content = str(args.get("content", ""))
        with io.open(p, "w", encoding="utf-8") as fh:
            fh.write(content)
        # ★ R305-T2 · sec_review 接线（纯规则只告警不驳回：照写 ok=True，
        #   findings 进 obs 回喂 LLM；坏输入 [] 不拦）
        try:
            from dwc.llm.sec_review import review_diff as _srev
            _sw = _srev(content, os.path.relpath(p, ROOT))
        except Exception:
            _sw = []
        return {"ok": True, "path": os.path.relpath(p, ROOT),
                "bytes": len(content.encode("utf-8")),
                "sec_warnings": _sw}
    if op == "mcp":
        # ★ R224 · MCP 工具调用（标准协议面: server 配置在 config/mcp.json
        #   — 维护者写 agent 只读; 未配置的 server 明确报错不静默）
        from dwc.llm import mcp_client as M
        server = str(args.get("server", ""))
        tool = str(args.get("tool", ""))
        if not server or not tool:
            raise TaskExecError("mcp 需要 server 与 tool: %r" % (args,))
        # ★ R309-② · 发现缓存 TTL（yaml 可调；probe() 供健康检查单用，
        #   每次调用不双倍 RPC）。
        try:
            from dwc.caps.registry import cap_limit as _cap_lim2
            _mttl = _cap_lim2("mcp", "probe_ttl_s", 300)
        except Exception:
            _mttl = 300
        return M.tools_call(server, tool, args.get("args") or {},
                            ttl_s=_mttl)
    if op == "run":
        cmd = args.get("cmd")
        if not isinstance(cmd, list) or not cmd:
            raise TaskExecError("cmd 必须是非空 argv 列表: %r" % (cmd,))
        joined = " ".join(str(x) for x in cmd).lower()
        hit = [w for w in _FORBIDDEN if w in joined]
        if hit:
            raise TaskExecError("危险命令黑名单命中 %s: %s" % (hit, joined[:120]))
        # ★★★ R400 · 拦截"自写搜索脚本" —— 现场（某 code-locate 题/某 code-locate 题）模型不用
        #   search_code，改用 `python -c <自己写的 os.walk 脚本>`：
        #   ① 它的分类逻辑把『MemoryKernel 的定义行』归到 REFERENCES（答不出）
        #   ② 脚本自己还会抛 `TypeError: Object of type set is not JSON
        #      serializable`，模型据此"撤回"正确答案
        #   工具层（readonly=True，如 search_code 自己）不拦。
        if (not args.get("_from_tool") and len(cmd) >= 3
                and str(cmd[0]).lower().endswith(("python", "python.exe"))
                and str(cmd[1]) == "-c"
                and ("definitions" in joined
                     or ("os.walk" in joined and "re." in joined))):
            return {"ok": False,
                    "error": "已拦截：不要用 run_command 跑自写的搜索脚本"
                             "（分类会错、参数还会被截断）。"
                             "请直接调用 search_code(pattern='符号名')，"
                             "答案在它的 === DEFINITIONS 段。"}
        ask = _ask_level(joined)
        confirmed = args.get("_confirmed") or set()
        if ask and any(str(c) in joined for c in confirmed):
            # ★ R222 · 人工授权通道: ctx 带 '人工授权: <词>' ⇒ 放行 + 留痕
            r0 = subprocess.run([str(x) for x in cmd], cwd=ROOT,
                                capture_output=True, text=True, timeout=60,
                                encoding="utf-8", errors="replace")
            return {"ok": r0.returncode == 0, "rc": r0.returncode,
                    "stdout": tool_raw.clip(r0.stdout or "", limit=4000),
                    "stderr": (r0.stderr or "")[:1000],
                    "confirmed_by_human": ask}
        if ask:
            # ★ R225 · 实时审批（发布级: 头部 agent 的 ask=等客户端决定）——
            #   ① pending 落盘 ② 飞书通知用户 ③ 轮询授权答复（≤ ASK_WAIT）
            #   ④ approve ⇒ 真执行带人戳 / 否则拒（R222 重投通道仍保留）
            ans = _ask_human(ask, joined, args.get("_task_id") or "")
            if ans is True:
                r0 = subprocess.run([str(x) for x in cmd], cwd=ROOT,
                                    capture_output=True, text=True,
                                    timeout=60, encoding="utf-8",
                                    errors="replace")
                return {"ok": r0.returncode == 0, "rc": r0.returncode,
                        "stdout": tool_raw.clip(r0.stdout or "", limit=4000),
                        "stderr": (r0.stderr or "")[:1000],
                        "confirmed_by_human": ask}
            raise TaskExecError(
                "ask_required: %r 类操作被拒或未获授权（%s）。换路或在"
                " final 说明需要人工做哪步" % (ask, ans))
        try:
            r = subprocess.run([str(x) for x in cmd], cwd=ROOT,
                               capture_output=True, text=True, timeout=60,
                               encoding="utf-8", errors="replace")
            return {"ok": r.returncode == 0, "rc": r.returncode,
                    "out": tool_raw.clip(r.stdout or "", limit=6000),
                    "err": (r.stderr or "")[:1500]}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "timeout 60s"}
    raise TaskExecError("未知动作 op=%r（白名单: read/write/run/"
                        "web_read/web_search/mcp/delegate/ask/final）" % op)


#: ★★★ R383 · 「声称执行了动作」的模式。
#:   现场（2026-10-20 全池）：模型零动作却在 answer 里写「已写入 xxx」
#:   「文件创建成功」「已执行命令,退出码 0」—— 全是幻觉。
#:   注意必须用正则：真实文本是「已**在** `note.txt` **写入**」——
#:   动词被路径隔开，纯子串「已写入」匹配不到（已踩）。
_ACTION_CLAIM_RE = re.compile(
    r"(?:已|成功)[^。\n]{0,40}?(?:写入|创建|保存|生成|修改|删除|追加|执行|运行|提交)"
    r"|(?:写入|创建|保存|执行|运行)成功"
    r"|(?:written|created|saved|executed)\b",
    re.IGNORECASE)

#: ★★★ R383 · 「明确拒绝执行」的模式（这类文本不是答案）。
_REFUSAL_RE = re.compile(
    r"我无法(?:执行|直接|完成|访问|读取|写入)"
    r"|我没有(?:访问|终端|文件|工具)"
    r"|没有可用的(?:文件|终端|工具|命令)"
    r"|无法访问文件系统"
    r"|cannot access|no (?:file )?tools available|no terminal",
    re.IGNORECASE)


def _claimed_action_without_actions(text: str, n_actions: int) -> str:
    """★★★ R383 · 零动作却声称做过动作 ⇒ 返回命中的片段（否则空串）。

    R380 把"非 JSON 纯文本"收下当答案，结果模型**说**它写了文件就被
    当成完成（`某 write 题/某 write 题/某 write 题/某 write 题` 现场：文件根本没写）。
    这是假成功 —— 降级与成功不可区分。
    """
    if n_actions > 0:
        return ""
    m = _ACTION_CLAIM_RE.search(text or "")
    return m.group(0)[:40] if m else ""


def _looks_like_refusal(text: str, n_actions: int) -> str:
    """★★★ R383 · 零动作且明确拒绝 ⇒ 返回命中片段（否则空串）。

    现场：`某 analyze 题` 答「我无法执行文件写入（没有可用的文件/终端工具）」
    被判 done —— 这是拒绝，不是答案。
    """
    if n_actions > 0:
        return ""
    m = _REFUSAL_RE.search(text or "")
    return m.group(0)[:40] if m else ""


#: ★ R438 · 策略产物读取（带 mtime 缓存：产物变了下一轮就生效，不必重启）
_POLICY_CACHE: Dict[str, Any] = {}


def _policy(component: str, key: str, default: Any) -> Any:
    """读 evo_targets 的产物；坏文件/未知组件 ⇒ default + stderr 留痕。"""
    try:
        from dwc.organs import evo_targets as ET
        p = ET.path_of(component)
        try:
            mt = os.path.getmtime(p)
        except OSError:
            return default
        ck = component + "|" + str(mt)
        hit = _POLICY_CACHE.get(ck)
        if hit is None:
            hit = ET.read(component)
            _POLICY_CACHE.clear()
            _POLICY_CACHE[ck] = hit
        return hit.get(key, default)
    except Exception as exc:  # noqa: BLE001 — 策略坏不拦任务，但必须留痕
        import sys as _s
        _s.stderr.write("策略读取失败 %s.%s: %r\n" % (component, key, exc))
        return default


def tool_budget() -> _budget.ToolBudget:
    """★ R441 · 三段式工具预算（context_mgmt 维度，可被进化改写）。

    坏值/坏文件 ⇒ 退回模块默认（`_policy` 已留痕）；返回前统一 `normalized()`，
    保证 economy ≤ strict ≤ finalize（倒序配置不许把阶段语义倒过来）。
    """
    def _g(key: str, default: int) -> int:
        try:
            return int(_policy("context_mgmt", key, default))
        except Exception:      # noqa: BLE001 — 预算坏不拦任务（_policy 已留痕）
            return default

    return _budget.ToolBudget(
        economy_after=_g("budget_economy_after", 6),
        strict_after=_g("budget_strict_after", 10),
        finalize_after=_g("budget_finalize_after", NATIVE_TOOLS_MAX_ROUNDS),
        reminder_every=_g("budget_reminder_every", 3),
    ).normalized()


def read_default_lines() -> int:
    """read_file 缺省行数（context_mgmt 维度）。"""
    try:
        return int(_policy("context_mgmt", "read_default_lines", 200))
    except (TypeError, ValueError):
        return 200


def output_max_chars() -> int:
    """最终答案最大字符数（output_plumbing 维度）。"""
    try:
        return int(_policy("output_plumbing", "max_answer_chars", 6000))
    except (TypeError, ValueError):
        return 6000


def _cap_answer(s: Any) -> str:
    """最终答案统一出口：strip + 截断（output_plumbing 的唯一消费者）。"""
    t = str(s or "").strip()
    n = output_max_chars()
    return t if len(t) <= n else t[:n]


#: ★★★ R384 · 原生 tool calling 的工具表（与内部 op 白名单一一对应）。
#:   模型本来就会调工具（实测 finish=tool_calls / read_file{path:...}），
#:   是旧代码用手拼 JSON 提示词逼它输出散文 ⇒ 全池 51/54 = 94% 零动作。
TASK_TOOLS = [
    {"type": "function", "function": {
        "name": "read_file",
        "description": "读取仓库内文件的文本内容（相对路径）",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"}},
                       "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "write_file",
        "description": "把内容写入文件（相对路径，覆盖写）",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"},
                                      "content": {"type": "string"}},
                       "required": ["path", "content"]}}},
    {"type": "function", "function": {
        "name": "run_command",
        "description": "在仓库根目录执行 shell 命令并返回输出",
        "parameters": {"type": "object",
                       "properties": {"cmd": {"type": "string"}},
                       "required": ["cmd"]}}},
    {"type": "function", "function": {
        "name": "list_dir",
        "description": "列出目录下的文件名",
        "parameters": {"type": "object",
                       "properties": {"path": {"type": "string"}},
                       "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "search_code",
        "description": "在代码里搜索字符串/符号。输出分两段："
                       "=== DEFINITIONS (N) === 是**定义行**（def/class），"
                       "=== REFERENCES (N) === 是引用行。"
                       "★ 问「X 定义在哪个文件」时**只看 DEFINITIONS 段**，"
                       "答案就在那里。"
                       "★★ 定位符号**必须用这个工具**：不要用 run_command "
                       "跑自写的 python 搜索脚本（参数太长会被截断，"
                       "而且自己写的脚本常把定义误判成引用）。"
                       "不要用 list_dir 逐层翻目录。",
        "parameters": {"type": "object",
                       "properties": {"pattern": {"type": "string"},
                                      "path": {"type": "string"}},
                       "required": ["pattern"]}}},
    {"type": "function", "function": {
        "name": "find_files",
        "description": "按文件名通配符查找文件（如 *.py / README*），返回路径列表",
        "parameters": {"type": "object",
                       "properties": {"pattern": {"type": "string"},
                                      "path": {"type": "string"},
                                      "ignore_case": {"type": "boolean"}},
                       "required": ["pattern"]}}},
    {"type": "function", "function": {
        "name": "final_answer",
        "description": "任务完成时调用，提交最终答案（中文）",
        "parameters": {"type": "object",
                       "properties": {"answer": {"type": "string"}},
                       "required": ["answer"]}}},
]

# ★ R438 · client_tool 维度：从产物合并额外工具（只增不改，重名忽略）
try:
    from dwc.organs import evo_targets as _ET_T
    _extra_tools = _ET_T.read("client_tool").get("tools") or []
    _known = {t.get("function", {}).get("name") for t in TASK_TOOLS}
    for _t in _extra_tools:
        _n = (_t or {}).get("function", {}).get("name")
        if _n and _n not in _known:
            TASK_TOOLS.append(_t)
            _known.add(_n)
except Exception as _e:  # noqa: BLE001 — 产物坏不拦任务，但留痕
    import sys as _s
    _s.stderr.write("tools_extra 合并失败: %r\n" % (_e,))

#: 工具名 → 内部 op 名 + 参数改名
_TOOL_TO_OP = {
    "read_file": ("read", {"path": "path"}),
    "write_file": ("write", {"path": "path", "content": "content"}),
    "run_command": ("run", {"cmd": "cmd"}),
    "list_dir": ("run", {}),          # 转成 ls 命令
    "search_code": ("run", {}),       # 转成 grep 命令
    "find_files": ("run", {}),        # 转成 Python find（避开 Windows find.exe）
    "final_answer": ("final", {"answer": "answer"}),
}


#: ★★★ R391 · `find` 在 Windows 上会解析到 **C:\Windows\System32\find.exe**
#:   （语法完全不同：`find "str" file`），模型写的 GNU 写法
#:   `find src -type f -name *.py` 一律 rc=2「参数格式不正确」
#:   ⇒ 模型重试到复读熔断（现场 nb_1020_185347_28 / 185728_32 卡死）。
#:   修：`find` 一律转成等价的 Python 实现（不依赖 PATH 里哪个 find）。
_FIND_PY = (
    "import os,sys,fnmatch\n"
    "root=sys.argv[1]; pat=sys.argv[2]; ic=sys.argv[3]=='1'\n"
    "skip=" + repr(_FIND_SKIP_DIRS) + "\n"
    "n=0\n"
    "for d,ds,fs in os.walk(root):\n"
    "    ds[:]=[x for x in ds if x not in skip]\n"
    "    for f in fs:\n"
    "        a=f.lower() if ic else f; b=pat.lower() if ic else pat\n"
    "        if fnmatch.fnmatch(a,b):\n"
    "            print(os.path.join(d,f)); n+=1\n"
    "print('TOTAL',n)\n"
)


#: ★★★ R394 · `search_code` 用 Python 实现（不再走 grep）。
#:   现场（2026-10-20 20:19 全池）：某 code-locate 题「execute_user_task 定义在哪个文件」
#:   第一轮 grep 成功，之后连续 3 轮 ok=False（同一词搜不到）⇒ 复读熔断。
#:   根因：`grep -rn` 返回的是**所有引用**（几十行），定义行被淹没在
#:   调用点里；模型读不出"哪个是定义"，只好换个词再搜。
#:   修：定义（def/class X）**置顶**，引用**限流**，一眼就能看到答案。
_SEARCH_PY = (
    "import os,sys,re\n"
    "pat=sys.argv[1]; root=sys.argv[2]\n"
    "skip=" + repr(_REPO_SKIP_DIRS) + "\n"
    "rx_def=re.compile(r'^\\s*(?:async\\s+)?(?:def|class)\\s+'+re.escape(pat)+r'\\b')\n"
    "rx=re.compile(re.escape(pat))\n"
    "defs=[]; refs=[]; lines_hit=[]\n"
    # ★★★ R429 · 路径写错时**必须大声报错**，不能静默 0/0。
    #   现场（某 read-fact 题，12:53）：模型把 path 传成**文件**（`src/dwc/organs/memory.py`）
    #   或相对路径（`organs`）⇒ `os.walk` 什么都不遍历 ⇒ 打印
    #   `DEFINITIONS(0)/REFERENCES(0)` ⇒ 模型据此断定"仓库里没有这个符号"，
    #   最后只敢给一个"推测"而不是取证结论。
    #   ★ R432 · 注释里**不许写答案**（本仓库就是评测语料 —— 写进注释
    #     = 把答案递给模型；上面这句原稿写了类名，被模型搜到过一次）。
    #   0 命中 ≠ 符号不存在；**路径错必须与符号不存在可区分**。
    "if not os.path.exists(root):\n"
    "    print('=== PATH NOT FOUND: %s ===' % root); print('（路径不存在 —— 这不是"
    "“符号不存在”，请换成仓库内相对路径，如 src/dwc）'); sys.exit(3)\n"
    "files=[]\n"
    "if os.path.isfile(root): files=[root]\n"
    "else:\n"
    "    for d,ds,fs in os.walk(root):\n"
    "        ds[:]=[x for x in ds if x not in skip]\n"
    "        for f in fs:\n"
    "            if f.endswith('.py'): files.append(os.path.join(d,f))\n"
    "for p in files:\n"
    "    try: lines=open(p,encoding='utf-8',errors='replace').read().splitlines()\n"
    "    except Exception: continue\n"
    "    for i,l in enumerate(lines,1):\n"
    "        if rx_def.match(l): defs.append('%s:%d:%s'%(p,i,l.strip()[:120])); lines_hit.append(l)\n"
    "        elif rx.search(l): refs.append('%s:%d:%s'%(p,i,l.strip()[:120])); lines_hit.append(l)\n"
    "print('=== DEFINITIONS (%d) ===' % len(defs))\n"
    "for x in defs[:20]: print(x)\n"
    "print('=== REFERENCES (%d) ===' % len(refs))\n"
    "for x in refs[:30]: print(x)\n"
    # ★★★ R437 · 0/0 必须给方向，不能让模型把"搜不到"当成"不存在"。
    #   现场（全池 2 轮）：某 read-fact 题问 env 开关名，模型搜了多词短语 ⇒
    #   `DEFINITIONS (0) / REFERENCES (0)` ⇒ 它写下「检索结果均为 0/0」
    #   后放弃，或编一个名字。实际符号就在仓库里，只是它的检索词太长。
    #   ★ 这不是给答案：只是告诉它"换个搜法"，不透露任何标识符。
    "if not defs and not refs:\n"
    "    print('=== 0 命中（不等于不存在）===')\n"
    "    print('本工具按子串匹配：换更短的词根 / 换目录重搜，或改用 find_files 按文件名找。')\n"
    # ★★★ R430 · **检索词过泛**时给出"更长标识符"候选。
    #   现场（某 read-fact 题）：问"记忆修订的新节点用哪个保留键链回旧节点"，模型搜
    #   `prev` ⇒ 77 条引用、0 条定义 ⇒ 它把泛命中里的裸词当成了结果。
    #   0 定义 + 大量引用 = 这个词只是**更长标识符的一部分** ——
    #   把包含它的标识符按出现次数列出来，模型就能看到完整键。
    #   ★ R432 · 本注释原稿把两处正确键名都写出来了，模型搜到过它 ——
    #     **本仓库就是评测语料，注释不许写答案**。
    #   ★ 这不是"给答案"：候选是从**它自己搜到的行**里统计出来的，
    #     判据、闸、评分一律不变。
    "if not defs and lines_hit:\n"
    "    cnt={}\n"
    "    for l in lines_hit:\n"
    "        for m in re.findall(r'[A-Za-z_][A-Za-z0-9_]*', l):\n"
    "            if pat in m and m != pat: cnt[m]=cnt.get(m,0)+1\n"
    "    top=sorted(cnt.items(), key=lambda kv: (-kv[1], kv[0]))[:8]\n"
    "    if top:\n"
    "        print('=== 候选更长标识符（含 %s，按出现次数）===' % pat)\n"
    "        for k,v in top: print('%s  x%d' % (k,v))\n"
    "        print('（0 条定义但有引用 —— 检索词很可能只是上面某个标识符的一部分）')\n"
)


def _search_to_python(pat: str, path: str):
    """search_code ⇒ Python 实现（定义置顶 + 限流）。

    ★★★ R403 · **剥掉模型误带的 `def `/`class ` 前缀**。
    现场（某 code-locate 题，03:40）：模型传 `pattern="class MemoryKernel"`，
    定义正则变成 `class class MemoryKernel` ⇒ DEFINITIONS **0 条**，
    而原文匹配到 1 行 ⇒ 全落在 REFERENCES。模型据此认为"没有定义"，
    转头答了一个不存在的文件名。

    剥前缀后 `class MemoryKernel` ⇒ 定义 1 条 ⇒ 直接命中 memory.py。
    """
    p = str(pat or "").strip()
    _m = re.match(r"^(?:def|class)\s+(.+)$", p)
    if _m:
        p = _m.group(1).strip()
    # ★ 模型还会带尾巴：`class MemoryKernel:` / `def foo(` —— 尾部的
    #   `:` `(` 会让 `\b` 边界失效（`: ` 不是词字符）⇒ 定义又判 0 条。
    p = p.rstrip(":(").strip()
    return [sys.executable or "python", "-c", _SEARCH_PY, p, path]


def _find_to_python(toks: list):
    """把 `find PATH [-type f] [-name|-iname PAT]` 转成 Python argv。

    解析不了就返回 None（交给原命令，至少不改变语义）。
    """
    if not toks or str(toks[0]).lower() != "find":
        return None
    path = "."
    pat = "*"
    ic = False
    i = 1
    seen_path = False
    while i < len(toks):
        t = str(toks[i])
        if t in ("-name", "-iname") and i + 1 < len(toks):
            pat = str(toks[i + 1])
            ic = (t == "-iname")
            i += 2
            continue
        if t == "-type" and i + 1 < len(toks):
            i += 2          # 只支持 -type f；目录也无所谓，输出只列文件
            continue
        if not seen_path and not t.startswith("-"):
            path = t
            seen_path = True
        i += 1
    return [sys.executable or "python", "-c", _FIND_PY,
            path, pat, "1" if ic else "0"]


def _argv_of(cmd):
    """★★★ R384-fix · 把 `run_command` 的字符串拆成 argv 列表。

    现场：`run` op 严格要求 **argv 列表**（`cmd 必须是非空 argv 列表`），
    而原生工具的 `run_command(cmd: string)` 传的是字符串
    ⇒ 所有命令都报 `ok: False`（某 analyze 题 实测 `ls -la` 连挂两次）。

    ★ 必须用 `posix=True`：模型常传 `-E "max_round|max_rounds"` 这种
      带引号的串；`posix=False` 会**保留引号** ⇒ grep 收到
      `'"max_round|..."'`（带字面引号）⇒ 永远搜不到（已踩两次）。
      posix=True 会正确剥引号，且把反斜杠当转义 —— 本仓库路径统一用
      正斜杠，代价可接受。
    """
    if isinstance(cmd, list):
        toks = [str(x) for x in cmd]
    else:
        s = str(cmd or "").strip()
        if not s:
            return []
        try:
            import shlex
            toks = [t for t in shlex.split(s, posix=True) if t]
        except ValueError:
            # 引号不配对等病态输入 ⇒ 退回朴素切分（至少不炸）
            toks = s.split()
    # ★★★ 管道/重定向/串联：`run` op **不经 shell**，这些符号只会被当
    #   字面参数传给命令 ⇒ 必然失败；过 shell 又是注入面。
    #   现场：模型爱写 `grep ... | head -20` / `ls; find . -name x`
    #   （**没有空格**时 shlex 切出 `'ls;'`，不是可执行文件 ⇒ 卡死）。
    #
    #   ★ 必须在 **token 层**处理，不能在字符串层按 `|` 切：
    #     `-E "max_round|max_rounds"` 里的 `|` 是 grep 的**交替模式**，
    #     按字符串切会把模式切坏（已踩）。shlex 已把引号内当整体。
    _SEPS = ("||", "&&", "|", ";", ">>", ">", "2>", "&")

    def _is_boundary(t):
        """token 是**独立**分隔符，或以分隔符**结尾/开头**（`ls;` / `;ls`）。

        ★ 不认"中间夹着"的写法：`max_round|max_rounds` 是 grep 的交替
          模式，必须原样保留（已踩 —— 按中间 `|` 切会把模式切坏）。
        """
        if t in _SEPS:
            return True
        return any(t.endswith(s) or t.startswith(s) for s in _SEPS)

    def _split_cmd_tok(t):
        """命令位置 token 若以分隔符结尾（`ls;`），返回 (头, 是边界)。"""
        for sep in _SEPS:
            if t.endswith(sep):
                return t[:-len(sep)], True
            if t.startswith(sep):
                return "", True
        return t, False

    i = 0
    while i < len(toks):
        # `cd` / `pushd` 是 shell 内建（Windows 无 cd.exe），cwd 固定为仓库根
        # ⇒ 跳过这一段，继续找下一条真命令（`cd . && ls -la` ⇒ 跑 `ls -la`）
        if toks[i].strip("\"'").lower() in ("cd", "pushd"):
            i += 1
            while i < len(toks) and not _is_boundary(toks[i]):
                i += 1
            i += 1                      # 跳过该边界 token
            continue
        head, had_sep = _split_cmd_tok(toks[i])
        if had_sep:
            seg = [head] if head else []
        else:
            seg = list(toks[i:])
            for j, t in enumerate(seg):
                if t in _SEPS:
                    seg = seg[:j]
                    break
        # ★★★ R391 · `find` ⇒ Python 实现（Windows 的 find.exe 语法不同）
        _f = _find_to_python(seg)
        return _f if _f is not None else [x for x in seg if x]
    return []


def _tool_calls_to_step(tool_calls: list):
    """★★★ R384 · 原生 tool_calls → 内部 step dict（复用既有 dispatch）。

    只做**转换**，不改执行路径 —— 既有 op 白名单/沙箱/审计全部保留。
    """
    if not tool_calls:
        return None
    tc = tool_calls[0] or {}
    fn = tc.get("function") or {}
    name = fn.get("name") or ""
    if name not in _TOOL_TO_OP:
        return None
    op, mapping = _TOOL_TO_OP[name]
    raw = fn.get("arguments")
    try:
        args = json.loads(raw) if isinstance(raw, str) else (raw or {})
    except (ValueError, TypeError):
        args = {}
    if not isinstance(args, dict):
        args = {}
    if name == "list_dir":
        return {"op": "run", "readonly": True, "_from_tool": True,
                "cmd": ["ls", "-la", str(args.get("path") or ".")]}
    if name == "run_command":
        return {"op": "run", "cmd": _argv_of(args.get("cmd"))}
    if name == "search_code":
        pat = str(args.get("pattern") or "")
        path = str(args.get("path") or "src")     # ★ 默认只搜 src（全仓 grep 太慢）
        if not pat:
            return None
        # ★★★ R394 · 改用 Python 实现：定义置顶 + 引用限流
        #   （grep 会把定义埋在几十行引用里 ⇒ 模型读不出答案，反复重搜）
        return {"op": "run", "readonly": True, "_from_tool": True,
                "cmd": _search_to_python(pat, path)}
    if name == "find_files":
        pat = str(args.get("pattern") or "")
        path = str(args.get("path") or ".")
        if not pat:
            return None
        return {"op": "run", "readonly": True, "_from_tool": True,
                "cmd": _find_to_python(
                    ["find", path, "-name", pat] if not args.get("ignore_case")
                    else ["find", path, "-iname", pat])}
    step = {"op": op}
    for src_k, dst_k in mapping.items():
        if src_k in args:
            step[dst_k] = args[src_k]
    return step


#: ★★★ R385 · 原生工具模式的硬轮数上限。
#:   现场：某 read-fact 题 在 `max_rounds=999` 下跑 **140 轮 / 278 动作 / 625 秒**
#:   还给出空答案；同批 某 read-fact 题 只要 2 轮 6.5 秒。不是慢，是死循环。
#:   一个任务烧 10 分钟 ⇒ 52 单 9 小时且答案为空。
NATIVE_TOOLS_MAX_ROUNDS = 15

#: ★★★ R385 · 同一 (op,target) 重复达到此次数 ⇒ 下一轮强制 final。
NATIVE_TOOLS_REPEAT_LIMIT = 4


def _use_native_tools() -> bool:
    """★★★ R384 · 是否走原生 tool calling（默认开；可 env/config 关掉）。

    关闭方式（排障用）：`DWC_LLM_NATIVE_TOOLS=0`。
    走哪条路会写进报告（`tool_mode`），降级与成功可区分。
    """
    v = os.environ.get("DWC_LLM_NATIVE_TOOLS")
    if v is not None:
        return v.strip().lower() not in ("0", "false", "no", "off")
    return True


def _tools_unsupported(res) -> bool:
    """★★ 端点不认识 `tools` 参数（400 / unknown field）⇒ 可诚实回退。"""
    err = str(getattr(res, "error", "") or "").lower()
    code = (getattr(res, "meta", None) or {}).get("http_code")
    if code == 400 and ("tool" in err or "unknown" in err or "invalid" in err):
        return True
    return ("tool" in err and ("unsupported" in err or "not support" in err
                               or "unknown" in err))


def _extract_json(text: str):
    """★ R217 · LLM 响应 JSON 鲁棒提取（判据: 拿到能用的 dict, 不苛求纯净）。

    容错序（bench llm_format 失败实测形态）:
    ① 整体 json.loads
    ② 剥 ```json / ``` 代码块包裹
    ③ 从后往前逐行 json.loads（模型常在 JSON 后追加说明文本）
    ④ 首个 { 到最后一个 } 的子串
    全失败返回 None（不猜不编 — 提取的是模型给的, 不是造的）。
    """
    t = (text or "").strip()
    if not t:
        return None
    for cand in (t, t.strip("`"), t.replace("```json", "").replace("```", "").strip()):
        try:
            o = json.loads(cand)
            if isinstance(o, dict):
                return o
        except Exception:                      # noqa: BLE001
            pass
    for ln in reversed(t.splitlines()):
        ln2 = ln.strip().strip("`").strip()
        if not ln2:
            continue
        try:
            o = json.loads(ln2)
            if isinstance(o, dict):
                return o
        except Exception:                      # noqa: BLE001
            continue
    a, b = t.find("{"), t.rfind("}")
    if 0 <= a < b:
        try:
            o = json.loads(t[a:b + 1])
            if isinstance(o, dict):
                return o
        except Exception:                      # noqa: BLE001
            pass
    return None


#: R225 · 实时审批等待上限（秒）—— 超时=拒绝（不无限挂线节）
ASK_WAIT = int(os.environ.get("DWC_ASK_WAIT", "900"))
#: G7 静默计数（ask 链路的 except: pass 必须有计数 — 门判据）
_ASK_SILENT = [0]


def _ask_hush(where: str, exc: Exception) -> None:
    _ASK_SILENT[0] += 1
    if _ASK_SILENT[0] <= 3:
        import sys as _sys
        _sys.stderr.write("ask 链路静默×%d @%s: %s\n"
                          % (_ASK_SILENT[0], where, exc))
ASK_PENDING = os.path.join(ROOT, "var", "dwc_ask.jsonl")
ASK_ANSWERS = os.path.join(ROOT, "var", "dwc_ask_answers.jsonl")


def _notify_feishu(text: str) -> None:
    """轻量飞书通知 — 委托 agent_rpc.send_feishu（单实现防漂移）。"""
    try:
        from dwc.agent_rpc import send_feishu
        send_feishu(text)
    except Exception:                           # noqa: BLE001
        pass


def _ask_human(ask_word: str, cmd_joined: str, tid: str):
    """★ R225 · 实时审批: pending → 飞书问 → 轮询答复。返回 True=批准,
    'timeout'/'denied:<词>'=拒绝。等待期线程挂起（R219 异步接单后主循环
    不受影响 — Semaphore 名额占用见 runbook 诚实边界）。"""
    # ★ 路径守卫: pending 只许落 var/ 生产区（防测试/错配置泄漏写错位置）
    _var = os.path.normpath(os.path.join(ROOT, "var"))
    if not os.path.normpath(os.path.dirname(ASK_PENDING)).startswith(_var):
        raise TaskExecError("ASK_PENDING 不在 var/ 下（路径错乱拒写）: %s"
                            % ASK_PENDING)
    try:
        os.makedirs(os.path.dirname(ASK_PENDING), exist_ok=True)
        with io.open(ASK_PENDING, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"task_id": tid, "word": ask_word,
                                 "cmd": cmd_joined[:200],
                                 "ts": time.strftime("%Y-%m-%dT%H:%M:%S+08:00")},
                                ensure_ascii=False) + "\n")
        _notify_feishu("🖐 DWC 请求授权\n任务: %s\n操作: %s\n"
                       "回复『授权 %s』或『拒绝 %s』（我经 RPC 转达）"
                       % (tid or "?", cmd_joined[:200], ask_word, ask_word))
    except OSError as exc:
        _ask_hush("pending落盘/通知", exc)
    t0 = time.time()
    while time.time() - t0 < ASK_WAIT:
        try:
            if os.path.exists(ASK_ANSWERS):
                lines = io.open(ASK_ANSWERS, encoding="utf-8").read().splitlines()
                hit_idx = None
                approved = False
                for i, ln in enumerate(lines):
                    if not ln.strip():
                        continue
                    a = json.loads(ln)
                    if str(a.get("word", "")).strip() == ask_word.strip():
                        hit_idx, approved = i, bool(a.get("approve"))
                        break
                if hit_idx is not None:
                    # ★ 一次性消费: 匹配答复即从文件移除（旧授权不永久有效 —
                    #   一次授权只放行一次等待中的操作, 下次 ask 重新问）
                    rest = [x for i, x in enumerate(lines)
                            if i != hit_idx and x.strip()]
                    with io.open(ASK_ANSWERS, "w", encoding="utf-8") as fh:
                        fh.write("".join(x + "\n" for x in rest))
                    if approved:
                        return True
                    return "denied:%s" % ask_word
        except (OSError, ValueError) as exc:
            _ask_hush("答复轮询读", exc)
        time.sleep(5)
    return "timeout(%.0fs)" % ASK_WAIT


def _parse_confirmed(ctx: Optional[str]) -> set:
    """★ R222 · 人工授权解析: ctx 里 '人工授权: <词>' 行 → 放行词集合。"""
    out = set()
    for ln in (ctx or "").splitlines():
        if ln.strip().startswith("人工授权:"):
            out.add(ln.split("人工授权:", 1)[1].strip())
    return out


def _revise_step(*, llm: Any, task: str, step: Dict[str, Any], why: str,
                 recent: List[Dict[str, Any]],
                 qa_mode: bool = False) -> Optional[Dict[str, Any]]:
    """★ State Revision 轻量版（2609.28416 §2.3）: 对 noisy 提案重写一次。

    ★ 每次判别**只调一次**; 失败返回 None ⇒ 调用方 fallback 保留原提案
      （EditAct _fallback 纪律 — 修订器故障绝不卡任务）。
    ★ 修订禁产 final（validate allow_final=False — 终局分支已结算）。
    """
    _plat = ("本机Windows无grep/ls/curl管道、无shell管道符;"
             "搜文件用python -c(os.walk)，命令必须是argv列表。"
             if os.name == "nt" else "")
    prompt = (
        _plat + "你在执行任务, 上一步被判为噪声动作。\n"
        "任务: %s\n"
        "噪声动作: %s\n"
        "判别原因: %s\n"
        "最近动作观察: %s\n"
        # ★ R302补5 · qa 下修订只许 read（通用模板劝 run⇒qa 必驳回，
        #   T_R302Z 现场 10 轮驳回耗尽轮数。约束前移到产出端）。
        % (task,
           # ★★★ R405 · `default=str` 必须加 —— `step` 里带 `_confirmed`
           #   （set 类型，人工授权词集合），裸 `json.dumps` 必抛
           #   `TypeError: Object of type set is not JSON serializable`。
           #   现场（某 run-verify 题）：模型执行 gate.py 被拦成噪声 → 构造重写提示时炸
           #   → 模型看到"命令失败"→ 放弃 → 判 ✗。
           json.dumps({k: v for k, v in step.items()
                       if k != "analysis"}, ensure_ascii=False,
                      default=str)[:400],
           why[:200],
           json.dumps(recent[-3:], ensure_ascii=False, default=str)[:900])
        + ("问答任务只许取证：op 只能是 read（给 path），不要 final。"
           "只输出 JSON: {\"analysis\": \"…\", \"op\": \"read\", "
           "\"path\": \"…\"}" if qa_mode else
           "请**换一条路径/换参数/换动作类型**重写下一步（不要重复噪声动作, "
           "不要 final）。只输出 JSON: {\"analysis\": \"…\", \"op\": "
           "\"read|write|run\", \"path\": \"…\"（read/write）, \"cmd\": "
           "\"…\"（run）}"))
    try:
        r = llm.complete(prompt, json_mode=True)
        if not getattr(r, "ok", False):
            return None
        obj = json.loads(r.text or "{}")
        if not isinstance(obj, dict) or not obj.get("op"):
            return None
        return obj
    except Exception as exc:             # noqa: BLE001 — fallback 但**留痕**
        # ★ G7: 曾静默吞 TypeError（complete 无 tag 参数 — B 臂 46 次修订
        #   全灭的根因）— 吞掉的异常必须可见
        sys.stderr.write("revise_step 失败(保留原提案): %s: %s\n"
                         % (type(exc).__name__, exc))
        return None


_SRC_FAIL = globals().setdefault("_SOURCES_FAIL", [0])   # G7: 沉淀失败必须计数


def _extract_sources(log: List[Dict[str, Any]], *, task_id: str, task: str,
                     answer: str = "", artifacts: Optional[List[str]] = None) -> None:
    """★ R266A · 任务知识沉淀: actions_log 的 web_search/web_read 信源 +
    final 结论/产物 → dwc_sources.jsonl; 论文类 URL 分拣进 dwc_reading_list
    （C 层进化投单的候选池）。G7: 写失败计数+stderr, 不阻断主链。"""
    queries: List[str] = []
    urls: List[Dict[str, str]] = []
    for row in log:
        if not isinstance(row, dict) or row.get("phase") != "obs":
            continue
        op = row.get("op")
        target = str(row.get("target") or "")
        obs: Dict[str, Any] = {}
        try:
            obs = json.loads(row.get("obs") or "{}")
        except (ValueError, TypeError):
            obs = {}
        if op == "web_search":
            if target:
                queries.append(target[:200])
        elif op == "web_read" and target.startswith(("http://", "https://")):
            low = target.lower()
            kind = ("paper" if ("arxiv.org" in low or low.endswith(".pdf")
                                or "openreview.net" in low)
                    else "doc")
            urls.append({"url": target, "kind": kind,
                         "snippet": str(obs.get("content", ""))[:300]})
    if not queries and not urls and not (answer or "").strip():
        return                       # 零信源零发现不写（不刷账本）
    rec = {"task_id": task_id, "at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
           "task": task[:300], "queries": queries[:10], "urls": urls[:20],
           "findings": (answer or "")[:600],
           "artifacts": list(artifacts or [])[:10]}
    try:
        os.makedirs(os.path.dirname(SOURCES), exist_ok=True)
        with io.open(SOURCES, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        papers = [u for u in urls if u["kind"] == "paper"]
        if papers:
            known = set()
            if os.path.exists(READING):
                for ln in io.open(READING, encoding="utf-8"):
                    ln = ln.strip()
                    if ln:
                        try:
                            known.add(json.loads(ln).get("url", ""))
                        except (ValueError, TypeError):
                            continue
            with io.open(READING, "a", encoding="utf-8") as fh:
                for u in papers:
                    if u["url"] not in known:
                        fh.write(json.dumps(
                            {"url": u["url"], "first_seen": rec["at"],
                             "task_id": task_id, "dispatched_at": None},
                            ensure_ascii=False) + "\n")
    except OSError as exc:           # G7: 记不了不许杀主链, 也不许无痕
        _SRC_FAIL[0] += 1
        if _SRC_FAIL[0] <= 3:
            import sys as _sys
            _sys.stderr.write("sources 沉淀失败×%d: %s\n"
                              % (_SRC_FAIL[0], exc))


def _revision_retry(*, task: str, fail: Dict[str, Any], llm: Any,
                    sid: str, progress: Any = None) -> Optional[Dict[str, Any]]:
    """★ R256 · 任务级修订重试（2609.28416 §3.3 AEWM-RFT 数据策略的 DWC 落地）。

    失败任务 → LLM 基于失败留痕**重写任务理解** → 二跑（不再三跑, 防循环）。
    二跑仍失败也返回二跑结果（带 revised 标 — 失败现场更有信息）。
    revision_pair 供调用方入记忆（correction 轨迹比成功轨迹多学东西 — §3.3）。
    """
    global _PAIRS_FAIL
    try:
        prompt = (
            "上一个任务执行失败, 请**重写任务**（更小步/更明确/补上缺失前提）"
            "让下一次执行能走通。只输出 JSON: {\"revised_task\": \"…\"}\n"
            "原任务: %s\n失败状态: %s\n失败原因: %s\n已做动作: %s"
            % (task, fail.get("status"), str(fail.get("why", ""))[:300],
               json.dumps([{"op": e.get("op"),
                            "ok": e.get("ok"),
                            "t": str(e.get("target", ""))[:60]}
                           for e in (fail.get("actions_log") or [])
                           if isinstance(e, dict) and e.get("phase") == "obs"][-8:],
                          ensure_ascii=False)[:1200]))
        r = llm.complete(prompt, json_mode=True)
        obj = json.loads(r.text or "{}") if getattr(r, "ok", False) else {}
        revised = str(obj.get("revised_task", "")).strip()
        if not revised or revised == task.strip():
            return None                    # 修订无产出 ⇒ 不重跑
    except Exception:                      # noqa: BLE001 — 修订失败=不重跑
        return None
    if progress:
        progress({"ev": "revision_retry", "revised": revised[:200]})
    try:      # _sess 是 execute_user_task 闭包 — 模块级直写同款文件
        os.makedirs(SESSIONS, exist_ok=True)
        with io.open(os.path.join(SESSIONS, sid + ".jsonl"), "a",
                     encoding="utf-8") as fh:
            fh.write(json.dumps({"at": time.strftime("%H:%M:%S"),
                                 "phase": "task_revision", "original": task[:200],
                                 "revised": revised[:200],
                                 "fail_why": str(fail.get("why", ""))[:200]},
                                ensure_ascii=False)[:2000] + "\n")
    except OSError:
        _PAIRS_FAIL += 1   # ★ G7: 留痕失败计数（_sess_fails 同族）
    res2 = execute_user_task(revised, llm=llm, task_id=sid + "_r1",
                             retry_on_fail=False, progress=progress)
    res2["revised"] = True
    res2["revision_pair"] = {
        "original_task": task, "revised_task": revised,
        "fail_why": str(fail.get("why", ""))[:300],
        "fail_status": fail.get("status"),
        "retried_status": res2.get("status"),
        "retried_ok": res2.get("status") == "done"}
    try:
        with io.open(os.path.join(SESSIONS, sid + ".jsonl"), "a",
                     encoding="utf-8") as fh:
            fh.write(json.dumps({"at": time.strftime("%H:%M:%S"),
                                 "phase": "task_revision_result",
                                 "task_id": sid + "_r1",
                                 "status": res2.get("status")},
                                ensure_ascii=False)[:2000] + "\n")
    except OSError:
        _PAIRS_FAIL += 1   # ★ G7: 留痕失败计数（_sess_fails 同族）
    # ★ 修订对落盘（retention 4 臂的候选原料 — 接入留后续轮, 诚实 gap）
    try:
        pair_p = PAIRS_PATH or os.path.join(
            os.environ.get("DWC_VAR_DIR") or os.path.join(ROOT, "var"),
            "dwc_pairs.jsonl")
        os.makedirs(os.path.dirname(pair_p), exist_ok=True)
        with io.open(pair_p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(res2["revision_pair"], ensure_ascii=False) + "\n")
    except Exception as exc:               # noqa: BLE001 — G7: 计数不静默
        _PAIRS_FAIL += 1
        sys.stderr.write("dwc_pairs 落盘失败(%d): %s\n" % (_PAIRS_FAIL, exc))
    return res2


def execute_user_task(task: str, *, llm: Any, max_rounds: int = 999,
                      ctx: Optional[str] = None,
                      task_id: Optional[str] = None,
                      _depth: int = 0,
                      retry_on_fail: bool = True,
                      progress: Optional[Any] = None) -> Dict[str, Any]:
    """★ 接单执行: 任务描述 → 多轮 LLM+白名单动作 → final 结果。

    返回报告 dict: {task_id?/task, status, rounds, answer, artifacts,
    actions_log, why} — status ∈ {done, incomplete}。
    """
    # ★★★ R385 · 原生工具模式硬上限（某 read-fact 题 实测 140 轮 / 625 秒 / 空答案）。
    #   `max_rounds=999` 是给 JSON 路径的历史宽松值；原生工具会死循环。
    if _use_native_tools() and max_rounds > NATIVE_TOOLS_MAX_ROUNDS:
        max_rounds = NATIVE_TOOLS_MAX_ROUNDS
    os.makedirs(WORK, exist_ok=True)
    # ★ R218 · 自我认知注入（每次接单加载, 跨任务存活 — CLAUDE.md 同款;
    #   文件缺席=空串不装有, 读失败不炸单）
    self_md = ""
    try:
        if os.path.exists(SELF_MD):
            self_md = io.open(SELF_MD, encoding="utf-8").read()[:4000]
    except OSError:
        self_md = ""
    # ★ R218 · 会话留痕（session 概念最小形态: 每任务一个 jsonl, 轮转可查）
    sid = (task_id or ("T_" + time.strftime("%m%d_%H%M%S")))
    sess_path = os.path.join(SESSIONS, sid + ".jsonl")

    _sess_fail = globals().setdefault("_SESS_FAIL", [0])   # G7: 静默必须计数

    def _sess(ev: Dict[str, Any]) -> None:
        try:
            os.makedirs(SESSIONS, exist_ok=True)
            with io.open(sess_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"at": time.strftime("%H:%M:%S"), **ev},
                                    ensure_ascii=False)[:2000] + "\n")
        except OSError as exc:               # 留痕失败不阻断主链, 但必须计数
            _sess_fail[0] += 1               # （G7: 记不了不许杀主链, 也不许无痕）
            if _sess_fail[0] <= 3:           # 前 3 次写 stderr（不刷屏）
                import sys as _sys
                _sys.stderr.write("session 留痕失败×%d: %s\n"
                                  % (_sess_fail[0], exc))
    system = (
        "你是 DWC 独立 agent 的任务执行体。完成用户的任务。每轮只输出一个"
        " JSON 对象（无多余文本）: {\"analysis\": \"本步思考\", \"op\":"
        " \"read|write|run|final\", ...参数}。"
        # ★★★ R384 · 原生工具模式下必须换口径（旧口径会让模型困惑）
        " 【原生工具模式】你已挂载函数工具：read_file / write_file /"
        " run_command / list_dir / search_code / find_files / final_answer。"
        "**必须调用工具**，"
        "不要在正文里描述「我将要做什么」或「已做了什么」——"
        " 只有真正调用工具才算执行。"
        # ★★★ R391 · 探索策略（code-locate 20% 的主因是"逐层 ls"）
        " ★★ 定位策略（找「X 定义在哪个文件/哪一行」）:"
        " **第一步就用 search_code(pattern='X')**，它会直接给出"
        "「文件:行号:内容」；**不要用 list_dir / ls 逐层翻目录**"
        "（现场：反复 `ls -la .` 直到复读熔断，11 轮零进展）。"
        " 找不到再放宽: 换符号名/换路径 path='.'; 找文件用 find_files。"
        # ★★★ R400 · 现场（某 code-locate 题/某 code-locate 题/某 code-locate 题/某 code-locate 题）：模型不用 search_code，
        #   改用 run_command 跑**自写的 python 搜索脚本** —— ①参数太长被截断
        #   ②自己的脚本把『MemoryKernel 的定义行』归到 REFERENCES ⇒ 答不出。
        " ★★★ **绝对不要**用 run_command 跑自写的 python/grep 搜索脚本："
        "参数太长会被截断，而且自己写的分类逻辑常把定义误判成引用。"
        "search_code 的输出里 **=== DEFINITIONS 段就是答案**。"
        # ★ R400 · 某 code-locate 题 现场：DEFINITIONS(1) 已给出 effort.py，但后续一次
        #   工具报错后模型**撤回了正确答案**并拒答 ⇒ 证据一旦到手就别撤回。
        " 一旦 DEFINITIONS 段给出了文件，**直接用它作答**；"
        "后续工具报错不代表已有证据失效，不要因此撤回正确答案。"
        # ★ R400-d · 某 code-locate 题 现场：问「CLI 入口路由文件叫什么」——没有符号名，
        #   模型反复搜不存在的符号、find TOTAL 0，最后拒答。
        " 若问题**没有给出符号名**（如「入口/路由/配置文件叫什么」）："
        "用 find_files(pattern='cli*') 或 search_code(pattern='ArgumentParser')"
        " / 'add_parser' 这类**结构性特征**去定位，不要凭空猜文件名。"
        " ★ 不要在 Windows 上直接用 `find`（会命中 Windows 的 find.exe，"
        "语法不同必失败）—— 用 find_files 工具。"
        " 任务完成时立即调用 final_answer，**不要反复验证同一件事**"
        "（一次成功即收工；实测 26 轮里有 20 轮是多余自证）。"
        " · 读文件: {\"op\":\"read\",\"path\":\"相对路径\"}"
        " · 写文件(只许 var/inbox_work/ 下): {\"op\":\"write\",\"path\":"
        "\"var/inbox_work/x.md\",\"content\":\"...\"}"
        " · 跑命令(argv列表,60s超时): {\"op\":\"run\",\"cmd\":[\"python\",\"-c\",\"...\"]}"
        " · 抓网页(研究查资料; http/https, 20s超时, 自动转纯文本):"
        " {\"op\":\"web_read\",\"url\":\"https://...\"}"
        " · 搜索(研究起点=查 X; 免 key, 返回 Top 标题+URL+摘要, "
        "拿到 URL 再 web_read 抓正文):"
        " {\"op\":\"web_search\",\"query\":\"关键词\"}"
        " · 调 MCP 外部工具（标准协议口; server 须在 config/mcp.json 配）:"
        " {\"op\":\"mcp\",\"server\":\"名\",\"tool\":\"工具名\",\"args\":{}}"
        " · 派独立子代理（隔离上下文做子研究, 返回摘要; 限 1 层）:"
        " {\"op\":\"delegate\",\"task\":\"子任务描述\"}"
        " · 任务完成时: {\"op\":\"final\",\"answer\":\"结论(中文)\","
        "\"artifacts\":[\"写出的文件相对路径\"]}"
        " 有充分信息就尽快 final；不确定就先 read 探查。禁止越权写路径。"
        " · read 截断提示: obs 带 truncated/hint 时用同 path+offset=行号"
        " 翻页读后面（★ 没有 offset 参数时永远只会读到同一段 — "
        "禁止原地重读）。"
        " ★ 运行环境: 本机是 Windows 主机, cmd 是**原生 argv 直接执行**"
        "（无 wsl、无 bash、不要经任何 shell 包装）; python 可直接用"
        "（['python', '-c', ...]）; 命令输出按 utf-8 解码。"
        " ★ 复读熔断: 连续做同一个动作读到同样结果说明此路不通 — "
        "换 offset/换路径/换参数, 或基于已有信息尽快 final, 不要原地重复。")
    # ★ R306 · prompt OTA（文件基线命中则覆盖；缺失⇒内嵌老路一字不差）。
    try:
        from dwc.llm.prompt_ota import ota_system as _ota
        system = _ota("task_exec", system, __file__, key=str(sid or task))
    except Exception as _ota_e:     # 留痕不炸单（G7）
        _sess({"phase": "ota_miss", "why": str(_ota_e)[:80]})
    if self_md:
        system += ("\n\n# 自我认知（你的持久记忆文件, 每单加载）\n" + self_md)
    # ★ R301-C · qa 分流（纯问句⇒直答通道；规则 fail-closed，边界走执行路）。
    from dwc.llm.step_judge import is_qa_task
    qa_mode = is_qa_task(task)
    _sess({"phase": "task_mode", "qa_mode": qa_mode})
    # ★ R301-C · qa 直答句（运行时拼接，system 原文不动）。
    #   问答任务完成标准就是答案：首轮信息足可直接 final（≥10 字）。
    if qa_mode:
        system += ("\n★ 本题是问答：有充分信息首轮可直接 final（answer≥10 字，"
                   "中文）；需依据先 read 再答，不编空话。")
    # ★ R266B · 任务记忆注入（同 self_md 语义=持久记忆每单加载; lessons
    #   属外部管线 ctx 保持 A/B 口径不变, sources 归"记忆文件"族内部注入。
    #   检索/写入失败留痕不炸单 — G7）
    try:
        from dwc.agent_quality import sources_context
        _sc = sources_context(task)
        if _sc:
            system += ("\n\n# 任务记忆（你此前找到的相关信源/知识）\n" + _sc)
    except Exception as _exc:        # noqa: BLE001
        _SRC_FAIL[0] += 1
        if _SRC_FAIL[0] <= 3:
            import sys as _sys
            _sys.stderr.write("sources_context 注入失败×%d: %s\n"
                              % (_SRC_FAIL[0], _exc))
    # ★ R438 · skill 维度：把匹配到的技能正文拼进 system
    #   （改前 Mutator.SKILLS 既无落盘也无消费者 ⇒ 技能维度不存在）
    try:
        from dwc.organs import skill_store as _SS
        _sk = _SS.context(task, k=1)
        if _sk:
            system += "\n\n# 技能（已验证的做法）\n" + _sk
    except Exception as _exc2:      # noqa: BLE001 — 坏不拦任务，但留痕
        _SRC_FAIL[0] += 1
        if _SRC_FAIL[0] <= 3:
            import sys as _sys2
            _sys2.stderr.write("skill 注入失败×%d: %s\n"
                               % (_SRC_FAIL[0], _exc2))
    log: List[Dict[str, Any]] = []
    dup_sigs: List[str] = []   # ★ R247 复读熔断: (op|target|obs哈希) 滑窗
    #: ★ R384 · 原生工具模式下"只输出正文不调工具"的已重试次数（上限 1）
    _native_nudge = [0]
    #: ★ R396 · 强制 final 的状态（熔断后给一次机会，仍不提交才判死）
    _ff_used = [0]
    _ff_pending = [False]
    _last_rev_sig: Optional[str] = None   # ★ R255 修订去重（连续同签名⇒fallback）
    _r302_strikes = 0   # ★ R302 · 同任务引用打回计数（≥2 放行防死循环）
    #: ★★★ R418 · 每个闸**各自**的打回额度（闸之间不许互相吃掉）
    _gate_strikes: dict = {}
    _r4_blanks = 0      # ★ R302补5b · R4 无 op 连空计数（≥3 诚实收敛）
    last_image: Optional[str] = None   # ★ R226: 最近读到的图（下轮挂给 LLM）
    prompt = "任务: %s\n%s" % (task, ("\n上下文: " + ctx) if ctx else "")
    for rnd in range(1, max_rounds + 1):
        obs: Dict[str, Any] = {}   # ★ R247: final 轮不走 _do_action —
        #   每轮开头重置, 留痕段引用不至 UnboundLocal
        if progress:
            progress({"ev": "round", "n": rnd})
        _imgs = [last_image] if last_image else None
        # ★ R301-F · qa 取证上限（read 尝试≥4 仍不 final⇒硬推收敛。
        #   现场：R5 拦 run 后改 read×10 不答——收集无上限；
        #   补丁：计尝试数（失败的瞎探也算，不能靠失败续命）。
        if qa_mode:
            _n_read = sum(1 for e in log
                          if isinstance(e, dict) and e.get("phase") == "obs"
                          and e.get("op") == "read")
            if _n_read >= 4:
                prompt = ("任务: %s\n已取证 %d 次（read 成功）。不要再收集，"
                          "现在基于已有信息直接 final 作答（answer≥10 字中文）。"
                          % (task, _n_read))
        # ★★★ R385 · 原生工具模式的死循环防护（某 read-fact 题 实测 140 轮/625 秒）。
        #   两个出口：
        #   ① 同一 (op,target) 重复 ≥ NATIVE_TOOLS_REPEAT_LIMIT ⇒ 强制 final
        #   ② 轮数逼近上限 ⇒ 强制 final（给一次收尾机会）
        _force_final = False          # ★ R396 · 每轮先归零
        if _ff_pending[0]:            # ★ 上一轮熔断 ⇒ 本轮强制 final
            _force_final = True
            _ff_pending[0] = False
        if _use_native_tools():
            # ★ R441 · 三段式预算：先按当前轮次取阶段与提醒
            _tb = tool_budget()
            _stage = _budget.stage_of(rnd, _tb)
            _rem = _budget.reminder(rnd, _tb)
            if _rem:
                # ★ 只追加，不重写 —— 提醒是给"这一轮的观测"加的，不是换系统提示
                prompt = prompt + "\n\n" + _rem
            _rep_cnt: dict = {}
            for e in log or []:
                if isinstance(e, dict) and e.get("phase") == "obs":
                    _k = (e.get("op"), str(e.get("target") or "")[:80])
                    _rep_cnt[_k] = _rep_cnt.get(_k, 0) + 1
            _max_rep = max(_rep_cnt.values()) if _rep_cnt else 0
            if (_max_rep >= NATIVE_TOOLS_REPEAT_LIMIT
                    or _stage == "finalize"):
                # ★ 追加而不是覆盖 —— qa_mode 的取证上限提示要保留
                #   （覆盖会让两套收敛信号互相抵消，test_r301f 抓到过）
                # ★ R441 · 两种触发原因必须说清（否则"重复 1 次"是假话）
                if _stage == "finalize":
                    _why = ("★ 工具预算已用完（第 %d 轮），停止收集/执行。"
                            % (rnd,))
                else:
                    _why = ("★ 停止收集/执行。同一动作已重复 %d 次"
                            "（本轮第 %d 轮），继续重复不会得到新信息。"
                            % (_max_rep, rnd))
                prompt = (prompt + "\n\n" + _why + "\n"
                          "**现在立即调用 final_answer** 提交你目前掌握的最佳答案"
                          "（answer≥10 字中文）。不要再调用 read_file / "
                          "run_command / search_code。")
                # ★★★ R396 · 光靠提示词不够 —— 现场（21:35 全池）模型
                #   已经 read 到答案（`read memory.py ok=True`）却继续重复
                #   同一搜索 3 次，直到复读熔断判 incomplete。
                #   ⇒ 卡住时用 **tool_choice 强制 final_answer**（API 层硬约束，
                #   不依赖模型自觉）。端点不支持就自动退回 auto。
                _force_final = True
        # ★ R237 token 级流式: 有 progress 且 client 支持 ⇒ SSE 流,
        #   每 delta 发 token 事件（chat 端状态机提取 answer 流式打印;
        #   中间轮 JSON 无 answer 键 ⇒ 天然静默, final 轮才见逐字输出）
        # ★★★ R384 · 原生 tool calling 优先。
        #   端点实测正常返回 `finish=tool_calls` + 结构化参数；旧的手拼
        #   JSON 提示词逼模型输出散文 ⇒ 全池 51/54 = 94% 零动作。
        #   流式与 tool_calls 不兼容（要解析 delta 里的 tool_call 分片），
        #   故工具路径走非流式；非工具路径保持原流式行为。
        _native = _use_native_tools()
        if _native:
            try:
                _tc = ("auto" if not _force_final else
                       {"type": "function",
                        "function": {"name": "final_answer"}})
                res = llm.complete(prompt, system=system,
                                   tools=TASK_TOOLS, tool_choice=_tc)
            except TypeError as _exc:
                # ★ 该 LLM 实现不支持 tools 参数（旧桩/别的 provider）
                #   ⇒ 诚实回退到 JSON 路径，并把回退写进报告。
                if "tools" in str(_exc):
                    _native = False
                    res = None
                else:
                    raise
            # ★ 端点不支持 tools（400/unknown field）⇒ 诚实回退到 JSON 路径
            if _native and res is not None \
                    and not getattr(res, "ok", False) and _tools_unsupported(res):
                _native = False
                res = None
        if not _native:
            if progress and hasattr(llm, "complete_stream"):
                res = llm.complete_stream(
                    prompt, system=system, json_mode=True,
                    images=_imgs,
                    on_delta=lambda t: progress({"ev": "token", "t": t}))
            else:
                res = llm.complete(prompt, system=system,
                                   json_mode=True, images=_imgs)
        _tool_mode = "native" if _native else "json"
        if not getattr(res, "ok", False):
            # ★★★ R422 · **基础设施故障与模型失败必须可区分** ——
            #   端点 502/503/429 或传输超时不是模型的错；原来两者都写成
            #   「LLM 失败: …」⇒ 跑分时把 7 分钟的端点抖动记成 12 单模型失败。
            #   `[infra]` 标记让 bench 能重投/剔除，而不是算进通过率。
            _meta = getattr(res, "meta", None) or {}
            _infra = (_meta.get("http_code") in (429, 500, 502, 503, 504)
                      or _meta.get("kind") == "transport")
            return {"task": task, "task_id": sid, "status": "incomplete",
                    "rounds": rnd,
                    "why": "LLM 失败%s: %s"
                           % ("[infra]" if _infra else "",
                              getattr(res, "error", "?")),
                    "actions_log": log}
        # ★★★ R384 · 优先用**原生 tool_calls**（端点本来就会调工具，
        #   是旧代码把手拼 JSON 逼它输出散文 —— 全池 51/54 = 94% 零动作）。
        _tcs = (getattr(res, "meta", None) or {}).get("tool_calls") or []
        step = _tool_calls_to_step(_tcs) if _tcs else _extract_json(res.text)
        if step is None:
            # ★★★ R384 · 原生工具模式下，模型**不调工具却输出散文**是协议
            #   违反（我们已把工具挂上去了）。现场：某 write 题 只 1 轮 0 动作，
            #   回"I'll check the directory structure"就被当答案。
            #   处理：先重试一次并明确要求调用工具；仍不调 ⇒ 判 incomplete。
            if _native:
                if _native_nudge[0] < 1:
                    _native_nudge[0] += 1
                    prompt = (
                        "任务: %s\n★ 你**没有调用任何工具**，只是输出了正文。"
                        "这不算执行。请立刻调用工具（read_file / write_file / "
                        "run_command / list_dir / search_code / final_answer），"
                        "不要输出任何正文说明。" % task)
                    continue
                # ★★★ R437 · **不再判死** —— 落到下面 R380 的纯文本处理。
                #   理由与 R380 同一条：**格式不该把正确答案一起扔掉**。
                #   R383 的两道护栏仍然生效（声称做过动作但零动作 / 拒绝执行）。
                #   现场：全池 2 轮 208 次里 4 次；工具修复后复测 3 单里 2 单
                #   命中此路径（都是"只答文件名"的短问句，模型直接写正文）。
                pass
            # ★★★ R380 · 纯文本答案**不许判死**。
            #   现场（2026-10-20 09:40 跑批）：8 单失败里 7 单的 `why`
            #   就是答案本身（`prev_node_id` / `dwc_pairs.jsonl` /
            #   那个不存在的文件名）—— 模型答对了，只是输出纯文本而不是
            #   `{"op":"final","answer":...}`，被这里判死。
            #   成因：`reasoning_effort="none"`（R377 为修「推理吃光
            #   token」而加）压制推理后，模型不再"先想格式再答"。
            #   ⇒ 格式判死把正确答案一起扔了。**用格式换正确率是错的**。
            #   护栏：空/纯空白仍判 incomplete（"什么都没有"≠答案）。
            _raw = str(getattr(res, "text", "") or "")
            if _raw.strip():
                # ★★★ R383 · 「声称已执行但零动作」必须判死（修 R380 假成功）。
                #   现场（2026-10-20 全池 52 单）：51/54 报告 actions_log 空，
                #   而模型写「已写入 var/inbox_work/list.md」—— 文件根本没写。
                #   R380 把纯文本收下当答案 ⇒ 模型"说"写了就算完成 = 假成功。
                #   判据：零动作 + 文本声称做过动作 ⇒ incomplete（幻觉）。
                _acts = len(log or [])
                _hit = _claimed_action_without_actions(_raw, _acts)
                if _hit:
                    return {"task": task, "task_id": sid,
                            "status": "incomplete", "rounds": rnd,
                            "why": "模型声称已执行（%r）但零动作记录 —— "
                                   "幻觉动作，未真正执行" % _hit,
                            "actions_log": log}
                _ref = _looks_like_refusal(_raw, _acts)
                if _ref:
                    return {"task": task, "task_id": sid,
                            "status": "incomplete", "rounds": rnd,
                            "why": "模型拒绝执行（%r）—— 未完成任务" % _ref,
                            "actions_log": log}
                # ★★★ R437 · 纯文本路径也要过**幻觉文件名闸** ——
                #   否则「不调工具直接写正文」会成为绕过 R419 的后门：
                #   模型可以编一个不存在的文件名而不被打回。
                if qa_mode:
                    # ★ R437 · 闸本身坏了不许炸单，但必须留痕（G7）
                    _pg_fail = [0]
                    try:
                        if _phantom_file_gate(task, _raw):
                            return {"task": task, "task_id": sid,
                                    "status": "incomplete", "rounds": rnd,
                                    "answer": "（未能给出有效答案：给出仓库中"
                                              "不存在的文件名，判为幻觉，不予采信）",
                                    "artifacts": [], "actions_log": log}
                    except Exception as _ge:        # noqa: BLE001
                        _pg_fail[0] += 1
                        import sys as _sys
                        _sys.stderr.write("phantom gate 失败×%d: %s\n"
                                          % (_pg_fail[0], _ge))
                return {"task": task, "task_id": sid,
                        "status": "done", "rounds": rnd,
                        "answer": _cap_answer(_raw),
                        "artifacts": [], "actions_log": log,
                        "answer_mode": "plain_text",
                        "why": "模型直接给出纯文本答案（非 JSON）—— 已收下"}
            return {"task": task, "task_id": sid, "status": "incomplete",
                    "rounds": rnd,
                    "why": "LLM 返回空内容（既非 JSON 也非文本）",
                    "actions_log": log}
        op = step.get("op")
        # ★★★ R426 · 模型把**原生工具名**当 op 用（`op='search_code'`）——
        #   现场（某 code-locate 题，11:29 复跑）：连续 3 轮 `op='search_code' 不在契约集`
        #   ⇒ 搜索动作全被丢掉 ⇒ 模型只能凭印象答 ⇒ 顽固幻觉。
        #   根因：`_TOOL_TO_OP` 只在**原生 tool_calls** 路径生效，
        #   JSON 步（模型自己写 `{"op":"search_code",...}`）没接映射。
        #   ★ 同一件事有两种写法，就该有同一个归一化入口。
        if isinstance(op, str) and op in _TOOL_TO_OP:
            _tc = [{"function": {
                "name": op,
                "arguments": json.dumps(
                    {k: v for k, v in step.items()
                     if k not in ("op", "analysis", "why")},
                    ensure_ascii=False)}}]
            _st2 = _tool_calls_to_step(_tc)
            if _st2:
                _sess({"round": rnd, "phase": "opmap",
                       "why": "原生工具名归一: %s -> %s"
                              % (op, _st2.get("op"))})
                step = _st2
                op = step.get("op")
        # ★ R223 · delegate 子代理（真子代理最小形态: 独立上下文隔离 —
        #   子探索的大量 read 输出不淹主任务; depth 限 1 层防递归爆炸）
        if op == "delegate":
            try:  # ★ R308-② · delegate 也受能力开关管（拒收留痕进下一轮）
                from dwc.caps.registry import is_enabled as _cap_on
                from dwc.llm.errors import err as _err2
                if not _cap_on("delegate"):
                    obs = _err2("CAP_DISABLED",
                                "能力 delegate 已关闭"
                                "（config/capabilities.yaml）")
                    prompt = ("任务: %s\n子代理返回(JSON): %s\n请继续（下一步 op）"
                              % (task, json.dumps(obs, ensure_ascii=False)[:2500]))
                    log.append({"round": rnd, "op": "delegate",
                                "analysis": str(step.get("analysis", ""))[:200]})
                    _sess({"round": rnd, "op": "delegate",
                           "analysis": str(step.get("task", ""))[:200]})
                    continue
            except Exception:
                _cap_broken = True
            if _depth >= 1:
                obs = {"ok": False, "error": "子代理内不可再 delegate（深度"
                       "上限 1 — 防递归; 自己继续做）"}
            else:
                # ★ R227 · 真并行子代理: tasks 数组 ⇒ ThreadPool 并发
                #   （各独立上下文, 摘要汇总回喂; 上限 3 防打爆 LLM）
                # ★ R309-① · 熔断：整批超 timeout_s 即弃未完、obs 留痕。
                try:
                    from dwc.caps.registry import cap_limit as _cap_lim
                    _dt = _cap_lim("delegate", "timeout_s", 600)
                except Exception:
                    _dt = 600
                subs = step.get("tasks")
                if isinstance(subs, list) and len(subs) >= 2:
                    from concurrent.futures import ThreadPoolExecutor
                    from concurrent.futures import wait as _fwait

                    def _one(k_sub):
                        return execute_user_task(
                            str(k_sub[1]), llm=llm, max_rounds=999,
                            task_id="%s_sub%d_%d" % (sid, rnd, k_sub[0]),
                            _depth=_depth + 1)
                    with ThreadPoolExecutor(max_workers=3) as pool:
                        _futs = [pool.submit(_one, k)
                                 for k in list(enumerate(subs))[:3]]
                        _doner, _pend = _fwait(_futs, timeout=_dt)
                    if _pend:
                        for _f in _pend:
                            _f.cancel()
                        _tout = True
                    else:
                        _tout = False
                    results = [f.result() for f in _futs if f.done()
                               and not f.cancelled()]
                    # ★ R305-T4 · coordinator 接线（并发执行不变，kanban 记账：
                    #   每 sub queued→done/fail，与 run_plan 同格式。
                    #   写失败记 kanban_drops 进 obs，不静默）
                    try:
                        from dwc.llm.coordinator import mark as _kmark
                        _kb = os.path.join(ROOT, "var", "kanban.jsonl")
                        _drops = 0
                        for _s, _r in zip(list(enumerate(subs))[:3], results):
                            _drops += (not _kmark(_kb, str(_s[1]), "queued"))
                            _drops += (not _kmark(
                                _kb, str(_s[1]),
                                "done" if _r.get("status") == "done"
                                else "fail"))
                    except Exception as _ke:  # noqa: BLE001 — 坏不断轮，计数留痕
                        _drops = -1
                    obs = {"ok": True, "subagent": True, "parallel": True,
                           "kanban_drops": _drops,
                           "subs": [{"status": r.get("status"),
                                     "rounds": r.get("rounds"),
                                     "answer": str(r.get("answer", ""))[:900],
                                     "why": r.get("why", "")}
                                    for r in results]}
                    if _tout:
                        obs = {"ok": False, "subagent": True,
                               "parallel": True,
                               "code": "DELEGATE_TIMEOUT",
                               "error": "delegate 并行批超时（>%ss）已弃未完" % _dt,
                               "done_n": len(results),
                               "subs": obs["subs"]}
                else:
                    try:
                        from concurrent.futures import ThreadPoolExecutor \
                            as _TPE1
                        with _TPE1(max_workers=1) as _pool1:
                            _fut1 = _pool1.submit(
                                execute_user_task, str(step.get("task", "")),
                                llm=llm, max_rounds=999,
                                task_id="%s_sub%d" % (sid, rnd),
                                _depth=_depth + 1)
                            # ★ R309-① · 单发熔断：TimeoutError 才记超时，
                            #   别的错照旧上抛（老行为不变）。
                            sub = _fut1.result(timeout=_dt)
                    except TimeoutError:
                        # ★ R310-④ · 超时 obs 带码（聚合可查）。
                        sub = {"status": "timeout", "rounds": 0, "answer": "",
                               "code": "DELEGATE_TIMEOUT",
                               "why": "delegate 超时（>%ss）已弃" % _dt}
                    obs = {"ok": True, "subagent": True,
                           "sub_status": sub.get("status"),
                           "sub_rounds": sub.get("rounds"),
                           "sub_answer": str(sub.get("answer", ""))[:1500],
                           "sub_why": sub.get("why", "")}
                    if sub.get("status") == "timeout":
                        obs["ok"] = False
                        obs["code"] = sub.get("code", "DELEGATE_TIMEOUT")
                        obs["error"] = sub.get("why", "")
            log.append({"round": rnd, "op": "delegate",
                        "analysis": str(step.get("analysis", ""))[:200]})
            _sess({"round": rnd, "op": "delegate",
                   "analysis": str(step.get("task", ""))[:200]})
            prompt = ("任务: %s\n子代理返回(JSON): %s\n请继续（下一步 op）"
                      % (task, json.dumps(obs, ensure_ascii=False)[:2500]))
            continue
        log.append({"round": rnd, "analysis": str(step.get("analysis", ""))[:300],
                    "op": op})
        _sess({"round": rnd, "op": op,
               "analysis": str(step.get("analysis", ""))[:200]})
        if op == "final":
            # ★★★ R407 · **标识符类问题必须取证** ——
            #   现场（read-fact 全池）：模型对"问某个标识符"的题不取证，
            #   凭"看起来像"直接答，甚至编出一个**全仓 0 命中**的名字。
            #   两单的共同点：问题在问**一个标识符**（类名/变量名/文件名），
            #   模型不取证、凭"看起来像"直接答。
            #   ★ R432 · 这里原来把两道题的答案与题面都写出来了，
            #     而本仓库就是评测语料 —— 注释里不写答案。
            #   R400-f 只拦"答案含文件名"，而类名/变量名没有 `.py` 后缀 ⇒ 漏掉。
            #
            #   规则：问题在问标识符 + 答案含代码标识符 + 零取证 ⇒ 打回。
            #   （纯知识问答不受影响：问题不问标识符就不触发。）
            #   ★★★ R418 · **每个闸独立计数** ——
            #   现场（某 read-fact 题）：模型 3 次读同一个源文件，
            #   共用的 `_r302_strikes` 就到 2 了 ⇒ 模型第三次拒答时**所有闸
            #   一起失效** ⇒「有证据却拒答」被当成答案收下。
            #   闸不该互相吃掉额度：每个闸各自 2 次，总轮次仍由 N 轮上限兜底。
            if qa_mode:
                _ans0 = str(step.get("answer", ""))
                _has_ev = any(isinstance(e, dict)
                              and e.get("phase") == "obs" and e.get("ok")
                              for e in log)
                if _gate_strikes.get("r407", 0) < 2:
                    _why407 = _ident_gate(task, _ans0, _has_ev)
                    if _why407:
                        _gate_strikes["r407"] = _gate_strikes.get("r407", 0) + 1
                        _sess({"round": rnd, "phase": "refcheck", "ok": False,
                               "why": "标识符类问题零取证（凭印象猜）"})
                        prompt = _why407
                        continue
                # ★ R407-b · 答案里的 `DWC_*` 变量名必须在仓库里真实存在
                if _gate_strikes.get("r407b", 0) < 2:
                    _why407b = _fake_ident_gate(_ans0)
                    if _why407b:
                        _gate_strikes["r407b"] = \
                            _gate_strikes.get("r407b", 0) + 1
                        _sess({"round": rnd, "phase": "refcheck", "ok": False,
                               "why": "答案含仓库中不存在的 DWC_* 变量名"})
                        prompt = _why407b
                        continue
                # ★★★ R417 · **有取证也编文件名** ⇒ 打回 ——
                #   现场（某 code-locate 题）：跑了 find_files、读了两个文件，最后仍答
                #   一个仓库里不存在的路由文件名（真实入口 `cli_main.py`）。
                #   文件名是否存在是可判定事实，不该靠模型自觉。
                if _gate_strikes.get("r417", 0) < 2:
                    _why417 = _phantom_file_gate(task, _ans0)
                    if _why417:
                        _gate_strikes["r417"] = _gate_strikes.get("r417", 0) + 1
                        _sess({"round": rnd, "phase": "refcheck", "ok": False,
                               "why": "答案文件名在仓库中不存在（幻觉）"})
                        prompt = _why417
                        continue
                # ★★★ R408 · **有证据却拒答**必须打回 ——
                #   现场（某 read-fact 题）：模型搜到命中行、读了该文件
                #   （正文里就有答案），甚至还读到一个内容就是答案的文件 ——
                #   最后仍答「未检索到任何证据，不做猜测」。
                #   **证据在手还拒答**，比猜错更冤。
                #   不做猜测」。**证据在手还拒答**，比猜错更冤。
                if _gate_strikes.get("r408", 0) < 2:
                    _why408 = _refusal_gate(task, _ans0, _has_ev,
                                            _ev_excerpt(log))
                    if _why408:
                        _gate_strikes["r408"] = _gate_strikes.get("r408", 0) + 1
                        _sess({"round": rnd, "phase": "refcheck", "ok": False,
                               "why": "有取证却拒答"})
                        prompt = _why408
                        continue
            # ★★★ R400-f · **零取证的"文件名断言"必须打回** ——
            #   现场（某 code-locate 题/某 code-locate 题）：模型第 1 轮直接 final 猜了一个**不存在的文件名**，
            #   引用校验打回后它撤回并拒答。
            #   规则：答案里出现文件名 ⇒ 必须至少有一次成功取证（obs ok）。
            #   （纯知识问答不涉及文件名 ⇒ 不受影响。）
            if qa_mode and _r302_strikes < 2:
                _ans0 = str(step.get("answer", ""))
                _claims_file = bool(re.search(
                    r"[\w\-/\\]+\.(?:py|md|json|ya?ml|toml|jsonl|txt)",
                    _ans0))
                _has_ev = any(isinstance(e, dict)
                              and e.get("phase") == "obs" and e.get("ok")
                              for e in log)
                if _claims_file and not _has_ev:
                    _r302_strikes += 1
                    _sess({"round": rnd, "phase": "refcheck", "ok": False,
                           "why": "零取证的文件名断言（凭印象猜）"})
                    prompt = ("任务: %s\n你在**没有做任何取证**的情况下直接"
                              "给出了文件名 —— 这是猜测，不予采纳。\n"
                              "先调用 search_code(pattern='<问题里的符号名>')，"
                              "从 === DEFINITIONS 段拿到真实文件，再 final。"
                              % task)
                    continue
            # ★ R302 · qa 引用校验（ALCE 本地版；执行路零变）。
            #   不实⇒打回重答（走 prompt，revision 禁 final 走不通）；
            #   同任务≥2 次⇒放行（防 F 型死循环）。
            if qa_mode and _r302_strikes < 2:
                from dwc.llm.step_judge import verify_final_refs
                # ★ R303-⑥ · 取证 URL 透传（final 编 URL 打回；无取证默认空⇒含URL即拦）
                _obs_urls = tuple(str(e.get("target", ""))
                                  for e in log
                                  if isinstance(e, dict)
                                  and e.get("phase") == "obs"
                                  and e.get("op") == "web_read"
                                  and e.get("ok"))
                _ref_err = verify_final_refs(str(step.get("answer", "")),
                                             obs_urls=_obs_urls)
                if _ref_err is not None:
                    _r302_strikes += 1
                    _sess({"round": rnd, "phase": "refcheck", "ok": False,
                           "why": _ref_err[:150]})
                    # ★★★ R400-e · 现场（某 code-locate 题/某 code-locate 题 反复）：引用被打回后模型
                    #   **撤回答案并拒答**（"我无法确证"），而不是去取证。
                    #   提示词必须明确要求"先取证再答"，并给出具体动作。
                    prompt = ("任务: %s\n你的 final 引用不实（%s）。"
                              "**不要撤回后拒答** —— 请立即用 "
                              "search_code(pattern='<问题里的符号名>') 取证，"
                              "答案在返回的 === DEFINITIONS 段；"
                              "拿到文件后再 final。"
                              "若确实搜不到，才答「未找到」，并说明搜过什么。"
                              % (task, _ref_err[:150]))
                    continue
            # ★★★ R423 · **顽固拒答 ⇒ 判失败**（证据在手，两次纠正仍拒答）——
            #   现场（某 read-fact 题）：模型 3 次读同一个源文件，
            #   revision 自己都写下了答案，
            #   R408 打回**两次**（提示里贴了证据原文），第三次仍答
            #   「没有检索到任何 TUI 主题证据」⇒ 额度用尽后被当成答案收下。
            #   ★ 与 R419 同构：**已知有证据还拒答**不是"完成"，是失败。
            if qa_mode and _gate_strikes.get("r408", 0) >= 2:
                _ans_r = str(step.get("answer", ""))
                _has_ev_r = any(isinstance(e, dict)
                                and e.get("phase") == "obs" and e.get("ok")
                                for e in log)
                if _refusal_gate(task, _ans_r, _has_ev_r, _ev_excerpt(log)):
                    _sess({"round": rnd, "phase": "refcheck", "ok": False,
                           "why": "顽固拒答：两次打回后仍拒答"})
                    return {"task": task, "task_id": sid, "status": "incomplete",
                            "rounds": rnd,
                            "answer": "（未能给出有效答案：已取到证据，"
                                      "但连续两次纠正后仍拒答，判为失败）",
                            "artifacts": [], "actions_log": log}
            # ★★★ R419 · **顽固幻觉 ⇒ 判失败**（不许把已知为假的答案交出去）——
            #   现场（某 code-locate 题，R419 全池）：R417 打回两次，模型第三次仍答
            #   同一个不存在的路径，额度用完后这个答案就被当成结果了。
            #   ★ 判据：文件名存在与否是**可判定事实** —— 两次纠正仍不改，
            #     说明是编的；宁可交 incomplete，也不交一个假文件名。
            if (qa_mode and _gate_strikes.get("r417", 0) >= 2
                    and _phantom_file_gate(task,
                                           str(step.get("answer", "")))):
                _sess({"round": rnd, "phase": "refcheck", "ok": False,
                       "why": "顽固幻觉：两次打回后仍给不存在的文件名"})
                return {"task": task, "task_id": sid, "status": "incomplete",
                        "rounds": rnd,
                        "answer": "（未能给出有效答案：连续两次给出仓库中"
                                  "不存在的文件名，判为幻觉，不予采信）",
                        "artifacts": [], "actions_log": log}
            if progress:
                progress({"ev": "final",
                          "answer": str(step.get("answer", ""))[:400]})
            _sess({"round": rnd, "op": "final", "answer":
                   str(step.get("answer", ""))[:200]})
            _extract_sources(log, task_id=sid, task=task,      # ★ R266A
                             answer=str(step.get("answer", "")),
                             artifacts=list(step.get("artifacts") or []))
            return {"task": task, "task_id": sid, "status": "done",
                    "rounds": rnd,
                    "answer": _cap_answer(step.get("answer", "")),
                    "artifacts": list(step.get("artifacts") or []),
                    "actions_log": log}
        try:
            if op == "run":
                step = {**step, "_confirmed": _parse_confirmed(ctx),
                        "_task_id": sid}
            # ★ R255 · EditAct 事前判别 + 轻量修订（2609.28416 §2.2/2.3 规则版;
            #   R247 熔断保留为第二防线; env DWC_STEP_JUDGE=0 可关）
            if op != "final" and os.environ.get("DWC_STEP_JUDGE", "1") != "0":
                from dwc.llm.step_judge import (judge_step, step_signature,
                                                validate_step)
                recent_obs = [e for e in log
                              if isinstance(e, dict)
                              and e.get("phase") == "obs"][-6:]
                _v, _jwhy, _jrule = judge_step(step, recent_obs,
                                             qa_mode=qa_mode)
                _sess({"round": rnd, "phase": "judge", "verdict": _v,
                       "rule": _jrule, "why": _jwhy[:150]})
                if _v == "noisy":
                    # ★ R302补2 · qa 诚实收敛（取证≥4 后仍缺 op⇒自动 final。
                    #   T_R302W 现场：F 劝 3 次，模型回无 op 思考块耗尽轮数。
                    #   零编造：只报取证事实＋未找到，不给结论）。
                    # ★ 补5b · R4 连空≥3 直接收敛（T_R302Z：10 轮全无 op，
                    #   零取证——如实说"未能给出有效动作"，不耗尽轮数）。
                    _reads = sum(1 for e in log
                                 if isinstance(e, dict)
                                 and e.get("phase") == "obs"
                                 # ★ R303-⑥ · web_read 成功与 read 同权计取证
                                 and e.get("op") in ("read", "web_read"))
                    if qa_mode and _jrule == "R4":
                        _r4_blanks += 1
                    else:
                        _r4_blanks = 0
                    if (qa_mode and _jrule == "R4"
                            and (_reads >= 4 or _r4_blanks >= 3)):
                        _tgt = sorted({str(e.get("target", ""))
                                       for e in log
                                       if isinstance(e, dict)
                                       and e.get("phase") == "obs"
                                       and e.get("op") == "read"})[:5]
                        _sess({"round": rnd, "phase": "refcheck", "ok": True,
                               "why": "qa 无 op 诚实收敛"})
                        _ans = (("经多轮取证仍未能定位确切依据，"
                                 "如实说明：已查阅 %s，未找到直接答案。"
                                 % "、".join(_tgt)) if _tgt else
                                "多轮未能给出有效动作，如实说明："
                                "没有完成取证，给不出有依据的答案。")
                        return {"task": task, "task_id": sid,
                                "status": "done", "rounds": rnd,
                                "answer": _ans,
                                "artifacts": [], "actions_log": log}
                    # ★ R301-E · R5 短路（qa 下违禁动作不执行不修订——
                    #   revision 禁 final，修了 LLM 也不听；直接 blocked 回 prompt）。
                    if _jrule == "R5":
                        _sess({"round": rnd, "phase": "revision",
                               "fallback": "R5_blocked_no_exec"})
                        obs = {"ok": False,
                               "error": "R5 拦截未执行: %s" % _jwhy[:150]}
                        log.append({"round": rnd, "phase": "obs", "op": op,
                                    "target": "R5_blocked",
                                    "ok": False,
                                    "obs": "R5 拦截未执行"})
                        _sess({"round": rnd, "op": op, "phase": "obs",
                               "target": "R5_blocked", "args": "",
                               "ok": False, "obs": "R5 拦截未执行"})
                        prompt = ("任务: %s\n上一轮动作被拦截（%s）。"
                                  "问答只许 read 取证或直接 final（answer≥10 字）。"
                                  "不要再出 run/write/delegate。"
                                  % (task, _jwhy[:150]))
                        continue
                    rev = _revise_step(llm=llm, task=task, step=step,
                                       why=_jwhy, recent=recent_obs,
                                       qa_mode=qa_mode)
                    if rev is None:
                        _sess({"round": rnd, "phase": "revision",
                               "fallback": "revision_llm_failed"})
                    else:
                        _err = validate_step(rev, allow_final=False,
                                            qa_mode=qa_mode)
                        _sig = step_signature(rev)
                        if _err is None and _sig != _last_rev_sig:
                            _sess({"round": rnd, "phase": "revision", "ok": True,
                                   "new_op": rev.get("op"),
                                   "why": str(rev.get("analysis", ""))[:150]})
                            step = rev
                            op = str(rev.get("op"))
                            _last_rev_sig = _sig
                        else:
                            _sess({"round": rnd, "phase": "revision",
                                   "fallback": _err or "duplicate_replacement"})
                            _last_rev_sig = _sig
                            # ★ R302补3 · qa 下 revision 被驳回⇒直回 prompt
                            #   （T_R302X 现场：驳回进 fallback obs，模型学不到，
                            #   连出无 op 熔断。驳回不记 obs、不耗熔断）。
                            if qa_mode and _err:
                                prompt = ("任务: %s\n修订被驳回（%s）。"
                                          "问答只许 read 取证或直接 final"
                                          "（answer≥10 字中文），不要再出别的。"
                                          % (task, _err[:150]))
                                continue
            obs = _do_action(op, step)
            if (op == "read" and isinstance(obs, dict)
                    and obs.get("image_path")):
                last_image = obs["image_path"]
        except TaskExecError as exc:
            obs = {"ok": False, "error": str(exc)}
        except Exception as exc:               # noqa: BLE001
            obs = {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}
        if progress:
            _tgt = step.get("path") or step.get("cmd") or step.get("tasks") \
                or step.get("task") or ""
            progress({"ev": "action", "round": rnd, "op": op,
                      "target": str(_tgt)[:80],
                      "ok": bool((obs or {}).get("ok", True)),
                      "detail": str((obs or {}).get("error", ""))[:120]})
        # ★ R247 留痕: target + 观察摘要（曾只有 analysis — 17:13 wsl 乱码
        #   案无现场可查, 只能靠 LLM 自述反推）
        _sess({"round": rnd, "op": op, "phase": "obs",
               "target": str(step.get("path") or step.get("cmd")
                             or step.get("task") or step.get("url")  # R266A
                             or step.get("query") or "")[:160],
               "args": _args_snapshot(step),
               "ok": bool((obs or {}).get("ok", True)),
               "obs": json.dumps(obs, ensure_ascii=False)[:400]})
        # ★ R255 修正: obs 行进 actions_log — judge 的 recent_obs 需要结构化
        #   历史（target/ok）; 此前 log 只有 op 行 ⇒ 判别历史恒空（真bug）。
        log.append({"round": rnd, "phase": "obs", "op": op,
                    "target": str(step.get("path") or step.get("cmd")
                                  or step.get("task") or step.get("url")  # R266A
                                  or step.get("query") or "")[:160],
                    "args": _args_snapshot(step),
                    "ok": bool((obs or {}).get("ok", True)),
                    "obs": json.dumps(obs, ensure_ascii=False)[:300]})
        # ★ R247 复读熔断: 999 轮开放后必须有硬出口 — 连续 3 轮同
        #   动作同目标同结果 = 此路不通（17:12 实测: read 同段×3 至上限）
        import hashlib as _hl
        _tgt_sig = str(step.get("path") or step.get("cmd")
                       or step.get("task") or "")[:160]
        _sig = "%s|%s|%s" % (op, _tgt_sig, _hl.sha1(
            json.dumps(obs, ensure_ascii=False, sort_keys=True)
            .encode("utf-8", "replace")).hexdigest()[:12])
        dup_sigs.append(_sig)
        if len(dup_sigs) >= 3 and len(set(dup_sigs[-3:])) == 1:
            # ★★★ R396 · 原生工具模式：熔断**不要直接判死** ——
            #   现场（21:35 全池）模型已经 read 到答案，却继续重复搜索，
            #   熔断直接把任务判 incomplete（本可答对）。
            #   ⇒ 先给**一次强制 final** 的机会（API 层 tool_choice 硬约束），
            #   仍不提交才判死。
            if _use_native_tools() and _ff_used[0] < 1:
                _ff_used[0] += 1
                _ff_pending[0] = True
                dup_sigs.clear()
                _sess({"round": rnd, "phase": "force_final",
                       "why": "复读熔断 ⇒ 强制 final_answer 收尾"})
                continue
            # ★ R302补2b · qa 熔断亦诚实收敛（熔断在 judge 前截，
            #   R4 收敛分支不可达——同条件在此复用，零编造）。
            if qa_mode and sum(
                    1 for e in log
                    if isinstance(e, dict) and e.get("phase") == "obs"
                    and e.get("op") == "read") >= 4:
                _tgt = sorted({str(e.get("target", ""))
                               for e in log
                               if isinstance(e, dict)
                               and e.get("phase") == "obs"
                               and e.get("op") == "read"})[:5]
                _sess({"round": rnd, "phase": "refcheck", "ok": True,
                       "why": "qa 熔断诚实收敛"})
                return {"task": task, "task_id": sid,
                        "status": "done", "rounds": rnd,
                        "answer": ("经多轮取证仍未能定位确切依据，"
                                   "如实说明：已查阅 %s，未找到直接答案。"
                                   % "、".join(_tgt)),
                        "artifacts": [], "actions_log": log}
            return {"task": task, "task_id": sid, "status": "incomplete",
                    "rounds": rnd,
                    "why": ("复读熔断: 连续 3 轮同动作同结果（%s / %s…）"
                            " — 换 offset/路径/参数或直接 final"
                            % (op, _tgt_sig[:60])),
                    "actions_log": log}
            _fail = {"status": "incomplete", "why": "复读熔断",
                     "actions_log": log}
            if retry_on_fail and _depth == 0:
                _r2 = _revision_retry(task=task, fail=_fail, llm=llm,
                                      sid=sid, progress=progress)
                if _r2 is not None:
                    return _r2
        # ★ R221 · 会话 compaction（滑动窗口+摘要 — 头部 agent 的上下文
        #   管理最小形态）: 窗口=最近 2 轮原文; 更早轮压成前情摘要注入 ——
        #   旧形态只带"上一步", 第 3 轮起 LLM 已忘了第 1 轮干了什么（长任务
        #   反复重读同文件的根因）。摘要是压缩不是删除（信息保留有界）。
        recent = log[-2:]
        older = log[:-2]
        prefix = ""
        if older:
            # ★ R257 · 证伪标记（2609.28416 §1.2 contamination 第1型对抗）:
            #   该轮 obs ok=False ⇒ 其结论是**被证伪的**, 摘要打标而非删除
            #   （删=彻底遗忘会复用, 标记=保留证伪记录防引用）。
            _okmap = {e.get("round"): e.get("ok") for e in log
                      if isinstance(e, dict) and e.get("phase") == "obs"}
            bits = []
            for e in older:
                _mark = (" [✗证伪—结论勿引用]"
                         if _okmap.get(e.get("round")) is False else "")
                bits.append("第%s轮 %s%s%s" % (
                    e.get("round"), e.get("op"),
                    ("（%s）" % e["analysis"][:80]) if e.get("analysis") else "",
                    _mark))
            prefix = "前情摘要（更早轮次已压缩; ✗证伪轮的结论不可用）: " \
                + " → ".join(bits) + "\n"
        prompt = ("任务: %s\n%s最近轮次: %s\n上一步动作观察(JSON): %s\n"
                  "请继续（下一步 op）"
                  % (task, prefix,
                     json.dumps(recent, ensure_ascii=False)[:1200],
                     tool_raw.clip(json.dumps(obs, ensure_ascii=False), limit=6000)))
    _fail = {"status": "incomplete", "why": "达轮数上限未 final",
             "actions_log": log}
    if retry_on_fail and _depth == 0:
        _r2 = _revision_retry(task=task, fail=_fail, llm=llm, sid=sid,
                              progress=progress)
        if _r2 is not None:
            return _r2
    _extract_sources(log, task_id=sid, task=task)   # ★ R266A: 没完成也沉淀
    return {"task": task, "task_id": sid, "status": "incomplete",
            "rounds": max_rounds,
            "why": "达轮数上限未 final", "actions_log": log}
