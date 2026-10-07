"""★★★★★ R54 · 细粒度分数（用户裁决「甲」: 多任务 pass_rate = k/n）。

=== 背景 ===
R50 实测分数 ∈ {0,1} ⇒ δ 可行域只剩 {0}（`δ∈[0,1)` 全等价、`δ≥1` 退化）
⇒ **δ 没有调节空间**（与 R41 量化阶梯同根）
⇒ 用户选**甲**: 多任务 pass_rate（论文原意）⇒ 分数连续 ⇒ δ 有意义

=== 我在实现里踩的坑（测试要锁住）===
★★★ 第一版 `pass_rate` 拿 `v.diffs` 当分母 —— **完全错**:
  `Verdict.diffs` 存的是**只失败的**条目（成功时 = `[]`）
  ⇒ 把「失败数」当「总数」⇒ k/n 无意义
  ⇒ 根因: 我核了 `_diff`（产 n 条）却**没核 Verdict 到底存了什么**
  ⇒⇒ ★ 所以 judge 现在把 `n_checks/k_passed` 直接存进 Verdict
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.judge import Judge, overall_score, pass_rate  # noqa: E402


class F:
    """★ 最小 Verdict 替身（只带用到的字段）。"""

    def __init__(self, success, n=None, k=None, diffs=None):
        self.success = success
        self.n_checks = n
        self.k_passed = k
        self.diffs = diffs or []


# ── pass_rate: 单 task k/n ──────────────────────────────────

def test_pass_rate_fine_grained():
    """★★★★ 二值下不存在的中间值必须出现（甲案的存在理由）。"""
    assert pass_rate(F(False, 2, 0)) == 0.0
    assert pass_rate(F(False, 2, 1)) == pytest.approx(0.5)   # ← 关键
    assert pass_rate(F(True, 2, 2)) == 1.0
    assert pass_rate(F(False, 3, 1)) == pytest.approx(1 / 3)


def test_pass_rate_none_semantics():
    """★★ None 的三种来源都**不许**被当分数（0 或 1 都是编造）:
      ① success=None（未评价） ② n 未记（旧对象/早期 return） ③ n<=0
    """
    assert pass_rate(None) is None
    assert pass_rate(F(None, None, None)) is None       # 未评价
    assert pass_rate(F(False, None, 1)) is None          # 没记 n
    assert pass_rate(F(False, 0, 0)) is None             # 分母 0
    assert pass_rate(F(False, -1, 0)) is None            # 负数


def test_pass_rate_never_uses_diffs_as_denominator():
    """★★★★★ 锁我第一版的**错**: `v.diffs` 是**只含失败**的条目
    （成功时 = `[]`）⇒ 拿它当分母 = 把失败数当总数
    ⇒ 这条断言用「diffs 与 n_checks 故意不一致」的替身证明选对了字段。
    """
    # 成功: diffs=[] 但 n=4 k=4 ⇒ 应 1.0（若用 diffs 当分母 ⇒ None/错）
    assert pass_rate(F(True, 4, 4, diffs=[])) == 1.0
    # 失败但 diffs 只有 1 条(只存失败的), 而真实 n=4 ⇒ 应 1/4 而非 0/1
    assert pass_rate(F(False, 4, 1, diffs=[{"ok": False}])) == pytest.approx(0.25)


# ── overall_score: 聚合 Ŝ_t ─────────────────────────────────

def test_overall_score_micro_average():
    """★★ micro 平均（Σk/Σn）—— 不是 mean(pass_rate):
      1-check 与 4-check 若等权, 4-check 任务的信息量被低估。
    """
    r = overall_score([F(False, 4, 1), F(False, 1, 1)])
    assert r["k"] == 2 and r["n"] == 5
    assert r["score"] == pytest.approx(0.4)
    # 对照: mean(ratio) = mean(0.25, 1.0) = 0.625 —— **不该**是它
    assert r["score"] != pytest.approx(0.625), (
        "★ 必须 Σk/Σn, 不能 mean(ratio)")


def test_overall_score_skips_unrated_and_reports_basis():
    """★★ 未评价的**不进分母**（对齐「None 不当 0/1」）+ 可复核。"""
    r = overall_score([F(False, 2, 1), F(None, None, None), F(True, 2, 2)])
    assert r["k"] == 3 and r["n"] == 4, "★ None 那个不该进分母"
    assert r["n_skipped"] == 1
    assert "3/4" in r["basis"], "★ basis 要能复算"


def test_overall_score_empty_is_none():
    """★ 空 / 全未评价 ⇒ **None**（不许 0/0 也不许默认满分）。"""
    assert overall_score([]) is None
    assert overall_score([F(None, None, None), F(None, None, None)]) is None


# ── 端到端: 真 judge 产的 Verdict ──────────────────────────

def test_real_verdict_carries_k_and_n():
    """★★ 端到端: judge evaluate 出来的 Verdict 必须**自带** k/n
    （否则调用方只能拿 diffs 猜 —— 那就是我第一版的错）。
    """
    from dwc.organs.actor import build_implementation, execute_task, Actor
    j = Judge()
    BUGGY = "def sum_first_n(n):\n    return sum(range(n))"
    # 全错
    out = execute_task(Actor(), j, "code_fix_001", implementation=BUGGY)
    v = j.evaluate("code_fix_001", "dev", observed=out["observation"])
    assert v.n_checks == 2 and v.k_passed == 0
    assert pass_rate(v) == 0.0
    # 全对
    fix = build_implementation("sum_first_n", BUGGY,
                               "return sum(range(n + 1))")
    out2 = execute_task(Actor(), j, "code_fix_001", implementation=fix)
    v2 = j.evaluate("code_fix_001", "dev", observed=out2["observation"])
    assert v2.n_checks == 2 and v2.k_passed == 2, (
        "★ 成功时 diffs=[] 但 k/n **必须**照记（否则 pass_rate 没原料）")
    assert pass_rate(v2) == 1.0
    # ★ 部分通过 ⇒ **0.5**（二值时代不可能）
    part = "def sum_first_n(n):\n    return sum(range(n + 1)) if n != 3 else 0"
    out3 = execute_task(Actor(), j, "code_fix_001", implementation=part)
    v3 = j.evaluate("code_fix_001", "dev", observed=out3["observation"])
    assert pass_rate(v3) == pytest.approx(0.5), (
        "★★★ 0.5 就是甲案的存在理由 —— 二值下没有它")
