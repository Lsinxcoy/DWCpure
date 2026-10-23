# -*- coding: utf-8 -*-
"""R189-B · train split 无标签面扩容 + 三层口径洞修复。

三层洞（每层都是实测抓的, 不是读代码猜的）:
  洞①（R184 已留痕, R189-B 实修）: 无标签 ctx 里 op 判据键全 None ⇒ 6 op 中
     4 个 abstain, 剩 root_parse_ok/nonempty_diff 恒 clean ⇒ A_train 恒 1.0
  洞②（R189-B 新抓）: train behavior 无 impl_store ⇒ implementation=None
     ⇒ PureFunctionExecutor 跑 **REFERENCE 基准** ⇒ 观测不是 agent 产出
     ⇒ 论文 A_train 语义被架空
  洞③（R189-B 新抓, 最深）: a_train_weighted 只认**当前选中的树**的 op
     ⇒ TRAIN_POOL 新加的 exec_ok/evidence_rich 不在树上 ⇒ 票被静默丢弃
     ⇒ 恒 1.0（修法: op_filter 显式覆盖）

验收锚: A_train 在 15 条盘上 **不再恒 1.0**（实测 0.9167 — 4/12 条真负例）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.drawback import Node as _N, _eval as _ev          # noqa: E402
from dwc.organs.ops import (DEFAULT_POOL, EVIDENCE_MIN_CHARS,     # noqa: E402
                            TRAIN_POOL, op_evidence_rich,
                            op_exec_ok)
from dwc.organs.metric_loop import (a_train_weighted,             # noqa: E402
                                    reliability_weight)
from dwc.harness.loop import Loop                                  # noqa: E402


# ── 池结构 ─────────────────────────────────────────────────
def test_train_pool_extends_default():
    """★★ TRAIN_POOL = DEFAULT_POOL + 2 无标签 op（门③候选族不动）。"""
    assert len(DEFAULT_POOL) == 6
    assert len(TRAIN_POOL) == 8
    assert {op.name for op in TRAIN_POOL} - {op.name for op in DEFAULT_POOL} \
        == {"exec_ok", "evidence_rich"}


def test_default_pool_unchanged_for_gates():
    """★★★ 门③仍用 DEFAULT_POOL（R189-B 最小手术: 不动已绿行为面）。"""
    from dwc.organs.metric_loop import _POOL_OPS
    assert set(_POOL_OPS) == {op.name for op in DEFAULT_POOL}


# ── 无标签 op 三态 ─────────────────────────────────────────
def test_exec_ok_three_states():
    """★★★ exec_ok: raised ⇒ drawback / None ⇒ clean / 键缺席 ⇒ abstain。"""
    ops = {"exec_ok": op_exec_ok()}
    def st(ctx):
        return _ev(_N(kind="leaf", op="exec_ok"), ops, None, None, ctx)
    assert st({"exec_error": "RecursionError"}) == "drawback"
    assert st({"exec_error": None}) == "clean"
    assert st({}) == "abstain"          # 键缺席 ≠ drawback（R166 同族纪律）


def test_evidence_rich_threshold():
    """★★ evidence_rich: <阈值 ⇒ drawback（太短 = 没什么可判的）。"""
    ops = {"evidence_rich": op_evidence_rich()}
    def st(ctx):
        return _ev(_N(kind="leaf", op="evidence_rich"), ops, None, None, ctx)
    assert st({"output_chars": EVIDENCE_MIN_CHARS}) == "clean"   # 边界含
    assert st({"output_chars": EVIDENCE_MIN_CHARS - 1}) == "drawback"
    assert st({}) == "abstain"


# ── op_filter（洞③修复）──────────────────────────────────────
def test_op_filter_overrides_tree():
    """★★★ 洞③: op_filter 给的 op 集合说话, 不被树的 op 限死。"""
    from dwc.organs.direction import EvolutionDirection as D  # noqa: E402
    from dwc.organs.drawback import Node as _Nd
    tree = _Nd(kind="leaf", op="root_parse_ok")     # 树只含 root 一个 op
    tv = [{"root_parse_ok": "clean", "exec_ok": "drawback"}]
    # 旧行为（无 op_filter）⇒ 只数树的 op ⇒ 恒 1.0
    assert a_train_weighted(tv, tree, {}) == 1.0
    # R189-B ⇒ op_filter=两 op ⇒ drawback 的 exec_ok 进分母 ⇒ 0.5
    assert a_train_weighted(tv, tree, {}, op_filter=["root_parse_ok",
                                                    "exec_ok"]) == 0.5


def test_op_filter_empty_returns_none():
    """★ 空 op 集合 ⇒ None（fail-closed, 不返回 0 假冒共识）。"""
    from dwc.organs.drawback import Node as _Nd
    assert a_train_weighted([{"x": "clean"}], _Nd(kind="leaf", op="x"),
                            {}, op_filter=[]) is None


# ── 15 条无标签盘 + A_train 非退化（洞②修复的实证）───────────
def test_train_anchors_expanded_to_15():
    """★★ train.json 6 → 15 条, 全部 unlabeled（无 expected 纪律不破）。"""
    import json
    import io
    with io.open(os.path.join(ROOT, "config", "anchors", "train.json"),
                 encoding="utf-8") as fh:
        d = json.load(fh)
    tasks = [k for k in d if not k.startswith("_")]
    assert len(tasks) == 15
    for k in tasks:
        v = d[k]
        assert v.get("unlabeled") is True
        assert "expected" not in v and "expected_keywords" not in v \
            and "expected_behavior" not in v, "%s 带了 label ⇒ train 纪律崩" % k


def test_a_train_no_longer_degenerate():
    """★★★ 总验收锚: 15 条盘上 A_train ≠ 1.0（退化根因三层全修）。

    ★ 为什么 ≤ 1.0 恒等断言不够: 若盘上**真的**全 clean（如未来 impl 全修好）
      ⇒ A_train=1.0 是**如实结果**。所以本测试断言的是「盘上有负例存在」
      — 由 broken 初值（factorial 无限递归等 4 条）保证, 写死不依赖实现漂移。
    """
    lp = Loop()
    lp.impl_store.clear()          # 清 agent 已修状态 ⇒ 用 broken 初值面
    a = lp._train_outputs_consensus()
    assert a is not None, "train 面缺席 ⇒ fail-closed（本盘应 12 条可跑）"
    assert a < 1.0, ("A_train=1.0 ⇒ 三层洞复发（观测=REFERENCE 基准 / op 不进 "
                     "分母 / 判据键全 None）; 实测应 ~0.9167")
    assert "12 outputs" in (lp._last_a_train_why or "")


def test_broken_impl_fallback_not_reference():
    """★★★ 洞②: behavior 面无 impl_store ⇒ 回退 broken_dev 同 fn 初值,
    **绝不跑 REFERENCE**（基准不是 agent 产出 — 论文语义）。"""
    lp = Loop()
    lp.impl_store.clear()
    rec = lp.judge.train_anchors["train_code_005"]     # factorial
    impl = lp._broken_impl_for_fn(rec)
    assert impl and "return n * factorial(n)" in impl, (
        "应拿到 factorial 的 broken 初值（无限递归态）")
    assert "n <= 1" not in impl, "拿到 REFERENCE 了 ⇒ 洞②复发"


def test_train_kind_still_evaluate_raises():
    """★★★ R184 纪律①: train 无 label ⇒ evaluate 恒 raise（不放水）。"""
    from dwc.organs.judge import Judge
    j = Judge()
    with pytest.raises(Exception):
        j.evaluate("train_code_001", split="train", observed={})


def test_train_with_golden_raises():
    """★★★ R184 纪律②: train.json 带 label ⇒ 载入即 raise（train 有 label
    就变成第二个 dev）。"""
    import json
    import io
    import tempfile
    from dwc.organs.judge import Judge
    bad = {"train_code_001": {"verifier_kind": "behavior",
                              "checks": [{"fn": "average", "args": "1",
                                          "expected": "1.0"}],
                              "unlabeled": True}}
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with io.open(path, "w", encoding="utf-8") as fh:
        json.dump(bad, fh)
    try:
        with pytest.raises(Exception):
            Judge(train_path=path)
    finally:
        os.remove(path)


def test_a_train_weights_are_reliability_scaled():
    """★ κ=10 权重口径仍在（R182 — 新 op_filter 不改加权公式）。"""
    assert reliability_weight(0.25) == pytest.approx(1 / 3.5, abs=1e-9)
    assert reliability_weight(None) == 1.0
