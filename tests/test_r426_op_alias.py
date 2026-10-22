# -*- coding: utf-8 -*-
"""R426 · 模型把原生工具名当 op 用 ⇒ 必须归一，不能判"不在契约集"。

★★★ 现场（cl08 复跑，2026-10-22 11:29，session nb_1022_112903_02）：
    judge | op='search_code' 不在契约集     ← 第 1 轮，搜索被丢
    judge | read 目标不存在（幻觉路径）     ← 模型开始瞎读
    judge | op='search_code' 不在契约集     ← 第 2 轮，又被丢
    judge | op='search_code' 不在契约集     ← 第 3 轮，又被丢
    ⇒ 模型**一次都没搜成**，只能凭印象答 ⇒ 顽固幻觉，两次打回后判 incomplete。

    根因：`_TOOL_TO_OP` 只接在**原生 tool_calls** 路径上
    （`_tool_calls_to_step`），模型改用 JSON 步写
    `{"op": "search_code", "pattern": ...}` 时没有归一入口，
    契约集 `VALID_OPS` 只认 read/write/run/...，于是整步被丢。

★ 规则：**同一件事有两种写法，就必须有同一个归一化入口。**
"""
from __future__ import annotations

import io
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import task_exec as T  # noqa: E402


class _Script:
    configured = True

    def __init__(self, steps):
        self.steps = steps
        self.n = 0

    def complete(self, prompt, **kw):
        from types import SimpleNamespace
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


SESS_DIR = None  # 运行时取 T.SESSIONS（conftest 会把 DWC_VAR_DIR 指到 tmp）


def _sess_dir():
    # ★ 必须读模块属性：conftest 在导入前把 DWC_VAR_DIR 指到测试临时目录
    return getattr(T, "SESSIONS", os.path.join(ROOT, "var", "dwc_sessions"))


def _sess_rows(sid):
    """读本任务的 session 留痕（judge / opmap 都写在这里，不进 actions_log）。"""
    p = os.path.join(_sess_dir(), sid + ".jsonl")
    if not os.path.exists(p):
        return []
    with io.open(p, encoding="utf-8", errors="replace") as fh:
        return [json.loads(l) for l in fh if l.strip()]


def _judge_whys(sid):
    return [str(r.get("why") or "") for r in _sess_rows(sid)
            if r.get("phase") == "judge"]


def _cleanup(sid):
    try:
        os.remove(os.path.join(_sess_dir(), sid + ".jsonl"))
    except OSError:
        pass


def test_search_code_as_op_is_executed_not_dropped():
    """★★★ 核心：`op='search_code'` 要被归一成 run 并**真的执行**。"""
    sid = "T_R426_a"
    try:
        rep = T.execute_user_task(
            "DWC 的 CLI 入口文件是哪个？只答路径。",
            llm=_Script([
                {"analysis": "搜入口", "op": "search_code",
                 "pattern": "def main", "path": "src/dwc"},
                {"analysis": "答", "op": "final",
                 "answer": "src/dwc/cli_main.py"},
            ]), task_id=sid, max_rounds=6)
        whys = _judge_whys(sid)
        assert not any("不在契约集" in w for w in whys), whys
        assert any(r.get("phase") == "opmap" for r in _sess_rows(sid)), \
            "应有 opmap 归一留痕"
        assert any(e.get("phase") == "obs" and e.get("ok")
                   for e in rep["actions_log"]), "归一后必须真的跑出 obs"
    finally:
        _cleanup(sid)


def test_find_files_as_op_is_normalized():
    """★★ `find_files` / `list_dir` 同样要归一（不是只有 search_code）。"""
    sid = "T_R426_b"
    try:
        T.execute_user_task(
            "DWC 的 CLI 入口文件是哪个？只答路径。",
            llm=_Script([
                {"analysis": "找", "op": "find_files",
                 "pattern": "cli_main.py", "path": "src"},
                {"analysis": "答", "op": "final",
                 "answer": "src/dwc/cli_main.py"},
            ]), task_id=sid, max_rounds=6)
        whys = _judge_whys(sid)
        assert not any("不在契约集" in w for w in whys), whys
        assert any(r.get("phase") == "opmap" for r in _sess_rows(sid))
    finally:
        _cleanup(sid)


def test_unknown_op_still_rejected():
    """★★★ 反面：真的不存在的 op 仍要判 noisy（不许把闸口开成万能放行）。"""
    sid = "T_R426_c"
    try:
        T.execute_user_task(
            "随便问一句",
            llm=_Script([
                {"analysis": "乱写", "op": "definitely_not_a_tool", "x": 1},
                {"analysis": "答", "op": "final", "answer": "不知道"},
            ]), task_id=sid, max_rounds=6)
        whys = _judge_whys(sid)
        assert any("不在契约集" in w for w in whys), whys
    finally:
        _cleanup(sid)
