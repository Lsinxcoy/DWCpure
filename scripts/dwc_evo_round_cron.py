# -*- coding: utf-8 -*-
"""★★★ R279 · 进化收尾 cron 包装（no_agent 脚本作业用）。

★ 只报告、不落地（--apply 永不自动开 —— 落盘须人工拍板）。
★ 路径：代码经 .dwc_repo 指针找仓库；数据固定 ~/.dwc 生产库。
★ CRON RUNS THE COPY: 同步 %LOCALAPPDATA%/hermes/scripts/ 后生效。

cron: 每日 04:00（nightbench 02:30 跑完后顺手收尾，错开 03:00 备份）。
"""
from __future__ import annotations

import json
import os
import sys


def _prod_root() -> str:
    home = os.path.expanduser("~")
    p = os.path.join(home, ".dwc")
    if not os.path.isdir(p):
        raise RuntimeError("生产 .dwc 不在 %s" % p)
    return p


def _code_root() -> str:
    d = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        _mk = os.path.join(d, ".dwc_repo")
        if os.path.isfile(_mk):
            try:
                with open(_mk, encoding="utf-8") as _f:
                    _r = _f.readline().strip()
                if _r and os.path.isdir(_r):
                    return _r
            except OSError:
                pass
            return d
        d = os.path.dirname(d)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    import argparse as _ap
    _p = _ap.ArgumentParser()
    _p.add_argument("--no-resume", action="store_true")
    _a = _p.parse_args()
    sys.path.insert(0, os.path.join(_code_root(), "scripts"))
    sys.path.insert(0, os.path.join(_code_root(), "src"))
    import dwc_evo_round as EVO
    from dwc.llm.client import LLMClient
    from dwc.organs.evolver import Evolver, LLMMutator
    from dwc.organs.judge import Judge
    from dwc.organs.predictor import OutcomePredictor
    prod = _prod_root()
    db = os.path.join(prod, "var", "dwc_prod.sqlite")
    # ★ R299-b2 · 基线跨轮落盘：Judge 带 path（points 落 var/dwc_task_scores
    #   .jsonl＋evidence，trial 基线/peer 基线下轮可读；内存轮抛则基线恒空
    #   门恒 not_evaluated）。仓库根为锚（R292），测试 Judge() 无参零写。
    judge = Judge(store_path=os.path.join(prod, "var",
                                              "dwc_task_scores.jsonl"),
                  evidence_path=os.path.join(prod, "var",
                                             "dwc_evidence.jsonl"))
    llm = LLMClient()
    mu = LLMMutator(llm=lambda p: (
        lambda r: r.text if r.ok else (_ for _ in ()).throw(
            RuntimeError(r.error)))(llm.complete(p, max_tokens=1500)))
    rep = EVO.run_round(
        db, Evolver(), mu, "anchors: %s" % (sorted(judge.anchors)[:12],),
        trial_fn=lambda t, pa, code=None: EVO._real_trial(
            judge, llm, t, pa, code=code),
        apply=False,
        rules_path=os.path.join(prod, "config", "anchors", "rules.json"),
        fn_of=lambda r: "average", task_of=lambda r: "code_fix_007",
        max_clusters=3,
        # ★ B3 · 火力转攻生产生效：库里混入 reasoning sigs 也排后，
        #   code_fix 簇先吃 max_clusters 预算（验证便宜 u 大好验）。
        priority_prefixes=("code_fix",),
        want_code_of=lambda t: (
            judge.anchors.get(t, {}) or {}).get(
            "category", "") == "code_repair",
        # ★ R309-⑦ · epoch ledger（默认开；--no-resume 关）。
        ledger_path=os.path.join(prod, "var", "evo_round_ledger.jsonl"),
        resume=not _a.no_resume)
    try:  # ★ R280 · Brier 每日可观测（坏了留痕不掀报告）
        _op = OutcomePredictor(log_path=os.path.join(
            prod, "var", "dwc_predictor.jsonl"))
        rep["predictor"] = _op.calibrate()
    except Exception as exc:  # noqa: BLE001
        rep["predictor"] = {"n": -1, "brier": None, "note": "校准跳过: %s" % exc}
    print(json.dumps(rep, ensure_ascii=False, indent=1)[:2000], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
