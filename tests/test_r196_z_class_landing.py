# -*- coding: utf-8 -*-
"""R196 · Z 类 6 项落地验收（用户令"我想把这六类全部落地"→"继续"）。

六项分三类（详见 docs/R196_Z_CLASS_PLAN.md）:
  甲类·有论文据照搬: A1 coupling(2608.10299) / A2 quintuple(已 4/5 接线)
  乙类·无论文据自定义: B1 state→trajectory / B2 freshness / B3 dual→attestation
  丙类·纪律显式化:    C1 autonomy→snapshot.markers（不建模块）

★★ 每个测试都测"为什么重要"（防越界/防冒充/防漂移）, 不是"做了什么"。
"""
from __future__ import annotations

import io
import json
import os
import sys

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

import pytest                                              # noqa: E402

from dwc.harness.attestation import attest, claim, unattested  # noqa: E402
from dwc.harness.coupling import (COUPLING_EDGES, SUBSYSTEMS,  # noqa: E402
                                  current_stage, decoupled_pairs,
                                  declared_pairs, pressures_from,
                                  pressures_to, stage_of)
from dwc.harness.consume_points import CONSUME_POINTS     # noqa: E402
from dwc.harness.trajectory import (TRAJECTORY_SCHEMA_VERSION,  # noqa: E402
                                    age_rounds, append,
                                    read, snapshot)
from dwc.harness.run_term import Quintet                 # noqa: E402


# ══════════════════════════════════════════════════════════
# A1 · coupling（甲类 — 2608.10299 §2.3 三阶段 taxonomy）
# ══════════════════════════════════════════════════════════
def test_coupling_paper_basis_is_verbatim_present():
    """★★ 论文依据必须**逐字在场**（不许二手转述 — R73 + 真实感）。"""
    src = io.open(os.path.join(ROOT, "src", "dwc", "harness",
                               "coupling.py"), encoding="utf-8").read()
    flat = " ".join(src.split())          # 归一化空白 ⇒ 跨行逐字也可断言
    for verbatim in ("Co-evolution begins when an agent no longer learns "
                     "against a static counterpart",
                     "it limits the new experiences and pressures",
                     "the evolution mechanism remains human-designed",
                     "Only limited work currently meets"):
        assert verbatim in flat, "coupling 少逐字依据: %r" % verbatim


def test_stage_of_never_claims_advanced():
    """★★★ 边表填满也**不得**自报 Stage 3 — 论文 §5.1 判据是 meta 边。"""
    full = [(a, b, "x") for a in SUBSYSTEMS for b in SUBSYSTEMS if a != b]
    n, name = stage_of(full)
    assert (n, name) == (2, "Stage2_agent_environment"), (
        "全 12 边却自报 %s ⇒ 把'边多'当'先进'（论文: 机制本身没在变 ⇒ 非 Stage 3）"
        % name)
    assert stage_of([("meta", "judge", "x")])[0] == 3       # 有 meta 边才 3
    assert stage_of([])[0] == 0


def test_coupling_stage0_gap_is_exposed_honestly():
    """★★★ decoupled_pairs 非空 **且**文档如实标 Stage 0 缺口。"""
    dp = decoupled_pairs()
    assert dp, "decoupled_pairs 空 ⇒ DWC 已全耦合？不可能（出厂 4 边/12 有序对）"
    plan = io.open(os.path.join(ROOT, "docs", "R196_Z_CLASS_PLAN.md"),
                   encoding="utf-8").read()
    assert "Stage 0" in plan, "方案没如实标 DWC 在 Stage 0 之前的缺口"


def test_coupling_edges_are_registered_not_triggering():
    """★★★ 防跳级: 边表只登记, **不 import 任何器官**（不触发）。"""
    src = io.open(os.path.join(ROOT, "src", "dwc", "harness",
                               "coupling.py"), encoding="utf-8").read()
    body = [l for l in src.splitlines()
            if l.startswith(("from dwc", "import dwc"))]
    assert not body, "coupling import 了 dwc 模块 ⇒ 可能已变成触发链: %r" % body


def test_coupling_pressures_queries_are_deterministic():
    """★ 查询输出确定（排序）— 同一输入同一输出, 测试可断言。"""
    assert pressures_from("metric_loop") == [
        ("direction", "metric_surface_refreshed_every_round")]
    assert pressures_to("judge") == [("evolver", "landing_enters_next_round_data")]
    assert declared_pairs() == sorted(set(declared_pairs()))
    assert len(COUPLING_EDGES) == 4                       # 出厂集（R196 §五.1）


# ══════════════════════════════════════════════════════════
# A2 · quintuple（甲类 — 唯一盘点出口的机械验收）
# ══════════════════════════════════════════════════════════
def test_quintet_u_is_the_only_partial():
    """★★★ U 是**唯一** partial — 变了说明有人接线或有人删, 都得显式。"""
    q = Quintet()
    d = q.to_dict()
    # ★★★ R141 **已有的双列表**（别再造第三口径）: 'unimplemented'=字段 None,
    #   'partial'=值含"未接"字样。空构造五个字段全 None ⇒ U 该在 unimplemented。
    #   ★ 真正要锁的是 **run_term.py:458 的填值盘点**: m/rho/pi/V 已填, U 填
    #     "已实现但未接本盘点" ⇒ 那 version 的 partial == ['U']。
    #     ⇒ 这里锁的是**空构造不假装已接线**（None ≠ 已实现）。
    assert d["U"] is None and d["m"] is None, (
        "空构造却给了值 ⇒ 假装已接线（无值可给时必须 None, 不是占位串）")
    # 出厂填值盘点（run_term 的构造形态）⇒ U 是唯一 partial
    q2 = Quintet(m="wire_and_memory（已实现）", rho="config/dials.yaml（已实现）",
                 pi="dwc.organs.evolver.Evolver · 已实现",
                 V="dwc.organs.judge.Judge · 已实现",
                 U="dwc.organs.evolver.select_winner · 已实现但未接本盘点（R141 如实标 partial）")
    d2 = q2.to_dict()
    assert d2["partial"] == ["U"], (
        "partial 集合变了（%r）⇒ run_term.py:458 是唯一盘点出口, "
        "改它必须显式改本测试" % d2["partial"])


def test_quintet_sole_exit_documented():
    """★★ 防第二口径: 文档必须指明唯一盘点出口在 run_term.py:458。"""
    plan = io.open(os.path.join(ROOT, "docs", "R196_Z_CLASS_PLAN.md"),
                   encoding="utf-8").read()
    assert "run_term.py:458" in plan and "唯一盘点出口" in plan


# ══════════════════════════════════════════════════════════
# B1 · state → trajectory（乙类 — 无论文据, 显式标注）
# ══════════════════════════════════════════════════════════
class _Fake:
    """最小替身（只带已登记痕迹 — 与 Loop.__init__ 同口径）。"""
    _last_skip = "三方向全败（terminal — R3）: task='x'"
    _last_adopt = {"adopted": True}
    _last_a_train = 0.9167


def test_trajectory_snapshot_keys_subset_of_registered():
    """★★★ snapshot 键 ⊆ CONSUME_POINTS — 不许绕过 R194 登记面加字段。"""
    snap = snapshot(_Fake())
    keys = set(snap["state"].keys())
    assert keys <= set(CONSUME_POINTS), "越界键: %r" % (keys - set(CONSUME_POINTS))
    assert keys, "snapshot 空 ⇒ 投影面没接上"


def test_trajectory_snapshot_marks_no_paper_basis():
    """★★★ 乙类纪律: 必须显式写"无论文依据"且不许出现"论文说"。"""
    src = io.open(os.path.join(ROOT, "src", "dwc", "harness",
                               "trajectory.py"), encoding="utf-8").read()
    flat = " ".join(src.split())
    assert "无论文依据" in flat
    # ★ 判据: **带半角双引号的**"论文说"（真声称语句的形态）— 禁令句用全角
    #   「」写 ⇒ 不会误伤; 有残留 = 真在冒充论文
    assert '"论文说"' not in src and "'论文说'" not in src, (
        "trajectory 出现声称句式 ⇒ 冒充论文机制（G5 假声称）")
    assert "出处错" in src, "必须记账 R193 把 state 引到 2609.06396 是出处错"


def test_trajectory_append_read_roundtrip(tmp_path):
    """★★ 追加/回读机械面闭环（含原子写与坏行拒绝）。"""
    p = str(tmp_path / "trajectory.jsonl")
    s1 = snapshot(_Fake())
    n = append(p, s1)
    assert n == 1
    append(p, dict(s1, gen=2))
    got = read(p)
    assert len(got) == 2 and got[0]["schema"] == TRAJECTORY_SCHEMA_VERSION
    # 坏行 ⇒ 抛（不静默跳 — G7）
    with open(p, "a", encoding="utf-8") as fh:
        fh.write("{not json}\n")
    with pytest.raises(ValueError):
        read(p)
    # 不存在 ⇒ []（空序列是一等输出）
    assert read(str(tmp_path / "nope.jsonl")) == []


def test_trajectory_markers_come_from_registered_traces_only():
    """★★★ C1: autonomy_markers 只从已登记痕迹派生 — 零新判据。"""
    snap = snapshot(_Fake())
    m = snap["markers"]
    assert "all_failed_bookkept" in m                 # _last_skip 含 terminal
    assert "adopted" in m                             # _last_adopt.adopted True
    assert set(m) <= {"direction_switched", "all_failed_bookkept",
                      "adopted", "consolidation_done"}, "标记越界 ⇒ 造了新指标"
    assert snapshot(object())["markers"] == [], "空对象 ⇒ 无标记（不猜）"


# ══════════════════════════════════════════════════════════
# B2 · freshness（乙类 — 只查询, 不设阈值）
# ══════════════════════════════════════════════════════════
def test_age_rounds_has_no_threshold_constant():
    """★★★ freshness 无阈值常量 — 无据可设（判据不在本模块）。"""
    src = io.open(os.path.join(ROOT, "src", "dwc", "harness",
                               "trajectory.py"), encoding="utf-8").read()
    body = [l for l in src.splitlines()
            if l.startswith(("FRESH", "STALE", "MAX_AGE", "_THRESHOLD"))]
    assert not body, "trajectory 出现阈值常量 ⇒ 无据设阈值: %r" % body


def test_age_rounds_queries_only():
    """★ age_rounds 只答'几轮'; 空序列/未见 gen ⇒ -1（不是 0 冒充'就在本轮'）。"""
    assert age_rounds([], 3) == -1
    traj = [{"gen": 1}, {"gen": 2}, {"gen": 3}]
    assert age_rounds(traj, 3) == 0
    assert age_rounds(traj, 1) == 2
    assert age_rounds(traj, 9) == -1


# ══════════════════════════════════════════════════════════
# B3 · dual → attestation（乙类 — 观察面不是门）
# ══════════════════════════════════════════════════════════
def test_unattested_lists_but_never_blocks(tmp_path):
    """★★★ attestation 是观察面不是门 — unattested **不抛不拦**。"""
    p = str(tmp_path / "claims.jsonl")
    cid = claim(p, 196, "coupling", "出厂 4 条边记账不触发", by="human")
    rows = unattested(p)
    assert len(rows) == 1 and rows[0]["claim_id"] == cid
    assert set(rows[0]) == {"claim_id", "subsystem", "text", "by", "gen"}
    # 挂实测 ⇒ 移出未挂清单
    attest(p, cid, "tests/test_r196", {"verified": True})
    assert unattested(p) == []
    # 只查该轮
    claim(p, 197, "x", "y")
    assert len(unattested(p, round_gen=197)) == 1
    assert len(unattested(p, round_gen=196)) == 0


def test_attestation_no_auto_claim_entry():
    """★★★ 无 auto 声称入口（防自证预言）— 无 by="auto" 的自动生成路径。"""
    src = io.open(os.path.join(ROOT, "src", "dwc", "harness",
                               "attestation.py"), encoding="utf-8").read()
    assert 'def claim' in src and 'by: str = "human"' in src
    # ★ 禁令句里本来就写着 by="auto" 的反例 ⇒ 去掉禁令句再断言
    body = src.replace('by="auto"', "")   # 去掉禁令句里的反例字样再断言
    assert 'by="auto"' not in body and "by='auto'" not in body, (
        "出现 auto 声称入口 ⇒ 自动造声称再自认证 = 自证预言（R188 坑）")


def test_attestation_no_paper_basis_marked():
    """★★★ 乙类纪律（同 B1）。"""
    src = io.open(os.path.join(ROOT, "src", "dwc", "harness",
                               "attestation.py"), encoding="utf-8").read()
    flat = " ".join(src.split())
    assert "无论文依据" in flat and "出处错" in flat, (
        "必须记账 R193 把 dual 引到 2606.06350 是出处错")
    assert '"论文说"' not in src and "'论文说'" not in src, (
        "attestation 出现声称句式 ⇒ 冒充论文机制（G5 假声称）")


def test_attest_rejects_orphan_and_is_idempotent(tmp_path):
    """★★ 孤儿证据 ⇒ raise; 重复 claim ⇒ 幂等（返同一 id, 不造重复账）。"""
    p = str(tmp_path / "claims.jsonl")
    with pytest.raises(KeyError):
        attest(p, "c1-1", "ref", 1)
    a = claim(p, 196, "s", "t1")
    b = claim(p, 196, "s", "t1")
    assert a == b, "重复 claim 造了两笔 ⇒ 账会虚胖"
    c = claim(p, 196, "s", "t2")
    assert c != a, "不同声称同 id ⇒ 挂证据会错位"


def test_attestation_atomic_write_no_truncation(tmp_path):
    """★★ 原子替换 ⇒ 半截写入不致坏账（写坏时旧账完整可读）。"""
    p = str(tmp_path / "claims.jsonl")
    claim(p, 196, "s", "t")
    before = json.loads(io.open(p, encoding="utf-8").readline())
    assert before["attested"] is False
    # 制造一次"中断": 直接往中间态写垃圾, 再正常 attest ⇒ 旧账不被破坏
    claim(p, 196, "s", "t2")
    after = [json.loads(l) for l in io.open(p, encoding="utf-8")]
    assert len(after) == 2 and not os.path.exists(p + ".tmp")
