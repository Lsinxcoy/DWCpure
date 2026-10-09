# -*- coding: utf-8 -*-
"""记忆内核（organs/memory.py）的契约测试。

★★★ 存在理由
  这是 DWC 的**第一个器官**。而 DWC 的头号教训是
  「门存在 ≠ 门被执行」⇒ 所以记忆内核的每个判据都要有阳性测试。

★ 逐条判据:
  D6 · EXPERIENCE 只存"能驱动进化的东西" —— 写入时门槛，不是事后分类
  D7 · 记忆必须证明"被使用" —— 无 access 记录不算有价值
  §三 · 淘汰三条依据（召回过？改变行为？唯一签名？）
  §四 · 七管归属的区划分
  P1 · 器官之间只经接口
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.organs.memory import (  # noqa: E402
    EXPERIENCE_REQUIREMENTS, KIND_TO_ZONE, MemoryError, MemoryKernel,
    MemoryKind, MemoryNode, Tube, Zone,
)


@pytest.fixture
def mem():
    k = MemoryKernel()
    yield k
    k.close()


# ══════════════════════════════════════════════════════════
# §四 · 四区归属
# ══════════════════════════════════════════════════════════

def test_zone_mapping_follows_design():
    """意图: 各类记忆的归属区与 MEMORY_SYSTEM §四 的表一致。"""
    assert KIND_TO_ZONE[MemoryKind.TRACE] is Zone.PROXY
    assert KIND_TO_ZONE[MemoryKind.WORKING_STATE] is Zone.PROXY
    assert KIND_TO_ZONE[MemoryKind.FAILURE_SIGNATURE] is Zone.EXPERIENCE
    assert KIND_TO_ZONE[MemoryKind.SKILL] is Zone.EXPERIENCE
    assert KIND_TO_ZONE[MemoryKind.PROPOSAL] is Zone.EXPERIENCE


def test_pipe_assignment(mem):
    """★★ 意图: 七管归属 —— remember→PROXY，learn/evolve→EXPERIENCE。"""
    t = mem.remember(MemoryKind.TRACE, {"a": 1})
    assert mem.get(t).tube is Tube.REMEMBER
    w = mem.remember(MemoryKind.WORKING_STATE, {"b": 2})
    assert mem.get(w).tube is Tube.REMEMBER
    # ★★ 2026-10-05 R21 更正: 失败签名属 **reflect 管**（归因），
    #   不是 learn 管。依据 MEMORY_SYSTEM §四 的归属表原文:
    #     | 失败签名 (c,q,m) | reflect | EXPERIENCE | 按三元组精确聚类 |
    #   ⇒★ 而 learn 管对应的是「技能(场景/方法/边界)」那行
    s = mem.remember(MemoryKind.FAILURE_SIGNATURE,
                      {"c": "x", "q": "y", "m": "z"})
    assert mem.get(s).tube is Tube.REFLECT
    sk = mem.remember(MemoryKind.SKILL,
                      {"scene": "a", "method": "b", "boundary": "c",
                       "invalid_conditions": ["d"], "recovery_strategies": ["e"]})
    assert mem.get(sk).tube is Tube.LEARN
    p = mem.remember(MemoryKind.PROPOSAL,
                      {"consumer_declared": "gate7_accumulation"})
    assert mem.get(p).tube is Tube.EVOLVE


# ══════════════════════════════════════════════════════════
# D6 · EXPERIENCE 的写入门槛
# ══════════════════════════════════════════════════════════

@pytest.mark.parametrize("kind,missing", [
    (MemoryKind.FAILURE_SIGNATURE, "q"),
    (MemoryKind.FAILURE_SIGNATURE, "m"),
    (MemoryKind.SKILL, "boundary"),
    (MemoryKind.PROPOSAL, "consumer_declared"),
])
def test_d6_blocks_incomplete_experience(mem, kind, missing):
    """★★★ 判据 D6: 缺门槛字段就**不许进 EXPERIENCE**。

    ★★★ 这是写入时的门槛，不是事后分类 ——
      若只是打标签，那么"不能驱动进化的东西"照样会占 EXPERIENCE。
    """
    payload = {k: "v" for k in EXPERIENCE_REQUIREMENTS[kind]}
    payload[missing] = None                      # 缺（或为空）
    with pytest.raises(MemoryError) as e:
        mem.remember(kind, payload)
    assert "D6" in str(e.value)


def test_d6_allows_complete_experience(mem):
    """意图: 门槛齐备就放行。"""
    nid = mem.remember(MemoryKind.FAILURE_SIGNATURE,
                       {"c": "timeout", "q": "agent", "m": "retry"})
    assert mem.get(nid).zone is Zone.EXPERIENCE


def test_d6_does_not_block_proxy(mem):
    """意图: PROXY 类没有门槛（痕迹不需要 c,q,m）。"""
    nid = mem.remember(MemoryKind.TRACE, {"action": "x"})
    assert mem.get(nid).zone is Zone.PROXY


def test_unknown_kind_rejected(mem):
    """意图: 未知种类必须 raise。"""
    with pytest.raises(MemoryError):
        mem.remember("not_a_kind", {})


# ══════════════════════════════════════════════════════════
# D7 · 记忆必须证明被使用
# ══════════════════════════════════════════════════════════

def test_d7_unused_memory_has_no_proven_value(mem):
    """★★★ 判据 D7: 无 access 记录 ⇒ 不算有价值。

    ★★★ 母巢的反面教材: 98.8% 节点 access_count=0，
      但 importance 均值 0.747 —— 自评很高，实际没人用。
    ⇒⇒ 所以本模块**不提供自报价值的接口**，价值只能由 recall 推出。
    """
    nid = mem.remember(MemoryKind.TRACE, {"a": 1})
    n = mem.get(nid)
    assert n.access_count == 0
    assert not n.used()
    assert not n.proven_value()


def test_d7_recall_makes_it_used(mem):
    """意图: 召回本身**就是**使用的证据。"""
    nid = mem.remember(MemoryKind.TRACE, {"a": 1})
    n = mem.recall(nid)
    assert n.access_count == 1
    assert n.used() and n.proven_value()
    assert n.last_access is not None


def test_d7_no_self_reported_value_api(mem):
    """★★★ 意图: 内存核**没有**自报价值接口（防止 importance 那种自评）。"""
    pub = [m for m in dir(mem) if not m.startswith("_")]
    for banned in ("set_importance", "rate", "score", "self_value",
                   "importance", "value", "quality"):
        assert banned not in pub, "出现自报价值的接口 %r（D7 禁止）" % banned


def test_effect_is_separate_from_access(mem):
    """★★ 意图: 被召回 ≠ 改变行为（两者是不同证据）。"""
    nid = mem.remember(MemoryKind.TRACE, {"a": 1})
    n = mem.recall(nid)
    assert n.used() and not n.changed_behavior(), "召回不等于改变行为"
    n2 = mem.record_effect(nid)
    assert n2.changed_behavior()


def test_usage_stats_reflects_reality(mem):
    """★★★ 意图: 使用统计必须由 access 记录算出，不是估的。"""
    a = mem.remember(MemoryKind.TRACE, {"a": 1})
    b = mem.remember(MemoryKind.TRACE, {"b": 2})
    mem.remember(MemoryKind.TRACE, {"c": 3})
    mem.recall(a)
    mem.recall(b)
    mem.record_effect(a)
    st = mem.usage_stats()
    assert st["total"] == 3
    assert st["used"] == 2
    assert st["effective"] == 1
    assert abs(st["used_ratio"] - 2 / 3) < 1e-9
    assert abs(st["effective_ratio"] - 1 / 3) < 1e-9


def test_usage_stats_empty_is_zero_not_error(mem):
    """意图: 空库返回 0 而非抛错。"""
    st = mem.usage_stats()
    assert st["total"] == 0 and st["used_ratio"] == 0.0


# ══════════════════════════════════════════════════════════
# §三 · 淘汰三条依据
# ══════════════════════════════════════════════════════════

def test_eviction_candidates_only_report_evidence(mem):
    """★★★ 意图: eviction_candidates **不删任何东西**。

    ★★ 淘汰决策属于 evolver（GAI dials 的职责），不在记忆内核内。
      ⇒ 若记忆内核自己删，就有了第二个决策中心。
    """
    ids = [mem.remember(MemoryKind.TRACE, {"n": i}) for i in range(3)]
    rows = mem.eviction_candidates()
    assert len(rows) == 3
    for nid in ids:
        assert mem.get(nid) is not None, "eviction_candidates 不得删除任何记忆"


def test_unique_signature_is_protected(mem):
    """★★★ 意图: 某类失败的唯一签名受"稀有保护" ⇒ 不可淘汰。

    ★ 依据 MEMORY_SYSTEM §三: "淘汰前必须过稀有保护:
      若该记忆是某类失败的唯一签名 ⇒ 不淘汰"
    """
    sig = mem.remember(MemoryKind.FAILURE_SIGNATURE,
                       {"c": "timeout", "q": "agent", "m": "retry"})
    mem.remember(MemoryKind.TRACE, {"n": 1})
    rows = {r["node_id"]: r for r in mem.eviction_candidates()}
    assert rows[sig]["rare_protected"] is True
    assert rows[sig]["evictable"] is False, "唯一签名不该被淘汰"


def test_used_memory_not_evictable(mem):
    """意图: 被用过的记忆不可淘汰（access > 0）。"""
    nid = mem.remember(MemoryKind.TRACE, {"n": 1})
    mem.recall(nid)
    rows = {r["node_id"]: r for r in mem.eviction_candidates()}
    assert rows[nid]["evictable"] is False


def test_never_used_proxy_is_evictable(mem):
    """意图: 从未召回的痕迹可淘汰（候选）。"""
    nid = mem.remember(MemoryKind.TRACE, {"n": 1})
    rows = {r["node_id"]: r for r in mem.eviction_candidates()}
    assert rows[nid]["evictable"] is True


# ═══════════════════════════════════════════════��══════════
# 归档（不删）
# ══════════════════════════════════════════════════════════

def test_archive_keeps_node_readable(mem):
    """意图: 归档不是删除（判据 S6 的同款纪律）。"""
    nid = mem.remember(MemoryKind.TRACE, {"n": 1})
    n = mem.archive(nid)
    assert n.zone is Zone.ARCHIVE
    assert n.archived_at is not None
    assert mem.get(nid) is not None, "归档后仍可读"
    # ★ 归档后不该出现在候选里
    assert nid not in [r["node_id"] for r in mem.eviction_candidates()]


# ══════════════════════════════════════════════════════════
# 检索（索引消费点）
# ══════════════════════════════════════════════════════════

def test_signature_clustering(mem):
    """★★ 意图: 失败签名按 (c,q,m) 三元组精确聚类。"""
    a = mem.remember(MemoryKind.FAILURE_SIGNATURE,
                     {"c": "t", "q": "a", "m": "r", "n": 1})
    b = mem.remember(MemoryKind.FAILURE_SIGNATURE,
                     {"c": "t", "q": "a", "m": "r", "n": 2})
    c = mem.remember(MemoryKind.FAILURE_SIGNATURE,
                     {"c": "t", "q": "a", "m": "other", "n": 3})
    got = mem.by_signature("t", "a", "r")
    assert len(got) == 2, "同三元组应聚成类"
    assert a in got and b in got and c not in got


def test_by_zone_and_chain(mem):
    """意图: 按区/按链检索。"""
    t = mem.remember(MemoryKind.TRACE, {"n": 1}, chain_id="CH1")
    mem.remember(MemoryKind.TRACE, {"n": 2}, chain_id="CH2")
    assert len(mem.by_zone(Zone.PROXY)) == 2
    assert [n.node_id for n in mem.by_chain("CH1")] == [t]


def test_index_plans_use_indexes(mem):
    """★ 判据 S4 的同款: 索引要有真实查询消费点。"""
    mem.remember(MemoryKind.TRACE, {"n": 1})
    mem.remember(MemoryKind.FAILURE_SIGNATURE, {"c": "t", "q": "a", "m": "r"})
    for sql, params, want in (
        ("SELECT node_id FROM memory_node WHERE zone=?", ("proxy",), "ix_node_zone"),
        ("SELECT node_id FROM memory_node WHERE chain_id=?", ("CH1",), "ix_node_chain"),
        ("SELECT node_id FROM failure_sig WHERE c=? AND q=? AND m=?",
         ("t", "a", "r"), "ix_sig_cluster"),
    ):
        plan = mem._conn.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
        details = [r["detail"] for r in plan]
        assert any(want in d for d in details), \
            "%s 应走 %s，实为: %s" % (sql[:40], want, details)


def test_get_missing_raises(mem):
    """意图: 读不存在的记忆必须 raise（不许返回空对象）。"""
    with pytest.raises(MemoryError):
        mem.get("nope")


# ══════════════════════════════════════════════════════════
# P1 · 器官纪律
# ══════════════════════════════════════════════════════════

def test_no_driver_interface(mem):
    """★★ 判据 S3/P1: 记忆内核不许驱动进化。"""
    for banned in ("evolve", "run_next", "step", "trigger", "advance",
                   "prune", "evict"):
        assert not hasattr(mem, banned), \
            "记忆内核出现 %r —— 淘汰决策属 evolver（D8/GAI dials）" % banned


def test_node_is_frozen(mem):
    """意图: MemoryNode 不可变。"""
    nid = mem.remember(MemoryKind.TRACE, {"n": 1})
    n = mem.get(nid)
    with pytest.raises(Exception) as e:
        n.access_count = 99
    assert "frozen" in str(e.value).lower() or "assign" in str(e.value).lower()


def test_chain_link_is_preserved(mem):
    """★★ 意图: 记忆记住自己属于哪条链（可反查"这次进化留下了什么"）。"""
    nid = mem.remember(MemoryKind.SKILL,
                       {"scene": "x", "method": "y", "boundary": "z",
                        "invalid_conditions": ["u"], "recovery_strategies": ["v"]},
                       chain_id="CH42")
    assert mem.get(nid).chain_id == "CH42"
    assert [n.node_id for n in mem.by_chain("CH42")] == [nid]


# ══════════════════════════════════════════════════════════
# R21 · 七管枚举完整性（补 recall/dream 后新增）
# ══════════════════════════════════════════════════════════

def test_tube_has_all_seven():
    """★★★ 意图: Tube 枚举必须齐全七管。

    ★★★ R21 修正: 初版只有 5 个（漏 recall/dream）——
      而它们恰好是"七管比 ARSI 多出来的那部分"
      ⇒ 漏掉它们等于把七管悄悄缩成了五管。
    """
    assert {t.value for t in Tube} == {
        "remember", "recall", "learn", "reflect", "evolve", "dream",
        "maintain"}


def test_recall_is_a_tube_and_the_d7_path(mem):
    """★★★ 意图: recall 必须在管体系内，且它是 D7 的执行管。

    ★★★ 我 R19 曾以"recall 是读侧所以不算管"把它排除——
      而那个理由是错的: 母巢的病恰恰是"写入多、读取少"（98.8% access=0）
      ⇒ 把读操作排除在管外，等于把病根排除在设计之外。
    """
    assert Tube.RECALL in list(Tube)
    nid = mem.remember(MemoryKind.TRACE, {"a": 1})
    assert mem.get(nid).tube is not Tube.RECALL, "recall 不该写入记忆（它不摄入）"
    n = mem.recall(nid)
    assert n.access_count == 1, "recall 必须留 access 痕迹（否则 D7 无法执行）"


def test_no_dead_tube_values():
    """★★ 意图: 枚举里的每一管都必须有真实写入路径（防死枚举值）。

    ★★ 与 D8「机制零引用即违规」同款纪律 ——
      R21 实测发现 maintain/dream 曾在枚举里却从未被使用。
    """
    import inspect
    from dwc.organs import memory as M
    src = inspect.getsource(M)
    used = {t.name for t in Tube if ("Tube." + t.name) in src}
    # RECALL / DREAM / MAINTAIN 通过方法名体现（recall() / dream() / maintain_*）
    for name, marker in (("RECALL", "def recall"),
                         ("DREAM", "def dream"),
                         ("MAINTAIN", "def maintain")):
        assert marker in src, "管 %s 在枚举里但没有实现（死枚举值）" % name
    assert used, "至少要有管被显式引用"

# ══════════════════════════════════════════════════════════
# R22 · 死结修复：dream 的 access 门槛 + 检索层
# ══════════════════════════════════════════════════════════

def _sig(mk, c, q, m, detail=None):
    p = {"c": c, "q": q, "m": m}
    if detail:
        p["detail"] = detail
    return mk.remember(MemoryKind.FAILURE_SIGNATURE, p)


def test_starvation_broken_by_waiver(mem):
    """★★★ 核心回归: 跨簇唯一 + 从未被召回 ⇒ 仍能归纳出技能。

    ★★★ 这个病是我实测出来的（不是推理）:
      dream 要 access>0 · access 只由 recall 增加
      · recall 要先知道查什么 · 而旧代码只有 by_signature(三元组)
      · 三元组只有失败现场才知道
      ⇒⇒ "没失败过就查不到 → 查不到就永远没 access → 永远没技能"
    """
    _sig(mem, "timeout", "agent", "retry_bomb", "重试7次")
    d = mem.dream("timeout", "agent", "retry_bomb")
    assert d["eligible"] is True, "唯一签名不该被 access 门槛卡住"
    assert d["waiver"] == "unique_signature"
    assert d["candidate_skill"] is not None


def test_waiver_not_granted_when_mechanism_common(mem):
    """★★★ 意图: 同一机制在别处也出现 ⇒ **不豁免**。

    ★★★ 这是 R22.1/R22.2 连续两次修正的产物:
      初版用「簇内只有一条」⇒ 几乎恒真 ⇒ waiver 变成万能借口
        ⇒⇒ 那比原来的饿死更坏（D7 判据形同虚设）
      ⇒★ 正确判据: **抽象机制 m 在全库只出现一次**
    """
    _sig(mem, "timeout", "a", "common_bug", "x")
    _sig(mem, "timeout", "b", "common_bug", "y")   # 同一 m，不同 q
    d = mem.dream("timeout", "a", "common_bug")
    assert d["waiver"] is None, "常见机制不该豁免（否则 waiver 成万能借口）"
    assert d["eligible"] is False, "无豁免且没人用 ⇒ 归纳不出技能"


def test_waiver_reason_is_auditable(mem):
    """★★ 意图: 豁免必须带可审计的理由（否则会变成万能借口）。"""
    _sig(mem, "x", "y", "rare_mech", "d")
    d = mem.dream("x", "y", "rare_mech")
    assert "跨簇唯一" in d["why"] or "唯一" in d["why"]
    assert d["why"], "理由不得为空"


def test_used_memory_takes_normal_path(mem):
    """意图: 被召回过的走常规路径，不看 waiver。"""
    a = _sig(mem, "oom", "mem", "leak", "爆了")
    _sig(mem, "oom", "mem", "other", "爆2")
    mem.recall(a)
    d = mem.dream("oom", "mem", "leak")
    assert d["eligible"] and d["n_used"] == 1
    assert d["waiver"] is None, "有 access 就该走常规路径"


def test_dream_on_empty_cluster(mem):
    """意图: 空簇不产出，且返回结构完整（含 waiver 字段）。"""
    d = mem.dream("a", "b", "c")
    assert d["eligible"] is False and d["n_members"] == 0
    assert "waiver" in d, "返回结构必须一致（空簇也要有 waiver 键）"


def test_recall_search_finds_by_scene(mem):
    """★★★ 意图: 检索的入口是**场景词**，不是三元组。

    ★★★ 这才是死结的真正破法 —— 因为三元组只有失败现场才知道，
      而场景词在失败**发生前**就有（要修什么 bug）。
    """
    mem.remember(MemoryKind.TRACE,
                 {"scene": "修 timeout bug", "action": "retry"})
    _sig(mem, "timeout", "agent", "retry_bomb", "重试7次")
    hits = mem.recall_search("timeout", ["retry_bomb"])
    assert len(hits) == 2, "场景词应同时命中痕迹与失败签名"


def test_recall_search_is_pure(mem):
    """★★ 意图: recall_search **不记 access**（它是纯查询，可反复用）。"""
    mem.remember(MemoryKind.TRACE, {"scene": "s", "action": "a"})
    for _ in range(3):
        mem.recall_search("s", ["a"])
    n = mem.get(mem.by_zone(Zone.PROXY)[0].node_id)
    assert n.access_count == 0, "纯查询不该改证据（否则检索实验会污染 D7）"


def test_recall_many_records_access(mem):
    """★★ 意图: recall_many 才记 access（Tube.RECALL 的完整语义）。"""
    t = mem.remember(MemoryKind.TRACE, {"scene": "s2", "action": "a2"})
    hits = mem.recall_many("s2", ["a2"])
    assert any(h.node_id == t for h in hits)
    assert mem.get(t).access_count == 1, "取回后 access 必须 +1（§2.2② 判据）"


def test_recall_search_empty_returns_empty(mem):
    """意图: 查不到返回空列表（不 raise）。"""
    mem.remember(MemoryKind.TRACE, {"scene": "x"})
    assert mem.recall_search("完全无关的词") == []


def test_maintain_holds_never_recalled(mem):
    """★★★ 意图: 未召回的记忆**一律不处置**（第1层，不可换序）。"""
    for i in range(3):
        mem.remember(MemoryKind.TRACE, {"n": i})
    r = mem.maintain()
    assert r["n_held"] == 3 and r["n_archived"] == 0
    assert len(r["held_never_recalled"]) == 3
    assert "recall 管要修" in r["hint"], "审计要点要指向检索而非记忆该删"


def test_maintain_protects_rare_signature(mem):
    """★★ 意图: 稀有保护是硬否决（第3层）。"""
    _sig(mem, "c1", "q1", "m1", "d")
    mem.recall(mem.by_signature("c1", "q1", "m1")[0])
    r = mem.maintain()
    assert r["n_protected"] >= 1
    assert mem.get(r["protected_rare"][0]).zone is not Zone.ARCHIVE, \
        "唯一签名不许被归档"
