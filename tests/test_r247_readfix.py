# -*- coding: utf-8 -*-
"""R247 · 执行核可靠性锁（read 翻页 · 环境声明 · 复读熔断 · 999 轮 · 留痕）。

★ 起因: 17:12/17:13 两单真实失败 — ①read 恒定截断无翻页 ⇒ 4 轮复读同段
  至上限; ②LLM 生成 wsl.exe 命令 + GBK 解 UTF-16 乱码污染推理 + session
  无 cmd/obs 留痕。
"""
import io
import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from dwc.llm import task_exec as TE  # noqa: E402


class _FakeLLM:
    """按脚本依次吐 step; 记录收到的 system/prompt。"""

    def __init__(self, steps):
        self._steps = list(steps)
        self.systems = []
        self.prompts = []

    def complete(self, prompt, **kw):
        self.prompts.append(prompt)
        self.systems.append(kw.get("system", ""))
        step = (self._steps.pop(0) if self._steps
                else {"analysis": "done", "op": "final", "answer": "完"})
        return SimpleNamespace(ok=True, text=json.dumps(step, ensure_ascii=False),
                               error="", meta={})

    def complete_stream(self, prompt, **kw):
        r = self.complete(prompt, **kw)
        on_delta = kw.get("on_delta")
        if on_delta:
            on_delta(r.text)
        return r


def _run(tmp_task, steps, **kw):
    old = os.environ.get("DWC_SESS_DIR")
    return TE.execute_user_task(tmp_task, llm=_FakeLLM(steps), **kw)


def test_read_offset_paging():
    """★★★ read 翻页锁: offset 取不同段 + truncated/hint 引导。"""
    import dwc.llm.task_exec as m
    d = os.path.join(m.ROOT, "var", "__test_read247__")
    os.makedirs(d, exist_ok=True)
    src = os.path.join(d, "big.txt")
    io.open(src, "w", encoding="utf-8").write(
        "\n".join("行%d" % i for i in range(1, 301)))
    rel = "var/__test_read247__/big.txt"
    try:
        step = {"op": "read", "path": rel}
        o1 = m._do_action("read", dict(step))
        o2 = m._do_action("read", dict(step, offset=250, limit=50))
        assert o1["truncated"] is True
        assert "offset=" in o1["hint"]
        assert o1["content"].startswith("行1")
        assert o2["offset"] == 250
        assert o2["returned_lines"] == 50
        assert "行251" in o2["content"]
        assert o2["truncated"] is False          # 250+50=300 读完
    finally:
        try:
            os.remove(src)
            os.rmdir(d)
        except OSError:
            pass


def test_default_max_rounds_999():
    """★★★ 轮上限 999 锁（用户: '999 6也太少了'）。"""
    import inspect
    sig = inspect.signature(TE.execute_user_task)
    assert sig.parameters["max_rounds"].default == 999


def test_dup_fusion_blowout():
    """★★★ 复读熔断锁: 同 read×3 ⇒ 立即 incomplete 带熔断 why
    （999 轮的硬出口 — 不许空转打满）。"""
    steps = [{"analysis": "读", "op": "read", "path": "config/drift.yaml"}] * 6
    rep = _run("熔断测试", steps)
    assert rep["status"] == "incomplete"
    assert "复读熔断" in rep["why"]
    assert rep["rounds"] <= 4, rep["rounds"]


def test_system_declares_env_and_paging():
    """★★★ system prompt 锁: Windows 环境声明 + offset 翻页 + 复读指引。"""
    llm = _FakeLLM([{"analysis": "a", "op": "final", "answer": "x"}])
    TE.execute_user_task("smoke", llm=llm)
    sys_p = llm.systems[0]
    assert "Windows" in sys_p and "wsl" in sys_p
    assert "offset" in sys_p
    assert "复读熔断" in sys_p or "原地重复" in sys_p


def test_run_declares_utf8():
    """★★★ run 编码锁: 3 处 subprocess 显式 utf-8（GBK 解 UTF-16 乱码案）。"""
    import io as _io
    src = _io.open(TE.__file__, encoding="utf-8").read()
    assert src.count('encoding="utf-8"') >= 3
    # 不许存在 text=True 却无 encoding 的裸调用
    import re
    for m in re.finditer(r"subprocess\.run\((?:[^()]|\([^()]*\))*\)", src):
        seg = m.group(0)
        if "text=True" in seg:
            assert "encoding" in seg, seg[:200]


def test_session_records_target_and_obs(tmp_path, monkeypatch):
    """★★★ 留痕锁: session jsonl 记 target + obs（失败现场可查）。"""
    out = tmp_path / "sess.jsonl"
    monkeypatch.setattr(TE, "SESSIONS", str(tmp_path))
    llm = _FakeLLM([{"analysis": "读配置", "op": "read",
                     "path": "config/drift.yaml"},
                    {"analysis": "完", "op": "final", "answer": "好"}])
    TE.execute_user_task("留痕测试", llm=llm, task_id="T_lock247")
    p = tmp_path / "T_lock247.jsonl"
    assert p.exists()
    rows = [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()
            if x.strip()]
    obs_rows = [r for r in rows if r.get("phase") == "obs"]
    assert obs_rows, rows
    r0 = obs_rows[0]
    assert r0.get("op") == "read"
    assert "config/drift.yaml" in str(r0.get("target", ""))
    assert "n_lines" in str(r0.get("obs", ""))
    assert r0.get("ok") is True
