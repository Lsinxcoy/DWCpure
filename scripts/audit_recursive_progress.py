# -*- coding: utf-8 -*-
"""★ R336 · recursive-progress 轻量 ablation 审计。

survey §3.3 counterfactual control 的最小版：
  同一批 failure sigs，分别在「继承 learned rules」与「冻结 incumbent
  （清空 learned rules）」下跑 collect_unmapped，比较 unmapped 数。
  差值 = inherited state 对后续 improvement procedure 的帮助（improver gain
  的代理），而非 task success（capability gain）。

用法:
    python scripts/audit_recursive_progress.py [--db PATH] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from dwc.organs.evolver import Evolver, Mutator
from dwc.organs.judge import Judge
import dwc_evo_round as E


def _snapshot_rules():
    return dict(Mutator.RULES)


def _restore_rules(snap):
    Mutator.RULES.clear()
    Mutator.RULES.update(snap)


def audit(db_path: str, limit: int = 200) -> dict:
    Judge()
    evolver = Evolver()
    snap = _snapshot_rules()

    # 有继承
    with_inh = E.collect_unmapped(db_path, evolver,
                                  fn_of=lambda r: "average",
                                  task_of=lambda r: "code_fix_007",
                                  reproducible_only=False)
    n_with = len(with_inh) if isinstance(with_inh, list) else 0

    # 冻结 incumbent：清空 learned（保留种子 none），重跑
    Mutator.RULES.clear()
    without_inh = E.collect_unmapped(db_path, evolver,
                                    fn_of=lambda r: "average",
                                    task_of=lambda r: "code_fix_007",
                                    reproducible_only=False)
    n_without = len(without_inh) if isinstance(without_inh, list) else 0

    _restore_rules(snap)
    gain = n_without - n_with  # 正 = 继承减少了 unmapped（有帮助）
    return {
        "n_unmapped_with_inheritance": n_with,
        "n_unmapped_without_inheritance": n_without,
        "improver_gain_proxy": gain,
        "verdict": ("improver_gain" if gain > 0
                    else "no_improver_gain" if gain == 0
                    else "inheritance_hurts"),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(
        os.path.expanduser("~"), ".dwc", "var", "dwc_prod.sqlite"))
    ap.add_argument("--limit", type=int, default=200)
    a = ap.parse_args()
    r = audit(a.db, a.limit)
    print(json.dumps(r, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
