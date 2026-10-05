# 进化维度总表 · 34 个对象

> 判据：R1 代码/文档有独立标识符 · R2 指向可被改变的系统部件 · R3 同物异名归并
> 验证：全部代码路径已实测存在（非 README 推断）
> 日期：2026-10-03

## 一、对象层（1-28）

| # | 对象 | 名称（同物异名） | 出处 | 代码标识符 / 证据 |
|---|------|----------------|------|------------------|
| 1 | 标量参数/配置 | MetaParams / Config / T1参数 / L3模型参数 / prompt_param / skill_threshold / cron_quota | v6-L0,L3 · Ultra-T1 · 母巢4层 · 母巢kind | `gene_specs` x150 · `CONFIG_` x54 |
| 2 | 提示词 | Prompt / prompt | v6-L6 · 母巢RSPL | `class Prompt` x12 |
| 3 | 技能 | Skill / L2技能层 / skill | v6-L2 · CIP · ARSI | `class Skill` x20 · `EmpowermentDimension.SKILL` |
| 4 | 记忆 | Memory / L1外部记忆策略技能 / memory / memory_management | v6-L8 · 母巢4层 · RSPL · HarnessX | `class Memory` x64 · `MemoryFacade` |
| 5 | 工具 | Tool / tool / tool_ecosystem / tool_use | v6-L7 · RSPL · HarnessX · ARSI模块 | `class Tool` x71 · c4 |
| 6 | 知识/语义 | Knowledge / T2语义 / knowledge | v6-L9 · Ultra-T2 · ARSI | `class Knowledge` x40 |
| 7 | 代码 | Code / L4底层代码 | v6-L4 · CIP | `AstMutator` (evolution/ast_mutator.py) |
| 8 | 架构/拓扑 | Architecture / L2工作流架构 | v6-L11 · 母巢4层 | `op_type='topology'` 仅注释 · **未使用** |
| 9 | 策略 | Strategy / policy | v6-L1 · RSPL | `class Strategy` x14 |
| 10 | 智能体 | agent / agent_loop | 母巢RSPL · ARSI模块 | `class Agent` x25 |
| 11 | 协作/社会图 | Collaboration / social_graph | v6-L10 · ARSI | `Collaboration` x90 |
| 12 | 上下文 | context_assembly / context_management | HarnessX-c2 · ARSI模块 | c2 · context_management |
| 13 | 观测 | observability / observation_management | HarnessX-c8 · ARSI模块 | c8 · observation_management |
| 14 | 执行环境 | environment / execution_environment | ARSI · HarnessX-c5 | `EmpowermentDimension.ENVIRONMENT` |
| 15 | 外部机制源 | T3 GitHub机制 / T4 论文机制 | Ultra-T3/T4 | `mechanisms/source_fetcher.py` |
| 16 | 评估器/奖励 | evaluation_and_reward | HarnessX-c6 | c6 evaluation_and_reward |
| 17 | 置信校准 | calibration | ARSI赋能 | `EmpowermentDimension.CALIBRATION` |
| 18 | 推理增强 | L0推理增强 | 母巢4层 | `CoT` x183 |
| 19 | harness | harness | ARSI赋能 | `class Harness` x30 |
| 20 | 基础设施 | infrastructure | ARSI模块 | infrastructure x20 |
| 21 | 元认知 | metacognition | ARSI赋能 | `EmpowermentDimension.METACOGNITION` |
| 22 | 任务分解 | decomposition | ARSI赋能 | `EmpowermentDimension.DECOMPOSITION` |
| 23 | 注意力 | attention | ARSI赋能 | `EmpowermentDimension.ATTENTION` |
| 24 | 训练桥 | training_bridge | HarnessX-c9 | c9 training_bridge |
| 25 | 控制/安全 | control_and_safety | HarnessX-c7 | ★ `FROZEN_DIMS={"c7"}` 禁进化 |
| 26 | 模型选择 | model_selection | HarnessX-c1 | c1 model_selection |
| 27 | 任务完成检测 | task_completion_detection | ARSI模块 | task_completion_detection |
| 28 | 元进化(提名) | MetaEvolution | v6-L5 | ★ 代码无此名；见 29-34 |

## 二、元层（29-34）★ 进化方式/标准自身可进化

| # | 对象 | 出处 | 代码证据 | 状态 |
|---|------|------|---------|------|
| 29 | **评估器自身** | RQGM 2606.26294 | `registry.py:2942` `_evaluator_epoch_check` (5处) | ✅ 实现 |
| 30 | **进化判据/适应度** | 蓝图 VERIFY ANCHOR | `registry.py:101` `evaluate_candidate` (10处) | ✅ 实现 |
| 31 | **代码自身(自指)** | Gödel 递归自指 | `semantic_evolution.py:154` `dynamic_patch` | ✅ 实现 + 7门 |
| 32 | **变异算子集合** | GA 算子 | `evolution_engine.py:99` MutationStrategy/CrossoverOperator/SelectionMethod | ✅ 实现 |
| 33 | **进化准入标准** | AntiEvolution | `anti_evolution_gate.py:53` + `selection_gate.py:231` | ✅ 实现 |
| 34 | **算法选择器** | Darwin Gödel Machine | 全仓零命中 | ❌ 仅设计 |

### 元层 29 · 评估器 epoch 化（原文）
```
registry.py 注释:
  C3 (2026-08-25, RQGM 2606.26294 蓝本): 评估器 epoch 化反思 —
  每 10 次 A/B 决策后检查"决策时预期 vs promote 后实际 effect"偏差,
  超阈值则调整 margin (过松收紧/过严放宽) 并清空采样缓冲
  (selective erasure: 只清被换评估器判过的记录).
  不改 SelectionGate 内部逻辑, epoch 管理在 registry 层.
```

### 元层 30 · 适应度公式（原文）
```
BLUEPRINT_MATCH_AUDIT.md:
  蓝图原文: fitness = 0.5×T1节点效用 + 0.5×EffectTracker均值 (双信号消自指)
  修复: registry.evaluate_candidate 改为逐对样本用 fused fitness
```

### 元层 31 · Gödel 自指沙箱 7 道门
```
_FORBIDDEN_TARGETS = ("loop","loop.py","agent_core.loop",
                      "safety","harness.wal","iron_law")
_static_guard       → 禁 import / __import__ / open / eval / exec / compile
                    → 禁访问 loop/wal/os/sys/safety/write_node/acquire_token
_policy_shape_check → 无 While(tick挂死) / 节点≤2000 / 函数≤16 / 须有产出
+ 执行门 / golden门 / 内源门
计数: n_patches / adopted / rejected_target / rejected_static /
      rejected_shape / rejected_exec / rejected_golden / rejected_endo
测试: tests/test_recursive_self_patch.py · tests/test_fix7_godel.py
默认: loop._godel = False (默认关)
```

### 元层 32 · 算子集合（枚举实测）
```
MutationStrategy    : gaussian / uniform / inversion / swap / power
CrossoverOperator   : single_point / multi_point / uniform / blend
SelectionMethod     : tournament / roulette / rank / truncation / sus
```

### 元层 34 · 设计原文（未实现）
```
HIVE_ENHANCEMENT_BACKLOG.md:
  母巢 GA 现在固定算法+启发式适应度, 缺"自己选进化算法"
  可落地建议: 在 evolution/ 加算法选择器, 维护多个优化器后端
  ★ 对应 Darwin Gödel Machine 元进化层
```

## 三、被剔除的项（有判据）

```
19 项  过程维度: 进化方向4(FORWARD/LATERAL/BACKWARD/STAGNANT)
                + 自适应阶段4(exploitation/conservation/release/reorganization)
                + Omega五步5(learn/reflect/reason/derive/implement)
                + Omega六步6(source/cross_ref/deep/absorption/implement/evolve)
  判据: 描述"怎么进化", 不产生 before_hash→after_hash

 5 项  产物成熟度阶梯: Evidence→Episode→ReasoningStrategy→Workflow→Skill
  判据: 同一对象的成熟度, 不是 5 个对象
```

## 四、关键发现

```
① 48% 同物异名: 56 项名称 → 28 个对象
   最狠一组: "标量参数" 被起 7 个名字

② 元层 6 个对象是我第二轮才发现的 —— 因为判据 R1 只查"类/常量",
   而元层对象多为方法(_evaluator_epoch_check)或藏在阶段注释下

③ 两个已死/冻结:
   第 8 架构/拓扑  op_type='topology' 仅注释, 实测 op_type 只用
                   gene_spec/update_node/rollback/openspace_probe
   第 25 控制安全   FROZEN_DIMS={"c7"} never an evolution target

④ 第 34 算法选择器: 设计过, 全仓零命中 ⇒ 未实现
```
