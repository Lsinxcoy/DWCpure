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

#: 注入: 该任务每次判分都给错观测（δ 稀有度追踪的靶）
NOISE_TASKS = {"code_fix_004"}
N_TERMS = 6
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
            s = str(x)
            if s.lstrip("-").isdigit():
                return int(s)
            if s in ("True", "False"):
                return s == "True"
            if len(s) >= 2 and s[0] == s[-1] == "'":
                return s[1:-1]
            return s
        arg, val = _coerce(c["args"]), _coerce(c["expected"])
        if tid in NOISE_TASKS:
            val = val + 1000 if isinstance(val, int) else str(val) + "_wrong"
        obs.setdefault(fn, []).append([arg, val])
    return obs


def _exec(task):
    """step 链的执行器（Receipt 形态）—— 试运行里执行=空转, 判分在下方手动。"""
    return Receipt(ok=True, detail={}, verified=True)


def main() -> int:
    d = DWC(3, 50, executor=_exec)
    # 隔离生产 store（试运行数据独立可归档）
    d.judge.store = TaskScoreStore(dw_version="trial-r82")
    dev_ids = sorted(
        t for t in d.judge.anchors if not t.startswith("_")
        and d.judge.anchors[t].get("verifier_kind") == "behavior")
    print("behavior 任务 %d 条（reasoning kw 类跳过判分）, 注入噪声: %s"
          % (len(dev_ids), sorted(NOISE_TASKS)))

    records = []
    for term in range(N_TERMS):
        # ① run_term 全链（六步/判分/任务源 el_selected/快照进 ℋ）
        rep = d.run_term("T%d" % term, n_steps=2)
        src = rep.next_task_source or {}
        el = src.get("el_selected")
        # ② 手动判分 PER_TERM 个任务（轮询）—— C3' 积累（δ 数据源）
        judged = []
        for i in range(PER_TERM):
            tid = dev_ids[(term * PER_TERM + i) % len(dev_ids)]
            v = d.judge.evaluate(tid, observed=_obs_for(d.judge.anchors, tid))
            judged.append((tid, bool(v.success)))
            # ③ 树观测回填（EL 速率口的数据源）
            # ★ W5 纪律: 已带真值 score 的节点不覆盖（provenance 单向）——
            #   首个判分定观测; 后续轮回判分照进 C3'（δ 积累）但树不重填
            node = d.world_model.trees["dev"].nodes.get(tid)
            if node is not None and node.score is None:
                d.world_model.record_observation(
                    "dev", tid, 1.0 if v.success else 0.0, bool(v.success))
        # ④ Dreaming
        dr = d.dream(k2_max=8)
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
            "dream": {"V": dr.v_by_version["π0"], "m_star": dr.m_star,
                      "k2_max": dr.k2_max,
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

    out = os.path.join(ROOT, "docs", "trial_report_r82.json")
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
