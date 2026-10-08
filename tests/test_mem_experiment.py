# -*- coding: utf-8 -*-
"""mem_guidance_vs_replay 实验的构造与流程测试（离线, 不打真端点）。

★★ 为什么测实验本身
  实验是「V1 假设的第一个对照检验」—— 若树揭示泄了旁支、或三臂 prompt
  不同骨架、或前提（buggy 必须被判 fail）不成立, 对照就是假的。
  ⇒ 锁对照的**干净性**, 而不是锁某个结果方向。
"""
from __future__ import annotations

import ast
import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.experiments.mem_guidance_vs_replay import (  # noqa: E402
    ARMS, MEMO_BUDGET, SEED_MEMORY, TASKS, TRUTH_SOURCE, build_prompt,
    extract_code, make_tree, reveal_path, run_experiment,
)
from dwc.llm.client import LLMResult  # noqa: E402

FIX = {
    "sum_first_n": "def sum_first_n(n):\n    return sum(range(n + 1))",
    "average": "def average(xs):\n    return sum(xs) / len(xs) if xs else 0.0",
    "factorial": ("def factorial(n):\n    r = 1\n"
                  "    for i in range(1, n + 1):\n        r *= i\n    return r"),
    "fibonacci": ("def fibonacci(n):\n    a, b = 0, 1\n"
                  "    for _ in range(n):\n        a, b = b, a + b\n    return a"),
}


class FakeLLM:
    """离线假 LLM: 按 prompt 里的函数名给正确修复（或按开关给垃圾）。"""

    configured = True

    def __init__(self, garbage=False):
        self.garbage = garbage
        self.n = 0

    def complete(self, prompt, *, system=None, **kw):
        self.n += 1
        if self.garbage:
            return LLMResult(ok=True, text="我觉得这样挺好（无代码）",
                             source="llm")
        for fn, code in FIX.items():
            if fn in prompt:
                return LLMResult(ok=True, text="```python\n%s\n```" % code,
                                 source="llm")
        return LLMResult(ok=True, text="def unknown():\n    pass",
                         source="llm")


# ══════════════════════════════════════════════════════════
# 树与 prefix-only 揭示
# ══════════════════════════════════════════════════════════

def test_tree_layers_c_then_q():
    """根 → c → q → 叶 三层（c/q 词汇 = judge.classify_c/q 实测值域）。"""
    t = make_tree(SEED_MEMORY)
    assert set(t["c_branches"]) == {"E_VALUE", "E_OFF_BY_ONE", "E_TYPE",
                                    "E_NO_RESULT", "E_NONE"}
    assert "wrong_magnitude" in t["c_branches"]["E_VALUE"]
    assert "off_by_one_in_range" in t["c_branches"]["E_OFF_BY_ONE"]


def test_reveal_requires_both_c_and_q():
    """★ prefix-only: c 缺 ⇒ 零揭示; c 在 q 缺 ⇒ 只有结构事实。"""
    t = make_tree(SEED_MEMORY)
    items, s = reveal_path(t, "E_NOT_EXIST", "whatever")
    assert items == [] and "零揭示" in s
    items2, s2 = reveal_path(t, "E_OFF_BY_ONE", "not_a_q")
    assert items2 == [] and "未揭示" in s2 and "分支存在" in s2


def test_reveal_path_returns_matching_leaves():
    """路径命中 ⇒ 揭示该 (c,q) 的叶子。"""
    t = make_tree(SEED_MEMORY)
    items, s = reveal_path(t, "E_OFF_BY_ONE", "off_by_one_in_range")
    assert len(items) == 1 and items[0]["scene"] == "斐波那契少迭代一轮"
    assert "已揭示 1 条" in s
    # 001–003 的路径: E_VALUE/wrong_magnitude 三条全揭
    items2, _ = reveal_path(t, "E_VALUE", "wrong_magnitude")
    assert len(items2) == 3
    # ★ 同 c 异 q 且 q 不存在 ⇒ c 分支在但叶不揭（prefix-only 部分揭示）
    items3, s3 = reveal_path(t, "E_VALUE", "no_such_q")
    assert items3 == [] and "分支存在" in s3 and "未揭示" in s3
    # 干扰叶（同 c 的另一条 q）不随路径泄露
    items4, _ = reveal_path(t, "E_VALUE", "wrong_magnitude")
    assert all(x["q"] == "wrong_magnitude" for x in items4)


def test_replay_block_never_leaks_side_branches():
    """★★ 关键: replay 臂的文本**不得**含旁支内容（否则对照被污染）。

    覆盖两种旁支: 异 c（E_TYPE）与**同 c 异 q**（E_VALUE/guard_missing）。
    """
    t = make_tree(SEED_MEMORY)
    items, s = reveal_path(t, "E_OFF_BY_ONE", "off_by_one_in_range")
    block = build_prompt("replay", "t", "def f(): pass",
                         memo_items=items, replay_summary=s)
    assert "斐波那契少迭代一轮" in block          # 路径内容在
    assert "字符串当数字比" not in block            # 旁支(异 c)不泄
    assert "空序列没护栏" not in block              # 旁支(同 c 异 q)不泄
    assert "累加和少算一项" not in block            # 同 c 另一 q 的叶也不泄


# ══════════════════════════════════════════════════════════
# 三臂 prompt 骨架
# ══════════════════════════════════════════════════════════

def test_none_arm_has_no_memory():
    """C 臂: 零记忆（下界）。"""
    p = build_prompt("none", "t", "def f(): pass")
    assert "过往经验" not in p and "回放树" not in p


def test_guidance_arm_has_all_memory_flat():
    """A 臂: 全部记忆平铺（≤ 预算上限）。"""
    p = build_prompt("guidance", "t", "def f(): pass",
                     memo_items=SEED_MEMORY[:MEMO_BUDGET])
    assert "累加和少算一项" in p and "布尔极性反了" in p
    assert len(SEED_MEMORY) == MEMO_BUDGET


def test_same_skeleton_across_arms():
    """★ 对照干净性: 三臂的任务骨干部逐字相同（只有记忆块不同）。"""
    kw = dict(task_id="t", buggy="def f():\n    return 1")
    bodies = []
    for arm in ARMS:
        p = build_prompt(arm, **kw)
        i = p.find("修复下面")
        assert i >= 0, arm
        bodies.append(p[i:])
    assert bodies[0] == bodies[1] == bodies[2]


def test_memory_block_contains_only_memory_lines():
    """★★ 盲区补锁（破坏②实测漏网）: 记忆块里**只许**有记忆条目与表头 ——

    夹带任务指令（如「必须用记忆里的方法」）会单方面约束某一臂 ⇒ 对照被污染。
    骨架比对只看「修复下面」之后, 抓不到这里 ⇒ 本测试逐行锁前缀。
    """
    t = make_tree(SEED_MEMORY)
    items, s = reveal_path(t, "E_VALUE", "wrong_magnitude")
    heads = {
        "guidance": build_prompt("guidance", "t", "def f(): pass",
                                 memo_items=SEED_MEMORY[:MEMO_BUDGET]),
        "replay": build_prompt("replay", "t", "def f(): pass",
                               memo_items=items, replay_summary=s),
    }
    allowed = ("过往经验（历史教训, 直接参考）:", "过往经验回放树:",
               "沿路径已揭示的经验:", "- [")
    for arm, p in heads.items():
        head = p[:p.find("修复下面")]
        for line in head.split("\n"):
            s_ = line.strip()
            if not s_:
                continue
            assert s_.startswith(allowed), \
                "★ %s 臂的记忆块混入非记忆行: %r" % (arm, s_[:60])


def test_unknown_arm_rejected():
    """阳性: 未知臂 ⇒ 报错（不静默混入对照）。"""
    with pytest.raises(ValueError, match="未知臂"):
        build_prompt("cheat", "t", "def f(): pass")


# ══════════════════════════════════════════════════════════
# 代码抽取
# ══════════════════════════════════════════════════════════

def test_extract_code_from_fence_and_bare():
    assert extract_code("```python\ndef a():\n    pass\n```") is not None
    assert extract_code("def a():\n    pass") is not None
    assert extract_code("def a(:\n    broken") is None     # 语法坏 ⇒ None
    assert extract_code("") is None


# ══════════════════════════════════════════════════════════
# 全流程（FakeLLM 离线, judge 真跑）
# ══════════════════════════════════════════════════════════

def test_experiment_premise_buggy_must_fail():
    """★ 实验前提: buggy 实现必须被判 fail —— run 内置前提检查。"""
    res = run_experiment(FakeLLM(), repeat=1, tasks={
        "code_fix_001": TASKS["code_fix_001"]})
    errs = [r for r in res["records"] if "前提失败" in r.get("error", "")]
    assert not errs, "前提崩了: %s" % errs
    # 且 buggy 的真实签名被用作 B 臂路径依据
    rows = [r for r in res["records"] if r["arm"] == "replay"]
    assert rows and rows[0]["sig_c"] and rows[0]["sig_c"].startswith("E_")


def test_experiment_full_loop_counts_and_verdict():
    """FakeLLM 给 golden 修复 ⇒ 三臂全 pass, 汇总/verdict 字段齐（4 任务×2）。"""
    res = run_experiment(FakeLLM(), repeat=2, tasks=TASKS)
    for arm in ARMS:
        s = res["arms"][arm]
        assert s["n_calls"] == 4 * 2, (arm, s)      # 4 任务 × 2 重复
        assert s["n_llm_ok"] == s["n_calls"]
        assert s["n_pass"] == s["n_calls"], (arm, s)  # golden 修复全过 judge
        assert s["pass_rate"] == 1.0
    v = res["verdict"]
    assert v["v1_memory_useful"] is False           # none 也是 1.0 ⇒ 记忆无增益
    assert v["paper_direction_replay_gt_guidance"] is False
    # 预算对等审计: guidance 恒 8 条, replay 按真实路径命中(1 或 3 条)
    assert res["arms"]["guidance"]["memo_n_per_call"] == [MEMO_BUDGET]
    assert res["arms"]["none"]["memo_n_per_call"] == [0]
    rp = res["arms"]["replay"]["memo_n_per_call"]
    assert all(0 <= n <= MEMO_BUDGET for n in rp)
    assert 1 in rp and 3 in rp, "路径命中应分档: 004=1 条, 001–003=3 条, 实得 %s" % rp


def test_experiment_garbage_reply_counted_not_passed():
    """垃圾回复 ⇒ parsed=False 计入降级, 不算 pass（不静默）。"""
    res = run_experiment(FakeLLM(garbage=True), repeat=1, tasks={
        "code_fix_001": TASKS["code_fix_001"]})
    s = res["arms"]["guidance"]
    assert s["n_llm_ok"] == 1 and s["n_parsed"] == 0 and s["n_pass"] == 0
    errs = [r for r in res["records"] if "不可解析" in r.get("error", "")]
    assert errs


def test_truth_source_declared():
    """G2: 实验模块声明真值源。"""
    assert "judge" in TRUTH_SOURCE["真值源位置"]
