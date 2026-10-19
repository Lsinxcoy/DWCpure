# MASS 深度学习分析 · Recursive Self-Improvement through Multi-Agent Self-Supervision

> 论文：Hyunin Lee et al. (UC Berkeley × Sakana AI), arXiv 2610.12176, 2026-10-08
> 基座：Qwen3.6-27B-FP8 + qwen-code 0.20.0
> 对应 DWC：自进化代码修复系统（failure_sig → propose → trial → judge → adopt）

## 1. 问题定义

- **非可验证任务**（开放研究）的 RSI 监督瓶颈：输出超过人类专家可靠评估能力。
- 模型本身是最强可用的 optimizer + evaluator（optimizee = evaluator = optimizer）。
- 单实例同质循环：一个模型难以自我批判/改进复杂推理。
- MASS 的解法：**多智能体自监督** —— 用多 agent 工作流引出集体智能，再蒸馏回共享权重。

## 2. 核心机制（三层）

### 2.1 内层：进化式工作流优化（weights frozen）

- 把多 agent 协作编码为**工作流 prompt 文本**（角色 + 指令 + 输出契约 + 路由）。
- 进化搜索：propose → execute → self-evaluate → revise，受**结构护栏**约束。
- 评估：self-evaluator 对比两个 workspace（pairwise preference），Bradley–Terry 排名。
- 产出：最优工作流（computational graph-like orchestration）。

### 2.2 外层：SFT 蒸馏（weights update）

- 在优化后的工作流下生成轨迹。
- 联合微调共享模型：orchestrator 对话 + subagent 对话都算 loss。
- 更新后的模型重新担任全部三角色 → 递归循环 L0 → L1 → L2。

### 2.3 结构护栏（关键）

- 必须真实调用 worker（禁止空转）。
- 执行/验证指令追加到工作流（bare-prompt 评估时移除）。
- 交付物覆盖率 ≥ 0.6。
- 循环检测（相同 workflow 可因随机性成败）。
- 外部强模型（GPT-5.5/Claude Opus 4.8）最终报告，内部用 self-judge。

## 3. 关键实证

| 指标 | L0 | L1 | L2 |
|---|---|---|---|
| 测试任务 win rate vs base | — | 53.9% | 69.9% |
| ScienceAgentBench | 28.7% | 30.4% | 31.7% |
| MLR-Bench | 1.58 | 1.80 | 2.40 |
| AstaBench | 0.053 | 0.055 | 0.067 |
| DSBench | 0.473 | — | 0.482 |
| score/output token | 1× | — | 1.2–1.6× |

- 多 agent 轨迹训练效率：学生在 28.8M token 达到 68.3% win rate，单 agent 需 42M token（31% 更少）。
- 委派率：1/110 → 48/110 轨迹。
- 信息流：roles/instructions 任务信息 ↓，contracts/hops 任务信息 ↑（任务信息从“谁做什么”转移到“如何交接”）。
- 机制假说：**预测问题分离** —— orchestrator 映射 task+prior results → bounded assignment；subagent 映射 assignment+artifacts → implementation；两损失更新同一 θ，联合训练协调与局部执行。

## 4. 与 DWC 的映射矩阵

| MASS 机制 | DWC 现状 | 差距 / 可吸收点 |
|---|---|---|
| 三角色分离 (solver/eval/judge) | evolver 提案 / trial 执行 / judge 判分 | 已对齐；但 judge 与 mutator 共享 LLM 时存在同质循环风险 |
| 工作流作为可进化对象 | 单变更提案（one patch） | **缺**：无多 agent 工作流 primitive；可加 workflow candidate |
| 进化搜索 + 结构护栏 | gene bank + paired screen + reconstruct | 护栏部分有（sandbox/recovery）；缺 worker 调用要求、交付覆盖率 |
| Pairwise preference 排名 | paired screening (R348) | 已对齐 Bradley–Terry 思路 |
| 轨迹蒸馏 (SFT) | skill 系统 (R350) | 可把多 agent 轨迹蒸馏为 skill/prompt，而非权重 |
| 信息流度量 | 无 | **缺**：可加 contract vs role 信息流指标 |
| 委派率跟踪 | 无 | **缺**：可加 delegation rate |
| 循环检测/随机失败 | recovery (R354) | 部分；缺跨 seed 重复执行 |
| 外部强模型最终报告 | gate + external judge? | 已有 gate；可加外部 judge 审计 |

## 5. 对 DWC 的可落地吸收（建议轮次）

- **R355 · Workflow-as-graph primitive**：proposal 可编码 multi-agent 计划（agents/roles/contracts/routing），不只单 patch。gate K16 检查。
- **R356 · Pairwise workflow preference**：候选 workflow 两两比较（复用 paired screen），Bradley–Terry 排名。gate K17。
- **R357 · Structural guardrails**：要求真实 worker 调用、交付覆盖率 ≥0.6、循环检测、跨 seed 重复。gate K18。
- **R358 · Trace distillation**：把多 agent 轨迹蒸馏为 skill/prompt exemplar（复用 R350 skill bank）。gate K19。
- **R359 · Information-flow metric**：度量 contract vs role 任务信息流。gate K20。
- **R360 · Delegation rate tracking**：跟踪委派率，作为进化健康指标。gate K21。

## 6. 风险与边界

- DWC 不做权重微调（无 SFT），只能把轨迹蒸馏为 prompt/skill，效果上限低于 MASS。
- 自评器 agreement 仅 ~0.3，DWC 的 judge 也需外部审计（已有 gate，但缺外部强模型）。
- 同质循环风险：mutator 与 judge 共享 LLM 时，需保持 evaluator 独立性或引入外部 judge。
- 循环检测：相同 workflow 随机成败，需跨 seed 重复执行才能归因。

## 7. 结论

MASS 的核心贡献是 **multi-agent workflow 作为可进化对象 + 轨迹蒸馏**，与 DWC 已有的 code-level 进化互补。DWC 已吸收 Evo² 的 recombination/U-shaped/recovery，下一步可吸收 MASS 的 workflow-level 进化与轨迹蒸馏，但需注意 DWC 无权重训练的上限。
PY