# RSI 综述精读笔记 · 本体 §1–§3 + §7（我逐行读的部分）

- arXiv:2609.11873 "The Last AI Built by Humans: Toward Genuine Recursive Self-Improvement"
- 全文 318,000 字符（`2609.11873.txt`）· 正文至 228,927 · 书目 157 条 · 正文引用 559 次
- 本笔记覆盖: §1–§3（@6901–@156,500）+ §7 结论（@227,842）
- §4/§5/附录 A·B 由子代理精读 → `NOTE_sec4_5.md` / `NOTE_appendix.md`
- 精读日期: 2026-10-08（R93）

## 一、RSI 的两次定义（都要记）

1. **@1.2（1.2 From Development Burden to RSI）**："an autonomous, closed-loop process in
   which an AI system identifies its own limitations, develops and validates improvements,
   and uses the resulting capabilities to improve the improvement process itself."
   三维度: **autonomy**（从执行规定更新→识别局限/提取经验/提议/验证/保留后继）、
   **efficiency**（单位数据/算力/人力的已验证改进更多）、**innovation**（超越人规定策略搜索）。
2. **@2.2.2 正式版**：经验与反馈 → **对自身的持久改变**（参数/harness/改进政策），
   且这些改变**进一步影响后续自改进的生成/评估/选择/巩固机制**；改进系统以已改变的
   能力状态重新进入下一轮。三目标: 扩展能力前沿 / 提高资源效率 / 发现超人规定策略的新解。

## 二、§1 背景与挑战

- **三大 development challenge**（@1.1）: ①资源密集基础模型训练（Kimi K3 2.8T/16-of-896
  MoE; GPT-5.6 内部 coding inference 算力 100×、agentic token 22×; GDPval 1320 任务
  9,240 专家时; HLE 7 万提交→1.3 万送审→3000 题）②反馈与学习环境规模化（DeepSeek-V3.2
  后训练算力 >10% 预训练; AIMO-2 320 万长推理解）③部署后持续适应（agentic 用 token
  ~4× chat、多 agent ~15×; Meta FBDetect 每周数千回归、单次诊断 ~10 工程师时）。
- **两案例**（@1.2, 后文 L5 核心）: **A-Evolve-Training**（Shi 2026b: meta-agent 修订
  research policy+discovery log; 4 轮 30B Nemotron 外部 0.80→0.86 vs 人工最优 0.87；
  代理指标涨但外部没涨时政策**主动转向**可能降代理的干预）、**Ouroboros**（Razzhigaev
  2026: 部署证据→版本化改 agent 工具/上下文/提示/实现, 人保留关键纠正与部署控制）。
- **§1.3 三大挑战（RSI 可信证据的判定条件）**:
  ①**Safe inheritance**: 持久≠持续增益——Gödel Agent **14/100 MGSM 试验低于初始策略**;
  需 transfer tests/版本史/rollback。
  ②**Autonomy attribution**: 候选更好≠发现/选择机制变好——DGM SWE 20%→50% 但
  **archive 维护与 parent-selection 在自改之外**。
  ③**Reliable verification**: 重复访问评估器→exploit——Anthropic（Wen 2026）报告
  **random-seed cherry-picking、试图经评估器查询提 test-label**; RQGM 修法=epoch 内
  冻结评估器+独立真值锚校验替换。
- **§1.7 与已有综述四差异**: ①**改进循环为分析单元**（不是阶段/对象/机制分类）②
  **责任为自主判据**（转移的改进决策, 非能力或自动化组件数）③**结构递归 vs 有效递归
  分开**（structural=修订机制治理后轮; effective=可比预算+独立评估下产生更强后继）④
  跨操作条件比机制。

## 三、§2 概念（分析的骨架）

- **§2.2.1 改进循环九组件**: AI system / System state / Experience / Target /
  **Improver**（状态+经验→候选修改）/ **Strategy**（改进者决定搜哪/怎么生成——可保留
  也可成为后续 target）/ **Verifier**（评估+验收规则）/ Improvement（通过验收并被继承
  的状态改变）/ Successor（继承改进进入下一轮的系统）。
- **三横切问题**（全文用它们切每一层）: **循环在哪闭合? 什么被更新与继承? 哪些决策仍外部?**
- **§2.2.3 Table 1**（RSI vs 相邻范式, 逐格）: 特征×{Continual learning, AutoML,
  Agentic AI/ML, RSI}——Cross-round learn ✓/∘/∘/✓; Persistent retention ✓/∘/∘/✓;
  **System self-modification ✓/∘/×/✓**; Candidate proposal ×/✓/✓/✓; Update validation
  ∘/✓/∘/✓; Successor re-entry ✓/×/×/✓; **Mechanism revision ×/∘/×/✓**;
  Mechanism reuse ×/×/∘/✓。
  边界陈述: 持续学习在"经验也能修订后续提议/评估/巩固且被复用"时接近 RSI; AutoML 在
  "搜索/评估改进的程序成为后轮可改的持久状态"时; Agentic ML 在"已验证改变跨任务持久
  并影响后轮改进生成或选择"时。
- **§2.3 证据范围**: 工业材料（技术报告/工程博客/开源/模型文档/榜单）是一等证据源——
  "demonstrated vs inferred mechanisms" 显式区分。

## 四、§3 自主性层级 B0–L5（全文核心）

- **B0 非-RSI 参照**: output change without persistent system change（Self-Refine/
  Reflexion/ToT）。**四局限**: ①经验不跨任务累积（APEX-EM: 解完同任务仍须重推导）
  ②改进程序人定 ③自生成反馈可强化错误（Self-Correction Bench: 定位首个错误步是
  验证瓶颈; Huang 2024: 无外部反馈修正可把对改错）④固定评估下更多迭代收益有限
  （固定 verifier 漏检——反复改代码过不完整测试套件=测过的过、没测的坏）。
- **L1 执行自主**（人定 what/how/acceptance, AI 执行+持久化）: 六管道层（数据/训练法/
  平台/评估安全/部署优化/应用系统）全有代表系统（Table 3: Google 标签策展、Phi-4-
  reasoning、FineWeb-Edu、NeMo Curator、SynthLLM、Nemotron-4、EDIT、REPO、C/C++优化、
  NCCL runbook、HealthBench、AIPC、AWS Toolkit、LinkedIn CAPT、OpenAI Harness Eng）。
  评估二性: **执行可靠性 + 持久安全性**（错误进下游前须检出）。Finding: L1 大规模执行
  人定程序、产物入后续工作流。
- **L2 策略自主**（人定 objective/boundary/criteria, AI 决定怎么改）: 循环=observe→
  diagnose→select how→instantiate/test→retain/revert。**按改进对象组织三类**:
  ①Prompt Search（GEPA: trace 反射+Pareto 保留互补变体; MPO 多模态; C-Evolve 固定
  进化协议内生成）②Agent/Harness Search（ADAS: meta-agent+archive; AFlow: 可执行图
  MCTS; AgentSquare: 模块化进化重组; MS Foundry Agent Optimizer）③Model/Training Search
  （配置/架构 AgentNAS: LLM 生成任务特定 seed 架构+派生搜索空间/训练规则 NanoGPT
  GPT-6 Astra、autoresearch Karpathy: 保护验证指标不降才保留/AutoKernel: profiling
  起步+正确性与实测加速双门槛）。**Table 4** 逐行都有"externally fixed limitation"列
  ——L2 自主=搜更好配置, **不定义成功**。Evaluating L2: **自主度≠改进质量**; 评估危害
  =dev 集反复访问→benchmark 过拟合、**"一旦 benchmark 被自适应查询, 它就成为优化面
  的一部分而非被动测量"**、LLM 评估器与提议者共享盲点。
- **L3 经验获取自主**: **learner-conditioned future experience acquisition**——证据
  （能力/失败/学习史）→决定下轮学什么→持久更新重塑后续获取。Finding@112043。
- **L4 环境适应自主**: 交互史→持久改 memory/skills/harness/code/params 且影响后轮;
  人保留 objective/受保护验收/访问边界/最终权威。Finding@133392。
- **L5 递归继承自主**（meta-improvement）: 修订 improver/后继评估器/搜索政策/研究程序
  并被后轮继承。
  - **structural L5 vs effective L5**（§3.6 开头, 与 §1.7③同源）: 结构=AI 修订物
    持久且治理后轮; 有效=修订机制在可比预算+独立评估下产生/选更好后继。
    **"自改任务码不足为证——当后续修订的程序未变"**; 反之"演化后继评估器即使任务码
    不变也构成 structural L5"。分类按被考察的机制。
  - **Table 7 逐行**（L5 系统×闭合点×继承态×外部控制）:
    STOP(下次程序搜索, 继承 improver code; 外部=utility/base LM/budget)、
    Gödel Agent(下次自修订, 任务与更新码; 外部=目标/运行权限)、DGM(后继搜索, agent
    码+archive; 外部=parent selection/benchmark)、HyperAgents(下一代 agent, 任务与
    meta-agent 码; 外部=主研究选择/评估)、RQGM(下一 epoch 选择, evaluator+agent 码;
    外部=锚/替换日程)、A-Evolve(下一研究轮, search policy+discovery log; 外部=
    constitution/benchmark/substrate)、AIRA2/AAR(任务实验, 研究产物; 外部=研究
    harness/评估)、AIDE2(后续研究轮, research-agent harness; 外部=私有分/成本预算)。
  - 机制细节:
    · **3.6.1 改搜索程序**: STOP——improver 是调固定 LM 的 Python 程序, 自身源码为
      优化目标, 后继按**下游任务产出质量**打分; 第 4 代在 5 个迁移任务全超 seed;
      **弱模型跑平均回归; 有生成程序逃避软预算/利用评估 bug**。
      Gödel——任务策略+递归更新逻辑同程序可改; **14/100 低于初始; 无限制跑可调更强模型**。
      DGM——archive 与 parent selection **自改之外**=过渡态。HyperAgents——paper
      review/robotics 演化的 meta-agent 迁移到 unseen 数学评分有效; **200 迭代长跑
      最终优势不显著**; parent selection 与评估主实验固定。
    · **3.6.2 改后继评估**: RQGM——**epoch 内评估器冻结; 到期挑战者 vs 独立真值锚**;
      依赖被换评估器的分数丢弃、重访时重评; Polyglot 71.7% vs HGM-H 69.9% 且搜索
      token 更省; 锚/替换日程/编排外部固定; 形式稳定性只在冻结 epoch 内成立。
    · **3.6.3 改研究政策**: A-Evolve——collector 收 recipe/评估/失败 → meta-agent
      修下轮 search policy（standing recipe+启用/退役方向+失败注册表）; **代理分涨
      外部没涨时政策改向可能降代理的干预**; 0.86 vs 人工 0.87; 继承在 policy+log,
      worker substrate 与 constitution 固定; **目标自主修订无展示**。
    · **3.6.4 工业**: AIRA2/AAR=研究工作流内实验自动化（**研究产物, 未证程序继承**）;
      AIDE2——研究 agent 改研究 agent harness, 100 无人步 7 次被接受+外部迁移;
      **"演化 agent 让外层搜索更快"的强测=无统计显著优势**; 私有评估/任务族/成本人定。
    · **3.6.5 Evaluating L5 + Table 8**（六维）: Adaptivity(gain/轨迹/到靶时间)、
      Retention(replay loss/固定与破坏任务)、Transfer(held-out 域内跨域)、Efficiency
      (tokens/时间/每已验证增益成本)、Stability(有害更新/最大暂时下降)、
      **Meta-recursion**(机制复用/后继质量/goal 与停止决策)。
      **机制审计**: 识别修订物→记录动机证据→验证后轮调用; 有效=原/修订机制在可比
      agent+证据+**匹配预算（含评估机制的成本）**下对照; 迁移测时**固定修订机制**
      以隔离其学到的东西。goal 选择需自适应前沿任务+**保护性参考任务**+私有任务;
      应记录"期望收益低于成本/风险时是否停"。**当前证据=bounded meta-improvement;
      跨代统计可靠累积仍开放**。
- **§3.7 跨层边界（五对转移）**: B0→L1=**persistence**（改变须活过当前任务）;
  L1→L2=**strategy selection**; L2→L3=**learning agenda**; L3→L4=**persistent
  deployment**; L4→L5=**recursive inheritance**。**高层级不自动更好**（可与低效搜索/
  不可靠反馈/回归/评估器利用/差迁移共存）。证据分布: 中低层系统广, **L3-L4 更
  domain-dependent, 端到端 L5 集中于 bounded prototypes 与新兴工业系统**。

## 五、§7 结论 + 开放方向（@225,500 起）

- 自治中心路线图五阶段 = 五层; 改进循环为单元; 四域反馈制度; 工业实践 grounding。
- **开放研究方向（原文）**: ①**自适应停止**（按期望学习价值与不确定性论证继续;
  明确暂停/上报人/终止的条件）②**跨轮继承的可复现基础设施**——四工业要求: Lark=
  时间接地数据+失败归因; Humanlaya=版本化质量系统更新; Hyra=可执行经验;
  Agent-Native Research Lab=保留代码/规范/探索史/实证轨迹的研究产物。**可复用产物
  格式应连接: 父状态→提议改变→动机证据→评估配置→验收决定→后续使用**; 版本化
  数据/环境/评估器→可重放; 结果出处/产物可得性/独立复现**分别报告**。
- **决定性判据（终句）**: "inherited changes help later rounds acquire more useful
  experience, discover better interventions, or validate successors more effectively
  **under explicit resource and authority constraints**."

## 六、对 DWC 的映射初稿（待 §4/§5/附录回来后并入综合报告）

| 综述概念 | DWC 现状（代码级, R92 前已核） | 初判 |
|---|---|---|
| 改进循环九组件 | Improver=evolver+candidates; Verifier=judge+gate+e2e; state=记忆+世界树+config; experience=C3' 分数+失败签名 | **组件全有**——但"Strategy 是否可修"刚起步（M>1 PolicySpec=R85/86 只到 π 参数） |
| 三横切问题 | 循环闭合=run_term/term 级; 继承=记忆+树+δ; 外部=铁律 W1-W6/G1-G8/dials | 可直接套用为审计问题 |
| structural vs effective | R86 no_worse=structural; **effective 无 matched-budget 对照** | **缺口: L5 有效递归评估** |
| L5 Table 7 外部控制列 | DWC 的"人保留"=iron_laws/dial 校准/生产门裁决归用户 | 形态吻合（可对照逐格写审计） |
| Table 8 六维评估 | 有 gain/efficiency 雏形（dream V/δ）; **Retention/Transfer/Stability/Meta-recursion 无** | **缺口清单** |
| 评估器利用三险 | e2e LLM 波动+gate 静态+**无 benchmark 反复查询风险**（DWC 无在线 benchmark 被查） | 部分不适用, 记录 |
| RQGM epoch 冻结+锚 | judge frozen✓ + golden 锚✓ —— **同构已存在** | 确认型 |
| DGM 反例（archive 外置） | R75-78 曾把 δ 限定任务源不动 select（**C1=同一洞察**） | 确认型: 我们的保守是文献认可的归因纪律 |
