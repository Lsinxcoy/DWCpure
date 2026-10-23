# -*- coding: utf-8 -*-
"""R438 · meta_evolution：按压力调整进化自己的旋钮。

★ 改前 evolution.yaml 只能人手改：系统每天跑进化轮，却从不根据
  "多少候选被配额挤掉"调整自己的预算 ⇒ 元进化维度没有闭环。

锁：
1. 无配额压力 ⇒ None（不许为改而改）。
2. 有 quota_exceeded ⇒ cap +1。
3. 到上界 ⇒ None。
4. 冷却期内 ⇒ None。
5. apply 按行改、保留注释、备份、读回一致。
6. 越界/未知键 ⇒ 拒。
"""
import io
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs import meta_policy as MP   # noqa: E402

_YAML = """# 注释必须保留
version: 1
evolution:
  feed_from_terms: true
  max_sigs_per_term: 50
  auto_apply: true
  auto_apply_max_per_round: 1
  prompt_evolve_weekday: -1
"""


def _rep(n_quota):
    return {"results": [{"adopt": "quota_exceeded"} for _ in range(n_quota)]}


def test_no_pressure_no_change():
    assert MP.propose(_rep(0), {"auto_apply_max_per_round": 1}) is None


def test_pressure_raises_cap():
    a = MP.propose(_rep(2), {"auto_apply_max_per_round": 1})
    assert a and a["key"] == "auto_apply_max_per_round"
    assert a["old"] == 1 and a["new"] == 2


def test_cap_at_bound():
    assert MP.propose(_rep(3), {"auto_apply_max_per_round": 3}) is None


def test_cooldown():
    assert MP.propose(_rep(1), {"auto_apply_max_per_round": 1},
                      last_ts=1.0, now=2.0) is None


def test_apply_preserves_comments(tmp_path):
    p = tmp_path / "evolution.yaml"
    p.write_text(_YAML, encoding="utf-8")
    out = MP.apply("auto_apply_max_per_round", 2, path=str(p),
                   backup_dir=str(tmp_path / "bak"))
    txt = p.read_text(encoding="utf-8")
    assert "# 注释必须保留" in txt
    assert "auto_apply_max_per_round: 2" in txt
    assert out["backup"] and os.path.isfile(out["backup"])


def test_apply_rejects_out_of_bounds(tmp_path):
    p = tmp_path / "evolution.yaml"
    p.write_text(_YAML, encoding="utf-8")
    with pytest.raises(ValueError):
        MP.apply("auto_apply_max_per_round", 9, path=str(p))


def test_apply_rejects_unknown_key(tmp_path):
    p = tmp_path / "evolution.yaml"
    p.write_text(_YAML, encoding="utf-8")
    with pytest.raises(ValueError):
        MP.apply("nope", 1, path=str(p))
