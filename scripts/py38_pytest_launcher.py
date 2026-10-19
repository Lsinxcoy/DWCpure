# -*- coding: utf-8 -*-
"""py38/通用 pytest 启动器: 把 repo src 加入 sys.path 后运行 pytest。"""
import sys
import os

repo = sys.argv[1]
src = os.path.join(repo, "src")
compat = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts", "ast_compat")
for p in (compat, src, repo):
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

# Python 3.9+ ast.alias 兼容
try:
    import ast
    _orig = ast.alias
    def _alias(name, asname=None, *, lineno=0, col_offset=0, **kw):
        return _orig(name, asname, lineno=lineno, col_offset=col_offset, **kw)
    ast.alias = _alias
except Exception:
    pass

import pytest
raise SystemExit(pytest.main(sys.argv[2:]))
