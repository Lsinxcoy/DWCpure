# -*- coding: utf-8 -*-
"""R438 · 落地闭环：配置开关 / 配额 / 备份 / 回滚。

★ 锁的是"进化真的能改变行为"这条链的**最后一米**：
  改前 `apply=False` 硬编码 + `ensure_loaded()` 零调用 + rules.json 不存在
  ⇒ 试跑再漂亮也不落盘，落了也没人读。

锁：
1. `evolution.yaml` 的 `auto_apply` / `auto_apply_max_per_round` 必填无默认。
2. `run_round(apply=True, max_land=1)` 只落 1 条，其余标 quota_exceeded。
3. `_land_adopted` 落地后必须有备份文件。
4. `_rollback_key` 删单键 + 原子写 + 先备份，不碰别的键。
"""
import importlib.util
import json
import os
import sqlite3
import sys
import types

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _cron():
    return _load(os.path.join(ROOT, "scripts", "dwc_evo_round_cron.py"),
                 "cron_r438_test")


def _evo():
    return _load(os.path.join(ROOT, "scripts", "dwc_evo_round.py"),
                 "evo_r438_test")


# ── 1. 配置必填 ────────────────────────────────────────────

def test_auto_apply_is_required(tmp_path):
    from dwc.foundation.dial_config import load_evolution, DialError
    p = tmp_path / "evo.yaml"
    p.write_text("version: 1\nevolution:\n  feed_from_terms: true\n"
                 "  max_sigs_per_term: 50\n", encoding="utf-8")
    try:
        load_evolution(str(p))
    except DialError as exc:
        assert "auto_apply" in str(exc)
    else:
        raise AssertionError("缺 auto_apply 必须报错，不许默认 False")


def test_auto_apply_parsed(tmp_path):
    from dwc.foundation.dial_config import load_evolution
    p = tmp_path / "evo.yaml"
    p.write_text("version: 1\nevolution:\n  feed_from_terms: true\n"
                 "  max_sigs_per_term: 50\n  auto_apply: false\n"
                 "  auto_apply_max_per_round: 2\n"
                 "  prompt_evolve_weekday: -1\n", encoding="utf-8")
    cfg = load_evolution(str(p))
    assert cfg["auto_apply"] is False
    assert cfg["auto_apply_max_per_round"] == 2


# ── 2. 配额 ────────────────────────────────────────────────

class _Mu:
    def __init__(self):
        self.RULES = {}
        self.last_reason = ""

    def propose_from_cluster(self, sigs, context="", want_code=False,
                             learned_hint="", operator="improve",
                             component=""):
        from dwc.organs.evolver import Proposal
        s0 = dict(sigs[0])
        return Proposal(
            proposal_id="P_test_" + str(s0.get("fn")),
            failure_signature=s0, component=(component or "control_flow"),
            target=str(s0.get("fn")), patch="return 1",
            code=None, rationale="test", dimension="D1",
            target_layer="assets", operator=operator)


class _Ev:
    def __init__(self):
        self.mutator = types.SimpleNamespace(RULES={})
        self.landed = []

    def diagnose(self, sigs):
        return {"unmapped": sigs}

    def accept(self, p, **kw):
        return {"decision": "adopted_not_implemented", "gates": []}

    def _land_adopted(self, p, admission_round=None):
        self.landed.append(p.target)
        return {"outcome": "landed", "key": "k:" + p.target}


def _mkdb(path, rows):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE failure_sig (c TEXT,q TEXT,m TEXT,node_id TEXT)")
    for r in rows:
        con.execute("INSERT INTO failure_sig VALUES (?,?,?,?)", r)
    con.commit()
    con.close()


def test_max_land_caps_round(tmp_path, monkeypatch):
    EVO = _evo()
    monkeypatch.setattr(EVO, "probe_signatures", lambda t: {("E", "Q")})
    db = str(tmp_path / "t.sqlite")
    _mkdb(db, [("E", "Q", "llm_asserted:1", "n1"),
               ("E", "Q", "llm_asserted:1", "n2")])
    ev = _Ev()
    rep = EVO.run_round(
        db, ev, _Mu(), "ctx",
        lambda t, pa, code=None: {"success": True, "in_score": 1.0,
                                  "held_out": 1.0, "baseline_in": 0.5,
                                  "baseline_ho": 0.5, "mode": "code"},
        True, rules_path=str(tmp_path / "rules.json"),
        fn_of=lambda r: r[3], task_of=lambda r: "t",
        max_land=1, resume=False)
    assert len(ev.landed) == 1, "配额 1 却落了 %d 条" % len(ev.landed)
    decs = [r.get("adopt") for r in rep["results"]]
    assert "quota_exceeded" in decs
    assert rep["results"][1].get("reason", "").startswith("落地配额已满")


# ── 3. 备份 ────────────────────────────────────────────────

def test_land_adopted_writes_backup(tmp_path, monkeypatch):
    from dwc.organs import evolver as EV
    rules = tmp_path / "config" / "anchors" / "rules.json"
    rules.parent.mkdir(parents=True)
    monkeypatch.setattr(EV.Mutator, "LEARNED_PATH", str(rules))
    monkeypatch.setattr(EV.Mutator, "SEED_KEYS", frozenset())
    p = EV.Proposal(proposal_id="P1", failure_signature={"c": "E", "q": "Q",
                                                          "fn": "f"},
                    component="control_flow", target="f", patch="return 1",
                    rationale="t", dimension="D1",
                    target_layer="assets", operator="improve")
    p.state = "adopted_not_implemented"
    ev = EV.Evolver()
    out = ev._land_adopted(p, admission_round="2026-10-23")
    assert out["outcome"] == "landed"
    assert rules.is_file(), "rules.json 没写出来"
    assert out.get("backup") and os.path.isfile(out["backup"])


# ── 4. 回滚 ────────────────────────────────────────────────

def test_rollback_removes_single_key(tmp_path):
    cron = _cron()
    rules = tmp_path / "rules.json"
    rules.write_text(json.dumps({"learned": {"a:b:c": {"x": 1},
                                             "d:e:f": {"x": 2}}}),
                     encoding="utf-8")
    out = cron._rollback_key("a:b:c", str(rules), str(tmp_path / "bk"))
    assert out["outcome"] == "rolled_back"
    data = json.loads(rules.read_text(encoding="utf-8"))
    assert list(data["learned"]) == ["d:e:f"], "回滚动了别的键"
    assert os.path.isfile(out["backup"])


def test_rollback_missing_key_is_loud(tmp_path):
    cron = _cron()
    rules = tmp_path / "rules.json"
    rules.write_text(json.dumps({"learned": {}}), encoding="utf-8")
    out = cron._rollback_key("nope", str(rules), str(tmp_path / "bk"))
    assert out["outcome"] == "not_found"


def test_learned_path_isolated_from_production():
    """★★ 守卫：测试进程的 LEARNED_PATH 绝不许指向生产 rules.json。

    现场：一次全量跑完后 config/anchors/rules.json 消失。
    只靠 fixture 里 monkeypatch 不够（有测试会把它 pin 回生产路径），
    所以 conftest 在 import dwc 之前用 DWC_LEARNED_PATH 把真源指到 tmp。
    """
    from dwc.organs.evolver import Mutator
    p = Mutator.LEARNED_PATH.replace("\\", "/")
    assert not p.endswith("config/anchors/rules.json"), p
