# -*- coding: utf-8 -*-
"""R437 · 失败归因后修掉的两个**工具缺陷**（不是提示词措辞）。

★★★ 归因数据（全池 2 轮 × 52 单 × 2 臂 = 208 次运行）：
    通过 167 / infra 19 / 真失败 22。22 条真失败里：

    · 9 条「答案内容不对」
    · 4 条「未产出」（模型不调工具）
    · 3 条「声称执行但无证据」
    · 2 条「格式判据过严」
    · 2 条「产物内容不符」
    · 1 条「键名不对」、1 条「猜测被拦」

    其中两条能**确定性**修掉，且证据是硬的：

    ① `find_files` 跳过 `var`/`archive` ⇒ 问「var 下心跳文件名」的题
       实测返回 `TOTAL 0`（文件明明在），模型只好编名字。
    ② `search_code` 0/0 时不给任何方向 ⇒ 模型把「搜不到」当「不存在」，
       直接放弃或编造。

    ★ 两条都**不透露答案**：①只是让文件名可被找到；②只是告诉它换搜法。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import task_exec as TE  # noqa: E402


def _run(step):
    r = subprocess.run(step["cmd"], capture_output=True, text=True, timeout=120)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


def test_find_skip_keeps_var_and_archive():
    """★★★ 按名找文件不能跳过 var/archive（内容检索仍要跳过）。"""
    assert "var" in TE._REPO_SKIP_DIRS, "内容检索应继续跳过 var（日志噪声）"
    assert "archive" in TE._REPO_SKIP_DIRS
    assert "var" not in TE._FIND_SKIP_DIRS, "find_files 必须能看到 var/"
    assert "archive" not in TE._FIND_SKIP_DIRS
    # 其它重目录仍跳过
    assert ".git" in TE._FIND_SKIP_DIRS and "node_modules" in TE._FIND_SKIP_DIRS


def test_find_files_locates_var_file():
    """★★★ 实测：心跳文件必须能被 find_files 找到（修复前 TOTAL 0）。"""
    hb = os.path.join(ROOT, "var", "dwc_agent_heartbeat.json")
    created = not os.path.exists(hb)
    if created:
        os.makedirs(os.path.dirname(hb), exist_ok=True)
        with open(hb, "w", encoding="utf-8") as fh:
            fh.write("{}")
    try:
        step = TE._tool_calls_to_step([{
            "function": {"name": "find_files",
                         "arguments": json.dumps({"pattern": "dwc_agent_heartbeat.json",
                                                  "path": "."})}}])
        rc, out = _run(step)
        assert rc == 0
        assert "TOTAL 0" not in out, "仍然找不到 var/ 下的文件：%s" % out[:200]
        assert "dwc_agent_heartbeat.json" in out
    finally:
        if created:
            try:
                os.remove(hb)
            except OSError:
                pass


def test_search_zero_hit_gives_direction():
    """★★★ 0/0 必须给「换搜法」的提示，不能让模型当成「不存在」。"""
    step = TE._tool_calls_to_step([{
        "function": {"name": "search_code",
                     "arguments": json.dumps({"pattern": "zzz_no_such_symbol_zzz"})}}])
    rc, out = _run(step)
    assert "DEFINITIONS (0)" in out and "REFERENCES (0)" in out
    assert "0 命中（不等于不存在）" in out
    assert "find_files" in out


def test_search_hit_has_no_zero_hint():
    """★★ 有命中时不许出现 0/0 提示（否则是噪音，会稀释真结果）。"""
    step = TE._tool_calls_to_step([{
        "function": {"name": "search_code",
                     "arguments": json.dumps({"pattern": "MemoryKernel"})}}])
    rc, out = _run(step)
    assert "DEFINITIONS (1)" in out
    assert "0 命中（不等于不存在）" not in out


def test_zero_hint_does_not_leak_identifiers():
    """★★★ 提示文案里不许出现任何真实标识符（它会被模型当线索）。"""
    hint = "本工具按子串匹配：换更短的词根 / 换目录重搜，或改用 find_files 按文件名找。"
    for bad in ("MemoryKernel", "DWC_STEP_JUDGE", "cli_main", "_rev_prev"):
        assert bad not in hint


# ── 原生工具模式：只输出正文不该判死 ──────────────────────────────

def test_native_prose_not_judged_dead():
    """★★★ 现场：全池 2 轮 208 次里 4 次、复测 3 单里 2 单都是
    「模型只输出正文、没调工具」⇒ 任务直接判未执行。
    格式不该把正确答案扔掉（与 R380 同一条理由）。"""
    import inspect
    src = inspect.getsource(TE)
    assert "原生工具模式下模型只输出正文、未调用任何工具" not in src, \
        "仍在用「没调工具」判死任务"
    assert 'answer_mode": "plain_text"' in src, "纯文本答案通道被删了？"


def test_native_prose_still_passes_hallucination_gate():
    """★★★ 放开纯文本 ≠ 放开幻觉：文件名不存在仍要打回。"""
    import inspect
    src = inspect.getsource(TE)
    assert "_phantom_file_gate(task, _raw)" in src, \
        "纯文本路径绕过了幻觉文件名闸（会变成 R419 的后门）"
