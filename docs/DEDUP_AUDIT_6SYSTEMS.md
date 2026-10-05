# DWC · 6 套进化对象体系的严格去重审计

> 2026-10-03 · 判据：39 仓库源码逐字提取，两两交叉比对，不按 README/表格推断
> 触发：用户「我觉得应该先做严格去重审计」
> 方法：`scripts/dedup_audit.py` + `dedup_cross.py`，存证 `.cache/dedup_result.json`

---

## 一、六套体系的逐字清单（源码提取）

### 体系 1 · 12 层（Prometheus-X `layers.py`，实测 12/12）

```text
L0_MetaParams       Auto-tune evolution hyperparameters (from CIP_Hermes_v2 L0)
L1_Strategy         Explore/exploit strategy evolution
L2_Skill            Skill acquisition and composition
L3_Config           Configuration parameter evolution
L4_Code             Code quality evolution with AST mutations (from Protogonos + V8Pro)
L5_MetaEvolution    Evolution of evolution — layer interaction matrix
L6_Prompt           Prompt template evolution; 7 strategies + fitness tracking per strategy
L7_Tool             Tool configuration evolution
L8_Memory           Memory system evolution
L9_Knowledge        Knowledge base evolution with real graph operations. 5 operations
L10_Collaboration   Multi-agent collaboration evolution — team size and communication
L11_Architecture    Architecture evolution with real structural analysis. 5 operations
```

### 体系 2 · 9 维（ARSI `taxonomy.py`，实测 9/9）

```text
c1 model_selection        c6 evaluation_and_reward
c2 context_assembly       c7 control_and_safety    ← FROZEN_DIMS = frozenset({"c7"})
c3 memory_management      c8 observability
c4 tool_ecosystem         c9 training_bridge
c5 execution_environment
```

### 体系 3 · 4 层（hermes-collective-intelligence，实测 4/4）

```text
L1ConfigMutator    L2SkillMutator    L3BehaviorMutator    L4CodeMutator
```

### 体系 4 · 4 轨（Ultra，★ 实测有两套命名）

```text
版本 A (docs/multi_type_kb_seven_pipe_evolution.md):
   T1 参数  T2 语义  T3 提取  T4 编译
版本 B (docs/p7_handbook_behavior_localization.md):
   T1 参数  T2 语义  T3 GitHub机制  T4 论文机制
```

**★ 这是审计发现的第 1 处不一致**：同一仓库的两份文档，T3/T4 命名不同。

```text
对照源码实证:
   evolution_state.py      docstring: "EvolutionState — T1 进化状态跨会话持久化"
   semantic_evolution.py   docstring: "SemanticEvolutionEngine — T2 语义进化轨道"
   mechanism_extractor.py  → T3 (提取)
   mechanism_compiler.py   docstring: "MechanismCompiler — T4 第四轨: 将论文编译为新机制草案"
⇒ 源码支持 A 版 (T1持久化/T2语义/T3提取/T4编译);
  B 版 (T3 GitHub/T4 论文) 是"T3/T4 的取材来源"表述, 非轨道名。
```

### 体系 5 · 3 方向（Prometheus-X / Y）

```text
Prometheus-X strategies.py: ForwardDirection / LateralDirection / ReverseDirection
Prometheus-Y direction.py:  EvolutionDirection.FORWARD / LATERAL / REVERSE
```

### 体系 6 · 15 变异（MSTAR `mutator.py`，实测 15/15 枚举）

```text
Schema 变异 (3):  SCHEMA_FIELD_ADD / SCHEMA_FIELD_REMOVE / SCHEMA_FIELD_MODIFY
Logic 变异 (3):   LOGIC_READ_MODIFY / LOGIC_WRITE_MODIFY / LOGIC_QUERY_ADD
Instructions (7): KEYWORD_ADD / KEYWORD_REMOVE / KEYWORD_REPLACE /
                  THRESHOLD_ADJUST / PRIORITY_ADJUST / GUIDANCE_MODIFY /
                  CROSSOVER / ENSEMBLE
随机变异 (1):     RANDOM_CHANGE
```

**★ 这是审计发现的第 2 处不一致**：docstring 写 "Instructions 变异 (7)" 却列了 **8 个**名字（keyword_add/remove/replace + threshold/priority/guidance + crossover + ensemble）。实际枚举 15 个，所以总数对，但分类数字错。

---

## 二、★ 归并到统一对象后的覆盖

### 2.1 关键分类：对象 vs 过程

```text
★ 6 套体系里只有 4 套在枚举"对象" (12层/9维/4层/4轨);
  另外 2 套枚举的是"过程" (3方向 = 怎么变, 15变异 = 用什么手法变)。
  ⇒ 严格去重时必须先分这两类, 否则会把"过程"误当成"对象"。
```

### 2.2 各体系对【对象层】的覆盖

| 体系 | 对象数 | 覆盖 |
|---|---|---|
| 12 层 | 11 | 标量参数/超参, 策略, 技能, 记忆, 知识, 代码, 元进化, 提示词, 工具, 协作, 架构 |
| 9 维 | 9 | 模型选择, 上下文, 记忆, 工具, 执行环境, 评估器, 控制/安全, 观测, 训练桥 |
| 4 层 | 4 | 标量参数/超参, 技能, 行为/工作流, 代码 |
| 4 轨 | 4 | 标量参数/超参, 知识, 外部机制源(GitHub), 外部机制源(论文) |

### 2.3 ★ 并集 = 21 个对象

```text
1  标量参数/超参      8  提示词          15 评估器
2  策略               9  工具            16 控制/安全
3  技能              10  协作            17 模型选择
4  记忆              11  上下文          18 训练桥
5  知识              12  观测            19 行为/工作流
6  代码              13  执行环境        20 外部机制源(GitHub)
7  架构              14  元进化          21 外部机制源(论文)
```

### 2.4 ★★ 这是审计发现的第 3 处问题（最重要）

```text
旧表 (docs/EVOLUTION_DIMENSIONS_TABLE.md) 说 28 个对象层;
本轮 6 套体系并集只有 21 个。

差 7 个, 逐个核实:

  ① 智能体 (旧#10)        39 仓库零命中 (搜 agent_spec/AgentSpec/agent_evolution)
  ② 推理增强 (旧#18)      39 仓库零命中
  ③ harness (旧#19)       387 文件命中, 但它是"承载器"不是"被进化对象"
                          (HarnessX 是评估 harness, 不是进化目标)
  ④ 基础设施 (旧#20)      95 文件命中, 但全是基础设施代码本身, 非进化对象
  ⑤ 元认知 (旧#21)        19 文件 / 2 仓库 (仅 ARSI) —— 是 ARSI 独有维度
  ⑥ 任务分解 (旧#22)      125 文件 / 19 仓库 —— 但多为"用任务分解"非"进化任务分解"
  ⑦ 注意力 (旧#23)        136 文件 / 20 仓库 —— 同上
  ⑧ 任务完成检测 (旧#27)   11 文件 / 9 仓库 —— 同上

  ★ 复核更正 (我第一版口径过窄, 用宽口径重测):
    ① 智能体: 宽口径 191 文件 / 27 仓库命中 —— 但收紧到"进化模块内"仍有 42 处
       (ARSI taxonomy.py 的 agent_loop / MSTAR reflector_agent 的 "Agent analyzes
        failures → gene" / 母巢 reasoning_bank.evolve)
       ⇒ 不能判"零命中"。准确结论: **agent 作为进化对象有实现, 但只在 ARSI/MSTAR 少数仓库**
    ② 推理增强: 收紧后 8 处 (MSTAR predictor 的 reasoning 基因 / 母巢 reasoning_bank.evolve /
       prometheus-v3/v9pro/v10 的 speculative_evolution reasoning gene)
       ⇒ 同样不能判"零命中"。准确结论: **reasoning 作为可进化基因有实现, 覆盖 5 个仓库**

  ★ 真相 (修正后): 旧表把 ARSI 的 EmpowermentDimension 6 个类
    (KnowledgeDimension/DecompositionDimension/CalibrationDimension/
     AttentionDimension/MetacognitionDimension/EnvironmentDimension)
    当成了"6 个独立进化对象" —— 这一点仍然成立。

  ★ 实测 ARSI empowerment/dimensions.py 原文:
    "Three dimensions implemented with full closed loops:
     1. knowledge — detect missing knowledge, generate via LLM, validate via re-test
     2. decomposition — analyze task split quality, generate better splits, validate
     3. calibration — measure confidence-accuracy gap, generate calibration curve, validate"
    "Each dimension follows: sense → generate → validate → record"

  ⇒ 6 个类里只有 3 个有完整闭环 (knowledge/decomposition/calibration),
    另 3 个 (attention/metacognition/environment) 是同类实现但未声明闭环。
```

**★ 修正后的准确账**：

```text
旧表 28 个对象层  →  严格去重后 21 个 (6 套体系并集)
  移出 2 个 (非 6 套体系): 智能体 / 推理增强 —— 有实现, 但不属于任何一套体系,
                            列为"可选对象"待定
  删 2 个: harness(承载器非对象) / 基础设施(基础设施代码非对象)
  删 3 个: 元认知 / 注意力 / 任务完成检测 —— 是 ARSI 的"赋能维度"(dimension),
          与"可进化对象"不同层 (dimension 是"从哪个角度诊断", 不是"改什么")

★ 保留 21 个 (全部有 39 仓库源码出处)
★ 另: 旧表 #17 置信校准 = ARSI CalibrationDimension 有完整闭环, 应保留
```

---

## 三、★ 审计发现的第 4 处问题：元层 6 个的来源

```text
旧表元层 29-34:
  29 评估器自身    registry.py:2942 _evaluator_epoch_check   ← 母巢
  30 进化判据      registry.py:101  evaluate_candidate        ← 母巢
  31 代码自身      semantic_evolution.py:154 dynamic_patch    ← 母巢
  32 变异算子集合  evolution_engine.py:99 MutationStrategy    ← 母巢
  33 进化准入标准  anti_evolution_gate.py:53 + selection_gate ← 母巢+Z
  34 算法选择器    全仓零命中                                  ← 仅设计

★ 本轮 39 仓库实测补充:
  33 进化准入标准 有 4 个仓库实现 (Prometheus-Z 4前置 / ARSI 4步 /
     MSTAR 4门 / Prometheus-X 4步检测) ⇒ 是 6 套里覆盖最广的元层对象
  34 算法选择器 实测 Prometheus-X strategies.py 有 UCB1Bandit + IslandEvolution
     ⇒ 旧表"全仓零命中"不准确, 至少 Prometheus-X/Omega/Z 有 UCB1 实现
```

---

## 四、★ 修正后的统一清单

```text
【对象层】21 个
  1 标量参数/超参  2 策略      3 技能      4 记忆      5 知识
  6 代码           7 架构      8 提示词    9 工具     10 协作
 11 上下文        12 观测     13 执行环境 14 元进化   15 评估器
 16 控制/安全     17 模型选择 18 训练桥   19 行为/工作流
 20 外部机制源(GitHub)        21 外部机制源(论文)

【元层】6 个 (进化自己)
 22 评估器自身    23 进化判据   24 代码自身
 25 变异算子集合  26 进化准入标准  27 算法选择器

【过程层】18 个 (不是对象, 是"怎么变")
 3 方向: FORWARD / LATERAL / REVERSE
 15 变异: SCHEMA×3 / LOGIC×3 / INSTRUCTIONS×7 / RANDOM×1

★ 总计: 21 对象 + 6 元层 = 27 个可进化对象 (旧表 34 → 修正 27)
```

---

## 五、★ 与旧表 34 的逐项差异表

| 旧表项 | 本轮结论 | 判据 |
|---|---|---|
| #10 智能体 | ⚠ 降级 | 宽口径 191 文件/27 仓库; 收紧到进化模块内 42 处 (ARSI agent_loop / MSTAR reflector_agent) ⇒ 有实现但非 6 套体系之一, 降为"可选对象" |
| #18 推理增强 | ⚠ 降级 | 收紧后 8 处 (MSTAR reasoning 基因 / 母巢 reasoning_bank.evolve / v3/v9pro/v10) ⇒ 有实现但非 6 套体系之一, 降为"可选对象" |
| #19 harness | ❌ 删 | 387 文件命中但它是承载器, 非被进化对象 |
| #20 基础设施 | ❌ 删 | 95 文件命中但全是基础设施代码, 非进化对象 |
| #21 元认知 | ❌ 删 | 是 ARSI 赋能 dimension, 非对象层 |
| #22 任务分解 | ❌ 删 | 同上 (ARSI DecompositionDimension) |
| #23 注意力 | ❌ 删 | 同上 (ARSI AttentionDimension) |
| #27 任务完成检测 | ❌ 删 | 同上 (ARSI 模块, 非对象) |
| #17 置信校准 | ✅ 留 | ARSI CalibrationDimension, 有完整闭环 |
| #14 执行环境 | ✅ 留 | ARSI EnvironmentDimension + c5 execution_environment |
| #15 外部机制源 | ✅ 留 | Ultra T3/T4 实测 |
| #8 架构/拓扑 | ✅ 留 | 12 层 L11_Architecture + L10_Collaboration |
| 新增 行为/工作流 | ➕ 加 | hermes-CI L3BehaviorMutator 实测 (旧表无此项) |
| #34 算法选择器 | ⚠ 修正 | 旧表"零命中"不准, Prometheus-X/Omega/Z 有 UCB1Bandit |
| #33 进化准入标准 | ⚠ 修正 | 实测 4 个仓库实现 (覆盖最广的元层) |

---

## 六、★ 对 DWC 的影响

```text
① 对象层从 28 → 21
   上一轮 Q1 裁决的 21 个 = 16 明确 + 5 追加(工具/架构/智能体/评估器/基础设施)
   ★ 其中"智能体"和"基础设施"本轮实测无出处 ⇒ 追加项应改为 3 个, 不是 5 个
   ⇒ 修正: Q1 范围 = 16 + 3 (工具/架构/评估器) = 19 个, 再按 8a/8b + 16a/16b 拆

② 元层 6 个全部保留, 但 #33/#34 要修正描述

③ 过程层 18 个 (3方向 + 15变异) 应归入"进化算子"而非"进化对象"
   ★ 之前 DIMENSION_REPORT 把"进化方向 4 种"剔除是对的 (它是过程);
     本轮实测方向只有 3 种 (FORWARD/LATERAL/REVERSE), 旧报告写 4 种是错的
```

---

## 七、诚实边界

```text
① 本轮"零命中"判据是搜 39 仓库源码。若某对象只在文档/设计里存在而从未写码,
   会被判"删" —— 这是"实现级"判据, 与"设计级"清单不同。
② 4 轨两套命名 (A: T1持久化/T2语义/T3提取/T4编译 vs B: T3 GitHub/T4论文)
   源码支持 A 版为轨道名, B 版是取材来源。但两份文档都是你自己的, 需你确认。
③ MSTAR 15 变异的分类数字 (docstring 说 Instructions 7 个却列 8 个) 是文档瑕疵,
   实际枚举 15 个正确。
④ 旧表 #34"全仓零命中"仅指当时的 4 个项目; 本轮 39 仓库实测 UCB1Bandit 覆盖 11 仓库
   (Omega/Omega-Genesis/Omega-Omega/Ultra/Ultra-MultiTypeKB/X/Z/SYNTHEX...),
   ThompsonBandit 2 仓库, AdaptiveStrategySelector 1 仓库 (仅 SYNTHEX)。
⑤ ★ 自我纠错: 我第一版对"智能体/推理增强"用了过窄正则 (agent_spec/AgentSpec/
   agent_evolution/reasoning_enhance) 得出"零命中"。宽口径重测后两者均有实现。
   ⇒ 凡"零命中"类否定结论, 必须用宽口径复核, 否则会把"名字不同"误判为"不存在"。
```

---

## 附：存证

```text
脚本: scripts/dedup_audit.py  scripts/dedup_cross.py
数据: .cache/dedup_raw.json  .cache/dedup_result.json
源码: .cache/gh_clones/ (39 仓库)
```
