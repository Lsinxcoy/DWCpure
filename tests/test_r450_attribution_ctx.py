# -*- coding: utf-8 -*-
"""R450 · 归因上下文：把"这次调用属于谁"做成 with 块，进出必还原。

为什么需要：生产里真正调 LLM 的不是 agent（它默认 --llm 关），
而是进化轮的起草。归因必须加在**调用发生的地方**，
并且不能因为异常把线程标签漏给下一个任务。
"""
from __future__ import annotations

import pytest

from dwc.llm import cost as C


def test_sets_inside_and_restores_outside():
    C.set_tag("prev")
    C.set_profile("lite")
    try:
        with C.attribution(tag="t1", profile="deep"):
            assert C.current_tag() == "t1"
            assert C.current_profile() == "deep"
        assert C.current_tag() == "prev"
        assert C.current_profile() == "lite"
    finally:
        C.clear_tag()
        C.clear_profile()


def test_restores_even_on_exception():
    C.set_tag("prev")
    try:
        with pytest.raises(RuntimeError):
            with C.attribution(tag="t2", profile="compact"):
                raise RuntimeError("boom")
        assert C.current_tag() == "prev"
        assert C.current_profile() == ""
    finally:
        C.clear_tag()


def test_none_keeps_previous_value():
    C.set_tag("keep")
    try:
        with C.attribution(tag=None, profile="lean"):
            assert C.current_tag() == "keep"
            assert C.current_profile() == "lean"
    finally:
        C.clear_tag()
        C.clear_profile()
