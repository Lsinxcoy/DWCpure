# -*- coding: utf-8 -*-
"""R206 · P1 安全网三件: 健康探针 + 备份 + 铁律生产豁免清单。"""
from __future__ import annotations

import io
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

PY = sys.executable


# ═══ 健康探针 ═══
def test_health_probe_current_state_healthy():
    """★★ 生产现状（R205 台账+db 在位, 无最新段 error）⇒ 探针零问题。"""
    import dwc_prod_health as H
    issues = H.check()
    assert issues == [], "现状不该有健康问题: %s" % issues


def test_health_probe_flags_missing_db():
    """★★ 探针可违反状态: db 缺失 ⇒ 必须报（不静默）。"""
    import dwc_prod_health as H
    orig = H.DB
    H.DB = os.path.join(ROOT, "var", "__no_such_db__.sqlite")
    try:
        issues = H.check()
    finally:
        H.DB = orig
    assert any("db 缺失" in x for x in issues), "db 缺失没被抓: %s" % issues


def test_health_probe_latest_segment_only():
    """★★★ 口径锁: 历史段 error 不复发（首跑误报校准）—— 台账历史段放
    error 行、最新段干净 ⇒ 零问题。"""
    import json
    import dwc_prod_health as H
    orig = H.LOG
    fake = os.path.join(ROOT, "var", "__fake_log__.jsonl")
    # ★ 相对时间（Layer 22: 首版写死 2026-10-12T16:50 —— 跨时跑就触发停滞
    #   判据误报, 测试数据失效不是判据错; 停滞判据=最后事件距今>STALL_H）
    import time as _t
    _now = _t.time()
    def _ts_ago(sec):
        return _t.strftime("%Y-%m-%dT%H:%M:%S+08:00",
                           _t.localtime(_now - sec))
    rows = [
        {"term": 0, "error": "旧历史错误（已修复不复发）",
         "ts": _ts_ago(7200)},
        {"event": "completed", "ts": _ts_ago(7199)},
        {"term": 0, "pass_rate": 0.0, "ts": _ts_ago(120)},
        {"event": "completed", "ts": _ts_ago(119)},
    ]
    with io.open(fake, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    H.LOG = fake
    try:
        issues = H.check()
    finally:
        H.LOG = orig
        os.remove(fake)
    assert issues == [], "历史段 error 被复发误报: %s" % issues


# ═══ 备份 ═══
def test_backup_snapshots_all_objects():
    """★★★ 备份端到端: 五对象（两锚+epoch ledger+iron_laws+db）全进快照 +
    rc0。"""
    r = subprocess.run([PY, os.path.join(ROOT, "scripts", "dwc_backup.py")],
                       capture_output=True, text=True, cwd=ROOT, timeout=180)
    assert r.returncode == 0, "rc=%d stderr=%s" % (r.returncode, r.stderr[-200:])
    bdir = os.path.join(ROOT, "var", "backup")
    # ★ Layer-22 判据校准(2026-10-13): 目录里可能混入普通文件
    #   (dev_seed.json) — sorted(listdir)[-1] 会取到文件而非快照目录。
    #   只取目录; 与 dwc_backup.py 的 dirs 过滤同款。
    newest = sorted(x for x in os.listdir(bdir)
                    if os.path.isdir(os.path.join(bdir, x)))[-1]
    got = set()
    for dp, dn, fn in os.walk(os.path.join(bdir, newest)):
        for f in fn:
            got.add(os.path.relpath(os.path.join(dp, f),
                                    os.path.join(bdir, newest)))
    norm = {x.replace("\\", "/") for x in got}
    for need in ("anchors/dev.json", "anchors/broken_dev.json",
                 "anchors/anchor_epochs.jsonl", "iron_laws.yaml",
                 "dwc_prod.sqlite"):
        assert need in norm, "备份缺对象 %r: %s" % (need, norm)


# ═══ 铁律豁免清单 ═══
def test_iron_law_exemption_doc_covers_all_11():
    """★★ 豁免文档完备性: 2 真判 + 1 na + 8 豁免 = 11 条全交代（与
    iron_runtime 的 not_instrumented 集一致 — 不许文档漏律）。"""
    import dwc.foundation.iron_runtime as IR
    p = os.path.join(ROOT, "docs", "IRON_LAW_PRODUCTION.md")
    doc = io.open(p, encoding="utf-8").read()
    for lid in ("G8", "G11", "G1"):
        assert lid in doc, "豁免文档缺已生效律 %s" % lid
    for lid in IR._NOT_INSTRUMENTED:
        assert lid in doc, "豁免文档缺律 %s" % lid
    n_exempt = sum(1 for l in doc.splitlines()
                   if l.startswith("| G") and "补全前置条件" not in l
                   and "─" not in l and "判据" not in l)
    assert n_exempt >= 8, "豁免表行数不足: %d" % n_exempt


def test_cron_copies_in_sync():
    """★★ CRON RUNS THE COPY: 三脚本的 hermes 副本 md5 与仓库一致
    （cron 跑的是副本 — 不同步 = 改了不生效）。"""
    import hashlib
    def md5(p):
        return hashlib.md5(open(p, "rb").read()).hexdigest()
    dst = os.path.expandvars(r"%LOCALAPPDATA%\hermes\scripts")
    if not os.path.isdir(dst):
        pytest.skip("本机未安装 hermes cron 副本（CI 正常）")
    for f in ("dwc_prod_run.py", "dwc_prod_health.py", "dwc_backup.py"):
        a = os.path.join(ROOT, "scripts", f)
        b = os.path.join(dst, f)
        assert os.path.exists(b), "副本缺失: %s" % b
        assert md5(a) == md5(b), "%s 副本不同步（cron 跑旧码）" % f
