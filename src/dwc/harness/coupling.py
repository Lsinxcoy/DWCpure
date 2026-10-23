"""coupling · 机制间压力传播的**记账面**（R196 · Z 类落地 甲类 A1）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 只**登记与查询**"谁给谁压力"的边; 不产生压力、不触发调用、不判分。

★★★ TRUTH_SOURCE（判据 G2）· 论文依据（**甲类 = 有据照搬**）
  2608.10299 §2.3 三阶段 taxonomy（R192 woff §2.2 逐字）:
      Stage 1 Agent–Agent      A^{t+1} = ({a_i^{t+1}}_1..n, Π^{t+1}) = Ω(A^t, E, τ^t)
                               "Within a fixed environment"; "Co-evolution begins
                               when an agent no longer learns against a static counterpart"
      Stage 2 Agent–Environment  (A^{t+1}, E^{t+1}) = Ω(A^t, E^t, τ^t)
                               "When the environment remains fixed, it limits the new
                                experiences and pressures"
      Stage 3 Meta             Ω^{t+1} = Γ^t(S^t, Ω^t, τ^t), then S^{t+1} = Ω^{t+1}(S^t, τ^t)
                               "In Stage 2, the evolution mechanism remains human-designed,
                                so the system can change its contents but not how they change"
  Stage 3 判据（§5.1 逐字）: 机制修订必须**由下层 co-evolving 生态系统的联合轨迹
  诱导**, 并且**必须反过来改变该生态系统的后续进化条件**。

★★★ DWC 现状的诚实定位（R196 实测）
  DWC 现在在 **Stage 0**（论文 taxonomy 之前）: judge / metric_loop / direction /
  evolver 四机制各管一段、**互不触发**——metric 选出新 op 不会让 direction 重排
  fallback 序; direction 换向不会让 metric 重估树。
  ⇒ 本模块把"互不触发"这件事变成**可数的账**, 不改一行链行为。

★★★★ 四条边界（防做成假的）
  ① **只记账不触发**——第一版绝不自动调用对方。压力传播 = 写入 ledger 并由既有
     消费点（_dir_ledger_append / credit_entries）消费。自动触发是 Stage 1 的
     行为, 得先有 Stage 0 的账才谈得上（**不跳级**）。
  ② **不新增常量表**（A1 纪律, R194 vocabulary 同款）: 边表是**登记**, 不是判据。
  ③ `stage_of()` 报的是"**账记到第几阶段**", 不是"系统有多先进"。DWC 自报
     Stage 0 是**如实的**, 不是缺陷（论文原文: "Only limited work currently
     meets our definition of Stage 3"）。
  ④ 测试锁: 边表填满也**不得**自报 Stage 3（见 tests/test_r196 的
     test_stage_of_never_claims_advanced）。
"""

from __future__ import annotations

#: ★★ 压力边（登记面 — 不是判据, 不是触发链）
#:   (from_subsystem, to_subsystem, pressure_name)
#:   第一版 4 条 = R196 方案 §五.1 经用户默许的出厂集（用户 2026-10-12 令"继续"）。
COUPLING_EDGES: tuple[tuple[str, str, str], ...] = (
    # ★★★ R197 · 命名修正（我 R196 的边名是**事件式误导** — 实测三条边
    #   根本没有事件可接, 但有真实的**耦合形态**; 按事实重命名）:
    #   "metric 面每轮常开" ⇒ 不是"op 判定变了才触发": loop.py:972-977
    #     每轮无条件跑 dev_points_from_store ⇒ metric 的新鲜度**已经**是
    #     每轮级别。旧名 op_verdicts_changed 暗示事件驱动 ⇒ 错。
    #   "换向只改尝试序不改选优口径" ⇒ select(dev_points, a_train=) 的
    #     判据面（judge/a_train）**不接受** direction 输入; 能接的只有
    #     `trees=` 候选族提示 = 改门③语义 ⇒ R181 判高危不进链 ⇒ 旧名
    #     direction_switched 暗示 metric 会因换向而变 ⇒ 错。
    #   "judge 面无写入入口" ⇒ evaluate() 只读; 落地的效应走**下一轮**的
    #     自然数据（轮间耦合, 非轮内调用）⇒ 旧名 verdict_distribution_shifted
    #     暗示 judge 会推分布给 evolver ⇒ 错。
    ("metric_loop", "direction", "metric_surface_refreshed_every_round"),
    ("direction", "metric_loop", "direction_switches_do_not_enter_select"),
    ("evolver", "judge", "landing_enters_next_round_data"),
    ("judge", "evolver", "failure_signature_clusters_fed"),
)

#: ★ DWC 的四个机制子系统（harness/organs 的已登记结构 — 不自造第五个）
SUBSYSTEMS: tuple[str, ...] = ("judge", "metric_loop", "direction", "evolver")

#: ★ 阶段名（与论文 §2.3 taxonomy 对齐; Stage 0 = 论文之前的"互不触发"）
_STAGE_NAMES: tuple[str, ...] = (
    "Stage0_uncoupled", "Stage1_agent_agent",
    "Stage2_agent_environment", "Stage3_meta")


def pressures_from(subsystem: str) -> list[tuple[str, str]]:
    """子系统 ⇒ 它**向外出压力**的 (to, pressure_name) 清单。

    ★ 未登记子系统 ⇒ []（如实 — 不猜边; 越界的调用方自己负责）。
    """
    return [(to, pn) for (frm, to, pn) in COUPLING_EDGES if frm == subsystem]


def pressures_to(subsystem: str) -> list[tuple[str, str]]:
    """子系统 ⇒ **谁向它**施压的 (from, pressure_name) 清单。"""
    return [(frm, pn) for (frm, to, pn) in COUPLING_EDGES if to == subsystem]


def declared_pairs() -> list[tuple[str, str]]:
    """已登记的 (from, to) 有序对（去重排序 ⇒ 输出确定, 测试可断言）。"""
    return sorted({(f, t) for (f, t, _) in COUPLING_EDGES})


def decoupled_pairs() -> list[tuple[str, str]]:
    """**尚未登记**压力的有序子系统对（如实暴露 Stage 0 的缺口）。

    ★ 非空是事实陈述, 不是缺陷 — 论文说 Stage 3 是"Only limited work"达到的。
    ★ 测试锁的原因串必须含 "Stage 0" ⇒ 谁把边表填满也不能顺带改口径。
    """
    decl = set(declared_pairs())
    return sorted((a, b) for a in SUBSYSTEMS for b in SUBSYSTEMS
                  if a != b and (a, b) not in decl)


def stage_of(edges: list[tuple[str, str, str]]) -> tuple[int, str]:
    """给定边集 ⇒ (阶段号, 阶段名) —— **记账判定, 不是能力判定**。

    ★ 判据（可机复现, 全部来自边表本身, 不引入外部信号）:
        0: 空边集                     ⇒ Stage0_uncoupled
        1: 非空但无跨子系统环境边      ⇒ Stage1_agent_agent
        2: 有跨子系统边但缺 meta 边    ⇒ Stage2_agent_environment
        3: 含 meta 边                 ⇒ Stage3_meta
      meta 边 = from 或 to 为 "meta"/"evolution_mechanism" 的边
      （论文 Stage 3 = "the evolution mechanism itself" 在变）。
    ★★ 上限锁: 即使填满 4 子系统的全 12 条边, 只要**没有 meta 边**就仍是
      Stage 2 —— 这正是论文 §5.1 的判据（机制本身没在变 ⇒ 不是 Stage 3）。
    """
    if not edges:
        return (0, _STAGE_NAMES[0])
    meta = ("meta", "evolution_mechanism")
    has_cross = any(f != t for (f, t, _) in edges)
    has_meta = any(f in meta or t in meta for (f, t, _) in edges)
    if has_meta:
        return (3, _STAGE_NAMES[3])
    if has_cross:
        return (2, _STAGE_NAMES[2])
    return (1, _STAGE_NAMES[1])


def current_stage() -> tuple[int, str]:
    """★ 出厂边表的阶段（DWC 如实自报 — R196 出厂集 ⇒ Stage 2）。"""
    return stage_of(list(COUPLING_EDGES))


COUPLING_MECHANICS = {
    "no_auto_trigger": "边表只记账; 压力由既有消费点(_dir_ledger_append/credit_entries)读",
    "paper": "2608.10299 §2.3 三阶段 taxonomy + §5.1 Stage3 判据（逐字在 docstring）",
    "honest_stage": "stage_of 报账不报能力; DWC 出厂 = Stage 2（有跨机制边无 meta 边）",
}
