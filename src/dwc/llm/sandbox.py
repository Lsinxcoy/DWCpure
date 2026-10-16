# -*- coding: utf-8 -*-
"""R295-Task1 · 沙箱：LLM 代码→真跑出 observed（code_repair 写码真执行）。

★★★ 定位（DWC-AUTO）：自我强化执行通道 —— code_repair 试跑的真执行器。
★ 安全模型（AST 层全拒，不靠事后超时碰运气）：
  禁 Import/ImportFrom（禁 import 全系）／禁 open/exec/eval/compile 调用／
  禁双下划线属性（逃逸口）／禁 while（无限循环）。
★ 执行：受限 builtins（纯函数子集）＋5s 线程超时兜底。
★ 失败语义：恶意⇒抛 SandboxError（大声）；缺函数/跑挂⇒None（trial 未评价）。
"""
from __future__ import annotations

import ast
import threading
from typing import Any, Dict, List, Optional


class SandboxError(Exception):
    """★ 沙箱拒绝（恶意代码大声炸，不静默跳过）。"""


_BANNED_CALLS = frozenset({"open", "exec", "eval", "compile", "input",
                           "__import__"})


class _Guard(ast.NodeVisitor):
    """★ AST 门卫：恶意节点⇒SandboxError。"""

    def visit_Import(self, node):  # noqa: N802
        raise SandboxError("禁 import（沙箱禁网禁文件）")

    def visit_ImportFrom(self, node):  # noqa: N802
        raise SandboxError("禁 from-import（沙箱禁网禁文件）")

    def visit_While(self, node):  # noqa: N802
        raise SandboxError("禁 while（无限循环 AST 层拒）")

    def visit_Attribute(self, node):  # noqa: N802
        if "dunder" in ("dunder",) and node.attr.startswith("__"):
            raise SandboxError("禁双下划线属性（逃逸口不开）")
        self.generic_visit(node)

    def visit_Call(self, node):  # noqa: N802
        f = node.func
        name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")
        if name in _BANNED_CALLS:
            raise SandboxError("禁内建调用 %r（开口不开）" % (name,))
        self.generic_visit(node)


_SAFE_BUILTINS = {
    "sum": sum, "len": len, "range": range, "abs": abs, "min": min,
    "max": max, "round": round, "float": float, "int": int, "list": list,
    "dict": dict, "tuple": tuple, "set": set, "sorted": sorted,
    "enumerate": enumerate, "zip": zip, "map": map, "filter": filter,
    "any": any, "all": all, "pow": pow, "divmod": divmod,
    "isinstance": isinstance, "True": True, "False": False, "None": None,
}


def _run(code: str, skel: Dict[str, List[List[Any]]],
          out: Dict[str, Any]) -> None:
    """★ 线程内真跑（超时靠外层 join）。"""
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        out["error"] = "语法错：%s" % (e,)
        return
    try:
        _Guard().visit(tree)
    except SandboxError as e:
        out["sandbox_error"] = str(e)
        return
    env: Dict[str, Any] = {"__builtins__": dict(_SAFE_BUILTINS)}
    try:
        exec(compile(tree, "<llm_code>", "exec"), env)  # noqa: S102
    except Exception as e:                              # noqa: BLE001
        out["error"] = "执行错：%r" % (e,)
        return
    obs: Dict[str, List[List[Any]]] = {}
    for fn, pairs in skel.items():
        if fn not in env or not callable(env[fn]):
            return  # ★ 缺函数⇒整体 None（调用方判未评价）
        try:
            obs[fn] = [[args, env[fn](args)] for args, _ in pairs]
        except Exception as e:                          # noqa: BLE001
            out["error"] = "函数 %s 跑挂：%r" % (fn, e)
            return
    out["observed"] = obs


def run_code_observed(code: str, skel: Dict[str, List[List[Any]]],
                      timeout: float = 5.0) -> Optional[Dict[str, Any]]:
    """LLM 代码→沙箱真跑→observed（与 judge.evaluate 同形态）。

    恶意⇒抛 SandboxError；缺函数/跑挂/超时⇒None（trial 侧判未评价）。
    """
    out: Dict[str, Any] = {}
    t = threading.Thread(target=_run, args=(code, skel, out), daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        return None  # ★ 超时⇒None（线程 daemon，随进程收尸）
    if out.get("sandbox_error"):
        raise SandboxError(out["sandbox_error"])
    return out.get("observed")
