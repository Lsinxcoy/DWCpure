# -*- coding: utf-8 -*-
"""dwc_bench2 · 真实任务跑批 + 进化 A/B（R259 · 短板 1 效果证明层）。

★★★ G2 纪律（验收在 agent 外）:
  · run-verify 类: **验收器独立重跑 cmd**（不采信 agent 的 answer/rc）
  · write 类: **验收器独立读文件**（不采信 agent 自述）
  · fact/locate/analyze 类: 机器判 answer 文本（contains/regex — 不是 LLM 判 LLM）
  · 全程零 LLM 自评成功。

=== A/B 设计（唯一变量 = 进化面）===
  A 臂: DWC_STEP_JUDGE=0 + ctx=None（无 lessons 注入, 无修订 — bench 直调
        execute_user_task 天然绕过 agent 的 lessons/revision 面）
  B 臂: judge 默认开 + ctx=lessons_context(task)（模拟 agent 生产路径）
  两臂同 max_rounds（防轮数混淆变量）。A 先跑（无修订不污染 B）；
  B 臂在线进化是其真实语义（"进化开着的系统"）。

用法:
  python scripts/dwc_bench2.py --arm A --limit 5     # smoke
  python scripts/dwc_bench2.py --arm A                # 全量 A 臂
  python scripts/dwc_bench2.py --arm B                # 全量 B 臂（A 之后）
  python scripts/dwc_bench2.py --report               # 读最近两跑出对比报告
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

TASKS = os.path.join(_ROOT, "config", "eval_tasks.jsonl")
EVAL_DIR = os.path.join(_ROOT, "var", "eval")
PY = sys.executable
THROTTLE = 3   # ★ 单间节流秒数（端点限流实测）


# ══════════ 验收器（agent 外独立判）══════════

def _file_of(path_rel: str) -> str:
    return os.path.join(_ROOT, path_rel)


#: ★★★ R389 · 猜测/弃权措辞（命中即**不算确证**）。
#:   现场（2026-10-20 全池）：某 read-fact 题 问"记忆系统内核类名"，agent 答
#:   「没有取证信息…可能是 MemoryKernel」，判据 `contains` 给了 ✓。
#:   这不是"找到了"，是"猜对了"。
#:   ★ 只收**明确的**猜测/弃权标记；"如果…则…"这类假设句**不收**
#:     （太常见，会误杀正常答案）。
_HEDGE_PATTERNS = (
    "可能是", "大概是", "估计是", "也许是", "或许是", "应该是",
    "推测", "猜测", "我猜", "大概", "或许", "似乎",
    "无法确认", "无法确定", "无法给出确切", "无法读取", "无法访问",
    "没有取证", "无取证", "未能找到", "未能确认", "不确定",
    "没有可用", "缺少取证",
)

#: 允许"推测"的判据类型（`allow_guess: true` 时跳过检查）
_GUESS_AWARE_TYPES = ("contains", "contains_any", "contains_equiv",
                      "contains_all", "regex")


#: 引号内的片段**不是模型的断言** —— 「最不确定的分支」这种是术语
_QUOTED_SPAN = re.compile(r"[「『“\"][^」』”\"]{0,80}[」』”\"]")


def _strip_quoted(s: str) -> str:
    """去掉引号包裹的片段（「」『』“”""）。

    ★★★ R433 · 现场（某 historical 题）：正确答案里有这么一句 ——
      「…选「pass-rate 最不确定的分支」先探索…」
    其中"不确定"是信息增益的**术语**（指熵最高的分支），不是模型在犹豫。
    R392 已经只看命中句，但命中句里恰好含这个术语 ⇒ 正确回答被判
    `guess-credit-blocked`。**引号里的话是引用，不是断言。**
    """
    try:
        return _QUOTED_SPAN.sub(" ", s or "")
    except Exception:
        return s or ""


def _is_guessing(ans: str) -> str:
    """返回命中的猜测措辞（空串 = 不是猜测）。"""
    low = _strip_quoted(ans).lower()
    for h in _HEDGE_PATTERNS:
        if h in low:
            return h
    return ""


def _sentences(ans: str) -> list:
    """按中英文句末标点/换行切句（保留分隔符，便于回拼）。"""
    parts = re.split(r"(?<=[。！？!?；;\n])", ans or "")
    return [p for p in parts if p.strip()]


def _match_sentences(check: dict, ans: str) -> list:
    """找出**命中答案**的那一句（或多句）。

    ★ R392 · 猜测判定必须只看命中句 —— 长答案里一句免责声明
      不该把整条确证答案判死（R389 按全文扫，误杀了大量正确回答）。
    """
    t = check.get("type")
    sents = _sentences(ans)
    if not sents:
        return []
    if t == "regex":
        m = re.search(check.get("pattern") or "", ans)
        if not m:
            return []
        pos = m.start()
        acc = 0
        for s in sents:
            if acc <= pos < acc + len(s):
                return [s]
            acc += len(s)
        return []
    if t == "contains":
        needles = [check.get("target") or ""]
    elif t in ("contains_any", "contains_equiv", "contains_all"):
        needles = [str(x) for x in (check.get("target") or [])]
    else:
        return []
    needles = [n for n in needles if n]
    if not needles:
        return []
    hits = []
    for s in sents:
        for n in needles:
            ok = (n.lower() in s.lower()) if t == "contains_equiv" else (n in s)
            if ok:
                hits.append(s)
                break
    return hits


def _hedge_block(check: dict, ans: str):
    """若**命中句**是猜测且未显式豁免 ⇒ 返回 (False, how)；否则 None。

    ★★★ R392 · 句子级（不是全文级）：
      · "定义在 task_exec.py。别的不确定。"  ⇒ 命中句确证 ⇒ ✓
      · "无法确认。不过可能是 task_exec.py"  ⇒ 命中句猜测 ⇒ ✗
      定位不到命中句（target 不在答案里）⇒ 不判猜测（让未命中逻辑判 ✗）。
    """
    if check.get("allow_guess"):
        return None
    if check.get("type") not in _GUESS_AWARE_TYPES:
        return None
    ctx = _match_sentences(check, ans)
    if not ctx:
        return None
    for s in ctx:
        hit = _is_guessing(s)
        if hit:
            return (False, "guess-credit-blocked: 命中句含猜测措辞 %r"
                           "（不算确证）" % hit)
    return None


def _agent_ran(cmd: str, report) -> tuple:
    """★★★ R388 · 在 agent 的 `actions_log` 里找"真跑过这条命令"的证据。

    返回 (found: bool, why: str)。

    证据判据（三重，全部要满足）：
      ① 有 `op == "run"` 的 obs 动作
      ② 该动作 `ok` 为真（命令真执行成功，不是失败的尝试）
      ③ 命令命中同一个目标 —— 用**测试文件名/命令首段**做 needle，
         允许参数变体（`-q` / `-p no:randomly` / `--tb=short`）

    ★ 为什么不能只信 `ok`：agent 可能跑的是别的命令。
    ★ 为什么不能只看 answer：agent 会在 answer 里写"已验证通过"（幻觉）。
    """
    if not isinstance(report, dict):
        return (False, "缺 report —— 无法确认 agent 是否执行（禁止静默放行）")
    log = report.get("actions_log") or []
    if not isinstance(log, list):
        return (False, "actions_log 非列表")

    # needle：优先取命令里的测试文件路径，其次取命令首 40 字符
    needle = ""
    m = re.search(r"(tests[/\\][\w./\\-]+\.py)", cmd or "")
    if m:
        needle = m.group(1).replace("\\", "/")
    else:
        needle = (cmd or "").strip()[:40]

    # ★★★ R397 · **归一化匹配** —— 判据里写的是字符串命令
    #   `python -c "import os;n=sum(...)"`，而 agent 的动作是 argv 列表
    #   `['python','-c','import os;n=sum(...)']`，JSON 序列化后是
    #   `["python", "-c", "import os..."]` ⇒ 带引号/空格的 needle
    #   **永远匹配不到** ⇒ 3 单 run-verify 被误判 no-agent-evidence
    #   （现场 某 run-verify 题/某 run-verify 题/某 run-verify 题）。
    #   修：两边都去掉所有非字母数字字符再比。
    def _norm(s: str) -> str:
        return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", (s or "").lower())

    # ★★★ R413-b · **解释器不参与匹配** ——
    #   判据写 `python scripts/gate.py`，agent 实际用绝对路径
    #   `C:/Users/.../venv/Scripts/python.exe scripts/gate.py`；
    #   归一化后 needle 是 `pythonscriptsgatespy`，blob 里却是
    #   `...pythonexescriptsgatespy` ⇒ needle 不是子串 ⇒ 误判零证据
    #   （某 run-verify 题 现场：agent 真跑了、rc=0、输出"总结: 全部通过"）。
    #   解释器换哪个都一样，**命令本体**才是证据。
    needle = re.sub(
        r"^(?:[A-Za-z]:[\\/][^\s]*?python(?:\.exe)?|python[\d.]*(?:\.exe)?)\s+",
        "", needle, flags=re.I)

    _needle_n = _norm(needle)
    if not _needle_n:
        return (False, "无法从命令提取特征（cmd 为空）")

    for e in log:
        if not isinstance(e, dict) or e.get("phase") != "obs":
            continue
        if e.get("op") != "run":
            continue
        if not e.get("ok"):
            continue
        blob = " ".join(str(e.get(k) or "") for k in ("cmd", "target", "obs"))
        if _needle_n in _norm(blob):
            return (True, "agent 执行过（needle=%r）" % needle[:50])
    return (False, "agent 未执行该命令（零动作或未命中 %r）" % needle[:50])


def _nz(s) -> str:
    """归一化：去掉所有非字母数字/中文字符，转小写（与 R397 同口径）。"""
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(s or "").lower())


def _obs_out(e) -> str:
    """从留痕条目里取出**命令输出正文**（obs 可能是 dict 或 JSON 字符串）。"""
    o = e.get("obs")
    if isinstance(o, dict):
        return str(o.get("out") or "")
    if isinstance(o, str):
        try:
            d = json.loads(o)
            if isinstance(d, dict):
                return str(d.get("out") or "")
        except Exception:                       # noqa: BLE001 — 坏行按原文
            pass
        return o
    return ""


def _answer_anchor(check: dict, answer: str, rerun_out: str) -> str:
    """★★★ R413 · 从"判据命令的复核输出"或"最终答案"里取一个**答案锚点**。

    优先用 `target` 之后的那一段（rv06：`PYFILES 98` ⇒ `98`）；
    没有 target 时退化为答案里最长的字母数字串（rv08：40 位 SHA）。
    """
    tgt = str(check.get("target") or "")
    if tgt and tgt in rerun_out:
        after = rerun_out.split(tgt, 1)[1].strip()
        tok = re.split(r"\s+", after)[0] if after else ""
        tok = tok.strip("\"'()[]{}.,;:：，。；、（）")
        # ★★★ R413-b · 只有**纯数字**才配当"数值锚点"（某 run-verify 题 的 `98`）。
        #   某 run-verify 题 的 target 是中文短语 `全部通过`，后面跟的是 `（rc=0）`
        #   ⇒ 取出来是 `rc=0` 这种噪声 ⇒ 改成**直接用 target 本身当锚点**：
        #   agent 的输出里必须真的出现"全部通过"，这比命令串形状更硬。
        if tok.isdigit():
            return tok
        return tgt
    toks = re.findall(r"[0-9A-Za-z_]{4,}", answer or "")
    return max(toks, key=len) if toks else ""


def _agent_saw(anchor: str, report, cmd: str = "") -> bool:
    """★★★ R413 · agent **自己跑出来的输出**里是否出现过答案锚点。

    这就是"证据等价"：不要求命令串一致，但答案必须是从它自己的执行结果
    里来的。★ 零动作 / 跑了无关命令 ⇒ 输出里没有锚点 ⇒ 仍然判失败。

    ★★★ R413-c · 光有锚点还不够 —— 还得是**干这活的那条命令**产出的：
      · 判据命令里有文件名（`scripts/gate.py`）⇒ 该次 run 的命令必须提到同一文件；
      · 没有文件名 ⇒ 两边至少共享 2 个词元（rv08：`git`/`log`/`1`）。
      否则 `python scripts/other.py` 只要打印"全部通过"就能冒领。
    """
    if not isinstance(report, dict) or not anchor:
        return False
    log = report.get("actions_log") or []
    if not isinstance(log, list):
        return False
    a = _nz(anchor)
    if not a:
        return False

    _FILE_RE = r"[\w./\\-]*[\w-]\.(?:py|json|jsonl|md|txt|ya?ml)"
    want_files = {f.replace("\\", "/").lower()
                  for f in re.findall(_FILE_RE, cmd or "")}
    want_toks = {t for t in re.findall(r"[a-z0-9_]{2,}", (cmd or "").lower())}

    for e in log:
        if not isinstance(e, dict):
            continue
        if e.get("phase") != "obs" or e.get("op") != "run" or not e.get("ok"):
            continue
        out_n = _nz(_obs_out(e))
        if not out_n or a not in out_n:
            continue
        # ★ 这条 run 是不是"干这活的命令"？
        #   ★ 仅当判据有 target（在核对某个具体输出）时才要求相关；
        #     target 为空时锚点就是答案本身（某 run-verify 题 的 40 位 SHA），
        #     偶然产出同一个哈希的概率可以忽略。
        blob = " ".join(str(e.get(k) or "") for k in ("cmd", "target"))
        blob_l = blob.replace("\\", "/").lower()
        if cmd:
            if want_files:
                if not any(f in blob_l for f in want_files):
                    continue
            else:
                got = {t for t in re.findall(r"[a-z0-9_]{2,}", blob_l)}
                if len(want_toks & got) < 2:
                    continue
        # ★ 短**数字**锚点（如 "98"）只认**聚焦输出**，防止在长列表里偶然命中；
        #   中文短语锚点（如 "全部通过"）本来就该在整段输出里找 ——
        #   长输出恰恰是"真的跑了门禁"的证据。
        if a.isdigit() and len(a) < 8 and len(out_n) > 40:
            continue
        return True
    return False


def verify(check: dict, answer: str, since=None, report=None) -> tuple:
    """返回 (ok: bool, how: str)。how 记录判定依据（审计）。

    ★★★ R378 · `since`（投单时刻 epoch）—— 文件类判据必须校验文件是
      **本轮写的**。现场取证（2026-10-20 09:00 跑批）：`wr08` 被判 ✓，
      但 `var/inbox_work/` 里那个文件 mtime 是 **528591 秒前**（6 天前
      残留），任务本身 `status=incomplete, answer=None`。
      ⇒ 判据验的是历史残留，不是本轮产出。
      不传 `since` ⇒ 保持旧语义（兼容既有调用）。
    """
    t = check.get("type")
    ans = answer or ""
    # ★★★ R389 · 猜测不记功（统一前置，所有答案类判据都过这道门）
    _hb = _hedge_block(check, ans)
    if _hb is not None:
        return _hb
    if t == "contains":
        return (check["target"] in ans, "answer contains %r" % check["target"][:40])
    if t == "first_key":
        # ★★★ R431 · **最先出现的键**判据（"只答X"类任务专用）。
        #   现场（某 read-fact 题，17:05）：模型先给出一个**错的裸词**，随后又提到
        #   正确的完整键来否定它；`contains` 判据命中子串 ⇒ 判 ✓。
        #   **答案明确是错的，判据却给了分** —— 判据不许给白送分。
        #   规则：谁**先出现**，谁就是模型给出的答案；正确答案必须排最前。
        #   （短词是长键的子串，但长键位置更靠前时仍然判对。）
        #   ★ R432 · 注释里不写具体键名（本仓库是评测语料，注释会被搜到）。
        cands = [str(x) for x in (check.get("target") or [])]
        best, bi = None, None
        for c in cands:
            i = ans.find(c)
            if i >= 0 and (bi is None or i < bi):
                best, bi = c, i
        ok = bool(cands) and best == cands[0]
        return (ok, "first-key %r (pos %s)" % (best, bi))
    if t == "regex":
        return (bool(re.search(check["pattern"], ans)),
                "answer regex %r" % check["pattern"][:40])
    if t == "contains_any":
        hits = [x for x in check["target"] if x in ans]
        return (bool(hits), "answer any-of %r" % hits[:3])
    if t == "contains_equiv":
        # ★★★ R381 · 等价形式判据（任一等价写法命中即通过）。
        #   现场（2026-10-20 第 0 步实验）：`某 read-fact 题` 问「PowerShell 需要
        #   TrimStart 的字符码」，判据只认 `0xfeff`，模型答 `65279`
        #   —— **65279 就是 0xFEFF**，答对了却被判 ✗。
        #   ⇒ 判据验的是"写法"不是"答案"，把正确答案判死。
        hits = [x for x in check["target"] if str(x).lower() in ans.lower()]
        return (bool(hits), "answer equiv-of %r" % hits[:3])
    if t == "contains_all":
        miss = [x for x in check["target"] if x not in ans]
        return (not miss, "answer all-of; miss=%r" % miss)
    if t == "rc_and_contains":
        # ★★★ R413 · **先复核，再验证据**（顺序换了：复核输出要用来取答案锚点）
        cmd = check["cmd"]
        try:
            r = subprocess.run(
                (cmd.replace("python ", PY + " ", 1)
                 if cmd.startswith("python ") else cmd),
                shell=True, capture_output=True, text=True, timeout=300,
                cwd=_ROOT, encoding="utf-8", errors="replace")
        except Exception as exc:                    # noqa: BLE001
            return (False, "verify-rerun failed: %s" % exc)
        ok = r.returncode == 0 and (not check["target"]
                                    or check["target"] in (r.stdout + r.stderr))
        how = "rerun rc=%d anchor=%r" % (r.returncode, check["target"][:30])
        # ★★★ R388 · 还要 **agent 侧证据**：它必须真的执行过。
        #   现场（2026-10-20 全池）：run-verify 10/10 = 100%，而这是假的 ——
        #   旧实现只有"判据自己重跑"，agent 零动作也能过。
        if not check.get("allow_self_verify"):
            found, why = _agent_ran(cmd, report)
            if not found:
                # ★★★ R413 · 证据等价：命令串不同不算数，但**答案必须出现在
                #   agent 自己跑出来的输出里**（某 run-verify 题 的 `98`、某 run-verify 题 的 SHA）。
                #   零动作 / 无关命令 ⇒ 输出里没有锚点 ⇒ 仍然判失败。
                anchor = _answer_anchor(check, ans, r.stdout + r.stderr)
                _rel = cmd if check.get("target") else ""
                if not _agent_saw(anchor, report, _rel):
                    return (False, "no-agent-evidence: " + why)
                how = "agent-ran-equivalent(anchor=%r) + %s" % (anchor, how)
            else:
                how = "agent-ran + " + how
        return (ok, how)
    if t in ("file_contains", "file_contains_all", "file_lines"):
        p = _file_of(check["path"])
        if not os.path.exists(p):
            return (False, "file missing: %s" % check["path"])
        # ★★★ R378 · 旧文件不算本轮产出（防历史残留假通过）
        if since is not None:
            try:
                if os.path.getmtime(p) < float(since) - 1.0:
                    return (False, "file stale（mtime 早于本轮投单）: %s"
                            % check["path"])
            except OSError as exc:
                return (False, "file mtime 读失败: %s" % exc)
        body = io.open(p, encoding="utf-8", errors="replace").read()
        if t == "file_contains":
            return (check["target"] in body, "file contains %r"
                    % check["target"][:30])
        if t == "file_contains_all":
            miss = [x for x in check["target"] if x not in body]
            return (not miss, "file all-of; miss=%r" % miss)
        if t == "file_lines":
            n = len([l for l in body.splitlines() if l.strip()])
            return (n == check["lines"] and check["target"] in body,
                    "file lines=%d want=%d" % (n, check["lines"]))
    return (False, "unknown check type %r" % t)


# ══════════ 跑批 ══════════

def run_arm(arm: str, limit: int = 0, max_rounds: int = 30) -> dict:
    from dwc.llm.client import LLMClient
    from dwc.llm.task_exec import execute_user_task
    if arm == "A":
        os.environ["DWC_STEP_JUDGE"] = "0"
    else:
        os.environ.pop("DWC_STEP_JUDGE", None)

    llm = LLMClient()
    if not getattr(llm, "configured", False):
        print("✗ LLM 未配置")
        return {}
    tasks = [json.loads(l) for l in io.open(TASKS, encoding="utf-8")
             if l.strip()]
    if limit:
        tasks = tasks[:limit]
    os.makedirs(EVAL_DIR, exist_ok=True)
    out_p = os.path.join(EVAL_DIR, "run_%s_%s.jsonl"
                         % (arm, time.strftime("%m%d_%H%M%S")))
    n_ok = 0
    rows = []
    for i, t in enumerate(tasks, 1):
        ctx = None
        if arm == "B":
            try:
                from dwc.agent_quality import lessons_context
                ctx = lessons_context(t["task"]) or None
            except Exception:                        # noqa: BLE001
                ctx = None
        time.sleep(THROTTLE)        # ★ 节流（连续快调触发端点限流 — 实测）
        t0 = time.time()
        rep = execute_user_task(t["task"], llm=llm, ctx=ctx,
                                task_id="eval_%s_%s" % (arm, t["id"]),
                                max_rounds=max_rounds)
        # ★ 瞬断重试: 首轮即挂（≤2 轮 incomplete）大概率端点瞬断, 退避重跑一次
        if rep.get("status") == "incomplete" and (rep.get("rounds") or 0) <= 2:
            time.sleep(10)
            rep = execute_user_task(t["task"], llm=llm, ctx=ctx,
                                    task_id="eval_%s_%s" % (arm, t["id"]),
                                    max_rounds=max_rounds)
        dt = time.time() - t0
        ok, how = verify(t["check"], str(rep.get("answer", "")), report=rep)
        n_ok += 1 if ok else 0
        row = {"arm": arm, "id": t["id"], "kind": t["kind"], "ok": ok,
               "verify": how, "status": rep.get("status"),
               "rounds": rep.get("rounds"), "secs": round(dt, 1),
               "revised": bool(rep.get("revised"))}
        rows.append(row)
        with io.open(out_p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print("[%s %d/%d] %s %-12s %s (%.0fs, r=%s)" % (
            arm, i, len(tasks), "✓" if ok else "✗", t["id"],
            t["kind"], dt, rep.get("rounds")))
    summ = {"arm": arm, "n": len(tasks), "ok": n_ok,
            "success": round(n_ok / max(1, len(tasks)), 3),
            "by_kind": {}}
    try:  # ★ R269-④ · 记忆快照（哪次记忆赢的，可归因）
        from dwc.agent_quality import memory_snapshot_hash
        summ["memory_sha"] = memory_snapshot_hash()
    except Exception:                            # noqa: BLE001
        summ["memory_sha"] = "unknown"
    for k in sorted({r["kind"] for r in rows}):
        sub = [r for r in rows if r["kind"] == k]
        summ["by_kind"][k] = "%d/%d" % (sum(r["ok"] for r in sub), len(sub))
    with io.open(os.path.join(
            EVAL_DIR, "summary_%s_%s.json" % (arm, time.strftime("%m%d_%H%M%S"))),
            "w", encoding="utf-8") as fh:
        json.dump(summ, fh, ensure_ascii=False, indent=1)
    print("\n==== %s 臂: %d/%d = %.1f%% ====" % (arm, n_ok, len(tasks),
                                                100 * n_ok / max(1, len(tasks))))
    print(json.dumps(summ["by_kind"], ensure_ascii=False))
    return summ


def report() -> int:
    """最近 A/B 两跑对比（进化净收益）。"""
    import glob
    def _latest(arm):
        fs = sorted(glob.glob(os.path.join(EVAL_DIR, "summary_%s_*.json" % arm)))
        return json.load(io.open(fs[-1], encoding="utf-8")) if fs else None
    a, b = _latest("A"), _latest("B")
    if not a or not b:
        print("✗ 需要 A/B 两臂各至少一跑（先跑 A 再跑 B）")
        return 1
    delta = round(b["success"] - a["success"], 3)
    print("==== 进化净收益（B 开进化 − A 关进化）====")
    print("A(关进化): %d/%d = %.1f%%" % (a["ok"], a["n"], 100 * a["success"]))
    print("B(开进化): %d/%d = %.1f%%" % (b["ok"], b["n"], 100 * b["success"]))
    print("净收益 Δ = %+.1f 个百分点" % (100 * delta))
    print("分类型 A:", json.dumps(a["by_kind"], ensure_ascii=False))
    print("分类型 B:", json.dumps(b["by_kind"], ensure_ascii=False))
    with io.open(os.path.join(EVAL_DIR, "ab_report.json"), "w",
                 encoding="utf-8") as fh:
        json.dump({"A": a, "B": b, "delta_pp": round(100 * delta, 1)},
                  fh, ensure_ascii=False, indent=1)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arm", choices=("A", "B"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-rounds", type=int, default=30)
    ap.add_argument("--report", action="store_true")
    args = ap.parse_args()
    if args.report:
        return report()
    if not args.arm:
        ap.error("--arm A|B 或 --report")
    run_arm(args.arm, args.limit, args.max_rounds)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
