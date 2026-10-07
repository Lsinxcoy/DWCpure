"""★★★★ R56 · has_drop/has_rise 单源判据（e2e 与 pytest 同一套）。

=== 为什么单独立 ===
R55 我挑明「σ 没见过跌 ⇒ 那个语义就是没验过」⇒ R56 加「跌过」断言,
但第一版**内联在 e2e 里** ⇒ pytest 验不到 ⇒ 破坏 ④⑤ 直接去掉断言
**没红**（我验错了方向, 但**根因是判据没单源** —— R39「一个判据不许散
多处」的变体）。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.evolver import has_drop, has_rise  # noqa: E402


def test_drop_detected():
    """★ R56 实测序列（0.5556→…→1.0→0.7778）⇒ 跌过 3 次。"""
    seq = [0.5556, 0.6667, 0.7778, 1.0, 0.7778, 1.0, 0.7778, 1.0]
    # ★ 跌的相邻对: 1.0→0.7778 (idx4) · 1.0→0.7778 (idx6) ⇒ **2 次**
    #   （我第一版拍成 3 —— 又没算就写断言）
    r = has_drop(seq)
    assert r["ok"] is True and r["n_drops"] == 2
    assert r["first_drop"] == (1.0, 0.7778)
    assert r["precondition"] is True


def test_all_rising_has_no_drop():
    """★★★ 纯涨序列 ⇒ **必须说没跌**（那正是「σ 语义没验」的状态）。"""
    r = has_drop([0.5556, 0.6667, 0.7778, 1.0])
    assert r["ok"] is False
    assert any("从未跌过" in x for x in r["reasons"])
    assert r["n_drops"] == 0


def test_flat_counts_as_no_drop_and_no_rise():
    """★ 恒定 = **既没跌也没涨**（严格 < / >）—— 两个方向都要测。

    ★★★ R56 破坏⑤ 抓出的**测试缺口**: 我只测了 has_drop 的恒定,
      **没测 has_rise 的恒定** ⇒ 把 `>` 改 `>=` 没红（同 R49「单条件
      any≡all」那类 —— 测试只覆盖了一半）
    """
    flat = [1.0, 1.0, 1.0]
    assert has_drop(flat)["ok"] is False and has_drop(flat)["n_drops"] == 0
    assert has_rise(flat)["ok"] is False and has_rise(flat)["n_rises"] == 0


def test_precondition_is_not_fail():
    """★★ 数据不足（<2 个）= **precondition=False**，`ok=None`
    —— 不是 fail（同 natural_rise / σ_t 的模式）。"""
    for v in (has_drop([]), has_drop([0.5])):
        assert v["precondition"] is False and v["ok"] is None
        assert v["n_drops"] == 0
    for v in (has_rise([]), has_rise([0.5])):
        assert v["precondition"] is False and v["ok"] is None


def test_rise_counterpart():
    """★ has_rise: 纯涨 ⇒ ok=True·n=3; 纯跌 ⇒ ok=False（说从未涨过）。"""
    up = has_rise([0.5, 0.6, 0.7, 0.8])
    assert up["ok"] is True and up["n_rises"] == 3
    down = has_rise([1.0, 0.9, 0.8])
    assert down["ok"] is False
    assert any("从未涨过" in x for x in down["reasons"])


def test_two_distinct_judges():
    """★★★ 「涨过」与「跌过」是**两条不同判据**（R56 我混淆过）:
    同一序列可以只满足其中一条。
    """
    seq = [0.5, 0.6, 0.7]          # 只涨不跌
    assert has_rise(seq)["ok"] is True and has_drop(seq)["ok"] is False
    seq2 = [0.7, 0.6, 0.5]         # 只跌不涨
    assert has_drop(seq2)["ok"] is True and has_rise(seq2)["ok"] is False
