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
from typing import Any, Dict, Set


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
    # ★ 回退：仓库本地布局（<repo>/scripts/<脚本名>）—— cron 拷贝必有指针，走不到这。
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


sys.path.insert(0, os.path.join(_code_root(), "src"))

from dwc.organs.evolver import Evolver, LLMMutator, Mutator
from dwc.observability.context import measurement_role, task_measurement_context


#: ★ R437 · 探针缓存（task → 该任务的破坏实现能跑出的 (c,q) 集合）。
_PROBE_CACHE: Dict[str, Set[Any]] = {}


def probe_signatures(task: str) -> Set[Any]:
    """★★★ R437 · 跑该任务的**破坏实现**，返回它真实产生的 (c,q) 集合。

    ★ 为什么要有这个：旧口径按 `m.startswith("llm_asserted")` 判断"能不能
      复现"——那是**猜**，不是测。实测 `code_fix_002` 的破坏实现产生
      `E_VALUE/wrong_magnitude`，而现场 811 条是 `E_NO_RESULT/abstained`
      ⇒ 前者能复现、后者不能。前缀过滤把两者一起扔了。

    ★ 判定：签名 (c,q) ∈ 返回集合 ⇒ 该失败是"代码 bug 引起的"，进代码车道；
      否则 ⇒ 是 agent 执行侧的（弃答/答错），进行为车道。

    ★ 跑挂（obs=None）⇒ 返回 `{"__crash__"}`：崩溃本身就是这个 bug 的表现。
    ★ 无破坏实现 ⇒ 空集（该任务没有代码可修）。
    ★ 任务**不在锚点集里** ⇒ 返回 `{"__unknown__"}`：无从判断，保持老行为
      （合成/历史调用方传的 task 不在 dev.json 里，不能凭空判成行为车道）。
    """
    if task in _PROBE_CACHE:
        return _PROBE_CACHE[task]
    out: Set[Any] = set()
    try:
        root = _code_root()
        with io.open(os.path.join(root, "config", "anchors", "broken_dev.json"),
                     encoding="utf-8") as _fh:
            broken = json.load(_fh)
        with io.open(os.path.join(root, "config", "anchors", "dev.json"),
                     encoding="utf-8") as _fh:
            anchors = json.load(_fh)
        if task not in anchors:
            out.add("__unknown__")
        impl = str((broken.get(task) or {}).get("broken_impl") or "")
        if impl.strip():
            from dwc.llm.executor import obs_skeleton
            from dwc.llm.sandbox import run_code_observed
            from dwc.organs.judge import Judge
            obs = run_code_observed(impl, obs_skeleton(anchors, task))
            if obs is None:
                out.add("__crash__")
            else:
                v = Judge().evaluate(task, "dev",
                                     observed={"observed": obs,
                                               "★_executed": True})
                for s in (getattr(v, "sigs", None) or []):
                    out.add((str(s.get("c")), str(s.get("q"))))
    except Exception:                    # noqa: BLE001 — 探针坏 ⇒ 保守当行为车道
        out = set()
    _PROBE_CACHE[task] = out
    return out


def collect_unmapped(db_path, evolver, fn_of, task_of,
                     priority_prefixes=None, task_filter=None,
                     reproducible_only=True,
                     filtered_out=None,
                     use_archive_priors=True):
    """★ 读库 → diagnose → 只收 unmapped 簇（按 key_for 分组）。

    ★ B3 · 火力转攻（reasoning 组 0.888 验证贵 → code_fix 组主攻）：
      priority_prefixes＝任务前缀优序（如 ("code_fix",)），稳定排序 ——
      命中簇按前缀序排前，非命中保原相对序在后。None＝老路插入序
      （默认，旧调用零变）。簇优序看首个 sig 的 task（同簇同源）。
    ★ B1 · 独立深挖（Cai Thm 3：池子里没有，验证再松也收不到 —— 007
      50 次失败同任务，单独立簇深挖）：task_filter＝只收该 task 的 sigs
     （None＝全收老路）。配 hint_mode="fresh"＋max_clusters=1 即深挖轮。
    ★ R328 · trial 复现力分流（默认开）：m＝llm_asserted* 是 agent 执行
      侧自断言 —— trial 的 judge verifier 复现不了（R327 live 实证：63
      条 trial 全满分，基线亦满分，零 delta 不落地）。evo 只吃 verifier
      可复现簇，执行侧归 agent_quality 回路。False＝全收老路（预算自负，
      trial 空转满分已知）。
    """
    con = sqlite3.connect(db_path)
    try:
        # ★★★ R437 · 真实任务名在 memory_node.payload 里（表本身没有 task 列）。
        #   改前：`select c,q,m,node_id from failure_sig` + cron 传常量 lambda
        #   ⇒ 2034 条签名全被标成同一个任务，聚簇全糊在一起。
        try:
            rows = con.execute(
                "select f.c, f.q, f.m, f.node_id, "
                "       coalesce(json_extract(n.payload,'$.task'),'') "
                "from failure_sig f "
                "left join memory_node n on n.node_id = f.node_id").fetchall()
        except sqlite3.OperationalError:
            # 旧库/最小测试库没有 memory_node ⇒ 退回老查询（task 由调用方兜底）
            rows = [tuple(r) + ("",) for r in con.execute(
                "select c,q,m,node_id from failure_sig").fetchall()]
    finally:
        con.close()
    sigs = [{"c": r[0], "q": r[1], "m": r[2], "node_id": r[3],
             "fn": fn_of(r),
             # ★ 真实任务名优先取 payload；取不到才回退调用方兜底
             "task": (str(r[4] or "").strip() or task_of(r))}
            for r in rows]
    # ★ R437 · payload 不存 fn（实测 0/2034 有值）⇒ 从锚点 checks 反查。
    #   查不到就留空（空 fn 只影响聚簇粒度，不影响正确性）。
    _anchors: Dict[str, Any] = {}
    try:
        with io.open(os.path.join(_code_root(), "config", "anchors", "dev.json"),
                     encoding="utf-8") as _fh:
            _anchors = json.load(_fh)
    except (OSError, ValueError):
        _anchors = {}
    for _s in sigs:
        if not _s.get("fn"):
            _ck = (_anchors.get(_s.get("task", "")) or {}).get("checks") or []
            _s["fn"] = str((_ck[0] or {}).get("fn") or "") if _ck else ""
    if task_filter is not None:
        # ★ B1 · 独立深挖：只收目标 task（单独立簇，深挖一轮）。
        sigs = [s for s in sigs if s.get("task") == task_filter]
    if reproducible_only:
        # ★★★ R437 · 分流口径从"猜前缀"改成"实测签名"。
        #   旧：m.startswith("llm_asserted") ⇒ 2034 条全扔（含真能复现的）。
        #   新：跑该任务的破坏实现，看它能不能产出**同一种失败签名**；
        #       能 ⇒ 代码车道（有代码可修）；不能 ⇒ 行为车道（agent 弃答/答错）。
        _code_sigs, _behavior_sigs = [], []
        for _s in sigs:
            _probe = probe_signatures(str(_s.get("task", "") or ""))
            _hit = (("__unknown__" in _probe) or ("__crash__" in _probe)
                    or ((str(_s.get("c")), str(_s.get("q"))) in _probe))
            (_code_sigs if _hit else _behavior_sigs).append(_s)
        sigs = _code_sigs
        if filtered_out is not None:
            filtered_out.extend(_behavior_sigs)
    if not sigs:
        return []
    if use_archive_priors:
        try:
            from dwc.organs.evolver import Mutator as _MM
            _at = []
            for _lst in (_MM.ARCHIVE or {}).values():
                for _e in (_lst or []):
                    _t = (_e or {}).get("task")
                    if _t and _t not in _at:
                        _at.append(_t)
            if _at:
                _pp = list(priority_prefixes or [])
                for _t in _at:
                    if _t not in _pp:
                        _pp.append(_t)
                priority_prefixes = tuple(_pp)
        except Exception:  # noqa: BLE001 — priors 坏不断主路
            pass
    out = evolver.diagnose(sigs)
    groups = {}
    for s in out.get("unmapped", []):
        k = Mutator.key_for(s)
        groups.setdefault(k, []).append(s)
    _clusters = [{"key": k, "sigs": v} for k, v in groups.items()]
    if priority_prefixes:
        # ★ B3 · 稳定优序：命中 rank 小排前；非命中 rank＝＋∞保原序。
        def _rank(cl):
            _t = str((cl["sigs"] or [{}])[0].get("task", "") or "")
            for _i, _p in enumerate(priority_prefixes):
                if _t.startswith(_p):
                    return _i
            return len(priority_prefixes) + 1
        _clusters = sorted(_clusters, key=_rank)  # 稳定：同 rank 保原序
    return _clusters


def _read_done(path, date):
    """★ R309-⑦ · 读 epoch ledger 当日记录 {key: rec}。坏行跳过，缺文件=空。

    ★ R310-② · ok 显式 False 的簇=失败过，下轮带 fix 重跑（不跳过）；
      ok 缺省=老 ledger 行，视作已做（向后兼容）。
    """
    done = {}
    if not path:
        return done
    try:
        with open(path, encoding="utf-8") as _fh:
            _lines = _fh.read().splitlines()
    except OSError:
        _lines = []
    for _ln in _lines:
        try:
            _d = json.loads(_ln)
        except Exception:
            continue
        if isinstance(_d, dict) and _d.get("date") == date and _d.get("key"):
            done[_d["key"]] = _d
    return done


def _append_ledger(path, rec):
    """★ R309-⑦ · 单簇完成即 append（一行一簇，crash 不丢已做）。"""
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as _fh:
            _fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError as _le:
        _ledger_err = _le


def triage_report(rep):
    """★ R310-③ · triage 分类机（抄 Capy triage：分类＋recommendations）。

    纯呈现：只读 rep["results"]，不改任何判定。类别：
    landed（已落）/ready（trial 过待拍板）/stuck（预算耗尽）
    /draft_failed（起草挂）/skipped（resume 跳过）。
    ★ A6 · peak-picking 禁令（companion：HarnessX 报 peak 73.8% 而终态
      49.5%）：本报告只呈当轮终态＋ledger 行，不回溯历史 peak，不跨轮
      取最优。任何新增呈现面同律。
    """
    try:
        tasks = []
        for _r in (rep or {}).get("results", []) or []:
            _k = _r.get("key", "?")
            if _r.get("landed") is True:
                _c = "landed"
            elif _r.get("trial") is True:
                _c = "ready"
            elif "ledger 已做" in str(_r.get("reason", "")):
                _c = "skipped"
            elif _r.get("drafted") is False and _r.get("trial") is None:
                _c = "draft_failed"
            else:
                _c = "stuck"
            tasks.append({"key": _k, "category": _c,
                          "trial": _r.get("trial"),
                          "adopt": _r.get("adopt"),
                          "reason": str(_r.get("reason", ""))[:200]})
        _sum = {"total": len(tasks), "landed": 0, "ready": 0, "stuck": 0,
                "skipped": 0, "draft_failed": 0}
        for _t in tasks:
            _sum[_t["category"]] += 1
        _recs = []
        for _t in tasks:
            if _t["category"] == "ready":
                _recs.append("落盘拍板：%s（trial 已过，--apply 审后落）"
                             % (_t["key"],))
            elif _t["category"] == "stuck":
                _recs.append("重跑或停：%s（%s）"
                             % (_t["key"], _t["reason"][:100]))
            elif _t["category"] == "draft_failed":
                _recs.append("下轮重看：%s（起草挂，瞬时抖可能自愈）"
                             % (_t["key"],))
        return {"summary": _sum, "tasks": tasks,
                "recommendations": _recs}
    except Exception as _te:
        return {"summary": {"total": 0, "landed": 0, "ready": 0, "stuck": 0,
                            "skipped": 0, "draft_failed": 0},
                "tasks": [], "recommendations": [],
                "note": "triage 失败：%r" % (_te,)}


def _forbidden_expected(judge):
    """返回 benchmark expected_behavior 集合；judge=None ⇒ None（不可判定）。"""
    if judge is None:
        return None
    out = set()
    for _a in (getattr(judge, "anchors", None) or {}).values():
        _eb = (_a or {}).get("expected_behavior")
        if _eb:
            out.add(_eb)
    return out


def run_round(db_path, evolver, mu, context, trial_fn, apply, rules_path,
              backup_dir=None, fn_of=None, task_of=None, max_clusters=3,
              want_code_of=None, mech_log=None, trace_log=None,
              ledger_path=None, resume=True, ledger_date=None,
              max_attempts=3, priority_prefixes=None,
              task_filter=None, hint_mode="reuse", pool_n=None,
              reproducible_only=True, clusters=None, max_land=None,
              lane_component="control_flow", judge=None):
    """★ 一轮收尾：聚簇→起草→试跑→（可选）落盘。返回可审计报告。

    ★ R295-Task3 · want_code_of(task)→bool（code_repair 写码真执行分流；
      None=不求码，老路零变）。trial_fn 三参契约 (task, patch, code=None)。
    ★ R310-⑤ · max_attempts（默认 3）：单簇 trial 非 True 重试预算。
    ★ B4 · 候选池 N（Cai Thm 3 Eq.8：N 进界 —— 池子里没有，验证再松也
      收不到）：pool_n＝单簇候选池上限（串行试，单进程无真并行；None＝
      max_attempts 老路）。调大即涨 LLM 预算（每候选一次起草＋trial）。
    ★ A6 · peak-picking 禁令：返回体只装当轮终态（results 当轮行＋ledger
      追加行），禁报历史 peak（companion HarnessX 反例：报 peak 73.8% 而
      终态 49.5%）。调用方要趋势自己读 ledger 全史，本函数不代取最优。
    ★ D4 · 术语对齐（18813 四段）：本函数四段＝
      diagnose（collect_unmapped：聚失败签名成簇）→
      propose（propose_from_cluster：簇→候选）→
      assess（trial_fn 试跑＋accept 门判：候选→真分）→
      admit（_land_adopted：过门→RULES 落地）。
      旧名保留（collect_unmapped 被 r278 测试直调，改名破调用面 ——
      对齐先行术语，改名另轮）。
    ★ B3 · 火力转攻：priority_prefixes 透传 collect_unmapped（默认 None
      老路；cron 传 ("code_fix",) 生产生效）。
    ★ B1 · 独立深挖：task_filter＋hint_mode 透传（默认全收＋reuse 老路；
      cron --deep-task 传 task＋fresh＋max_clusters=1 即深挖轮）。
    ★ R328 · reproducible_only 透传（默认 True 分流；False 全收老路）。
    """
    fn_of = fn_of or (lambda r: "")
    # ★ B4 · 候选池 N 单真源（None⇒max_attempts；单进程串行，无真并行）。
    _pool_n = pool_n if pool_n is not None else max_attempts
    task_of = task_of or (lambda r: "")
    want_code_of = want_code_of or (lambda t: False)
    _nonrepro: list = []
    # ★ B3 · 外部簇注入（--from-proposals）：给了就不读库 —— live 路径
    #   的签名带 fn/task，比 failure_sig 表（无 fn 列）更准。
    if clusters is None:
        clusters = collect_unmapped(db_path, evolver, fn_of, task_of,
                                    priority_prefixes=priority_prefixes,
                                    task_filter=task_filter,
                                    reproducible_only=reproducible_only,
                                    filtered_out=_nonrepro)
    else:
        clusters = list(clusters)
    # ★ D4-① diagnose 段（18813：失败签名→候选前，先聚簇定位病灶）。
    results = []
    # ★ R438 · 单轮落地配额（None = 不限；生产由 evolution.yaml 给 1）
    _n_landed = 0
    # ★ R309-⑦ · 当日已做 key（ledger 缺=空集=老路全跑，一字不差）。
    _date = ledger_date or time.strftime("%Y-%m-%d")
    _done = (_read_done(ledger_path, _date)
             if (ledger_path and resume) else {})
    for cl in clusters[:max(1, max_clusters)]:
        item = {"key": cl["key"], "n": len(cl["sigs"]),
                "drafted": False, "trial": None,
                "landed": False, "backup": None}
        _rec = _done.get(cl["key"])
        # ★ R310-② · ok=False 的簇=上轮失败，带 fix 重跑（只跳真做过的）。
        _fix = ""
        if _rec is not None and _rec.get("ok", True) is not True:
            _fix = str(_rec.get("note", "") or _rec.get("reason", ""))[:300]
        elif _rec is not None:
            item["reason"] = "ledger 已做（resume 跳过）"
            results.append(item)
            continue
        # ★ R310-⑤ · 重试预算：propose＋trial 包进 attempt 循环（起草抛错/
        #   None 不占预算直接停——瞬时抖下轮 cron 重来，不在本轮烧 LLM）。
        _att = 0
        _fatal = False
        _ok = None
        t = None
        p = None
        while True:
            _att += 1
            try:
                _task = cl["sigs"][0].get("task", "")
                # ★ R300-A · hint 组装（同簇查 RULES，有则禁重复段；try 包，
                #   坏不断起草——hint 是增强非门槛）。
                _hint = ""
                try:
                    from dwc.organs.evolver import Mutator as _MM
                    _s0 = dict(cl["sigs"][0])
                    _k = _MM.key_for({"c": _s0.get("c"), "q": _s0.get("q"),
                                      "fn": _s0.get("fn")})
                    _old = _MM.RULES.get(_k)
                    if hint_mode == "fresh":
                        # ★ B1 · hint 换血 ξ（Cai Thm 3：旧 patch 已 50 次证
                        #   伪，池外无解 —— 不用旧 patch，改喂簇内失败明细）。
                        _det = "; ".join(
                            "%s/%s/%s" % (s.get("c"), s.get("q"),
                                          s.get("m"))
                            for s in cl["sigs"][:10])
                        _hint = ("失败明细换血ξ（不用旧patch）：%s" % (_det,))
                    elif isinstance(_old, dict):
                        _hint = "%s：%s" % (_old.get("m", ""),
                                           _old.get("patch", ""))
                except Exception:               # noqa: BLE001 — 坏则无段
                    _hint = ""
                # ★ R305-T3 · project_hint 接线（trace_log 传了⇒同组前情追加；
                #   不传老路零变。坏不拦，hint 是增强非门槛）。
                if trace_log:
                    try:
                        from dwc.llm.project_hint import proj_id as _pid
                        from dwc.llm.project_hint import project_hint as _ph
                        _gt: dict = {}
                        with open(trace_log, encoding="utf-8") as _fh:
                            for _ln in _fh.read().splitlines():
                                try:
                                    import json as _js
                                    _d = _js.loads(_ln)
                                except Exception:
                                    continue
                                if isinstance(_d, dict) and _d.get("task"):
                                    _gt.setdefault(
                                        _pid(str(_d["task"])), []).append(
                                            _ln[:200])
                        _ph_seg = _ph(_task, _gt)
                        if _ph_seg:
                            _hint = ((_hint + "\n" + _ph_seg)
                                     if _hint else _ph_seg)
                    except Exception:           # noqa: BLE001 — 坏则无段
                        pass
                # ★ R310-② · fix 注入（首轮）：上轮失败原因进 hint（Capy
                #   --fix 语义；失败变燃料）。
                if _fix and _att == 1:
                    _hint = ((_hint + "\n" if _hint else "") +
                             "上轮失败（fix）：%s" % (_fix,))
                # ★ R349 · reconstructive retrieval：archive 重建上下文喂 propose。
                try:
                    _rc = Mutator.reconstruct_context(_task)
                    if _rc:
                        _hint = ((_hint + "\n" + _rc) if _hint else _rc)
                except Exception:  # noqa: BLE001 — 坏不断起草
                    pass
                # ★ R350 · skill select：DWC-internal skill 上下文喂 propose。
                try:
                    _sk = Mutator.skill_select(_task)
                    if isinstance(_sk, dict) and _sk.get("content"):
                        _hint = ((_hint + "\n" + _sk["content"]) if _hint else _sk["content"])
                except Exception:  # noqa: BLE001 — 坏不断起草
                    pass
                # R351 Evo2 donor strategy injection
                try:
                    _donor = Mutator.select_donor(_task)
                    if isinstance(_donor, dict) and _donor.get("mechanism"):
                        _hint = ((_hint + "\n[donor: %s -> d=%.3f]" % (
                            _donor["mechanism"], _donor.get("observed_effect", 0)))
                                 if _hint else "[donor: %s]" % _donor["mechanism"])
                except Exception:
                    pass
                # R351 Evo2 donor strategy injection
                try:
                    _donor = Mutator.select_donor(_task)
                    if isinstance(_donor, dict) and _donor.get("mechanism"):
                        _hint = ((_hint + "\n[donor: %s -> d=%.3f]" % (
                            _donor["mechanism"], _donor.get("observed_effect", 0)))
                                 if _hint else "[donor: %s]" % _donor["mechanism"])
                except Exception:
                    pass
                # R351 Evo2 donor strategy injection
                try:
                    _donor = Mutator.select_donor(_task)
                    if isinstance(_donor, dict) and _donor.get("mechanism"):
                        _hint = ((_hint + "\n[donor: %s -> d=%.3f]" % (
                            _donor["mechanism"], _donor.get("observed_effect", 0)))
                                 if _hint else "[donor: %s]" % _donor["mechanism"])
                except Exception:
                    pass
                _key = Mutator.key_for(cl["sigs"][0])
                # ★ R447 · 同族经验注入：把库里**同族**的 lesson 拼进起草提示。
                #   ★★ 只拼 lesson，绝不拼 code —— Harness² 实测继承实现会掉分
                #   （WB-code 73.4→63.2）。经验可以借鉴，实现不能继承。
                try:
                    from dwc.organs import library as _LB
                    _lh = _LB.hint_for(_key)
                    if _lh:
                        _hint = ((_hint or "") + _lh)
                        item["hint_lessons"] = _lh.count("\n- ")
                except Exception as _le:      # noqa: BLE001 — 经验注入坏不掀轮
                    item["hint_lessons"] = "error: %r" % (_le,)
                _op = "draft" if _key not in Mutator.RULES else "improve"
                if str(_task).startswith("code_fix"):
                    _op = "debug" if _op == "improve" else _op
                if len(cl["sigs"]) > 1:
                    _op = "crossover"
                # ★ R438 · 车道组件只传给支持它的 mutator（鸭子类型：
                #   测试替身/旧实现没有 component 参数时，行为与改前一致）
                _kw_comp = {}
                try:
                    import inspect as _insp
                    if "component" in _insp.signature(
                            mu.propose_from_cluster).parameters:
                        _kw_comp = {"component": lane_component}
                except (TypeError, ValueError):
                    _kw_comp = {}
                with task_measurement_context(
                        _task, candidate_id=cl["key"], rollout_id=str(_att)):
                    with measurement_role("editor"):
                        p = mu.propose_from_cluster(
                            cl["sigs"], context,
                            want_code=want_code_of(_task),
                            learned_hint=_hint,
                            operator=_op,
                            **_kw_comp)
                # ★ COR-02 · patch 层 dedup：patch 不得包含 benchmark 的
                #   expected_behavior。judge 缺失 ⇒ 不可判定：只报告时标
                #   unavailable；apply 时 fail-closed，绝不静默跳过。
                _forbidden = _forbidden_expected(judge)
                if _forbidden is None:
                    item["dedup_status"] = "unavailable"
                    if apply:
                        item["reason"] = ("dedup_unavailable_fail_closed: "
                                          "judge 未传入，无法检查 benchmark 泄漏")
                        _fatal = True
                        break
                else:
                    item["dedup_status"] = "checked"
                    if p is not None and any(_f in (p.patch or "")
                                            for _f in _forbidden):
                        item["reason"] = ("patch leaks benchmark expected_behavior "
                                          "(dedup reject)")
                        _fatal = True
                        break
            # ★ D4-② propose 段（簇→候选；候选≠有效，门＋试跑在后）。
            except Exception as exc:  # ★ cron 体质：单簇端点抖不许掀整轮（留痕继续）
                item["reason"] = "起草抛错：%r" % (exc,)
                _fatal = True
                break
            if p is None:
                item["reason"] = mu.last_reason
                _fatal = True
                break
            item["drafted"] = True
            item["proposal_id"] = p.proposal_id
            _u0 = _usage_total()
            with task_measurement_context(
                    _task, candidate_id=p.proposal_id, rollout_id=str(_att)):
                with measurement_role("evaluation"):
                    t = trial_fn(cl["sigs"][0].get("task", ""), p.patch, p.code)
            # ★ R445 · 这次 trial 烧的 token（评测开销，不是规则成本 —— 见 pareto.py）
            item["trial_tokens"] = max(0, _usage_total() - _u0)
            # ★ D4-③ assess 段（试跑＋门判：候选→真分；真伪由门＋held_out 定）。
            item["trial"] = t                  # ★ 原样存（bool/dict 照旧）
            # ★ R290-P1 · 归一：dict 取 success，bool/None 照旧（旧契约不断）。
            _ok = (t.get("success") if isinstance(t, dict) else t)
            if _ok is True or _att >= max(1, _pool_n):
                break
        item["attempts"] = _att
        if _fatal:
            results.append(item)
            continue
        if _att > 1 and _ok is not True:
            item["reason"] = "重试预算耗尽（%d 次 trial 未过）" % (_att,)
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
            # ★ R438 · 落地配额：满了就只报告（不静默 —— reason 写明）
            if max_land is not None and _n_landed >= max_land:
                item["reason"] = ("落地配额已满（max_land=%d）—— 本轮只报告不落"
                                  % max_land)
                item["adopt"] = "quota_exceeded"
                results.append(item)
                continue
            # ★ R287-C · adopt 门（Evolver.accept）：trial 布尔无分数 ⇒
            #   accept 缺 baseline/current 会判 not_evaluated/blocked。
            #   诚实处置：先判，有分数走门（第五态→_land_adopted 落）；
            #   无分数走 legacy 直落但标记 decision（门没判≠门过了 ——
            #   收紧点：trial_fn 带分数之日 legacy 分支删除，见 ★TODO）。
            try:
                # ★ R300-A · 传 mode（code 路走知识分支；缺省 report 老路）。
                # ★ A1a · Eq.8 四数：m＝本轮验证样本量（in＋ho 非 None 个数；
                #   非 dict trial⇒None 诚实缺席）；KT̂＝attempts（比较次数）。
                _m = (((t.get("in_score") is not None) +
                       (t.get("held_out") is not None))
                      if isinstance(t, dict) else None)
                _ad = evolver.accept(
                    p, baseline=_base, current=_cur,
                    mode=((t.get("mode") or "report")
                          if isinstance(t, dict) else "report"),
                    m=_m, k_comparisons=_att)
            except Exception as exc_a:  # noqa: BLE001
                _ad = {"decision": "accept_error",
                       "why": "accept 抛错：%r" % (exc_a,)}
            item["adopt"] = _ad.get("decision")
            # ★ R310-① · 门阵列透出（调用方只读，decision 口径不动）。
            item["gates"] = _ad.get("gates", [])
            if "delta_in" in _ad:
                item["delta_in"] = _ad["delta_in"]
            if "delta_ho" in _ad:  # ★ R291-P4 Task 2 · 真 Δ_ho 透出（门判的）
                item["delta_ho"] = _ad["delta_ho"]
            if _ad.get("decision") == "adopted_not_implemented":
                # ★ R438 · 架构类提案**不许自动落**（系统层改动须人工批准）
                if p.component == "architecture":
                    from dwc.organs.arch_queue import enqueue as _aq_enq
                    item["arch"] = _aq_enq(p.component, p.target,
                                           p.patch, p.rationale)
                    item["adopt"] = "queued_for_approval"
                    item["reason"] = ("架构类提案已入人工审批队列"
                                      "（var/architecture_queue.jsonl）")
                else:
                    # ★ R291-P4 Task 2 · 门判过⇒置第五态再落地（_land_adopted
                    #   前置要 p.state；置态=记录门判结果，不编造）。
                    p.state = "adopted_not_implemented"
                    # ★ C3 · provenance：admission 轮用 ledger_date（轮日期口径）。
                    # ★ D4-④ admit 段（过门→RULES 落地；门没过不落地 R291 已删）。
                    item["backup"] = evolver._land_adopted(
                        p, admission_round=ledger_date)
                    item["landed"] = True
                    _n_landed += 1
                    # ★ R446 · P4 改进库：落地即入库（三要素缺一不入，不写半条）。
                    #   ★ 只写不读：起草仍走 rules.json 的 hint_code —— 不假装已复用。
                    try:
                        from dwc.organs import library as _LB
                        _ent = _LB.from_rule(
                            str(cl.get("key") or ""),
                            {"rationale": getattr(p, "rationale", ""),
                             "provenance": {"proposal_id":
                                            getattr(p, "proposal_id", "")}},
                            t if isinstance(t, dict) else {})
                        _why = _LB.validate(_ent)
                        if _why:
                            item["library"] = {"added": False, "why": _why}
                        else:
                            _row = _LB.add(entry=_ent)
                            item["library"] = ({"added": True,
                                                "cue": _row["cue"]}
                                               if _row else
                                               {"added": False, "why": "落盘失败"})
                    except Exception as _le:      # noqa: BLE001 — 记账坏不撤落地
                        item["library"] = {"added": False, "why": repr(_le)}
            else:
                # ★ R291-P4 Task 3 · legacy 直落已删（条件①②齐：trial 有
                #   分数＋accept 拿真输入）。门没判过（blocked/rejected/
                #   not_evaluated/accept_error）⇒ 不落地，只留痕 ——
                #   门没判≠门过了。
                item["reason"] = ("accept 门未过（%s）：无分数 trial 或门判"
                                  "未通过 ⇒ 不落地（legacy 直落 R291 已删）"
                                  % (_ad.get("decision"),))
        results.append(item)
        # ★ R309-⑦ · 簇终即记（append-only；落的是试跑记录≠代码落地，
        #   不撞 R279 只报告不落盘）。
        # ★ R310-② · 重跑簇（_fix 非空）也记新行（ledger 按行追加，后行、
        #   同 key ok=True 即视为已做——读时后写覆盖先写靠 dict 赋值序）。
        if ledger_path and (cl["key"] not in _done or _fix):
            _t = item.get("trial")
            _ok = (_t.get("success") if isinstance(_t, dict) else _t)
            _append_ledger(ledger_path, {
                "date": _date, "key": cl["key"], "n": len(cl["sigs"]),
                "proposal_id": item.get("proposal_id"),
                "ok": _ok, "landed": item.get("landed", False),
                "attempts": item.get("attempts", 1),
                # ★ R310-② · note 供下轮 fix（dict trial 取 reason）。
                "note": (str(_t.get("reason", ""))[:200]
                         if isinstance(_t, dict) else ""),
                "reason": str(item.get("reason", ""))[:200],
                "ts": time.time()})
    # ★ R285-P2 · 未接线清单（QUALITY_GATE Γ："本应调用但未调用"负事件）。
    #   门：Loop.round 生产调用之日即摘牌之时，在此之前任何接线 PR 一律拒。
    # ★ R294 · 三项全摘（R290-P0 world.select IG 排序／R291-P4 metric.select→
    #   adopt 真 held_out／R290-P2 direction 起草环）⇒ 清单清零（全接线）。
    # ★ 审计黄① · 机制健康门（只读+建议：读目录 enabled＋mech 留痕→advise，
    #   立案进 report；绝不改配置。mech_log=None 老路零变）。
    _mech_advise = []
    if mech_log:
        try:
            from dwc.foundation.mech_registry import load as _mload
            from dwc.foundation.mech_health import advise as _madv
            from dwc.llm.mech_trace import read_mech_events as _mread
            _reg = _mload()
            _en = [n for n, e in _reg.items() if e.get("enabled")]
            _mech_advise = _madv(_en, _mread(mech_log))
        except Exception:                   # noqa: BLE001 — 坏不断轮
            _mech_advise = []
    _rep = {"n_clusters": len(clusters), "results": results,
            "not_wired": [], "mech_advise": _mech_advise,
            "filtered_nonreproducible": len(_nonrepro),
            # ★ R437 · 两条车道分开报：代码车道进 evolver，行为车道进队列。
            #   旧口径只有一个 filtered 数，看不出"被丢掉的是什么"。
            "n_code_sigs": sum(len(_c.get("sigs") or []) for _c in clusters),
            "n_behavior_sigs": len(_nonrepro),
            "behavior_sigs": _nonrepro[:2000]}
    # ★ D2 · envelope 声明（companion：search cost 与 envelope 分开列）。
    #   trial_rounds＝本轮 trial 调用总数（attempts 求和）；by_mode＝trial
    #   mode 分布（按 results 行计末次 trial 的 mode；code 路＝LLM search
    #   面；report/legacy_bool＝零 search 查表面）；llm_calls/tokens＝unmeasured（llm 在 trial_fn 闭包内＋
    #   R42 声明 DWC 未记 token —— 诚实缺席，计数需另轮改 trial 契约）。
    _env_modes: dict = {}
    for _it in results:
        _tt = _it.get("trial")
        _m = (_tt.get("mode") if isinstance(_tt, dict) else "legacy_bool")
        _env_modes[_m or "report"] = _env_modes.get(_m or "report", 0) + 1
    _rep["envelope"] = {
        "trial_rounds": sum(int(_it.get("attempts", 1) or 1)
                            for _it in results),
        "pool_N": _pool_n,  # ★ B4 · 候选池上限（Thm 3 Eq.8 的 N）
        "by_mode": _env_modes,
        "llm_calls": "unmeasured（llm 在 trial_fn 闭包内 — 另轮改契约）",
        # ★ R439/R442 · token 现在**真的记了**（var/llm_usage.jsonl + cost_ledger）。
        #   旧文案"未记 token"已不成立，留着就是幻影声明。
        "tokens": "见 cost_attribution（var/llm_usage.jsonl 按 task 聚合）",
        "search_cost": "另列：by_mode.code＝LLM search 面；其余零 search"}
    # ★ R445 · P3 Pareto（观测）：把本轮候选按 (分数, trial token) 放到前沿上。
    #   ★★ 诚实：DWC 一轮只留**一个**成功候选（试到过就 break）⇒ 前沿必然只有一个点，
    #   这一步今天不改变任何决策。它的价值是**把数据结构备好**：
    #   等多候选并行那天（需预算支持），select() 才真的有得选。
    try:
        from dwc.organs import pareto as _PA
        _pts = []
        for _r in results:
            _t = _r.get("trial")
            _sc = _t.get("in_score") if isinstance(_t, dict) else None
            _tk = _r.get("trial_tokens")
            if _sc is None or _tk is None:
                continue
            _pts.append({"name": str(_r.get("proposal_id") or _r.get("key") or ""),
                         "score": _sc, "cost": _tk})
        _rep["pareto"] = {
            "n_candidates": len(_pts),
            "front": _PA.non_dominated(_pts),
            "lite": (_PA.select(_pts, "lite") or {}).get("name"),
            "medium": (_PA.select(_pts, "medium") or {}).get("name"),
            "heavy": (_PA.select(_pts, "heavy") or {}).get("name"),
            "note": ("观测项，不接管 landing：一轮只有一个成功候选，前沿必然单点；"
                     "且 trial_tokens 是评测开销、不是规则线上成本"),
        }
    except Exception as _pe:      # noqa: BLE001 — Pareto 坏不掀轮
        _rep["pareto"] = {"error": repr(_pe)}
    # ★ R448 · 上下文决策分布（trigger|selector → 次数 / 压缩比）
    try:
        from dwc.llm import context_log as _clog
        _rep["context"] = _clog.summary()
    except Exception as _ce:      # noqa: BLE001 — 留痕坏不掀轮
        _rep["context"] = {"error": repr(_ce)}
    # ★ R446 · P4 改进库（观测）：落地即入库，这里只报规模。
    #   ★ R447 起库**已接入起草**：hint_for() 的输出拼进 learned_hint
    #   （只注 lesson，不注 code）。
    try:
        from dwc.organs import library as _LB
        _lib = _LB.load()
        _rep["library"] = {
            "n_entries": len(_lib),
            "families": sorted({_LB.family(str(r.get("cue") or ""))
                                for r in _lib}),
            "note": "已接入起草：hint_for → learned_hint（只注 lesson）",
        }
    except Exception as _le:      # noqa: BLE001 — 库坏不掀轮
        _rep["library"] = {"error": repr(_le)}
    # ★ R442 · 成本归因（回溯）：本轮每任务平均 token + 与上次快照的走向。
    #   ★★ 诚实边界（R445 更正）：trial **确实会调 LLM**（peer held-out），
    #   但那部分是**评测开销**，两臂都要付，与候选规则的线上成本无关
    #   ⇒ 不能拿它当"候选成本"。这里量的是**生产**成本（按 task_id 聚合）。
    #   没有数据 ⇒ None（不猜 0）。
    try:
        from dwc.organs import cost_attribution as _ca
        _snap = _ca.snapshot(note="evo_round")
        _rep["cost_attribution"] = {
            "n_tasks": _snap.get("n_tasks"),
            "mean_total": _snap.get("mean_total"),
            "trend": _ca.trend(),
            # ★ R447 · 按档位分布（哪档更省，跑几天才有结论）
            "by_profile": _ca.by_profile(),
            "scope": "回溯归因（生产任务）；trial 的 token 是评测开销，不是规则成本",
        }
    except Exception as _ce:      # noqa: BLE001 — 归因坏不掀轮
        _rep["cost_attribution"] = {"error": repr(_ce)}
    # ★ R449 · 规则版本成本轴：每条已落地规则按激活时刻切前后两段。
    #   ★★ 这是**分段相关不是因果**（激活前后任务构成会变），每份结果自带 confound。
    try:
        from dwc.organs import cost_attribution as _ca2
        from dwc.organs.evolver import Mutator as _Mu2
        _rc: Dict[str, Any] = {}
        for _rk, _rv in (_Mu2.RULES or {}).items():
            if _rk in _Mu2.SEED_KEYS:
                continue
            _rc[_rk] = _ca2.by_rule_epoch(
                (_rv or {}).get("activated_at"))
        _rep["rule_cost"] = _rc
    except Exception as _re:      # noqa: BLE001 — 成本轴坏不掀轮
        _rep["rule_cost"] = {"error": repr(_re)}
    # ★ R310-③ · triage 附报告（纯呈现，不改判定）。
    _rep["triage"] = triage_report(_rep)
    return _rep


# ★ R291-P4 Task 3 · _land（legacy 直落落盘）已删 —— 唯一调用点已删，
#   死函数不留（_land_adopted 是唯一的落地路径）。
def _code_prompt(fn: str, skel) -> str:
    """★ R295-Task3 · 写码 prompt（peer 独立出码用；本 task 的码起草已出）。"""
    import json as _json
    return ("写一个完整可执行 Python 函数（只输出代码块、无解释，"
            "不要复述本指令、不要写思考过程）：\n"
            "函数名 %s，输入输出形态（fn -> [[args, 期望], ...]，args 是单个参数）：\n%s\n"
            "纯函数，只用 sum/len/range 等纯内建，禁 import、禁 open/exec/eval、"
            "禁 while、禁双下划线属性。"
            % (fn, _json.dumps(skel, ensure_ascii=False)))


def _extract_code(text: str, fn: str = ""):
    """★ 取 ```python 块（无⇒None，不编）。

    ★ R295补 · 兜底裸码：LLM 有时鹦鹉学舌只复述指令、无成对 fence，
      或直接贴裸 def——此时按 `^def <fn>(` 起抓到文末（安全不降级：
      沙箱 AST 全拒仍在，坏码进沙箱照拒）。
    """
    import re
    m = re.search(r"```(?:python)?\s*(.*?)```", text or "", re.S)
    if m and m.group(1).strip():
        return m.group(1).strip()
    if fn:
        m2 = re.search(r"(?m)^def\s+%s\s*\(.*"
                       % re.escape(fn), text or "")
        if m2:
            return (text[m2.start():]).strip()
    return None


def _evo_spread():
    """★ A3 · 小Δ熔断读数：bench report 的 spread_mean（D1 常驻）。

    无文件/无值/坏 ⇒ None（缺席不开门 —— spread 未测时熔断永不开，
    不猜阈值；0.0=测了零方差，任何非零 |Δ| 都值得验，照样开）。
    """
    try:
        with io.open(os.path.join(_code_root(), "var",
                                  "dwc_bench_results.json"),
                     encoding="utf-8") as f:
            _r = json.load(f).get("spread_mean")
        return float(_r) if _r is not None else None
    except (OSError, ValueError, TypeError):    # noqa: BLE001 — 坏不断试跑
        return None


def _small_delta_fused(in_score, base):
    """★ A3 · 小Δ熔断判据（Cai Thm 5：|Δ|<spread ⇒ 不烧 peer 验证预算）。

    回 (fused, d_in)：差任一 None/读数 None ⇒ (False, d_in) 不熔断。
    """
    _d = ((in_score - base)
          if (in_score is not None and base is not None) else None)
    _sp = _evo_spread()
    if _d is not None and _sp is not None and abs(_d) < _sp:
        return True, _d
    return False, _d


def _peer_held_out_code(judge, llm, task, max_tokens=1500, max_attempts=3,
                         hint_code=None):
    """★ R295-Task3 · peer 写码独立评估（fail-closed：任一步坏⇒None）。

    peer fn 与 dev fn 不一样（R291-P4 Task4）⇒ peer 另出码另真跑，
    不是复用本 task 的 code。llm 缺席（沙箱单测）⇒None。★ R295补 ·
    peer prompt 出码不稳定（有时回解释无代码块）⇒无码重试
    max_attempts 次，空码不进沙箱（compile(None) TypeError 免吞）；
    3 次都不出⇒None（fail-closed，不编分）。
    ★ R299 · hint_code（trial 成功码 few-shot）：非空⇒拼进 peer prompt
    当翻译参考（本轮已验证算法，翻译成功率>从零写）；缺席/空⇒老路
    （prompt 不变）。hint 只进 prompt，不进判分（judge 零改）；
    ho 仍 None⇒门仍 blocked（门语义零改）。
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
        # ★ R299 · hint 拼 prompt（非空才拼；空⇒老路一字不差）
        _base_prompt = _code_prompt(_pfn, _pskel)
        if (hint_code or "").strip():
            _base_prompt += ("\n已验证对的同族解（仅供翻译参考，"
                             "必须按上面函数名/形态重写）：\n%s"
                             % hint_code.strip())
        for _ in range(max_attempts):
            with task_measurement_context(task):
                with measurement_role("evaluation"):
                    _pr = llm.complete(_base_prompt,
                                       max_tokens=max_tokens)
            if not _pr.ok:
                continue
            _pcode = _extract_code(_pr.text or "", _pfn)
            if not (_pcode or "").strip():
                continue  # ★ 无码重试（不进沙箱）
            _pobs = run_code_observed(_pcode, _pskel)
            if _pobs is None:
                continue  # ★ 跑挂重试（换一版码）
            return judge.held_out_score(_peer, _pobs)
        return None
    except Exception:                               # noqa: BLE001 — 坏不断试跑
        return None


def _usage_total() -> int:
    """当前用量日志的 prompt+completion 总和（trial 前后差值 = 这次 trial 烧的）。"""
    try:
        from dwc.llm import cost as _c
        import io as _io
        n = 0
        with _io.open(_c.usage_log_path(), encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                n += int(r.get("prompt_tokens") or 0)
                n += int(r.get("completion_tokens") or 0)
        return n
    except Exception:      # noqa: BLE001 — 记账坏不许掀轮
        return 0


def _real_trial(judge, llm, task, patch, max_tokens=1500, code=None,
                agent_executor=None):
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
    # ★ R299-b · 基线前置快照（自己不当自己基线）：
    #   evaluate→store.record 当场记点，判后取 base 拿到的是自己刚判的分
    #   （d_in 恒 0，门永不过）。先 snapshot 历史（dev 同 task 末 point
    #   ＋ peer test 末 point），再判。无历史⇒None（门 not_evaluated 诚实）。
    # ★ R299-b3 · 同轮串行污染切除（首调记点数，切片只取轮首已有点）：
    #   同轮多簇共享 judge，后簇快照会读到前簇刚记的分（b_in=前簇分）。
    #   首调时 evaluate 尚未跑，len=轮首点数；已有 n0（同轮后簇）⇒沿用。
    #   跨轮新 Judge 无 n0⇒重记（生产每轮新实例，安全）。
    def _snap(_task, _split):
        try:
            _n0 = getattr(judge, "_r299_n0", None)
            if not isinstance(_n0, int):
                try:
                    _n0 = len(judge.task_scores())
                    judge._r299_n0 = _n0
                except Exception:               # noqa: BLE001 — 坏则全查
                    _n0 = None
            _pts = [p for p in judge.task_scores(split=_split)
                    if p.task_id == _task]
            if isinstance(_n0, int):
                _all = judge.task_scores()
                _pts = [p for p in _all[:_n0]
                        if p.split == _split and p.task_id == _task]
            return _pts[-1].score if _pts else None
        except Exception:                       # noqa: BLE001 — 历史坏不断试跑
            return None
    _peer = None
    try:
        if hasattr(judge, "held_out_peer"):
            _peer = judge.held_out_peer(task)
    except Exception:                           # noqa: BLE001 — 表坏不断试跑
        _peer = None
    _base_in = _snap(task, "dev")
    _base_ho = _snap(_peer, "test") if _peer else None
    # ★ R339 · agent 路径（可插拔）：若注入 agent_executor，则真跑 agent
    #   路径，失败 fail-closed（不回落报数路，避免混归因）。
    if agent_executor is not None:
        try:
            _res = agent_executor(task, patch, code)
        except Exception as _ae:  # noqa: BLE001 — 大声留痕
            return {"success": None, "in_score": None, "baseline_in": _base_in,
                    "held_out": None, "mode": "agent", "partial": None,
                    "reason": "agent 路径抛错：%r" % (_ae,), "activated": False,
                    "mechanism_ran": False}
        if not isinstance(_res, dict) or _res.get("success") is None and \
                _res.get("in_score") is None:
            return {"success": None, "in_score": None, "baseline_in": _base_in,
                    "held_out": None, "mode": "agent", "partial": None,
                    "reason": "agent 路径无有效结果（fail-closed）", "activated": False,
                    "mechanism_ran": False}
        _res = dict(_res)
        _res.setdefault("mode", "agent")
        _res.setdefault("baseline_in", _base_in)
        _res.setdefault("partial", _res.get("in_score"))
        _res.setdefault("activated", True)
        _res.setdefault("mechanism_ran", True)
        _res.setdefault("recovery_attempted", False)
        return _res
    _mode = "report"
    if code and _cat == "code_repair":
        from dwc.llm.sandbox import run_code_observed, SandboxError
        _mode = "code"
        _diag: Dict[str, Any] = {}
        _skel = obs_skeleton(judge.anchors, task)
        try:
            _obs = run_code_observed(code, _skel, diag=_diag)
        except SandboxError as _se:
            return {"success": None, "in_score": None, "baseline_in": None,
                    "held_out": None, "mode": _mode, "partial": None,
                    "reason": "沙箱拒：%s" % (_se,), "activated": False}
        if _obs is None:
            return {"success": None, "in_score": None, "baseline_in": None,
                    "held_out": None, "mode": _mode, "partial": None,
                    "reason": "沙箱跑挂/缺函数（fail-closed）：%s"
                              % (_diag.get("error") or "缺函数或超时",),
                    "activated": False}
        suc = judge.evaluate(task, "dev",
                             observed={"observed": _obs,
                                       "★_executed": True}).success
        # ★ R299-b · 基线用前置快照（判后取=自己，d_in 恒 0 死门已除）。
        base = _base_in
        _cur = (1.0 if suc is True else (0.0 if suc is False else None))
        # ★ A3 · 小Δ熔断（code 路）：|Δ_in|<spread ⇒ 跳过 peer 验证，
        #   省出码+沙箱 LLM 预算；held_out=None ⇒ 门仍 blocked（门语义零改）。
        _fused, _d_in = _small_delta_fused(_cur, base)
        # ★ R443 · 逐例对比（分数之外看得见"哪几例错了"）
        try:
            from dwc.organs import contrast as _CT
            # ★ 期望值只能从 anchor 的 checks 取 —— 骨架里的 expected 是 None
            _exp = _CT.expected_from_checks(
                (judge.anchors.get(task) or {}).get("checks"))
            _ct = _CT.from_observed(_skel, _obs, _exp)
        except Exception as _ce:      # noqa: BLE001 — 对比坏不掀 trial
            _ct = {"error": repr(_ce)}
        if _fused:
            return {"success": suc,                    "in_score": _cur,
                    "partial": _cur,
                    "baseline_in": base,
                    "baseline_ho": _base_ho, "held_out": None,
                    "mode": _mode, "contrast": _ct,
                    "reason": ("A3小Δ熔断：|Δ_in|=%.4f<spread，不烧peer预算"
                               % (_d_in,)), "activated": True, "mechanism_ran": True}
        return {"success": suc,
                "in_score": (1.0 if suc is True else
                             (0.0 if suc is False else None)),
                "partial": (1.0 if suc is True else
                            (0.0 if suc is False else None)),
                "baseline_in": base,
                "baseline_ho": _base_ho,
                # ★ R299 · trial 成功码喂 peer（成功才传；失败/None 码
                #   不污染 peer——fail-closed feeding）。
                "held_out": _peer_held_out_code(
                    judge, llm, task, max_tokens=max_tokens,
                    hint_code=(code if suc is True else None)),
                "mode": _mode, "activated": True, "contrast": _ct}
    skel = obs_skeleton(judge.anchors, task)
    prompt = build_observed_prompt(task, skel, "") + "\n" + patch
    with task_measurement_context(task):
        with measurement_role("probe"):
            r = llm.complete(prompt, max_tokens=max_tokens)
    if not r.ok:
        return {"success": None, "in_score": None, "baseline_in": None,
                "held_out": None, "mode": _mode, "partial": None, "activated": False,
                "mechanism_ran": False}
    obs = parse_llm_observed(r.text or "", skel)
    if obs is None:
        return {"success": None, "in_score": None, "baseline_in": None,
                "held_out": None, "mode": _mode, "partial": None, "activated": False,
                "mechanism_ran": False}
    suc = judge.evaluate(task, "dev",
                         observed={"observed": obs,
                                   "★_executed": True}).success
    # ★ R299-b · 基线用前置快照（report 路同修，自己不当基线）。
    base = _base_in
    _cur = (1.0 if suc is True else (0.0 if suc is False else None))
    # ★ A3 · 小Δ熔断（report 路）：判据与 code 路同一函数，口径唯一。
    _fused, _d_in = _small_delta_fused(_cur, base)
    if _fused:
        return {"success": suc,                    "in_score": _cur,
                    "partial": _cur,
                "baseline_in": base,
                "baseline_ho": _base_ho, "held_out": None, "mode": _mode,
                "reason": ("A3小Δ熔断：|Δ_in|=%.4f<spread，不烧peer预算"
                           % (_d_in,)), "activated": True}
    # ★ R295-Task3 · peer 切写码独立评估（老报数 peer 退役：patch 建议文本
    #   进 peer prompt 是 R294 实证的错配通道，peer 也写码真跑）。
    _ho = _peer_held_out_code(judge, llm, task, max_tokens=max_tokens)
    return {"success": suc,
            "in_score": (1.0 if suc is True else
                         (0.0 if suc is False else None)),
            "partial": (1.0 if suc is True else
                        (0.0 if suc is False else None)),
            "baseline_in": base,
            "baseline_ho": _base_ho,
            "held_out": _ho, "mode": _mode, "activated": True, "mechanism_ran": True}


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
    # ★ B3 · 从 live 提案账读簇（给了就不读 failure_sig 表）
    ap.add_argument("--from-proposals", default="",
                    help="读 var/evo_proposals.jsonl 的未映射簇（B3）")
    args = ap.parse_args()
    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)
    db = args.db or os.path.join(root, "var", "dwc_prod.sqlite")
    rules = args.rules or os.path.join(root, "config", "anchors",
                                       "rules.json")
    from dwc.llm.client import LLMClient
    from dwc.organs.judge import Judge
    # ★ R299-b2 · 人跑入口同 cron：基线落盘（var 下，仓库根为锚）。
    judge = Judge(store_path=os.path.join(
        root, "var", "dwc_task_scores.jsonl"),
        evidence_path=os.path.join(root, "var", "dwc_evidence.jsonl"))
    llm = LLMClient()
    mu = LLMMutator(llm=lambda p: (
        lambda r: r.text if r.ok else (_ for _ in ()).throw(
            RuntimeError(r.error)))(llm.complete(p, max_tokens=800)))
    ctx = "anchors tasks: %s" % (sorted(judge.anchors.keys())[:12],)

    # ★ B3 · 外部簇（live 提案账）—— 给了就不读库
    _clusters = None
    _ep = None
    _prop_path = args.from_proposals
    if _prop_path:
        from dwc.harness import evo_proposals as _ep_mod
        _ep = _ep_mod
        _items = _ep.pending_unmapped(_prop_path)
        _clusters = _ep.group_by_key(_items)
        print("from-proposals: %d 簇 / %d 签名 (path=%s)"
              % (len(_clusters), len(_items), _prop_path))
        if not _clusters:
            print("无待起草簇 —— 不跑本轮")
            return 0

    rep = run_round(db, Evolver(), mu, ctx,
                    trial_fn=lambda t, pa, code=None: _real_trial(
                        judge, llm, t, pa, code=code),
                    apply=args.apply, rules_path=rules,
                    backup_dir=args.backup_dir or None,
                    fn_of=lambda r: args.fn,
                    task_of=lambda r: args.task,
                    max_clusters=args.max_clusters,
                    clusters=_clusters,
                    want_code_of=lambda t: (
                        judge.anchors.get(t, {}) or {}).get(
                        "category", "") == "code_repair",
                    judge=judge)
    print(json.dumps(rep, ensure_ascii=False, indent=1)[:2000])
    # ★ B3 · 已落地的簇标记消费（未落地的下轮重试 —— 不静默丢弃）
    if _prop_path and _clusters and _ep is not None:
        _landed = [r["key"] for r in (rep.get("results") or [])
                   if r.get("landed") is True and r.get("key")]
        if _landed:
            _ep.mark_consumed(_prop_path, _landed)
        print("consumed: %d/%d 簇已落地并标记"
              % (len(_landed), len(_clusters)))
    # ★ R审计-P2 · 参数进化驱动（进化轮结束也判一次: trial 期间的
    #   read 截断观测同样算压力信号；无信号/防抖内 ⇒ 台账跳过，不打扰）
    try:
        from dwc.organs.evo_driver import EvoParamDriver as _ParamDrvR
        _pdr = _ParamDrvR()
        print("param driver: %s" % json.dumps(
            _pdr.run("context_mgmt"), ensure_ascii=False))
    except Exception as _pe2:            # noqa: BLE001 — 驱动坏不拦轮次
        print("param driver 未挂: %s" % (_pe2,))
    # ★ R审计-P2 · P0-4 · MemoryKernel.dream 接线（失败聚簇→技能候选）
    #   ★ 与 Core.dream（树级 V* 反刍）分工不同: 本处是**签名聚簇归纳**,
    #     把 N 条同类失败凝成一条"以后怎么避免"的技能候选（D6/D7 的落点）。
    #   ★ 只读: dream 不写节点、不改 access（沙箱语义）；采纳归 evolver。
    try:
        from dwc.organs.memory import MemoryKernel as _MK
        _mk = _MK(db)
        _cl: dict = {}
        for _r in _mk._conn.execute("SELECT c,q,m FROM failure_sig"):
            _k = (_r["c"], _r["q"], _r["m"])
            _cl[_k] = _cl.get(_k, 0) + 1
        _cands = []
        for (_c, _q, _m) in _cl:
            _d = _mk.dream(_c, _q, _m)
            if _d.get("eligible"):
                _cands.append({"c": _c, "q": _q, "m": _m,
                               "n_members": _d.get("n_members"),
                               "skill": _d.get("candidate_skill")})
        _mk.close()
        print("dream: %d 簇, %d 条技能候选" % (len(_cl), len(_cands)))
        if _cands:
            print(json.dumps(_cands[:5], ensure_ascii=False, indent=1)[:1200])
    except Exception as _de:            # noqa: BLE001 — dream 坏不拦轮次
        print("dream 未跑: %s: %s" % (type(_de).__name__, _de))
    return 0


if __name__ == "__main__":
    sys.exit(main())
