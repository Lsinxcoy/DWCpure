# -*- coding: utf-8 -*-
"""R455 · 选择状态持久化 + 供给题覆盖优先。

★ 现实背景（写测试时的实测）：队列 15 道题只跑过 1 道。
  根因是 `_sel`/`_day` 只在内存里，重启即清零 ⇒ 永远回到 pool[0]。
"""
import io
import json
import os

from dwc.organs import selection_state as SS


def _p(tmp_path):
    return str(tmp_path / "agent_sel.json")


# ── 持久化 ─────────────────────────────────────────────────────

def test_roundtrip_keeps_sel_and_day(tmp_path):
    p = _p(tmp_path)
    sel = {"last": "code_fix_002", "streak": 3,
           "used": ["code_fix_001", "code_fix_002"],
           "cooldown": {"reproduce_003": 4}}
    day = {"key": "2026-10-24", "terms": 7, "cost": 1.5}
    assert SS.save(sel, day, p) is True
    s, d = SS.load(p, today="2026-10-24")
    assert s == sel and d == day


def test_missing_file_returns_defaults(tmp_path):
    s, d = SS.load(_p(tmp_path), today="2026-10-24")
    assert s == {"last": None, "streak": 0, "used": [], "cooldown": {}}
    assert d["terms"] == 0 and d["key"] == "2026-10-24"


def test_corrupt_file_falls_back(tmp_path):
    p = _p(tmp_path)
    io.open(p, "w", encoding="utf-8").write("{not json")
    s, d = SS.load(p, today="2026-10-24")
    assert d["terms"] == 0 and s["used"] == []


def test_day_rollover_resets_counters_but_keeps_coverage(tmp_path):
    """★ 过夜只清当日计数，覆盖进度（used）不能丢 —— 否则第二天又从 pool[0] 开始。"""
    p = _p(tmp_path)
    SS.save({"last": "a", "streak": 2, "used": ["a", "b"], "cooldown": {}},
            {"key": "2026-10-23", "terms": 40, "cost": 9.0}, p)
    s, d = SS.load(p, today="2026-10-24")
    assert d["terms"] == 0 and d["cost"] == 0.0 and d["key"] == "2026-10-24"
    assert s["used"] == ["a", "b"]


def test_bad_field_types_are_sanitized(tmp_path):
    p = _p(tmp_path)
    io.open(p, "w", encoding="utf-8").write(json.dumps(
        {"sel": {"streak": "x", "used": "nope", "cooldown": []},
         "day": {"key": "2026-10-24", "terms": "y", "cost": "z"}}))
    s, d = SS.load(p, today="2026-10-24")
    assert s["streak"] == 0 and s["used"] == [] and s["cooldown"] == {}
    assert d["terms"] == 0 and d["cost"] == 0.0


# ── 供给覆盖优先 ───────────────────────────────────────────────

POOL = ("code_fix_001", "supply_a", "supply_b")


def test_unrun_supply_wins_over_advice():
    got = SS.pick_with_supply("code_fix_001", POOL, ("supply_a", "supply_b"),
                              used=["code_fix_001"])
    assert got == "supply_a"


def test_covered_supply_leaves_choice_alone():
    got = SS.pick_with_supply("code_fix_001", POOL, ("supply_a", "supply_b"),
                              used=["supply_a", "supply_b"])
    assert got == "code_fix_001"


def test_supply_in_cooldown_is_skipped():
    got = SS.pick_with_supply("code_fix_001", POOL, ("supply_a", "supply_b"),
                              used=[], cooldown={"supply_a": 5})
    assert got == "supply_b"


def test_already_on_unrun_supply_is_kept():
    got = SS.pick_with_supply("supply_b", POOL, ("supply_a", "supply_b"), used=[])
    assert got == "supply_b"


def test_empty_supply_is_a_noop():
    assert SS.pick_with_supply("code_fix_001", POOL, (), []) == "code_fix_001"


def test_supply_outside_pool_is_ignored():
    """队列里的题没注入判分器/池子 ⇒ 选了也跑不了，不许选。"""
    got = SS.pick_with_supply("code_fix_001", POOL, ("ghost",), used=[])
    assert got == "code_fix_001"


# ── 接线（源码锁：防止写了模块但没接）────────────────────────

def test_agent_wires_state_and_supply():
    src = io.open(os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "scripts", "dwc_agent.py"),
        encoding="utf-8").read()
    assert "_load_state()" in src, "启动时没加载选择状态"
    assert "pick_with_supply(" in src, "选择器没接供给覆盖"
    assert "supply=tuple(_SUPPLY_IDS)" in src, "select_task 没传供给题"


def test_cron_copy_in_sync():
    """★ cron 跑的是 %LOCALAPPDATA%/hermes/scripts 下的副本，不是仓库文件。
    副本漂移 ⇒ 定时任务跑旧码，`cronjob list` 完全看不出来。"""
    import hashlib
    import pytest
    repo = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "scripts", "supply_checkpoint.py")
    copy = os.path.join(os.environ.get("LOCALAPPDATA", ""), "hermes", "scripts",
                        "supply_checkpoint.py")
    if not os.path.exists(copy):
        pytest.skip("本机没有 cron 副本（非部署环境）")
    h = lambda p: hashlib.md5(open(p, "rb").read()).hexdigest()
    assert h(copy) == h(repo), "副本与仓库漂移 ⇒ cron 跑旧码（改动只算半改）"
