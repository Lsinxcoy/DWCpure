# -*- coding: utf-8 -*-
"""R82 · 生产多轮试运行（四机制长程演化证据 · 不动 src）。

★★★ 这个脚本验证什么
  R76-R81 落的四机制（EL 采样 / δ 任务源排序 / direction_hint / Dreaming）
  在**真实生产链**（DWC 构造播种 → 多 term → C3' 判分积累 → 树观测回填 →
  dream）下的**演化轨迹** —— 单测/集成各测了静态快照, 本脚本看长程活链:
  · el_selected 的 status/generation/index 随观测积累的推进
  · δ 任务级排序: 注入持续失败任务后其 δ 稀有度上升、排序上浮
  · direction_hint 的 stalled→LATERAL 出现
  · DreamReport 的 V 随树观测增长的轨迹
★ 判分走 judge.evaluate（C3' 记录点 — run_term 内的 score 不进 C3'）;
  树观测由本脚本手动回填（run_term 的执行→回填自动化留后续轮）。
★ 执行器=按 golden 造观测（对/错可控）—— 证明的是**链路活**, 不是能力。
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.core import DWC                                    # noqa: E402
from dwc.organs.actor import Receipt                        # noqa: E402
from dwc.organs.judge import TaskScoreStore                 # noqa: E402

#: 注入: 该任务每次判分都给错观测（δ 稀有度追踪的靶）; CLI 可覆盖:
#:   python trial_run.py --noise code_fix_004   指定注入
#:   python trial_run.py --noise none           无噪声（EL 阈值效应验证轮 R83）
_NO = sys.argv[sys.argv.index("--noise") + 1] if "--noise" in sys.argv \
    else "code_fix_004"
NOISE_TASKS = set() if _NO == "none" else {x for x in _NO.split(",") if x}
#: --terms N: 长程轮数（默认 6; 长程运行传 20+）; --m1: Dreaming 带 M>1 网格（R86 首跑）
_TERMS = int(sys.argv[sys.argv.index("--terms") + 1]) if "--terms" in sys.argv \
    else 6
_M1 = "--m1" in sys.argv
N_TERMS = _TERMS
PER_TERM = 3          # 每 term 判分任务数（轮询）—— δ 组内样本加速积累


def _obs_for(anchors, tid: str) -> dict:
    """按 golden checks 造 observed: noise 任务给错值, 其他对值。

    ★ R82 实测口径: judge 比对**数字** args/value（字符串 args 判 ✗）——
      golden 的 args/expected 是字符串, 这里数字化（isdigit 才转）。
    """
    obs: dict = {}
    for c in anchors[tid].get("checks", []):
        if "fn" not in c:
            continue                       # kw 类（reasoning）跳过 — 本脚本只判 behavior
        fn = c["fn"]

        def _coerce(x):
            # R83: literal_eval 统一覆盖 数字/布尔/列表/字符串字面量
            #   （002 的 args="[1,2,3]" 列表 + expected="2.0" 浮点是 R82 口径盲区）
            import ast
            try:
                return ast.literal_eval(str(x))
            except (ValueError, SyntaxError):
                return x
        arg, val = _coerce(c["args"]), _coerce(c["expected"])
        if tid in NOISE_TASKS:
            val = val + 1000 if isinstance(val, int) else str(val) + "_wrong"
        obs.setdefault(fn, []).append([arg, val])
    return obs


def _mk_exec(anchors):
    """★ R84 换线: executor 回执带 detail[observed]（judge 契约）——
    step 尾自动 judge.evaluate + 树回填（不再是空 Receipt）。"""
    def _exec(task):
        tid = task.get("task_id", "")
        obs = _obs_for(anchors, tid) if tid in anchors else None
        return Receipt(ok=True,
                       detail=({"observed": obs} if obs else {}),
                       verified=True)
    return _exec


def main() -> int:
    d = DWC(3, 50, executor=None)
    # 隔离生产 store（试运行数据独立可归档）
    d.judge.store = TaskScoreStore(dw_version="trial-r82")
    dev_ids = sorted(
        t for t in d.judge.anchors if not t.startswith("_")
        and d.judge.anchors[t].get("verifier_kind") == "behavior")
    d.executor = _mk_exec(d.judge.anchors)   # R84: 换线 executor
    if _M1:
        # ★ R89 · 多分支世界（M>1 差异化前提, R88 留档销账）:
        #   R88 的 dev 单树 10 节点全部很快揭示 ⇒ 四变体 V 恒等;
        #   这里**构造**多分支 t2（root→a/b/c; a 带成功 score、b 带失败 score、
        #   c 未观测）—— **验证变体区分机制的形状, 非能力声明**（口径同 R82:
        #   人造观测证明链路通, 不冒充真实任务成绩）。
        #   R89 修正（首版恒等的根因, 实测抓到）: ①t2 节点名不命中 dmap
        #   （δ 是 judge 任务域）⇒ π0 与 w=0 键全 0 同序 ②树小 K₂ 覆盖全揭示
        #   ⇒ 揭示集与选择无关 ⇒ V 恒等。修法: **节点命名=judge task_id**
        #   （dmap 命中, R77 node_id 同域设计的直接复用）+ K₂=4 截断
        #   （揭示集因选择而异 ⇒ max_s 分化 ⇒ V 真分化）。
        wm = d.world_model
        wm.seed("t2", "r")
        for br in ("code_fix_004", "code_fix_001", "code_fix_002"):
            wm.expand("t2", "root", node_id=br, action="branch-" + br,
                      provenance="observed")
        wm.expand("t2", "code_fix_004", node_id="code_fix_006",
                  action="deep-006", provenance="observed")
        # score 按任务史: 001 成功(1.0), 002/004 失败(0.0); 006 未观测
        wm.record_observation("t2", "code_fix_001", 1.0, True)
        wm.record_observation("t2", "code_fix_004", 0.0, False)
        wm.record_observation("t2", "code_fix_002", 0.0, False)
    print("behavior 任务 %d 条（reasoning kw 类跳过判分）, 注入噪声: %s"
          % (len(dev_ids), sorted(NOISE_TASKS)))

    records = []
    for term in range(N_TERMS):
        # ① run_term 全链（六步/判分/任务源 el_selected/快照进 ℋ）
        rep = d.run_term("T%d" % term, n_steps=2)
        src = rep.next_task_source or {}
        el = src.get("el_selected")
        # ② 执行 PER_TERM 个任务（轮询）—— **R84 换线: step 尾自动判分+回填**
        #   （C3' 积累 + 树观测全自动, 不再手动 evaluate/record_observation）
        judged = []
        for i in range(PER_TERM):
            tid = dev_ids[(term * PER_TERM + i) % len(dev_ids)]
            out = d.step({"task_id": tid, "kind": "dev"})
            j = out["judgement"]
            assert j is not None, "★ R84 契约: 带 observed 应自动判分 (%s)" % tid
            judged.append((tid, bool(j["success"])))
        # ④ Dreaming（--m1 ⇒ R86 M>1 网格: π0 + w_delta∈{0,0.5} + no-reveal 变体）
        from dwc.organs.replay import PolicySpec
        variants = [PolicySpec(w_delta=0.0), PolicySpec(w_delta=0.5),
                    PolicySpec(prefer_revealable=False)] if _M1 else None
        dr = d.dream(k2_max=4 if _M1 else 8, policy_variants=variants)
        # ⑤ 当前 δ 排序快照（top3 任务）
        dmap = d._task_deltas()
        top3 = sorted(dmap.items(), key=lambda kv: -kv[1])[:3]
        rec = {
            "term": term,
            "el_selected": (None if el is None else {
                "status": el["status"], "generation": el["generation"],
                "index": el["index"], "pass_rate": el["pass_rate"],
                "picked": el["picked"]["node"],
                "hint": el["direction_hint"]}),
            "judged": judged,
            "n_obs": d.world_model.observed_count(),
            "pool_rate": d.world_model.observed_rate(),
            "delta_top3": [(t, round(x, 4)) for t, x in top3],
            "dream": {"V": dr.v_by_version[dr.m_star], "m_star": dr.m_star,
                      "k2_max": dr.k2_max, "v_by": dr.v_by_version,
                      "per_world_kn": [(t, k, n) for t, V, k, n
                                       in dr.per_world]},
        }
        records.append(rec)
        print("T%d: el=%s judged=%s pool=%.2f top3=%s dream.V=%.3f" % (
            term, (el or {}).get("status", "-"),
            " ".join("%s:%s" % (t[-3:], "✓" if ok else "✗") for t, ok in judged),
            rec["pool_rate"] or 0.0,
            " ".join("%s(%.2f)" % (t[-3:], x) for t, x in top3),
            rec["dream"]["V"]))

    tag = "clean" if not NOISE_TASKS else "noise-" +         "-".join(sorted(NOISE_TASKS))
    tag += "_t%d%s" % (N_TERMS, "_m1" if _M1 else "")
    out = os.path.join(ROOT, "docs", "trial_report_r88_%s.json" % tag)
    with open(out, "w", encoding="utf-8") as f:
        json.dump({
            "round": "R82 trial",
            "n_terms": N_TERMS, "per_term": PER_TERM,
            "noise_tasks": sorted(NOISE_TASKS),
            "records": records,
        }, f, ensure_ascii=False, indent=1)
    print("报告: %s (%d B)" % (out, os.path.getsize(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
