# -*- coding: utf-8 -*-
"""R448 · 上下文决策留痕（先把三元组变成可观测，再谈可进化）。

现在压缩是硬编码一条路：留最近 2 轮 + 更早的拼成摘要。
没有数据就不知道"换 selector 会不会更好" —— 所以先记，不改。
"""
from __future__ import annotations

import json

from dwc.llm import context_log as CL


def _rows(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def test_record_writes_all_triad_fields(tmp_path):
    p = str(tmp_path / "c.jsonl")
    CL.record(round=7, trigger="rounds", selector="all_older",
              reposition=False, n_kept=2, n_compressed=5,
              falsified=1, before_chars=900, after_chars=300, path=p)
    r = _rows(p)[0]
    assert (r["round"], r["trigger"], r["selector"]) == (7, "rounds", "all_older")
    assert r["reposition"] is False
    assert (r["n_kept"], r["n_compressed"], r["falsified"]) == (2, 5, 1)
    assert r["before_chars"] == 900 and r["after_chars"] == 300


def test_bad_path_does_not_raise(tmp_path):
    """旁路失败只留痕 —— 不许因为写日志把任务打断。"""
    CL.record(round=1, trigger="rounds", selector="x", reposition=False,
              n_kept=0, n_compressed=0, falsified=0,
              before_chars=0, after_chars=0,
              path=str(tmp_path / "no_such_dir" / "deep" / "c.jsonl"))


def test_default_path_follows_var_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DWC_VAR_DIR", str(tmp_path))
    CL.record(round=1, trigger="rounds", selector="x", reposition=False,
              n_kept=1, n_compressed=2, falsified=0,
              before_chars=10, after_chars=5)
    assert (tmp_path / "context_decisions.jsonl").exists()
