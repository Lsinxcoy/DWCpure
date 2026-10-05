# DWC · 记忆到底记什么

> 2026-10-03 · 判据：只报实测，区分设计/实现/落地
> 问题：DWC 是独立 agent，记忆记哪些东西？毕竟要靠记忆驱动进化。

---

## 一、先看两边实测（都是反面教材）

### ARSI：121 万条记忆，平均 55 字符，98.8% 是机械模板

```text
memories 1,210,896 条 / traces 877,528 条 / causal_links 318,678 条
三区分布:  proxy 882,230  |  experience 328,674

content 实测样本:
  [learn] success (effect=0.60)
  [evolve] success (effect=0.63)
  [knowledge] sense=True gen=inject_knowledge val=unknown
  [calibration] sense=False gen=none val=success
  [brief] mimo-desktop: 深度分析 ARSI 系统的赋能闭环效果

★ 平均 55.4 字符 / 中位 48 字符
★ 121 万条里只有 1.2% 有 "[ACTION] outcome (effect=N)" 结构
★ generation 字段全 = 0 (1,210,904 条无一例外)
```

**问题：这些"记忆"里没有可复用的东西。** `[learn] success` 不是经验，是日志。

### 母巢：21 万条节点，平均 113 字符，但只有 9 条 procedure

```text
nodes 210,444 条
node_type 分布:
  fact       147,768   ← 71%
  concept     62,662   ← 30%
  procedure        9   ← ★ 0.004%
  episode          5   ← ★ 0.002%

平均 113.3 字符 / 中位 83

content 样本:
  [成功技能] 场景「hermes_ingest_concep」方法: 知识库中Hermes_i节点的偏好描述存在...
  [反面教材] 失败模式「timeout」(general) 累计 5 次失败: 遇到该场景不应照旧路径执行...
  [待验证技能] 场景「hermes_ingest_concep」方法: 确定性回答: 基于 5 条相关知识...
```

**★ 关键失衡**：21 万条里只有 **9 条 procedure、5 条 episode**。
即：母巢存了海量"事实"和"概念"，但**几乎没存"怎么做"**。
而进化要改的正是"怎么做"——**没有 procedure，进化就没有对象**。

---

## 二、论文怎么说（2608.24876 Recuris，DWC D2/D5 的来源）

### 2.1 记忆分两层，耦合才产生证据

```text
原文: "Working Memory tracks task progress and guides skill selection
      from Experiential Memory, grounding skill use in current needs
      rather than the full history. This coupling also turns execution
      into structured evidence that localizes failures to specific
      memory components."

★ 三个要点:
  ① Working Memory (𝒲) 追任务进度, 并从 ℰ 里选技能
  ② 选技能的依据是"当前需要", 不是完整历史
  ③ ★ 这个耦合把"执行"变成"结构化证据", 能把失败**定位到具体记忆组件**
```

**第 ③ 条是关键**：失败不是笼统的"任务失败"，而是"**哪个记忆组件**导致失败"。

### 2.2 进化的对象是 Skill Memory，不是全部记忆

```text
原文: "a fixed Meta-Agent turns that evidence into localized,
      validation-gated updates to Skill Memory that reshape execution
      and yield new evidence, forming a bounded recursive
      memory-evolution loop"

★ Meta-Agent 是**固定的** (不进化)
★ 只有 Skill Memory 被更新
★ 更新是 localized (局部) + validation-gated (过验证门)
```

### 2.3 论文的完整章节结构（架构索引）

```text
2.1 Skill Memory Architecture
2.2 Within-Task Verified EM–WM Coupling
    2.2.1 Structured Working State
    2.2.2 State-Grounded Skill Invocation
    2.2.3 Evidence-Grounded State Update
2.3 Bounded Cross-Task Skill Memory Evolution
    2.3.1 Trace-Based Failure Localization
    2.3.2 ...
```

**★ 注意 `2.2.1 Structured Working State`** —— 工作态是**结构化的**，不是自由文本。

### 2.4 一条硬事实：跨任务进化在无结构任务上失败

```text
原文: "Terminal-Bench 2.1 has no such structure, and cross-task
      evolution on it admitted no patch in thirteen runs of the
      evolution loop. What works there is retrying inside a single
      task, with or without memory written between attempts."

★ 跨任务进化 13 轮，一个 patch 都没产出 —— 在无结构任务上
★ 有结构才可进化。这是 DWC 选任务源时必须考虑的
```

---

## 三、DWC 记忆记什么（我的方案）

### 3.1 三区（照搬 ARSI，但补上"实质内容"）

```text
SELF       身份 + 铁律引用  (永不删除, 改进算子不能重写)
EXPERIENCE 可复用经验       ★ 这是进化的养料
PROXY      原始痕迹         (喂料, 蒸馏后可清理)

★ ARSI 的问题不是三区划分, 是 EXPERIENCE 里存的是 "[learn] success"。
  DWC 的 EXPERIENCE 必须存"可复用的东西", 不是"发生过什么"。
```

### 3.2 记四类内容（按"能否驱动进化"判定）

```text
① 任务痕迹 (PROXY) —— 每次 actor 行动一条
   字段: task_id / state_before / action / params / state_after /
         outcome / effect / ★ 失败定位(哪个记忆组件)
   ★ 判据: 没有"失败定位"的痕迹, 不算合格痕迹 (论文 2.3.1)

② 失败签名 (EXPERIENCE) —— 从多次同类失败归纳
   c = 终止级原因 (外部真值源, 枚举)
   q = 因果角色 (root / contributing / symptom)
   m = 抽象机制名 (跨轮可比)
   ★ 依据 2606.09498: 按三元组精确聚类, 不按语义相似度

③ 技能 (EXPERIENCE) —— ★ 这是论文里进化的直接对象
   论文叫 Skill Memory; 母巢叫 procedure (只有 9 条)
   字段: 场景(何时用) / 方法(怎么做) / 边界(何时不用)
   ★ 关键: 技能不是直接存的, 是从多次同类失败里归纳的

④ 工作态 𝒲 (PROXY 的特例) —— 当前任务进度
   ★ 必须结构化 (论文 2.2.1 Structured Working State)
   ★ 从"当前需要"取输入, 不是从完整历史取
```

### 3.3 明确不记的（避免变成第二个母巢）

```text
✗ 纯事实 (母巢 147,768 条 fact, 71%) —— 事实不进进化
✗ 纯概念 (母巢 62,662 条 concept, 30%)
✗ 机械日志 ("[learn] success (effect=0.60)" —— ARSI 的 121 万条)
✗ 自我评价 —— 撞原则 1 (判据必须在系统之外)
```

**判据**：**一条记忆值不值得存，看它能否成为进化的输入。**
不能的（事实、概念、日志）可以留，但**不算 EXPERIENCE**，不该参与进化。

---

## 四、记忆 → 进化的完整链路（这是"依靠记忆驱动进化"的落地）

```text
actor 做任务
   ↓ 产出痕迹 (含失败定位)
PROXY
   ↓ 蒸馏 (importance*0.6 + surprise*0.4 ≥ 阈值)
EXPERIENCE
   ├─ 失败签名 (c,q,m)   ← 按三元组聚类
   └─ 技能 (场景/方法/边界)  ← ★ 进化的直接对象
   ↓ evolver 消费
提案: 改哪个技能 / 哪个机制
   ↓ 过门 (非补偿式准入)
应用: 改 actor 的运行时旋钮  ← 原则 4 消费点
   ↓
新痕迹 → 回到第一步
★ 这个环一旦转起来, 才是"记忆驱动进化"
```

### 4.1 一个必须回答的问题：进化改"技能"还是改"代码"？

```text
ARSI: 改 manifest (声明式), 但 "Does not auto-edit core" ⇒ 不改代码
母巢: 改 gene (标量), 但产物不落地 ⇒ 不改行为
Recuris 论文: 改 Skill Memory (技能文本), 不碰模型与完整 agent 程序

原文: "Recuris recursively evolves M_k within a fixed outer agent
      harness rather than rewriting the underlying model or the
      full agent program."

★ 论文的选择: 进化对象 = 技能记忆, 外层 harness 固定
★ 这是个重要取舍 —— 不碰 harness, 只改技能
```

**DWC 建议**：

```text
第一版: 只进化"技能" (照论文)
  · 技能 = 场景/方法/边界 三字段文本
  · 进化 = 改写这三个字段
  · 不碰 harness, 不碰代码
  ★ 好处: 消费点明确 (actor 选技能时的检索结果), 可验证
  ★ 风险: 天花板低 (技能文本改不动系统结构)

第二版: 加上"机制参数" (照母巢 gene_applier 的设计)
  · 但必须满足原则 4 (运行时消费点 + 写入后读回)
```

---

## 五、与 DWC 现有决定的衔接

```text
D2  𝒲 工作态 / ℰ 经验态 双视图      → 本文件 §3.2 的 ④ 与 ②③
D4  记忆可淘汰 (append + evict)     → UtilityDecay 已定
D5  记录粒度 = 失败签名 (c,q,m)      → 本文件 §3.2 的 ②
原则 1 判据在系统之外               → §3.3 明确不记"自我评价"
原则 4 产物必须有运行时消费点        → §4 的链路末端
```

**新增一条**：

```text
D6 · EXPERIENCE 只存"能驱动进化的东西"
  事实/概念/日志不算 EXPERIENCE, 不进进化。
  ★ 判据: 这条记忆能否成为 evolver 的输入?
    不能 ⇒ 留在 PROXY 或另设归档区, 不占 EXPERIENCE
  ★ 依据: 母巢 21 万条里 71% 是 fact, 但只有 9 条 procedure
          —— 存了一堆不能进化的东西, 所以进化无对象
```

---

## 六、待你拍板

```text
Q1 EXPERIENCE 的准入判据用哪条?
   甲 "能否驱动进化" (严格, 我建议)
   乙 保留 ARSI 的 importance/surprise 阈值 (宽)

Q2 进化对象第一版定在哪?
   甲 只进化技能 (照 Recuris 论文, 我建议)
   乙 技能 + 机制参数
   丙 技能 + 参数 + harness

Q3 技能的结构?
   甲 场景/方法/边界 三字段 (照论文, 我建议)
   乙 自由文本 (好写但不可比)
```
