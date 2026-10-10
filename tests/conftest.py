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

import pytest


@pytest.fixture(autouse=True)
def _reset_process_global_state():
    """每个测试前后复位两个进程内全局表（③门树注入 + 门②planner 开关）。"""
    from dwc.harness import gates as _gates
    _gates.set_current_tree(None)
    _gates.set_planner_layer(False)
    yield
    _gates.set_current_tree(None)
    _gates.set_planner_layer(False)
