# -*- coding: utf-8 -*-
"""R385 · 原生工具模式必须防死循环（rf01 实测 140 轮 / 625 秒）。

★★★ 现场取证（2026-10-20 16:0x，R384 原生 tool calling 首测）:
  rf01  "PowerShell 需要 TrimStart 的字符码" ⇒ **140 轮 / 278 动作 /
        **625 秒**，最后 answer 为空、判 ✗。
  rf02  同一批、同一配置 ⇒ 2 轮 / 3 动作 / 6.5 秒，答对。

  ⇒ 不是"慢"，是**死循环**：模型找不到答案就无限 read/run 自证，
    而 `max_rounds=999` 给了它 999 次机会。一个任务烧 10 分钟，
    52 单就是 9 小时，且答案还是空的。

★ 判据（本轮锁的）:
  · 原生工具模式下 `max_rounds` 必须有**硬上限**（不许 999）
  · 同一 (op,target) 重复 ≥4 次 ⇒ 下一轮强制 `final_answer`
  · 到上限仍无答案 ⇒ `incomplete`（不许假装 done）
  · 正常 2–3 轮就能完成的任务**不受影响**（回归保护）
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import task_exec as T  # noqa: E402


class _Res:
    def __init__(self, text="", tool_calls=None):
        self.ok = True
        self.text = text
        self.error = ""
        self.meta = {"finish_reason": "tool_calls" if tool_calls else "stop"}
        if tool_calls:
            self.meta["tool_calls"] = tool_calls


def _tc(name, args):
    return [{"id": "c", "type": "function",
             "function": {"name": name,
                          "arguments": json.dumps(args, ensure_ascii=False)}}]


class _LoopLLM:
    """永远返回同一个 read 动作（模拟 rf01 的死循环）。"""

    configured = True

    def __init__(self):
        self.n = 0

    def complete(self, *a, **k):
        self.n += 1
        return _Res("", _tc("read_file", {"path": "README.md"}))


@pytest.fixture()
def work(tmp_path, monkeypatch):
    monkeypatch.setattr(T, "ROOT", str(tmp_path))
    monkeypatch.setattr(T, "WORK", str(tmp_path))
    monkeypatch.setattr(T, "SESSIONS", str(tmp_path / "sessions"))
    (tmp_path / "sessions").mkdir(exist_ok=True)
    monkeypatch.setattr(T, "SELF_MD", str(tmp_path / "self.md"))
    (tmp_path / "README.md").write_text("x", encoding="utf-8")
    monkeypatch.setenv("DWC_LLM_NATIVE_TOOLS", "1")
    return tmp_path


# ─────────────────────── ① 硬上限


def test_native_max_rounds_is_bounded():
    """★★★ 原生工具模式必须有硬上限（不许 999）。"""
    assert hasattr(T, "NATIVE_TOOLS_MAX_ROUNDS"), "缺 NATIVE_TOOLS_MAX_ROUNDS"
    v = T.NATIVE_TOOLS_MAX_ROUNDS
    assert isinstance(v, int) and 3 <= v <= 40, (
        "NATIVE_TOOLS_MAX_ROUNDS=%r 不合理（应 3–40）" % (v,))


def test_runaway_loop_terminates_quickly(work):
    """★★★ 死循环必须在上限内终止（rf01 实测 140 轮 / 625 秒）。"""
    llm = _LoopLLM()
    rep = T.execute_user_task("找某个字符码", llm=llm, task_id="t_loop")
    assert rep["rounds"] <= T.NATIVE_TOOLS_MAX_ROUNDS + 2, (
        "跑了 %s 轮，超过上限 —— 死循环没被拦住" % rep["rounds"])
    assert llm.n <= T.NATIVE_TOOLS_MAX_ROUNDS + 3, (
        "调了 %d 次 LLM（应 ≤ 上限）" % llm.n)
    # 没答案就必须诚实报 incomplete
    assert rep["status"] == "incomplete", (
        "死循环却报 done（answer=%r）" % rep.get("answer"))


def test_runaway_why_is_informative(work):
    """★★ 超限的 why 必须说明是"重复动作/轮数上限"，便于审计。"""
    rep = T.execute_user_task("找某个字符码", llm=_LoopLLM(),
                              task_id="t_loop2")
    why = str(rep.get("why") or "")
    assert why.strip(), "incomplete 但 why 空着"
    assert ("重复" in why) or ("上限" in why) or ("轮" in why), why


# ─────────────────────── ② 不许误伤正常任务


def test_normal_task_still_fast(work):
    """★★★ 回归保护：2 轮就能完成的任务不许被上限/熔断误伤。"""
    class _LLM:
        configured = True

        def __init__(self):
            self.n = 0

        def complete(self, *a, **k):
            self.n += 1
            if self.n == 1:
                return _Res("", _tc("read_file", {"path": "README.md"}))
            return _Res("", _tc("final_answer", {"answer": "答案是 42 字符"}))

    rep = T.execute_user_task("读 README 后回答", llm=_LLM(),
                              task_id="t_normal")
    assert rep["status"] == "done", rep
    assert rep["rounds"] <= 4, "正常任务被拖到 %s 轮" % rep["rounds"]
    assert "42" in str(rep.get("answer") or "")


def test_repeat_detector_forces_final(work):
    """★★★ 轮数逼近上限 ⇒ 强制 final（模型配合时能收尾成功）。

    注意：**完全相同**的动作+观察由既有「复读熔断」(R247, 3 次) 先拦下
    （那是正确行为，不归本条管）。本条测的是"每轮动作都不同、但一直在
    兜圈子"——复读熔断抓不到，只能靠轮数上限强制收尾。
    """
    class _LLM:
        configured = True

        def __init__(self):
            self.n = 0
            self.forced = False

        def complete(self, prompt, *a, **k):
            self.n += 1
            # 收到"强制 final"指令就配合收尾
            if "立即调用 final_answer" in str(prompt):
                self.forced = True
                return _Res("", _tc("final_answer",
                                    {"answer": "基于已读内容，答案是 X"}))
            # 每轮读不同文件（复读熔断抓不到）
            return _Res("", _tc("read_file",
                                {"path": "f%d.txt" % self.n}))

    llm = _LLM()
    for _i in range(1, 20):
        (work / ("f%d.txt" % _i)).write_text("答案 X\n", encoding="utf-8")
    rep = T.execute_user_task("不停兜圈子", llm=llm, task_id="t_repeat")
    assert llm.forced, "轮数上限没有触发强制 final 指令"
    assert rep["status"] == "done", (
        "模型配合收尾了却判 incomplete（rounds=%s why=%r）"
        % (rep["rounds"], rep.get("why")))
    assert rep["rounds"] <= T.NATIVE_TOOLS_MAX_ROUNDS, (
        "跑到 %s 轮才收（上限 %s）" % (rep["rounds"],
                                      T.NATIVE_TOOLS_MAX_ROUNDS))
