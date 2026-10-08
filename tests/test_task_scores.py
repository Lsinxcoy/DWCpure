# -*- coding: utf-8 -*-
"""C3' 逐任务分数序列（TaskScorePoint/Store + TS3 双查询口）契约测试。

★★★ 为什么这份测试重要
  这是判据 C3' 的本体（docs/TASK_SCORE_TRACKING.md 设计定稿落地），也是
  δ_θ（R69）欠下的**生产数据链** —— 没有它, WeaknessEstimator 只能吃
  测试注入的假 history。
★ 判据族: TS1 字段必填 · TS2 版本真源 · TS3 双口缺一不可 ·
  未评价不记 · 点与证据成对 · 空组不装 0
"""
from __future__ import annotations

import dataclasses
import json
import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.foundation.version import dw_version  # noqa: E402
from dwc.organs.judge import (  # noqa: E402
    Judge, JudgeError, TaskScorePoint, TaskScoreStore, Verdict,
)


def _ok_verdict(tid="t1", split="dev", n=2, k=2):
    return Verdict(tid, split, True, "测试判据", "dev_anchors",
                   n_checks=n, k_passed=k)


def _store(tmp_path, name="scores.jsonl", evi="evi.jsonl", **kw):
    return TaskScoreStore(path=str(tmp_path / name),
                          evidence_path=str(tmp_path / evi), **kw)


# ══════════════════════════════════════════════════════════
# TS1 / TS2（字段纪律与版本真源）
# ══════════════════════════════════════════════════════════

def test_ts1_eleven_fields_all_required():
    """TS1: 11 字段**必填无默认** —— 缺任何一个直接 TypeError。"""
    fields = [f.name for f in dataclasses.fields(TaskScorePoint)]
    assert len(fields) == 11, fields
    assert all(f.default is dataclasses.MISSING
               and f.default_factory is dataclasses.MISSING
               for f in dataclasses.fields(TaskScorePoint)), \
        "★ TaskScorePoint 字段不许有默认（G11 同款: 缺字段事后不可解释）"
    assert "n_assertions" in fields and "dw_version" in fields
    with pytest.raises(TypeError):
        TaskScorePoint(task_id="t", group_id="g", round_index=1,
                       split="dev", wm_version="", dw_version="v",
                       score=1.0, rung=1, evidence_ref="mem#1",
                       recorded_at="t")            # 缺 n_assertions


def test_ts2_dw_version_is_git_truth(tmp_path):
    """TS2: 版本源 = git 真源（非空 sha）; 无 git ⇒ 显式 nogit 不装。"""
    assert len(dw_version(ROOT)) == 40, "仓库在 ⇒ 40 位 sha"
    fake = tmp_path / "fake_repo"
    (fake / ".git").mkdir(parents=True)
    (fake / ".git" / "HEAD").write_text("ref: refs/heads/main\n")
    (fake / ".git" / "refs" / "heads").mkdir(parents=True)
    (fake / ".git" / "refs" / "heads" / "main").write_text("a" * 40 + "\n")
    assert dw_version(str(fake)) == "a" * 40
    # 注入覆盖优先（测试/审计用）
    s = TaskScoreStore(dw_version="injected-v1")
    assert s.dw_version == "injected-v1"


def test_store_single_side_path_rejected(tmp_path):
    """成对存储: 只给 score 不给 evidence（或反）⇒ 构造就 raise。"""
    with pytest.raises(JudgeError, match="同给或同不给"):
        TaskScoreStore(path=str(tmp_path / "s.jsonl"))
    with pytest.raises(JudgeError, match="同给或同不给"):
        TaskScoreStore(evidence_path=str(tmp_path / "e.jsonl"))


# ══════════════════════════════════════════════════════════
# 判分点即记录点（接线）
# ══════════════════════════════════════════════════════════

def test_evaluate_records_score_point():
    """★ judge.evaluate 尾部自动记录: score=k/n · group=category · rung 来配置。"""
    j = Judge()
    tid = [k for k in j.anchors if not k.startswith("_")][0]
    task = j.anchors[tid]
    # ★ observed 是**执行结果**结构（函数→[[入参,返回]…]）, 不是 golden 本身
    #   （reasoning_001 的 {"answer":…} 同款: 与 golden 对上才 pass）
    obs = {"sum_first_n": [[3, 6], [5, 15]]}
    v = j.evaluate(tid, observed=obs)            # 与 golden 对上 ⇒ 全过
    assert v.success is True
    pts = j.task_scores(split="dev")
    assert len(pts) == 1
    p = pts[0]
    assert p.task_id == tid
    assert p.score == pytest.approx(v.k_passed / float(v.n_checks))
    assert p.n_assertions == v.n_checks == len(task["checks"]), \
        "★ n_assertions 必须 = 配置 checks 数（TS4 精神: 分辨率来自配置声明）"
    assert p.group_id == task["category"]
    assert p.rung == task["verifier_rung"]
    assert p.split == "dev" and p.round_index == 1
    assert p.dw_version and len(p.dw_version) in (40, 5, 6)  # sha 或 nogit/unknown


def test_not_evaluated_not_recorded():
    """★ 未评价（observed=None）⇒ 不记 —— score 是 float, None 不许冒充。"""
    j = Judge()
    tid = [k for k in j.anchors if not k.startswith("_")][0]
    v = j.evaluate(tid, observed=None)
    assert v.success is None
    assert j.task_scores(split="dev") == []


def test_round_index_increments_per_task():
    """一个任务一轮一条不覆盖: 同任务评两次 ⇒ round 1, 2。"""
    j = Judge()
    tid = [k for k in j.anchors if not k.startswith("_")][0]
    task = j.anchors[tid]
    j.evaluate(tid, observed=task)
    j.evaluate(tid, observed=task)
    assert [p.round_index for p in j.task_scores(split="dev")] == [1, 2]


# ══════════════════════════════════════════════════════════
# TS3 双查询口（缺一不可 — 只有聚合=等于没做）
# ══════════════════════════════════════════════════════════

def test_ts3_both_query_ports_exist():
    """TS3: judge.task_scores + judge.group_scores 都必须是实例方法。"""
    j = Judge()
    assert callable(getattr(j, "task_scores"))
    assert callable(getattr(j, "group_scores"))
    # 口②在无数据时不装数
    assert j.group_scores(split="test") == {}


def test_group_scores_mean_and_empty_group_absent(tmp_path):
    """口②聚合 = 组内均值; ★ 无条目的组不出现（不装 0）。"""
    s = TaskScoreStore(dw_version="v")
    s.record(_ok_verdict("t1", "dev", n=4, k=4),   # score 1.0
             group_id="A", rung=1)
    s.record(_ok_verdict("t2", "dev", n=4, k=0),   # score 0.0
             group_id="A", rung=1)
    s.record(_ok_verdict("t3", "dev", n=2, k=1),   # score 0.5
             group_id="B", rung=2)
    gs = s.group_scores(split="dev")
    assert gs == {"A": 0.5, "B": 0.5}
    # round_index 过滤（t3 是 round 1; 只看 round 1 ⇒ A 含两条、B 一条）
    assert s.group_scores(split="dev", round_index=1) == gs
    assert s.group_scores(split="dev", round_index=9) == {}   # 空不装


def test_task_scores_split_filter():
    """口①过滤: split / wm_version 两个维度。"""
    s = TaskScoreStore(dw_version="v")
    s.record(_ok_verdict("t1", "dev"), group_id="A", rung=1)
    s.record(_ok_verdict("t2", "test"), group_id="A", rung=1)
    assert [p.task_id for p in s.task_scores(split="dev")] == ["t1"]
    assert len(s.task_scores()) == 2
    assert s.task_scores(wm_version="other") == []


# ══════════════════════════════════════════════════════════
# 落盘 · 载回 · evidence 配对
# ══════════════════════════════════════════════════════════

def test_persist_and_reload(tmp_path):
    """落盘模式: 判分即写盘, 第二个 store 同路径载回（重启不丢）。"""
    s = _store(tmp_path)
    s.record(_ok_verdict("t1", "dev", n=2, k=1), group_id="A", rung=1)
    s.record(_ok_verdict("t2", "dev"), group_id="A", rung=1)
    assert os.path.exists(str(tmp_path / "scores.jsonl"))
    s2 = _store(tmp_path)
    assert [p.task_id for p in s2.task_scores(split="dev")] == ["t1", "t2"]
    assert s2.task_scores(split="dev")[0].score == pytest.approx(0.5)
    # 磁盘行 = 完整 11 字段 JSON（不是截断投影）
    row = json.loads((tmp_path / "scores.jsonl").read_text().splitlines()[0])
    assert len(row) == 11 and row["n_assertions"] == 2


def test_evidence_ref_roundtrip(tmp_path):
    """约定④: 点里只有 ref; 按 ref 能拉回 evidence 全文（含落盘后载回）。"""
    s = _store(tmp_path)
    s.record(_ok_verdict("t1", "dev"), group_id="A", rung=1)
    ref = s.task_scores(split="dev")[0].evidence_ref
    assert "#" in ref and "t1" not in ref          # ★ 只传 ID, 不内嵌
    assert s.evidence(ref)["task_id"] == "t1"
    # 载回后按 ref 仍可拉回（evidence 文件也成对载）
    s2 = _store(tmp_path)
    ref2 = s2.task_scores(split="dev")[0].evidence_ref
    assert s2.evidence(ref2)["task_id"] == "t1"


def test_dangling_evidence_ref_raises(tmp_path):
    """悬空 ref 大声报错（点与证据必须成对 —— 不静默返回空）。"""
    s = TaskScoreStore(dw_version="v")
    with pytest.raises(JudgeError, match="不可解析"):
        s.evidence("mem#999")


# ══════════════════════════════════════════════════════════
# 生产接线（core 主类）
# ══════════════════════════════════════════════════════════

def test_core_wires_production_store_paths():
    """★ core.DWC 的 judge 走生产落盘路径; 旁路 Judge() 默认内存隔离。"""
    from dwc.core import DWC
    d = DWC(3, 50)                              # depth_limit/max_nodes 必填
    assert d.judge.store.path is not None
    assert os.path.basename(d.judge.store.path) == "task_scores.jsonl"
    assert os.path.basename(d.judge.store.evidence_path) == "evidence.jsonl"
    assert Judge().store.path is None, \
        "★ 旁路/测试构造必须默认内存模式（零污染）"
    d.close() if hasattr(d, "close") else None
