"""noncomp · 非补偿门三步（2609.24972 §3.3 原文 · V2 门⑤「顺序不可换」）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 服务门组的第 ⑤ 步: 噪声地板 → 成本规则/整形 → 领域守卫。**非补偿
    （non-compensatory）**: 每一步独立否决, 别的项表现好**不能补偿**某
    一步失败 —— 与 seesaw 式加权门的根本差别（原文反复强调）。
  ★ 不抢位: 不判总分（judge）· 不算 split 差（split 门, R 已 live 于
    evolver）; 本模块只做**阈值型**判定（确定性, 输入已算好的 S/ΔS/ΔC/
    ν_str/guards — 由调用方给）。
  ★ 与退火预算（式 4 b_t）的关系: 式 4 是** proposer 侧约束**（本轮允许多
    少可归因编辑）, 不是本门的评估输入; 两者不同层（设计稿列门⑥）。

★★★ TRUTH_SOURCE（判据 G2）
  判定只基于**注入的已算数值**（S/ΔS/ΔC/ν_str）—— 本模块不重新计算分
  数（那样它就成了第二个 judge; 引用 R14 教训: 只读已判事实）。
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

#: 门的判定结论（显式三值 — None/缺输入⊥ 与 reject 分开）
PASS = "pass"
REJECT = "reject"
BLOCKED = "blocked"        # 输入口径外（缺 δ/缺域守卫表等）⇒ 无法判


class NonCompError(Exception):
    """门输入/参数的显式拒绝（负 δ / 权重越界 / 守卫表口径混用）。"""


@dataclass(frozen=True)
class GateInput:
    """一次非补偿判定的输入（全部已算数值 — TRUTH_SOURCE: 本模块不算分）。

    ★ score S 与被改进分 S_star 都须在场（地板判据要两者差）;
      delta_s（ΔS）/delta_c（ΔC）/nu_str（ν_str）按 2a/2b 分支语义给;
      domain_guard_ok: 领域守卫表判定（调用方给 — 本模块不重判域）。
    ★ noise_band δ（S*−δ 的 δ）必填 ≥0; 缺 ⇒ blocked（不能硬设 0 =
      地板失效 = 静默放行）。
    """

    score: float
    score_star: float
    delta_s: float
    delta_c: float
    nu_str: float = 0.0
    noise_band: float | None = None
    domain_guard_ok: bool | None = None
    floor_weights: dict[str, float] | None = None   # 2b 整形权重

    def __post_init__(self) -> None:
        for n in ("score", "score_star", "delta_s", "delta_c", "nu_str"):
            v = getattr(self, n)
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise NonCompError("%s 须数值, 实 %r" % (n, v))
        if self.noise_band is not None and self.noise_band < 0:
            raise NonCompError("noise_band δ 须 ≥0, 实 %r" % (self.noise_band,))
        if self.domain_guard_ok is not None and not isinstance(
                self.domain_guard_ok, bool):
            raise NonCompError(
                "domain_guard_ok 须 bool 或 None（None=未提供 ⇒ 步骤③ blocked）")


def _weights(inp: GateInput) -> tuple[float, float, float]:
    """2b 整形权重（缺省等权 — 调用方可覆盖; 权重须非负且不全 0）。"""
    d = inp.floor_weights or {}
    ws = float(d.get("ws", 1.0))
    wc = float(d.get("wc", 1.0))
    wn = float(d.get("wn", 1.0))
    for name, w in (("ws", ws), ("wc", wc), ("wn", wn)):
        if w < 0:
            raise NonCompError("权重 %s 须 ≥0, 实 %r" % (name, w))
    if ws == 0 and wc == 0 and wn == 0:
        raise NonCompError("整形权重不全 0（全 0 ⇒ 门永假/永真, 禁）")
    return ws, wc, wn


def evaluate(inp: GateInput) -> dict[str, Any]:
    """★ 非补偿三步（顺序不可换 — 任一步失败即 reject, 后续不跑）。"""
    if not isinstance(inp, GateInput):
        raise NonCompError("evaluate 要 GateInput, 实 %r"
                           % (type(inp).__name__,))
    steps: list[dict[str, Any]] = []

    # ① 噪声地板 Ŝ ≥ S* − δ（δ 缺 ⇒ blocked — 不许硬设 0）
    if inp.noise_band is None:
        return {"verdict": BLOCKED, "steps": [], "why":
                "noise_band δ 未提供 ⇒ 地板不可判（不硬设 0 — 静默放行禁）",
                "order": list(NONCOMP_ORDER)}
    floor = inp.score_star - inp.noise_band
    ok1 = inp.score >= floor
    steps.append({"step": "noise_floor", "ok": ok1,
                  "detail": "Ŝ=%.4f %s S*−δ=%.4f" % (
                      inp.score, "≥" if ok1 else "<", floor)})
    if not ok1:
        return {"verdict": REJECT, "steps": steps, "why":
                "① 噪声地板未过（Ŝ < S*−δ ⇒ 收益在噪声带内不可信）",
                "order": list(NONCOMP_ORDER)}

    # ② 成本规则/整形（按 ΔS > δ 分支 — 原文 2a/2b, 顺序在①之后）
    if inp.delta_s > inp.noise_band:
        # 2a 成本规则: ΔC ≤ β₀ + β₁·ΔS（β 缺省 0/1 ⇒ ΔC ≤ ΔS — 标注口径）
        beta0, beta1 = 0.0, 1.0
        limit = beta0 + beta1 * inp.delta_s
        ok2 = inp.delta_c <= limit + 1e-12
        steps.append({"step": "cost_rule", "ok": ok2,
                      "branch": "2a (ΔS>δ)",
                      "detail": "ΔC=%.4f %s β₀+β₁ΔS=%.4f"
                                % (inp.delta_c, "≤" if ok2 else ">", limit)})
    else:
        ws, wc, wn = _weights(inp)
        shaped = ws * inp.delta_s - wc * inp.delta_c + wn * inp.nu_str
        ok2 = shaped > 0
        steps.append({"step": "shaped", "ok": ok2,
                      "branch": "2b (ΔS≤δ)",
                      "detail": "ws·ΔS−wc·ΔC+wn·ν_str=%.4f %s 0"
                                % (shaped, ">" if ok2 else "≤")})
    if not ok2:
        return {"verdict": REJECT, "steps": steps, "why":
                "② %s 未过" % steps[-1]["step"], "order": list(NONCOMP_ORDER)}

    # ③ 领域守卫（缺判定 ⇒ blocked — 守卫表是外部知识, 不默认放过）
    if inp.domain_guard_ok is None:
        return {"verdict": BLOCKED, "steps": steps, "why":
                "③ domain guards 未提供判定 ⇒ blocked（守卫放行权不在本模块）",
                "order": list(NONCOMP_ORDER)}
    steps.append({"step": "domain_guards", "ok": bool(inp.domain_guard_ok),
                  "detail": "守卫判定=%r" % (inp.domain_guard_ok,)})
    if not inp.domain_guard_ok:
        return {"verdict": REJECT, "steps": steps, "why":
                "③ 领域守卫未过（即使①②都好也不能补偿 — 非补偿语义）",
                "order": list(NONCOMP_ORDER)}

    return {"verdict": PASS, "steps": steps,
            "why": "①②③全过（各步独立成立 — 非补偿: 不可互偿）",
            "order": list(NONCOMP_ORDER)}


def batch(inputs: Sequence[GateInput]) -> list[dict[str, Any]]:
    """批量（保序 — 评估按候选序进）。"""
    return [evaluate(i) for i in inputs]


#: 三步顺序（原文 §3.3 — 值枚举, 顺序即契约）
NONCOMP_ORDER: tuple[str, ...] = ("noise_floor", "cost_or_shaped",
                                  "domain_guards")

NONCOMP_MECHANICS: dict[str, str] = {
    "order": "噪声地板 → 成本规则(2a)/整形(2b) → 领域守卫（顺序不可换）",
    "non_compensatory": "每步独立否决 — 别的步骤好不能补偿某步失败（与 seesaw 加权门根本差别）",
    "blocked_not_pass": "δ 缺/守卫缺 ⇒ blocked（不硬设默认值 ⇒ 静默放行禁）",
    "annealing_elsewhere": "式 4 退火预算是 proposer 侧约束（本轮可归因编辑数）, 不是本门输入（设计稿门⑥）",
    "truth_source": "输入 S/ΔS/ΔC/ν_str 全由调用方算好（本模块不算分 — 防第二个 judge）",
}
