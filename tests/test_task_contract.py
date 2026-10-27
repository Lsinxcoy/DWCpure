# -*- coding: utf-8 -*-
"""P0 · TaskContract 完成判定 + 轮数预算提示。"""
from __future__ import annotations

import os
import sys
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.llm.task_contract import TaskContract                 # noqa: E402
from dwc.llm import task_exec as TE                             # noqa: E402


def _contract(task, *, qa=False, root=""):
    return TaskContract.from_task(task, qa_mode=qa, max_rounds=10, root=root)


def test_qa_contract_only_needs_answer():
    c = _contract("介绍一下 pytest 是什么", qa=True)
    assert c.checks == ("answer_nonempty",)
    v = c.evaluate({"answer": "pytest 是 Python 测试框架。"})
    assert v["ok"] and v["checks"]["answer_nonempty"]


def test_write_task_without_artifact_is_incomplete():
    c = _contract("生成一份报告并保存到 var/inbox_work/report.md")
    v = c.evaluate({"answer": "已完成", "actions_log": []})
    assert not v["ok"] and "artifact_exists" in v["missing"]


def test_write_task_with_real_artifact_passes(tmp_path):
    p = tmp_path / "report.md"
    p.write_text("# 报告\n", encoding="utf-8")
    c = _contract("生成一份报告并保存", root=str(tmp_path))
    v = c.evaluate({"answer": "", "artifacts": ["report.md"]})
    assert v["ok"], v
    assert v["evidence"]["n_artifacts_nonempty"] == 1


def test_expected_artifact_ignores_unrelated_file(tmp_path):
    (tmp_path / "def_count.py").write_text("print(1)\n", encoding="utf-8")
    c = _contract("统计后把数字写进 var/inbox_work/def_count.txt",
                  root=str(tmp_path))
    v = c.evaluate({
        "answer": "1486",
        "artifacts": ["def_count.py"],
        "actions_log": [{"op": "write", "ok": True,
                         "target": "def_count.py"}],
    })
    assert not v["ok"] and "artifact_exists" in v["missing"]
    assert v["evidence"]["expected_artifacts"] == ["var/inbox_work/def_count.txt"]


def test_script_only_task_does_not_require_rerun(tmp_path):
    p = tmp_path / "var" / "inbox_work" / "mult3.py"
    p.parent.mkdir(parents=True)
    p.write_text("print(33)\n", encoding="utf-8")
    c = _contract("写一个脚本 var/inbox_work/mult3.py, 运行后打印 1 到 100 中 3 的倍数个数",
                  root=str(tmp_path))
    assert c.checks == ("artifact_exists",)
    v = c.evaluate({"answer": "", "artifacts": ["var/inbox_work/mult3.py"]})
    assert v["ok"], v


def test_pytest_word_is_not_run_intent():
    c = _contract("读 README.md, 找到 pytest 那一行的 passed 数字, "
                  "写进 var/inbox_work/readme_test.txt")
    assert not c.run_intent
    assert c.checks == ("artifact_exists",)


def test_write_log_target_must_exist(tmp_path):
    c = _contract("写一个文件并保存", root=str(tmp_path))
    v = c.evaluate({
        "answer": "好了",
        "actions_log": [{"op": "write", "ok": True,
                         "target": "missing.md"}],
    })
    assert not v["ok"] and "artifact_exists" in v["missing"]


def test_run_task_needs_successful_verification(tmp_path):
    p = tmp_path / "out.txt"
    p.write_text("ok", encoding="utf-8")
    c = _contract("运行脚本并把结果写进 out.txt", root=str(tmp_path))
    assert "verification_ok" in c.checks
    v = c.evaluate({
        "answer": "done",
        "artifacts": ["out.txt"],
        "actions_log": [{"op": "write", "ok": True, "target": "out.txt"}],
    })
    assert not v["ok"] and "verification_ok" in v["missing"]
    v2 = c.evaluate({
        "answer": "done",
        "artifacts": ["out.txt"],
        "actions_log": [
            {"op": "write", "ok": True, "target": "out.txt"},
            {"op": "run", "ok": True, "target": "python out.py"},
        ],
    })
    assert v2["ok"], v2


def test_turn_budget_note_only_after_half():
    assert TE._turn_budget_note(1, 10) == ""
    assert TE._turn_budget_note(5, 10) == ""
    note = TE._turn_budget_note(7, 10)
    assert "6/10" in note and "turn-budget" in note
    assert TE._turn_budget_note(1, 1) == ""


class _FinalLLM:
    configured = True

    def __init__(self, answer="好了"):
        self.answer = answer

    def complete(self, prompt, system=None, **kw):
        return SimpleNamespace(
            ok=True, error=None,
            text='{"analysis": "done", "op": "final", "answer": "%s"}'
                 % self.answer)


def test_integration_plain_qa_stays_done():
    rep = TE.execute_user_task("介绍一下 pytest 是什么", llm=_FinalLLM("pytest 是测试框架"),
                               max_rounds=2)
    assert rep["status"] == "done"
    assert rep["terminal_reason"] == "completed"
    assert rep["contract"]["checks"] == {"answer_nonempty": True}


def test_integration_fake_write_is_downgraded():
    rep = TE.execute_user_task("生成一份报告并保存到 var/inbox_work/x.md",
                               llm=_FinalLLM("已完成"), max_rounds=2)
    assert rep["status"] == "incomplete"
    assert rep["terminal_reason"] == "contract_failed"
    assert "artifact_exists" in rep["contract"]["missing"]
