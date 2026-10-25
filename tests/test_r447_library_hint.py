# -*- coding: utf-8 -*-
"""R447 · 库复用：把同族 lesson 拼成起草提示（**只拼 lesson，不拼 code**）。

为什么只拼 lesson：Harness² 实测"直接继承上一轮实现"会掉分
（WB-code 73.4→63.2）。经验可以借鉴，实现不能继承。
"""
from __future__ import annotations

import json
import os

from dwc.organs import library as LB

CUE = "E_VALUE:wrong_magnitude:average"


def _lib(tmp_path, rows):
    p = os.path.join(str(tmp_path), "lib.jsonl")
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return p


def test_empty_library_gives_empty_hint(tmp_path):
    assert LB.hint_for(CUE, path=_lib(tmp_path, [])) == ""


def test_same_family_lesson_is_included(tmp_path):
    p = _lib(tmp_path, [{"cue": "E_VALUE:wrong_magnitude:fibonacci",
                         "lesson": "量级错时先看数量级再比数值",
                         "evidence": {"in_score": 1.0}, "ts": 1}])
    h = LB.hint_for(CUE, path=p)
    assert "量级错时先看数量级再比数值" in h
    assert h.startswith("\n[同族经验]")


def test_other_family_is_excluded(tmp_path):
    p = _lib(tmp_path, [{"cue": "E_VALUE:off_by_one:average",
                         "lesson": "别家经验", "evidence": {"in_score": 1.0}, "ts": 1}])
    assert LB.hint_for(CUE, path=p) == ""


def test_limit_caps_number_of_lines(tmp_path):
    rows = [{"cue": "E_VALUE:wrong_magnitude:f%d" % i,
             "lesson": "经验%d" % i, "evidence": {"in_score": 1.0}, "ts": 1}
            for i in range(5)]
    h = LB.hint_for(CUE, path=_lib(tmp_path, rows), limit=3)
    assert h.count("\n- ") == 3
    assert "经验2" in h and "经验3" not in h


def test_long_lesson_is_truncated(tmp_path):
    p = _lib(tmp_path, [{"cue": "E_VALUE:wrong_magnitude:x",
                         "lesson": "长" * 100, "evidence": {"in_score": 1.0}, "ts": 1}])
    h = LB.hint_for(CUE, path=p, max_chars=10)
    assert "长" * 10 in h and "长" * 11 not in h


def test_future_entries_are_excluded(tmp_path):
    """★ 防未来泄漏：now 之前的条目才算数。"""
    p = _lib(tmp_path, [{"cue": "E_VALUE:wrong_magnitude:x",
                         "lesson": "未来的经验", "evidence": {"in_score": 1.0},
                         "ts": 999}])
    assert LB.hint_for(CUE, path=p, now=100) == ""


def test_hint_never_carries_code(tmp_path):
    """★★ 核心纪律：经验可以借鉴，实现不能继承。"""
    p = _lib(tmp_path, [{"cue": "E_VALUE:wrong_magnitude:x",
                         "lesson": "看清量级", "code": "def secret(): return 42",
                         "evidence": {"in_score": 1.0}, "ts": 1}])
    h = LB.hint_for(CUE, path=p)
    assert "看清量级" in h
    assert "secret" not in h and "return 42" not in h
