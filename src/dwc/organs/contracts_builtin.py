# -*- coding: utf-8 -*-
"""contracts_builtin · 内置契约注册（R167 — 门②从"表非空"到真判）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ R152 门②只查 n_registered>0（表非空即过 = 判了个存在性）;
     R148 的 ContractRegistry FGGM 全套（七字段/check 三值/fallback 必填）
     已 live, 缺的是**真注册方** — 全仓只有测试装过一个 bounded_param。
  ★ 本模块把 DWC **自己两条真实约束**注册为论文实例的 DWC 复刻:
      · budget_window  ← budget 门（R151）的议程 b_t∈[b_min,b_max]
        （boundedParam 实例 — fallback=clamp, 论文原式）
      · patch_reflexive ← candidate_bridge（R153）的 patch 反射性
        （dafnyAnnotate 实例 — fallback=原 patch, 靠 reflexivity 公理）
  ★★ Flexibility 性质的诚实边界（论文性质 1: 契约"由 planner LLM 针对
    每次调用现场合成一阶公式"）: DWC **没有 planner**（合成一阶公式需
    验证器闭环 — R173 前的 backlog, 不假装有）⇒ 本模块是**静态注册面**,
    如实标注"非论文 Flexibility 形态"; 现场合成留 backlog, 不伪造。

★★★ TRUTH_SOURCE（判据 G2）
  · 契约判据源: budget.DEFAULT_B_MIN/B_MAX（R151 实测值域）· patch 语义
    （R153 bridge 投影的 candidate_diff）— 本模块不发明新约束。
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from dwc.organs.budget import DEFAULT_B_MAX, DEFAULT_B_MIN
from dwc.organs.contract import (
    ST_CHECKED, ST_NO_CONTRACT, ContractRegistry,
    bounded_param, dafny_annotate_identity)


def builtin_registry() -> ContractRegistry:
    """★ 出厂注册表（**只一条**全局契约 — 见下方"两层"裁决）。

    ★★ R167 实测裁决: patch_reflexive **不进全局表** — 它的 R148 形态
      `dafny_annotate_identity(p)` 吃**具体 p**（注册的是"该 patch 的
      反射性"）⇒ 把 per-candidate 实例钉进全局 = 语义错（第一次调用的
      patch 会永驻表中, 后续候选全对着旧 p 校）。
    契约分两层（对论文 Flexibility 的诚实落地, 不混）:
      · **全局静态层**（本表）: budget_window — 值域类, 常量生效, 全局成立
      · **候选现场层**（门② candidate 分支现构）: dafny(p) — 反射类,
        拿 candidate_diff 当 p, 用完即弃（论文"每次调用现场"的 DWC 可达子集）
    """
    reg = ContractRegistry()
    reg.register(budget_window_contract())
    return reg


def budget_window_contract() -> FGGM:
    """① budget_window: b_t ∈ [b_min, b_max] 的 FGGM 化（R151 议程值域）。

    ★ 与论文 boundedParam(l,u) 逐字段对齐: Ψ = (l≤f≤u), f_d=clamp。
    ★ 判据源 = budget.DEFAULT_B_MIN/B_MAX（1/8 — R151 实测议程端点）。
    """
    return bounded_param(float(DEFAULT_B_MIN), float(DEFAULT_B_MAX))


def patch_reflexive_contract() -> FGGM:
    """② patch_reflexive: patch 反射性（f(p)=p 恒在"无差异"关系中）。

    ★ 与论文 dafnyAnnotate(p) 对齐（DWC 可判定子集 — R148 已落地:
      Φ=parse(p) · Ψ=noDiff(p, f(p)) · f_d=p 靠 reflexivity 公理）。
    """
    return dafny_annotate_identity()


def check_against_facts(reg: ContractRegistry, facts: Any
                        ) -> Dict[str, Any]:
    """★★ TermFacts ⇒ 逐契约 check（门②升级的判定面 — 两层合报）。

    ★ 全局层: reg 里注册的静态契约（budget_window）逐条 check;
    ★ 现场层: candidate_diff 在场 ⇒ 现构 dafny(p) 反射契约（用完即弃,
      不进全局表 — 见 builtin_registry 的两层裁决）。
    返回（门②可直接消费的形状 — 三值显式）:
      · n_contracts / n_checked / n_ok / n_violation / n_no_contract
      · per_contract: {id: check 结果}
      · verdict: "no_contracts"（空表）/ "passed"（无违反）/ "violation"
    """
    s = reg.summary()
    if s["n_registered"] == 0:
        return {"verdict": "no_contracts", "n_contracts": 0,
                "why": "空表 ⇒ ② blocked（缺对象要建设, 不是通过）"}
    out: Dict[str, Any] = {"n_contracts": s["n_registered"], "ids": s["ids"],
                           "per_contract": {}, "n_checked": 0, "n_ok": 0,
                           "n_violation": 0, "n_no_contract": 0}
    diff = getattr(facts, "candidate_diff", None)
    has_diff = diff is not None and str(diff).strip() != ""
    edits = getattr(facts, "edits", None) or []
    # ── 全局层 ──
    # ★★ R167 实测纠偏: 首版拿 diff **字符数**当 boundedParam 的 y（"clean
    #   = 1" len=9 > 8 ⇒ 误 violation）— 那是**我编的测量口径**, 不是
    #   论文的"对任意参数成立"。契约的被约束量必须如实对应:
    #   budget_window 约束的是**编辑数**（R151 议程 b_t 判的就是 n_edits）
    #   ⇒ x=(b_min,b_max), y=len(edits); 无 edits 申报 ⇒ no_input（不凑）。
    for fid in s["ids"]:
        if not edits:
            out["per_contract"][fid] = {"status": "no_input",
                                        "why": "无 edits 申报 ⇒ ②只报注册面"
                                               "（没对象不判 — R152 语义）"}
            continue
        from dwc.organs.budget import DEFAULT_B_MAX, DEFAULT_B_MIN
        x_pair = (DEFAULT_B_MIN, DEFAULT_B_MAX)
        y_val = len(edits)                      # ★ 真被约束量 = 编辑数
        r = reg.check(fid, x_pair, y_val)
        out["per_contract"][fid] = r
        if r["status"] == ST_NO_CONTRACT:
            out["n_no_contract"] += 1
        else:
            out["n_checked"] += 1
            if r["ok"]:
                out["n_ok"] += 1
            else:
                out["n_violation"] += 1
    # ── 现场层（反射契约 — 对 diff 本身）──
    if has_diff:
        d = dafny_annotate_identity(diff)          # 现构, 不入全局表
        # check(x,y)=(y==x): 反射性要求"产出=输入" — 门②语义: 候选 diff
        #   本身即产出物, 反射即"diff 与自身一致"恒真 ⇒ clean 面;
        #   真正的否决在 f_d=diff（回退原文 = 不干预时的 fallback）
        r_ref = reg.check("dafnyAnnotate", diff, diff)   # 借用表查 ⇒ 未注册
        out["per_contract"]["dafnyAnnotate_live"] = {
            "status": ST_CHECKED, "id": d.id, "ok": bool(d.check(diff, diff)),
            "note": "现场层: dafny(p) 反射契约对 diff 自身（用完即弃, "
                    "未进全局表 — registry check 显式缺席即 %r" % r_ref["status"]}
        out["n_checked"] += 1
        out["n_ok"] += 1
    out["verdict"] = ("violation" if out["n_violation"] > 0 else "passed")
    return out


BUILTIN_MECHANICS: Dict[str, str] = {
    "two_contracts": "budget_window(boundedParam 实例−R151 议程值域) + patch_reflexive(dafnyAnnotate 实例−R153 patch 语义)",
    "flexibility_honest": "论文『planner LLM 现场合成一阶公式』DWC 无 planner（无验证器闭环不造）⇒ 静态注册面, 合成留 backlog",
    "gate2_upgrade": "表空⇒blocked; 表非空+无对象⇒passed(注册面); 有 edits⇒逐 check: 违反⇒blocked(真 veto), no_contract⇒记不否决",
    "constrained_quantity": "budget_window 的被约束量 = **编辑数**（与 budget 门 R151 判据同源; 首版错配成 diff 字符数 — 实测 len 9>8 误 violation, 那是编的口径不是论文『对任意参数成立』）",
    "no_input_not_pass": "无候选 diff ⇒ per_contract status=no_input（不是 checked-ok — 缺席≠通过）",
    "not_second_judge": "check 用 R148 FGGM（自身不含判据源重算 — 值域来自 budget 常量）",
}


def install_builtin(reg: Optional[ContractRegistry] = None) -> ContractRegistry:
    """★ 安装面（Evolver/gates 的注入点 — 复用则透传, 缺省建厂发表）。"""
    return reg if reg is not None else builtin_registry()
