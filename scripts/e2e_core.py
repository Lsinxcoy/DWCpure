"""F4 · core.py 三入口端到端（生产主类链路）—— 与 e2e_loop.py 互补。

★★★★★ 为什么补这个脚本（R202b 深度审计发现 F4）:
  e2e_loop.py 的 step1-8 走的是**器官级直连**（Judge/Evolver/Applier 单独
  构造后串接），完全没经过 DWC 主类。
  但生产入口是 `DWC(depth_limit, max_nodes).step/run_term/ingest` ——
  主类内部的**三层决策链**（pre_enactment→llm→heuristic）、`_judge_and_backfill`
  的 W5 回填纪律、`dream` 路由、iwm 对照臂记账，全部只在主类里才走得到。
  ⇒ "分段绿 != 主类链路通" 的 R30 同款风险（本轮已实证: e2e_loop 全绿但
    core.step 的 dispatch 路径从未被端到端验证过）

  ★ 本脚本验证的三条链路（对应 ARCHITECTURE §2.1 三入口）:
    ① step(task)  → _decide(三层决策) → actor.act → ingest(不变量①②) →
                     _judge_and_backfill(真判分+W5 回填) → dispatch 路由
    ② ingest     → 失败痕迹必须带 failure_signature（不变量②硬闸）
    ③ run_term   → TermRunner 六步全周期（前测后测/预算/iwm 状态机）

  ★ 复跑: `python scripts/e2e_core.py`（任意 cwd）
    成功标志: 三段 SEG=passed 且 rc=0
  ★ 与 e2e_loop.py 一样用 subprocess 跑子进程 —— 避免 kernel 陈旧模块
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PY = sys.executable or "python"

_SRC = os.path.join(ROOT, "src")


def _clean():
    """清 __pycache__（subprocess 里跑 fresh 解释器 —— kernel 陈旧坑）。"""
    subprocess.run(
        ["find", os.path.join(ROOT, "src"), os.path.join(ROOT, "tests"),
         "-name", "__pycache__", "-type", "d", "-exec", "rm", "-rf", "{}", "+"],
        capture_output=True)


_SEG = {}


def _seg(name, ok, detail=""):
    _SEG[name] = ok
    print("  %s_SEG=%s  %s" % (name.upper(), "passed" if ok else "FAILED", detail))


# ══════════════════════════════════════════════════════════════
# 子进程: 走真 DWC 主类三入口全链路
# ══════════════════════════════════════════════════════════════
_CHILD = r'''
import os, sys, json
sys.path.insert(0, r"__SRC__")

from dwc.core import DWC, DwcError
from dwc.organs.actor import Actor, execute_task, Receipt
from dwc.organs.memory import MemoryKind

_actor0 = Actor()
def _exe(task):
    r = execute_task(_actor0, d.judge, task["task_id"])
    return Receipt(ok=bool(r["observation"]),
                   detail={"observed": r["observation"]}, verified=True)

d = DWC(depth_limit=3, max_nodes=50, executor=_exe)

# ── ① step 链路: 真任务 → 三层决策 → 执行 → ingest → 判分+回填 → dispatch ──
task = {"task_id": "code_fix_001", "kind": "dev"}
out = d.step(task)
assert "decision" in out and "trace" in out and "memory_id" in out, "step 返回缺键"
assert out["decision"]["source"] in ("llm", "heuristic"), "decision source 非法: %r" % out["decision"]["source"]
assert out["memory_id"], "ingest 没返回 memory_id"
assert "judgement" in out, "step 缺 judgement 键"
assert "action_dispatched" in out, "step 缺 action_dispatched 键"

# 判分必须真发生（code_fix_001 是 dev 任务, executor 有真观测）
j = out["judgement"]
assert j is not None, "dev 任务 step 后 judgement 不该是 None（_judge_and_backfill 应判分）"
assert "success" in j, "judgement 缺 success 键"

# action_dispatched 是五路由之一
d_ = out["action_dispatched"]
assert d_["kind"] in ("remember", "dream", "learn", "evolve", "maintain") or not d_["dispatched"], "dispatch kind 非法: %r" % d_["kind"]
assert "how" in d_ or "why" in d_, "dispatch 缺 how/why 痕迹"

# ── ② ingest 不变量②: 失败痕迹必须带 failure_signature ──
bad_trace = {"outcome": "raised", "success": False, "detail": {}}
try:
    d.ingest(bad_trace, chain_id="CH_e2e")
    raise AssertionError("ingest 不变量②被绕过: 失败痕迹无 failure_signature 该 raise")
except DwcError as exc:
    assert "failure_signature" in str(exc), "raise 信息未点名不变量②: %s" % exc

# ── ③ run_term 链路: TermRunner 六步全周期 ──
rep = d.run_term("code_fix_001", n_steps=1)
from dwc.harness.run_term import TermReport
assert isinstance(rep, TermReport), "run_term 返回类型非法: %r" % type(rep).__name__
assert d.iwm is not None, "iwm 器官缺失"
assert d._replay_history is not None, "_replay_history 缺失（dream 历史快照）"

# ── ④ difficulty/success_stats（R207 · P2-8 残口补全: 六公开方法全入 e2e）──
diff = d.difficulty("code_repair")
assert isinstance(diff, list), "difficulty 返回类型非法: r" + type(diff).__name__
ss = d.success_stats()
assert isinstance(ss, dict) and ss, "success_stats 空或类型非法"

# ── ⑤ 多 term 幂等（R207 · P2-8 长程段: 生产形态=多 term 持久轮）──
#   二次 run_term 同 dev 域: W5 回填幂等 + judgement 真判（R205 口径回归）
rep2 = d.run_term("code_fix_002", n_steps=1)
assert isinstance(rep2, TermReport), "第二 term 返回类型非法"
assert rep2.judgement is not None, "第二 term 无 judge 判定"

print(json.dumps({
    "decision_source": out["decision"]["source"],
    "judge_success": j.get("success"),
    "dispatch_kind": d_["kind"],
    "dispatched": d_.get("dispatched"),
    "mem_id_present": bool(out["memory_id"]),
    "difficulty_n": len(diff),
    "success_stats_groups": len(ss),
    "multi_term_judged": rep2.judgement is not None,
}))
'''.replace("__SRC__", _SRC.replace("\\", "\\\\"))


def _run_child():
    _clean()
    r = subprocess.run([PY, "-c", _CHILD], capture_output=True, text=True,
                       timeout=180, cwd=ROOT)
    print("  child rc=%d" % r.returncode)
    if r.stdout.strip():
        print("  child stdout tail:", r.stdout.strip().splitlines()[-1][:150])
    if r.returncode != 0 and r.stderr.strip():
        print("  child stderr tail:")
        for ln in r.stderr.strip().splitlines()[-12:]:
            print("    ", ln[:160])
    return r.returncode, r.stdout.strip()


print("=" * 60)
print("step 1 · core.py 三入口端到端（真 DWC 主类）")
print("=" * 60)
rc, out = _run_child()
_seg("core_e2e", rc == 0, "rc=%d" % rc)

print("\n" + "=" * 60)
print("F4 收官 · 主类三入口端到端")
print("=" * 60)
print("  STEP1_CORE=%s" % ("passed" if _SEG.get("core_e2e") else "failed"))
sys.exit(0 if all(_SEG.values()) else 1)
