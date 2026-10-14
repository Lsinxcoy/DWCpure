# -*- coding: utf-8 -*-
"""R263b · 降级哨兵锁 — "dwc 无法唤醒"根因回归（2026-10-14 用户实测）。

根因链（三重）:
  ① `.dwc\\.venv` 缺 textual（hermes venv 有 8.2.8 — 双环境漂移）;
  ② `class DwcApp(App)` 在**模块级**无条件执行 → import 失败时 NameError
     **先于** `main()` 的 `if not _TUI_OK` 回退逻辑 — 降级设计有但短路;
  ③ 用户链 A（.local\\bin\\dwc.cmd → .dwc venv）走到该副本直接崩 rc=1。

锁: import textual 失败时模块级加载必须**不炸**（哨兵 App=object 生效,
main() 回退路径可达）— 不锁 textual 存在性（环境漂移靠本锁兜底）。
"""
import io
import os
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
TUI = os.path.join(ROOT, "scripts", "dwc_tui.py")


def test_tui_module_loads_without_textual():
    """★ 行为锁: 屏蔽 textual 后模块级加载不 NameError（哨兵生效）。"""
    code = (
        "import sys, runpy\n"
        "sys.modules['textual'] = None   # 屏蔽 → ImportError 模拟缺依赖\n"
        "mod = runpy.run_path(%r, run_name='dwc_tui_probe')\n"
        "assert mod['_TUI_OK'] is False, mod.get('_TUI_ERR')\n"
        "assert mod['App'].__name__ == '_Any', mod['App']  # 哨兵已置\n"
        "assert mod['Binding']('k','fn').__class__.__name__ == '_Any'  # 可调用\n"
        "print('SENTINEL_OK')\n" % TUI
    )
    r = subprocess.run([sys.executable, "-c", code],
                       capture_output=True, text=True, timeout=60,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    assert r.returncode == 0 and "SENTINEL_OK" in out, out[-600:]


def test_tui_sentinel_in_source():
    """★ 源锁: 哨兵赋值在 except 块内（与 _TUI_ERR 同级）— 改缩进/挪位即红。"""
    src = io.open(TUI, encoding="utf-8").read()
    i_exc = src.find("except Exception as _e:")
    i_sent = src.find("for _n in (")
    i_class = src.find("class DwcApp(App):")
    assert 0 < i_exc < i_sent < i_class, (i_exc, i_sent, i_class)
    # 哨兵段在 except 块内（4 空格起）
    line = src[src.rfind("\n", 0, i_sent) + 1:src.find("\n", i_sent)]
    assert line.startswith("    for _n in ("), repr(line)


def test_sentinel_covers_all_textual_imports():
    """★ 源锁: 哨兵名字集 == try 块 textual 导入名集（加新 import 漏补即红）。"""
    import re
    src = io.open(TUI, encoding="utf-8").read()
    i_try = src.find("try:")
    i_exc = src.find("except Exception as _e:")
    imported = []
    for m in re.finditer(r"from textual[\w.]* import (.+)",
                         src[i_try:i_exc]):
        for n in m.group(1).split(","):
            n = n.strip().split(" as ")[-1].strip()
            if n:
                imported.append(n)
    i_loop = src.find('for _n in (')
    i_end = src.find("):", i_loop)
    sentinel = re.findall(r'"(\w+)"', src[i_loop:i_end])
    assert sorted(imported) == sorted(sentinel), (imported, sentinel)
