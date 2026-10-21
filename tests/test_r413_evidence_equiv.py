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


# ══════════════════ R413-b · 解释器路径不该影响取证 ══════════════════

def test_interpreter_absolute_path_matches():
    """★★★ rv07 复刻：判据写 `python scripts/gate.py`，
    agent 用绝对路径 `C:/.../python.exe scripts/gate.py` ⇒ 必须算取证。

    现场：agent 真跑了、rc=0、输出末尾"总结: 全部通过"，
    却因 argv[0] 是绝对路径被判 `no-agent-evidence`。
    """
    check = {"type": "rc_and_contains",
             "cmd": "python scripts/gate.py", "target": "全部通过"}
    rep = _rep((("['C:/Users/x/venv/Scripts/python.exe','scripts/gate.py']"),
                "DWC 质量门\n总结: 全部通过\n"))
    ok, how = B2.verify(check, "门禁已运行，全部通过", report=rep)
    assert ok is True, how
    assert "agent-ran" in how, how


def test_interpreter_still_requires_the_script():
    """★★ 反面：换了绝对路径解释器，但跑的是**别的脚本** ⇒ 仍 ✗。"""
    check = {"type": "rc_and_contains",
             "cmd": "python scripts/gate.py", "target": "全部通过"}
    rep = _rep((("['C:/Users/x/venv/Scripts/python.exe','scripts/other.py']"),
                "全部通过"))
    ok, how = B2.verify(check, "全部通过", report=rep)
    assert ok is False, how
    assert "no-agent-evidence" in how, how


def test_chinese_target_anchor_is_target_itself():
    """★★ rv07 锚点：中文 target 后面跟 `（rc=0）` 时，
    锚点必须取 **target 本身**，不是 `rc=0` 这种噪声。"""
    chk = {"type": "rc_and_contains", "cmd": "x", "target": "全部通过"}
    got = B2._answer_anchor(chk, "答：全部通过", "总结: 全部通过（rc=0）\n")
    assert got == "全部通过", got


def test_numeric_anchor_still_preferred():
    """★ 旧行为保护：`PYFILES 98` 仍取数字锚点 `98`（更精确）。"""
    chk = {"type": "rc_and_contains", "cmd": "x", "target": "PYFILES"}
    got = B2._answer_anchor(chk, "共 98 个", "PYFILES 98\n")
    assert got == "98", got
