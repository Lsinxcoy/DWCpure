# -*- coding: utf-8 -*-
"""R243a · watchdog 生产修复锁（用户截图 agent down → 14:15 实测根因）。

★★★ 生产事实（2026-10-13 14:15 cron 输出原文）:
  '拉活告警发送失败: No module named yaml' + agent 死 2h 无进程 —
  双根因: ①cron 的 python 无 yaml ⇒ 告警崩、②拉活用 sys.executable(缺
  yaml/psutil)⇒ agent 拉起即崩、③Popen 无 DETACHED ⇒ 随 cron 会话死。
  ★ 修复已真实端到端验证（tools python 跑副本 → 拉活 + 飞书送达 msg=om_…）
"""
import importlib.util
import io
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT = os.path.join(ROOT, "scripts", "dwc_agent_watch.py")
_TOOLS_PY = os.path.join(os.environ.get("LOCALAPPDATA", "~"),
                         "hermes", "tools")


def _load():
    spec = importlib.util.spec_from_file_location("dwc_agent_watch", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_agent_python_prefers_venv():
    """★★★ 拉活解释器锁: venv 优先（cron 的 sys.executable 缺依赖）。"""
    m = _load()
    py = m._agent_python()
    assert "venv" in py.lower(), py          # 必须 hermes venv
    assert os.path.isfile(py), py
    # env 覆盖
    os.environ["DWC_PY"] = sys.executable
    try:
        assert m._agent_python() == sys.executable
    finally:
        os.environ.pop("DWC_PY", None)


def test_feishu_cfg_yaml_degraded():
    """★★★ yaml 降级锁: 无 yaml 环境走正则解析且字段齐全（告警必达）。"""
    import sys as _s
    m = _load()
    # 人为屏蔽 yaml
    sys.modules["yaml"] = None
    old = _s.modules.get("yaml")
    try:
        if old is not None:
            del sys.modules["yaml"]
        _real_import = __builtins__["__import__"] if isinstance(
            __builtins__, dict) else __builtins__.__import__

        def _no_yaml(name, *a, **kw):
            if name == "yaml":
                raise ImportError("No module named 'yaml'（模拟 cron 环境）")
            return _real_import(name, *a, **kw)

        import builtins
        builtins.__import__ = _no_yaml
        try:
            cfg = m._feishu_cfg()
        finally:
            builtins.__import__ = _real_import
    finally:
        if old is not None:
            sys.modules["yaml"] = old
        sys.modules.pop("yaml", None)
    assert isinstance(cfg, dict)
    for k in ("app_id", "app_secret", "home_channel_id"):
        assert cfg.get(k), (k, cfg)


def test_spawn_detached_flags():
    """★★★ 拉活脱离锁: DETACHED|NEW_GROUP|NO_WINDOW（随 cron 会话死的根因）。"""
    s = io.open(SCRIPT, encoding="utf-8").read()
    assert "DETACHED_PROCESS" in s
    assert "CREATE_NO_WINDOW" in s
    assert "close_fds=True" in s
    # 不再用裸 sys.executable 直接拉活
    assert "py = sys.executable\n" not in s


def test_copy_synced():
    """★★★ 副本同步锁（CRON RUNS THE COPY）。"""
    import hashlib
    copy = os.path.join(os.environ.get("LOCALAPPDATA", "~"),
                        "hermes", "scripts", "dwc_agent_watch.py")
    if not os.path.isfile(copy):
        pytest.skip("副本未同步")
    md5 = lambda p: hashlib.md5(open(p, "rb").read()).hexdigest()
    assert md5(SCRIPT) == md5(copy)
