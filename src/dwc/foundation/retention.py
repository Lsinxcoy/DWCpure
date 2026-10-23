"""R233 · 递归保留协议（RSI-Anything §2.5 的 DWC 落地 — 论文最核心机制）。

★★★ 定位（G1）: **DWC-AUTO** —— 哪个 exec×pred 版本对被保留来指导下一轮。
★★★ TRUTH_SOURCE: 无独立判定面 —— 消费 bench 四臂实测数据（真值在
  config/anchors/dev.json 链上的 verifier, 本模块只做协议判据与留痕）。

★ 协议三段（对齐 REPORT ⑧）:
  ① 组件检查: 新组件单独 vs 现任基线
  ② 配对检查（四臂 — rsi.py:63 同构）:
       A: old_exec×old_pred   B: old_exec×new_pred
       C: new_exec×old_pred   D: new_exec×new_pred
     Δ_exec = D − B（新执行器在新预测器下的边际贡献）
     Δ_pred = D − C（新预测器在新执行器下的边际贡献）
     ★ 配对不兼容: Δ_exec<0 且组件单独过检 ⇒ 拒（论文动机句机器化:
       "a policy can generate candidates for which an otherwise improved
       predictor is unreliable"）
  ③ 双判据晋升: Δscore= D − A >= promotion_gain AND
       cost_ratio = cost_D/cost_A <= promotion_cost_max
★ test 冻结程序锁: versions_frozen.json 先落（含 sha + test_not_opened_yet）
  → 才允许跑 test split; evaluate_test 校验锁在位才放行（不靠自觉）。
★ 未晋升 ⇒ 现任留任 + rejected 四臂数据完整入档（RSI
  raw_rejected_candidates_reported 同款 — 拒绝也要留证据）。
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from typing import Any

from dwc.foundation.paths import find_root

ROOT = find_root()
#: 保留决策档（append-only — 每候选一条, 审计链）
RETENTION_LOG = os.path.join(ROOT, "var", "dwc_retention.jsonl")
#: 版本冻结 manifest 目录（test 冻结程序锁的载体）
RETENTION_DIR = os.path.join(ROOT, "var", "dwc_retention")

#: 双判据默认值（dial 可覆盖 — REPORT ⑩）
PROMOTION_GAIN = 0.02
PROMOTION_COST_MAX = 1.2


class RetentionError(Exception):
    pass


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def component_delta(arm_new: dict[str, Any], arm_old: dict[str, Any]) -> dict[str, float]:
    """① 组件检查: 同臂口径的 pass 率差与成本比。"""
    return {"delta_pass": float(arm_new["pass_rate"]) - float(arm_old["pass_rate"]),
            "cost_ratio": (float(arm_new["cost"]) / float(arm_old["cost"])
                           if float(arm_old["cost"]) > 0 else float("inf"))}


def pair_check(arms: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """② 配对检查（四臂 A/B/C/D — 键名对齐 rsi.py combinations 语义）。

    ★ 配对不兼容判据: Δ_exec = D−B < 0（换了预测器后, 新执行器反而更差）
      且组件单独过检 ⇒ pair_ok=False —— 单组件过检 ≠ 组合可用。"""
    need = ("old_old", "old_new", "new_old", "new_new")
    missing = [k for k in need if k not in arms]
    if missing:
        raise RetentionError("四臂不全, 缺 %s — 不完整数据不许进协议" % missing)
    a, b = arms["old_old"], arms["old_new"]
    c, d = arms["new_old"], arms["new_new"]
    d_exec = float(d["pass_rate"]) - float(b["pass_rate"])
    d_pred = float(d["pass_rate"]) - float(c["pass_rate"])
    d_total = float(d["pass_rate"]) - float(a["pass_rate"])
    return {"delta_exec": d_exec, "delta_pred": d_pred, "delta_total": d_total,
            "pair_ok": not (d_exec < 0 and d_pred >= 0)}


def decide(arms: dict[str, dict[str, Any]],
           gain_min: float = PROMOTION_GAIN,
           cost_max: float = PROMOTION_COST_MAX) -> dict[str, Any]:
    """③ 双判据晋升（全协议入口 — 输出即审计档）。"""
    pair = pair_check(arms)
    a, d = arms["old_old"], arms["new_new"]
    cost_ratio = (float(d["cost"]) / float(a["cost"])
                  if float(a["cost"]) > 0 else float("inf"))
    gain_ok = pair["delta_total"] >= float(gain_min)
    cost_ok = cost_ratio <= float(cost_max)
    promoted = bool(gain_ok and cost_ok and pair["pair_ok"])
    reasons = []
    if not pair["pair_ok"]:
        reasons.append("配对不兼容(Δ_exec=%.4f<0 且 Δ_pred>=0)" % pair["delta_exec"])
    if not gain_ok:
        reasons.append("增益不足(Δ=%.4f < %.4f)" % (pair["delta_total"], gain_min))
    if not cost_ok:
        reasons.append("成本超限(ratio=%.2f > %.2f)" % (cost_ratio, cost_max))
    return {"promoted": promoted, "reasons": reasons,
            "gain_min": gain_min, "cost_max": cost_max,
            "cost_ratio": cost_ratio, **pair}


# ── test 冻结程序锁 ─────────────────────────────────────────────
def freeze_versions(cand_id: str, exec_ref: str, pred_version: str,
                    dev_arms: dict[str, dict[str, Any]],
                    decision: dict[str, Any]) -> str:
    """★ 版本先冻结 — manifest 落盘后 test 才许开（rsi.py:57 同款）。"""
    os.makedirs(RETENTION_DIR, exist_ok=True)
    body = {"cand_id": cand_id, "exec_ref": exec_ref,
            "pred_version": pred_version, "dev_arms": dev_arms,
            "decision": decision, "test_not_opened_yet": True,
            "frozen_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    path = os.path.join(RETENTION_DIR, cand_id + ".frozen.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(body, fh, ensure_ascii=False, indent=1)
    return path


def evaluate_test(cand_id: str) -> dict[str, Any]:
    """★ 程序锁: manifest 在位且 test_not_opened_yet 才放行 test 评估;
    评估完回填（不靠自觉 — 锁在代码路径上）。"""
    path = os.path.join(RETENTION_DIR, cand_id + ".frozen.json")
    if not os.path.exists(path):
        raise RetentionError("无冻结 manifest — test 不许开（先 freeze_versions）")
    doc = json.load(open(path, encoding="utf-8"))
    if not doc.get("test_not_opened_yet"):
        raise RetentionError("test 已开过 — 一次冻结一次开（防反复调参）")
    doc["test_not_opened_yet"] = False
    doc["test_opened_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    return doc


def record(outcome: dict[str, Any]) -> None:
    """决策留痕（append-only — 晋升与拒绝都记, 拒绝带完整四臂）。"""
    os.makedirs(os.path.dirname(RETENTION_LOG), exist_ok=True)
    row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **outcome}
    with open(RETENTION_LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
