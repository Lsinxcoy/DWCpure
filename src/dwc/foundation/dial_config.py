# -*- coding: utf-8 -*-
"""world_tree.yaml / difficulty.yaml / dials.yaml 的加载器 + 校验器。

定位声明（DWC-MEM · 记忆底座 · 判据 G1 定位门）
  ★ 本模块是三份策略配置的加载器与校验器。能力组 / 收束策略 / 难度语义 /
    dial 档位 = "进化对象与判据口径的定义"，属记忆底座职责 ⇒ DWC-MEM。
  ★ 与 capability_groups 的分工:
      capability_groups —— 校验"能力组与源数据是否一致"（跨文件核对）
      本模块            —— 校验"枚举/必填/互斥是否成立"（文件内自洽）
  ★ 只读不写：任何违反都 raise DialError，绝不静默降级（判据 E2/E3）。

★★★ 存在理由
  R13 实测发现三处"设计说了、config 里没有"的字段（Z1/Z3、X1、M6）。
  本轮把它们落盘 —— 但**落盘不等于生效**：
  没有校验器的 yaml 只是一段文本，任何人改了都不会变红。
  ⇒ 这正是 R9 那条教训的延伸: 派生字段与枚举都必须被机器核对。
"""
from __future__ import annotations

import io
import os
from typing import Any, Dict

import yaml

ROOT = r"E:/Divine Wisdom Core"
CFG = os.path.join(ROOT, "config")

WORLD_TREE_PATH = os.path.join(CFG, "world_tree.yaml")
DIFFICULTY_PATH = os.path.join(CFG, "difficulty.yaml")
DIALS_PATH = os.path.join(CFG, "dials.yaml")


class DialError(Exception):
    """配置违反硬约束。★ 与 capability_groups.ConfigError 同款（承重代码不吞异常）。"""


def _load(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise DialError("配置不存在: %s" % path)
    obj = yaml.safe_load(io.open(path, encoding="utf-8").read())
    if not isinstance(obj, dict):
        raise DialError("配置顶层不是映射: %s" % path)
    return obj


def _need(obj: Dict[str, Any], key: str, where: str) -> Any:
    """★ 必填检查。★ 缺失必须 raise —— 不许给默认值（K4/G11/X1/Q1/M6 同款纪律）。"""
    if key not in obj or obj[key] is None:
        raise DialError("%s: 必填字段 %r 缺失或为 None" % (where, key))
    return obj[key]


# ══════════════════════════════════════════════════════════
# world_tree.yaml — 判据 Z1 / Z2 / Z3
# ══════════════════════════════════════════════════════════

STRATEGIES = {"ig_tree", "gepa_pareto"}
PARETO_DIMS = {"task", "task_group"}


def load_world_tree(path: str = WORLD_TREE_PATH) -> Dict[str, Any]:
    wt = _load(path)
    tree = _need(wt, "world_tree", "world_tree.yaml")

    # ── Z1 · strategy 必填且在枚举内 ──
    strategy = _need(tree, "strategy", "world_tree.world_tree")
    if strategy not in STRATEGIES:
        raise DialError("Z1: strategy=%r 不在 %s 内" % (strategy, sorted(STRATEGIES)))

    # ── Z3 · pareto_dim 必填且在枚举内 ──
    # ★ 即使当前 strategy=ig_tree 也必须写死 —— 否则将来切路线时静默退化
    dim = _need(tree, "pareto_dim", "world_tree.world_tree")
    if dim not in PARETO_DIMS:
        raise DialError("Z3: pareto_dim=%r 不在 %s 内" % (dim, sorted(PARETO_DIMS)))

    # ── Z2 · 若 strategy=gepa_pareto，必须校验 n_pareto_min ──
    n_min = _need(tree, "n_pareto_min", "world_tree.world_tree")
    if strategy == "gepa_pareto":
        # ★★ 2026-10-05 反向验证抓到: Z3 的 task_group 检查原先排在 Z2 之后。
        #   而 Z2 会先因"任务数不足"报错 ⇒ 于是 task_group 这条**永远轮不到**
        #   ⇒⇒ 若将来任务数真到 50+，那个致命错误就没人拦了
        #   ⇒⇒ 改法: Z3 的维度检查提到 Z2 之前（维度是**用法错误**，
        #     任务数是**前置条件**，用法错误应先报）
        if dim == "task_group":
            raise DialError(
                "Z3: 逐分组 Pareto 会让 Algorithm 2 退化为全局 argmax "
                "⇒ 正是 Figure 6a 的局部最优陷阱 ⇒ 禁止")
        n_tasks = _sealed_task_count()
        if n_tasks < int(n_min):
            raise DialError(
                "Z2: strategy=gepa_pareto 但 sealed 任务数 %d < n_pareto_min %d"
                % (n_tasks, n_min))

    # ── Z6 · 卡住检测必须配处置 ──
    stuck = _need(tree, "stuck", "world_tree.world_tree")
    _need(stuck, "n_stuck", "world_tree.world_tree.stuck")
    on_stuck = _need(stuck, "on_stuck", "world_tree.world_tree.stuck")
    if on_stuck not in {"switch_strategy", "halt"}:
        raise DialError("Z6: on_stuck=%r 不合法" % on_stuck)

    # ── Z4 · 候选必须持久化 + 记 lineage ──
    cand = _need(tree, "candidates", "world_tree.world_tree")
    if not _need(cand, "persist", "world_tree.world_tree.candidates"):
        raise DialError("Z4: candidates.persist 必须为 true（原文 'tracked'）")
    lineage = _need(cand, "lineage", "world_tree.world_tree.candidates")
    if lineage != "parent_id":
        raise DialError("Z4: candidates.lineage 必须是 parent_id，实为 %r" % lineage)

    # ── Z5 · merge 三条件 ──
    merge = _need(tree, "merge", "world_tree.world_tree")
    if not _need(merge, "require_all", "world_tree.world_tree.merge"):
        raise DialError("Z5: merge.require_all 必须为 true（三条件同时满足）")

    return wt


def _sealed_task_count() -> int:
    p = r"E:/ARSI/config/sealed_tasks.yaml"
    if not os.path.exists(p):
        raise DialError("sealed_tasks 不存在 ⇒ Z2 无法判定（不是『通过』）")
    obj = yaml.safe_load(io.open(p, encoding="utf-8").read())
    tasks = obj.get("tasks") if isinstance(obj, dict) else obj
    if not tasks:
        raise DialError("sealed_tasks 里没有 tasks ⇒ Z2 无法判定")
    return len(tasks)


# ══════════════════════════════════════════════════════════
# difficulty.yaml — 判据 X1 / X2 / X3
# ══════════════════════════════════════════════════════════

SEMANTICS = {"group_baseline", "world_knowledge"}


def load_difficulty(path: str = DIFFICULTY_PATH) -> Dict[str, Any]:
    d = _load(path)
    diff = _need(d, "difficulty", "difficulty.yaml")

    # ── X1 · semantics 必填无默认，且在枚举内 ──
    sem = _need(diff, "semantics", "difficulty.difficulty")
    if sem not in SEMANTICS:
        raise DialError("X1: semantics=%r 不在 %s 内（★ 别用字段名 residual）"
                        % (sem, sorted(SEMANTICS)))

    # ── X2 · n_obs=0 时必须 NaN，不许 0 ──
    nobs = _need(diff, "n_obs", "difficulty.difficulty")
    zero = _need(nobs, "zero_means", "difficulty.difficulty.n_obs")
    # ★★ 2026-10-05 反向验证抓到: 若 zero_means 写成 0（数字），
    #   原来的 `zero != "NaN"` 会短路成 False ⇒ 反而放行！⇒ 必须先查类型
    if not isinstance(zero, str):
        raise DialError(
            "X2: n_obs.zero_means 必须是字符串 'NaN'，实为 %r（类型 %s）"
            % (zero, type(zero).__name__))
    if zero != "NaN":
        raise DialError(
            "X2: n_obs.zero_means=%r ⇒ 『没观测过』与『观测到频率为 0』"
            "在数值上不可区分（同 C3' / Q5 纪律）" % zero)

    # ── X3 · 路线甲的写掩码约束不可放宽 ──
    dr = _need(diff, "deep_research", "difficulty.difficulty")
    enabled = _need(dr, "enabled", "difficulty.difficulty.deep_research")
    outside = _need(dr, "require_outside_write_mask",
                    "difficulty.difficulty.deep_research")
    if not outside:
        raise DialError(
            "X3: require_outside_write_mask 不可为 false —— "
            "deep-research 代理必须在写掩码之外（撞 G10 + GAI grounded 条件②）")
    # ★ 启用路线甲时，semantics 必须同步为 world_knowledge（否则 X4 会报不一致）
    if enabled and sem != "world_knowledge":
        raise DialError(
            "★ deep_research.enabled=true 但 semantics=%r —— "
            "启用路线甲时语义必须切到 world_knowledge，否则 X4 字段对不上" % sem)

    return d


# ══════════════════════════════════════════════════════════
# dials.yaml — 判据 M6
# ══════════════════════════════════════════════════════════

DIAL_BOOLS = ("m_in_agent", "rho_grounded", "rho_external_content",
              "rho_agent_can_rewrite")


def load_dials(path: str = DIALS_PATH) -> Dict[str, Any]:
    o = _load(path)
    dials = _need(o, "dials", "dials.yaml")

    # ── M6 · 四个布尔必须显式（逐个查，缺失即 raise）──
    for b in DIAL_BOOLS:
        if b not in dials:
            raise DialError("M6: dial %r 未显式声明（四布尔都必须有值）" % b)
        if not isinstance(dials[b], bool):
            raise DialError("M6: dial %r 必须是布尔，实为 %r" % (b, dials[b]))

    # ── 硬要求 · grounded 条件②（撞原则 1 就 raise）──
    if not dials["rho_grounded"]:
        raise DialError("dials: rho_grounded 必须为 true（GAI grounded 条件② + 原则 1）")
    if dials["rho_agent_can_rewrite"]:
        raise DialError(
            "dials: rho_agent_can_rewrite 必须为 false —— "
            "否则 evaluation base 落在 agent 可写面内 ⇒ 撞原则 1 ⇒ "
            "且撞 2607.12790 实测的『评估器塌缩成 always-pass』")

    # ── 快照字段必须与四布尔一致（防手改出不一致）──
    snap = _need(o, "snapshot_fields", "dials.yaml")
    if sorted(snap) != sorted(DIAL_BOOLS):
        raise DialError("snapshot_fields 必须正好是四个 dial，实为 %r" % (snap,))

    return o


# ══════════════════════════════════════════════════════════

def validate_all() -> Dict[str, Any]:
    return {
        "world_tree": load_world_tree(),
        "difficulty": load_difficulty(),
        "dials": load_dials(),
    }


if __name__ == "__main__":
    v = validate_all()
    wt = v["world_tree"]["world_tree"]
    df = v["difficulty"]["difficulty"]
    dl = v["dials"]["dials"]
    print("三份配置校验通过")
    print("  world_tree  strategy=%s pareto_dim=%s n_pareto_min=%s "
          "n_stuck=%s on_stuck=%s"
          % (wt["strategy"], wt["pareto_dim"], wt["n_pareto_min"],
             wt["stuck"]["n_stuck"], wt["stuck"]["on_stuck"]))
    print("  difficulty  semantics=%s deep_research.enabled=%s zero_means=%s"
          % (df["semantics"], df["deep_research"]["enabled"],
             df["n_obs"]["zero_means"]))
    print("  dials       " + " ".join("%s=%s" % (k, dl[k]) for k in DIAL_BOOLS))
    print("  Z2 自检: sealed=%d < n_pareto_min=%d ⇒ gepa_pareto 不可用（符合预期）"
          % (_sealed_task_count(), wt["n_pareto_min"]))