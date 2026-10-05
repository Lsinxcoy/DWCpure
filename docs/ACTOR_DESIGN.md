# DWC · `actor`（行动者）设计

> 2026-10-03 · 判据：ARSI core.py 逐行实测 + 16 篇论文原文
> 定位：原则 5（行动必须可评价）的**唯一载体**；唯一产生痕迹的器官
> 前置：`ARCHITECTURE.md` §4.2（原 204 字符）· `docs/ACTOR_TASK_SOURCE.md`（任务源已定）

---

## 一、先说结论

```text
★ ARSI 的 actor 有两个硬问题, 都是"名字与实现不符":

  问题 1 · 它不做任务, 只观测宿主
     ingest_trace(agent_id, action, outcome, effect)   ← 宿主喂数据
     ★ ARSI 的 5 个候选动作实测:
       dream     真实现 (DreamPipeline)
       learn     真实现 (蒸馏 PROXY→EXPERIENCE)
       maintain  真实现 (记忆巩固)
       evolve    ★ 占位符: note="mutation_attempted_unanchored", effect=0.0
       remember  ★ 空操作: note="waiting for new traces"
     ⇒ 它是"记忆维护员", 不是"任务执行者"

   ★ 行号 (core.py 逐行核实):
     L722  _execute_evolve docstring: """Evolve: attempt mechanism mutation (placeholder)."""
     L692  remember 分支: return {"type": "remember", "note": "waiting for new traces"}"

  问题 2 · ★ success 判定有硬编码的假成功
     ARSI core.py step() 原文:
       if decision["action"] == "remember":
           exec_ok = False
           exec_note = "waiting_new_traces"
     ★ remember 永远 exec_ok=False —— 它被**硬编码**成永不成功。
     ★ 更严重: 效果值也是硬编码的:
       self.iwm.observe_behavior(..., effect=0.6 if exec_ok else 0.2, ...)
     ⇒ effect 只有两个值 (0.6/0.2), 不携带任何真实信息。

   ★ 行号 (core.py 逐行核实):
     L556-558  if decision["action"] == "remember":  exec_ok = False
     L572      effect=0.6 if exec_ok else 0.2

★ 所以 DWC 的 actor 要: ①真有任务 ②success 必须来自外部判据。
```

---

## 二、ARSI actor 的完整实测

### 2.1 循环结构（step() 原文骨架）

```python
def step(self) -> dict:
    """Execute one full ARSI cycle.
    Decision priority:
      1. Pre-enactment (Layer 2 dynamics prediction)
      2. LLM (if pre-enactment confidence too low)
      3. Heuristic (fallback)
    """
    self._step_count += 1

    # 0. Train dynamics model periodically
    if self._step_count % 10 == 1 or not self._dynamics_trained:
        ...
    # 1. Refresh world state
    state = self.siwm.refresh_state()
    # 3. Three-layer decision — skip untrusted pre-enactment when IWM says so
    candidates = ["dream", "learn", "evolve", "maintain", "remember"]
    advice = self.iwm.governor_advice(state)
    # Layer A: Pre-enactment
    if use_pre:
        pre_result = self.pre_enactment.select_best_adaptive(state, candidates)
    if pre_result["confidence"] > 0.1:
        decision = pre_result;  result["decision_source"] = "pre_enactment_adaptive"
    else:
        # Layer B: LLM decision
        llm_decision = self.llm_governor.decide(state, candidates)
        ...
    # IWM forbid_default_dream: override dream → learn
    ...
    # 3b. Execute the action
    exec_result = self._execute_action_str(decision["action"], state)
```

**★ 关键数字**：`pre_result["confidence"] > 0.1`（**core.py L491**）—— 这个 **0.1 是硬编码阈值**。

```text
★ 问题: 预测置信度 > 0.1 就用预测, 否则问 LLM。
  0.1 是极低的门槛 —— 意味着"几乎任何非零置信度"都直接采用预测,
  LLM 层几乎不会被触发。
★ 且这违反 DWC 原则 9 的方向: 世界模型应该**门控**决策,
  但"门控"不等于"只要 >0.1 就完全接管"。
```

### 2.2 五个候选动作的实测

| 动作 | 实现状态 | 实测证据 |
|---|---|---|
| `dream` | ✓ 真实现 | `self.dream.execute(state)` → DreamPipeline |
| `learn` | ✓ 真实现 | 蒸馏 PROXY→EXPERIENCE, 返回 `distilled` 计数 |
| `maintain` | ✓ 真实现 | 记忆巩固 |
| `evolve` | ★ **占位符** | docstring 第一行: `"""Evolve: attempt mechanism mutation (placeholder)."""` |
| `remember` | ★ **空操作** | `return {"type":"remember","note":"waiting for new traces"}` |

**★ `evolve` 的原文（这是"生 0 死 0"的代码级根因）**：

```python
def _execute_evolve(self, state: WorldState) -> dict:
    """Evolve: attempt mechanism mutation (placeholder)."""
    exp_count = state.phi.storage_stats.get("experience_count", 0)
    if exp_count < 5:
        return {"type": "evolve", "note": f"insufficient experience ({exp_count}/5)"}

    # External effect anchor required (S5): placeholder cannot self-score as verified
    from arsi.foundation.effect_anchor import record_external_effect
    anchor = record_external_effect(
        self.store, mechanism="evolve_attempt",
        effect=0.0, source="internal_score", evidence_ref="",
    )
    return {"type": "evolve", "note": "mutation_attempted_unanchored",
            "effect": 0.0, "effect_anchor": anchor.to_dict()}
```

```text
★ 它诚实 —— docstring 写了 (placeholder), effect 固定 0.0, 标成 unanchored。
★ 但结果是: **进化这个动作在 ARSI 里从未真正执行过**。
  ⇒ "生 0 死 0" 不是 bug, 是这个占位符的直接后果。
```

### 2.3 ★ 缺陷：success 判定被硬编码

```python
# core.py step() 原文
        exec_ok = not (
            isinstance(exec_result, dict)
            and exec_result.get("type") in ("freeze", "error")
        ) and not (isinstance(exec_result, dict) and exec_result.get("note") == "unknown action")
        # Stricter meaningful success for IWM calibrator
        exec_note = ""
        if isinstance(exec_result, dict):
            exec_note = str(exec_result.get("note") or exec_result.get("type") or "")
            if decision["action"] == "learn" and int(exec_result.get("distilled", 0) or 0) <= 0:
                exec_ok = False
                exec_note = exec_note or "learn_no_distill"
            if decision["action"] == "remember":
                exec_ok = False
                exec_note = "waiting_new_traces"
```

```text
★★ 三处硬编码 (机械可查):
   ① remember 永远 exec_ok = False      ← 无条件的
   ② learn 的 success 靠 distilled 计数  ← 内部计数, 不是外部判据
   ③ effect 只有两个值: effect=0.6 if exec_ok else 0.2

★ 后果: IWM 的校准器收到的 effect 是二值噪声, 不是真实效果。
  ⇒ IWM 的 self_trust 建立在假数据上。

★ 与 DWC 原则 5 的冲突: "行动必须可评价" —— 但这里 success 是**动作类型**决定的,
  不是**结果**决定的。同一个动作永远同一个判定, 与它做得好不好无关。
```

### 2.4 痕迹 schema（BehaviorTrace 原文）

```python
class BehaviorTrace(BaseModel):
    """A single behavioral observation from a host agent or ARSI itself."""
    id: str = Field(default_factory=lambda: uuid4().hex)
    agent_id: str = ""
    state_before: WorldState = Field(default_factory=WorldState)
    action: str = ""
    action_params: dict = Field(default_factory=dict)
    state_after: WorldState = Field(default_factory=WorldState)
    outcome: str = ""
    effect: float = 0.0
    generation: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)
```

```text
★ 字段齐全 (前后状态 + 动作 + 参数 + 结果 + 效果 + 代际), 但:
  · outcome 是**自由字符串** (无枚举)  ⇒ 无法机械聚类
  · effect 是**自评浮点**            ⇒ 违反原则 1
  · ★ 没有"失败定位"字段             ⇒ Recuris 的判据说"没有失败定位的痕迹不算合格"
  · ★ 没有"任务/目标"字段            ⇒ 痕迹不知道自己在做哪个任务
  · ★ 没有"证据"字段                 ⇒ 无法回答"凭什么说它成功了"
```

---

## 三、论文给 actor 的五件事

### 3.1 ★ 三层粒度：Trajectory / User turn / Subscene（2609.08183 §3.1）

| 粒度 | 定义（原文） | 用途 |
|---|---|---|
| **Trajectory** | "a complete interaction executed by the deployment harness, preserving user requests, model responses, tool calls, environment observations, recovery attempts, and terminal outcomes" | 完整执行历史 |
| **User turn** | "begins with a user request and ends at the next user request or task termination" | 序列化的基本单元 |
| **Subscene** | "groups adjacent user turns that **share a local goal**" | 语义刻画单元 |

**★ 两条硬约束（原文）**：

```text
① "Tool results and harness-injected messages do not initiate a new user turn."
   ⇒ 工具结果与 harness 注入的消息**不切分** turn 边界。

② 上下文保留策略 (不对称, 有意的):
   "the current request and its interleaved reasoning, tool calls, and
    observations are retained… Earlier visible responses and tool interactions
    remain available as context, whereas **reasoning from earlier turns is omitted**."
   ⇒ 历史 reasoning **丢弃**, 历史可见响应**保留**。
   ★ 论文说这与 DeepSeek-V3.2 的 convention 一致。
```

**★ DWC 的映射**：

```text
ARSI 的 BehaviorTrace = 一次动作 (最细)
DWC 需要三层:

  Trajectory  = 一次完整任务执行 (对应一个世界节点 W)
  Turn        = 一次"任务尝试" (从取任务到出结果)
                ★ 切分判据: 工具结果不切分 (照抄原文约束)
  Subscene    = 共享局部目标的连续 turn
                ★ 这是"失败定位"的粒度 —— 中间失败 vs 后续成功可区分

★ 为什么必须有 Subscene: 论文原文 "Long trajectories are evaluated in segments
  and subsequently aggregated at the turn level so that **intermediate failures
  can be distinguished from successful later recovery**"
  ⇒ 没有 Subscene, 一次"先失败后修正"的轨迹会被整体判为失败。
```

### 3.2 ★ 结构化 trace Γ（2608.24876 §2.2.3）—— 最可移植的一块

```text
harness 每步发出结构化 trace Γ, 链接:
   任务状态 / 被调技能 / 动作 / 结果
```

**★ 注入故障实验（Table 4，量化 Γ 的价值）**：

```text
向某个组件注入已知故障, 让固定 judge 从三类证据中指出故障组件。
每类 9 样本 × 2 次重复 = 每条件 54 次裁决。恒定猜测基线 = 33.3% (三选一)

证据条件          ℰ     𝒲     ρ    Macro   Macro-F1
仅结果          0.0   38.9   0.0   13.0     10.4    ★ 低于恒定猜测
原始轨迹       61.1   50.0   0.0   37.0     31.2    ★ 仅高出基线不到 4 点
结构化 trace   72.2   83.3  38.9   64.8     63.4    ★ 近乎翻倍
```

**★ 论文对差距来源的判断（原文，全文最值钱的一段）**：

```text
"The per-fault rows say where the gain comes from, and it is **observability
 rather than reasoning**. An invocation fault is a **non-event**: nothing
 appears in the transcript where a skill should have been injected, and
 neither condition without Γ's mechanism events names it **even once**,
 against 38.9% from Γ."
```

```text
★★ "失败是**非事件**" —— 这是 DWC 必须抄的核心洞察:
   调用失败时, 记录里**什么都没有**(该出现的没出现)。
   只有结构化 Γ 能记下"本该发生但没发生"。

★ 对 DWC 的直接含义:
   actor 的痕迹必须记录**预期与实际的差**, 不只是实际发生了什么。
   ⇒ 痕迹 schema 必须有 "expected" 字段 (见 §4.3)
```

### 3.3 ★ Verified Coupling：完成由外部回执验证（2608.24876 §2.2）

```text
论文的判据 (原文):
  "判据不是『我说了我完成了』, 而是『我收到了匹配的工具回执』。"
★ 这是 L7 (形状正确≠有价值) 在论文级的落地 —— 完成性必须由外部回执验证。
```

**★ DWC 的落地**：

```text
actor 的 success **不许自己判**。三个来源 (按优先级):
  ① judge 的 verdict (密封任务集, 进程外)
  ② 工具回执 (执行器的真实返回, 如测试通过/失败)
  ③ ★ 若两者都没有 ⇒ 记 NOT_EVALUATED, **不许记成功**
```

### 3.4 ★ prediction–action–outcome 三分离（2609.08183 §3.4）

```text
每轮保留三样东西 (原文):
  "the router's raw prediction, the policy-adjusted decision, and the
   tier actually served, so that **predicted demand, policy constraints,
   and executed action remain independently analyzable**"

两条用途分离 (原文):
  ① prediction–action 分离: "isolate the routing estimate used for curriculum
     ordering without treating **the tier actually served as the training label**"
  ② outcome 不进课程、进分配: "Outcome fields instead provide deficiency
     signals for the capability-guided allocation"
```

```text
★★ 对 DWC 的含义 (这直接解决 actor 的一个设计难点):
   预测/决策/结果 三者必须分开存, 因为:
     · 预测 → 用于排序 (哪类任务先做)
     · 决策 → 用于归因 (谁做的决定)
     · 结果 → 用于分配 (哪个能力弱)

   ★ 特别地: "被实际服务的东西不能当训练标签"
     ⇒ DWC 的痕迹不许把"实际执行的动作"当成"应该执行的动作"的标签。
```

### 3.5 ★ 质量评估的六维 + 不压成单一分数（2609.08183 §3.2）

```text
六个独立维度:
  goal attainment / instruction adherence / tool use /
  evidence consistency / error recovery / termination

★ 四条纪律 (原文):
  ① 高确定性失败用**规则**检测 (缺失响应/未解决调用/未恢复的终止错误)
  ② 需任务级解释的交给语义 judge, 且 "restricted to evidence explicitly
     present in the trajectory"
  ③ ★ "Missing evidence or an interrupted judge call is **never converted
     into a positive verdict**."  ← 对共谋塌缩的直接免疫
  ④ ★ "retains the structural state, the six quality dimensions, and evidence
     coverage rather than **compressing them into a single heuristic score**"

★ 三档输出 (可直接抄):
  internally complete   → 直接进语义评估
  partially recoverable → 只贡献因果闭合的子轨迹
  quarantined           → 隔离
★ 论文的界限声明: "Structural validity establishes reliable serialization
  and replay, but does **not** imply correct tool selection or task success."
```

---

## 四、DWC 的 actor 设计

### 4.1 形态：三段式

```text
┌──────────────────────────────────────────────────────────────────┐
│  actor（行动者）· 唯一产生痕迹的器官                               │
│                                                                   │
│  ① 取任务 task_loop/                                              │
│     W.legal_actions() → 采样 (EL 调度器) → 得到本轮任务            │
│     ★ 任务源 = 世界模型 (已定, 见 ACTOR_TASK_SOURCE.md)            │
│                                                                   │
│  ② 执行 execute/                                                  │
│     observe → decide → act → record                              │
│     决策优先级: 预测(世界模型, 有门控) → LLM → 启发式               │
│     ★ 每步发出结构化 trace Γ (§3.2)                                │
│                                                                   │
│  ③ 记录 record/                                                   │
│     三层粒度: Trajectory / Turn / Subscene (§3.1)                 │
│     ★ 三分离: prediction / decision / outcome (§3.4)               │
│     ★ success 来自外部 (§3.3): judge verdict 或工具回执            │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 ★ 修 ARSI 缺陷 1：候选动作集与七管对齐

```text
ARSI 的 5 个动作 (dream/learn/evolve/maintain/remember) 是**记忆维护动作**,
不是任务动作 —— 因为 ARSI 的 actor 不做任务。

DWC 有两类动作, 必须分开:

甲 · 任务动作 (做任务)
   来自世界的 legal_actions(), 每个动作对应一个待探索的叶子
   ★ 这是 actor 的**主职**

乙 · 维护动作 (照搬 ARSI, 但明确它们是维护不是任务)
   dream / learn / maintain / remember
   ★ evolve 不进 actor —— 进化由 evolver 器官负责 (见 §2.4.2 归属表)
   ★ 且维护动作的 success 判定也必须外部化 (修 ARSI 缺陷 2)

★ 结构: 每轮 run_term 固定跑 N 个任务动作 + 1 个维护动作
  (维护动作的频率由 iwm 的 advice 决定, 不是硬编码)
```

### 4.3 ★ 痕迹 schema（DWC 版，补 ARSI 缺的五个字段）

```python
@dataclass
class Trace:
    # ── 身份 ──
    id: str
    trajectory_id: str          # ★ 新增: 属哪次完整执行
    turn_index: int             # ★ 新增: 第几次尝试
    subscene_id: str            # ★ 新增: 共享局部目标的分组 (§3.1)

    # ── 任务 (ARSI 缺) ──
    task_id: str                # ★ 新增: 在做哪个任务
    task_source: str            # world_node_id / sealed_dev / sealed_test

    # ── 三分离 (2609.08183 §3.4) ──
    prediction: dict            # 世界模型的预测 (含 confidence)
    decision: dict              # 实际决策 (含 source: 预测/LLM/启发式)
    outcome: str                # ★ 枚举, 不是自由字符串

    # ── 执行 ──
    action: str
    action_params: dict
    state_before: dict
    state_after: dict
    # ★ expected: 修"失败是非事件" (§3.2)
    expected: dict              # 本该发生什么 (调用前登记)
    observed: dict              # 实际发生了什么

    # ── 证据 (ARSI 缺) ──
    evidence: dict              # ★ 新增: 凭什么说这个结果
    success_source: str         # ★ 新增: judge_verdict / tool_receipt / NOT_EVALUATED
    success: Optional[bool]     # ★ None = 未评价, 不许当 False 也不许当 True

    # ── 失败定位 (Recuris 判据) ──
    failure_signature: Optional[dict]   # {c: 终止原因, q: 因果角色, m: 机制名}
    # ★ 没有 failure_signature 的失败痕迹, 不算合格痕迹

    generation: int
    timestamp: str
```

**★ 五处关键设计**：

```text
① success: Optional[bool] —— None 表示未评价
   ★ 修 ARSI 缺陷: ARSI 的 exec_ok 是 bool, 且被硬编码。
     DWC 允许 None, 且规则是 "None 不许当 False 也不许当 True" (见 §4.5)

② expected / observed 分离
   ★ 修"失败是非事件" (§3.2): 调用失败时, 记录里什么都没有。
     只有记下 expected, 才能发现"本该发生但没发生"。

③ failure_signature 是必填 (对失败痕迹)
   ★ Recuris 判据: "没有失败定位的痕迹不算合格痕迹"
   ★ 格式与 D5 一致: (c 终止级原因, q 因果角色, m 抽象机制名)

④ 三分离 (prediction/decision/outcome)
   ★ 2609.08183 §3.4: "被实际服务的东西不能当训练标签"

⑤ outcome 是枚举, 不是自由字符串
   ★ ARSI 的 outcome 是自由字符串 ⇒ 无法机械聚类
     DWC: PASS / WARN / FAIL / NOT_EVALUATED (照抄 §3.5 的四档)
```

### 4.4 ★ 修 ARSI 缺陷 2：success 判定的四级来源

```text
优先级 (高到低):
  ① judge_verdict    ← 密封任务集的判定 (进程外, 最强)
  ② tool_receipt     ← 执行器的真实回执 (如测试通过/失败)
  ③ self_report      ← ★ 只能记为"声称", 不许记为 success
  ④ NOT_EVALUATED    ← 无任何外部判据

★ 规则 (机械可检查):
   success is True   ⟺  success_source ∈ {judge_verdict, tool_receipt} 且判据通过
   success is False  ⟺  同上但判据未通过
   success is None   ⟺  success_source ∈ {self_report, NOT_EVALUATED}
   ★ 若 success_source == "self_report" 而 success is True ⇒ 违规

★ 修 ARSI 的三处硬编码:
   · remember 永远 False   → 改为: 由 tool_receipt 判定 (有回执才算)
   · learn 靠 distilled 计数 → 改为: distilled>0 且 judge 确认经验可用
   · effect 二值 (0.6/0.2)  → 删除; effect 只从外部源取 (照 ARSI effect_anchor 白名单)
```

### 4.5 ★ 新增：世界模型的门控接口（修原则 9 的落地）

```text
原则 9: 世界模型必须门控决策, 不许只做账本。

ARSI 的做法 (有问题): if pre_result["confidence"] > 0.1: 用预测
  ★ 0.1 太低 ⇒ 预测几乎总接管 ⇒ 实际是"预测独裁", 不是"门控"。

DWC 的做法: 门控有三个层级, 且必须留出 LLM 的机会
  ① 预测可用 (confidence ≥ τ_high, 且 iwm 未降级)
     → 直接用预测, 但记 prediction 到痕迹
  ② 预测弱 (τ_low ≤ confidence < τ_high)
     → ★ 问 LLM, 但把预测作为**先验**喂给它 (不是覆盖)
  ③ 预测不可用 (confidence < τ_low 或 iwm 降级)
     → LLM 独立决策

★ τ_high / τ_low 不许硬编码 —— 必须由 iwm 的校准器给出
  (修 ARSI 的 0.1 硬编码)

★ 判据 (可机械检查): actor 里不得出现浮点字面量作决策阈值
```

### 4.6 ★ 新增：Subscene 的构造规则

```text
★ 2609.08183 只说了 Subscene 是"共享局部目标的连续 turn", 没给算法。
  DWC 需要一个可执行判据:

Subscene 边界 (机械规则):
  · 新 Subscene  ⟺ 目标变化 (goal 字段的 new/modified 标记)
  · 延续 Subscene ⟺ 目标是 continued/resumed
  · ★ 工具结果不切分 (原文约束 ①)

失败定位的粒度 (2609.08183 §3.2 的用途):
  在每个 Subscene 内独立评价 → 再在 Turn 级聚合
  ⇒ 这样"中间失败 + 后续成功"能被区分

★ 四档评级 (照抄 §3.5):
  PASS / WARN / FAIL / NOT_EVALUATED, 且评估覆盖率单独存
  ★ 且: "Missing evidence or an interrupted judge call is never converted
    into a positive verdict."
```

### 4.7 ★ 新增：六维质量不压成单一分数

```text
★ 2609.08183 §3.2 原文:
  "retains the structural state, the six quality dimensions, and evidence
   coverage rather than **compressing them into a single heuristic score**"

DWC 的 actor 痕迹必须保留六维:
  goal_attainment / instruction_adherence / tool_use /
  evidence_consistency / error_recovery / termination

★ 为什么不压成一分 (DWC 自己的理由, 有实证):
  母巢 task_contract.py 的旧秤四分量 (presence/richness/novelty/quality)
  **全是输出形状** ⇒ 实干 0.5359 < 空壳 0.8504 (方向反了)。
  ★ 压成单一分数的后果: 空壳比实干得分高。
```

### 4.8 ★ 可机械检查的判据（gate.py 候选）

```text
A1 · success 来源合法
   success is True ⇒ success_source ∈ {judge_verdict, tool_receipt}
   依据: ARSI 的 remember 硬编码 False / learn 靠内部计数

A2 · 失败痕迹必须有签名
   每条 success is False 的痕迹, failure_signature 非空且含 (c,q,m)
   依据: 2608.24876 "没有失败定位的痕迹不算合格痕迹"

A3 · 三分离齐备
   痕迹必须同时含 prediction / decision / outcome 三个字段
   依据: 2609.08183 §3.4

A4 · 无硬编码决策阈值
   actor 目录下不得出现浮点字面量作 if 阈值 (如 confidence > 0.1)
   依据: ARSI core.py 的 0.1

A5 · expected/observed 成对
   每条痕迹必须同时含 expected 与 observed
   依据: 2608.24876 "失败是非事件"

A6 · 六维不压缩
   痕迹的质量字段必须是 dict (六维), 不得是单个 float
   依据: 2609.08183 §3.2 + 母巢 0.5359<0.8504 实证

A7 · 未评价不等于失败
   不得把 success is None 计入失败率
   依据: 2609.08183 "never converted into a positive verdict"
   ★ 同时也不许计入成功 —— 覆盖率单独报
```

---

## 五、诚实边界

```text
① ARSI 的 actor 我做的是静态审计 (读 core.py 全文 + grep 调用点), 未运行它。
   "remember 永远 exec_ok=False" 是 core.py 原文, 逐字核对过。

② 三层粒度 (Trajectory/Turn/Subscene) 是 2609.08183 的**训练语料**组织方式,
   不是 agent 运行时结构。我把它迁到 DWC 的痕迹组织 —— 这是**我的映射**,
   论文没有说"agent 运行时应该这样存痕迹"。★ 但 §3.2 的"分段评估"用途
   (区分中间失败与后续成功) 是论文原文明说的, 那部分是直接的。

③ Subscene 边界规则 (§4.6) 是我的构造 —— 论文只给了定义没给算法。

④ 四级 success 来源 (§4.4) 是我的设计, 论文只说"完成由外部回执验证",
   没有分级。

⑤ τ_high / τ_low 由 iwm 给出 —— 但 iwm 的校准器能否给出这两个值**未验证**。
   若不能, 退化为人工设定 (同 δ_θ 的处境)。

⑥ 六维质量评估需要"语义 judge" —— 它与 §4.1 的密封 judge 是什么关系**未定**:
   是同一个 judge 的两个用途, 还是两个独立组件? ★ 这是留给下一轮的缺口。
```

---

## 六、与 judge 设计的接口（原则 6 的进展）

```text
★ actor → judge 的接口契约:
   actor 产出 Trace (含 evidence 字段)
   judge 消费 Trace, 产出 Verdict
   ★ actor 不得自己填 success=True 当判据 (只能填 success_source)

★ actor → memory 的接口契约:
   Trace 写进 memory 的 PROXY 区 (见 MEMORY_SYSTEM.md 七管)
   ★ 必须带 failure_signature 才算合格痕迹

★ world_model → actor 的接口契约:
   W.legal_actions() → 任务列表
   ★ actor 不得自己造任务 (任务源唯一)
```

---

## 附：存证

```text
ARSI 源码: src/arsi/core.py (step / _execute_action_str / _execute_evolve)
           src/arsi/foundation/schema.py (BehaviorTrace)
           src/arsi/foundation/effect_anchor.py (EXTERNAL_SOURCES 白名单)
论文报告:  docs/papers/2609.08183.md (§3.1 三层 / §3.2 六维 / §3.4 三分离)
           docs/papers/2608.24876.md (§2.2 回执 / §2.2.3 Γ / Table 4)
已定文档:  docs/ACTOR_TASK_SOURCE.md (任务源 = 世界模型)
           docs/MEMORY_SYSTEM.md (七管) · docs/MEMORY_CONTENT.md (记什么)
```

```text
★ 本文引用的 ARSI core.py 五处原文, 已逐行核实行号:
   L491  confidence > 0.1 (硬编码决策阈值)
   L556  remember 硬编码 exec_ok = False
   L572  effect=0.6 if exec_ok else 0.2 (二值 effect)
   L692  remember 空操作分支
   L722  _execute_evolve 的 (placeholder) docstring
```
