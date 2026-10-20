# -*- coding: utf-8 -*-
"""R388 · `rc_and_contains` 必须要求 **agent 真跑过** 该命令。

★★★ 现场（2026-10-20 全池 52 单）：
  `run-verify` 类 **10/10 = 100%** —— 而这是假的。
  判据 `rc_and_contains` 的实现是**判据自己重跑命令**：

      subprocess.run(check["cmd"])          # ← 判据在跑，不是 agent
      ok = rc == 0 and target in out

  ⇒ agent 什么都不做，只要仓库里那套测试是绿的，就判 ✓。
  ⇒ 10 单全是白送，占全池 18.5%。

★ 判据的正确定义：
  "agent 是否**验证过**这个事实" —— 所以必须有 **agent 侧的动作证据**
  （actions_log 里有一条 `run` 且 ok=True，命令命中同一个目标）。
  判据自己重跑只能作为**独立复核**（防止 agent 谎报），
  **不能单独构成通过**。

★ 锁的语义：
  ① 有 agent 动作证据 + 复核通过  ⇒ ✓
  ② 零动作（agent 没跑过）        ⇒ ✗（"未执行，自行重跑不算功劳"）
  ③ 有动作但复核失败              ⇒ ✗
  ④ 没传 report（老调用方）        ⇒ ✗ 并说明缺证据（不许静默放行）
  ⑤ 显式 `allow_self_verify: true` ⇒ 保持旧语义（仅用于自测判据本身）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_bench2 as B2  # noqa: E402


def _check(cmd=None, target="passed", **extra):
    d = {"type": "rc_and_contains",
         "cmd": cmd or "python -m pytest tests/test_r252_effort.py -q",
         "target": target}
    d.update(extra)
    return d


def _report(actions=None, status="done", answer="验证通过"):
    return {"status": status, "answer": answer, "actions_log": actions or []}


def _run_act(cmd, ok=True):
    return {"round": 1, "phase": "obs", "op": "run", "target": cmd,
            "cmd": cmd, "ok": ok, "obs": "1 passed"}


# ───────────────────── ① 有 agent 证据 ⇒ 通过


def test_agent_ran_it_passes():
    """agent 真跑了那条 pytest ⇒ 判 ✓。"""
    rep = _report([_run_act("python -m pytest tests/test_r252_effort.py -q")])
    ok, how = B2.verify(_check(), "已运行并通过", report=rep)
    assert ok is True, how
    assert "agent" in how.lower() or "ran" in how.lower(), how


# ───────────────────── ② 零动作 ⇒ 必须失败（核心）


def test_zero_action_fails_even_if_rerun_is_green():
    """★★★ 核心：agent 零动作，判据自己重跑是绿的 ⇒ **仍必须判 ✗**。

    这就是 run-verify 10/10 = 100% 假通过的根因。
    """
    rep = _report([])                     # 零动作
    ok, how = B2.verify(_check(), "验证通过", report=rep)
    assert ok is False, (
        "agent 零动作却被判通过 —— 判据自行重跑给 agent 记了功: %s" % how)
    assert "未执行" in how or "no-agent" in how.lower(), how


def test_zero_action_but_agent_claims_success_still_fails():
    """agent 只在 answer 里说"已验证通过"、零动作 ⇒ 仍判 ✗（幻觉）。"""
    rep = _report([], answer="我已运行 pytest，全部通过，rc=0")
    ok, how = B2.verify(_check(), rep["answer"], report=rep)
    assert ok is False, how


# ───────────────────── ③ 有动作但复核失败 ⇒ ✗


def test_agent_ran_but_rerun_fails():
    """agent 跑了但判据复核失败 ⇒ ✗（不许只看 agent 自述）。"""
    rep = _report([_run_act("python -m pytest tests/test_r252_effort.py -q")])
    chk = _check(cmd="python -c \"raise SystemExit(3)\"", target="")
    ok, how = B2.verify(chk, "done", report=rep)
    assert ok is False, how


# ───────────────────── ④ 缺 report ⇒ 不许静默放行


def test_missing_report_fails_loudly():
    """★★ 老调用方没传 report ⇒ 判 ✗ 并说明（禁止静默放行）。"""
    ok, how = B2.verify(_check(), "验证通过")
    assert ok is False, how
    assert "report" in how.lower() or "证据" in how, how


# ───────────────────── ⑤ 显式豁免


def test_allow_self_verify_keeps_old_semantics():
    """★ 显式 `allow_self_verify: true` ⇒ 保持旧语义（自测判据本身用）。"""
    chk = _check(cmd='python -c "print(1)"', target="1", allow_self_verify=True)
    ok, how = B2.verify(chk, "x", report=_report([]))
    assert ok is True, how


# ───────────────────── ⑥ 其它判据类型不受影响


def test_other_check_types_unaffected_by_report():
    """★★ contains / regex 等不看 report，行为不变（回归保护）。"""
    assert B2.verify({"type": "contains", "target": "abc"}, "xxabcxx",
                     report=_report([]))[0] is True
    assert B2.verify({"type": "regex", "pattern": r"^3$"}, "3",
                     report=_report([]))[0] is True


# ───────────────────── ⑦ 证据匹配要认得出命令变体


def test_evidence_matches_command_variant():
    """★★ agent 跑的命令可能带额外参数（-p no:randomly / --tb=short），
    只要命中同一个测试文件就算证据。"""
    rep = _report([_run_act(
        "python -m pytest tests/test_r252_effort.py -q -p no:randomly --tb=short")])
    ok, how = B2.verify(_check(), "passed", report=rep)
    assert ok is True, how


def test_evidence_requires_ok_true():
    """★★ 动作存在但 ok=False（命令失败）⇒ 不算"验证过"。"""
    rep = _report([_run_act(
        "python -m pytest tests/test_r252_effort.py -q", ok=False)])
    ok, how = B2.verify(_check(), "passed", report=rep)
    assert ok is False, how


def test_evidence_matches_argv_list_vs_string_command():
    """★★★ R397 · 判据写的是**字符串**命令，agent 动作是 **argv 列表**。

    现场（2026-10-20 22:15 全池）rv06/rv07/rv08 全被判
    `no-agent-evidence`，但 agent 其实跑了：

        判据 cmd:   python -c "import os;n=sum(...)"
        agent cmd:  ['python', '-c', 'import os;n=sum(...)']
        JSON 形态:  ["python", "-c", "import os;n=sum(...)"]

    带引号+空格的 needle 永远匹配不到 ⇒ 3 单被误判。
    修：两边去掉非字母数字字符后再比。
    """
    chk = {"type": "rc_and_contains",
           "cmd": 'python -c "print(1)"', "target": "1"}
    rep = _report([{"round": 1, "phase": "obs", "op": "run",
                    "cmd": ["python", "-c", "print(1)"],
                    "target": "['python', '-c', 'print(1)']",
                    "ok": True, "obs": "1"}])
    ok, how = B2.verify(chk, "1", report=rep)
    assert ok is True, how


def test_evidence_normalized_match_still_rejects_other_command():
    """★★ 归一化不能变成"什么都能匹配"（跑的是别的命令 ⇒ 仍 ✗）。"""
    chk = {"type": "rc_and_contains",
           "cmd": 'python -c "print(ALPHA_ONLY)"', "target": "ALPHA_ONLY"}
    rep = _report([{"round": 1, "phase": "obs", "op": "run",
                    "cmd": ["python", "-c", "print(BETA_OTHER)"],
                    "ok": True, "obs": "BETA_OTHER"}])
    ok, how = B2.verify(chk, "ALPHA_ONLY", report=rep)
    assert ok is False, how
