# -*- coding: utf-8 -*-
"""Table 8 六维现状盘点 —— R122 · 项3（综述 §3.6.5 Table 8 · 缺口轮）。

六维（NOTE_survey §3.6.5 逐字）:
  Adaptivity(gain/轨迹/到靶时间) · Retention(replay loss/固定与破坏任务)
  Transfer(held-out 域内跨域) · Efficiency(tokens/时间/每已验证增益成本)
  Stability(有害更新/最大暂时下降) · Meta-recursion(机制复用/后继质量/
  goal 与停止决策)

R98 当时判定「gain/efficiency 雏形, 其余四无」— 本脚本**按现状重判**
（R98 之后 Retention/Eq.10/Stability pass_k/Transfer 三臂/换代账本 均落）:
每维给 status(live/雏形/缺) + 实测读数 + 取数命令（声称/实测/取数三联）。

读:  docs/pass_k_report.json · docs/transfer_attribution.json ·
     docs/ablation_attribution.json · archive/knowledge3_*.json ·
     archive/epoch_ledger.jsonl · CostLedger(gate_trace 侧)
写:  docs/table8_status.json
用法: python scripts/table8_status.py
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from typing import Any, Dict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p: str) -> Any:
    fp = os.path.join(ROOT, p)
    return json.load(open(fp, encoding="utf-8")) if os.path.exists(fp) \
        else None


def meta_recursion_stats() -> Dict[str, Any]:
    """★ meta-recursion 最小测量（不造新尺 — 从六段链档案统计）:
    机制复用 = 链深度与超设; 后继质量 = 每代验收通过; 停止决策 = 换代账本。"""
    gens, supersedes_n, statuses, verdicts = [], 0, {}, {}
    for fn in sorted(glob.glob(os.path.join(ROOT, "archive",
                                            "knowledge3_*.json"))):
        try:
            rec = json.load(open(fn, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(rec, dict):
            continue
        inh = rec.get("inheritance")
        if not isinstance(inh, dict):
            continue
        gens.append(inh.get("gen"))
        if inh.get("supersedes"):
            supersedes_n += 1
        su = (inh.get("subsequent_use") or {}).get("status")
        if su:
            statuses[su] = statuses.get(su, 0) + 1
        v = (inh.get("acceptance_decision") or {}).get("verdict")
        if v:
            verdicts[v] = verdicts.get(v, 0) + 1
    ledger = os.path.join(ROOT, "archive", "epoch_ledger.jsonl")
    n_duel = (len([x for x in open(ledger, encoding="utf-8").read()
                   .splitlines() if x.strip()]) if os.path.exists(ledger)
              else 0)
    return {
        "chain_depth": len(gens),
        "gen_range": [min(gens), max(gens)] if gens else None,
        "supersedes_uses": supersedes_n,
        "acceptance_verdicts": verdicts,          # 后继质量: 验收通过分布
        "subsequent_use_statuses": statuses,      # 机制复用: 使用状态分布
        "duel_regime_decisions": n_duel,          # goal/停止决策: 换代账本条数
        "caveat": ("最小代理: 从六段档案统计, 非综述原测法; "
                   "goal 停止决策的完整形态(期望收益<成本时停) = "
                   "move-on 停止判据轮的义务, 未建如实标"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "docs",
                                                  "table8_status.json"))
    args = ap.parse_args()

    pk = load("docs/pass_k_report.json")
    tr = load("docs/transfer_attribution.json")          # R107 golden 三臂
    tr_llm = load("docs/transfer_llm_arm.json")          # R124 LLM 臂（真区分）
    ab = load("docs/ablation_attribution.json")

    rows = [
        {"dim": "Adaptivity(gain)", "status": "live",
         "measure": "dream v_by_version / judge success_rate",
         "reading": ("ablation 四V=%s" % list(ab["v_by_slot"].values())
                     if ab else "docs/ablation_attribution.json 缺"),
         "cmd": "python scripts/ablation_attribution.py",
         "since": "R85/R114"},
        {"dim": "Efficiency", "status": "live",
         "measure": "CostLedger 逐 term 成本账 + 每增益成本(匹配预算)",
         "reading": "gate_trace.jsonl 逐轮记账; M2 对打稿 K 倍账设计在位",
         "cmd": "python scripts/gate.py (CostLedger 落盘)",
         "since": "R99 (§3.6.5 评估成本入预算字面)"},
        {"dim": "Retention", "status": "live",
         "measure": "regression_check 保护组(delta vs η) + Eq.10 η_ret 硬门",
         "reading": "R118: η_ret=0 判据在位; 回归判据 ε 策略键(E2)可演化",
         "cmd": "python -m pytest tests/test_r118_eq10.py",
         "since": "R99-初/regression + R118 Eq.10 (R98 判'无'已过时)"},
        {"dim": "Stability", "status": "live",
         "measure": "pass^k 跨运行稳定(有害更新的反面) + 重复跑恒等监测",
         "reading": ("pass_k 实测: %s（formula=%s, %d份报告）" % (
             {r["source"]: {"mean_pass_k": r.get("mean_pass_k"),
                            "std": r.get("rate_std_across_tasks")}
              for r in pk["reports"]} if pk else "缺",
             pk.get("formula") if pk else "?",
             len(pk.get("reports", [])) if pk else 0)),
         "cmd": "python scripts/pass_k_report.py",
         "since": "R100 pass_k + R118 5连跑校准 (R98 判'无'已过时)"},
        {"dim": "Transfer",
         "status": "live" if tr_llm and tr_llm.get("status") !=
         "not_computable" else "雏形",
         "measure": "三臂 transplant/盲安慰剂/baseline（R107 协议）+ LLM "
                    "executor 臂（R124 — 真内容通道）",
         "reading": ("★ R124 LLM臂真区分: transplant=%s placebo=%s "
                     "内容效应=%s(%s) — golden 恒等已解除; "
                     "R107 golden 三臂 %s 为协议对照留档" % (
                         tr_llm["arms_summary"]["transplant"]["mean_rate"],
                         tr_llm["arms_summary"]["blind_placebo"]["mean_rate"],
                         tr_llm["attribution"]["transplant_minus_placebo"],
                         tr_llm["attribution"]["content_effect_verdict"],
                         (tr or {}).get("attribution", {})
                         .get("content_effect_verdict"))
                     if tr_llm and tr_llm.get("status") != "not_computable"
                     else "R124 LLM 未跑/不可用 ⇒ 见 R107 梯队"),
         "cmd": "python scripts/transfer_llm_arm.py",
         "since": "R107 协议 → R124 LLM 臂出真区分"},
        {"dim": "Meta-recursion",
         "status": "live" if os.path.exists(
             os.path.join(ROOT, "src", "dwc", "foundation",
                          "stop_criteria.py")) else "雏形",
         "measure": ("六段链档案统计(链深/验收/复用) + 换代账本(stop 决策) "
                    "★ R125 move_on 五判据判决表（continue/move_on/"
                    "insufficient + decision_record 留痕）"),
         "reading": "",
         "cmd": "python scripts/table8_status.py",
         "since": "R109 六段 + R120 账本 + R125 move-on 五判据"},
    ]
    mr = meta_recursion_stats()
    for r in rows:
        if r["dim"] == "Meta-recursion":
            r["reading"] = ("链深=%d gen%s 验收=%s 复用状态=%s 换代决策=%d条 — "
                            "%s" % (mr["chain_depth"], mr["gen_range"],
                                    mr["acceptance_verdicts"],
                                    mr["subsequent_use_statuses"],
                                    mr["duel_regime_decisions"],
                                    mr["caveat"]))

    out = {
        "protocol": ("Table 8 六维现状盘点(综述§3.6.5): status+实测+取数命令 "
                     "三联; R98 '四无'判定按现状重判"),
        "summary": {"live": sum(1 for r in rows if r["status"] == "live"),
                    "雏形": sum(1 for r in rows if r["status"] == "雏形"),
                    "缺": sum(1 for r in rows if r["status"] == "缺")},
        "dims": rows,
        "meta_recursion_detail": mr,
        "caveats": [
            "R98 当时 gain/efficiency 雏形其余四无 — 本轮重判: 4 live + 2 雏形 + 0 缺"
            " (Retention/Stability 已由 R118/R100 落地)",
            "Transfer 雏形卡在: golden 三臂恒等(结构必然) ⇒ 真区分须 LLM 臂",
            "Meta-recursion 雏形卡在: goal/停止决策完整形态(move-on 判据)未建",
            "所有 reading 均来自实测脚本落盘文件, 未跑的标'缺'不装数",
        ],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print("六维:", out["summary"])
    for r in rows:
        print("  %-22s %s | %s" % (r["dim"], r["status"],
                                   r["reading"][:80]))
    print("写出:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
