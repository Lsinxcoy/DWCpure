# -*- coding: utf-8 -*-
"""三份新配置（world_tree / difficulty / dials）的**反向验证**测试。

★★★ 为什么这份测试与普通单元测试相反
  普通单元测试: 造一个正确输入，看返回对不对。
  本文件:     造 24 个**错误**输入，看每个是否都被拒绝。
  ⇒ ★★ 因为 R13 的实测教训:
       ① `zero_means=0` 曾让 `zero != "NaN"` 短路成 False 而放行
       ② Z3 的 task_group 检查曾被 Z2 挡在后面 ⇒ 永远轮不到
       ⇒⇒ 这两类漏洞**正向测试一个都抓不到**（正确输入下它们不会触发）

★ 覆盖的判据: Z1 Z2 Z3 Z4 Z5 Z6 / X1 X2 X3 / M6
"""
from __future__ import annotations

import io
import os
import sys
import tempfile

import pytest
import yaml

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.foundation import dial_config as dc  # noqa: E402


def _mutated(fname, mutate):
    """把配置改坏后写到临时文件，返回路径。"""
    src = os.path.join(ROOT, "config", fname)
    obj = yaml.safe_load(io.open(src, encoding="utf-8").read())
    mutate(obj)
    fd, tmp = tempfile.mkstemp(suffix=".yaml")
    os.close(fd)                       # ★ 必须关，否则 Windows 锁住文件
    with io.open(tmp, "w", encoding="utf-8") as f:
        yaml.safe_dump(obj, f, allow_unicode=True)
    return tmp


# ══════════════════════════════════════════════════════════
# 基线：三份配置必须是有效的
# ══════════════════════════════════════════════════════════

def test_all_three_configs_valid():
    """意图: 落盘的配置本身必须自洽（否则下面的反例测试都无意义）。"""
    v = dc.validate_all()
    assert v["world_tree"]["world_tree"]["strategy"] in dc.STRATEGIES
    assert v["difficulty"]["difficulty"]["semantics"] in dc.SEMANTICS


# ══════════════════════════════════════════════════════════
# Z1–Z6 · world_tree.yaml
# ══════════════════════════════════════════════════════════

@pytest.mark.parametrize("mutate,expect,desc", [
    (lambda o: o["world_tree"].__setitem__("strategy", "bogus"), "Z1", "strategy 值非法"),
    (lambda o: o["world_tree"].__setitem__("strategy", True), "Z1", "strategy 写成布尔"),
    (lambda o: o["world_tree"].pop("strategy"), "必填", "strategy 缺失"),
    (lambda o: o["world_tree"].__setitem__("pareto_dim", "none"), "Z3", "pareto_dim 非法"),
    (lambda o: o["world_tree"].pop("pareto_dim"), "必填", "pareto_dim 缺失"),
    (lambda o: o["world_tree"].__setitem__("strategy", "gepa_pareto"), "Z2",
     "切 gepa_pareto 但任务数不足"),
    (lambda o: (o["world_tree"].__setitem__("strategy", "gepa_pareto"),
                o["world_tree"].__setitem__("pareto_dim", "task_group")), "Z3",
     "切 gepa_pareto 且用 task_group"),
    (lambda o: o["world_tree"]["candidates"].__setitem__("persist", False), "Z4",
     "candidates.persist=False"),
    (lambda o: o["world_tree"]["candidates"].__setitem__("lineage", "parent"), "Z4",
     "lineage 名字错"),
    (lambda o: o["world_tree"]["merge"].__setitem__("require_all", False), "Z5",
     "merge.require_all=False"),
    (lambda o: o["world_tree"]["stuck"].__setitem__("on_stuck", "retry"), "Z6",
     "on_stuck 非法"),
    (lambda o: o["world_tree"]["stuck"].pop("n_stuck"), "必填", "n_stuck 缺失"),
])
def test_world_tree_rejects(mutate, expect, desc):
    """意图: world_tree.yaml 的每种错配都必须被拒绝且报对编号。"""
    p = _mutated("world_tree.yaml", mutate)
    try:
        with pytest.raises(dc.DialError) as e:
            dc.load_world_tree(p)
        assert expect in str(e.value), \
            "%s: 期望报 %r，实为 %s" % (desc, expect, e.value)
    finally:
        os.remove(p)


# ══════════════════════════════════════════════════════════
# X1–X3 · difficulty.yaml
# ══════════════════════════════════════════════════════════

@pytest.mark.parametrize("mutate,expect,desc", [
    (lambda o: o["difficulty"].__setitem__("semantics", "bogus"), "X1", "semantics 非法"),
    (lambda o: o["difficulty"].__setitem__("semantics", "residual"), "X1",
     "★ 写成字段名 residual（我 2026-10-04 的错）"),
    (lambda o: o["difficulty"].pop("semantics"), "必填", "semantics 缺失"),
    (lambda o: o["difficulty"]["n_obs"].__setitem__("zero_means", 0), "X2",
     "★ zero_means=0（数字冒充字符串，曾短路放行）"),
    (lambda o: o["difficulty"]["n_obs"].pop("zero_means"), "必填", "zero_means 缺失"),
    (lambda o: o["difficulty"]["deep_research"].__setitem__(
        "require_outside_write_mask", False), "X3", "放开写掩码约束"),
    (lambda o: o["difficulty"]["deep_research"].__setitem__("enabled", True),
     "semantics", "启用路线甲但语义不同步"),
])
def test_difficulty_rejects(mutate, expect, desc):
    """意图: difficulty.yaml 的每种错配都必须被拒绝。"""
    p = _mutated("difficulty.yaml", mutate)
    try:
        with pytest.raises(dc.DialError) as e:
            dc.load_difficulty(p)
        assert expect in str(e.value), \
            "%s: 期望报 %r，实为 %s" % (desc, expect, e.value)
    finally:
        os.remove(p)


# ══════════════════════════════════════════════════════════
# M6 · dials.yaml
# ══════════════════════════════════════════════════════════

@pytest.mark.parametrize("mutate,expect,desc", [
    (lambda o: o["dials"].__setitem__("rho_grounded", False), "grounded",
     "rho_grounded=False（撞原则 1）"),
    (lambda o: o["dials"].__setitem__("rho_agent_can_rewrite", True), "原则 1",
     "★ agent 可改写 base（撞原则 1 + 评估器塌缩）"),
    (lambda o: o["dials"].pop("rho_external_content"), "M6", "四布尔缺一"),
    (lambda o: o["dials"].__setitem__("m_in_agent", "true"), "M6", "值写成字符串"),
    (lambda o: o.__setitem__("snapshot_fields", ["m_in_agent"]), "snapshot_fields",
     "snapshot_fields 与四布尔不一致"),
])
def test_dials_rejects(mutate, expect, desc):
    """意图: dials.yaml 的每种错配都必须被拒绝。"""
    p = _mutated("dials.yaml", mutate)
    try:
        with pytest.raises(dc.DialError) as e:
            dc.load_dials(p)
        assert expect in str(e.value), \
            "%s: 期望报 %r，实为 %s" % (desc, expect, e.value)
    finally:
        os.remove(p)


# ══════════════════════════════════════════════════════════
# 检查顺序本身也是契约
# ══════════════════════════════════════════════════════════

def test_z3_dimension_checked_before_z2():
    """★★ 意图: Z3 的维度检查必须排在 Z2 之前。

    ★★ 2026-10-05 反向验证抓到: 原顺序下 Z2 会先因"任务数不足"报错，
      于是 task_group 这条**永远轮不到** ⇒ 若将来任务数真到 50+，
      那个致命错误（Algorithm 2 退化成全局 argmax）就没人拦。
      ⇒⇒ 顺序是契约，不是实现细节。
    """
    p = _mutated("world_tree.yaml",
                 lambda o: (o["world_tree"].__setitem__("strategy", "gepa_pareto"),
                            o["world_tree"].__setitem__("pareto_dim", "task_group")))
    try:
        with pytest.raises(dc.DialError) as e:
            dc.load_world_tree(p)
        assert "Z3" in str(e.value), \
            "维度错误应先于任务数错误上报（用法错误优先于前置条件）"
    finally:
        os.remove(p)


def test_missing_file_raises_not_empty():
    """★★ 意图: 配置文件不存在必须 raise，不许返回空 dict。

    这是 gate.py n_a 契约在配置侧的对应:
    "文件缺失"必须与"配置合法"区分开。
    """
    with pytest.raises(dc.DialError) as e:
        dc.load_world_tree(path=os.path.join(ROOT, "config", "_no_such.yaml"))
    assert "不存在" in str(e.value)


# ══════════════════════════════════════════════════════════
# retention.yaml — 判据 D8（2026-10-05 MEMORY_SYSTEM §六 Q2 裁决后新增）
# ══════════════════════════════════════════════════════════

def _mutated_retention(mutate):
    src = os.path.join(ROOT, "config", "retention.yaml")
    obj = yaml.safe_load(io.open(src, encoding="utf-8").read())
    mutate(obj)
    fd, tmp = tempfile.mkstemp(suffix=".yaml")
    os.close(fd)
    with io.open(tmp, "w", encoding="utf-8") as f:
        yaml.safe_dump(obj, f, allow_unicode=True)
    return tmp


def test_retention_baseline_valid():
    """意图: 落盘的 retention 必须自洽。"""
    r = dc.load_retention()
    assert r["retention"]["dead_after_terms"] >= 1


def test_d8_unit_is_term_not_step():
    """★★★ 意图: dead_after_terms 的单位是 **term**。

    ★★★ 依据 ARCHITECTURE 原则 8 原文:「N 应由 term 边界推导，
      而不是拍一个固定轮数」⇒ 固定轮数（10/20 轮）两个旧选项都违反该原则。
      ⇒ 所以配置里不得出现 step 语义的字段。
    """
    r = dc.load_retention()
    ret = r["retention"]
    assert "dead_after_terms" in ret and "dead_after_steps" not in ret
    raw = io.open(os.path.join(ROOT, "config", "retention.yaml"),
                  encoding="utf-8").read()
    assert "dead_after_steps" not in raw, "配置里不该出现 step 语义的字段"


@pytest.mark.parametrize("bad,desc", [
    (0, "N=0"), ("ten", "N 是字符串"), (3.5, "N 是小数"), (None, "N 缺失"),
])
def test_d8_dead_after_terms_type_and_range(bad, desc):
    """★★ 意图: N 必须是 >=1 的整数（必填无默认）。"""
    p = _mutated_retention(lambda o: o["retention"].__setitem__(
        "dead_after_terms", bad))
    try:
        with pytest.raises(dc.DialError):
            dc.load_retention(p)
    finally:
        os.remove(p)


def test_d8_zero_reference_requires_both_checks():
    """★★★ 意图: import==0 **且** invoke==0 才算零引用。

    ⇒ 少任何一项都不行（否则"仅测试引用"会被误判成有引用）。
    """
    for field in ("require_import_zero", "require_invoke_zero"):
        p = _mutated_retention(lambda o, f=field: o["retention"][
            "zero_reference"].__setitem__(f, False))
        try:
            with pytest.raises(dc.DialError) as e:
                dc.load_retention(p)
            assert "D8" in str(e.value)
        finally:
            os.remove(p)


def test_d8_tests_only_class_enum():
    """意图: tests_only_is 必须在枚举内。"""
    p = _mutated_retention(lambda o: o["retention"]["zero_reference"].__setitem__(
        "tests_only_is", "bogus"))
    try:
        with pytest.raises(dc.DialError):
            dc.load_retention(p)
    finally:
        os.remove(p)


def test_d8_never_recalled_must_hold():
    """★★★ 意图: 未召回的记忆不许直接淘汰。

    ★★★ 依据 MEMORY_SYSTEM §三「未召回 ⇒ 进未验证区，**不淘汰**
      （可能是检索策略问题）」—— 简掉这层会误杀"检索没覆盖到"的记忆。
    """
    p = _mutated_retention(lambda o: o["retention"]["memory"].__setitem__(
        "never_recalled", "evict"))
    try:
        with pytest.raises(dc.DialError) as e:
            dc.load_retention(p)
        assert "检索策略" in str(e.value)
    finally:
        os.remove(p)


def test_d8_rare_signature_must_protect():
    """★ 意图: 稀有保护不可关（它是独立的硬否决，不是加权项）。"""
    p = _mutated_retention(lambda o: o["retention"]["memory"].__setitem__(
        "rare_signature", "evict"))
    try:
        with pytest.raises(dc.DialError):
            dc.load_retention(p)
    finally:
        os.remove(p)


def test_d8_order_fixed_required():
    """★★ 意图: 三层判据的顺序不可换。"""
    p = _mutated_retention(lambda o: o["retention"]["memory"].__setitem__(
        "order_fixed", False))
    try:
        with pytest.raises(dc.DialError) as e:
            dc.load_retention(p)
        assert "顺序" in str(e.value)
    finally:
        os.remove(p)


def test_d8_require_evidence_required():
    """★★ 意图: 判零引用必须留证据（母巢教训: 只有结论没证据）。"""
    p = _mutated_retention(lambda o: o["retention"]["gate"].__setitem__(
        "require_evidence", False))
    try:
        with pytest.raises(dc.DialError) as e:
            dc.load_retention(p)
        assert "证据" in str(e.value)
    finally:
        os.remove(p)


def test_validate_all_includes_retention():
    """意图: validate_all 必须覆盖四份配置。"""
    v = dc.validate_all()
    assert set(v) == {"world_tree", "difficulty", "dials", "retention"}