# -*- coding: utf-8 -*-
"""R120 · E2 换代常态化 — 换代账本持久化 + 判决末条读取 + duel 联动。

验收（常态化 = 首次结果过目后机制长期运行的三件）:
  □ epoch_ledger.jsonl 每次对拍 append（历史可审计, 只增不改）
  □ read_last_regime: 末条=最新判决; 无/空=False; 坏行/缺字段=raise 不静默
  □ dep_scan main 走账本末条（不再依赖单文件覆盖写）
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from dep_scan import read_last_regime  # noqa: E402

LEDGER = os.path.join(ROOT, "archive", "epoch_ledger.jsonl")


def test_read_last_regime_boundaries(tmp_path):
    """末条判决语义: 无/空/末True/末False/坏行/缺字段 六态。"""
    p = str(tmp_path / "ledger.jsonl")
    assert read_last_regime(p) is False              # 无账本
    open(p, "w").write("")                            # 空账本
    assert read_last_regime(p) is False
    with open(p, "a", encoding="utf-8") as f:         # 两行, 末条=False
        f.write(json.dumps({"regime_change": True}) + "\n")
        f.write(json.dumps({"regime_change": False}) + "\n")
    assert read_last_regime(p) is False               # 末条 = 最新
    with open(p, "a", encoding="utf-8") as f:         # 末条翻转 True
        f.write(json.dumps({"regime_change": True}) + "\n")
    assert read_last_regime(p) is True
    with open(p, "a", encoding="utf-8") as f:         # 坏行 ⇒ raise 不静默
        f.write("{broken json\n")
    with pytest.raises(json.JSONDecodeError):
        read_last_regime(p)
    # 缺字段 ⇒ raise（不静默当 False 装"未换代"）
    p2 = str(tmp_path / "bad_field.jsonl")
    open(p2, "w").write(json.dumps({"decision": "x"}) + "\n")
    with pytest.raises(ValueError, match="缺 regime_change"):
        read_last_regime(p2)


def test_duel_appends_ledger_history():
    """★ duel 常态化: 跑一次 append 一行, 历史前缀不变（只增不改）。"""
    before = (open(LEDGER, encoding="utf-8").read()
              if os.path.exists(LEDGER) else "")
    r = subprocess.run([sys.executable,
                        os.path.join(ROOT, "scripts", "challenger_duel.py")],
                       capture_output=True, timeout=600, cwd=ROOT)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[-600:]
    after = open(LEDGER, encoding="utf-8").read()
    assert after.startswith(before), "★ 账本历史被改写（append 只增不改违约）"
    assert len(after.splitlines()) == len(before.splitlines()) + 1
    last = json.loads(after.splitlines()[-1])
    # 常态化记录完整性: 判决/challenger/指纹/行为差异四件在位
    assert last["decision"] == "incumbent_holds"
    assert last["regime_change"] is False
    assert last["challenger"].startswith("regression_epsilon")
    assert len(last["incumbent_fp"]) == 8
    assert last["behaviour_differs"] is True
    # 末条读取联动: 当前账本 ⇒ 从未换代
    assert read_last_regime(LEDGER) is False
