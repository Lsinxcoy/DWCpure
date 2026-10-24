# -*- coding: utf-8 -*-
"""R211 · 交互式 CLI 界面（学 GitHub 头部 agent: 无参 REPL + 斜杠命令）。"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
PY = sys.executable
CHAT = os.path.join(ROOT, "scripts", "dwc_chat.py")


def _run(args=(), inp=None, t=90):
    return subprocess.run([PY, CHAT] + list(args), capture_output=True,
                          text=True, cwd=ROOT, timeout=t, input=inp,
                          encoding="utf-8", errors="replace")


def test_single_shot_status_json():
    """★ -c 单发（= opencode run 地位）: /status 出可解析 JSON。"""
    r = _run(["-c", "/status"])
    assert r.returncode == 0, r.stderr[-200:]
    out = json.loads(r.stdout)
    assert "pid" in out and "queue" in out


def test_slash_prefix_filter():
    """★★ 斜杠过滤（Claude Code 模式: 输 /字母 报候选）。"""
    r = _run(["-c", "/st"])
    assert r.returncode == 0 and "/status" in r.stdout, r.stdout[:200]


def test_repl_pipe_session():
    """★★★ 无参 = REPL: BANNER + 状态栏 + /help + /quit 干净退出
    （管道喂 stdin 模拟会话 — 真 tty 由人工验收）。"""
    r = _run([], inp="/help\n/quit\n")
    assert r.returncode == 0, r.stderr[-200:]
    # ★ R238 锁跟语义: 横幅仍是"品牌块字 + 定位句"（文案随设计升级）
    assert "DIVINE WISDOM CORE" in r.stdout \
        and "独立常驻 agent" in r.stdout
    assert "/watch" in r.stdout, "help 缺命令"
    assert "再见" in r.stdout, "未正常收尾"


def test_natural_language_submits_and_tracks(monkeypatch=None):
    """★★ 自然语言(异步模式) = 投单+跟踪: handle(纯文本) 走 submit 并触发
    watch（watch 打桩不真等）; 单子随后 cancel 清理。
    ★ R236 语义校准: 默认已改同步直驱（见 test_r236_interact）——
      本锁改测 /bg 异步通道（两形态各有锁, 行为变锁跟语义不删）。"""
    import dwc_chat as C
    import dwc_agent as A
    C.BG_MODE = True                        # ★ 切异步投单模式
    watched = []
    orig_watch = C.watch
    C.watch = lambda tid, **kw: watched.append(tid)
    tid = "T_r211_chat"
    st = A._done_state()
    st.pop(tid, None)
    with open(A.INBOX_DONE, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False)
    try:
        assert C.handle("帮我读一下 core.py") is True
    finally:
        C.watch = orig_watch
        C.BG_MODE = False
    assert watched and watched[0].startswith("T_"), "没触发跟踪: %s" % watched
    # 清理刚投的单
    import agent_rpc as R
    for it in (R.cmd_list("pending") or {}).get("items", []):
        R.cmd_cancel(it["id"])


def test_call_degrades_to_local_when_rpc_down():
    """★★ RPC 降级: 网断 ⇒ call 落本地直调同一指令核心（单实现两前端 —
    agent 没起时 CLI 仍可用）。"""
    import dwc_chat as C
    orig = C._rpc
    C._rpc = lambda m, p=None, timeout=20: None     # 模拟 agent 离线
    try:
        out = C.call("list")
    finally:
        C._rpc = orig
    assert isinstance(out, dict) and "items" in out, out


def test_quit_aliases():
    """/quit /q /exit 都退出（学 OpenCode 别名习惯）。"""
    for q in ("/quit", "/q", "/exit"):
        r = _run([], inp=q + "\n")
        assert r.returncode == 0 and "再见" in r.stdout, q
