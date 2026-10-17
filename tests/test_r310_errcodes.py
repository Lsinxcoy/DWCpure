# -*- coding: utf-8 -*-
"""R310-④ · 错误码枚举：obs 失败带 code（聚合可查），message 原样保留。"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))


def test_err_shape():
    from dwc.llm.errors import err, CODES
    o = err("CAP_DISABLED", "能力 run 已关闭")
    assert o == {"ok": False, "code": "CAP_DISABLED",
                 "error": "能力 run 已关闭"}
    assert "CAP_DISABLED" in CODES and "DELEGATE_TIMEOUT" in CODES


def test_do_action_carries_code(tmp_path, monkeypatch):
    from dwc.llm import task_exec as T
    from dwc.caps import registry as R
    p = tmp_path / "capabilities.yaml"
    p.write_text("caps:\n  run:\n    enabled: false\n", encoding="utf-8")
    monkeypatch.setenv("DWC_CAPS_PATH", str(p))
    R.reload()
    try:
        obs = T._do_action("run", {"cmd": ["echo", "hi"]})
        assert obs.get("code") == "CAP_DISABLED", obs
        assert "已关闭" in obs.get("error", "")
    finally:
        monkeypatch.delenv("DWC_CAPS_PATH", raising=False)
        R.reload()
