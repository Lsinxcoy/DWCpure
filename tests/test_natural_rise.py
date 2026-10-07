"""★★★★★ R55 · 「分数必须自然涨过」判据（与 e2e **单源** natural_rise）。

=== 为什么 ===
R51/R54 我一直在**构造**波动（轮换 base/cur、与上轮同分才轮换）
⇒ ⇒★ 分数是**编排出来的**，不是**演化出来的**
⇒ R55 首推: 让分数**自然涨一次**（构造的不算数）

=== 本测试验的四条硬要求 ===
 ① 至少一次严格上涨 ② 涨那次的 src 不许是「构造对照」
 ③ 分数不许恒定 ④ srcs 缺省时**不能**因为验不了就放过②（显式标出来）
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.evolver import natural_rise  # noqa: E402


def test_real_rise_passes():
    """★ 真演化序列（R55 实测: 0.5556→0.5556→0.6667→0.8889）⇒ ok。"""
    r = natural_rise([0.5556, 0.5556, 0.6667, 0.8889],
                     ["overall(修1)", "overall(修2, 002没修对)",
                      "overall(修3)", "overall(修4)"])
    assert r["ok"], r["reasons"]
    assert r["n_rises"] == 2
    assert r["first_rise"] == pytest.approx((0.5556, 0.6667))
    assert r["src_checked"] is True


def test_flat_sequence_fails():
    """★★ 恒定 ⇒ 没涨 ⇒ **必须红**（R54 边界①: 细粒度没用上）。"""
    r = natural_rise([1.0, 1.0, 1.0])
    assert not r["ok"]
    assert any("从未自然涨过" in x for x in r["reasons"])
    assert any("恒定" in x for x in r["reasons"])


def test_constructed_rise_fails():
    """★★★★ 涨是**构造**的 ⇒ 必须红（这是本函数存在的核心理由）。"""
    r = natural_rise([0.5, 1.0], ["overall", "构造对照(轮换 cur)"])
    assert not r["ok"]
    assert any("构造" in x for x in r["reasons"]), r["reasons"]


def test_missing_src_cannot_smuggle_through():
    """★★★ srcs 缺省 ⇒ 不能**因为验不了就放过②** —— 显式标 src_checked=False。"""
    r = natural_rise([0.5, 1.0])          # 涨了, 但没 src 可查
    assert r["ok"] is False or r["src_checked"] is False, \
        "★ 没 src 时至少要说清 src 没查（否则是假装查过）"
    assert r["src_checked"] is False
    # 而且 srcs 为空列表也要同样处理
    r2 = natural_rise([0.5, 1.0], [])
    assert r2["src_checked"] is False


def test_empty_and_single():
    """★ 空 / 单点 ⇒ 无法验证 ⇒ ok=False（不是放行）。"""
    assert natural_rise([])["ok"] is False
    assert natural_rise([0.5])["ok"] is False
    assert "空序列" in " ".join(natural_rise([])["reasons"])


def test_declining_fails():
    """★ 单调降 ⇒ 没涨 ⇒ 红。"""
    r = natural_rise([1.0, 0.5, 0.3])
    assert not r["ok"]
