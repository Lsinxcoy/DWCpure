# -*- coding: utf-8 -*-
"""agent 存活看门狗 —— 跑批期间防「静默死亡污染结果」。

★★★ 为什么需要（现场取证 2026-10-20）:
  · 08:52 agent 静默死亡：无 traceback、无冻结标志、预算未到、pid 文件残留
  · 10:00 前再次死亡
  · 死因未查明 ⇒ 不能靠"查根因"来解决，只能靠"死了就发现并拉起"

★★ 关键判据（踩过坑）:
  · **不能**用 `cmdline.endswith("scripts/dwc_agent.py")` —— agent 会
    re-exec 成 `hermes-runtime` 的 python，且 cmdline 后面跟着
    `--llm --interval 30`，endswith 必然漏判（已导致双开+被杀事故）。
  · 正确判据：**任一 cmdline 元素包含 `scripts/dwc_agent.py`**，
    且排除自己（`-c` 内联脚本会命中自己）。
  · 心跳 pid 存活 ≠ 服务可用：还要看心跳时间是否新鲜（>`stale_sec` 即判死）。

★ 用法:
    python scripts/dwc_watchdog.py --check          # 只检查，退出码 0/1
    python scripts/dwc_watchdog.py --ensure         # 检查并拉起（幂等）
    python scripts/dwc_watchdog.py --ensure --interval 20
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HB = os.path.join(ROOT, "var", "dwc_agent_heartbeat.json")
PIDF = os.path.join(ROOT, "var", "dwc_agent.pid")
STDERR = os.path.join(ROOT, "var", "dwc_agent_stderr.log")
AGENT = os.path.join(ROOT, "scripts", "dwc_agent.py")

DEFAULT_STALE_SEC = 600          # 心跳超过 10 分钟没更新 ⇒ 判死


def _py() -> str:
    """优先用 venv python（runtime 的 PEP668 装不进依赖）。"""
    cand = os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(sys.executable))), "Scripts", "python.exe")
    if os.path.isfile(cand):
        return cand
    return sys.executable


def find_agents() -> list:
    """返回所有 dwc_agent 进程 pid。

    ★★★ 判据：任一 cmdline 元素**包含** `scripts/dwc_agent.py`
      （不是 endswith —— 带参数时 endswith 漏判，已致双开事故）。
    排除自己：`python -c "..."` 的 cmdline 里脚本路径在源码字符串里，
    会被 contains 命中 ⇒ 必须排除 `-c`。
    """
    try:
        import psutil
    except ImportError:
        return []
    me = os.getpid()
    out = []
    for p in psutil.process_iter(["pid", "cmdline"]):
        try:
            if p.pid == me:
                continue
            cl = [str(x).replace("\\", "/") for x in (p.info.get("cmdline") or [])]
            if "-c" in cl:                     # 内联脚本，不是真 agent
                continue
            if any(x.endswith("scripts/dwc_agent.py") or
                   "scripts/dwc_agent.py" == x.split(" ")[0] for x in cl):
                out.append(p.pid)
        except Exception:                      # noqa: BLE001 — 进程可能已退
            continue
    return out


def heartbeat() -> dict:
    try:
        return json.load(open(HB, encoding="utf-8"))
    except Exception:                          # noqa: BLE001
        return {}


def check(stale_sec: float = DEFAULT_STALE_SEC) -> dict:
    """返回 {alive, pids, hb_age, reason}。"""
    pids = find_agents()
    hb = heartbeat()
    hb_pid = int(hb.get("pid") or 0)
    hb_ts = str(hb.get("ts") or "")

    age = None
    if hb_ts:
        try:
            from datetime import datetime
            dt = datetime.fromisoformat(hb_ts.replace("Z", "+00:00"))
            age = (datetime.now(dt.tzinfo) - dt).total_seconds()
        except Exception:                      # noqa: BLE001
            age = None

    alive = bool(pids) and (age is None or age <= stale_sec)
    reason = ""
    if not pids:
        reason = "no_process"
    elif age is not None and age > stale_sec:
        reason = "heartbeat_stale(%.0fs)" % age
    return {"alive": alive, "pids": pids, "hb_pid": hb_pid,
            "hb_age": age, "reason": reason}


def ensure(interval: int = 20) -> dict:
    """确保 agent 在跑；不在就拉起。幂等。"""
    st = check()
    if st["alive"]:
        return dict(st, action="none")

    # ★★★ R402 · **有进程就绝不拉新进程** —— 现场（2026-10-21 03:25）：
    #   `check()` 把"心跳过期"判成"死了"，于是删掉 pid 锁再拉一个新的；
    #   但老进程还活着 ⇒ **两个 agent 同时消费同一个收件箱**
    #   ⇒ 同一单被跑 13 次、状态互相覆盖、报告被后跑的覆盖。
    #   心跳过期 ≠ 进程死亡（长任务里心跳线程可能卡住）。
    #   宁可告警"心跳过期"，也绝不允许出现第二个消费者。
    if st.get("pids"):
        try:
            err = open(STDERR, "a", encoding="utf-8")
            err.write("\n===== 心跳过期但进程仍在，拒绝重复拉起 %s · pids=%s · %s =====\n"
                      % (time.strftime("%Y-%m-%dT%H:%M:%S"),
                         st.get("pids"), st.get("reason")))
            err.flush()
            err.close()
        except OSError:
            pass
        return dict(st, action="stale_heartbeat_refused")

    # 到这里才是"确实没有进程" ⇒ 清理残留 pid 文件（单例锁会拒绝启动）
    for f in (PIDF, PIDF + ".lock"):
        try:
            if os.path.exists(f):
                os.remove(f)
        except OSError:
            pass

    flags = (getattr(subprocess, "DETACHED_PROCESS", 0x8)
             | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
    err = open(STDERR, "a", encoding="utf-8")
    err.write("\n===== watchdog 拉起 %s =====\n"
              % time.strftime("%Y-%m-%dT%H:%M:%S"))
    err.flush()
    pr = subprocess.Popen([_py(), AGENT, "--llm", "--interval", str(interval)],
                          cwd=ROOT, stdout=subprocess.DEVNULL, stderr=err,
                          creationflags=flags, close_fds=True)

    # 轮询到心跳新鲜为止（最多 120s）
    t0 = time.time()
    while time.time() - t0 < 120:
        time.sleep(3)
        st2 = check()
        if st2["alive"]:
            return dict(st2, action="restarted", launcher=pr.pid)
    return dict(check(), action="restart_failed", launcher=pr.pid)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--ensure", action="store_true")
    ap.add_argument("--interval", type=int, default=20)
    ap.add_argument("--stale-sec", type=float, default=DEFAULT_STALE_SEC)
    a = ap.parse_args()

    if a.ensure:
        r = ensure(a.interval)
    else:
        r = check(a.stale_sec)
    print(json.dumps(r, ensure_ascii=False))
    sys.exit(0 if r.get("alive") else 1)


if __name__ == "__main__":
    main()
