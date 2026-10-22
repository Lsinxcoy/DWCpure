# -*- coding: utf-8 -*-
"""R431 · "只答X"类任务用 `first_key` 判据（rf08 假通过）。

★★★ 现场（2026-10-22 17:05，rf08）：
    模型答：
      「prev（保留键 `prev`；修订实现里内部也会见到 `_rev_prev`，
        但对外链回旧节点的键名就是 `prev`）」

    `check: {type: contains, target: "_rev_prev"}` ⇒ 命中 ⇒ **判 ✓**。

    答案明确是错的（它说键名就是 `prev`），判据却给了分。
    ⇒ 池 A 的 51/54 里有一分是白送的。

★ 规则：判据不许给白送分。对"只答X"类任务，
  **谁先出现，谁就是模型给出的答案**；正确答案必须排最前。

★ 为什么不用 `answer == target`：任务允许模型补一句解释，
  太严会把正确答案判死（rf05 那种"…是 MemoryKernel（定义于 …）"）。
  `first_key` 只看顺序，不看写法。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_bench2 as B  # noqa: E402

CHECK = {"type": "first_key", "target": ["_rev_prev", "prev"]}


def test_wrong_answer_mentioning_right_one_fails():
    """★★★ 现场原句：先说 prev、再提 _rev_prev ⇒ 必须判 ✗。"""
    ans = ("prev（保留键 `prev`；修订实现里内部也会见到 `_rev_prev`，"
           "但对外链回旧节点的键名就是 `prev`）")
    ok, how = B.verify(CHECK, ans)
    assert ok is False, how
    assert "first-key 'prev'" in how


def test_correct_answer_first_passes():
    """★★ 正确答案在前 ⇒ ✓（`prev` 是子串也不影响）。"""
    for ans in ("_rev_prev",
                "`_rev_prev`（保留键）",
                "_rev_prev，不是 prev"):
        ok, how = B.verify(CHECK, ans)
        assert ok is True, (ans, how)


def test_explained_correct_answer_still_passes():
    """★★ 允许补一句解释（别把正确答案判死）。"""
    ans = "记忆修订的新节点用 `_rev_prev` 链回旧节点。"
    ok, how = B.verify(CHECK, ans)
    assert ok is True, how


def test_missing_both_is_fail():
    """★★ 两个键都没出现 ⇒ ✗（不能因为"没答"就算过）。"""
    ok, how = B.verify(CHECK, "不知道")
    assert ok is False
    assert "pos None" in how


def test_contains_still_unchanged():
    """★★ 其它任务的 `contains` 语义不许被顺手改掉。"""
    ok, how = B.verify({"type": "contains", "target": "MemoryKernel"},
                       "内核是 MemoryKernel（定义于 x.py:1）")
    assert ok is True
    ok2, _ = B.verify({"type": "contains", "target": "MemoryKernel"}, "不知道")
    assert ok2 is False
