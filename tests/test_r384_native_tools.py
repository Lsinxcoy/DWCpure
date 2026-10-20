# -*- coding: utf-8 -*-
"""R384 · 原生 tool calling（修「94% 零动作」的根因）。

★★★ 现场取证（2026-10-20 全池 52 单）:
  · **51/54 = 94% 的报告 `actions_log` 为空** —— agent 全程没调过工具
  · 模型在 answer 里写「已写入 `var/inbox_work/list.md`」而文件根本没写
  · write 类通过率 1/8 = 12%（因为它需要真写文件）

★★ 双重根因:
  ① `task_exec` 用**手工拼 JSON 提示词**（`llm.complete(prompt,
     json_mode=True)`），逼模型在散文里输出 `{"op":"read",...}`。
     模型不照做 ⇒ 输出纯文本/XML（`<read path="..."/>`）。
  ② **更致命**：即使模型想调工具，client 也把它扔了 —— 端点返回
     `tool_calls` 时 `msg["content"]` 是**空串**，而 `complete()` 里
     `if not isinstance(text, str) or not text.strip()` 直接判
     `kind="empty"` ⇒ **tool_calls 被当成"空响应"丢弃**。

  实测端点原生 tool calling 完全正常:
      finish=tool_calls  tool_calls=1
        → read_file {"path": "src/dwc/llm/task_exec.py"}

★ 判据（本轮锁的）:
  · `client.complete(tools=...)` 必须把 `tools` 放进请求体
  · 响应含 `tool_calls` ⇒ `ok=True` 且 `meta["tool_calls"]` 透出
    （**不许**判成 kind="empty"）
  · 空 content + 无 tool_calls ⇒ 仍判 `kind="empty"`（回归保护）
  · `task_exec` 必须把 tool_calls 转成内部 step 并**真正执行**
    （actions_log 必须 > 0）
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import client as C  # noqa: E402
from dwc.llm import task_exec as T  # noqa: E402


class _Resp:
    def __init__(self, body: dict):
        self._raw = json.dumps(body).encode("utf-8")
        self.headers = {"Content-Type": "application/json"}

    def read(self):
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _tc(name, args):
    """构造一个原生 tool_call 列表（测试用）。"""
    return [{"id": "c", "type": "function",
             "function": {"name": name,
                          "arguments": json.dumps(args, ensure_ascii=False)}}]


def _body_with_tool_calls(name="read_file", args=None, content=""):
    return {"choices": [{
        "message": {
            "role": "assistant",
            "content": content,
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {"name": name,
                             "arguments": json.dumps(args or {}, ensure_ascii=False)},
            }],
        },
        "finish_reason": "tool_calls",
    }]}


@pytest.fixture(autouse=True)
def _iso(monkeypatch):
    monkeypatch.setenv("DWC_LLM_RETRIES", "0")
    monkeypatch.setattr(C, "_load_file_config", lambda: {})


def _client():
    return C.LLMClient(base_url="http://fake/v1", api_key="k", model="m",
                       timeout=5)


# ─────────────────────── ① 请求体必须带 tools


def test_tools_are_sent_in_body(monkeypatch):
    """★★★ `tools=` 必须进请求体（否则端点永远不会返回 tool_calls）。"""
    seen = {}

    def _uo(req, timeout=None):
        seen["body"] = json.loads(req.data.decode("utf-8"))
        return _Resp(_body_with_tool_calls())

    monkeypatch.setattr(C.urllib.request, "urlopen", _uo)
    tools = [{"type": "function",
              "function": {"name": "read_file", "description": "读文件",
                           "parameters": {"type": "object",
                                          "properties": {"path": {"type": "string"}}}}}]
    _client().complete("x", tools=tools, tool_choice="auto")

    assert "tools" in seen["body"], "tools 没进请求体"
    assert seen["body"]["tools"][0]["function"]["name"] == "read_file"
    assert seen["body"].get("tool_choice") == "auto"


def test_no_tools_key_when_not_passed(monkeypatch):
    """★ 不传 tools ⇒ 请求体里不许有 tools 键（老调用方行为不变）。"""
    seen = {}

    def _uo(req, timeout=None):
        seen["body"] = json.loads(req.data.decode("utf-8"))
        return _Resp({"choices": [{"message": {"content": "ok"},
                                   "finish_reason": "stop"}]})

    monkeypatch.setattr(C.urllib.request, "urlopen", _uo)
    _client().complete("x")
    assert "tools" not in seen["body"]


# ─────────────────────── ② tool_calls 必须透出（不许当空响应）


def test_tool_calls_are_exposed_not_empty(monkeypatch):
    """★★★ 空 content + 有 tool_calls ⇒ ok=True 且 meta 透出 tool_calls。

    这是「94% 零动作」的致命一环：旧代码把 tool_calls 判成 kind="empty"
    直接丢弃 ⇒ 模型想调工具也没用。
    """
    monkeypatch.setattr(
        C.urllib.request, "urlopen",
        lambda *a, **k: _Resp(_body_with_tool_calls(
            "read_file", {"path": "src/dwc/llm/task_exec.py"})))

    r = _client().complete("x", tools=[{"type": "function", "function": {
        "name": "read_file", "parameters": {}}}])

    assert r.ok is True, "tool_calls 被判成失败/空响应（真因）: %r" % r.error
    tcs = (r.meta or {}).get("tool_calls")
    assert tcs, "meta 里没有 tool_calls —— 被丢弃了"
    assert tcs[0]["function"]["name"] == "read_file"
    assert "task_exec.py" in tcs[0]["function"]["arguments"]
    assert (r.meta or {}).get("finish_reason") == "tool_calls"


def test_empty_without_tool_calls_still_empty(monkeypatch):
    """★★★ 回归保护：真空响应（无 tool_calls）仍判 kind="empty"。"""
    monkeypatch.setattr(
        C.urllib.request, "urlopen",
        lambda *a, **k: _Resp({"choices": [{"message": {"content": ""},
                                            "finish_reason": "stop"}]}))
    r = _client().complete("x")
    assert r.ok is False
    assert (r.meta or {}).get("kind") == "empty"


def test_reasoning_only_still_detected(monkeypatch):
    """★★ 回归保护：只有推理、无正文、无 tool_calls ⇒ reasoning_only。"""
    monkeypatch.setattr(
        C.urllib.request, "urlopen",
        lambda *a, **k: _Resp({"choices": [{
            "message": {"content": "", "reasoning_content": "想了很久"},
            "finish_reason": "length"}]}))
    r = _client().complete("x")
    assert r.ok is False
    assert (r.meta or {}).get("kind") == "reasoning_only"


# ─────────────────────── ④ run_command 必须转成 argv 列表


def test_run_command_string_becomes_argv():
    """★★★ `run` op 要求 argv 列表，字符串会直接报错。

    现场：an01 的 `ls -la src/dwc/organs` 连挂两次（ok: False），
    因为 `run` 严格要求 `cmd` 是非空 argv 列表。
    """
    step = T._tool_calls_to_step(_tc("run_command",
                                     {"cmd": "ls -la src/dwc/organs"}))
    assert isinstance(step["cmd"], list), "cmd 仍是字符串 —— run op 会报错"
    assert step["cmd"][:2] == ["ls", "-la"], step["cmd"]


def test_list_dir_becomes_argv():
    """★★ list_dir 也要转成 argv。"""
    step = T._tool_calls_to_step(_tc("list_dir", {"path": "src/dwc"}))
    assert isinstance(step["cmd"], list)
    assert step["cmd"][0] == "ls"


def test_search_code_tool_exists():
    """★★★ code-locate 类任务必须有搜索工具（只有 read 找不到符号）。"""
    names = [t["function"]["name"] for t in T.TASK_TOOLS]
    assert "search_code" in names, "缺 search_code —— 定位符号只能瞎猜"
    step = T._tool_calls_to_step(_tc("search_code",
                                     {"pattern": "class MemoryKernel"}))
    assert isinstance(step["cmd"], list)
    assert "grep" in step["cmd"][0], step["cmd"]


def test_argv_strips_quotes():
    """★★★ 引号必须被剥掉（posix=False 会保留 ⇒ grep 永远搜不到）。

    现场：模型传 `-E "max_round|max_rounds"`，旧实现给出
    `'"max_round|max_rounds"'`（带字面引号）⇒ grep 报 ok=False。
    """
    got = T._argv_of('-E "max_round|max_rounds"')
    assert got == ["-E", "max_round|max_rounds"], got
    assert not any(q in "".join(got) for q in ('"', "'")), got


def test_argv_truncates_pipes_and_redirects():
    """★★★ `run` 不经 shell ⇒ 管道/重定向必须截断（否则必然 ok=False）。

    现场：模型爱写 `grep ... | head -20`，`|` 被当字面参数传给 grep。
    """
    got = T._argv_of('grep -rn "熔断" --include=*.py src | head -20')
    assert got == ["grep", "-rn", "熔断", "--include=*.py", "src"], got
    assert "|" not in got and "head" not in got
    got2 = T._argv_of("ls -la src > out.txt")
    assert got2 == ["ls", "-la", "src"], got2


def test_run_command_with_quotes_and_pipe_executes():
    """★★★ 端到端：带引号+管道的 run_command 要能真跑通。"""
    step = T._tool_calls_to_step(
        _tc("run_command", {"cmd": 'grep -rn "import" src/dwc/llm/client.py | head -3'}))
    assert step["cmd"][0] == "grep"
    assert "|" not in step["cmd"]
    obs = T._do_action(step["op"], step)
    assert obs.get("ok") is True, obs
    assert "import" in str(obs.get("out") or "")


def test_write_file_maps_to_write_op():
    """★★ write_file → op=write（path/content 原名直通）。"""
    step = T._tool_calls_to_step(_tc("write_file",
                                     {"path": "var/inbox_work/a.txt",
                                      "content": "hi"}))
    assert step["op"] == "write"
    assert step["path"] == "var/inbox_work/a.txt"
    assert step["content"] == "hi"


def test_final_answer_maps_to_final():
    """★★ final_answer → op=final。"""
    step = T._tool_calls_to_step(_tc("final_answer", {"answer": "结论"}))
    assert step["op"] == "final"
    assert step["answer"] == "结论"


def test_unknown_tool_returns_none():
    """★★ 未知工具名 ⇒ None（不许瞎执行）。"""
    assert T._tool_calls_to_step(_tc("rm_rf", {"path": "/"})) is None


def test_task_exec_executes_tool_calls(tmp_path, monkeypatch):
    """★★★ task_exec 拿到 tool_calls ⇒ 必须真执行（actions_log > 0）。

    现场：write 类 1/8 = 12%，因为模型从没真写过文件。
    """
    from dwc.llm import task_exec as T

    monkeypatch.setattr(T, "WORK", str(tmp_path))
    monkeypatch.setattr(T, "SESSIONS", str(tmp_path / "sessions"))
    (tmp_path / "sessions").mkdir(exist_ok=True)
    monkeypatch.setattr(T, "SELF_MD", str(tmp_path / "self.md"))

    target = tmp_path / "hello.txt"

    class _LLM:
        configured = True

        def __init__(self):
            self.n = 0

        def complete(self, *a, **k):
            self.n += 1
            if self.n == 1:
                # 第一轮：原生 tool_call 写文件
                r = T_Res("")
                r.meta = {"tool_calls": [{
                    "id": "c1", "type": "function",
                    "function": {"name": "write_file",
                                 "arguments": json.dumps(
                                     {"path": str(target),
                                      "content": "EVAL_WRITE_OK"},
                                     ensure_ascii=False)}}],
                    "finish_reason": "tool_calls"}
                return r
            # 第二轮：final
            r = T_Res(json.dumps({"op": "final", "answer": "done"},
                                 ensure_ascii=False))
            r.meta = {"finish_reason": "stop"}
            return r

    rep = T.execute_user_task("写文件", llm=_LLM(), task_id="t_tools")
    assert len(rep.get("actions_log") or []) > 0, (
        "tool_calls 没被执行 —— actions_log 仍为空（94% 零动作的真因）")
    assert target.exists(), "文件没被真写出来"
    assert "EVAL_WRITE_OK" in target.read_text(encoding="utf-8")


class T_Res:
    def __init__(self, text):
        self.ok = True
        self.text = text
        self.error = ""
        self.meta = {"finish_reason": "stop"}
