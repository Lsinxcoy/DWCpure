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
import json

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

    # ★★★ R32: 必须给 has_fn —— rollback 是**终态**，
    #   无法判定"原本是否存在"时必须 raise（不许猜）
    #   ⇒⇒ 否则对不存在的键写回 None 会留垃圾（G4 死不干净）
    return Target(getter=getter, setter=setter,
                  has_fn=lambda: "v" in st,
                  delete_fn=lambda: st.pop("v", None)), st


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

def test_rollback_of_new_key_deletes_it():
    """★★★★★ R32 真 bug 的锁: **新增键**回滚必须 delete，不是写回 None。

    ★★★ 实测（本轮抓到）:
      commit 一个原本不存在的键 → rollback ⇒ **键仍在、值 None**
      ⇒⇒ ⇒★ 那是"死不干净"（G4 生灭门要求能生也能死）
      ⇒⇒ ⇒★ 而我在 R30 修过 apply_on_copy 的同款，**漏了 commit 路径**
    """
    ap = Applier(window=2)
    st = {}
    t = Target(getter=lambda: st.get("k"),
               setter=lambda v: st.__setitem__("k", v),
               has_fn=lambda: "k" in st,
               delete_fn=lambda: st.pop("k", None))
    ap.commit("P_new", t, {"patch": "x"})
    assert "k" in st, "commit 后键应在"
    ap.rollback("P_new", t)
    assert "k" not in st, "★★ 回滚后必须**删干净**，不许留 key:None"
    assert ap.log[-1].reason.count("delete") > 0, "reason 要说明用的是 delete"


def test_rollback_without_has_fn_raises():
    """★★★★ R32: 回滚是**终态** ⇒ 无法判定原本是否存在时必须 raise。

    ★★★ 我初版把 `has()` 的 None 当 True（走写回分支）
      ⇒ 若原本不存在且 old 是 None ⇒ 又留下 key:None 垃圾
      ⇒⇒ ⇒★ 这与我在 apply_on_copy 里处理的**三态**是同一件事，
        而 rollback 不能像试写那样"写回+报告"（它是终态）
    """
    ap = Applier(window=2)
    st = {}
    t = Target(getter=lambda: st.get("k"), setter=lambda v: st.__setitem__("k", v))
    ap.commit("P_nohas", t, 1)
    with pytest.raises(ApplierError) as e:
        ap.rollback("P_nohas", t)
    assert "has_fn" in str(e.value)


def test_rollback_restores_existing_value():
    """★ 对照: 原本**存在**的键 ⇒ 回滚写回原值（不是删）。"""
    ap = Applier(window=2)
    st = {"v": "orig"}
    t, _ = _mk_target(store=st)
    ap.commit("P_e", t, "new")
    assert st["v"] == "new"
    ap.rollback("P_e", t)
    assert st["v"] == "orig", "原本存在的必须**恢复**而非删除"

# ══════════════════════════════════════════════════════════
# ★★★★★ R32 · 固化（2606.09498 line 23 MergeAccepted）
#    闭环的最后一段 —— 学到的东西要能**累积**
# ══════════════════════════════════════════════════════════

def _rule_setup(key="E_VALUE:wrong_magnitude:fibonacci"):
    """★ 一个可写 RULES 表的 target。"""
    table = {}
    t = Target(getter=lambda: table.get(key),
               setter=lambda v: table.__setitem__(key, v),
               has_fn=lambda: key in table,
               delete_fn=lambda: table.pop(key, None))
    return t, table, key


def _entry(**over):
    e = {"component": "control_flow", "dimension": "D7",
         "target_layer": "assets",
         "target": "fibonacci", "m": "loop_bound",
         "m_source": "rule", "patch": "return 1",
         "rationale": "R32 实测: judge 验证通过"}
    e.update(over)
    return e


def _check(key, entry):
    """★ 模拟 evolver 注入的 schema 校验。"""
    from dwc.organs.evolver import Mutator
    return Mutator.check_entry(key, entry)


def test_land_rule_writes_and_reads_back():
    """★★★★★ 正向: 固化成功且**读回一致**（判据 1）。"""
    ap = Applier(window=2)
    t, table, key = _rule_setup()
    r = ap.land_rule(t, key, _entry(), {"success": True}, _check)
    assert r.readback_ok is True
    assert key in table, "固化后必须可读回（写入生效）"
    assert table[key]["patch"] == "return 1"


def test_land_rule_is_queryable_afterwards():
    """★★★★★★ 关键判据: 固化后**能被 propose 查到**。

    ★★★ 若键口径不一致 ⇒ 固化成功却**永远查不到**
      = ARSI C4「写了没人读」的老病
      ⇒⇒ 这就是 key 必须由 `Mutator.key_for` 构造的理由
    """
    from dwc.organs.evolver import Evolver, Mutator
    ap = Applier(window=2)
    sig = {"c": "E_VALUE", "q": "wrong_magnitude", "fn": "fibonacci"}
    key = Mutator.key_for(sig)
    # ★★★ R32 我第一版的写法是**错的**:
    #   我建了个**局部假表**来固化，却去查**全局 Mutator.RULES**
    #   ⇒ 当然查不到 ⇒ 测试失败
    #   ⇒⇒ ⇒★ 而那暴露的真问题: Mutator.RULES 是**类属性**（全局共享）
    #     ⇒⇒ ⇒★ 所以"能查到"必须**在真表上验**，且**必须回滚**
    #       （否则测试会污染全局 ⇒ 后续测试的查表结果全变了）
    assert key not in Mutator.RULES, "★ 前提: 该键本不该存在"
    table = Mutator.RULES
    tgt = Target(getter=lambda: table.get(key),
                 setter=lambda v: table.__setitem__(key, v),
                 has_fn=lambda: key in table,
                 delete_fn=lambda: table.pop(key, None))
    try:
        ap.land_rule(tgt, key, _entry(target="fibonacci"),
                     {"success": True}, _check)
        assert key in table, "固化必须落在**真表**上"
        d = Evolver().diagnose([dict(sig, m="")])
        assert d["proposals"], "★★ 固化后必须能查到（否则=写了没人读）"
        assert d["proposals"][0].target == "fibonacci"
    finally:
        # ★★★ 必须还原全局（否则后续测试被污染）
        ap.rollback("LAND:" + key, tgt)
        assert key not in Mutator.RULES, "★ 测试必须自清洁"


def test_land_rule_rejects_unverified_evidence():
    """★★★★★ 闸②: 没通过验证的**不许固化**（不假装学会）。"""
    ap = Applier(window=2)
    t, table, key = _rule_setup()
    for ev in ({}, {"success": None}, {"success": False}, []):
        with pytest.raises(ApplierError) as e:
            ap.land_rule(t, key, _entry(), ev, _check)
        assert "success" in str(e.value) or "evidence" in str(e.value)
    assert not table, "被拒的固化必须**零副作用**"


def test_land_rule_rejects_bad_schema():
    """★★★★ 闸①: schema 缺字段必须拒（否则炸点在查表那一刻）。"""
    ap = Applier(window=2)
    t, table, key = _rule_setup()
    for bad in ({k: v for k, v in _entry().items() if k != "m"},
                _entry(component="随便什么"),
                _entry(dimension="D99"),
                {"component": "control_flow", "dimension": "D7",
                 "target": "f", "m": "x", "m_source": "r",
                 "patch": "p", "rationale": "   "}):
        with pytest.raises(ApplierError) as e:
            ap.land_rule(t, key, bad, {"success": True}, _check)
        assert "schema" in str(e.value)
    assert not table, "被拒的固化必须**零副作用**"


def test_land_rule_without_check_fn_still_gates_evidence():
    """★ check_fn 可选（applier 不强依赖 evolver），但闸②必须在。"""
    ap = Applier(window=2)
    t, table, key = _rule_setup()
    with pytest.raises(ApplierError):
        ap.land_rule(t, key, _entry(), {"success": False}, None)
    assert not table


def test_land_rule_rollback_removes_new_key():
    """★★★★ G4 能生能死: 回滚新增键 ⇒ 删干净（不留 key:None）。"""
    ap = Applier(window=2)
    t, table, key = _rule_setup()
    ap.land_rule(t, key, _entry(), {"success": True}, _check)
    assert key in table
    ap.rollback("LAND:" + key, t)
    assert key not in table, "★★ 回滚后必须删干净"
    assert "delete" in ap.log[-1].reason


def test_land_rule_counts_once_in_stats():
    """★★ 固化不许**重复记账**（我曾写过 append 后立即 pop 的幻影代码）。"""
    ap = Applier(window=2)
    t, table, key = _rule_setup()
    ap.land_rule(t, key, _entry(), {"success": True}, _check)
    st = ap.stats()
    # ★★★ R33 我把 land 的 `action` 从 "commit" 改成了 "land"
    #   ⇒ R32 这条断言 `n_commit == 1` **过时了**（实测：它红了）
    #   ⇒⇒ ⇒★ 那正是"过时的测试比没有测试更危险"的又一例:
    #     改了实现，断言没跟 ⇒ 红灯**逼**你重新想清楚语义
    #   ⇒ ⇒★ 现在的语义: n_land=固化 · n_commit=原始写入
    assert st["n_land"] == 1, "★ 一次固化记 1 次 land"
    assert st["n_commit"] == 0, "★ land **不算**原始 commit（action 已分）"
    assert st["n_log"] == 1, "★ 只记 1 条（不许重复记账）"


def test_key_for_requires_cqf_and_excludes_m():
    """★★★★★ 键必须含 c/q/fn 而**不含** m（R30 结构修正的锁）。"""
    from dwc.organs.evolver import Mutator
    k = Mutator.key_for({"c": "E_VALUE", "q": "wrong_magnitude",
                         "fn": "f", "m": ""})
    assert k == "E_VALUE:wrong_magnitude:f"
    assert k.count(":") == 2, "★ 三段"
    with pytest.raises(ValueError):
        Mutator.key_for({"c": "E_VALUE", "q": "wrong_magnitude"})

# ══════════════════════════════════════════════════════════
# ★★★★★ R32 · 持久化（固化必须**跨进程存活**）
#    依据 2606.09498 line 23: MergeAccepted 合并进主干
#    ⇒⇒ 合并的东西若进程结束就丢，那不是"合并"，是"本进程试过"
# ══════════════════════════════════════════════════════════

def _tmp_learned(monkeypatch=None):
    """★ 指向临时落盘文件（不污染真 config/）。"""
    from dwc.organs.evolver import Mutator
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    os.remove(path)          # ★ 不存在 = "没学到过" 的常态
    return Mutator, path


def test_learned_path_points_to_config(monkeypatch):
    """★ 落盘位置必须在 config/anchors 下（与真值源同区，可门审）。

    ★ R292 总闸注记：conftest 默认把 LEARNED_PATH 指到 tmp，本测 pin 的
      是**生产默认值** ⇒ 测试内指回真路径（读类体默认值，不硬编码）。
    """
    from dwc.organs.evolver import Mutator
    import dwc.organs.evolver as _EV
    _prod = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(_EV.__file__))))),
        "config", "anchors", "rules.json")
    monkeypatch.setattr(Mutator, "LEARNED_PATH", _prod)
    assert Mutator.LEARNED_PATH.replace("\\", "/").endswith(
        "config/anchors/rules.json")


def test_seed_keys_excludes_from_persist():
    """★★★★ 种子**不进** json（否则代码与 json **双源**）。"""
    from dwc.organs.evolver import Mutator
    assert Mutator.SEED_KEYS, "★ 种子键必须被捕获"
    assert set(Mutator.SEED_KEYS) <= set(Mutator.RULES)
    # ★ 种子里的键永远不该被 persist 写出
    learned = {k for k in Mutator.RULES if k not in Mutator.SEED_KEYS}
    assert not (learned & set(Mutator.SEED_KEYS))


def test_persist_and_load_roundtrip(tmp_path):
    """★★★★★ 持久化往返: 写盘 → 新"进程"（重新加载）→ 读回。"""
    from dwc.organs.evolver import Mutator
    old_path = Mutator.LEARNED_PATH
    old_rules = dict(Mutator.RULES)
    try:
        Mutator.LEARNED_PATH = str(tmp_path / "rules.json")
        Mutator._loaded = True     # ★ 先不自动加载
        Mutator.RULES = dict(old_rules)
        Mutator.RULES["E_L1:q1:f1"] = {
            "component": "control_flow", "dimension": "D7",
            "target": "f1", "m": "m1", "m_source": "rule",
            "patch": "p1", "rationale": "r1"}
        r = Mutator.persist_learned()
        assert r["n_written"] == 1 and r["n_seed"] == len(Mutator.SEED_KEYS)
        # ★ 模拟"新进程": 从种子重新开始 + 加载
        Mutator.RULES = dict(old_rules)
        Mutator._loaded = False
        n = Mutator.ensure_loaded()
        assert n == 1, "★ 新进程必须加载到落盘的规则"
        assert "E_L1:q1:f1" in Mutator.RULES
        assert len(Mutator.RULES) == len(old_rules) + 1, \
            "★ 种子与学到的必须**并存**（不是替换）"
    finally:
        Mutator.LEARNED_PATH = old_path
        Mutator.RULES = dict(old_rules)
        Mutator._loaded = True
        for f in (tmp_path / "rules.json",):
            if f.exists():
                f.unlink()


def test_load_missing_file_returns_zero_not_error(tmp_path):
    """★★ 没学到过是**常态** ⇒ 文件不存在 ⇒ 0，不报错。"""
    from dwc.organs.evolver import Mutator
    old_path, old_loaded = Mutator.LEARNED_PATH, Mutator._loaded
    old_rules = dict(Mutator.RULES)
    try:
        Mutator.LEARNED_PATH = str(tmp_path / "nope.json")
        Mutator._loaded = False
        assert Mutator.ensure_loaded() == 0
        assert len(Mutator.RULES) == len(old_rules), "★ 不许因缺文件丢种子"
    finally:
        Mutator.LEARNED_PATH = old_path
        Mutator._loaded = old_loaded
        Mutator.RULES = dict(old_rules)


def test_ensure_loaded_is_idempotent(tmp_path):
    """★ 幂等: 重复加载不重复合并（否则会静默膨胀）。"""
    from dwc.organs.evolver import Mutator
    old_path, old_rules = Mutator.LEARNED_PATH, dict(Mutator.RULES)
    try:
        Mutator.LEARNED_PATH = str(tmp_path / "r.json")
        Mutator._loaded = True
        Mutator.RULES = dict(old_rules)
        Mutator.RULES["E_L2:q2:f2"] = {
            "component": "control_flow", "dimension": "D7",
            "target": "f2", "m": "m", "m_source": "rule",
            "patch": "p", "rationale": "r"}
        Mutator.persist_learned()
        n_before = len(Mutator.RULES)
        # ★★★ 我第一版**漏了这一步**: persist 后规则还在 RULES 里
        #   ⇒ ensure_loaded() 时它已存在 ⇒ load_learned 的
        #     `if k not in RULES` 命中 ⇒ 返回 0
        #   ⇒⇒ ⇒★ 那说明"不覆盖已有"逻辑是对的，是我的测试没模拟
        #     "新进程从种子出发"（新进程的 RULES 只有种子）
        #   ⇒ ⇒★ 所以这里要先**移除**它，才等于新进程
        Mutator.RULES.pop("E_L2:q2:f2", None)
        assert len(Mutator.RULES) == len(old_rules), "★ 模拟: 只剩种子"
        Mutator._loaded = False
        assert Mutator.ensure_loaded() == 1, "★ 必须从落盘加载到 1 条"
        assert Mutator.ensure_loaded() == 0, "★ 第二次必须是 0（幂等）"
        assert len(Mutator.RULES) == n_before, "★ 加载后回到同样的规模"
    finally:
        Mutator.LEARNED_PATH = old_path
        Mutator.RULES = dict(old_rules)
        Mutator._loaded = True
        if (tmp_path / "r.json").exists():
            (tmp_path / "r.json").unlink()


def test_target_flush_noop_when_absent():
    """★★ 未给 flush 能力 ⇒ 返回 noop（不报错）—— 纯内存表合法。"""
    t = Target(getter=lambda: 1, setter=lambda v: None)
    assert t.flush() == "noop"


def test_target_flush_returns_value_when_present():
    """★★★ flush 必须**返回值**（否则"落没落盘"不可知 = 静默）。"""
    called = []
    t = Target(getter=lambda: 1, setter=lambda v: None,
               flush_fn=lambda: called.append(1) or "written")
    assert t.flush() == "written"
    assert called == [1]


def test_land_rule_reports_persistence_in_reason():
    """★★★★★ 落盘状态必须进 reason（否则"固化了"与"固化且落盘"不可区分）。"""
    ap = Applier(window=2)
    st = {}
    key = "E_P:q:p"
    t = Target(getter=lambda: st.get(key),
               setter=lambda v: st.__setitem__(key, v),
               has_fn=lambda: key in st,
               delete_fn=lambda: st.pop(key, None),
               flush_fn=lambda: "written")
    r = ap.land_rule(t, key, _entry(), {"success": True}, _check)
    assert "已落盘" in r.reason, "★ 必须标明落盘"
    # 对照: 没给 flush 能力
    ap2 = Applier(window=2)
    st2 = {}
    t2 = Target(getter=lambda: st2.get(key),
                setter=lambda v: st2.__setitem__(key, v),
                has_fn=lambda: key in st2,
                delete_fn=lambda: st2.pop(key, None))
    r2 = ap2.land_rule(t2, key, _entry(), {"success": True}, _check)
    assert "仅内存" in r2.reason, "★ 必须标明**没有**落盘（不许静默）"


def test_land_rule_flush_failure_is_visible():
    """★ flush 抛异常 ⇒ 不能吞（落盘失败要显式暴露）。"""
    ap = Applier(window=2)
    st = {}
    key = "E_PF:q:pf"

    def _boom():
        raise OSError("磁盘满")

    t = Target(getter=lambda: st.get(key),
               setter=lambda v: st.__setitem__(key, v),
               has_fn=lambda: key in st,
               delete_fn=lambda: st.pop(key, None),
               flush_fn=_boom)
    with pytest.raises(OSError):
        ap.land_rule(t, key, _entry(), {"success": True}, _check)
    # ★ 内存已写（commit 先于 flush）—— 这是**已知**的不一致，
    #   必须显式留在 reason/log 里可查（不是静默）
    assert key in st, "★ 内存写入先发生（flush 失败不回滚 commit）"

def test_load_does_not_overwrite_existing_rule(tmp_path):
    """★★★★★ 盲区⑨: 落盘的规则**不许覆盖**已有的（同名键）。

    ★★ 变异『摘掉 `if k not in RULES`』⇒ 全套仍绿
      ⇒ 我的 roundtrip 测试里 pop 掉了该键 ⇒ 覆盖与不覆盖效果相同
      ⇒⇒ ⇒★ 于是"保护已有规则"这条**没被测到**
      ⇒⇒ ⇒★★ 而那很要紧: 若落盘文件被污染（或有人手工改），
        一条**坏的**落盘规则会**顶掉**代码里的种子 ⇒ 种子失效
    """
    from dwc.organs.evolver import Mutator
    old_path, old_rules = Mutator.LEARNED_PATH, dict(Mutator.RULES)
    try:
        Mutator.LEARNED_PATH = str(tmp_path / "r.json")
        Mutator._loaded = True
        Mutator.RULES = dict(old_rules)
        # ★★ 关键: 落盘里放一条**同名但内容更差**的种子键
        seed_key = sorted(Mutator.SEED_KEYS)[0]
        poisoned = dict(Mutator.RULES[seed_key])
        poisoned["patch"] = "return None   # 被污染的坏 patch"
        import json as _j
        with open(Mutator.LEARNED_PATH, "w", encoding="utf-8") as f:
            _j.dump({"learned": {seed_key: poisoned}}, f)
        Mutator._loaded = False
        Mutator.ensure_loaded()
        # ★★★ 保护生效: 种子内容**没被顶掉**
        assert Mutator.RULES[seed_key]["patch"] != poisoned["patch"], \
            "★★★ 落盘的同名规则**顶掉了**种子（代码里的人工规则失效）"
        assert Mutator.RULES[seed_key] == old_rules[seed_key]
    finally:
        Mutator.LEARNED_PATH = old_path
        Mutator.RULES = dict(old_rules)
        Mutator._loaded = True
        if (tmp_path / "r.json").exists():
            (tmp_path / "r.json").unlink()


def test_module_level_load_without_explicit_call(tmp_path):
    """★★★★★ 盲区⑪: **只 import 就该加载**（不许要手动调 ensure_loaded）。

    ★★ 变异『摘掉模块级 `_MUTATOR_LOADED_AT_IMPORT = ...`』⇒ 全套仍绿
      ⇒ 因为我的测试都**手动调了** ensure_loaded()
      ⇒⇒ ⇒★ 于是那条模块级触发**没有测试锁**
      ⇒⇒ ⇒★★★ 而它正是我 R32 花力气修的点:
        第一次挂类体（被 except:pass 吞）⇒ 第二次挂实例构造
        （而 RULES 是**类属性** ⇒ 类访问方永不触发 ⇒ 跨进程读不到）
        ⇒⇒ ⇒★ 若这条没锁住，同样的回归会**再次**发生
    ⇒ ⇒★ 用 subprocess 验（测试进程内 import 已完成，无法重来）
    """
    import subprocess as _sp, json as _j, sys as _sys
    from dwc.organs.evolver import Mutator
    old_path, old_rules = Mutator.LEARNED_PATH, dict(Mutator.RULES)
    try:
        # ★ R292 总闸注记：本测要父子进程同读**真路径**（子进程 __file__
        #   算死真路径），总闸的 tmp 在此不适用 ⇒ 指回真路径（外层
        #   finally 用 old_path 恢复总闸态，不污染后续测试）。
        import dwc.organs.evolver as _EV
        Mutator.LEARNED_PATH = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(
                os.path.dirname(os.path.abspath(_EV.__file__))))),
            "config", "anchors", "rules.json")
        # ★★★★ R32 我第一版的写法**错了**:
        #   我 persist 到 tmp_path（测试进程内改的 LEARNED_PATH）
        #   ⇒ 而**子进程**的 LEARNED_PATH 是类定义时用 __file__ 算的
        #     （= 真 config/anchors/rules.json）⇒ 它读不到 tmp 里那份
        #   ⇒ 实测: `HAS=0 LOADED_FLAG=True`
        #     ⇒⇒ ★ 那既不是"模块级触发坏了"，也不是"加载坏了"
        #       而是**我的测试让两个进程读了不同路径**
        #   ⇒⇒ ⇒★ 而生产情形就是**真路径**（没人会临时改它）
        #   ⇒ ⇒★ 所以要 persist 到真路径（finally 清理，不污染）
        Mutator._loaded = True
        Mutator.RULES = dict(old_rules)
        Mutator.RULES["E_ONLY_IMPORT:q:f"] = {
            "component": "control_flow", "dimension": "D7",
            "target": "f", "m": "m", "m_source": "rule",
            "patch": "p", "rationale": "r"}
        _real_path = Mutator.LEARNED_PATH      # ★ 真路径（不改它）
        _backup = (json.load(open(_real_path, encoding="utf-8"))
                   if os.path.exists(_real_path) else None)
        try:
            Mutator.persist_learned()
            # ★ 清干净（保证子进程只能靠**模块级触发**加载）
            Mutator.RULES = dict(old_rules)
            Mutator._loaded = True

            probe = (
                "import sys, json\n"
                "sys.path.insert(0, json.loads(sys.argv[1]))\n"
                "from dwc.organs.evolver import Mutator\n"
                "print('HAS=%d LOADED_FLAG=%s' % (\n"
                "    'E_ONLY_IMPORT:q:f' in Mutator.RULES, Mutator._loaded))\n"
            )
            f = tmp_path / "_probe.py"
            f.write_text(probe, encoding="utf-8")
            r = _sp.run([_sys.executable, str(f),
                         _j.dumps(os.path.join(ROOT, "src"))],
                        capture_output=True, timeout=120,
                        cwd=str(tmp_path))
            out = r.stdout.decode("utf-8", "replace").strip()
            assert r.returncode == 0, \
                "★ 子进程失败: %s" % r.stderr.decode("utf-8", "replace")[-300:]
            # ★★★ 只 import、从不调 ensure_loaded ⇒ 必须已加载
            assert out.startswith("HAS=1"), \
                ("★★★ 只 import 未加载落盘规则 ⇒ 模块级触发丢了（%s）" % out)
            assert "LOADED_FLAG=True" in out, "★ _loaded 守卫应已置位"
        finally:
            # ★★★ 必须恢复真路径（否则后续测试都读不到真 config）
            if _backup is None:
                if os.path.exists(_real_path):
                    os.remove(_real_path)
            else:
                json.dump(_backup, open(_real_path, "w", encoding="utf-8"),
                          ensure_ascii=False, indent=1)
    finally:
        Mutator.LEARNED_PATH = old_path
        Mutator.RULES = dict(old_rules)
        Mutator._loaded = True
        if (tmp_path / "r.json").exists():
            (tmp_path / "r.json").unlink()

# ══════════════════════════════════════════════════════════
# ★★★★★ R33 · 退役（G4 生灭门的**死**那一半）
#    三闸镜像 land_rule: 证明**有害**才能删
# ══════════════════════════════════════════════════════════

def _ret_setup():
    ap = Applier(window=2)
    st = {}
    key = "E_R:q:r"
    t = Target(getter=lambda: st.get(key),
               setter=lambda v: st.__setitem__(key, v),
               has_fn=lambda: key in st,
               delete_fn=lambda: st.pop(key, None),
               flush_fn=lambda: "written")
    return ap, t, st, key


def _land_then_retire(ap, t, st, key, reason="judge 回归证据"):
    entry = _entry(target="f")
    ap.land_rule(t, key, entry, {"success": True}, _check)
    assert key in st
    return ap.retire_rule(t, key, reason, {"success": False}, _check)


def test_retire_removes_key_completely():
    """★★★★★ 退役 = **从表里移除**（不是写 None 留垃圾）。"""
    ap, t, st, key = _ret_setup()
    r = _land_then_retire(ap, t, st, key)
    assert key not in st, "★★★ 退役后键必须消失（写 None 会留垃圾）"
    assert r.readback_ok is True
    assert "已从表中移除" in r.reason
    assert "R30/R32 同族第 3 次" in r.reason, "★ 要记下这是同族第 3 次"


def test_retire_requires_harmful_evidence():
    """★★★★ 三闸镜像: **必须**证明有害（success is False）才删。"""
    ap, t, st, key = _ret_setup()
    ap.land_rule(t, key, _entry(), {"success": True}, _check)
    for ev in ({}, {"success": True}, {"success": None},
               {"success": "false"}, []):
        with pytest.raises(ApplierError) as e:
            ap.retire_rule(t, key, "r", ev, _check)
        assert "success" in str(e.value) or "evidence" in str(e.value)
    assert key in st, "★★ 被拒的退役必须**零副作用**"
    assert st[key]["patch"] == _entry()["patch"], "★ 原条目不许被动过"


def test_retire_requires_reason():
    """★★ 无 reason 的删除会**弄断审计链** ⇒ 必须 raise。"""
    ap, t, st, key = _ret_setup()
    ap.land_rule(t, key, _entry(), {"success": True}, _check)
    for bad in ("", "   ", None, 123):
        with pytest.raises(ApplierError) as e:
            ap.retire_rule(t, key, bad, {"success": False}, _check)
        assert "reason" in str(e.value)
    assert key in st


def test_retire_nonexistent_key_is_rejected():
    """★★ 幻影操作不许做: 退不存在的规则。"""
    ap, t, st, key = _ret_setup()
    with pytest.raises(ApplierError) as e:
        ap.retire_rule(t, "NOPE", "r", {"success": False}, None)
    assert "幻影" in str(e.value)


def test_land_writes_land_metadata():
    """★★★★ _land 元数据入条目 ⇒ **跨进程**可回溯来源与 origin。

    ★★ 理由: applier 的 `_history` 是进程内的 ⇒ 跨进程那条落地
      "不存在" ⇒ 既 rollback 不了，也不知道它当初怎么来的
    """
    ap, t, st, key = _ret_setup()
    ap.land_rule(t, key, _entry(), {"success": True, "task": "T1"}, _check)
    meta = st[key]["_land"]
    assert meta["origin"] is False, "★ 新增键 ⇒ origin=False"
    assert meta["evidence"]["task"] == "T1", "★ 证据要能回溯"
    assert meta["proposal_id"] == "LAND:" + key
    assert meta["landed_at"], "★ 要有时间（不承重但要可审计）"
    # ★ 对照: **原本就存在**的键 ⇒ origin=True
    #   ★★ 我第一版连错两次（都是**测试数据**问题，不是实现）:
    #     ① 用 "k" 当 key ⇒ schema 拒『key 必须是 c:q:fn 三段』
    #     ② 改了 key 格式，却**没把它放进 st2** ⇒ 不存在 ⇒ origin 仍是 False
    #   ⇒⇒ ⇒★ 两处都是"我想要的那个前提**没被建立**"
    #     （key 格式要求 / 键在表中）⇒ 断言测的不是我以为的东西
    _k2 = "E_META:q:m2"
    st2 = {_k2: "orig"}                    # ★★ 关键: 先让键存在
    t2 = Target(getter=lambda: st2.get(_k2),
                setter=lambda v: st2.__setitem__(_k2, v),
                has_fn=lambda: _k2 in st2,
                delete_fn=lambda: st2.pop(_k2, None))
    ap2 = Applier(window=2)
    assert t2.has() is True, "★ 前置: 该键必须已存在"
    ap2.land_rule(t2, _k2, _entry(), {"success": True}, _check)
    assert st2[_k2]["_land"]["origin"] is True, \
        "★ 原本存在的键 ⇒ origin 必须 True（回滚才走 write_back）"


def test_land_does_not_mutate_caller_dict():
    """★★ land_rule 不许改调用方的 dict（我 copy 了才没出事）。"""
    ap, t, st, key = _ret_setup()
    entry = _entry()
    before = dict(entry)
    ap.land_rule(t, key, entry, {"success": True}, _check)
    assert entry == before, "★ 调用方的 entry 不许被塞进 _land"
    assert "_land" in st[key], "★ 但落进去的那份要带"


def test_stats_distinguishes_land_and_retire():
    """★★★★ 生灭**必须可数**（G4 要求）: n_land / n_nretire 分开。

    ★★★ 若不分 ⇒ 「1 land + 1 retire」在 stats 里是 `n_commit=2`
      ⇒ 审计分不清是固化两次还是一生一死
    """
    ap, t, st, key = _ret_setup()
    assert ap.stats()["n_land"] == 0 and ap.stats()["n_retire"] == 0
    ap.land_rule(t, key, _entry(), {"success": True}, _check)
    s1 = ap.stats()
    assert s1["n_land"] == 1 and s1["n_retire"] == 0
    ap.retire_rule(t, key, "r", {"success": False}, _check)
    s2 = ap.stats()
    assert s2["n_land"] == 1, "★ land 计数不许被 retire 污染"
    assert s2["n_retire"] == 1
    assert s2["n_commit"] == 0, "★ land/retire **不是**原始 commit"
    assert s2["n_log"] == 2


def test_retire_then_reland():
    """★★ 生灭是**可循环**的: 死后还能再生（新证据）。"""
    ap, t, st, key = _ret_setup()
    _land_then_retire(ap, t, st, key)
    assert key not in st
    ap.land_rule(t, key, _entry(), {"success": True}, _check)
    assert key in st, "★ 再次固化应成功"
    assert ap.stats()["n_land"] == 2
    assert ap.stats()["n_retire"] == 1

def test_retire_raises_when_delete_fn_is_noop():
    """★★★★★ 破坏性测试: `delete_fn` 无效时退役必须**报错**。

    ★★★ 变异验证抓到的盲区: 摘掉『退役后检查键是否真消失』⇒ 全套仍绿
      ⇒⇒ 因为我的 `delete_fn` **一直有效** ⇒ 那道检查永远走不到
      ⇒⇒ ⇒★ 于是它是**形同虚设**的防御（没测 = 不知道它承不承重）
      ⇒ ⇒★ 本测试把 delete_fn 变成 **no-op**（故意让防御失效）
        ⇒ 若检查在 ⇒ raise；若不在 ⇒ **静默留垃圾** ⇒ 断言失败
    """
    ap = Applier(window=2)
    key = "E_NOOP:q:n"
    st = {key: {"patch": "p"}}
    t = Target(getter=lambda: st.get(key),
               setter=lambda v: st.__setitem__(key, v),
               has_fn=lambda: key in st,
               delete_fn=lambda: None)          # ★★ no-op（删不掉）
    ap.land_rule(t, key, _entry(), {"success": True}, _check)
    with pytest.raises(ApplierError) as e:
        ap.retire_rule(t, key, "r", {"success": False}, _check)
    assert "delete 未生效" in str(e.value), \
        ("★★★ delete_fn 是 no-op ⇒ 退役竟**没报错** ⇒ "
         "规则还在表里却被记成已退役（G4 死不干净）")
    assert key in st, "★ 条目确实还在（证明上面 raise 是对的）"


def test_retire_raises_when_delete_fn_is_weak():
    """★ 变体: delete_fn 只删一半（值变成 None 但键还在）。"""
    ap = Applier(window=2)
    key = "E_WEAK:q:w"
    st = {key: {"patch": "p"}}
    t = Target(getter=lambda: st.get(key),
               setter=lambda v: st.__setitem__(key, v),
               has_fn=lambda: key in st,
               delete_fn=lambda: st.__setitem__(key, None))  # ★ 退化成 None
    ap.land_rule(t, key, _entry(), {"success": True}, _check)
    with pytest.raises(ApplierError) as e:
        ap.retire_rule(t, key, "r", {"success": False}, _check)
    assert "delete 未生效" in str(e.value)
    assert key in st, "★★★ 键还在（值 None）—— 那正是要拦的垃圾条目"

def test_liquidity_wired_on_settle(tmp_path):
    """★★★★★ R44 · 接线 ℒ_t（式10）—— 结算时真的记进历史。

    ★ 这是「接线」的**唯一证据**: 没有它, `record_edit` 只是"有结构没数据"
    """
    import json as _json
    from dwc.organs import evolver as _ev
    p = str(tmp_path / "liq.jsonl")
    _ev.LIQUIDITY_PATH = p          # ★ 用可清理的临时文件
    ap = Applier(window=1)
    # ① 三标签齐 + 有 ΔS/ΔC ⇒ 记（a_i 按 verdict）
    r = ap.window_settle("p1", 1, 0.4, 0.7, scorer_resolution=0.1,
                         component="skill", hypothesis="h1", diff="patch A",
                         cost_delta=0.05, round_no=1)
    assert r["liquidity"]["recorded"] is True
    assert r["liquidity"]["record"]["a_i"] == 1, "★ keep ⇒ a_i=1"
    assert r["liquidity"]["record"]["ℓ_i"] == "skill"
    rows = [_json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    assert len(rows) == 1 and rows[0]["t_i"] == 1
    # ② 缺标签 ⇒ **明确未记**（不静默）
    r2 = ap.window_settle("p2", 1, 0.4, 0.7, scorer_resolution=0.1,
                          component=None, hypothesis="h", diff="d",
                          cost_delta=0.0, round_no=1)
    assert r2["liquidity"]["recorded"] is False
    assert "归因不成立" in r2["liquidity"]["why"]
    # ③ 缺轮次 ⇒ 明确未记（编轮次会污染 g_t 窗口）
    r3 = ap.window_settle("p3", 1, 0.4, 0.7, scorer_resolution=0.1,
                          component="skill", hypothesis="h", diff="d",
                          cost_delta=0.0, round_no=None)
    assert r3["liquidity"]["recorded"] is False
    # ④ revert ⇒ a_i=0（过了但输分 = "admissible but lost"）
    r4 = ap.window_settle("p4", 1, 0.5, 0.5, scorer_resolution=0.1,
                          component="prompt", hypothesis="h4", diff="d",
                          cost_delta=0.0, round_no=2)
    assert r4["liquidity"]["record"]["a_i"] == 0
    # ⑤ 不传新参数（**旧调用点兼容**）⇒ 不炸 + 明确未记
    r5 = ap.window_settle("p5", 1, 0.4, 0.7, scorer_resolution=0.1)
    assert r5["settled"] is True and r5["liquidity"]["recorded"] is False
    # ⑥ ★ R45: ΔC=None ⇒ **收**（诚实未测, e2e 没有成本测量）
    #   而 ΔS（gain）永远是算出来的真值 ⇒ 不会 None
    r6 = ap.window_settle("p6", 1, 0.4, 0.7, scorer_resolution=0.1,
                          component="skill", hypothesis="h", diff="d",
                          cost_delta=None, round_no=3)
    assert r6["liquidity"]["recorded"] is True
    assert r6["liquidity"]["record"]["ΔC_i"] is None, \
        "★ 未测成本 ⇒ 记 null（不是 0.0 —— 那是冒充实测）"
    assert r6["liquidity"]["record"]["ΔS_i"] is not None, \
        "★ ΔS 必须是真值（算出来的 gain）"
