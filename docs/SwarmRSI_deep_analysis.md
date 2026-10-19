# SwarmRSI 深度学习分析 · Recursive Self-Improvement through Evolving Scientific Agent Swarm

> 论文：Qianru Meng et al., arXiv 2610.20431, 2026-10-14
> 对应 DWC：自进化代码修复系统（failure_sig → propose → trial → judge → adopt）

## 1. 问题定义

科学 agent swarm 的 RSI：多 agent 通过实验经验提升研究能力。两个障碍：
1. **失败归因模糊**：实验失败不知是 hypothesis 还是 implementation 的问题。
2. **整体分数掩盖有用组件**：表现差的程序可能包含其他 agent 需要的组件。

## 2. 核心机制（三层）

### 2.1 Feedback-Guided Swarm Mutation

- H-mutation：改变 hypothesis（研究方向）。
- P-mutation：保持 hypothesis，只修 implementation。
- 决策依据：其他 agent 的实验反馈（performance differences → hypothesis revision；unmet needs → program repair）。

### 2.2 Complementary Swarm Recombination

- **Rebase**：保留 hypothesis，换到另一个 agent 的 program base 上实现（need-label overlap 选 base）。
- **Crossover**：按 per-instance utility 优势组合 complementary 组件（Eq.5 donor selection）。
- 保留失败/无增益的程序，供后续复用。

### 2.3 Recursive Swarm Evolution

- 共享研究状态图 𝒢：hypotheses/programs/evidence/unresolved needs + edges（hypothesis–program 关联、parent/reuse 关系）。
- H/P selection：discounted-UCB（Eq.6）+ exploration + request pressure。
- 审计门控：code audit（执行状态/产物有效性/evaluator 反馈）+ scientific audit（源码/输出对比）→ hypothesis credit。
- 请求发射：failure → deepen（program refinement）；mixed gains/losses → broaden（hypothesis exploration）；new incumbent → deepen retained hypotheses。
- 状态更新：𝒢_{t+1}=Update(𝒢_t,ξ_t)；s_{t+1}=Assemble(q,𝒢_{t+1})。

## 3. 关键实证

- OpenProblems 平均 76.2（Gemini 3.1 Pro Preview），NatureBench Match-SOTA 44.4%（最高），MLE-Bench Lite Any-Medal 81.8%。
- DeepSeek-V4-Pro 一种子：~77% 最终 best programs 来自 rebase/crossover/feedback-triggered update。
- 继承状态迁移：held-out 任务 mean g 12.01→21.89，Match-SOTA 41.7%→86.1%。
- 失败分析：93.3% faithful interventions without gain；6.7% implementation/execution 问题；valid score 可掩盖问题（task 00838）。

## 4. 与 DWC 映射矩阵

| SwarmRSI 机制 | DWC 现状 | 差距 / 可吸收点 |
|---|---|---|
| H/P mutation 分类 | 单一 improve operator | **缺**：提案无 H/P 类型区分 |
| 共享研究状态图 | gene bank + archive | **缺**：无统一 inheritable state graph（hypothesis/program/evidence/needs） |
| Rebase | R351 recombination（whole） | **缺**：无“保留 hypothesis，换 base 实现” |
| Crossover（per-instance） | R351 recombination（whole） | **缺**：无组件级 crossover |
| Discounted-UCB H/P selection | U-shaped sampling (R353) | **缺**：无 H/P 前沿 + UCB 选择 |
| 审计门控 hypothesis credit | sandbox + judge | **缺**：无 code/scientific audit 门控 credit |
| 请求发射（deepen/broaden） | 无 | **缺**：无 unresolved needs 驱动下一轮 |
| 跨任务状态迁移 | archive priors | **缺**：无 inheritable state transfer |

## 5. 对 DWC 的可落地吸收（建议轮次）

- **R361 · H/P mutation 分类**：proposal.operator 扩展 H/P，gate K22。
- **R362 · 共享研究状态图**：inheritable state graph（hypothesis/program/evidence/needs），gate K23。
- **R363 · Rebase operator**：保留 hypothesis，换 base 实现，gate K24。
- **R364 · Per-instance crossover**：组件级组合，gate K25。
- **R365 · Discounted-UCB H/P selection**：H/P 前沿 + UCB，gate K26。
- **R366 · 审计门控 hypothesis credit**：code/scientific audit，gate K27。
- **R367 · 请求发射**：deepen/broaden/unresolved needs，gate K28。
- **R368 · 跨任务状态迁移**：inheritable state transfer，gate K29。

## 6. 风险与边界

- DWC 是 code-fix 进化，非科学任务；SwarmRSI 的 per-instance utility 需映射为 per-test-case utility。
- 审计门控可能过度拒绝（valid score 掩盖问题的反例）。
- UCB 需要 token cost 计量（DWC 目前无 token accounting）。

## 7. 结论

SwarmRSI 的核心贡献是 **inheritable research state + H/P mutation + complementary recombination + audit-gated credit**，与 DWC 的 gene bank/recombination 互补。DWC 已有 recombination (R351) 和 U-shaped (R353)，下一步可吸收 H/P 分类、rebase、per-instance crossover、UCB 选择与审计门控。
PY