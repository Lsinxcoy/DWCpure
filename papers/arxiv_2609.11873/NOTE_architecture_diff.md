# 架构对照 · 综述的 RSI 架构 × DWC 实现架构（R97c）

> 方法: 综述 §2.2.1 改进循环九组件 + 三横切问题 + L1–L5 自治层级 ↔ DWC 七器官七环节。
> 行号证据由 `grep -n` 机器核验（2026-10-09, git 100）, 非记忆。
> 定位: 综述给**责任框架**（什么归 AI/什么归人）, DWC 给**器官实现**（怎么跑）——
> 两者正交, 互为审计。

## 一 · 九组件映射（综述 anatomy → DWC 代码）

| 综述组件 | DWC 对应 | 代码证据（机器核） |
|---|---|---|
| AI system | `class DWC` 主类（三入口收拢） | core.py:93 |
| System state（跨轮继承） | 三层: 记忆（MemoryNode/trace 链）+ 世界树（W1–W6）+ 锁值 config（dials/iron_laws） | world_model.py 内 W 纪律标记 ×5（grep -c） |
| Experience | C3' 分数点（TaskScorePoint+evidence）+ 失败签名 (c,q,m) + trace 记忆回执 | `_judge_and_backfill` core.py:252 |
| Target（本轮改什么） | `Proposal.target` + 单点改动构造拦截 | evolver.py:1079 / `_assert_single_change` :1168（:1164 构造时调） |
| Improver | `evolver.propose` + candidates（LLM 按 trace 推导, 2609.08183 分工） | evolver.py:1515; ProposalGate :1560 |
| Strategy | 任务源排序（δ/`_el_pick`）+ dream 选择策略（PolicySpec）——**只到参数级可修订** | core.py:292; replay.py:201 |
| Verifier | 四层: judge 真值判分（golden 锚）+ gate 静态纪律 + e2e 链路 + **生产门裁决归用户** | judge.py:96 Verdict / :686 evaluate / :923 evaluate_with_fallback |
| Improvement（被接受的状态改变） | 被 land 的 Proposal + 知识档（每轮声称/实测）+ MergeAccepted 固化 | archive/knowledge3_R*.json ×91 |
| Successor | **缺位（真实差异 §五-1）**——只有世界的快照后继, 无 agent 版本后继 | dream 消费 ℋ core.py:387 |

## 二 · 三横切问题对照

1. **循环在哪闭合** — 综述: 闭环处=自治级别的判定处; DWC: `run_term`（core.py:359,
   term 级: 执行→判分→回填→任务源→快照）+ `dream`（core.py:387, 离线评估选优）——
   同构且闭合点显式。
2. **什么被继承** — 综述: System state; DWC: 记忆+树+C3' 累积+δ+锁值——同构,
   且 W5 单向真值纪律（真值只进不改）使继承比综述多数案例更"硬"。
3. **哪些决策仍外部** — 综述: Table 7 External controls 列; DWC: W1–W6 + G1–G8 门 +
   锁值（B_WINDOW=8 el_sched.py:38 / NOISE_DELTA=0.15 evolver.py:657）+ judge 真值
   文件不可写 + 生产门裁决归用户——**两套体系是同一件事的两种写法, DWC 版更工程化**。

## 三 · L1–L5 逐层定位（DWC 在综述坐标系的位置）

| 层 | 综述判据 | DWC 判定 | 依据 |
|---|---|---|---|
| B0→L1 | 改变活过当前任务 | ✅ 远超 L1 | 知识档/记忆/固化跨轮持久 |
| L2 策略自主 | AI 决定怎么改; objective/criteria 外部定 | ✅ 成立 | δ 任务源排序 + EL 状态机（B/τ 锁值内自主调度）+ dream 选优; objective/验收在用户与铁律 |
| L3 经验获取 | learner-conditioned 闭环; **外部池的选择型也构成**（§3.4 明文: "Repeatedly selecting material from an externally supplied pool can exhibit this mechanism when selection adapts to the learner"） | ✅ 成立（选择型） | δ 从判分史（learner state）→ 排序下次任务 → 判分改 δ = 闭环存在; 任务池=外部 dev anchors（综述允许此形态） |
| L4 部署适应 | 部署交互→持久态改, 外部验收 | ⚠️ 形态有、环境不真 | 记忆写入（D6 门槛/FAILURE_SIGNATURE）=交互→持久态; 但"部署"=dev 任务循环非真实生产——bounded 任务流 |
| L5 structural | 修订物治理后轮改进 | ⚠️ 最小子集 | M>1 PolicySpec 修订 dream 选择策略且后轮继承（replay.py:165 select_policy / :189 no_worse / current 必含）——但修订**参数**非机制代码, 网格枚举非反馈开发（R85 稿自陈） |
| L5 effective | 可比预算+独立评估下产更强后继 | ❌ 无 | 无 matched budget 对照; 横搜证实该三件套 32 篇各≤1 篇（SYNTHESIS 三档计数「需更多设计」档） |

**一句话定位**: DWC = L2 稳 + L3 选择型成立 + L4 bounded + L5 structural 最小子集 +
effective 未做——与综述 §3.7「L5 集中于 bounded prototypes」的全领域画像一致。

## 四 · 相同点（结构同构 5 条）

1. 同以改进循环为分析/实现单元（run_term 七环节 ≈ propose→evaluate→retain→next）。
2. 同把「哪些决策仍外部」当一等公民（Table 7 External controls ↔ W/G 门+锁值+用户终审）。
3. 同向 structural/effective 分离（综述 §3.6.5 ↔ DWC「声称 vs 实测」三层验证——
   **雏形**, 缺 matched budget 那一半）。
4. 同向 verifier 独立性（golden 锚/TRUTH_SOURCE ↔ RQGM 独立锚、AIRA2 标签隐藏）。
5. 同用「接受规则」约束保留（ProposalGate/_assert_single_change ↔ Table 2 技术族 D 族）。

## 五 · 不同点（真实差异 6 条）

1. **Successor 缺位（架构选择非遗漏）**: 综述 RSI 强调后继系统继承（跨版本 agent）;
   DWC 是**单实例持续状态机**——快照 ℋ 是世界的后继, agent 自身无版本后继（git 知识档
   算痕迹不算机制）。引用「继承」时须说明是**状态继承非系统继承**。
2. **Strategy 可修订深度**: 综述 L5 案例修策略**代码**（STOP/Gödel）; DWC 只到**参数域**
   （w_delta/prefer_revealable, 锁值拒入）——刻意保守（R85）换可归因性。
3. **评估器路线相反**: 综述主流允许评估器共演化（RQGM/DecoEvo）; DWC 判据固定
   （𝒢_fixed 同族）——文献两面有据（RQGM 锚/日程也外控）, **有意的正面冲突**
   （SYNTHESIS 冲突 1 留裁决）。
4. **改进对象量级**: 综述案例多为权重/训练数据/部署 harness（大算力）; DWC 零训练
   （全库无梯度层）——落 Table 2 的 E 族+C6, **不落 C1–C4 训练族**。
5. **循环触发源**: 综述多为评估分数驱动实验轮; DWC=**机械节律**（run_term 轮转+EL
   窗口+δ 缓存失效）——无「LLM 反思后立项」（candidates 用 LLM 但按 trace 确定性
   推导）——触发自动化程度高、自主立项程度低。
6. **Verifier 分层更细**: DWC 把综述单 Verifier 拆为 judge+gate+e2e+用户终审四层——
   工程细化非理论分歧（DWC 超出综述粒度处）。

## 结论

**骨架同构**（循环/继承/外控三问完全可互译）; DWC 在 L1–L3 有实打实位置、L4/L5 是
bounded 最小子集; DWC 独有强化=**纪律可执行化**（W/G/锁值/单点拦截）, 独有缺位=
**Successor 版本机制**与 **effective-L5 对照**（两处均已入 SYNTHESIS 待拍/留位清单）。
