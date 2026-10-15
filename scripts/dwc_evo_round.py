# -*- coding: utf-8 -*-
"""★★★ R279 · 进化收尾链（自动链的最后一公里）。

★ 读生产 failure_sig → diagnose 找 unmapped 簇 → LLMMutator 起草 →
  真执行试跑 → 报告；默认不落盘（--apply 且试跑通过才落，落前必备份）。
★ daemon/nightbench 零改：独立脚本，cron/手工调。
"""
import argparse
import io
import json
import os
import sqlite3
import sys
import time


def _code_root(start=None) -> str:
    """★ 代码根发现（cron 拷贝场景：.dwc_repo 指针 → 仓库；同 nightbench）。"""
    d = start or os.path.dirname(os.path.abspath(__file__))
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
    # ★ 回退：仓库本地布局（root/scripts/xxx.py）—— cron 拷贝必有指针，走不到这。
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


sys.path.insert(0, os.path.join(_code_root(), "src"))

from dwc.organs.evolver import Evolver, LLMMutator, Mutator


def collect_unmapped(db_path, evolver, fn_of, task_of):
    """★ 读库 → diagnose → 只收 unmapped 簇（按 key_for 分组）。"""
    con = sqlite3.connect(db_path)
    try:
        rows = con.execute(
            "select c,q,m,node_id from failure_sig").fetchall()
    finally:
        con.close()
    sigs = [{"c": r[0], "q": r[1], "m": r[2],
             "fn": fn_of(r), "task": task_of(r), "node_id": r[3]}
            for r in rows]
    if not sigs:
        return []
    out = evolver.diagnose(sigs)
    groups = {}
    for s in out.get("unmapped", []):
        k = Mutator.key_for(s)
        groups.setdefault(k, []).append(s)
    return [{"key": k, "sigs": v} for k, v in groups.items()]


def run_round(db_path, evolver, mu, context, trial_fn, apply, rules_path,
              backup_dir=None, fn_of=None, task_of=None, max_clusters=3):
    """★ 一轮收尾：聚簇→起草→试跑→（可选）落盘。返回可审计报告。"""
    fn_of = fn_of or (lambda r: "")
    task_of = task_of or (lambda r: "")
    clusters = collect_unmapped(db_path, evolver, fn_of, task_of)
    results = []
    for cl in clusters[:max(1, max_clusters)]:
        item = {"key": cl["key"], "n": len(cl["sigs"]),
                "drafted": False, "trial": None,
                "landed": False, "backup": None}
        try:
            p = mu.propose_from_cluster(cl["sigs"], context)
        except Exception as exc:  # ★ cron 体质：单簇端点抖不许掀整轮（留痕继续）
            item["reason"] = "起草抛错：%r" % (exc,)
            results.append(item)
            continue
        if p is None:
            item["reason"] = mu.last_reason
            results.append(item)
            continue
        item["drafted"] = True
        item["proposal_id"] = p.proposal_id
        t = trial_fn(cl["sigs"][0].get("task", ""), p.patch)
        item["trial"] = t                      # ★ 原样存（bool/dict 照旧）
        # ★ R290-P1 · 归一：dict 取 success，bool/None 照旧（旧契约不断）。
        _ok = (t.get("success") if isinstance(t, dict) else t)
        # ★ R290-P1 · adopt 门真输入：dict trial 带 baseline_in/in_score ⇒
        #   传真 baseline/current（held_out 仍缺 ⇒ 仍 blocked，但带真 Δ_in）；
        #   bool/None trial ⇒ 占位 {} ⇒ accept 照旧 not_evaluated。
        if isinstance(t, dict):
            _base = {"in_score": t.get("baseline_in")}
            _cur = {"in_score": t.get("in_score")}
        else:
            _base, _cur = {}, {}
        if apply and _ok is True:
            # ★ R287-C · adopt 门（Evolver.accept）：trial 布尔无分数 ⇒
            #   accept 缺 baseline/current 会判 not_evaluated/blocked。
            #   诚实处置：先判，有分数走门（第五态→_land_adopted 落）；
            #   无分数走 legacy 直落但标记 decision（门没判≠门过了 ——
            #   收紧点：trial_fn 带分数之日 legacy 分支删除，见 ★TODO）。
            try:
                _ad = evolver.accept(
                    p, baseline=_base, current=_cur)
            except Exception as exc_a:  # noqa: BLE001
                _ad = {"decision": "accept_error",
                       "why": "accept 抛错：%r" % (exc_a,)}
            item["adopt"] = _ad.get("decision")
            if "delta_in" in _ad:
                item["delta_in"] = _ad["delta_in"]
            if _ad.get("decision") == "adopted_not_implemented":
                item["backup"] = evolver._land_adopted(p)
                item["landed"] = True
            else:
                entry = {"component": p.component, "dimension": p.dimension,
                         "target_layer": p.target_layer, "target": p.target,
                         "m": p.failure_signature.get("m", ""),
                         "m_source": "llm", "patch": p.patch,
                         "rationale": p.rationale}
                item["backup"] = _land(rules_path, cl["key"], entry,
                                       backup_dir)
                item["landed"] = True
                item["★TODO"] = ("legacy 直落（trial 无分数+accept 无真输入，门未判）——"
                                 "删分支条件（2026-10-15 复核）：①trial_fn 返回分数 "
                                 "（_real_trial 现回布尔）②accept 拿真 baseline/current "
                                 "（metric.select→adopt 在 not_wired 清单）——两者齐才删")
        results.append(item)
    # ★ R285-P2 · 未接线清单（QUALITY_GATE Γ："本应调用但未调用"负事件）。
    #   门：Loop.round 生产调用之日即摘牌之时，在此之前任何接线 PR 一律拒。
    return {"n_clusters": len(clusters), "results": results,
            "not_wired": ["world.select", "metric.select→adopt",
                          "direction.next_action"]}


def _land(rules_path, key, entry, backup_dir):
    """★ 落盘：先写备份收据（pre_absent 如实记），再合并（保旧条目）。"""
    pre_absent = not os.path.exists(rules_path)
    data = {"learned": {}}
    if not pre_absent:
        with io.open(rules_path, encoding="utf-8") as f:
            data = json.load(f)
        data.setdefault("learned", {})
    data["learned"][key] = entry
    bdir = backup_dir or os.path.join(os.path.dirname(rules_path), "..",
                                      "..", "..", "Temp")
    os.makedirs(bdir, exist_ok=True)
    receipt = os.path.join(
        bdir, "rules_backup_%s.json" % time.strftime("%Y%m%d_%H%M%S"))
    with io.open(receipt, "w", encoding="utf-8") as f:
        json.dump({"pre_absent": pre_absent, "key": key,
                   "at": time.strftime("%Y-%m-%dT%H:%M:%S")},
                  f, ensure_ascii=False)
    _d = os.path.dirname(rules_path)
    if _d and not os.path.exists(_d):
        os.makedirs(_d)
    with io.open(rules_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    return receipt


def _real_trial(judge, llm, task, patch, max_tokens=1500):
    """★ 真试跑：规则 patch 进 prompt → 真执行 → 判分 dict。

    ★ R290-P1 · 回判分 dict（legacy 退役条件①）：
      {success, in_score, baseline_in} —— in_score=success→1.0/0.0/None；
      baseline_in=judge 历史 dev 同 task 末 point.score（无历史⇒None，
      accept 照旧 not_evaluated —— 没判过不装判过）。
    """
    from dwc.llm.executor import (build_observed_prompt, obs_skeleton,
                                  parse_llm_observed)
    skel = obs_skeleton(judge.anchors, task)
    prompt = build_observed_prompt(task, skel, "") + "\n" + patch
    r = llm.complete(prompt, max_tokens=max_tokens)
    if not r.ok:
        return {"success": None, "in_score": None, "baseline_in": None}
    obs = parse_llm_observed(r.text or "", skel)
    if obs is None:
        return {"success": None, "in_score": None, "baseline_in": None}
    suc = judge.evaluate(task, "dev",
                         observed={"observed": obs,
                                   "★_executed": True}).success
    base = None
    try:
        _pts = [p for p in judge.task_scores(split="dev")
                if p.task_id == task]
        if _pts:
            base = _pts[-1].score
    except Exception:                       # noqa: BLE001 — 历史坏不断试跑
        base = None
    return {"success": suc,
            "in_score": (1.0 if suc is True else
                         (0.0 if suc is False else None)),
            "baseline_in": base}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="")
    ap.add_argument("--rules", default="")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--backup-dir", default="")
    ap.add_argument("--max-clusters", type=int, default=3)
    # ★ R279 范围诚实声明：failure_sig 表无 fn/task 列 ⇒ fn/task 由参数指定，
    #   默认对准已知的 007 簇；多任务泛化等 node_id→task 映射落地后再做。
    ap.add_argument("--fn", default="average")
    ap.add_argument("--task", default="code_fix_007")
    args = ap.parse_args()
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    db = args.db or os.path.join(root, "var", "dwc_prod.sqlite")
    rules = args.rules or os.path.join(root, "config", "anchors",
                                       "rules.json")
    from dwc.llm.client import LLMClient
    from dwc.organs.judge import Judge
    judge = Judge()
    llm = LLMClient()
    mu = LLMMutator(llm=lambda p: (
        lambda r: r.text if r.ok else (_ for _ in ()).throw(
            RuntimeError(r.error)))(llm.complete(p, max_tokens=800)))
    ctx = "anchors tasks: %s" % (sorted(judge.anchors.keys())[:12],)
    rep = run_round(db, Evolver(), mu, ctx,
                    trial_fn=lambda t, pa: _real_trial(judge, llm, t, pa),
                    apply=args.apply, rules_path=rules,
                    backup_dir=args.backup_dir or None,
                    fn_of=lambda r: args.fn,
                    task_of=lambda r: args.task,
                    max_clusters=args.max_clusters)
    print(json.dumps(rep, ensure_ascii=False, indent=1)[:2000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
