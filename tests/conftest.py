# -*- coding: utf-8 -*-
"""tests 全局 conftest — R183 起的进程内全局态复位（测试基建修, 非产品修）。

★ 背景（R183 实测回归的根治）: gates._CURRENT_TREE 是**进程内共享表**
  （R181 采纳面 — Metric Loop 真换判据树的注入点）。R183 起 Loop.round
  末尾的 Metric Loop tick 会**真 adopt**（select ⇒ 回归 ⇒ 注入）⇒ 任何
  跑 round 的测试都会在表里留下注入树 ⇒ 同 session 后续测试的
  "未注入 ⇒ 出厂树"假设被打爆（实测: r165/r180 的 round 打爆了 r166/
  r181 的断言 — 红 2 处, 逐一定位到泄漏链）。
★ 一处治净: autouse fixture 在**每个测试前后**复位注入表 — 不依赖每个
  测试文件自律（R180/R183 已各自加过, 但 r165 这种老文件漏了 ⇒ 全局
  conftest 才是正解 — 新全局态接入时的注册点也应在此登记）。
★ 不动被测产品的复位语义: 这是**测试隔离**（默认被测码不带全局态）,
  产品里 adopt 是持久进程内生效（daemon 重启才复位 — R181 设计如此）。
★ R185 登记: planner 现场层开关 _SHARED_PLANNER_LAYER 同族（进程内
  全局 — Loop(planner_live=True) 的 round 会装表; 门②读表 ⇒ 同样
  必须前后复位, 否则泄漏给后续文件的"缺省 off"断言）。
"""
from __future__ import annotations

import atexit
import io
import os
import shutil
import tempfile

import pytest

# ★★★ R264 · 生产 var 全局隔离（2026-10-14 实锤: test_r211 清理时 cancel 了
#   **所有 pending 单** ⇒ 用户 10:10:31 真实派的 "帮我读一下 core.py" 被
#   测试误杀(cancelled 无报告); 此前已有 pairs/session 污染三例）。
#   机制: agent_rpc.VAR 读 DWC_VAR_DIR（既有开关）⇒ 本 conftest 在**任何
#   测试模块 import dwc 之前**设它 ⇒ 全进程 INBOX/DONE/REPORTS/LOG/DB 落
#   tmp ⇒ 真生产 inbox 永不进测试视野。生产不设该 env ⇒ 零行为变化。
_DWC_TEST_VAR = tempfile.mkdtemp(prefix="dwc_test_var_")
os.environ["DWC_VAR_DIR"] = _DWC_TEST_VAR
atexit.register(shutil.rmtree, _DWC_TEST_VAR, ignore_errors=True)

# ★★★ R434 · 提示词 A/B 的「钉版本」文件是**实验态**，测试一律看不到。
#   现场：跑 A/B 时 `var/prompt_force.json` 存在（task_exec=v2），
#   任何读提示词的测试都被钉到候选版本 ⇒ `test_canary_hash_pinned`
#   的 pct=0 断言拿到 v2 而变红。指到不存在的 tmp 路径即"没有钉版本"。
os.environ["DWC_PROMPT_FORCE_FILE"] = os.path.join(_DWC_TEST_VAR,
                                                   "prompt_force.json")

# ★★★ R438 · 已学规则文件同样**绝不许**指向生产：
#   现场：一次全量跑完后 config/anchors/rules.json 消失（被某个把
#   LEARNED_PATH pin 回生产路径的测试连带删掉）。只靠 fixture 里
#   monkeypatch 不够——必须在 import dwc 之前就把真源指到 tmp。
os.environ["DWC_LEARNED_PATH"] = os.path.join(_DWC_TEST_VAR, "rules.json")


@pytest.fixture(autouse=True)
def _reset_process_global_state():
    """每个测试前后复位两个进程内全局表（③门树注入 + 门②planner 开关）。"""
    from dwc.harness import gates as _gates
    _gates.set_current_tree(None)
    _gates.set_planner_layer(False)
    yield
    _gates.set_current_tree(None)
    _gates.set_planner_layer(False)


# ★★★ R292 · 测试副作用总闸（P4 收尾副作用根治②③）。
#
# ② _land_adopted→persist_learned 写死 LEARNED_PATH（生产 rules.json ——
#    config/anchors 下被跟踪文件）。R287-C 靠人 monkeypatch，R291-P4
#    实锤没遵守 ⇒ 生产文件被测试写盘。本闸默认指到 tmp。
# ③ 测试调脚本函数写死 docs/*.json＋archive/*.jsonl（被跟踪 8 文件 ——
#    R290/R291 全量一次脏 8 个，提交前 checkout 救火）。本闸跑前快照、
#    跑后还原（断言在 teardown 前跑完，不受影响）。
# ★ var/ 已 gitignore 不管；gate/e2e 人跑落盘不管（本闸只管 tests/）。
_R292_SNAPSHOT_FILES = [
    "docs/challenger_duel.json",
    "docs/deep_water_audit.json",
    "docs/dep_scan.json",
    "docs/hce_split_report.json",
    "docs/table8_status.json",
    "docs/transfer_attribution.json",
    "archive/epoch_ledger.jsonl",
    "archive/gate_trace.jsonl",
]
_R292_ROOT = r"E:/Divine Wisdom Core"


def _r292_read_bytes(p):
    try:
        with io.open(p, "rb") as f:
            return f.read()
    except Exception:                           # noqa: BLE001 — 缺席即 None
        return None


@pytest.fixture(autouse=True)
def _r292_no_side_effects(tmp_path, monkeypatch):
    """★★ 总闸：LEARNED_PATH→tmp＋被跟踪文件快照还原（每测自动）。"""
    try:
        from dwc.organs.evolver import Mutator
        monkeypatch.setattr(Mutator, "LEARNED_PATH",
                            str(tmp_path / "learned_isolated.json"))
        # ★ R438 · 生产 rules.json 现在会真有落盘规则；RULES 是类级全局，
        #   不复位就会渗进所有测试的计数断言（实测 24 红）。
        Mutator.RULES.clear()
        Mutator.RULES.update(Mutator.SEED_SNAPSHOT)
    except Exception:                           # noqa: BLE001 — evolver 坏不断全量
        pass
    _before = {_f: _r292_read_bytes(os.path.join(_R292_ROOT, _f))
               for _f in _R292_SNAPSHOT_FILES}
    yield
    for _f, _content in _before.items():
        _p = os.path.join(_R292_ROOT, _f)
        if _content is None:
            if os.path.exists(_p):
                os.remove(_p)  # ★ 测试新建的 ⇒ 删（本来就没有）
        elif _r292_read_bytes(_p) != _content:
            with io.open(_p, "wb") as fh:
                fh.write(_content)
