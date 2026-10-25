"""LLM 执行体（LLM executor）—— R126 · 把「执行环境默认化」落成 src 件。

起源: R124 scripts/transfer_llm_arm.py 的 llm_executor（实验臂）。
本件把它提升为 src 级共用执行体, 让「LLM 当执行环境」不再只是
某个实验脚本的私有能力 —— 但**默认零破坏**（见下）。

契约（与 Actor §3.3② 完全同构 — 复用 Receipt, 不发明第二套）:
  · executor(task) -> Receipt(ok, verified, detail)
  · behavior 任务: detail={"observed": {fn: [[args, value], ...]}}
    ⇒ judge 判分（真执行通道）
  · 非 behavior / 端点不可用 / 解析失败: detail={} ⇒ judge 判
    NOT_EVALUATED（未评价 — **不当 False**, 不当 0, 不猜）
  · 端点错 (res.error) 与「不猜测」同路径: 不编 observed

为何在 llm/ 下而不是 organs/: 它是**执行环境**（外设）, 不是器官。
  器官是判据/记忆/演化 — executor 是「手」, 按 README §「executor 由
  调用方注入」原语义放在 llm/ 包内供注入。

定位（DWC-AUTO · 自我强化）: 执行体是进化循环的**真观测来源** —
  没有它, run_term 只能自造观测（R25 诚实占位）⇒ 所有进化测量
  退化为恒等。本件把「有真观测的可能」变成一条默认可开的接线。

TRUTH_SOURCE（G2）: observed 由 LLM 对 anchors checks 结构的回复解析而来
  ⇒ 判分真值仍在 config/anchors/*.json（judge 域, 字节级 frozen）;
  LLM 是**被测对象**不是判据源; 解析失败 ⇒ NOT_EVALUATED（如上）。
"""
from __future__ import annotations

import ast
import json
import os
import re
from typing import Any

from dwc.organs.actor import Receipt
from dwc.observability.context import measurement_role, task_measurement_context

#: src/dwc/llm/executor.py ⇒ 四级上跳到仓库根（src/dwc/llm → src/dwc
#: → src → root）— core.py 只用三级是因为它在 src/dwc/ 而非 src/dwc/llm/
ANCHOR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))), "config", "anchors")


def load_anchors(path: str | None = None) -> dict[str, Any]:
    """读 dev anchors（judge 同源 — 不复制判据）。"""
    p = path or os.path.join(ANCHOR_DIR, "dev.json")
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def coerce(x: Any) -> Any:
    """字面量还原（judge 域的 args 是 str）— 失败原样返回不猜。"""
    try:
        return ast.literal_eval(str(x))
    except (ValueError, SyntaxError):
        return x


def obs_skeleton(anchors: dict[str, Any], tid: str
                 ) -> dict[str, list[list[Any]]]:
    """任务 fn→[[args, None]] 骨架（None=待执行体填, 不当预填 0）。"""
    g = anchors.get(tid) or {}
    obs: dict[str, list[list[Any]]] = {}
    for c in g.get("checks", []):
        if "fn" not in c:
            continue
        obs.setdefault(c["fn"], []).append([coerce(c.get("args", "")), None])
    return obs


def parse_llm_observed(raw: str, skeleton: dict[str, list[list[Any]]]
                       ) -> dict[str, list[list[Any]]] | None:
    r"""从 LLM 回复抽 observed（对 skeleton 的 fn 找 JSON/字面块）— 不猜。

    只接受能解析成 {fn: [[a, v], ...]} 的形态; 其它 ⇒ None。

    ★ R277b-4 · 推理模型的长前言会把 skeleton 回声 + 真 JSON 混在一起,
      贪婪 \{.*\} 一口吞下必炸 ⇒ 改多候选逐个试（由后往前, 真答案
      通常在末尾）; 先剥 markdown 围栏。
    """
    if not raw or not raw.strip():
        return None
    text = re.sub(r"```(?:json)?", "", raw.strip())
    cands = [m.group(0) for m in re.finditer(r"\{[^{}]*\}", text)]
    cands.append(re.search(r"\{.*\}", text, re.DOTALL).group(0)
                 if re.search(r"\{.*\}", text, re.DOTALL) else "")
    for blob in reversed(cands):  # ★ 真答案通常在末尾 ⇒ 倒序优先
        if not blob:
            continue
        parsed = None
        for dec in (json.loads, ast.literal_eval):
            try:
                parsed = dec(blob)
                break
            except Exception:
                continue
        if not isinstance(parsed, dict):
            continue
        out: dict[str, list[list[Any]]] = {}
        for fn, pairs in parsed.items():
            if (isinstance(pairs, list) and pairs
                    and all(isinstance(x, list) and len(x) == 2
                            for x in pairs)):
                out[str(fn)] = [[coerce(x[0]), coerce(x[1])]
                                for x in pairs]
        if out:
            return out
    return None


def parse_method(raw: str) -> str:
    """★ R458 · 从同一份回复里抽 `_method`（模型自述的做法）。

    没有 ⇒ 空串（不猜、不补）。这是**自述**，不是验证过的方法：
    只有判分通过时才允许写进记忆，且 payload 标 `m_source=llm_self_report`。
    """
    if not raw or not raw.strip():
        return ""
    text = re.sub(r"```(?:json)?", "", raw.strip())
    cands = [m.group(0) for m in re.finditer(r"\{[^{}]*\}", text)]
    greedy = re.search(r"\{.*\}", text, re.S)
    if greedy:
        cands.append(greedy.group(0))
    for blob in reversed(cands):
        if not blob:
            continue
        parsed = None
        for dec in (json.loads, ast.literal_eval):
            try:
                parsed = dec(blob)
                break
            except Exception:                  # noqa: BLE001 — 换下一个候选
                continue
        if not isinstance(parsed, dict):
            continue
        v = parsed.get("_method") or parsed.get("method")
        if isinstance(v, str) and v.strip():
            return v.strip()[:200]
    return ""


def _bigrams(s: str):
    """中文没有空格分词 ⇒ 用 2-gram 集合算重叠（对中英混排都成立）。"""
    t = "".join(ch for ch in (s or "") if not ch.isspace())
    if len(t) <= 1:
        return {t} if t else set()
    return {t[i:i + 2] for i in range(len(t) - 1)}


def memory_text(memory: Any, task: str = "", k: int = 5,
                max_chars: int = 1800, min_cov: float = 0.45,
                record: bool = True) -> str:
    """按**当前任务**取最相关的 k 条 skill 做法（不是全量倾倒）。

    ★ R457 · 旧实现把库里全部 SKILL 渲染进 prompt：实测 71 条 = 29,952 字符，
      既贵又稀释信号。

    ★ 相关性判据（实测标定，不是拍脑袋）：
      以任务文本与 scene+method 的 2-gram 覆盖率 `cov = |命中| / |任务信息gram|`
      为口径，先剔除在库里过于常见（df > 30%）的 gram（"的""函数"这类）。
      实测：同一任务原文 cov=1.000 / 无关任务 cov=0.081
      ⇒ 阈值 0.45 干净分开。命中不足 3 个信息 gram 一律不认。
      **没有相关做法就返回空** —— 不拿无关经验凑数。

    ★ M0 · `record=True` 时把这次 skill 召回写入 `memory_retrieval`，
      并给选中节点 access+1。没有命中也要记 zero-hit（不能只记成功）。
    """
    def _record(ids: list[str], scores: list[float]) -> None:
        if not record:
            return
        fn = getattr(memory, "record_retrieval", None)
        if fn is None:
            return
        try:
            fn(task, "skill_prompt", ids, scores,
               source="memory_text", touch=True)
        except Exception as exc:            # noqa: BLE001 — 测量坏不掀 prompt
            import sys as _sys
            _sys.stderr.write("memory_text 检索记账失败（跳过）: %s\n" % exc)

    if memory is None or not str(task or "").strip():
        return ""
    rows = memory._conn.execute(
        "SELECT node_id, payload FROM memory_node WHERE kind='skill'"
        " AND archived_at IS NULL").fetchall()
    if not rows:
        _record([], [])
        return ""
    skills = []
    for r in rows:
        try:
            d = json.loads(r["payload"])
        except (ValueError, TypeError, KeyError, IndexError):
            continue
        skills.append((str(r["node_id"]), d,
                       _bigrams("%s %s" % (d.get("scene") or "",
                                           d.get("method") or ""))))
    if not skills:
        _record([], [])
        return ""
    df = {}
    for _nid, _d, b in skills:
        for g in b:
            df[g] = df.get(g, 0) + 1
    n = len(skills)
    tb = _bigrams(task)
    info = {g for g in tb if df.get(g, 0) <= max(2, 0.3 * n)}
    if len(info) < 3:
        _record([], [])
        return ""
    scored = []
    for nid, d, b in skills:
        hit = info & b
        if len(hit) < 3:
            continue
        cov = len(hit) / float(len(info))
        if cov < min_cov:
            continue
        scored.append((nid, cov, len(hit), json.dumps(d, ensure_ascii=False)))
    if not scored:
        _record([], [])
        return ""
    scored.sort(key=lambda x: (-x[1], -x[2]))
    out, total, seen = [], 0, set()
    selected_ids: list[str] = []
    selected_scores: list[float] = []
    for nid, cov, _nh, s in scored:
        if s in seen:
            continue
        s = s[:400]
        if total + len(s) > max_chars:
            break
        out.append(s)
        selected_ids.append(nid)
        selected_scores.append(round(float(cov), 6))
        seen.add(s)
        total += len(s)
        if len(out) >= k:
            break
    _record(selected_ids, selected_scores)
    return "\n".join(out)


def build_observed_prompt(tid: str, skel: dict[str, Any],
                            mt: str) -> str:
    """★ R277b-5 · 观测 prompt 单一构造点（禁 null 回声——推理模型
    会把 skeleton 原样抄回，None 不换值 ⇒ observed 残疾 ⇒ m 残疾）。

    三条硬指令: 只输出最终 JSON / 每个值必须是具体值 / 不许留 null。
    ★ R458 · 加 `_method`：模型顺带说出"怎么算的"。成功时这条就是
      skill 记忆的 method —— 否则 term 只产失败签名，永远学不到做法。
      它是**自述**（m_source=llm_self_report），只在判分通过时才落库。
    """
    return (
        "任务 %s 的观测需要返回 observed, 形态如下（fn -> "
        "[[args, observed_value], ...]）:\n%s\n"
        "已知参考资料（skill 工件, 可能有用）:\n%s\n"
        "只输出最终 JSON 对象（只有 observed 的内容，不要解释，"
        "不要重复上面的形态示例）。每个 observed_value 都必须是"
        "具体值 —— 不许留 null：不确定的填你认为最可能正确的值。\n"
        "并在同一对象里加一个键 \"_method\"，值为一句话（≤80 字）"
        "说明你是怎么得到这些值的（用了什么公式/步骤）。"
        % (tid, json.dumps(skel, ensure_ascii=False), mt or "（无）"))


class LLMExecutorFactory:
    """造一个按需带记忆文本的 LLM executor（注入 Actor 用）。

    stats 计数（n_calls/n_parsed/n_errors）供「执行体使用率」测量 —
      恒等/空转问题（README 陷阱 #4「挂载≠活着」）的实测工具。
    """

    def __init__(self, llm: Any, anchors: dict | None = None,
                 tasks: list[str] | None = None):
        self.llm = llm
        self.anchors = anchors if anchors is not None else load_anchors()
        self.tasks = set(tasks) if tasks is not None else None
        self.stats = {"n_calls": 0, "n_parsed": 0, "n_errors": 0}

    def _enabled(self, tid: str) -> bool:
        g = self.anchors.get(tid) or {}
        if g.get("verifier_kind") != "behavior":
            return False
        return self.tasks is None or tid in self.tasks

    def make(self, memory: Any = None) -> callable:
        """产出 executor 闭包（memory 每次调用时取其当前文本）。"""

        def _exec(task: dict[str, Any]) -> Receipt:
            tid = str(task.get("task_id", ""))
            if not self._enabled(tid):
                # ★ R277b-10 · 非 behavior 不执行 —— 显式码（空包含糊，
                #   直调者会误当观测喂 judge；下游认 error_code 走未评价）。
                return Receipt(ok=True, verified=True, detail={
                    "error_code": "llm_not_enabled"})
            self.stats["n_calls"] += 1
            skel = obs_skeleton(self.anchors, tid)
            # ★ R457 · 用**题目原文**召回相关做法（没有相关经验就为空）
            _task_txt = (self.anchors.get(tid) or {}).get("prompt") or tid
            mtxt = memory_text(memory, _task_txt) if memory is not None else ""
            prompt = build_observed_prompt(tid, skel, mtxt)
            try:
                _sys_json = "只输出 JSON, 不解释。"
                try:  # ★ R306 · prompt OTA（缺失⇒内嵌老路）
                    from dwc.llm.prompt_ota import note_miss as _ota_miss
                    from dwc.llm.prompt_ota import ota_system as _ota
                    _sys_json = _ota("sys_json", _sys_json, __file__)
                except Exception:
                    _ota_miss()
                with task_measurement_context(
                        tid, candidate_id=task.get("candidate_id"),
                        rollout_id=task.get("rollout_id"),
                        protocol_id=task.get("protocol_id")):
                    with measurement_role("solver"):
                        res = self.llm.complete(prompt, system=_sys_json)
            except Exception as exc:            # 端点炸 ⇒ 未评价, 不当 False
                self.stats["n_errors"] += 1
                return Receipt(ok=True, verified=True, detail={
                    "error_code": "llm_transport_error",
                    "llm_error": "%s" % type(exc).__name__})
            err = getattr(res, "error", None)
            if err or not getattr(res, "text", None):
                self.stats["n_errors"] += 1
                return Receipt(ok=True, verified=True, detail={
                    "error_code": "llm_no_text", "llm_error": str(err)})
            observed = parse_llm_observed(res.text, skel)
            if observed is None:
                return Receipt(ok=True, verified=True, detail={
                    "error_code": "llm_parse_failed"})
            self.stats["n_parsed"] += 1
            return Receipt(ok=True, verified=True,
                           detail={"observed": observed,
                                   "method": parse_method(res.text)})
        return _exec
