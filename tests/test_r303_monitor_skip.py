# -*- coding: utf-8 -*-
"""R303-② monitor-mode省token：无变化跳过LLM，纯规则零调用。"""
from dwc.llm.monitor import monitor_skip


def test_all_calm_skip():
    why = monitor_skip(has_new_input=False, last_done_ok=True, skips=0)
    assert isinstance(why, str) and why


def test_new_input_no_skip():
    assert monitor_skip(has_new_input=True, last_done_ok=True, skips=0) is None


def test_last_fail_no_skip():
    assert monitor_skip(has_new_input=False, last_done_ok=False, skips=0) is None


def test_two_skips_force_run():
    assert monitor_skip(has_new_input=False, last_done_ok=True, skips=2) is None
