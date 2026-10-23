"""contract · FGGM 契约检查（2603.25111 §4.2 · V2 门②「判定能力是否真可用」）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 服务门组的第 ② 步: 候选被 leakage 放过之后, 检查它是否**满足
    它自己声明的输入/输出契约**（(Φ_l, Ψ_l) 局部一阶公式）。
  ★ 不抢位: 不判正确性语义（judge 的事）· 不判收益（非补偿门）·
    不合成一阶公式（planner LLM 的事 — 性质 1 Flexibility）。
  ★ Alg 4 check 是**机械检查器**: 给定 (x, y) 与契约, 返回真/假;
    它不理解契约的意义（理解在验证器 — DWC 尚未接）。

★★★ TRUTH_SOURCE（判据 G2）
  本模块只检查**已注册契约的机械实例**（值域/类型/反射性等可判定子集）
  — 不产生"这个改动好不好"的判断; 一阶语义面显式 not_instrumented。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

#: FGGM 七字段（Eq.15 BNF 逐字段 — 值枚举, 不自创字段）
FGGM_FIELDS: tuple[str, ...] = ("id", "gmid", "type_sig", "phi_l", "psi_l",
                                "f_p", "f_d")

#: 检查结论（check 的三值 — false 必须带违规记录, 不许静默）
ST_CHECKED = "checked"
ST_NO_CONTRACT = "no_contract"     # 没注册契约（不是违规 — 显式缺席）
ST_NO_FALLBACK = "no_fallback"     # 无 fallback ⇒ 拒（性质 4）


class ContractError(Exception):
    """契约定义/注册的显式拒绝（缺字段/fallback 缺/检查器非 callable）。"""


@dataclass(frozen=True)
class FGGM:
    """一条 FGGM 声明的**DWC 可落地子集**（七字段 + 机械检查器）。

    ★ id 唯一; f_d（fallback）非 None（性质 4: 没有 fallback 拒绝采样器
      可能耗尽样本; fallback 是"契约对所有参数无条件成立"的机制）;
    ★ check 是 Alg 4 的 DWC 代理: 一个**确定性** callable
      (x, y) -> bool —— 本模块只认"确定性检查器", 不认 LLM 自评
      （DWC 无验证器 ⇒ LLM 检查算语义面, 显式不进本模块 — 见模块头）。
    """

    id: str
    type_sig: str
    check: Callable[[Any, Any], bool]
    fallback: Callable[..., Any]
    gmid: str = ""
    phi_l: str = ""
    psi_l: str = ""
    f_p: str = ""
    info: str = ""

    def __post_init__(self) -> None:
        if not self.id:
            raise ContractError("FGGM.id 非空")
        # ★ f_d（fallback）是 DWC 落点的必填字段（性质 4 — 无它拒绝采样
        #   可能耗尽; f_p/gmid/phi/psi 是描述性字段, 可空但有 note 兜底）
        if self.fallback is None:
            raise ContractError("FGGM.f_d（fallback）必填（性质 4）")
        if not callable(self.check):
            raise ContractError("FGGM.check 须为 callable (x, y) -> bool")
        if not callable(self.fallback):
            raise ContractError("FGGM.f_d 须可调用（已验证的 fallback）")

    def run_fallback(self, *args: Any, **kw: Any) -> Any:
        """★ 已验证的 fallback 入口（Fig.2 (2) 的 DWC 落点）。

        ★ 语义对齐论文: fallback 可能"缺乏 GM 的解题能力（低任务性能）",
          但阻止进入不安全状态（高约束满足）⇒ 调用方拿它当兜底, 不当作
          正常产物评估。
        """
        return self.fallback(*args, **kw)


class ContractRegistry:
    """契约注册表 + check 门（同 id 重注册即抛 — 不静默换契约）。"""

    def __init__(self) -> None:
        self._f: dict[str, FGGM] = {}

    def register(self, f: FGGM) -> None:
        if f.id in self._f:
            raise ContractError(
                "契约重名 %r（不静默换契约 — 先 unregister）" % (f.id,))
        self._f[f.id] = f

    def unregister(self, fid: str) -> None:
        if fid not in self._f:
            raise KeyError(fid)
        del self._f[fid]

    def get(self, fid: str) -> FGGM | None:
        return self._f.get(fid)

    def check(self, fid: str, x: Any, y: Any) -> dict[str, Any]:
        """★ Alg 4 check 的 DWC 落地: 确定性检查 + fallback 在场校验。

        返回（三值显式 — 不许把"没契约"混成"契约失败"）:
          · no_contract — 该 id 未注册（显式缺席, 不是通过）
          · ok=True/False — 检查器判定 + 违规上下文
        """
        f = self._f.get(fid)
        if f is None:
            return {"status": ST_NO_CONTRACT, "id": fid,
                    "ok": None,                       # ★ None ≠ False
                    "note": "未注册契约 ⇒ 显式缺席（不默认通过）"}
        ok = bool(f.check(x, y))
        return {"status": ST_CHECKED, "id": fid, "ok": ok,
                "note": ("契约违反 — 该候选不许过门②"
                         if not ok else "契约满足")}

    def summary(self) -> dict[str, Any]:
        return {"n_registered": len(self._f),
                "ids": sorted(self._f),
                "fields": list(FGGM_FIELDS)}


# ── 论文两个实例的 DWC 复刻（可判定子集 — 逐字段对账） ──────────────

def bounded_param(l: float, u: float) -> FGGM:
    """★ 实例 1（§4.2 原文逐字映射）: Ψ_l: (l ≤ f) ∧ (f ≤ u); f_d = clamp。"""
    if not (isinstance(l, (int, float)) and isinstance(u, (int, float))):
        raise ContractError("bounded_param l/u 须数值")
    return FGGM(id="boundedParam(%r,%r)" % (l, u),
                gmid="NN^2: R^2 -> R", type_sig="(l: float, u: float) -> float",
                phi_l="", psi_l="(l <= f(l,u)) and (f(l,u) <= u)",
                info="§4.2 boundedParam 实例",
                check=lambda x, y: (float(x[0]) <= float(y) <= float(x[1])),
                # f_d(l, u, y) = min(max(l, y), u) — clamp（论文原式, DWC 收 (x,y) 两参）
                fallback=lambda x, y: min(max(float(x[0]), float(y)),
                                          float(x[1])))


def dafny_annotate_identity(p: Any) -> FGGM:
    """★ 实例 2（§4.2 原文逐字映射）: Φ_l: parse(p); f_d = p（反射性回退）。

    ★ DWC 落点用**纯函数域**复刻反射性: check(x,y) = (y == x)（Dafny 的
      reflexivity 公理 ∀x. parse(x) ⟹ noDiff(x,x) 在"不改内容"域的等价
      形态）; f_d(y)=x（回退到原输入）。
    """
    return FGGM(id="dafnyAnnotate", gmid="llm", type_sig="p -> p",
                phi_l="parse(p)",
                psi_l="parse(p) and noDiff(p, f(p))",
                info="§4.2 dafnyAnnotate 实例（DWC 反射性子集: y==x）",
                check=lambda x, y: (y == x),
                fallback=lambda x, y: x)


def no_diff_fallback(p: Any, y: Any) -> Any:
    """论文原句 f_d(p, y) = p — 回退到原程序（反射性保证的可复用件）。"""
    return p


CONTRACT_MECHANICS: dict[str, str] = {
    "seven_fields": "Eq.15 BNF: id;GMid;typeSig;(Φ_l,Ψ_l);f_p;f_d;info",
    "four_properties": "§4.2: Flexibility / Parameter-Independent / Local Objective / fallback 必要性",
    "fallback_why": "无 fallback ⇒ 拒绝采样可能耗尽; fallback=约束无条件成立的关键",
    "dwc_subset": "只做确定性 check + fallback 注册（Alg 4 机械面）",
    "verify_gap": "一阶验证器未接 ⇒ 语义面 not_instrumented（契约检查≠契约证明）",
}
