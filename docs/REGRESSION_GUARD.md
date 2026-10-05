# DWC 保护组回归约束（§9 第 25 项 (c)）

> **状态**：设计定稿（**未写代码**，`src/` 仍为空）
> **日期**：2026-10-04
> **缺口原文**：§9 第 25 项 (c) —— "保护组回归约束 `r̂_{t,j} ≤ ϵ_j` —— ★ DWC 当前**完全没有**这一项"
> **本文件解决**：把这条从"建议"变成可实现的形式，并给判据。
> **参照（已逐字核）**：
> `E:/Divine Wisdom Core/papers_txt/2603.06333.txt`（SAHOO，Eq.18–23 + D.4 停止规则，正文 @49100+）
> `E:/Divine Wisdom Core/papers_txt/refs/2501.07278.txt`（FGT/BWT/FWT，式16–18）

---

## 一、缺口本体（2609.2680 §7.2 式9）

```text
A_t = 1{ Δ̂_val ≥ η_t ,  r̂_{t,j} ≤ ϵ_j ∀j ,  C_{≤t+1} ≤ B }

★ DWC 已有: Δ̂_val ≈ 非补偿四判据 / C ≤ B ≈ 退火预算 b_t
★ DWC 缺 : r̂_{t,j} ≤ ϵ_j —— 保护组回归约束
⇒ 建议（原文）: 每个候选必须声明它保护哪些能力组, 且各组回归 ≤ ϵ_j
```

★ **必须先说清它防的是什么**（SAHOO 原文，D.1 第一句）：

```text
"A critical concern in recursive self-improvement is **regression**: the phenomenon
 where quality improvements in later cycles are **undone by reversion to earlier
 behaviour**."
```

⇒ ★★ 这是**进化特有的**失效：不是"没变好"，是**变好了又退回去**。
  单轮的 Δ̂_val 完全看不出它 —— 这一轮的门会放行。

---

## 二、★★ 两种可抄的判据（各有取舍，我选后者为主）

### 2.1 FGT（2501.07278 式16）—— 截面型

```text
FGT_t = (1/(t−1)) Σ_{i=1..t−1} [ max_{j∈{i..t}} {J_{j,i}}_j − J_{t,i} ]

★ 原文: "FGT evaluates the **average accuracy drop of each old task**, representing that
         whether **useful experience are maintained successfully**"
★ 配套: BWT_t = (1/(t−1)) Σ (J_{t,i} − J_{i,i})   —— 旧任务是否受益（可为正）
★ FWT_t = (1/(t−1)) Σ_{i=2..t} (J_{i,i} − J̃_i)    —— J̃ = 无经验基线
```

**★★★ 这里有一个陷阱，已用代码证实**（2026-10-04 实测）：

```text
式(16) 的 max 取的是**历史峰值** max_{j≥i} {J_{j,i}}
⇒ 若某任务退化后又恢复到历史峰值, FGT 归零 ⇒ 被当作"没遗忘"
实测: 单任务 0.9 → 0.5 → 0.9
      t=1 (退化期) FGT = 0.4000  ✓ 正确报出
      t=2 (恢复后) FGT = 0.0000  ★ 归零
⇒ 问题: FGT 度量的是「距**历史峰值**多远」, 不是「距最近一次可用水平多远」
⇒ ★ 含义: 退化**被恢复**后, 历史记录里看不出曾经退化过
  ⇒ 若 DWC 需要"退化发生过"这件事本身可审计（而不只是"当前是否低于峰值"）,
    FGT 单独不够, 必须配时序指标（SAHOO 的 R_c 用了历史序列, 不会丢这段）
```

**★★ 已撤回的一个错误结论**（诚实记录）：

```text
我原本还写了第二个"陷阱"：FGT 的峰值锚会**掩盖反复的小退化**。
⇒ 实测**不成立**: 单任务 0.50 → 0.51 → 0.52 → 0.40, t=3 的 FGT = 0.1200
⇒ FGT **确实**报出了这 0.12 的退化, 并没有被掩盖。
⇒ ★ 撤回该结论。FGT 的真实弱点只有上面那一个（恢复后归零）。
★ 教训: 写"陷阱"这类论断时必须构造数值反例跑一遍, 不能只靠推理。
```

### 2.2 ★★ 回归风险（SAHOO Eq.18–23）—— 时序型，选它为主

```text
【Eq.18 回归风险本体】
  R_c = Pr( Q_c < Q_max − δ | H_c ),   H_c = {Q_0, …, Q_{c−1}}
  ★ 含义: "the probability that the next-cycle quality falls below Q_max − δ"
  ★ 对应 DWC: r̂_{t,j} = R_c（每个保护组 j 各一个）

【Eq.19 波动】  σ = std(H_c)
【Eq.20 趋势】  Q̂_t = α + β·t      (β<0 下降趋势; |β| 每轮速率)
【Eq.21 波动归一化缺口】
  z = (Q_c − Q_max) / (σ + ε)      ★ "how many standard deviations the current
                                      value lies below the historical peak"
【Eq.22 高斯近似】
  R_c ≈ Φ( (Q_max − δ − Q̂_{c+1}) / σ )     Φ = 标准正态累积分布
  ★ 原文自陈假设: "Under the **working approximation** that prediction errors are
    approximately Gaussian with standard deviation σ" + "Under **i.i.d. assumption**"
【Eq.23 趋势调整】
  R_c^adj = min{ 1,  R_c + 1{β < −ε_trend} · λ·|β| }
  ★ 原文: "increases the estimated risk when the fitted trend is **significantly
    negative** and otherwise leaves it unchanged"
  ★ λ "controls sensitivity to trend magnitude"; 趋势调整 "is **calibrated from
    validation-set oscillations** to detect persistent downward trends"

【D.4 停止规则】
  选 τ_R ∈ (0,1)。若 R_c^adj ≥ τ_R ⇒ "the system should issue a warning and
  consider **pausing further improvement cycles**"
  ★ τ_R "chosen by calibration (for example at a chosen percentile of observed
    risk during a validation period)"
```

### 2.3 ★ 为什么选 SAHOO 而不是 FGT

```text
维度        FGT (2501.07278)          SAHOO R_c^adj
──────────────────────────────────────────────────────────────────
形态        事后统计（当前低于峰值多少）  事前：预测下一轮会不会退
对应缺口    r̂_{t,j} 的"测"            r̂_{t,j} 的"预判"
★ 与门的关系  可作否决依据（事后）      可作为门的**预警输入**（事前）
基线锚      历史峰值（有陷阱）         Q_max − δ（显式容忍带）
波动处理    ✗ 无                       σ 归一化 ⇒ 不同量纲可比
趋势        ✗ 无                       β + ε_trend ⇒ 捕捉持续下降
★ 成本      O(t) 一次算完              需要每轮拟合（线性最小二乘，极便宜）

★★ 结论: FGT 用作**事后审计指标**（每轮记录，趋势图）,
   SAHOO R^adj 用作**门的预警输入** ⇒ 两者并存, 不二选一
```

---

## 三、★★ "能力组"的定义（DWC 侧的映射）

```text
★ 缺口原文说 "它保护哪些能力组", 但没定义组是什么。DWC 侧的定义:

能力组 (Capability Group) := 一个可独立评测的能力维度 j, 满足:
  ① 有稳定的 sealed 评测集（否则回归无从测起）—— 对应约束 3「双 split」
  ② 有历史成绩序列 {J_{j,i}}（否则 Q_max 无从算）
  ③ 组之间不可完全重叠（否则 ϵ_j 会被重复计罚）

★ 候选变更必须声明 protected_groups: set[str]
  —— 声明"我保护哪些组"，未声明的组按 ϵ 默认值处理（见 §四）

★ 与第 2 项 b_t 的关系: b_t 限"改几个", protected_groups 限"改完不能弄坏哪些"
  ⇒ 两个正交, 都要
```

---

## 四、★★★ ϵ_j 的三档口径（照抄守卫① 的双轨结构）

```text
★★ 为什么不能只有一个固定阈值: 与 theta_dev 同病 ——
   固定阈值在"整体变强后"会自我设限, 在"整体变弱时"会让退化解潜伏。

  ϵ_j = max( ϵ_floor_j ,  κ_r · rolling_Rmean_j ,  prev_ϵ_j )

  ϵ_floor_j   绝对容忍带下限（对应 SAHOO 的 δ, 是**有意允许**的回归幅度）
  κ_r·rolling  跟得上进步
  prev_ϵ_j     防抖锚（单调不跳变）

★ 与 SAHOO 的接口: ϵ_j 就是 Eq.18 里的 δ（"what counts as a meaningful regression"）
  ★ 原文明说 δ 是**按组定**的 ⇒ "for a given threshold δ>0", 每个组可有自己的
```

---

## 五、★ 三态保留 + 成本台账（25(c) 的两条同源要求）

```text
★ 要求一 · 三态保留（缺口原文）:
    accept / 保持现状 / **入 archive 待选**
  ⇒ DWC 的 applier 缺"入档"这一态
  ★★ 这与 DGM Table 1 的 +27.0pp 直接相关: 归档非贪心是最大收益源
    ⇒ "入 archive" 不是可选, 是主要收益路径

★ 要求二 · 失败尝试与成本也要记录（缺口原文）:
    "failed attempts and their costs also require recording"
  ⇒ DWC 的成本台账缺"被拒候选"这一项
  ★ 与第 5 项的五态结果同源: failed / rejected / unverified 都必须留成本

★ 成本必须报**向量**不报标量（缺口原文）:
    c = c_proposal + c_train + c_validation + c_execution   （式10 四分量）
    ★ "report a **resource vector** rather than add unlike units"
    ⇒ 「token」与「GPU-小时」不可直接相加 —— 与 (k) 后代评估预算归属同源
```

---

## 六、可机械检查的判据（gate.py 候选，R1–R6）

```text
R1 · 每个候选声明 protected_groups, 且非空
   空声明 ⇒ 不许进准入流程（原则 4: 无消费点的产物不许进）
   ★ 依据: 缺口原文 "must declare it protects which capability groups"

R2 · 每个保护组有 sealed 评测集 + 历史成绩序列
   ⇒ 组的定义三条（§三）可机械检查
   ★ 依据: §三 ①②; 无序列则 Q_max 与 FGT 都无从算

R3 · 回归风险进门的输入, 不只是审计记录
   ★ 若 R_c^adj 只被记录不被门读 ⇒ 它是死指标（同第 5 项 Level 3）
   ★ 与原则 9 同一纪律: 必须有一处门控消费
   ★★★★ 2026-10-04 R8 修正: 本条形式上可判, 但**现在不可执行 = 死判据**
     原因: R3 的输入需要"历史成绩序列", 而
           config/capability_groups.yaml 三组的 has_history_scores **全为 false**
     ⇒ ⇒ 无序列 ⇒ Q_max 与 FGT 都无从算 ⇒ 门读不到回归风险
     ⇒ ★ 这是与 TASK_SCORE_TRACKING 抓到的那条**完全同型**的问题:
         Λ=0.03 死判据（形式可判但阈值物理上永不触发）
     ⇒ ★★ 所以它不是"缺判据形式"，是**缺前置数据**
     ⇒ 依赖链: C3'/TS1（TaskScorePoint 落盘）→ has_history_scores 转 true → R3 才活
     ⇒ ★ 而这与缺口 A9 第一层同款: 判据落盘了，但数据/口径没到位

R4 · ϵ_j 用双轨（floor + rolling + anchored）, 不许纯固定
   ★ 依据: §四 与 theta_dev 同构
   ★★★★ 2026-10-04 R8 补: 三个分支的定义**已完整**，在 STATE_SCHEMA §六:
       floor    = theta_floor（绝对下限，防"越来越差也认可"）
       rolling  = κ · mean(history)（滑动基线，κ<1 是宽容系数）
       anchored = prev_theta（保证阈值单调不跳变，防抖）
       ★ 并有 anchored_no_history 第四态（无历史时回退）
       ★ 取值规则: max(cands, key=…) 且按硬度排序 floor > rolling > anchored
       ★★ 踩过的坑（STATE_SCHEMA 已记）: 若写成 if/elif 依次比较,
          prev_theta 通常是三者最大 ⇒ floor/rolling 永不触发 ⇒ kind 恒 anchored
          ⇒ 该字段失去诊断价值 ★ 这是真 bug，不是笔误
   ⇒ ★★ 判据形式: 三个分支参数（theta_floor / κ / prev_theta）都必须显式声明,
     且三者不得全相等（相等 ⇒ 退化为纯固定 ⇒ 违规）

R5 · applier 有"入 archive"这一态, 且入档路径有真实消费点
   ★ 依据: §五 要求一 + DGM +27.0pp
   ★ 若入档后无人读 ⇒ 它是另一个 branch_merges

R6 · 被拒候选的成本入台账, 且报资源向量不报标量
   ★ 依据: §五 要求二 + 式10 四分量
```

---

## 七、诚实边界

```text
① 本设计**未写代码**，`src/` 仍为空。
② 未验证: R1–R6 全是设计推理。
③ ★★ SAHOO 的高斯近似有两条**论文自陈的假设**，必须照录:
     · "working approximation that prediction errors are approximately Gaussian"
     · "Under i.i.d. assumption with σ estimated from historical volatility"
   ⇒ 质量序列非高斯 / 非 i.i.d. 时, Eq.22 的近似会失真
   ⇒ ★ DWC 的质量序列是**阶梯函数**风险（母巢 score_in 的教训：
     量化阶梯使同台阶内 gain 恒 0）⇒ σ 会趋于 0 ⇒ 除零
   ⇒ ★★ 应对: ε 正则项不是可选的, 必须有下界; 且 σ 过小时应退回 FGT 口径
④ ★ τ_R 与 λ 的具体值未定（论文只说"由校准得出", 未给数）。
   ⇒ 与 θ_dev / ϵ_j 一样, 须在 DWC 真实负载上校准。
⑤ ★ "能力组"的划分是**我的设计**, 论文没给（DWC 独有的问题）。
   ⇒ 划几组、每组怎么测, 需第 6 项（器官接口契约）定稿后才能落。
⑥ 未核实: DWC 的 sealed 评测集当前只有 15 条（ARSI 起步量）,
   ⇒ 保护组的组数上限受此约束（每组都要有评测集）
⑦ FGT 的"历史峰值陷阱"（§2.1）是我的分析, 不是论文自陈的缺陷。
   ★ 但推导基于式(16) 的字面形式, 可复核。
```

---

## 八、★ 实测记录（rc=0 全通，并抓到我一个自造的错误结论）

```text
✓ 陷阱1 证实: 0.9→0.5→0.9 ⇒ t=1 FGT=0.4000, t=2 FGT=0.000000
✓ ★★ 原"陷阱2"被实测推翻: 0.50→0.51→0.52→0.40 ⇒ t=3 FGT=0.1200 (不是 0)
  ⇒ 我的"峰值锚掩盖小退化"结论**不成立, 已撤回**
✓ SAHOO 判别力: 稳定上升 adj=0.0002 < 温和下降 1.0000 ≤ 持续下降 1.0000
  ⇒ 单调递增（温和与持续都撞到 cap=1.0, 区分度在此区间消失 —— 诚实记录）
✓ delta 作用: 0.01→adj=1.0000, 0.30→adj=0.9936 ⇒ 容忍带越大风险越低 ✓
★ eps 正则项是**必需**的, 不是可选:
  eps=0 且 sigma=0 ⇒ ZeroDivisionError（实测崩）; eps≥1e-12 才不崩
  ⇒ 与诚实边界③一致: DWC 的质量序列是阶梯函数（母巢 score_in 教训）⇒ sigma 常为 0

★ 两处诚实修正:
  ① 撤回"掩盖小退化"结论（实测推翻）
  ② 修正 §2.3 对比表: FGT 不是"只能事后否决" —— 它可作否决依据,
     SAHOO 的优势在**事前预警**与σ/β 归一化, 不在"能不能否决"
```

---

## 九、诚实边界（补）

```text
⑧ 实测覆盖: FGT 式16 字面实现 / SAHOO Eq.19-23 / delta 单调性 / eps 除零。
   **未测**: 多任务混合时的加权、真实质量序列（实测用的是构造的小数组）。
⑨ ★ 实测发现 SAHOO 在"温和下降"与"持续下降"两例都饱和到 adj=1.0
   ⇒ ⇒ 在真实场景下 cap=1.0 可能过早触发 ⇒ τ_R 的校准必须用真实分布,
     不能用我这三个人造数组。
```

---

*设计定稿 · 2026-10-04 · SAHOO Eq.18-23 为主 + FGT 式16 为审计 · 参照两篇原文逐字核 · 未写代码*