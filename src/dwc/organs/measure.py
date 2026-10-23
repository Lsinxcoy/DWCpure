"""measure · 四量度量（2609.11873 · EVOLUTION_CORE_V2 §3.3「写了≠用了」）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 服务环节⑤/⑦ 的**质检面**: 把"一个候选改进"的生命周期切成四段分别
    度量 —— update quality（写得对不对）/ activation（会不会被检索到）/
    faithful use（检索到会不会照做）/ downstream benefit（照做有没有
    用）。治"98.8% 未访问无人发现"的病（只测①=假装完整）。
  ★ 不抢位: 不判分（judge）· 不记因果链（wiring）· 不改被观测方 ——
    本模块只**投影**已存在的事实面（judge 三数 / 记忆统计 / 调用方注入
    的执行痕迹）, 不插入 memory 内部（recall_search 的"不记 access"是
    R22 语义, 不许破坏）。

★★★ TRUTH_SOURCE（判据 G2）
  本模块**不产生**成功判定 — 四个量的分子/分母全部来自调用方注入或
  已判事实投影; 缺埋点 ⇒ **显式 not_instrumented**（X2 纪律: 缺席≠0,
  不许编 0.0 冒充"测过了"）。

=== 四量在 DWC 的可算性审计（R144 取证结论, 逐条有依据）===
  ① update quality      **可算** ← judge.score（三数口径, 现成）
  ② activation          **未埋点** — recall_search 不记 access（R22 语义,
                        access_count 归 recall() 专有）⇒ not_instrumented
  ③ faithful use        **未埋点** — 无"检索到⇒按 method 执行"的痕迹面
                        ⇒ not_instrumented
  ④ downstream benefit  **部分可算** — 若调用方能给"用了 vs 没用"两组的
                        judge 分数差, 可算; 否则 not_instrumented
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

#: 四量 id（2609.11873 §原文顺序 — 值枚举, 不自创量）
QUANTITIES: tuple[str, ...] = ("update_quality", "activation",
                               "faithful_use", "downstream_benefit")

#: 未埋点标记（显式 — 调用方不得把缺席读成 0）
NOT_INSTRUMENTED = "not_instrumented"


class MeasureError(Exception):
    """四量输入的显式拒绝（负值/超界/口径混用）。"""


@dataclass(frozen=True)
class UpdateQuality:
    """① 写得对不对 — judge 三数投影（R14 口径: 未评价不混入）。

    ★ n_pass/n_fail/not_evaluated ≥0 且不全 0（空判⇒ raise — 没判≠0 分）;
      quality = n_pass/(n_pass+n_fail)（not_evaluated 显式旁列不进分母）。
    """

    n_pass: int
    n_fail: int
    not_evaluated: int = 0

    def __post_init__(self) -> None:
        for n in ("n_pass", "n_fail", "not_evaluated"):
            v = getattr(self, n)
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise MeasureError("UpdateQuality.%s 须 ≥0 整数, 实 %r"
                                   % (n, v))
        if self.n_pass == 0 and self.n_fail == 0:
            raise MeasureError(
                "空判定（pass=fail=0）⇒ 无质量事实（未判≠0 分 — R14）")

    def as_dict(self) -> dict[str, Any]:
        den = self.n_pass + self.n_fail
        return {"instrumented": True,
                "quality": self.n_pass / den if den else None,
                "n_pass": self.n_pass, "n_fail": self.n_fail,
                "not_evaluated": self.not_evaluated,
                "note": "quality=pass/(pass+fail); 未评价旁列不进分母"}


@dataclass(frozen=True)
class Activation:
    """② 会不会被检索到（埋点投影面, 由调用方喂 — 本模块不插 memory）。

    ★ n_items 总候选资产数 ≥0; n_retrieved ≥0 且 ≤ n_items;
      activation = n_retrieved/n_items（n_items=0 ⇒ 口径外 raise — 空库
    不是 0% 命中）。★ 未喂 ⇒ NOT_INSTRUMENTED（recall_search R22 语义
    不记 access ⇒ DWC 暂无系统内自动源）。
    """

    n_items: int
    n_retrieved: int

    def __post_init__(self) -> None:
        for n in ("n_items", "n_retrieved"):
            v = getattr(self, n)
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise MeasureError("Activation.%s 须 ≥0 整数, 实 %r"
                                   % (n, v))
        if self.n_items == 0:
            raise MeasureError("n_items=0 ⇒ 空库无分母（不是 0% 命中）")
        if self.n_retrieved > self.n_items:
            raise MeasureError("n_retrieved(%d) > n_items(%d) — 口径越界"
                               % (self.n_retrieved, self.n_items))

    def as_dict(self) -> dict[str, Any]:
        return {"instrumented": True,
                "activation": self.n_retrieved / self.n_items,
                "n_items": self.n_items, "n_retrieved": self.n_retrieved}


@dataclass(frozen=True)
class FaithfulUse:
    """③ 检索到会不会照做 — 用了的里面有多少**按 method 执行**。

    ★ n_retrieved_used ≥0（检索到且被用的）; n_faithful ≥0 且 ≤ 前者;
      faithful = n_faithful/n_retrieved_used（0 ⇒ 口径外 raise）。
    ★ 未喂 ⇒ NOT_INSTRUMENTED（无执行痕迹面）。
    """

    n_retrieved_used: int
    n_faithful: int

    def __post_init__(self) -> None:
        for n in ("n_retrieved_used", "n_faithful"):
            v = getattr(self, n)
            if isinstance(v, bool) or not isinstance(v, int) or v < 0:
                raise MeasureError("FaithfulUse.%s 须 ≥0 整数, 实 %r"
                                   % (n, v))
        if self.n_retrieved_used == 0:
            raise MeasureError("n_retrieved_used=0 ⇒ 无分母（没检索到被用"
                               "⇒ faithful 无定义, 不是 0）")
        if self.n_faithful > self.n_retrieved_used:
            raise MeasureError("n_faithful(%d) > 分母(%d) — 口径越界"
                               % (self.n_faithful, self.n_retrieved_used))

    def as_dict(self) -> dict[str, Any]:
        return {"instrumented": True,
                "faithful": self.n_faithful / self.n_retrieved_used,
                "n_retrieved_used": self.n_retrieved_used,
                "n_faithful": self.n_faithful}


@dataclass(frozen=True)
class DownstreamBenefit:
    """④ 照做有没有用 — 用了的一组的 judge quality 差（无独立成功判定）。

    ★ quality_used/quality_unused ∈[0,1]（调用方从 judge 投影 — 本模块
      不再判分）; benefit = used − unused（正=用了更好）。
    ★ 任一侧 None ⇒ not_instrumented（不拿 0 顶替 — 那样"照做没用"和
      "没测"就分不开了）。
    """

    quality_used: float | None = None
    quality_unused: float | None = None

    def __post_init__(self) -> None:
        for v in (self.quality_used, self.quality_unused):
            if v is not None and (isinstance(v, bool)
                                  or not isinstance(v, (int, float))
                                  or not (0.0 <= v <= 1.0)):
                raise MeasureError("quality_* 须为 None 或 [0,1], 实 %r"
                                   % (v,))

    def as_dict(self) -> dict[str, Any]:
        if self.quality_used is None or self.quality_unused is None:
            return {"instrumented": False, "status": NOT_INSTRUMENTED,
                    "note": "缺单侧质量 ⇒ 不算差（缺席≠0: 不拿 0 顶替"
                            "『照做没用』）"}
        return {"instrumented": True,
                "benefit": self.quality_used - self.quality_unused,
                "quality_used": self.quality_used,
                "quality_unused": self.quality_unused}


def measure(update: UpdateQuality | None = None,
            activation: Activation | None = None,
            faithful: FaithfulUse | None = None,
            downstream: DownstreamBenefit | None = None
            ) -> dict[str, Any]:
    """★ 四量汇总（2609.11873 §口径 — 缺的量显式 not_instrumented）。

    ★ 返回 health: 四量中**已埋**数量（0..4）+ 逐量明细。
      health=1（只有①）就是母巢那个病（只测写得对不对）— 数字说话。
    """
    # ★ 按位校验（位置即口径 — 把 Activation 喂给 update 位要显式拒绝,
    #   否则"谁是哪个量"靠调用方自觉 = 静默错配）
    parts: list[tuple[str, Any | None, type]] = [
        ("update_quality", update, UpdateQuality),
        ("activation", activation, Activation),
        ("faithful_use", faithful, FaithfulUse),
        ("downstream_benefit", downstream, DownstreamBenefit)]
    out: dict[str, Any] = {}
    instrumented = 0
    for name, obj, cls in parts:
        if obj is None:
            out[name] = {"instrumented": False, "status": NOT_INSTRUMENTED,
                         "note": "调用方未提供该量输入 ⇒ 显式缺席"
                                 "（不编 0.0）"}
        else:
            if not isinstance(obj, cls):
                raise MeasureError(
                    "四量输入类型不匹配: %s 位须 %s, 实为 %r（口径混用"
                    " — 位置即口径, 不靠自觉）"
                    % (name, cls.__name__, type(obj).__name__))
            out[name] = obj.as_dict()
            if out[name].get("instrumented"):
                instrumented += 1
    return {"quantities": out, "instrumented_count": instrumented,
            "of": len(QUANTITIES),
            "health": ("%d/%d 埋点 — %s" % (
                instrumented, len(QUANTITIES),
                "只测①=母巢那个病（写得对错 ≠ 被用）" if instrumented == 1
                else "多维度在测") if instrumented else "无量"),
            "quantities_order": list(QUANTITIES)}


MEASURE: dict[str, str] = {
    "four_quantities": "2609.11873: update quality / activation / faithful use / downstream benefit",
    "disease": "只测① ⇒ 98.8% 未访问无人发现（母巢实证）",
    "noshow": "缺埋点 ⇒ not_instrumented（缺席≠0 — 不编 0.0 冒充测过）",
    "instr_status": "① judge 现成可算 · ②③④ 缺系统埋点（recall_search R22 不记 access）",
}
