# -*- coding: utf-8 -*-
"""splitfeed · held_out 数据面 — 从 judge 真判产出 split 两份判分口径。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 服务 R159 留下的唯一缺口: split 门恒 na（accept 判 blocked 是因
    held_out 无判定口径）。本模块把 dev/test **两个真实 split**（judge
    TRUTH_SOURCE 已声明: dev.json 10 条 + test_sealed.json 9 条 + 互不
    相交）跑成两份判分 ⇒ accept 第一次能真判。
  ★ 不抢位: 不判单 task 对错（judge 的分）· 不判接受（accept 的分）;
    本模块只做**口径装配**（逐 task evaluate → 聚合成 in/ho 两份分）。
  ★★ held-in 口径裁决（**设计稿没规定 dev 内怎么切, 显式记录选择**）:
      方案 A: held_in=dev 全部, held_out=test_sealed 全部（最简 —
        但 in 与 ho 都是"全集", Δ_ho 测的是跨 split 泛化 ✓ 符合
        "held-in 与 held-out 两组"的原文语义）
      方案 B: dev 内再切 held-in/held-out（更细但样本本来就只有 10 条）
      ★ 取 A: ① 论文只要"两组不重叠" ② dev 再切会让两边都太小,
        judge 的 k/n 细粒度会被切碎到没有统计意义 ③ 实现最小（G4 不扩权）
  ★ "no part of metric evolution reads it" 的落地纪律（test 锁定原文）:
    test_sealed 只准由本模块在**候选评估时读**, 不准 proposer/变异器/
    规则学习读 —— 调用方传入的 callable 只决定"改哪个实现", 不许从
    test 的 golden 反推（防泄漏 — R147 门①的同族精神）。

★★★ TRUTH_SOURCE（判据 G2）
  · 单 task 判定 ← judge.evaluate（唯一判据源 — 本模块不自己比字符串）
  · 聚合 ← judge.overall_score（k/n 细粒度单源函数 — R54 起就在用的口径）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

#: 我们的 split 组合（裁决 A — 见 docstring; 值枚举, 不增第三组除非设计改）
HELD_IN_SPLIT = "dev"
HELD_OUT_SPLIT = "test"

#: test 锁定纪律（防泄漏 — 读 test 的**调用时序**声明, 不是能力限制）
TEST_LOCKED_NOTE = ("test_sealed 只准候选评估读（『no part of metric "
                    "evolution reads it』— 2607.12790 §2.2）")


class SplitFeedError(Exception):
    """口径装配的显式拒绝（判据源失效 / split 空 / 实现未给）。"""


@dataclass(frozen=True)
class SplitScores:
    """两份判分口径（evolver.accept 的直接输入 — 字段名与它对齐）。"""

    in_score: Optional[float]
    held_out_score: Optional[float]
    in_detail: Dict[str, Any] = field(default_factory=dict)
    held_out_detail: Dict[str, Any] = field(default_factory=dict)

    def as_accept_pair(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """★ 转 accept(baseline, current) 的一份（in_score/held_out_score）。"""
        return ({"in_score": self.in_score,
                 "held_out_score": self.held_out_score},
                {"in_score": self.in_score,
                 "held_out_score": self.held_out_score})


def _tasks_of(judge: Any, split: str) -> List[str]:
    """★ split 的任务清单（R160 核实: judge.anchors / judge.sealed 是真实属性）:
      · dev  ⇒ judge.anchors（Judge.__init__ L585 加载）
      · test ⇒ judge.sealed（L606: 文件存在即加载, 缺 ⇒ None ⇒ 空表）
    ★ 排除 `_` 前缀元键（_provenance/_split — 不是任务）。
    """
    src = judge.anchors if split == "dev" else getattr(judge, "sealed", None)
    if not isinstance(src, dict):
        return []
    return sorted(k for k in src if not k.startswith("_"))


def _aggregate(judge: Any, split: str, tasks: Sequence[str],
               run_impl: Callable[[str], Any]) -> Dict[str, Any]:
    """★ 单 split 聚合（逐 task: 跑实现 → judge.evaluate → 收 Verdict）。"""
    from dwc.organs.judge import overall_score

    verdicts = []
    for tid in tasks:
        try:
            # ★ R169: split 透传给 run_impl（双参 lambda 收; 单参 lambda
            #   走 TypeError 回落 — splitfeed 的调用方（e2e/loop）都是
            #   新双参形; 旧单参形向后兼容）
            try:
                out = run_impl(tid, split)
            except TypeError:
                out = run_impl(tid)                  # 旧形参 impl 兼容
            v = judge.evaluate(tid, split, observed=out)
        except Exception as exc:                     # noqa: BLE001 — 留痕不静默
            raise SplitFeedError(
                "task %r 在 split=%r 评估失败: %s: %s"
                % (tid, split, type(exc).__name__, exc))
        verdicts.append(v)
    ov = overall_score(verdicts)
    if ov is None:
        return {"score": None, "n": 0,
                "note": "全 task 未评价 ⇒ 缺席≠0（不造 0.0 冒充测过）"}
    return {"score": float(ov["score"]), "k": ov.get("k"), "n": ov.get("n"),
            "n_tasks": len(verdicts)}


def feed(judge: Any, run_impl: Callable[[str], Any], *,
         held_in_split: str = HELD_IN_SPLIT,
         held_out_split: str = HELD_OUT_SPLIT,
         tasks: Optional[Sequence[str]] = None) -> SplitScores:
    """★ 一份候选实现 ⇒ held-in/held-out 两份判分（accept 的弹药）。

    ★ run_impl(task_id) → observation：由调用方给（它持"改哪个实现"的
      上下文; 本模块不知道候选长什么样）。
    ★ tasks: **评估面限定**（本模块能判的子集 — R161 实测: e2e 演示集
      只实现了 4 个 code_fix task, 而 dev split 有 10 条 ⇒ 不编数据,
      显式收窄评估面并如实记账）; None = split 全量。
    ★ 缺哪个 split 的锚点 ⇒ 那个口径 None（不给 accept 假数据 — 它会
      因此判 blocked ⇒ 上层映射 na, 归因链完整）。
    """
    in_tasks = _tasks_of(judge, held_in_split)
    ho_tasks = _tasks_of(judge, held_out_split)
    if tasks is not None:
        _lim = set(tasks)
        in_tasks = [t for t in in_tasks if t in _lim]
        ho_tasks = [t for t in ho_tasks if t in _lim]
    if not in_tasks:
        raise SplitFeedError("held_in split=%r 无锚点任务 ⇒ 无 in 口径"
                             % (held_in_split,))
    in_d = _aggregate(judge, held_in_split, in_tasks, run_impl)
    ho_d: Dict[str, Any]
    if not ho_tasks:
        ho_d = {"score": None, "note": "held_out split=%r 无锚点 ⇒ ho 缺席"
                                      "（不拼 dev 副本 — 那让回归检测虚设）"
                                      % (held_out_split,)}
    else:
        ho_d = _aggregate(judge, held_out_split, ho_tasks, run_impl)
    return SplitScores(
        in_score=in_d.get("score"), held_out_score=ho_d.get("score"),
        in_detail=in_d, held_out_detail=ho_d)


def feed_pair(judge: Any, base_impl: Callable[[str], Any],
              cand_impl: Callable[[str], Any], *,
              tasks: Optional[Sequence[str]] = None, **kw: Any
              ) -> Tuple[Dict[str, float], Dict[str, float]]:
    """★★ baseline/current 两份 ⇒ accept(baseline, current) 的**一对**。

    ★ 这才是 R159 split 门缺的最后一环: accept 要两份判定口径, 本函数
      一次产齐（同一 judge 同一 split 组合 — 比较才同口径）。
    ★ tasks: 评估面限定（透传给两侧 feed — 两边限同一子集才有得比）。
    """
    b = feed(judge, base_impl, tasks=tasks, **kw)
    c = feed(judge, cand_impl, tasks=tasks, **kw)
    base = {"in_score": b.in_score, "held_out_score": b.held_out_score}
    cur = {"in_score": c.in_score, "held_out_score": c.held_out_score}
    for name, d in (("baseline", base), ("current", cur)):
        if d["in_score"] is None:
            raise SplitFeedError(
                "%s 的 in_score 缺席 ⇒ accept 无从比起（None≠0 — 不许"
                "拼 0.0 混入 Δ）" % (name,))
    return (base, cur)


SPLITFEED_MECHANICS: Dict[str, str] = {
    "split_combo": "held_in=dev(10 条) · held_out=test_sealed(9 条) — 两真实 split 互不相交",
    "why_not_split_dev": "设计稿未规定 dev 内切法; 取全集组合（A 案）: ①论文只要两组不重叠 ②dev 再切样本太小 k/n 无统计意义 ③实现最小",
    "test_lock": "test_sealed 只准候选评估读（no part of metric evolution reads it）— proposer/规则学习不许读",
    "absent_not_zero": "split 无锚点 ⇒ 口径 None（accept 判 blocked ⇒ 上层 na; 不造 0.0）",
    "same_judge_pair": "feed_pair 用同一 judge 同 split 组合产两份 ⇒ Δ 同口径可比",
}
