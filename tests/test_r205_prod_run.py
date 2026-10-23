# -*- coding: utf-8 -*-
"""R205 · 生产运行器 + 树观测回填自动化（P0 四缺口轮）。

P0-1 常驻运行器: scripts/dwc_prod_run.py（多 term + 护栏 + JSONL 台账 + cron 形态）
P0-2 持久化: var/dwc_prod.sqlite（摆脱 :memory:; var/ 已 gitignore）
P0-3 能力通道: --llm 走 R126 LLMExecutorFactory（端点实测活）
P0-4 回填自动化: _close_stages 三重口径（真执行 ∩ success非None ∩ 首次）
    ★ 三重口径的由来: 首跑冒烟 W5 冲突 —— judge.details 是全集判分（含
      fallback False）, 且树真值不可覆盖（W5 锚定纪律）⇒ 只喂首次真执行。
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.core import DWC                                    # noqa: E402
from dwc.organs.actor import Actor, execute_task, Receipt   # noqa: E402


def _dwc() -> DWC:
    d = DWC(depth_limit=3, max_nodes=50)
    actor = Actor()

    def exe(task):
        r = execute_task(actor, d.judge, task["task_id"])
        return Receipt(ok=bool(r["observation"]),
                       detail={"observed": r["observation"]}, verified=True)
    d.executor = exe
    d.runner.executor = exe
    return d


# ══════════════════════════════════════
# P0-4 · 回填三重口径
# ══════════════════════════════════════
def test_backfill_first_term_marks_observed():
    """★★★ 首 term 后: 真执行任务在 dev 树上变 observed（score 非 None）——
    回填自动化真发生（此前 trial_run 手动喂）。"""
    d = _dwc()
    rep = d.run_term("code_fix_001", n_steps=1)
    tree = d.world_model.tree("dev")
    obs = [tid for tid, n in tree.nodes.items() if n.score is not None]
    assert obs, "首 term 没有任何树回填（P0-4 缺口回归）"
    # 真执行集 = ★_executed 键（executor 真跑的 behavior 任务）
    assert "code_fix_001" in obs or rep.judgement is not None


def test_backfill_second_term_idempotent_no_w5():
    """★★★ W5 冲突回归锁: 连续两次 run_term 不抛 WorldModelError ——
    重复回填被『首次才喂』口径挡住（判分不可覆盖 = 锚定纪律）。"""
    d = _dwc()
    d.run_term("code_fix_001", n_steps=1)
    rep2 = d.run_term("code_fix_002", n_steps=1)   # 抛 W5 即失败
    assert rep2.judgement is not None


def test_backfill_only_executed_behavior_tasks():
    """★★ provenance 防线: dev 13 任务里只有 executor 真跑的 6 behavior
    任务进树 —— keyword_match/expected_values 与 fallback 判定不许污染
    树观测（①真执行 ∩ ②success非None ∩ ③首次 三重口径的第一维）。"""
    d = _dwc()
    d.run_term("code_fix_001", n_steps=1)
    tree = d.world_model.tree("dev")
    # ★ R287-E · 名单动态口径（anchor+3 根因：007/008/009 也是 behavior。
    #   硬编码 001..006 ⇒ 新 behavior 锚一落地就超集。改从 judge.anchors
    #   读 verifier_kind==behavior —— 下次 anchor+1 不再炸。）
    behavior = {tid for tid, a in d.judge.anchors.items()
                if isinstance(a, dict) and a.get("verifier_kind")
                == "behavior" and not str(tid).startswith("_")}
    obs = {tid for tid, n in tree.nodes.items() if n.score is not None}
    assert obs, "首 term 无任何回填（回填自动化回归）"
    assert obs <= behavior, "非 behavior 任务被喂进树: %s" % (obs - behavior)
    assert "reasoning_001" not in obs, "keyword_match 任务不进树"
    assert "reproduce_001" not in obs, "expected_values 任务不进树"


# ══════════════════════════════════════
# P0-1/P0-2 · 运行器 + 持久化
# ══════════════════════════════════════
def test_prod_run_persists_db_and_ledger():
    """★★★ 运行器端到端: subprocess 跑 --terms 1 ⇒ rc0 + 空 stdout
    （health=silence）+ db 文件落盘 + 台账 completed 事件。"""
    var = os.path.join(ROOT, "var")
    log = os.path.join(var, "dwc_prod_log.jsonl")
    before = 0
    if os.path.exists(log):
        before = len(io.open(log, encoding="utf-8").read().strip().splitlines())
    r = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "dwc_prod_run.py"),
         "--terms", "1", "--steps", "1"],
        capture_output=True, text=True, timeout=300, cwd=ROOT)
    assert r.returncode == 0, "rc=%d stderr=%s" % (r.returncode, r.stderr[-300:])
    assert r.stdout.strip() == "", "正常轮不许 stdout（health=silence）"
    assert os.path.exists(os.path.join(var, "dwc_prod.sqlite")), "db 没落盘"
    lines = io.open(log, encoding="utf-8").read().strip().splitlines()
    assert len(lines) > before, "台账没追加"
    tail = [json.loads(x) for x in lines[before:]]
    assert any(x.get("event") == "completed" for x in tail), (
        "无 completed 事件: %s" % tail[-2:])


def test_prod_run_guard_events_documented():
    """★ 护栏事件留痕: 两类停机事件（stopped_budget/stopped_collapse）在
    运行器源码里带台账事件（先停后报 — 不静默死）。"""
    src = io.open(os.path.join(ROOT, "scripts", "dwc_prod_run.py"),
                  encoding="utf-8").read()
    assert '"event": "stopped_budget"' in src
    assert '"event": "stopped_collapse"' in src
    assert "best_pass" in src, "退化崩塌基线缺失（冷启动误伤回归）"


def test_var_is_gitignored():
    """★★ P0-2 卫生: var/ 绝不入库（生产库与台账不是代码）。"""
    r = subprocess.run(["git", "-C", ROOT, "check-ignore", "-v", "var/dwc_prod.sqlite"],
                       capture_output=True, text=True)
    assert r.stdout.strip(), "var/ 未被 gitignore（库可能入库）"
