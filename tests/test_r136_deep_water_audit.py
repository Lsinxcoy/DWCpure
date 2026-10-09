# -*- coding: utf-8 -*-
"""R136 · 深水四欠账机器盘点 — Z4/Z5 live + δ_θ/routing partial + ECE/AppD absent。

验收:
  □ 七项全在（4 项 + ITEMS 长度）— 漏项即红
  □ 逐项 status 与证据计数（防"凭旧记忆判缺口"）
  □ exclude 纪律: not_dispatched/未做 字样不当接线（R136 实测教训）
  □ absent 项双 0（code/wire 全无）⇒ 不装"实现过"
  □ partial 项必须有 code 命中但 wire=0（声明≠接线）
  □ 盘点只读: 不改任何 .py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from deep_water_audit import ITEMS, audit, scan  # noqa: E402


def test_seven_items_all_present():
    """★ 七项全列（旧记忆六项 + coupling 独立 = 7）— 漏项即红。"""
    assert len(ITEMS) == 7
    ids = {i["id"] for i in ITEMS}
    assert ids == {"Z4", "Z5", "delta_theta", "ECE", "AppendixD",
                   "coupling", "routing"}


def test_exclude_self_declared_not_done():
    """★ 纪律: '未做/not_dispatched' 字样不当接线证据。"""
    hits_with = scan(r"ECE", )
    hits_excluded = scan(r"ECE")
    # iwm.py 的自陈行应被排除（排除后一条"未做"都不剩）
    assert all("未做" not in h for h in hits_excluded)
    # 排除只减不增: 有排除的扫描 ≤ 无排除的扫描（排除口径永不加命中）
    raw = scan(r"ECE", exclude_rx=r"__never__")
    assert len(hits_excluded) <= len(raw)
    # 且排除确有实效: 不排除时确有自陈行
    assert any("未做" in h for h in raw)


def test_audit_statuses():
    """★ 逐项状态: Z4/Z5/coupling live; δ_θ/routing partial; ECE/AppD absent。"""
    res = audit()
    by = {o["id"]: o["status"] for o in res["items"]}
    assert by["Z4"] == "live" and by["Z5"] == "live"
    assert by["coupling"] == "live"
    assert by["delta_theta"] == "partial"
    assert by["routing"] == "partial"
    assert by["ECE"] == "absent" and by["AppendixD"] == "absent"
    # partial ⇒ code>0 且 wire=0; absent ⇒ 双 0; live ⇒ wire>0
    for o in res["items"]:
        if o["status"] == "partial":
            assert o["code_hits"] > 0 and o["wire_hits"] == 0
        elif o["status"] == "absent":
            assert o["code_hits"] == 0 and o["wire_hits"] == 0
        else:
            assert o["wire_hits"] > 0


def test_doc_has_next_rounds():
    """文档须列待办 + 汇总裁决。"""
    p = os.path.join(ROOT, "docs", "deep_water_audit.json")
    assert os.path.exists(p), "先跑 scripts/deep_water_audit.py"
    d = json.load(open(p, encoding="utf-8"))
    assert d["n_items"] == 7
    assert d["verdict"]["next_rounds"] == ["delta_theta", "ECE",
                                           "AppendixD", "routing"]
    assert d["summary"] == {"live": 3, "partial": 2, "absent": 2}


def test_audit_readonly():
    """★ 只读: 跑盘点不动任何源码（git status 仍干净）。"""
    # 只查已跟踪源码的**内容修改**（untracked 新文件是本轮工作产物,
    # 不算盘点污染）⇒ git diff --name-only（仅 tracked）
    r = subprocess.run(["git", "diff", "--name-only"],
                       capture_output=True, cwd=ROOT)
    changed = [l for l in r.stdout.decode().splitlines()
               if l.strip().endswith(".py")]
    assert not changed, changed[:5]
