# -*- coding: utf-8 -*-
"""R204 · 铁律运行时执行面 —— GateSnapshot.laws_block 的真实来源。

定位声明（G1 定位门）: **DWC-AUTO（自我强化）** —— 铁律守卫的是自我强化
  的边界（冻结主权/效用锚/熔断/脱敏），属自我强化约束面而非记忆底座。

★★★ TRUTH_SOURCE · 本模块的系统外真值源（G2 真值门）:
    判定只读 **config/iron_laws.yaml 文件字节**（黄金配置文件, agent 不可写
    —— 与 judge.py 的 dev.json 同款地位）: 律的 id/severity/check_fn/
    enforcement/certification_limit_text 全部来自该文件, 本模块不缓存不改写。
    ⇒ 文件读不到 ⇒ _load_cfg raise（不静默返回空律表 —— 空表=装作没有铁律）。

★★★ 为什么存在（审计发现族 F1 同款）:
  iron_laws.yaml 的 11 条 check_fn **全部只有名字没有实现**（yaml 尾部
  自陈"本文件不含实现"）—— ARSI 的病根是「10 条铁律生效 0 条」而没有任何
  机制承认这一点。本模块把配置面接进 run_term 盘点:

  · 有真输入的律        ⇒ **真判**（pass / warn / block）
  · 本轮无对象的律      ⇒ na（gates.py 三态同款 —— 无对象 ≠ 过）
  · 数据面无设置方的律  ⇒ not_instrumented + 逐条 why（**可审计的缺席**）

  ⇒ 产出 IronReport 进 rep.iron_report; block/warn 喂 _build_state 的
    laws_block/laws_warn —— 这就是该字段的真实来源（此前恒 () = 装死）。

★★ G11（severity=meta, check_fn=null）不进检查路径（yaml 设计: 恒真的
  否定性承诺, 没有可违反的状态 —— 给它编 check_fn 就是 ARSI 的病）。
  其唯一执行形式 enforcement=report_must_quote 由本模块落地:
  run_term 先执行「摘录」（get_certification_limit 把 yaml 的
  certification_limit_text 写进 rep.certification_limit）, 再执行「判在位」
  （evaluate 判字段非空, 缺 ⇒ block[G11]）—— 报告必引认证限制, 真执行。

判据 I8（每个 check_fn 调用点 > 0）: checked 列表就是调用证据。
"""
from __future__ import annotations

import io
import os
from typing import Any, Dict, List, Optional

import yaml

#: ★★ G2 真值源声明（系统外文件 — 判定读它的字节, 不信内存自述）
TRUTH_SOURCE = [("iron_laws", os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))),
    "config", "iron_laws.yaml"))]

#: 本模块的真值源路径（= TRUTH_SOURCE[0][1] — 同源单点, 不两处维护）
IRON_YAML = TRUTH_SOURCE[0][1]

#: ★ 数据面无设置方的律 —— 逐条 why 全部为 2026-10-12 R204 src 全仓 grep 实测
_NOT_INSTRUMENTED: Dict[str, str] = {
    "G2": "层阈值结构不存在 —— dials/drift/difficulty 均为单层 config（无 i<j 层级可单调）",
    "G3": "frozen 字段无设置方 —— src 全仓 grep 'frozen' 零业务命中（ARSI 同款病: 读的字段没人写）",
    "G4": "memory_consolidate 不存在 —— memory.py grep 'consolidat' 零命中",
    "G5": "effect 数据面不存在 —— credit/evolver/applier grep 'effect' 零命中",
    "G6": "runner 无 LLM client 句柄 —— n_fail 状态活在 llm/client 实例上, run_term 拿不到",
    "G7": "Lyapunov 无埋点 —— src grep 'lyapunov' 零命中（仅 yaml 有名字）",
    "G9": "高熵判定无实现 —— memory_write/decision 触发点无熵度量",
    "G10": "sealed 访问无审计日志面 —— splitfeed 有锁语义但无访问留痕可判",
}

#: ★ 本轮无对象（na）—— trigger 的对象在 term 周期内不存在（非数据面问题）
_NA: Dict[str, str] = {
    "G1": "trigger=pre_apply —— run_term 盘点无候选落地动作"
          "（设计/执行分离的判据点在落地时刻, applier 不在 term 周期）",
}

#: G8（唯一有真输入可判的 warn 律）—— trigger=proposal_gate → term 盘点映射:
#: 因果链五环齐套（与 T1 判据同源的 stages 真数据）
_REQUIRED_STAGES = ("decision", "turn", "trace", "experience", "change")


def _load_cfg(path: str = IRON_YAML) -> Dict[str, Any]:
    """配置面加载（形态校验 — 没校验的 yaml 只是文本, core 同款纪律）。"""
    obj = yaml.safe_load(io.open(path, encoding="utf-8").read())
    if not isinstance(obj, dict) or "version" not in obj:
        raise ValueError("iron_laws.yaml 缺 version")
    laws = obj.get("laws")
    if not isinstance(laws, list) or not laws:
        raise ValueError("iron_laws.yaml 的 laws 必须是非空列表")
    return obj


def get_certification_limit(path: str = IRON_YAML) -> str:
    """★ G11 的唯一执行形式（enforcement=report_must_quote）的**动作侧**:
    把 certification_limit_text 摘进报告字段。空串 = 配置缺席（会被
    evaluate 判 block[G11] —— 不静默装有）。
    """
    cfg = _load_cfg(path)
    for law in cfg["laws"]:
        if law.get("severity") == "meta" and law.get("check_fn") is None:
            return str(law.get("certification_limit_text") or "").strip()
    return ""


def evaluate_for_term(rep: Any, *, certification_limit_present: bool,
                      path: str = IRON_YAML) -> Dict[str, Any]:
    """★ run_term 盘点点的铁律评估 —— 真判/na/not_instrumented 三态+。

    返回 IronReport:
      block / warn      : 真判违规的律 id（喂 _build_state.laws_block/laws_warn）
      checked           : 真判过的律（含 verdict/how —— 判据 I8 调用证据）
      na                : 本轮无对象（无对象 ≠ 过）
      not_instrumented  : 数据面无设置方（逐条 why —— 可审计的缺席）
    """
    cfg = _load_cfg(path)
    block: List[str] = []
    warn: List[str] = []
    checked: List[Dict[str, Any]] = []
    na: List[Dict[str, str]] = []
    not_instr: List[Dict[str, str]] = []
    stages = {x.get("stage") for x in (getattr(rep, "stages", None) or [])}
    for law in cfg["laws"]:
        lid = str(law.get("id"))
        sev = str(law.get("severity"))
        if sev == "meta":
            # ── G11 · report_must_quote: 判「摘录动作已发生」──
            ok = bool(certification_limit_present)
            checked.append({"id": lid, "severity": sev,
                            "verdict": "pass" if ok else "block",
                            "how": "enforcement=report_must_quote: "
                                   "rep.certification_limit 非空"})
            if not ok:
                block.append(lid)
            continue
        if lid in _NA:
            na.append({"id": lid, "severity": sev, "why": _NA[lid]})
            continue
        if lid in _NOT_INSTRUMENTED:
            not_instr.append({"id": lid, "severity": sev,
                              "why": _NOT_INSTRUMENTED[lid]})
            continue
        if lid == "G8":
            # ── G8 · 因果链五环齐（trigger=proposal_gate → term 盘点映射）──
            missing = [x for x in _REQUIRED_STAGES if x not in stages]
            ok = not missing
            checked.append({"id": lid, "severity": sev,
                            "verdict": "pass" if ok else "warn",
                            "how": "五环 stages 齐套（T1 同源真数据）",
                            "missing": missing})
            if not ok:
                warn.append(lid)
            continue
        # ★ 新律未接判据 ⇒ 显式 not_instrumented（不静默跳过 — G7 同族）
        not_instr.append({"id": lid, "severity": sev,
                          "why": "R204 执行器未接此律判据（新律须显式接判据或扩表）"})
    return {"block": block, "warn": warn, "checked": checked, "na": na,
            "not_instrumented": not_instr, "n_laws": len(cfg["laws"]),
            "note": "四态: block/warn=真判 · na=本轮无对象 · "
                    "not_instrumented=数据面无设置方（逐条 why 可审计）"}
