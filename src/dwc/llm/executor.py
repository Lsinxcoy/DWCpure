# -*- coding: utf-8 -*-
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
from typing import Any, Dict, List, Optional

from dwc.organs.actor import Receipt

#: src/dwc/llm/executor.py ⇒ 四级上跳到仓库根（src/dwc/llm → src/dwc
#: → src → root）— core.py 只用三级是因为它在 src/dwc/ 而非 src/dwc/llm/
ANCHOR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))))), "config", "anchors")


def load_anchors(path: Optional[str] = None) -> Dict[str, Any]:
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


def obs_skeleton(anchors: Dict[str, Any], tid: str
                 ) -> Dict[str, List[List[Any]]]:
    """任务 fn→[[args, None]] 骨架（None=待执行体填, 不当预填 0）。"""
    g = anchors.get(tid) or {}
    obs: Dict[str, List[List[Any]]] = {}
    for c in g.get("checks", []):
        if "fn" not in c:
            continue
        obs.setdefault(c["fn"], []).append([coerce(c.get("args", "")), None])
    return obs


def parse_llm_observed(raw: str, skeleton: Dict[str, List[List[Any]]]
                       ) -> Optional[Dict[str, List[List[Any]]]]:
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
    cands.append(re.search(r"\{.*\}", text, re.S).group(0)
                 if re.search(r"\{.*\}", text, re.S) else "")
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
        out: Dict[str, List[List[Any]]] = {}
        for fn, pairs in parsed.items():
            if (isinstance(pairs, list) and pairs
                    and all(isinstance(x, list) and len(x) == 2
                            for x in pairs)):
                out[str(fn)] = [[coerce(x[0]), coerce(x[1])]
                                for x in pairs]
        if out:
            return out
    return None


def memory_text(memory: Any) -> str:
    """把记忆库全部未归档 SKILL 工件渲染成文本（内容通道）。"""
    rows = memory._conn.execute(
        "SELECT payload FROM memory_node WHERE kind='skill'"
        " AND archived_at IS NULL").fetchall()
    if not rows:
        return ""
    return "\n".join(json.dumps(json.loads(r["payload"]), ensure_ascii=False)
                     for r in rows)


def build_observed_prompt(tid: str, skel: Dict[str, Any],
                            mt: str) -> str:
    """★ R277b-5 · 观测 prompt 单一构造点（禁 null 回声——推理模型
    会把 skeleton 原样抄回，None 不换值 ⇒ observed 残疾 ⇒ m 残疾）。

    三条硬指令: 只输出最终 JSON / 每个值必须是具体值 / 不许留 null。
    """
    return (
        "任务 %s 的观测需要返回 observed, 形态如下（fn -> "
        "[[args, observed_value], ...]）:\n%s\n"
        "已知参考资料（skill 工件, 可能有用）:\n%s\n"
        "只输出最终 JSON 对象（只有 observed 的内容，不要解释，"
        "不要重复上面的形态示例）。每个 observed_value 都必须是"
        "具体值 —— 不许留 null：不确定的填你认为最可能正确的值。"
        % (tid, json.dumps(skel, ensure_ascii=False), mt or "（无）"))


class LLMExecutorFactory:
    """造一个按需带记忆文本的 LLM executor（注入 Actor 用）。

    stats 计数（n_calls/n_parsed/n_errors）供「执行体使用率」测量 —
      恒等/空转问题（README 陷阱 #4「挂载≠活着」）的实测工具。
    """

    def __init__(self, llm: Any, anchors: Optional[Dict] = None,
                 tasks: Optional[List[str]] = None):
        self.llm = llm
        self.anchors = anchors if anchors is not None else load_anchors()
        self.tasks = set(tasks) if tasks is not None else None
        self.stats = {"n_calls": 0, "n_parsed": 0, "n_errors": 0}

    def _enabled(self, tid: str) -> bool:
        g = self.anchors.get(tid) or {}
        if g.get("verifier_kind") != "behavior":
            return False
        return self.tasks is None or tid in self.tasks

    def make(self, memory: Any = None) -> "callable":
        """产出 executor 闭包（memory 每次调用时取其当前文本）。"""

        def _exec(task: Dict[str, Any]) -> Receipt:
            tid = str(task.get("task_id", ""))
            if not self._enabled(tid):
                return Receipt(ok=True, verified=True, detail={})
            self.stats["n_calls"] += 1
            skel = obs_skeleton(self.anchors, tid)
            mtxt = memory_text(memory) if memory is not None else ""
            prompt = build_observed_prompt(tid, skel, mtxt)
            try:
                res = self.llm.complete(prompt, system="只输出 JSON, 不解释。")
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
                           detail={"observed": observed})
        return _exec
