# -*- coding: utf-8 -*-
"""R258 · ReHarness 后向修订锁（版本链 · grounding · diagnostic gate · demo 环）。

★ 起因: 2610.12668 — forward-only 记忆在分布漂移下 stability 全线负;
  修订必须 grounded 在源轨迹, 当前实例只作反馈（防泄漏）。
"""
import os
import shutil
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from dwc.organs.memory import (MemoryError as DwcMemoryError,  # noqa: E402
                               MemoryKind, MemoryKernel)
from dwc.organs.revision import revise_from_outcome  # noqa: E402


def _mk():
    mem = MemoryKernel()
    nid = mem.remember(MemoryKind.SKILL, {
        "scene": "排序任务", "method": "大数在前",
        "boundary": "仅降序场景", "invalid_conditions": ["升序任务"],
        "recovery_strategies": ["检查任务方向"]})
    return mem, nid


# ════ ① 版本链 ════

def test_revise_version_chain():
    """★★★ 版本链锁: 新节点链 _rev_prev; 旧节点只加指针, 内容原样。"""
    mem, nid = _mk()
    new = mem.revise(nid, {"scene": "排序任务", "method": "大数在前仅降序",
                           "boundary": "降序时; 升序相反",
                           "invalid_conditions": ["升序任务"],
                           "recovery_strategies": ["检查方向"]},
                     source_traj="tr:τ5 排序失败", why="升序任务被误导")
    assert new.node_id != nid
    assert new.payload["_rev_prev"] == nid
    assert new.payload["_rev_src"].startswith("tr:")
    old = mem.get(nid)
    assert old.payload.get("_revised_to") == new.node_id
    assert old.payload["method"] == "大数在前"      # 内容字段原样（守门）
    # 双向可回溯
    assert mem.get(new.payload["_rev_prev"]).node_id == nid


def test_revise_grounding_required():
    """★★★ G2 grounding 锁: 无源轨迹 ⇒ 大声失败（不许无源修订）。"""
    mem, nid = _mk()
    import pytest
    with pytest.raises(DwcMemoryError, match="源轨迹"):
        mem.revise(nid, {"scene": "s", "method": "m", "boundary": "b",
                         "invalid_conditions": [], "recovery_strategies": []},
                   source_traj="", why="w")


def test_revise_only_skill():
    """★★★ 事件流不修订（R104 同族）: FAILURE_SIGNATURE/TRACE 拒绝。"""
    mem = MemoryKernel()
    tid = mem.remember(MemoryKind.TRACE, {"action": "a", "task": "t", "step": 1})
    import pytest
    with pytest.raises(DwcMemoryError, match="只对 SKILL"):
        mem.revise(tid, {"scene": "s", "method": "m", "boundary": "b"},
                   source_traj="x", why="w")


# ════ 检索留痕 ════

def test_retrieval_tracing():
    """★★★ 检索留痕锁: recall_search 后 last_retrieved 可查（修订候选集）。"""
    mem, nid = _mk()
    hits = mem.recall_search("排序", ["大数"], k=3)
    assert hits
    cand_ids = [n.node_id for n in mem.last_retrieved()]
    assert nid in cand_ids


# ════ 触发器（memory 轨）════

class _FakeLLM:
    def __init__(self, text):
        self._t = text
        self.calls = 0

    def complete(self, prompt, *, system=None, max_tokens=1200,
                 json_mode=False, images=None):
        self.calls += 1
        return SimpleNamespace(ok=True, text=self._t, error="", meta={})


def test_revise_from_outcome_diagnostic_gate():
    """★★★ diagnostic gate（§6 poker 教训）: incomplete ⇒ 不修订。"""
    mem, nid = _mk()
    mem.recall_search("排序", ["大数"], k=3)
    llm = _FakeLLM('{"scene": "x", "method": "y", "boundary": "z"}')
    r = revise_from_outcome(mem, llm, task="排序", status="incomplete",
                            fail_why="超时")
    assert r["revised"] == 0 and r["skipped"] == "nondiagnostic"
    assert llm.calls == 0                       # 连 LLM 都不调（零成本）


def test_revise_from_outcome_done_triggers():
    """★★★ 成败明确 ⇒ 修订检索用过的 SKILL（LLM 被调, 新版本落库）。"""
    mem, nid = _mk()
    mem.recall_search("排序", ["大数"], k=3)
    llm = _FakeLLM('{"scene": "排序任务", "method": "降序时大数在前",'
                   ' "boundary": "仅降序"}')
    r = revise_from_outcome(mem, llm, task="排序", status="failed",
                            fail_why="升序被判错")
    assert r["revised"] == 1 and llm.calls == 1
    new = mem.get(r["details"][0]["new"])
    assert new.payload["_rev_prev"] == nid


def test_no_retrieved_no_revision():
    """★★★ 零检索 ⇒ 无候选（不修订没用过的条目）。"""
    mem, _ = _mk()
    r = revise_from_outcome(mem, _FakeLLM("{}"), task="t", status="failed")
    assert r["revised"] == 0 and r["skipped"] == "no_retrieved_skill"


# ════ ④ revision_demo（memory 轨）════

def test_revision_demo():
    """★★★ demo 锁（③）: 修订过的条目进 revision_demo（forward-write 示范）。"""
    mem, nid = _mk()
    mem.recall_search("排序", ["大数"], k=3)
    llm = _FakeLLM('{"scene": "排序任务", "method": "新方法", "boundary": "b"}')
    r = revise_from_outcome(mem, llm, task="排序", status="done")
    assert r["revised"] == 1
    demo = mem.revision_demo()
    assert "修订示例" in demo and "新方法" in demo


# ════ 文件轨（agent 侧）════

def test_revision_lessons_file_track(tmp_path, monkeypatch):
    """★★★ 文件轨锁: 失败任务 ⇒ 规矩 md 修订 + .hist 版本存档 + demo 文件;
      incomplete ⇒ 跳过; 事件流 lessons JSONL 不动。"""
    from dwc import agent_quality as AQ
    # 隔离到 tmp
    monkeypatch.setattr(AQ, "SKILLS_DIR", str(tmp_path / "skills"))
    os.makedirs(AQ.SKILLS_DIR, exist_ok=True)
    sp = os.path.join(AQ.SKILLS_DIR, "exhausted.md")
    with open(sp, "w", encoding="utf-8") as fh:
        fh.write("# 规矩\n\n轮数耗尽前先 final。")
    # 教训文件（recall_lessons 数据源）指向存在 skill 的 fail_mode
    les_p = str(tmp_path / "lessons.jsonl")
    monkeypatch.setattr(AQ, "LESSONS", les_p,
                        raising=False)
    import json
    with open(les_p, "w", encoding="utf-8") as fh:
        fh.write(json.dumps({"task": "跑任务 耗尽", "fail_mode": "exhausted",
                             "detail": "d", "task_id": "T1"}, ensure_ascii=False)
                 + "\n")
    llm = _FakeLLM("轮数耗尽前先 final; 信息不足只读一个最关键文件。")
    # diagnostic gate
    r0 = AQ.revision_lessons("跑任务 耗尽", status="incomplete", llm=llm)
    assert r0["revised"] == [] and r0["skipped"] == "nondiagnostic"
    # failed ⇒ 修订
    r1 = AQ.revision_lessons("跑任务 耗尽", status="failed",
                             fail_why="4 轮读同段", llm=llm)
    assert "exhausted" in r1["revised"]
    assert "信息不足" in open(sp, encoding="utf-8").read()
    hist = os.path.join(AQ.SKILLS_DIR, ".hist")
    assert os.path.isdir(hist) and os.listdir(hist), "旧版必须存档（版本链）"
    demo_p = os.path.join(AQ.SKILLS_DIR, "_revision_demo.md")
    assert os.path.exists(demo_p) and "exhausted" in open(demo_p,
                                                          encoding="utf-8").read()


def test_consolidate_keeps_revised(tmp_path, monkeypatch):
    """★★★ 固化不覆盖修订版（③ — 修订是 forward-write 的上游）。"""
    from dwc import agent_quality as AQ
    monkeypatch.setattr(AQ, "SKILLS_DIR", str(tmp_path / "skills"))
    monkeypatch.setattr(AQ, "LESSONS", str(tmp_path / "l.jsonl"), raising=False)
    os.makedirs(AQ.SKILLS_DIR, exist_ok=True)
    sp = os.path.join(AQ.SKILLS_DIR, "exhausted.md")
    with open(sp, "w", encoding="utf-8") as fh:
        fh.write("修订版规矩（outcome 驱动）。")
    import json
    with open(AQ.LESSONS, "w", encoding="utf-8") as fh:
        for i in range(AQ.SKILL_MIN + 1):
            fh.write(json.dumps({"task": "t%d" % i, "fail_mode": "exhausted",
                                 "detail": "d", "task_id": "T%d" % i}) + "\n")
    made = AQ.consolidate_skills()
    assert "exhausted" not in made, "已修订规矩不许被模板覆盖"
    assert "修订版规矩" in open(sp, encoding="utf-8").read()
