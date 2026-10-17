# -*- coding: utf-8 -*-
"""R303-③ 机制目录：config/mechanisms.yaml + mech_registry 只读加载/开关/调用。"""
import pytest

from dwc.foundation import mech_registry as M


def test_load_four_seeded():
    reg = M.load()  # ★ 只读加载无写污染，直接用仓库 root（find_root 发现）
    assert set(["sec_review", "monitor_skip", "verify_final_refs", "delegate"]) <= set(reg)
    assert all(reg[n]["enabled"] for n in ("sec_review", "monitor_skip"))


def test_unknown_disabled():
    reg = M.load()
    assert M.is_enabled(reg, "no_such_mech") is False


def test_call_seeded_entry():
    # ★ 用 R302 现成 verify_final_refs 验 call 通路（sec_review 属方案①，未落地前不碰）
    import tempfile
    reg = M.load()
    with tempfile.TemporaryDirectory() as td:
        out = M.call(reg, "verify_final_refs", "见 config/dwc_self.md 第30行“轮上限”", td)
    assert out is None or isinstance(out, str)


def test_call_unknown_raises():
    import pytest as _p
    reg = M.load()
    with _p.raises(KeyError):
        M.call(reg, "no_such_mech")


def test_load_rejects_dead_entry(tmp_path, monkeypatch):
    import yaml
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "mechanisms.yaml").write_text(
        yaml.safe_dump(
            [{"name": "ghost", "entry": "dwc.llm.task_exec:no_such_fn_xyz",
              "enabled": True}]),
        encoding="utf-8")
    import dwc.foundation.mech_registry as _M
    monkeypatch.setattr(_M, "find_root", lambda: str(tmp_path))
    import pytest as _p
    with _p.raises(ValueError):
        _M.load()
