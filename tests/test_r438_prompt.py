# -*- coding: utf-8 -*-
"""R438 · prompt 维度：候选→A/B→晋升的**驱动层**。

★ 锁的是"有人开车"：
  改前 candidate/ab/manifest 三件套都在，但没有东西把它们串起来
  ⇒ 提示词永远停在 v1。

锁：
1. 没有已学规则 ⇒ skipped（不生成空候选去烧 A/B）。
2. 候选生成成功 ⇒ 解析出版本号并进入 A/B。
3. verdict=promote ⇒ promoted=True（并把 --promote 传给 ab）。
4. verdict=reject ⇒ promoted=False（stable 不动）。
5. 候选脚本失败 ⇒ candidate_failed，不进入 A/B。
6. 每种结果都落台账。
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_prompt_evolve as PE   # noqa: E402


class R:
    def __init__(self, rc=0, out=b"", err=b""):
        self.returncode, self.stdout, self.stderr = rc, out, err


def test_rules_from_learned(tmp_path):
    p = tmp_path / "rules.json"
    p.write_text(json.dumps({"learned": {
        "K1": {"component": "control_flow", "patch": "先取证再回答"},
        "K2": {"component": "prompt", "patch": "只输出一个 JSON 对象"},
        "K3": {"component": "code", "patch": "别猜"},
    }}, ensure_ascii=False), encoding="utf-8")
    got = PE.rules_from_learned(str(p), max_rules=2)
    assert len(got) == 2
    assert "只输出一个 JSON 对象" in got       # prompt 优先
    assert "先取证再回答" in got               # control_flow 次之


def test_missing_rules_file_is_empty(tmp_path):
    assert PE.rules_from_learned(str(tmp_path / "nope.json")) == []


def test_no_rules_skips(tmp_path):
    led = tmp_path / "ledger.jsonl"
    rep = PE.evolve(rules=[], ledger=str(led))
    assert rep["outcome"] == "skipped"
    assert json.loads(led.read_text(encoding="utf-8").splitlines()[-1])["outcome"] == "skipped"


def test_promote_path(tmp_path):
    led = tmp_path / "ledger.jsonl"
    out = tmp_path / "var"
    out.mkdir()
    seen = []

    def runner(cmd, timeout):
        seen.append(cmd)
        if "--candidate" not in cmd:
            return R(0, "已生成 prompts/task_exec.v2.md（x）".encode("utf-8"))
        (out / "prompt_ab_task_exec_v2_20261023_120000.json").write_text(
            json.dumps({"verdict": "promote", "wins": ["a", "b"],
                        "losses": []}), encoding="utf-8")
        return R(0, b"ok")

    rep = PE.evolve(rules=["r1"], runner=runner, out_dir=str(out),
                    ledger=str(led))
    assert rep["candidate"] == "v2"
    assert rep["verdict"] == "promote" and rep["promoted"] is True
    assert rep["outcome"] == "promoted"
    assert any("--promote" in c for c in seen)
    assert json.loads(led.read_text(encoding="utf-8").splitlines()[-1])["promoted"] is True


def test_reject_keeps_stable(tmp_path):
    out = tmp_path / "var"
    out.mkdir()

    def runner(cmd, timeout):
        if "--candidate" not in cmd:
            return R(0, b"prompts/task_exec.v3.md")
        (out / "prompt_ab_task_exec_v3_x.json").write_text(
            json.dumps({"verdict": "reject", "wins": [], "losses": ["a"]}),
            encoding="utf-8")
        return R(0, b"ok")

    rep = PE.evolve(rules=["r1"], runner=runner, out_dir=str(out),
                    ledger=str(tmp_path / "l.jsonl"))
    assert rep["verdict"] == "reject" and rep["promoted"] is False
    assert rep["outcome"] == "kept_stable"


def test_candidate_failure_stops(tmp_path):
    def runner(cmd, timeout):
        return R(1, b"", "拒绝覆盖已存在版本".encode("utf-8"))

    rep = PE.evolve(rules=["r1"], runner=runner,
                    ledger=str(tmp_path / "l.jsonl"))
    assert rep["outcome"] == "candidate_failed"
    assert rep["candidate"] == ""


def test_dry_run_does_not_execute(tmp_path):
    seen = []
    rep = PE.evolve(rules=["r1"], dry_run=True,
                    runner=lambda c, t: seen.append(c) or R(0, b""),
                    ledger=str(tmp_path / "l.jsonl"))
    assert rep["outcome"] == "dry_run" and not seen
