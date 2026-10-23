# -*- coding: utf-8 -*-
"""R297-Task2 · 备份加固（sqlite backup API＋rules.json＋latest 指针）。

★ R206 脚本已存在，本任务只补三处（只增不改其余）。
★ 零真 LLM；raises 配额见末尾。
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def test_r297_backup_sqlite_usable(tmp_path):
    """★ 在线拷：源库正被写（WAL 有未 checkpoint）⇒备份库可打开可查。"""
    import dwc_backup as BAK
    src = str(tmp_path / "prod.sqlite")
    _c = sqlite3.connect(src)
    _c.execute("create table t(a)")
    _c.execute("insert into t values (1)")
    _c.commit()
    _c.execute("pragma journal_mode=WAL")
    _c.execute("insert into t values (2)")  # ★ 未 commit？commit 了但 WAL 未 checkpoint
    _c.commit()
    os.makedirs(str(tmp_path / "anchors_empty"), exist_ok=True)
    out = BAK.run_backup(src_db=src,
                         anchors_dir=str(tmp_path / "anchors_empty"),
                         dest_root=str(tmp_path / "bak"))
    db2 = sqlite3.connect(os.path.join(out, "dwc_prod.sqlite"))
    n = db2.execute("select count(*) from t").fetchone()[0]
    _c.close(); db2.close()
    assert n == 2, n


def test_r297_backup_includes_rules(tmp_path):
    """★ rules.json 在备份里（adopt 落了新条必须备下来）。"""
    import dwc_backup as BAK
    anch = tmp_path / "anchors"
    anch.mkdir()
    (anch / "rules.json").write_text('{"learned": {}}', encoding="utf-8")
    src = str(tmp_path / "prod.sqlite")
    sqlite3.connect(src).execute("create table t(a)").close()
    out = BAK.run_backup(src_db=src, anchors_dir=str(anch),
                         dest_root=str(tmp_path / "bak"))
    assert os.path.isfile(os.path.join(out, "anchors", "rules.json"))
    latest = open(os.path.join(str(tmp_path / "bak"), "latest"),
                  encoding="utf-8").read().strip()
    assert latest in out  # ★ latest 指针指本次


def test_r297_raises_quota_missing_db(tmp_path):
    """★ raises 配额：源库缺席⇒抛大声（不静默备出空目录）。"""
    import dwc_backup as BAK
    with pytest.raises(Exception):
        BAK.run_backup(src_db=str(tmp_path / "nope.sqlite"),
                       anchors_dir=str(tmp_path),
                       dest_root=str(tmp_path / "bak"))
