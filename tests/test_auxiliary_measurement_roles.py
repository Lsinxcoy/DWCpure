"""W1 · 辅助 LLM 的真实角色与任务归属（离线实测，不打端点）。"""
from __future__ import annotations

import importlib
import json
import os
import sys
from types import SimpleNamespace

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from dwc.observability import context as mc  # noqa: E402


class RecordingLLM:
    configured = True

    def __init__(self, text="{}", *, boom=False):
        self.text = text
        self.boom = boom
        self.calls = 0

    def complete(self, prompt, **kwargs):
        self.calls += 1
        mc.emit_llm_observation({"kind": "aux_test_call"})
        if self.boom:
            raise RuntimeError("synthetic transport failure")
        return SimpleNamespace(ok=True, text=self.text, error=None,
                               source="test", meta={})


@pytest.fixture
def observations(monkeypatch):
    events = []
    monkeypatch.setattr(mc, "_SINK", events.append)
    monkeypatch.setattr(mc, "_STORE", None)
    return events


def only_call(events):
    calls = [e for e in events if e.get("kind") == "aux_test_call"]
    assert len(calls) == 1, calls
    return calls[0]


def test_core_decision_has_task_identity_and_restores_on_error(observations):
    from dwc.core import DWC
    llm = RecordingLLM("remember")
    dwc = DWC(3, 50, llm=llm, executor=lambda task: None)
    task = {"task_id": "T-core", "candidate_id": "C-core",
            "rollout_id": "R-core", "protocol_id": "P-core"}
    assert dwc._decide(task)["action"] == "remember"
    event = only_call(observations)
    assert event["call_role"] == "decision"
    assert {k: event[k] for k in
            ("task_id", "candidate_id", "rollout_id", "protocol_id")} == task

    observations.clear()
    failing = DWC(3, 50, llm=RecordingLLM(boom=True),
                  executor=lambda task: None)
    assert failing._decide({"task_id": "T-core-error"})["source"] == "heuristic"
    assert only_call(observations)["call_role"] == "decision"
    mc.emit_llm_observation({"kind": "after_error"})
    assert observations[-1]["call_role"] == "solver"
    assert "task_id" not in observations[-1]


def test_agent_quality_review_uses_real_lesson_task(observations, tmp_path,
                                                    monkeypatch):
    from dwc import agent_quality as aq
    monkeypatch.setattr(aq, "SKILLS_DIR", str(tmp_path))
    (tmp_path / "exhausted.md").write_text("old rule", encoding="utf-8")
    monkeypatch.setattr(aq, "recall_lessons", lambda task, k: [
        {"task_id": "T-review", "fail_mode": "exhausted"}])
    result = aq.revision_lessons("task text", status="failed",
                                 llm=RecordingLLM("new rule"))
    assert result["revised"] == ["exhausted"]
    event = only_call(observations)
    assert event["call_role"] == "review"
    assert event["task_id"] == "T-review"

    observations.clear()
    (tmp_path / "exhausted.md").write_text("old rule", encoding="utf-8")
    aq.revision_lessons("task text", status="failed",
                        llm=RecordingLLM(boom=True))
    assert only_call(observations)["call_role"] == "review"


def test_memory_revision_role_and_exception_path(observations):
    from dwc.organs.memory import MemoryKernel, MemoryKind
    from dwc.organs.revision import revise_from_outcome
    mem = MemoryKernel(":memory:")
    mem.remember(MemoryKind.SKILL, {
        "scene": "sort", "method": "old", "boundary": "b",
        "invalid_conditions": ["none"], "recovery_strategies": ["retry"]})
    mem.recall_search("sort", ["old"], k=3)
    result = revise_from_outcome(
        mem, RecordingLLM('{"scene":"sort","method":"new","boundary":"b"}'),
        task="sort task", status="failed")
    assert result["revised"] == 1
    assert only_call(observations)["call_role"] == "revision"

    observations.clear()
    mem.recall_search("sort", ["new"], k=3)
    revise_from_outcome(mem, RecordingLLM(boom=True), task="sort task",
                        status="failed")
    error_calls = [e for e in observations if e.get("kind") == "aux_test_call"]
    assert error_calls
    assert all(e["call_role"] == "revision" for e in error_calls)


def test_planner_role_and_task_from_task_view(observations):
    from dwc.organs.planner import craft
    llm = RecordingLLM(
        '{"kind":"bounded_param","params":{"l":1,"u":8}}')
    made, trace = craft({"task_id": "T-planner", "candidate_id": "C-planner"},
                        llm)
    assert made is not None and trace["outcome"] == "crafted"
    event = only_call(observations)
    assert event["call_role"] == "planner"
    assert event["task_id"] == "T-planner"
    assert event["candidate_id"] == "C-planner"

    observations.clear()
    with pytest.raises(RuntimeError, match="synthetic"):
        craft({"task_id": "T-planner-error"}, RecordingLLM(boom=True))
    assert only_call(observations)["call_role"] == "planner"


def test_memory_expansion_preserves_ambient_task_and_error_role(observations,
                                                                monkeypatch):
    import dwc.llm.client as client
    from dwc.organs import memory
    llm = RecordingLLM('["sum", "求和"]')
    monkeypatch.setattr(client, "LLMClient", lambda **kwargs: llm)
    monkeypatch.setattr(memory, "_EXPAND_CACHE", {})
    with mc.task_measurement_context("T-expansion", protocol_id="P-memory"):
        assert memory._llm_expand("计算总和") == ["sum", "求和"]
    event = only_call(observations)
    assert event["call_role"] == "expansion"
    assert event["task_id"] == "T-expansion"
    assert event["protocol_id"] == "P-memory"

    observations.clear()
    monkeypatch.setattr(memory, "_EXPAND_CACHE", {})
    monkeypatch.setattr(client, "LLMClient",
                        lambda **kwargs: RecordingLLM(boom=True))
    assert memory._llm_expand("failure query") == []
    assert only_call(observations)["call_role"] == "expansion"


def test_candidate_editor_role_and_available_task(observations):
    from dwc.organs.candidates import CandidateGenerator
    payload = {"patches": [], "m": "m", "component": "control_flow",
               "dimension": "D7", "target_layer": "assets"}
    generator = CandidateGenerator(llm=RecordingLLM(json.dumps(payload)))
    with mc.task_measurement_context("T-candidate", candidate_id="C-input"):
        generator._llm_generate(
            {"c": "E_VALUE", "q": "wrong_magnitude"},
            [{"ok": False, "fn": "f", "args": 1, "expected": 2, "actual": 3}],
            "def f(x):\n    return x", "f")
    event = only_call(observations)
    assert event["call_role"] == "editor"
    assert event["task_id"] == "T-candidate"
    assert event["candidate_id"] == "C-input"

    observations.clear()
    failing = CandidateGenerator(llm=RecordingLLM(boom=True))
    result = failing._llm_generate({"c": "c", "q": "q"}, [], "", "f")
    assert result["ok"] is False
    assert only_call(observations)["call_role"] == "editor"


def test_executor_solver_has_task_fields_and_error_role(observations):
    from dwc.llm.executor import LLMExecutorFactory
    anchors = {"T-executor": {"verifier_kind": "behavior", "checks": [
        {"fn": "f", "args": "1", "expected": "2"}]}}
    llm = RecordingLLM('{"f": [[1, 2]]}')
    exe = LLMExecutorFactory(llm, anchors=anchors).make()
    receipt = exe({"task_id": "T-executor", "candidate_id": "C-executor",
                   "rollout_id": "R-executor", "protocol_id": "P-executor"})
    assert receipt.detail["observed"] == {"f": [[1, 2]]}
    event = only_call(observations)
    assert event["call_role"] == "solver"
    assert {k: event[k] for k in
            ("task_id", "candidate_id", "rollout_id", "protocol_id")} == {
                "task_id": "T-executor", "candidate_id": "C-executor",
                "rollout_id": "R-executor", "protocol_id": "P-executor"}

    observations.clear()
    failing = LLMExecutorFactory(RecordingLLM(boom=True), anchors=anchors).make()
    assert failing({"task_id": "T-executor"}).detail[
        "error_code"] == "llm_transport_error"
    assert only_call(observations)["call_role"] == "solver"


def test_experiment_solver_has_arm_round_and_dataset(observations):
    from dwc.experiments.mem_guidance_vs_replay import run_experiment
    llm = RecordingLLM("def sum_first_n(n):\n    return sum(range(n + 1))")
    result = run_experiment(llm, repeat=1, rounds=1,
                            tasks={"code_fix_001": "def sum_first_n(n):\n    return 0"})
    assert result["arms"]["none"]["n_calls"] == 1
    calls = [e for e in observations if e.get("kind") == "aux_test_call"]
    assert len(calls) == 4
    event = calls[0]
    assert event["call_role"] == "solver"
    assert event["task_id"] == "code_fix_001"
    assert event["candidate_id"] == "none"
    assert event["rollout_id"] == "0:1"
    assert event["protocol_id"] == "dev"

    observations.clear()
    with pytest.raises(RuntimeError, match="synthetic"):
        run_experiment(RecordingLLM(boom=True), repeat=1, rounds=1,
                       tasks={"code_fix_001": "def sum_first_n(n):\n    return 0"})
    assert only_call(observations)["call_role"] == "solver"


def test_evo_peer_evaluation_role_and_error_path(observations):
    evo = importlib.import_module("dwc_evo_round")
    judge = SimpleNamespace(
        sealed={"T-peer": {"checks": [{"fn": "f", "args": "1"}]}},
        held_out_peer=lambda task: "T-peer")
    assert evo._peer_held_out_code(judge, RecordingLLM(boom=True), "T-evo") is None
    event = only_call(observations)
    assert event["call_role"] == "evaluation"
    assert event["task_id"] == "T-evo"


def test_evo_trial_probe_role_and_error_path(observations):
    evo = importlib.import_module("dwc_evo_round")
    judge = SimpleNamespace(anchors={"T-probe": {"checks": [
        {"fn": "f", "args": "1"}]}})
    with pytest.raises(RuntimeError, match="synthetic"):
        evo._real_trial(judge, RecordingLLM(boom=True), "T-probe", "patch")
    event = only_call(observations)
    assert event["call_role"] == "probe"
    assert event["task_id"] == "T-probe"


def test_evo_editor_has_real_cluster_and_attempt_identity(observations):
    evo = importlib.import_module("dwc_evo_round")

    class Mu:
        last_reason = "stop after measured draft"

        def __init__(self):
            self.llm = RecordingLLM("not json")

        def propose_from_cluster(self, sigs, context, **kwargs):
            self.llm.complete(context)
            return None

    report = evo.run_round(
        ":memory:", SimpleNamespace(), Mu(), "draft context",
        trial_fn=lambda *args: None, apply=False, rules_path="unused",
        clusters=[{"key": "C-evo", "sigs": [
            {"task": "T-evo", "c": "c", "q": "q", "fn": "f"}]}])
    assert report["results"][0]["drafted"] is False
    event = only_call(observations)
    assert event["call_role"] == "editor"
    assert event["task_id"] == "T-evo"
    assert event["candidate_id"] == "C-evo"
    assert event["rollout_id"] == "1"


def test_evo_trial_inherits_candidate_and_evaluation_role(observations):
    evo = importlib.import_module("dwc_evo_round")

    class Mu:
        last_reason = ""

        def propose_from_cluster(self, sigs, context, **kwargs):
            return SimpleNamespace(proposal_id="P-evo", patch="patch", code=None)

    def trial(task, patch, code):
        RecordingLLM("{}").complete("trial")
        return {"success": True}

    report = evo.run_round(
        ":memory:", SimpleNamespace(), Mu(), "draft context", trial_fn=trial,
        apply=False, rules_path="unused",
        clusters=[{"key": "C-evo", "sigs": [
            {"task": "T-evo", "c": "c", "q": "q", "fn": "f"}]}])
    assert report["results"][0]["trial"]["success"] is True
    event = only_call(observations)
    assert event["call_role"] == "evaluation"
    assert event["task_id"] == "T-evo"
    assert event["candidate_id"] == "P-evo"
    assert event["rollout_id"] == "1"
