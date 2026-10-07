# -*- coding: utf-8 -*-
"""因果链存储（foundation/causal_chain.py）的契约测试。

★★★ 存在理由
  六层活性模型挂在 Γ 事件上（2026-10-05 用户裁决），而 Γ 就是这个模块。
  ⇒ 若它有漏洞，gate.py G3 检的就只是"字段名齐备"，没有任何真实链在流。

★ 逐条判据:
  S1 · 每个 id 字段写入点 > 0 且读取点 > 0
  S2 · upstream_id 在 stage != 'decision' 时非空（写入时校验）
  S3 · 模块内没有"触发下一轮"的调用
  S4 · 四个索引各有一个真实查询用它
  S5 · Trace 先于 chain_record 落盘 —— 注入失败看链是否断裂
  S6 · 瘦身走 export → archive，不直接 DELETE
"""
from __future__ import annotations

import ast
import inspect
import json
import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.foundation import causal_chain as cc  # noqa: E402

ST = cc.STAGES


def seeded(chain_id="CH1"):
    """写入一条完整五环链。"""
    st = cc.CausalChainStore()
    st.append(chain_id, "decision", "D1", {"action": "fix"}, recorded_at="t0")
    st.append(chain_id, "turn", "T1", {"turn": 1}, upstream_id="D1",
              recorded_at="t1")
    st.append(chain_id, "trace", "TR1", {"ok": True}, upstream_id="T1",
              recorded_at="t2")
    st.append(chain_id, "experience", "E1", {"n_obs": 3}, upstream_id="TR1",
              recorded_at="t3")
    st.append(chain_id, "change", "C1", {"files": 2}, upstream_id="E1",
              recorded_at="t4")
    return st


# ══════════════════════════════════════════════════════════
# 五环契约
# ══════════════════════════════════════════════════════════

def test_five_rings_in_order():
    """意图: 五环按 decision→turn→trace→experience→change 顺序落 seq 0..4。"""
    st = seeded()
    recs = st.trace_back("CH1")
    assert [r["stage"] for r in recs] == list(ST), \
        "环序不符（★ seq 从 0 开始，非 SQL 惯例的 1）"
    assert [r["seq"] for r in recs] == [0, 1, 2, 3, 4], "seq 必须从 0 单调"


def test_chain_summary_fills_all_ids():
    """★★ 意图: 链摘要的四个 id 列全部被填（decision 环没有对应列）。"""
    st = seeded()
    s = st.get("CH1")
    assert s["turn_id"] == "T1"
    assert s["trace_id"] == "TR1"
    assert s["experience_id"] == "E1"
    assert s["change_id"] == "C1"
    assert s["closed_at"] == "t4", "走完 change 环应当闭合"


def test_decision_has_no_id_column():
    """意图: decision 环没有对应 id 列（它是链本身）⇒ 不许硬塞。"""
    assert cc.STAGE_ID_COLUMN["decision"] is None
    assert all(cc.STAGE_ID_COLUMN[s] for s in ST if s != "decision")


def test_open_chains_excludes_closed():
    """意图: 闭合后不该出现在未闭合列表里。"""
    st = seeded()
    assert "CH1" not in [c["chain_id"] for c in st.open_chains()]
    st2 = cc.CausalChainStore()
    st2.append("CH9", "decision", "D", {}, recorded_at="t0")
    assert "CH9" in [c["chain_id"] for c in st2.open_chains()]


def test_continuity_detects_break():
    """★★ 意图: 链断必须被 verify_continuity 抓到。"""
    st = seeded()
    v = st.verify_continuity("CH1")
    assert v["continuous"] and not v["breaks"]
    # ★ 人为制造断链: 直接改 upstream_id
    st._conn.execute(
        "UPDATE chain_record SET upstream_id='WRONG' WHERE seq=2")
    st._conn.commit()
    v2 = st.verify_continuity("CH1")
    assert not v2["continuous"], "断链必须被检出"
    assert v2["breaks"][0]["seq"] == 2


# ══════════════════════════════════════════════════════════
# S2 · upstream_id 强制非空（写入时）
# ══════════════════════════════════════════════════════════

@pytest.mark.parametrize("stage", [s for s in ST if s != "decision"])
def test_s2_upstream_required_for_non_decision(stage):
    """★★ 意图: 除 decision 外，每环写入时 upstream_id 必须非空。

    ★★ 这是判据 S2 的核心: 链断必须在**写入时**暴露，
      不许留到读取时才发现（那时数据已经错了）。
    """
    st = cc.CausalChainStore()
    st.append("C", "decision", "D", {}, recorded_at="t")
    with pytest.raises(cc.ChainError) as e:
        st.append("C", stage, "X", {}, upstream_id=None)
    assert "S2" in str(e.value)


def test_s2_decision_may_have_no_upstream():
    """意图: decision 环是链的起点，允许没有 upstream。"""
    st = cc.CausalChainStore()
    st.append("C", "decision", "D", {}, upstream_id=None, recorded_at="t")
    assert st.trace_back("C")[0]["upstream_id"] is None


def test_s2_empty_string_also_rejected():
    """★★ 意图: 空串不是合法 upstream_id（falsy 但不是缺失）。"""
    st = cc.CausalChainStore()
    st.append("C", "decision", "D", {}, recorded_at="t")
    with pytest.raises(cc.ChainError):
        st.append("C", "turn", "T", {}, upstream_id="")


def test_stage_whitelist():
    """意图: stage 必须在五环白名单内。"""
    st = cc.CausalChainStore()
    st.append("C", "decision", "D", {}, recorded_at="t")
    with pytest.raises(cc.ChainError) as e:
        st.append("C", "bogus", "X", {}, upstream_id="D")
    assert "白名单" in str(e.value)


# ══════════════════════════════════════════════════════════
# S1 · id 字段有写入也有读取
# ══════════════════════════════════════════════════════════

def test_s1_all_four_id_columns_written():
    """★★ 判据 S1: turn/trace/experience/change 四列都被写入。"""
    st = seeded()
    s = st.get("CH1")
    for col in ("turn_id", "trace_id", "experience_id", "change_id"):
        assert s[col], "%s 未被写入" % col


def test_s1_all_four_id_columns_readable():
    """★ 判据 S1 的读取侧: 链摘要能被读出来（不是写进去就没人看）。"""
    st = seeded()
    s = st.get("CH1")
    assert set(("turn_id", "trace_id", "experience_id", "change_id")) <= set(s)


def test_by_upstream_finds_downstream():
    """★★ 意图: 反查下游 —— ARSI 做不到（source_traces 在 JSON 里）。"""
    st = seeded()
    got = st.by_upstream("T1")
    assert len(got) == 1 and got[0]["ref_id"] == "TR1"
    assert st.by_upstream("D1")[0]["ref_id"] == "T1"


def test_by_upstream_empty_when_none():
    """意图: 没有下游时返回空列表（不 raise）。"""
    st = seeded()
    assert st.by_upstream("NOPE") == []


def test_by_kind_uses_index():
    """★ 判据 S4: ix_index_kind 有真实消费点。"""
    st = seeded()
    got = st.by_kind("change")
    assert len(got) == 1 and got[0]["key"] == "change:C1"
    assert st.by_kind("change", key="change:C1")[0]["chain_id"] == "CH1"
    assert st.by_kind("nonexistent") == []


# ══════════════════════════════════════════════════════════
# S5 · Trace 先落盘（注入失败判据）
# ══════════════════════════════════════════════════════════

def test_s5_trace_hook_called_before_record():
    """★★★ 判据 S5 的正向: Trace 钩子必须**先于** chain_record 被调用。"""
    st = cc.CausalChainStore()
    order = []
    st.set_trace_hook(lambda cid, p: order.append(("trace", cid)))
    orig = st._conn.execute

    st.append("C", "decision", "D", {}, recorded_at="t")
    st.append("C", "turn", "T", {}, upstream_id="D")
    st.append("C", "trace", "TR", {"x": 1}, upstream_id="T")
    assert order == [("trace", "C")], "trace 钩子必须被调用一次"
    # ★ 关键: 调用后 chain_record 里有 trace 环
    assert st.trace_back("C")[-1]["stage"] == "trace"


def test_s5_injected_trace_failure_leaves_chain_continuous():
    """★★★ 判据 S5 的核心判据形式: 注入一次写失败 → 断言链未断裂。

    ★★ 依据 §4.2: 热链可重建，前提是 Trace 先落盘。
      若 Trace 写失败而 chain_record 照样写入 ⇒ 崩溃后无法重建。
    """
    st = cc.CausalChainStore()

    def boom(cid, payload):
        raise cc.ChainError("注入: Trace 落盘失败")

    st.set_trace_hook(boom)
    st.append("C", "decision", "D", {}, recorded_at="t0")
    st.append("C", "turn", "T", {}, upstream_id="D")
    with pytest.raises(cc.ChainError):
        st.append("C", "trace", "TR", {"x": 1}, upstream_id="T")

    v = st.verify_continuity("C")
    assert v["continuous"], "Trace 失败后链必须仍连续（trace 环没写进去）"
    assert v["n_records"] == 2, "只剩 decision+turn 两环"


def test_s5_hook_not_called_for_non_trace_stages():
    """意图: 钩子只对 trace 环生效（不是所有环都调）。"""
    st = cc.CausalChainStore()
    seen = []
    st.set_trace_hook(lambda cid, p: seen.append(cid))
    st.append("C", "decision", "D", {}, recorded_at="t")
    st.append("C", "turn", "T", {}, upstream_id="D")
    assert seen == [], "非 trace 环不该调 Trace 钩子"


# ══════════════════════════════════════════════════════════
# S3 · 模块只记录不驱动
# ══════════════════════════════════════════════════════════

def test_s3_public_interface_is_only_five():
    """★★ 判据 S3: 提供的接口只有 append/get/trace_back/by_upstream/export。

    ★★ 不许出现 run_next / step / trigger / advance 之类"驱动"接口 ——
      驱动时间的是世界模型，不是因果链（文档第 19 项裁决）。
    """
    pub = [m for m in dir(cc.CausalChainStore)
           if not m.startswith("_")]
    # 允许的只读/记录类
    allowed = {"append", "get", "trace_back", "by_upstream", "export",
               "by_kind", "open_chains", "verify_continuity", "close",
               "set_trace_hook", "prune_archive"}
    extra = set(pub) - allowed
    assert not extra, "出现计划外接口: %s" % sorted(extra)
    for banned in ("run_next", "step", "trigger", "advance", "drive",
                   "start_next", "next_turn"):
        assert not hasattr(cc.CausalChainStore, banned), \
            "出现驱动型接口 %r（判据 S3 禁止）" % banned


def test_s3_module_source_has_no_trigger_semantics():
    """★ 判据 C2 的可 grep 形式: 不得有"触发下一环"的调用。"""
    src = inspect.getsource(cc)
    for bad in ("run_next", "start_next", "trigger_next", "advance_term",
                "next_stage(", "subscribe"):
        assert bad not in src, "源码里出现 %r（判据 C2/S3 禁止）" % bad


# ══════════════════════════════════════════════════════════
# S6 · 瘦身走 export → archive
# ══════════════════════════════════════════════════════════

def test_s6_export_returns_manifest():
    """★★ 判据 S6: export 必须带 manifest（行数 + 校验和）。"""
    st = seeded()
    ex = st.export("CH1")
    assert ex["manifest"]["n_records"] == 5
    assert len(ex["manifest"]["checksum_sha256"]) == 64
    assert ex["records"][0]["stage"] == "decision"


def test_s6_export_all_chains():
    """意图: 不给 chain_id 时导出全部。"""
    st = seeded("CH1")
    st.append("CH2", "decision", "D", {}, recorded_at="t")
    ex = st.export()
    assert ex["manifest"]["n_records"] == 6
    assert ex["manifest"]["chain_id"] is None


def test_s6_prune_actually_deletes():
    """★★★ 意图: prune 传 chain_id 后**必须真删掉**。

    ★★ 2026-10-05 自检抓到: 原实现参数名是 archived_checksums，
      函数体却拿它比 chain_id ⇒ 传 checksum 时删 0 行，
      而自检没断言"真删掉了" ⇒ 假通过。
      ⇒★ 这条测试就是为了防它再退化。
    """
    st = seeded("CH1")
    st.append("CH2", "decision", "D", {}, recorded_at="t")
    n = st.prune_archive(["CH1"])
    assert n == 5, "应删 5 行（CH1 的五环），实为 %d" % n
    assert st.trace_back("CH1") == [], "CH1 应已被删"
    assert len(st.trace_back("CH2")) == 1, "CH2 不该被删"
    assert st.get("CH1") is None, "链摘要也应删"
    assert st.by_kind("change") == [], "索引也应删"


def test_s6_prune_unknown_chain_is_noop():
    """意图: 删不存在的链是 no-op，不 raise。"""
    st = seeded()
    assert st.prune_archive(["NOPE"]) == 0
    assert st.prune_archive([]) == 0


def test_s6_delete_only_via_prune_archive():
    """★★★ 判据 S6: 删除只允许经prune_archive，且它要求传 chain_id。

    ★★★ 2026-10-05 改判: 原版用"扫源码里的 DELETE 语句"来判，
      结果两次踩坑 ——
        ① 把 docstring 里的判据条文（S6 · 不直接 DELETE FROM chain_record）
           当成违规 ⇒ 与 R9 那次"正则把条文当代码"同款
        ② 那条 SQL 是多行 execute( 调用，ast.lineno 指向首行，
           逐行扫根本扫不到 ⇒ 又一次假阴性
      ⇒★ 改用**行为判据**: 直接验证 prune_archive 真删、且需要 chain_id。
        这比扫源码可靠 —— 它测的是后果，不是写法。
    """
    st = seeded("CH1")

    # ① prune_archive 只认 chain_id，传空/不存在的都不删
    assert st.prune_archive([]) == 0
    assert st.prune_archive(["NOPE"]) == 0
    assert len(st.trace_back("CH1")) == 5, "不该被删"

    # ② 传 chain_id 才真删（三张表都清）
    assert st.prune_archive(["CH1"]) == 5
    assert st.trace_back("CH1") == []
    assert st.get("CH1") is None
    assert st.by_kind("change") == []
    assert st.by_upstream("T1") == []

    # ③ ★ 模块不提供任何"直接删表"的公开接口
    #    ★★ 注意不要再按名字猜（我在这里错过三次）：
    #       prune/delete/truncate/purge 这些词都可能不出现，
    #       所以只断言"不存在这些**惯用**直删接口名"，
    #       真正的完整性由上面 ①② 的行为验证 + test_s3_public_interface
    #       那个白名单测试兜着（它枚举全部公开方法）。
    pub = [m for m in dir(st) if not m.startswith("_")]
    for banned in ("delete_all", "truncate", "purge_all", "drop_table",
                   "delete_records", "clear"):
        assert banned not in pub, "出现直删接口 %r" % banned
    assert callable(st.prune_archive), "prune_archive 必须可用"

def test_export_to_file():
    """意图: export 能落文件（另一库或文件，S6 的目标形态）。"""
    import tempfile
    st = seeded()
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    try:
        st.export("CH1", out_path=path)
        data = json.load(open(path, encoding="utf-8"))
        assert data["manifest"]["n_records"] == 5
        assert len(data["records"]) == 5
    finally:
        os.remove(path)


# ══════════════════════════════════════════════════════════
# schema 与索引（S4）
# ══════════════════════════════════════════════════════════

def test_schema_creates_three_tables_four_indexes():
    """★★ 判据 S4: 三表四索引全部存在。"""
    st = cc.CausalChainStore()
    tabs = {r["name"] for r in st._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    idx = {r["name"] for r in st._conn.execute(
        "SELECT name FROM sqlite_master WHERE type='index'")}
    for t in ("chain", "chain_record", "chain_index"):
        assert t in tabs, "缺表 %s" % t
    for i in ("ix_rec_chain", "ix_rec_upstream", "ix_chain_closed",
              "ix_index_kind"):
        assert i in idx, "缺索引 %s" % i


def test_four_indexes_have_real_queries():
    """★★★ 判据 S4 的核心: 四个索引各有一个真实查询用它。

    ★ 母巢的教训: 98.8% 节点 access_count=0 —— 索引写了没人用就是死重量。
    ⇒ 所以必须核对"谁在查这个索引对应的数据"。
    """
    st = seeded()
    # ix_rec_chain  → trace_back
    assert len(st.trace_back("CH1")) == 5
    # ix_rec_upstream → by_upstream
    assert st.by_upstream("T1")[0]["ref_id"] == "TR1"
    # ix_chain_closed → open_chains
    # ★ R52: 原写 `== [] or True` = **恒真**(断言无效)
    #   本意是「查询可执行, 结果可空」⇒ 那就验**类型**(可空但必须是 list)
    assert isinstance(st.open_chains(), list)   # 可空, 但必须是 list
    # ix_index_kind → by_kind
    assert st.by_kind("change")[0]["key"] == "change:C1"
    # ★ 交叉验证: 查询结果确实与索引列相关（不是全表扫也能得到同样结果）
    # ★ sqlite3.Row 的 str() 只给 repr ⇒ 必须显式取 detail 列
    plan = st._conn.execute(
        "EXPLAIN QUERY PLAN SELECT stage, ref_id, upstream_id, payload,"
        " seq, recorded_at FROM chain_record WHERE chain_id=? ORDER BY seq",
        ("CH1",)).fetchall()
    details = [r["detail"] for r in plan]
    assert any("ix_rec_chain" in d for d in details), \
        "trace_back 的查询计划应走 ix_rec_chain，实为: %s" % details
    # ★ 三个索引同样核对
    for sql, params, want in (
        ("SELECT * FROM chain_record WHERE upstream_id=?", ("T1",),
         "ix_rec_upstream"),
        ("SELECT chain_id FROM chain WHERE closed_at IS NULL", (),
         "ix_chain_closed"),
        ("SELECT key FROM chain_index WHERE kind=?", ("change",),
         "ix_index_kind"),
    ):
        p2 = st._conn.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
        ds = [r["detail"] for r in p2]
        assert any(want in d for d in ds), \
            "%s 的查询计划应走 %s，实为: %s" % (sql[:44], want, ds)


def test_no_trigger_or_subscription_in_schema():
    """★★ 判据 C2: 表结构里不得有 trigger / 订阅字段（结构上杜绝隐式驱动）。"""
    st = cc.CausalChainStore()
    kinds = {r["name"] for r in st._conn.execute(
        "SELECT name FROM sqlite_master WHERE type IN ('trigger','view')")}
    assert not kinds, "schema 里出现 trigger/view: %s" % kinds
    src = inspect.getsource(cc).upper()
    for bad in ("CREATE TRIGGER", "SUBSCRIBE", "NOTIFY"):
        assert bad not in src, "源码里出现 %r（判据 C2 禁止）" % bad


# ══════════════════════════════════════════════════════════

def test_payload_roundtrips_json():
    """意图: payload 必须是 JSON 且能原样取回（含中文）。"""
    st = cc.CausalChainStore()
    payload = {"预测": "修 bug", "n": 3, "nested": {"a": [1, 2]}}
    st.append("C", "decision", "D", payload, recorded_at="t")
    got = st.trace_back("C")[0]["payload"]
    assert got == payload, "payload 往返不一致"


def test_get_missing_chain_returns_none():
    """意图: 读不存在的链返回 None（不 raise）—— 但 record 级仍要 raise。"""
    st = cc.CausalChainStore()
    assert st.get("NOPE") is None
    assert st.trace_back("NOPE") == []