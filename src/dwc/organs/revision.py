"""revision · 记忆后向修订触发器（ReHarness 2610.12668 §3.2 — R258）。

★★★ 定位（G1）: **DWC-MEM** —— 记忆管线的反馈回写; 非评分（G2）。

=== 论文机制（§3.2/3.3）===
  前向 harness 的病: 写入的反思永不基于**下游效果**更新 ⇒ 过度泛化/过时
  条目持续误导（论文 sorting 反例; 实测 stability 全线负值）。
  解法: 任务完成后, 用「源轨迹 τ_i + 当前任务成败 τ_t」修订**检索用过的
  条目**; 新内容必须 grounded 在源轨迹（τ_t 只作反馈 — 防泄漏）。

=== DWC 双轨（诚实对齐架构）===
  · memory 轨（本模块 + MemoryKernel.revise）: SKILL 条目（EXPERIENCE 区）
    —— evolve/term 管场景, 结构化版本链。
  · 文件轨（agent_quality.revision_lessons）: dwc_skills/*.md 规矩
    —— agent 接单场景（lessons_context 注入面）。
  两轨共享触发纪律:
    ★ diagnostic gate（§6 poker 教训）: 只在任务 status ∈ {done, failed}
      时修订 —— incomplete/超时是**噪声反馈**, 不修订。
    ★ grounding: 修订必引源（文件轨引教训条目, memory 轨引 source_traj）。
    ★ 事件流不修订（R104 同族）: lessons JSONL 是失败事实, 只修规矩解读。
"""
from __future__ import annotations

import json
import sys
from typing import Any

from dwc.organs.memory import MemoryKernel, MemoryKind
from dwc.observability.context import measurement_role


def revise_from_outcome(memory: MemoryKernel, llm: Any, *,
                        task: str, status: str,
                        fail_why: str = "") -> dict[str, Any]:
    """★ 任务结局 → 修订该任务检索用过的 SKILL 条目（memory 轨）。

    diagnostic gate: status 不在 {done, failed} ⇒ 跳过（噪声不修）。
    返回 {"revised": int, "skipped": str|None, "details": [...]}。
    """
    if status not in ("done", "failed"):
        return {"revised": 0, "skipped": "nondiagnostic", "details": []}
    cands = [n for n in memory.last_retrieved(n=8)
             if n.kind is MemoryKind.SKILL
             and n.payload.get("method") or n.payload.get("scene")]
    if not cands:
        return {"revised": 0, "skipped": "no_retrieved_skill", "details": []}
    details = []
    for n in cands[:2]:        # ★ k=2（论文 k=5 检索修订; DWC 任务小, 保守起步
        prompt = (
            "记忆条目曾被用于任务, 请按任务结局**修订**它（有条件则加限定, "
            "过时则改写; 新内容必须来自条目自身的证据, 不许编造）。\n"
            "任务: %s\n结局: %s\n%s\n"
            "原条目(scene=%s, method=%s, boundary=%s):\n%s\n"
            "只输出 JSON: {\"scene\": \"…\", \"method\": \"…\", "
            "\"boundary\": \"…\"}"
            % (task[:300], status, ("失败原因: " + fail_why[:200]) if fail_why else "",
               n.payload.get("scene", ""), str(n.payload.get("method", ""))[:80],
               str(n.payload.get("boundary", ""))[:120],
               json.dumps({k: v for k, v in n.payload.items()
                           if not k.startswith("_")},
                          ensure_ascii=False)[:800]))
        try:
            with measurement_role("revision"):
                r = llm.complete(prompt, json_mode=True)
            obj = json.loads(r.text or "{}") if getattr(r, "ok", False) else {}
        except Exception as exc:                # noqa: BLE001 — 修订失败不阻断
            sys.stderr.write("mem_revise LLM 失败: %s\n" % exc)
            continue
        if not isinstance(obj, dict) or not obj.get("method"):
            continue
        try:
            # ★ D6: SKILL 五字段门槛 — 以旧 payload 为底, 只覆盖修订的三字段
            merged = {k: v for k, v in n.payload.items()
                      if not k.startswith("_")}
            merged.update({
                "scene": obj.get("scene", n.payload.get("scene", "")),
                "method": obj.get("method", ""),
                "boundary": obj.get("boundary", "")})
            new_id = memory.revise(
                n.node_id, merged,
                source_traj="outcome:%s/%s" % (task[:80], status),
                why="任务%s, 回修检索条目" % status)
            details.append({"old": n.node_id, "new": new_id.node_id})
        except Exception as exc:                # noqa: BLE001
            sys.stderr.write("mem_revise 落库失败: %s\n" % exc)
    return {"revised": len(details), "skipped": None, "details": details}
