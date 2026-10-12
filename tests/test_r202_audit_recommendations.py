# -*- coding: utf-8 -*-
"""R202 · 审计悬置三裁决落地锁（用户令"全部执行你的推荐"）。

① LATERAL 同 component 优先（推荐b）— Mutator.propose_lateral
   prefer_components 分组选 kin; 组空回落全集（R173 不弃候选）
② RULES target 真源校验（推荐b）— check_entry(dev_targets=…)
   生产注入（loop 固化 + e2e 固化）= 主路径必过
③ anchor drift 监控常驻（推荐a）— scripts/dwc_anchor_drift_watch.py
   + cron 副本同步锁（CRON RUNS THE COPY 防漂移）
"""
from __future__ import annotations

import hashlib
import os
import sys

ROOT = r"E:\Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.evolver import COMPONENT_VOCAB, Mutator      # noqa: E402

CODE_PREF = tuple(c for c in COMPONENT_VOCAB if c != "prompt")
EV = {"component": "prompt", "dimension": "D3", "target_layer": "prompt",
      "m": "x", "m_source": "rule", "patch": "p", "rationale": "r"}


# ══════════════════════════════════════════════
# ① LATERAL 同 component 优先
# ══════════════════════════════════════════════
def test_lateral_prefers_same_component_group():
    """★★★ behavior 任务偏好代码组件: average 的 kin 从 pow2(prompt)
    变为 sum_first_n(control_flow) — R200 实测痛点（借文本 patch 编译炸）。"""
    m = Mutator()
    sig = {"c": "E_VALUE", "q": "wrong_magnitude", "fn": "average"}
    p_no = m.propose_lateral(sig)                       # 未传 = R173 原行为
    p_pref = m.propose_lateral(sig, prefer_components=CODE_PREF)
    assert p_no.component == "prompt", "未传偏好必须保持 sorted 首个（原行为）"
    assert p_pref.component == "control_flow", (
        "偏好代码组件应选到 sum_first_n, 实得 %s/%s"
        % (p_pref.target, p_pref.component))


def test_lateral_text_task_prefers_prompt():
    """★★ 文本任务偏好 prompt kin（不借代码 patch）。"""
    m = Mutator()
    p = m.propose_lateral({"c": "E_VALUE", "q": "wrong_magnitude",
                           "fn": "range"},
                          prefer_components=("prompt",))
    assert p.component == "prompt"


def test_lateral_empty_pref_group_falls_back():
    """★★★ 偏好组空 ⇒ 回落全集首个（R173 不因偏好弃候选 — 弃权只在真无同族）。"""
    m = Mutator()
    p = m.propose_lateral({"c": "E_NO_RESULT",
                           "q": "abstained_or_missing", "fn": "zzz"},
                          prefer_components=("prompt",))
    assert p is not None and p.component == "control_flow", (
        "偏好组空必须回落, 实得 %r" % (p and p.component,))


def test_lateral_no_family_still_none():
    """★★ 真无同族 ⇒ None（原弃权语义不变）。"""
    m = Mutator()
    assert m.propose_lateral({"c": "E_BRAND_NEW", "q": "never_seen",
                              "fn": "zzz"},
                             prefer_components=CODE_PREF) is None


def test_loop_wires_prefer_into_lateral():
    """★★★ 生产接线: loop 按任务 kind 构造 prefer 并传入 _dir_generate。"""
    src = open(os.path.join(ROOT, "src", "dwc", "harness", "loop.py"),
               encoding="utf-8").read()
    assert "prefer_components=_prefer" in src, "loop 没把 prefer 传进生成器"
    assert 'in ("keyword_match",\n' in src or "expected_values" in src, (
        "prefer 构造缺 kind 分流")
    # Evolver 委派透传（Loop 调的是 evolver.propose_lateral）
    esrc = open(os.path.join(ROOT, "src", "dwc", "organs", "evolver.py"),
                encoding="utf-8").read()
    assert "prefer_components=prefer_components)" in esrc, "委派没透传"


# ══════════════════════════════════════════════
# ② target 真源校验（注入式）
# ══════════════════════════════════════════════
def test_check_entry_rejects_off_truth_target():
    """★★★ 注入时: target∉(dev task∪fn) ⇒ missing 拒。"""
    dt = Mutator.dev_targets()
    miss = Mutator.check_entry("E:q:no_such_fn", dict(EV, target="no_such_fn"),
                               dev_targets=dt)
    assert miss == ["target∉真源(dev task∪fn): 'no_such_fn'"], miss


def test_check_entry_accepts_both_target_semantics():
    """★★★ 双载两语义都放行: task_id（文本族）与 fn 名（behavior 族）。"""
    dt = Mutator.dev_targets()
    assert Mutator.check_entry("E:q:reproduce_001",
                               dict(EV, target="reproduce_001"),
                               dev_targets=dt) == []
    assert Mutator.check_entry("E:q:sum_first_n",
                               dict(EV, component="control_flow",
                                    target="sum_first_n"),
                               dev_targets=dt) == []


def test_check_entry_uninjected_stays_compatible():
    """★★ 未注入 ⇒ 不查（合成占位 target 'f' 合规 — schema/真源解耦的
    既有测试设计不为校验破坏）。"""
    assert Mutator.check_entry("E:q:f", dict(EV, target="f")) == []


def test_dev_targets_matches_truth_source():
    """★★ dev_targets 两路同源: 缺省读 TRUTH_SOURCE 文件 == 从 anchors 算。"""
    import io
    import json
    from dwc.organs.judge import TRUTH_SOURCE
    data = json.loads(io.open(TRUTH_SOURCE[0][1], encoding="utf-8").read())
    assert Mutator.dev_targets(data) == Mutator.dev_targets()


def test_production_injection_wired():
    """★★★ 生产注入在环: loop 固化与 e2e 固化都走注入版（主路径必过 —
    Layer 23.2: 纪律必须在真实写入路径生效, 不是装饰）。"""
    lsrc = open(os.path.join(ROOT, "src", "dwc", "harness", "loop.py"),
                encoding="utf-8").read()
    assert "dev_targets=Mutator.dev_targets(self.judge.anchors)" in lsrc, (
        "loop 固化没注入真源校验")
    esrc = open(os.path.join(ROOT, "scripts", "e2e_loop.py"),
                encoding="utf-8").read()
    assert "_chk = lambda k, e:" in esrc and "_M.dev_targets()" in esrc, (
        "e2e 固化没注入")
    # e2e 的 land_rule 尾参全走 _chk（不残留裸 check_entry）
    import re
    bare = [m.group(0) for m in re.finditer(r"land_rule\([^)]*_M\.check_entry",
                                            esrc, re.S)]
    assert not bare, "e2e 还有裸注入的 land_rule: %r" % bare


# ══════════════════════════════════════════════
# ③ drift 监控常驻（cron 副本同步锁）
# ══════════════════════════════════════════════
def test_drift_watch_script_contract():
    """★★★ 监控脚本契约: 仓库真源存在 + 关键纪律在位（直连 API / 节流 /
    心跳 / deliver local 由 cron 配置锁）。"""
    p = os.path.join(ROOT, "scripts", "dwc_anchor_drift_watch.py")
    src = open(p, encoding="utf-8").read()
    assert "drift_signals(REPO)" in src, "没消费 drift_signals"
    assert "tenant_access_token" in src and "message_id" in src, (
        "没走直连 API（no_agent deliver:feishu 不可靠 — skill 铁律）")
    assert "THROTTLE_S" in src and "heartbeat" in src, "缺节流/心跳"
    assert "receive_id_type" in src, "缺 open_id 私聊适配"


def test_drift_watch_health_is_silent():
    """★★★ 健康必须静默（hermes-cron-feishu 铁律: 空 stdout = 不投递,
    cron 2h tick 不轰炸; 有建议才投递）。

    ★ 行为级: 直接跑脚本, 断言 rc=0 且空 stdout（不是只读源码文本）。
    ★ 日度心跳例外: 当天首次 tick 发一条后, 后续 tick 必须静默（已由
      cron copy 的 state 验证 — 手动 run1 后 run2 空）。
    """
    import subprocess
    ROOT_DIR = r"E:\Divine Wisdom Core"
    r = subprocess.run(
        [sys.executable, os.path.join(ROOT_DIR, "scripts",
                                      "dwc_anchor_drift_watch.py")],
        capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-300:]
    assert r.stdout == "", (
        "健康 tick 必须静默（空 stdout），实得:\n%r" % r.stdout[:300])


def test_drift_watch_no_heartbeat_on_second_tick_of_day():
    """★★ 当日第二次 tick 静默（心跳只发一条, cron 不轰炸）。"""
    import json as _json
    st_path = os.path.join(os.environ["LOCALAPPDATA"], "hermes", "scripts",
                           ".dwc_drift_watch_state.json")
    import time as _t
    st = {"heartbeat": _t.strftime("%Y-%m-%d"), "sugg": None}
    _json.dump(st, open(st_path, "w", encoding="utf-8"), ensure_ascii=False)
    import subprocess
    r = subprocess.run(
        [sys.executable, r"E:\Divine Wisdom Core\scripts\dwc_anchor_drift_watch.py"],
        capture_output=True, text=True)
    assert r.returncode == 0
    assert r.stdout == "", "同日二次 tick 不得输出"


def test_cron_copy_in_sync():
    """★★★ CRON RUNS THE COPY 防漂移锁（skill 纪律: md5 断言）—
    cron 实际跑的是 hermes/scripts 下的副本, 仓库改完必须同步。"""
    repo = os.path.join(ROOT, "scripts", "dwc_anchor_drift_watch.py")
    copy = os.path.join(os.environ["LOCALAPPDATA"], "hermes", "scripts",
                        "dwc_anchor_drift_watch.py")
    assert os.path.exists(copy), "cron 副本缺失 ⇒ 作业跑旧码/或不存在"
    h = lambda p: hashlib.md5(open(p, "rb").read()).hexdigest()  # noqa: E731
    assert h(repo) == h(copy), (
        "副本与仓库漂移 ⇒ 仓库修复对 cron 不生效（改动只算半改）— "
        "执行: cp scripts/dwc_anchor_drift_watch.py %%LOCALAPPDATA%%/hermes/scripts/")
