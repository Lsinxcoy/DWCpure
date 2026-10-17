# -*- coding: utf-8 -*-
"""R308-② · 能力注册表：有名＋开关＋契约（抄 Claude bridge 点名制）。"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "src"))


def test_loads_yaml_table(tmp_path):
    from dwc.caps.registry import load_table
    p = tmp_path / "capabilities.yaml"
    p.write_text("caps:\n  read:\n    enabled: true\n  run:\n    enabled: false\n",
                 encoding="utf-8")
    t = load_table(str(p))
    assert t["read"]["enabled"] is True
    assert t["run"]["enabled"] is False


def test_is_enabled_defaults_true(tmp_path):
    from dwc.caps.registry import is_enabled
    p = tmp_path / "capabilities.yaml"
    p.write_text("caps:\n  read:\n    enabled: true\n", encoding="utf-8")
    assert is_enabled("read", path=str(p)) is True
    assert is_enabled("mcp", path=str(p)) is True
    assert is_enabled("run", path=str(p)) is True


def test_disabled_is_respected(tmp_path):
    from dwc.caps.registry import is_enabled
    p = tmp_path / "capabilities.yaml"
    p.write_text("caps:\n  run:\n    enabled: false\n", encoding="utf-8")
    assert is_enabled("run", path=str(p)) is False


def test_bad_file_fails_open(tmp_path):
    from dwc.caps.registry import is_enabled, load_table
    assert load_table(str(tmp_path / "nope.yaml")) == {}
    assert is_enabled("run", path=str(tmp_path / "nope.yaml")) is True
    p = tmp_path / "bad.yaml"
    p.write_text("caps: [unclosed", encoding="utf-8")
    assert is_enabled("run", path=str(p)) is True


def test_env_path_override(tmp_path, monkeypatch):
    from dwc.caps import registry as R
    p = tmp_path / "capabilities.yaml"
    p.write_text("caps:\n  run:\n    enabled: false\n", encoding="utf-8")
    monkeypatch.setenv("DWC_CAPS_PATH", str(p))
    R.reload()
    try:
        assert R.is_enabled("run") is False
        assert R.is_enabled("read") is True
    finally:
        monkeypatch.delenv("DWC_CAPS_PATH", raising=False)
        R.reload()


def test_do_action_refuses_disabled(tmp_path, monkeypatch):
    from dwc.llm import task_exec as T
    from dwc.caps import registry as R
    p = tmp_path / "capabilities.yaml"
    p.write_text("caps:\n  run:\n    enabled: false\n", encoding="utf-8")
    monkeypatch.setenv("DWC_CAPS_PATH", str(p))
    R.reload()
    try:
        obs = T._do_action("run", {"cmd": ["echo", "hi"]})
        assert obs.get("ok") is False
        assert "disabled" in str(obs.get("error", "")).lower() \
            or "关闭" in str(obs.get("error", ""))
    finally:
        monkeypatch.delenv("DWC_CAPS_PATH", raising=False)
        R.reload()


def test_do_action_default_all_enabled():
    from dwc.llm import task_exec as T
    obs = T._do_action("run", {"cmd": ["echo", "hi"]})
    assert obs.get("ok") is True


def test_delegate_disabled_refuses(tmp_path, monkeypatch):
    from dwc.llm import task_exec as T
    from dwc.caps import registry as R
    p = tmp_path / "capabilities.yaml"
    p.write_text("caps:\n  delegate:\n    enabled: false\n", encoding="utf-8")
    monkeypatch.setenv("DWC_CAPS_PATH", str(p))
    R.reload()
    calls = {"n": 0}

    class _R:
        ok = True
        text = ('{"op": "delegate", "task": "子任务", "analysis": "x"}')

    class _R2:
        ok = True
        text = ('{"op": "final", "answer": "收尾", "analysis": "x"}')

    seq = [_R(), _R2()]

    class _LLM:
        def complete(self, prompt, **kw):
            box.append(prompt)
            r = seq[min(calls["n"], 1)]
            calls["n"] += 1
            return r

    box = []
    try:
        r = T.execute_user_task("测 delegate 门", llm=_LLM(),
                                task_id="T_R308DLG", retry_on_fail=False)
        assert r["status"] == "done", r
        assert any("已关闭" in str(p) for p in box), str(box)[:800]
    finally:
        monkeypatch.delenv("DWC_CAPS_PATH", raising=False)
        R.reload()


def test_disabled_list(tmp_path):
    from dwc.caps.registry import disabled_list
    p = tmp_path / "capabilities.yaml"
    p.write_text("caps:\n  run:\n    enabled: false\n  read:\n    enabled: true\n",
                 encoding="utf-8")
    assert disabled_list(path=str(p)) == ["run"]
    assert disabled_list(path=str(tmp_path / "nope.yaml")) == []
