"""memory_guard · 记忆写入的来源信任与污染检查（M1.6）。

定位声明 · **DWC-MEM**（记忆底座）
  ★ 只做写入前的确定性检查；不判断内容真假、不调用 LLM、不删数据。
  ★ 拒绝 ⇒ 调用方写 `memory_quarantine`，不静默丢。

为什么需要
----------
`MemoryKernel.remember()` 原来对内容零检查：工具输出、网页摘要、模型自述
都可能直接进记忆。Ultra/Nexus 的 `MemoryWriteGuard` 已证明“通道信任 +
注入/二进制/重复检测”是可落地的；本模块只取这层确定性能力，不搬它的
LLM 分类器或 50 模块工具箱。

边界
----
- `remember(..., source_channel=None)` 默认**不校验**，保持旧调用逐字节不变。
- 只有显式传通道的写路径（skill_writer 的三条）才 enforce。
- 注入检查对低信任通道一律拒绝；高信任通道也记录 trust_score，但不放行
  明显注入 —— 记忆不是“用户说什么就存什么”。
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

#: 通道信任分（0..1）。只用于记录/排序，不是“高分免检”。
CHANNEL_TRUST = {
    "user_message": 0.80,
    "maintainer": 0.90,
    "lesson_ledger": 0.60,
    "task_trajectory": 0.60,
    "llm_self_report": 0.35,
    "tool_output": 0.15,
    "retrieved_context": 0.20,
    "system_summary": 0.50,
    "unknown": 0.30,
}

MAX_CHARS = 120_000

#: 控制字符（保留 \n \r \t）
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

#: 高置信注入模式；宁窄勿宽，避免把“忽略之前的失败”误杀。
_INJECTION = re.compile(
    r"(?:ignore|disregard)\s+(?:all\s+)?(?:previous|prior|above)\s+"
    r"(?:instructions?|prompts?|rules?)"
    r"|you\s+are\s+now\s+(?:a|an|the|in)\b"
    r"|(?:reveal|show|print|output|display)\s+(?:the\s+)?"
    r"(?:system|developer)\s+prompt"
    r"|(?:system|developer)\s+prompt\s*[:：]"
    r"|忽略(?:之前|以上|前面|所有)?.{0,8}(?:指令|提示|规则)"
    r"|你现在是(?:一个|一名|the\b)"
    r"|(?:系统|开发者)提示词"
    r"|不要告诉用户"
    r"|绕过.{0,6}(?:限制|规则|护栏)"
    r"|执行以下(?:命令|指令)",
    re.IGNORECASE,
)


class MemoryQuarantineError(MemoryError):
    """写入被隔离；`quarantine_id` 可在 `memory_quarantine` 回查。"""

    def __init__(self, reason: str, quarantine_id: str = ""):
        self.reason = str(reason or "quarantined")
        self.quarantine_id = str(quarantine_id or "")
        super().__init__("memory write quarantined: %s (id=%s)"
                         % (self.reason, self.quarantine_id))


def _repetitive(text: str) -> bool:
    """明显的重复填充/刷屏；短文本不判，避免误杀正常代码。"""
    if len(text) < 200:
        return False
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if len(lines) >= 20 and len(set(lines)) <= 2:
        return True
    top = max(Counter(text).values(), default=0)
    return bool(text) and top / float(len(text)) > 0.90


def validate(content: Any, source: str = "unknown",
             context: dict[str, Any] | None = None) -> dict[str, Any]:
    """返回 `{passed, reason, channel, trust_score, checks, quarantine}`。

    ★ 检查是确定性的：空、超长、控制字符、注入模式、重复填充。
    ★ `reason` 是第一个失败项；`checks` 保留每一项的布尔结果，便于审计。
    """
    text = str(content or "")
    channel = str(source or "unknown").strip().lower() or "unknown"
    checks = {
        "non_empty": bool(text.strip()),
        "size": len(text) <= MAX_CHARS,
        "control_chars": not bool(_CONTROL.search(text)),
        "injection": not bool(_INJECTION.search(text)),
        "repetition": not _repetitive(text),
    }
    reason = ""
    for key in ("non_empty", "size", "control_chars", "injection",
                "repetition"):
        if not checks[key]:
            reason = key
            break
    return {
        "passed": not reason,
        "reason": reason,
        "channel": channel,
        "trust_score": float(CHANNEL_TRUST.get(channel, CHANNEL_TRUST["unknown"])),
        "checks": checks,
        "quarantine": bool(reason),
    }
