# -*- coding: utf-8 -*-
"""direction · 进化三方向 FORWARD/LATERAL/REVERSE（器官⑥ 探索 · Prometheus-Y）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 服务环节⑥ 探索与进化链的**方向选择**，不碰记忆读写 ⇒ 非 DWC-MEM。
  ★ 不抢位: 不声明 REPLACES。

=== 出处（EVOLUTION_CORE_V2 §8.3 · ALL_REPOS_EVOLUTION_DESIGN §六/结论2）===
  EvolutionDirection.FORWARD   前进 (在现有基础上改进)
  EvolutionDirection.LATERAL   横向 (换一个方向试)
  EvolutionDirection.REVERSE   后退 (回退到更简单的方案)

  ★ 39 仓库实测: **只有 Prometheus-Y / Omega 两个有"方向"概念**（39 仓进化矩阵
    实测 —— 本机 Prometheus-Omega 源码已 grep 无 EvolutionDirection 残留,
    以 ALL_REPOS 的 39 仓分析记录为权威实测）。
  ★ **三种是校正后口径**: DEDUP_AUDIT_6SYSTEMS L254「本轮实测方向只有 3 种,
    旧报告写 4 种是错的」—— 所以本模块**锁 3**, 第 4 个成员是历史错误。

=== 链位（ALL_REPOS 结论 2 的互补链, 方向是**第一环**）===
  方向选择 (Y) → 门 (ARSI) → 形式化验证 (MSTAR) → 落地 (MSTAR rollback)
    → 固化 (Z)
  ⇒ 方向选择发生在**门之前**（提案/展开的头）—— 这是本模块将来的接线位,
    具体接谁由设计裁决（见模块尾诚实边界）。

=== 辨析（设计原文, 别混）===
  ★ 三方向 **≠** 2609.04128 的 length/scenario/skill —— 后者是「难度方向的
    分解」（残差难度的三个分量）, 三方向是**进化操作的方向性**。
  ★ 三方向 **≠** 世界树收束（WORLD_TREE 系设计对方向零提及 —— 已 grep 核实;
    select 只吃信息增益 W4, 与方向无关）。
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple


class EvolutionDirection(str, Enum):
    """三方向（值枚举 —— G11 同款: 值域固定, 不许静默加第四个）。

    ★ str 混合: 与 "FORWARD" 直等、可直接 json 序列化（提案/日志携带）。
    ★ 三语义逐字来自设计（EVOLUTION §8.3 / ALL_REPOS §六）——
      改语义必须改 SEMANTICS 表, 不许只改注释（名字与实现对齐）。
    """

    FORWARD = "FORWARD"   # 前进 (在现有基础上改进)
    LATERAL = "LATERAL"   # 横向 (换一个方向试)
    REVERSE = "REVERSE"   # 后退 (回退到更简单的方案)


#: 语义表 —— 与枚举**同处存放**（两处漂移就违反"名字与实现对齐"）
SEMANTICS: Dict[EvolutionDirection, str] = {
    EvolutionDirection.FORWARD: "前进 (在现有基础上改进)",
    EvolutionDirection.LATERAL: "横向 (换一个方向试)",
    EvolutionDirection.REVERSE: "后退 (回退到更简单的方案)",
}

# ════════════════════════════════════════════════════════════════════
# ★★★ R191 · REVERSE 语义**辨析**（用户令"深度思考REVERSE属于哪个类型"后裁决）
#
#   裁决: REVERSE = **类型一「简化 target（提案侧）」**;
#        「回退到更弱验收（类型二）」在 DWC **禁行**。
#
#   为什么类型二禁行（机器可判的三条, 不是品味）:
#     ① G2 判据在系统外 — TRUTH_SOURCE=config/anchors/*.json; R189-B 刚把
#        "train 带 label ⇒ raise" 焊死。降 verifier_rung / 改 checks 是
#        同一个洞的另一个入口（数据面→强度面）, 不许从旁门绕过。
#     ② 门⑥账本只认"落地了" — 松标准 +1 分 = 奖励放水 = fake-success 形态,
#        污染 fitness。
#     ③ R184/R161 的 split 分离纪律 — 验收标准不可被进化面改写; 否则 e2e
#        数字仍好看, 但不再意味着同一件事。
#
#   本地库论文反例（2603.25111 · FGGM 的 f_d fallback, 门②同源）:
#     原话 "f_d 可能缺乏 GM 的解题能力（低任务性能）, 它阻止候选 agent
#           进入不安全的程序状态（高约束满足）"
#     实例 boundedParam: f_d(l,u,y)=min(max(l,y),u)（clamp）
#     ⇒ "退一步"退的是**能力**（提案侧 target）, 契约 Φ_l/Ψ_l 一步不让
#     ⇒ 论文性质② Parameter-Independent Correctness: 契约对任意 θ 成立
#     ⇒ 照类型二做 = 让拒绝采样器自己改验收公式 = 反对该论文的全部意义
#
#   诚实的现状面（R188 实测 + R191 摊开 RULES 复核）:
#     RULES 7 条（prompt×4 / control_flow×3）无一条是"更简单"类
#       · prompt 答案写短 = 丢关键词 ⇒ keyword_match 必 fail（无收益）
#       · 代码修法只有对/错（range(n)↔range(n+1) 无"半对"中间态）
#       · 同 component 备选修法已在 R173 LATERAL（propose_lateral）里
#     ⇒ 本面 REVERSE 实际可行度 0 = **如实 []**, 不是缺陷、不是 backlog。
#     硬造候选 = 为填满三方向而生成注定 fail 的 patch ⇒ 违反 R188
#     "None 是合法结果"纪律。
# ════════════════════════════════════════════════════════════════════
#: ★★★ R191 · REVERSE 辨析的**机器可读**形态（语义声明, 不是第二份语义 —
#:   与 SEMANTICS 同存同源: 只回答"REVERSE 允许动什么/禁止动什么"）。
REVERSE_SCOPE: Dict[str, object] = {
    #: 允许动的一侧（提案侧 — 能力的退一步, 2603.25111 的 f_d 形状）
    "allowed": ("target", "patch", "proposal"),
    #: 禁止动的一侧（判据侧 — G2/门⑥账本/split 三条纪律）
    "forbidden": ("verifier_rung", "checks", "anchor", "acceptance",
                  "threshold", "golden", "split"),
}

#: 方向总数 —— 锁 3（DEDUP L254: 旧报告的 4 种是错的, 3 是校正后口径）
N_DIRECTIONS = 3


class DirectionError(Exception):
    """方向值违规必须大声报错（G7 静默门同族）。"""


def ensure_direction(value) -> EvolutionDirection:
    """值 → EvolutionDirection（★ 精确值枚举, 拒一切外来形态）。

    ★ 拒: None（"无方向"不是第四方向 —— 没想清楚要显式说, 不许拿 None
      冒充）、大小写变体（"forward" ≠ "FORWARD" —— 值枚举精确匹配,
      猜着兼容就等于把漂移放进来）、未知值。
    """
    if isinstance(value, EvolutionDirection):
        return value
    if value is None:
        raise DirectionError(
            "方向缺失 —— None **不是**第四方向: 提案没定方向时必须显式 "
            "三选一, 不许 None 冒充「未标注」")
    if isinstance(value, str):
        for d in EvolutionDirection:
            if value == d.value:        # ★ 精确 ==, 不做 casefold
                return d
    raise DirectionError(
        "方向值 %r 不在 %r 内（值枚举精确匹配 —— 大小写变体也拒）"
        % (value, [d.value for d in EvolutionDirection]))


def semantics_of(value) -> str:
    """方向 → 逐字语义（查表, 语义只有一份真源 SEMANTICS）。"""
    return SEMANTICS[ensure_direction(value)]


# ══════════════════════════════════════════════════════════
# ★★★ R188 · DirectionController（R186 搜论文 → R187 A×B 收敛分析 → 本件）
#   选择策略的三条规则（每条论文出处, 全部纯函数可单测）:
#     R1 停滞即换    — EvoTS 2608.17933 原文: "invalid or its improvement
#                     is no greater than a threshold"
#     R2 序内 fallback — 2609.04128 §5.5 原文: "randomly order the three
#                     directions ... fall back to the next direction"
#     R3 全败记账终止 — 同原文 "The branch terminates only when all three
#                     directions fail" + DWC 纪律「None 是合法结果」
#   ★ A×B 收敛（R187）: A(何时换向)=next_action 的**输入**（state）,
#     B(向哪里换)=next_action 的**输出**（direction+candidate）——
#     二者在 pick_direction 的同一决策点汇合, 不再分时/空两件。
# ══════════════════════════════════════════════════════════

#: 噪声带（R185 同源 — score 增益 ≤ 该值视为无增益, 不是"变小了"）
NOISE_BAND = 0.01

#: REVERSE「更简单」代理判据的 patch 长度上限（字符 — 表达式片段口径）
REVERSE_MAX_PATCH = 16

#: 视为「无效」的链判（EvoTS 的 invalid — 门拦/出错都算, idle 不算:
#   idle 是本方向没有可试对象, 归 R3 的 n_candidates==0 分支）
INVALID_VERDICTS = frozenset({"blocked", "error"})


@dataclass(frozen=True)
class DirectionAttempt:
    """一次方向尝试的记录（时间面的最小单位 — R188 R1 的判据输入）。

    ★ 全部字段可从 Loop 现有量构造（不发明新事实源）:
      direction  — ensure_direction 校验过的三方向之一
      stagnant   — 调用方判 or 由 stagnant_of() 从下面三字段推
      score_gain — None = 无前值（首试）; DWC 现有 score 序列可算
      verdict    — Loop 现有 chain_verdict 原值（blocked/error/...）
      n_candidates — 该方向真生成的候选数（0 = unfixable_now）
    """
    direction: EvolutionDirection
    score_gain: Optional[float] = None
    verdict: Optional[str] = None
    #: -1 = 未填（**不是** 0）—— 0 是"真跑了但一个候选都没出",
    #: 语义不同必须分开（实测: 首版默认 0 让"未填"被误判形态③,
    #: 首试直接判停滞 ⇒ fallback 链错乱 — R188 smoke 抓到）
    n_candidates: int = -1
    note: str = ""

    def is_invalid(self) -> bool:
        """EvoTS 'invalid' — 链判 in INVALID_VERDICTS。

        ★ verdict None（还没判）⇒ False（没信息不下判 — fail-closed 到
          「非无效」而不是「猜它无效」—— 宁可多试一次方向）
        """
        return (self.verdict or "") in INVALID_VERDICTS

    def _gain_in_band(self) -> bool:
        """增益落入噪声带 ⇒ 视为无增益（R185 同源口径）。

        ★ gain None ⇒ False（首试无前值, 没有"没增益"这回事）
        ★ 负增益 ⇒ True（真的退步 — 比停滞更强的换向信号）
        """
        return self.score_gain is not None and self.score_gain <= NOISE_BAND

    def has_no_candidate(self) -> bool:
        """本方向一个候选都生成不出（无对象可换 — R1 的第三种形态）。

        ★ **只有显式填过**（>= 0）才算 —— 未填（-1）是"没信息",
          不下的判据（fail-closed: 宁可多试一次方向, 不猜它停滞）。
        """
        return self.n_candidates == 0


@dataclass(frozen=True)
class DirectionDecision:
    """next_action 的输出（空间面的最小单位 — A×B 收敛的汇合点）。"""
    direction: EvolutionDirection
    reason: str
    order: Tuple[EvolutionDirection, ...] = ()
    n_tried: int = 0


def fallback_order(round_no: int, task_id: str = "") ->         Tuple[EvolutionDirection, ...]:
    """R2 · 三方向的尝试**全序**（04128 "randomly order" 的 DWC 实例化）。

    ★ 不用真随机: 以 sha256(f"{round_no}|{task_id}") 派生确定性全序 ——
      04128 要的是 vary（别每轮同序 ⇒ 卡死在同一首发方向）,
      DWC 纪律要的是可复现（同 round 同 task ⇒ 同序, 便于跨会话重放审判）。
    ★ 三方向全在内（锁 3 — 不因"某个方向没候选"就从序里删掉:
      删了就等于提前宣布它败了, 而它可能只是本轮没有对象。）
    """
    # G1/G7: round_no 必须是 int（None/"1" 都不猜着 stringify —
    #   试跑不可复现比炸更贵; DWC 全链 round_no 都是 int）
    if isinstance(round_no, bool) or not isinstance(round_no, int):
        raise DirectionError(
            "round_no 必须是 int, 实为 %r（别拿字符串化兜底 — 会静默"
            "产生不可复现的序）" % (round_no,))
    if not isinstance(task_id, str):
        raise DirectionError(
            "task_id 必须是 str, 实为 %r" % (task_id,))
    seed = hashlib.sha256(
        ("%s|%s" % (round_no, task_id)).encode("utf-8")).hexdigest()
    dirs = [d for d in EvolutionDirection]           # 枚举序 = 稳定打底
    # 确定性洗牌: seed 重复分组 — 每个方向取一段 hash, 按 (段, 枚举位) 排序
    return tuple(sorted(
        dirs,
        key=lambda d: (seed[(_vi := dirs.index(d)) * 8:(_vi + 1) * 8],
                       dirs.index(d))))


def stagnant_of(attempt: DirectionAttempt) -> bool:
    """R1 · 一次尝试是否「停滞」（EvoTS 判据的 DWC 三态映射）。

    ★ 三种形态任一成立 ⇒ 停滞（换向信号）:
      ① invalid            — verdict ∈ {blocked, error}
      ② gain ≤ NOISE_BAND  — 有效果但不够看（或退步）
      ③ n_candidates == 0  — 无对象可试（unfixable_now 的一等输出）
    ★ 三者全不成立 ⇒ False —— 包括**首试**（gain None ⇒ 不下"无增益"判）
    """
    return (attempt.is_invalid()
            or attempt._gain_in_band()
            or attempt.has_no_candidate())


def next_action(state: Sequence[DirectionAttempt],
                round_no: int = 0, task_id: str = "") -> DirectionDecision:
    """R1+R2 · 沿 fallback 序找第一个未试过的方向 ⇒ 决策。

    ★ 已试过 = state 里已有非停滞尝试的方向（停滞过的方向**不进**本
      集合 — 04128 的语义: 当前方向失败就 fall back 到下一个, 不回头。
      ⇒⇒ ⇒**链不回退**: once stagnant, 该方向本轮不再选。
    ★ 全序耗尽 ⇒ 抛 DirectionError（R3 的记账触发条件在调用方:
      上游拿 terminal 记台账 + unfixable_now, 不造第四方向）。
    """
    order = fallback_order(round_no, task_id)
    # 04128 原文 "fall back to the next direction" — **链不回退**:
    # 停滞过的方向本轮不再选 ⇒ 已试集合 = **全部**试过的（含停滞的）;
    # 实测 smoke（首版只排除"未停滞的"）⇒ 停滞的首发方向又被选中,
    # fallback 死循环 — R188 抓到
    tried_all = {a.direction for a in state}
    for d in order:
        if d not in tried_all:
            return DirectionDecision(
                direction=d,
                reason=("fallback_order[%d]=%s（已试 %d 个方向后选未试的）"
                        % (order.index(d), d.value, len(tried_all))),
                order=order, n_tried=len(state))
    raise DirectionError(
        "三方向全试过且均停滞 ⇒ terminal（R3: 全败记账, 不造第四方向）"
        " tried=%r" % ([a.direction.value for a in state],))


def reverse_candidates(rules_index: Optional[Dict[str, Dict]] = None,
                       component: str = "") -> List[str]:
    """R3 的 REVERSE 半边 · **表驱动**候选键（不是候选本身 — 候选由
    evolver 产, 本函数只回答"回退方向可试哪些 target"）。

    ★ 设计语义（EVOLUTION §8.3 逐字）: 「回退到更简单的方案」——在 DWC
      的形态 = 同 component 的 target 中, 存在**比当前更简单**的规则
      （更小 patch / 更少约束 / 保留更少）。判据用 patch 长度的字典序,
      可复现无魔法。
    ★★★ 诚实边界: RULES 现有 7 条**无一条**是"更简单"类的（修法全是
      补全/追加 — 都是向前的）⇒ 本函数当前如实返回 []。**这不是缺陷**:
      没有更简单的修法可回退时, REVERSE 无对象 = R1 形态③（n_candidates
      == 0）⇒ 上游记台账。将来 RULES 增长出简化类 target 时, 这里是
      **唯一登记点**（不在别处硬编码）。
    """
    rules = dict(rules_index or {})
    if not component:
        return []
    # ★★★ R191 · 类型二防御（禁行判据侧降阶）: 调用方若把"降 verifier_rung /
    #   改 checks / 动 golden"这类**判据侧**条目塞进 rules_index 想让 REVERSE
    #   挑 ⇒ 大声报错, 不静默返候选（REVERSE 只允许动提案侧 target/patch）。
    #   ⇒ 与 G2（判据在系统外）/ R189-B（train 带 label ⇒ raise）同族。
    for key, rule in sorted(rules.items()):
        if not isinstance(rule, dict):
            continue
        leaked = sorted(set(REVERSE_SCOPE["forbidden"]) & set(rule))
        if leaked:
            raise DirectionError(
                "RULES %r 带了判据侧字段 %r ⇒ REVERSE 禁行类型二"
                "（回退到更弱验收 — 通不过 G2 判据在系统外 / 门⑥账本只认"
                "「落地了」/ split 分离纪律; 依据 2603.25111 性质②: 契约对"
                "任意 θ 成立, 2603.25111 的 f_d 退的是能力不是契约）"
                % (key, leaked))
    simplifiable = []
    for key, rule in sorted(rules.items()):      # 排序 ⇒ 输出确定
        if not isinstance(rule, dict):
            continue
        if rule.get("component") != component:
            continue
        patch_text = str(rule.get("patch", "") or "")
        # 「更简单」的代理 = patch 短（≤ REVERSE_MAX_PATCH 字符）——
        # patch 是**表达式片段**（RULES 口径）: 短 = 改动面窄 = 简单。
        # 完整 DTC（diff tree complexity）不在 DWC 判据面内 ⇒ 如实标
        # 长度代理, 不冒充复杂度度量
        if patch_text and len(patch_text.strip()) <= REVERSE_MAX_PATCH:
            simplifiable.append("%s|%s" % (key, patch_text.strip()))
    return simplifiable


# ══════════════════════════════════════════════════════════
# 诚实边界（R73 的范围, 别把「枚举在」当「选择在」）
# ══════════════════════════════════════════════════════════
# ★ 已做: 三方向枚举（锁 3）· 逐字语义表（同处防漂移）· 值枚举校验
#         （ensure_direction 精确匹配拒 None/大小写/未知）· 链位声明
#         · 与 length/scenario/skill 的辨析
# ★ 未做（**设计未给, 不发明**）:
#   · **选择策略** —— 设计只给三方向与语义, **没给"何时选哪个"的判据**
#     （EVOLUTION §8.3 / ALL_REPOS §六/结论2 全文已核, 零策略描述）
#     ⇒ 本模块不自造策略; 有据的只有链位（方向选择在门之前）
#   · **消费接线** —— 谁带 direction 字段（evolver 提案 / 探索展开 / …）
#     设计未裁决 ⇒ 不顺手改已有接口（add 方向字段=行为面变更）
#   · ★ 候选接线观察（**我的实例化, 未接未复核**）: world_tree.yaml 的
#     `stuck.on_stuck: switch_strategy`（换策略）语义近似 LATERAL、
#     「回退更简单」近似 REVERSE —— 若将来裁决联动, 这是第一落点
#   · ★ ⑥ search/ 组件树是**四件**（weakness / el_sched / replay / direction
#     —— EVOLUTION 树 L656-660 实数）: 本轮落 direction, **replay.py
#     （回放仿真器, 2609.14858, 候选集含 current）仍未做**
#     —— 此前口头说「器官⑥ 只剩一件」是**数错**, 以树为准
# ★ 未与第二人复核。
