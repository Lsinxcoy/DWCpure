"""★★★★★ R48 · 「用了没引」静态守卫（AST）—— 同族错误已犯 **7 次**。

=== 为什么是测试而不是"每次修" ===
我犯的 7 次（全是同一形态: 用了一个模块却没 import）:
  1. applier 的 `_record_liquidity` 用 `io.open`（未 import io）
  2. e2e 出口自清洁用 `io.open`（未 import io）—— **R47 当场认了"没守卫"**
  3. e2e `_ev.LIQUIDITY_PATH`（e2e 没 import _ev）
  4. `LIQUIDITY_PATH` 用 `os.path` 而 `import os` 在 L652（引用先于定义）
  5-7. 若干 `import os` / `os.join` 手滑（同族变体）
⇒ ⇒★ **修完就忘 ⇒ 迟早再犯**（我自己在 R47 诚实边界里写了"没有守卫"）
  ⇒ 这条就是那个守卫: 纯静态 AST, 不跑代码, 违规即红

=== 判据（先声明口径）===
只查「**标准库模块名**被使用但未绑定」—— 白名单见 `MODS`。
★ 为什么限定标准库: 这类名字**不可能是局部变量**, 误报面最小;
  7 次错误全部落在该清单内（os/io/json/re/glob/subprocess/sys/ast…）
★ 绑定来源 = `import` / `import … as` / `from … import` / **赋值/参数/**
  循环目标/with as（凡 `Name(Store)`）—— 有定义就不算「没引」
★ 使用来源 = `Name(Load)` 且在 MODS 内（如 `os.path.join` 取 `os`）
"""
import ast
import glob
import io
import os

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

MODS = {
    "os", "io", "json", "re", "glob", "shutil", "subprocess", "sys",
    "ast", "time", "math", "textwrap", "itertools", "dataclasses",
    "pathlib", "collections", "typing", "functools", "hashlib", "random",
    "copy", "tempfile", "shlex", "struct", "csv", "datetime", "string",
}


def scan_source(src: str):
    """扫一段源码 → (违规列表, 用到的 MODS, 已绑定的 MODS)。

    ★ 违规 = 用到但未绑定（名字在 MODS 内且无任何定义）
    ★ SyntaxError 单独返回（不静默 —— 解析不了就该**看见**）
    """
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return None, [], [], "SyntaxError L%s: %s" % (e.lineno, e.msg)
    bound, used = set(), {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            for a in n.names:
                bound.add(a.asname or a.name.split(".")[0])
        elif isinstance(n, ast.ImportFrom):
            for a in n.names:
                if a.name != "*":
                    bound.add(a.asname or a.name)
        elif isinstance(n, ast.Name):
            if isinstance(n.ctx, ast.Store):
                bound.add(n.id)
            elif isinstance(n.ctx, ast.Load) and n.id in MODS:
                used.setdefault(n.id, n.lineno)
    bad = [(m, ln) for m, ln in sorted(used.items()) if m not in bound]
    return bad, sorted(used), sorted(bound & MODS), None


def project_files():
    """★ R48 教训: **`os.path.join(ROOT, "/src/...")` 会丢 ROOT**
    —— POSIX 规则: join 遇**前导 / 的绝对段**就丢掉前面的
    ⇒ `os.path.join("E:/X", "/src/a.py")` == `"/src/a.py"` ⇒ glob 扫到 0 个
    ★ 幸好 `len(files) >= 50` 那条断言**当场抓到**（否则守卫静默失效 =
      最坏的一种假绿: 一个什么都没查的门）
    ⇒ 修法: 用拼接（或去掉前导 /）。两种都留, 别再踩。
    """
    out = []
    for pat in ("src/**/*.py", "scripts/*.py", "tests/*.py"):
        out += glob.glob(os.path.join(ROOT, pat), recursive=True)
    return sorted(set(out))


def test_project_has_no_missing_imports():
    """★★★★★ 正向: 全库 0 违规（src + scripts + tests）。

    ★ 口径先声明: 只查 MODS 清单内的标准库名（那 7 次全在内）
    ★ 任何一处违规都**点名**到 文件:行 —— 不报"总数"了事
    """
    files = project_files()
    assert len(files) >= 50, "★ 扫到 %d 个文件（太少 ⇒ glob 路径坏了）" % len(files)
    violations, errors = [], []
    for f in files:
        src = io.open(f, encoding="utf-8", errors="replace").read()
        bad, _, _, err = scan_source(src)
        if err:
            errors.append("%s %s" % (os.path.relpath(f, ROOT), err))
        elif bad:
            violations.append("%s: %s" % (
                os.path.relpath(f, ROOT),
                ", ".join("%s@L%d" % (m, l) for m, l in bad)))
    assert not errors, "★★ 语法错误的文件（要看见, 不跳过）:\n  " + "\n  ".join(errors)
    assert not violations, (
        "★★★★★ 「用了没引」—— 同族错误第 8 次？（我已犯 7 次, 这就是那个守卫）\n  "
        + "\n  ".join(violations))


# ── 误报面（5 个边界, 每个都要"不红"）─────────────────────

def test_accepts_function_local_import():
    """函数内 import 也算绑定（我第 4 次「引用先于定义」的反面）。"""
    src = "def f():\n    import os\n    return os.path.join('a', 'b')\n"
    bad, used, bound, err = scan_source(src)
    assert err is None and bad == [], "★ 函数内 import 应算绑定, 实得 %s" % bad


def test_accepts_import_alias():
    """`import os as o` + `o.path` ⇒ 要认（别名绑定）。"""
    src = "import os as o\nx = o.path.join('a')\n"
    bad, used, bound, err = scan_source(src)
    assert err is None and bad == [], "★ 别名 import 应算绑定, 实得 %s" % bad
    # 反面: 别名绑定后, 用**原名**仍该报（否则守卫太松）
    src2 = "import os as o\nx = os.path.join('a')\n"
    bad2, _, _, err2 = scan_source(src2)
    assert bad2 == [("os", 2)], "★ 用原名而只 import 了别名 ⇒ 应报, 实得 %s" % bad2


def test_accepts_from_import():
    """`from x import y` ⇒ y 绑定（常见形态不许误报）。"""
    src = "from dwc.organs.evolver import os\nx = os.path.join('a')\n"
    bad, _, _, err = scan_source(src)
    assert err is None and bad == [], "★ from-import 应算绑定, 实得 %s" % bad


def test_accepts_local_shadow_assignment():
    """局部赋值也算定义（`os = None` 后用 ⇒ 不是「没引」是「重定义」）。"""
    src = "def f():\n    os = None\n    return os\n"
    bad, _, _, err = scan_source(src)
    assert err is None and bad == [], "★ 局部赋值应算定义, 实得 %s" % bad


def test_ignores_names_outside_mods_list():
    """★ MODS 之外的裸名**不查**（声明过的口径 —— 那些可能是局部变量）。"""
    src = "x = mything.attr\n"          # mything 不在 MODS
    bad, _, _, err = scan_source(src)
    assert err is None and bad == [], "★ MODS 外不许误报, 实得 %s" % bad


# ── 违规面（3 个, 每个都必须**红**）──────────────────────

def test_flags_bare_use_without_import():
    """★ 直接 `os.remove(...)` 而无 import ⇒ 报到行号。"""
    src = "def f(p):\n    os.remove(p)\n"        # ← 我犯过的形态
    bad, _, _, err = scan_source(src)
    assert err is None
    assert bad == [("os", 2)], "★ 应报 os@L2, 实得 %s" % bad


def test_flags_wrong_name_after_alias_import():
    """★ `import os as o` 却用 `os` ⇒ 报（别名不是万能遮罩）。"""
    src = "import os as o\nx = os.path.join('a')\n"
    bad, _, _, err = scan_source(src)
    assert bad == [("os", 2)], "实得 %s" % bad


def test_flags_every_missing_module_not_just_first():
    """★★ 多个都没引 ⇒ **逐个都报**（不只报第一个 —— 否则修一个漏一个）。"""
    src = "a = os.path.join('x')\nb = io.open('y')\nc = json.load(z)\n"
    bad, _, _, err = scan_source(src)
    got = [m for m, _ in bad]
    assert got == ["io", "json", "os"], "★ 三个都要报, 实得 %s" % got


def test_scan_source_reports_syntax_error_loudly():
    """★ 解析不了**不许静默**（否则文件坏了守卫还绿 = G7 违例）。"""
    bad, _, _, err = scan_source("def f(:\n  pass\n")
    assert err and "SyntaxError" in err
    assert bad is None
