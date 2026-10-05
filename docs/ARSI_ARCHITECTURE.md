# ARSI 核心架构

> 来源：`src/arsi/` 实读 + `docs/PROGRESS.md` + `harness/pillars.py` + `core.py`
> 日期：2026-10-03

## 一、一句话

**ARSI = 一个自创生递归自我改进系统（Autopoietic Recursive Self-Improvement），由一个 `ARSI` 主类持有全部器官，`step()` 是完整决策+执行循环。**

---

## 二、六层支柱（`harness/pillars.py`，2026-09-23 二次研读后升格）

```text
Autopoiesis = 总纲，贯穿各层（不是并列的一层）

L0  Anchored Constitution         我们被允许成为什么       GAI 2609.13406
L1  Contracted Computation        每次调用上什么恒真       SEVerA 2603.25111
L2  Regularized MetaRSI           如何改而不自欺           RRSI × AIDE²
L3  Introspective World + Vitals  世界/自我如何流, 何时漂  SIWM/ODE/CTM + SAHOO
L4  Dream-RSI                     探索策略如何被梦出       2609.14858
L5  Evaluative Epistemology       什么算证据               Grader 2607.12790
```

**L0 里写死的一条（Maturana 组织/结构二分）**：

```python
"organization=rho_iron_laws_sealed_goals"       组织 = ρ 铁律，冻结
"structure=omega_harness_host_policies"         结构 = Ω harness，可改
"stage3_may_change_structure_never_organization"
```

---

## 三、四大支柱（README 自述）

| 支柱 | 回答的问题 | 落点 |
|---|---|---|
| **Autopoiesis** | 系统为何是活的 | 边界、自生产、Governor |
| **MetaRSI** | 改进算子如何组合 | 调度、铁律、增益归因 |
| **MWM / SIWM** | 世界与自我如何被建模 | η、预测、pre-enactment |
| **Dream-RSI** | 策略如何被递归改进 | 世界池、回放、GridPlan/β、manifest、eval 回退 |

---

## 四、运行时：`ARSI.step()` 三层决策

```text
决策优先级:
  1. Pre-enactment (Layer 2 dynamics 预测)   confidence > 0.1 就用
  2. LLM 决策                                 (LLM 可用时)
  3. 启发式                                    (兜底)

候选动作: ["dream", "learn", "evolve", "maintain", "remember"]

实际流程 (core.py 实读):
  0. 每 10 步训练 dynamics 模型
  1. siwm.refresh_state() → S_t = (Φ_t, Ψ_t)
  2. iwm.governor_advice(state) → 12 个建议字段
     含 degrade_to_baseline / downweight_pre_enactment /
        forbid_default_dream / prefer_learn / downweight_memory_ops
  3. Layer A: pre_enactment.select_best_adaptive(state, candidates)
  4. Layer B: llm_governor.decide(state, candidates)
  5. IWM 覆写: forbid_default_dream 时 dream → learn
  6. iwm.record_decision() 记 provenance (可回放"为什么选 a")
  7. _execute_action_str(action, state)
  8. 成本记账 cost_ledger.record_llm_call()
```

---

## 五、IWM — 内省世界模型（架构里最有特色的一块）

```text
"Real introspection requires:
   Q1 organ reliability      → control hooks
   Q2 knowledge frontier     → explore/exploit bias
   Q3 loop efficacy          → evidence-based self-metric updates (no η hand-twisting)
   Q4 transition ledger      → self-change audit
   Q5 decision provenance    → replay why a was chosen
   Q6 calibrate              → degrade to baseline when introspector is untrustworthy"
```

**六个器官（代码实测）：**

```text
OrganSelfModel          器官自模型 (behavior_predictor/dynamics/dream/portfolio/memory)
KnowledgeFrontier       知识前沿
LoopEfficacy            回路效能 (VERDICT_HURT / VERDICT_NEUTRAL)
TransitionLedger        自变更审计 (jsonl)
DecisionProvenance      决策溯源 (可回放为何选 a)
IntrospectorCalibrator  内省器不可信时降级回 baseline
```

**第 6 条是关键设计**：连"内省器本身"都有信任度，不可信就退回基线——这是母巢没有的。

---

## 六、铁律 G1-G10（不可被任何改进算子修改）

```yaml
G1  设计/执行分离    策略生成与突变落地解耦               warn
G2  分级安全门      层级越深阈值越高                    warn
G3  冻结/人类主权    冻结开关优先级高于所有进化           block
G4  审计触发        巩固须含 why/trigger/verify         warn
G5  客观效用锚      效果 ∈ [-1,+1]，禁自评              block
G6  熔断            CLOSED/OPEN/HALF_OPEN 状态机       block
G7  数学收敛        Lyapunov 函数单调下降               warn
G8  因果问责        假设→设计→结果因果链完整才激活        warn
G9  高熵校验        高熵记忆和决策主动生成验证请求         warn
G10 密封评估层      任务集/评分规则/发布门槛在所有写掩码之外  block
```

**不变式（代码原文）：**

```text
Invariant: for all reachable state S, for all improvement operator U:
       G(U(S)) = G(S)
The value of iron laws never changes after any improvement.
```

**4 条 block 级**：G3 人类主权 / G5 效用锚 / G6 熔断 / G10 密封评估。

---

## 七、九维赋能（`EmpowermentDimension` 枚举）

```python
skill / harness / knowledge / decomposition / metacognition
attention / environment / social_graph / calibration
```

**生命周期四阶段 + 轮换纪律**：

```python
STAGE_WEIGHTS = {"infancy": 0.3, "growth": 1.0, "maturity": 0.5, "decline": 0.8}

DimensionManager(max_per_term=2, min_data_sufficiency=0.3)
# Key design: each term focuses on 2-3 dimensions (rotation, not all-at-once).
```

**实测 6/9 完整闭环**（knowledge/decomposition/calibration/attention/metacognition/environment）。

---

## 八、模块地图（实测体积）

```text
harness        54 文件  253 KB   进化底座 (ModularRSI × HarnessX)
world_model    15 文件  185 KB   SIWM/WorldPool/ReplayWorld/ODE
adapters        9 文件  114 KB   host 耦合 (hermes/mimo/synthex)
foundation     20 文件  110 KB   schema/store/iron_laws/llm/cost_ledger
iwm            11 文件   84 KB   内省世界模型
meta           11 文件   82 KB   Dream-RSI 元层 (GridPlan/β sweep/eval_loop)
governor        7 文件   62 KB   决策器官 + 维度管理
empowerment     5 文件   61 KB   九维赋能引擎
mnemosyne       4 文件   22 KB   三区记忆
```

---

## 九、记忆底座：Mnemosyne 三区

```python
SELF       身份 (永不删除, 改进算子不能重写核心)
EXPERIENCE 提炼的智慧 (跨 agent 共享, 可归档)
PROXY      宿主原始轨迹 (喂料, 蒸馏后可清理)
```

**三道机制**：`DopamineGate`（写入门）/ `UtilityDecay`（效用遗忘）/ `EdgeDiscovery`（主动关联）。

---

## 十、架构的评价（我的判断）

### 强的地方

```text
1 约束层完整: 铁律 G1-G10 + block/warn 分级 + 不变式声明
2 内省有信任度: IWM Q6 "内省器不可信时降级回 baseline"
3 决策有溯源: DecisionProvenance 可回放"为什么选 a"
4 边界写进代码: organization(冻结) vs structure(可改) 是常量不是注释
5 记忆有淘汰: UtilityDecay 是"忘掉无用的"而非"忘掉旧的"
```

### 弱的地方（实测）

```text
1 进化不落地: evolver.py 原文 "Does not auto-edit core
   — manifests are reviewable artifacts"
2 梦境评估 42.8% 无差异: compare_log.jsonl 1095 行里 469 行
   delta_score == 0.0 (dream_avg == fixed_avg)
3 17 次 rollback 全是 LIVE_REGRESSION (真实退化), 不是"梦比现实好"
4 重心偏了: harness 253KB vs mnemosyne 22KB = 11.5:1
5 判据未冻结: taxonomy 只冻结 c7(control/safety), Grader/评分器不在冻结名单
   这违反 DWC 原则 2
```

### 一句话总结

**ARSI 的架构设计比母巢干净（约束层完整、边界写进代码、内省有信任度），但它的进化同样不落地，且判据没有被冻结——这两点正是 DWC 要修的。**
