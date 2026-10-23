"""★ EvaluatorEpochGuard —— R113 · E1 约束半（设计稿④ §⑤ epoch/checkpoint 合同）。

定位声明（DWC-MEM · 记忆底座 · 判据 G1 定位门）
  epoch 合同 = 段内评估器冻结、点界才可换（RQGM 2606.26294 指数 checkpoint
  同款: "只在 checkpoint 上、且只按 anchor best-belief 换评估器"）。
  本类 = 合同的**约束执行者**: E1 落类+探针（零行为风险）, E2 换代流接入。

★ 分层边界（设计稿④ §④）: 锚与判分执行不进化; 本 guard 锁的是
  **评估策略层的 epoch 冻结** — 不是锁锚。
★ E1 范围: 冻结/换界/记录。challenger 对拍+平票在位者 = E2（须接入
  meta-eval 准入门后才许换）。
"""
from __future__ import annotations

import time
from typing import Any

__all__ = ["EpochViolation", "EvaluatorEpochGuard"]


class EpochViolation(RuntimeError):
    """★ 段内改评估器 ⇒ raise（不是警告不是日志 — 合同的牙齿）。"""


class EvaluatorEpochGuard:
    """epoch 内评估器冻结 + 点界换代记录。

    用法（E2 接入后的形, E1 由测试驱动）:
        g = EvaluatorEpochGuard(epoch_id=3, judge_fingerprint="<fp8>")
        g.check(current_fp)          # 段内任何时点: 不一致 ⇒ raise
        g.close_epoch(new_fp)        # 点界换代: 记录 + 锁移
    """

    def __init__(self, epoch_id: int, judge_fingerprint: str):
        if not isinstance(epoch_id, int) or epoch_id < 0:
            raise EpochViolation("epoch_id 必须非负 int: %r" % (epoch_id,))
        if not (isinstance(judge_fingerprint, str)
                and len(judge_fingerprint) == 8):
            raise EpochViolation(
                "judge_fingerprint 必须 8 位: %r" % (judge_fingerprint,))
        self.epoch_id = epoch_id
        self.judge_fingerprint = judge_fingerprint
        #: 换代轨迹（点界记录 — G7: 换代不许无痕）
        self.transitions: list[dict[str, Any]] = []

    def check(self, current_fingerprint: str) -> None:
        """★ 段内合同: 当前评估器指纹 ≠ 本 epoch 锁 ⇒ 违约 raise。"""
        if current_fingerprint != self.judge_fingerprint:
            raise EpochViolation(
                "★ epoch %d 段内评估器变更被拒: 锁 %s ≠ 当前 %s — "
                "换代只能走点界 close_epoch（设计稿④ §⑤合同）"
                % (self.epoch_id, self.judge_fingerprint,
                   current_fingerprint))

    def close_epoch(self, new_fingerprint: str, *, reason: str,
                    by: str = "challenger_win") -> int:
        """点界换代: 记录轨迹 + 锁移到新指纹 + 返回新 epoch_id。

        ★ E2 义务（本方法只记不裁）: 调用方必须已完成 challenger 对拍
          （meta-eval 准入 + 锚比对 + 平票在位者）—— 本类不复核对拍,
          对拍完整性由 E2 的 challenger 流保证（诚实边界: 见稿 §⑧）。
        """
        if not reason:
            raise EpochViolation("换代必须给 reason（G7 不许无痕换标准）")
        if new_fingerprint == self.judge_fingerprint:
            raise EpochViolation(
                "换代指纹与在位者相同 ⇒ 不是换代（平票在位者已由对拍层裁, "
                "此处防误记）")
        self.transitions.append({
            "from_epoch": self.epoch_id, "from_fp": self.judge_fingerprint,
            "to_fp": new_fingerprint, "reason": reason, "by": by,
            "at": time.time()})
        self.epoch_id += 1
        self.judge_fingerprint = new_fingerprint
        return self.epoch_id

    def to_dict(self) -> dict[str, Any]:
        return {"epoch_id": self.epoch_id,
                "judge_fingerprint": self.judge_fingerprint,
                "n_transitions": len(self.transitions),
                "transitions": list(self.transitions)}
