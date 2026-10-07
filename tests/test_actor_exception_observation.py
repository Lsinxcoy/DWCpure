"""★★★★★ R55 · 执行器**抛异常**时不许崩（L622 那个 IndexError）。

=== 事故 ===
我 probe 4 个 task 时 `code_fix_003` 的 buggy 实现触发:
    `calls.append([_as_literal(c["args"]), ex.calls[-1][1]])` ⇒ **IndexError**
根因: `act` 在 `executor(task)` 抛异常时记 `outcome="raised"` 后 **return**
    ⇒ `ex.calls` **是空的** ⇒ `[-1]` 越界
⇒ ⇒★ 我读 `PureFunctionExecutor` 时只看了 happy path, **没读 act 的异常分支**
    （先读再写没做到）

=== 修法（不是掩盖）===
无调用记录 ⇒ 诚实记 **None** ⇒ judge 收到 actual=None ⇒ 判 **fail**
（实现抛异常时就该 fail —— 那是对的, 不是隐藏）
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.actor import Actor, PureFunctionExecutor, execute_task  # noqa: E402
from dwc.organs.judge import Judge  # noqa: E402


def test_executioner_exception_yields_none_not_indexerror():
    """★★★ 实现**抛异常** ⇒ 该 check 的 actual = **None**, 且**不崩**。"""
    # 这个实现对所有输入都抛（除零）
    bad = "def sum_first_n(n):\n    return 1 // 0"
    out = execute_task(Actor(), Judge(), "code_fix_001", implementation=bad)
    obs = out["observation"]["sum_first_n"]
    assert len(obs) == 2, "★ 每个 check 都要有一条观察（缺了 judge 就没原料）"
    for pair in obs:
        assert pair[1] is None, \
            "★ 执行器抛异常 ⇒ 无调用记录 ⇒ 应诚实记 None, 实得 %r" % (pair[1],)


def test_buggy_factorial_does_not_crash():
    """★★ R55 现场: `code_fix_003` 的 buggy 实现（range(1,n) 漏 n）——
    此前 IndexError 崩了 e2e ⇒ 现在必须正常跑出观察。
    """
    buggy = ("def factorial(n):\n"
             "    r = 1\n"
             "    for i in range(1, n):\n"
             "        r *= i\n"
             "    return r")
    j = Judge()
    out = execute_task(Actor(), j, "code_fix_003", implementation=buggy)
    v = j.evaluate("code_fix_003", "dev", observed=out["observation"])
    # ★ 不要求具体分数, 只要求**没崩**且 k/n 有记录（可算 pass_rate）
    assert v.n_checks and v.n_checks >= 1
    assert v.k_passed is not None


def test_executor_exception_is_recorded_in_trace():
    """★ 异常被记成 **outcome="raised"**（不是「没发生」—— act 的语义）。"""
    ex = PureFunctionExecutor("sum_first_n",
                              source="def sum_first_n(n):\n    return 1 // 0")
    a = Actor()
    tr = a.act({"task_id": "t", "kind": "code_repair", "fn": "sum_first_n",
                "args": 3}, ex, expected={"value": 6})
    assert tr.outcome == "raised"
    assert tr.failure_signature, "★ 异常要产签名（c 的原料）"
    assert ex.calls == [], "★ 抛异常 ⇒ 没有调用记录（这正是 L622 崩的原因）"
