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
    # ★ B1 · 独立深挖轮（007 单独立簇＋hint 换血：一轮试跑）。
    _p.add_argument("--deep-task", default=None,
                    help="只深挖该 task（task_filter＋hint fresh＋单簇）")
    # ★ B4 · 候选池 N（默认 3 老路；调大涨 LLM 预算 —— Thm 3 Eq.8）。
    _p.add_argument("--pool-n", type=int, default=3)
    # ★ N7 · 起草预算校准（probe：want_code 路 1000 fail/1500 pass；
    #   无码路 800 pass；真实 prompt 多 ~600 字 reasoning 开销 ⇒ 2000 余量）。
    _p.add_argument("--draft-tokens", type=int, default=2000)
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
            RuntimeError(r.error)))(
                llm.complete(p, max_tokens=_a.draft_tokens)))
    rep = EVO.run_round(
        db, Evolver(), mu, "anchors: %s" % (sorted(judge.anchors)[:12],),
        trial_fn=lambda t, pa, code=None: EVO._real_trial(
            judge, llm, t, pa, code=code),
        apply=False,
        rules_path=os.path.join(prod, "config", "anchors", "rules.json"),
        fn_of=lambda r: "average", task_of=lambda r: "code_fix_007",
        # ★ B3 · 火力转攻生产生效：库里混入 reasoning sigs 也排后，
        #   code_fix 簇先吃 max_clusters 预算（验证便宜 u 大好验）。
        priority_prefixes=("code_fix",),
        # ★ B1 · 独立深挖轮（--deep-task）：单 task＋hint 换血＋单簇。
        task_filter=_a.deep_task,
        hint_mode=("fresh" if _a.deep_task else "reuse"),
        max_clusters=(1 if _a.deep_task else 3),
        pool_n=_a.pool_n,
        want_code_of=lambda t: (
            judge.anchors.get(t, {}) or {}).get(
            "category", "") == "code_repair",
        # ★ R309-⑦ · epoch ledger（默认开；--no-resume 关）。
        ledger_path=os.path.join(prod, "var", "evo_round_ledger.jsonl"),
        resume=not _a.no_resume)
    # ★ N1 · 执行侧 sigs 归 agent_quality 回路：有被分流的 llm_asserted
    #   sigs ⇒ 写 inbox 任务（去重），让 resident agent 重做（R329 转单
    #   的自动版；不静默吞掉）。
    try:
        _nfiltered = int(rep.get("filtered_nonreproducible") or 0)
        if _nfiltered > 0:
            import json as _j
            _inbox = os.path.join(prod, "var", "dwc_inbox.jsonl")
            _done = os.path.join(prod, "var", "dwc_inbox_done.json")
            _done_ids = set()
            try:
                with open(_done, encoding="utf-8") as _f:
                    _done_ids = set(json.load(_f).keys())
            except (OSError, ValueError):
                _done_ids = set()
            _existing = set()
            try:
                with open(_inbox, encoding="utf-8") as _f:
                    for _ln in _f:
                        try:
                            _existing.add(json.loads(_ln).get("id"))
                        except Exception:
                            pass
            except OSError:
                pass
            # 读 db 取 distinct task
            import sqlite3 as _sq
            _con = _sq.connect(db)
            _tasks = [r[0] for r in _con.execute(
                "SELECT DISTINCT task FROM failure_sig "
                "WHERE m LIKE 'llm_asserted%'").fetchall()]
            _con.close()
            for _t in _tasks:
                _tid = "evo_auto_%s" % (_t,)
                if _tid in _existing or _tid in _done_ids:
                    continue
                _line = _j.dumps({"id": _tid, "task": _t,
                                  "by": "evo_auto_route",
                                  "ts": __import__("datetime").datetime.now().isoformat()},
                                 ensure_ascii=False)
                with open(_inbox, "a", encoding="utf-8") as _f:
                    _f.write(_line + "\n")
    except Exception as _e:  # noqa: BLE001 — 路由坏不掀轮
        print("N1 route warn:", repr(_e))
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
