# -*- coding: utf-8 -*-
"""R208 · 独立 agent 形态（用户纠偏: 批处理 → 独立常驻 agent）。

agent 主体: scripts/dwc_agent.py —— 常驻 + 自主任务源（上轮
  next_task_source.world_tree_action.node）+ 日限/崩塌护栏 + 冻结人工门
  + 心跳/pid 文件。
守夜人: scripts/dwc_agent_watch.py —— pid+心跳判活, 死→拉活+告警;
  冻结中不干预（人工门最高优先）。
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
VAR = os.path.join(ROOT, "var")
PY = r"C:\Users\41228\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"


# ═══ agent 自主任务源 ═══
def test_select_task_prefers_own_next_source():
    """★★★ 自主权核心: 上轮 run_term 自产的 world_tree_action.node 即下轮
    任务（"measurement triggers next iteration" 的进程级落地）。"""
    import dwc_agent as A
    from types import SimpleNamespace
    rep = SimpleNamespace(next_task_source={"tasks": [
        {"kind": "wire_dead_mechanism", "target": "m"},
        {"kind": "world_tree_action", "tree": "dev", "node": "reproduce_002"},
    ]})
    assert A.select_task(rep) == "reproduce_002"


def test_select_task_seed_fallback():
    """★ 无源/空源 ⇒ DEV_POOL 轮询（seed 语义, 不崩不空转）。"""
    import dwc_agent as A
    from types import SimpleNamespace
    assert A.select_task(None) in A.DEV_POOL
    assert A.select_task(
        SimpleNamespace(next_task_source={"tasks": []})) in A.DEV_POOL


# ═══ agent 常驻短跑（subprocess）═══
def test_agent_lifecycle_short_run():
    """★★★ 全生命周期: started→terms→stopped(daily_limit) 入台账 + pid
    退出即清 + 心跳落盘。"""
    lg = os.path.join(VAR, "dwc_prod_log.jsonl")
    before = 0
    if os.path.exists(lg):
        before = len(io.open(lg, encoding="utf-8").read().strip().splitlines())
    # ★ 测试隔离: 生产冻结标志（--freeze）不许污染短跑场景 — 暂存后恢复
    frozen = os.path.join(VAR, "dwc_agent_frozen")
    held = frozen + ".held"
    if os.path.exists(frozen):
        os.rename(frozen, held)
    try:
        r = subprocess.run(
            [PY, os.path.join(ROOT, "scripts", "dwc_agent.py"),
             "--interval", "1", "--steps", "1", "--terms-per-day", "2"],
            capture_output=True, text=True, timeout=180, cwd=ROOT)
    finally:
        if os.path.exists(held):
            os.rename(held, frozen)
    assert r.returncode == 0, "rc=%d stderr=%s" % (r.returncode, r.stderr[-200:])
    rows = [json.loads(x) for x in
            io.open(lg, encoding="utf-8").read().strip().splitlines()[before:]]
    events = [x.get("event") for x in rows if "event" in x]
    assert "agent_started" in events, "无 started 事件: %s" % events
    assert "agent_stopped" in events, "无 stopped 事件: %s" % events
    stop = [x for x in rows if x.get("event") == "agent_stopped"][-1]
    assert stop["by"] == "daily_limit", "停机原因非日限: %s" % stop
    terms = [x for x in rows if "agent_term" in x]
    assert len(terms) == 2, "日限 2 未生效: %d terms" % len(terms)
    assert not os.path.exists(os.path.join(VAR, "dwc_agent.pid")), (
        "退出未清 pid（守夜人会误判）")


def test_agent_freeze_gate():
    """★★ 冻结人工门: --freeze 建标志 → 循环下轮优雅停（by=freeze）;
    --unfreeze 清。"""
    import dwc_agent as A
    try:
        A.main([A.__file__, "--freeze"])
        assert os.path.exists(A.FROZEN)
    finally:
        A.main([A.__file__, "--unfreeze"])
    assert not os.path.exists(A.FROZEN)


# ═══ 守夜人 ═══
def test_watchdog_detects_dead_agent():
    """★★ 判活: agent 未跑 ⇒ _alive False（守夜人会拉活）。"""
    import dwc_agent_watch as W
    pidf = os.path.join(VAR, "dwc_agent.pid")
    exists_before = os.path.exists(pidf)
    try:
        if exists_before:
            os.remove(pidf)
        assert W._alive() is False
    finally:
        pass   # pid 文件不恢复（生产 agent 当前冻结中, 由守夜人拉活）


def test_watchdog_respects_freeze():
    """★★ 冻结豁免: 冻结标志在 ⇒ watchdog main 直接 0 不拉活不告警
    （人工门最高优先 — 与母巢"人要停就停着"同源）。"""
    import dwc_agent_watch as W
    open(W.FROZEN, "w").write("t")
    try:
        r = subprocess.run([PY, os.path.join(ROOT, "scripts", "dwc_agent_watch.py")],
                           capture_output=True, text=True, timeout=60)
        assert r.returncode == 0
        assert "restarted" not in r.stdout, "冻结中却拉活了: %s" % r.stdout
    finally:
        os.remove(W.FROZEN)


def test_cron_copy_paths_point_to_repo():
    """★★ CRON RUNS THE COPY 路径坑锁: 副本（hermes/scripts）import 后
    VAR/ROOT 必须指**仓库**路径 — 按 __file__ 定位会找错 var（drift watch
    同款坑, R208 现场抓过）。"""
    dst = os.path.expandvars(r"%LOCALAPPDATA%\hermes\scripts")
    r = subprocess.run(
        [PY, "-c",
         "import sys; sys.path.insert(0, r'%s'); import dwc_agent_watch as W;"
         "import dwc_agent as A; print(W.VAR, A.ROOT)" % dst],
        capture_output=True, text=True, timeout=60)
    out = r.stdout.strip()
    # ★ 路径含空格 ⇒ 不能按空格 split — 断言两段前缀都出现
    assert out.startswith("E:/Divine Wisdom Core/var"), "副本 VAR 错: %s" % out
    assert out.endswith("E:/Divine Wisdom Core"), "副本 ROOT 错: %s" % out
