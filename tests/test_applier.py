# -*- coding: utf-8 -*-
"""applier（organs/applier.py）的契约测试。

★★★ 这个器官是闭环的最后一段（APPLIER_DESIGN §一 实测）
  ARSI  · 无落地器 ⇒ 860 accepted → **2 applied**
  Ultra · 无落地器（evolve 0 条）
  Nexus · 无落地器（8 行常量）
  母巢  · 有落地器，但记录了三次失败
  ⇒⇒ ★★ 所以这里每条判据都配阳性 + 阴性两侧

★ 三条判据（APPLIER_DESIGN §五）
  判据 1 · 应用必须可读回（读回不符 ⇒ raise，不许静默）
  判据 2 · 应用必须有回滚路径（写回 + 读回确认）
  判据 3 · 应用必须有窗口（不立即生效）

★ 母巢三次失败的修正（§三）
  失败 1 · base 必须打老配置（自己减自己 = 0 ⇒ 100% 回退）
  失败 2 · scorer 是量化阶梯 ⇒ **降门槛无用**（分辨率是前提）
  失败 3 · 立即生效 ⇒ 无法归因（⇒ 强制窗口）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.organs.applier import (  # noqa: E402
    DEFAULT_WINDOW, TARGETS, Applier, ApplierError, AppliedResult, Target,
)


class Store(dict):
    """★ 简单目标对象（可读回）。"""

    def get(self, k="v"):
        return self[k]

    def put(self, k, v):
        self[k] = v


def _mk_target(store=None, readback_fn=None):
    st = store if store is not None else {"v": "old"}
    if readback_fn:
        def getter():
            return readback_fn(st)

    else:
        def getter():
            return st["v"]

    def setter(v):
        st["v"] = v
    return Target(getter=getter, setter=setter), st


# ══════════════════════════════════════════════════════════
# 判据 1 · 可读回
# ══════════════════════════════════════════════════════════

def test_commit_writes_and_reads_back():
    """★★★★ 意图: commit 写入后读回一致 ⇒ 成功。"""
    ap = Applier(window=2)
    t, st = _mk_target()
    r = ap.commit("P1", t, "new")
    assert r.action == "commit" and r.readback_ok is True
    assert st["v"] == "new", "主干应被更新"


def test_commit_raises_when_readback_mismatches():
    """★★★★★ 判据 1: 读回不符必须 raise，不许静默计成功。

    ★★★ 这治母巢 P0-3（返回 ok:True 但零副作用）
    """
    ap = Applier(window=2)
    t, st = _mk_target(readback_fn=lambda s: "MISMATCH")
    with pytest.raises(ApplierError) as e:
        ap.commit("P2", t, "new")
    # ★★★ R29 修正: 必须**精确到异常来源**
    #   因为 AppliedResult.__post_init__ 是第二道防御，它也 raise
    #   ⇒ 若只断言"含『静默』"，两处消息都能满足 ⇒
    #     commit() 的检查就被掩盖了（单摘变异测不到）
    #   ⇒⇒ ★ 所以断言到「commit 读回不符」这个**只有 commit() 才有**的措辞
    #   ⇒⇒ ⇒★ 让两道防御各自独立可验证
    msg = str(e.value)
    assert "commit 读回不符" in msg, "异常必须来自 commit() 的显式检查"
    assert "'new'" in msg and "'MISMATCH'" in msg, "必须报出差异的两侧值"
    assert "静默" in msg


def test_applied_result_requires_readback_on_commit():
    """★★★ 意图: AppliedResult 的 __post_init__ 强制读回（独立于 Applier）。"""
    with pytest.raises(ApplierError):
        AppliedResult(proposal_id="P", action="commit", readback_ok=False)
    with pytest.raises(ApplierError):
        AppliedResult(proposal_id="P", action="rollback", readback_ok=False)
    # shadow 不需要读回（它不落主干）
    AppliedResult(proposal_id="P", action="shadow", readback_ok=False)


def test_applied_result_rejects_unknown_action():
    """★ 意图: action 限定三种。"""
    with pytest.raises(ApplierError):
        AppliedResult(proposal_id="P", action="随便", readback_ok=True)


# ══════════════════════════════════════════════════════════
# 判据 2 · 可回滚
# ══════════════════════════════════════════════════════════

def test_rollback_restores_old_value():
    """★★★★ 判据 2: 回退 = 写回旧值 + 读回确认。"""
    ap = Applier(window=2)
    t, st = _mk_target(store={"v": "original"})
    ap.commit("P3", t, "changed")
    assert st["v"] == "changed"
    r = ap.rollback("P3", t)
    assert st["v"] == "original", "必须恢复原值"
    assert r.readback_ok is True and r.action == "rollback"


def test_rollback_without_history_raises():
    """★★★ 判据 2: 无落地历史 ⇒ 无法回滚（raise，不许静默）。"""
    ap = Applier(window=2)
    t, st = _mk_target()
    with pytest.raises(ApplierError) as e:
        ap.rollback("P_never_landed", t)
    assert "无落地历史" in str(e.value)


def test_rollback_readback_mismatch_raises():
    """★★★★ 判据 2: 回滚的读回不符也必须 raise。"""
    ap = Applier(window=2)
    t, st = _mk_target(store={"v": "orig"})
    ap.commit("P4", t, "changed")
    # ★ 换一个读回会错的目标
    t_bad, st_bad = _mk_target(store={"v": "orig"},
                               readback_fn=lambda s: "STILL_WRONG")
    ap._history["P4b"] = "orig"
    with pytest.raises(ApplierError):
        ap.rollback("P4b", t_bad)


# ══════════════════════════════════════════════════════════
# 判据 3 · 窗口
# ══════════════════════════════════════════════════════════

def test_default_window_is_five():
    """★★ 意图: 默认窗口 = 母巢那 5 tick。"""
    assert DEFAULT_WINDOW == 5
    assert Applier().window == 5


def test_window_not_settled_when_short():
    """★★★★ 判据 3: 窗口未满 ⇒ 不结算。"""
    ap = Applier(window=3)
    r = ap.window_settle("P", steps=2, base_score=0.5, current_score=0.9,
                         scorer_resolution=0.01)
    assert r["settled"] is False
    assert "窗口未满" in r["why"]


def test_window_settled_when_full():
    """★★★ 判据 3: 窗口满 ⇒ 结算。"""
    ap = Applier(window=3)
    r = ap.window_settle("P", steps=3, base_score=0.4, current_score=0.6,
                         scorer_resolution=0.01, min_gain=0.0)
    assert r["settled"] is True and r["verdict"] == "keep"
    assert r["gain"] == pytest.approx(0.2)


# ══════════════════════════════════════════════════════════
# ★★★ 母巢三次失败的修正
# ══════════════════════════════════════════════════════════

def test_failure1_self_subtract_gives_revert():
    """★★★★★ 母巢失败 1: base 打了新配置 ⇒ 自己减自己 = 0 ⇒ 回退。

    ★★ 原文: 「base 必须打老配置，current 打新配置。自己减自己 = 0」
    ⇒⇒ 那会导致 100% 回退（我实测过 gain=0.0 → reverted）
    """
    ap = Applier(window=3)
    r = ap.window_settle("P", steps=3, base_score=0.5, current_score=0.5,
                         scorer_resolution=0.01, min_gain=0.0)
    assert r["gain"] == 0.0
    assert r["verdict"] == "revert", "gain=0 ⇒ 回退"
    assert "自己减自己" in r["★"]


def test_failure2_quantized_ladder_blocks_decision():
    """★★★★★ 母巢失败 2: scorer 是量化阶梯 ⇒ **降门槛无用**。

    ★★★ 原文: 「score_in 是量化阶梯函数，同一台阶内 gain 恒 0，
       **降门槛无用**」⇒⇒ 所以先验**分辨率**，无分辨率不判胜负
    """
    ap = Applier(window=3)
    # ★ 即使 current 比 base 高很多，分辨率=0 ⇒ 不判
    r = ap.window_settle("P", steps=3, base_score=0.5, current_score=0.9,
                         scorer_resolution=0.0, min_gain=0.0005)
    assert r["verdict"] == "no_resolution"
    assert "降门槛无用" in r["why"]
    assert "分辨率" in r["why"]


def test_failure2_missing_resolution_not_reported():
    """★★★ 母巢失败 2 补充: 未报分辨率 ⇒ 也不判（不默认 1）。"""
    ap = Applier(window=3)
    r = ap.window_settle("P", steps=3, base_score=0.5, current_score=0.9,
                         scorer_resolution=None)
    assert r["verdict"] == "no_resolution_reported"
    assert "分辨率" in r["why"]


def test_failure3_immediate_effect_forbidden_by_window():
    """★★★★ 母巢失败 3: 立即生效 ⇒ 无法归因 ⇒ 窗口强制。"""
    ap = Applier(window=5)
    # 立即结算（steps=0）⇒ 不结算
    r = ap.window_settle("P", steps=0, base_score=0.5, current_score=0.9,
                         scorer_resolution=0.01)
    assert r["settled"] is False, "立即生效会被窗口挡住"


# ══════════════════════════════════════════════════════════
# 落地顺序（2606.09498 Algorithm 1）
# ══════════════════════════════════════════════════════════

def test_apply_on_copy_does_not_touch_trunk():
    """★★★★★ line 9: 在**副本**上试写，生产主干不被触碰。

    ★★ 而母巢的影子方向相反（先 _apply 落生产 → 等 window → 才结算）
    """
    ap = Applier(window=3)
    t, st = _mk_target(store={"v": "old"})
    r = ap.apply_on_copy("P5", t, {"patch": "candidate"})
    assert r["on_copy"] is True and r["restored"] is True
    assert st["v"] == "old", "★ 主干必须保持不动（line 9 之前）"


def test_commit_is_separate_from_copy():
    """★★★ 意图: commit 与试写是两步（不能混）。"""
    ap = Applier(window=3)
    t, st = _mk_target(store={"v": "old"})
    ap.apply_on_copy("P6", t, "candidate")
    assert st["v"] == "old"
    ap.commit("P6", t, "final")
    assert st["v"] == "final"


# ══════════════════════════════════════════════════════════
# 消费点声明
# ══════════════════════════════════════════════════════════

def test_targets_declared_with_verify():
    """★★★ 意图: 消费点声明含 verify（DWC 比母巢多的字段）。

    ★ APPLIER_DESIGN §4.2: 母巢只有 consumer/path/attr
    """
    for name, t in TARGETS.items():
        assert "consumer" in t and "path" in t
        assert "verify" in t, "%s 缺 verify 字段" % name
        assert t.get("★ 属可写面") is True


# ══════════════════════════════════════════════════════════
# 职责边界
# ══════════════════════════════════════════════════════════

def test_applier_does_not_score_or_generate():
    """★★★ 意图: applier 不判分、不生成提案。"""
    ap = Applier(window=2)
    for banned in ("score", "judge", "evaluate", "propose", "diagnose",
                   "generate_patch"):
        assert not hasattr(ap, banned), \
            "applier 出现 %r —— 判分属 judge、生成属 evolver" % banned


def test_stats_reports_commit_and_rollback_counts():
    """★ 意图: 统计分开报 commit / rollback。"""
    ap = Applier(window=2)
    t, st = _mk_target(store={"v": "orig"})
    ap.commit("P7", t, "new")
    ap.rollback("P7", t)
    st2 = ap.stats()
    assert st2["n_commit"] == 1 and st2["n_rollback"] == 1


# ══════════════════════════════════════════════════════════
# ★★★ 闭环实证: 提案 → 试写 → commit → 结算
# ══════════════════════════════════════════════════════════

def test_full_landing_cycle():
    """★★★★★ 闭环实证: 副本试写 → commit → 窗口满 → 结算保留。

    ⇒⇒ 这是 ARSI 860 accepted → 2 applied 那个断点的解法
    """
    ap = Applier(window=3)
    rules = {"E_A:fn:kind": {"patch": "old"}}
    t = Target(getter=lambda: rules["E_A:fn:kind"],
               setter=lambda v: rules.__setitem__("E_A:fn:kind", v))

    # line 9: 副本
    cp = ap.apply_on_copy("P_full", t, {"patch": "candidate"})
    assert rules["E_A:fn:kind"] == {"patch": "old"}

    # commit: 真写
    res = ap.commit("P_full", t, {"patch": "new"})
    assert res.readback_ok and rules["E_A:fn:kind"] == {"patch": "new"}

    # 窗口满 → 结算（有改进 ⇒ keep）
    r1 = ap.window_settle("P_full", steps=3, base_score=0.3,
                          current_score=0.6, scorer_resolution=0.01)
    assert r1["verdict"] == "keep"

    # 若不达标 ⇒ 回退
    r2 = ap.window_settle("P_bad", steps=3, base_score=0.7,
                          current_score=0.4, scorer_resolution=0.01)
    assert r2["verdict"] == "revert"
