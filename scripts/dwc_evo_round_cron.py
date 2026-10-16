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
    sys.path.insert(0, os.path.join(_code_root(), "scripts"))
    sys.path.insert(0, os.path.join(_code_root(), "src"))
    import dwc_evo_round as EVO
    from dwc.llm.client import LLMClient
    from dwc.organs.evolver import Evolver, LLMMutator
    from dwc.organs.judge import Judge
    from dwc.organs.predictor import OutcomePredictor
    prod = _prod_root()
    db = os.path.join(prod, "var", "dwc_prod.sqlite")
    judge = Judge()
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
        want_code_of=lambda t: (
            judge.anchors.get(t, {}) or {}).get(
            "category", "") == "code_repair")
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
