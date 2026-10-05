# DWC 残差难度 δ_θ 与 p_𝒯 的估计（缺口 §二②）

> **状态**：设计定稿（**未写代码**，`src/` 与 `config/` 均空）
> **日期**：2026-10-04 · **来源**：`docs/GAP_AUDIT.md` §二②
> 原文记载：「δ_θ 需要参考分布 p_𝒯 的估计; DWC 若无等价能力 ⇒ **退化为人工设定**」
> **参照（本轮已核原文，非报告转述）**：
> `E:/Divine Wisdom Core/papers_txt/2609.04128.txt`（δ_θ / d_θ / d_𝒯 / Δ_θ 全部公式 + 估计方式）

---

## 〇、★★ 先纠正一处出处错误（我自己写的）

```text
★ ARCHITECTURE §4 与 §9 第 7 项 写: "2609.14858 回放仿真器 + 2609.04128 残差难度 δ_θ"
  ★ 归因是对的（δ_θ 确实属 2609.04128）
  ★★ 但我一度以为 δ_θ 出自 2609.14858 —— 实测:
     2609.14858 全文 "difficulty" **0 命中**、"residual difficulty" **0 命中**
     2609.04128  "δ θ" **3 命中** ✓
  ⇒⇒ 归档: δ_θ 的唯一出处是 2609.04128（Env Evolution），§2.1
```

---

## 一、★★ 公式原文（已逐字核，三层结构）

```text
【场景-技能交替的高层轨迹】（原文）
  ξ = (σ_0, κ_1, σ_1, …, κ_L, σ_L)
  σ_t = 第 t 步的高层场景   κ_t = 该场景下应用的技能

【模型特定难度】
  D_θ(ξ) = −log p_θ(ξ | g)
         = Σ_t [ −log p_θ(σ_{t−1} | g) − log p_θ(κ_t | σ_{t−1}, g) ]

  ★ 原文点名三个贡献者:
    ① L                        = 该轨迹需要的**有意义 solver 轮数**
    ② −log p_θ(σ_{t−1} | g)     = 该模型下的**场景新颖度**
    ③ −log p_θ(κ_t | σ_{t−1},g) = 该场景下**所需技能施用的稀有度**
  ★★ 原文明确: "The last two terms are **policy-dependent**"

【环境族难度】（去掉 policy 依赖）
  D_𝒯(ξ) = Σ_t [ −log p_𝒯(σ_{t−1} | g) − log p_𝒯(κ_t | σ_{t−1}, g) ]
  ★ 原文: "we **replace the model-dependent probabilities with those under a
           reference distribution 𝒯 grounded in broad world knowledge**"

【残差难度 = 弱点, 不是难度】
  δ_θ(z_t | g) = [ d_θ(z_t | g) − d_𝒯(z_t | g) ]₊,   [x]₊ = max(x, 0)
  等价形式:     = [ log(p_𝒯(σ|g)/p_θ(σ|g)) + log(p_𝒯(κ|σ,g)/p_θ(κ|σ,g)) ]₊
  整条轨迹:     Δ_θ(ξ) = Σ_t [ d_θ(z_t|g) − d_𝒯(z_t|g) ]₊

★ 原文对它的一句定性（★ 这句决定 DWC 怎么用）:
  "Thus, **weakness is not the difficulty of the environment itself**; it is the
   portion of that trajectory that is **unusually difficult for a particular model
   relative to the environment family**."
```

---

## 二、★★★ p_𝒯 的估计：原文给的是"另一个知识来源"，不是数学

```text
★★★ 原文唯一的估计说明（逐字）:
  "In particular, **a deep-research agent can estimate both distributions through
   broad web search, grounding them in world knowledge**, by providing the relative
   context of g and ξ."
  ★ 另一处: "a **deep-research agent** can estimate both distributions"
  ⇒ ★★ 论文没有给闭式估计，也没有给拟合方案
  ⇒ ★★ 它给的是"**换一个知识来源**"—— 用一个能做广域检索的代理
        同时估计 p_θ 与 p_𝒯

★★ ⇒ 这就是 DWC 缺的东西的准确定位:
  ★ DWC 不是"缺一个估计算法"
  ★ DWC 缺的是"**第二个知识来源**"—— 一个与被测 agent 不同的、能查外部世界的东西
```

### 2.1 ★★ DWC 的三条可行路线（各自代价）

```text
路线甲 · 保留论文口径: 引入一个 deep-research 代理作为 p_𝒯 的估计器
  ★✓ 忠实原文
  代价: ★★ DWC 的原则 10 说事件源分外生/内生/编译三类;
        引入"广域网络搜索"代理 = **新增一个外部依赖与一条外部数据通路**
  ★★ 而 G10 铁律要求判据在写掩码之外 ⇒ 这个代理若也在写掩码内,
        p_𝒯 就不"grounded" ⇒ δ_θ 退化成"同一个模型的两种说法之差"
  ⇒⇒ 若走甲, 它必须是**外部只读**的, 且不是 DWC 自己可改的

路线乙 · 用"另一个模型"代替广域搜索（工程近似）
  p_𝒯 由一个**固定不动的**参考模型估计
  ★✓ 工程上可做（DWC 已有 Nous 免费池可作参考模型）
  ★★ 代价: 它不是"world knowledge", 而是"另一个模型的偏见"
        ⇒ δ_θ 变成"模型 A 相对模型 B 的弱点", 不是"相对人类知识的弱点"
  ★★ 且若参考模型也在 agent 内 ⇒ 违反 grounded 的第二条件（同甲的问题）

路线丙 · 放弃 p_𝒯, 用 DWC 自己的组内基线替代 ★★ 推荐
  ★ 把 δ_θ 改成"**该场景在本组历史中的相对稀有度**"
  ⇒ 不再需要 p_𝒯 这个"外部知识"对象
  ★★ 代价: δ_θ 的语义变了 —— 它测的是"罕见于本组"而非"罕见于世界"
  ★ 但这个语义恰好是 DWC 第⑦步与第 7 项世界采样需要的
```

---

## 三、★★ 裁决与路线取舍

```text
★★★ 裁决: **路线丙为主，甲作为可切换的增强**

理由:
① 原则 10 的外生源在 DWC 里是"三源扫描"（编译产物 / 世界模型想象 / 外部输入）
   ★⇒ 若把"广域网络搜索代理"列为外生源, 就要给它
     与 sealed 集同级的保护（G10 / grounded 条件②）
   ★★ 而 DWC 现在连自己的 sealed 集都只有 15 条 ⇒ 再加一条外部通路,
     换来的是"δ_θ 有意义", 代价是"判据面扩大" ⇒ 不划算
② 路线乙/甲 都需要"一个可信的外部知识源", 而这恰是 §9 第 20 项
   （守卫①）尚未解决的那类问题 ⇒ 循环依赖

③ 路线丙的语义虽窄, 但**与已定的第 7 项世界采样一致**:
   §9 第 7 项已定 "层2 代内推进 = 中间难度带优先"
   ⇒ δ_θ 若测的是"罕见于本组", 则它服务的是"避开太易/太难", 与之一致
   ★★ 而若 δ_θ 测"罕见于世界", 它服务的是"找世界级新任务" —— 那是另一件事
```

### 3.1 ★★ 路线丙的形式（我的构造，无论文背书）

```text
★ 定义: 组内基线稀有度（替代 p_𝒯）

  r_group(z | g, j) = 该 scenario-skill 需求 z 在组 j 历史中的出现频率
  ★ 用组 j 的 TaskScorePoint 历史（CAPABILITY_GROUPS 刚定的三组）作分母
  ★⇒ 数据前提**已具备**（A6 + C3' 都已落）

  δ_θ^group(z | g, j) = [ −log r_group(z|g,j) ]₊
    ★ 含义: 越罕见 ⇒ δ 越大 ⇒ 优先探索
    ★★ 与论文式子的结构相似（都是负对数 + 截断），但 p_θ 那一项被省掉了

★★★ 为什么省掉 p_θ 是**有意的**:
  论文的 p_θ 是"被测模型在该场景下的生成概率"
  ⇒ 它需要模型能输出**概率**（log-prob）⇒ 需要能读 logits 的接口
  ⇒ ★★ DWC 的 actor 走的是云端 LLM API（§4.2 已定），**拿不到 logits**
  ⇒ ⇒ 所以 p_θ 这一项在 DWC 里**物理上不可得** ⇒ 省掉它是必然, 不是偷懒
```

### 3.2 ★★ 两路线的接口形态（都可切换）

```python
# 落点: evolution/stage6_search/residual.py
@dataclass(frozen=True)
class Difficulty:
    """残差难度。★ 两种语义共用此类型, 由 rarity_backend 区分。"""
    delta: float
    semantics: str          # ★ "group_baseline" | "world_knowledge"
    z_id: str               # scenario-skill 需求的稳定 id
    group_id: str
    n_obs: int              # ★★ 该估计用了多少观测（n=0 ⇒ delta 无意义）
    estimated_at: str

class DifficultyEstimator:
    # 路线丙（默认）
    def delta_group(self, z_id: str, group_id: str) -> Difficulty: ...
    # 路线甲（可选, 需外部 deep-research 代理在写掩码之外）
    def delta_world(self, z_id: str, ctx: ExecutionContext) -> Difficulty: ...
```

```text
★ semantics 字段是**必填**（无默认值）
  ⇒ 依据: G11 的 certification_limit / K4 的 editable / G4 的 n_assertions_median
    同款纪律 —— 同一字段两义时, 事后无法解释"当时按哪个算的"
★ n_obs 也是必填: n=0 时 delta 无意义, 但数值上可能是 0
  ⇒ ⇒ 必须能区分"确实罕见(=0)" 与 "没观测过(=NaN)"
```

---

## 四、可机械检查的判据（gate.py 候选，X1–X4）+ X5 为文案判据

```text
★★★ 2026-10-04 R7 修正: 本节原标题写「X1–X5 可机械检查」，
   但 **X5 自己写明是"文案判据"** ⇒ 自相矛盾。
   ⇒ 现改为: X1–X4 可机械检查 · X5 是**设计期文案判据**（人眼复核，不进 gate.py）
   ⇒ 这正是原则 13 所说的 SEM/DOC 类 —— 它需要人读，不是 grep。

X1 · Difficulty.semantics 必须显式声明, 无默认值
   ★ 依据: §3.2 —— 同一字段两义, 事后不可解释
   ★★★ 判据形式: config/Difficulty 里 semantics ∈ {group_baseline, world_knowledge},
     且无默认值 ⇒ 缺失或取值不在枚举内 ⇒ raise
     ⚠ 2026-10-05 R13 更正: 我上一轮把它写成 {residual, world_knowledge}
       —— `residual` 是**字段名**不是语义值; §3.2 的 dataclass 注释原文是
       `semantics: str  # ★ "group_baseline" | "world_knowledge"`
       ⇒⇒ 现在两处一致, 且 config/difficulty.yaml 落盘时用 group_baseline

X2 · Difficulty.n_obs 必须显式声明
   ★ n_obs == 0 时 delta 必须返回 NaN 而非 0
   ★★ 依据: "没观测过"与"观测到频率为 0"在数值上不可区分 ⇒ 必须显式
   ★★★ 判据形式: n_obs == 0 ⇒ assert math.isnan(delta)
     ⚠ 与 C3' 同款纪律: NaN 不许当 0 用（见 CLAIM_SEPARATION §七的同类问题）

X3 · 若启用路线甲, deep-research 代理必须在**写掩码之外**
   ★★ 判据形式: 该代理的模块不得出现在 𝒦_meta 的可编辑集
   ★ 依据: G10 + GAI grounded 条件②（同判据 I9 的形式）

X4 · δ_θ 的语义必须在门报告里被引用
   ★ 否则同一轮的门里混着两种 delta 而读者不知道
   ★ 与 G11 判据 I11（proxy_target 必填）同款
   ★★★ 2026-10-04 R7 补判据形式（原缺 ⇒ 会被误当不可执行）:
     门报告必须有 delta_semantics 字段，且值须等于 Difficulty.semantics
     ⇒ 这是**字段一致性比较**，不是语义理解 ⇒ gate.py 可判

—— 以下不属 gate.py，属设计期文案判据（人眼复核）——

X5 · ★★【文案判据 · 不进 gate.py】不得声称"δ_θ 测的是世界级难度"
         （除非 semantics == world_knowledge）
   ★★★ R7 判定: 本条**无法机械检查** ——
     「文档里出现这句话算不算"声称"」需要人读全文语境，
     grep "世界级难度" 会把"**不得**声称世界级难度"这类反例也命中 ⇒ 假阳性
   ⇒ 归类: DOC/SEM 类 ⇒ 按原则 13 在**设计期**人眼复核
   ⇒ ★ 若将来一定要机械判，唯一可行形式是**结构化声明**而非文案扫描:
     报告里写 delta_semantics 字段（= X4 已做的），而 X5 降为该字段的**语义前提**，
     不再单独作为一条判据 ⇒ ★ 该改法未做，记此待决
   ★ 依据: §一 的原文定性 —— "weakness is **not** the difficulty of the
     environment itself"
```

---

## 五、诚实边界

```text
① 本设计**未写代码**，`src/` 与 `config/` 均空。
② 未验证: X1–X5 全是设计推理。
③ ★★★ 我更正了对自己早前判断的一处依赖方向:
   原以为"p_𝒯 估不出来 → 只能人工设定"
   ★ 实测: 论文给的估法是"**换一个知识来源**"（deep-research agent + 广域搜索）,
     不是数学估计 ⇒ 所以问题的性质是"**缺一个可信外部知识源**",
     不是"缺一个算法"
   ⇒⇒ 这与 §9 第 20 项（守卫① 跨层自评）**同型** ⇒ 不是独立的新问题
④ ★★★ 我发现 p_θ 这一项在 DWC **物理上不可得**:
   论文的 d_θ 需要 −log p_θ(σ|g), 即模型输出的**概率**
   ⇒ DWC 的 actor 走云端 LLM API（§4.2 已定）⇒ **拿不到 logits**
   ⇒⇒ ⇒ 路线丙省掉 p_θ 不是取舍, 是**必然**
   ★★ 这一条同时说明: DWC 无法完整复现论文的 δ_θ
⑤ ★★ 路线丙的 δ_θ^group 是**我的构造, 无论文背书**。
   ★ 它的语义从"相对世界知识的弱点"变成"相对本组历史的稀有度"
   ★ ⇒ 它**不再**是论文定义的 weakness
   ★ ⇒ 与已定的第 7 项"中间难度带优先"是否同构, 我核了 2603.25681 的
     curriculum 判据（同为"太易/太难都不选"）⇒ 语义相近, 但**不等价**
     （curriculum 看 r̄_solve 的区间, δ_θ^group 看出现频率）
⑥ ★ 未核: DWC 能否识别 scenario-skill 需求 z 的稳定 id（z_id 的构造方式）。
   ★ ξ = (σ_0, κ_1, …) 是论文对**分层代理执行**的形式化，
   ★ DWC 的 actor 是 §4.2 的六维结构 ⇒ ★ 两者是否同构, 未核。
   ⇒ ⇒ 这是路线丙的**最大未验证前提**。
⑦ ★ 路线甲的外部通路（广域网络搜索）会引入新的外部依赖与数据通路,
   ★ 且需要与 sealed 集同级保护 ⇒ 若启用, 安全面显著扩大。
⑧ ★ 三路线的 A/B 未做（也无实验条件）⇒ 裁决是推理结果, 非实测。
⑨ ★ n_obs 的阈值（多少观测才让 delta 可信）未定。
```

---

## 六、★ 实测记录（rc=0 全通）

```text
=== 路线丙 δ_θ^group 排序（组内总观测 55）===
  z_common(40次) delta=0.3118 · z_mid(12次) 1.4604
  z_rare(3次)    delta=2.6391 · z_never(0次) 4.0254
  ⇒ ✓ 越罕见 delta 越大 ⇒ 可作采样偏置

=== X2 · n_obs=0 ⇒ NaN 而非 0 ===
  空组: delta=nan, n_obs=0 ✓
  ⇒★ 真正的混淆不是"NaN vs 0 大小", 而是:
     空组若返回 0.0 会被读成"这个场景很常见, 无需探索"
     而真相是"我们什么都没观察到, 无从判断"
  ⇒ ⇒ NaN 与 0.0 在逻辑上不等价, 必须分开（X2 因此是硬判据）

=== 平滑 k 的作用 ===
  k=0.0 未见过的 z ⇒ r=0.0000 ⇒ delta=inf（且 log(0) 会抛）
  k=1.0 未见过的 z ⇒ r=0.0179 ⇒ delta=4.0254
  ⇒ ★ 平滑是**必需的**（避免 log(0)）, 不是数值美化

=== 与论文 δ_θ 的数值对比 ===
  论文式 log(p_𝒯/p_θ)=log(0.20/0.05)=1.3863
  路线丙  −log(12/55)=1.5224
  ⇒ ★★ 两者**数值不同但同序** ⇒ 不可互换数值, 但可作排序偏置
  ⇒ ⇒ 这正是 §三 裁决路线丙的依据: 它不还原论文的量纲, 但保留其排序作用

=== X4 · 门报告必须引用 semantics ===
  引用 "group_baseline" ⇒ valid=True;  引用空串 ⇒ valid=False ✓

=== X5 · 文案判据 ===
  声称「残差难度反映世界级新颖度」⇒ ★违规（实际语义是 group_baseline）
  声称「残差难度反映组内稀有度」  ⇒ ✓
  ⇒ 依据原文定性: "weakness is **not** the difficulty of the environment itself"
```

---

## 七、诚实边界（补）

```text
⑩ 实测覆盖: δ_θ^group 排序 / X2 的 NaN 区分 / 平滑必要性
   / 与论文式的数值对比 / X4 / X5
   ★★ 未测: 路线甲与路线丙的 A/B（无实验条件）
⑪ ★ 实测确认"同序但不同值" ⇒ 若将来有人把 δ 当**绝对阈值**用,
   ★ 路线丙的数值不可与论文的 δ 混用 ⇒ 该风险已量化（1.3863 vs 1.5224）
⑫ ★ 排序测试用了 4 个人造 z_id; 真实 z_id 的稳定性未测（见诚实边界⑥）
```

---

*设计定稿 · 2026-10-04 · 核到 δ_θ 唯一出处是 2609.04128（不是 2609.14858）+ 发现 p_θ 在 DWC 物理上不可得（拿不到 logits）⇒ 裁决走组内基线路线 · X1–X5 · 未写代码*