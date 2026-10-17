# -*- coding: utf-8 -*-
"""planner · 契约现场合成面（器官⑧ planner · 2603.25111 §4.3 三阶段 DWC 复刻）。

DWC-AUTO（自我强化）: 契约合成 ⇒ 门②逐契约判 ⇒ 通过了才用 — 自我强化的
  判据面扩展; 不动 DWC-MEM 记忆底座（合成契约只进现场层, 不写记忆）。

★ R167 悬案的本轮解除: 论文性质 1 Flexibility（契约不能预定义, 由 planner
  LLM 针对每次调用现场合成一阶公式）。R167 裁决"DWC 无 planner ⇒ 留 backlog,
  不造 planner（越权无验证器）"—— **验证器现已四层齐**:
    ① judge 判分（真判）② 六门（②门逐契约 check + ⑤noncomp ΔS判）
    ③ R170 试跑复验 ④ R174 replay 不劣于 current
  ⇒ "合成-验证"闭环成立, 本模块补**合成面**。

★★ 安全边界（不开 eval 面）: LLM 只产**取参数**（模板族 JSON: 数值/集合/
  比较符）, **check 逻辑全静态白名单**（λ 在代码里, 不来自 LLM）。自由公式
  DSL（BNF Eq15 的完整一阶语言）不在 DWC 落点 — 理由: eval 字符串 = 注入面,
  且 DWC 判据是结构化 checks, 不是 Dafny 规格 ⇒ 白名单模板族是**有据的
  可判定子集**（contract.bounded_param 同款: 论文 §4.2 实例 1 的 DWC 复刻）。

★★ R167 边界保持: 合成契约**只进现场层**（per-candidate, 用完即弃,
  不进全局表）— 首次调用的 patch 永驻全局 = per-candidate 钉死全局 = 语义错。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from dwc.organs.contract import (FGGM, ContractError, ContractRegistry,
                                bounded_param)

#: ★ 模板族（白名单 — 静态 λ, 不来自 LLM; LLM 只选 kind + 填参）
TEMPLATES: Dict[str, Dict[str, Any]] = {
    # kind: {descriptor, params 说明, build}
    "bounded_param": {
        "doc": "Ψ_l: (l <= f) ∧ (f <= u); f_d = clamp（contract.bounded_param 同款）",
        "params": {"l": "float", "u": "float"},
        "build": lambda p: bounded_param(float(p["l"]), float(p["u"])),
    },
    "delta_band": {
        "doc": "ΔS = (v_after - v_before) ∈ [l,u]（e2e noise_band 的形式化）",
        "params": {"l": "float", "u": "float"},
        "build": lambda p: FGGM(
            id="deltaBand(%r,%r)" % (float(p["l"]), float(p["u"])),
            gmid="NN^2: R^2 -> R",
            type_sig="(l: float, u: float) -> float",
            phi_l="", psi_l="(%r <= d(v_after,v_before)) and "
                           "(d(v_after,v_before) <= %r)" % (float(p["l"]),
                                                            float(p["u"])),
            info="R175 delta_band 模板（e2e L558 delta_c=0.01 的形式化）",
            check=lambda x, y: (float(x[0]) <= float(y) <= float(x[1])),
            fallback=lambda x, y: min(max(float(x[0]), float(y)),
                                      float(x[1]))),
    },
    "enum_member": {
        "doc": "y ∈ S（取值域成员 — target/dimension 的有效集合）",
        "params": {"members": "list[str]"},
        "build": lambda p: FGGM(
            id="enumMember(%d)" % len(p["members"]),
            gmid="NN^1: Set -> bool",
            type_sig="(S: set[str]) -> bool",
            phi_l="", psi_l="y in S",
            info="R175 enum_member 模板（COMPONENT_VOCAB 取值域的形式化）",
            # ★★ R178 实测纠偏: 初版 `str(y) in set(x[0])` 吃 **x 参数** 的
            #   members — 但 FGGM.check(x,y) 的 x 是"契约自身参数组",
            #   planner 模板的参数在 build 时已固化（id/psi 里的就是）⇒
            #   构造后 FGGM 不持有原始 members ⇒ x=() 时 IndexError（实测
            #   踩过）。正确形态: 参数进**闭包**（build 时 captured）, check
            #   不依赖 x ⇒ 与 bounded_param 的 check(x,y) 协议兼容（x 可 ()）
            check=lambda x, y: (str(y) in set(p["members"])),
            fallback=lambda x, y: y),
    },
}


class PlannerError(Exception):
    """合成/校验失败必须大声报错（G7 同族 — 不许静默 ⊥）。"""


def available_templates() -> List[str]:
    """可合成模板族名（审计面 — planner 的能力边界）。"""
    return sorted(TEMPLATES)


def _validate_spec(spec: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """★★ Alg3 validateFGGM 的 DWC 版（本地校验 — 不把 llm 输出当真）。

    校验: kind 在白名单 · 参数类型对 · 数值有限 · enum 非空且全 str
    返回 (kind, params) — 任一条不过 ⇒ PlannerError（**带原因** — R175:
    这个 err 会回灌 llm, 所以必须具体到哪条不合规）
    """
    if not isinstance(spec, dict):
        raise PlannerError("spec 须 dict（llm 输出须为 json object）")
    kind = spec.get("kind")
    if kind not in TEMPLATES:
        raise PlannerError(
            "kind=%r 不在白名单 %r（DWC 只认模板族, 不开自由公式 — "
            "eval 面=注入面）" % (kind, available_templates()))
    params = spec.get("params")
    if not isinstance(params, dict):
        raise PlannerError("params 须 dict（模板参数表）")
    sig = TEMPLATES[kind]["params"]
    for k, want in sig.items():
        if k not in params:
            raise PlannerError("缺参数 %r（%s 需要 %r）" % (k, kind, sig))
        v = params[k]
        if want == "float":
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                raise PlannerError(
                    "参数 %r 须数值（实得 %r: %r）" % (k, type(v).__name__, v))
            import math as _m
            if not _m.isfinite(float(v)):
                raise PlannerError("参数 %r 非有限数（%r）" % (k, v))
        elif want == "list[str]":
            if not isinstance(v, list) or not v:
                raise PlannerError("参数 %r 须非空 list（实得 %r）" % (k, v))
            if not all(isinstance(s, str) and s.strip() for s in v):
                raise PlannerError("参数 %r 元素须非空 str" % (k,))
            # ★★ 退化契约防伪（R175 实测: LLM 从 code_fix 任务合出
            #   enumMember(1) — 单成员 S 恒真 ⇒ 契约无判定力 = 放水!）:
            #   成员 <2 的 enum 无分辨力 ⇒ 拒（与 ""or True"" 同族 — 门
            #   ②的"没契约≠契约满足"反方向: 有契约但恒真也不行）
            if len(v) < 2:
                raise PlannerError(
                    "参数 %r 的成员 <2（%r）— 单成员集合恒真 ⇒ 契约无判定力"
                    "（放水面 — 拒）" % (k, v))
    # ★★ 数值型模板的区间非退化（l < u — reversed/空区间恒假或恒真都
    #   是无判定力形态 — 与 enum 同纪律）
    if kind in ("bounded_param", "delta_band"):
        try:
            if float(params["l"]) >= float(params["u"]):
                raise PlannerError(
                    "参数区间退化 l=%r >= u=%r（空/单点区间无判定力 — 拒）"
                    % (params["l"], params["u"]))
        except (TypeError, ValueError) as exc:
            raise PlannerError("区间参数不可比: %s: %s" % (type(exc).__name__,
                                                        exc))
    return kind, params


def build_fggm(spec: Dict[str, Any]) -> FGGM:
    """validate + build（白名单构造器 ⇒ 真 FGGM; 构造自身炸 ⇒ PlannerError）。"""
    kind, params = _validate_spec(spec)
    try:
        return TEMPLATES[kind]["build"](params)
    except (ContractError, KeyError, TypeError, ValueError) as exc:
        raise PlannerError(
            "模板 %r 构造失败: %s: %s（kind/params 过了但 build 炸 — "
            "原因回灌 planner）" % (kind, type(exc).__name__, exc))


def parse_llm_spec(text: str) -> Dict[str, Any]:
    """LLM 文本 ⇒ spec dict（容忍 ```json 栅栏 — 模型常见输出形态）。"""
    t = (text or "").strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t[3:]
        if t.endswith("```"):
            t = t[:-3]
        t = t.strip()
        if t.lower().startswith("json"):
            t = t[4:].strip()
    try:
        obj = json.loads(t)
    except ValueError as exc:
        raise PlannerError("LLM 输出非 JSON: %s: %s（回灌重来）"
                           % (type(exc).__name__, exc))
    if isinstance(obj, list) and obj:
        obj = obj[0]                      # 模型有时包一层 list
    if not isinstance(obj, dict):
        raise PlannerError("LLM JSON 顶层须 object（实得 %r）"
                           % type(obj).__name__)
    return obj


def craft(task_view: Dict[str, Any], llm: Any, *,
          budget: int = 3) -> Tuple[Optional[FGGM], Dict[str, Any]]:
    """★★★ R175 三阶段（论文 Alg1 defineFGGM → validateFGGM → 包候选）。

    任务面 ⇒ LLM 合成 spec ⇒ 本地 validate+build ⇒ (FGGM, 痕迹)
    · 失败 ⇒ err 回灌（预算内重试; δ 耗尽 ⇒ (None, 痕迹) — **不返回
      假契约**; llm 不可用/未配置 ⇒ 同 ⊥）
    · 痕迹: attempts/trace（每次失败的原因 — 审计面, 可复盘）
    """
    trace: List[Dict[str, Any]] = []
    if llm is None or not getattr(llm, "configured", False):
        return None, {"outcome": "no_llm", "why": "llm 未配置 ⇒ 不合成",
                      "attempts": 0, "trace": trace}
    try:  # ★ R270-④ · 程序模板 hint（空库恒 None，零行为变化）
        from dwc.organs.workflow_templates import suggest_workflow
        _hint = suggest_workflow(str(task_view.get("kind", "")),
                                 dict(task_view))
        if _hint:
            task_view = dict(task_view, workflow_hint=_hint)
    except Exception:                            # noqa: BLE001
        pass
    prompt = compose_prompt(task_view)
    err: Optional[str] = None
    for attempt in range(1, max(1, budget) + 1):
        user = prompt if err is None else (
            prompt + "\n\n★★ 上次合成被拒, 原因: %s\n按原因修正, "
            "只回 JSON。" % err)
        res = llm.complete(user, json_mode=True, max_tokens=400)
        if not getattr(res, "ok", False):
            trace.append({"attempt": attempt, "stage": "llm",
                          "why": getattr(res, "error", "llm 失败")})
            err = "llm 调用失败"
            continue
        try:
            spec = parse_llm_spec(res.text)
            f = build_fggm(spec)
            return f, {"outcome": "crafted", "attempts": attempt,
                       "id": f.id, "trace": trace}
        except PlannerError as exc:
            trace.append({"attempt": attempt, "stage": "validate",
                          "why": str(exc)})
            err = str(exc)
    return None, {"outcome": "budget_exhausted", "attempts": budget,
                  "why": "err 回灌 %d 次未过（论文: δ 耗尽 ⇒ ⊥）" % budget,
                  "trace": trace}


def compose_prompt(task_view: Dict[str, Any]) -> str:
    """任务面 ⇒ planner prompt（白名单模板族 + 取参要求 — 结构封闭）。

    ★ 实现用 list-join（R175 教训: 字符串拼接里的 \n 经多层转义
      容易断串 — 实测踩过; join 形态无转义层）。
    """
    q = task_view.get("quantity")
    _planner_head = "你是 DWC 的契约合成器（planner）。为下面的任务面现场合成一份判定契约。"
    try:  # ★ R306 · prompt OTA（缺失⇒内嵌老路）
        from dwc.llm.prompt_ota import ota_system as _ota, note_miss as _ota_miss
        _planner_head = _ota("planner_head", _planner_head, __file__)
    except Exception:
        _ota_miss()
    _target = ""
    if q:
        _target = (
            "★★ 本次被约束量: %r（当前值 %r）— 契约必须约束**这个量**, "
            "别的字段只是背景, 别把背景当约束对象。"
            % (q.get("name"), q.get("value"))) + "\n"
    _dumps = json.dumps({k: {"doc": v["doc"], "params": v["params"]}
                         for k, v in TEMPLATES.items()}, ensure_ascii=False,
                        indent=1)
    try:  # ★ R307 · 模板渲染（失败⇒老路，老路一字不差）
        from dwc.llm.prompt_ota import render_here as _render
        from dwc.llm.prompt_ota import note_miss as _ota_miss2
        _t = _render("planner", {"head": _planner_head, "target_block": _target,
                                 "templates_dump": _dumps,
                                 "task_face": json.dumps(task_view,
                                                         ensure_ascii=False)[:600]},
                     __file__)
        if _t:
            return _t
    except Exception:
        _ota_miss2()
    lines: List[str] = [
        _planner_head,
    ]
    if q:
        # ★★ R178 实测纠偏: 不带靶 ⇒ LLM 曾把 diff_head 当 enum_member
        #   的 members（约束对象错）⇒ 回灌两次仍错 ⇒ ⊥。任务面必须显式
        #   声明"被约束量是什么、当前值多少"（论文每次调用现场的
        #   in-context 上下文）— 不给答案, 只给靶
        lines.append(_target.rstrip("\n"))
    lines += [
        "★★ 你只能从这些模板里选 kind 并填 params（白名单, 不许发明结构）:",
        json.dumps({k: {"doc": v["doc"], "params": v["params"]}
                    for k, v in TEMPLATES.items()}, ensure_ascii=False,
                   indent=1),
        "★ 任务面: " + json.dumps(task_view, ensure_ascii=False)[:600],
        "★★ 只回一个 JSON object: {\"kind\": <模板名>, \"params\": {...}}。",
        "数值用数字不用字符串; 不要解释、不要多余字段。",
    ]
    return "\n".join(lines)
