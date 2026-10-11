# -*- coding: utf-8 -*-
"""anchor_drift · 锚点漂移的**观察面**（R198 · Stage 2 的真身, 但**不自动换代**）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 只**算信号 + 列触发条件**; 不改 anchor 文件、不自动换代、不判分。

★★★★★ **论文依据（甲类 — 有据可搬, 逐字在场）**
  2608.10299 §2.3 Stage 2（Agent–Environment）递推逐字:
      `(A^{t+1}, E^{t+1}) = Ω(A^t, E^t, τ^t)`
      原文对 Stage 1 的判据: "Co-evolution begins when an agent no longer
      learns against a **static counterpart**"
      原文对 Stage 2 的边界: "When the environment remains fixed, it
      **limits the new experiences and pressures**"
  ⇒ DWC 的 environment = **judge 的锚点**（dev.json + sealed 标签）。
    R196 coupling 已记账: DWC 四机制互不触发是 Stage 0; 而"anchor 永不
    变"是**更硬的 static counterpart** — 那条不是账, 是事实。

★★★ TRUTH_SOURCE（判据 G2）· 为什么只观察不自动换代
  ① **G10 grounded 双条件**（GAI §2.2 逐字）: ①内容来自系统外（世界与目标）
     ②base 本身在 agent 外 ⇒ 若让 DWC 自己改 anchor, 第②条即破
     ⇒⇒ ⇒ **换代权在系统外（人）**, 本模块只把"该换了"变成可数的事实。
  ② **judge.py 逐字**: "agent 仍不可改判分, 换代只能走 **epoch 点界流程**"
     ⇒ epoch 是**点界**（离散时刻的人为裁决）, 不是连续量的自动判定。
  ③ **守门人单调性**（2606.14249, dev.json _provenance 逐字 "只增不改"）:
     换代 = **加新任务**, 不改旧任务的 expected/checks
     ⇒ 漂移若偷改旧锚 = 直接违反 provenance 明写的纪律。

★★★ 本模块算的信号（**全部来自既有产物, 零新判据零新采样**）
  · dev_pass_rate    ← evidence.jsonl（split=dev 的 success 比例）
  · val_pass_rate    ← evidence.jsonl（split=val; R179 起 val 是锚点外持有面）
  · per_task_pass    ← 逐 task 的通过率（哪个锚点已被"学穿"）
  · rung_mix         ← dev.json 各 verifier_rung 的任务数（锚点难度结构）
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

#: ★ epoch 账本（jsonl 追加; 每次换代一行 — 换代由人执行, 本模块只读它）
EPOCH_LEDGER = "anchor_epochs.jsonl"

#: ★ 建议触发条件（**列出来给人看, 不自动执行** — 阈值是建议不是判据）
SUGGESTION_RULES: Dict[str, str] = {
    "dev_saturated": "dev_pass_rate ≥ 0.95 且连续 ≥2 轮 ⇒ 学穿了, 该加新任务",
    "val_degraded": "val_pass_rate 比 dev_pass_rate 低 ≥0.2 ⇒ 泛化面在退化",
    "rung_monotone": "verifier_rung 全是 1 ⇒ 锚点难度结构单一, 该补高 rung",
}


def epoch_of(root: str) -> int:
    """当前 epoch 号（账本末条; 无账本 ⇒ 1 — R141 出厂口径）。"""
    rows = read_epochs(root)
    return int(rows[-1]["epoch"]) if rows else 1


def read_epochs(root: str) -> List[Dict[str, Any]]:
    """回读 epoch 账本（坏行 raise — G7; 无文件 ⇒ [] 一等输出）。"""
    p = os.path.join(root, "archive", EPOCH_LEDGER)
    if not os.path.exists(p):
        return []
    out: List[Dict[str, Any]] = []
    with open(p, encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError("%s 第 %d 行坏 ⇒ 拒绝猜: %s" % (p, ln, exc))
    return out


def record_epoch(root: str, *, new_epoch: int, by: str,
                 why: str, added_tasks: List[str]) -> Dict[str, Any]:
    """登记一次换代（**人执行换代后调本函数记账** — 本函数不碰 anchor 文件）。

    ★ 单调性检查（守门人 2606.14249）: new_epoch 必须 > 当前 epoch
      ⇒ 回退 epoch = 拒绝（换代只向前; 与 direction 锁 3 同纪律）。
    ★ added_tasks 非空: 换代 = 加任务, 不允许"只改号不动锚"（那没发生漂移）。
    """
    cur = epoch_of(root)
    if new_epoch <= cur:
        raise ValueError("epoch 只能前进: %d → %d 被拒（换代不回退）"
                         % (cur, new_epoch))
    if not added_tasks:
        raise ValueError("换代必须加任务（守门人单调性: 只增不改）"
                         " ⇒ added_tasks 空 ⇒ 没发生漂移, 不许记账")
    rec = {"epoch": new_epoch, "prev_epoch": cur, "by": by, "why": why,
           "added_tasks": sorted(added_tasks)}
    p = os.path.join(root, "archive", EPOCH_LEDGER)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return rec


def drift_signals(root: str) -> Dict[str, Any]:
    """★ 漂移信号（**只读既有产物** — evidence.jsonl + dev.json）。"""
    ev = os.path.join(root, "config", "anchors", "evidence.jsonl")
    rows: List[Dict[str, Any]] = []
    if os.path.exists(ev):
        rows = [json.loads(l) for l in open(ev, encoding="utf-8") if l.strip()]
    dev = [r for r in rows if r.get("split") == "dev"]
    val = [r for r in rows if r.get("split") == "val"]
    per: Dict[str, List[bool]] = {}
    for r in dev:
        per.setdefault(str(r.get("task_id")), []).append(bool(r.get("success")))
    per_task = {k: (sum(v) / len(v)) for k, v in sorted(per.items())}
    # ★ 缺席如实化: 无 dev 证据 ⇒ None（不是 0 — "没测过"≠"全错"）
    dev_rate = (sum(1 for r in dev if r.get("success")) / len(dev)) if dev else None
    val_rate = (sum(1 for r in val if r.get("success")) / len(val)) if val else None
    rung_mix = _rung_mix(root)                      # 先算（建议规则要吃它）
    return {
        "epoch": epoch_of(root),
        "n_dev": len(dev), "n_val": len(val),
        "dev_pass_rate": dev_rate,
        "val_pass_rate": val_rate,
        "per_task_pass": per_task,
        "rung_mix": rung_mix,
        "suggestions": _suggestions(dev_rate, val_rate, per_task,
                                   rung_mix),
    }


def _rung_mix(root: str) -> Dict[str, int]:
    """dev.json 的 verifier_rung 分布（锚点难度结构 — 全 1 = 单一）。"""
    p = os.path.join(root, "config", "anchors", "dev.json")
    if not os.path.exists(p):
        return {}
    d = json.load(open(p, encoding="utf-8"))
    out: Dict[str, int] = {}
    for k, v in d.items():
        if k.startswith("_") or not isinstance(v, dict):
            continue
        r = str(v.get("verifier_rung", "absent"))
        out[r] = out.get(r, 0) + 1
    return dict(sorted(out.items()))


def _suggestions(dev_rate: Optional[float], val_rate: Optional[float],
                 per_task: Dict[str, float], rung_mix: Dict[str, int]
                 ) -> List[str]:
    """满足触发条件的建议键（**给人看的清单 — 不执行任何动作**）。

    ★★ 自洽纪律: `SUGGESTION_RULES` 里登记的键**必须**在本函数有对应实现
      — 登记不执行的键 = 幻影规则（tests 锁 len(建议键) 覆盖）。
    """
    out: List[str] = []
    if dev_rate is not None and dev_rate >= 0.95:
        out.append("dev_saturated")
    if per_task and all(v >= 0.95 for v in per_task.values()):
        out.append("dev_saturated")           # 逐 task 也学穿 ⇒ 同键（去重由 set）
    if (dev_rate is not None and val_rate is not None
            and (dev_rate - val_rate) >= 0.2):
        out.append("val_degraded")
    # rung_monotone: rung 全同值（且非空）⇒ 难度结构单一
    if rung_mix and len(rung_mix) == 1:
        out.append("rung_monotone")
    return sorted(set(out))


ANCHOR_DRIFT_MECHANICS = {
    "no_auto_epoch": "换代权在系统外（G2/G10 grounded 双条件②: base 在 agent 外）; 本模块只记账+列建议",
    "monotonic": "epoch 只能前进; 换代必须加任务（守门人 2606.14249 只增不改）",
    "paper": "2608.10299 §2.3 Stage 2 递推 + static counterpart 判据（逐字在 docstring）",
    "signals_from_evidence": "信号全部来自 evidence.jsonl / dev.json — 零新采样零新判据",
}
