"""H2 · factual SKILL → REFERENCE 迁移：dry-run、保留旧节点、procedural 不动。"""
from __future__ import annotations

from dwc.organs import skill_writer as SW
from dwc.organs.memory import MemoryKernel, MemoryKind


def _fact_skill(mem):
    return mem.remember(MemoryKind.SKILL, {
        "scene": "阶乘",
        "method": "阶乘定义为 n! = n×(n-1)!；5! = 120",
        "boundary": "success_pattern:math",
        "invalid_conditions": "非阶乘任务不适用",
        "recovery_strategies": "重新诊断",
        "skill_kind": "factual",
        "task_id": "T1",
    })


def _proc_skill(mem):
    return mem.remember(MemoryKind.SKILL, {
        "scene": "定位代码符号",
        "method": "先搜索定义，再读取文件，最后核对行号",
        "boundary": "success_pattern:code",
        "invalid_conditions": "非代码定位不适用",
        "recovery_strategies": "重新诊断",
        "skill_kind": "procedural",
        "task_id": "T2",
    })


def test_plan_is_dry_run(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    fid = _fact_skill(mem)
    _proc_skill(mem)
    rep = SW.plan_factual_migration(mem)
    assert rep["n_skills"] == 2
    assert rep["n_actions"] == 1
    assert rep["actions"][0]["node_id"] == fid
    assert SW.reference_count(mem) == 0
    assert mem.get(fid).status == "active"


def test_apply_migrates_only_factual_and_keeps_history(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    fid = _fact_skill(mem)
    pid = _proc_skill(mem)
    rep = SW.migrate_factual(mem, apply=True)
    assert rep["applied"] is True
    assert len(rep["written"]) == 1
    new = rep["written"][0]["new_id"]
    assert SW.reference_count(mem) == 1
    assert mem.get(pid).status == "active"
    assert mem.get(fid).status == "superseded"
    _active = mem._conn.execute(
        "SELECT COUNT(*) FROM memory_node WHERE kind='skill'"
        " AND status='active'").fetchone()[0]
    assert _active == 1
    assert mem.get(new).kind is MemoryKind.REFERENCE
    assert mem.get(new).payload["claim"].startswith("阶乘定义为")
    assert mem.get(new).proof_count >= 1


def test_migration_is_idempotent(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    _fact_skill(mem)
    SW.migrate_factual(mem, apply=True)
    rep2 = SW.migrate_factual(mem, apply=True)
    assert rep2["n_actions"] == 0
    assert rep2["written"] == []


def test_chat_skill_is_skipped_not_migrated(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    cid = mem.remember(MemoryKind.SKILL, {
        "scene": "你现在拥有跨任务上下文记忆了吗",
        "method": "部分具备，建议把结论写入文件。",
        "boundary": "success_pattern:chat",
        "invalid_conditions": "不适用",
        "recovery_strategies": "重新诊断",
        "skill_kind": "chat",
    })
    rep = SW.plan_factual_migration(mem)
    assert rep["n_actions"] == 1
    assert rep["actions"][0]["action"] == "skip"
    assert rep["actions"][0]["why"] == "chat_not_durable"
    out = SW.migrate_factual(mem, apply=True)
    assert out["written"] == []
    assert SW.reference_count(mem) == 0
    assert mem.get(cid).status == "active"
    assert mem.memory_stats()["skill_kind"].get("chat") == 1
