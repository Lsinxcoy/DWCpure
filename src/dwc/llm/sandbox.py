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
from typing import Any


class SandboxError(Exception):
    """★ 沙箱拒绝（恶意代码大声炸，不静默跳过）。"""


#: ★ R审计-P1 · 资源上限（防 LLM 生成代码做资源耗尽攻击）:
#:   · for 循环总迭代上限 —— range 迭代数必须 ≤ 此值（AST 层 + 运行时兜底）
#:   · 字面量上限 —— 防 `[0]*10**9` / 超限常量（内存/CPU 耗尽）
_MAX_ITER = 1_000_000
_MAX_LITERAL = 1_000_000


def _eval_literal(node: ast.AST | None, limit: int):
    """安全评估字面量表达式 ⇒ (value, is_big)。

    - 节点是可评估的字面量结构（数值常量 ± 算术，无 Name/调用）⇒ 返回
      (真值, |真值| > limit)。求值**不执行代码**，纯 AST 递归。
    - 含变量/调用等不可评估 ⇒ (None, False)：放行（变量大小受 range
      守卫约束，`x*x` 这类乘法不拦）。
    - 求值中检测到超限 ⇒ 立即 (None, True)：拒绝（防 10**(10**9) 自爆）。
    """
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float)):
            v = abs(node.value)
            return (None, True) if v > limit else (node.value, False)
        return (None, False)  # 字符串/列表等字面量：可评估但不判大小
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub,
                                                               ast.UAdd)):
        val, big = _eval_literal(node.operand, limit)
        if big:
            return (None, True)
        if val is None:
            return (None, False)
        return (-val if isinstance(node.op, ast.USub) else val, False)
    if isinstance(node, ast.BinOp):
        lv, lb = _eval_literal(node.left, limit)
        if lb:
            return (None, True)
        rv, rb = _eval_literal(node.right, limit)
        if rb:
            return (None, True)
        if lv is None or rv is None:
            return (None, False)  # 含变量 ⇒ 结果规模不可静态定，放行
        try:
            if isinstance(node.op, ast.Add):
                v = lv + rv
            elif isinstance(node.op, ast.Sub):
                v = lv - rv
            elif isinstance(node.op, ast.Mult):
                v = lv * rv
            elif isinstance(node.op, ast.Div):
                v = lv / rv
            elif isinstance(node.op, ast.FloorDiv):
                v = lv // rv
            elif isinstance(node.op, ast.Mod):
                v = lv % rv
            elif isinstance(node.op, ast.Pow):
                v = lv ** rv
            else:
                return (None, False)
        except (OverflowError, ZeroDivisionError, ValueError):
            return (None, True)  # 求值异常 ⇒ 按大处理（拒）
        return (None, True) if abs(v) > limit else (v, False)
    return (None, False)  # Name/调用/容器展开等：不可评估


_BANNED_CALLS = frozenset({"open", "exec", "eval", "compile", "input",
                           "__import__"})


class _Guard(ast.NodeVisitor):
    """★ AST 门卫：恶意节点⇒SandboxError。"""

    def visit_Import(self, node):
        raise SandboxError("禁 import（沙箱禁网禁文件）")

    def visit_ImportFrom(self, node):
        raise SandboxError("禁 from-import（沙箱禁网禁文件）")

    def visit_While(self, node):
        raise SandboxError("禁 while（无限循环 AST 层拒）")

    def visit_For(self, node):
        """★ R审计-P1 · for 循环资源守卫：iter 必须是受限 range。"""
        it = node.iter
        if not (isinstance(it, ast.Call)
                and isinstance(it.func, ast.Name) and it.func.id == "range"):
            raise SandboxError("禁非 range 迭代（for 资源守卫）")
        if len(it.args) == 0 or len(it.args) > 3:
            raise SandboxError("range 参数数非法")
        stop = it.args[1] if len(it.args) >= 2 else it.args[0]
        _, big = _eval_literal(stop, _MAX_ITER)
        if big:
            raise SandboxError("range 上限超过 %d（for 资源守卫）" % _MAX_ITER)
        self.generic_visit(node)

    def visit_Assign(self, node):
        """★ R审计-P1 · 赋值超限常量 ⇒ 拒（堵 `x=10**9; [0]*x` 数据流洞）。"""
        _, big = _eval_literal(node.value, _MAX_LITERAL)
        if big:
            raise SandboxError("赋值超大字面量（资源守卫）")
        self.generic_visit(node)

    def visit_BinOp(self, node):
        """★ R审计-P1 · 乘法/幂尺度守卫：大常量参与 ⇒ 拒（防 [0]*10**9）。

        规则：任一侧**字面量求值超限** ⇒ 拒；含变量（如 x*x）⇒ 放行
        （变量由 range 运行时兜底约束）。
        """
        if isinstance(node.op, (ast.Mult, ast.Pow)):
            _, lb = _eval_literal(node.left, _MAX_LITERAL)
            _, rb = _eval_literal(node.right, _MAX_LITERAL)
            if lb or rb:
                raise SandboxError("乘法/幂含超大字面量（资源守卫）")
        self.generic_visit(node)

    def visit_Attribute(self, node):
        if node.attr.startswith("__"):
            raise SandboxError("禁双下划线属性（逃逸口不开）")
        self.generic_visit(node)

    def visit_Call(self, node):
        f = node.func
        name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", "")
        if name in _BANNED_CALLS:
            raise SandboxError("禁内建调用 %r（开口不开）" % (name,))
        self.generic_visit(node)


def _safe_range(*args: int) -> range:
    """★ R审计-P1 · 运行时 range 兜底：迭代数超上限 ⇒ OverflowError。

    静态 AST 守卫拦字面量 range；这是对**变量传入**的兜底
    （如 `n=999999999; range(n)`，静态无法判 n 的来源）。
    len(range) 是 O(1) 数学计算，安全。
    """
    r = range(*args)
    if len(r) > _MAX_ITER:
        raise OverflowError(
            "range 迭代数 %d 超上限 %d（沙箱资源守卫）" % (len(r), _MAX_ITER))
    return r


_SAFE_BUILTINS = {
    "sum": sum, "len": len, "range": _safe_range, "abs": abs, "min": min,
    "max": max, "round": round, "float": float, "int": int, "list": list,
    "dict": dict, "tuple": tuple, "set": set, "sorted": sorted,
    "enumerate": enumerate, "zip": zip, "map": map, "filter": filter,
    "any": any, "all": all, "pow": pow, "divmod": divmod,
    "isinstance": isinstance, "True": True, "False": False, "None": None,
}


def parse_guarded(code: str, filename: str = "<llm>") -> ast.Module:
    """解析并过 AST 门卫；恶意节点抛 SandboxError。"""
    tree = ast.parse(code, filename=filename)
    _Guard().visit(tree)
    return tree


def compile_guarded(code: str, filename: str = "<llm>"):
    """编译已过门卫的代码；不执行。"""
    return compile(parse_guarded(code, filename), filename, "exec")


def safe_globals() -> dict[str, Any]:
    """受限 builtins + 纯数学模块；不暴露 import/open/os。"""
    import math
    return {"__builtins__": dict(_SAFE_BUILTINS), "math": math}



def _run(code: str, skel: dict[str, list[list[Any]]],
          out: dict[str, Any]) -> None:
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
    env: dict[str, Any] = {"__builtins__": dict(_SAFE_BUILTINS)}
    try:
        exec(compile(tree, "<llm_code>", "exec"), env)  # noqa: S102
    except Exception as e:                              # noqa: BLE001
        out["error"] = "执行错：%r" % (e,)
        return
    obs: dict[str, list[list[Any]]] = {}
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
                      timeout: float = 5.0,
                      diag: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """LLM 代码→沙箱真跑→observed（与 judge.evaluate 同形态）。

    恶意⇒抛 SandboxError；缺函数/跑挂/超时⇒None（trial 侧判未评价）。

    ★ R438 · diag：把线程内的失败原因（语法错/执行错/函数跑挂）带出来。
      改前 out["error"] 写完就丢 ⇒ 调用方只能报"沙箱跑挂"，
      与"缺函数""超时"不可区分（违反"降级必须可区分"）。
    """
    out: dict[str, Any] = {}
    t = threading.Thread(target=_run, args=(code, skel, out), daemon=True)
    t.start()
    t.join(timeout)
    if t.is_alive():
        if diag is not None:
            diag["error"] = "超时 %.1fs" % (timeout,)
        return None  # ★ 超时⇒None（线程 daemon，随进程收尸）
    if diag is not None:
        diag.update(out)
    if out.get("sandbox_error"):
        raise SandboxError(out["sandbox_error"])
    return out.get("observed")
