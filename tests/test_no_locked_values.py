"""★★★★★ R53 · 「锁值型断言」守卫 —— R52 那 3 处假绿的**起因**。

=== 为什么这条守在「起因」而不是「结果」 ===
R52 我扫出 3 处 `or True`，其中最重的一处是:
    `for k, v in m.RULES.items(): assert set(k.split(":")) == {…写死…}`
  ⇒ 断言**锁死了运行时可变数据的派生** ⇒ 种子一改就该红
  ⇒⇒ ★ 但红了之后人会怎么做？**改断言迁就代码 → 再加 `or True`**
  ⇒ 所以 `or True` 是**症状**（R52 管），这条管**病根**

=== 判据（**先声明口径** —— 两条, 都要求「≥3 项字面量」）===
  A. **循环依赖型**: 断言在 `for …` 循环体内, 且用到了**循环目标变量**
     ⇒ 语义: 在遍历**数据**时锁死数据的形状（数据一变就腐烂）
  B. **可变源型**: 断言比较 `== <≥3 项字面量>`, 且提到**运行时可变源**
     名字（见 `MUTABLE`）⇒ 语义: 锁死可变容器的键集/内容

★ 为什么要求 ≥3 项: 1-2 项多为**契约**（如 `== {'c','q','m'}` 是
  failure_signature 的设计三元组）⇒ 那种锁值**是对的**（见 `set<3` 3 处）
★ 为什么不查 `scalar ==`（351 处）/ `a == b`（83 处）: 误报面巨大
★ **不查 `STRUCTURAL`/`K_META`/`NEED_FILES` 这类设计常量** —— 它们就该固定

=== R53 实测（先扫后写, 不猜）===
  · `set>=3` 现状 9 处, 其中 **8 处是顶层锁设计契约**（合理, 不报）
  · 判据 A 命中 **1 处**（test_activity:284, 同类风险 ⇒ 已改结构断言）
  · 判据 B 命中 **0 处**（R52 原案已改 ⇒ B 是**防将来**的）
  · ★ 用 R52 原案反验: 判据 A **抓得到**（否则守卫是假的）
"""
import ast
import glob
import io
import os
import re

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

#: ★ **运行时可变**的容器名（B 判据用）
#:   ⚠ 这份清单是**我列的**（主观）—— 判据口径的一部分, 可推翻
#:   ★ 只放「运行时会变」的: 种子可被固化改写、候选池会增删、
#:     跨轮文件只增不删。**不放** STRUCTURAL/K_META（设计常量, 锁死才对）
MUTABLE = {
    "RULES", "LEARNED", "learned", "candidates", "pool", "rejected",
    "score_history", "known_signatures",
}

#: 字面量至少几项才算「锁清单」（1-2 项多为契约）
MIN_ITEMS = 3


def big_literal_eq(node) -> int:
    """找 `… == <≥3 项字面量>` → 返回项数; 找不到返回 0。"""
    for sub in ast.walk(node):
        if isinstance(sub, ast.Compare) and len(sub.ops) == 1 and \
                isinstance(sub.ops[0], ast.Eq) and len(sub.comparators) == 1:
            c = sub.comparators[0]
            if isinstance(c, (ast.Set, ast.List)) and \
                    len(c.elts) >= MIN_ITEMS:
                return len(c.elts)
            if isinstance(c, ast.Dict) and len(c.keys) >= MIN_ITEMS:
                return len(c.keys)
    return 0


def find_locked_value_asserts(src: str):
    """扫源码 → [dict(rule, line, text, why)] 的锁值断言清单。

    ★ 返回 None = 解析不了（**不静默** —— G7）
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    out = []

    def add(a, rule, why):
        out.append({"rule": rule, "line": a.lineno,
                    "text": ast.unparse(a.test)[:96], "why": why})

    for node in ast.walk(tree):
        # ── 判据 A: 循环体内 + 用到循环变量 ──
        if isinstance(node, ast.For):
            targets = {n.id for n in ast.walk(node.target)
                       if isinstance(n, ast.Name)}
            for st in node.body:
                for a in ast.walk(st):
                    if not isinstance(a, ast.Assert):
                        continue
                    if not big_literal_eq(a.test):
                        continue
                    used = {n.id for n in ast.walk(a.test)
                            if isinstance(n, ast.Name)}
                    if used & targets:
                        add(a, "A",
                            "循环内锁数据形状（用了循环变量 %s）"
                            % sorted(used & targets)[0])
        # ── 判据 B: 提到可变源名 ──
        if isinstance(node, ast.Assert):
            if not big_literal_eq(node.test):
                continue
            txt = ast.unparse(node.test)
            hit = [m for m in MUTABLE if re.search(r"\b%s\b" % m, txt)]
            if hit:
                add(node, "B", "锁**可变源** %s 的形状" % sorted(hit))
    # A/B 可能对同一断言各报一次（保留, 因为是两种理由）
    return out


def project_files():
    out = []
    for pat in ("src/**/*.py", "scripts/*.py", "tests/*.py"):
        out += glob.glob(os.path.join(ROOT, pat), recursive=True)
    return sorted(set(f for f in out if "__pycache__" not in f))


def test_no_locked_value_asserts_in_project():
    """★★★★★ 全库 0「锁可变数据形状」的断言（点名 + 规则 + 理由）。

    ★ ★ 判据 A/B 的口径见模块 docstring（≥3 项字面量 + 循环/可变源）
    ★ 这条守 R52 那 3 处的**病根**: 锁值 → 红 → 改断言迁就 → `or True`
    """
    files = project_files()
    assert len(files) >= 50, "★ 扫到 %d 个（太少 ⇒ 路径坏了）" % len(files)
    bad, errs = [], []
    for f in files:
        src = io.open(f, encoding="utf-8", errors="replace").read()
        res = find_locked_value_asserts(src)
        if res is None:
            errs.append(os.path.relpath(f, ROOT))
        else:
            for r in res:
                bad.append("%s:%d [%s] %s  ← %s"
                           % (os.path.relpath(f, ROOT), r["line"],
                              r["rule"], r["text"], r["why"]))
    assert not errs, "★ 语法错的文件（要看见）: %s" % errs
    assert not bad, (
        "★★★★★ 锁值型断言 —— 锁死**可变数据**的形状 ⇒ 数据一变就红 ⇒ "
        "接着就会有人加 `or True`（R52 那 3 处的病根）:\n  "
        + "\n  ".join(bad))


def test_catches_r52_original_case():
    """★★★★ 反验: 守卫必须抓到 **R52 原案**（否则它是假的）。

    ★ R52 原案（我写的, 一直假绿直到 R52）:
        for k, v in m.RULES.items():
            assert set(k.split(":")) == {…7 个写死值…}
    """
    src = '''
def case(m):
    for k, v in m.RULES.items():
        assert set(k.split(":")) == {"E_OFF_BY_ONE", "E_ZERO_DIV",
                                     "E_NO_BASE", "sum_first_n",
                                     "average", "factorial", "code_repair"}
'''
    res = find_locked_value_asserts(src)
    assert res and len(res) >= 1, "★★ 必须抓到 R52 原案, 实得 %s" % res
    assert any(r["rule"] == "A" for r in res), "★ 判据 A 该命中: %s" % res
    assert "循环" in res[0]["why"], "★ 理由要指出循环变量, 实得 %r" % res[0]["why"]


def test_catches_mutable_source_lock():
    """★ 判据 B: 锁**可变源**键集（即便不在 for 里）。"""
    src = 'assert set(RULES.keys()) == {"a", "b", "c", "d"}\n'
    res = find_locked_value_asserts(src)
    assert res and res[0]["rule"] == "B", "★ B 该命中, 实得 %s" % res
    assert "RULES" in res[0]["why"]


def test_allows_design_contract_locks():
    """★★ **不误报**: 顶层锁**设计常量**/契约是**对的**（R53 实测 8 处）。"""
    ok = [
        # 设计常量（STRUCTURAL 这类就该固定 —— 不在 MUTABLE 里）
        'assert STRUCTURAL == {"client_tool", "skill", "memory", "subagent"}',
        # 1-2 项的契约（failure_signature 三元组）
        "assert set(tr.failure_signature) == {'c', 'q', 'm'}",
        # 顶层（非循环）且不用可变源
        'assert set(v) == {"world_tree", "difficulty", "dials", "retention"}',
        # 非字面量比较（两边都是变量）
        "assert after == before",
        # 标量比较（351 处, 不查）
        "assert len(snap) == 2",
    ]
    for src in ok:
        assert find_locked_value_asserts(src) == [], \
            "★ 误报: %r" % src


def test_guard_reports_syntax_error_loudly():
    """★ 解析不了**不许静默返回空**（坏文件 = 守卫绿 = G7 违例）。"""
    assert find_locked_value_asserts("def f(:\n  pass\n") is None
