# -*- coding: utf-8 -*-
"""processors · agent harness 的五个策略处理器（Phase B3 · 2026-10-19）

DWC-AUTO 定位声明（器官 · 判据 G1 定位门）
  ★ 服务环节③（提案）的**可进化策略面**: 每个 Processor 对应一个 hook，
    其构造参数就是 genotype 字段（定位方式 / 上下文长度 / 解析格式 /
    错误反馈粒度）。变异一个参数 = 一个候选策略。
  ★ 不抢位: 本模块只实现策略逻辑，不定义 hook 协议（那是 organs/hook.py），
    不编排回合（那是 harness/agent_harness.py）。

★★★ TRUTH_SOURCE（判据 G2）
  本模块不判"补丁对不对"——它只做文本选择/组装/解析/校验/格式化。
  真正的真值在注入的 run_tests 回调（SWE-bench 测试执行结果）。

★ G4 生灭门说明
  本模块不生成候选池（无 generate/evolve 语义）——处理器是**被选择的对象**，
  选择与淘汰由 evolver 负责。池上限不在本模块。

★ G7 静默门
  JSON 解析失败必须留痕：`note_parse_miss()` 计数，不静默 return None。
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional

from dwc.organs.hook import ProcessorSpec

# ── 解析失败留痕（G7：降级兜底必须可审计）──────────────────────
_PARSE_MISS: Dict[str, Any] = {"n": 0, "last": ""}


def note_parse_miss(why: str) -> None:
    _PARSE_MISS["n"] += 1
    _PARSE_MISS["last"] = str(why)[:200]


def parse_miss_count() -> int:
    return int(_PARSE_MISS["n"])


def parse_miss_last() -> str:
    return str(_PARSE_MISS["last"])


# ══════════════════════════════════════════════════════════════════
# 1. FileSelector · step_start
# ══════════════════════════════════════════════════════════════════

def _keywords(problem_statement: str, f2p_tests: List[str]) -> List[str]:
    kws: List[str] = []
    for t in f2p_tests or []:
        head = t.split("::")[0]
        stem = os.path.basename(head).replace(".py", "").replace("test_", "")
        if stem:
            kws.append(stem.lower())
    title = (problem_statement or "").split("\n")[0].lower()
    for w in re.split(r"[^a-z0-9_]+", title):
        if len(w) > 3:
            kws.append(w)
    seen: set = set()
    out: List[str] = []
    for k in kws:
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def select_by_keyword(problem_statement: str, files: List[str],
                      f2p_tests: List[str], limit: int = 3) -> List[str]:
    """三级匹配：basename 精确 → basename 包含 → 全路径包含。"""
    kws = _keywords(problem_statement, f2p_tests)

    def base(f: str) -> str:
        return os.path.basename(f).lower().replace(".py", "")

    for predicate in (
        lambda f: any(k == base(f) for k in kws),
        lambda f: any(k in base(f) or base(f) in k for k in kws),
        lambda f: any(k in f.lower().replace(os.sep, "/") for k in kws),
    ):
        hit = [f for f in files if predicate(f)]
        if hit:
            return hit[:limit]
    return []


def file_selector(mode: str = "keyword", limit: int = 3) -> ProcessorSpec:
    """step_start: 选出本轮要读的文件并载入内容。

    mode:
      keyword    —— 关键词三级匹配（零 LLM 成本）
      llm_select —— 让 LLM 从文件列表里挑（多一次调用）
    """
    def call(state: Dict[str, Any]) -> List[str]:
        deps = state["deps"]
        pol = state["policy"]
        files = list(deps.list_files())
        ps = state.get("problem_statement", "")
        f2p = state.get("f2p_tests", [])

        chosen: List[str] = []
        if mode == "llm_select" and files:
            prompt = ("Issue:\n" + ps[:1200] +
                      "\n\nAvailable source files:\n" + ", ".join(files[:60]) +
                      '\n\nWhich files are most relevant? Output JSON: {"files": ["p1"]}\nMax 3.\n')
            raw = deps.call_llm("You are a software engineer. Output valid JSON only.",
                                prompt, 400)
            obj = parse_json_tolerant(raw)
            if isinstance(obj, dict) and isinstance(obj.get("files"), list):
                chosen = [f for f in obj["files"] if f in files][:limit]
            if not chosen:
                note_parse_miss("llm_select 未产出有效 files 列表")

        if not chosen:
            chosen = select_by_keyword(ps, files, f2p, limit)

        state["target_files"] = chosen
        contents: Dict[str, str] = {}
        for f in chosen[:1]:
            c = deps.read_file(f, pol.context_chars)
            if c:
                contents[f] = c
        state["file_contents"] = contents
        return chosen

    return ProcessorSpec(name="file_selector", hook="step_start", order="NORMAL",
                         singleton_group="selector", call=call)


# ══════════════════════════════════════════════════════════════════
# 2. PromptBuilder · before_model
# ══════════════════════════════════════════════════════════════════

_INSTRUCTION = (
    "\n\nFind the bug and output ONLY a JSON object with three keys:\n"
    '"file": the file path to modify (relative to repo root),\n'
    '"old_string": the EXACT original code to replace '
    "(copy-paste from above, must match character-for-character),\n"
    '"new_string": the replacement code.\n\n'
    "CRITICAL: old_string must be a WHOLE-LINE block copied verbatim from above "
    "(never a partial line or a fragment of a line). Include every full line you "
    "want to replace, with its original indentation.\n"
    "Output valid JSON only. No explanation.\n"
)


def prompt_builder(include_f2p: bool = True,
                   include_files: bool = True) -> ProcessorSpec:
    """before_model: 把 issue + 源码 + 上一轮错误组装成 prompt。"""
    def call(state: Dict[str, Any]) -> str:
        parts = ["Issue:\n" + state.get("problem_statement", "")[:1500]]
        if include_f2p and state.get("f2p_tests"):
            parts.append("\nF2P tests (will verify the fix):\n"
                         + "\n".join(state["f2p_tests"][:3]))
        if include_files:
            for f, c in state.get("file_contents", {}).items():
                parts.append("\n--- %s ---\n%s" % (f, c))
        err = state.get("previous_error", "")
        if err:
            parts.append("\n\nPrevious attempt failed:\n" + err[:800]
                         + "\nPlease fix the issue and try again.")
        parts.append(_INSTRUCTION)
        state["prompt"] = "\n".join(parts)
        return state["prompt"]

    return ProcessorSpec(name="prompt_builder", hook="before_model", order="NORMAL",
                         singleton_group="prompt", call=call)


# ══════════════════════════════════════════════════════════════════
# 3. OutputParser · after_model
# ══════════════════════════════════════════════════════════════════

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def parse_json_tolerant(text: str) -> Optional[dict]:
    """容忍 ```json 围栏 / 前后废话的 JSON 提取。

    ★ 失败必须留痕（G7）——不静默 return None。
    """
    if not text:
        note_parse_miss("空响应")
        return None
    cands = [text.strip()]
    m = _FENCE.search(text)
    if m:
        cands.append(m.group(1).strip())
    # 最外层花括号切片（取第一个 { 到最后一个 }）
    lo, hi = text.find("{"), text.rfind("}")
    if lo != -1 and hi > lo:
        cands.append(text[lo:hi + 1])
    for c in cands:
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except (json.JSONDecodeError, TypeError):
            continue
    note_parse_miss("无可解析 JSON: %s" % text[:120])
    return None


def output_parser(mode: str = "json") -> ProcessorSpec:
    """after_model: 把 LLM 原文解析成 action。

    mode:
      json —— 三键对象 {file, old_string, new_string}（当前唯一实现）
      （codeact / diff / whole_file 在 Phase F 接入，本阶段显式拒绝）
    """
    def call(state: Dict[str, Any]) -> Optional[dict]:
        raw = state.get("raw_response", "")
        if mode != "json":
            state["action"] = None
            state["parse_failed"] = True
            note_parse_miss("未实现的 patch_format: %s" % mode)
            return None

        obj = parse_json_tolerant(raw)
        if obj and all(k in obj for k in ("file", "old_string", "new_string")):
            state["action"] = {"file": obj["file"],
                               "old_string": obj["old_string"],
                               "new_string": obj["new_string"]}
            state["parse_failed"] = False
            return state["action"]

        state["action"] = None
        state["parse_failed"] = True
        return None

    return ProcessorSpec(name="output_parser", hook="after_model", order="NORMAL",
                         singleton_group="parser", call=call)


# ══════════════════════════════════════════════════════════════════
# 4. ActionGuard · before_tool
# ══════════════════════════════════════════════════════════════════

def action_guard() -> ProcessorSpec:
    """before_tool: 应用前的最小结构校验（不判语义对错）。"""
    def call(state: Dict[str, Any]) -> bool:
        a = state.get("action") or {}
        bad = (not a.get("file")
               or not a.get("old_string")
               or a.get("old_string") == a.get("new_string"))
        state["guard_failed"] = bool(bad)
        if bad:
            state["previous_error"] = "action 结构不合法（缺 file/old_string 或 old==new）"
        return not bad

    return ProcessorSpec(name="action_guard", hook="before_tool", order="NORMAL",
                         singleton_group="guard", call=call)


# ══════════════════════════════════════════════════════════════════
# 5. ErrorFeeder · after_tool
# ══════════════════════════════════════════════════════════════════

def error_feeder(mode: str = "full") -> ProcessorSpec:
    """after_tool: 决定下一轮喂回多少错误信息。

    mode:
      full            —— 全量（默认）
      truncated       —— 截 300 字（省 token）
      assertion_only  —— 只留断言/异常行（聚焦）
    """
    def call(state: Dict[str, Any]) -> str:
        tr = state.get("tool_result") or {}
        if tr.get("ok"):
            state["previous_error"] = ""
            return ""
        msg = state.get("previous_error", "") or ""
        if mode == "truncated":
            msg = msg[:300]
        elif mode == "assertion_only":
            lines = [ln for ln in msg.splitlines()
                     if "assert" in ln.lower() or "error" in ln.lower()]
            msg = "\n".join(lines[-5:]) or msg[:300]
        state["previous_error"] = msg
        return msg

    return ProcessorSpec(name="error_feeder", hook="after_tool", order="NORMAL",
                         singleton_group="feeder", call=call)


# ══════════════════════════════════════════════════════════════════
# 6. 默认装配
# ══════════════════════════════════════════════════════════════════

def default_registry(policy=None):
    """按 Policy 装一套默认处理器（Policy 缺省时用 keyword/json/full）。"""
    from dwc.harness.agent_harness import Policy
    from dwc.organs.hook import HookRegistry

    pol = policy or Policy()
    reg = HookRegistry()
    reg.register(file_selector(mode=pol.localization))
    reg.register(prompt_builder())
    reg.register(output_parser(mode=pol.patch_format))
    reg.register(action_guard())
    reg.register(error_feeder(mode="full"))
    return reg


__all__ = [
    "note_parse_miss", "parse_miss_count", "parse_miss_last",
    "select_by_keyword", "parse_json_tolerant",
    "file_selector", "prompt_builder", "output_parser",
    "action_guard", "error_feeder", "default_registry",
]
