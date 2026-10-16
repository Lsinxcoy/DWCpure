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
              backup_dir=None, fn_of=None, task_of=None, max_clusters=3,
              want_code_of=None):
    """★ 一轮收尾：聚簇→起草→试跑→（可选）落盘。返回可审计报告。

    ★ R295-Task3 · want_code_of(task)→bool（code_repair 写码真执行分流；
      None=不求码，老路零变）。trial_fn 三参契约 (task, patch, code=None)。
    """
    fn_of = fn_of or (lambda r: "")
    task_of = task_of or (lambda r: "")
    want_code_of = want_code_of or (lambda t: False)
    clusters = collect_unmapped(db_path, evolver, fn_of, task_of)
    results = []
    for cl in clusters[:max(1, max_clusters)]:
        item = {"key": cl["key"], "n": len(cl["sigs"]),
                "drafted": False, "trial": None,
                "landed": False, "backup": None}
        try:
            _task = cl["sigs"][0].get("task", "")
            p = mu.propose_from_cluster(cl["sigs"], context,
                                        want_code=want_code_of(_task))
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
        t = trial_fn(cl["sigs"][0].get("task", ""), p.patch, p.code)
        item["trial"] = t                      # ★ 原样存（bool/dict 照旧）
        # ★ R290-P1 · 归一：dict 取 success，bool/None 照旧（旧契约不断）。
        _ok = (t.get("success") if isinstance(t, dict) else t)
        # ★ R290-P1 · adopt 门真输入：dict trial 带 baseline_in/in_score ⇒
        #   传真 baseline/current（held_out 仍缺 ⇒ 仍 blocked，但带真 Δ_in）；
        #   bool/None trial ⇒ 占位 {} ⇒ accept 照旧 not_evaluated。
        # ★ R291-P4 Task 2 · held_out 真值进门（trial 带 held_out/baseline_ho
        #   ⇒ 门真判 accept/blocked/rejected；缺 ⇒ 仍 blocked 带真 Δ_in）。
        if isinstance(t, dict):
            _base = {"in_score": t.get("baseline_in"),
                     "held_out_score": t.get("baseline_ho")}
            _cur = {"in_score": t.get("in_score"),
                    "held_out_score": t.get("held_out")}
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
            if "delta_ho" in _ad:  # ★ R291-P4 Task 2 · 真 Δ_ho 透出（门判的）
                item["delta_ho"] = _ad["delta_ho"]
            if _ad.get("decision") == "adopted_not_implemented":
                # ★ R291-P4 Task 2 · 门判过⇒置第五态再落地（_land_adopted
                #   前置要 p.state；置态=记录门判结果，不编造）。
                p.state = "adopted_not_implemented"
                item["backup"] = evolver._land_adopted(p)
                item["landed"] = True
            else:
                # ★ R291-P4 Task 3 · legacy 直落已删（条件①②齐：trial 有
                #   分数＋accept 拿真输入）。门没判过（blocked/rejected/
                #   not_evaluated/accept_error）⇒ 不落地，只留痕 ——
                #   门没判≠门过了。
                item["reason"] = ("accept 门未过（%s）：无分数 trial 或门判"
                                  "未通过 ⇒ 不落地（legacy 直落 R291 已删）"
                                  % (_ad.get("decision"),))
        results.append(item)
    # ★ R285-P2 · 未接线清单（QUALITY_GATE Γ："本应调用但未调用"负事件）。
    #   门：Loop.round 生产调用之日即摘牌之时，在此之前任何接线 PR 一律拒。
    # ★ R294 · 三项全摘（R290-P0 world.select IG 排序／R291-P4 metric.select→
    #   adopt 真 held_out／R290-P2 direction 起草环）⇒ 清单清零（全接线）。
    return {"n_clusters": len(clusters), "results": results,
            "not_wired": []}


# ★ R291-P4 Task 3 · _land（legacy 直落落盘）已删 —— 唯一调用点已删，
#   死函数不留（_land_adopted 是唯一的落地路径）。
def _code_prompt(fn: str, skel) -> str:
    """★ R295-Task3 · 写码 prompt（peer 独立出码用；本 task 的码起草已出）。"""
    import json as _json
    return ("写一个完整可执行 Python 函数（只输出 ```python 代码块，无解释）：\n"
            "函数名 %s，输入输出形态（fn -> [[args, 期望], ...]，args 是单个参数）：\n%s\n"
            "纯函数，只用 sum/len/range 等纯内建，禁 import、禁 open/exec/eval、"
            "禁 while、禁双下划线属性。"
            % (fn, _json.dumps(skel, ensure_ascii=False)))


def _extract_code(text: str):
    """★ 取 ```python 块（无⇒None，不编）。"""
    import re
    m = re.search(r"```(?:python)?\s*(.*?)```", text or "", re.S)
    return m.group(1).strip() if m else None


def _peer_held_out_code(judge, llm, task, max_tokens=1500):
    """★ R295-Task3 · peer 写码独立评估（fail-closed：任一步坏⇒None）。

    peer fn 与 dev fn 不一样（R291-P4 Task4）⇒ peer 另出码另真跑，
    不是复用本 task 的 code。llm 缺席（沙箱单测）⇒None。
    """
    try:
        from dwc.llm.executor import (build_observed_prompt, obs_skeleton,
                                      parse_llm_observed)
        from dwc.llm.sandbox import run_code_observed
        if llm is None or not hasattr(judge, "held_out_peer"):
            return None
        _peer = judge.held_out_peer(task)
        if _peer is None:
            return None
        _pskel = obs_skeleton(judge.sealed, _peer)
        _pfn = next(iter(_pskel))
        _pr = llm.complete(_code_prompt(_pfn, _pskel), max_tokens=max_tokens)
        if not _pr.ok:
            return None
        _pcode = _extract_code(_pr.text or "")
        if not _pcode:
            return None
        _pobs = run_code_observed(_pcode, _pskel)
        if _pobs is None:
            return None
        return judge.held_out_score(_peer, _pobs)
    except Exception:                               # noqa: BLE001 — 坏不断试跑
        return None


def _real_trial(judge, llm, task, patch, max_tokens=1500, code=None):
    """★ 真试跑：规则 patch 进 prompt → 真执行 → 判分 dict。

    ★ R290-P1 · 回判分 dict（legacy 退役条件①）：
      {success, in_score, baseline_in} —— in_score=success→1.0/0.0/None；
      baseline_in=judge 历史 dev 同 task 末 point.score（无历史⇒None，
      accept 照旧 not_evaluated —— 没判过不装判过）。
    ★ R295-Task3 · code_repair 分流（code 非空＋category 对上）：
      沙箱真跑 code 得 observed→evaluate（judge 零改，_diff 不动），
      mode="code"；沙箱拒/跑挂⇒success=None fail-closed（不回落报数 ——
      回落混归因）；无 code/非 code_repair⇒老报数路 mode="report"。
    """
    from dwc.llm.executor import (build_observed_prompt, obs_skeleton,
                                  parse_llm_observed)
    _cat = ""
    try:
        _cat = (judge.anchors.get(task, {}) or {}).get("category", "")
    except Exception:                           # noqa: BLE001 — 坏不断试跑
        _cat = ""
    _mode = "report"
    if code and _cat == "code_repair":
        from dwc.llm.sandbox import run_code_observed, SandboxError
        _mode = "code"
        try:
            _obs = run_code_observed(
                code, obs_skeleton(judge.anchors, task))
        except SandboxError as _se:
            return {"success": None, "in_score": None, "baseline_in": None,
                    "held_out": None, "mode": _mode,
                    "reason": "沙箱拒：%s" % (_se,)}
        if _obs is None:
            return {"success": None, "in_score": None, "baseline_in": None,
                    "held_out": None, "mode": _mode,
                    "reason": "沙箱跑挂/缺函数（fail-closed）"}
        suc = judge.evaluate(task, "dev",
                             observed={"observed": _obs,
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
                "baseline_in": base,
                "held_out": _peer_held_out_code(judge, llm, task,
                                                max_tokens=max_tokens),
                "mode": _mode}
    skel = obs_skeleton(judge.anchors, task)
    prompt = build_observed_prompt(task, skel, "") + "\n" + patch
    r = llm.complete(prompt, max_tokens=max_tokens)
    if not r.ok:
        return {"success": None, "in_score": None, "baseline_in": None,
                "held_out": None, "mode": _mode}
    obs = parse_llm_observed(r.text or "", skel)
    if obs is None:
        return {"success": None, "in_score": None, "baseline_in": None,
                "held_out": None, "mode": _mode}
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
    # ★ R295-Task3 · peer 切写码独立评估（老报数 peer 退役：patch 建议文本
    #   进 peer prompt 是 R294 实证的错配通道，peer 也写码真跑）。
    _ho = _peer_held_out_code(judge, llm, task, max_tokens=max_tokens)
    return {"success": suc,
            "in_score": (1.0 if suc is True else
                         (0.0 if suc is False else None)),
            "baseline_in": base,
            "held_out": _ho, "mode": _mode}


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
                    trial_fn=lambda t, pa, code=None: _real_trial(
                        judge, llm, t, pa, code=code),
                    apply=args.apply, rules_path=rules,
                    backup_dir=args.backup_dir or None,
                    fn_of=lambda r: args.fn,
                    task_of=lambda r: args.task,
                    max_clusters=args.max_clusters,
                    want_code_of=lambda t: (
                        judge.anchors.get(t, {}) or {}).get(
                        "category", "") == "code_repair")
    print(json.dumps(rep, ensure_ascii=False, indent=1)[:2000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
