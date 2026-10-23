# -*- coding: utf-8 -*-
"""R438 · architecture 维度：人工审批队列（不自动落）。

★ 改前 architecture 在 K_META 里 editable=True，但没有任何队列：
  提案要么被当普通规则自动落，要么无声消失。

锁：
1. 入队写 append-only 事件流；同内容去重。
2. 默认状态 pending；approve/reject 改变状态。
3. 重复决定 ⇒ already_decided（不追加垃圾事件）。
4. 未入队的 id ⇒ not_found。
5. list 可按状态过滤。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs import arch_queue as AQ   # noqa: E402


def test_enqueue_and_list(tmp_path):
    p = str(tmp_path / "q.jsonl")
    r = AQ.enqueue("architecture", "pipeline", "加一条总线", "why", p=p)
    assert r["outcome"] == "queued"
    rows = AQ.list_items("pending", p=p)
    assert len(rows) == 1 and rows[0]["target"] == "pipeline"


def test_dedup(tmp_path):
    p = str(tmp_path / "q.jsonl")
    a = AQ.enqueue("architecture", "pipeline", "同一条", p=p)
    b = AQ.enqueue("architecture", "pipeline", "同一条", p=p)
    assert a["id"] == b["id"] and b["outcome"] == "already_queued"


def test_approve_flow(tmp_path):
    p = str(tmp_path / "q.jsonl")
    pid = AQ.enqueue("architecture", "x", "y", p=p)["id"]
    out = AQ.decide(pid, approve=True, by="用户", note="同意", p=p)
    assert out["outcome"] == "approved"
    assert AQ.list_items("approved", p=p)[0]["decided_by"] == "用户"
    assert AQ.list_items("pending", p=p) == []


def test_reject_flow(tmp_path):
    p = str(tmp_path / "q.jsonl")
    pid = AQ.enqueue("architecture", "x", "y", p=p)["id"]
    assert AQ.decide(pid, approve=False, note="影响判据", p=p)["outcome"] == "rejected"
    assert AQ.list_items("rejected", p=p)


def test_double_decide_is_idempotent(tmp_path):
    p = str(tmp_path / "q.jsonl")
    pid = AQ.enqueue("architecture", "x", "y", p=p)["id"]
    AQ.decide(pid, approve=True, p=p)
    out = AQ.decide(pid, approve=False, p=p)
    assert out["outcome"] == "already_decided"
    # 事件流只应有一条 approve（不追加 reject）
    ev = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
    assert sum(1 for e in ev if e["event"] == "approve") == 1
    assert not any(e["event"] == "reject" for e in ev)


def test_unknown_id(tmp_path):
    p = str(tmp_path / "q.jsonl")
    assert AQ.decide("A_nope", approve=True, p=p)["outcome"] == "not_found"


def test_cli_list_runs(tmp_path):
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import dwc_arch_queue as CLI
    p = str(tmp_path / "q.jsonl")
    AQ.enqueue("architecture", "x", "y", p=p)
    assert CLI.main(["--list", "--queue", p]) == 0
