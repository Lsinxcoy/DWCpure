"""R303-④ Project视图（对标 Cursor Projects 轻量版）。

同组任务共享认知：task_id 前缀归组，取同组近3任务留痕拼 ≤5 行短 hint。
纯规则、零 LLM。IO（读 sessions 台账）由调用方做，本模块只做纯拼装。

定位声明（DWC-MEM · 记忆底座）：跨任务共享认知沉淀 ⇒ 属 DWC-MEM。
"""
from __future__ import annotations

MAX_CHARS = 400
MAX_TASKS = 3
MAX_LINES = 5


def proj_id(task_id: str) -> str:
    """归组：code_fix_007→code_fix；无下划线原样返回。永不抛错。"""
    try:
        t = str(task_id)
        return t.rsplit("_", 1)[0] if "_" in t else t
    except Exception:
        return ""


def project_hint(task_id: str, group_traces: dict[str, list[str]]) -> str:
    """group_traces: {同组task_id: [留痕串]}。返回 hint（空组返回 ""）。"""
    try:
        if not group_traces:
            return ""
        keys = sorted(group_traces)[:MAX_TASKS]
        lines: list[str] = []
        for k in keys:
            for s in (group_traces.get(k) or [])[:2]:
                lines.append("%s：%s" % (k, str(s)[:80]))
                if len(lines) >= MAX_LINES:
                    break
            if len(lines) >= MAX_LINES:
                break
        h = "本组前情：" + "；".join(lines)
        return h[:MAX_CHARS]
    except Exception:
        return ""
