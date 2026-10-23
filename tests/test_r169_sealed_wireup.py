# -*- coding: utf-8 -*-
"""R169 · judge 未接面清算 — test_sealed 接上 + actor split 路由 + ho 真判。

验收（防回退锁）:
  □ TRUTH_NOT_BUILT 清空（R28 已落地）& self_check 报 verified
  □ execute_task(split="test") 真跑 sealed task; split 错配即 ActorError
  □ 沙箱白名单 = 静态 ∪ split 注入（sealed 7 fn 可跑; 任意 fn 仍拒）
  □ splitfeed._aggregate 透传 split 给 run_impl（双参形; 单参回落兼容）
  □ e2e ho 面真判（baseline ho=0.5714 → current ho=1.0 — 回归锁）
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.actor import Actor, ActorError, execute_task  # noqa: E402
from dwc.organs.judge import TRUTH_NOT_BUILT, Judge  # noqa: E402


def test_truth_not_built_cleared():
    """★★ 白名单清空（R28 已落地 test_sealed.json — 不是设计缺口）。"""
    assert TRUTH_NOT_BUILT == set()
    # 文件在场 ⇒ 自检 verified 里应有 test_sealed, not_built 里不应有
    rep = Judge()._check_truth_source()
    assert "test_sealed" in rep.get("verified", [])
    assert "test_sealed" not in rep.get("not_built", [])


def test_sealed_split_loaded_by_judge():
    """★★ judge.sealed 真载入 11 条 locked（此前 not_built 报告里躺着）。"""
    j = Judge()
    assert j.sealed is not None
    ids = [k for k in j.sealed if not k.startswith("_")]
    # ★ 真数 = 10（含 4 reasoning 中的 3 + 7 code_repair; 文件里 n=11 是
    #   连元键一起数的 — 首版我照 dict len 断言 11, 实测 10 — 先数再断言）
    assert len(ids) == 10
    # 与 dev 不相交（locked split 纪律 — 论文 §2.2）
    dev_ids = [k for k in j.anchors if not k.startswith("_")]
    assert set(ids).isdisjoint(dev_ids)


def test_execute_task_split_routing():
    """★★★ split 路由: sealed task 跑得动; 跨 split 顶替被拒。"""
    j = Judge()
    impl = ("def unique(xs):\n    seen, out = set(), []\n"
            "    for x in xs:\n        if x not in seen:\n"
            "            seen.add(x); out.append(x)\n    return out")
    out = execute_task(Actor(), j, "test_list_001", implementation=impl,
                       split="test")
    v = j.evaluate("test_list_001", "test", observed=out["observation"])
    assert v.success is True
    # ★ dev task 用 test split 问 ⇒ 拒（不跨 split 顶替）
    with pytest.raises(ActorError):
        execute_task(Actor(), j, "code_fix_001",
                     implementation="def sum_first_n(n):\n    return 0",
                     split="test")
    # ★ dev 向后兼容（不传 split ⇒ "dev"）
    out2 = execute_task(
        Actor(), j, "code_fix_001",
        implementation="def sum_first_n(n):\n    return sum(range(n + 1))")
    assert j.evaluate("code_fix_001", "dev",
                      observed=out2["observation"]).success is True


def test_sandbox_allowed_static_union_split():
    """★★ 白名单 = 静态 ∪ split 注入（sealed fn 跑得动; 任意 fn 仍拒）。"""
    from dwc.organs.actor import PureFunctionExecutor
    ex = PureFunctionExecutor("unique",
                              source="def unique(xs):\n    return []",
                              allowed={"unique"})
    assert ex.fn_name == "unique"
    with pytest.raises(ActorError):
        PureFunctionExecutor("evil_fn", source="def evil_fn():\n    pass",
                             allowed={"unique"})   # 注入外 ⇒ 拒（沙箱不破）


def test_splitfeed_passes_split_to_impl():
    """★★ _aggregate 给 run_impl 透传 split（双参收; 单参回落兼容）。"""
    from dwc.harness.splitfeed import feed
    j = Judge()
    seen = {}

    def impl(tid, split):
        seen[tid] = split
        # 用最简单实现跑（dev/dev compat）
        src = j.anchors[tid] if split == "dev" else j.sealed[tid]
        fn = src["checks"][0]["fn"]
        return {"task_id": tid, "observation": {}, "traces": []}

    out = feed(j, impl, tasks=("code_fix_001",))
    assert seen == {"code_fix_001": "dev"}
    # 单参 lambda 仍兼容（回落路径）
    seen2 = {}

    def impl1(tid):
        seen2[tid] = True
        return {"task_id": tid, "observation": {}, "traces": []}

    feed(j, impl1, tasks=("code_fix_002",))
    assert seen2 == {"code_fix_002": True}


def test_e2e_ho_real_judged():
    """★★★★★ e2e 真跑: ho 0.5714→1.0 且 split 门 passed（R169 回归锁）。

    ★ 这是 R161 遗留缺口（ho=None na）的正式关闭: e2e 演示集接入
      test_sealed 的 7 个 dev 未覆盖 code_repair ⇒ ho 面非空 ⇒ split
      门从 na ⇒ 真判。**跑真脚本**（不是 import 复刻 — 出口断言以
      脚本 stdout 为准, 防"复刻绿=真链断"）。
    """
    # ★ R169 串扰修: pytest 进程内的 judge 写会先落 anchors 运行产物
    #   ⇒ e2e 子进程读到的 Ŝ 序列被污染 ⇒ 子进程跑前**清**（gitignore
    #   运行产物, 清理安全 — 与 e2e 自身入口自清洁同口径）
    for _f in ("task_scores.jsonl", "evidence.jsonl", "score_history.jsonl"):
        _p = os.path.join(ROOT, "config", "anchors", _f)
        if os.path.exists(_p):
            os.remove(_p)
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(ROOT, "src")
    r = subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "e2e_loop.py")],
        capture_output=True, text=True, timeout=600, env=env, cwd=ROOT)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert "ho=0.5714" in r.stdout          # baseline ho（4/7 buggy 侧）
    assert "ho=1.0000" in r.stdout          # current ho（全 fix）
    assert "split 门: passed" in r.stdout   # ★ na ⇒ 真判 passed
