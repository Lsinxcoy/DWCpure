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
  R13 实测发现三处"设计说了、config 里没有"的字段（Z1/Z3、X1、M6）；
  R19 追加 D8 的 dead_after_terms（MEMORY_SYSTEM §六 Q2 已裁决按 term 计）。
  本轮把它们落盘 —— 但**落盘不等于生效**：
  没有校验器的 yaml 只是一段文本，任何人改了都不会变红。
  ⇒ 这正是 R9 那条教训的延伸: 派生字段与枚举都必须被机器核对。
"""
from __future__ import annotations

import io
import os
from typing import Any, Dict

import yaml

from dwc.foundation.paths import find_root
ROOT = find_root()
CFG = os.path.join(ROOT, "config")

WORLD_TREE_PATH = os.path.join(CFG, "world_tree.yaml")
DIFFICULTY_PATH = os.path.join(CFG, "difficulty.yaml")
REPLAY_PATH = os.path.join(CFG, "replay.yaml")
DIALS_PATH = os.path.join(CFG, "dials.yaml")
EVOLUTION_PATH = os.path.join(CFG, "evolution.yaml")


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

    # ── Z5 · merge 三条件 + 发生率日志 ──
    merge = _need(tree, "merge", "world_tree.world_tree")
    if not _need(merge, "require_all", "world_tree.world_tree.merge"):
        raise DialError("Z5: merge.require_all 必须为 true（三条件同时满足）")
    # ★ R68 补: log_rate 是 Z5 后半句（"merge occurs sparsely" ⇒ 必须记
    #   发生率）—— 原校验器漏了这个键, 与「全字段必填无默认」纪律不符
    _need(merge, "log_rate", "world_tree.world_tree.merge")

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
# replay.yaml — Dreaming 循环参数（R80 · 设计稿三裁决③）
# ══════════════════════════════════════════════════════════

def load_replay(path: str = REPLAY_PATH) -> Dict[str, Any]:
    """β₁/β₂ + ℋ 快照上限。

    ★ β 必填（R74 的「必传无默认」纪律在配置层的对应）—— 文件缺 β =
      DialError, 不许代码里编默认（论文未报值, NOISE_DELTA 的反面）。
    ★ β ≥ 0 = 论文符号约束; history_max ≥ 1。
    """
    o = _load(path)
    rep = _need(o, "replay", "replay.yaml")
    b1 = _need(rep, "beta1", "replay.replay")
    b2 = _need(rep, "beta2", "replay.replay")
    for name, b in (("beta1", b1), ("beta2", b2)):
        if not isinstance(b, (int, float)) or isinstance(b, bool) or b < 0:
            raise DialError(
                "R80: replay.%s 须为 ≥0 数值（论文符号约束 β≥0）, 实为 %r"
                % (name, b))
    hm = _need(rep, "history_max", "replay.replay")
    if not isinstance(hm, int) or isinstance(hm, bool) or hm < 1:
        raise DialError(
            "R80: replay.history_max 须为 ≥1 整数, 实为 %r" % (hm,))
    # ★ R252 · §5.2 effort 段必填（论文未报系数 ⇒ 无默认, β 同款纪律）
    ef = _need(rep, "effort", "replay.replay")
    eps = _need(ef, "plateau_eps", "replay.effort")
    fu = _need(ef, "factor_up", "replay.effort")
    fd = _need(ef, "factor_down", "replay.effort")
    lo = _need(ef, "lo", "replay.effort")
    hi = _need(ef, "hi", "replay.effort")
    if not isinstance(eps, (int, float)) or isinstance(eps, bool) or eps < 0:
        raise DialError("R252: effort.plateau_eps 须 ≥0 数值, 实为 %r" % (eps,))
    if not isinstance(fu, (int, float)) or isinstance(fu, bool) or fu <= 1:
        raise DialError("R252: effort.factor_up 须 >1, 实为 %r" % (fu,))
    if not isinstance(fd, (int, float)) or isinstance(fd, bool) \
            or not 0 < fd < 1:
        raise DialError("R252: effort.factor_down 须 ∈(0,1), 实为 %r" % (fd,))
    for name, v in (("lo", lo), ("hi", hi)):
        if not isinstance(v, int) or isinstance(v, bool) or v < 1:
            raise DialError("R252: effort.%s 须 ≥1 整数, 实为 %r" % (name, v))
    if hi < lo:
        raise DialError("R252: effort.hi=%r < lo=%r" % (hi, lo))
    return {"beta1": float(b1), "beta2": float(b2), "history_max": hm,
            "effort": {"plateau_eps": float(eps), "factor_up": float(fu),
                       "factor_down": float(fd), "lo": lo, "hi": hi}}


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
# drift.yaml — 环节⑤ 防漂移的档位（iwm.drift 的配置面）
# ══════════════════════════════════════════════════════════

DRIFT_PATH = os.path.join(CFG, "drift.yaml")
DRIFT_WEIGHT_KEYS = ("semantic", "lexical", "structural", "distributional")


def load_drift(path: str = DRIFT_PATH) -> Dict[str, Any]:
    """环节⑤ 的档位校验（GDI 权重 / tau / CAR 下限 / self_trust 下限）。

    ★ 与 load_world_tree 同款纪律: 必填、无默认、可审计 ——
      「没有校验器的 yaml 只是一段文本」。
    ★ 权重和 Σ==1（Eq.13），缺席信号由 drift() 在运行期归一（不改本文件）。
    """
    o = _load(path)
    d = _need(o, "drift", "drift.yaml")

    # ── 四权重必填 + 数值 + Σ=1（Eq.12–13）──
    w = _need(d, "weights", "drift.drift")
    total = 0.0
    for k in DRIFT_WEIGHT_KEYS:
        if k not in w:
            raise DialError("drift: weights.%s 未显式声明（四信号权重必填）" % k)
        v = w[k]
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not (0.0 <= float(v) <= 1.0):
            raise DialError("drift: weights.%s 必须 ∈ [0,1], 实为 %r" % (k, v))
        total += float(v)
    extra = set(w) - set(DRIFT_WEIGHT_KEYS)
    if extra:
        raise DialError("drift: weights 有未知键 %s（四信号之外的权重没有出处）"
                        % sorted(extra))
    if abs(total - 1.0) > 1e-9:
        raise DialError("drift: Σweights = %.6f ≠ 1（Eq.13 硬约束）" % total)

    # ── tau_gdi ∈ (0, 1] ──
    tau = _need(d, "tau_gdi", "drift.drift")
    if isinstance(tau, bool) or not isinstance(tau, (int, float)) or not (0.0 < float(tau) <= 1.0):
        raise DialError("drift: tau_gdi 必须 ∈ (0,1], 实为 %r" % tau)

    # ── car_floor 数值（E.3: 负 CAR = drift without improvement ⇒ 停）──
    cf = _need(d, "car_floor", "drift.drift")
    if isinstance(cf, bool) or not isinstance(cf, (int, float)):
        raise DialError("drift: car_floor 必须是数值, 实为 %r" % cf)

    # ── self_trust（ARSI calibrate: degrade_below / min_samples）──
    db = _need(d, "degrade_below", "drift.drift")
    if isinstance(db, bool) or not isinstance(db, (int, float)) or not (0.0 <= float(db) <= 1.0):
        raise DialError("drift: degrade_below 必须 ∈ [0,1], 实为 %r" % db)
    ms = _need(d, "min_samples", "drift.drift")
    if isinstance(ms, bool) or not isinstance(ms, int) or ms < 1:
        raise DialError("drift: min_samples 必须是 >=1 的整数, 实为 %r" % ms)

    # ── R215 · trust_window（Layer 22 判据校准: 全历史 trust 在永久降级
    #   策略下是自锁 —— 采纳降级⇒无改进⇒trust 恒 0⇒永久降级。ARSI 语义应为
    #   **近期样本**: trust 只看窗口内 iwm 臂）──
    tw = _need(d, "trust_window", "drift.drift")
    if isinstance(tw, bool) or not isinstance(tw, int) or tw < 1:
        raise DialError("drift: trust_window 必须是 >=1 的整数, 实为 %r" % tw)

    # ── R232 · bench 预测式选择（评测层 — 不碰世界树任务源层）──
    bench = _need(d, "bench", "drift.drift")
    if not isinstance(bench, dict):
        raise DialError("drift.bench 须为映射, 实为 %r" % type(bench).__name__)
    lam = _need(bench, "explore_lambda", "drift.bench")
    if isinstance(lam, bool) or not isinstance(lam, (int, float)) or lam < 0:
        raise DialError("drift.bench.explore_lambda 须为 >=0 的数, 实为 %r" % lam)
    sm = _need(bench, "select_mode", "drift.bench")
    if sm not in ("auto", "full"):
        raise DialError("drift.bench.select_mode ∈ {auto, full}, 实为 %r" % sm)

    return o


# ══════════════════════════════════════════════════════════
# retention.yaml — 判据 D8（机制零引用即违规）
# ══════════════════════════════════════════════════════════

RETENTION_PATH = os.path.join(CFG, "retention.yaml")

_DEAD_ACTIONS = {"hold", "evict"}
_ZERO_REF_CLASSES = {"zero", "not_zero_reference"}


def load_retention(path: str = RETENTION_PATH) -> Dict[str, Any]:
    """判据 D8 的配置面。★ 2026-10-05 MEMORY_SYSTEM §六 Q2 裁决后新增。

    ★★★ 关键语义: dead_after_terms 的单位是 **term** 不是 step。
      依据: ARCHITECTURE 原则 8 原文「N 应由 term 边界推导，
      而不是拍一个固定轮数」⇒ 固定轮数（10/20）两个旧选项都违反该原则。
    """
    r = _load(path)
    ret = _need(r, "retention", "retention.yaml")

    # ── D8 · 必填无默认 ──
    n = _need(ret, "dead_after_terms", "retention.retention")
    if not isinstance(n, int) or n < 1:
        raise DialError(
            "D8: dead_after_terms 必须是 >=1 的整数，实为 %r（类型 %s）"
            % (n, type(n).__name__))

    # ── 零引用的判据口径（ARCHITECTURE 原则 8 的"严格口径"）──
    zr = _need(ret, "zero_reference", "retention.retention")
    for f in ("require_import_zero", "require_invoke_zero"):
        if not isinstance(_need(zr, f, "retention.retention.zero_reference"), bool):
            raise DialError("D8: zero_reference.%s 必须是布尔" % f)
    cls = _need(zr, "tests_only_is", "retention.retention.zero_reference")
    if cls not in _ZERO_REF_CLASSES:
        raise DialError(
            "D8: zero_reference.tests_only_is=%r 不在 %r 内"
            % (cls, sorted(_ZERO_REF_CLASSES)))
    # ★★ 判据口径的硬要求: 两个都必须为 0 才算零引用
    #   （依据 ARCHITECTURE 原则 8 原文「import 次数 = 0 **且** invoke 次数 = 0」）
    if not (zr["require_import_zero"] and zr["require_invoke_zero"]):
        raise DialError(
            "D8: 零引用的判据口径是 import==0 **且** invoke==0"
            "（ARCHITECTURE 原则 8 原文）⇒ 两者都必须是必检项")

    # ── 记忆三层判据（MEMORY_SYSTEM §三，顺序不可换）──
    mem = _need(ret, "memory", "retention.retention")
    for f, allowed in (("never_recalled", {"hold", "evict"}),
                       ("never_changed_behavior", {"hold", "candidate"}),
                       ("rare_signature", {"protect", "evict"})):
        v = _need(mem, f, "retention.retention.memory")
        if v not in allowed:
            raise DialError(
                "D8: memory.%s=%r 不在 %s 内" % (f, v, sorted(allowed)))
    # ★★★ 第1层的语义硬要求: 未召回的记忆不许直接淘汰
    #   依据 MEMORY_SYSTEM §三「未召回 ⇒ 进未验证区，**不淘汰**
    #   （可能是检索策略问题）」—— 简掉这层就会误杀检索策略没覆盖到的记忆
    if mem["never_recalled"] != "hold":
        raise DialError(
            "D8: memory.never_recalled 必须是 hold —— "
            "『未召回 ≠ 淘汰，���能是检索策略问题』（MEMORY_SYSTEM §三）")
    # ★★★ 稀有保护必须保持 protect（2026-10-05 Q3 裁决）
    #   原校验只查了枚举值 ⇒ 把 protect 改成 evict 能过 ⇒ 裁决与代码不一致
    #   ⇒★ 依据 MEMORY_SYSTEM §三:「淘汰前必须过稀有保护:
    #     若该记忆是某类失败的唯一签名 ⇒ **不淘汰**」—— 它是硬否决
    if mem["rare_signature"] != "protect":
        raise DialError(
            "D8: memory.rare_signature 必须是 protect —— "
            "『某类失败的唯一签名 ⇒ 不淘汰』是硬否决（MEMORY_SYSTEM §三），"
            "不是可调档位（Q3 裁决: 照用三层判据）")
    if not _need(mem, "order_fixed", "retention.retention.memory"):
        raise DialError(
            "D8: memory.order_fixed 必须为 true —— 三层判据的顺序不可换")

    # ── 门检配置 ──
    g = _need(ret, "gate", "retention.retention")
    if not isinstance(_need(g, "report_on_zero_reference",
                            "retention.retention.gate"), bool):
        raise DialError("D8: gate.report_on_zero_reference 必须是布尔")
    if not _need(g, "require_evidence", "retention.retention.gate"):
        raise DialError(
            "D8: gate.require_evidence 不可为 false —— "
            "判零引用必须能事后核『为什么判它死』（母巢教训: 只有结论没证据）")

    return r

# ══════════════════════════════════════════════════════════
# evolution.yaml — R370 · B2 进化喂食灰度开关
# ══════════════════════════════════════════════════════════

def load_evolution(path: str = EVOLUTION_PATH) -> Dict[str, Any]:
    """run_term 结束后是否把失败签名喂给 evolver.diagnose。

    ★ 两个键都必填无默认（灰度纪律: 默认关这件事必须写在文件里，
      不许代码里 `get(..., False)` 悄悄兜底 —— 兜底会让「配置文件缺失」
      和「显式关闭」变得不可区分）。
    """
    o = _load(path)
    ev = _need(o, "evolution", "evolution.yaml")
    feed = _need(ev, "feed_from_terms", "evolution.evolution")
    if not isinstance(feed, bool):
        raise DialError(
            "R370: evolution.feed_from_terms 须为 bool, 实为 %r" % (feed,))
    mx = _need(ev, "max_sigs_per_term", "evolution.evolution")
    if not isinstance(mx, int) or isinstance(mx, bool) or mx < 1:
        raise DialError(
            "R370: evolution.max_sigs_per_term 须为 ≥1 整数, 实为 %r" % (mx,))
    # ★ R438 · 自动落地开关（必填无默认 —— 同 feed 的理由：缺键与"显式关闭"
    #   必须可区分；代码里 `get(..., False)` 兜底会让配置缺失静默变成关）
    auto = _need(ev, "auto_apply", "evolution.evolution")
    if not isinstance(auto, bool):
        raise DialError(
            "R438: evolution.auto_apply 须为 bool, 实为 %r" % (auto,))
    cap = _need(ev, "auto_apply_max_per_round", "evolution.evolution")
    if not isinstance(cap, int) or isinstance(cap, bool) or cap < 1:
        raise DialError(
            "R438: evolution.auto_apply_max_per_round 须为 ≥1 整数, 实为 %r"
            % (cap,))
    return {"feed_from_terms": feed, "max_sigs_per_term": mx,
            "auto_apply": auto, "auto_apply_max_per_round": cap}


# ══════════════════════════════════════════════════════════

def validate_all() -> Dict[str, Any]:
    return {
        "world_tree": load_world_tree(),
        "difficulty": load_difficulty(),
        "dials": load_dials(),
        "retention": load_retention(),
        "evolution": load_evolution(),
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
    rt = v["retention"]["retention"]
    print("  retention  dead_after_terms=%s（单位=term 非 step）· "
          "tests_only_is=%s"
          % (rt["dead_after_terms"],
             rt["zero_reference"]["tests_only_is"]))
    print("  Z2 自检: sealed=%d < n_pareto_min=%d ⇒ gepa_pareto 不可用（符合预期）"
          % (_sealed_task_count(), wt["n_pareto_min"]))