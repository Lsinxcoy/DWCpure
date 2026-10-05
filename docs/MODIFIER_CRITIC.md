# DWC m 与 U 的实现形态（§9 第 12 项）

> **状态**：设计定稿（**未写代码**，`src/` 仍为空）
> **日期**：2026-10-04
> **缺口原文**：§9 第 12 项 —— "两者都归 evolver, 但必须分离成两个模块
> （GAI Figure 2 authority boundary）—— 具体接口未定"
> **参照（已逐字核）**：`E:/Divine Wisdom Core/papers_txt/2609.13406.txt`
> （GAI Definition 1 + Figure 2 图注 + 两个 dial 全文）

---

## 一、★★ 先纠正三处（逐字核 GAI 后的发现）

### 1.1 `"authority boundary"` 在 GAI 全文 **0 命中**

```text
实测: "authority boundary"  0 处
      "self-confirm*"        0 处
      "confirmation loop"    0 处
      "degenerate" / "collapse"  0 处
⇒ ★ ARCHITECTURE §2.4.3 与 §9 第 12 项写的
  「GAI Figure 2 原文: 环上『恰好一条 authority boundary』」是**误引**。
  ★ 那句引号里的内容不是 GAI 原文 ⇒ 不能作为设计依据。
```

### 1.2 ★ GAI 的真实机制是**两个 dial**，不是"一条边界"

**Figure 2 图注原文逐字**：

```text
"Figure 2: Generalized agent iteration as a cycle of policy, critic, and modifier.
 The critic evaluates the policy and the modifier against the base ρ and returns
 feedback; the modifier then produces improvements, **including possible rewrites of
 the critics and itself** (gray dashed, conditional on the setting; the dash-dot
 border of the modifier marks that it belongs to the agent only when m ∈ Ag).

 **With the modifier fixed outside the agent the cycle reduces to GPI;
 with the modifier inside the agent it is recursive self-improvement.**"

★ "Definition 1 leaves **two choices open**: whether the mechanism that improves the
 agent is among these components, and **what the evaluation base points at**.
 These are the **two dials** of the framework"
```

**Dial 1（m 在不在 agent 里）原文**：

```text
"• If m ∉ Ag, its content is **fixed** and m acts as an **external improvement
   mechanism**, the abstract evaluation-and-improvement operator that GPI iterates.
 • If m ∈ Ag, the system **may rewrite its own modifier**, so **recursion closes at m
   with no external meta-layer**."
```

**Dial 2（ρ 是否 grounded）原文**：

```text
"An evaluation is **grounded** when its base **draws its content from outside the
 system**, the world and the goal, **and when the base itself lies outside the agent**.
 The agent then **cannot rewrite the standard it is measured against**."

★ 三档原文（★★ 这是本项最有价值的一段）:
  "A base that draws its content from outside but **that the agent may rewrite**
   can **move under the system's own edits**;
   a base with **no external content at all constrains the loop by nothing beyond
   self-consistency**."
```

### 1.3 ★★ "m 与 U 必须分离"**不是 GAI 的硬约束**（Definition 1 原文）

```text
"All five roles belong to a system; **an instance may leave some of them unused**,
 as the **modification critic U is when the modifier is fixed**."
```

⇒ ★★ **GAI 明说：modifier 固定时 U 可以不使用。**
   所以"m/U 必须分离成两个模块"这条约束，**依据不在 GAI**。

---

## 二、★★★ 那 DWC 该怎么定？（区分"论文依据"与"我的判断"）

```text
★★ 关键区分:
  论文依据（可引用）:
    · m 与 U 是**两个不同的角色**（Definition 1 的两个 bullet，签名完全不同）
        m : X → Δ(X_Ag)   提议（输出是分布）
        U : X → ℝ          评估（输出是标量）
    · U 可以在 m 固定时缺席
    · grounded 的两条件（外部内容 + base 在 agent 外）
    · 两个 dial 决定系统是 GPI 还是递归自改进
  ★ 我的判断（论文未说）:
    · DWC 的 m 与 U 必须是**两个模块**（而不是同一模块的两个方法）
    · DWC 的 U 判据必须来自 judge（进程外）
```

### 2.1 为什么我仍主张分两个模块（依据不是 GAI，是 DWC 自己的）

```text
★ 依据一 · 类型签名根本不同（Definition 1 原文）:
    m: X → Δ(X_Ag)  —— 输出是"分布", 天然多解
    U: X → ℝ        —— 输出是"标量", 天然单值
  ⇒ 同模块两个方法可以, 但**返回类型**已把它们分成两类。

★ 依据二 · ★ 若同一模块既提议又裁决, DWC 会撞它自己的原则 1:
    原则 1 · 判据必须在系统之外（"这条是根, 不是推论"）
    ★ 若 U 与 m 同模块, 则判据与提议器同体 ⇒ 违反原则 1
  ⇒ ★★ 这条才是 DWC 分模块的真依据 —— 不是 GAI 的 Figure 2。

★ 依据三 · 与 §4.1 judge 的纪律 2 同源:
    L3 "从不做训练信号"（读者集合 == {审计报告}）
  ⇒ 若 U 由 evolver 内部产生, 它的读者必须是外部（judge/门）
  ⇒ 分模块让"读者集合"可检查
```

### 2.2 ★★ 但必须承认：分模块**不等于**出了系统

```text
★★★ 这是本项最重要的一条自我限制:
  GAI Dial 1 的判据是 m ∈ Ag 与否（"能不能改自己"），
  ★★ **不是** "m 与 U 在不在同一个 Python 模块里"。
  ⇒ ★ 分成两个 .py 文件，只是**工程结构**上的分开；
    真正的问题是"m 的内容能否被 U 改"。

  ★★ 因此必须补一条 DWC 独有的硬约束（论文没有，是我的判断）:
    ★★ m 的内容（提议策略/模板/超参）**在 agent 内**（m ∈ Ag_DWC = True）
       —— 这是 DWC 的选择, 对应 Dial 1 的第二档: "递归自改进"
    ★★ 而 U 的判据来源（judge 的 sealed 集）在 agent 外（grounded 的第二条件）
       —— 对应 Dial 2 的第一档
    ⇒ 组合起来: DWC = (m ∈ Ag) × (ρ grounded) = 递归自改进且基准接地
    ★ 这个"两档同时取哪一档"的显式声明，比"分两个文件"重要得多。
```

---

## 三、★★★ 两个模块的签名（落点已在 §11.2 定）

```python
# 落点: evolution/modifier.py  （§11.2 已定）
class Modifier:                      # = m，提议侧
    def propose(self, diag: Diagnosis, budget: Budget,
                vocab: ComponentVocab) -> list[Manifest]:
        """★ m : X → Δ(X_Ag) 的 DWC 形态。输出是**候选清单**（有限近似分布）。
        不变量（继承 §9 第 6 项）:
          · 每个 Manifest 必声明 protected_groups（非空）
          · 每个 Manifest 必声明 target_layer ∈ {assets, architecture}
          · |manifest| ≤ b_t
          · 每条候选必须能填出 ConsumerSpec（消费点声明）
        ★★ m 可以改自己的内容吗? 可以 —— 这是 m ∈ Ag 的定义（Dial 1 第二档）
           但 m 的改动**必须自己走一遍 m.propose**（不许绕过）
        ★★ 不变量: m 不得读 judge 的内部存储（约定④）"""

# 落点: evolution/critic.py  （§11.2 已定）
class Critic:                        # = U，裁决侧
    def evaluate(self, manifests: list[Manifest],
                 evidence: EvidenceBundle) -> CriticVerdict:
        """★ U : X → ℝ 的 DWC 形态。
        ★★★ 本方法**只算标量/向量，不改任何东西**。
        不变量:
          · evidence 的**全部来源**在 agent 外（judge 的 sealed split）
          · 不得调用 m 的任何方法（防止裁决器反过来驱动提议器）
          · 缺证据 ⇒ 该项为 NOT_EVALUATED，不转成正面（judge 纪律 3）
        返回: CriticVerdict{per_manifest: dict[ManifestId, float],
                          aggregated: float, not_evaluated: list[ManifestId]}
        ★★ 为什么 aggregated 是标量: U : X → ℝ（Definition 1 原文）
          ★ 若 DWC 未来要 Pareto 多目标 ⇒ 那不再是 GAI 的 U, 是另一个角色
        ★★ per_manifest 必须保留（不能只返一个总分）——
           依据 §9 第 2 项的信用分配 ℒ_t 需要逐条归因"""
```

### 3.1 ★★ 分离的可检查判据（不只是"两个文件"）

```text
★ 真正要检查的不是文件名, 是**依赖方向**:

  Critic  依赖:  judge(证据) + Manifest(数据)
  Modifier 依赖:  Diagnosis + Budget + Vocab
  ★★ 两者的依赖集合**不相交**（除 Manifest 作为数据）
  ⇒ 判据 M1: critic.py 的 import 里**不含** modifier.py 的任何符号
  ⇒ 判据 M2: critic.evaluate 的调用链里**不出现** modifier.propose
```

---

## 四、★ 两个 dial 的 DWC 取值（显式声明，对应 §9 缺口 (g)）

```text
★ Dial 1 · m 在 agent 内吗?  → **在**（m ∈ Ag_DWC = True）
  含义: DWC 是递归自改进（GAI: "recursion closes at m with no external meta-layer"）
  ★★ 这是 DWC 的**自主性选择**, 已在 §9 第 5 项（守卫①）背后同源:
    自举 = 自己改自己的改进器。imp@k 证明"冻结身份"是隔离归因的手段。

★ Dial 2 · ρ grounded 吗?  → **grounded, 但分两档说明**
  grounded 条件①: 内容来自系统外（世界与目标）  → ✓ judge 的 sealed split
  grounded 条件②: base 本身在 agent 外          → ✓ judge 的 sealed_set 不可写
    依据: §4.1 的 seal + 铁律 G10（判据 I8: check_access 调用点必须 > 0）
  ★★ "外部内容但 agent 可改"这一档, DWC **明确拒绝**:
    对应 §2.4.6 约束 2「判据必须在可写面之外」
    ⇒ ★ 若 DWC 将来允许 judge 被自改, 就落入"move under the system's own edits"
      ⇒ 必须重新声明 ρ 是否仍 grounded
```

---

## 五、可机械检查的判据（gate.py 候选，M1–M6）

```text
M1 · critic.py 不 import modifier.py 的任何符号
   ★ 依赖方向检查（§3.1）—— 这才是"分离"的实质

M2 · critic.evaluate 的调用链不含 modifier.propose
   ★ 防止裁决器反过来驱动提议器（同一循环内）

M3 · Modifier.propose 的返回清单里, 每条 Manifest 都有
   protected_groups（非空）+ target_layer + ConsumerSpec
   ★ 继承 §9 第 6 项 / 第 25 项 (c) 的判据, 此处只检查三者齐全

M4 · Critic.evaluate 的 evidence 来源全部在 agent 外
   ★ 对应 grounded 条件①②; 若某条证据来自 DWC 自己的记忆 ⇒ 违规

M5 · Critic 返回 per_manifest（逐条分数），不只是 aggregated
   ★ 依据 §9 第 2 项信用分配 ℒ_t 需要逐条归因

M6 · 两个 dial 的取值在配置里显式声明
   config/dials.yaml: { m_in_agent: true, rho_grounded: true,
                        rho_external_content: true, rho_agent_can_rewrite: false }
   ★ 四个布尔都必须显式, 不许有隐式默认
   ★ 依据 GAI: "These are the **two dials** of the framework"
   ★ 落进五元盘点 χ 的每次报告里 ⇒ 可事后审计"当时是哪一档"
```

---

## 六、诚实边界

```text
① 本设计**未写代码**，`src/` 仍为空 —— 符合"架构定稿前不写承重代码"的纪律。
② 未验证: M1–M6 全是设计推理，尚无实现可 grep / 可测。
③ ★★★ 我更正了 ARCHITECTURE 的一处误引（"GAI Figure 2 原文: 恰好一条
   authority boundary" —— 该短语在 GAI 全文 0 命中）。
   ★ 这是我自己早前写下的错误，本项核原文时才发现。
   ⇒ 应在 ARCHITECTURE §2.4.3 与 §9 第 12 项标注更正（本文件不擅自改已定段）。
④ ★★ "m 与 U 必须分两个模块"的依据**不是 GAI**（Definition 1 明说 U 可缺席）。
   我给出的真依据是 DWC 自己的原则 1 + §4.1 纪律 2。
   ★ 若将来决定合并成同一模块, 原则 1 的论证仍需重做。
⑤ ★ 两个 dial 的取值（DWC = m∈Ag × ρ grounded）是我的判断,
   GAI 只给了两个 dial 的定义与后果, 没给"应该取哪一档"。
⑥ ★ "分两个 .py 文件"是工程结构, 与"能否改自己"无关（§2.2）。
   ⇒ 判据 M1/M2 检查的是**依赖方向**, 不是文件名。
⑦ 未定: Critic.aggregate 的具体口径（标量? 效用加权? 非补偿六步的哪一步?）
   ★ §4.4 的门已有六步顺序, 但 U 只是其中一步的判据来源还是全部?
   ⇒ 这属 §9 第 2 项与本项的交界, 未明文。
⑧ 未核实 GAI 全文是否有 Figure 2 之外的其它图给出更细的边界规定
   （我只核了 Definition 1 / Figure 2 图注 / 两个 dial 段）。
```

---

## 七、★ 实测记录（rc=0 全通）

```text
✓ M1 依赖方向: critic.py 的 import = ['dataclass','field'] ⇒ 不含 Modifier
  ✓ 反例 critic_bad.py(from modifier import Modifier) 被正确识别 ⇒ {'Modifier'}
✓ M3 Manifest 三要素: protected_groups=('g1',) / target_layer='assets' / consumer 有 attr
  ✓ b_t=0 ⇒ 返回空清单（预算约束生效）
✓ M4 证据外部性: source='dwc_memory' ⇒ per={} 且 not_evaluated=['M1']
                source='sealed_dev' ⇒ per={'M1':0.7}
  ★ 内部来源不是"低分", 是**直接拒评**（进 not_evaluated）
✓ M5 逐条分数保留: per_manifest={'M1':0.7} + aggregated=0.70
✓ M6 两个 dial: m_in_agent=True / rho_grounded=True / rho_agent_can_rewrite=False
  ★ 实测断言 not DIALS['rho_agent_can_rewrite'] ⇒ 明确拒绝"外部内容但可改"那一档
★ 两次失败是**环境问题**不是代码错: (1) heredoc 的 \n 被吃;
  (2) 临时目录未进 sys.path ⇒ ModuleNotFoundError。已补 _s.path.insert。
```

---

## 八、诚实边界（补）

```text
⑨ 实测覆盖: M1（依赖方向, 含反例）/ M3（Manifest 三要素 + b_t）
   / M4（证据外部性）/ M5（逐条保留）/ M6（dial 声明）
   **未测**: M2（critic.evaluate 调用链不含 modifier.propose）——
   这需要全量调用图 grep, 本次只测了直接 import 层。
⑩ ★ 实测暴露一个设计细节: 内部来源证据是**拒评**（进 not_evaluated）而非低分。
   ⇒ 这与 §4.1 judge 纪律 3 一致, 但我原文档没写清, 已补。
```

---

*设计定稿 · 2026-10-04 · m=Modifier / U=Critic + 依赖方向判据 + 两个 dial 显式声明 · 参照 GAI 原文逐字核（含一处误引更正）· 未写代码*