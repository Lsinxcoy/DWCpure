"""el_sched · EL 调度器（器官⑥ 探索 · 2609.04128 式 2）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 服务环节⑥（ARCHITECTURE 三段式①: legal_actions → 采样(EL 调度器) → 本轮任务）,
    不碰记忆读写 ⇒ 非 DWC-MEM。★ 不抢位: 不声明 REPLACES。

★★★ TRUTH_SOURCE（判据 G2: 含判定能力的模块必须声明）
  本模块**不产生**成功判定 —— 布尔观测（judge success）由调用方注入
  （世界树 observe / run_term 判分回填）; p̂ 只是窗口均值, 不是自评。

=== 论文原文（papers_txt/2609.04128.txt, 式 2 与其后一段逐字）===
  (g_{u+1}, k_{u+1}) = (g_u, k_u)                            if p̂_u ≤ τ
                    = (g_u, k_u + 1)                         if p̂_u > τ ∧ k_u < N_{i,g}
                    = (g_u + 1, 1)                           if p̂_u > τ ∧ k_u = N_{i,g}
    p̂_u(E) = (1/B) Σ_{b=1..B} r_{u,b}
  "We use B=8 and τ=6/8. Once the current environment exceeds this threshold,
   the scheduler moves to the next environment in the same generation.
   It advances to the next generation only when no environments remain in
   the current one."

★ ★ 两级推进 —— EVOLUTION_CORE_V2 §8.2 的「6/8 通过才放行下一代」是口语压缩:
    ① p̂ > τ ⇒ **同代内移动到下一环境**（不是直接换代）
    ② 代内环境用尽（k=N）才 **换代**
  且 **p̂ = τ（恰好 6/8）走的是「≤ τ」分支 = 停滞** —— 原文是 ≤τ 停、>τ 进,
  所以 6/8 整恰好不推进, 7/8 才推进。本模块按论文逐字, 不按口语。
★ 零模型依赖: 只吃布尔观测（8 次）—— 与 δ_θ 的可迁移性主张同源。
★ 窗口未满 B ⇒ 判不了 ⇒ status="insufficient"（"没观测过"不许默认通过
  也不许默认停滞 —— X2 / C3' 同族纪律）。
"""
from __future__ import annotations

from dataclasses import dataclass

#: 论文取值（2609.04128 式 2 后: "We use B=8 and τ=6/8"）——
#: 有出处的常量, 不是"没想过"的默认（NOISE_DELTA=0.15 同款; 锁值测试防漂移）
B_WINDOW: int = 8
TAU: float = 6.0 / 8.0

#: 决策状态（四态 —— insufficient 单列, 不与停滞混淆）
STATUS_INSUFFICIENT = "insufficient"     # 窗口未满 B, 判不了
STATUS_STALLED = "stalled"               # p̂ ≤ τ: 卡住当前环境
STATUS_NEXT_ENV = "next_environment"     # p̂ > τ 且 k < N: 同代推进
STATUS_NEXT_GEN = "next_generation"      # p̂ > τ 且 k = N: 换代


class ElSchedError(Exception):
    """调度器状态违规必须大声报错（G7 静默门同族）。"""


@dataclass(frozen=True)
class ELDecision:
    """一次判定的完整读数（status 必填 —— 三义状态事后不可解释, X1 同族）。"""

    status: str
    generation: int          # 当前代 g
    index: int               # 当代第 k 个环境（1-based, 对齐公式的 k）
    pass_rate: float | None   # p̂; insufficient 时 None（不装 0）


class ELScheduler:
    """式 2 的三段状态机（零模型, 只吃布尔观测）。

    ★ B / tau 可在构造覆盖（默认=论文值）—— 覆盖只用于测试; 生产锁值
      由 test 的 B_WINDOW/TAU 常量断言把守（防"改常量迁就实现"）。
    ★ n_envs（= 论文 N_{i,g}, 当代环境总数）由每次 decide 传入 ——
      DWC 世界树的代内环境数是动态的（legal_actions 随揭示变化）,
      调度器自己数不了, 这是与论文任务集静态 N 的**实例化差异**（明标）。
    """

    def __init__(self, B: int = B_WINDOW, tau: float = TAU, *,
                 generation: int = 1, index: int = 1):
        if isinstance(B, bool) or not isinstance(B, int) or B < 1:
            raise ElSchedError("B 须为 ≥1 整数（窗口大小）, 实得 %r" % (B,))
        if not (0.0 < tau <= 1.0):
            raise ElSchedError("tau 须在 (0, 1], 实得 %r" % (tau,))
        if generation < 1 or index < 1:
            raise ElSchedError(
                "generation/index 须 ≥1（论文 k, g 都是 1-based）, 实得 %r/%r"
                % (generation, index))
        self.B = B
        self.tau = float(tau)
        self.generation = generation
        self.index = index
        self._window: list[int] = []

    # ── 观测注入（滑动窗口, 只收布尔）──────────────────────
    def record(self, success: bool) -> None:
        """收一次布尔观测（judge 的 success —— 本模块不产生判定）。"""
        if not isinstance(success, bool):
            raise ElSchedError(
                "布尔观测必须是 bool（零模型依赖的全部输入）, 实得 %r"
                % (type(success).__name__,))
        self._window.append(1 if success else 0)
        if len(self._window) > self.B:
            self._window = self._window[-self.B:]

    @property
    def n_obs(self) -> int:
        return len(self._window)

    @property
    def pass_rate(self) -> float | None:
        """p̂ = (1/B)Σr —— 窗口未满 B ⇒ **None**（判不了, 不是 0.0）。"""
        if len(self._window) < self.B:
            return None
        return sum(self._window) / float(self.B)

    # ── 式 2 的三段判定（副作用: 推进时清窗 —— 新环境新窗口）──
    def decide(self, n_envs: int) -> ELDecision:
        """按式 2 判一次（**序列口**: 观测经 record 灌窗, 读窗判）。

        ★ insufficient / stalled 不改状态; next_* 推进并**清空窗口**
          （新环境的观测与旧环境不可混窗 —— 混了 p̂ 就不是"当前环境"的了）。
        ★ R76: 三段核心拆到 decide_from_rate —— 本方法 = 读窗 + 核心 + 推进清窗,
          行为与拆分前逐条等价（原有 11 项测试锁死不动）。
        """
        p = self.pass_rate
        d = self.decide_from_rate(p, n_envs)
        if d.status in (STATUS_NEXT_ENV, STATUS_NEXT_GEN):
            self._window = []                    # 序列口的推进清窗
        return d

    def decide_from_rate(self, pass_rate: float | None,
                         n_envs: int) -> ELDecision:
        """式 2 三段核心（**速率口**: 调用方直接给已算好的 p̂）。

        ★ 给 None ⇒ insufficient（"没观测过"不冒充 —— 与序列口同纪律）。
        ★ 不碰窗口（速率口无窗可清 —— 观测聚合方式归调用方,
          如世界树候选池 Σn_pass/Σn_obs 的实例化）。
        ★ R76 批1 接线用: A core.step 缺省取任务 / B run_term 任务源标注 ——
          与序列口共用同一状态机（generation/index 同一份）。
        """
        if isinstance(n_envs, bool) or not isinstance(n_envs, int) \
                or n_envs < 1:
            raise ElSchedError(
                "n_envs(=N_{i,g}) 须为 ≥1 整数, 实得 %r" % (n_envs,))
        if self.index > n_envs:
            raise ElSchedError(
                "当前 k=%d 已超过当代环境数 N=%d —— 状态不一致, "
                "不许静默算下去" % (self.index, n_envs))
        p = pass_rate
        if p is None:
            return ELDecision(STATUS_INSUFFICIENT, self.generation,
                              self.index, None)
        if p <= self.tau:
            # 原文第一分支: p̂ ≤ τ ⇒ 状态**完全不动**（恰 6/8 也停滞）
            return ELDecision(STATUS_STALLED, self.generation,
                              self.index, p)
        # p̂ > τ
        if self.index < n_envs:
            self.index += 1                      # 同代内移动
            status = STATUS_NEXT_ENV
        else:
            self.generation += 1                 # 换代
            self.index = 1
            status = STATUS_NEXT_GEN
        return ELDecision(status, self.generation, self.index, p)

    def snapshot(self) -> dict:
        """状态读数（审计/日志用 —— 不改状态）。"""
        return {"generation": self.generation, "index": self.index,
                "B": self.B, "tau": self.tau, "n_obs": self.n_obs,
                "pass_rate": self.pass_rate}


# ══════════════════════════════════════════════════════════
# 诚实边界（R70 的范围, 别把「能算」当「接上了」）
# ══════════════════════════════════════════════════════════
# ★ 已做: 式 2 三段状态机（含 =τ 停滞边界与两级推进）· 滑窗 p̂ · insufficient
#         单列 · 代内/换代推进清窗 · 锁值常量 B=8 τ=6/8（出处: 式 2 后原文）
# ★ 未做（下轮/依赖裁决）:
#   · **运行流接线**: ARCHITECTURE 三段式① 的「legal_actions → 采样(EL) →
#     本轮任务」—— core.step 现取 acts[0]; 换 EL 采样=**取任务行为变更**
#     （run_term/e2e 的任务顺序会变）⇒ 单独一轮做, 本轮不顺手改（R69 同纪律）
#   · record 的观测源接线: 现由调用方注入（唯一调用方=测试）
#   · N 的语义差异: 论文 N_{i,g} 是静态任务集结构; DWC 代内环境数随揭示
#     动态 ⇒ n_envs 每次由调用方传（实例化差异, 已在 docstring 明标）
#   · 与 Z6 卡住检测的分工: Z6=轮级连续无改进; EL=环境级通过率窗口 ——
#     两层不同不冲突, 但**联动策略**（EL 停滞与 Z6 同时触发怎么办）未设计
# ★ "6/8 放行下一代"的口语口径与原文有两处出入, 已在模块头逐字标注:
#   ① 6/8 是**同代移动**门槛不是换代门槛（换代看代内用尽）
#   ② 恰 6/8=τ 走停滞分支（7/8 才推进）—— 按论文 ≤τ/>, 不按口语
# ★ 未与第二人复核。
