# -*- coding: utf-8 -*-
"""R127 · M2 二期 LLM 臂对打 — ga_duel --executor llm。

验收:
  □ make_executor(mode="golden") 零破坏（R123 读数不变 — 协议留档）
  □ make_executor(mode="llm") ⇒ 产出 executor 真走 LLM（非 golden 替身）
  □ mode="llm" 的 executor 四失败模态 ⇒ NOT_EVALUATED（不当 0/False）
  □ GA 臂行走 LLM executor 时 dream 返回 v_by_version（不断链）
  □ caveats 动态化: llm 模式写"真抖动/无方差只报方向", golden 写结构必然
  □ 对打纪律不因臂换而松（预算硬上限/K 倍账/平局判 A 同款）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from dwc.organs.actor import Receipt  # noqa: E402

import ga_duel  # noqa: E402


def _anchors():
    import json
    return json.load(open(os.path.join(ROOT, "config", "anchors",
                                       "dev.json"), encoding="utf-8"))


class _FakeRes:
    def __init__(self, text="", error=None):
        self.text, self.error = text, error


class _FakeLLM:
    configured = True

    def __init__(self, text=""):
        self.text, self.calls = text, []

    def complete(self, prompt, system=""):
        self.calls.append(prompt)
        return _FakeRes(self.text)


def test_make_executor_golden_zero_break():
    """★ golden 替身原样: behavior 任务回 expected 灌满 ⇒ 恒等 1.0。"""
    anch = _anchors()
    exe = ga_duel.make_executor(anch)          # 默认 mode=golden
    beh = [t for t, r in anch.items()
           if not t.startswith("_")
           and r.get("verifier_kind") == "behavior"][0]
    rc = exe({"task_id": beh})
    assert isinstance(rc, Receipt) and rc.verified is True
    obs = rc.detail["observed"]
    # golden ⇒ observed 值 == coerce(expected)（结构必然恒等的来源;
    #   _coerce 把 '6'→6 是 judge 域形态 — 不是偏差）
    expects = [ga_duel._coerce(c["expected"])
               for c in anch[beh]["checks"] if "fn" in c]
    got = [v for pairs in obs.values() for _, v in pairs]
    assert got and got == expects


def test_make_executor_llm_mode_routes_to_factory(monkeypatch):
    """mode="llm" ⇒ 走 LLMExecutorFactory（真通道, 不是 golden 替身）。"""
    anch = _anchors()
    beh = [t for t, r in anch.items()
           if not t.startswith("_")
           and r.get("verifier_kind") == "behavior"][0]
    seen = {}

    class _Rec:
        def __init__(self, exe):
            self._exe = exe

        def __call__(self, task):
            seen["called"] = True
            return self._exe(task)

    fake = _FakeLLM(text="我不会 JSON")
    # ga_duel.make_executor 内 `from dwc.llm import LLMClient` — 函数内
    #   import 每次执行都从 **dwc.llm 包** 取属性 ⇒ 必须 patch 包属性,
    #   patch ga_duel 模块属性无效（这是 patch 目标的常见坑）
    import dwc.llm as _llm_pkg
    monkeypatch.setattr(_llm_pkg, "LLMClient", lambda *a, **k: fake)
    exe = ga_duel.make_executor(anch, mode="llm", memory=None)
    rc = exe({"task_id": beh})
    assert seen.get("called") is True or fake.calls      # 真打过 LLM
    # fake 回"我不会 JSON" ⇒ 解析失败 ⇒ NOT_EVALUATED（不当 0/False）
    assert "observed" not in rc.detail
    assert rc.detail.get("error_code") == "llm_parse_failed"


def test_make_executor_llm_good_reply_gives_observed():
    """LLM 好回复 ⇒ observed 进入 detail（真执行通道通）。"""
    anch = _anchors()
    beh = [t for t, r in anch.items()
           if not t.startswith("_")
           and r.get("verifier_kind") == "behavior"][0]
    skel = {}                       # 从 script 的 LLMExecutorFactory 复刻 skeleton
    from dwc.llm.executor import obs_skeleton
    skel = obs_skeleton(anch, beh)
    fn0 = sorted(skel)[0]
    import json
    good = "```json\n%s\n```" % json.dumps({fn0: skel[fn0]})
    fake = _FakeLLM(text=good)
    import pytest as _p

    import dwc.llm as _llm_pkg
    _orig = _llm_pkg.LLMClient
    _llm_pkg.LLMClient = lambda *a, **k: fake
    try:
        exe = ga_duel.make_executor(anch, mode="llm", memory=None)
        rc = exe({"task_id": beh})
    finally:
        _llm_pkg.LLMClient = _orig
    assert "observed" in rc.detail and fn0 in rc.detail["observed"]


def test_ga_duel_golden_regression_doc_unchanged():
    """★ 协议留档: docs/ga_duel.json（R123 golden 跑）恒在且 verdict 判 A。"""
    import json
    p = os.path.join(ROOT, "docs", "ga_duel.json")
    if not os.path.exists(p):
        pytest.skip("golden 留档未生成（本机先跑过 --executor golden 才有）")
    d = json.load(open(p, encoding="utf-8"))
    assert d["verdict"]["winner"] == "single"        # tie→incumbent
    assert d["discipline"]["single_within"] is True
    assert d["discipline"]["ga_within"] is True
    assert d["budget"]["k_ratio_ga_over_single"] == 2.0


def test_cli_has_executor_switch():
    """CLI 暴露 --executor {golden,llm}（默认 golden = 不换默认行为）。"""
    import inspect
    src = inspect.getsource(ga_duel.main)
    assert '"--executor"' in src
    assert 'default="golden"' in src
    assert 'mode=args.executor' in src
