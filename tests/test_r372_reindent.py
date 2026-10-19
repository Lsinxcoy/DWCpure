# -*- coding: utf-8 -*-
"""R372 · 缩进对齐的行为锁（Phase C2）。

Phase C 分级基准实测：5103 / 5221 的失败级是 `syntax_ok=False`，
根因是 new_string 的基准缩进与 old_string 不一致 ⇒ IndentationError。
本测试锁住"替换时自动对齐缩进"这条修复。
"""
import importlib.util
import os
import textwrap

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)

_SPEC = importlib.util.spec_from_file_location(
    "dwc_fuzzy_match_mod",
    os.path.join(_ROOT, "scripts", "dwc_fuzzy_match.py"),
)
F = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(F)


def test_reindent_adds_missing_indent():
    actual = "        if x:\n            return 1\n"
    new = "if x:\n    return 2\n"
    out = F.reindent_to_match(actual, new)
    assert out == "        if x:\n            return 2"


def test_reindent_removes_extra_indent():
    actual = "    if x:\n        return 1\n"
    new = "        if x:\n            return 2\n"
    out = F.reindent_to_match(actual, new)
    assert out == "    if x:\n        return 2"


def test_reindent_noop_when_same():
    actual = "    a = 1\n"
    new = "    a = 2\n"
    assert F.reindent_to_match(actual, new) == new


def test_reindent_preserves_blank_lines():
    actual = "    a = 1\n"
    new = "a = 2\n\nb = 3\n"
    out = F.reindent_to_match(actual, new)
    assert out == "    a = 2\n\n    b = 3"


def test_apply_replacement_fixes_indentation_end_to_end():
    content = textwrap.dedent("""\
        def f():
            if True:
                return 1
    """)
    old = "        return 1"          # LLM 抄成了 8 空格
    new = "    return 2"              # LLM 只给了 4 空格
    out, msg = F.apply_replacement(content, old, new)
    assert msg == "ok"
    # 实际块缩进是 8 空格，替换后必须仍是 8 空格，否则 IndentationError
    assert "\n        return 2\n" in out
    compile(out, "<t>", "exec")       # 语法必须过


def test_apply_replacement_still_fails_on_missing_old():
    out, msg = F.apply_replacement("a = 1\n", "zzz", "b = 2\n")
    assert out is None
    assert "未找到" in msg


def test_inline_fragment_is_rejected():
    """行内片段会污染后半行 ⇒ 必须在落地前拒绝（Phase C 实测根因）。"""
    content = "for name, new in enumerate(field):\n    pass\n"
    out, msg = F.apply_replacement(content, "for name, new in",
                                   "setattr(node, name, new)")
    assert out is None
    assert "整行对齐" in msg


def test_whole_line_block_still_applies():
    content = "for name, new in enumerate(field):\n    pass\n"
    out, msg = F.apply_replacement(
        content, "for name, new in enumerate(field):\n    pass",
        "setattr(node, name, new)")
    assert msg == "ok"
    assert out == "setattr(node, name, new)\n"
    compile(out, "<t>", "exec")
