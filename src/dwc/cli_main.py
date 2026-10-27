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
  dwc memory-stats          # 记忆契约/检索统计（只读）
  dwc knowledge build       # 记忆 → var/knowledge/*.md（可重建）
  dwc memory consolidate    # 近重复合并（默认 dry-run）
  dwc memory maintain       # 记忆维护计划（--apply 才归档）
"""
from __future__ import annotations

import json
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
        # ★ R审计-P2 · pid 文件有两种历史形态: 纯数字 或 {"pid": N}
        #   （现场: 纯数字时 json.load 返回 int ⇒ .get() AttributeError
        #    ⇒ stop 静默失败 ⇒ 旧进程残留 + 新进程抢锁）
        raw = open(pf, encoding="utf-8").read().strip()
        try:
            _j = json.loads(raw)
            pid = int(_j.get("pid", 0)) if isinstance(_j, dict) else int(_j)
        except (ValueError, TypeError):
            pid = int(raw or 0)
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
    if cmd == "memory-stats":
        # ★ M3.4/MEM-18/MEM-03/MEM-14 · 只读消费：不生成、不启用重机制
        from dwc.agent_rpc import DB
        from dwc.organs.memory import MemoryKernel
        from dwc.organs.memory_bench import bench
        from dwc.organs import memory_policy
        m = MemoryKernel(DB)
        try:
            out = {
                "retrieval": m.retrieval_stats(),
                "quality": m.retrieval_quality(None),
                "bench": bench(m, {}),
                "policy": memory_policy.status(),
                "contract": m.memory_stats(),
            }
        finally:
            m.close()
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0
    if cmd == "knowledge":
        # ★ H6 · 只读投影：build/check/list/search；不改 skill prompt
        from dwc.agent_rpc import DB
        from dwc.organs.memory import MemoryKernel
        from dwc.organs import knowledge_page as KP
        sub = rest[0] if rest else "list"
        args = rest[1:]
        out_dir = None
        scope = None
        for i, a in enumerate(args):
            if a == "--out" and i + 1 < len(args):
                out_dir = args[i + 1]
            if a == "--scope" and i + 1 < len(args):
                scope = args[i + 1]
        m = MemoryKernel(DB)
        try:
            if sub == "build":
                rep = KP.build(m, out_dir=out_dir, scope=scope)
            elif sub == "check":
                rep = KP.check(m, out_dir=out_dir)
            elif sub == "search":
                q = " ".join(a for a in args if not a.startswith("--"))
                rep = KP.search(m, q, out_dir=out_dir)
            else:
                rep = {"pages": KP.list_pages(out_dir=out_dir)}
        finally:
            m.close()
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return 0
    if cmd == "memory":
        # ★ H5 · 离线 consolidation：默认 dry-run；--apply 才写
        from dwc.agent_rpc import DB
        from dwc.organs.memory import MemoryKernel
        from dwc.organs import consolidate as C
        sub = rest[0] if rest else "consolidate"
        args = rest[1:]
        apply_flag = "--apply" in args
        scope = None
        for i, a in enumerate(args):
            if a == "--scope" and i + 1 < len(args):
                scope = args[i + 1]
        if sub == "migrate-factual":
            from dwc.organs import skill_writer as SW
            m = MemoryKernel(DB)
            try:
                rep = SW.migrate_factual(m, apply=apply_flag)
            finally:
                m.close()
            print(json.dumps(rep, ensure_ascii=False, indent=1))
            return 0
        if sub == "bench":
            from dwc.organs.memory_bench import bench
            labels_path = None
            for i, a in enumerate(args):
                if a == "--labels" and i + 1 < len(args):
                    labels_path = args[i + 1]
            if not labels_path:
                print("memory bench 需要 --labels <json>（{query: [node_id,...]}）")
                return 1
            try:
                with open(labels_path, encoding="utf-8") as fh:
                    labels = json.load(fh)
            except (OSError, ValueError) as exc:
                print("labels 读取失败: %s" % exc)
                return 1
            m = MemoryKernel(DB)
            try:
                rep = bench(m, labels if isinstance(labels, dict) else {})
            finally:
                m.close()
            print(json.dumps(rep, ensure_ascii=False, indent=1))
            return 0
        if sub == "maintain":
            from dwc.organs import memory_maintenance as MM
            m = MemoryKernel(DB)
            try:
                rep = m.maintain() if apply_flag else MM.plan(m)
            finally:
                m.close()
            print(json.dumps(rep, ensure_ascii=False, indent=1))
            return 0
        if sub != "consolidate":
            print("未知 memory 子命令 %r（当前: consolidate, migrate-factual, maintain, bench）" % sub)
            return 1
        m = MemoryKernel(DB)
        try:
            rep = C.apply(m, scope=scope) if apply_flag else C.plan(
                m, scope=scope)
        finally:
            m.close()
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return 0
    if cmd == "workflow":
        # ★ P2 · 可恢复编排：步骤内容哈希缓存；--resume 复用未变步骤
        from dwc.llm.workflow import run_workflow
        sub = rest[0] if rest else "run"
        args = rest[1:]
        if sub != "run":
            print("未知 workflow 子命令 %r（当前: run）" % sub)
            return 1
        spec_path = next((a for a in args if not a.startswith("--")), None)
        if not spec_path:
            print("workflow run 需要 <spec.json>")
            return 1
        run_id = None
        resume = False
        max_rounds = 6
        for i, a in enumerate(args):
            if a == "--run-id" and i + 1 < len(args):
                run_id = args[i + 1]
            if a == "--resume" and i + 1 < len(args):
                resume = True
                run_id = args[i + 1]
            if a == "--max-rounds" and i + 1 < len(args):
                try:
                    max_rounds = max(1, int(args[i + 1]))
                except ValueError:
                    print("--max-rounds 非整数，使用默认 %d" % max_rounds,
                          file=sys.stderr)
        try:
            with open(spec_path, encoding="utf-8") as fh:
                spec = json.load(fh)
        except (OSError, ValueError) as exc:
            print("workflow spec 读取失败: %s" % exc)
            return 1
        from dwc.llm.client import LLMClient
        from dwc.llm.task_exec import execute_user_task

        def _runner(task, opts):
            mr = int(opts.get("max_rounds") or max_rounds)
            return execute_user_task(task, llm=LLMClient(), max_rounds=mr)

        try:
            rep = run_workflow(spec, runner=_runner, run_id=run_id,
                               resume=resume)
        except (ValueError, OSError) as exc:
            print("workflow 失败: %s" % exc)
            return 1
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return 0 if rep.get("status") == "done" else 1
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
