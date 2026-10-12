# -*- coding: utf-8 -*-
"""R210 · 独立指令面: 指令核心单实现 + HTTP RPC + CLI 壳（用户拍板案①）。"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import time
import urllib.request

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc import agent_rpc as R                                # noqa: E402

PY = r"C:\Users\41228\AppData\Local\hermes\hermes-agent\venv\Scripts\python.exe"


# ═══ 指令核心（单实现）═══
def test_submit_query_cancel_chain():
    """★★★ 指令链: submit → query=pending → cancel → query=cancelled
    （cancel 走 done 态对账 — append-only inbox 不改写）。"""
    tid = "T_r210_lock"
    st = R._done_state()
    st.pop(tid, None)
    with open(R.INBOX_DONE, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False)
    r = R.cmd_submit("锁测试单", id=tid)
    assert r["ok"], r
    assert R.cmd_query(tid)["state"] == "pending"
    assert R.cmd_cancel(tid)["ok"]
    assert R.cmd_query(tid)["state"] == "cancelled"


def test_submit_rejects_duplicate_and_empty():
    """★ 协议边界: 空任务拒; done 态 id 撞车拒。"""
    assert R.cmd_submit("")["ok"] is False
    r = R.cmd_submit("t", id="T_r210_lock")   # 上一锁已把它标 cancelled
    assert r["ok"] is False and "已存在" in r["error"]


def test_status_shape():
    """★★ status 形态锁: pid/frozen/heartbeat/queue/db 齐（我与监控的消费口）。"""
    s = R.cmd_status()
    for k in ("pid", "frozen", "heartbeat", "queue", "db_bytes"):
        assert k in s, "status 缺字段 %r" % k
    assert "pending" in s["queue"] and "done" in s["queue"]


def test_list_dedups_and_orders_newest_first():
    """★★ list: 同 id 多次投单去重 + 后投先列（append-only 的现实修正）。"""
    tid = "T_r210_dup"
    with open(R.INBOX, "a", encoding="utf-8") as fh:
        for _ in range(2):
            fh.write(json.dumps({"id": tid, "task": "dup"}, ensure_ascii=False)
                     + "\n")
    st = R._done_state()
    st.pop(tid, None)
    with open(R.INBOX_DONE, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False)
    items = R.cmd_list()["items"]
    assert sum(1 for x in items if x["id"] == tid) == 1, "未去重"
    R.cmd_cancel(tid)


# ═══ HTTP RPC ═══
def test_rpc_auth_and_call():
    """★★★ RPC: 错 token 401 拒; 对 token status 200 ok; 未知方法报错表。"""
    srv = R.serve(port=18823)                  # 随机高位端口（不撞 agent 的 8802）
    try:
        time.sleep(0.3)
        def call(method, token):
            body = json.dumps({"method": method}).encode()
            req = urllib.request.Request(
                "http://127.0.0.1:18823/rpc", data=body,
                headers={"Content-Type": "application/json",
                         "X-DWC-Token": token})
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return resp.status, json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                return e.code, json.loads(e.read().decode())
        tok = R.load_or_make_token()
        code, out = call("status", "bad")
        assert code == 401, (code, out)
        code, out = call("status", tok)
        assert code == 200 and out["ok"] and "pid" in out["result"]
        code, out = call("no_such_cmd", tok)
        assert out["ok"] is False and "未知指令" in out["error"]
    finally:
        srv.shutdown()


# ═══ 单例锁（R210 现场根治: 双 agent 互踩）═══
def test_singleton_lock_refuses_second_start():
    """★★★ 单例锁: pid 文件已有活 agent ⇒ 拒启 rc1（同 db 双写的事故锁）。
    ★★ 全程隔离（DWC_VAR_DIR）: 曾用生产 pid 文件伪造活 pid 留死尸
      （2026-10-12 实测把守夜人引去误拉活）—— 现在隔离目录自洽。"""
    import psutil
    iso = os.path.join(R.VAR, "__r210_lock__")
    if os.path.exists(iso):
        import shutil
        shutil.rmtree(iso)
    os.makedirs(iso, exist_ok=True)
    io.open(os.path.join(iso, "dwc_agent.pid"), "w",
            encoding="utf-8").write(str(os.getpid()))   # 伪造活 pid
    r = subprocess.run([PY, os.path.join(ROOT, "scripts", "dwc_agent.py")],
                       capture_output=True, text=True, timeout=60, cwd=ROOT,
                       env=dict(os.environ, DWC_VAR_DIR=iso))
    assert r.returncode == 1 and "拒绝双开" in r.stderr, (
        "单例锁失效: rc=%d %s" % (r.returncode, r.stderr[-120:]))
    # ★ 无污染: 生产 pid 文件不被本测试触碰（死尸教训）
    if os.path.exists(R.PID):
        prod = int(io.open(R.PID, encoding="utf-8").read().strip())
        assert prod != os.getpid(), "测试把生产 pid 污染成本进程"


# ═══ CLI 壳 ═══
def test_cli_json_output_parseable():
    """★ CLI: --json 输出机器可解析（程序消费口）。"""
    r = subprocess.run([PY, os.path.join(ROOT, "scripts", "dwc_cli.py"),
                        "status", "--json"],
                       capture_output=True, text=True, timeout=60, cwd=ROOT)
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert "pid" in out and "queue" in out
