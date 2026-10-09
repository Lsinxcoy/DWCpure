# -*- coding: utf-8 -*-
"""router · 七桶路由（2609.14857 ModularRSI Appendix B Table 8 · EVOLUTION_CORE_V2 §3.2）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 服务环节⑥/⑦ 之间的**诊断→演化路由**：把一次 term 的观测（通过/失败
    分布 + 成本）分成 Table 8 原文的 7 桶，**决定该 term 的候选有没有
    进化资格**（infra_only 不进化 — 否则演化会试图用 harness 改动去修
    环境 bug, 论文原文的明确禁令）。
  ★ 不抢位: 不判分（judge 职责）· 不改动（applier 职责）· 不聚类（evolver
    .diagnose 职责）—— 本模块只做**已判分结果**的桶分类与路由裁决。
  ★ 目录说明: EVOLUTION_CORE_V2 目录树把本模块画在 `①diagnosis/router.py`,
    但 DWC 现有惯例是 organs/ 扁平（evolver/judge/replay 并列）⇒ 按
    **一致性 > 设计稿目录**落 organs/router.py（逻辑分组在模块头保留）。

★★★ TRUTH_SOURCE（判据 G2）
  本模块**不产生**任何判定分数 — 输入 pass/fail 计数与 cost 由调用方给
  （judge 判分投影 + CostLedger 台账）; 桶归属是**对这些已判事实的分类",
  "不是新的成功判定。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: Table 8 原文七桶（2609.14857 Appendix B — 值枚举, 不自创桶）
BUCKETS: Tuple[str, ...] = (
    "all_pass_efficient",   # 全过且成本低于 BudgetGate 上限
    "all_pass_wasteful",    # 全过但成本超上限（省成本也是改进面）
    "mixed",                # 有过有败（正常改进面）
    "fixable_fail",         # 全败但可修（当前权限/工具/上下文下能改）
    "stuck_fail",           # 同签名重复 N 次仍失败 ⇒ recovery hint
    "unreachable_fail",     # 当前权限/工具/上下文下不可能成功 ⇒ 弃权
    "infra_only",           # 只观测到 infra/环境层失败 ⇒ 不进化
)

#: 弃权是一等输出（Table 8 Listing 2: is_culprit=false / fixable_now=false）
ACTIONS: Tuple[str, ...] = ("propose", "recovery_hint", "abstain",
                            "no_evolution", "no_diagnosis")

#: 桶 ⇒ 路由动作（Table 8 原文处理策略 — 不许改语义）
ROUTE: Dict[str, str] = {
    "all_pass_efficient": "no_evolution",     # 无改进面可提
    "all_pass_wasteful": "propose",           # 成本面改进（省浪费）
    "mixed": "propose",                        # 失败侧提改动
    "fixable_fail": "propose",                 # 提改动
    "stuck_fail": "recovery_hint",             # 同动作重复失败 ⇒ 恢复提示
    "unreachable_fail": "abstain",             # 弃权（一等输出）
    "infra_only": "no_diagnosis",              # 不进诊断（论文原文禁令）
}
#: 进化资格（哪些桶的候选允许进 evolver — infra_only 明确除外）
EVOLVABLE: Tuple[str, ...] = tuple(
    b for b in BUCKETS if ROUTE[b] in ("propose", "recovery_hint"))


class RouterError(Exception):
    """路由输入的显式拒绝（负计数/成本负/口径越界）。"""


@dataclass(frozen=True)
class TermObservation:
    """一次 term 的**已判事实**（调用方注入, 本模块不判分 — TRUTH_SOURCE）。

    ★ n_pass/n_fail ≥0 且不全 0（空 term 无观测 ⇒ 不给桶, 显式拒绝）;
      infra_fail = 环境/harness 层失败计数（非被测对象失败）。
    ★ cost ≤ budget_ceiling ⇒ efficient; 超过 ⇒ wasteful（成本维度。
      budget_ceiling None ⇒ 不做成本判（口径外不猜, 返回带 note）。
    """

    n_pass: int = 0
    n_fail: int = 0
    infra_fail: int = 0
    cost: Optional[float] = None
    budget_ceiling: Optional[float] = None
    repeat_signature_count: int = 0   # 同失败签名重复次数（stuck 判据）
    stuck_threshold: int = 3          # Table 8 语义: 重复 N 次仍失败
    reachable: bool = True            # 当前权限/工具/上下文下可成功?
    signature_present: bool = False   # 失败是否带 (c,q,m) 签名

    def __post_init__(self) -> None:
        for name in ("n_pass", "n_fail", "infra_fail",
                     "repeat_signature_count", "stuck_threshold"):
            v = getattr(self, name)
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise RouterError(
                    "TermObservation.%s 须为 ≥0 整数, 实为 %r" % (name, v))
        if self.n_pass == 0 and self.n_fail == 0 and self.infra_fail == 0:
            raise RouterError(
                "空观测（pass=fail=infra=0）⇒ 无事实可分桶（不是 all_pass）")
        if self.cost is not None and self.cost < 0:
            raise RouterError("cost 须 ≥0（CostLedger 口径）, 实为 %r"
                             % (self.cost,))
        # cost/budget_ceiling 的真判据在 route()（wasteful 需 n_fail==0
        # ∧ cost>ceiling — 构造期只做值域校验, 不预判桶）


def route(obs: TermObservation) -> Dict[str, Any]:
    """★ 七桶路由（Table 8 原文语义 — 顺序判定, 先 infra 后 reach）。

    判定链（顺序即优先级, 与论文"infra_only 不进诊断"的排他性一致）:
      ① infra_only     : 唯一失败源是 infra（n_pass==0 ∧ n_fail==0 ∧ infra>0）
      ② all_pass_*     : n_fail==0 ∧ infra==0（成本分 efficient/wasteful）
      ③ unreachable    : reachable=False（当前不可能成功 ⇒ 弃权）
      ④ stuck_fail     : repeat_signature_count ≥ stuck_threshold
      ⑤ fixable_fail   : 签名在且可修（默认 — 有签名就是可修证据）
      ⑥ mixed          : 其余有败情形
    """
    if not isinstance(obs, TermObservation):
        raise RouterError("route 要 TermObservation, 实为 %r"
                          % (type(obs).__name__,))

    # ① infra_only（只观测到环境层失败 — 排除 harness 改动修环境 bug）
    if obs.n_pass == 0 and obs.n_fail == 0 and obs.infra_fail > 0:
        bucket = "infra_only"
    # ② 全过（成本维度再分 efficient/wasteful）
    elif obs.n_fail == 0 and obs.infra_fail == 0 and obs.n_pass > 0:
        if (obs.cost is not None and obs.budget_ceiling is not None
                and obs.cost > obs.budget_ceiling):
            bucket = "all_pass_wasteful"
        else:
            bucket = "all_pass_efficient"
    # ③ unreachable（当前权限/工具/上下文下不可能成功 — 弃权一等输出）
    elif not obs.reachable:
        bucket = "unreachable_fail"
    # ④ stuck（同签名重复 N 次仍失败 ⇒ recovery hint 而非改动）
    elif obs.repeat_signature_count >= obs.stuck_threshold:
        bucket = "stuck_fail"
    # ⑤ mixed（有过有败 — 非全败的失败情形: pass>0 ∧ fail>0）
    elif obs.n_pass > 0 and obs.n_fail > 0:
        bucket = "mixed"
    # ⑥ fixable（全败但有签名 ⇒ 可指认 component — 提改动）
    elif obs.n_fail > 0:
        bucket = "fixable_fail"
    # ⑦ 兜底（不可达: 上面②③④已覆盖全过/不可达/stuck, ⑤⑥覆盖有败）
    else:
        raise RouterError(
            "桶判定落入兜底 — TermObservation 组合未覆盖: "
            "pass=%d fail=%d infra=%d reachable=%s"
            % (obs.n_pass, obs.n_fail, obs.infra_fail, obs.reachable))

    action = ROUTE[bucket]
    return {
        "bucket": bucket,
        "action": action,
        "evolvable": bucket in EVOLVABLE,
        "route": dict(ROUTE),           # 全表随行（调用方免查表）
        "evolvable_buckets": list(EVOLVABLE),
        "note": _note(bucket, obs),
    }


def _note(bucket: str, obs: TermObservation) -> str:
    """路由理由（人读 — 每个桶一句话出处, 备考勤）。"""
    if bucket == "infra_only":
        return ("infra_only ⇒ 不诊断（Table 8: infra 失败若进诊断, 演化会"
                "试图用 harness 改动修环境 bug — 明文禁令）")
    if bucket == "all_pass_wasteful":
        return ("全过但 cost=%.3f > ceiling=%.3f ⇒ 省成本是改进面"
                % (obs.cost, obs.budget_ceiling))
    if bucket == "all_pass_efficient":
        return "全过且成本在限 ⇒ 无改进面 ⇒ 不进化"
    if bucket == "unreachable_fail":
        return "当前权限/工具/上下文下不可能成功 ⇒ 弃权（一等输出）"
    if bucket == "stuck_fail":
        return ("同签名重复 %d ≥ 阈值 %d 仍失败 ⇒ recovery hint 而非改动"
                % (obs.repeat_signature_count, obs.stuck_threshold))
    if bucket == "fixable_fail":
        return "失败带签名且可修 ⇒ 提改动"
    return "混合观测 ⇒ 走失败侧提改动"


def batch(observations: Sequence[TermObservation]) -> List[Dict[str, Any]]:
    """批量路由（保持顺序 — 调用方按 term 序列喂, 不改写次序）。"""
    return [route(o) for o in observations]
