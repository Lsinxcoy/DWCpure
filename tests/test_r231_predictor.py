# -*- coding: utf-8 -*-
"""R231 · 行为结果预测器（视图层）：Beta 后验数学 / replay / 树键只读 / 身份校验。"""
from __future__ import annotations

import io
import json
import os
import sys

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.organs import predictor as P                            # noqa: E402
import pytest                                                   # noqa: E402


def _fresh(tmp_path):
    return P.OutcomePredictor(
        log_path=str(tmp_path / "pred.jsonl"), world_model=None)


def test_posterior_math_exact(tmp_path):
    """★★★ 后验数学锁: 先验 Beta(1,1), 5 成 3 败 ⇒ p̂=(5+1)/(8+2)=0.6 精确。"""
    p = _fresh(tmp_path)
    for _ in range(5):
        p.observe("op:run", True)
    for _ in range(3):
        p.observe("op:run", False)
    r = p.predict("op:run")
    assert r["p"] == 0.6, r                    # 精确相等 — 不是约等
    assert r["n"] == 8 and r["source"] == "ledger"
    # 无观测键 ⇒ 先验
    fresh = p.predict("op:never")
    assert fresh["p"] == 0.5 and fresh["n"] == 0


def test_tree_key_reads_tree_and_never_writes(tmp_path):
    """★★★ 树键只读锁: 注入假世界树 ⇒ 谱系直读（Laplace 同式）;
    observe 树族键 ⇒ 结构上拒（双写禁令）。"""
    class _Node:
        def __init__(self, n_obs=0, n_pass=0, parent_id=None):
            self.n_obs, self.n_pass, self.parent_id = n_obs, n_pass, parent_id

    class _Tree:
        def __init__(self, nodes):
            self.nodes = nodes
        def lineage_obs(self, node_id):
            n_obs = n_pass = 0
            cur = self.nodes.get(node_id)
            while cur is not None:
                n_obs += cur.n_obs
                n_pass += cur.n_pass
                cur = self.nodes.get(cur.parent_id) if cur.parent_id else None
            return n_obs, n_pass

    class _WM:
        trees = {"demo": _Tree({
            "root": _Node(n_obs=3, n_pass=1),
            "n1": _Node(n_obs=4, n_pass=2, parent_id="root")})}

    p = P.OutcomePredictor(log_path=str(tmp_path / "p.jsonl"),
                           world_model=_WM())
    r = p.predict("tree:demo/n1")
    # 谱系和: n_obs=7, n_pass=3 ⇒ p=(3+1)/(7+2)=4/9
    assert r["source"] == "tree" and r["n"] == 7
    assert abs(r["p"] - 4.0 / 9.0) < 1e-12, r
    # 双写禁令
    with pytest.raises(P.PredictorError, match="双写|不许 observe"):
        p.observe("tree:demo/n1", True)
    # 世界模型不可用 ⇒ 诚实缺失
    q = P.OutcomePredictor(log_path=str(tmp_path / "q.jsonl"))
    assert q.predict("tree:demo/n1")["source"] == "tree_unavailable"


def test_replay_rebuild_equals_online(tmp_path):
    """★★ replay 防遗忘锁: 日志重放重建的计数与在线计数逐键一致。"""
    log = str(tmp_path / "pred.jsonl")
    a = P.OutcomePredictor(log_path=log)
    seq = [("op:run", True), ("op:run", True), ("run:x", False),
           ("op:run", False), ("rung:3", True), ("run:x", True)]
    for k, ok in seq:
        a.observe(k, ok)
    b = P.OutcomePredictor(log_path=log)       # 重放
    for k in {x[0] for x in seq}:
        assert a.predict(k) == b.predict(k), k


def test_calibration_honest(tmp_path):
    """★★ 校准诚实锁: 完美校准流（p 恒 0.5 交替成败）Brier=0.25;
    全对流 Brier→0 — 校准器自身可测（不装样子）。"""
    p = _fresh(tmp_path)
    for i in range(50):
        p.observe("k", i % 2 == 0)             # 先验下 p=0.5 交替
    cal = p.calibrate()
    assert cal["n"] == 50 and abs(cal["brier"] - 0.25) < 1e-9
    q = P.OutcomePredictor(log_path=str(tmp_path / "q.jsonl"))  # 独立日志
    for _ in range(50):
        q.observe("k", True)
    assert q.calibrate()["brier"] < 0.05       # 学到的 p≈0.98, 全对 ⇒ 低 Brier


def test_checkpoint_identity_locks(tmp_path, monkeypatch):
    """★★ checkpoint 身份锁: sha 篡改 / version 不符 ⇒ 拒载（rsi.py 同款）。"""
    ck = tmp_path / "ckpt.json"
    monkeypatch.setattr(P, "PRED_CKPT", str(ck))
    p = _fresh(tmp_path)
    p.observe("op:run", True)
    info = p.checkpoint()
    assert info["keys"] == 1 and os.path.exists(info["path"])
    P.OutcomePredictor.load(path=str(ck),
                            log_path=str(tmp_path / "pred.jsonl"))   # 正常载
    # sha 篡改
    doc = json.load(io.open(ck, encoding="utf-8"))
    doc["doc"]["counts"]["op:run"] = [99, 1]
    json.dump(doc, io.open(ck, "w", encoding="utf-8"))
    with pytest.raises(P.PredictorError, match="sha"):
        P.OutcomePredictor.load(path=str(ck),
                                log_path=str(tmp_path / "pred.jsonl"))
    # version 不符（先改 version 再重算 sha — 保证只有 version 一项失配）
    doc["doc"]["version"] = "pred-v0"
    doc["sha"] = P._sha(json.dumps(doc["doc"], ensure_ascii=False,
                                   sort_keys=True))
    json.dump(doc, io.open(ck, "w", encoding="utf-8"))
    with pytest.raises(P.PredictorError, match="version"):
        P.OutcomePredictor.load(path=str(ck),
                                log_path=str(tmp_path / "pred.jsonl"))


def test_uncertainty_shrinks_with_data(tmp_path):
    """★ 不确定度单调收缩: 数据越多 uncertainty 越小（探索项的数学性质）。"""
    p = _fresh(tmp_path)
    u0 = p.predict("op:run")["uncertainty"]
    for _ in range(20):
        p.observe("op:run", True)
    u1 = p.predict("op:run")["uncertainty"]
    assert u1 < u0 and abs(u1 - 1.0 / 22.0) < 1e-12
