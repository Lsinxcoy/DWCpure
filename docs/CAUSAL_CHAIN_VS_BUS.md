# DWC · 需要事件总线吗？（§9 第 4 优先项的裁决）

> 2026-10-03 · 触发：用户质疑 —— "需要事件总线吗？我们不是定了世界模型是决策核心，
> 它才是驱动时间推进的动力，不是吗"
> 判据：ARSI 全仓 grep（有/无总线 + 因果链）+ 母巢 EventBus 实测 + 论文原文
> 前置：`ARCHITECTURE.md` §2.3 三层驱动 / 原则 10 / 原则 11

---

## 一、★ 先给结论：用户对了一半，但漏了第二条轴

```text
★ 用户说的"世界模型驱动时间推进" —— **完全正确**。
  §2.3 决策层已定: 世界模型 → 预测后果 → 选动作/相位。
  事件总线**不驱动时间** —— 驱动时间是世界模型。

★ 但"事件总线"这个词被 v3 混了两个不同的职责:

  ┌─ 轴 A: 驱动时间 (什么让下一轮发生)
  │   ★ 已定 = 世界模型。事件总线**不参与**。
  │
  └─ 轴 B: 记录因果 (这一轮为什么发生, 由谁触发)
      ★ 未定 = 这才是 §2.3 ③ 事件层真正要解决的。
      它与"驱动时间"是**正交的两条轴**。

★ 所以正确的问法不是"要不要总线", 而是:
  "轴 B (因果记录) 用什么形态实现 —— 总线, 还是 ledger?"
```

**★ 关键实测：ARSI 没有事件总线，它用 ledger。**

```text
grep 结果 (全仓, 排除 __pycache__):
  · ARSI 有 "event_bus" / "EventBus" 的文件: **0 个**
  · ARSI 只有 2 处含 "publish" 字样, ★ 已逐行核实 —— **两处都是假阳性**:
    core.py:136          "# Hyperparams: official **unpublished** → config/..."
    meta/dream_rsi_params.py:3  "Official hyperparams **unpublished** → ARSI defaults..."
    ⇒ 是 "unpublished" 里的 "publish", 与总线无关。
  · ★ 宽口径复核 (event_bus|EventBus|\.publish\(|\.subscribe\(|publish_sync|
    message_queue|pubsub|pub_sub, 全 src/ 递归): **命中 0 处**
    ⇒ ARSI **确实零总线**, 结论确认。

  ★ ARSI 实际用的是四个 ledger (全在 iwm/ 与 foundation/):
    iwm/provenance.py          DecisionProvenance  Q5: 为什么选 a
    iwm/transition_ledger.py   TransitionLedger    Q4: 行动后我变成了什么
    iwm/vitals_ledger.py       为什么指标是平的
    foundation/cost_ledger.py  成本记账

  ⇒ ★ 一个成熟的 RSI 系统 (ARSI) 选择了 **ledger, 不是总线**。
```

---

## 二、★ 但 ARSI 的 ledger 方案有一处硬缺陷：链是断的

### 2.1 四个 ledger 各自独立，互不引用

```text
grep "四个 ledger 之间有无互相引用":
  --- provenance 被谁 import ---        (除定义处, 只有 core.py 用它的 decision_id)
  --- transition_ledger 被谁 import ---  iwm/__init__.py (仅内部装配)
  --- cost_ledger 被谁 import ---        core.py:63 (只做成本统计)
  --- vitals_ledger 被谁 import ---      harness/runtime_wiring.py (诊断)

★ 四个 ledger **没有共同的键**, 也没有互相引用:
  · DecisionProvenance 的键: decision_id (capacity=200 的内存环)
  · TransitionLedger 的键:   organ + action (无 id)
  · CostLedger 的键:         无 (只有累计值)
  · CausalLink 的键:          experience_id + source_traces[]
```

### 2.2 ★ 链断裂的代码级证据

```python
# foundation/schema.py 原文
class CausalLink(BaseModel):
    """Causal chain for experience provenance."""
    experience_id: str
    source_traces: list[str] = Field(default_factory=list)   # ← 本该是 trace.id 列表
    distilled_at: datetime = ...
    verified_by: Optional[str] = None
    applied_to: list[dict] = ...
    freshness_eta: float = 1.0
```

```text
★ BehaviorTrace **没有 decision_id / chain_id 字段** (实测: 三个都 ✗ 无)

★ 于是链在这里断了:
   DecisionProvenance 产出 decision_id (core.py:538 result["decision"]["provenance_id"])
        ↓  ★ 没有任何地方把这个 id 写进 BehaviorTrace
   BehaviorTrace 产出 trace.id
        ↓  CausalLink.source_traces 填的是 proxy_record.id (mnemosyne/core.py:212)
   CausalLink 产出 experience_id
        ↓
   ★ 四个环节, 三处断裂 —— 无法回答"这个经验是由哪个决策产生的"

★ CausalLink 全仓使用点 (宽口径 grep):
   schema.py (定义) / store.py (读写) / foundation/__init__.py (导出)
   mnemosyne/core.py:212 (唯一写入点)
   ★ 读取点: store.get_causal_link() —— 但谁调用它? grep 结果: 0 处
   ⇒ CausalLink 写了但**没人读**。
```

### 2.3 ★ 母巢的反面：总线是接线的，但链也没贯通

```text
★ 更正: 我前一轮说"母巢 subscribe/publish 0 处"是**错的** (grep 太窄)。
  宽口径实测 —— 母巢 EventBus **确实接线了**:

  cns/nexus.py:24        self.bus = EventBus()
  cns/nexus.py:167,175   self.bus.publish_sync(PipelineEvent(...))
  agent_core/loop.py:1259  self._cns_orch.subscribe(_bus)
  agent_core/loop.py:1264  self.cerebral_cortex.subscribe(self.nexus.bus)
  agent_core/loop.py:3435-3449  _bus.publish_sync(PipelineEvent(...))  ×4
  lifecycle/cerebral_cortex.py:112  订阅 EventBus

★ 但 chain_id 仍是断的 (这印证了原则 11 的判断):
  PipelineEvent.chain_id 有 default_factory=uuid4() ⇒ **不传就自动生成新 uuid**
  ⇒ 每次 publish 若不显式传 chain_id, 就产生一个新的孤立链 —— 链自动断裂。
  ★ 这正是原则 11 说的"有字段但 7 处全不传"。
```

---

## 三、★ 裁决：不要总线，要"一条链"（三种形态的对比）

```text
三个候选:

甲 · 事件总线 (pub/sub)
   · 母巢的形态: EventBus + PipelineEvent{pipeline, data, chain_id}
   · 优点: 解耦器官, 支持多订阅者
   · ★ 缺点 (DWC 语境): 
     ① 与"世界模型驱动"重复 —— 总线的 publish 会被误当成"驱动"
     ② chain_id 靠调用方传 ⇒ 漏传即断链 (母巢实测)
     ③ 订阅关系隐式 ⇒ 无法静态检查"谁被通知了"
     ④ DWC 是单进程单主循环, 没有多订阅者的真实需求

乙 · 分散 ledger (ARSI 的形态)
   · 四个独立 ledger, 各记各的
   · 优点: 每个 ledger 职责单一, 易实现
   · ★ 缺点: **没有共同的键** ⇒ 链断 (ARSI 实测三处断裂)

丙 · ★ 单一因果链 (DWC 采用)
   · 一条链贯穿: 决策 → 行动 → 痕迹 → 经验 → 变更
   · 每个环节的 id **强制**进入下一个环节的记录
   · ★ 不是 pub/sub, 是**显式传递 + 可查表**
```

**★ 裁决：丙。理由（三条，都有实测支撑）**

```text
理由 1 · 用户是对的: 驱动时间是世界模型, 不是总线
  ⇒ 总线的"驱动"职责在 DWC 里是**空的** (世界模型已占)。
     留着它会诱使人把 publish 当驱动 ⇒ 重犯母巢"predict → 直接 run"的错。

理由 2 · ARSI 用 ledger 而非总线, 但链断了
  ⇒ DWC 要的不是"更多 ledger", 是"ledger 之间有共同的键"。

理由 3 · 原则 11 已经定了方向:
  "① chain_id 必须作为事件信封字段被传递 (不许只留字段不用)
   ② 链上下文用显式 chain_id 查表, 不用'栈顶'隐式取"
  ⇒ ★ 原则 11 说的"信封"不必是总线信封 ——
     它可以就是**记录本身的一个字段**。这是本轮的落地。
```

---

## 四、★ DWC 的因果链形态（定稿）

### 4.1 一条链，五个环节，四个 id

```text
┌────────────────────────────────────────────────────────────────────┐
│  单一因果链 causal_chain/                                          │
│                                                                    │
│  ① 决策  decision_id    世界模型/LLM/启发式 选了什么                │
│        ↓ ★ decision_id 必须写进 ②                                 │
│  ② 行动  turn_id        这次任务尝试 (含 decision_id)               │
│        ↓ ★ turn_id 必须写进 ③                                     │
│  ③ 痕迹  trace_id       一次动作的完整记录 (含 turn_id + task_id)   │
│        ↓ ★ trace_id 必须写进 ④                                    │
│  ④ 经验  experience_id  蒸馏产物 (含 source_trace_ids[])           │
│        ↓ ★ experience_id 必须写进 ⑤                               │
│  ⑤ 变更  change_id      进化落地的改动 (含 based_on_experience_ids[])│
│                                                                    │
│  ★ 五个环节共用一个 chain_id (贯穿始终, 由 ① 生成, 后续继承)         │
└────────────────────────────────────────────────────────────────────┘
```

### 4.2 ★ 与 ARSI 的关键差别：字段是**强制**的，不是可选的

```text
★ ARSI 的病: BehaviorTrace 无 decision_id 字段 ⇒ 断链无法修复。
  CausalLink.source_traces 填的是 proxy_record.id, 不是 trace.id ⇒ 语义漂移。

DWC 的修法: 每个环节的记录**必须**含上游 id, 且判据可机械检查:

  Turn.decision_id         必填
  Trace.turn_id            必填
  Experience.source_trace_ids[]  非空
  Change.based_on_experience_ids[] 非空

★ 判据 (C1): 每个 id 字段的**写入点**必须存在, 且**读取点**必须存在
  —— ARSI 的 CausalLink 写入点 1 个, 读取点 0 个 ⇒ 违规。
```

### 4.3 ★ 与"世界模型驱动"的接口（回答用户的关切）

```text
★ 明确边界: 因果链**只记录, 不驱动**。

  世界模型 → 决策 → (写 decision_id) → 执行 → (写 trace_id) → ...
       ↑ 驱动                                                ↓ 只记录
       └────────── 链上的记录被 evolver 消化 ←────────────────┘

★ 判据 (C2): causal_chain/ 里不得有任何"触发下一轮"的调用。
  它只提供: append(记录) / get(chain_id) / trace_back(id)
  ★ 反向: 世界模型的 legal_actions() 可以**读**链 (作为难度估计的输入),
    但链不许**写**世界模型的状态。

★ 这条边界一划, 就避免了"总线式隐式驱动"的老路:
  母巢的 publish → 中枢按 DAG 触发下游, 就是隐式驱动。
```

### 4.4 ★ 与记忆七管的接口

```text
★ 因果链不是独立的存储, 它是**跨七管的连接件**:

  remember 摄入 → 写 trace_id + turn_id
  learn 蒸馏    → 写 experience_id + source_trace_ids[]
  evolve 落地   → 写 change_id + based_on_experience_ids[]
  maintain 巩固 → 读链, 检查"每条经验是否有来源"

★ 判据 (C3): 七管的每个写入动作, 必须带上链上的 id。
  依据: DWC 记忆核心 "没有失败定位的痕迹不算合格痕迹" ——
        同理, 没有链 id 的记忆不算合格记忆。
```

### 4.5 ★ 修 ARSI 的"写了没人读"

```text
★ ARSI 实测: CausalLink 写入点 1 个, get_causal_link() 调用点 0 个。

DWC 判据 (C4): 每个链环节必须有**至少一个消费者**。
  · decision_id  → 消费者: iwm 的 provenance 回放 (Q5)
  · turn_id      → 消费者: 失败签名诊断 (D5 的 c,q,m)
  · trace_id     → 消费者: learn 蒸馏
  · experience_id → 消费者: evolver 提案
  · change_id    → 消费者: 回滚器 (inverse_op)

★ 判据: grep 每个 id 字段的读取点, 结果必须 > 0。
  依据: 母巢记忆核心的教训 —— "机制必须接线 (零引用 = 不许存在)"
```

### 4.6 停止规则与链的关系

```text
★ 2603.06333 §2.7 的五条停止规则里, 有三条需要链:
  ① 连续三次迭代质量变化 < 0.01  → 需要链上的 quality 序列
  ② 回归风险 R_c^adj > τ_R       → 需要链上的历史峰值 𝒬_max
  ⑤ GDI > 校准阈值               → 需要链上的基线快照

⇒ ★ 链不只是"审计", 它是停止规则的**数据来源**。
  没有链, 三条停止规则无法实现。
```

---

## 五、可机械检查的判据（gate.py 候选，5 条）

```text
C1 · 链上 id 写入点与读取点都存在
   每个 id 字段 (decision_id/turn_id/trace_id/experience_id/change_id):
   写入点 > 0 且 读取点 > 0
   依据: ARSI CausalLink 写入 1 / 读取 0

C2 · 因果链不驱动
   causal_chain/ 不得有任何触发下一轮的调用
   判据: 该目录不得 import 世界模型/actor 的写接口
   依据: 用户关切 —— 驱动时间是世界模型

C3 · 七管写入必带链 id
   remember/learn/evolve/maintain 的写入点必须含链上 id
   依据: DWC 记忆核心 "没有失败定位的痕迹不算合格痕迹"

C4 · 每个链环节有消费者
   五个 id 各自的读取点 > 0
   依据: 母巢 "零引用 = 不许存在"

C5 · chain_id 贯穿不新生成
   五个环节共用一个 chain_id, 不得中途 uuid4()
   判据: 除 ① 决策处外, 不得出现 uuid4() 生成 chain_id
   依据: 母巢 PipelineEvent.chain_id default_factory=uuid4() ⇒ 漏传即断链
```

---

## 六、诚实边界

```text
① ★ 更正我前一轮的一处错误: 我说"母巢 EventBus subscribe/publish 0 处"是**错的**。
   宽口径 grep 后: 母巢 EventBus **确实接线** (nexus.py:24/167/175,
   loop.py:1259/1264/3435-3449, cerebral_cortex.py:112)。
   当时 grep 用了窄模式 (`\.subscribe(`) 漏了 `self.bus.publish_sync` 等形态。
   ★ 教训: 否定性结论必须用宽口径复核 (这条我记过, 这次又犯了)。

② ★ 已逐行核实: core.py 与 dream_rsi_params.py 的 publish 字样都是
   "unpublished" 的假阳性。宽口径复核 (7 种模式) 命中 0 处。
   ⇒ "ARSI 零总线" 结论**确认** (不再是未验证项)。

③ "链在 ARSI 里断了三处" 是静态分析:
   (a) BehaviorTrace 无 decision_id 字段 (实测三字段全 ✗)
   (b) CausalLink.source_traces 填 proxy_record.id (mnemosyne/core.py:212 原文)
   (c) get_causal_link() 调用点 0 处 (宽口径 grep)
   ★ 未验证: 若有动态读取 (getattr / 反射) 会漏。

④ 五个环节 (决策→行动→痕迹→经验→变更) 是我的设计 ——
   论文没有给这条链。★ 但每一条边 (哪个 id 必须进哪个记录)
   都有实测依据 (ARSI 断在哪, DWC 就在哪补)。

⑤ ★ 未定: 链的**存储形态** (追加日志? 表? 内存环?)。
   ARSI 的 DecisionProvenance 是 capacity=200 的内存环 ⇒ 满了会覆盖。
   DWC 该多大 / 是否落盘 —— 留给下一轮。
```

---

## 附：存证

```text
ARSI 源码: src/arsi/iwm/{provenance.py, transition_ledger.py, vitals_ledger.py}
           src/arsi/foundation/{cost_ledger.py, schema.py:133 CausalLink}
           src/arsi/mnemosyne/core.py:212 (唯一 CausalLink 写入点)
           src/arsi/core.py:390 (BehaviorTrace 构造, 无 decision_id)
           src/arsi/core.py:538/617/626 (provenance_id 只在 result dict 里)
           ★ grep "event_bus|EventBus" src/ → 0 个文件
母巢源码:  cns/event_bus.py (40 行, PipelineEvent.chain_id default_factory=uuid4)
           cns/nexus.py:24/167/175 · agent_core/loop.py:1259/1264/3435-3449
           lifecycle/cerebral_cortex.py:112
论文报告:  docs/papers/2603.06333.md §2.7 (五条停止规则 —— 三条需要链)
前置文档:  ARCHITECTURE.md §2.3 (三层驱动) / 原则 10 / 原则 11
```
