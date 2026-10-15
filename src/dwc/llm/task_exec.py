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
import json
import os
import re  # ★ R276c · ask 词边界（platform/transform 误含 rm 曾误拦只读扫描）
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional

from dwc.foundation.paths import find_root
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


def _do_action(op: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """执行一个白名单动作 → 观察（回喂 LLM 的材料）。"""
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
            lim = min(400, max(1, int(args.get("limit", 0) or 0)))
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
        return {"ok": True, "path": os.path.relpath(p, ROOT),
                "bytes": len(content.encode("utf-8"))}
    if op == "mcp":
        # ★ R224 · MCP 工具调用（标准协议面: server 配置在 config/mcp.json
        #   — 维护者写 agent 只读; 未配置的 server 明确报错不静默）
        from dwc.llm import mcp_client as M
        server = str(args.get("server", ""))
        tool = str(args.get("tool", ""))
        if not server or not tool:
            raise TaskExecError("mcp 需要 server 与 tool: %r" % (args,))
        return M.tools_call(server, tool, args.get("args") or {})
    if op == "run":
        cmd = args.get("cmd")
        if not isinstance(cmd, list) or not cmd:
            raise TaskExecError("cmd 必须是非空 argv 列表: %r" % (cmd,))
        joined = " ".join(str(x) for x in cmd).lower()
        hit = [w for w in _FORBIDDEN if w in joined]
        if hit:
            raise TaskExecError("危险命令黑名单命中 %s: %s" % (hit, joined[:120]))
        ask = _ask_level(joined)
        confirmed = args.get("_confirmed") or set()
        if ask and any(str(c) in joined for c in confirmed):
            # ★ R222 · 人工授权通道: ctx 带 '人工授权: <词>' ⇒ 放行 + 留痕
            r0 = subprocess.run([str(x) for x in cmd], cwd=ROOT,
                                capture_output=True, text=True, timeout=60,
                                encoding="utf-8", errors="replace")
            return {"ok": r0.returncode == 0, "rc": r0.returncode,
                    "stdout": (r0.stdout or "")[:4000],
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
                        "stdout": (r0.stdout or "")[:4000],
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
                    "out": (r.stdout or "")[:6000],
                    "err": (r.stderr or "")[:1500]}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "timeout 60s"}
    raise TaskExecError("未知动作 op=%r（白名单: read/write/run/"
                        "web_read/web_search/mcp/delegate/ask/final）" % op)


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
                 recent: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """★ State Revision 轻量版（2609.28416 §2.3）: 对 noisy 提案重写一次。

    ★ 每次判别**只调一次**; 失败返回 None ⇒ 调用方 fallback 保留原提案
      （EditAct _fallback 纪律 — 修订器故障绝不卡任务）。
    ★ 修订禁产 final（validate allow_final=False — 终局分支已结算）。
    """
    prompt = (
        "你在执行任务, 上一步被判为噪声动作。\n"
        "任务: %s\n"
        "噪声动作: %s\n"
        "判别原因: %s\n"
        "最近动作观察: %s\n"
        "请**换一条路径/换参数/换动作类型**重写下一步（不要重复噪声动作, "
        "不要 final）。只输出 JSON: {\"analysis\": \"…\", \"op\": "
        "\"read|write|run\", \"path\": \"…\"（read/write）, \"cmd\": "
        "\"…\"（run）}" % (task,
                 json.dumps({k: v for k, v in step.items()
                             if k != "analysis"}, ensure_ascii=False)[:400],
                 why[:200],
                 json.dumps(recent[-3:], ensure_ascii=False)[:900]))
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
    if self_md:
        system += ("\n\n# 自我认知（你的持久记忆文件, 每单加载）\n" + self_md)
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
    log: List[Dict[str, Any]] = []
    dup_sigs: List[str] = []   # ★ R247 复读熔断: (op|target|obs哈希) 滑窗
    _last_rev_sig: Optional[str] = None   # ★ R255 修订去重（连续同签名⇒fallback）
    last_image: Optional[str] = None   # ★ R226: 最近读到的图（下轮挂给 LLM）
    prompt = "任务: %s\n%s" % (task, ("\n上下文: " + ctx) if ctx else "")
    for rnd in range(1, max_rounds + 1):
        obs: Dict[str, Any] = {}   # ★ R247: final 轮不走 _do_action —
        #   每轮开头重置, 留痕段引用不至 UnboundLocal
        if progress:
            progress({"ev": "round", "n": rnd})
        _imgs = [last_image] if last_image else None
        # ★ R237 token 级流式: 有 progress 且 client 支持 ⇒ SSE 流,
        #   每 delta 发 token 事件（chat 端状态机提取 answer 流式打印;
        #   中间轮 JSON 无 answer 键 ⇒ 天然静默, final 轮才见逐字输出）
        if progress and hasattr(llm, "complete_stream"):
            res = llm.complete_stream(
                prompt, system=system, max_tokens=1600, json_mode=True,
                images=_imgs,
                on_delta=lambda t: progress({"ev": "token", "t": t}))
        else:
            res = llm.complete(prompt, system=system, max_tokens=1600,
                               json_mode=True, images=_imgs)
        if not getattr(res, "ok", False):
            return {"task": task, "task_id": sid, "status": "incomplete",
                    "rounds": rnd,
                    "why": "LLM 失败: %s" % getattr(res, "error", "?"),
                    "actions_log": log}
        step = _extract_json(res.text)
        if step is None:
            # ★ R217 · 容错后仍失败才报 incomplete（bench 最大失败单点
            #   llm_format: 模型爱包 ```json 代码块/多行/前后缀文本）
            return {"task": task, "task_id": sid, "status": "incomplete",
                    "rounds": rnd,
                    "why": "LLM 响应非 JSON（容错提取后仍失败）: %s"
                           % str(res.text)[:120],
                    "actions_log": log}
        op = step.get("op")
        # ★ R223 · delegate 子代理（真子代理最小形态: 独立上下文隔离 —
        #   子探索的大量 read 输出不淹主任务; depth 限 1 层防递归爆炸）
        if op == "delegate":
            if _depth >= 1:
                obs = {"ok": False, "error": "子代理内不可再 delegate（深度"
                       "上限 1 — 防递归; 自己继续做）"}
            else:
                # ★ R227 · 真并行子代理: tasks 数组 ⇒ ThreadPool 并发
                #   （各独立上下文, 摘要汇总回喂; 上限 3 防打爆 LLM）
                subs = step.get("tasks")
                if isinstance(subs, list) and len(subs) >= 2:
                    from concurrent.futures import ThreadPoolExecutor

                    def _one(k_sub):
                        return execute_user_task(
                            str(k_sub[1]), llm=llm, max_rounds=999,
                            task_id="%s_sub%d_%d" % (sid, rnd, k_sub[0]),
                            _depth=_depth + 1)
                    with ThreadPoolExecutor(max_workers=3) as pool:
                        results = list(pool.map(
                            _one, list(enumerate(subs))[:3]))
                    obs = {"ok": True, "subagent": True, "parallel": True,
                           "subs": [{"status": r.get("status"),
                                     "rounds": r.get("rounds"),
                                     "answer": str(r.get("answer", ""))[:900],
                                     "why": r.get("why", "")}
                                    for r in results]}
                else:
                    sub = execute_user_task(str(step.get("task", "")),
                                            llm=llm, max_rounds=999,
                                            task_id="%s_sub%d" % (sid, rnd),
                                            _depth=_depth + 1)
                    obs = {"ok": True, "subagent": True,
                           "sub_status": sub.get("status"),
                           "sub_rounds": sub.get("rounds"),
                           "sub_answer": str(sub.get("answer", ""))[:1500],
                           "sub_why": sub.get("why", "")}
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
                    "answer": str(step.get("answer", "")),
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
                _v, _jwhy, _jrule = judge_step(step, recent_obs)
                _sess({"round": rnd, "phase": "judge", "verdict": _v,
                       "rule": _jrule, "why": _jwhy[:150]})
                if _v == "noisy":
                    rev = _revise_step(llm=llm, task=task, step=step,
                                       why=_jwhy, recent=recent_obs)
                    if rev is None:
                        _sess({"round": rnd, "phase": "revision",
                               "fallback": "revision_llm_failed"})
                    else:
                        _err = validate_step(rev, allow_final=False)
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
               "ok": bool((obs or {}).get("ok", True)),
               "obs": json.dumps(obs, ensure_ascii=False)[:400]})
        # ★ R255 修正: obs 行进 actions_log — judge 的 recent_obs 需要结构化
        #   历史（target/ok）; 此前 log 只有 op 行 ⇒ 判别历史恒空（真bug）。
        log.append({"round": rnd, "phase": "obs", "op": op,
                    "target": str(step.get("path") or step.get("cmd")
                                  or step.get("task") or step.get("url")  # R266A
                                  or step.get("query") or "")[:160],
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
                     json.dumps(obs, ensure_ascii=False)[:6000]))
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
