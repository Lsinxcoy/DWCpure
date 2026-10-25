# -*- coding: utf-8 -*-
"""R457 · 把"学到的做法"写进记忆 —— 让 skill 不再是 0 条。

★★★ 定位（G1）: **DWC-AUTO** —— 自我强化：自己学到的做法，自己存成可检索的记忆。

为什么必须有
------------
实测（R457 前）：生产记忆库 `memory_node` 5,073 条里 **skill = 0**，
而 `var/dwc_lessons.jsonl` 里躺着 **905 条 success_pattern**（904 条带
"成功做法（...）"）—— 系统一直在学，只是学到的做法**从未进入记忆**。

后果是两条链同时断：

1. `dwc/llm/executor.py::memory_text()` 只读 `kind='skill'` ⇒ 恒返回空
   ⇒ 模型 prompt 里的"已知参考资料"永远是「（无）」
2. 记忆库的 EXPERIENCE 区只有 failure_sig（失败），没有"做对了什么"
   ⇒ 检索面只有负样本

★ D6 纪律：SKILL 属 EXPERIENCE，payload 必须含
  `scene / method / boundary / invalid_conditions / recovery_strategies`。
  缺一项就**不写**（fail-closed）—— 不编恢复策略。
  本模块的 `recovery_strategies` 不是编的：它写的是系统真实行为
  （本条失效 ⇒ 本轮失败签名进 evolver 重新诊断），见 `_RECOVERY`。

★ 去重：`src_key = sha1(task + method)`。同一做法重复出现只写一次；
  近重复由 `MemoryKernel.remember` 自己的合并逻辑处理（R104）。
"""
from __future__ import annotations

import hashlib
import io
import json
import os
from typing import Any, Dict, Iterable, Optional, Set

from dwc.organs.memory import MemoryKind
from dwc.organs.memory_guard import MemoryQuarantineError

#: 成功做法失效后的真实去向（不是策略发明：失败签名本来就进 evolver）
_RECOVERY = "失效时按本轮失败签名重新诊断（evolver 通道），不沿用本条"

#: 只收这类 fail_mode（成功路径）；失败类不进 SKILL
_SUCCESS_PREFIX = "success_pattern"

#: M1 · 过程技能的动作词/步骤词（规则可审计；不确定 ⇒ factual）
_ACTION_WORDS = (
    "先", "然后", "再", "接着", "步骤", "读取", "搜索", "定位", "修改",
    "运行", "执行", "验证", "检查", "测试", "复现", "修复", "对比",
    "read", "search", "locate", "edit", "patch", "run", "test", "verify",
    "grep", "diff", "open", "write",
)
_FACTUAL_MARKERS = ("定义为", "等于", "公式", "答案是", "即", "结果为")


def classify_skill_kind(scene: Any, method: Any) -> str:
    """把 skill 分成 procedural / factual / chat。

    ★ 为什么需要: 生产 7 条 skill 里 6 条是最终答案/事实，不是过程；
      不分类就会把“阶乘=120”当可复用做法，污染 prompt。
    ★ 保守规则: 不确定 ⇒ factual（宁可少认过程，不把答案冒充步骤）。
    ★ 只做元数据；是否过滤由调用方/M1.3 决定，不在本函数删数据。
    """
    text = ("%s %s" % (_clip(scene, 400), _clip(method, 800))).strip().lower()
    if not text:
        return "factual"
    # ★ 问答式 scene（“...吗/？”）通常是解释，不是过程；先判 chat。
    if str(scene or "").strip().endswith(("吗", "？", "?")):
        return "chat"
    action_hits = sum(1 for w in _ACTION_WORDS if w in text)
    step_hits = sum(1 for w in ("先", "然后", "再", "接着", "步骤")
                    if w in text)
    # ★ 先判 chat：带建议/我认为的长文即使含“先/再”，也是对话建议，
    #   不是可执行过程；否则会被动作词误判成 procedural。
    chat_hits = sum(1 for w in ("建议", "你可以", "我认为", "总结一下")
                    if w in text)
    if chat_hits >= 2:
        return "chat"
    if action_hits >= 2 or (step_hits >= 1 and action_hits >= 1):
        return "procedural"
    if any(w in text for w in _FACTUAL_MARKERS):
        return "factual"
    return "factual"



def _clip(s: Any, n: int) -> str:
    return str(s or "").strip()[:n]


def src_key(task: Any, method: Any) -> str:
    """做法指纹（task + method）。同一做法只写一次。"""
    raw = "%s\x00%s" % (_clip(task, 400), _clip(method, 800))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _action_digest(value: Any) -> str:
    """动作参数/观察的引用哈希；轨迹里只存 ref，不内联原文。"""
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(
        raw.encode("utf-8", "replace")).hexdigest()


def procedure_from_actions(actions_log: Any,
                           evidence_ref: str = "") -> Dict[str, Any]:
    """把 `task_exec.actions_log` 投影成过程技能字段（M1.2）。

    ★ 只抽**真实发生过的动作**：`phase=obs` 且 `op` 非 final。
    ★ 不推断前置条件；没有动作 ⇒ `procedure_status=not_instrumented`，
      不编 steps。
    ★ `verification` 只认 run/test/check 且 ok；`failure_modes` 只认
      ok=False 的真实失败，不把猜测写成失败模式。
    """
    steps: list[Dict[str, Any]] = []
    tools: list[str] = []
    verification: list[Dict[str, Any]] = []
    failure_modes: list[Dict[str, Any]] = []
    for entry in actions_log or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("phase") != "obs":
            continue
        op = str(entry.get("op") or "")
        if not op or op == "final":
            continue
        target = str(entry.get("target") or "")[:200]
        ok = bool(entry.get("ok"))
        obs_ref = _action_digest(entry.get("obs", ""))
        steps.append({"op": op, "target": target, "ok": ok,
                      "obs_ref": obs_ref})
        if op not in tools:
            tools.append(op)
        if op in ("run", "test", "check") and ok:
            verification.append({"op": op, "target": target,
                                 "obs_ref": obs_ref})
        if not ok:
            failure_modes.append({"op": op, "target": target,
                                  "obs_ref": obs_ref})
    return {
        "preconditions": [],          # 不推断：真实前置条件未登记
        "steps": steps,
        "tools": tools,
        "verification": verification,
        "failure_modes": failure_modes,
        "recovery_strategies": _RECOVERY if failure_modes else "",
        "evidence_ref": evidence_ref,
        "procedure_status": "observed" if steps else "not_instrumented",
    }


def lesson_to_payload(row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """把一条 lesson 变成 SKILL payload；不合格返回 None（fail-closed）。

    合格条件（全部满足才写）：
      · fail_mode 以 `success_pattern` 开头
      · task 与 detail 都非空
    """
    if not isinstance(row, dict):
        return None
    fm = _clip(row.get("fail_mode"), 120)
    if not fm.startswith(_SUCCESS_PREFIX):
        return None
    task = _clip(row.get("task"), 400)
    detail = _clip(row.get("detail"), 800)
    # ★ 太短的 task/detail 是占位或测试残留（实测台账里混进过
    #   task="任务X" detail="假答案" 这种行）—— 不做成"经验"。
    if len(task) < 4 or len(detail) < 12:
        return None
    return {
        "scene": task,
        "method": detail,
        "boundary": fm,
        # 什么时候不适用：不属于这一类任务时
        "invalid_conditions": "任务不属于 %s 类，或该任务已有更新的成功做法" % fm,
        "recovery_strategies": _RECOVERY,
        "skill_kind": classify_skill_kind(task, detail),
        "src_key": src_key(task, detail),
        "task_id": _clip(row.get("task_id"), 80),
        "quality": row.get("quality"),
        "at": row.get("at"),
    }


def existing_keys(memory: Any) -> Set[str]:
    """库里已有做法的 src_key 集合（一次查询，供批量去重）。"""
    keys: Set[str] = set()
    try:
        rows = memory._conn.execute(
            "SELECT payload FROM memory_node WHERE kind='skill'").fetchall()
    except Exception:                     # noqa: BLE001 — 库不可读 ⇒ 空集
        return keys
    for r in rows:
        try:
            d = json.loads(r[0])
        except (ValueError, TypeError):
            continue
        k = d.get("src_key")
        if k:
            keys.add(str(k))
    return keys


def promote_lesson(memory: Any, row: Dict[str, Any],
                   seen: Optional[Set[str]] = None) -> Optional[str]:
    """写一条；重复或不合格返回 None。"""
    p = lesson_to_payload(row)
    if p is None:
        return None
    if seen is not None:
        if p["src_key"] in seen:
            return None
    else:
        if p["src_key"] in existing_keys(memory):
            return None
    nid = memory.remember(MemoryKind.SKILL, p, source_channel="lesson_ledger")
    if seen is not None:
        seen.add(p["src_key"])
    return nid


def promote_pending(memory: Any, path: Optional[str] = None,
                    limit: Optional[int] = None) -> Dict[str, int]:
    """把 lessons 里尚未入库的成功做法写成 SKILL。

    返回 `{n_seen, n_written, n_dup, n_skip, n_quarantined}` ——
    `n_seen = n_written + n_dup + n_skip` 仍成立；
    `n_quarantined` 是 `n_skip` 的子计数（被写入门拒绝，不是解析失败）。
    """
    path = path or os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))),
        "var", "dwc_lessons.jsonl")
    out = {"n_seen": 0, "n_written": 0, "n_dup": 0, "n_skip": 0,
           "n_quarantined": 0}
    seen = existing_keys(memory)
    try:
        fh = io.open(path, encoding="utf-8")
    except OSError:
        return out
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            out["n_seen"] += 1
            try:
                row = json.loads(line)
            except ValueError:
                out["n_skip"] += 1
                continue
            p = lesson_to_payload(row)
            if p is None:
                out["n_skip"] += 1
                continue
            if p["src_key"] in seen:
                out["n_dup"] += 1
                continue
            try:
                memory.remember(MemoryKind.SKILL, p,
                                source_channel="lesson_ledger")
            except MemoryQuarantineError:
                # 被写入门拒绝：已进 memory_quarantine；计 skip 子类，不静默
                out["n_quarantined"] += 1
                out["n_skip"] += 1
                continue
            seen.add(p["src_key"])
            out["n_written"] += 1
            if limit is not None and out["n_written"] >= int(limit):
                break
    return out


#: 模型自述的做法：不是验证过的方法，只在判分通过时才落库
_METHOD_SOURCE = "llm_self_report"


def from_term(memory: Any, task: str, prompt: str, method: str,
              passed: bool, quality: Optional[float] = None,
              procedure: Optional[Dict[str, Any]] = None,
              evidence_ref: str = "",
              source_channel: str = "llm_self_report") -> Optional[str]:
    """★ R458 · term 判分**通过** ⇒ 把模型自述的做法写成 SKILL。

    为什么需要：term 失败只写 failure_sig（"错在哪"），成功却什么都不写
    ⇒ 记忆里永远只有负样本，函数类题目召回恒空。

    为什么只在通过时写：`method` 是模型自述（未验证）；只有它给出的答案
    被判分器判为正确，这条"怎么做"才至少有**一次实证**背书。
    payload 带 `m_source=llm_self_report` —— 读者能看出它不是人工核定的。

    ★ M1.2：`procedure` 来自真实 `actions_log`（`procedure_from_actions`）；
      有步骤 ⇒ `skill_kind=procedural`，没有则保持 classifier 的判断。
      没有 procedure 也不编步骤，`procedure_status=not_instrumented`。
    """
    if not passed or not str(method or "").strip():
        return None
    scene = _clip(prompt or task, 400)
    m = _clip(method, 800)
    if len(scene) < 4 or len(m) < 4:
        return None
    proc = procedure if isinstance(procedure, dict) else {}
    steps = proc.get("steps") if isinstance(proc.get("steps"), list) else []
    kind = "procedural" if steps else classify_skill_kind(scene, m)
    payload = {
        "scene": scene,
        "method": m,
        "boundary": "term_pass:%s" % _clip(task, 80),
        "invalid_conditions": "任务不是「%s」时不适用" % scene[:60],
        "recovery_strategies": _RECOVERY,
        "skill_kind": kind,
        "preconditions": proc.get("preconditions") or [],
        "steps": steps,
        "tools": proc.get("tools") or [],
        "verification": proc.get("verification") or [],
        "failure_modes": proc.get("failure_modes") or [],
        "evidence_ref": evidence_ref or proc.get("evidence_ref") or "",
        "procedure_status": proc.get("procedure_status") or "not_instrumented",
        "src_key": src_key(scene, m),
        "task_id": _clip(task, 80),
        "m_source": _METHOD_SOURCE,
        "quality": quality,
    }
    return memory.remember(MemoryKind.SKILL, payload,
                           source_channel=source_channel)


def from_task_result(memory: Any, task: str, prompt: str, result: Any,
                     passed: bool, quality: Optional[float] = None
                     ) -> Optional[str]:
    """从一次**已判分通过**的任务结果写过程技能（M1.2 接线口）。

    ★ 只认真实 `actions_log`；没有动作 / 没有 trajectory_ref ⇒ 不写。
    ★ `passed` 必须由外部判分器给出，不能拿 `status=done` 冒充正确。
    """
    if not passed or not isinstance(result, dict):
        return None
    proc = procedure_from_actions(
        result.get("actions_log") or [],
        evidence_ref=str(result.get("trajectory_ref") or ""))
    if not proc.get("steps"):
        return None
    method = str(result.get("answer") or "").strip()
    if not method:
        return None
    return from_term(memory, task, prompt, method, passed=True,
                     quality=quality, procedure=proc,
                     evidence_ref=str(result.get("trajectory_ref") or ""),
                     source_channel="task_trajectory")


def skill_count(memory: Any) -> int:
    """生产核对用：库里 skill 节点数。"""
    try:
        return int(memory._conn.execute(
            "SELECT COUNT(*) FROM memory_node WHERE kind='skill'").fetchone()[0])
    except Exception:                     # noqa: BLE001
        return -1
