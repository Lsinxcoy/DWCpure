# RSI 综合报告 · The Last AI Built by Humans（2609.11873）全材料深读九节裁决 + DWC 强化方向

> R93–R97 · 2026-10-08~09 · 材料: 综述本体 318,000 字符 + 23 篇逐行精读 + 9 篇摘要级
> + 133 条无 ID 书目 + 反刍三轮。每条结论标注来源文件。

## 一 · 材料清单 + 逐字核实状态

| 材料 | 深度 | 状态 |
|---|---|---|
| 综述本体 §1–§3+§7（~150K 字符） | 逐行 | NOTE_survey.md · Table 1/2/4/7/8 逐格 |
| 综述 §4–§5（四域+工业） | 逐行（子代理） | NOTE_sec4_5.md · 209 源偏移 · 抽验 3 数字回原文命中 |
| 综述附录 A/B 大表 | 逐格（子代理） | NOTE_appendix.md · Table 11 44/44、Table 12 149/149 回查匹配 |
| 23 篇带 ID 论文 | **逐行**（全部标注） | docs/papers/<id>.md ×23（17–37K/份 · 引文归一回核 0 未命中） |
| 9 篇补搜新抓 | **摘要级**（abstract 逐字） | NOTE_idsearch_abstract.md（分层标注） |
| ~105 条其余书目 | 书目级（频次+语境） | refmap.json（157 条 · 559 正文引用） |
| 反刍 | 三轮三视角 | RUMINATE.md + ruminate_probe1.json |

**假阳性/假阴性排除记录**：① 2602.01550 搜到实为 NexusAgent ≠ OriGene → txt/pdf 已删
② refmap key 含 "et al." 双体系 → 归一后 157/156 收敛 ③ 子代理纠我预设错误（附录在
References 之后）④ EvoMDT/autoresearch 两 ID 待核（已标）⑤ HLE "3,000 题" 综述与论文
2,500 口径差（按未核标注，不改写）。

## 二 · 核心材料给出的缺口（带原文短引）

1. **effective recursion 没有可操作协议**——"matched budgets, including the cost of
   evaluating the mechanisms"（§3.6.5）是要求不是现状；横搜 32 篇 matched budget 仅 1 命中。
2. **跨代统计可靠累积未建立**——"Statistically reliable accumulation across generations
   under comparable resources remains open"（§3.6.5 Finding 前）。
3. **自适应停止是研究优先**（§7 原文）——期望收益<成本/风险时该停的判据未定义。
4. **跨轮继承缺产物格式**（§7）——"parent state → proposed change → motivating evidence →
   evaluation configuration → acceptance decision → subsequent use" 六段格式被点名待建。
5. **判得准⇒下轮更好的耦合度量**：全文仅 S3Gym 一次尝试且 ρ≈−0.010。
6. **四域全部未实现完整改进器演化**（§4 各域 gap 节）。

## 三 · 补读解出的硬结论（★标对应缺口）

- ★(1) **有效 L5 三件套各为孤证**（Verma matched-budget / RQGM 独立锚 / Verma 安慰剂）
  ⇒ 空白坐实而非共识缺失（RUMINATE 探针①②⑤）。
- ★(5) **S3Gym 实测**: agent 自评 agreement 0.496≈抛硬币、ρ(A,g)=−0.010；Chess 域自评
  与改进零相关 ⇒ 「judge 禁自评」从纪律升为有实测弹药的结论（同时裁决: HealthBench
  0.709 可用是**对象不同**——rubric 内容判分可对齐外部锚，非真冲突）。
- ★(4) **继承产物格式已有四工业对照物**（§4/§5: Lark 时间接地+失败归因 / Humanlaya
  版本化质量更新 / Hyra 可执行经验 / ARA 保留代码规范探索史实证轨迹——ARA 使问答
  93.7% vs 72.4%）。
- ★(2) **SEA-Eval 的 T 序列**（每已验证增益 token）+ pass^k（τ-bench: pass¹=61% 时
  pass⁸<25%）给出可复现的轨迹判据两件。
- **AIRA2 HCE 三段解耦**（80/10/10、标签隐藏、最终选择只用未参与搜索的 D_val）——
  搜索信号与选择信号分离的现成设计。
- **Dep(z) 定向失效**（RQGM dep set + Metis invalidate 两篇独立命名）。
- **Verma 安慰剂**: 看自己失败代码有害（−0.061 p=0.006, 锚定 2-14%→33-68%）；
  等预算盲重采样在 7B 以下全面最优。
- **经典法基线不容跳过**（HPO 评测: CMA-ES/TPE 一致胜 LLM agent 含前沿模型）。

## 四 · 新增可直接抄的机制（与缺口分列——均为「拿来即用」件）

| 机制 | 出处 | 落点（代码级） |
|---|---|---|
| meta-evaluation 协议（macro-F1+随机基线 0.50+人类分布分位） | HealthBench | dev 10 锚点旁各存独立复算——judge 侧零新器官 |
| pass^k 无偏估计 C(c,k)/C(n,k) | τ-bench | judge.score 输出加一维 |
| 重复采样+分布报告（两次 5-run 差 5–10pp） | Phi-4-reasoning | 判分链可靠性读数, 与 EL B=8 同源 |
| repair_layer 三行映射（失败事件→修哪一层） | AIPC §4.4.1 | FAILURE_SIGNATURE 加必填字段（D6 同款门槛） |
| recovered/regressed 配对口径 + invalid_conditions/recovery_strategies 字段 | PRACTICE 表4(+2.6pp) | 技能/经验卡 schema 扩展 |
| dynamic_n 检索（余弦一阶导峰值） | MemToolAgent | recall_search 可选实现 |
| 近重复合并 salience→摘要→τ 三步 | PAHF | memory 写入侧 |
| 技能 many-to-one 分层合并（128→B32） | Trace2Skill | dream specs 骨架自然落点 |
| 高 access+长期无 effect ⇒ 强制重验 | PAHF | access/effect 记账已有, 只差触发规则 |

## 五 · 文献路线关系

- 综述以「改进循环+责任」为单元，与四篇相邻综述（Tao/Gao/Fang/Ren）**互补非包含**；
  与「AI for AI」类框架（Liu/Zong/Xu/Ye）差异在责任判据。
- 23 篇精读各自谱系: L5 族（STOP→Gödel→DGM→RQGM→HyperAgents→A-Evolve→AIDE2）在
  §3.6 Table 7 串成一条; L2 搜索族（ADAS/AFlow/AgentSquare/GEPA）; 记忆族
  （VOYAGER→ReasoningBank→Trace2Skill→Evo-memory→Metis）。
- **勿把「没引用」当不相关**: H-JEPA（2610.06805, 本项目前一轮已深读）不在本综述
  书目——世界模型分层是相邻路线, 其 Table1 cost 几何结论已固化为 R92 方案 C 依据。

## 六 · 必须裁决的正面冲突（既有原则 ↔ 文献主流）

1. **评估器共演化**（RQGM 主流可做）↔ **DWC judge 固定判据**（2608.24876 𝒢_fixed 不进
   递归）——**建议维持 DWC**（先例: DGM 的 archive 外置也是刻意; 要开必须先过「改判据
   而非改代码」的裁决, 不默认开）。
2. **种群/交叉搜索**（AgentNAS/AFlow 主流）↔ **_assert_single_change 单点归因**——
   引入前必须先裁决归因模型（AgentNAS 自己也承认主表=seed42 单种子的消融问题）。
3. **多目标 Pareto 验收**（DecoEvo: 分数耦合对照 13/15 反向的教训）↔ **DWC 单目标
   no_worse_than_current**——升级属 M>1 域扩展, 留位待裁决。
4. **LLM 自修补臂**（部分族系主张）↔ **Verma 否定 + DWC 现状无臂**——**维持现状**,
   引入须配等预算安慰剂+锚定探针+k≈2 上限三件套。

## 七 · 缺口可结案度（三档计数）

- **已有实证答案可落**（8）: judge meta-eval / pass^k+重复采样 / repair_layer /
  CostLedger T 序列 / 记忆带失败对照 / 恢复配对口径 / 近重复合并 / 强制重验规则
- **待拍板**（5, 需你裁决）: HCE 第三段解耦（dev 拆搜索/选择信号）/ 成功侧归纳通道 /
  自评面审计三件套（仅当开自评面）/ Pareto 升级 / effective-L5 最小 matched 对照
- **需更多设计**（4, 留位）: 评估器共演化（先改判据）/ 种群搜索（先裁归因）/
  自适应停止（无标准可抄）/ 跨轮继承六段格式（四工业对照物需先统一设计）

## 八 · 最该记住的四条

1. **结构递归 DWC 已达标（M>1/no_worse/知识档链），有效递归是下一个战场**——且文献
   三件套各为孤证，DWC 是跟随设计者不是抄袭者（可先做 matched-term 最小对照）。
2. **judge 是 DWC 最强资产也是最大升级面**: RQGM 锚/HealthBench meta-eval/S3Gym 禁自评
   实测三篇都指向它——判分可信度的度量目前为零。
3. **可观测性缺口比机制缺口更实惠**: T 序列、pass^k、repair_layer、recovered/regressed
   全是「记账维度」而非新器官——一轮可落一批。
4. **守纪律有文献背书**: C1 单点归因（↔DGM 反例）、评估器固定（↔RQGM 边界）、锁值
   校准（↔HPO 经典胜）——DWC 的保守三条都被独立实证支持。

## 九 · 诚实条款

- 深度分层如实: **23 篇逐行** / **9 篇摘要级**（abstract 逐字, 未逐行）/ **~105 条书目级**
  （引用语境+频次, 无原文阅读）; 综述本体 §1-3+§7 逐行, §4-5+附录为子代理逐行
  （已抽验收数字）。
- 原文自陈限定已照录: 综述为叙述性证据范围（§2.3 工业材料一等公民）; HyperAgents
  200 迭代不显著; AIDE2 外层加速无统计显著; Push-T 3 层=数据不足归因。
- 转述口径差: HLE 3000 vs 2500（未核不改写）; EvoMDT/autoresearch 两 ID 待核;
  refmap f 值两处合并伪值（子代理已留痕）。
- 本报告数字均带源文件（NOTE_*/docs/papers/RUMINATE）; 未复核的不写具体数。

---

# 附: DWC 强化方向（结合当前实现 · 分级）

> 背景锚: DWC 当前 = 七器官/七环节/三入口 · 四机制活链（R84 自动化）· M>1（R86）·
> 三大借鉴方案（R92: A 单调性/B 段式回放/C 分层任务树）· 门纪律 G1-G8+W1-W6。

## P0 · 可直接落（一轮内, 不动判据不动 select）

| # | 强化 | 依据 | 动作 |
|---|---|---|---|
| 1 | **CostLedger 加 (round, task) 维 → T 序列** | SEA-Eval（Table8 Adaptivity+Efficiency 行, 即插即用） | term_cost/cumulative/rejected 已有, 补两列即可算「每已验证增益成本」 |
| 2 | **judge meta-evaluation** | HealthBench 协议 | dev 10 锚点独立复算 → macro-F1+随机基线+分位——**判分可信度从 0 到有** |
| 3 | **pass^k + 重复采样报告** | τ-bench + Phi-4 方差纪律 | judge.score 输出加维度; 单次判分链得可靠性读数 |
| 4 | **repair_layer 字段** | AIPC §4.4.1 三行映射 | FAILURE_SIGNATURE 加必填层（D6 门槛同款, 改动极小） |
| 5 | **进度指标单调性验证** | H-JEPA Fig8（R92-A 已固化） | 纯分析脚本, R88 数据现成——**先知道现有 cost 好坏** |

## P1 · 需裁决（中等工作量, 各带一个决定）

| # | 强化 | 依据 | 需你拍的板 |
|---|---|---|---|
| 6 | **成功侧归纳通道** | Trace2Skill + 10 篇横搜命中 | 成功轨迹→lesson 的归纳是否进 ingest 不变量②的扩展域 |
| 7 | **记忆带失败对照实验** | Evo-memory 表3 | 跑一组「DWC 现状 vs 剔除 FAILURE_SIGNATURE」对照（读 task_scores） |
| 8 | **HCE 第三段（搜索/选择信号解耦）** | AIRA2 | dev 是否拆 D_search/D_select 两段——现 dev 一肩挑两职是真缺口 |
| 9 | **段式回放（R92-B）+ 分层任务树（R92-C）** | H-JEPA + 本综述 cost 几何 | 已固化方案, 批准执行序即可（A 先行判断优先级） |
| 10 | **自评审计三件套**（Agree/NMAE/over-confidence） | S3Gym/HealthBench/RQGM | 仅当未来开任何 agent 自评面时启用; 现状维持禁自评 |

## P2 · 留位（撞判据/文献空白, 不默认动）

| # | 项 | 为什么留位 |
|---|---|---|
| 11 | effective-L5 matched-term 最小对照 | 三件套文献各≤1 篇——DWC 是跟随设计者; 先出最小版设计稿 |
| 12 | 评估器共演化 | 撞 𝒢_fixed 判据层硬约束——**先裁判据再谈代码**（RQGM 的锚/日程也全在外控） |
| 13 | Pareto 多目标 no_worse | M>1 域扩展, DecoEvo 教训=须配分数解耦+盲审计+冻结集四件套 |
| 14 | 自适应停止 | 综述开放方向, 无标准可抄——与 stop/预算类信号（10 篇各异）一并后置 |
| 15 | 跨轮继承六段产物格式 | 四工业对照物（Lark/Humanlaya/Hyra/ARA）需先统一设计再对齐 |

## 诚实不采纳（明确理由）

- **LLM 自修补臂**: Verma 否定域+DWC 现状恰绕开（candidates 确定性推导）——保持;
  若引入必须三件套（安慰剂/锚定探针/k≈2）。
- **权重训练**（SIA 族）: DWC 无梯度层, 全库零参数训练——架构边界。
- **种群/交叉默认引入**: 与 _assert_single_change 正面冲突——先裁归因模型。
