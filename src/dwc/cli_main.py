"""R235 · `dwc` 专属命令入口（console_scripts entry — 头部 agent 同款形态）。

★★★ 定位（G1）: **DWC-AUTO** —— 用户面对的唯一命令面。
★★★ 单实现纪律: 指令核心仍只在 agent_rpc; 本模块只做**路由**（不实现业务）。

★ 形态（opencode/claude 惯例: 无参 = 进交互界面）:
  dwc                       # 无参 ⇒ chat REPL（原生交互界面）
  dwc chat / dwc ask "任务"  # 显式交互 / 单发派单
  dwc update [--check]      # 从 GitHub 拉取更新 + 重启 agent
dwc status|doctor|...     # agent_rpc 九指令（与 HTTP RPC / CLI 同一实现）
  dwc start [--llm] / stop  # 常驻 agent 生命周期
  dwc setup / bench         # 配置向导 / 任务基准
"""
from __future__ import annotations

import os
import subprocess
import sys


def _root() -> str:
    if os.environ.get("DWC_ROOT", "").strip():
        return os.environ["DWC_ROOT"].strip()
    cur = os.path.dirname(os.path.abspath(__file__))     # src/dwc/
    while True:
        if (os.path.isdir(os.path.join(cur, "src", "dwc"))
                and os.path.isdir(os.path.join(cur, "config"))):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise RuntimeError("找不到 DWC 根 — 设 DWC_ROOT")
        cur = parent


def _py() -> str:
    return sys.executable


def _run_script(name: str, args) -> int:
    """scripts/ 下的脚本以子进程跑（保持各脚本独立可跑 — dispatcher 只路由）。"""
    root = _root()
    return subprocess.call([_py(), os.path.join(root, "scripts", name)] + list(args),
                           cwd=root)


def _rpc(argv) -> int:
    """九指令 + doctor → dwc_cli（它委托 agent_rpc 单实现）。"""
    return _run_script("dwc_cli.py", argv)


def _stop_agent() -> int:
    import json
    root = _root()
    pf = os.path.join(root, "var", "dwc_agent.pid")
    if not os.path.exists(pf):
        print("agent 未运行（无 pid 文件）")
        return 1
    try:
        pid = int(json.load(open(pf, encoding="utf-8")).get("pid", 0))
    except (ValueError, OSError):
        pid = 0
    try:
        import psutil
        if pid and psutil.pid_exists(pid):
            psutil.Process(pid).terminate()
            print("已停止 agent (pid %d)" % pid)
        else:
            print("pid 文件在但进程不在 — 清理 pid 文件")
        if os.path.exists(pf):
            os.remove(pf)
        return 0
    except ImportError:
        print("需要 psutil 才能 stop — 手动 taskkill /PID %d" % pid)
        return 1


def main(argv=None) -> int:
    for _stream in (sys.stdout, sys.stderr):
        try:                                   # ★ UTF-8 输出（936 码页防乱）
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError) as _e:
            # G7: 不静默 — 老 Python/管道流不支持 reconfigure 时留一行痕
            sys.stderr.write("utf8 reconfigure 跳过: %s\n" % _e)
    argv = list(sys.argv[1:] if argv is None else argv)
    cmd = argv[0] if argv else "chat"
    rest = argv[1:]
    if cmd in ("chat", "repl"):
        # ★ R239: 默认全屏 TUI（textual）; --plain 走老 REPL;
        #   TUI 脚本内 textual 不可用会自动回退 chat（降级不硬撑）
        if rest and rest[0] == "--plain":
            return _run_script("dwc_chat.py", rest[1:])
        return _run_script("dwc_tui.py", rest)
    if cmd in ("ask", "-c", "--ask"):
        # 单发: dwc ask "任务" ⇒ chat -c "任务"
        return _run_script("dwc_chat.py", ["-c"] + rest)
    if cmd in ("status", "doctor", "submit", "query", "list", "cancel",
               "freeze", "unfreeze", "history"):
        return _rpc([cmd] + rest)
    if cmd == "start":
        root = _root()
        agent = os.path.join(root, "scripts", "dwc_agent.py")
        kwargs = {}
        if os.name == "nt":
            kwargs["creationflags"] = (0x00000008 | 0x00000200)  # DETACHED|NEW_PROCESS
        subprocess.Popen([_py(), agent] + rest, cwd=root,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         stdin=subprocess.DEVNULL, **kwargs)
        print("agent 启动中（后台）— dwc status 查看")
        return 0
    if cmd == "stop":
        return _stop_agent()
    if cmd == "update":        # ★ R248 自更新（GitHub 为源）
        from dwc.foundation.updater import check, update
        if rest and rest[0] in ("--check", "-c", "check"):
            st = check()
            if not st.get("ok"):
                print("✗ 检查失败: %s" % st.get("why"))
                return 1
            if st.get("update_available"):
                print("⬆ 可更新: 落后 %d 个提交 (本地 %s → 远端 %s)"
                      % (st["behind"], st["local"][:9], st["remote"][:9]))
            else:
                print("✓ 已是最新 (%s)" % st.get("local", "")[:9])
            return 0
        rep = update()
        if rep.get("changed"):
            print("✓ 已更新 %s → %s (%d 个提交)"
                  % (rep["from"], rep["to"], rep["commits"]))
            ag = rep.get("agent", {})
            print(("agent 已重启 (pid=%s)" % ag.get("pid")) if ag.get("ok")
                  else ("agent 重启: %s" % ag.get("why", "?")))
            if rep.get("deps_changed"):
                print("⚠ 依赖变更: %s" % rep["deps_hint"])
            return 0
        print("— 未更新: %s" % rep.get("why", "?"))
        return 1 if rep.get("why", "").startswith(("fetch", "pull")) else 0
    if cmd == "setup":
        return _run_script("dwc_setup.py", rest)
    if cmd == "bench":
        return _run_script("dwc_bench.py", rest)
    if cmd in ("help", "-h", "--help"):
        print(__doc__)
        return 0
    print("未知子命令 %r — dwc help 查看全部" % cmd)
    return 1


if __name__ == "__main__":
    sys.exit(main())
