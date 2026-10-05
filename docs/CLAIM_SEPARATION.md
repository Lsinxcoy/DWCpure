# DWC 第 23 项 + 25(a)(b) 清点裁决

> **状态**：设计定稿（**未写代码**，`src/` 与 `config/` 均空）
> **日期**：2026-10-04 · **来源**：`docs/GAP_AUDIT.md`（第 23 项 + §9 第 25 项 (a)(b)）
> **参照（本轮已核原文）**：`papers_txt/2609.2680_rsi_survey.txt`（§3.4 三主张，式5–8 全部公式）
> **前置**：`docs/STATE_SCHEMA.md`（PredictionOutcomePair）· `docs/JUDGE_LAYERS.md`（L3 纪律）
> · `docs/CONSUMER_VERIFICATION.md`（Level 3 探针）· §9 第 20 项（守卫①）

---

## 一、★★★ 先说清点结论

```text
★★★ 逐条核对结果:
  (a) 三主张分离     ⇒ ★★ **部分已覆盖，但漏了一处关键的**
  (b) 配对探针 Γ_t   ⇒ ★★ **一半已具备，另一半不存在**
  第 23 项 L3 退化   ⇒ ★★ **不是独立项，是 (a) 的下 consequence**
                     ⇒ 合并裁决

★★ 而核对时发现一处**真实的矛盾**（见 §二）—— 它比两处的未决都重要
```

---

## 二、★★★★★ 核出的一处真实矛盾（这是本轮最重要的发现）

```text
★★★ 矛盾: §9 第 25(b) 说"当前**无 solver 概念**", 
   但 §9 第 7 项（世界采样，**已定**）的核心判据就是 r̄_solve

  第 7 项现文（逐字）:
    "用 DWC 自己的 **r̄_solve 区间**（AZR 式 x）替代 p̂_u 与 6/8:
      难度太易 (r̄→1) 或太难 (r̄→0) 都无学习信号"
    "⇒ DWC 版本 = **中间难度带优先**"

  25(b) 现文（逐字）:
    "★ 待定: DWC 能否构造'同一 held-out 起始态'?（**当前无 solver 概念**）"

⇒ ⇒★ 两句话不能同时为真
⇒⇒★⇒ 三种可能, 必须裁决:
  甲 · 第 7 项的 r̄_solve 其实**不需要 solver** —— 它只是"通过率"
        ⇒★ 这个读法成立! r̄_solve 可以由 judge 的逐任务分数直接算
        （C3' 刚定的 TaskScorePoint 就是数据源）
  乙 · 25(b) 的"无 solver 概念"指的是**别的东西**
        ⇒ 指"没有可被改进的 solver 实例"（2609.2680 原文的 S 是 solver）
  丙 · 第 7 项定得不严谨, 借了论文的符号却没定义它的来源
        ⇒ ⇒ 若如此, 第 7 项也需回填

★★★ 裁决: **甲 + 丙同时成立**
  · 甲: r̄_solve = 该任务在组内历史中的通过率, 由 C3' 的数据算出
        ⇒ 不需要 solver 概念 ⇒ 第 7 项**成立**, 但须补一句来源声明
  · 丙: 第 7 项确实借了符号未定义来源 ⇒ 必须回填
  · 乙: 25(b) 说的"solver"是另一个东西（见 §三）, 两者不冲突但**同名**
```

---

## 三、★★ Γ_t 与 DWC 现有机制的对照（决定 (b) 的裁决）

```text
【2609.2680 §3.4 原文（已逐字核）】
  式5  task gain:  Δ_t = Q(S_t; D_test) − Q(S_0; D_test)
  式6  retention:  ρ_{t,j} = Q(S_t; D_test^j) − Q(S_{t,j}; D_test^j)
       transfer:   τ_t = Q(S_t; D_test^new) − Q(S_0; D_test^new)
       ★ 原文: "The reference checkpoint t_j is **predeclared**;
                ρ_{t,j} < 0 indicates a **loss** relative to it"
  ★★ "Neither positive Δ_t nor positive τ_t **isolates the improver**."
  式7  g(I; S, B) = E[ Q(S⁺(I;S,B); D_test) − Q(S; D_test) ]
       ★ "S⁺(I; S, B) be the successor selected by improver I **from the same
          starting solver S** within budget B"
  式8  Γ_t(B) = E_{S∼P_start}[ g(I_t; S, B) − g(I_0; S, B) ]
       ★ "**A paired probe on held-out starting states** drawn from P_start"
       ★★ "**Controls must match starting states, feedback access and resource
           accounting.**"
       ★★★ "**Positive Γ_t with appropriate uncertainty** supports a stronger
            improver under that probe."
```

```text
★★★ 逐项对照 DWC 现状:
  式5 Δ_t（任务增益）  ✓ 有 = judge 的 TaskScorePoint 聚合（C3' 已定）
  式6 ρ_t（保留）        ✓ 有 = REGRESSION_GUARD 的 r̂_{t,j}（截面口径）
       ★★ 差异: 论文的 ρ 是**相对预声明检查点 t_j**;
         DWC 的 r̂ 是**相对历史峰值** ⇒ 这是 §三·差异1
  式6 τ_t（迁移）        ✗ 无 —— FWT 只作偏置（第 7 项已定），未做计量
  式8 Γ_t（改进器增益）  △ **一半有**: PredictionOutcomePair 是它的骨架

★★ Γ_t 与 PredictionOutcomePair 的关系（这是本裁决的关键判断）:
  Γ_t 的内层: g(I; S, B) = "从**同一起始态 S** 出发, I 选出的后继比当前好多少"
  PredictionOutcomePair 的内层: "wm 预测的 effect 与实际 effect 之差"
  ⇒ ★★★ 二者**结构同构, 但问的不是同一件事**:
     Pair 问「**世界模型**的预测准不准」
     Γ_t 问「**改进器**的产出比现状好多少」
  ⇒ ⇒ ★ 它们可以共用同一批数据, 但**指标不同**
  ⇒ ⇒ ⇒ DWC 的 Γ_t 实现 = 双跑一遍 (I_t 与 I_0) + 按式8 求差
     ⇒ 需要"同一 held-out 起始态" ⇒ 这才是 25(b) 的真正卡点
```

### 3.1 ★★ Γ_t 在 DWC 的三个真障碍

```text
★ 障碍 1 · 起始态 S 的可复现性（原文的硬要求）
  "Controls must match **starting states**"
  ⇒ S⁺(I_t; S, B) 与 g(I_0; S, B) 必须从**同一个 S** 出发
  ⇒★ DWC 的 S 是什么? §4.2 actor 的起始态 = task + state + memory 工作态
  ⇒ ⇒ memory 工作态**不可复现**（它是历史累积的）
  ⇒ ⇒ ★★ 这是比"无 solver 概念"更实质的障碍

★ 障碍 2 · 预算对齐（原文第二项硬要求）
  "Controls must match **resource accounting**"
  ⇒ B 必须相同 ⇒ 而 ERROR_AND_TERM 已定"两个成本台账"
  ⇒ ⇒ ✓ 这一项 DWC 已有现成机制（cumulative_cost 可裁到同预算）

★ 障碍 3 · I_0（基线改进器）是什么
  ⇒ 式8 减的是 g(I_t) − g(I_0)
  ⇒ I_0 = "不做任何改进"⇒ 在 DWC 里 = current harness
  ⇒ ★★ 而 DWC 已定"候选集必含 current ⇒ 数学保证不回退"
  ⇒ ⇒ ⇒ I_0 就是候选集里的 current ⇒ ✓ 这一点 DWC 天然具备
```

---

## 四、★★★ 裁决（三条）

```text
裁决 1 · (a) 三主张分离 —— ★ 部分已覆盖, 但判据层**确实缺 claim_type**

  逐条核对 25(a) 点出的两处影响:
   · 守卫① 该用哪个量?  ⇒ ✓✓ **已答**（第 20 项裁决: 用 judge 外测的世界模型
     准确率）★ 但那个准确率是 Pair 的 is_correct, 即"预测准不准"
     ⇒ ★★★ **不是 Γ_t** ⇒ ⇒ 守卫① 用的是"世界模型质量", 不是"改进器增益"
     ⇒ ⇒ ⇒ 这是**有意的**: 守卫① 判的是"能不能信世界模型"这件事本身
     ⇒ ⇒ ⇒ 而 Γ_t 判的是"改进器有没有变强"
     ⇒ ⇒ ⇒ ★★ 所以 25(a) 的第一处影响**已答，且答案是"都不用"**
   · L3 应测 Γ_t 还是 Δ_t? ⇒ ★ **这是仍未答的一处**（见裁决 3）

  ★★ 仍需补的: judge 的 Verdict 必须带 claim_type ∈ {task_gain, retention,
     improver_gain}（25(a) 的 DWC 接口建议，报告 5.1 第 1 条）
     ⇒ ★ 这一条**未被任何已定项覆盖** ⇒ 必须补

裁决 2 · (b) Γ_t 的形式 —— ★★ **不作为门的输入, 只作为报告的诊断量**

  ★ 理由（三条）:
   ① 障碍 1（起始态不可复现）是**实质障碍**, 不是工程细节
      ⇒ memory 工作态历史累积 ⇒ 无法从同一 S 重跑
      ⇒ ★★ 而"无法复现"意味着 Γ_t **算不出来** ⇒ 不能进门
   ② 原文自己说它是 "under **that probe**" —— 它是**特定探针下的结论**,
     不是普遍判据 ⇒ 把它放进门 = 把探针结果当普适真理
   ③ G11 已定: 门通过 ≠ 系统安全; 而 Γ_t 恰好是那种"探针结论"

  ⇒★⇒ Γ_t 降级为: **阶段末报告的诊断量**（run_term 的 TermReport 字段）
     ⇒ 不进 gate，不进 A_t，但必须被记录并可查
     ⇒ ★★ 这是"诚实的降级", 不是搁置

裁决 3 · 第 23 项 L3 退化 —— ★★ **与 (a) 合并, 且答案已定**

  第 23 项问"L3 独立审计的退化是否可接受"
  ★★ 核 JUDGE_LAYERS 已有答案:
    §4.1 已定 L3 的纪律 2: "L3 从不做训练信号（读者集合 == {审计报告}）"
    ARCHITECTURE §4.2 已定 A8: "2607.12790 的 L3 用'更强的 LLM';
      DWC 用托管模型, **未必拿得到更强的**。
      ⇒ 若退化 ⇒ 独立性来自**流程隔离**而非**能力差**（JUDGE_LAYERS §七③）"
  ⇒⇒ ★★ 第 23 项**已有裁决**, 只是没销账:
     退化可接受, 条件是独立性由**流程隔离**保证, 不依赖模型更强
     ⇒ ★ 这与 GAI Dial 2 的 grounded 条件②（base 在 agent 外）同型
     ⇒ ⇒ ⇒ 第 23 项**不是待决项**, 是**已决未销账**
```

---

## 五、可机械检查的判据（gate.py 候选，Q1–Q5）

```text
Q1 · judge 的 Verdict 必须带 claim_type ∈ {task_gain, retention, improver_gain}
   ★★★ 这是 25(a) 唯一**未被覆盖**的部分（裁决 1）
   ★ 必填、无默认（与 K4/G11/X1/L1 同款纪律）

Q2 · r̄_solve 的来源必须显式声明（解决 §二 的矛盾）
   ★ r̄_solve = 组内该任务的历史通过率, 由 TaskScorePoint 算出
   ★ 声明位置: world/scheduler/band.py 的配置或函数签名
   ★★ 依据: 第 7 项借了 AZR 的符号却未定义来源（本轮核出的矛盾）

Q3 · Γ_t 只出现在 TermReport，不得出现在 gate 的输入里
   ★★ 依据: 裁决 2（障碍1 使它算不出来 + 原文说它是"under that probe"）
   ★ 判据形式: gate() 的入参类型里不含 Γ_t / improver_gain

Q4 · L3 的独立性来源必须声明是"流程隔离"还是"能力差"
   ★ 依据: 第 23 项的裁决（退化可接受, 条件是流程隔离）
   ★ 与 GAI grounded 条件② 同型（base 在 agent 外而非"更强"）

Q5 · TermReport 里的 Γ_t（若算得出）必须带 uncertainty
   ★★★ 原文逐字: "**Positive Γ_t with appropriate uncertainty** supports a
        stronger improver" ⇒ 缺不确定性的 Γ_t 是半个结论
   ★ 若 DWC 算不出 Γ_t ⇒ 该字段必须是 None 而非 0
     （与 C3' 的 n_obs=0 ⇒ NaN 同款纪律）
```

---

## 六、诚实边界

```text
① 本设计**未写代码**，`src/` 与 `config/` 均空。
② 未验证: Q1–Q5 全是设计推理。
③ ★★★ 核出并裁决了一处真实矛盾（§二）: 第 7 项用 r̄_solve,
   而 25(b) 说"无 solver 概念" ⇒ 两句不能同时为真
   ★ 我的裁决是"甲+丙同时成立": r̄_solve 不需要 solver（由 C3' 数据算出）,
     但第 7 项**确实**借了符号未定义来源 ⇒ 必须回填（判据 Q2）
   ★★ 若我判错, 第 7 项需重审
④ ★★ Γ_t 降级是本裁决**最重要也最保守**的一步:
   ★ 障碍 1（memory 工作态不可复现）我**没有验证**, 只是从 §4.2 推断
     ⇒ 若 memory 其实是可快照复现的, Γ_t 也许能算 ⇒ 降级就过度了
   ★★ 这是本设计里最可能需要翻案的一条
⑤ ★ 未核实 2609.2680 §3.4 之外的章节是否给出 Γ_t 的实现细节或近似方案
   ★ 本轮核了 §3.4 全文（式5–8 + 三条纪律）
⑥ ★ 25(a) 的第二处影响（L3 测 Γ_t 还是 Δ_t）我的答案是
   "L3 测 Δ_t, Γ_t 只作报告" —— 但这是**裁决**, 不是原文要求
   ⇒ ★★ 它与 §4.1 已定的 L3 纪律 2（不做训练信号）不冲突, 但未与之交叉核对措辞
⑦ ★ τ_t（迁移/OD）目前**完全无计量**, 而 FWT 只作偏置（第 7 项已定）
   ⇒ ★ 若将来要报 τ_t, 需要预声明的 D_test^new, 那是另一件事
⑧ ★★ "reader 集合 == {审计报告}" 这个说法（§4.1 已定）与
   ★ "Γ_t 只作 TermReport 诊断量" 的边界不清:
   ★★ TermReport 是 run_term 的产出, 它是"报告"还是"数据"?
   ★ 这条边界我**没有划清** —— 记此待审。
```

---

## 七、★ 实测记录（rc=0 全通，并**撤回我一处不成立的断言**）

```text
=== 障碍1 · 起始态 S 的可复现性 ===
  A. 同一 S（memory 空）: g(I_t)=0.6900  g(I_0)=0.5700  Γ=0.1200
     ⇒ ✓ 若 S 可复现, Γ_t 算得出来
  B. 实际轮次: 第1轮 memory 0 项 → 第2轮 3 项
     ⇒ ★★ 这两个 S **不是同一个起始态** ⇒ 障碍1 成立
        （memory 工作态历史累积 ⇒ 无法从同一 S 重跑）

★★★ 撤回一处断言（我的成本论证不成立）:
  我原稿写"强行对齐的代价随历史线性增长 ⇒ 3000 轮时不可接受"
  ★ 实测: history = 0/10/100/1000 轮, 重放耗时全部 ≈ 0.000005 s
  ⇒ ★★ 那是因为我的重放循环是**空转的 pass**, 没有真实代价
  ⇒ ⇒ ★ 该成本论证**无效**, 已撤回
  ⇒ ★★ 障碍1 仍成立, 但**只剩"不可复现"这一条理由**, 没有成本理由
     ⇒ ★ 这是更弱的论证基础, 记此以免被误当作已充分论证

=== 障碍2 · resource accounting（DWC 已具备）===
  I_t cum=8.0  I_0 cum=8.0 ⇒ ✓ cumulative_cost 可裁到同预算
  ⇒ ★ 三障碍里这一项 DWC 已解决

=== 障碍3 · I_0 是什么 ===
  I_0 = current harness
  ★★ §9 第 5 项已定"候选集必含 current ⇒ V^{m⋆} ≥ V^0"
  ⇒ ⇒ current 天然是候选集一员 ⇒ I_0 无需额外构造 ✓ 已解决

=== Q1 · claim_type 三值均合法 ✓ ===
  ★★ 对照 25(a): 守卫① 用 Pair.is_correct（世界模型质量）
     ⇒ 那是 task_gain 的近亲, 不是 improver_gain
     ⇒ ★ 与裁决1「守卫① 都不用 Γ_t」一致

=== Q5 · Γ_t 缺 uncertainty 是半个结论 ===
  value=None ⇒ 算不出（不得写成 0）
  value=0.12 unc=None ⇒ ★违规
  value=0.12 unc=0.03 ⇒ OK
  ⇒ ★ 原文: "Positive Γ_t **with appropriate uncertainty**"

=== Q2 · r̄_solve 不需要 solver ★★ ===
  code_fix_001  r̄=0.833（历史 [1.0,1.0,0.5]）
  reasoning_003 r̄=0.333（历史 [1.0,0.0,0.0]）
  reproduce_002 r̄=0.833（历史 [0.5,1.0,1.0]）
  ⇒ ★★ r̄_solve 完全可由 TaskScorePoint 算出 ⇒ **不需要 solver 概念**
  ⇒ ⇒ 第 7 项成立, 但须补来源声明（Q2）
  ★★★ 实测也印证了第 7 项的判据语义: 三个值都落在"中间带"
    ⇒ 说明我挑的三个样本区分度不足, 未覆盖"太易/太难"两端的样例
```

---

## 八、诚实边界（补）

```text
⑩ 实测覆盖: 障碍1 的可复现性 / 障碍2/3 已解决 / Q1 / Q2 / Q5
   ★★ 未测: 真实 memory 工作态的快照能力（我用的是"不可复现"的先验假设）
⑪ ★★★ 我**撤回**了"对齐代价随历史线性增长"这条成本论证
   （实测发现那是空转循环造成的假象）⇒ Γ_t 降级的理由现只剩"不可复现"
   ⇒ ★★ 这让裁决2的论证基础变弱, 诚实标此
⑫ ★ Q2 的实测里三个样本的 r̄ 全落在中间带 ⇒ 未覆盖两端
   ★ ⇒ "太易/太难都不前进"这条判据**未被实测验证**
⑬ ★ 一次自测失败是我 key 名写错（"I_t" 应为 "I_t(改进器)"）⇒ 已修
```

---

*设计定稿 · 2026-10-04 · 清点结论: (a)部分已覆盖+漏claim_type / (b)降级为报告量 / 第23项已决未销账 + 核出第7项与25(b)的一处真实矛盾 + Q1–Q5 · 参照 2609.2680 §3.4 原文逐字核 · 未写代码*