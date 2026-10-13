# -*- coding: utf-8 -*-
"""R248 · 自更新锁（ff-only / 拦截 / 三面指令注册 / 真 fetch）。

★ 安全: 单测全部 restart_agent=False（不杀真 agent）; 双仓模拟在 var/。
"""
import io
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from dwc.foundation import updater as U  # noqa: E402

ROOT = U._dwc_root()


def _git(cwd, *a):
    return subprocess.run(["git", "-C", cwd] + list(a), capture_output=True,
                          text=True, timeout=60, encoding="utf-8",
                          errors="replace").stdout.strip()


def _two_repos():
    """bare remote + 两个 clone（每例唯一目录 — Windows 下 .git 对象
    只读, 复用目录 rmtree 会 PermissionError）。"""
    import shutil
    import time as _t
    WORK = os.path.join(ROOT, "var", "__test_r248_%d" % (_t.time_ns() % 10**9,))
    os.makedirs(WORK, exist_ok=True)
    rem = os.path.join(WORK, "remote.git")
    subprocess.run(["git", "init", "--bare", "-q", rem], check=True)
    a = os.path.join(WORK, "a")
    subprocess.run(["git", "clone", "-q", rem, a], check=True)
    for f, v in (("a/f.txt", "v1\n"),):
        p = os.path.join(a, f)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        io.open(p, "w", encoding="utf-8").write(v)
    _git(a, "add", "-A"); _git(a, "-c", "user.email=t@t", "-c", "user.name=t",
                               "commit", "-q", "-m", "v1")
    _git(a, "push", "-q", "origin", "master")
    b = os.path.join(WORK, "b")
    subprocess.run(["git", "clone", "-q", rem, b], check=True)
    return a, b


def test_check_detects_behind(tmp_path=None):
    """★★★ check 锁: 远端有新提交 ⇒ behind/available。"""
    a, b = _two_repos()
    io.open(os.path.join(a, "f.txt"), "w", encoding="utf-8").write("v2\n")
    _git(a, "add", "-A"); _git(a, "-c", "user.email=t@t", "-c", "user.name=t",
                               "commit", "-q", "-m", "v2")
    _git(a, "push", "-q", "origin", "master")
    st = U.check(b)
    assert st["ok"] is True
    assert st["behind"] == 1
    assert st["update_available"] is True


def test_update_ff_only_pulls():
    """★★★ update 锁: ff-only 拉新 + sha 验证（不重启 agent）。"""
    a, b = _two_repos()
    io.open(os.path.join(a, "f.txt"), "w", encoding="utf-8").write("v3\n")
    _git(a, "add", "-A"); _git(a, "-c", "user.email=t@t", "-c", "user.name=t",
                               "commit", "-q", "-m", "v3")
    _git(a, "push", "-q", "origin", "master")
    rep = U.update(root=b, restart_agent=False)
    assert rep["changed"] is True
    assert rep["commits"] == 1
    assert _git(b, "rev-parse", "HEAD") == _git(a, "rev-parse", "HEAD")


def test_update_blocks_dirty():
    """★★★ update 拦截锁: 工作区脏 ⇒ 拒绝（生产禁 stash）。"""
    a, b = _two_repos()
    io.open(os.path.join(a, "f.txt"), "w", encoding="utf-8").write("v4\n")
    _git(a, "add", "-A"); _git(a, "-c", "user.email=t@t", "-c", "user.name=t",
                               "commit", "-q", "-m", "v4")
    _git(a, "push", "-q", "origin", "master")
    io.open(os.path.join(b, "f.txt"), "w", encoding="utf-8").write("local edit\n")
    rep = U.update(root=b, restart_agent=False)
    assert rep["changed"] is False
    assert "脏" in rep["why"]


def test_update_blocks_ahead():
    """★★★ update 拦截锁: 本地领先 ⇒ 拒（防分叉被 ff 掩盖）。"""
    a, b = _two_repos()
    io.open(os.path.join(a, "f.txt"), "w", encoding="utf-8").write("v5\n")
    _git(a, "add", "-A"); _git(a, "-c", "user.email=t@t", "-c", "user.name=t",
                               "commit", "-q", "-m", "v5")
    _git(a, "push", "-q", "origin", "master")
    io.open(os.path.join(b, "g.txt"), "w", encoding="utf-8").write("local\n")
    _git(b, "add", "-A"); _git(b, "-c", "user.email=t@t", "-c", "user.name=t",
                               "commit", "-q", "-m", "local")
    rep = U.update(root=b, restart_agent=False)
    assert rep["changed"] is False
    assert "领先" in rep["why"]


def test_noop_when_current():
    """★★★ noop 锁: 已最新 ⇒ changed=False。"""
    a, b = _two_repos()
    rep = U.update(root=b, restart_agent=False)
    assert rep["changed"] is False
    assert "最新" in rep["why"]


def test_cli_update_route():
    """★★★ CLI 路由锁: cli_main 含 update 分支 + help 表。"""
    p = os.path.join(ROOT, "src", "dwc", "cli_main.py")
    src = io.open(p, encoding="utf-8").read()
    assert 'cmd == "update"' in src
    assert "dwc update [--check]" in src


def test_tui_and_chat_register_update():
    """★★★ 指令注册锁: TUI/chat 都认 /update。"""
    t = io.open(os.path.join(ROOT, "scripts", "dwc_tui.py"),
                encoding="utf-8").read()
    assert '"/update", "/u"' in t
    assert '("/update", "从 GitHub' in t
    c = io.open(os.path.join(ROOT, "scripts", "dwc_chat.py"),
                encoding="utf-8").read()
    assert '"/update", "/u"' in c
