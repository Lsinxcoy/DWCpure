# -*- coding: utf-8 -*-
"""R418 · 每个闸独立额度 —— 闸之间不许互相吃掉打回次数。

★★★ 现场（R418 全池第 12 单，rf12「TUI 主题名叫什么」）：
    轮次轨迹（session 实录）：
      … force_final（复读熔断）
      refcheck: **有取证却拒答**        ← R408 打回第 1 次
      refcheck: **答案文件名在仓库中不存在（幻觉）** ← R417 打回第 1 次
      final: 「无法给出…没有检索到任何 TUI 主题证据」
    ⇒ 两个闸共用 `_r302_strikes`，各打回一次就到 2，
      模型第三次拒答时 **所有闸一起失效**，拒答被当成答案收下。

★ 修法：每个闸各自 2 次额度（`_gate_strikes` 字典），
  总轮次仍由 max_rounds 兜底。
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import task_exec as T  # noqa: E402

#: 拼接构造，避免这个假名被仓库检索命中（自证预言）
FAKE = "tui_theme_" + "x.py"


class _Script:
    configured = True

    def __init__(self, steps):
        self.steps = steps
        self.n = 0
        self.prompts = []

    def complete(self, prompt, **kw):
        from types import SimpleNamespace
        self.prompts.append(prompt)
        i = min(self.n, len(self.steps) - 1)
        self.n += 1
        return SimpleNamespace(ok=True, error="", meta={},
                               text=json.dumps(self.steps[i],
                                               ensure_ascii=False))

    def complete_stream(self, prompt, **kw):
        return self.complete(prompt, **kw)


@pytest.fixture(autouse=True)
def _json_path(monkeypatch):
    monkeypatch.setenv("DWC_LLM_NATIVE_TOOLS", "0")


def test_refusal_gate_survives_phantom_file_strike():
    """★★★ 核心：R417 打回一次之后，R408 仍必须能打回两次。

    旧实现（共用计数器）在这一步就哑了：第三次拒答被直接收下。
    """
    llm = _Script([
        {"analysis": "读证据", "op": "read", "path": "scripts/dwc_theme.py"},
        # ① 编一个不存在的文件名 ⇒ R417 打回
        {"analysis": "编", "op": "final",
         "answer": "主题定义在 %s 里。" % FAKE},
        # ② 有证据却拒答 ⇒ R408 第 1 次
        {"analysis": "拒答", "op": "final",
         "answer": "无法确定：未检索到任何与 TUI 主题相关的证据。"},
        # ③ 再拒答 ⇒ R408 第 2 次（旧实现此处已失效）
        {"analysis": "又拒答", "op": "final",
         "answer": "无法确定：未检索到任何与 TUI 主题相关的证据。"},
        # ④ 终于答对
        {"analysis": "答", "op": "final", "answer": "deep"},
    ])
    rep = T.execute_user_task("DWC 的 TUI 主题名（theme）叫什么？只答主题名。",
                              llm=llm, task_id="T_R418_a", max_rounds=14)
    n_refusal = sum(1 for p in llm.prompts if "却仍然拒答" in p)
    assert n_refusal == 2, (
        "拒答闸只打回了 %d 次 —— 被别的闸吃掉了额度" % n_refusal)
    assert "deep" in str(rep.get("answer")), rep.get("answer")


def test_each_gate_still_capped():
    """★★ 反面：单闸仍有上限（不许无限打回把轮次耗尽）。"""
    llm = _Script([
        {"analysis": "读", "op": "read", "path": "scripts/dwc_theme.py"},
        {"analysis": "拒答", "op": "final",
         "answer": "无法确定：未检索到任何与 TUI 主题相关的证据。"},
    ])
    T.execute_user_task("DWC 的 TUI 主题名（theme）叫什么？只答主题名。",
                        llm=llm, task_id="T_R418_b", max_rounds=10)
    n_refusal = sum(1 for p in llm.prompts if "却仍然拒答" in p)
    assert n_refusal == 2, "单闸打回次数应恰好为 2（防死循环），实际 %d" % n_refusal


# ══════════════ R423 · 顽固拒答 ⇒ 判失败 ══════════════

def test_stubborn_refusal_fails_instead_of_accepting(monkeypatch):
    """★★★ rf12 复刻：两次打回后仍拒答 ⇒ status=incomplete。

    现场：模型 3 次读 dwc_theme.py，revision 自己都写下
    「Theme names visible in header: deep (Deep Space)」，
    最后仍答「没有检索到任何证据」。
    """
    monkeypatch.setenv("DWC_LLM_NATIVE_TOOLS", "0")
    bad = {"analysis": "拒答", "op": "final",
           "answer": "无法确定：未检索到任何与 TUI 主题相关的证据。"}
    llm = _Script([
        {"analysis": "读", "op": "read", "path": "scripts/dwc_theme.py"},
        bad, bad, bad,
    ])
    rep = T.execute_user_task("DWC 的 TUI 主题名（theme）叫什么？只答主题名。",
                              llm=llm, task_id="T_R423_a", max_rounds=12)
    assert rep["status"] == "incomplete", rep["status"]
    assert "拒答" in str(rep.get("answer")), rep.get("answer")
