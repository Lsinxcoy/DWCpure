# -*- coding: utf-8 -*-
"""Python 3.9+ ast.alias 兼容垫片 (SWE-bench 旧 pytest)。

旧版 pytest 在 rewrite.py 中调用 ``ast.alias(name, asname)`` 不带 lineno/col_offset,
在 Python 3.9+ 上触发 "required field lineno missing from alias"。
此垫片在解释器启动时 (sitecustomize) 注入默认值, 使旧代码可跑。
"""
import ast

_orig = ast.alias


def _alias(name, asname=None, *, lineno=0, col_offset=0, **kw):
    return _orig(name, asname, lineno=lineno, col_offset=col_offset, **kw)


ast.alias = _alias
