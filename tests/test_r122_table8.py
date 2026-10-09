# -*- coding: utf-8 -*-
"""R122 · 项3 Table 8 缺口轮 — 六维盘点出数 + 状态判定断言。

验收:
  □ 六维全在（不漏维）· status 分布 = 4 live + 2 雏形 + 0 缺（按现状重判）
  □ 每维三联齐全: status + measure + 取数命令（声称/实测/取数纪律）
  □ 实测读数来自落盘文件（pass_k/transfer/ablation 真键真值）
  □ meta-recursion 从六段档案统计（链深/验收分布/换代账本条数）
  □ R98 '四无'过时判定被显式记录（Ret/Stab 已落地的证据在位）
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def test_table8_status_runs_and_six_dims_complete():
    outp = os.path.join(ROOT, "docs", "table8_status.json")
    r = subprocess.run([sys.executable,
                        os.path.join(ROOT, "scripts", "table8_status.py")],
                       capture_output=True, timeout=300, cwd=ROOT)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[-600:]
    d = json.load(open(outp, encoding="utf-8"))
    dims = {x["dim"].split("(")[0]: x for x in d["dims"]}
    assert set(dims) == {"Adaptivity", "Efficiency", "Retention",
                         "Stability", "Transfer", "Meta-recursion"}
    # 按现状重判的分布（R98 '四无'过时）
    assert d["summary"] == {"live": 4, "雏形": 2, "缺": 0}
    # 每维三联: status + measure + cmd（取数命令在位 — 声称/实测/取数）
    for x in d["dims"]:
        assert x["status"] in ("live", "雏形", "缺"), x
        assert x["measure"] and x["cmd"], "★ 三联缺: %s" % x["dim"]
        assert x["reading"], "★ 实测读数缺: %s" % x["dim"]
    # Retention/Stability 的 live 依据 = R118/R100（R98 判'无'已过时的显式记录）
    assert "R98 判'无'已过时" in d["dims"][2]["since"]
    assert "R98 判'无'已过时" in d["dims"][3]["since"]


def test_meta_recursion_stats_from_archive():
    """meta-recursion 最小测量: 从六段档案统计（不造新尺）。"""
    from table8_status import meta_recursion_stats
    mr = meta_recursion_stats()
    assert mr["chain_depth"] >= 13          # R109-R121 六段链
    gmin, gmax = mr["gen_range"]
    assert gmin == 109 and gmax >= 121
    assert mr["acceptance_verdicts"].get("accepted", 0) >= 13
    assert mr["duel_regime_decisions"] >= 1   # 换代账本在位
    assert "caveat" in mr and "goal" in mr["caveat"]  # 停止决策未建如实


def test_stability_and_transfer_readings_real_keys():
    """实测读数来自真键（pass_k mean_pass_k / transfer experiment.arms）。"""
    d = json.load(open(os.path.join(ROOT, "docs", "table8_status.json"),
                       encoding="utf-8"))
    dims = {x["dim"].split("(")[0]: x for x in d["dims"]}
    st = dims["Stability"]["reading"]
    assert "mean_pass_k" in st and "pass^2" in st
    tr = dims["Transfer"]["reading"]
    assert "transplant" in tr and "placebo" in tr
    assert "结构必然" in tr      # golden 恒等的效度边界如实
    ab = dims["Adaptivity"]["reading"]
    assert "1.0" in ab          # ablation 四 V 真值
