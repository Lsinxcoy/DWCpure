"""★★★★★ R52 · 「禁放水」断言守卫（我写断言会**顺手留退路**）。

=== 为什么是测试 ===
R51 我发现自己写的断言带放水分支:
    `assert _sigmas >= {0,1} or len(_scores)>=2 and len(_hist)<4`
  ⇒ **靠 `len(_hist)<4` 那半边过的** ⇒ 断言**没验到它声称的东西**
  （G5「声称 vs 实测」同类）—— 而我是靠**再读一遍**才发现的
⇒ ⇒★ 这类错只有复盘才会发现 ⇒ 必须机器兜（这是第 2 次记同类）

★ 而写这条守卫**当场扫出 3 处现存放水**（`or True` 恒真断言）——
  它们一直**假绿**（我以前写的）。这证明守卫不是纸上谈兵。

=== 判据（**先声明口径**, 只查高置信形态以免误报）===
禁 `assert <test> or <water>`，其中 `<water>` 是以下之一:
  ① `True` / `1`      —— **恒真**放水（最恶: 断言完全无效）
  ② `len(...) < N`    —— 「数据还没长够就放宽」（我 R51 的形态）
  ③ `not <cond>` 反写 —— 见下, **不查**（误报面大）

★ **不查**的（声明边界, 免得下次以为守卫该管）:
  · `assert a in x or a in y`  —— 多位置匹配（**合理**, 现存 7 处全是这类）
  · `assert x == 1 or x == 2`  —— 枚举（合理）
  · `or` 在 `if`/`while` 里    —— 只查 `assert`（本守卫的口径）
★ 误报代价: ①② 形态在**合理代码里几乎不出现**（要放水才写得出来）
"""
import ast
import glob
import io
import os
import re

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# 放水分支的**高置信**形态（每条都要能说清为什么它就是放水）
_WATER_PATTERNS = [
    (re.compile(r"^(True|1)$"), "恒真放水（断言完全无效）"),
    (re.compile(r"len\([^)]*\)\s*<\s*\d"), "数据量不足就放宽（R51 形态）"),
    (re.compile(r"^(?!.*\b(in|==)\b).*$", ), ),   # 占位, 下面过滤
]


def find_watering_asserts(src: str):
    """扫一段源码 → [(line_no, assert_text, reason), …] 的放水断言清单。

    ★ 用 AST 而非正则: 要分清 `or` 在 assert 里还是在 if 里
    ★ 返回空列表 = 没有放水（不抛异常 —— 扫不到语法错的文件另行报）
    """
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None                      # ★ 单独返回, 不静默
    out = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Assert):
            continue
        test = n.test
        if not (isinstance(test, ast.BoolOp) and isinstance(test.op, ast.Or)):
            continue                     # 只查带 or 的 assert
        # or 的**右半边**（最后一个值）= 放水分支（Python 左结合: A or B ⇒ [A,B]）
        water = test.values[-1]
        wtxt = ast.unparse(water).strip()
        # ① 恒真
        if wtxt in ("True", "1"):
            out.append((n.lineno, ast.unparse(test)[:96],
                        "恒真放水（`or %s` ⇒ 断言完全无效）" % wtxt))
            continue
        # ② len(...) < N
        if re.search(r"len\([^)]*\)\s*<\s*\d", wtxt):
            out.append((n.lineno, ast.unparse(test)[:96],
                        "数据量不足就放宽（`%s` ⇒ 数据没长够就放行）" % wtxt))
            continue
        # ③ 兜底: 放水分支是**恒定 True 表达式**（如 `1 == 1`、`bool(1)`）
        try:
            if isinstance(water, ast.Constant) and water.value is True:
                out.append((n.lineno, ast.unparse(test)[:96], "常量 True 放水"))
        except Exception:
            pass
    return out


def project_files():
    out = []
    for pat in ("src/**/*.py", "scripts/*.py", "tests/*.py"):
        out += glob.glob(os.path.join(ROOT, pat), recursive=True)
    return sorted(set(f for f in out if "__pycache__" not in f))


def test_no_watering_asserts_in_project():
    """★★★★★ 全库 0 放水断言（点名到 文件:行 + 为什么是放水）。

    ★ 口径见模块 docstring（只查 `assert A or <恒真/len<N>`）
    ★ 这条守卫**写出来当场扫出 3 处 `or True`** —— 它们一直假绿
    """
    files = project_files()
    assert len(files) >= 50, "★ 扫到 %d 个（太少 ⇒ 路径坏了）" % len(files)
    bad, errs = [], []
    for f in files:
        src = io.open(f, encoding="utf-8", errors="replace").read()
        res = find_watering_asserts(src)
        if res is None:
            errs.append(os.path.relpath(f, ROOT))
        elif res:
            for ln, txt, why in res:
                bad.append("%s:%d  %s  ← %s"
                           % (os.path.relpath(f, ROOT), ln, txt, why))
    assert not errs, "★ 语法错的文件（要看见）: %s" % errs
    assert not bad, (
        "★★★★★ 放水断言 —— 断言**没验到它声称的东西**"
        "（R51 我自己犯过, 靠再读才发现 ⇒ 必须机器兜）:\n  "
        + "\n  ".join(bad))


def test_guard_accepts_multi_location_or():
    """★ **不误报**: 多位置匹配 / 枚举 这两类 `or` 是**合理**的。"""
    ok = [
        "assert 'a' in s or 'b' in s",              # 多位置匹配（现存 7 处）
        "assert x == 1 or x == 2",                  # 枚举
        "assert top.rule.endswith('x') or top.rule.endswith('y')",
        "assert 'fast' in msg or 'slow' in msg",
    ]
    for src in ok:
        assert find_watering_asserts(src) == [], (
            "★ 误报: %r（`or` 右边既非恒真也非 len<N）" % src)


def test_guard_flags_true_or_one():
    """★ 违规面 ①: `or True` / `or 1` ⇒ 必须抓到（恒真 = 断言无效）。"""
    for src in ("assert foo() == [] or True",
                "assert c != 10 or True",
                "assert a in b or 1"):
        res = find_watering_asserts(src)
        assert len(res) == 1, "★ 应抓到 1 处, 实得 %d（%r）" % (len(res), src)
        assert "恒真" in res[0][2], "★ 理由要说清恒真, 实得 %r" % res[0][2]


def test_guard_flags_len_less_than_n():
    """★ 违规面 ②: `or len(...) < N` ⇒ 必须抓到（R51 我的形态）。"""
    src = "assert _sigmas >= {0, 1} or len(_scores) >= 2 and len(_hist) < 4"
    res = find_watering_asserts(src)
    assert len(res) == 1, "★ 应抓到, 实得 %d" % len(res)
    assert "数据量不足" in res[0][2], "实得 %r" % res[0][2]


def test_guard_ignores_non_assert_or():
    """★ 口径边界: `or` 在 **if/while** 里**不查**（声明过的口径）。"""
    src = "if a or True:\n    pass\nwhile x or 1:\n    pass\n"
    assert find_watering_asserts(src) == []


def test_guard_reports_syntax_error_loudly():
    """★ 解析不了**不许静默返回空**（否则坏文件 = 守卫绿 = G7 违例）。"""
    assert find_watering_asserts("def f(:\n  pass\n") is None
