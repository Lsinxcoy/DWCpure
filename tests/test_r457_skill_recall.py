# -*- coding: utf-8 -*-
"""R457 · skill 记忆产出 + recall 进任务选择。

守四件事：
  1. 只有"成功做法"能变成 SKILL（失败类/缺字段一律不写 —— D6 fail-closed）
  2. 同一做法只写一次（幂等：重复跑 promote 不增长）
  3. 记账四个数必须对得上（n_seen = written + dup + skip）
  4. 选择口径：失败过的最优先，没跑过的其次，跑过没失败的最后；冷却让位
"""
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if os.path.join(_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "src"))

from dwc.organs import skill_writer as SW       # noqa: E402
from dwc.organs import task_recall as TR        # noqa: E402
from dwc.organs.memory import MemoryKernel, MemoryKind  # noqa: E402


def _lesson(task="查某个符号在哪个文件", detail="先搜索定义，再读取文件，最后核对 x.py",
            fail_mode="success_pattern:code-locate", task_id="T1"):
    return {"task": task, "detail": detail, "fail_mode": fail_mode,
            "task_id": task_id, "quality": 0.75, "at": 1.0}


# ── skill_writer ──────────────────────────────────────────────────────
def test_lesson_to_payload_has_all_d6_fields():
    p = SW.lesson_to_payload(_lesson())
    for k in ("scene", "method", "boundary",
              "invalid_conditions", "recovery_strategies"):
        assert p and p.get(k), "缺 D6 字段 %s" % k


def test_failure_lesson_is_not_a_skill():
    assert SW.lesson_to_payload(_lesson(fail_mode="wrong_result")) is None


def test_lesson_without_detail_is_rejected():
    assert SW.lesson_to_payload(_lesson(detail="")) is None


def test_promote_writes_and_is_idempotent(tmp_path):
    mem = MemoryKernel(db_path=str(tmp_path / "m.db"))
    p = tmp_path / "lessons.jsonl"
    rows = [_lesson(task_id="A"),
            _lesson(task_id="B", task="另一个任务",
                    detail="成功做法（answer contains 'y.py'）：换路径取证"),
            _lesson(task_id="C", fail_mode="wrong_result")]
    p.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows),
                 encoding="utf-8")

    r1 = SW.promote_pending(mem, path=str(p))
    assert r1["n_written"] == 2, r1
    assert r1["n_skip"] == 1, r1
    assert r1["n_seen"] == r1["n_written"] + r1["n_dup"] + r1["n_skip"]
    # ★ H2 · 一条 procedural 写 SKILL；一条 factual 写 REFERENCE
    assert SW.skill_count(mem) == 1
    assert SW.reference_count(mem) == 1

    r2 = SW.promote_pending(mem, path=str(p))
    assert r2["n_written"] == 0 and r2["n_dup"] == 2, r2
    assert SW.skill_count(mem) == 1, "重复跑不许增长"
    assert SW.reference_count(mem) == 1, "重复跑不许增长"


def test_promoted_skill_is_readable_by_memory_text(tmp_path):
    """★ 关键接线：写进去的东西必须能被 memory_text 按任务召回。"""
    from dwc.llm.executor import memory_text
    mem = MemoryKernel(db_path=str(tmp_path / "m.db"))
    p = tmp_path / "lessons.jsonl"
    p.write_text(json.dumps(_lesson(), ensure_ascii=False), encoding="utf-8")
    SW.promote_pending(mem, path=str(p))
    got = memory_text(mem, "查某个符号在哪个文件")
    assert "x.py" in got


def test_memory_text_is_scoped_to_the_task(tmp_path):
    """没有相关做法 ⇒ 空；不许把全库倒进 prompt。"""
    from dwc.llm.executor import memory_text
    mem = MemoryKernel(db_path=str(tmp_path / "m.db"))
    p = tmp_path / "lessons.jsonl"
    p.write_text(json.dumps(_lesson(), ensure_ascii=False), encoding="utf-8")
    SW.promote_pending(mem, path=str(p))
    assert memory_text(mem, "") == ""
    assert memory_text(mem, "完全无关的另一个领域的问题") == ""
    assert memory_text(mem, "查某个符号在哪个文件") != ""


# ── task_recall ───────────────────────────────────────────────────────
def test_rank_failed_first_then_unrun_then_used():
    stats = {"failed": {"n_fail": 3, "n_skill": 0},
             "clean": {"n_fail": 0, "n_skill": 0}}
    used = ["failed", "clean"]
    assert TR.rank_key("failed", stats, used)[0] == 0
    assert TR.rank_key("brand_new", stats, used)[0] == 1
    assert TR.rank_key("clean", stats, used)[0] == 2


def test_pick_prefers_failure_over_rotation():
    stats = {"a": {"n_fail": 2, "n_skill": 0}, "b": {"n_fail": 0, "n_skill": 0}}
    got = TR.pick(["a", "b"], stats, used=["a", "b"])
    assert got == "a"


def test_pick_skips_cooldown():
    stats = {"a": {"n_fail": 9, "n_skill": 0}}
    assert TR.pick(["a", "b"], stats, cooldown=["a"], used=["a", "b"]) == "b"


def test_pick_returns_empty_when_all_cooling():
    assert TR.pick(["a"], {}, cooldown=["a"]) == ""


def test_task_stats_counts_failures_by_task(tmp_path):
    mem = MemoryKernel(db_path=str(tmp_path / "m.db"))
    mem.remember(MemoryKind.FAILURE_SIGNATURE,
                 {"c": "E_VALUE", "q": "wrong", "m": "x", "task": "t1"})
    mem.remember(MemoryKind.FAILURE_SIGNATURE,
                 {"c": "E_VALUE", "q": "wrong", "m": "y", "task": "t1"})
    mem.remember(MemoryKind.FAILURE_SIGNATURE,
                 {"c": "E_TYPE", "q": "wrong", "m": "z", "task": "t2"})
    st = TR.task_stats(mem)
    assert st["t1"]["n_fail"] == 2
    assert st["t2"]["n_fail"] == 1
