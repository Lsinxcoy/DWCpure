# -*- coding: utf-8 -*-
"""★★★ R279 · 进化收尾 cron 包装（no_agent 脚本作业用）。

★ 落地策略（R438 改）：由 `config/evolution.yaml` 的 `auto_apply` 决定。
  关 ⇒ 只报告；开 ⇒ 试跑通过 + 门判 adopted 才写 rules.json（带备份）。
  单轮落地条数由 `auto_apply_max_per_round` 限（默认 1）。
★ 回滚：`--rollback <key>` 删单键；`--restore <backup.json>` 整文件还原。
★ 路径：代码经 .dwc_repo 指针找仓库；数据根与 agent 同源（仓库 var/）。
★ CRON RUNS THE COPY: 同步 %LOCALAPPDATA%/hermes/scripts/ 后生效。

cron: 每日 04:00（nightbench 02:30 跑完后顺手收尾，错开 03:00 备份）。
"""
from __future__ import annotations

import json
import os
import sys
import time


def _prod_root() -> str:
    """生产数据根 —— 必须与 **agent 写库的根**一致。

    ★★★ R437 · 旧实现无条件返回 `~/.dwc`，而 agent 用 `find_root()/var`。
      实测：`~/.dwc/var/dwc_prod.sqlite` 最后写入 **10-17 09:11**，
      只有 68 条 failure_sig；仓库 `var/` 的库 **10-23 08:49**，2053 条。
      ⇒ 每日进化轮读的是 6 天前的库，所以恒 `n_clusters: 0`。

      现在：仓库根有库就用仓库根（与 agent 同源），没有才回退旧 .dwc。
    """
    root = _code_root()
    if os.path.exists(os.path.join(root, "var", "dwc_prod.sqlite")):
        return root
    home = os.path.expanduser("~")
    p = os.path.join(home, ".dwc")
    if os.path.isdir(p):
        return p
    raise RuntimeError("找不到生产库：%s/var 与 %s 都没有 dwc_prod.sqlite"
                       % (root, p))


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


def _rollback_key(key: str, rules_path: str, backup_dir: str) -> dict:
    """★ R438 · 删掉一条已落地规则（单键回滚，不动其它键）。

    ★ 为什么不复用 `evolver.rollback_rule`：那个函数的备份布局是
      `backup_root/latest → <stamp>/anchors/rules.json`（演练脚本用），
      与本轮 `var/backups/rules_<ts>.json` 不同源。两套布局混用会
      在回滚时读到旧快照 ⇒ 把别人刚落的一起冲掉。
    ★ 原子写：tmp + os.replace，避免半截 JSON。
    """
    import json as _j
    import os as _os
    import shutil as _sh
    import time as _t
    if not _os.path.isfile(rules_path):
        return {"outcome": "not_found", "why": "rules.json 不存在",
                "path": rules_path}
    with open(rules_path, encoding="utf-8") as _f:
        data = _j.load(_f)
    learned = data.get("learned") or {}
    if key not in learned:
        return {"outcome": "not_found", "key": key, "n_learned": len(learned)}
    _os.makedirs(backup_dir, exist_ok=True)
    bak = _os.path.join(backup_dir, "rules_before_rollback_%s.json"
                        % _t.strftime("%Y%m%d_%H%M%S"))
    _sh.copy2(rules_path, bak)
    learned.pop(key)
    data["learned"] = learned
    tmp = rules_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as _f:
        _j.dump(data, _f, ensure_ascii=False, indent=1)
    _os.replace(tmp, rules_path)
    return {"outcome": "rolled_back", "key": key,
            "n_learned": len(learned), "backup": bak}


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
    # ★ R438 · 回滚与还原（落地后的后悔药）
    _p.add_argument("--rollback", default=None,
                    help="删掉一条已落地规则（key 形如 c:q:fn）")
    _p.add_argument("--restore", default=None,
                    help="用备份文件整份还原 rules.json")
    _p.add_argument("--report-only", action="store_true",
                    help="强制只报告（覆盖 evolution.yaml 的 auto_apply）")
    _a = _p.parse_args()
    sys.path.insert(0, os.path.join(_code_root(), "scripts"))
    sys.path.insert(0, os.path.join(_code_root(), "src"))
    import dwc_evo_round as EVO
    from dwc.llm.client import LLMClient
    from dwc.organs.evolver import Evolver, LLMMutator, Mutator
    from dwc.organs.judge import Judge
    from dwc.organs.predictor import OutcomePredictor
    from dwc.foundation.dial_config import load_evolution
    prod = _prod_root()
    rules_path = os.path.join(prod, "config", "anchors", "rules.json")

    # ★ R454 · 先消费难度阶梯的 L3 请求：
    #   agent 饱和到 L3 时**只写请求不起草**（tick 里不能调 LLM），
    #   起草在本入口做 —— 这里本来就有 LLM 预算。
    _esc = os.path.join(prod, "var", "supply_escalate.json")
    if os.path.isfile(_esc):
        import subprocess as _sp
        try:
            _r = _sp.run(
                [sys.executable,
                 os.path.join(_code_root(), "scripts", "supply_l3.py")],
                capture_output=True, text=True, timeout=900)
            print(json.dumps({"supply_l3_rc": _r.returncode,
                              "supply_l3_out": (_r.stdout or "").strip()[-400:]},
                             ensure_ascii=False), flush=True)
        except Exception as _e:       # noqa: BLE001 — 供给失败不许挡住进化轮
            print(json.dumps({"supply_l3_error": repr(_e)},
                             ensure_ascii=False), flush=True)

    # ★ R438 · 回滚 / 还原：先处理，不必跑轮
    if _a.rollback or _a.restore:
        if _a.restore:
            import shutil as _sh
            if not os.path.isfile(_a.restore):
                print(json.dumps({"error": "备份不存在: %s" % _a.restore},
                                 ensure_ascii=False))
                return 2
            _sh.copy2(_a.restore, rules_path)
            print(json.dumps({"restored": _a.restore, "to": rules_path},
                             ensure_ascii=False))
            return 0
        _rb = _rollback_key(_a.rollback, rules_path,
                            os.path.join(prod, "var", "backups"))
        print(json.dumps(_rb, ensure_ascii=False))
        return 0 if _rb.get("outcome") == "rolled_back" else 2

    # ★ R438 · 启动即加载已学规则（改前 `ensure_loaded` 全仓库零调用
    #   ⇒ 即使 rules.json 有内容，新进程也读不到 = 学了等于没学）
    _n_loaded = Mutator.ensure_loaded()
    _cfg = load_evolution()
    _apply = bool(_cfg["auto_apply"]) and not _a.report_only
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
        apply=_apply,
        max_land=_cfg["auto_apply_max_per_round"],
        rules_path=rules_path,
        # ★★★ R437 · 任务名/函数名不再由这里硬编码 —— `collect_unmapped`
        #   从 memory_node.payload 读真实 task（表本身没有 task 列），
        #   fn 从锚点 checks 反查。这里只保留兜底（读不到时为空）。
        fn_of=lambda r: "", task_of=lambda r: "",
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
        resume=not _a.no_resume,
        judge=judge)
    # ★★★ R437 · 行为车道落盘：这些失败不进 evolver（没有代码可修），
    #   但也**不许静默丢** —— 落队列，交给提示词/技能/工具反馈那条车道。
    try:
        _beh = rep.get("behavior_sigs") or []
        if _beh:
            import time as _tm
            _q = os.path.join(prod, "var", "behavior_queue.jsonl")
            _seen = set()
            try:
                with open(_q, encoding="utf-8") as _fq:
                    for _ln in _fq:
                        try:
                            _seen.add(json.loads(_ln).get("key"))
                        except Exception:
                            pass
            except OSError:
                pass
            _n_new = 0
            with open(_q, "a", encoding="utf-8") as _fq:
                for _s in _beh:
                    _k = "%s:%s:%s" % (_s.get("task"), _s.get("c"), _s.get("q"))
                    if _k in _seen:
                        continue
                    _seen.add(_k)
                    _fq.write(json.dumps({"key": _k, "sig": _s,
                                          "ts": _tm.time()},
                                         ensure_ascii=False) + "\n")
                    _n_new += 1
            rep["behavior_queued"] = _n_new
            rep["behavior_queue_total"] = len(_seen)
    except Exception as _e:  # noqa: BLE001 — 队列坏不掀轮
        rep["behavior_queue_error"] = repr(_e)
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
            # ★★★ R437 · 表里没有 task 列（旧 SQL 恒报 no such column）——
            #   真实任务名在 memory_node.payload 里。
            import sqlite3 as _sq
            _con = _sq.connect(db)
            _tasks = [r[0] for r in _con.execute(
                "SELECT DISTINCT json_extract(n.payload,'$.task') AS task "
                "FROM failure_sig f JOIN memory_node n "
                "  ON n.node_id = f.node_id "
                "WHERE json_extract(n.payload,'$.task') IS NOT NULL"
            ).fetchall() if r[0]]
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
    # ★ R438 · 记忆维度：教训晋升（改前 promote_lessons 生产零调用
    #   ⇒ 1205 条教训永远停在 short 层，且没有注入点）
    try:
        from dwc.agent_quality import promote_lessons
        rep["lessons_promoted"] = promote_lessons()
    except Exception as _e:  # noqa: BLE001 — 晋升坏不掀轮（留痕）
        rep["lessons_promoted"] = {"error": repr(_e)}
    # ★ R438 · prompt 维度：按排程跑一次「已学规则→候选→A/B→晋升」
    #   为什么按 weekday：A/B 要 stable/candidate 各跑一遍子集（1-4h），
    #   每天跑会和当日进化轮抢 agent 并发。
    try:
        _pwd = int(_cfg.get("prompt_evolve_weekday", -1))
        if _pwd >= 0 and time.localtime().tm_wday == _pwd:
            from dwc_prompt_evolve import evolve as _prompt_evolve
            rep["prompt_evolve"] = _prompt_evolve(promote=True)
        else:
            rep["prompt_evolve"] = {"outcome": "not_scheduled",
                                    "weekday": int(time.localtime().tm_wday),
                                    "configured": _pwd}
    except Exception as _e:  # noqa: BLE001 — 提示词轮坏不掀当日进化轮
        rep["prompt_evolve"] = {"error": repr(_e)}
    # ★ R438 · meta_evolution：按压力调整**进化自己的旋钮**（带 3 天冷却）
    try:
        from dwc.organs import meta_policy as _MP
        _st_p = os.path.join(prod, "var", "meta_evolution.json")
        _last = 0.0
        try:
            with open(_st_p, encoding="utf-8") as _f:
                _last = float(json.load(_f).get("ts", 0) or 0)
        except (OSError, ValueError):
            _last = 0.0
        _adj = _MP.propose(rep, _cfg, last_ts=_last)
        if _adj:
            _MP.apply(_adj["key"], _adj["new"],
                      path=os.path.join(prod, "config", "evolution.yaml"))
            _adj["ts"] = time.time()
            with open(_st_p, "w", encoding="utf-8") as _f:
                json.dump(_adj, _f, ensure_ascii=False)
            rep["meta_evolution"] = _adj
        else:
            rep["meta_evolution"] = {"outcome": "no_pressure"}
    except Exception as _e:  # noqa: BLE001 — 元进化坏不掀当日轮（留痕）
        rep["meta_evolution"] = {"error": repr(_e)}
    # ★ R438 · 统一进化台账（每条候选一行：落没落、为什么、备份在哪）
    rep["auto_apply"] = _apply
    rep["rules_loaded"] = _n_loaded
    try:
        import time as _tm2
        _led = os.path.join(prod, "var", "evolution_ledger.jsonl")
        _n_led = 0
        with open(_led, "a", encoding="utf-8") as _f:
            for _it in rep.get("results", []):
                _f.write(json.dumps({
                    "ts": _tm2.time(),
                    "component": "control_flow",
                    "key": _it.get("key"),
                    "decision": _it.get("adopt"),
                    "landed": bool(_it.get("landed")),
                    "reason": _it.get("reason") or "",
                    "backup": _it.get("backup"),
                    "trial": _it.get("trial"),
                }, ensure_ascii=False, default=str) + "\n")
                _n_led += 1
        rep["ledger"] = {"path": _led, "n": _n_led}
    except Exception as _e:  # noqa: BLE001 — 台账坏不掀轮（留痕）
        rep["ledger_error"] = repr(_e)
    # ★ R438-j · 报告必须让人看见"这轮到底做了什么"。
    #   改前 [:2000] 截断，behavior_sigs（2093 条）把后面的
    #   lessons_promoted / prompt_evolve / meta_evolution 全挤出视野 ⇒
    #   cron 输出看起来只有一堆签名，等于没报告。
    _slim = {k: v for k, v in rep.items() if k != "behavior_sigs"}
    if isinstance(_slim.get("results"), list):
        _slim["results"] = [{k: v for k, v in r.items() if k != "sigs"}
                            for r in _slim["results"]]
    if isinstance(_slim.get("behavior_sigs"), list):
        _slim["behavior_sigs"] = "%d 条（已省略）" % len(rep["behavior_sigs"])
    print(json.dumps(_slim, ensure_ascii=False, indent=1)[:6000], flush=True)
    return 0


def _bootstrap_interpreter() -> None:
    """★ R438-j · cron 解释器自举（Hermes 自带 python 没有 pyyaml）。

    现场：R438 新增的 `load_evolution` 在 import 期 `import yaml`，
          而 cron 用 `%LOCALAPPDATA%/hermes/tools/python-3.x/python.exe` 跑脚本，
          该解释器无 PyYAML ⇒ ModuleNotFoundError ⇒ 整轮进化不跑。
    做法：缺 yaml 就换到 Hermes venv 的解释器重跑本文件（带 DWC_REEXEC 防环）。
          Windows 上不用 os.execv —— 含空格路径会被拆断（R428 教训）。
    """
    try:
        import yaml  # noqa: F401
        return
    except ImportError:
        pass
    if os.environ.get("DWC_REEXEC") == "1":
        raise SystemExit("缺少 PyYAML，自举后仍缺（DWC_REEXEC 已设，避免死循环）")
    _cands = [
        os.path.expandvars(r"%LOCALAPPDATA%\hermes\hermes-agent\venv\Scripts\python.exe"),
        os.path.expanduser("~/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"),
    ]
    for _c in _cands:
        _c = os.path.abspath(_c)
        if not os.path.isfile(_c):
            continue
        if os.path.realpath(_c) == os.path.realpath(sys.executable):
            continue
        import subprocess
        _env = dict(os.environ, DWC_REEXEC="1")
        raise SystemExit(subprocess.call(
            [_c, os.path.abspath(__file__)] + sys.argv[1:], env=_env))


if __name__ == "__main__":
    _bootstrap_interpreter()
    sys.exit(main())
