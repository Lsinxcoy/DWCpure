"""DWC 命令执行策略。

定位声明 · **DWC-AUTO**（自我强化）
  ★ 本模块只做 allow/deny/ask 决策，不执行命令。
  ★ 黑名单不是安全边界；这里用 allowlist + 明确的审批态。
  ★ `python -c` 默认拒绝；只有工具层私有标记 `_from_tool` 才允许。
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass

#: 只读命令：qa_mode 与普通 run 都允许
READONLY = frozenset({
    "echo", "ls", "dir", "find", "grep", "rg", "cat", "type",
    "head", "tail", "wc", "stat", "pwd", "tree", "where", "which",
})

#: 需要人工授权的写/外发命令（仍不是 allowlist 的替代品）
ASK = frozenset({
    "rm", "rmdir", "del", "mv", "move", "cp", "copy",
    "curl", "wget", "ssh", "scp", "pip", "npm",
})

#: 只读 git 子命令
READONLY_GIT = frozenset({
    "status", "diff", "log", "show", "rev-parse", "ls-files", "grep",
})

#: 允许的 python -m 模块
PY_MODULES = frozenset({"pytest", "unittest", "compileall"})

#: 允许的静态检查器
CHECKERS = frozenset({"pytest", "ruff", "bandit"})


@dataclass(frozen=True)
class RunDecision:
    allowed: bool
    reason: str
    requires_approval: bool = False
    ask: str = ""


def _base(argv0: str) -> str:
    exe = shutil.which(argv0) or argv0
    return os.path.basename(exe).lower().removesuffix(".exe")


def check(argv, *, cwd: str, from_tool: bool = False,
          allow_unsafe: bool = False) -> RunDecision:
    """返回 allow/deny/ask；不执行任何命令。"""
    if not isinstance(argv, list) or not argv:
        return RunDecision(False, "cmd 必须是非空 argv 列表")
    if any(not isinstance(x, str) or "\x00" in x for x in argv):
        return RunDecision(False, "argv 含非字符串或 NUL")
    name = _base(argv[0])

    # python：只允许 -m 测试/编译；python -c 仅工具层私有标记
    if name in {"python", "python3", "py"}:
        if len(argv) >= 3 and argv[1] == "-m" and argv[2] in PY_MODULES:
            return RunDecision(True, "python -m 测试/编译")
        if len(argv) >= 3 and argv[1] == "-c" and from_tool:
            return RunDecision(True, "工具层 python -c")
        return RunDecision(False, "python -c/脚本执行默认禁止")

    if name in CHECKERS:
        return RunDecision(True, "测试/静态检查")
    if name in READONLY:
        if name == "find" and any(
                str(x).lower() in {"-exec", "-execdir", "-ok", "-okdir",
                                   "-delete", "-fprint", "-fprintf"}
                for x in argv[1:]):
            return RunDecision(False, "find 的 -exec/-delete 等写操作禁止")
        return RunDecision(True, "只读命令")
    if name == "git":
        sub = argv[1] if len(argv) > 1 else ""
        if sub in READONLY_GIT:
            if any(str(x).startswith(("--open-files-in-pager",
                                      "--ext-diff", "--textconv"))
                   for x in argv[2:]):
                return RunDecision(False, "git 只读命令的危险选项禁止")
            return RunDecision(True, "git 只读")
        return RunDecision(False, "git 写操作需专用审批",
                           requires_approval=True, ask="git " + sub)
    if name in ASK:
        return RunDecision(False, "写/外发命令需人工授权",
                           requires_approval=True, ask=name + " ")
    if allow_unsafe:
        return RunDecision(True, "DWC_ALLOW_UNSAFE_RUN 显式开启",
                           requires_approval=True, ask="unsafe")
    return RunDecision(False, "命令不在 allowlist")


def safe_env() -> dict[str, str]:
    """只传运行必需变量；不把 API key/token 传给子进程。"""
    allow = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP",
             "HOME", "USERPROFILE", "PYTHONPATH", "PATHEXT")
    env = {k: os.environ[k] for k in allow if k in os.environ}
    # 子进程默认走 UTF-8，避免 Windows GBK 把工具输出打断
    env.setdefault("PYTHONIOENCODING", "utf-8")
    env.setdefault("PYTHONUTF8", "1")
    return env
