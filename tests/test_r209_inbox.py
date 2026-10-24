# -*- coding: utf-8 -*-
"""R209 · 任务收件箱 + LLMTaskExecutor（"不接我的单算什么独立 agent"轮）。"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
PY = sys.executable

from dwc.llm import task_exec as TE                            # noqa: E402


class _FakeLLM:
    """预设 JSON 响应序列的假 LLM（LLMClient.complete 契约: ok/text/error）。"""
    def __init__(self, steps, ok=True):
        self.steps = list(steps)
        self.ok = ok
        self.configured = True

    def complete(self, prompt, **kw):
        class R: pass
        r = R()
        r.ok = self.ok
        r.error = None if self.ok else "端点挂了"
        r.text = json.dumps(self.steps.pop(0), ensure_ascii=False) \
            if (self.ok and self.steps) else ""
        return r


# ═══ executor 白名单与护栏 ═══
def test_executor_read_write_final_chain():
    """★★★ 全链: read→write→final 三轮, 产物真落 var/inbox_work/。"""
    llm = _FakeLLM([
        {"analysis": "先读", "op": "read", "path": "config/iron_laws.yaml"},
        {"analysis": "写产物", "op": "write",
         "path": "var/inbox_work/r209_test.md", "content": "# 测试产物"},
        {"analysis": "完成", "op": "final", "answer": "已读已写",
         "artifacts": ["var/inbox_work/r209_test.md"]},
    ])
    rep = TE.execute_user_task("测试任务", llm=llm)
    assert rep["status"] == "done" and rep["rounds"] == 3
    # ★ R255: actions_log 含 obs 行（judge 历史来源）— 只取决策行
    assert [l["op"] for l in rep["actions_log"]
            if l.get("phase") != "obs"] == ["read", "write", "final"]
    p = os.path.join(ROOT, "var", "inbox_work", "r209_test.md")
    assert os.path.exists(p) and io.open(p, encoding="utf-8").read() == "# 测试产物"


def test_executor_write_guard_rejects_escape():
    """★★★ 写路径护栏: var/inbox_work/ 之外的写必须拒（工作区隔离）。"""
    llm = _FakeLLM([{"analysis": "越界", "op": "write",
                     "path": "src/dwc/evil.py", "content": "x"}])
    rep = TE.execute_user_task("越界任务", llm=llm)
    # 动作被拒（观察含 error 回喂）→ fake LLM 无后续 ⇒ incomplete 如实报
    assert rep["status"] == "incomplete", rep
    assert rep["actions_log"][-1]["op"] == "write"
    assert not os.path.exists(os.path.join(ROOT, "src", "dwc", "evil.py")), (
        "越界写竟然成功了")


def test_executor_run_forbidden_cmd_blocked():
    """★★ run 护栏: 危险命令黑名单（rm -rf）必须拦 —— _do_action raise
    TaskExecError（execute_user_task 统一转 {"ok":False} 观察回喂 LLM）。"""
    import pytest
    with pytest.raises(TE.TaskExecError, match="黑名单"):
        TE._do_action("run", {"cmd": ["rm", "-rf", "/"]})


def test_executor_llm_failure_is_honest_incomplete():
    """★ LLM 失败不静默: complete().ok=False ⇒ incomplete 带 why。"""
    llm = _FakeLLM([], ok=False)
    rep = TE.execute_user_task("t", llm=llm)
    assert rep["status"] == "incomplete" and "LLM 失败" in rep["why"]


# ═══ inbox 协议 ═══
def test_inbox_take_and_done_dedup():
    """★★★ 收件箱协议: 投单→take 取到→标记 done→再 take 跳过（同 id 不二做）。"""
    import dwc_agent as A
    tid = "T_r209_lock_test"
    st = A._done_state()
    if tid in st:
        del st[tid]
        with open(A.INBOX_DONE, "w", encoding="utf-8") as fh:
            json.dump(st, fh, ensure_ascii=False)
    with open(A.INBOX, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"id": tid, "task": "锁测试单", "by": "test"},
                            ensure_ascii=False) + "\n")
    item = A.take_inbox()
    assert item and item["id"] == tid, "take 没取到投单: %s" % item
    st[tid] = "done"                       # 模拟消费完成
    with open(A.INBOX_DONE, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False)
    item2 = A.take_inbox()
    assert item2 is None or item2["id"] != tid, "done 后没跳过: %s" % item2


def test_submit_cli_appends_inbox():
    """★ --submit 投单 CLI: 追加进 inbox 且可被 take 读到。"""
    r = subprocess.run([PY, os.path.join(ROOT, "scripts", "dwc_agent.py"),
                        "--submit", "CLI 投单测试", "--id", "T_cli_r209"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "投单成功" in r.stdout, r.stdout[-200:]
    import dwc_agent as A
    rows = [json.loads(x) for x in io.open(A.INBOX, encoding="utf-8")
            .read().splitlines() if x.strip()]
    assert any(x.get("id") == "T_cli_r209" for x in rows), "CLI 投单没进 inbox"


def test_run_user_task_marks_done_and_report():
    """★★★ 消费全链: run_user_task（真 LLMClient 构造 — configured 判可用）
    报告落 dwc_reports/<id>.json + done state 记账。"""
    import dwc_agent as A
    tid = "T_r209_nomark"
    fake = _FakeLLM([{"analysis": "直接完", "op": "final", "answer": "ok",
                      "artifacts": []}])
    item = {"id": tid, "task": "记账锁", "ctx": None}
    rep = A.run_user_task(item, use_llm=True, llm=fake)   # ★ 注入假 LLM
    assert rep["id"] == tid and rep["status"] == "done"
    p = os.path.join(A.REPORTS, tid + ".json")
    assert os.path.exists(p), "报告没落盘"
    assert A._done_state().get(tid) in ("done", "incomplete"), "done 态没记"
