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


def run_round(db_path, evolver, mu, context, trial_fn, apply, rules_path,
              backup_dir=None, fn_of=None, task_of=None, max_clusters=3,
              want_code_of=None, mech_log=None, trace_log=None,
              ledger_path=None, resume=True, ledger_date=None,
              max_attempts=3):
    """★ 一轮收尾：聚簇→起草→试跑→（可选）落盘。返回可审计报告。

    ★ R295-Task3 · want_code_of(task)→bool（code_repair 写码真执行分流；
      None=不求码，老路零变）。trial_fn 三参契约 (task, patch, code=None)。
    ★ R310-⑤ · max_attempts（默认 3）：单簇 trial 非 True 重试预算。
    ★ A6 · peak-picking 禁令：返回体只装当轮终态（results 当轮行＋ledger
      追加行），禁报历史 peak（companion HarnessX 反例：报 peak 73.8% 而
      终态 49.5%）。调用方要趋势自己读 ledger 全史，本函数不代取最优。
    """
    fn_of = fn_of or (lambda r: "")
    task_of = task_of or (lambda r: "")
    want_code_of = want_code_of or (lambda t: False)
    clusters = collect_unmapped(db_path, evolver, fn_of, task_of)
    results = []
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
                    if isinstance(_old, dict):
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
                p = mu.propose_from_cluster(cl["sigs"], context,
                                            want_code=want_code_of(_task),
                                            learned_hint=_hint)
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
            t = trial_fn(cl["sigs"][0].get("task", ""), p.patch, p.code)
            item["trial"] = t                  # ★ 原样存（bool/dict 照旧）
            # ★ R290-P1 · 归一：dict 取 success，bool/None 照旧（旧契约不断）。
            _ok = (t.get("success") if isinstance(t, dict) else t)
            if _ok is True or _att >= max(1, max_attempts):
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
            # ★ R287-C · adopt 门（Evolver.accept）：trial 布尔无分数 ⇒
            #   accept 缺 baseline/current 会判 not_evaluated/blocked。
            #   诚实处置：先判，有分数走门（第五态→_land_adopted 落）；
            #   无分数走 legacy 直落但标记 decision（门没判≠门过了 ——
            #   收紧点：trial_fn 带分数之日 legacy 分支删除，见 ★TODO）。
            try:
                # ★ R300-A · 传 mode（code 路走知识分支；缺省 report 老路）。
                _ad = evolver.accept(
                    p, baseline=_base, current=_cur,
                    mode=((t.get("mode") or "report")
                          if isinstance(t, dict) else "report"))
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
                # ★ R291-P4 Task 2 · 门判过⇒置第五态再落地（_land_adopted
                #   前置要 p.state；置态=记录门判结果，不编造）。
                p.state = "adopted_not_implemented"
                # ★ C3 · provenance：admission 轮用 ledger_date（轮日期口径）。
                item["backup"] = evolver._land_adopted(
                    p, admission_round=ledger_date)
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
            "not_wired": [], "mech_advise": _mech_advise}
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
        # ★ R299-b · 基线用前置快照（判后取=自己，d_in 恒 0 死门已除）。
        base = _base_in
        _cur = (1.0 if suc is True else (0.0 if suc is False else None))
        # ★ A3 · 小Δ熔断（code 路）：|Δ_in|<spread ⇒ 跳过 peer 验证，
        #   省出码+沙箱 LLM 预算；held_out=None ⇒ 门仍 blocked（门语义零改）。
        _fused, _d_in = _small_delta_fused(_cur, base)
        if _fused:
            return {"success": suc, "in_score": _cur,
                    "baseline_in": base,
                    "baseline_ho": _base_ho, "held_out": None,
                    "mode": _mode,
                    "reason": ("A3小Δ熔断：|Δ_in|=%.4f<spread，不烧peer预算"
                               % (_d_in,))}
        return {"success": suc,
                "in_score": (1.0 if suc is True else
                             (0.0 if suc is False else None)),
                "baseline_in": base,
                "baseline_ho": _base_ho,
                # ★ R299 · trial 成功码喂 peer（成功才传；失败/None 码
                #   不污染 peer——fail-closed feeding）。
                "held_out": _peer_held_out_code(
                    judge, llm, task, max_tokens=max_tokens,
                    hint_code=(code if suc is True else None)),
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
    # ★ R299-b · 基线用前置快照（report 路同修，自己不当基线）。
    base = _base_in
    _cur = (1.0 if suc is True else (0.0 if suc is False else None))
    # ★ A3 · 小Δ熔断（report 路）：判据与 code 路同一函数，口径唯一。
    _fused, _d_in = _small_delta_fused(_cur, base)
    if _fused:
        return {"success": suc, "in_score": _cur,
                "baseline_in": base,
                "baseline_ho": _base_ho, "held_out": None, "mode": _mode,
                "reason": ("A3小Δ熔断：|Δ_in|=%.4f<spread，不烧peer预算"
                           % (_d_in,))}
    # ★ R295-Task3 · peer 切写码独立评估（老报数 peer 退役：patch 建议文本
    #   进 peer prompt 是 R294 实证的错配通道，peer 也写码真跑）。
    _ho = _peer_held_out_code(judge, llm, task, max_tokens=max_tokens)
    return {"success": suc,
            "in_score": (1.0 if suc is True else
                         (0.0 if suc is False else None)),
            "baseline_in": base,
            "baseline_ho": _base_ho,
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
    # ★ R299-b2 · 人跑入口同 cron：基线落盘（var 下，仓库根为锚）。
    judge = Judge(store_path=os.path.join(
        root, "var", "dwc_task_scores.jsonl"),
        evidence_path=os.path.join(root, "var", "dwc_evidence.jsonl"))
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
