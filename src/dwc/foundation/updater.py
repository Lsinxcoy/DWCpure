"""R248 · 自更新器 — 以 GitHub 仓库为源（用户 2026-10-13 指令）。

定位: DWC-AUTO（自我强化 — 更新链让常驻体从远端源获得新能力）。
★ G7 痕迹: except 降级全部计数进 _DEGRADED（不静默）。

★ 安全边界（生产纪律）:
  - 只 ``--ff-only`` 快进（禁 merge/禁历史改写）；落后且本地领先 ⇒ 拦截报分叉
  - 工作区脏 ⇒ 拦截列出文件（生产禁 stash）
  - pull 前后 sha 双验；失败回滚点 = pull 前 sha（ff-only 未动则天然回滚）
  - 依赖变更（pyproject/requirements diff）⇒ **提示不自动 pip**（装包动作
    有 PEP668/venv 面，交用户拍板）
  - 更新后**必须重启 resident agent**（改仓库≠进程跑新码）；重启走单例锁
    + DETACHED_PROCESS（R243a 同款），并轮询心跳验证真活
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
from typing import Any

_SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _dwc_root() -> str:
    """仓库根: src/dwc/foundation/updater.py → 上三级。"""
    return os.path.abspath(os.path.join(_SRC, "..", ".."))


_DEGRADED: dict[str, int] = {}   # ★ G7: 降级计数（心跳轮询/停进程）


def _deg(what: str) -> None:
    _DEGRADED[what] = _DEGRADED.get(what, 0) + 1


def _git(root: str, *args: str, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", root] + list(args), capture_output=True,
                          text=True, timeout=timeout, encoding="utf-8",
                          errors="replace")


def _venv_python(root: str) -> str:
    """优先仓内/已知 venv 解释器（agent 需要 yaml/psutil — R243a 教训）。"""
    env_py = os.environ.get("DWC_PY", "").strip()
    if env_py and os.path.exists(env_py):
        return env_py
    la = os.environ.get("LOCALAPPDATA", "").strip()
    cand = [os.path.join(os.path.dirname(root), "venv", "Scripts", "python.exe")]
    if la:      # ★ R228 纪律: 环境变量拼接, 零硬编码（且修双反斜杠路径 bug）
        cand.append(os.path.join(la, "hermes", "hermes-agent", "venv",
                                 "Scripts", "python.exe"))
    cand.append(sys.executable)
    for c in cand:
        if os.path.exists(c):
            return c
    return "python"


def check(root: str | None = None) -> dict[str, Any]:
    """查更新: behind/ahead/dirty/远端 tip（不改任何状态）。"""
    root = root or _dwc_root()
    out: dict[str, Any] = {"root": root}
    r = _git(root, "fetch", "origin", "master", timeout=90)
    if r.returncode != 0:
        return {"ok": False, "why": "fetch 失败(网络/远端): " +
                (r.stderr or r.stdout).strip()[:200]}
    local = _git(root, "rev-parse", "HEAD").stdout.strip()
    remote = _git(root, "rev-parse", "origin/master").stdout.strip()
    behind = int(_git(root, "rev-list", "--count", "HEAD..origin/master").stdout.strip() or 0)
    ahead = int(_git(root, "rev-list", "--count", "origin/master..HEAD").stdout.strip() or 0)
    dirty = [l for l in _git(root, "status", "--porcelain").stdout.splitlines() if l.strip()]
    out.update({"ok": True, "local": local, "remote": remote,
                "behind": behind, "ahead": ahead, "dirty_files": dirty,
                "update_available": behind > 0})
    return out


def _restart_agent(root: str) -> dict[str, Any]:
    """重启 resident agent 让新码生效（停→清 pid→detached 拉活→验心跳）。"""
    try:
        import psutil
    except Exception:                             # noqa: BLE001
        return {"ok": False, "why": "无 psutil — 手动: dwc stop && dwc start"}
    # 1. 停（cmdline 匹配, 只杀 agent 本体）
    killed: list[int] = []
    for p in psutil.process_iter(["pid", "cmdline"]):
        cl = p.info.get("cmdline")
        if cl and "dwc_agent.py" in " ".join(cl):
            try:
                p.terminate()
                killed.append(p.info["pid"])
            except Exception:                     # noqa: BLE001
                _deg("stop_process")
    time.sleep(2)
    pidf = os.path.join(root, "var", "dwc_agent.pid")
    try:
        if os.path.exists(pidf):
            os.remove(pidf)
    except OSError:
        _deg("remove_pidf")
    # 2. 拉活（venv python + detached flags — R243a）
    py = _venv_python(root)
    flags = (getattr(subprocess, "DETACHED_PROCESS", 0x8)
             | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
             | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
    try:
        subprocess.Popen([py, os.path.join(root, "scripts", "dwc_agent.py")],
                         cwd=os.path.join(root, "scripts"),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=flags, close_fds=True)
    except Exception as e:                        # noqa: BLE001
        return {"ok": False, "why": "拉活失败: %s" % e}
    # 3. 心跳验证（12s 内）
    hbf = os.path.join(root, "var", "dwc_agent_heartbeat.json")
    t0 = time.time()
    while time.time() - t0 < 12:
        try:
            import json as _j
            hb = _j.load(open(hbf, encoding="utf-8"))
            ts = str(hb.get("ts", ""))
            if ts >= time.strftime("%Y-%m-%dT%H:%M", time.localtime(time.time() - 60)):
                return {"ok": True, "pid": hb.get("pid"), "killed": killed}
        except Exception:                         # noqa: BLE001
            _deg("heartbeat_poll")
        time.sleep(2)
    return {"ok": False, "why": "12s 无心跳 — 手动看 var/dwc_agent.log",
            "killed": killed}


def update(root: str | None = None,
           restart_agent: bool = True) -> dict[str, Any]:
    """执行更新: ff-only pull → 依赖变更检测 → 重启 agent。"""
    root = root or _dwc_root()
    st = check(root)
    if not st.get("ok"):
        return {"changed": False, **st}
    if not st["update_available"]:
        return {"changed": False, "why": "已是最新 (%s)" % st["local"][:9]}
    if st["ahead"] > 0:
        return {"changed": False, "why": ("本地领先 origin %d 个提交 — "
                "需先 push 或人工处理分叉（禁改写历史）" % st["ahead"])}
    if st["dirty_files"]:
        return {"changed": False, "why": "工作区脏（生产禁 stash）— 先处理:",
                "files": st["dirty_files"][:12]}
    before = st["local"]
    r = _git(root, "pull", "--ff-only", "origin", "master", timeout=300)
    if r.returncode != 0:
        return {"changed": False, "why": "pull 失败: " +
                (r.stderr or r.stdout).strip()[:200], "rollback": before}
    after = _git(root, "rev-parse", "HEAD").stdout.strip()
    if after == before:
        return {"changed": False, "why": "pull 后 sha 未变 — 远端无新内容",
                "rollback": before}
    # 依赖变更检测（diff 统计里出现 requirements/pyproject ⇒ 提示）
    df = _git(root, "diff", "--name-only", before, after).stdout.splitlines()
    deps = [f for f in df if f.strip() in ("requirements.txt", "pyproject.toml")]
    n = int(_git(root, "rev-list", "--count", "%s..%s" % (before, after)).stdout.strip() or 0)
    rep: dict[str, Any] = {"changed": True, "from": before[:9], "to": after[:9],
                           "commits": n, "deps_changed": deps,
                           "deps_hint": ("需要: pip install -r requirements.txt"
                                         if deps else "")}
    if restart_agent:
        rep["agent"] = _restart_agent(root)
    return rep
