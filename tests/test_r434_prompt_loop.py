# -*- coding: utf-8 -*-
"""R434 · 提示词闭环：钉版本 / 候选生成 / A-B 判定。

★★★ 为什么需要"钉版本"：
    A/B 归因要求**同一道题**在 stable 与 candidate 两个提示词下各跑一次。
    agent 是常驻进程，env 改不了；所以用 `var/prompt_force.json` 在
    调用时读（按 mtime_ns 失效）—— 改文件即生效，不用重启。

★★★ 为什么判定要保守：
    单轮单题 n=1，通过率本身有 ~7pp 抖动。提示词是全流量生效的，
    宁可漏掉真提升，也不能把退化版本推上生产 ⇒ **任何一单退化就 reject**。
"""
from __future__ import annotations

import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from dwc.llm import prompt_ota as OTA   # noqa: E402
import dwc_prompt_ab as AB        # noqa: E402
import dwc_prompt_candidate as C  # noqa: E402

MF = {"task_exec": {"stable": "v1", "candidate": None, "pct": 0}}


def _reset(monkeypatch, path):
    monkeypatch.setenv("DWC_PROMPT_FORCE_FILE", str(path))
    OTA._FORCE["mtime"] = None
    OTA._FORCE["map"] = {}


def test_force_file_pins_version(tmp_path, monkeypatch):
    """★★★ 钉版本文件在 ⇒ `_ver` 返回被钉的版本（不读 manifest 灰度）。"""
    f = tmp_path / "force.json"
    f.write_text(json.dumps({"task_exec": "v2"}), encoding="utf-8")
    _reset(monkeypatch, f)
    assert OTA._ver("task_exec", MF, "any-key") == "v2"


def test_no_force_file_falls_back_to_manifest(tmp_path, monkeypatch):
    """★★ 没有钉版本文件 ⇒ 走 manifest（stable）。"""
    _reset(monkeypatch, tmp_path / "nope.json")
    assert OTA._ver("task_exec", MF, "any-key") == "v1"


def test_malformed_force_is_ignored_not_crash(tmp_path, monkeypatch):
    """★★ 坏文件 ⇒ 当没钉（不抛错），并计数。"""
    f = tmp_path / "force.json"
    f.write_text("{not json", encoding="utf-8")
    _reset(monkeypatch, f)
    before = OTA.miss_count()
    assert OTA._ver("task_exec", MF, "k") == "v1"
    assert OTA.miss_count() > before


def test_force_change_takes_effect_without_restart(tmp_path, monkeypatch):
    """★★★ 改钉版本立刻生效（mtime_ns 失效），这是 A/B 能跑的前提。"""
    f = tmp_path / "force.json"
    f.write_text(json.dumps({"task_exec": "v2"}), encoding="utf-8")
    _reset(monkeypatch, f)
    assert OTA._ver("task_exec", MF, "k") == "v2"
    f.write_text(json.dumps({"task_exec": "v3"}), encoding="utf-8")
    assert OTA._ver("task_exec", MF, "k") == "v3"


def test_force_only_affects_named_prompt(tmp_path, monkeypatch):
    """★★ 钉了 task_exec 不影响 planner（否则 A/B 会污染别的面）。"""
    f = tmp_path / "force.json"
    f.write_text(json.dumps({"task_exec": "v2"}), encoding="utf-8")
    _reset(monkeypatch, f)
    mf = dict(MF, planner={"stable": "v1", "candidate": None, "pct": 0})
    assert OTA._ver("planner", mf, "k") == "v1"


# ── 候选生成 ────────────────────────────────────────────────────────

def test_candidate_appends_single_rule():
    """★★★ 候选 = 基线原文 + 一条硬规则（单变量，归因才干净）。"""
    base = "你是执行体。\n每轮输出一个 JSON。\n"
    out = C.build(base, ["问标识符必须先 search_code 取证。"])
    assert out.startswith(base.rstrip("\n"))
    assert "硬规则" in out
    assert "1. 问标识符必须先 search_code 取证。" in out


def test_candidate_multiple_rules_numbered():
    out = C.build("base\n", ["规则甲", "规则乙"])
    assert "1. 规则甲" in out and "2. 规则乙" in out


def test_candidate_requires_rule():
    try:
        C.build("base", [])
    except SystemExit as e:
        assert "至少给一条" in str(e)
    else:
        raise AssertionError("空规则应拒绝")


def test_next_ver_is_beyond_existing():
    """★★ 新版本号必须大于现有最大版本（禁覆盖历史版本）。"""
    v = C.next_ver("task_exec")
    assert v.startswith("v")
    assert int(v[1:]) >= 2          # 现有 v1 至少


# ── A/B 判定 ────────────────────────────────────────────────────────

def _p(tid, s, c):
    return {"id": tid, "stable_ok": s, "cand_ok": c}


def test_decide_promote_when_wins_and_no_loss():
    pairs = [_p("a", False, True), _p("b", False, True)] + \
            [_p("c%d" % i, True, True) for i in range(10)]
    v, w, l = AB.decide(pairs, min_tasks=10, min_wins=2)
    assert v == "promote" and len(w) == 2 and not l


def test_decide_rejects_on_any_regression():
    """★★★ 一单退化就 reject —— 提示词全流量生效，不容忍回归。"""
    pairs = [_p("a", True, False)] + \
            [_p("b", False, True), _p("c", False, True)] + \
            [_p("d%d" % i, True, True) for i in range(10)]
    v, w, l = AB.decide(pairs, min_tasks=10, min_wins=2)
    assert v == "reject" and len(l) == 1


def test_decide_keep_when_no_difference():
    pairs = [_p("t%d" % i, True, True) for i in range(12)]
    v, _, _ = AB.decide(pairs, min_tasks=10, min_wins=2)
    assert v == "keep"


def test_decide_insufficient_when_too_few():
    pairs = [_p("a", False, True)]
    v, _, _ = AB.decide(pairs, min_tasks=10, min_wins=2)
    assert v == "insufficient"


def test_decide_one_win_is_not_enough():
    pairs = [_p("a", False, True)] + [_p("b%d" % i, True, True) for i in range(11)]
    v, _, _ = AB.decide(pairs, min_tasks=10, min_wins=2)
    assert v == "keep"


def test_ab_script_removes_force_file():
    """★★ 钉版本文件是实验态：脚本源码里必须有 finally 删除。"""
    src = io.open(os.path.join(ROOT, "scripts", "dwc_prompt_ab.py"),
                  encoding="utf-8").read()
    assert "finally:" in src
    assert "set_force(a.name, None)" in src
