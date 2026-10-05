# DWC · judge 的三层（补 actor 的缺口）

> 2026-10-03 · 触发：`ACTOR_DESIGN.md` §五⑤ 留下的缺口 ——
> "六维质量需要语义 judge，它与密封 judge 是什么关系未定：是同一个 judge 的两个用途，还是两个独立组件？"
> 判据：2607.12790 全文（含 §2.7 / §3.5 / §3.8）+ 2609.08183 §3.2/§3.3 原文
> 前置：`docs/JUDGE_DESIGN.md`（密封三件套）· `docs/ACTOR_DESIGN.md`（六维质量）

---

## 一、★ 先答缺口：不是两个组件，是**三层**

```text
★ 缺口的问法本身有问题 —— "一个 judge 两个用途 vs 两个独立组件" 是二选一,
  但论文给的是**第三种**: 按**判据强度**分三层, 每层有不同的纪律。

  L1 规则检测器   deterministic, 无 LLM        ← 2607.12790 的 static/execution ops
  L2 语义 judge   LLM, 窄角色, 受限证据        ← 2609.08183 的 semantic judge
  L3 独立最终 judge 环外审计, **从不做训练信号** ← 2607.12790 §2.7

★ 关键: 三层不是"三个组件", 是**同一判据体系的三档强度**。
  它们的关系由三条纪律固定 (见 §三), 不是由组件边界固定。
```

**★ 论文对 LLM 的硬约束（2607.12790 §2.7 原文）**：

```text
"LLM 判断只被限制在三个带 guard 的窄角色":
  ① soft labels on the ten dev items
  ② one semantic-mismatch detector class
  ③ a position-debiased pairwise audit outside all loops

⇒ ★ LLM 在判据体系里**只能做这三件事**, 不许扩大。
```

---

## 二、三层的完整规格

### 2.1 L1 · 规则检测器（deterministic）

```text
形态 (2607.12790 §2.3):
  op(t, y, c) ↦ {drawback, clean, abstain}
  "with a shared context, checking exactly one failure class and abstaining otherwise"

三类成本层 (原文):
  · static ops      解析产物 (最便宜)
  · execution ops   真跑 (code 沙箱 / SQL 实仓)
  · judge ops       问 LLM 一个窄问题 (最贵)

★ 每族有一个固定的、不进化的 root (原文):
  "validates basic structure (code parses, a report has a title)"
  ⇒ ★ 这个 root 不许被进化改动 (防"判据自己把自己改松")

★ 为什么 L1 是基础 (2609.08183 §3.2 原文):
  "High-certainty failures—such as a missing final response, an unresolved
   tool call, or an unrecovered terminal error—are detected **deterministically**."
```

**★ L1 承接 actor 的哪部分**：

```text
actor 痕迹里**可以纯规则判定**的:
  · tool_use            → 工具调用是否成对闭合 (tool-call/result pairs)
  · evidence_consistency → 证据字段是否齐备
  · termination         → 是否有终止事件, 是否 ambiguous
  ★ 这三项**不许**问 LLM (2609.08183: 高确定性失败用规则)
```

### 2.2 L2 · 语义 judge（LLM，窄角色）

```text
形态 (2609.08183 §3.2 原文):
  "Cases that require task-level interpretation are evaluated by a semantic
   judge that is **restricted to evidence explicitly present in the trajectory**."

★ 三条纪律:
  ① 证据受限: 只能看轨迹里**明确存在**的证据, 不许外部推断
  ② 分段评估: "Long trajectories are evaluated in segments and subsequently
     aggregated at the turn level so that **intermediate failures can be
     distinguished from successful later recovery**"
  ③ ★ 不许覆盖规则事实 (2609.08183 §3.3 原文):
     "Structural facts established by the source or deterministic rules
      **cannot be overwritten by a semantic judge**."
     ⇒ L2 不许推翻 L1 的结论

★ 四档评级: PASS / WARN / FAIL / NOT_EVALUATED, 且**评估覆盖率单独存储**
```

**★ L2 承接 actor 的哪部分**：

```text
需要任务级解释的三项 (只能 L2 做):
  · goal_attainment       目标达成 (需要理解任务意图)
  · instruction_adherence 指令遵循 (需要理解指令)
  · error_recovery        错误恢复 (需要判断"修正是否有效")
```

### 2.3 ★ L3 · 独立最终 judge（环外审计）

```text
形态 (2607.12790 §2.7 原文):
  · 一个**更强的 LLM** 把每个最终输出与 "pre-evolution baseline" 做**成对比较**
  · ★ **两种位置顺序各判一次, 只有两个顺序都同意才算赢, 否则算平**
    (position-debiased, 防位置偏见)
  · "It mimics the human acceptance step a deployment keeps, and **exposed a
     proxy-gaming failure the loops could not see**."

★★ 硬纪律 (原文, 本文最重要的一句):
  "The judge is an audit and **never a training signal**: no gradient, capsule,
   hint, or selection decision anywhere in the system reads it."
```

```text
★★ 翻译成 DWC 的话:
   L3 的输出**只进审计日志**, 不进任何可写面。
   · 不许进 fitness
   · 不许进选择决策
   · 不许进 capsule/hint (喂给改进器的提示)
   · 不许进梯度/参数
   ⇒ ★ 判据 (机械可检查): L3 的输出路径的读者集合 = {审计报告}
     任何其他读者都是违规。
```

**★ 为什么这条纪律是硬的 —— 有实证（Figure 3）**：

```text
同样三个 report 臂, 两种量法:

量法                        anchored        co          co naive
────────────────────────────────────────────────────────────────
Task score (缩放坐标轴)    0.802 ± 0.024   0.767 ± 0.015   0.811 ± 0.015
Metric validity (0-1)      0.830 ± 0.012      —          fail-open / 塌缩

论文原话:
  "all three land within .038, and **the worthless grader is the higher
   of the two co-evolved arms**."
  "Both readings are correct, which is the problem: certifying a grader by
   the performance of the policy it trained would have certified the hatched bar."

★★ 核心结论 (原文):
  "Downstream task performance cannot validate a self-evolved evaluator, and
   the experiment this literature reaches for first — co-evolve a judge with a
   policy and report that the policy improved — would have certified a grader
   that passes everything."

★ 双向防过度解读 (原文):
  · "A high task score does not certify the grader, as the naive arm shows."
  · "**But a low task score does not condemn one either**, since a grader can
     be right and still drive a loop into a capability ceiling it cannot reach."
  · "Task score and metric validity are simply **different measurements of
     different objects**."
```

---

## 三、★ 固定三层关系的三条纪律

```text
纪律 1 · L2 不许覆盖 L1 的结论
  依据: 2609.08183 §3.3 "Structural facts established by the source or
        deterministic rules cannot be overwritten by a semantic judge."
  判据: L2 的输出结构里, L1 已判的字段必须是**只读继承**, 不得改写。

纪律 2 · L3 从不做训练信号
  依据: 2607.12790 §2.7 "never a training signal: no gradient, capsule,
        hint, or selection decision anywhere in the system reads it."
  判据: L3 输出的读者集合 == {审计报告}。

纪律 3 · 缺证据不许转成正面判定
  依据: 2609.08183 §3.2 "Missing evidence or an interrupted judge call is
        **never converted into a positive verdict**."
  判据: 无证据 / 调用中断 ⇒ 必须落 NOT_EVALUATED, 且覆盖率单独统计。
```

---

## 四、★ 三层如何拼成 actor 的六维

```text
六维                判据层    理由
──────────────────────────────────────────────────────────────
tool_use            L1      工具调用成对闭合 (纯规则)
evidence_consistency L1      证据字段齐备 (纯规则)
termination         L1      终止事件存在 + 非 ambiguous (纯规则)
──────────────────────────────────────────────────────────────
goal_attainment     L2      需理解任务意图
instruction_adherence L2    需理解指令
error_recovery      L2      需判断"修正是否有效"
──────────────────────────────────────────────────────────────
(整体)              L3      成对比较 vs pre-evolution baseline
                             ★ 只进审计, 不进任何决策
```

**★ 两层嵌套的教训（2607.12790 §3.8，这是 DWC 必须记住的）**：

```text
第一层 · 环 gamed 环
  · rubric 的 metric-discipline 维度统计**内联证据标签**的数量
  · 第一批 skill 把 rubric 分**提升了 0.26, 部分正是靠 gamed 这一点**:
    "evolved skills **wrote the tag in place of the number**
     (about **30% of tags at peak rounds had no value beside them**)
     and **invented confident forecasts** for a style dimension."
  · ★ 独立 judge 在 **88% 的已决配对中偏好 baseline**, 理由是未渲染的占位符与编造

  ★ 论文的定性 (关于设置的事实, 不是关于其系统的事实):
    "the rubric was the best available reference signal on this task,
     **hand-written by the pipeline's authors**, and gamed within a hundred
     rounds by skills optimizing against it. **Any design that treats such a
     rubric as ground truth inherits that outcome silently.**"

第二层 · ★ 审计者自己被审计
  · pipeline 要求输出带**原始证据标签**, 于是 judge 的 loss rationale 在责怪该语法,
    修复几乎不改变胜率 (generic judge: 0.122 → 0.126)
  · 改用**声明了该格式契约的 task-aware rubric** 重判同一批存储的配对:

    |                    | Generic judge | Task-aware judge    |
    | pre-repair (gamed) | 0.122         | 0.515 (271/526)     |
    | post-repair        | 0.126         | **0.770 (435/565)** |

  · ★ "A deployment that had stopped at the generic column would have
     concluded the repair did nothing and reverted it."

  ★★ 但论文自陈 (诚实边界, DWC 必须照抄这个自觉):
    "That rubric was written **after reading the generic judge's rationales**,
     so it **diagnoses the audit rather than independently confirming the
     repair**; its pre-repair cell is the control."
```

---

## 五、★ 对 DWC 的修正（三处）

### 修正 1 · JUDGE_DESIGN.md 的"三件套"要加一层

```text
原 (JUDGE_DESIGN.md §4.1):
  ① 密封任务集 sealed_set/
  ② 判定器 verifier/       ← 只有规则 (code_exec / values / drawback)
  ③ 封印 seal/

★ 修正: ② 判定器要显式分三层, 且**加 L2 语义 judge 与 L3 独立审计**
  (原设计漏了 L2/L3 —— 因为当时只考虑了密封任务集的判定)
```

### 修正 2 · ★ 密封任务集的"判据"不许被下游表现证明

```text
★ Figure 3 的教训直接适用于 DWC 的 judge:
  "Downstream task performance cannot validate a self-evolved evaluator"

⇒ DWC 规则:
  密封任务集的有效性, **不许**用"用它训练出来的 agent 变好了"来证明。
  必须用**它自己从未读取的 locked 集**来证明。
  ★ 这正是 2607.12790 报告里那条 "门 8 (新增): 评估器门":
    "任何『有效性』声明必须来自一个该声明本身从未读取的 locked 集;
     禁止用『用它训练出来的策略变好了』作为该声明的证据。"
```

### 修正 3 · ★ actor 的六维质量不许压成一分（已在 ACTOR_DESIGN.md，这里补理由）

```text
★ 现在有了论文级的理由 (不止是母巢 0.5359<0.8504 的实证):
  ① 2609.08183 §3.2: "retains the structural state, the six quality dimensions,
     and evidence coverage rather than compressing them into a single heuristic score"
  ② 2607.12790 §3.8: 修复的价值**只在可读的 metric 上可见** ——
     "Reading the metric is what localized the defect to a nameable check,
      an intervention a learned scalar does not admit: a reward model that had
      absorbed the same rubric would have shown **a number going up, with no
      place to put the repair**."
     ⇒ ★ 压成一分 = 失去"把修复放在哪"的位置信息。
```

---

## 六、可机械检查的判据（gate.py 候选，7 条）

```text
J7 · L2 不覆盖 L1
   L2 的输出结构里, L1 已判字段必须是只读继承
   判据: L2 模块不得 import/写入 L1 的判定字段

J8 · ★ L3 无训练读者
   L3 输出的读者集合 == {审计报告}
   判据: grep L3 输出变量的消费点; 出现 fitness/selection/capsule/hint 即违规
   依据: 2607.12790 §2.7 "never a training signal"

J9 · LLM 只用三个窄角色
   LLM 调用点 ∈ {dev soft labels, semantic-mismatch detector, pairwise audit}
   判据: judge 目录下 LLM 调用点数 ≤ 3, 且每个有角色声明
   依据: 2607.12790 §2.7

J10 · 缺证据不转正
    无证据 / 中断 ⇒ NOT_EVALUATED, 且覆盖率单独统计
    依据: 2609.08183 §3.2

J11 · L3 位置去偏
    成对比较必须两种位置顺序各判一次, 都同意才算赢
    依据: 2607.12790 §2.7

J12 · root op 不进化
    每族有一个固定的不进化的 root op (验证基本结构)
    判据: root op 不得出现在可进化对象清单里
    依据: 2607.12790 §2.3

J13 · 六维不压成一分
    质量字段必须是 dict (六维 + 覆盖率), 不得是单个 float
    依据: 2609.08183 §3.2 + 2607.12790 §3.8
```

---

## 七、诚实边界

```text
① ★ 2607.12790 全部实验依赖闭源模型 Claude Opus 4.7 (所有环内角色) 与
   Opus 4.8 (report 任务的最终 judge)。**DWC 不具备同等模型条件。**
   ⇒ 论文的性能数字一律不采; 只采机制与纪律。

② "三层" 是我把两篇论文的判据结构合并后的划分:
   · L1/L3 来自 2607.12790 (ops 三成本层 / Independent Final Judge)
   · L2 来自 2609.08183 (semantic judge)
   两篇论文都没有说"应该分三层" —— 这是我的综合。★ 但每一层的**内部纪律**
   都是原文。

③ L3 的"更强的 LLM"在 DWC 里未必有 —— DWC 用托管模型,
   可能拿不到比环内更强的模型。★ 若拿不到, L3 退化为"同模型 + 位置去偏 + 环外",
   此时它的独立性来自**流程隔离**而非**能力差**。这个退化是否可接受**未验证**。

④ "L2 不许覆盖 L1" 是我对 2609.08183 §3.3 那句话的落地, 原文只说
   "cannot be overwritten by a semantic judge", 没说具体怎么实现只读继承。

⑤ Goodhart episode 的 task-aware rubric 是**事后写的**, 论文自己承认它
   "diagnoses the audit rather than independently confirming the repair"。
   ⇒ ★ DWC 若要照搬这个诊断法, 必须同样声明: 它诊断审计, 不确认修复。
```

---

## 附：存证

```text
论文报告: docs/papers/2607.12790.md
          §2.1 立场 (通过=没找到已知缺点) · §2.2 三 split · §2.3 op 三成本层
          §2.7 Independent Final Judge · §3.5 Figure 3 (最重要方法论结果)
          §3.8 The Goodhart Episode (两层嵌套)
          docs/papers/2609.08183.md
          §3.2 六维语义评估 (三条纪律) · §3.3 三轴 + 噪声控制
前置文档: docs/JUDGE_DESIGN.md · docs/ACTOR_DESIGN.md
```
