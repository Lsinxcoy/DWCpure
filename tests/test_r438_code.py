# -*- coding: utf-8 -*-
"""R438 · code 维度：学到并通过试跑的实现随规则落盘、下次直接复用。

★ 改前：`p.code` 只在试跑时用一次，试跑完就丢 ⇒ 同一签名再次出现时
  又从零起草（学到的东西没有留下来）。

锁：
1. `_land_adopted` 把 `p.code` 写进规则条目。
2. `persist_learned` 落盘后，**新进程**加载回来仍有 code。
3. `Mutator().propose(sig)` 返回的 Proposal 带上 code（= 复用入口）。
4. 没有 code 的规则 ⇒ Proposal.code 为 None（不伪造）。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.evolver import Evolver, Mutator, Proposal   # noqa: E402


def _mk(code, fn="fibonacci"):
    p = Proposal(proposal_id="P_r438_code",
                 failure_signature={"c": "E_VALUE", "q": "wrong_magnitude",
                                    "m": "m", "fn": fn},
                 component="code", target=fn, patch="按项累加",
                 code=code, rationale="r", dimension="D2",
                 target_layer="assets")
    p.state = "adopted_not_implemented"
    return p


def test_landed_code_persists_and_reproposes(tmp_path, monkeypatch):
    rules = tmp_path / "rules.json"
    monkeypatch.setattr(Mutator, "LEARNED_PATH", str(rules))
    monkeypatch.setattr(Mutator, "SEED_KEYS", frozenset())
    _snap = dict(Mutator.RULES)
    try:
        out = Evolver()._land_adopted(_mk("def fibonacci(n):\n    return n"))
        assert out["outcome"] == "landed", out
        data = json.loads(rules.read_text(encoding="utf-8"))
        # ★ SEED_KEYS 清空后 learned 里也有种子 ⇒ 必须按键取，不能取第一个
        entry = data["learned"]["E_VALUE:wrong_magnitude:fibonacci"]
        assert entry["code"].startswith("def fibonacci")

        # ★ 模拟新进程：清空内存 → 从盘加载
        Mutator.RULES.clear()
        Mutator._loaded = False
        Mutator.ensure_loaded()
        got = Mutator().propose({"c": "E_VALUE", "q": "wrong_magnitude",
                               "fn": "fibonacci"})
        assert got is not None
        assert got.code == "def fibonacci(n):\n    return n"
    finally:
        Mutator.RULES.clear()
        Mutator.RULES.update(_snap)
        Mutator._loaded = True


def test_rule_without_code_gives_none(tmp_path, monkeypatch):
    rules = tmp_path / "rules.json"
    monkeypatch.setattr(Mutator, "LEARNED_PATH", str(rules))
    monkeypatch.setattr(Mutator, "SEED_KEYS", frozenset())
    _snap = dict(Mutator.RULES)
    try:
        Evolver()._land_adopted(_mk(None, fn="fib2"))
        Mutator.RULES.clear()
        Mutator._loaded = False
        Mutator.ensure_loaded()
        got = Mutator().propose({"c": "E_VALUE", "q": "wrong_magnitude",
                               "fn": "fib2"})
        assert got is not None and got.code is None
    finally:
        Mutator.RULES.clear()
        Mutator.RULES.update(_snap)
        Mutator._loaded = True
