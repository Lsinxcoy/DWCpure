# -*- coding: utf-8 -*-
"""R437 · 进化输入分流：归因 + 实测可复现 + 两车道。

★★★ 现场（审计 2026-10-23）：
    · `failure_sig` 表没有 task 列，cron 用常量 lambda 补齐
      ⇒ 2034 条签名全被标成同一个任务。
    · 分流按 `m.startswith("llm_asserted")` **猜**，2034 条全被扔掉。
    · cron 的 `_prod_root()` 返回 `~/.dwc`，而 agent 写的是仓库 `var/`
      ⇒ 每日轮读的是 6 天前的库（68 行 vs 2053 行）。

★★★ 本测试锁三件事：
    ① task 必须从 payload 读（不再串任务）
    ② 可复现性必须**实测**（破坏实现能跑出同一种失败签名）
    ③ cron 不许再把任务名写死 / 不许读旧库
"""
from __future__ import annotations

import io
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import dwc_evo_round as EVO          # noqa: E402
from dwc.organs.evolver import Evolver   # noqa: E402


def _mkdb(path, rows):
    """rows = [(c, q, m, task)] —— 建最小 memory_node + failure_sig。"""
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE memory_node (node_id TEXT PRIMARY KEY, payload TEXT)")
    con.execute("CREATE TABLE failure_sig (c TEXT, q TEXT, m TEXT, node_id TEXT)")
    for i, (c, q, m, task) in enumerate(rows):
        nid = "n%d" % i
        con.execute("INSERT INTO memory_node VALUES (?,?)",
                    (nid, json.dumps({"c": c, "q": q, "m": m, "task": task},
                                     ensure_ascii=False)))
        con.execute("INSERT INTO failure_sig VALUES (?,?,?,?)", (c, q, m, nid))
    con.commit()
    con.close()


def test_task_read_from_payload(tmp_path):
    """★★★ 两条不同任务的签名，归因不许串。"""
    db = str(tmp_path / "t.sqlite")
    _mkdb(db, [("E_NO_RESULT", "abstained_or_missing", "llm_asserted:None",
                "code_fix_009"),
               ("E_VALUE", "wrong_magnitude", "llm_asserted:0.15",
                "code_fix_002")])
    got = []
    clusters = EVO.collect_unmapped(db, Evolver(), lambda r: "", lambda r: "",
                                    filtered_out=got)
    # 两条车道合起来看归因（E_NO_RESULT 进行为道，E_VALUE 进代码道）
    tasks = ({s["task"] for s in got}
             | {s["task"] for c in clusters for s in c["sigs"]})
    assert tasks == {"code_fix_009", "code_fix_002"}, tasks


def test_probe_matches_real_signature():
    """★★★ 破坏实现真的能跑出 E_VALUE/wrong_magnitude（不是猜的）。"""
    probe = EVO.probe_signatures("code_fix_002")
    assert ("E_VALUE", "wrong_magnitude") in probe, probe


def test_probe_empty_for_task_without_broken_impl():
    """★★ 没有破坏实现的任务 ⇒ 空集（没有代码可修）。"""
    assert EVO.probe_signatures("code_fix_009") == set()


def test_behavior_sig_goes_to_behavior_lane(tmp_path):
    """★★★ 弃答类失败不是代码 bug ⇒ 必须进行为车道，不许进 evolver。"""
    db = str(tmp_path / "t.sqlite")
    _mkdb(db, [("E_NO_RESULT", "abstained_or_missing", "llm_asserted:None",
                "code_fix_002")])
    beh = []
    clusters = EVO.collect_unmapped(db, Evolver(), lambda r: "", lambda r: "",
                                    filtered_out=beh)
    assert clusters == [], "弃答被错当成代码 bug 了"
    assert len(beh) == 1 and beh[0]["c"] == "E_NO_RESULT"


def test_code_sig_stays_in_evolver(tmp_path):
    """★★★ 能复现的签名必须留下（旧前缀过滤会把它一起扔掉）。"""
    db = str(tmp_path / "t.sqlite")
    _mkdb(db, [("E_VALUE", "wrong_magnitude", "llm_asserted:0.15",
                "code_fix_002")])
    beh = []
    clusters = EVO.collect_unmapped(db, Evolver(), lambda r: "", lambda r: "",
                                    filtered_out=beh)
    assert len(clusters) == 1, "能复现的签名被过滤掉了"
    assert beh == []
    assert clusters[0]["sigs"][0]["task"] == "code_fix_002"
    assert clusters[0]["sigs"][0]["fn"] == "average", "fn 应从锚点 checks 反查"


def test_cron_has_no_hardcoded_task():
    """★★★ 任务名写死 = 2034 条签名全串成一个任务。"""
    src = io.open(os.path.join(ROOT, "scripts", "dwc_evo_round_cron.py"),
                  encoding="utf-8").read()
    assert '"code_fix_007"' not in src
    assert 'lambda r: "average"' not in src


def test_cron_reads_task_from_payload():
    """★★★ 表里没有 task 列，必须走 json_extract(payload)。"""
    src = io.open(os.path.join(ROOT, "scripts", "dwc_evo_round_cron.py"),
                  encoding="utf-8").read()
    assert "DISTINCT task FROM failure_sig" not in src
    assert "json_extract(n.payload,'$.task')" in src


def test_prod_root_same_as_agent():
    """★★★ cron 的数据根必须与 agent 写库的根一致（旧实现恒 ~/.dwc）。"""
    import dwc_evo_round_cron as CRON
    assert CRON._prod_root() == CRON._code_root(), \
        "cron 读的不是 agent 写的那个库"
    assert os.path.exists(os.path.join(CRON._prod_root(), "var",
                                       "dwc_prod.sqlite"))
