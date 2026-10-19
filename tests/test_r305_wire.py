# -*- coding: utf-8 -*-
"""R305 · 新机制生产接线（monitor→主循环 / sec_review→动作前 /
project_hint→hint组装 / coordinator→多块任务）。"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_agent as A


def test_maybe_skip_calm():
    # 无委托+上轮全ok+连跳<2 ⇒ 跳过（省本轮 LLM）
    s = A._maybe_skip(prev_ok=True, item=None, skips=0)
    assert isinstance(s, str) and "monitor跳过" in s


def test_maybe_skip_has_item_runs():
    assert A._maybe_skip(prev_ok=True, item={"id": "u1"}, skips=0) is None


def test_maybe_skip_prev_fail_runs():
    assert A._maybe_skip(prev_ok=False, item=None, skips=0) is None


def test_maybe_skip_two_skips_runs():
    # 连跳2 ⇒ 强制跑（防饿死，与 monitor.MAX_SKIPS 同值）
    assert A._maybe_skip(prev_ok=True, item=None, skips=2) is None


def test_sec_warns_but_never_blocks(tmp_path, monkeypatch):
    # ★ R305-T2 · write 前 sec_review 只告警不驳回（照写 ok=True + sec_warnings）
    import dwc.llm.task_exec as TX
    work = tmp_path / "var" / "inbox_work"
    work.mkdir(parents=True)
    monkeypatch.setattr(TX, "ROOT", str(tmp_path))
    monkeypatch.setattr(TX, "WORK", str(work))
    r = TX._do_action("write", {"path": "var/inbox_work/x.txt",
                                "content": 'q = "SELECT * FROM t WHERE id=%s" % uid\n'})
    assert r["ok"] is True and os.path.exists(str(work / "x.txt"))
    assert len(r.get("sec_warnings") or []) >= 1


def test_sec_clean_no_warnings(tmp_path, monkeypatch):
    import dwc.llm.task_exec as TX
    work = tmp_path / "var" / "inbox_work"
    work.mkdir(parents=True)
    monkeypatch.setattr(TX, "ROOT", str(tmp_path))
    monkeypatch.setattr(TX, "WORK", str(work))
    r = TX._do_action("write", {"path": "var/inbox_work/y.txt",
                                "content": "print('hello')\n"})
    assert r["ok"] is True and (r.get("sec_warnings") or []) == []


def test_project_hint_appends(tmp_path, monkeypatch):
    # ★ R305-T3 · trace_log 传了⇒同组前情拼进 learned_hint；不传⇒老路零变
    import dwc_evo_round as _E
    log = tmp_path / "prod.jsonl"
    with open(str(log), "w", encoding="utf-8") as fh:
        fh.write('{"task": "code_fix_007", "pass_rate": 1.0}\n')
        fh.write('{"task": "code_fix_007", "pass_rate": 0.5}\n')
    got = {}
    monkeypatch.setattr(_E, "collect_unmapped",
                        lambda *a, **k: [{"key": "k",
                                          "sigs": [{"c": "C1", "q": "Q1",
                                                    "fn": "f", "m": "M1",
                                                    "task": "code_fix_009"}]}])

    class _Mu:
        def propose_from_cluster(self, sigs, context, want_code=None,
                                 learned_hint="", operator="improve"):
            got["hint"] = learned_hint
            return None
        last_reason = "t"
    rep = _E.run_round("x", None, _Mu(), context="",
                       trial_fn=lambda t, p, code=None: True,
                       apply=False, rules_path="y",
                       trace_log=str(log))
    assert "本组前情" in got["hint"]
    rep0 = _E.run_round("x", None, _Mu(), context="",
                        trial_fn=lambda t, p, code=None: True,
                        apply=False, rules_path="y")
    assert "本组前情" not in got["hint"]


def test_coordinator_kanban_on_parallel(tmp_path, monkeypatch):
    # ★ R305-T4 · delegate 并行后 kanban 记账（每 sub queued/done 两行）
    import json as _js
    import threading
    import dwc.llm.task_exec as TX
    import dwc.llm.coordinator as CO
    monkeypatch.setattr(TX, "ROOT", str(tmp_path))
    monkeypatch.setattr(TX, "SESSIONS", str(tmp_path))

    class _LLM:
        def __init__(self):
            self.lock = threading.Lock()
            self.n = 0

        def complete(self, prompt, system=None, **kw):
            with self.lock:
                self.n += 1
                n = self.n
            if n == 1:
                txt = _js.dumps({"op": "delegate",
                                 "tasks": ["子任务A", "子任务B"]})
            else:
                txt = _js.dumps({"op": "final", "answer": "答%d" % n,
                                 "artifacts": []})
            return type("R", (), {"ok": True, "text": txt,
                                  "error": None})()
    rep = TX.execute_user_task("并行主任务", llm=_LLM(), max_rounds=4,
                               task_id="T_par305")
    assert rep["status"] == "done", rep
    kb = tmp_path / "var" / "kanban.jsonl"
    lines = [ln for ln in kb.read_text(encoding="utf-8").splitlines()
             if ln.strip()]
    subs = sorted(_js.loads(ln).get("sub", "") for ln in lines)
    assert subs == ["子任务A", "子任务A", "子任务B", "子任务B"]
    sts = sorted(_js.loads(ln).get("status", "") for ln in lines)
    assert sts == ["done", "done", "queued", "queued"]
