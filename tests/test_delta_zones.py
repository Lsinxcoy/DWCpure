"""★★★★★ R57 · δ 的**对照实验**固化（三区行为可复跑）—— R58 用户拍板 δ=0.15（2026-10-08 选项②）已落地。

=== 为什么固化 ===
R50 我实测二值下 δ 只剩 {0}（无调节空间）⇒ R54 甲案让分数变 k/n
⇒ R56 得到真实序列 ⇒ 这里**用真实序列**扫 δ, 把三个行为区固化成
**可复跑的判据**（而不是我在报告里口头摆一次）。

=== 三个行为区（R56 真实序列的 Δ 档位）===
  Δ ∈ {+0.1111, +0.2222, −0.2222}（4 task 的 k/n 决定）
  ① δ ∈ [0, 0.111]    微涨算**涨**（最严格, 不容忍微小进步）
  ② δ ∈ (0.111, 0.222] ★ **容忍微涨 + 拒绝大涨** = 唯一有调节作用的区间
  ③ δ > 0.222         **退化**（涨也算停滞 ⇒ σ 恒 1 = 写死）

★ ★ 区间**依赖 Δ 档位** ⇒ task/check 数变 ⇒ 档位变 ⇒ 区间变
   （所以这里锁**行为**, 不锁区间数字 —— 数字会过期）
★ δ 的**具体值**是业务语义（「多小进步算噪声」）⇒ 本测试**不改** δ,
  只证明「δ 在这个区间里真的有调节作用」
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.evolver import noise_delta, stall_signal  # noqa: E402

# ★ R56 实测的**真实** e2e 序列（不是构造的）
REAL = [0.5555555555555556, 0.6666666666666666, 0.7777777777777778, 1.0,
        0.7777777777777778, 1.0, 0.7777777777777778, 1.0]


def _sigmas(seq, d):
    return [stall_signal(seq[:k], window=1, delta=d)["sigma"]
            for k in range(2, len(seq) + 1)]


def test_real_sequence_has_three_delta_zones():
    """★★★★ 三区行为（锁**行为**, 不锁区间数字 —— 数字会随 task 数过期）。"""
    s0 = _sigmas(REAL, 0.0)              # 最严格
    s_mid = _sigmas(REAL, 0.15)          # 容忍微涨（0.111 ≤ 0.15）
    s_big = _sigmas(REAL, 0.5)           # 退化
    # ① 严格区: 微涨(0.111)算涨 ⇒ 那两轮 σ=0
    assert s0[0] == 0 and s0[1] == 0, "★ δ=0 时微涨应算涨, 实得 %s" % s0[:2]
    # ② 容忍区: 同样的微涨算停滞 ⇒ 变 1（**这就是 δ 的调节作用**）
    assert s_mid[0] == 1 and s_mid[1] == 1, \
        "★ δ=0.15 应容忍微涨(0.111), 实得 %s —— δ 没起作用" % s_mid[:2]
    # ② 但**大跌**(−0.222)两种 δ 下都算停滞（跌不因 δ 而改变）
    assert s0[3] == 1 and s_mid[3] == 1, "★ 跌该恒为 σ=1"
    # ③ 退化区: 大涨(0.222)也被容忍 ⇒ 全 1 ⇒ **写死**
    assert set(s_big) == {1}, "★ δ 过大应退化(全 1), 实得 %s" % s_big


def test_delta_actually_changes_judgment():
    """★★★ 核心: δ 必须**真的改变判断**（否则 δ 是摆设 = R50 的死结）。"""
    strict = _sigmas(REAL, 0.0)
    tolerant = _sigmas(REAL, 0.15)
    assert strict != tolerant, "★ δ 从 0 → 0.15 判断没变 ⇒ δ 无调节作用"
    # 变的**恰好**是微涨那两轮（不是乱变）
    changed = [k for k in range(len(strict)) if strict[k] != tolerant[k]]
    assert changed == [0, 1], \
        "★ 应只在微涨(Δ=0.111)那两轮变, 实得变了 %s" % changed


def test_zone_boundary_uses_real_deltas():
    """★★ 区间边界由**真实 Δ 档位**决定（不拍死 0.111/0.222 ——
    那些数来自 4 task 的 k/n, task 数变了就过期）。"""
    ups = sorted({round(REAL[k] - REAL[k - 1], 4)
                  for k in range(1, len(REAL)) if REAL[k] > REAL[k - 1]})
    assert len(ups) >= 2, "★ 至少两档涨的 Δ 才能测出调节作用, 实得 %s" % ups
    small, big = ups[0], ups[-1]
    # ★ 严格区: δ = 小涨 ⇒ 不容忍
    assert _sigmas(REAL, small)[0] == 0
    # ★ 容忍区: δ > 小涨 且 ≤ 大涨 ⇒ 容忍小的、拒绝大的
    mid = (small + big) / 2
    s = _sigmas(REAL, mid)
    assert s[0] == 1, "★ δ=%.4f 应容忍微涨 %.4f" % (mid, small)
    assert s[2] == 0, "★ 但应拒绝大涨 %.4f（否则就是退化边缘）" % big
    # ★ 退化区: δ > 大涨 ⇒ 全 1
    assert set(_sigmas(REAL, big + 0.01)) == {1}


def test_current_delta_matches_user_ruling():
    """★★ 本测试**锁 δ 当前拍板值 = 0.15**（R58 · 2026-10-08 用户选项②）。
    ★ 这不是「锁死 0.15 是对的」, 而是**锁「改 δ 要经过拍板」这个纪律** ——
      下次改 δ 仍须: 拍板 → 改这里 → 更新 basis → 重跑三区。
    """
    assert noise_delta()["delta"] == 0.15, \
        "★ δ 变了 ⇒ 需要: ① 用户拍板 ② 更新 basis(区间的实测依据) " \
        "③ 重跑本测试的三区行为（当前拍板值 = 0.15）"


def test_delta_zone_report_is_reproducible():
    """★★ 报告里的三区表必须**可复跑**（不是我口头说的）。"""
    report = []
    for d in (0.0, 0.15, 0.5):
        s = _sigmas(REAL, d)
        report.append((d, s, s.count(1)))
    # 严格 < 容忍 < 退化（停滞次数单调递增）
    counts = [r[2] for r in report]
    assert counts == sorted(counts), \
        "★ δ 增大 ⇒ σ=1 的次数应单调不减, 实得 %s" % counts
    # 且退化区真的全 1
    assert report[-1][1] == [1] * 7, "★ δ=0.5 应退化(全 1)"
