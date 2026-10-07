"""★★★★ R56 · 锁 4 个 task 的 **fix 真的修对**（我 R55 犯过 002 没修对）。

=== 事故 ===
R55 我给 `code_fix_002` 写的 fix `sum(xs)/len(xs)` ⇒ 空列表
`ZeroDivisionError` ⇒ actual=None ⇒ fail（**只 1/2**）
而 checks 里有 `average([])` 期望 **0.0**（不是异常）
⇒ ⇒★ 我的 fix **漏了空列表边界** —— 修 fix 时没读 checks 的期望
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.actor import Actor, execute_task  # noqa: E402
from dwc.organs.judge import Judge, pass_rate  # noqa: E402

FIXES = {
    "code_fix_001": ("sum_first_n",
                     "def sum_first_n(n):\n    return sum(range(n + 1))"),
    "code_fix_002": ("average",
                     "def average(xs):\n    return sum(xs) / len(xs) if xs else 0.0"),
    "code_fix_003": ("factorial",
                     "def factorial(n):\n    r = 1\n    for i in range(1, n + 1):\n        r *= i\n    return r"),
    "code_fix_004": ("fibonacci",
                     "def fibonacci(n):\n    a, b = 0, 1\n    for _ in range(n):\n        a, b = b, a + b\n    return a"),
}


def test_every_fix_scores_full():
    """★★★ 每个 task 的 fix 必须 **满分**（否则 `修 N 个` 的分数没意义）。"""
    j = Judge()
    for tid, (_fn, src) in FIXES.items():
        out = execute_task(Actor(), j, tid, implementation=src)
        v = j.evaluate(tid, "dev", observed=out["observation"])
        assert v.k_passed == v.n_checks, \
            "%s 的 fix 只 %s/%s = %s（不是满分 ⇒ R55 那类漏边界又出现了）" % (
                tid, v.k_passed, v.n_checks, pass_rate(v))


def test_average_fix_handles_empty_list():
    """★★★ R56 现场: `average([])` 期望 **0.0**（不是异常）——
    我 R55 的 fix 因 ZeroDivisionError 只拿 1/2。
    """
    j = Judge()
    src = FIXES["code_fix_002"][1]
    out = execute_task(Actor(), j, "code_fix_002", implementation=src)
    obs = out["observation"]["average"]
    # 两个 check 都要有值, 且空列表那个 = 0.0
    assert len(obs) == 2
    empty = next(c for c in obs if c[0] == [])
    assert empty[1] == 0.0, \
        "★ `average([])` 应返回 0.0（checks 期望）, 实得 %r" % (empty[1],)


def test_buggy_still_partially_passes():
    """★ 对照: buggy 实现**不是全错**（002 buggy 恰好过了空列表）——
    那是「部分通过」的真来源, 别把它当全错的基线。
    """
    j = Judge()
    buggy = "def average(xs):\n    return sum(xs) / (len(xs) + 1)"
    out = execute_task(Actor(), j, "code_fix_002", implementation=buggy)
    v = j.evaluate("code_fix_002", "dev", observed=out["observation"])
    assert v.k_passed == 1 and v.n_checks == 2, \
        "★ buggy 应是 1/2（碰巧过了空列表）, 实得 %s/%s" % (v.k_passed, v.n_checks)
