# -*- coding: utf-8 -*-
"""R303-④ Project级上下文沉淀：同组近3任务留痕拼短hint，纯规则零LLM。"""
from dwc.llm.project_hint import project_hint, proj_id


def test_proj_id_group():
    assert proj_id("code_fix_007") == proj_id("code_fix_001") == "code_fix"
    assert proj_id("T_EXAM3") != proj_id("code_fix_007")


def test_same_group_hint():
    g = {"code_fix_001": ["run绕R5被拦", "revision只产read"], "code_fix_007": ["诚实收敛"]}
    h = project_hint("code_fix_009", g)
    assert "run绕R5被拦" in h and "诚实收敛" in h


def test_empty_group():
    assert project_hint("code_fix_009", {}) == ""


def test_truncate_400():
    g = {"code_fix_001": ["x" * 500]}
    h = project_hint("code_fix_002", g)
    assert len(h) <= 400
