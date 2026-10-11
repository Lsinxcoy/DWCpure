# -*- coding: utf-8 -*-
"""trajectory · 轮次状态序列的机械面（R196 · Z 类落地 乙类 B1 + B2）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 只**投影已登记字段** + jsonl 追加/回读; 不判分、不设阈值、不造新字段。

★★★★★ **无论文依据**（R196 记账 — 诚实条款, 违反即作废）
  R193 对账把 state 记成"2609.06396 的 (𝒟,θ,𝒽) 三元组" ⇒ **出处错**：
  实测该论文的 `𝒟` 是 **dev 数据集**（`𝒢_fixed(ℳ⁺;x,𝒟_dev)`），`θ/𝒽` 三元组
  在该论文**不存在**; 57 篇落档全文 grep `world state` = 0 命中该语义。
  ⇒ 本模块是 **DWC 自定义能力**, 不是任何论文机制的搬运。docstring 不许
    出现「论文说」字样（G5 声称门延伸: 冒充论文依据 = 假声称）。
  freshness 同理: 无"衰减/陈旧阈值"的论文据 ⇒ **只提供 age_rounds 查询,
  不设阈值**。

★★★ TRUTH_SOURCE（判据 G2）
  snapshot 的键**全部**来自 `harness/consume_points.py` 的 `CONSUME_POINTS`
  （R194 登记面, 16 条 Loop 痕迹）。**不许新增 _last_***: 加字段 = 绕过
  R194 的登记测试（那才是防漂移的门）。

★★★ 为什么这是真缺口（R196 机器证据）
  DWC 有"点"（16 个 _last_* 单轮快照）没有"状态序列": 跨轮问题（如
  "R190 修的三层洞在 R194 如何被证伪"）只能翻人写的 knowledge3_*.json,
  **没有机器轨迹可算**。本模块把单轮快照变成 jsonl 序列 ⇒ 可 diff 可统计。
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from dwc.harness.consume_points import CONSUME_POINTS

#: ★ jsonl 每行的 schema 版本（升版本号必须能读旧行 — 机械面不许静默丢数据）
TRAJECTORY_SCHEMA_VERSION = 1


def snapshot(loop: Any) -> Dict[str, Any]:
    """Loop ⇒ 一次轮次状态投影（**只读已登记字段**）。

    ★ 键的边界: 只取 `CONSUME_POINTS` 里登记过的键（R194 的 16 条 + dir_ledger）。
      Loop 上未登记的 _last_* 属性 ⇒ **不取**（取 = 绕过登记面, 测试锁）。
    ★ None 是合法一等输出: 缺席的痕迹如实记 None, 不填 0/{} 冒充。
    ★ autonomy_markers（丙类 C1）: 只从已登记痕迹**派生布尔标记**,
      零新判据 — 见 _autonomy_markers()。
    """
    attrs = [k for k in CONSUME_POINTS if k.startswith("last_")
             or k.startswith("dir_")]
    raw: Dict[str, Any] = {}
    for k in attrs:
        raw[k] = getattr(loop, "_" + k, None) if k != "dir_ledger" else None
    return {
        "schema": TRAJECTORY_SCHEMA_VERSION,
        "gen": int(os.environ.get("DWC_ROUND_GEN", "0")),
        "markers": _autonomy_markers(raw),
        "state": {k: _project(v) for k, v in raw.items()},
    }


def _project(v: Any) -> Any:
    """值 ⇒ 可 json 序列化的投影（不可序列化 ⇒ str() 兜底, **不静默丢**）。

    ★ 为什么兜 str 而不是 skip: 跳过 = 该键"看起来缺席"（与真缺席混）;
      str() 至少留下"这里有个非 JSON 值"的痕迹（G7 同族）。
    """
    if v is None or isinstance(v, (bool, int, float, str)):
        return v
    if isinstance(v, dict):
        return {str(k): _project(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_project(x) for x in v]
    return str(v)


def _autonomy_markers(raw: Dict[str, Any]) -> List[str]:
    """★ 丙类 C1 · autonomy 的如实记账（**不建 autonomy 模块**）。

    ★ "autonomy" 是论文的**功能描述词**, 不是该有同名模块的东西（R195 已用
      "问法本身错了"判过一次, 这是同族）。DWC 的自主性散在三处**已登记**痕迹里,
    本函数只把它们汇成布尔标记 — 零新判据零新常量:
      direction_switched — _last_dir_decision 在场且 reason 非空
      all_failed_bookkept — _last_skip 含"三方向全败（terminal"
      adopted             — _last_adopt 在场且 adopted=True
      consolidation_done  — _last_consolidation 在场且 outcome=="consolidated"
    """
    m: List[str] = []
    d = raw.get("last_dir_decision")
    if d is not None and getattr(d, "reason", ""):
        m.append("direction_switched")
    s = raw.get("last_skip")
    if isinstance(s, str) and "三方向全败（terminal" in s:
        m.append("all_failed_bookkept")
    a = raw.get("last_adopt")
    if isinstance(a, dict) and a.get("adopted") is True:
        m.append("adopted")
    c = raw.get("last_consolidation")
    if isinstance(c, dict) and c.get("outcome") == "consolidated":
        m.append("consolidation_done")
    return m


def append(archive_path: str, snap: Dict[str, Any]) -> int:
    """snap ⇒ jsonl 追加（返回新行号 — 1-based; 与 direction_ledger 同格式纪律）。

    ★ 父目录不存在 ⇒ 建（机械面不论断环境, 但也不静默失败 — 失败即抛）。
    """
    os.makedirs(os.path.dirname(os.path.abspath(archive_path)), exist_ok=True)
    with open(archive_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(snap, ensure_ascii=False) + "\n")
        fh.flush()
        os.fsync(fh.fileno())
    return len(read(archive_path))


def read(archive_path: str) -> List[Dict[str, Any]]:
    """回读（**机械面**）: 逐行 json.loads; 坏行 ⇒ 抛（不跳过 — G7）。

    ★ 文件不存在 ⇒ []（从未写过 = 空序列, 是合法一等输出, 不是错误）。
    """
    if not os.path.exists(archive_path):
        return []
    out: List[Dict[str, Any]] = []
    with open(archive_path, encoding="utf-8") as fh:
        for ln, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(
                    "%s 第 %d 行不是合法 json ⇒ 机械面拒绝猜: %s"
                    % (archive_path, ln, exc))
    return out


def age_rounds(traj: List[Dict[str, Any]], gen: int) -> int:
    """B2 · freshness 的**唯一查询**: 给定 gen ⇒ 距今几轮（无该 gen ⇒ -1）。

    ★★ **不设阈值**: DWC 无"多久算陈旧"的论文据 ⇒ 本函数只回答"几轮",
      判"算不算陈旧"是调用方的语义（G2: 判据不在本模块）。
    ★ 序列空 / gen 未出现 ⇒ -1（缺席是一等输出, 不返 0 冒充"就在本轮"）。
    """
    if not traj:
        return -1
    seen = [i for i, s in enumerate(traj)
            if int(s.get("gen", -1)) == gen]
    if not seen:
        return -1
    return len(traj) - 1 - seen[-1]


TRAJECTORY_MECHANICS = {
    "no_paper_basis": "R193 把 state 引到 2609.06396 属出处错（𝒟 是 dev set）⇒ 本模块是 DWC 自定义能力",
    "keys_only_from_consume_points": "snapshot 的键 ⊆ CONSUME_POINTS（R194 登记面）— 测试锁",
    "freshness_no_threshold": "age_rounds 只返 int; 无陈旧阈值（无据可设）",
    "autonomy_no_module": "C1 autonomy 不建模块; 只从已登记痕迹派生布尔标记",
}
