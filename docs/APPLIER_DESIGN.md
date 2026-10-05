# DWC · 应用层设计（进化核心第 4 步）

> 2026-10-03 · 判据：只报实测
> 用户裁决：①甲（8a/8b + 16a/16b 拆开）②甲（先定应用层）
> 问题：21 个可进化对象，每个都要"应用" —— 这是四项目共同的断点

---

## 一、先说结论

```text
★ 四项目里只有一个真正的落地器: 母巢的 GeneChampion (S6, 10,091 字符)

  ARSI:  无落地器 (evolver 明说 "Does not auto-edit core"), 860 accepted → 2 applied
  Ultra: 无落地器 (evolve 0 条)
  Nexus: 无落地器 (8 行常量)
  母巢:  ★ 有落地器, 且它记录了三次失败

★ DWC 应用层的形态应该照 GeneChampion, 但要修它的三处失败。
```

---

## 二、母巢落地器的完整形态（实测源码）

### 2.1 两层结构

```text
第一层: gene_applier.py (6,886 字符) — 基因 → 运行时旋钮的映射
        · GENE_TARGETS: 5 个基因的消费点声明
        · plan_apply():  出计划 (纯函数, 永不抛)
        · apply_shadow(): 影子应用, 绝不修改
        · apply_genes():  真写 (SHADOW=True 时退化为 shadow)

第二层: gene_champion.py (10,091 字符) — champion/challenger 守门
        ★ "真写唯一正门 = S6 GeneChampion" (gene_applier 原文)
```

### 2.2 消费点声明的形态（可直接复用）

```python
GENE_TARGETS = {
    "exploration_rate": {
        "consumer": "MultiStrategyScheduler ε-greedy 探索率",
        "path": "loop._evo_scheduler._epsilon",
        "attr": "_epsilon",
        "range": (0.01, 0.5),
    },
    "learning_rate": {
        "consumer": "MemPO GRPO 记忆效用更新步长",
        "path": "loop._mempo._grpo_lr",
        "attr": "_grpo_lr",
        "range": (0.001, 0.1),
    },
    "temperature": {
        "consumer": "ThermodynamicIntelligence 温度",
        "path": "loop._thermo._temperature",
        "attr": "_temperature",
        "range": (0.1, 1.0),
    },
    "memory_weight": {
        "consumer": "MemoryFacade TRS 可靠性权重 η",
        "path": "loop._memory_facade._reliability_eta",
        "attr": "_reliability_eta",
        "range": (0.1, 0.9),
    },
    "stability_factor": {
        "consumer": "分支合并门阈值 (经 merge_threshold_from 映射)",
        "path": "loop._merge_gate_threshold",
        "attr": "_merge_gate_threshold",
        "range": (0.5, 1.0),
    },
}
```

**四个字段**：`consumer`（谁用）/ `path`（在哪）/ `attr`（改哪个属性）/ `range`（钳制范围）。

### 2.3 落地器的完整状态机（★ 这是核心）

```python
def _step(self, tick, genes, metric, loop=None) -> dict:
    """推进一次守门. 返回 {phase, applied, champion, ...} (永不抛)."""

    # 1) 冷启动: 用现状播种 champion, 不动任何参数
    if self.champion is None:
        self.champion = {k: float(v) for k, v in genes.items() ...}
        return {"phase": "cold", "applied": 0, ...}

    # 2) 无候选: 与冠军同值 → 保持; 不同值 → 立候选并应用
    if self.challenger is None:
        if self._same(genes, self.champion):
            return {"phase": "hold", "applied": 0, ...}
        self.challenger = dict(genes)
        self._base_metric = self._self_score(self.champion)   # ★ 基线打 champion
        self._start_tick = tick
        _n = self._apply(self.challenger, loop)               # ★ 应用候选
        return {"phase": "explore", "applied": _n, ...}

    # 3) 候选窗口内: 继续持有
    _elapsed = int(tick) - int(self._start_tick)
    if _elapsed < self.window:
        return {"phase": "evaluating", "applied": 0, ...}

    # 4) 窗口满: 结算 (P72-2 峰值锁定: 须超 best-so-far + margin 才算赢)
    _m = self._self_score(self.challenger)
    _gain = _m - self._base_metric
    _peak = self._best_so_far
    _beats_peak = (_m is not None and (_peak is None or _m > _peak))
    _win = _gain is not None and _gain >= self.min_gain and _beats_peak
    if _win:
        self.champion = dict(self.challenger)
        self.promoted += 1
        self._best_so_far = _m            # 达峰即锁
        _phase = "promoted"
    else:
        _n = self._apply(self.champion, loop)   # ★ 回退
        self.reverted += 1
        _phase = "reverted"
```

**状态机五相**：`cold → hold → explore → evaluating → promoted | reverted`

### 2.4 安全约束（原文）

```text
安全约束:
    - 纯 tick 驱动, 无后台线程
    - 指标不可解析 (None/NaN/非数) 一律按"无改善"处理 → 回退 (保守优先)
    - 任何异常不抛出, 返回 phase="error" 交上层记录
    - history 有界 (默认 200), 防长跑内存增长
```

---

## 三、★ 母巢落地器记录的**三次失败**（这是最值钱的部分）

### 失败 1 · 口径不同源（gain 恒 ≈ 噪声）

```python
# gene_champion.py __init__ 原文注释
# 2026-09-26 (DIAG_GENE_CHAMP_REVERT_20260926.md):
#   `metric` 由调用方 (evolve_mixin:1555) 从 `evolution._last_env_score` 取,
#   而该字段在 evolution_engine 有**两处口径不同源的赋值**:
#     L1206 `_run_ga` **启动**时 `score_in({})`      ← 空参基准
#     L1442 `_run_ga` **结束**时 `score_in(best_genes)` ← 带基因
#   ⇒ champion 窗口两端拿到的都不是"本轮 challenger 的前后对比"
#   ⇒ gain 恒 ≈ 差值噪声 ⇒ 124 次回退 (实测 promoted=1/reverted=124)。
#   修法 (方案 A): champion **自己**用同一口径打两次水位 ——
#   应用 challenger 前打一次 base, 窗口末打一次 current。
```

**★ 教训：基线与结算必须同一口径，否则 gain 是两个无关读数之差。**

### 失败 2 · 基线打错了对象（gain 恒 = 0）

```python
# gene_champion.py _step 原文注释
# 2026-09-26 修正 (我的实现第一版又错一次): base 必须打
# **champion** 的分, 不是 challenger 的。
# 我第一版沿用 `_base_metric = _m` (而 `_m` 此刻是 challenger 的分)
# ⇒ 结算时 `_m` 也打 challenger ⇒ gain 恒 = 自己减自己 = 0.0
# ⇒ 仍然 100% 回退 (锁 test_gain_reflects_challenger_improvement
#   抓到的, 实测 0.1→0.9 判 reverted gain=0.0)。
# 同源比较的定义: base = 老基因水位, current = 新基因水位。
```

**★ 教训：base 必须打老配置，current 打新配置。自己减自己 = 0。**

### 失败 3 · 打分器是量化阶梯（降门槛无用）

```python
# gene_champion.py __init__ 原文注释
# 2026-09-26 回滚说明 (DIAG_METRIC_RESOLUTION_20260926.md 追加节):
#   min_gain 曾被降到 0.0005 (按实测 |gain| 中位数 0.000243 校准),
#   **生产验证 2h/40 采样后证伪并回滚到 0.01**:
#     · 晋升/回退比 0.087 → 0.15 (在噪声内, 无实质改善)
#     · metric 出现累积退化 (Δ = -0.057, 判据 ≥-0.02 未达标)
#     · 真因: `score_in` 是**量化阶梯函数** (由 _tick_summary 离散计数
#       决定 _base), 同一台阶内基因无分辨率 ⇒ gain 恒 0,
#       **降门槛无用**。4/7 轮回退的 gain 恰为 0.0 (逐位相同)。
#   保留偏严但安全的门槛, 好过看似灵敏却放行退化的门槛。
```

**★ 教训：打分器没有分辨率时，调门槛是自欺。必须先修打分器。**

---

## 四、DWC 应用层设计

### 4.1 形态：照 GeneChampion，三段式

```text
┌──────────────────────────────────────────────────────────────┐
│ ① 映射层 (mapping)                                            │
│    对象 → 消费点声明                                          │
│    {consumer, path, attr, range, verify}                      │
│    ★ 比母巢多一个 verify 字段 (写入后读回验证的判据)           │
├──────────────────────────────────────────────────────────────┤
│ ② 落地器 (applier) — 状态机五相                               │
│    cold → hold → explore → evaluating → promoted | reverted   │
│    ★ 纯 tick 驱动, 无后台线程                                  │
│    ★ 异常不抛, 返回 phase="error"                             │
├──────────────────────────────────────────────────────────────┤
│ ③ 回滚器 (rollback)                                           │
│    · 每次应用前存旧值 (champion)                               │
│    · 回退 = 写回旧值 + 读回确认                                │
│    · ★ 读回不通过 ⇒ 报错, 不许静默                            │
└──────────────────────────────────────────────────────────────┘
```

### 4.2 消费点声明（DWC 版，比母巢多 verify）

```python
TARGETS = {
    "prompt_version": {
        "consumer": "actor 的提示词模板",
        "path": "actor._prompt",          # 目标对象路径
        "attr": "_prompt_text",           # 改哪个属性
        "range": None,                    # 文本无 range
        "verify": "actor._prompt_text == candidate",   # ★ 写入后读回
    },
    "epsilon": {
        "consumer": "策略选择 ε-greedy 探索率",
        "path": "actor._policy",
        "attr": "_epsilon",
        "range": (0.01, 0.5),
        "verify": "abs(actor._policy._epsilon - candidate) < 1e-9",
    },
    "decomp_depth": {
        "consumer": "任务分解最大深度",
        "path": "actor._decomposer",
        "attr": "_max_depth",
        "range": (1, 8),
        "verify": "actor._decomposer._max_depth == candidate",
    },
    ...
}
```

**★ `verify` 是 DWC 新增的（母巢没有）**：

```text
母巢的病: apply_genes 里 setattr 后只计 _applied += 1, 不读回
          ⇒ "写成功了"和"值真变了"没被区分

DWC 要求: setattr 后必须读回, 读回不等于候选值 ⇒ 报错
  ★ 依据: DWC 原则 4 "写入后须读回确认值真变了"
```

### 4.3 落地器状态机（DWC 版）

```python
class Applier:
    """落地器: champion/challenger + 五相状态机 (照 GeneChampion)."""

    def __init__(self, window: int = 5, min_gain: float = 0.01):
        self.window = window
        self.min_gain = min_gain
        self.champion = None       # 当前生效
        self.challenger = None     # 待评估
        self._base_metric = None   # ★ 必须打 champion
        self._start_tick = None
        self._best_so_far = None   # 峰值锁定
        self.promoted = 0
        self.reverted = 0

    def step(self, tick, candidate, loop=None) -> dict:
        # 1) 冷启动
        if self.champion is None:
            self.champion = dict(candidate)
            return {"phase": "cold", "applied": 0}

        # 2) 立候选
        if self.challenger is None:
            if self._same(candidate, self.champion):
                return {"phase": "hold", "applied": 0}
            self.challenger = dict(candidate)
            self._base_metric = self._score(self.champion)   # ★ 打 champion
            self._start_tick = tick
            n = self._apply(self.challenger, loop)            # ★ 带读回验证
            return {"phase": "explore", "applied": n}

        # 3) 窗口内
        if tick - self._start_tick < self.window:
            return {"phase": "evaluating", ...}

        # 4) 结算
        m = self._score(self.challenger)
        gain = m - self._base_metric if (m is not None and self._base_metric is not None) else None
        win = gain is not None and gain >= self.min_gain and (self._best_so_far is None or m > self._best_so_far)
        if win:
            self.champion = dict(self.challenger)
            self.promoted += 1
            self._best_so_far = m
            return {"phase": "promoted", "gain": gain}
        else:
            self._apply(self.champion, loop)   # 回滚
            self.reverted += 1
            return {"phase": "reverted", "gain": gain}
```

### 4.4 ★ 三条必须写进纪律的教训（母巢用 3 次失败换来）

```text
纪律 1 · 基线与结算必须同一口径
  母巢的错: base 取 _run_ga 启动时的 score_in({}), current 取结束时的
            score_in(best_genes) —— 两个不同源的读数
  结果: gain 恒 ≈ 噪声, 124 次回退
  ★ DWC: base 与 current 必须由同一个 scorer 对同一批任务打分

纪律 2 · base 打老配置, current 打新配置
  母巢的错: 第一版 _base_metric = _m (此刻 _m 是 challenger 的分)
            ⇒ 结算时 _m 也打 challenger ⇒ gain = 自己减自己 = 0
  结果: 100% 回退 (0.1→0.9 判 reverted gain=0.0)
  ★ DWC: 明确写 base = score(champion), current = score(challenger)

纪律 3 · 打分器没分辨率时, 调门槛是自欺
  母巢的错: 把 min_gain 从 0.01 降到 0.0005 (按噪声中位数校准)
  结果: 晋升/回退比 0.087→0.15 (噪声内) + metric 累积退化 Δ=-0.057
  真因: score_in 是量化阶梯函数, 同一台阶内 gain 恒 0
  ★ DWC: 先验证 scorer 有分辨率 (同一批任务上, 不同配置应产出不同分),
         再谈门槛。分辨率是前提, 门槛是调节。
```

---

## 五、与"应用"相关的三个判据

```text
判据 1 · 应用必须可读回 (原则 4)
  setattr 后读回, 读回值 ≠ 候选值 ⇒ 报错, 不许静默计成功

判据 2 · 应用必须有回滚路径
  每次应用前存旧值; 回退 = 写回 + 读回确认
  ★ ARSI 的 inverse_op 862/862 全是非空 —— 这一点 ARSI 做对了

判据 3 · 应用必须有窗口 (不是立即生效)
  母巢的窗口 = 5 tick; 窗口末比对, 不达标回退
  ★ 理由: 立即生效 = 无法判断"是它带来的改变吗"
```

---

## 六、21 个对象的应用难度分级

```text
甲类 · 直接可写 + 可读回 (最容易)
  1 标量参数  2 提示词  9 策略  12 上下文  17 置信校准  18 推理增强
  22 任务分解  23 注意力
  ★ 载体是属性/文本, setattr + 读回即可

乙类 · 需要"条目标识" (中)
  3 技能  4 记忆  6 知识
  ★ 载体是记忆条目, 需要条目的增删改 + 版本

丙类 · 需要"代码替换" (难)
  5 工具  7 代码  8b 架构-结构  10 智能体  16a 评分实现  19 harness  20 基础设施  21 元认知  13 观测  27 完成检测
  ★ 需要: 静态门 + golden 测试 + 影子期 + 回滚

★ 建议: 第一版只开甲类 8 个 (能全部走通闭环), 乙丙类分批
  ★ 理由: 母巢 21 个对象全开的代价 = 88 文件 932KB + 24 个模块无引用
```

---

## 七、下一步

```text
已定:
  ① 拆项: 8a/8b + 16a/16b ✓
  ② 应用层形态: champion/challenger + 五相状态机 + 读回验证 ✓
  ③ 三条纪律: 同源口径 / base打老配置 / 打分器先有分辨率 ✓

待定:
  ④ 影子期退出判据 (不许"观测满 N tick"这种模糊话)
  ⑤ 甲类 8 个的消费点具体声明 (path/attr/range/verify)
```
