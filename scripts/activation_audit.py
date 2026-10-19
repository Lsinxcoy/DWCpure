# -*- coding: utf-8 -*-
"""activation_audit · 器官激活审计（Phase A · 2026-10-19）

DWC-AUTO 定位声明（静态审计工具，非器官）
  ★ 只做一件事: 从生产入口出发做 import 图可达性分析，
    回答"这个模块有没有活的调用链"，而不是"这个模块存不存在"。
  ★ 不判分、不写生产盘、不改任何代码 —— 输出只落 var/。

TRUTH_SOURCE: 真值 = 源码 AST 的 import 事实，本模块不生成任何 label。

为什么需要它（Phase A 的由来）:
  gate.py 的 K34 判据是 `if "def fitness_signal" not in _src` ——
  检查源码里有没有这行字，不检查有没有人调用它。
  于是"100% 测试通过"和"0% 生产接线"可以同时成立。
  本工具补的就是这个维度：可达性。

四态定义:
  PRODUCTION  从常驻 agent / 主循环可达（真生产链）
  SCRIPT      仅从工具脚本可达（批处理 / CLI，非常驻路径）
  TEST        仅被 tests/ 引用（单测绿 ≠ 生产接线）
  ORPHAN      无人引用

用法:
  python scripts/activation_audit.py            # 只打孤岛
  python scripts/activation_audit.py --all      # 打全表
  python scripts/activation_audit.py --json var/activation_audit.json
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import sys
from collections import deque
from typing import Dict, Iterable, List, Optional, Set, Tuple

# ── 根目录发现（本脚本在 scripts/ 下，上溯一级；DWC_ROOT 优先）──
_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.environ.get("DWC_ROOT") or os.path.dirname(_HERE)

SRC_DWC = os.path.join(ROOT, "src", "dwc")
TESTS_DIR = os.path.join(ROOT, "tests")
SCRIPTS_DIR = os.path.join(ROOT, "scripts")

# ── 生产入口：真正被常驻 agent / 主循环调用的入口 ──
PRODUCTION_ENTRIES = [
    "scripts/dwc_agent.py",              # 常驻 agent 本体
    "src/dwc/harness/run_term.py",       # 主循环
    "src/dwc/core.py",                   # 装配核心
]

# ── 工具链入口：可达但不算常驻生产链 ──
SCRIPT_ENTRIES = [
    "scripts/e2e_loop.py",
    "scripts/dwc_agent_patch.py",
    "scripts/dwc_benchmark_adapter.py",
    "scripts/dwc_benchmark_calibrate.py",
    "scripts/dwc_benchmark_longterm.py",
    "scripts/dwc_bench2.py",
    "scripts/dwc_nightbench.py",
    "scripts/real_llm_candidate.py",
    "scripts/dwc_bench.py",
]


# ══════════════════════════════════════════════════════════════════
# 1. 模块收集
# ══════════════════════════════════════════════════════════════════

def module_name_of_src(path: str) -> Optional[str]:
    """src/dwc/organs/hook.py -> dwc.organs.hook"""
    rel = os.path.relpath(path, os.path.join(ROOT, "src"))
    if not rel.endswith(".py") or rel.startswith(".."):
        return None
    parts = rel[:-3].replace(os.sep, ".").split(".")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def collect_modules() -> Dict[str, str]:
    out: Dict[str, str] = {}
    for dirpath, _dirnames, filenames in os.walk(SRC_DWC):
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            full = os.path.join(dirpath, fn)
            name = module_name_of_src(full)
            if name:
                out[name] = full
    return out


# ══════════════════════════════════════════════════════════════════
# 2. import 抽取（含相对导入解析）
# ══════════════════════════════════════════════════════════════════

def _parse(path: str) -> Optional[ast.AST]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return ast.parse(f.read(), filename=path)
    except (SyntaxError, UnicodeDecodeError, OSError):
        return None


def _resolve_relative(module: str, level: int, node_module: Optional[str]) -> Optional[str]:
    """解析相对导入的绝对前缀。

    module = dwc.harness.agent_harness, __package__ = dwc.harness
      level=1 -> dwc.harness
      level=2 -> dwc
    """
    if level <= 0:
        return node_module
    pkg_parts = module.split(".")[:-1]
    if level > 1:
        pkg_parts = pkg_parts[: -(level - 1)]
    base = ".".join(pkg_parts)
    if node_module:
        return (base + "." + node_module) if base else node_module
    return base or None


def extract_imports(path: str, module: str) -> Set[str]:
    """返回该文件 import 的全部 dwc.* 模块名（精确名，不做前缀展开）。"""
    tree = _parse(path)
    if tree is None:
        return set()
    found: Set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "dwc" or alias.name.startswith("dwc."):
                    found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            base = node.module or ""
            if node.level:
                resolved = _resolve_relative(module, node.level, node.module)
                if not resolved:
                    continue
                base = resolved
            if not (base == "dwc" or base.startswith("dwc.")):
                continue
            found.add(base)
            for alias in node.names:
                if alias.name == "*":
                    continue
                found.add(base + "." + alias.name)
    return found


# ══════════════════════════════════════════════════════════════════
# 3. 图构建与可达性
# ══════════════════════════════════════════════════════════════════

def build_graph(modules: Dict[str, str]) -> Dict[str, Set[str]]:
    return {name: extract_imports(path, name) for name, path in modules.items()}


def _parents(module: str) -> List[str]:
    parts = module.split(".")
    return [".".join(parts[:i]) for i in range(1, len(parts))]


def reachable_from(graph: Dict[str, Set[str]], roots: Iterable[str],
                   known: Set[str]) -> Set[str]:
    """BFS；精确匹配 + 隐式父包（import dwc.a.b 必然先 import dwc.a）。"""
    seen: Set[str] = set()
    q: deque = deque()

    def push(name: str) -> None:
        if name in known and name not in seen:
            seen.add(name)
            q.append(name)

    for r in roots:
        push(r)
        for p in _parents(r):
            push(p)

    while q:
        cur = q.popleft()
        for nxt in graph.get(cur, ()):
            push(nxt)
            for p in _parents(nxt):
                push(p)
    return seen


def scan_dir_refs(dirpath: str, modules: Dict[str, str]) -> Dict[str, Set[str]]:
    """扫描 tests/ 或 scripts/，返回 {被引用模块: {引用者文件名}}。精确匹配。"""
    refs: Dict[str, Set[str]] = {}
    if not os.path.isdir(dirpath):
        return refs
    for fn in sorted(os.listdir(dirpath)):
        if not fn.endswith(".py"):
            continue
        full = os.path.join(dirpath, fn)
        for imp in extract_imports(full, fn[:-3]):
            if imp in modules:
                refs.setdefault(imp, set()).add(fn)
    return refs


def roots_from_entries(paths: List[str], modules: Dict[str, str]) -> List[str]:
    """入口文件的根模块集合。

    src/ 下的入口直接映射成模块名；scripts/ 下的入口解析其 dwc import 作为根。
    """
    roots: List[str] = []
    for p in paths:
        full = os.path.join(ROOT, p.replace("/", os.sep))
        if not os.path.exists(full):
            continue
        name = module_name_of_src(full)
        if name:
            roots.append(name)
        else:
            roots.extend(sorted(imp for imp in extract_imports(full, os.path.basename(p)[:-3])
                                if imp in modules))
    return roots


# ══════════════════════════════════════════════════════════════════
# 4. 分类与报告
# ══════════════════════════════════════════════════════════════════

STATUS_ORDER = {"ORPHAN": 0, "TEST": 1, "SCRIPT": 2, "PRODUCTION": 3}


def classify(modules: Dict[str, str]) -> Tuple[Dict[str, dict], dict]:
    graph = build_graph(modules)
    known = set(modules)

    prod_roots = roots_from_entries(PRODUCTION_ENTRIES, modules)
    script_roots = roots_from_entries(SCRIPT_ENTRIES, modules)

    prod_reach = reachable_from(graph, prod_roots, known)
    script_reach = reachable_from(graph, script_roots, known) - prod_reach

    test_refs = scan_dir_refs(TESTS_DIR, modules)
    script_refs = scan_dir_refs(SCRIPTS_DIR, modules)

    # 直接 import 本模块的模块（反向边）
    imported_by: Dict[str, Set[str]] = {}
    for src, imps in graph.items():
        for imp in imps:
            if imp in known:
                imported_by.setdefault(imp, set()).add(src)

    rows: Dict[str, dict] = {}
    for name in sorted(known):
        if name in prod_reach:
            status = "PRODUCTION"
        elif name in script_reach or name in script_refs:
            status = "SCRIPT"
        elif name in test_refs:
            status = "TEST"
        else:
            status = "ORPHAN"

        consumers = set(imported_by.get(name, set()))
        consumers |= test_refs.get(name, set())
        consumers |= script_refs.get(name, set())

        rows[name] = {
            "module": name,
            "file": os.path.relpath(modules[name], ROOT).replace(os.sep, "/"),
            "status": status,
            "consumers": sorted(consumers)[:12],
            "consumer_count": len(consumers),
        }

    summary = {
        "root": ROOT.replace(os.sep, "/"),
        "module_count": len(known),
        "production": sum(1 for r in rows.values() if r["status"] == "PRODUCTION"),
        "script": sum(1 for r in rows.values() if r["status"] == "SCRIPT"),
        "test": sum(1 for r in rows.values() if r["status"] == "TEST"),
        "orphan": sum(1 for r in rows.values() if r["status"] == "ORPHAN"),
        "prod_roots": sorted(prod_roots),
        "script_roots": sorted(set(script_roots))[:20],
    }
    return rows, summary


def _print_all(rows: Dict[str, dict]) -> None:
    hdr = "%-40s %-11s %-6s %s" % ("MODULE", "STATUS", "CONS", "CONSUMERS")
    print(hdr)
    print("-" * len(hdr))
    for name, r in sorted(rows.items(),
                          key=lambda kv: (STATUS_ORDER[kv[1]["status"]], kv[0])):
        cons = ", ".join(r["consumers"][:3]) or "-"
        print("%-40s %-11s %-6d %s"
              % (name, r["status"], r["consumer_count"], cons))


def _print_islands(rows: Dict[str, dict]) -> None:
    print("=== 非生产链清单（不在常驻 agent 执行路径上）===")
    islands = [(n, r) for n, r in rows.items() if r["status"] != "PRODUCTION"]
    if not islands:
        print("（无）")
        return
    for n, r in sorted(islands, key=lambda kv: (STATUS_ORDER[kv[1]["status"]], kv[0])):
        print("  [%-6s] %-42s <- %s"
              % (r["status"], r["file"],
                 ", ".join(r["consumers"][:5]) or "(nobody)"))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="DWC 器官激活审计")
    ap.add_argument("--json", default=os.path.join(ROOT, "var", "activation_audit.json"))
    ap.add_argument("--all", action="store_true", help="打印全表（默认只打孤岛）")
    args = ap.parse_args(argv)

    modules = collect_modules()
    if not modules:
        print("ERROR: no modules found under %s" % SRC_DWC, file=sys.stderr)
        return 2

    rows, summary = classify(modules)

    print("=== DWC 激活审计 ===")
    print("root: %s" % summary["root"])
    print("modules: %d | PRODUCTION %d | SCRIPT %d | TEST %d | ORPHAN %d"
          % (summary["module_count"], summary["production"], summary["script"],
             summary["test"], summary["orphan"]))
    print("prod roots: %s" % ", ".join(summary["prod_roots"]))
    print("")
    if args.all:
        _print_all(rows)
        print("")
    _print_islands(rows)

    out_dir = os.path.dirname(args.json)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.json, "w", encoding="utf-8") as f:
        json.dump({"summary": summary, "modules": rows}, f,
                  ensure_ascii=False, indent=2)
    print("")
    print("json -> %s" % args.json.replace(os.sep, "/"))
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
