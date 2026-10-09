# -*- coding: utf-8 -*-
"""★ 六段继承产物 —— R109 · 稿①执行轮（综述 §7 原文六段的 DWC 落地）。

设计稿: docs/proposal_six_stage_inheritance.html（R108 过审稿）

定位声明（DWC-MEM · 记忆底座 · 判据 G1 定位门）
    六段继承产物 = knowledge3 知识档的字段扩展（跨轮可审计的继承记录），
    属记忆底座的档格式职责 ⇒ DWC-MEM。
六段  : parent state → proposed change → motivating evidence
        → evaluation configuration → acceptance decision → subsequent use

★ 四工业对照物的四必备属性（写入即校验, 违反 raise — G1/读前写入纪律）:
  Lark 时间接地    : at 是 ISO-8601 · gen 是 int
  Humanlaya 版本化 : parent_gen 链（== 上一档 gen, 断链 raise）
  Hyra 可执行经验  : 段2 kind∈{patch,config_delta,rule} ∧ exec_form 非空
  ARA 轨迹实证    : 段3 refs≥1 且每条 type+ref 齐（纯叙述=非法）

★ 只扩不破: 旧 knowledge3 档无 inheritance 键 ⇒ legacy（读取方按键分支）。
★ 段6 诚实: status=pending/invoked/effective/not_assessable 四值(pending+三态) +
  断供时 gap_note 必填（R106 双缺口同款 — 不留 null 装有）。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from typing import Any, Dict, List, Optional

__all__ = ["InheritanceError", "build_inheritance", "validate_inheritance",
           "attach_inheritance", "load_latest_gen"]

#: 六段键（顺序即 §7 原文顺序）
SEGMENTS = ("parent_state", "proposed_change", "motivating_evidence",
            "evaluation_config", "acceptance_decision", "subsequent_use")

#: 段2 可执行形态（Hyra 属性 — 三者皆无 ⇒ 非法）
CHANGE_KINDS = ("patch", "config_delta", "rule")

#: 段3 证据类型（ARA 属性 — 必机器可回查）
EVIDENCE_TYPES = ("trial_report", "commit", "gate_trace", "test",
                  "report_html")

#: 段6 状态（诚实四值: pending + 三态）
USE_STATUS = ("pending", "invoked", "effective", "not_assessable")

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}")  # Lark 属性


class InheritanceError(ValueError):
    """★ 六段不合格 ⇒ 写入期 raise（不留读取期发现 — 写入即校验）。"""


# ══════════════════════════════════════════════════
# 构造（收官流程调用 — 数字全由当轮实测注入, 不在此编造）
# ══════════════════════════════════════════════════
def build_inheritance(
    *,
    gen: int,
    parent_gen: Optional[int],
    at: str,
    parent_state: Dict[str, Any],
    proposed_change: Dict[str, Any],
    motivating_evidence: Dict[str, Any],
    evaluation_config: Dict[str, Any],
    acceptance_decision: Dict[str, Any],
    subsequent_use: Optional[Dict[str, Any]] = None,
    supersedes: Optional[str] = None,
) -> Dict[str, Any]:
    """构造六段对象（构造后立即 validate — 两步一体）。"""
    obj = {
        "gen": gen,
        "at": at,
        "parent_gen": parent_gen,
        "supersedes": supersedes,
        "parent_state": parent_state,
        "proposed_change": proposed_change,
        "motivating_evidence": motivating_evidence,
        "evaluation_config": evaluation_config,
        "acceptance_decision": acceptance_decision,
        # 段6 默认: 未观察 ⇒ pending + 断供说明（R106 缺口未接线前的诚实态）
        "subsequent_use": subsequent_use or {
            "status": "pending",
            "access": None, "effect": None,
            "observed_at_gen": None,
            "gap_note": ("recall/record_effect 生产喂数未接线 + 默认 "
                         ":memory: 不落盘（R106 双缺口）⇒ 本段尚无数据"),
        },
    }
    validate_inheritance(obj)
    return obj


# ══════════════════════════════════════════════════
# 校验（稿① §⑥ 七判据 — 逐条 raise 带定位信息）
# ══════════════════════════════════════════════════
def validate_inheritance(obj: Dict[str, Any]) -> None:
    if not isinstance(obj, dict):
        raise InheritanceError("六段对象必须是 dict, 实为 %r" % type(obj))

    # 判据1 · 六段齐全（缺段 ⇒ 继承物不可审计）
    missing = [k for k in SEGMENTS if k not in obj]
    if missing:
        raise InheritanceError("六段缺 %s（§7 原文六段一个不能少）" % missing)

    # 判据2 · 时间/代（Lark 属性）
    if not isinstance(obj.get("gen"), int) or obj["gen"] < 0:
        raise InheritanceError("gen 必须非负 int, 实为 %r" % obj.get("gen"))
    at = obj.get("at")
    if not (isinstance(at, str) and _ISO.match(at)):
        raise InheritanceError("at 必须 ISO-8601 起头, 实为 %r" % at)

    # 判据3 · 链（Humanlaya 属性）: parent_gen 要么 None(首档) 要么 int
    pg = obj.get("parent_gen")
    if pg is not None and (not isinstance(pg, int) or pg < 0):
        raise InheritanceError("parent_gen 必须 None 或非负 int, 实为 %r" % pg)

    # 判据4 · 段2 可执行（Hyra 属性）
    pc = obj["proposed_change"]
    if not isinstance(pc, dict):
        raise InheritanceError("proposed_change 必须 dict")
    kind = pc.get("kind")
    if kind not in CHANGE_KINDS:
        raise InheritanceError(
            "段2 kind∈%s, 实为 %r（纯叙述改动非法 — Hyra 可执行属性）"
            % (list(CHANGE_KINDS), kind))
    if not str(pc.get("exec_form") or "").strip():
        raise InheritanceError("段2 exec_form 不能为空（可执行形态缺失）")

    # 判据5 · 段3 可回查（ARA 属性）
    me = obj["motivating_evidence"]
    if not isinstance(me, dict):
        raise InheritanceError("motivating_evidence 必须 dict")
    refs = me.get("refs")
    if not (isinstance(refs, list) and refs):
        raise InheritanceError(
            "段3 refs 至少 1 条（ARA 轨迹实证属性 — 纯叙述非法）")
    for i, r in enumerate(refs):
        if not isinstance(r, dict) or not r.get("type") or not r.get("ref"):
            raise InheritanceError("段3 refs[%d] 缺 type/ref: %r" % (i, r))
        if r["type"] not in EVIDENCE_TYPES:
            raise InheritanceError(
                "段3 refs[%d].type∈%s, 实为 %r"
                % (i, list(EVIDENCE_TYPES), r["type"]))

    # 判据6 · 段4 指纹（G2 可比性）
    ec = obj["evaluation_config"]
    if not isinstance(ec, dict):
        raise InheritanceError("evaluation_config 必须 dict")
    sha = ec.get("truth_sha8")
    if not (isinstance(sha, str) and re.match(r"^[0-9a-f]{8}$", sha)):
        raise InheritanceError(
            "段4 truth_sha8 必须 8 位小写 hex, 实为 %r（G2 指纹缺失 ⇒ "
            "分数不可比）" % sha)
    if not isinstance(ec.get("judge_frozen"), bool):
        raise InheritanceError("段4 judge_frozen 必须 bool")
    if not str(ec.get("truth_source") or "").strip():
        raise InheritanceError("段4 truth_source 不能为空")

    # 判据7 · 段5 判定 + 段6 诚实
    ad = obj["acceptance_decision"]
    if not isinstance(ad, dict) or ad.get("verdict") not in ("accepted",
                                                             "rejected"):
        raise InheritanceError(
            "段5 verdict∈{accepted,rejected}, 实为 %r"
            % (ad.get("verdict") if isinstance(ad, dict) else ad))
    su = obj["subsequent_use"]
    if not isinstance(su, dict) or su.get("status") not in USE_STATUS:
        raise InheritanceError(
            "段6 status∈%s, 实为 %r" % (list(USE_STATUS),
                                        su.get("status") if isinstance(su, dict)
                                        else su))
    if su["status"] in ("pending", "not_assessable") and not su.get("gap_note"):
        raise InheritanceError(
            "段6 status=%r 必带 gap_note（断供如实 — 不留 null 装有）"
            % su["status"])


# ══════════════════════════════════════════════════
# 档接合 + 链读取
# ══════════════════════════════════════════════════
def attach_inheritance(record: Dict[str, Any],
                       inheritance: Dict[str, Any]) -> Dict[str, Any]:
    """把六段挂进 knowledge3 档（只扩不破: 已有键被覆盖=错误, 防误写历史）。"""
    if "inheritance" in record:
        raise InheritanceError(
            "档已带 inheritance（改档走 supersedes 新档, 不原地改 — "
            "Humanlaya 版本化属性）")
    validate_inheritance(inheritance)
    record = dict(record)
    record["inheritance"] = inheritance
    return record


def load_latest_gen(archive_dir: str) -> Optional[int]:
    """扫 knowledge3 档找最大 gen（parent_gen 链用）。无档 ⇒ None（首档）。"""
    best: Optional[int] = None
    if not os.path.isdir(archive_dir):
        return None
    for fn in os.listdir(archive_dir):
        if not (fn.startswith("knowledge3_") and fn.endswith(".json")):
            continue
        try:
            with open(os.path.join(archive_dir, fn), encoding="utf-8") as f:
                rec = json.load(f)
        except (OSError, ValueError):        # 档损坏不静默 — 留给上层报
            raise InheritanceError("档损坏不可读: %s（G7 不静默）" % fn)
        if not isinstance(rec, dict):
            # ★ archive 存在历史 list 形态档（json 合法, 只是主体非 dict ⇒
            #   不可能带 inheritance/gen）—— 跳过不装数, 不是损坏不 raise
            continue
        inh = rec.get("inheritance")
        if isinstance(inh, dict) and isinstance(inh.get("gen"), int):
            best = inh["gen"] if best is None else max(best, inh["gen"])
    return best


def truth_fingerprint(path: str) -> str:
    """★ truth_source 的 8 位指纹（段4 G2 可比性 — 文件字节 sha 前 8）。"""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:8]
