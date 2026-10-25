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

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
VAR = os.path.join(ROOT, "var")
PY = sys.executable


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


# ═══ agent 常驻短跑（subprocess；真端点，live 默认 skip）═══
@pytest.mark.live
def test_agent_lifecycle_short_run():
    """★★★ 全生命周期: started→terms→stopped(daily_limit) 入台账 + pid
    退出即清 + 心跳落盘。"""
    iso = os.path.join(VAR, "__r208_iso__")
    import shutil as _sh
    if os.path.exists(iso):
        _sh.rmtree(iso)     # ★ 每次清空隔离目录（残留台账让跨跑断言串味 — 实测 6≠2）
    os.makedirs(iso, exist_ok=True)
    lg = os.path.join(iso, "dwc_prod_log.jsonl")
    before = 0   # 隔离目录空台账 ⇒ 无需对账
    # ★ 测试隔离: ① 生产冻结标志 ② 活 agent 的 pid 文件（R210 单例锁会拒
    #   短跑）—— 都暂存后恢复, 生产态不被测试污染
    frozen = os.path.join(VAR, "dwc_agent_frozen")
    held = frozen + ".held"
    if os.path.exists(frozen):
        os.rename(frozen, held)
    pidf = os.path.join(VAR, "dwc_agent.pid")
    pid_held = pidf + ".held"
    if os.path.exists(pidf):
        os.rename(pidf, pid_held)
    try:
        os.makedirs(iso, exist_ok=True)
        _env = dict(os.environ, DWC_VAR_DIR=iso)
        r = subprocess.run(
            [PY, os.path.join(ROOT, "scripts", "dwc_agent.py"),
             "--interval", "1", "--steps", "1", "--terms-per-day", "2",
             "--rpc-port", "0"],          # 随机端口（不撞生产 8802）
            capture_output=True, text=True, timeout=180, cwd=ROOT,
            env=_env)
    finally:
        if os.path.exists(held):
            os.rename(held, frozen)
        if os.path.exists(pid_held):
            os.rename(pid_held, pidf)
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
    # ★ pid 判活性非文件存在（守夜人同口径）: 文件在但 pid 已死=死尸无害
    pidf = os.path.join(iso, "dwc_agent.pid")
    if os.path.exists(pidf):
        import psutil
        _p = int(io.open(pidf, encoding="utf-8").read().strip())
        assert not psutil.pid_exists(_p), "退出未清**活** pid（守夜人误判）"


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
def test_watchdog_detects_dead_agent(monkeypatch):
    """★★ 判活: agent 未跑 ⇒ _alive False（守夜人会拉活）。

    ★ R370 · 测试隔离：生产常驻 agent 在跑时 `process_iter` 会命中
      ⇒ 本测试必须先屏蔽进程扫描（它测的是「无进程 + pid 文件缺失 ⇒
      False」这条判据，不是「生产有没有 agent」）。
    """
    import dwc_agent_watch as W
    import psutil
    monkeypatch.setattr(psutil, "process_iter", lambda *a, **k: iter([]))

    pidf = os.path.join(VAR, "dwc_agent.pid")
    old = None
    if os.path.exists(pidf):
        with open(pidf, encoding="utf-8") as fh:
            old = fh.read()
        os.remove(pidf)
    try:
        assert W._alive() is False
    finally:
        # ★ 恢复生产 pid 文件 —— 测试不许把生产状态留在被删状态
        if old is not None:
            with open(pidf, "w", encoding="utf-8") as fh:
                fh.write(old)


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
         "import dwc_agent as A; print(W.VAR + '|' + A.ROOT)" % dst],
        capture_output=True, text=True, timeout=60)
    out = r.stdout.strip()
    # ★ 路径含空格 ⇒ 不能按空格 split — 断言两段前缀都出现。
    # ★ R228: 期望值动态取副本自己的 .dwc_repo 指针；没有指针才回退当前仓库。
    #   多部署共存时（测试仓库 vs 生产 cron 副本），副本指向的生产路径才是事实，
    #   不能用 find_root() 把测试仓库当成副本的归属。
    from dwc.foundation.paths import find_root

    def _norm(x):
        return x.replace("\\", "/").rstrip("/")
    var_part, root_part = out.split("|", 1)      # 路径含空格 — 竖线分隔
    pointer = os.path.join(dst, ".dwc_repo")
    if os.path.exists(pointer):
        with open(pointer, encoding="utf-8") as fh:
            repo = _norm(fh.read().strip())
    else:
        repo = _norm(find_root())
    assert _norm(var_part).startswith(repo + "/") and \
        _norm(var_part).endswith("/var"), "副本 VAR 错（应指仓库 var）: %s" % out
    assert _norm(root_part) == repo, "副本 ROOT 错（应指仓库根）: %s" % out
