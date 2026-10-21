# -*- coding: utf-8 -*-
"""R413 · 证据等价：答案出现在 agent **自己跑出来的输出**里，也算取证。

★★★ 现场（2026-10-21 R411 全池）：
  rv06：任务「统计 src/dwc 下 .py 数量」——
        agent 跑 `python -c "import os;print(sum(...))"` → 输出 `98`（正确）
        判据要的是另一条 `python -c "...print('PYFILES',n)"` → 也是 98
        ⇒ 命令串不匹配 ⇒ `no-agent-evidence` ✗
  rv08：任务「git log -1 输出哈希前 8 位」——
        agent 跑 `git log -1` → `182d5d6e…`（正确）
        判据要 `git log -1 --format=%h` ⇒ ✗

  两单都是**真取证 + 真答案**，被判据的"命令串精确匹配"误杀。

★ 修法（本测试锁定）：精确匹配失败后，若 **agent 某条成功的 run 输出里
  出现了答案锚点**，即视为取证成立。
★ 必须保住的反面：零动作 + 答案正确 ⇒ **仍然判失败**（防猜对）。
"""
from __future__ import annotations

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
sys.path.insert(0, os.path.join(ROOT, "src"))

import dwc_bench2 as B2  # noqa: E402

CHECK = {"type": "rc_and_contains",
         "cmd": "python -c \"print('PYFILES 98')\"",
         "target": "PYFILES"}


def _rep(*obs):
    """构造 actions_log：obs 是 (cmd, out) 对。"""
    log = []
    for cmd, out in obs:
        log.append({"phase": "act", "op": "run"})
        log.append({"phase": "obs", "op": "run", "ok": True,
                    "target": cmd,
                    "obs": '{"ok": true, "rc": 0, "out": "%s", "err": ""}' % out})
    return {"actions_log": log}


def test_equivalent_command_passes():
    """★★★ 新行为：等价命令 + 输出里有答案 ⇒ ✓（rv06 复刻）。"""
    rep = _rep(("['python','-c','import os;print(sum(1 for r,_,fs in "
                "os.walk(\"src/dwc\") for f in fs if f.endswith(\".py\")))']",
                "98"))
    ok, how = B2.verify(CHECK, "共 98 个 Python 文件", report=rep)
    assert ok is True, how
    assert "equivalent" in how, how


def test_hash_from_plain_git_log_passes():
    """★★ rv08 复刻：`git log -1` 的完整输出里含哈希 ⇒ ✓。"""
    sha = "182d5d6e5c50bfa8ee12759b5d937569e9a03f02"
    check = {"type": "rc_and_contains",
             "cmd": "python -c \"print('%s')\"" % sha,
             "target": ""}
    rep = _rep((("['git','log','-1']"),
                "commit " + sha + " (HEAD -> master)"))
    ok, how = B2.verify(check, "最新哈希前 8 位：182d5d6e", report=rep)
    assert ok is True, how


def test_zero_action_still_fails():
    """★★★ 反面：零动作 + 答案正确 ⇒ 仍然 ✗（防"猜对了"）。"""
    rep = {"actions_log": [{"phase": "act", "op": "final"}]}
    ok, how = B2.verify(CHECK, "共 98 个 Python 文件", report=rep)
    assert ok is False, how
    assert "no-agent-evidence" in how, how


def test_unrelated_output_still_fails():
    """★★ 反面：跑了无关命令、输出里没有答案 ⇒ ✗。"""
    rep = _rep((("['ls','src']"), "core.py organs llm"))
    ok, how = B2.verify(CHECK, "共 98 个 Python 文件", report=rep)
    assert ok is False, how


def test_exact_match_still_passes():
    """★ 旧行为保护：原样命令仍然走精确匹配这条路。"""
    rep = _rep((("python -c \"print('PYFILES 98')\""), "PYFILES 98"))
    ok, how = B2.verify(CHECK, "PYFILES 98", report=rep)
    assert ok is True, how
