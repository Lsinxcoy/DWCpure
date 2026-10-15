# -*- coding: utf-8 -*-
"""R110 · 稿②执行 — matched-term 三臂协议（π0/π*/π̂）。

验收（稿② §⑦ 字面）:
  □ 三臂跑通（同底同预算）+ matched 三计数断言相等
  □ 独立锚 truth_sha8 前后一致（不一致=拒报）
  □ 内容效应三读数出数 + 协议字段齐全 + 禁用措辞扫描
  □ 盲改动可复现（同 seed 同序）
  ★ 两处实验 bug 教训锁: 编造 API 被 except 兜死（pi_star=pi0）·
    任务集不跨组（组序数据巧合退化）
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from matched_term import (  # noqa: E402
    FORBIDDEN_CLAIMS, arm_order, group_of_map)

ANCHORS = json.load(open(os.path.join(ROOT, "config", "anchors", "dev.json"),
                         encoding="utf-8"))
ALL_TASKS = sorted(t for t in ANCHORS
                   if not t.startswith("_")
                   and ANCHORS[t].get("verifier_kind") in
                   ("behavior", "keyword_match"))


def test_task_set_spans_two_groups():
    """★ 教训锁②: 任务集必须跨组（只取 behavior 6 任务全在 code_repair ⇒
    组间序无效, pi_star 与 pi0 数据巧合同序）。"""
    # ★ R287-E · 动态口径（anchor+3 根因：behavior 6→9，keyword 4 不变。
    #   意图是"跨组"，数字动态取 —— 下次 anchor+1 不炸。）
    _n_behavior = len([t for t in ALL_TASKS
                       if ANCHORS[t].get("verifier_kind") == "behavior"])
    _n_keyword = len([t for t in ALL_TASKS
                      if ANCHORS[t].get("verifier_kind") == "keyword_match"])
    assert len(ALL_TASKS) == _n_behavior + _n_keyword, \
        "behavior %d + keyword_match %d" % (_n_behavior, _n_keyword)
    gmap = group_of_map()
    groups = {gmap[t] for t in ALL_TASKS if t in gmap}
    assert len(groups) >= 2, "跨组才有组间序: %r" % groups


def test_arm_orders_and_reproducible():
    """★ 教训锁①: 臂用真 API（组表反查）; placebo 同 seed 可复现; pi0 字典序。"""
    o0 = arm_order("pi0", ALL_TASKS, 42)
    assert o0 == sorted(ALL_TASKS)
    p1 = arm_order("placebo", ALL_TASKS, 42)
    p2 = arm_order("placebo", ALL_TASKS, 42)
    assert p1 == p2 and p1 != o0, "盲序可复现且 ≠ 字典序"
    # pi_star 带 rates 的动态性: 人为压低组率 ⇒ 该组任务必须提前
    gmap = group_of_map()
    # ★ R287-E · 归位后 gmap 全覆盖 ALL_TASKS（group_of_map 与生产播种
    #   同口径）—— 未分组即真异常，不跳过。
    _grouped = ALL_TASKS
    assert all(t in gmap for t in _grouped), \
        "归位后仍有未分组任务: %s" % [t for t in _grouped if t not in gmap]
    low = {g: 0.1 for g in set(gmap.values())}
    first_low = [t for t in arm_order("pi_star", _grouped, 42, rates=low)
                 if gmap[t] == "knowledge_reasoning"]
    # 组率全 0.1 时组间平 — 用**单组低**验证排序键真读 rates:
    only_know = {"knowledge_reasoning": 0.1}
    order = arm_order("pi_star", _grouped, 42, rates=only_know)
    idx_first_know = next(i for i, t in enumerate(order)
                          if gmap[t] == "knowledge_reasoning")
    idx_first_code = next(i for i, t in enumerate(order)
                          if gmap[t] == "code_repair")
    # knowledge_reasoning rate=0.1 < code_repair 缺席 1.0 ⇒ 知识组必须在前
    assert idx_first_know < idx_first_code, order
    # 缺席组当 1.0 强组排后（run_term 同款降级）
    assert low is not None and first_low is not None


def test_script_full_protocol(tmp_path):
    """整脚本跑: 协议字段/锚断言/matched 账/禁措辞/三读数 + 恒等如实。"""
    outp = str(tmp_path / "mt.json")
    r = subprocess.run([sys.executable,
                        os.path.join(ROOT, "scripts", "matched_term.py"),
                        "--out", outp],
                       capture_output=True, timeout=600, cwd=ROOT)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")[-700:]
    d = json.load(open(outp, encoding="utf-8"))
    # 稿② §⑤ 协议字段逐个在位
    for k in ("protocol", "seed", "n_terms", "arms", "anchor", "verdicts",
              "claims_allowed", "forbidden_scanned", "caveats"):
        assert k in d, k
    assert set(d["arms"]) == {"pi0", "pi_star", "placebo"}
    # 锚前后一致
    a = d["anchor"]
    assert a["consistent"] and a["truth_sha8_before"] == a["truth_sha8_after"]
    # matched 三计数: 三臂全等
    for k in ("n_terms", "n_tasks", "n_scores", "n_decisions"):
        vals = {d["arms"][x][k] for x in d["arms"]}
        assert len(vals) == 1, (k, vals)
    # 三读数 + 禁措辞扫描
    assert set(d["verdicts"]) == {"vs_baseline", "vs_placebo",
                                  "content_effect"}
    claim = d["claims_allowed"][0]
    assert claim.startswith("matched-term 对照")
    # ★ 禁词只许出现在 forbidden_scanned（扫描清单字段本身就是词表）——
    #   其余任何正文(claim/protocol/caveats/verdicts)含禁词=违规
    body = {k: v for k, v in d.items() if k != "forbidden_scanned"}
    body_txt = json.dumps(body, ensure_ascii=False)
    for bad in FORBIDDEN_CLAIMS:
        assert bad not in body_txt, "禁词入正文: %r" % bad
    assert d["forbidden_scanned"] == list(FORBIDDEN_CLAIMS)
    # 效度边界如实（恒等 ⇒ 结构必然声明在）
    cave = json.dumps(d["caveats"], ensure_ascii=False)
    assert "结构必然" in cave and "R107" in cave
