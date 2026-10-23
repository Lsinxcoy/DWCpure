"""consume_points · 消费点登记面（R193 债 X3 — 观测面五元组）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 不判分、不写盘、不发建议 — 只**登记**"哪个属性被谁读"这件事实。
  ★ 与 `organs/applier.py TARGETS` 的分工（**不抢位**）:
      applier.TARGETS  = **可写面**声明（applier 能写什么: consumer/path/attr/verify）
      consume_points  = **观测面**声明（Loop 的痕迹属性被谁读: 同名五元组, 但语义是"读"）
    ⇒ 母巢只有 consumer/path/attr 三字段, DWC 两边都加 verify = 回读函数
      （applier.py:75 的原口径, 本文件沿用同 schema 不另立字段名）。

★★★ TRUTH_SOURCE（判据 G2）
  本模块不自判 — 它只回答"登记了几条/某 consumer 是否在场"这种**结构事实**;
  消费方**读没读到**不在本模块判据面（那是调用方自己的事）。

★ 为什么现在才做（R193 的诚实记账）: R189 对账判 consume "ABSENT / 未显式化"
  — 实测**半错**: 五元组 schema 早在 applier.py:75 在场, 只是覆盖 1 条
  （mutation_rule）; Loop 侧的 L4/R170-R191 事实消费点（_last_skip /
  _dir_ledger_append / _last_metric_pick / _last_replay_pick / _last_a_train /
  _last_planner_trace / _last_consolidation / _last_adopt / _last_blocked /
  _last_n_candidates / _last_p0_patch / _last_dir_decision）**零登记**。
  本文件补登记 = 让"注释里提到的消费方"变成"可机器核的清单"。
"""

from __future__ import annotations

#: ★ 消费点五元组（与 applier.TARGETS 同 schema — consumer/path/attr/verify）
#:   consumer — 谁读（人/模块/测试/文档）
#:   path    — 属性路径（宿主对象.属性）
#:   attr    — 属性名
#:   range   — 值域/口径（None 是合法输出 ⇒ 必须写进 range, 否则消费方
#:              会拿 None 当异常）
#:   verify  — 回读/校验方式（怎么确认真读到了）
CONSUME_POINTS: dict[str, dict[str, str]] = {
    # ── R170-R173 · 单轮闭环痕迹（Loop 侧 L4-L11）────────────
    "last_skip": {
        "consumer": "daemon 探针 / e2e 断言 / 人工巡查",
        "path": "dwc.harness.loop.Loop._last_skip",
        "attr": "_last_skip",
        "range": "Optional[str] — None=本轮无跳过（合法一等输出, 非异常）",
        "verify": "读回 isinstance(str) 或 None; 非 None 时必含冒号前的分类词",
    },
    "last_blocked": {
        "consumer": "e2e 断言 / gate 复盘",
        "path": "dwc.harness.loop.Loop._last_blocked",
        "attr": "_last_blocked",
        "range": "List[str] — [] = 无门拦（合法）; 'gate_all:no_gated' 等具名",
        "verify": "读回 list; 元素 ∈ 已知门名集合",
    },
    "last_n_candidates": {
        "consumer": "e2e / 回归统计",
        "path": "dwc.harness.loop.Loop._last_n_candidates",
        "attr": "_last_n_candidates",
        "range": "int ≥ 0 — 0 = 本轮无候选过层①（如实, 非 error）",
        "verify": "读回 int; 与 gated['gated'] 长度一致",
    },
    "last_p0_patch": {
        "consumer": "R173 固化面 / 人工巡查",
        "path": "dwc.harness.loop.Loop._last_p0_patch",
        "attr": "_last_p0_patch",
        "range": "str — 首提案的 patch 片段（空 = 无提案, 不写）",
        "verify": "读回能用作 trial 输入的片段文本",
    },
    # ── R176-R183 · Metric Loop 痕迹 ───────────────────────────
    "last_a_train": {
        "consumer": "select(pts, a_train=) / e2e / 人工巡查",
        "path": "dwc.harness.loop.Loop._last_a_train",
        "attr": "_last_a_train",
        "range": "Optional[float] ∈ [0,1] — None=缺席（fail-closed, 不是 0）",
        "verify": "读回 float 或 None; None 时 _last_a_train_why 必有原因",
    },
    "last_a_train_why": {
        "consumer": "人工巡查 / e2e 归因",
        "path": "dwc.harness.loop.Loop._last_a_train_why",
        "attr": "_last_a_train_why",
        "range": "Optional[str] — a_train 缺席/非退化时的原因串; ; None=该面缺席（合法一等输出）"
                 "None=本轮未跑 train 共识面",
        "verify": "a_train is None ⇒ why 非 None（G7 不静默纪律）",
    },
    "last_metric_pick": {
        "consumer": "_try_adopt_metric_tree / e2e / daemon 探针",
        "path": "dwc.harness.loop.Loop._last_metric_pick",
        "attr": "_last_metric_pick",
        "range": "Optional[dict] — picked_key/s/candidates/notes; None=缺席",
        "verify": "读回 dict 且 picked_key ∈ candidate 键集或 None",
    },
    "last_adopt": {
        "consumer": "人工巡查 / e2e 复盘",
        "path": "dwc.harness.loop.Loop._last_adopt",
        "attr": "_last_adopt",
        "range": "Optional[dict] — {adopted: bool, why: str, ...}; None=未尝试采纳",
        "verify": "读回 dict 且 'adopted' 键在场（bool）",
    },
    # ── R185 · planner 现场层痕迹 ─────────────────────────────
    "last_planner_trace": {
        "consumer": "人工巡查 / per-candidate 契约复盘",
        "path": "dwc.harness.loop.Loop._last_planner_trace",
        "attr": "_last_planner_trace",
        "range": "Optional[dict] — per_contract['planner_live'] 投影; None=层缺席",
        "verify": "读回 dict 或 None; 常驻 __init__（诚实字段, R185 修过 AttributeError）",
    },
    # ── R188-R189 · direction 台账痕迹 ────────────────────────
    "last_dir_decision": {
        "consumer": "人工巡查 / 方向选择复盘",
        "path": "dwc.harness.loop.Loop._last_dir_decision",
        "attr": "_last_dir_decision",
        "range": "Optional[DirectionDecision] — next_action 的最近输出; None=未跑方向选择",
        "verify": "读回含 direction/attempts 字段或 None",
    },
    "last_consolidation": {
        "consumer": "R173 固化面复盘 / 人工巡查",
        "path": "dwc.harness.loop.Loop._last_consolidation",
        "attr": "_last_consolidation",
        "range": "Optional[dict] — {key, outcome: consolidated/seed_noop/error, ; None=该面缺席（合法一等输出）"
                 "readback_ok} 或 None（未落地 ⇒ 不固化, None 合法）",
        "verify": "读回 dict 且 outcome ∈ {consolidated, seed_noop, error} 或 None",
    },
    "last_ledger_entries": {
        "consumer": "④ downstream 素材面 / 人工巡查",
        "path": "dwc.harness.loop.Loop._last_ledger_entries",
        "attr": "_last_ledger_entries",
        "range": "List[dict] — 本轮 credit 记账出口; [] = 本轮无记账（合法）",
        "verify": "读回 list; 元素为 res.credit_entries 的投影副本",
    },
    "last_replay_pick": {
        "consumer": "R174 replay 选择面复盘 / e2e",
        "path": "dwc.harness.loop.Loop._last_replay_pick",
        "attr": "_last_replay_pick",
        "range": "Optional[dict] — {v, shortlist, picked, argmax_score, no_worse}; None=该面缺席（合法一等输出）",
        "verify": "读回 dict 且 picked ∈ v 的键",
    },
    "last_floor_n": {
        "consumer": "EL 调度复盘 / e2e",
        "path": "dwc.harness.loop.Loop._last_floor_n",
        "attr": "_last_floor_n",
        "range": "Optional[int] — EL decide 的 floor(n) 值; None=未跑 EL",
        "verify": "读回 int 或 None",
    },
    "dir_attempts": {
        "consumer": "DirectionController 复盘 / 人工巡查",
        "path": "dwc.harness.loop.Loop._dir_attempts",
        "attr": "_dir_attempts",
        "range": "Dict[str, List[DirectionAttempt]] — {} = 本轮无方向尝试（合法）",
        "verify": "读回 dict; 值为 DirectionAttempt 序列（n_candidates 缺省 -1）",
    },
    "dir_ledger": {
        "consumer": "人工巡查 / 会计痕",
        "path": "dwc.harness.loop.Loop._dir_archive_path() → "
                "archive/direction_ledger.jsonl",
        "attr": "direction_ledger.jsonl",
        "range": "文件（jsonl 追加）— 每方向尝试一行; 空文件=从未触发（合法）",
        "verify": "读回文件每行可 json.loads 且含 gen/task/direction/n_candidates",
    },
}


def consume_point_names() -> list[str]:
    """登记键清单（排序 ⇒ 输出确定 — 测试可断言）。"""
    return sorted(CONSUME_POINTS)


def consumer_of(name: str) -> str | None:
    """键 ⇒ consumer（未登记 ⇒ None — 不猜）。"""
    p = CONSUME_POINTS.get(name)
    return p.get("consumer") if p else None


def declared_range(name: str) -> str | None:
    """键 ⇒ 声明的值域（消费方判 None 是否合法的机器依据）。"""
    p = CONSUME_POINTS.get(name)
    return p.get("range") if p else None


def undeclared(attrs: list[str]) -> list[str]:
    """给定 Loop 属性清单 ⇒ **未登记**的那些（G7: 漏登记要显式, 不静默）。"""
    return sorted(a for a in attrs if a not in CONSUME_POINTS)
