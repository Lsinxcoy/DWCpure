# -*- coding: utf-8 -*-
"""R309-① · delegate 生命周期治理：超时熔断＋obs 留痕（yaml 可调）。"""
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))


def test_cap_limit_reads_yaml(tmp_path):
    from dwc.caps.registry import cap_limit
    p = tmp_path / "capabilities.yaml"
    p.write_text("caps:\n  delegate:\n    enabled: true\n    timeout_s: 42\n",
                 encoding="utf-8")
    assert cap_limit("delegate", "timeout_s", 600,
                     path=str(p)) == 42
    assert cap_limit("delegate", "missing_k", 600, path=str(p)) == 600
    assert cap_limit("nope", "timeout_s", 600, path=str(p)) == 600


def test_delegate_timeout_reports(tmp_path, monkeypatch):
    from dwc.llm import task_exec as T
    from dwc.caps import registry as R
    p = tmp_path / "capabilities.yaml"
    p.write_text("caps:\n  delegate:\n    enabled: true\n    timeout_s: 1\n",
                 encoding="utf-8")
    monkeypatch.setenv("DWC_CAPS_PATH", str(p))
    R.reload()

    box = []
    calls = {"n": 0}

    # prompt 序列：第 0 轮返回 delegate op，第 1 轮（子代理内）sleep，
    # 第 2 轮 final。
    seq = [types_S("delegate"), types_S("final"), types_S("final")]

    class _LLM2:
        def complete(self, prompt, **kw):
            box.append(prompt)
            n = calls["n"]
            calls["n"] += 1
            if n == 1:
                time.sleep(5)
            return seq[min(n, 2)]()

    try:
        t0 = time.monotonic()
        r = T.execute_user_task("测 delegate 熔断", llm=_LLM2(),
                                task_id="T_R309TO", retry_on_fail=False)
        dt = time.monotonic() - t0
        assert r["status"] == "done", r
        assert dt < 30, dt
        assert any("超时" in str(p_) for p_ in box), str(box)[:600]
    finally:
        monkeypatch.delenv("DWC_CAPS_PATH", raising=False)
        R.reload()


def types_S(op):
    class _R:
        ok = True
        if op == "delegate":
            text = '{"op": "delegate", "task": "子任务", "analysis": "x"}'
        else:
            text = '{"op": "final", "answer": "收尾", "analysis": "x"}'
    return _R
