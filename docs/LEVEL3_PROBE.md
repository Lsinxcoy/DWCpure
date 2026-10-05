# DWC Level 3 行为验证的探针（缺口 A7）

> **状态**：设计定稿（**未写代码**，`src/` 与 `config/` 均空）
> **日期**：2026-10-04 · **来源**：`docs/GAP_AUDIT.md` 缺口 A7
> 原文记载：「Level 3 能否实现（**依赖决策点形态全部定稿**）」
> **参照**：`ARCHITECTURE.md` §4.2（actor 三段式 + 决策优先级 + 三分离）
> `docs/CONSUMER_VERIFICATION.md` §二（Level 3 的原始定义）
> `docs/ORGAN_INTERFACES.md` §六（iwm.probe 签名）

---

## 一、★★★ 先说核实结果：**前提已具备**（A7 当初的阻塞理由已消失）

```text
★ A7 当初写的阻塞理由: "依赖决策点形态全部定稿"
★ 实测: 「决策点」一词在 ARCHITECTURE 全文只出现 2 处,
  且两处都是在说"依赖它定稿" ⇒ ★ 决策点形态确实从未被单独定稿
★★★ 但核实后发现, **决策点的形态已经隐含在 §4.2 里了**, 不必新造概念:

  §4.2 已定（逐条核原文）:
    形态 = 三段式: ① 取任务 W.legal_actions() → 采样(EL调度器) → 本轮任务
                    ② 执行 observe → decide → act → record
    决策优先级 = 预测(世界模型, **有门控**) → LLM → 启发式
    两类动作 = 甲任务动作(来自 legal_actions) / 乙维护动作(dream/learn/maintain/remember)
    三分离 = prediction / decision / outcome 分开存（2609.08183 §3.4）

⇒ ★★ Level 3 的"决策点" = §4.2 里的 **decide 那一步**, 三处:
     ① 采样门（① 段: 从 legal_actions() 选哪个任务）
     ② 决策源门（② 段 decide: 预测 / LLM / 启发式 谁说了算）
     ③ 动作执行门（② 段 act: 甲任务动作 / 乙维护动作）
⇒ ⇒ A7 的答案不是"能不能实现", 而是"**探针挂在这三处**"
```

### 1.1 ★ 为什么探针必须挂在这三处（而不是"任意决策点"）

```text
★ 一个基因被消费, 只可能通过这三条路径之一:
  ① 它改了 legal_actions() 的排序/权重 ⇒ 影响"选哪个任务"
  ② 它改了 iwm 的 τ_high/τ_low 或降级档 ⇒ 影响"谁说了算"
  ③ 它改了执行器/工具选择 ⇒ 影响"做什么"
⇒ ★★ 若一个基因不在这三条路径上, 它**结构上不可能被消费**
⇒ ⇒ L1/L2 会通过, 但 L3 必然失败 ⇒ 这正是"死基因"的准确定义
```

---

## 二、★★ 三类探针（每类对应一条路径）

```python
# 落点: organs/iwm/probe.py  （ORGAN_INTERFACES §六 probe 的实现）
@dataclass(frozen=True)
class DecisionProbe:
    """★ 探针规格。与 ConsumerSpec.decision_probe 一一对应。"""
    probe_id: str
    gene: str                 # 被探的基因（消费点声明里的 attr 对应物）
    kind: str                 # ★ "sample_gate" | "source_gate" | "action_gate"
    target: str               # 该决策点上读取该基因的位置
    expect_effect: str        # 期望观察到什么（表达式，由 ConsumerSpec 给）
    window_rounds: int        # ★ 在几轮内必须被观察到
```

```text
★ kind 的三值必须显式, 无默认值（与 K4/editable、G11/certification_limit 同款纪律）
★ window_rounds 必填: 无窗口的探针等于"永远等" ⇒ 会变成无期限的 pending
```

### 2.1 ★ 三类探针各自的观察点（基于 §4.2 的原文）

```text
① sample_gate（采样门）
  位置: §4.2 ① 段 "W.legal_actions() → 采样 (EL 调度器)"
  观察: 本轮被选中的任务是否因该基因而改变排序
  ★★ 依赖: 第 7 项已定的层1(FWT 偏置) / 层2(中间难度带)
     ⇒ 基因若作用于采样权重, 观察点是"选中任务的变化"
  ★ 注意: FWT 只作**偏置**不作**闸门**（第 7 项已定）
     ⇒ ★★ ⇒ 观察判据**不能**要求"每次都改变选择", 只能要求"曾改变过"
     ⇒ 这直接给出窗口语义: 窗口内**至少一次**可归因变化

② source_gate（决策源门）
  位置: §4.2 ② 段 "预测(世界模型, 有门控) → LLM → 启发式"
  观察: decision_source 字段的值是否因该基因而改变
  ★★ 这是最可观测的一处 —— §4.2 已定 Trace 三分离, decision 与 outcome 分开存
  ⇒ 可直接读 Trace.decision_source, 不需要新埋点 ★
  ★ 但注意: 守卫① 的 iwm.advice 也影响这个门（ORGAN_INTERFACES §六）
     ⇒ 若基因是 iwm 的 τ_high/τ_low, 它改变的是"何时降级" ⇒ 仍是 source_gate

③ action_gate（动作执行门）
  位置: §4.2 ② 段 act, 两类动作分流处
  观察: 实际执行的动作类别（甲任务/乙维护）与该基因预期是否一致
  ★★★ 这一类最难观测: 因为 §4.2 已定"维护动作频率由 iwm 定",
     而 iwm 的频率本身可能是另一个基因的效果
     ⇒ ⇒ 两个基因的效果会**互相混淆** ⇒ 见 §三的归因问题
```

---

## 三、★★★ 三个真问题（Level 3 的难点都在这里，不在"能不能写探针"）

```text
★★★ 问题 1 · **归因混淆**: 多个基因同时作用时, 效果归给谁?
  §4.2 已定 §9 第 2 项的 b_t = 退火编辑预算, b_min=1
  ⇒ 最后一轮只允许一个编辑 ⇒ ★ 那时归因是干净的
  ⇒ 但前期 b_t 可能 >1 ⇒ 效果可能来自多个基因
  ⇒⇒ 裁决: 探针只在 |本轮编辑集| == 1 时判定成功;
     否则 outcome 记 **inconclusive**（不是 failed, 也不是 verified）
  ★★ 与第 5 项的五态并列为第六态? ⇒ 我选: 不新增第六态,
     而是把 inconclusive 映射到 unverified + 附加 reason="multi_edit"
     ⇒ 理由: 五态的价值在于可聚合, 加第六态会破坏聚合查询

★★★ 问题 2 · **观察窗口的长度**依赖进化事件, 不是固定值
  ⇒ 若进化事件迟迟不发生 ⇒ 探针永远 pending
  ⇒ 裁决: window_rounds 的上限 = ERROR_AND_TERM 已定的 term 边界
     ⇒ 若 term 结束仍未观察到 ⇒ outcome=unverified + reason="window_expired"
  ★★ 这一条把 A5（term 边界）变成了 Level 3 的依赖 ⇒ 依赖链闭合

★★★ 问题 3 · **观察 ≠ 因果**: 基因改了 ε, 采样恰好没用到它
  ⇒ 裁决: 探针判据只要求"观察值与 expected_readback 一致",
     **不要求**"这次选择一定因此改变"
  ⇒ 理由: §4.2 已定 FWT 只作偏置不作闸门 ⇒ "必然改变"不是 DWC 的性质
  ⇒ ⇒ 这是"消费点"的最弱可证形式: 不是"它决定了决策", 而是"它在决策中被读到"
```

---

## 四、可机械检查的判据（gate.py 候选，L1–L6）

```text
L1 · 每个 ConsumerSpec 必须声明 decision_probe（无默认值）
   ★ 依据: 问题 3 —— 无探针 ⇒ 只能是 applied/verified 的旧命名, 无法判死基因
   ★★ 与 K4 / G11 / X1 同款纪律

L2 · DecisionProbe.kind 必须是三值之一, 且 target 不得为空串
   ★ 防止"声明了一个空探针"骗过 L1

L3 · probe 的观察点必须落在 §4.2 已定的三处之一
   ★ 判据形式: probe.target 的路径前缀 ∈ {task_sampler, decide, action_exec}
   ★★ 依据: §一 —— 不在这三条路径上的基因结构上不可能被消费

L4 · window_rounds 必填, 且必须 ≤ term 边界的步数上限
   ★★ 依据: 问题 2 —— 否则探针永远 pending
   ★ 依赖: ERROR_AND_TERM 的 T2（term 边界由进化事件决定, n_steps 只是上限）

L5 · |本轮编辑集| > 1 时, 探针判定必须记 inconclusive 而非 verified
   ★★ 依据: 问题 1 的归因混淆
   ★ 形式: reason == "multi_edit"

L6 · 每个基因的 outcome 必须在消费点审计里可聚合
   ★ 形式: ConsumerAudit 能按 {outcome, reason} 分组计数
   ★★★ 依据: 这正是"死基因事后可查"的唯一途径（CONSUMER_VERIFICATION §五）
```

---

## 五、★★ 与既有判据的接口（不新增概念）

```text
★ A7 落地后, 第五项的五态变成可判满的:
  applied   L1+L2 通过, L3 还没到窗口              ⇒ 暂态
  verified  L1+L2 通过 + L3 在单编辑轮观察到        ⇒ 真验证
  rejected  门拒（不是验证失败）                    ⇒ 流程正常
  failed    L1/L2 出错 ⇒ 已回滚                     ⇒ 技术失败
  unverified L3 到窗口末未观察到 ⇒ **死基因**
     ★★ reason 必填, 至少四种:
        "multi_edit"（归因混淆）· "window_expired"（窗口到）
        · "probe_missing"（未声明探针）· "gate_silent"（门静默通过）

★★★ ⇒★ 这条闭环了 DWC 里最重要的一条链:
  母巢 167,753 行 branch_merges 无人消费
  ⇒ DWC 的对应机制是"六步门 + 三级验证 + unverified 单独统计"
  ⇒ ★★ 而 unverified 能被统计的前提就是 L3 可实现 ⇒ **A7 是这条链的最后一环**
```

---

## 六、诚实边界

```text
① 本设计**未写代码**，`src/` 与 `config/` 均空。
② 未验证: L1–L6 全是设计推理。
③ ★★★ 我改了 A7 当初的表述: 它写"依赖决策点形态全部定稿", 而我核实后
   认为决策点形态**已隐含在 §4.2**（三段式 + 决策优先级 + 三分离）
   ⇒ ★ 这是我的判断, 不是文档明文 ⇒ 若 §4.2 将来改动, 本设计需重审
④ ★★★ action_gate 的归因混淆（问题 3 末）我**没有解决**, 只标了它存在:
   iwm 的维护动作频率本身可能是另一个基因的效果
   ⇒ ★ 两个基因的效果在观测上不可区分
   ⇒ ★ 缓解: 依赖 b_t 退火（末轮单编辑）；但前期无效
⑤ ★ window_rounds 的**具体值**未定, 只定了它的上限来源（term 边界）
⑥ ★★ 观察 ≠ 因果（问题 3）我选了最弱可证形式, 代价是:
   ⇒ 一个"恰好在决策中被读到但实际不影响结果"的基因也会算 verified
   ⇒ ★ 这是**有意的保守不足**: 强形式（要求影响决策）在 FWT 只作偏置的
     设计下不可证
⑦ ★ 未核实: §4.2 的三处决策点在实现上是否会真的读那个属性
     （设计上有读取路径 ≠ 代码里有）
⑧ ★ 六种 reason 我列了四种, "gate_silent" 未给精确定义
⑨ ★ 本设计未处理: 探针本身失败（探针代码报错）时的 outcome
     —— 推测应记 failed + reason="probe_error"，但未论证
```

---

## 七、★ 实测记录（rc=0 全通）

```text
✓ L2/L3 合法探针通过; 非法 kind 被拒; target 不在 §4.2 三处时被拒
  ⇒ ✓ 挂在三处之外的基因, **结构上不可能被消费**

=== L5 · 归因混淆的处理（问题1）===
  编辑数=1 观察到=True  ⇒ verified
  编辑数=1 观察到=False ⇒ unverified / window_expired
  编辑数=3 观察到=True  ⇒ unverified / **multi_edit**   ← 关键
  编辑数=3 观察到=False ⇒ unverified / window_expired
  ⇒ ✓ 多编辑时不判 verified（归因不干净, 不硬判）

=== L4 · 窗口依赖 term 边界（问题2）===
  window_rounds 5/20/50 ✓ · 51/100 ✗（超出 term 硬上限 50）
  ⇒ ★ A5（term 边界）成为 L3 的依赖 ⇒ **依赖链闭合**
  ⇒ term 结束仍未观察到 ⇒ reason="window_expired"

=== 问题3 · 观察 ≠ 因果（最弱可证形式）===
  观测=期望 且   影响选择 ⇒ verified
  观测=期望 且 **不影响**选择 ⇒ verified  ← ★ 有意的保守不足
  观测≠期望          ⇒ 不算
  ⇒ ★★ 强形式（要求影响决策）在 FWT 只作偏置的设计下**不可证**

=== L6 · outcome+reason 可聚合 ===
  verified —                1
  unverified multi_edit     1 / window_expired 1 / probe_missing 1
  failed    probe_error      1
  ⇒ 死基因合计 **3 条**（可聚合查）★ 这正是"死基因事后可查"的唯一途径
```

---

## 八、诚实边界（补）

```text
⑩ 实测覆盖: L2/L3 的探针合法性 / L5 的多编辑判定 / L4 的窗口边界
   / 问题3 的三种情形 / L6 的聚合
   ★★ 未测: 三类探针在真实决策流上的可观测性（无实现）
⑪ ★ 一次自测失败是我**代码笔误**（写了 `readback: Any_ = None if False else None`）
   ⇒ 已删除该段。★ 记此以免误读实测记录。
⑫ ★★ 实测暴露一个我在正文没写清的点: 编辑数>1 且**未**观察到时,
   reason 是 "window_expired" 而非 "multi_edit"
   ⇒ ⇒ 两个 reason 互斥还是可并存? 我选了互斥（先判观察, 再判编辑数）
   ⇒ ★ 这个优先级未在正文论证, 记此待审
⑬ ★ action_gate 的归因混淆（诚实边界④）实测**未覆盖**:
   我的测试里 action_gate 没有构造两个基因互相影响的场景
   ⇒ ★ 该问题仍是未解决状态, 不是"已验证可处理"
```

---

*设计定稿 · 2026-10-04 · 核实前提已具备（决策点=§4.2 三处）+ 三类探针 + 三个真问题（归因混淆/窗口依赖/观察≠因果）+ L1–L6 · 未写代码*