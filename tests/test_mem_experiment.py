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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.experiments.mem_guidance_vs_replay import (  # noqa: E402
    ARMS, HARD_PATH, MEMO_BUDGET, SEED_HIT, SEED_MEMORY, TASKS, TRUTH_SOURCE,
    _HardSandbox, _realistic_distractors, build_prompt, extract_code,
    hard_fns, hard_judge, hard_sources, make_tree, reveal_path,
    run_experiment,
)
from dwc.llm.client import LLMResult  # noqa: E402

FIX = {
    "sum_first_n": "def sum_first_n(n):\n    return sum(range(n + 1))",
    "average": "def average(xs):\n    return sum(xs) / len(xs) if xs else 0.0",
    "factorial": ("def factorial(n):\n    r = 1\n"
                  "    for i in range(1, n + 1):\n        r *= i\n    return r"),
    "fibonacci": ("def fibonacci(n):\n    a, b = 0, 1\n"
                  "    for _ in range(n):\n        a, b = b, a + b\n    return a"),
    "is_palindrome": ("def is_palindrome(s):\n"
                      "    return s.lower() == s[::-1].lower()"),
    "reverse_string": "def reverse_string(s):\n    return s[::-1]",
}
#: hard 任务的 golden 修复（离线 Fake 用; 真实验由真 LLM 产）
FIX.update({
    "is_leap": ("def is_leap(year):\n"
                "    return year % 400 == 0 or (year % 4 == 0 and year % 100 != 0)"),
    "caesar": ("def caesar(s, k):\n"
               "    out = []\n"
               "    for ch in s:\n"
               "        if 'a' <= ch <= 'z':\n"
               "            out.append(chr((ord(ch) - 97 + k) % 26 + 97))\n"
               "        elif 'A' <= ch <= 'Z':\n"
               "            out.append(chr((ord(ch) - 65 + k) % 26 + 65))\n"
               "        else:\n"
               "            out.append(ch)\n"
               "    return ''.join(out)"),
    "median": ("def median(xs):\n"
               "    if not xs:\n        return 0.0\n"
               "    s = sorted(xs)\n    n = len(s)\n"
               "    m = n // 2\n"
               "    return s[m] if n % 2 else (s[m - 1] + s[m]) / 2"),
    "chunk": ("def chunk(s, n):\n"
              "    if not s or n <= 0:\n        return []\n"
              "    return [s[i:i + n] for i in range(0, len(s), n)]"),
    "clamp": ("def clamp(v, lo, hi):\n"
              "    if lo > hi:\n        lo, hi = hi, lo\n"
              "    return min(max(v, lo), hi)"),
})


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
    assert "干扰经验" not in block                # 36 条程序干扰一条不泄
    assert "参数没归一" not in block              # 异 c 干扰场景不泄
    assert "累加和少算一项" not in block          # 同 c 另一 q 的叶也不泄


# ══════════════════════════════════════════════════════════
# 三臂 prompt 骨架
# ══════════════════════════════════════════════════════════

def test_none_arm_has_no_memory():
    """C 臂: 零记忆（下界）。"""
    p = build_prompt("none", "t", "def f(): pass")
    assert "过往经验" not in p and "回放树" not in p


def test_guidance_arm_has_all_memory_flat():
    """A 臂: 全部记忆平铺（= 全库 40 条, 稀释效应的注射器）。"""
    assert len(SEED_MEMORY) == 40 and len(SEED_HIT) == 4
    p = build_prompt("guidance", "t", "def f(): pass",
                     memo_items=SEED_MEMORY[:MEMO_BUDGET])
    assert "累加和少算一项" in p                    # 命中项在
    assert "干扰经验" in p                          # 干扰也全平铺进来
    assert len(SEED_MEMORY) == MEMO_BUDGET


def test_same_skeleton_across_arms():
    """★ 对照干净性: 三臂的任务骨干部逐字相同（code 与 qa 两种骨架都测）。"""
    for kwargs in (dict(material="def f():\n    return 1"),
                   dict(material="排序的最坏情况", material_kind="qa")):
        bodies = []
        for arm in ARMS:
            p = build_prompt(arm, "t", **kwargs)
            anchor = ("修复下面" if kwargs.get("material_kind") != "qa"
                      else "直接回答下面问题")
            i = p.find(anchor)
            assert i >= 0, arm
            bodies.append(p[i:])
        assert bodies[0] == bodies[1] == bodies[2], kwargs


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
    """FakeLLM 给 golden 修复 ⇒ 六任务三臂全 pass（早停 1 轮）· 汇总字段齐。"""
    res = run_experiment(FakeLLM(), repeat=2, tasks=TASKS, rounds=2)
    for arm in ARMS:
        s = res["arms"][arm]
        assert s["n_trials"] == 6 * 2, (arm, s)      # 6 behavior × 2 重复
        assert s["n_trials_passed"] == s["n_trials"], (arm, s)
        assert s["pass_rate"] == 1.0
        assert s["n_calls"] == 6 * 2, \
            "Fake 全过 ⇒ 每 trial 早停 1 轮, calls 应= trials, 实得 %s" % s["n_calls"]
    v = res["verdict"]
    assert v["v1_memory_useful"] is False           # none 也是 1.0 ⇒ 记忆无增益
    assert v["paper_direction_replay_gt_guidance"] is False
    # 预算审计: guidance=全库 40; replay 按真实签名分档 {0,1,3}
    #   （001–003=3 · 004=1 · 005/006 签名在树外=0 —— 事前实测值）
    assert res["arms"]["guidance"]["memo_n_per_call"] == [MEMO_BUDGET]
    assert res["arms"]["none"]["memo_n_per_call"] == [0]
    assert res["arms"]["replay"]["memo_n_per_call"] == [0, 1, 3], \
        res["arms"]["replay"]["memo_n_per_call"]


def test_seed_structure_hit_and_distractors():
    """★ 种子结构: 40 = 4 命中 + 36 干扰; 干扰 (c,q) 不落进命中路径。"""
    from dwc.experiments.mem_guidance_vs_replay import _distractors
    dis = _distractors()
    assert len(dis) == 36
    hit_paths = {("E_VALUE", "wrong_magnitude"),
                 ("E_OFF_BY_ONE", "off_by_one_in_range")}
    for d in dis:
        assert (d["c"], d["q"]) not in hit_paths, \
            "★ 干扰泄进命中路径: %s" % d
    assert len(SEED_MEMORY) == 40


def test_qa_channel_keyword_match_with_round2_feedback():
    """★ qa 通道: keyword_match 判分 + 第 2 轮**臂中立**反馈补关键词。"""
    class QAFake:
        configured = True

        def __init__(self):
            self.n = 0

        def complete(self, prompt, *, system=None, **kw):
            self.n += 1
            if "上一轮" in prompt:                  # 反馈到了才补关键词
                return LLMResult(ok=True, source="llm",
                                 text="快速排序最坏情况由 pivot 选择失衡造成，"
                                      "递归深度退化为 n，整体为最坏 O(n²)。")
            return LLMResult(ok=True, source="llm",
                             text="快排平均很快。")   # 缺全部关键词

    res = run_experiment(QAFake(), repeat=1, rounds=2,
                         tasks={}, qa=True)
    rows = [r for r in res["records"] if r["task"] == "reasoning_001"
            and r["arm"] == "none"]
    assert len(rows) == 2, rows                     # R1 fail → R2 pass
    assert rows[0]["pass_"] is False and rows[1]["pass_"] is True
    assert res["arms"]["none"]["n_trials"] == 4      # 4 条 reasoning 全跑
    # 臂中立反馈: build_prompt 注入的 feedback 三臂同文
    fb = "同一段反馈文本"
    bodies = [build_prompt(a, "t", "问题", material_kind="qa", feedback=fb)
              for a in ARMS]
    assert all(fb in b for b in bodies)
    tail = [b[b.find("上一轮尝试与判分反馈"):] for b in bodies]
    assert tail[0] == tail[1] == tail[2]


def test_early_stop_after_first_pass():
    """★ 早停: 第 1 轮就 pass ⇒ 该 trial 不再跑第 2 轮。"""
    res = run_experiment(FakeLLM(), repeat=1, rounds=3, tasks=TASKS)
    assert all(r["n_calls"] == 6 * 1 for r in
               (res["arms"][a] for a in ARMS)), \
        {a: res["arms"][a]["n_calls"] for a in ARMS}
    assert all(len({r["round"] for r in res["records"]
                    if r["arm"] == a}) == 1 for a in ARMS)


def test_experiment_garbage_reply_counted_not_passed():
    """垃圾回复 ⇒ parsed=False 计入降级, 不算 pass（不静默）。"""
    res = run_experiment(FakeLLM(garbage=True), repeat=1, tasks={
        "code_fix_001": TASKS["code_fix_001"]})
    s = res["arms"]["guidance"]
    assert s["n_llm_ok"] == 1 and s["n_parsed"] == 0 \
        and s["n_trials_passed"] == 0
    errs = [r for r in res["records"] if "不可解析" in r.get("error", "")]
    assert errs


def test_truth_source_declared():
    """G2: 实验模块声明真值源。"""
    assert "judge" in TRUTH_SOURCE["真值源位置"]


# ══════════════════════════════════════════════════════════
# R65 · 硬战场（hard dataset）
# ══════════════════════════════════════════════════════════

def test_hard_anchor_loads_and_premise():
    """hard 锚点: judge 同一逻辑可加载 · 5 题 checks≥5 · 基线全 fail（前提）。"""
    from dwc.organs.actor import Actor, execute_task
    assert os.path.exists(HARD_PATH)
    j = hard_judge()
    srcs = hard_sources(j)
    assert len(srcs) == 5, list(srcs)
    assert sorted(hard_fns(j)) == ["caesar", "chunk", "clamp", "is_leap",
                                   "median"], hard_fns(j)
    with _HardSandbox(hard_fns(j)):
        for tid, buggy in srcs.items():
            rec = j.anchors[tid]
            assert rec["verifier_kind"] == "behavior"
            assert len(rec["checks"]) >= 5, (tid, len(rec["checks"]))
            obs = execute_task(Actor(), j, tid, implementation=buggy)[
                "observation"]
            v = j.evaluate(tid, "dev", observed=obs)
            assert v.success is False, "★ %s 基线过了 ⇒ 前提不成立" % tid


def test_hard_sandbox_expands_then_restores():
    """★ 白名单: 具名扩 → 跑 → 必须恢复（含异常路径）。"""
    from dwc.organs.actor import PureFunctionExecutor as P
    before = P.ALLOWED
    with _HardSandbox(["is_leap"]):
        assert "is_leap" in P.ALLOWED
        assert set(before) <= set(P.ALLOWED)
    assert P.ALLOWED == before, "★ 白名单没恢复"
    try:
        with _HardSandbox(["caesar"]):
            raise RuntimeError("模拟中途异常")
    except RuntimeError:
        pass
    assert P.ALLOWED == before, "★ 异常路径白名单没恢复"


def test_realistic_distractors_are_misleading_not_placeholders():
    """★ R65 核心: 干扰是**真实误导措辞**（不是占位）· 恒 36 条 · 避开 exclude。"""
    exclude = {("E_VALUE", "wrong_magnitude"),
               ("E_OFF_BY_ONE", "off_by_one_in_range")}
    dis = _realistic_distractors(exclude)
    assert len(dis) == 36
    for d in dis:
        assert (d["c"], d["q"]) not in exclude, "★ 没避开签名: %s" % d
        assert "占位" not in d["fix_hint"] and "供稀释对照" not in d["fix_hint"], \
            "★ 还是占位文本: %s" % d["fix_hint"]
    hints = {d["fix_hint"] for d in dis}
    assert "range 是右开区间, 千万别手贱 +1, 多算是初学者错误" in hints
    assert len(hints) >= 12                     # 措辞不单一


def test_hard_run_offline_fake_full_pass():
    """hard 离线全流程: Fake 给 golden ⇒ 5 题三臂全过 · replay 恒零揭示（避让）。"""
    res = run_experiment(FakeLLM(), repeat=1, rounds=2, dataset="hard")
    assert res["dataset"] == "hard" and res["n_tasks"] == 5
    # 无前提失败（buggy 全 fail 已验）
    assert not [r for r in res["records"] if "前提失败" in r.get("error", "")]
    for arm in ARMS:
        s = res["arms"][arm]
        assert s["n_trials"] == 5 and s["n_trials_passed"] == 5, (arm, s)
        assert s["n_calls"] == 5, "全过早停 ⇒ 1 call/trial, %s" % arm
    assert res["arms"]["guidance"]["memo_n_per_call"] == [36]
    # ★ 避让设计: hard 签名不在树里 ⇒ replay 每次都零揭示
    assert res["arms"]["replay"]["memo_n_per_call"] == [0], \
        res["arms"]["replay"]["memo_n_per_call"]


def test_dataset_arg_validated():
    """阳性: 非法 dataset ⇒ 报错不静默。"""
    with pytest.raises(ValueError, match="dataset"):
        run_experiment(FakeLLM(), dataset="dev_test")


# ══════════════════════════════════════════════════════════
# R66 · 记忆增长 + 跨任务迁移（grown）
# ══════════════════════════════════════════════════════════

def _real_verdict_of_hard(tid):
    """真 judge 跑 hard buggy 拿一个真实失败 verdict。"""
    from dwc.organs.actor import Actor, execute_task
    from dwc.experiments.mem_guidance_vs_replay import (
        _HardSandbox, hard_fns, hard_judge, hard_sources)
    j = hard_judge()
    with _HardSandbox(hard_fns(j)):
        obs = execute_task(Actor(), j, tid,
                           implementation=hard_sources(j)[tid])["observation"]
    return j.evaluate(tid, "dev", observed=obs)


def test_grown_memory_written_from_real_verdict():
    """★★ R66 写入侧: 记忆条目 = judge 真实判分产物（不是合成/占位）。"""
    from dwc.experiments.mem_guidance_vs_replay import _memory_from_verdict
    v = _real_verdict_of_hard("hard_005_clamp")
    assert v.success is False
    m = _memory_from_verdict("hard_005_clamp", v)
    assert m["scene"] == "hard_005_clamp" and m["origin"] == "hard_005_clamp"
    assert (m["c"], m["q"]) == ("E_VALUE", "wrong_magnitude")  # 真签名
    # fix_hint 必须来自 diffs（fn/期望/实得）—— 真实可迁移的经验
    assert "上次实测失败" in m["fix_hint"] and "期望" in m["fix_hint"]
    assert "clamp" in m["fix_hint"]
    assert "占位" not in m["fix_hint"]


def test_grown_offline_full_flow_with_migration_reveal():
    """★ grown 离线全流程: 写入 5 条真记忆 → 消费 4 题三臂 · 迁移揭示分档。

    ★★ 迁移通道（事前结构事实）: dev001-003 与 hard_005 同签名,
    dev004 与 hard_003 同签名 ⇒ replay 每题恰好揭示 **1 条**长出来的记忆。
    """
    res = run_experiment(FakeLLM(), repeat=1, rounds=2, dataset="grown")
    assert res["dataset"] == "grown" and res["n_tasks"] == 4
    # 写入前提: 无写入失败记录
    assert not [r for r in res["records"]
                if r.get("arm") == "w" and r.get("error")], \
        [r for r in res["records"] if r.get("arm") == "w"]
    assert res["seed_memory"].startswith("★ 5 条**真实增长**"), res["seed_memory"]
    for arm in ARMS:
        s = res["arms"][arm]
        assert s["n_trials"] == 4 and s["n_trials_passed"] == 4, (arm, s)
    # guidance 平铺全部长出来的; none 零; replay 按同族签名揭示 1 条
    assert res["arms"]["guidance"]["memo_n_per_call"] == [5]
    assert res["arms"]["none"]["memo_n_per_call"] == [0]
    assert res["arms"]["replay"]["memo_n_per_call"] == [1], \
        "★ 迁移揭示应每题 1 条（同签名族）, 实得 %s" % \
        res["arms"]["replay"]["memo_n_per_call"]
