# -*- coding: utf-8 -*-
"""R406 · world_candidates.json 必须原子写（坏文件会让 agent 直接拒启）。

★★★ 现场（2026-10-21 05:00）：
    重启 agent 后进程立刻消失，stderr：
        dwc.organs.world_model.WorldModelError: Z4: tracked 清单读不回来
        （JSONDecodeError: Expecting ':' delimiter: line 54392 column 16）

    `config/anchors/world_candidates.json` 2.5MB / 13.5 万行，尾部完整、
    中部坏掉 —— 典型的"截断后又被续写"。

★ 根因：`_flush_tracked()` 用 `io.open(path,"w")` **先截断再写**；
  2.5MB 的写要几十毫秒，进程在这中间被杀 ⇒ 文件永久损坏 ⇒
  下次启动 `WorldModelError` **拒启**（这个设计是对的：不许悄悄空表开跑）。

★ 修法：临时文件 + fsync + `os.replace`（同分区原子）。
  要么读到旧文件，要么读到新文件，不存在半截。
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.world_model import WorldModel  # noqa: E402


def test_flush_is_atomic_and_reloadable(tmp_path):
    """★★★ 写完之后：文件合法 + 能重新载入 + 没有 .tmp 残留。"""
    p = str(tmp_path / "wc.json")
    wm = WorldModel(depth_limit=4, max_nodes=100, tracked_path=p)
    wm.tracked = [{"tree": "t", "node": "n%d" % i, "parent_id": "p",
                   "action": "a", "provenance": "observed", "at": 1.0}
                  for i in range(200)]
    wm._flush_tracked()
    obj = json.loads(open(p, encoding="utf-8").read())
    assert len(obj["tracked"]) == 200
    left = [f for f in os.listdir(str(tmp_path)) if ".tmp." in f]
    assert not left, left
    # 重新载入（模拟重启）
    wm2 = WorldModel(depth_limit=4, max_nodes=100, tracked_path=p)
    assert len(wm2.tracked) == 200


def test_corrupt_file_raises_loudly(tmp_path):
    """★★ 坏文件必须**大声拒启**（不许悄悄空表开跑）。"""
    p = tmp_path / "bad.json"
    p.write_text('{"tracked": [{"a": 1}, BROKEN', encoding="utf-8")
    with pytest.raises(Exception) as ei:
        WorldModel(depth_limit=4, max_nodes=100, tracked_path=str(p))
    assert "tracked" in str(ei.value).lower() or "Z4" in str(ei.value)
