# 补读笔记 · §2.1 + L3/L4 正文（R97b — 吃透声明的最后缺口）

> 背景: 用户追问「完全吃透没」→ 诚实盘点发现三块 50K 字符只有 Finding 摘要
> （§2.1 / L3 正文 / L4 正文）→ 本稿补读完成（2026-10-09 逐行）。
> 至此综述正文 228,927 字符**全部逐行**（我 100% + 子代理三笔记已抽验）。

## §2.1 Uneven Capability（@28529–37707）方法与三观察

- **HCI（Headroom-Closed Index）测量法**（Eq1–3）: 加权共识分（benchmark-owner 表 3 /
  独立同 harness 2.5 / 组合报告 2 / 模型作者表 1，**first-party 再 ×0.75 压自报**）
  → HCI 归一（0=入年前沿, 100=满分）→ 域轨迹=√n 加权的 90 分位前沿。
  协议不可链接的结果**留审计但不入轨迹**（33 中仅 17 入图）。
- **观察 1** 前沿增益幅度/时机各异: 2026 数学 86.4 / 研究生科学 85.8 / 广博知识 77.2 /
  法律 64.5 / 多模态 62.2；增量形态不同（法律 +48.2→+11.4→+4.9 放缓；数学
  32.8→53.6 加速；多模态 59.7→2.5 骤停）——单一聚合 benchmark 会掩盖这一切。
- **观察 2** 交互能力差距大: SWE 52.6 / 搜索终端 56.8 / **工具 agent 39.9（最低）**
  vs 研究生科学 85.8（差 45.9）; 网安 91.9 与工具 agent 差 52.0（**但 Cybench 子集变更
  =虚线警示**）。**有界易验证环境的增益未均匀迁移到长程有状态工作流。**
- **观察 3** 剩余 headroom 集中 RSI 潜在价值（示意式 R=100−0.22(100−T)：工具 agent
  39.9→86.8、SWE 52.6→89.6）——**示意图非预测**（原文自陈 illustrative）。
- 与自治分类学的对应: 有界评测≈L1–L2、环境任务≈L2–L3、交互工作流暴露 L3–L4 需求
  ⇒ **软件工程与工具使用是 RSI 主战场**（动机闭环）。

## §3.4 L3（@92842–112043）正文补读

- **判定属性**: learner-conditioned future experience acquisition 的**闭环依赖**
  （learner state ↔ 摄取 ↔ 持久学习 ↔ 后续摄取决策）。
  ★ **三个不构成**: 政策更新**顺带**改变访问状态不构成; 一次性过滤/保留不构成;
  管道自动化产出新样本不构成（§3.4.1 对工业数据管线的明确否定）。
  ★ 固定选择算法**可以**构成（只要用变化的 learner 反馈选后续经验）。
- **Table 5 逐格（9 行）**: 自适应任务生成/自博弈组（SSP/AZR/R-Zero/STP/PSV/VisPlay）
  + 环境自主练习组（VOYAGER/SIMA2/SEAgent），每行=Target × learner-conditioned 机制
  × 外部约束。R-Zero 一致性奖励=**代理非正确性证据**; PSV 难度标 easy/medium/hard
  **实际大幅重叠**=部分而非精确课程控制（原文自陈）。
- **Evaluating L3 对照设计**（可抄）: ①冻结摄取机制的 learner-state 输入（旧 checkpoint）
  ②换 learner-independent 日程 ③匹配数据源/算力/交互预算（**含经验生成与评估成本**）
  ④★**held samples 完全相同会移除要研究的分布适应本身**（对照设计的微妙边界）。
- **experience corruption** 概念: 缺陷经验/反馈跨轮传播（可进参数/技能/记忆/课程态）
  ——**结构性风险非每系统必然**; 评估须多轮追踪+有效性多样性+新任务迁移。
- ★ **引导课程的反馈 ≠ 保护性评估**: 通过任务选择/奖励构造/持久记忆反复访问测试
  实例会**使其成为学习过程的一部分**。

## §3.5 L4（@112516–133392）正文补读

- **三机制组 + Table 6 逐格（24 行）**: 轨迹蒸馏 / 迭代修订 agent 系统 / 选择性保留
  部署——每行 = Update target × Timing × **Update validation**（验收规则列：
  Dynamic Cheatsheet **无 held-out gate** · HarnessDev 冻结重放 hidden tasks ·
  ASPIRE verified score 不升即回滚 · DecoEvo 分数无关双审计+Pareto · HDSO 成对
  control/treatment · Library Drift 贡献衰减退役+封顶 · Tax AI 目标+回归测试+人工 PR）。
- **轨迹蒸馏四类**: 文本记忆（DynCheatsheet 单条演化笔记/ACE 计数器小补丁/ReasoningBank
  judged 轨迹→带标题策略）→ 结构化（APEX 里程碑依赖图回传+**未试分支显式加入**/
  PersonaAgent/PAHF 主动澄清/MemToolAgent 批评+动态检索数）→ 程序技能库
  （Trace2Skill 错误+成功双分析员分层合并/PRACTICE 批编辑增删合改/PANDO 在线规则/
  PILOT supervisor 蒸馏）→ **可执行工件**（Metis 高复用文本计划→**过沙箱编译才转**
  可调用工具/Evo-Harness 整 harness 模式/SHAPER 沙箱 Python）。
- **★ Harness Updating Is Not Harness Benefit（Lin 2026c）**: 更新能力与受益能力
  **分离**——更新能力基本独立于底模（小模型更新收益≈前沿模型）; 受益能力非单调，
  失败集中两模式: **①相关工件未被激活 ②激活但未忠实遵循** ⇒ **能力投资应放在
  解任务的 agent 而非 evolver**。→ 对 DWC 的直接提示: evolver 产出 Proposal 的
  「被执行器忠实遵循」率应是可观测量。
- **★ Library Drift**: 无界累积**逐渐劣化检索且先于任务分数可见**; 三件套=append-only
  证据日志（贡献衰减即退役）+活跃数封顶（新技能与存量竞争）+meta-skill 引导写入;
  **退役过激比无引导更差**（治理选择的非单调性）。
- **DecoEvo 循环性**: judge 随 solver 同涨可能=裁判变容易——解法=rubric 生成器
  **永不看 solver 总分** + 结构审计（覆盖任务需求）+ 对比审计（近平局区分力）双
  分数无关门 + Pareto。
- **HDSO 成对对照**: 同任务各跑两次（现批准库=control / 加候选技能=treatment），
  差异支持假设才入库，分级规模+独立任务确认。
- **Tax AI 生产门**: 字段级结构化纠正证据→重复失败分组成评测目标→**限定改动面**
  （抽取 schema/来源选择/映射器/评分器四件）→PR 人工审核→无法解决回流从业者。
- **Evaluating L4 + persistent update failure 四模式**: 错误教训/超范围适用/不调用
  相关更新/牺牲旧能力——**最终任务分数无法分离这些机制**; 可信评估必须把每个保留
  改变连到其证据→后续使用→新旧任务效果（→ DWC 知识档+证据链正是该形态的骨架）。
  反馈可能**内生于循环**（标签噪声/评估器随系统变/好工件仍不被执行）。
