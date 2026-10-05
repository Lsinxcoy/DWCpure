# DWC 世界树收束（§9 第 24 项 · 收尾）

> **状态**：设计定稿（**未写代码**，`src/` 与 `config/` 均空）
> **日期**：2026-10-04 · **来源**：`docs/GAP_AUDIT.md` 缺口 A2 + §9 第 25 项 (y)(x)(v)
> **参照（本轮已核原文，非 ARCHITECTURE 转述）**：
> `papers_txt/refs/2507.19457.txt`（GEPA, ICLR 2026 **Oral**, 273,016 字符 —— §3.1 / Algorithm 2 / Appendix D.1 全部读过）
> `papers_txt/refs/2408.08435.txt`（ADAS，归档无剪枝）
> `papers_txt/refs/2505.22954.txt`（DGM，归档非贪心 +27.0pp）
> `papers_txt/2609.04128.txt`（EL / δ_θ）
> **本轮解决的**：
> ★ ARCHITECTURE §2 写"信息增益" vs §9 第 25(y) 建议"默认 Pareto" —— **那处不一致**
> ★ 缺口 A2：剪枝策略 / 想象节点存哪（被错塞在第 23 项里）

---

## 〇、★★★ 先说本轮最重要的一件事：**我否掉了自己上次的建议**

```text
★ ARCHITECTURE §9 第 25(y) 里我写的是:
  "★ 建议: 默认 Pareto(更稳), 但两条都要能声明与切换"

★★★ 核 GEPA 原文后 —— **"更稳"这个判断是错的**:
  Appendix D.1 原文逐字:
    "While in our analysis, we found **GEPA+Merge works especially well for
     GPT-4.1 Mini**, it **lead to performance degradation when used with Qwen3 8B**.
     **Even Qwen3 8B benefits from Merge on one out of four tasks.**"

  ⇒ ★★★ Merge 在弱模型上是**负收益**, 且 4 个任务里只有 1 个受益
  ⇒ ⇒ ★ 我建议的"默认 Pareto 更稳"没有任何依据
  ⇒ ⇒★★ 修正: 两条路线**都不是默认**, 必须按判据选（见 §三）
```

---

## 一、★★ 两条路线的原文对照（这是"并列化"的依据）

| | **路线① 信息增益单树深挖** | **路线② GEPA Pareto + 反思** |
|---|---|---|
| 出处 | WORLD_TREE 现有设计 + 2609.04128 δ_θ | 2507.19457（ICLR 2026 **Oral**） |
| 收束动作 | 按信息增益优先展开/剪枝 | 按 **逐任务实例的 Pareto 前沿**采样 |
| 反馈来源 | 外部观测量（δ_θ 等） | **自然语言反思**（"reflects on them in natural language to diagnose problems"） |
| 打分方式 | 标量分数 | 逐任务实例的分数向量 |

### 1.1 ★★★ 关键差异：Pareto 的**维度**不同（这是最容易被误解的一点）

```text
★★★ GEPA 的 Pareto 前沿是**逐任务实例**维度的, 不是"逐节点/逐候选总分"

  Algorithm 2（原文逐字）:
    1: function SELECTCANDIDATE(P, S)
    2:   // Build instance-wise Pareto sets
    3:   foreach i in D
    4:     s*[i] ← max_k  S_P[k][i]              ← 每个任务实例单独取最高分
    5:     P*[i] ← {P[k] : S_P[k][i] = s*[i]}    ← 在该实例上并列的候选
    6:   end for
    7:   C ← unique candidates in ⋃_i P*[i]
    8:   D ← ∅
    9:   while there exists Φ ∈ C\D dominated by another in C\D do
   10:     D ← D ∪ {Φ}                            ← 严格被支配的才剪
   11:   end while
   12:   Remove D from each P*[i] to get P̂*[i]
   13:   Let f[Φ] = number of i for which Φ ∈ P̂*[i]    ← 领先多少个任务
   14:   Sample Φ_k from Ĉ with probability ∝ f[Φ_k]   ← 按领先数加权采样
   15:   return index k of Φ_k in P
   16: end function

  §3.1 原文: "For each training instance, GEPA records the highest score across all
   candidates, **forming a Pareto frontier. Candidates that achieve the best score on
   at least one task are retained, while strictly dominated ones are pruned.**"

⇒ ★★ 与 DWC 能力组（A6 已定三组）的关系:
  GEPA 的 "task instance" ≈ DWC 的"能力组"或"组内任务"
  ⇒ ★ ⇒ 若 DWC 采纳路线②, **A6 的三组正好就是 Pareto 的三个坐标轴**
  ⇒ ⇒ ⇒ 这是 A6 与世界树的接口 —— 之前没想到这一层

⇒ ★★ 原文还给了路线①失败的反例（这是并列化的最强理由）:
  Figure 6a 原文: "**after finding one new strategy (the first child node), the search
   repeatedly attempts to refine it, fails to improve, and ultimately depletes the
   budget**" ⇒ ★ 单树深挖在找到一条新策略后会**反复 refinement 卡住**
  ⇒ ★ 而路线①（信息增益单树）正是"单树" ⇒ ★★ 它有这个已知病
```

### 1.2 ★★★ 但路线②有个硬限制（移植风险）

```text
★★★★ 限制: GEPA 是 **prompt optimizer**, 不是机制进化器

  摘要原文: "we introduce GEPA (Genetic-Pareto), a **prompt optimizer**"
  §7 原文:  "We introduced GEPA, a **prompt optimizer for arbitrary LLM agents
             and workflows**"

⇒ ⇒ ★★ DWC 的进化对象是 21 个（含代码/架构/元进化），
       不是一个 prompt
⇒ ⇒ ★★ 路线②的可移植部分是**搜索骨架**（Pareto 采样 + 自然语言反思 + merge），
       不是它的对象（prompt）
⇒ ⇒ ⇒ 必须显式区分: "用 GEPA 的骨架搜 DWC 的对象" ≠ "用 GEPA"
★ 这条是本裁决里最关键的约束, 防止移植时被"GEPA 很强"这句话带走

★ 另: GEPA 需要"reflective prompt mutation" —— 即 LLM 读轨迹写新 prompt
  ⇒ DWC 的对应物是 MODIFIER_CRITIC.md 已定的 m.propose
  ⇒ ★ 可移植 ✓（m 已经是"诊断→提案"的角色）
```

---

## 二、★★★ Merge 的三个条件（比"要不要 merge"更该抄的东西）

```text
Appendix D.1 原文逐字:
  "Algorithm 3 defines the selection criteria: candidates are merged **only if**
   ① they **share a common ancestor**
   but have optimized **disjoint sets of prompts (complementary strategies)**,
   ② are **pareto-optimal**, and
   ③ **both candidates improve upon the aggregate performance of the ancestor**.
   GEPA routinely checks if the pool has 2 such candidates, invoking merge when
   identified. **These strict lineage conditions mean merge occurs sparsely.**"

  §5 的归因: "We attribute these gains to the ability of GEPA+Merge to identify
   **distinct optimization lineages**, that have learnt **complementary strategies
   (by evolving distinct modules)**, and merging them by **picking the best version
   of different modules from each of these lineages**"

⇒ ★★★ ★★ 这**正是 GAP_AUDIT 缺口 A2 的答案**, 且是三条硬条件 + 一个频率事实:
  ★ 归档/合并**不是**"把旧东西丢掉", 而是"**同一祖先 + 互补模块 + 都优于祖先** 才合"
  ★★ 原文自己说 "merge occurs **sparsely**" ⇒ ⇒ 频率低是**设计预期**, 不是缺陷
  ★ ⇒ DWC 的三态保留「入 archive 待选」因此有了**可抄的筛选条件**
```

### 2.1 ★★ A2 的答案（想象节点存哪 / 剪枝策略）

```text
★★ 剪枝策略 = GEPA 的 Pareto 剪枝, 但**必须扩到能力组维度**:
  剪掉 = 在**所有**组上都严格被支配的候选
  ⇒ 保留 = 在**至少一个**组上并列最高的候选
  ⇒ ★ 与 COMPONENT_VOCABULARY §四③ 的 ℬ_t 扩展**方向一致**
    （那里我已把 ℬ_t 改为 𝒯_t ∩ 𝒦_editable）

★★ 想象节点存哪 —— ★★★ 原文给了直接证据（GEPA 的 candidate pool 就是它）:
  "GEPA proceeds to evaluate the new system candidate on the **full D_pareto set**,
   **adding it to the list of candidates tracked** and marking the new system's parent."
  ★★ ⇒ 候选**持久化在池里**, 且**记录父子关系**（"marking the parent"）
  ⇒ ⇒ ★ 我原倾向"不存, 只在内存" —— **这是错的**
  ⇒ ⇒ 修正: 想象节点必须持久化 + 必须记 lineage（否则 merge 的①"同一祖先"判不了）
```

---

## 三、★★★ 裁决：两条路线**都不是默认**（这是与 ARCHITECTURE 的不同点）

```text
★★★ ARCHITECTURE §9 第 25(y) 写"建议: 默认 Pareto(更稳)"
   ★★ 本轮核原文后修正 —— 两路线的选择条件如下（互斥判据）:

  选路线②（Pareto + 反思）当且仅当三条同时成立:
    ① 组内任务数 ≥ n_pareto_min（否则 Pareto 维度不足, 前沿退化为单点）
       ★ 参照 GEPA 的规模: HotpotQA 150 train / 300 val / 300 test
       ⇒ ★ DWC 当前 sealed 15 条 ⇒ ★★★ **不满足** ⇒ 默认只能是路线①
    ② 进化对象是"可被 LLM 用自然语言反思并重写"的东西（prompt/指令/规则）
       ⇒ 代码与架构**不满足** ⇒ ⇒ 混合对象下路线②只能用于其中一部分
    ③ 有 lineage 记录能力（merge 的条件①依赖它）

  否则选路线①（信息增益单树）
  ★ 且路线①必须有**卡住检测**（Figure 6a 的病）:
    连续 N 轮 refinement 无改进 ⇒ 触发路线② 或换支

⇒ ★★ 结论: DWC 当前的正确默认是**路线①**, 且必须补卡住检测
⇒ ★⇒ ★ 我上次的"默认 Pareto"建议被原文否掉, 两次判断相反, 已如实记录
```

---

## 四、可机械检查的判据（gate.py 候选，Z1–Z6）

```text
Z1 · 世界树的收束策略必须在 config 里显式声明（strategy ∈ {ig_tree, gepa_pareto}）
   ★ 无默认值 —— 与 G11/K4/X1/Q1 同款纪律
   ★★ 依据: 两路线不可互换（§三的三条条件）

Z2 · 若 strategy = gepa_pareto, 必须校验 n_pareto_min
   ★★ 依据: §三① —— DWC 当前 15 条不满足 ⇒ 默认只能是 ig_tree
   ★ 这条把"能不能用 GEPA"变成一个算术检查

Z3 · Pareto 前沿的维度必须显式声明（pareto_dim: task | task_group）
   ★ 依据: Algorithm 2 是**逐任务实例**（§1.1）—— 不是逐总分
   ★★ 若误用"逐总分"的 Pareto, Algorithm 2 的 line 4-5 退化为全局 argmax
     ⇒ ★ 那就等于"永远选最好的" ⇒ 正是 Figure 6a 描述的局部最优陷阱

Z4 · 候选必须持久化 + 必须记 lineage（parent_id）
   ★★★ 依据: §二 原文 "adding it to the list of candidates tracked and marking the
     new system's parent" ⇒ 修正我原写的"倾向不存, 只在内存"

Z5 · merge 触发必须同时满足三条条件（同一祖先 / 互补集合 / 都优于祖先）
   ★★ 且必须记录 merge 发生率 —— 依据原文 "merge occurs sparsely"
   ★ 若发生率异常高 ⇒ 说明三条件没被真正检查（check log）
   ★★★ 依据: Appendix D.1 逐字

Z6 · 必须有卡住检测（连续 N 轮无改进）
   ★★★ 依据: Figure 6a 原文"repeatedly attempts to refine it, fails to improve,
     and ultimately depletes the budget"
   ★ 这是路线①的已知病, 不设检测就是明知有病不设防
```

---

## 五、诚实边界

```text
① 本设计**未写代码**，`src/` 与 `config/` 均空。
② 未验证: Z1–Z6 全是设计推理。
③ ★★★ 我**推翻了**自己上一轮的建议（"默认 Pareto 更稳"），
   依据是 GEPA 附录 D.1 的原文（Merge 在 Qwen3-8B 上负收益，4 个任务只 1 个受益）。
   ⇒ ★ 这是本轮最重要的产出: 一次基于原文的自我纠正。
④ ★★ GEPA 的移植是**骨架移植**（Pareto 采样 + 自然语言反思 + merge），
   ★★ 不是移植它的对象（prompt optimizer）
   ⇒ ★★★ DWC 的进化对象含代码/架构/元进化 ⇒ 不是 prompt
   ⇒ ★ 这是本次裁决最关键的约束, 但我**无法验证**骨架移植后效果是否仍在
⑤ ★ n_pareto_min 的具体值未定（我引 GEPA 的 150/300/300 作参照, 非依据）
⑥ ★★ A2 的"想象节点存哪"我改了结论（原倾向"不存只在内存"），
   依据是 GEPA 原文的候选池 + parent 标记。
   ★★ 但 GEPA 的候选池是**内存里的 prompt 集合**, 与 DWC 的世界树（需落盘追溯）
   ★★ 规模不同 ⇒ 我的修正是否过度, 未验证。
⑦ ★ Pareto 前沿的"task instance"与 DWC 能力组的对应关系是**我的推断**:
   GEPA 说的是 "training instance", DWC 说的是"能力组"或"组内任务" ⇒ 二者未必同构
⑧ ★ 未核 GEPA 的 Appendix K.1（具体 prompt 演化轨迹）与 DWC 的关系
⑨ ★ §三 的"三条同时成立"判据是我构造的（论文没给"何时该用哪条路线"）
⑩ ★★ ARCHITECTURE §2 与 §9 第 25(y) 的不一致我**只在本文件裁决**,
   ★ §2 的"信息增益"段与 §9 第 25(y) 的"默认 Pareto"建议**尚未回填修改**
   ⇒ 需另行回填（本文件不擅自改 §2 的已定段）
```

---

## 六、★ 实测记录（rc=0 全通，并纠正我一处期望值错误）

```text
=== Algorithm 2 忠实实现（D_ 全局最差）===
  候选 A  [0.9,0.5,0.5] 总1.90 / B [0.7,0.8,0.4] 总1.90
  候选 C  [0.6,0.6,0.9] 总2.10 / D_ [0.3,0.3,0.3] 总0.90
  保留集 C={A,B,C}   被剪=无
  ★★★ D_ 既不在 C 也不在 pruned —— line 7 原文 "C ← unique candidates in ∪P*[i]"
     ⇒ 它不是"被剪掉的", 是**"从未成为候选"** —— 两者含义不同
     ⇒ ★ 这正是 GEPA 不会像 Figure 6a 卡住的原因:
       在任一实例上非最优的候选, 根本没机会被反复 refinement

=== 采样分布（∝ f[Φ] = 领先多少个实例）===
  A 32.3% / B 35.3% / C 32.5%   ← 近均匀
  ★ 我原本以为 C 应最高, **是我算错**: A/B/C 各自只在**一个**实例上领先,
    f 均为 1 ⇒ 分布近均匀是正确行为（分布与总分无关）
  加一个真正三维领先的 E [0.95,0.85,0.95]:
    E **100%** ⇒ f 加权生效 ✓

=== ★★ Z3 · 逐实例 vs 逐总分（判据 Z3 的必要性）===
  逐实例 Pareto 保留: {A, B, C}
  逐总分 Pareto 保留: {C}  ← 只有总分最高的
  ⇒ ★★★ 两者不同 ⇒ 若误用总分, Algorithm 2 退化为"永远选最好的"
  ⇒ ⇒ 那正是 Figure 6a 描述的局部最优陷阱 ⇒ Z3 是硬要求

=== Figure 6a 的病 + 卡住检测 ===
  轨迹 [(R1,0.50),(R2,0.50),(R3,0.49),(R4,0.50),(R5,0.48),(R6,0.50)]
  N_STUCK=3 ⇒ **R4 触发**（论文原文是 "ultimately depletes the budget" 浪费到底）
  ⇒ 有卡住检测 ⇒ 可在 R4 就切路线②, 不必耗尽预算

=== Z5 · merge 三条件（四场景全对）===
  同祖先+互补+都更优 → True / 模块重叠 → False / 不同祖先 → False / a 未优于祖先 → False

=== Z2 · n_pareto_min 算术检查 ===
  DWC sealed=15 < n_pareto_min=50 ⇒ **不满足** ⇒ 默认只能是 ig_tree
```

---

## 七、诚实边界（补）

```text
⑩ 实测覆盖: Algorithm 2 的忠实实现 / f 加权 / 逐实例 vs 逐总分
   / 卡住检测 / merge 三条件 / n_pareto_min 算术
   ★★ 未测: 自然语言反思环节（需 LLM，DWC 走云端 API 无法离线测）
⑪ ★★ 实测纠正了我一处期望值错误: 我以为"f 加权会让总分最高者概率最高",
   实测 f 只看**领先多少个实例**, 与总分无关 ⇒ 三维领先者才显著获益
   ⇒ ★★ 这也说明: 若把 pareto_dim 误设为"总分", Algorithm 2 就失去全部意义
   ⇒ ⇒ Z3 从"注意事项"升级为"决定性判据"
⑫ ★★ 测试脚本本轮写了 5 版才跑通（前 4 版是我的索引/缩进/引号错误,
   其中一次把测试脚本本身改坏）⇒ 记录在此, 说明实测成本
   ★ 但每次失败都暴露了真实问题（如 D_ 不在 C 的发现）
⑬ ★ 未测 E 候选加入后 A/B/C 被支配的情形（被剪逻辑未单独触发过）
```

---

*设计定稿 · 2026-10-04 · 推翻"默认 Pareto"（原文依据）+ 两条路线并列的互斥判据 + A2 的答案（剪枝/存哪）+ Z1–Z6 · 参照 GEPA 273,016 字符原文逐段核 · 未写代码*