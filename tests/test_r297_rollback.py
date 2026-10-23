# -*- coding: utf-8 -*-
"""R297-Task3 · 回滚函数（整键替换＋坏键大声）。

★ 零真 LLM；raises 配额见末尾。
★ 复用 Task 2 备份结构（latest 指针→anchors/rules.json 快照）。
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def _write_rules(rules_path, learned):
    with open(rules_path, "w", encoding="utf-8") as fh:
        json.dump({"learned": learned}, fh, ensure_ascii=False, indent=1)


def test_r297_rollback_restores_key(tmp_path):
    """★ 坏键回滚⇒恢复备份值（整键替换，不 merge）。"""
    from dwc.organs.evolver import rollback_rule
    bak = tmp_path / "bak" / "20260101_000000" / "anchors"
    bak.mkdir(parents=True)
    (bak / "rules.json").write_text(
        '{"learned": {"k1": {"patch": "good"}}}', encoding="utf-8")
    (tmp_path / "bak" / "latest").write_text(
        "20260101_000000", encoding="utf-8")
    rules = str(tmp_path / "rules.json")
    _write_rules(rules, {"k1": {"patch": "bad"}})
    r = rollback_rule("k1", rules, str(tmp_path / "bak"))
    assert r["restored"] == "k1"
    assert json.loads(open(rules, encoding="utf-8").read()
                       )["learned"]["k1"]["patch"] == "good"


def test_r297_rollback_missing_key_loud(tmp_path):
    """★ 备份里无该键⇒KeyError 大声（不静默假装回滚成功）。"""
    from dwc.organs.evolver import rollback_rule
    bak = tmp_path / "bak" / "20260101_000000" / "anchors"
    bak.mkdir(parents=True)
    (bak / "rules.json").write_text('{"learned": {}}', encoding="utf-8")
    (tmp_path / "bak" / "latest").write_text(
        "20260101_000000", encoding="utf-8")
    rules = str(tmp_path / "rules.json")
    _write_rules(rules, {"k9": {"patch": "bad"}})
    with pytest.raises(KeyError):
        rollback_rule("k9", rules, str(tmp_path / "bak"))


def test_r297_rollback_no_backup_loud(tmp_path):
    """★ 无备份（latest 缺席）⇒FileNotFoundError 大声。"""
    from dwc.organs.evolver import rollback_rule
    rules = str(tmp_path / "rules.json")
    _write_rules(rules, {"k1": {"patch": "bad"}})
    with pytest.raises(FileNotFoundError):
        rollback_rule("k1", rules, str(tmp_path / "nobak"))
