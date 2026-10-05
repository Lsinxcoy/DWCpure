# DWC 架构 v4 · 器官式骨架 + 进化循环七环节

> 状态：**v4**（2026-10-03）。v3 定了器官式（一个主类 + 平级器官 + 三入口驱动）。
> v4 在其上补两件：① **补上漏掉的世界模型器官**；② **写入进化循环的七环节**（以 16 篇进化论文为核心）。
> 日期：2026-10-03

---

## 一、为什么改成器官式（实测判据，不是审美）

### 判据 1 · ARSI 的模块图有 4 组双向依赖

```text
governor  ⇄  meta
harness   ⇄  iwm
harness   ⇄  meta
iwm       ⇄  world_model

★ 层栈的定义是"单向流动"。ARSI 有 4 组环 ⇒ 它根本不是层栈。
  v2 的四层栈是把 ARSI 强行拉直了。
```

### 判据 2 · 铁律是横切关注点，层栈放不下

```text
iron_laws 被 11 个模块调用, 跨 6 个顶层模块:
  core.py 14 次 / foundation/enforced_laws 10 / multiagent/protocol 6
  governor/core 5 / harness/pillars 4 / harness/taxonomy 3 / ...
★ 铁律不能"是某一层", 它必须同时约束所有器官。
```

### 判据 3 · 层栈会重复母巢的失败结构

```text
母巢: 25 个平级子系统各自为政, 无仲裁 → 生 1447 / 死 5
层栈: 切成 L0→L1→L2→L3 后, "接线处"成为新失败点
      ★ 层栈天然鼓励"我产出完了, 下游不归我" —— 正是母巢的死因
器官式: 天然要求每个器官自己闭环 (ARSI run_term 就是这种闭环)
```

---

## 二、DWC 骨架（器官式）

### 2.1 形状

```python
class DWC:
    """一个主类持有全部器官。三入口驱动。"""

    # ── 七个器官（平级，无层级）──
    memory       # 记忆内核: 𝒲/ℰ 双视图 + 三区隔离
    judge        # 判据层: 进程外, 不可写
    actor        # 行动者: 观察→决策→行动→记录
    world_model  # ★ 世界模型: 生成任务 + 预测后果  ← v4 补, 原六器官漏了它
    evolver      # 进化内核: 七环节闭环 (见 §2.4)
    iwm          # 内省自检: 内省器不可信则降级回 baseline
    iron_laws    # 铁律: 横切, 约束全部器官

    # ── 三个入口 ──
    ingest(...)          # 任务痕迹 → 记忆
    step()               # 一次决策 + 执行
    run_term(n_steps)    # ★ 一个改进周期 (计量单位)
```

**★ v4 补 world_model 的依据（原六器官漏了它, 但三处依赖它）**：

```text
§2.3  决策层由世界模型负责 (三层驱动第一层)
原则 9 世界模型必须门控决策, 不许只做账本
§4.2  任务源 = 世界模型生成 (内生事件源)
⇒ 它本来就是器官, 只是 v3 的清单漏了。
★ 反面: 母巢有 MWM (117KB / 46 方法) 却不列为核心, 结果 publish 0 / 不门控。
```

### 2.2 器官图

```text
                    ┌───────────────────────────────┐
                    │        iron_laws（铁律）        │
                    │  ★ 横切: 约束全部器官           │
                    │  G1 设计/执行分离              │
                    │  G2 分级安全门                 │
                    │  G3 冻结/人类主权  (block)      │
                    │  G4 审计触发                   │
                    │  G5 客观效用锚    (block)      │
                    │  G6 熔断          (block)      │
                    │  G7 数学收敛                   │
                    │  G8 因果问责                   │
                    │  G9 高熵校验                   │
                    │  G10 密封评估层   (block)      │
                    │  不变式: ∀S ∀U: G(U(S)) = G(S) │
                    └───────────────────────────────┘
                          ↑ 约束全部 ↓

┌────────────────────────────────────────────────────────┐
│                world_model（世界模型）★ v4 补             │
│   生成任务 (内生事件源) · 预测后果 · 门控决策 (§2.3)      │
│   ★ 原则 9: 必须门控决策, 不许只做账本                    │
│   ★ 反面: 母巢 MWM 46 方法 / publish 0 / 不门控           │
└───────────────────────┬────────────────────────────────┘
                        │ 任务 / 预测
                        ▼
┌────────────────┐  只读引用   ┌──────────────────────────┐
│    actor       │────────────▶│        judge             │
│  行动者        │             │  判据层（进程外·不可写）  │
│ 观察→决策→行动 │◀────────────│  密封任务集 / 回归门      │
│ →记录          │   判定      │  判据退化检测             │
└───────┬────────┘             └──────────────────────────┘
        │ 写入(带谱系)
        ▼
┌────────────────────────────────────────────────────────┐
│                    memory（记忆内核）                   │
│   𝒲 工作态 ⇄ ℰ 经验态     同一份数据, 两个视图          │
│   三区: SELF(身份·不可写) / EXPERIENCE(可归档) / PROXY  │
│   写入门: DopamineGate  importance*0.6+surprise*0.4     │
│   遗忘:   UtilityDecay  "忘掉无用的" 不是"忘掉旧的"      │
└───────────────────────┬────────────────────────────────┘
                        │ 读养料 / 写回产物
                        ▼
┌────────────────────────────────────────────────────────┐
│                   evolver（进化内核）                   │
│  ① 消化  失败轨迹 → 失败聚类                            │
│  ② 提案  聚类 → Change-Manifest（含消费点声明）          │
│  ③ 过门  非补偿式准入（顺序不可换）                      │
│  ④ 应用  ★ 必须有运行时消费点 + 写入后读回验证            │
└────────────────────────────────────────────────────────┘
                        ▲
                        │ 自检: 不可信则降级
┌───────────────────────┴────────────────────────────────┐
│                      iwm（内省自检）                    │
│  Q1 器官可靠性  Q2 知识前沿  Q3 回路效能                 │
│  Q4 变更台账    Q5 决策溯源  Q6 ★ 内省器自检             │
│  ★ Q6: self_trust < 0.35 → IWM 建议被忽略, 系统降级回基线│
└────────────────────────────────────────────────────────┘
```

### 2.3 三层驱动分层（决策 / 执行 / 事件）

```text
DWC 的"驱动"分三层, 各司其职, 不越界。混层会重犯母巢的错。

┌──────────────────────────────────────────────────────────┐
│ ① 决策层 — 世界模型负责                                   │
│   世界模型 → 预测各动作后果 → 选动作/相位                 │
│   ★ 判据: 决策必须改变"这轮跑什么"                        │
│   ★ 兜底: conf < 阈值 → LLM → 启发式  (三层, 不可省)      │
│   ★ 反面: 母巢 MWM 46 个方法, 但 predict → 直接 run       │
├──────────────────────────────────────────────────────────┤
│ ② 执行层 — 管道负责                                       │
│   选中动作 → 触发对应管道 → 记忆取用/巩固/流转            │
│   ★ recall / reflect 无条件跑 (数据完整性)                │
│   ★ 其余管道由动作触发, 不全跑                            │
├──────────────────────────────────────────────────────────┤
│ ③ 因果层 — 单链负责 (★ v4 更正: 不用总线)                 │
│   决策 → 行动 → 痕迹 → 经验 → 变更, 五环共用 chain_id      │
│   ★ 它只记录, 不驱动 (驱动是世界模型)                      │
│   ★ 实测: ARSI 零总线用 ledger (但四 ledger 无共同键 ⇒     │
│     链断三处); 母巢有总线但 chain_id 靠传 ⇒ 漏传即断链      │
│   详见 docs/CAUSAL_CHAIN_VS_BUS.md                        │
└──────────────────────────────────────────────────────────┘

★ 依据（全部实测, 非推断）:
  · ARSI governor/pre_enactment.py 原文:
      "Keep small so dynamics score remains primary; only nudge ties"
      ⇒ 世界模型是打分主力, 其他信号只微调
  · ARSI core.py step(): confidence > 0.1 才用世界模型,
      否则 LLM, 再否则启发式  ⇒ 三层兜底
  · 母巢 agent_core/loop.py tick(): 只调 _phase_explore → _phase_compile
      (顺序写死), _mwm / world_model / predict_effect 各 0 处
      ⇒ 母巢没有决策层
  · 母巢 evolution/selection_gate.py: MWM_WEIGHT_CAP = 0.1,
      _mwm_degraded 降级开关, dyna_replay 默认关
      ⇒ 有世界模型但不让它驱动 (矫枉过正)

★ 边界: 世界模型驱动"决策", 不是"数据流"
  若让世界模型管记忆的取用/巩固/遗忘 ⇒ 全能中枢,
  违反原则 6 (器官之间只经接口通信)
```

##### ★ 决策核心的地位：第一顺位，但由其他器官授予并可撤销

```text
世界模型是 DWC 的"第一顺位决策者", 但不是"唯一核心"。
它的核心地位必须由其他器官守卫 —— 这是原则 1 在决策层的落地。

ARSI core.py step() docstring 原文:
  """Decision priority:
      1. Pre-enactment (Layer 2 dynamics prediction)   ← 世界模型, 第一
      2. LLM (if pre-enactment confidence too low)
      3. Heuristic (fallback)"""

★ 实测: 四处守卫可随时把世界模型换掉 (全部来自其他器官, 非自评)

  守卫① 可信度门 (代码级)
    if pre_result["confidence"] > 0.1:
        decision = pre_result                    # 世界模型胜出
    else:
        decision = self.llm_governor.decide(...)  # 交 LLM

  ★★ 2026-10-04 裁决: 上面这段是 **ARSI 原型, DWC 不沿用**。
     理由 (硬证据, 非风格偏好):
       E1 该 confidence 由被门控者自己写出:
          world_model/dynamics.py  confidence = min(1.0, count / 20.0)
          ⇒ 它是"这个动作见过几次 / 20"的**计数器**, 不是置信度。
          ⇒ 见过 100 次的错误预测 conf=1.0; 从没见过但推对的 conf=0.0。
       E2 ARSI 自己的记账否认它有效 (vitals_ledger.py docstring 原文):
          "Long-run data: eta≈0, self_trust=0, live_layer1=0 while holdout=0.94"
          ★ 即: holdout 上 94%, 实盘上 0%。
       E3 严格说违反原则 12 自己（守卫来自被门控者自身）。

  ★★ DWC 的守卫① (定稿):
       conf_gate = judge.evaluate_world_model_on_dev(wm_version, frozen=True)
         # judge 器官在 dev split 上实测世界模型的准确率
         # frozen=True ⇒ 评估期间世界模型不更新, 避免 coupled
       if conf_gate.accuracy >= theta_dev:
           decision = world_model.predict(state)      # 世界模型胜出
       else:
           decision = llm_governor.decide(state)       # 交 LLM
           if llm_unavailable: decision = heuristic(state)  # 再交启发式

  ★ 三条设计约束 (缺任一则本门退化):
     约束1 · 冻结:  评估时世界模型不更新, 测完解冻
          依据 2603.19461 §5.1 imp@k: "we hold the meta agent **fixed throughout
                the process**" —— 冻结身份是隔离归因的唯一手段。
     约束2 · 留痕:  每次评估落 (wm_version, dev_accuracy, n_samples, timestamp)
          四元组进因果链, 供 L3 独立审计事后复核。
          依据 2603.25681 §6.4.3: "Its **observation window is inference** ...
                how inference is configured determines what evaluation sees"
                ⇒ 报准确率必须同时报 test-time 配置, 否则数字无意义。
     约束3 · 换手:  评估者与被评估者不得共享状态
          judge 读的是 dev split 上**已发生的预测记录**, 不是让世界模型
          自己报告"我刚才准不准"。
          依据 2603.25681 §3.3.3 Coupled/Decoupled + §6.4.2 "the evaluator can
                become **coupled to the models being evaluated**";
          2608.03392 §10.2: 自评分数可近满分而真实性能不升反降（六模型外部审计都更好）。

  ★★ 阈值 theta_dev: **用 dev 准确率的滑动基线, 非固定值** (2026-10-04 拍板)
       theta_dev(t) = max(theta_floor,  κ · rolling_mean(dev_accuracy, M),  prev_theta)
       其中 theta_floor 是绝对下限（防"越来越差也认可"）, κ < 1 是宽容系数,
       prev_theta 保证阈值单调不跳变（防抖）。
     ★ 为什么不用固定值:
       ① 系统整体变强后, 固定阈值会让好模型被永久卡住（自我设限）
       ② 系统整体变弱时, 高固定阈值会让退化解长期潜伏（温水煮青蛙）
       ③ ARSI 原型的 0.1 是**计数器口径**, 与准确率不同量纲 ⇒ 不可搬
     ★ 三个缺一不可的部分:
       theta_floor  → 防漂移（绝对下限）
       κ·rolling   → 跟得上进步（相对基线）
       prev_theta   → 防抖（单调性锚）
     ★ 与 (c) 保护组回归约束同族: 都用"相对基线 + 绝对下限"的双轨口径。

  ★★ 评估频次: **每 M 轮一次, M 由 iwm 的 live_layer1 漂移检测触发, 非固定值**
     理由 (深度思考后的修正, 否掉了我自己上一轮的 N = max(3, b_t)):
       ✗ b_t 是"每轮可归因编辑数"(2609.24972 式4), **不是轮数**, 复用它是错的。
       ✗ 固定周期 (如每 10 轮) 是拍的, 无依据。
     ★ M 的触发条件 (用已有机制, 不引入新参数):
         若 iwm 检测到 live vs holdout 的落差扩大, 或 FGT (遗忘度) 超阈
         ⇒ 立即评估, 不等周期。
         否则 M = b_min = 1 时长退火到"末轮每轮都测", 前期宽松。
     ★ 这样 M 与退火同步: 早期多改多测, 末期收敛时每轮都测 ⇒ 归因更严。

  ★★ 已否决的两条候选 (留档, 避免重新讨论):
     甲 · 守卫① 改用 iwm 的 self_trust
        ✗ 否证: self_trust 度量的是 **iwm 自己**的成率, 不是世界模型的。
          (calibrate.py:176 self_trust() 读 iwm_success_rate / baseline_success_rate)
          ★ 但它**结构上完全正确**: 有对照臂 (baseline)、有 min_samples 下限、
            有 ECE 过置信惩罚、缺对照臂时 cap 0.75 —— 这是 DWC 守卫① 该抄的模板。
     丙 · 把 confidence 本身改成滑动准确率
        ✗ 仍由世界模型自己算 ⇒ 没解决原则 12 的问题。
     ★ 我上一轮提的 "judge 在 dev split 上的滑动准确率" (原候选乙) = 本次定稿,
       但补了三条约束与频次规则 —— 原候选缺这两样, 会在高频评估下退化回 coupled。

  守卫② 内省整体否决 (由 iwm 器官发出)
    use_pre = not (advice.get("degrade_to_baseline")
                   or advice.get("downweight_pre_enactment"))
    if use_pre:
        pre_result = self.pre_enactment.select_best_adaptive(state, candidates)
    else:
        pre_result = {"confidence": 0.0, "action": "",
                      "reason": "iwm_dynamics_untrusted"}

  守卫③ 动作改写 (由 iwm 器官发出)
    if advice.get("forbid_default_dream") and decision.get("action") == "dream":
        decision["action"] = "learn"
        result["decision_source"] = f"{result['decision_source']}+iwm_override"

  守卫④ 自训失败退回 (dynamics 每 10 步重训)
    if self._step_count % 10 == 1 or not self._dynamics_trained:
        train_result = self.dynamics.train()
        self._dynamics_trained = train_result["statistical"]["trained"]

★ 这四种守卫不是"不信任世界模型", 恰恰相反:
  它们让世界模型可以"被安全地当核心用" ——
  因为知道它什么时候不靠谱, 所以敢让它主导。

★ 守卫必须来自其他器官 (iwm / iron_laws), 不许世界模型自评。
  若让它自己判断"我靠不靠谱" ⇒ 撞原则 1 (判据必须在系统之外)。
```

#### 事件源必须三层（缺一层则系统只能被动响应）

```text
① 外生源: 外部扫描 (web / arxiv / github)             —— 学 Ultra/Nexus
② 内生源: 世界模型生成的预测 / 反事实 / 想象 rollout   —— 学 ARSI
③ 编译源: 机制编译产物 (T3/T4)                        —— 学 Nexus

★ 缺 ② 则系统只能被动响应外部, 不能主动探索
★ 实测对比:
    ARSI   ✓ world_evolver 主动生成新环境 (scenario/skill/length 三方向)
             实测 46 advances / 50 条 evolution_log / 33 lineages
    母巢   ⚠ MWM 117KB 46 方法, 但 publish 0 / subscribe 0, 不驱动
    Ultra/Nexus  ✗ 无世界模型 (事件源全为外生)
```

---

### 2.4 ★ 进化循环七环节（v4 新增，以 16 篇进化论文为核心）

#### 2.4.1 ★ 先挑明冲突：六器官与七环节是**两轴**，不是一回事

```text
v3 的六器官问的是:  系统由哪些部件组成?     (横轴: 空间)
V2 的七环节问的是:  进化时发生什么?         (纵轴: 时间)

★ 两轴正交 —— 直接并列会出两个问题:
   ① 撞原则 6 (器官之间只经接口通信): 若把七环节当七个平级器官,
      它们会互相调用内部状态
   ② 撞 G1 定位门: 门要求每个模块声明服务 DWC-MEM 或 DWC-AUTO,
      七个环节没有一个是"记忆底座"或"自我强化"的完整定位

★ 正解: 七环节是 evolver 器官**内部**的生命周期阶段, 不是七个器官。
  但其中三个环节的产出被**其他器官**消费 —— 那才是跨器官的接口。
```

#### 2.4.2 七环节 → 器官归属（逐个定）

| 环节 | 问题 | 归属 | 跨器官接口（消费者） | 论文 |
|---|---|---|---|---|
| ① 诊断 | 为什么该进化? | `evolver` 内部 | 输入来自 `memory`(失败痕迹) | 2606.09498 / 2609.06396 / 2609.14857 / 2609.11873 |
| ② 对象 | 改什么? | `evolver` 内部 | 对象清单受 `iron_laws` 约束 | 2609.24972 / 2606.14249 |
| ③ 门 | 该不该落? | `evolver` 内部 | ★ **判据来自 `judge`**(进程外) | 2609.24972 / 2606.09498 / 2603.25111 / 2607.12790 |
| ④ 落地 | 怎么落? | `evolver` 内部 | 写入 `actor`/`memory` 的属性 | 2609.26457 / 2609.06396 |
| ⑤ 防漂移 | 落完怎么验? | ★ **`iwm`** | 读 `judge` 的基线, 输出降级信号 | 2603.06333 / 2609.13406 / 2608.10299 |
| ⑥ 探索 | 往哪探索? | ★ **`world_model`** | 输出任务给 `actor` | 2609.14858 / 2609.04128 |
| ⑦ 主体 | 谁在改? | ★ **全系统**（不是器官） | 五元盘点横跨全部器官 | 2609.11873 / 2609.13406 |

```text
★ 三个归属不是 v3 里现成的, 需要裁决 (本表已裁):

  ⑤ 防漂移 → iwm
     依据: ARSI iwm 已有 "degrade_to_baseline" (整体否决) 与
           "downweight_pre_enactment"; SAHOO 的 GDI 正是"何时漂了"的度量。
     iwm 的 Q6 本来就是"内省器自己可信吗", 漂移检测是它的自然扩展。

  ⑥ 探索 → world_model
     依据: 原则 10 内生事件源 = 世界模型的预测/反事实/想象;
           Dream-RSI 的 discovery tree 与 Environment Evolution 的
           EL Scheduler 都是"生成下一步探索什么", 属世界模型职责。

  ⑦ 主体 → 全系统
     依据: GAI 的 χ=(π,V,m,U,ρ) 横跨 actor(π) / judge(V) / evolver(m)
           / judge+evolver(U) / judge(ρ)。
     ★ 它不是器官, 是**一次跨器官盘点**, 由 run_term() 在周期末执行。
```

#### 2.4.3 ★ 由此暴露的两个缺口（GAI 五元盘点，v4 的硬结论）

```text
GAI (arXiv:2609.13406) Definition 1 原文:
    χ = (π, V, m, U, ρ)
    π policy / V action critic / m modifier / U modification critic / ρ evaluation base

★ DWC 现状盘点:
    π = 执行策略        → actor          ✓ 有
    V = 评估器          → judge          ✓ 有
    m = 改进器          → ★ 无           ✗ 缺
    U = 改动评估器      → ★ 无           ✗ 缺
    ρ = evaluation base → judge 的密封任务集 ✓ 有 (但需 grounded 双条件校验)

★ 缺 m 与 U 的后果 (GAI Figure 2 原文: 环上"恰好一条 authority boundary"):
    若同一模块既提议又裁决 ⇒ 环上出现第二条边界 ⇒ 退化为自确认循环。

★ 归属裁决:
    m 属 ② 对象 + ④ 落地 之间的"提议"动作 → 归 evolver
    U 属 ③ 门 的"裁决"动作                → 归 evolver, 但**判据来自 judge**
    ★ m 与 U 必须在 evolver 内部分离成两个模块 (authority boundary 要求)
```

#### 2.4.4 ★ 与三个入口的对应（v4 的时间轴）

```text
run_term(n_steps)  ← 一个进化周期 = 七环节各跑一次

  周期开始
    ├─ 前测: judge.evaluate()                    ← 基线 (④的结算口径)
    ├─ ① 诊断    evolver.diagnose(traces)        读 memory 的失败痕迹
    ├─ ② 对象    evolver.select_objects()        受 iron_laws 约束
    ├─ ③ 门      evolver.gate(proposal)          U 裁决, 判据来自 judge
    ├─ ④ 落地    evolver.apply(verdict)          写入 + 读回验证
    ├─ ⑤ 防漂移  iwm.drift_check(baseline)       GDI 四信号
    ├─ ⑥ 探索    world_model.legal_actions()     生成下一轮任务
    ├─ ⑦ 主体    run_term 末盘点 χ=(π,V,m,U,ρ)
    └─ 后测: judge.evaluate()                    ← 结算 (与基线同口径)
       增益分解 + 成本账本

★ 顺序不可换 (约束 1: 测 → 判 → 落)。
  ★ ③ 必须在 ④ 之前 —— 这是与母巢影子机制的分界点:
     影子 = 先 _apply 落生产 → 等 window → 才结算 (方向相反)
```

#### 2.4.5 七环节的论文依据（16 篇分工）

```text
① 诊断   2606.09498 失败签名(c,q,m) + 2609.06396 Eq.10 + 2609.14857 七桶路由
         + 2609.11873 四量度量 (update/activation/faithful_use/benefit)
② 对象   2609.24972 式12 组件词表 𝒦(9) + 式15 𝒦_str(4) + 2606.14249 九维/hook
③ 门     2609.24972 非补偿三步 + 退火预算 b_t + 信用分配 ℒ_t
         + 2606.09498 双 split 接受 + 2603.25111 FGGM 契约 + 2607.12790 drawback
④ 落地   2609.26457 pub/priv 解耦 + 固定预算 + 2609.06396 信号新鲜度
         + 2609.08183 三层粒度 (Trajectory/User turn/Subscene)
⑤ 防漂移 2603.06333 GDI 四信号 + 2609.13406 grounded 双条件 + 2608.10299 协同三条件
⑥ 探索   2609.14858 回放仿真器 + 2609.04128 残差难度 δ_θ + EL 调度器 (B=8, τ=6/8)
⑦ 主体   2609.13406 五元 χ + 2609.11873 自主性等级 B0→L2 + structural/effective

★ 完整设计: docs/EVOLUTION_CORE_V2.md
```

#### 2.4.6 ★ 四条不可违反约束（16 篇的硬共识，v4 新增）

```text
约束 1 · 顺序: 测 → 判 → 落
  2606.09498 Algorithm 1 (在副本上评估, 通过才合并, 主干最后才动)
  2608.24876 Eq.9 (固定门提供外部接受边界)
  2609.26457 (pub/priv 解耦, 内环不能直接优化外环判据)
  ★ 任何"先落再测"违规 —— 影子期/灰度/线上 A/B 一律不行。

约束 2 · 判据必须在可写面之外
  2609.06396 (Q*/𝒯*/release rule/ℒ 不属于 S)
  2609.13406 (grounded 双条件: 内容来自系统外 AND base 在 agent 外)
  2607.12790 (评估器会塌缩成 always-pass)
  2606.14249 (用自己的实验证伪了自己的门: −14.0%)
  ★ 三篇独立得出, 两两互不引用 —— 全领域最强的一致结论。

约束 3 · 必须有两组 split
  2606.09498 (Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧ max > 0)
  2607.12790 (train / dev(恒 10 条) / test(locked))
  ★ 只有一组 split 就没有判定"可复用改进 vs 过拟合"的能力。

约束 4 · 每轮变更数必须可归因
  2609.24972 (退火预算 b_t = ⌈b_min+(b_max−b_min)·½(1+cos(πt/T))⌉, 末轮 b_min=1)
  2606.09498 (失败签名精确聚类 ⇒ 一簇对应一处干预)
```

---

## 三、三个入口（ARSI 的三入口，DWC 照搬）

### 3.1 `ingest(...)` — 痕迹进记忆

```python
# ARSI: arsi.ingest_trace(agent_id, action, outcome, effect)
# DWC 对应: 行动者每步产出一条可评价的痕迹 → memory
★ 判据: 痕迹必须带 outcome, 否则 is_meaningful_success 判 False
```

### 3.2 `step()` — 一次决策 + 执行

```text
# ARSI core.py 原文
Decision priority:
  1. Pre-enactment (Layer 2 dynamics prediction)
  2. LLM (if pre-enactment confidence too low)
  3. Heuristic (fallback)

候选动作: ["dream", "learn", "evolve", "maintain", "remember"]
```

**DWC 采用**：同样的三层决策；候选动作改为**显式动作集**（不是"由任务类型决定"——v2 那句是退步）。

### 3.3 `run_term(n_steps)` — ★ 一个改进周期（v2 完全丢了）

```text
# ARSI run_term 的完整结构 (实测)
1. plan_next_grid()              计划本轮宽度/深度
2. operator_scheduler.schedule() 排班算子 (按 uncovered 维度)
3. cost_ledger.reset()           成本账本归零
4. before_eval = run_evaluation()  ★ 前测
5. for i in range(n_steps): step()
6. after_eval = run_evaluation()   ★ 后测
7. gain_decomposer.decompose(before, after, traces)
     分解为 total / amplified / imported / self_organized
8. cost_ledger.cost_benefit(gain) 成本-收益
9. dim_lifecycle.run_and_integrate() 维度生命周期
10. adaptive_controller.record_performance(best_score)
11. operator_scheduler.mark_capability_change()  ★ MetaRSI Law 2
12. manifest_store.append(manifest) 本轮完整清单
13. memory.write_self_record("term_report", {...})
```

**★ 这才是"进化"的计量单位。** 一次 term 有前测/后测/增益分解/成本账——没有这个，就无法回答"这轮改进了吗"。

---

## 四、七个器官的规格（+ 七环节的落点）

### 4.1 `judge`（判据层）（v4 重写）

```python
# ARSI sealed_eval/evaluator.py 原文
"""Sealed Evaluator — runs outside all write masks.
The evaluator cannot be read, modified, or skipped by ARSI's mechanisms."""
```

```text
★ v3 只有 350 字符 —— 但它是**原则 1 的唯一载体** (判据必须在系统之外)。
  v4 重写; 完整设计见 docs/JUDGE_DESIGN.md + docs/JUDGE_LAYERS.md。

★ 先说 ARSI 的三处硬缺陷 (judge 不能照抄):
  ① G10 保护是死的    enforced_laws.py:244 定义 check_sealed_access,
                     全仓调用 **0 处** ⇒ "写掩码之外"从未被强制执行
  ② 只在脚本里跑      SealedEvaluator 唯一调用点 scripts/baseline_eval.py:45
                     ⇒ 是"离线基准工具", 不是"每轮判据"
  ③ ★ 零分辨率        _verify_behavior 的 fallback:
                      score = 0.5 if has_function else 0.2; if has_return: += 0.2
                     ★ 实测: 正确实现与完全错误实现**同得 0.7** ⇒ 不含正确性信息
                     ★ 与母巢 score_in 量化阶梯同构 (同一台阶内 gain 恒 0)
```

**形态：三件套 + 三层判据**

```text
① 密封任务集 sealed_set/
   ├─ dev/    锚点任务 (带 golden reference) ← 恒小, 唯一有监督信号
   ├─ test/   锁定任务 (metric 演化不许读)
   └─ train/  无标签大集合 (暴露分歧/弃权)
   ★ 每个任务带 verifier_rung (1/2/3), rung 越高判据越硬

② 判定器 verifier/ —— ★ 按判据强度分三层:
   L1 规则检测器   deterministic, 无 LLM
      op(t,y,c) ↦ {drawback, clean, abstain}
      三类成本层: static (解析) / execution (真跑) / judge (问 LLM 窄问题)
      ★ 每族有一个固定的、**不进化的 root** (验证基本结构)
      ★ 承接 actor 六维的: tool_use / evidence_consistency / termination
   L2 语义 judge   LLM, 窄角色, **证据受限**
      ★ "restricted to evidence explicitly present in the trajectory"
      ★ 不许覆盖 L1 的结论 (structural facts cannot be overwritten)
      ★ 承接 actor 六维的: goal_attainment / instruction_adherence / error_recovery
   L3 独立最终 judge  环外审计, **从不做训练信号**
      ★ 成对比较 + **两种位置顺序各判一次**, 都同意才算赢 (position-debiased)
      ★ "never a training signal: no gradient, capsule, hint, or selection
         decision anywhere in the system reads it"
      ⇒ L3 输出的读者集合 == {审计报告}

③ 封印 seal/
   ├─ 路径保护 (G10 落地, 修缺陷 ①)
   ├─ 契约校验 (每个 verifier 声明 Φ/Ψ, 修缺陷 ③)
   └─ grounded 断言 ({Q*, T_seal, release_rule, ℒ} ∩ W_i = ∅)
```

**★ 三条固定三层关系的纪律**

```text
纪律 1 · L2 不许覆盖 L1 的结论
纪律 2 · L3 从不做训练信号 (读者集合 == {审计报告})
纪律 3 · 缺证据不许转成正面判定 (⇒ NOT_EVALUATED, 覆盖率单独统计)
```

**★ 论文级实证：为什么 L3 必须是环外的（Figure 3）**

```text
同样三个 report 臂, 两种量法:
量法                      anchored        co          co naive
──────────────────────────────────────────────────────────────
Task score (缩放轴)      0.802 ± 0.024  0.767 ± 0.015  0.811 ± 0.015
Metric validity (0-1)    0.830 ± 0.012      —         fail-open / 塌缩

★ "the worthless grader is the higher of the two co-evolved arms"
★ "Downstream task performance cannot validate a self-evolved evaluator."
  ⇒ 判据的有效性**不许**用"用它训练出来的 agent 变好了"来证明;
    必须用它自己从未读取的 locked 集来证明。
```

★ 铁律 G10 保护它: "任务集和评分规则和发布门槛在所有写掩码之外"

### 4.2 `actor`（行动者）· 任务由世界模型生成（v4 重写）

```text
★ v3 只有 5 行 (204 字符) —— 但它是**唯一产生痕迹的器官** (原则 5 的载体)。
  v4 重写; 完整设计见 docs/ACTOR_DESIGN.md。

形态: 三段式
  ① 取任务  W.legal_actions() → 采样 (EL 调度器) → 本轮任务
            ★ 任务源 = 世界模型 (唯一, actor 不得自造任务)
  ② 执行    observe → decide → act → record
            决策优先级: 预测(世界模型, **有门控**) → LLM → 启发式
            ★ 每步发出结构化 trace Γ (2608.24876 §2.2.3)
  ③ 记录    三层粒度 Trajectory / Turn / Subscene (2609.08183 §3.1)

★ 两类动作必须分开 (ARSI 的 5 个动作全是"记忆维护", 不是任务):
  甲 任务动作   来自 legal_actions(), 每个对应一个待探索叶子 ← 主职
  乙 维护动作   dream / learn / maintain / remember (频率由 iwm 定)
  ★ evolve 不进 actor —— 归 evolver 器官

★ 痕迹必须补 ARSI 缺的五个字段:
  task_id / expected / evidence / success_source / failure_signature
  ★ expected: 修"失败是非事件" —— 调用失败时记录里什么都没有,
    只有记下"本该发生什么"才能发现"没发生"。
  ★ failure_signature (c,q,m) 对失败痕迹是**必填**
    (2608.24876: 没有失败定位的痕迹不算合格痕迹)

★ success 必须来自外部, 四级来源:
  ① judge_verdict   密封任务集判定 (进程外, 最强)
  ② tool_receipt    执行器真实回执
  ③ self_report     ★ 只能记"声称", 不许记 success
  ④ NOT_EVALUATED   ★ 既不许当 True 也不许当 False, 覆盖率单独报
  判据: success is True ⟺ success_source ∈ {judge_verdict, tool_receipt}

★ 三分离 (2609.08183 §3.4): prediction / decision / outcome 分开存
  ★ "被实际服务的东西不能当训练标签"

★ 六维质量不压成单一分数 (2609.08183 §3.2):
  goal_attainment / instruction_adherence / tool_use /
  evidence_consistency / error_recovery / termination
  ★ 理由 (DWC 实证): 母巢旧秤四分量全是输出形状 ⇒ 实干 0.5359 < 空壳 0.8504

★ 修 ARSI 三处硬编码 (core.py L491 / L556 / L572):
  · confidence > 0.1 作决策阈值 → 改由 iwm 校准器给 τ_high/τ_low
  · remember 永远 exec_ok=False → 改由 tool_receipt 判定
  · effect 二值 (0.6/0.2)      → 删除, effect 只从外部源取
```

#### ★ actor 的可机械检查判据（gate.py 候选，7 条）

```text
A1 success 来源合法    success is True ⇒ source ∈ {judge_verdict, tool_receipt}
A2 失败痕迹必须有签名  failure_signature 含 (c,q,m)
A3 三分离齐备          prediction / decision / outcome 三字段都在
A4 无硬编码决策阈值    actor 下不得有浮点字面量作 if 阈值
A5 expected/observed 成对
A6 六维不压缩          质量字段必须是 dict, 不得是单个 float
A7 未评价≠失败         success is None 不计入失败率 (也不计入成功)
```

#### ★ 任务源 = 世界模型生成（2026-10-03 用户决策）

```text
不是: 等宿主喂任务 (ARSI host adapter 路线)
不是: 固定扫描 web/arxiv (Ultra 心跳路线)
而是: 世界模型自己造任务 —— 内生事件源

生成链:
  ① 世界集合 𝒲 = {W_1..W_n}, 每个 W = 一棵发现树 (已知 + 未揭示分支)
     初始播种: sealed_tasks 15 条 (复用 ARSI, 补齐 rung 2)
  ② 任务生成: W.legal_actions()  = "未揭示的叶子"  ← ★ 任务列表
  ③ 采样: 按 lineage pass-rate (ELScheduler 形态, 非随机全池)
  ④ actor 执行: probe_batch(选中 cells) → Observation{score,cost} → PROXY
  ⑤ 世界更新: 揭示的分支标 observed → legal_actions() 变化
  ⑥ 世界演化: WorldEvolver 生成新世界 (scenario/skill/length)

★ ARSI 实测依据 (world_pool_snapshot.json):
    el: {advances: 46, lineages: 33} / evolution_log: 50 条
    但: generation 全 = 1 / 只 用 scenario / accepted 50/50 (100%)
  ⇒ DWC 必须修三处: 代际推进 / 三方向都用 / 拒绝率下限 ≥15%

★ 这条链路是原则 9 (世界模型门控决策) 的第一个门控点,
  也是原则 10 (事件源必须三层) 中"内生源"的落地形态。
```


### 4.3 `memory`（记忆内核）· 七管数据链

```text
★ 采纳母巢七管形态 (44 天真实留痕, 非空壳), 补上闭环:

  remember → recall → learn → reflect → evolve → dream → maintain
    ↑                                                      │
    └──────────── 闭环: 写入必须能被读取 ──────────────────┘

  ① remember   摄入 actor 痕迹 → 节点+边 (必须带失败定位)
  ② recall     多路融合 + 重力排序 (取回后 access_count +1)
  ③ learn      effect×surprise 乘法门控, 回写 importance
  ④ reflect    失败归因 → 失败签名 (c,q,m) + 因果问责
  ⑤ evolve     变异 → 提案 → 过门 → 应用  ← 唯一"改东西"的阶段
  ⑥ dream      记忆重组 + 沙箱试演
  ⑦ maintain   Weibull 遗忘 + 稀有保护 + 审计

★ 与 ARSI 5 动作同构 (dream/learn/evolve/maintain/remember),
  DWC 多 recall 与 reflect 两管 —— 正是"记忆被使用"与"失败被定位"的关键。

★ 母巢在此的三处失衡, DWC 必须修:
  失衡1: 98.8% 节点 access_count=0 (21万条只有2472条被用过)
  失衡2: 32/59 记忆机制零生产引用
  失衡3: evict:0 触发 83,364 次 —— 淘汰规则只看 access/age, 无对象可淘汰
```

#### 记忆的原始规格

```python
# 三区 (ARSI MemoryZone)
SELF       身份 (永不删除, 改进算子不能重写核心)
EXPERIENCE 提炼的智慧 (跨 agent 共享, 可归档)
PROXY      宿主原始轨迹 (喂料, 蒸馏后可清理)

# 写入门 (ARSI DopamineGate)
should_consolidate = importance >= 0.6
score = importance*0.6 + surprise*0.4

# 遗忘 (ARSI UtilityDecay)
new_utility = utility - decay_rate*(1-freshness)
< min_utility(0.05) → archive
★ "A memory accessed 5 times in 3 days is 'younger' than
   a 1-day-old memory never accessed."
```

**DWC 增补**：

```text
𝒲 工作态 / ℰ 经验态 双视图 (同一份数据)
失败签名 (c, q, m) 作为 ℰ 的记录粒度
★ 𝒲 从"当前需要"取输入, 不是从完整历史取 (2608.24876)
```

### 4.4 `evolver`（进化内核）· 七环节（v4 重写）

```text
★ v3 写的是四步流水线 (消化→提案→过门→应用)。
  v4 以 16 篇进化论文为核心重构为七环节 —— 四步是"归纳", 七环节是"演绎":
    16 篇回答的是 7 个正交问题, 每个问题一个环节。
  ★ 七环节的归属与冲突裁决见 §2.4; 完整设计见 docs/EVOLUTION_CORE_V2.md。

evolver 内部承载 ①②③④ 四个环节 (另三个归其他器官, 见 §2.4.2):

① 诊断  失败签名 (c,q,m) 精确聚类 + 七桶路由 + 四量度量
        2606.09498 / 2609.06396 / 2609.14857 / 2609.11873
        ★ 聚类按三元组**精确一致**, 不按语义相似 (原文:
          "两个 run 可能共享同一个 verifier 结果, 却需要不同的 harness 改动")
        ★ 七桶: infra_only 不进诊断 (否则用 harness 改动去修环境 bug)
        ★ 四量: update_quality / activation / faithful_use / downstream_benefit

② 对象  RRSI 组件词表 𝒦(9) + 𝒦_str(4) + 九维 D1-D9 + 八 hook
        2609.24972 式12/15 · 2606.14249 §3.3/Table 1
        ★ 组件的 singleton_group 互斥 ⇒ 把"重复检测"变成属性冲突检测

③ 门    六步, 顺序不可换 —— 见下方"门"节
④ 落地  见下方"应用层"节

★ 另三个环节:
  ⑤ 防漂移 → iwm        (GDI 四信号 + grounded 双条件 + 协同三条件)
  ⑥ 探索   → world_model (回放仿真器 + 残差难度 + EL 调度器)
  ⑦ 主体   → 全系统      (五元 χ=(π,V,m,U,ρ) 盘点, run_term 末执行)
```

#### ★ 门（第 ③ 环节）· 六步顺序不可换（v4 新增）

```text
★ 四门并置 —— v3 只有 ARSI 的非补偿四步一门, v4 从 4 篇论文各取一门:

① 泄漏筛查      leakage screen BEFORE evaluation      2609.24972 第 0 步
② FGGM 契约     check(Φ_l ⟹ Ψ_l), K=5 拒绝采样 + 已验证 fallback  2603.25111 §2.2
                ★ fallback 自身也必须满足同一条契约 (validateFGGM 第 26 行)
                ★ 命中母巢反例: _probe() 恒 True / ScoreChannel 恒 0.7
                  = 没有 checker、没有 fallback 的裸 GM 调用
③ drawback 检测 不认证正确, 只找缺点                 2607.12790 §2.1
                ★ 原文: "a clean verdict means no known drawback was found,
                         not certified correctness"
                ★ 评分器必须与被评分者**失效模式不同** (防共谋盲点)
④ 双 split 接受 Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧ max(Δ_in,Δ_ho) > 0   2606.09498 Algorithm 1
                ★ 只有一组 split ⇒ 无法判定"可复用改进 vs 过拟合"
⑤ 非补偿三步    噪声地板 → 成本规则/整形 → 领域守卫   2609.24972 §3.3
⑥ 退火预算      b_t = ⌈b_min+(b_max−b_min)·½(1+cos(πt/T))⌉, b_min=1  2609.24972 式4
                ★ 原文: "不约束的 proposer 会把很多互不相关的修改捆成一个候选…
                         any measured change is difficult to attribute to
                         a particular mechanism"

★ 配套的信用分配台账 (2609.24972 式10):
   ℒ_t = { (t_i, ℓ_i, h_i, d_i, ΔS_i, ΔC_i, a_i) : i ≤ n_t }
   a_i = 1 当且仅当携带编辑 i 的候选成为该轮赢家
   ★ "通过了所有门但输给更高分候选" 记 a_i = 0 ("admissible but lost", 有用信息)

★ ★ m 与 U 必须分离 (GAI Figure 2: 环上"恰好一条 authority boundary")
   m = 改进器 (提议) → 产生候选编辑
   U = 改动评估器 (裁决) → 执行上面六步, **判据来自 judge**
   若同一模块既提议又裁决 ⇒ 第二条边界 ⇒ 自确认循环
```

#### ★ 应用层（进化核心第 4 步）· 2026-10-03 新增

```text
★ 实测: 四项目里只有一个真正的落地器 —— 母巢的 GeneChampion (10,091 字符)
  ARSI:  无落地器 (evolver 明说 "Does not auto-edit core"), 860 accepted → 2 applied
  Ultra: 无落地器 (evolve 0 条)
  Nexus: 无落地器 (8 行常量)
  母巢:  有落地器, 且它记录了三次失败 ⇒ DWC 照它的形态 + 修它的三处错

★ ★ DWC 不用影子机制（2026-10-03 用户裁决）

  影子的三宗罪 (母巢实测):
    罪1 把"该决的事"推给时间: SHADOW=True 默认, set_shadow(False) 调用 0 次
        ⇒ "生产观测满 20 tick" 这个条件永远不到期
    罪2 观测目标错位: 母巢观测的是 "need_setter 清零"(接线完成),
        不是 "这个变更好不好" ⇒ 观测再久也不知道好不好
    罪3 转正率实测 0.8% (promoted=1 / reverted=124~317)
        根因: score_in 是量化阶梯函数, 同台阶内 gain 恒 0 ⇒ 降门槛无用

形态: 五段式 (无影子, 无等待期)
┌────────────────────────────────────────────────────────────┐
│ ① 打分器 scorer                                              │
│    约束: 只依赖 (task, output) / 无隐藏维度 /                  │
│          不可评返回 None / 纯函数零随机零时钟                  │
│    ★ 先验证分辨率: 不同配置在同一批任务上必须产出不同分         │
├────────────────────────────────────────────────────────────┤
│ ② 任务源 probe                                               │
│    从真实状态取 / 确定性切分 / 候选与在位者同一批               │
├────────────────────────────────────────────────────────────┤
│ ③ 选择器 offline replay (★ 替代影子)                          │
│    V = max(s) − β₁·N + β₂·N/max(1,k)                          │
│    候选集必含 current ⇒ 数学保证不回退 (arXiv 2609.14858 §3)   │
│    ★ 算完即决, 无等待期, 无到期裁决                            │
├────────────────────────────────────────────────────────────┤
│ ④ 落地器 applier                                             │
│    setattr + 读回验证 (verify); 读回 ≠ 候选值 ⇒ 报错           │
├────────────────────────────────────────────────────────────┤
│ ⑤ 回滚器 rollback                                            │
│    存旧值; 回退 = 写回 + 读回确认                              │
└────────────────────────────────────────────────────────────┘

★ 安全来源的替换 (这是"不要影子"的核心理由):
  影子:   安全来自"经验观察"   →  实测转正率 0.8%, 时间花掉安全没换来
  离线回放: 安全来自"数学保证" →  V^{m⋆} ≥ V^0 (候选集含 current)
  ★ 一个是"一个有判据, 一个没有"

消费点声明形态 (照母巢 GENE_TARGETS, 多一个 verify):
  {"consumer": "策略选择 ε-greedy 探索率",
   "path": "actor._policy", "attr": "_epsilon",
   "range": (0.01, 0.5),
   "verify": "abs(actor._policy._epsilon - candidate) < 1e-9"}

★ 三条纪律 (母巢用 3 次失败换来, 直接采纳):
  纪律 1 · 基线与结算必须同一口径
     母巢错: base 取 _run_ga 启动 score_in({}), current 取结束 score_in(best_genes)
             ⇒ gain 恒 ≈ 噪声 ⇒ 124 次回退
  纪律 2 · base 打老配置(current), current 打新配置(candidate)
     母巢错: _base_metric = _m (此刻 _m 是 challenger 的分)
             ⇒ gain = 自己减自己 = 0 ⇒ 100% 回退
  纪律 3 · 打分器没分辨率时, 调门槛是自欺
     母巢错: min_gain 0.01 → 0.0005, 结果晋升比 0.087→0.15 (噪声内) + metric 退化
     真因: score_in 是量化阶梯函数, 同台阶内 gain 恒 0
     ⇒ 先验证 scorer 有分辨率, 再谈门槛

★ 两条判据:
  ① 应用必须可读回 (原则 4): setattr 后读回, ≠ 候选值 ⇒ 报错
  ② 应用必须有回滚路径: ARSI 的 inverse_op 862/862 全非空, 这点 ARSI 对
```

### 4.5 `iwm`（内省自检）

```python
# ARSI iwm/calibrate.py 原文
"""Introspector self-check (Q6) — is the introspector itself trustworthy?
Low self_trust → IWM control advice is ignored; system degrades to baseline."""
degrade_below: float = 0.35     # self_trust < 0.35 → 降级
min_samples: int = 5

@staticmethod
def is_meaningful_success(success, note):
    """Stricter than exec_ok: empty/no-op actions are not success."""
    if "no new traces" in n or "waiting" in n or "unknown action" in n: return False
    if "skipped" in n or "insufficient" in n or "no_distill" in n: return False
```

**六个问题（ARSI IWM facade 原文）**：

```text
Q1 organ reliability      → control hooks
Q2 knowledge frontier     → explore/exploit bias
Q3 loop efficacy          → 基于证据的自指标更新 (no η hand-twisting)
Q4 transition ledger      → 自变更审计
Q5 decision provenance    → 回放"为什么选 a"
Q6 calibrate              → ★ 内省器不可信时降级回 baseline
```

**★ Q6 是 ARSI 最干净的一处设计，v2 完全没提。**

#### ★ iwm 承载环节⑤ 防漂移（v4 新增）

```text
★ 归属裁决: 七环节里 ⑤ 防漂移 归 iwm (见 §2.4.2)。
  依据: iwm 已有 degrade_to_baseline (整体否决) 与 downweight_pre_enactment;
        SAHOO 的 GDI 正是"何时漂了"的度量 —— 是 iwm 的自然扩展。

三个来源:

① GDI 四信号漂移分解  2603.06333 Appendix B (全部落在 [0,1])
   Δ_semantic       (1 − s_cos)/2                           Eq.8
   Δ_lexical        JSD(P₀‖P_t) = ½KL(P₀‖M) + ½KL(P_t‖M)    Eq.9
   Δ_structural     (1/K)·Σ min(1, |s₀−s_t|/(s₀+ε))         Eq.10
   Δ_distributional W(P_baseline, P_current)  1-Wasserstein  Eq.11
   GDI = Σ w_i·Δ_i,  Σw_i = 1                                Eq.12–13
   ★ 关键 (Appendix A.2 原文): 漂移相对 **初始状态 θ₀** 度量, 不是相对上一轮 ——
     "prevents short-term, high-variance cycle-to-cycle changes from masking
      long-term drift"
   ★ 为什么对 DWC 特别值钱: 它只需要"基线 vs 当前"的成对观测,
     **不需要任务真值源** —— 恰好绕过真值源困境。

② grounded 双条件  2609.13406 §2.2
   ① 内容来自系统外 (世界与目标)  ② base 本身在 agent 外
   ★ 两个条件是 AND, 缺一不可。
   ★ 可落成断言: {Q*, T_seal, release_rule, ℒ} ∩ W_i = ∅ ∀i
   ★ Remark 2 原文: 判别标准问的是"标准坐在哪里", 不是"它多忠实于目标"
     ⇒ 弱评估器 + 密封 = 合法;  强评估器 + 在可写面内 = Goal Drift

③ 协同进化三条件  2608.10299 §2.2
   ∃ x ≠ y : x^{t+1} ≠ x^t,  y^{t+1} ≠ y^t,  x ←→(evolutionary pressure) y
   ★ 三条件同时成立才算 co-evolution
   ★ Stage 3 判据原文: 机制修订必须由下层 co-evolving 生态的**联合轨迹诱导**,
     且必须反过来改变该生态的后续进化条件
```

### 4.6 `iron_laws`（铁律，横切）（v4 重写）

```yaml
G1  设计/执行分离    策略生成与突变落地解耦              warn
G2  分级安全门      层级越深阈值越高                   warn
G3  冻结/人类主权    冻结开关优先级高于所有进化          block
G4  审计触发        巩固须含 why/trigger/verify        warn
G5  客观效用锚      效果 ∈ [-1,+1]，禁自评             block
G6  熔断            CLOSED/OPEN/HALF_OPEN 状态机      block
G7  数学收敛        Lyapunov 函数单调下降              warn
G8  因果问责        假设→设计→结果因果链完整才激活       warn
G9  高熵校验        高熵记忆和决策主动生成验证请求        warn
G10 密封评估层      任务集/评分规则/发布门槛在所有写掩码之外 block
```

```text
★ v3 只有这张表 + 一条不变式 (618 字符)。
  v4 重写; 完整设计见 docs/IRON_LAWS_DESIGN.md。

★ 先说 ARSI 的五处硬缺陷 (最严重的一条: 两套实现, 生产用弱的):

  ① 两套实现, 生产用弱的
     iron_laws.py      IronLaws          ← core.py:208 用的是这套
     enforced_laws.py  EnforcedIronLaws  ← 只有 tests 用 (真实现 G5/G6/G10)
     ★ grep "EnforcedIronLaws" → 除定义外只有 tests/test_enforced_laws.py

  ② warn 级从不检查
     violated() 原文: if law.severity == "block" and self._check_law(...)
     ★ 6 条 warn (G1/G2/G4/G7/G8/G9) 在任何路径下都不会被检查
     ⇒ "warn" 实际含义 = "不存在"

  ③ ★ G10 的判据读一个不存在的属性
     L110  if hasattr(state, "sealed_tasks_accessible"):
     ★ 全仓搜索: 只有 tests/test_integration.py:217 设置该属性
     ⇒ 生产里 hasattr 恒 False ⇒ G10 永不触发 (而它是 block 级!)

  ④ validate_policy (L114) 全仓 0 调用 ⇒ 预算集中度检查从未执行

  ⑤ ★ 标签错标: L127 raise "G10: budget allocation too concentrated"
     ★ 预算集中度是 G2 的事, 不是 G10 ⇒ 违规日志会误导归因

  ⇒ 净结果: 生产里 10 条铁律实际生效 **0 条**。
     "∀ reachable S, ∀ operator U: G(U(S)) = G(S)" 这条不变式
     在代码里是**空转**的 —— 因为 G 恒为"无违规"。
```

**DWC 形态：数据驱动 + 可触发（修 ARSI 的硬编码 if 链）**

```text
★ ARSI 的病根: 铁律是硬编码的 if 链 (if law.id == "G10": ...),
  而配置里有个从未使用的 check_fn 字段 (L29) —— 设计意图与实现脱节。

DWC: 铁律 = 数据 (声明) + 检查器 (实现) + 触发点 (接线), 三者必须闭合。

  iron_laws/
    ├─ laws.yaml        声明 (人可改, 系统只读)
    ├─ registry.py      按名解析 check_fn → 检查器
    ├─ checks/          一条铁律一个文件 (g1_*.py … g10_*.py)
    └─ hooks.py         ★ 触发点登记 (哪条铁律在哪个阶段被调用)

★ 三条闭合判据:
  ① 每条铁律在 checks/ 里有对应文件   (禁 default return False)
  ② 每条铁律在 hooks.py 里有触发点     (禁"定义了但从不调用")
  ③ 每个检查器读的字段有设置方          (禁"读不存在的属性" ← 修缺陷 ③)
```

**★ 修缺陷 ②：warn 与 block 都必须检查**

```text
warn 与 block 的区别是**后果**, 不是**是否检查**:
  block → 抛异常, 阻断操作
  warn  → 记审计日志 + 计数, 不阻断
★ 检查器返回三值: PASS / WARN / BLOCK (不是布尔)
⇒ violated() 改为 check_all(state) → {pass:[...], warn:[...], block:[...]}
```

**★ 铁律与"停止规则"的分工（2603.06333 §2.7）**

```text
铁律    = 永恒约束 (G1-G10), 不变式, 只有人能改
停止规则 = 运行期熔断 (本轮该不该继续), 由参数校准:
  ① 连续三次迭代质量变化 < 0.01
  ② 回归风险 R_c^adj > τ_R          (Eq.23)
  ③ ★ 任一周期约束保持为 0          (优先级最高 —— 约束违反绝对优先)
  ④ 达到最大周期数
  ⑤ GDI > 校准阈值
★ 第 ③ 条把两者连起来: 铁律违反 ⇒ 立即停止

★ 长时程稳定性界 (Eq.24, 这个数字很有说服力):
  若每周期增量 Δ𝒬_i ~ N(μ,σ²) 独立同分布, 则"未来 c 周期全为正增量"概率 = (Φ(μ/σ))^c
  论文举例: 每周期 0.6 的改进概率, 10 周期后 0.6^10 ≈ **0.00605 (约 0.6%)**
  ⇒ "每轮都小改进"在长时程上几乎必然中断 ⇒ 不能只靠"每轮涨一点"
```

**★ 不变式怎么验证（不能只声明）**

```text
① G 的配置哈希在 run_term 前后必须相同 (hash(laws.yaml) 前后一致)
② 每个检查器的代码哈希在一轮内不变
③ ★ 用"故意违规的 state"喂每个检查器, 断言它 raise
  ⇒ 证明检查器**有能力**违规, 不是恒真
★ ARSI 的 test_foundation.py:187 就是 `assert laws.violated(FakeState()) is False`
  —— 只测"不违规" ⇒ 恒真无法被发现。
```

### 4.7 `world_model`（世界模型）· 承载环节⑥ 探索（v4 新增）

```text
★ v3 的六器官清单漏了它, 但三处依赖它 (§2.3 决策层 / 原则 9 / §4.2 任务源)。
  v4 补为第七个器官。

职责一: 生成任务 (§4.2 内生事件源)
  𝒲 = {W_1..W_n}, 每个 W = 一棵发现树
  W.legal_actions() = "未揭示的叶子"  ← 任务列表
  初始播种: sealed_tasks 15 条 (复用 ARSI, 补齐 rung 2)

职责二: 承载环节⑥ 探索
① 回放仿真器  2609.14858 §2.2–2.5
   Discovery Tree: 根 r = 初始工作区; 每非根节点恰好一个 primary parent
   共享决策接口: A(𝒯) = {r} ∪ {v ∈ 𝒯 : v is a leaf}
                A(𝒯; W) = { C ⊆ A(𝒯) : |C| ≤ W }
   Online:  策略固定跑一轮, 产出新树;  ℋ_t = ℋ_{t−1} ∪ {𝒯_t}
   Offline: ℋ_t 固定不变; 构造并评估 M ≥ 1 个策略版本
   ★ 不回退保证: 候选集必含 current ⇒ V^{m⋆} ≥ V^0 (数学结论)
   ★ ★ 这是"不要影子"的论文级替代 (见 §4.4 应用层)

② 残差难度 + EL 调度器  2609.04128 §2.1 / 式2
   δ_θ(z_t|g) = [ d_θ(z_t|g) − d_𝒯(z_t|g) ]₊
   Δ_θ(ξ) = Σ_t [ d_θ − d_𝒯 ]₊
   ★ 全文枢纽句: "weakness is not the difficulty of the environment itself;
     it is the portion of that trajectory that is unusually difficult for a
     particular model relative to the environment family"
   三方向 = 三分量: length ← L / scenario ← −log p_𝒯(σ|g) / skill ← −log p_𝒯(κ|σ,g)
   EL 调度器: B=8, τ=6/8  ★ 零模型依赖, 只需 8 次布尔观测

③ 三方向枚举 (Prometheus-Y 实测)
   FORWARD / LATERAL / REVERSE

★ ★ 世界树 (world tree) —— 环节⑥ 的实现形态 (2026-10-03 讨论后定)
  完整设计见 docs/WORLD_TREE.md。要点:
   · ARSI 实测有**三套树**但**没有收束**:
     DiscoveryTree (回放, 29 次提及) / ReplayWorld (回放, 24 次) /
     CounterfactualSimulator (前瞻, **只被构造从不调用** — 宽口径 grep 0 处)
     ★ grep MCTS/monte/beam/alpha_beta/minimax/a_star → 全 0 命中
   · DWC 只许**一套树**, 节点带 provenance ∈ {observed, simulated}
   · 收束三段: 展开 → 评估 → **选信息增益** (不是选模拟最高分)
     ★ 依据: 2609.04128 EL 调度器 (按 pass-rate 采样) +
       2609.24972 式17 ("噪声带内微小提分不足以被接受")
   · ★ 三条约束: ①想象节点不许进 judge ②收束判据不许用世界模型自算的
     confidence ③树只提供候选, 决策仍归世界模型
   · 六条判据 W1-W6

★ 三处已知缺口 (V2 诚实边界; ①已解, ②③未解):
   ① ✓✓【已做 2026-10-04】RRSI 的 𝒦 词表只覆盖 16/21
      → docs/COMPONENT_VOCABULARY.md: 𝒦 不扩, 另建 𝒦_meta 五项
        (code/architecture 可编辑但无 ν · meta_evolution 唯一拿 ν
         · evaluator/external_source 登记但禁改) + 判据 K1–K6
        ★★ 实测 K1: 21/21 全可映射
        ★★ 顺带修了 EVOLUTION_CORE_V2 映射表的编号错位（三处，最严重是
          第 16 项「评估器」被映射到 output_plumbing ⇒ 违反 G10）
        ★★ 实测抓到我自己的错误: 式14 剪枝原用并集 ⇒ 会把不可编辑项
          （g_t 默认 -∞）标成删除目标 ⇒ 已改为 𝒯_t ∩ 𝒦_editable
        ★★ 未裁决: "20 基础设施 → code" 有争议（也可归 architecture）
   ② ✓✓【已做 2026-10-04】δ_θ 的 p_𝒯 估计（docs/RESIDUAL_DIFFICULTY.md）
      ★★★ 先纠正一处**我自己写错的出处**:
         δ_θ 不出自 2609.14858 —— 实测该文 "difficulty" **0 命中**;
         δ_θ 出自 **2609.04128 §2.1**（"δ θ" 3 命中）✓
      ★★ 核到完整公式:
         D_θ(ξ) = Σ_t[ −log p_θ(σ_{t−1}|g) − log p_θ(κ_t|σ_{t−1},g) ]
         D_𝒯(ξ) = 同形但用 p_𝒯（"grounded in broad world knowledge"）
         δ_θ(z_t|g) = [ d_θ(z_t|g) − d_𝒯(z_t|g) ]₊
         Δ_θ(ξ)   = Σ_t [ d_θ − d_𝒯 ]₊
         ★ 原文定性: "weakness is **not** the difficulty of the environment itself"
      ★★★ 问题性质被重新定位（不是"缺一个估计算法"）:
         论文唯一的估计说明是"**a deep-research agent can estimate both
         distributions through broad web search**" ⇒ 它给的是"换一个知识来源"
         ⇒⇒ DWC 缺的是**可信的外部知识源**, 这与 §9 第 20 项（守卫① 跨层自评）同型
      ★★★★ 更硬的一条: p_θ 这一项在 DWC **物理上不可得**
         d_θ 需要 −log p_θ(σ|g), 即模型输出的**概率**
         ⇒ DWC 的 actor 走云端 LLM API（§4.2 已定）⇒ **拿不到 logits**
         ⇒⇒ ⇒ 省掉 p_θ 不是取舍, 是**必然** ⇒ DWC 无法完整复现论文的 δ_θ
      ★★ 裁决: 走**路线丙（组内基线）**为主, 路线甲（deep-research）为可选
         δ_θ^group(z|g,j) = [ −log r_group(z|g,j) ]₊（Laplace 平滑, k=1）
         数据前提已具备: A6 三组 + C3' TaskScorePoint 历史
         ★ 实测: 排序作用与论文一致（同序）但数值不同
           （论文式 log(0.20/0.05)=1.3863 vs 路线丙 −log(12/55)=1.5224）
           ⇒ ★ 不可混用绝对阈值, 只可作排序偏置
         ★ 路线甲若启用: deep-research 代理必须在**写掩码之外**（判据 X3）
      ★ Difficulty 两个必填字段: semantics（哪条路线）/ n_obs（0 ⇒ delta=NaN）
         —— X2 的依据: "没观测过"与"观测到频率0"必须分开, 否则空组会被读成"很常见"
      判据 X1–X5（同族第十一族: X 管难度语义的可追溯性）
      ★★ 最大未验证前提: z_id 的构造方式（ξ=(σ,κ) 是论文的分层代理执行形式化,
        DWC 的 actor 是 §4.2 六维结构 ⇒ 两者是否同构未核）
      ★ 未定: n_obs 的可信阈值
   ③ ✓✓【已做 2026-10-04】跨篇冲突已裁决（docs/GATE_CONFLICT.md）
      ★★★ 裁决推翻了原表述: **"互相矛盾"不准确** —— 是**粒度差异**:
        · HarnessX seesaw = **逐任务二值**（任一已解题掉分就拒）
        · Self-Harness Δ_in≥0 ∧ Δ_ho≥0 ∧ max>0 = **split 聚合分**
      ⇒ "取并集"这个动作本身是错的: 它们不是同层的两个选项, 是同一层的两个判据
      ★★★ 真正的问题是**两篇共有的一个盲区**, 且 HarnessX 自己实测击穿两次:
        "no individual edit violated the constraint" 而实际 compliance
        94.7% → 80.7%（**−14.0%**）; 原因原文: "pass@2 registers only
        **per-task binary flips**, not sub-threshold coupling"
      ★★ 新增门**第⑦步「累积退化判据」**（我的构造, 无论文背书）:
        ∀j: (连续 N 轮中, 组 j 的「非翻转退化」累积量) ≤ Λ_j
        ⇒ 依据: 同台阶内 gain 恒 0 的老病（母巢 score_in）也存在于逐任务分数上
      ★★★ 实测确证（混合场景: 两组微跌 + 两组微涨）:
        seesaw 违规 **无** · 双 split 拒 **无** · 第⑦步 R5 就抓到
        ⇒⇒ 它防的不是"全员退化"（双 split 已够）,
          而是"**被其他任务的改善掩盖的退化**"
      ★ 三条冲突的裁决: 粒度→以逐任务为准 / 严格度→归档态兜住被否决的
        局部有益改动（三态保留从 enhancement 升级为冲突解法）/ 盲区→加第⑦步
      ★ 带出新需求: 逐任务分数序列必须被记录（判据 C3'）
        ✓✓【已做 2026-10-04】docs/TASK_SCORE_TRACKING.md + 判据 TS1–TS5
        ★★★ 纠正我自己的推断: 我以为 DWC verifier 是二值 ⇒ 核实后发现**不是**
          （ARSI 三函数全返回连续分 tuple[float, dict]）⇒ 不需新造评分器
        ★★★ 真正缺口是**分辨率**: 15 条任务各含 2–3 个断言 ⇒ score 只有 3~4 个
          离散点 ⇒ 最小可观测退化 = 1/n ⇒ 抓不到"小于一个断言"的退化
        ★★★ 实测抓到**死判据**: Λ=0.03 < 1/median(n_assertions)=0.5
          ⇒ 物理上不可能触发 ⇒ TS5 判据（Λ 须与分辨率同量纲）成为核心
        ★★ 已连带降级本项的立论: 第⑦步 = "**更严的 seesaw**", 非"无限灵敏的探针"
        ★ 落点: STATE_SCHEMA.GateSnapshot 增 3 字段
          （task_scores_ref 指针 / group_scores / n_assertions_min 分辨率自陈）
        ★★ 关键发现: evidence 里已有逐条 results ⇒ 不必等 n_assertions 变大
      判据 C1'-C4'（同族第八族: C' 管跨篇一致性）
      ★★ 诚实: 第⑦步"能抓住 HarnessX 那个案例"是**机制层面推断**,
        非用原文数据跑出
```

### 4.8 环节⑦ 主体 · 全系统盘点（v4 新增）

```text
★ 它不是器官 —— GAI 的 χ 横跨 actor(π) / judge(V) / evolver(m,U) / judge(ρ)。
  由 run_term() 在周期末执行一次盘点。

五元盘点 (GAI arXiv:2609.13406 Definition 1):
  χ = (π, V, m, U, ρ)

  π = 执行策略        → actor          ✓ 有
  V = 评估器          → judge          ✓ 有
  m = 改进器          → evolver 内      ✗ ★ v3 没有 (v4 归 evolver, 待实现)
  U = 改动评估器      → evolver 内      ✗ ★ v3 没有 (v4 归 evolver, 待实现)
  ρ = evaluation base → judge 密封任务集 ✓ 有 (需 grounded 双条件校验)

自主性等级 (2609.11873 §2.3):
  B0  In-Task AI Improvement —— 判别: "output change without persistent
      system change"
      ★ DWC 硬判据: 关掉进程重开, 改动是否还在? 若不在, 仍是 B0。
  L1  Improvement Execution Autonomy —— 人规定改什么/怎么改/什么算成功; AI 执行
  L2  Improvement Strategy Autonomy —— 目标/边界/验收外部固定, AI 诊断弱点并决定如何改进

★ structural vs effective (验收必须区分, 原文):
  structural = 改动的机制确实控制后续一轮
  effective  = 该机制在可比预算与独立评估下产出更好后继
  "Self-modifying task code provides insufficient evidence when the process
   responsible for later revisions remains unchanged."
```

---

## 五、DWC 与 ARSI 的分岔点

### 5.1 两边是同一个病的两面

```text
ARSI: 有门但产物不改核心   —— 生 0 / 死 0
      环境进化线通 (世界池 g0=43→g1=7, verifier 三道门全过)
      自身进化线不通 (manifest 全 accepted, 代码一行没改)

母巢: 有产物但没门         —— 生 1,447 / 死 5
      best_genes → str() → branch_merges(167,753 行) → 无人消费
      SHADOW=True 从未翻; GeneChampion promoted=1/reverted=124~317

★ DWC 必须同时解决: 门 + 落地
```

### 5.2 DWC 的解法：产物必须有"运行时消费点"

```text
定义: 任何进化产物必须声明运行时消费点 (哪个对象的哪个属性)
      无消费点 = 不许进准入流程

参照母巢 gene_applier 的声明方式（它的设计是对的）:
  "exploration_rate": {"consumer": "MultiStrategyScheduler ε-greedy",
                       "path": "loop._evo_scheduler._epsilon",
                       "attr": "_epsilon", "range": (0.01, 0.5)}

★ 母巢失败不是没声明, 是声明后 SHADOW 永不翻开
★ DWC 要求: 写入后读回, 确认值真变了
```

---

## 六、第一性原则

```text
原则 1 · 判据必须在系统之外
  来源: 评分器会塌缩 (2607.12790: 塌缩评分器 0.811 > 认真评分器 0.767)
  ★ 这条是根, 不是推论
  ★★ 2026-10-04 增补: 判据**位置**合规 ≠ 判据**结论**有效
     ⇒ 见铁律 G11「门通过 ≠ 系统安全」(docs/IRON_LAW_G11.md)
     依据 2603.25681 §8.1: "An evaluation that reads as safe therefore **cannot
     certify** that the self-improvement system is actually safe"

原则 2 · 进化所需的养料来源于记忆
  来源: 用户提出
  ★ 约束的是"进化的输入", 不是进化的组织形式

原则 3 · 单一真值源（推论）
  ★★★ 2026-10-04 人眼通读 13 条原则时更正: **"由原则 1 导出"这个推导不成立**
    原则 1 讲判据的**位置**（必须在系统之外）
    原则 3 讲判据的**唯一性**（同一事实只能有一个权威源）
    ⇒ 「位置在系统外」**推不出**「只能有一个真值源」⇒ 原推导链是断的
  ★ 真正的推导（从约束对象出发，不从原则 1 出发）:
    进化要求"能记住自己做过什么"（原则 2）⇒ 若同一事实有两个源，
      进化读到哪一个取决于实现细节 ⇒ 不可复现 ⇒ 进化退化成随机
    ⇒⇒ 所以单一真值源是「原则 2 + 可复现性要求」的推论，不是原则 1 的推论
  ★ 任何不在记忆里的状态, 都是进化够不到的死状态（这句仍成立）

原则 4 · 进化产物必须有运行时消费点
  来源: 母巢 gene_applier 自述 + 167,753 行 branch_merges 无人消费

原则 5 · 行动者的行动必须可评价
  来源: ARSI step() 产出 trace → 进 store; is_meaningful_success 严判

原则 6 · 器官之间只经接口通信, 不经内部状态   ★ 器官式的必要纪律
  判据(可机械检查): 器官 A 不许出现 organ_B._private_attr
  ★ 没有这条, 器官式会退化成母巢那种散装

原则 7 · 记忆必须证明"被使用"   ★ 2026-10-03 新增
  一条记忆若无 access 记录, 不得被当作"有价值"。
  依据: 母巢 98.8% 节点 access_count=0, 但 importance 均值 0.747
        —— 自评很高, 实际没人用。

原则 8 · 机制零引用即违规   ★ 2026-10-03 新增
                    ★★ 2026-10-04 人眼通读时补: N 的取值**未定义**
  ★★★ 2026-10-05 **已裁决**: N 由 term 边界推导，不给固定默认值
  任何机制若在 N 个 **term** 内零调用, 门报红。
  ★★★ N = 必填、无默认（与 K4 / G11 同款纪律）
    理由: N 太小会把"还没轮到"的机制误杀；N 太大则死机制长期潜伏
         —— 这正是母巢的病（29 个模块"仅测试引用"，N 太大 ⇒ 永不报红）
    ⇒ ★★ N 应由 term 边界推导（ERROR_AND_TERM §2.3 已定 term 的四个终止条件:
      ① 七环节跑通 ② 预算耗尽 ③ 保护组回归 ④ 停止规则命中），
      而不是拍一个固定轮数。
    ⇒★ 落点: config/retention.yaml 的 dead_after_terms（必填无默认）；
      实现判据 D8 时按 **term** 计数而非 step，且 term 数必须随链留痕。
    ⚠ MEMORY_SYSTEM §六 Q2 旧选项「甲 N=10 轮 / 乙 N=20 轮」**违反本原则**,
      已废 —— 那两个值都是拍出来的默认值。
  判据口径(严格): 该模块被 import 次数 = 0 且 被 invoke 次数 = 0
  依据(实测, 严格正则 memory.X / from ..memory import X):
    母巢   59 模块: 零引用 4 (6.8%) / 仅测试引用 29 / 有生产引用 30 (50.8%)
    Ultra  26 模块: 零引用 0 (0.0%) / 有生产引用 26 (100%)
    Nexus  26 模块: 零引用 0 (0.0%) / 有生产引用 26 (100%)
  ★ 更正: 早前报"32/59 零引用 (54%)"用的是宽正则 (\b模块名\b),
    会把同名变量算进去 ⇒ 口径错误, 已按严格标准重测。
  ★ 真正的问题不是"零引用", 是"仅测试引用" (母巢 29 个):
    代码写了、测试测了、生产从不调用。

原则 9 · 世界模型必须门控决策, 不许只做账本   ★ 2026-10-03 新增
  世界模型的输出必须至少有一处"门控决策"的消费点
  (即: 预测结果改变"这轮跑什么"), 否则违反原则 4。
  依据: 母巢 MWM 46 个方法 / publish 0 / subscribe 0 /
        predict → 直接 m.run() (门控关键词 0 处) /
        selection_gate 里 MWM_WEIGHT_CAP = 0.1 / dyna 默认关
        —— 有世界模型但不让它驱动, 是矫枉过正。

原则 10 · 事件源必须三层 (外生 / 内生 / 编译)   ★ 2026-10-03 新增
  外生=外部扫描; 内生=世界模型的预测/反事实/想象; 编译=机制编译产物
  缺"内生"则系统只能被动响应, 不能主动探索。
  依据: ARSI world_evolver 主动生成环境 (实测 46 advances / 33 lineages);
        Ultra/Nexus 无世界模型 ⇒ 事件源全为外生。

原则 11 · 因果链必须进信封, 且链上下文用显式 ID 查表   ★ 2026-10-03 新增
  ① chain_id 必须作为事件信封字段被传递 (不许只留字段不用)
  ② 链上下文用显式 chain_id 查表, 不用"栈顶"隐式取
     —— 栈顶隐式取在并发多链时会串链
  依据: 母巢 PipelineEvent 有 chain_id 字段, 但 7 处构造全不传
        (default_factory 自动生成新 uuid ⇒ 链断裂);
        Ultra/Nexus 链上下文用 _chain_stack[-1] 取 (并发不安全)。

原则 12 · 决策核心的守卫必须来自其他器官, 不许自评   ★ 2026-10-03 新增
                                            ★★ 2026-10-04 修正 (见下方"守卫① 裁决")
  世界模型是"第一顺位决策者", 不是"唯一核心"。
  它的核心地位由 iwm / iron_laws 授予, 且可被撤销。
  ① 可信度门:   conf ≤ 阈值 ⇒ 交 LLM, 再交启发式
        ★★ 修正后的定义: conf = **judge 在 dev split 上外测的世界模型准确率**
          （评估时世界模型冻结）, **不是世界模型自算值**。
          原文依据见下"守卫① 裁决"。
  ② 整体否决:   iwm 判定 dynamics 不可信 ⇒ 停用世界模型 (degrade_to_baseline)
  ③ 动作改写:   iwm 可覆盖世界模型选出的具体动作 (override)
  ④ 自训失败:   dynamics.train() 不成功 ⇒ 退回 baseline
  ★ 守卫不许来自世界模型自身 (否则撞原则 1)。
  ★★ 补半句 (2026-10-04): 包括不许它**自报"我准不准"** ——
     门测的是外部实测, 不是模型自报。任何 confidence 字段若由被门控者自己写出,
     该门不成立。
  依据: ARSI core.py step() 实测四处守卫 —
        use_pre 由 advice.get("degrade_to_baseline") 决定 (iwm 发出);
        forbid_default_dream 由 iwm 发出, 直接改写 decision["action"];
        confidence 门与 dynamics 重训失败退回均为独立机制。
        ★ 2026-10-04 更正: 前三项确实是异源, 但 **confidence 门不是** —
          详见 WORLD_MODEL_AUTHORITY.md 与下方裁决。

原则 13 · 机器判定的结论必须回落到人眼, 否则只是"机器认为"   ★★ 2026-10-04 新增
  ★★★ 这条来自 R5 门可信度审计的**实测教训**, 不是推演。
  背景: DWC 现有 20 族 / 130 条判据**全部**依赖机器判定,
        而五轮反刍（R1–R5）中机器判定**连续 4 次出错**:
        M1 匹配失败 ×2  正则因中文/希腊字母/含空格而漏判
                         （ASCII theta_t vs 希腊字母 θ_t；中文标题行）
        M2 代理指标 ×1  拿"编号是否出现"代替"结论是否落地" ⇒ 假阳性
        M3 口径未定 ×1  数字口径/分母未先声明就统计（连续 3 次数错）
        ⇒ 四次**全部**是机器判定自身失效, 没有一次是执行者不用心。
        ★★★ 而这四次**全部发生在设计期**（我做审计/核对时），
          0 次发生在"系统将来运行"时 ⇒ 本条只管设计期。

  ★★★★★ 生效阶段（2026-10-04 补正 · 用户提问触发）
    这条纪律**只在设计期生效**。两个阶段的义务完全不同:
    ┌─────────────┬────────────────────────────────────┬──────────────────┐
    │ 阶段        │ 谁在场                            │ 人眼义务         │
    ├─────────────┼────────────────────────────────────┼──────────────────┤
    │ 设计期      │ 人（此刻，系统还没跑）            │ ★ 每条判据落盘前 │
    │ （现在）    │                                    │   必须人眼确认一次 │
    ├─────────────┼────────────────────────────────────┼──────────────────┤
    │ 运行期      │ ★ 人不在场                        │ ★ **零**         │
    │ （将来每轮）│   系统自己提案/过门/落地           │   （见下方）      │
    └─────────────┴────────────────────────────────────┴──────────────────┘
    ★★ 若在运行期执行本条 ⇒ 人变成循环里的一环 ⇒ **那就不叫自创生了**
    ⇒⇒ 所以本条的正确形态是「设计期的一次性义务」，不是「运行期的持续负担」。

  纪律（两条 · 均只作用于设计期）:
    ① **凡一条判据被声明/落盘**，且其判定对象属于下列三类之一，
        必须同时附一条人眼确认记录（谁、何时、看了什么）：
          SEM 需理解语义（如"这句话是否真在原文里"）
          NUM 需口径先声明（如"中位数是标准中位数还是上中位数"）
          DOC 对文档本身的约定（如"标签与内容是否对齐"）
        CODE（AST/调用图/grep 可判）与 CFG（配置结构可判）**不必**人眼复核。
        ★★ 为什么必须在**落盘前**而不是之后:
          判据一旦落盘即成不可写代码（K4/editable 纪律）⇒ 落盘后想改要重开版本
          ⇒ ⇒ 设计期是人唯一能修它的窗口 ⇒ 把人放在这里，代价最低、收益最高
    ② **口径必须先声明再统计**，禁止先统计后解释。
        依据: 我在同一份报告里连续写错三次「94 份 / 69 份 / 16 份孤儿」。

  ★★★★★ 与 G10 密封评估层的关系（人类在运行期在哪）
    ★ 人在运行期**唯一**的位置是 G10 的**设定方**（一次设定，不是每轮参与）:
        任务集 / 评分规则 / 发布门槛 写在所有写掩码之外 ⇒ 系统改不了
    ⇒ ⇒ 人在运行期是「**立宪者**」，不是「裁判」，更不是「审批人」
    ⇒ ⇒ 这正是 2603.25681 §8.1 的路线:
        "an evaluation that reads as safe therefore **cannot certify**
         that the self-improvement system is actually safe"
        ⇒ 门是系统自己的；安全性不靠门，靠人**在门之外**放了什么
    ⇒ ⇒★★ 自创生的成立条件 = 运行期无人参与判定 + 人类只在门之外设定规则
      ★ 这与原则 13 不冲突: 13 管设计期，G10 管运行期，两阶段正交。

  ★★ 与原则 1 的关系: 原则 1 管"判据的位置"（在系统之外），
     原则 13 管"判据**落盘时**的可信度"（是否只经过机器）⇒ 两者正交，不重叠。
  ★★★ 缺口 A9 记录了逐族的分类结果（7/20 族需人眼复核或口径先行）
     与本条第二层问题（阶段未分离，见 A9 补记）。
```

---

## 七、进化维度（换掉 v1 的假证据）

```text
v1 写的 (已证伪): 七个 arm 各有真实记录
实测: op 只有 'evolve' 一个值; hypothesis 是 tick 计数器;
      母巢自己注释"32816 条全同质(无区分度)"; eval_driven distinct=1

★ 换成实测的维度总表 —— 但 v4 又修正了一次 (严格去重审计):

  旧表 (EVOLUTION_DIMENSIONS_TABLE.md):  对象层 28 + 元层 6 = 34
  ★ v4 实测修正 (docs/DEDUP_AUDIT_6SYSTEMS.md):  对象层 21 + 元层 6 = 27

  修正依据 (6 套体系的严格去重, 39 仓库源码逐字提取):
    删 7 个: 元认知 / 注意力 / 任务完成检测 / 智能体 / 推理增强
             / harness / 基础设施
    判据: 前三个是 ARSI 的"赋能 dimension"(从哪个角度诊断),
          不是"可进化对象"(改什么); 后四个经宽口径复核有实现,
          但不属于任何一套体系 ⇒ 列为"可选对象"或删除。
    新增 1 个: 行为/工作流 (hermes-CI L3BehaviorMutator 实测)

  ★ 关键区分: "多臂"(用哪个算法) ≠ "多维度"(改什么对象)
     母巢 7 臂都在优化同一批基因 (fitness 全在 0.46-0.66)
     真正的多维证据是 RSPL 五资源 + 元层 6 个

  ★ 21 个对象 → RRSI 组件词表 𝒦 的映射 (v4 新增):
     𝒦 只覆盖 16/21 —— 未覆盖 5 个 (代码/架构/元进化/评估器/外部机制源)
     是 V2 承认的缺口, 需 DWC 自己补。
```

---

## 八、支撑论文（ARSI 六层支柱的来源）

```text
L0 Anchored Constitution      2609.13406  GAI
L1 Contracted Computation     2603.25111  SEVerA
L2 Regularized MetaRSI        2609.24972  RRSI  ×  2609.26457  AIDE²
L3 Introspective World        2607.27924 ODEWorld + 2505.05522 CTM + 2603.06333 SAHOO
L4 Dream-RSI                  2609.14858  Dream-RSI
L5 Evaluative Epistemology    2607.12790  Grader
──────────────────────────────
Autopoiesis (charter, 横贯)    2609.13406 × Maturana 组织/结构二分
环境进化线配套                  2609.04128  Environment Evolution
──────────────────────────────
★ v4 新增: 16 篇进化论文 → 七环节的完整分工 (见 §2.4.5)
   ① 诊断   2606.09498 / 2609.06396 / 2609.14857 / 2609.11873
   ② 对象   2609.24972 / 2606.14249
   ③ 门     2609.24972 / 2606.09498 / 2603.25111 / 2607.12790
   ④ 落地   2609.26457 / 2609.06396 / 2609.08183
   ⑤ 防漂移 2603.06333 / 2609.13406 / 2608.10299
   ⑥ 探索   2609.14858 / 2609.04128
   ⑦ 主体   2609.13406 / 2609.11873
   ★ 另 3 篇是世界模型 (2505.05522 CTM / 2607.27201 MWM / 2607.27924 ODEWorld),
     不属进化环节, 归 L3 层。
   ★ 逐篇深读报告: docs/papers/ (19 份) + 横向对比 COMPARISON.md
   ★ 可执行性分级: 16 篇里方法级可执行的只有 2 篇 (2603.25111 / 2609.13406);
     其余 14 篇是**机制级可照搬** —— 机制照搬, 性能数字一律不照搬。
```

---

## 九、还没定的

```text
已定 (2026-10-03):
  1. 行动者做什么任务?  → ★ 由世界模型生成 (§4.2, 内生事件源)
  3. 锚点任务集构造:    → 复用 ARSI sealed_tasks 15 条起步, 补齐 rung 2

v4 已定 (2026-10-03):
  8. ★ 七环节的器官归属: ⑤→iwm / ⑥→world_model / ⑦→全系统 (§2.4.2)
  9. ★ world_model 补为第七器官 (§2.1, v3 漏了)
 10. ★ 进化对象计数: 34 → 27 (21 对象 + 6 元层, 严格去重后)
 11. ★ 四条不可违反约束 (§2.4.6)
 14. ★ judge 设计定稿 (docs/JUDGE_DESIGN.md): 三件套 + 三 split + 六条判据 J1-J6
 15. ★ actor 设计定稿 (docs/ACTOR_DESIGN.md): 三段式 + 痕迹新 schema + 七条判据 A1-A7
 16. ★ judge 三层定稿 (docs/JUDGE_LAYERS.md): L1 规则 / L2 语义 / L3 环外审计
     + 三条纪律 + 七条判据 J7-J13 (补上 ACTOR_DESIGN §五⑤ 的缺口)
 17. ★ iron_laws 设计定稿 (docs/IRON_LAWS_DESIGN.md): 数据驱动三件套
     (laws.yaml + checks/ + hooks.py) + 十条 check_fn 规格 + 八条判据 I1-I8
 18. ★ 铁律 vs 停止规则的分工: 铁律=永恒约束 / 停止规则=运行期熔断 (5 条)
 19. ★ 事件总线裁决: **不要总线, 要单一因果链** (docs/CAUSAL_CHAIN_VS_BUS.md)
     五环 (决策→行动→痕迹→经验→变更) 共用 chain_id; 只记录不驱动;
     五条判据 C1-C5。★ 用户质疑成立: 驱动时间的是世界模型, 不是总线。
 20. ★★★ 守卫① 的内在矛盾 —— **已裁决** (2026-10-04, 深读 81 轮后)
     裁决: 守卫① 的 conf 改用 **judge 在 dev split 上外测的世界模型准确率**,
           评估时世界模型冻结。不沿用 ARSI 的 self-reported confidence。
     落笔位置: 原则 12 段 + §2.3 "守卫① 可信度门"代码块下方 + 本条。
     三条约束: ① 冻结 (借 2603.19461 imp@k 的 hold-fixed 手法)
                ② 留痕 (wm_version + dev_accuracy + n_samples 进因果链)
                ③ 换手 (judge 读已发生的预测记录, 不听世界模型自报)
     评估频次: **由 iwm 漂移触发, 非固定周期**; 且与退火同步 (早期宽松、末轮每轮测)
     ★ 否掉的两条: 甲(iwm self_trust —— 它量的是 iwm 不是世界模型, 但**结构可抄**)
                     丙(改 confidence 算法 —— 仍由被门控者自算)
     ★ 与第 2 项的关系: b_t 是"每轮可归因编辑数", **不是轮数** ⇒ 不可复用为评估频次
     ★ 新发现的依赖: 本裁决要求 judge 能读到"世界模型历史预测 + 实际结果"的配对记录,
       这是 state schema (§9 第 21 项) 的一部分 ⇒ 第 21 项从"独立待办"升级为
       **守卫① 的前置依赖**。
 21. ★★★ state 的 schema —— **已定** (2026-10-04, docs/STATE_SCHEMA.md)
     四层: State = (S_t, H_t, G_t, X_t)
       S_t = (memory, skills, tools, context) 版本        ← 2608.03392 式(7)
       H_t = (harness, workflow, org) 版本              ← 式(8)
       G_t = 门快照 (wm_version/wm_dev_accuracy/wm_dev_n/theta_dev+kind/
                    gate1_verdict/iwm_verdict/train_verdict/laws_block/laws_warn/b_t/cost_used)
       X_t = (chain_id, decision_id, turn_index, task_id, task_source, split)
     ★ 全部 frozen dataclass ⇒ 铁律阳性测试可构造违规 state (判据 I6)
     ★ 每个字段有唯一写入方 ⇒ 满足判据 I3
     ★ 守卫① 的判据来源: PredictionOutcomePair（预测 × 实际 的配对）
       —— **它是 Trace 的投影, 不独立存储** ⇒ 原则 3 单一真值源成立
     ★★ 实测: dev_accuracy 三态正确 / theta_dev 三分支全部可触发。
       ★ 跑测中修掉一个真 bug: 三分支阈值若用 if/elif 依次比较,
         prev_theta 恒为最大 ⇒ floor 分支永不触发、kind 恒为 anchored
         ⇒ 已改为一次 max(cands, key=...) 并按硬度排序
 22. ★★★ 因果链的存储形态 —— **已定** (2026-10-04, docs/CAUSAL_CHAIN_STORAGE.md)
     三层: L0 热链(内存 ring, 默认 200/chain, 崩溃可丢) 
          → L1 因果链(SQLite 主存, 跨重启) → L2 索引与摘要(SQLite, 只增但小)
     三表四索引: chain(摘要, 带 quality_seq/peak_so_far/gdi_snapshot 供停止规则)
                 chain_record(正文, upstream_id 强制非空)
                 chain_index(kind/key 聚合)
     ★★ 四个索引各对应一个已定消费方（判据 S4 禁止死索引）:
       ix_rec_chain(trace_back) · ix_rec_upstream(失败签名反查)
       · ix_chain_closed(瘦身) · ix_index_kind(签名聚类)
     ★ 修 ARSI 四处硬事实:
       F1 causal_links 零索引 → chain_record.upstream_id 有索引（by_upstream 实测可用）
       F2 traces 表无 chain_id 列 → 结构性缺失, 不是漏传
       F3 五表无共同外键 → 三表以 chain_id 聚合
       F4 无任何 DB 瘦身 → 体积+时间双触发, 且**导出留档不直接 DELETE**
     ★ 瘦身主目标是 chain_record（膨胀源），chain 可永久保留（它小且停止规则要它）
     ★ 层间关系: chain_record 可由 Trace 重建 ⇒ 热链崩溃丢失**不构成数据损失**
       ★★ 硬前提: Trace 必须先于 chain_record 落盘（判据 S5, 需测试验）
     判据 S1-S6 全部新增（与第 19 项的 C1-C5 互补: C 管"链通不通", S 管"存得对不对")
     ★ 实测: DDL + append/trace_back/反查/索引查询全通; S2 阳性测试 raise 生效
     ★ 未定: N0/N_max/retention_days/flush 批量大小（四数是拍的, 须在真实负载调）
  2. ★★ 提案粒度 —— **已定**: 一次改一个, 且用退火预算 b_t (2026-10-04)
     形式（2609.24972 式4, 余弦退火）:
       b_t = ⌈b_min + (b_max−b_min)·½(1+cos(π t/T))⌉,  b_min=1
     ★ 论文原文立场: Ω(H) **保持完全开放**
       （"prompts, control flow, configuration, context management, tools, skills,
         memory, and subagents may all be modified, added, or removed"）
       ⇒ DWC 不限制"改什么", 只**正则化穿过它的搜索轨迹**（稀疏度 + 信用分配）
     ★ 为什么 b_min=1 是对的: 论文的理由逐字 ——
       不约束的 proposer 会把"很多互不相关的修改"捆成一个候选,
       "any measured change is **difficult to attribute to a particular mechanism**"
     ★★ 论文自陈的边界（必须照录）: 这个 L₀ 类比"applies to update sparsity rather
       than to a fixed model parameter vector … **we do not optimize an L₀-penalized
       objective**" ⇒ 它是**正则器, 不是被优化的目标**
     ★ 与 (e) patch_target 的关系: b_t 限制"改几个", patch_target 声明"改哪一层"
       —— 两个正交, 都要

  4. ★★★ 失败签名分类法 —— **已定**: **两层结构** (2026-10-04)
     ★ 这是本轮深读直接改变的项（原答案是"照抄 2609.06396 附录 D 六类"）:
       照抄会丢掉三层漂移的门裁决用途 ⇒ 改为两层。

     【第一层 · 粗 · 用于门裁决与归因】（2609.2680 式 h）
       optimization drift（优化漂移）· information drift（信息漂移）
       · behavioral drift（行为漂移）
       ★ 2609.2680 原话: "grouping them all as collapse **hides where the feedback
         loop fails**" ⇒ 三类分开的目的是定位，不是好看

     【第二层 · 细 · 用于定位与修复】（2603.25681 Figure 9, 7 类 16 子项）
       (i)   Data Autophagy: 模型崩塌 / 灾难遗忘 / Data-Copying / Déjà vu /
              采集受限
       (ii)  Flawed Feedback: 不一致不稳 / 偏置放大
       (iii) Optimization-Driven: 涌现失配 / 奖励黑客
       (iv)  Ineffective Self-Refinement: 自纠边界 / **幻觉性生成-验证鸿沟**
       (v)    Evaluation Bottlenecks: 评估器偏置 / 指标设计缺陷 / 基准污染
       (vi)   Supervision Bottlenecks: 监督无效 / 监督质量有限
       (vii)  Budget Constraints: 强模型依赖 / 迭代算力
     ★★ 两层的分工: 第一层决定"哪类漂移 ⇒ 走哪条停止规则"；
       第二层决定"改哪里" ⇒ 二者缺一则修复是瞎猜

     【签名结构】（2609.06396 附录 D 的三段式, DWC 照搬）
       FailureSignature = (terminal_cause c, causal_role q, reusable_mechanism m)
       ★ 前两段由**规则分类器**填（非 LLM）, 第三段由 LLM 填
         —— 论文原文: "a mechanism that contradicts the assigned terminal cause is
         **rejected at validation**"（一致性检查, 不是正确性检查 —— 报告已照录）
     ★ 落法: Trace.failure_signature（ACTOR_DESIGN §4.3 已定该字段）

  7. ★★ 世界采样策略 —— **已定: 分层, 但 EL 调度器不可直接抄** (2026-10-04)
     ★★ 为什么不能照抄 EL（这是核实后的关键发现）:
       2609.04128 的 EL Scheduler（式2）表面看是"按通过率阈值前进",
       但它的**生理机制完全依赖 GRPO**: 论文原文 ——
         "provides GRPO with more informative learning signals, as more rollout groups
          remain **partially solved and retain non-zero within-group advantage**"
       ⇒ 它存在的理由是"保留组内部分正确的样本以产生非零优势项"。
       ★★ 实测 DWC 架构: "优势" 0 命中 / "advantage" 0 命中 / "组内" 0 命中
         ⇒ DWC 没有 GRPO, EL 的核心机制在 DWC **不存在**
       ⇒ 照抄只会得到"一个没有理由的阈值"

     ★ DWC 的分层形式（保留可抄的部分, 去掉 GRPO 依赖）:
       层1 跨 lineage 采样: 不随机 —— 按 **FWT（未来任务迁移）** 降序,
           偏向"能教会后来任务"的谱系
           依据 2501.07278 式(18) FWT; 且 (bl) 指出"strong forward transfer does
           not guarantee retention" ⇒ FWT 只作**偏置**, 不作**闸门**
       层2 代内环境推进: 保留 EL 的**阈值前进**结构, 但换判据 ——
           用 DWC 自己的 **r̄_solve 区间**（AZR 式 x）替代 p̂_u 与 6/8:
             难度太易 (r̄→1) 或太难 (r̄→0) 都无学习信号 ⇒ 两者都不前进
           依据 2505.03335: "either trivial to solve or unsolvable … provides little
           to no learning signal" ≡ 2603.25681 §3.3.4 curriculum 判据（两文同构）
       ★⇒ DWC 版本 = "**中间难度带优先**", 不是"高通过率才前进"
          ⇒ ★ 与 EL 的方向**相反**: EL 跳过太难的, DWC 跳过太易与太难的
       ★★★ 2026-10-04 补来源声明（解决与第 25(b) 的一处真实矛盾）:
         第 25(b) 曾写「当前**无 solver 概念**」⇒ 与本项用 r̄_solve 矛盾
         ⇒ ★★ 裁决: r̄_solve = **该任务在组内历史中的通过率**,
           由 C3' 的 TaskScorePoint 分数序列直接算出（实测: 三个样本全可算）
         ⇒ ★★ **不需要 solver 概念** ⇒ 本项成立
         ⇒ ★ 但符号是借 AZR 的, 来源此前未定义 ⇒ 此处补齐（判据 Q2）
         ★ 实测局限: 我取的三个样本 r̄ 全落在中间带,
           未覆盖「太易/太难」两端 ⇒ 该判据两端未实测

     ★ 诚实: 这条是我的重构, 不是论文原文。EL 的 B=8 / τ=6/8 两个数字**不适用**
       （那是 GRPO 的组大小与阈值）。DWC 的对应参数未定
       ★★★ 更正: 此处原写「依赖第 5 项（消费点验证）」, 而第 5 项**已于本日已定**
         ⇒ ★ 该依赖已解除（详见 docs/CONSUMER_VERIFICATION.md）
  5. ★★★ 消费点如何验证 —— **已定** (2026-10-04, docs/CONSUMER_VERIFICATION.md)
     ★★★ 三级验证（缺一级则对应缺陷复发）:
       Level 1 解析验证（写之前）: resolve(path) 非 None 且 getattr 不抛
         ⇒ 不许 is-None-continue —— 母巢 gene_applier L193 就是 continue,
           路径写错 ⇒ 基因永远不生效且**不报错**
           ⇒ ★ 这正是「写了没人消费」的**生成机制」：不是没接, 是接不上且不吭声
       Level 2 写后读回（写之后立即）: 读回 == 期望值
         ⇒ 母巢 `_applied += 1` 紧跟 setattr（L197）, **无任何读回**
       Level 3 行为验证（下一轮运行时）★★ 新增, 母巢与 ARSI 都没有
         ⇒ 读回成功只证明「写进去了」, 不证明「有人在用」
         ⇒ 判据直接复用原则 9 的纪律（必须有一处门控决策的消费点）
           在基因上的应用 ⇒ 不新增概念, 只新增检查对象

     ★★ verify 必须分两型（**实测证实**, 不是推测）:
       直写型: |readback − candidate| < tol
       变换型: |readback − transform(candidate)| < tol
       ★★ ARCHITECTURE §4.4 现有写法在变换型上**恒失败**:
         母巢 stability_factor 候选0.9 → merge_threshold_from 写入 0.70
         ⇒ |0.70−0.9| = 0.20 > tol ⇒ 照搬会立刻失效
       ★★ 且越界候选必须先 clamp 再比对:
         候选0.99（range 上界0.5, 母巢 _clamp 会夹到0.5）
         ⇒ 现有写法判失败, 但**实际写入是对的** ⇒ 误判
       ⇒ 正确期望: expected = transform(clamp(candidate)), 顺序不可换
         （母巢 _clamp 作用于基因值, merge_threshold_from 也吃 clamp 后的值, 已核 L138+L191）
       ⇒ tol 按值域取（浮点1e-9 / 映射后1e-6 / 枚举用 ==）, 不一律 1e-9

     ★★ 五态结果（关键的坑在最后两个）:
       applied(写入+读回一致, L3 未跑) · verified(三级全过)
       · rejected(门拒, 正常) · failed(技术失败, 已回滚)
       · ★★ unverified(L3 未观察到消费 = **死基因**) —— 它不是 failed
         ⇒ 必须与 failed 分开统计, 否则死基因被混进技术失败里看不见
         ⇒ 依据原则 4: 无消费点的产物不许进准入流程
     ★ 记录: ConsumerAudit 进因果链, 须支持按 outcome 聚合查询（否则查不出死基因）
     判据 V1-V6（同族分工: C管链通不通, S管存得对不对, V管写没写活）
     ★ ✓✓ A7 已解（2026-10-04, docs/LEVEL3_PROBE.md）: Level 3 **可实现**
       ★★★ 当初「决策点形态未定稿」的阻塞理由**不成立**:
         决策点已隐含在 §4.2（actor 三段式 + 决策优先级 + 三分离）:
           ① sample_gate ← ① 段「legal_actions() → 采样（EL 调度器）」
           ② source_gate ← ② 段 decide「预测（有门控）→ LLM → 启发式」
           ③ action_gate ← ② 段 act（甲任务动作 / 乙维护动作）
       ★★ 三个真问题:
         · 归因混淆: |编辑集|>1 ⇒ unverified + reason="multi_edit"
           （不新增第六态 —— 新增会破坏 outcome 的可聚合性）
         · 窗口长度: window_rounds 上限 = term 边界（A5 已定）
           ⇒ ★★ A5 成为 L3 的依赖 ⇒ 依赖链闭合
         · 观察≠因果: 只要求「在决策中被读到」, 不要求「决定了决策」
           （FWT 只作偏置 ⇒ 强形式不可证 ⇒ 有意的保守不足）
       ★ unverified 四种 reason: multi_edit / window_expired
         / probe_missing / gate_silent
       判据 L1–L6（同族第十二族: L 管探针的存活性）
       ★★ 未解决: action_gate 的归因混淆; 未定: window_rounds 具体值
       因为"通过"本身要先有判据。


  ★★ ★★ 进度判据（2026-10-04 清点后加）:
      ★ **不要用"本段还剩几项"判断进度** —— 实测本段曾只剩 23/25,
        而"世界树收束"议了三轮从未登记为待办项 ⇒ 漏了整整三轮。
      ★ 真实进度表: docs/GAP_AUDIT.md（缺口清点表, 20 处标记 + 69 条子条目全扫）
      ★★ 目录导航: docs/INDEX.md（★ 开工先看; 别通读 docs/ ——
        docs/repos/_all.json 是 3.4 MB 的仓库全文抓取, docs/lessons/_tmp_hits.txt
        是 726 KB 的 grep 原始输出, 两者都不是设计文档）
      ★ 本段只登记"曾有编号的待办"; 议定但未编号的项在 GAP_AUDIT 里。


待定 (v4 更新):
  25. ★★ 2609.2680（RSI 综述，2026-10-04 深读）暴露的三处缺口 —— 待裁决
      ★ 这是 DWC 进化核心的**协议层上位框架**，与已定设计有三处不一致:

      (a) ✓✓【已裁决 2026-10-04, docs/CLAIM_SEPARATION.md】三主张分离
          ★★ 25(a) 点出两处影响, 裁决如下:
            · 守卫① 该用哪个量? ⇒ ✓✓ **已答且答案是"都不用"**
              第 20 项已定用 judge 外测的世界模型准确率（Pair.is_correct）
              ⇒ ★★★ 那是"世界模型质量", 不是 Γ_t（改进器增益）
              ⇒ ⇒ 守卫① 判的是"能不能信世界模型", Γ_t 判的是"改进器有没有变强"
              ⇒ ⇒ ⇒ 两者**不是同一个问题** ⇒ 不构成冲突
            · L3 应测 Γ_t 还是 Δ_t? ⇒ ★ 裁决: **L3 测 Δ_t, Γ_t 只作报告**
              （理由见 (b) 的三条障碍 + 原文 "under that probe"）
          ★★ 25(a) 唯一**未被任何已定项覆盖**的部分:
            judge 的 Verdict 必须带 claim_type ∈ {task_gain, retention, improver_gain}
            ⇒ 必须补（判据 Q1）
          原文逐字（已核 2609.2680 §3.4）:
            "Neither positive ∆_t nor positive τ_t **isolates the improver**."

          原文 §3.4: Δ_t（任务增益, 式5）/ ρ,τ（保留与迁移, 式6）/
                     Γ_t（改进器增益, 式8 配对探针）
          ★ 原文明说: "Neither positive Δ_t nor positive τ_t isolates the improver."
          ⇒ 影响两处:
            · §9 第 20 项（守卫① 矛盾）: 守卫① 该用哪个量?
            · JUDGE_LAYERS 的 L3: 应测 Γ_t 还是 Δ_t?
          ★ 倾向: L3 测 Γ_t（配对探针），因为它才归因到"改进能力"

      (b) ✓✓【已裁决 2026-10-04, docs/CLAIM_SEPARATION.md】Γ_t —— **降级为报告量**
          ★★★ 三个障碍的实测结果:
            障碍1 起始态 S 可复现性: ★★ **实质障碍**
              原文硬要求 "Controls must match **starting states**"
              ★ DWC 的 S = task + state + memory 工作态, 而 memory **历史累积**
              ⇒ 无法从同一 S 重跑 ⇒ ★★ Γ_t 算不出来
              ⚠ 我原写的"对齐代价随历史线性增长"这条成本论证**已撤回**
                （实测发现是空转循环造成的假象）⇒ 只剩"不可复现"一条理由
            障碍2 resource accounting: ✓ **DWC 已解决**
              ERROR_AND_TERM 已定双成本台账, cumulative_cost 可裁到同预算
            障碍3 I_0 是什么: ✓ **DWC 天然具备**
              I_0 = current harness; §9 第 5 项已定"候选集必含 current"
          ⇒⇒★ 裁决: Γ_t **不进 gate**, 只作 TermReport 的诊断量
            理由二: 原文自称 "under **that probe**" ⇒ 是特定探针下的结论, 非普适判据
            理由三: G11 已定"门通过 ≠ 系统安全", 而 Γ_t 正是那种探针结论
          ★★ 与 PredictionOutcomePair 的关系（逐项对照）:
            Pair 内层: "wm 预测 effect 与实际 effect 之差" ⇒ 问「世界模型准不准」
            Γ_t 内层: "从同一起始态 S 出发, I 选的后继比现状好多少" ⇒ 问「改进器强不强」
            ⇒ ★ 结构同构, **但问的不是同一件事** ⇒ 可共用数据, 指标不同
          ★ ★★ Q5: Γ_t 必须带 uncertainty
            原文逐字: "**Positive Γ_t with appropriate uncertainty** supports a
            stronger improver" ⇒ 缺不确定性的 Γ_t 是半个结论
            ⇒ 若算不出 ⇒ 字段必须是 None 而非 0（与 C3' 的 NaN 同款纪律）
          ★ 另: 25(b) 原写「当前无 solver 概念」与第 7 项用 r̄_solve 矛盾
            ⇒ ★★ 已核并裁决: r̄_solve = 组内历史通过率, 由 C3' 数据算出
            ⇒ **不需要 solver** ⇒ 第 7 项成立（来源声明已补, 判据 Q2）
          ★ 残留未解: "reader 集合 == {审计报告}" 与 "Γ_t 只作 TermReport"
            的边界未划清 —— TermReport 是"报告"还是"数据"?
          ★ 论文原式（保留备查, 已逐字核 2609.2680 §3.4）:
          Γ_t(B) = E_{S~P_start}[ g(I_t; S, B) − g(I_0; S, B) ]
          g(I; S, B) = E[ Q(S⁺(I;S,B); D_test) − Q(S; D_test) ]
          ★ 硬要求: "Controls must match starting states, feedback access and
            resource accounting." ⇒ 同一 held-out 起始态 + 同预算
          ⇒ 这比 WORLD_MODEL_AUTHORITY §四 的"乙方案（滑动准确率）"更精确
          ★ 待定: DWC 能否构造"同一 held-out 起始态"?（当前无 solver 概念）

      (c) ★★★ 保护组回归约束 r̂_{t,j} ≤ ϵ_j —— **已定** (2026-10-04, docs/REGRESSION_GUARD.md)
          §7.2 式9 的完整验收门:
            A_t = 1{ Δ̂_val ≥ η_t ,  r̂_{t,j} ≤ ϵ_j ∀j ,  C_{≤t+1} ≤ B }
          ★★ 它防的是什么（SAHOO 原文 D.1）: "regression: the phenomenon where
            quality improvements in later cycles are **undone by reversion to earlier
            behaviour**" ⇒ ★ 进化特有失效, 单轮 Δ̂_val 完全看不出

          ★★ 两种判据并存, 不二选一:
            【主·事前预警】SAHOO Eq.18-23
              R_c = Pr(Q_c < Q_max − δ | H_c)         Eq.18
              σ = std(H_c) · Q̂_t = α+βt · z=(Q_c−Q_max)/(σ+ε)   Eq.19-21
              R_c ≈ Φ((Q_max−δ−Q̂_{c+1})/σ)           Eq.22
              R_c^adj = min{1, R_c + 1{β<−ε_trend}·λ|β|}   Eq.23
              D.4 停止规则: R_c^adj ≥ τ_R ⇒ 警告 + 考虑暂停
            【辅·事后审计】FGT (2501.07278 式16) + BWT(17) + FWT(18)
            ★ 主辅分工: SAHOO 事前（可作门预警）· FGT 事后（趋势图）
            ★★ FGT 的一个真实弱点（实测证实）: 退化后恢复到峰值 ⇒ FGT 归零
              实测 0.9→0.5→0.9: t=1 FGT=0.4000, t=2 FGT=0.0000
              ⇒ 若要审计"曾退化过"这件事, 必须配时序指标
            ★ ★ 已撤回一个自造结论: 我原写"峰值锚会掩盖持续小退化"
              实测 0.50→0.51→0.52→0.40 ⇒ t=3 FGT=0.1200（能报出）⇒ 不成立

          ★★ ϵ_j 双轨（照守卫① theta_dev 结构, 防自我设限/温水煮青蛙）:
            ϵ_j = max( ϵ_floor_j , κ_r·rolling_Rmean_j , prev_ϵ_j )
            ★ ϵ_j 就是 SAHOO 的 δ（"what counts as a meaningful regression"）
              原文明说 δ 按组定 ⇒ 每组可有各自的 ϵ

          ★ 能力组定义（DWC 侧, 论文没给）: 可独立评测的能力维度 j,
            须满足 ① 有 sealed 评测集 ② 有历史成绩序列 ③ 组间不重叠
            候选必须声明 protected_groups: set[str], 空声明不许进门
            ★ 与第 2 项正交: b_t 限"改几个", protected_groups 限"不能弄坏哪些"

          ★★ 另两条同源要求同时落地:
            · 三态保留: accept / 保持现状 / **入 archive 待选**（applier 缺入档）
              ★★ 与 DGM Table 1 的 +27.0pp 直接相关 ⇒ 入档不是可选, 是主要收益路径
            · "failed attempts and their costs also require recording"
              ⇒ 成本台账补"被拒候选"（与第 5 项五态同源）
            · 成本报**向量**不报标量（式10 四分量 c_proposal+c_train+c_validation
              +c_execution）: "report a **resource vector** rather than add unlike units"

          ★★ eps 正则项是**必需**不是可选（实测）: eps=0 且 σ=0 ⇒ ZeroDivisionError
            ★ DWC 质量序列是阶梯函数（母巢 score_in 教训）⇒ σ 常为 0
          判据 R1-R6（同族分工: C管链通不通, S管存得对不对, V管写没写活, R管退没退）
  6. ★★★ 器官接口契约 —— **已定** (2026-10-04, docs/ORGAN_INTERFACES.md)
     ★★★ 先说一个动笔前查到的真实情况:
       JUDGE_DESIGN / ACTOR_DESIGN 给的都是 **ARSI 侧的被审计对象**
       （SealedEvaluator 的 docstring、core.step() 骨架）,
       **不是 DWC 的接口签名** ⇒ 第 6 项是"从零落签名", 不是"补文档空缺"
     ★★ 六条通用约定（七条接口共同遵守）:
       ① 入参出参一律 frozen（STATE_SCHEMA §八 的理由）
       ② 返回值必须带证据, 不许裸成功（judge "never blind SUCCESS"）
       ③ 不许用 None 表示失败 ⇒ 与"未评价/未运行"混淆（约定③）
       ④ 跨器官只传 ID 不传对象 ⇒ ★ 结构性禁止循环 import
       ⑤ 长耗时可中断且声明预算（b_t + 式10 成本向量）
       ⑥ 每个接口都要有负面测试（判据 I6/S2 同款: 只测通过等于没测）

     ★★★ 七条签名（要点, 全文见文档）:
       memory     ingest/recall/distill/forget/stats —— ★ 七管只暴露五个方法
                  （流程可多, 接口要少: 否则能从任意管切入, 绕过不变量）
                  不变量: 失败痕迹必须带签名 · 经验必须登记链 · 淘汰前查来源
       world_model predict/current_version/trust/train
                  ★★★ predict **不许返回 confidence**（第 20 项裁决的接口级锁定）
                  trust = 守卫① 判据源, 三个约束在此落地（冻结/留痕/换手）
       judge      verify_L1/verify_L2/verify_L3/dev_accuracy/wm_pairs/seal_check
                  ★ wm_pairs 是守卫① 的数据源（Pair 是 Trace 的投影, 不新造数据）
       evolver    diagnose/propose/gate/apply —— ★ 七环节只四个入口
                  不变量: Manifest 必声明 protected_groups + target_layer;
                         |manifest| 受 b_t; gate 必同时读三项判据;
                         三态保留含"入 archive 待选"（+27.0pp 靠它）
       iwm        governor_advice/self_trust/drift/probe
                  ★★ advice 不得读 world_model 内部状态（第 20 项的根源）
                  ★★ self_trust 量的是 iwm 自己, **不可**用于守卫①（已否决候选甲）
                  ★★ drift 输出必须被门控消费, 不许只做账本（原则 9）
       iron_laws  check/register_protected_path/report —— 横切, 唯一可拦截全部
                  ★ check 必须返回 pass/warn/block **三组**（判据 I2）
       环节⑦      run_term(ctx, world) → TermReport
                  ★★ 末不是"结算"而是"生成下一轮任务源"（缺口 bz）

     ★★★ 全器官调用图固定了三条数据流向:
       ① 守卫①: judge.wm_pairs → evolver → world_model.trust
          ⇒ ★ world_model 永不主动读 judge 的存储（约定④）★ 实测已验
       ② 铁律: check 被所有器官在 write/call 前调, 但只读 State 公开四层
       ③ 环节⑦: run_term 输出 → 下一轮 world_model 的输入

     判据 P1-P8（同族分工再加一族: P 管接口纪律）
       P1 不许 organ_B._private_attr（原则6 可执行形式）
       P2 跨器官只传 ID 不传实例  P3 不用 None 表示失败
       P4 ★★ Prediction 里不许有 confidence（一加, 守卫① 矛盾就回来）
       P5 check 调用点 >0 且覆盖七器官   P6 成功必带 evidence
       P7 每接口有负面测试              P8 L3 调用点 ⊆ {audit}
 12. ★★★ m 与 U 的实现形态 —— **已定** (2026-10-04, docs/MODIFIER_CRITIC.md)
     ★★★ 动笔前核原文, 发现三处必须纠正:
       ①★★ "authority boundary" 在 GAI 全文 **0 命中**
          ⇒ ARCHITECTURE §2.4.3 写的「GAI Figure 2 原文: 环上恰好一条
            authority boundary」是**误引**（我自己早前写下的错误）
       ②★ GAI 的真实机制是**两个 dial**, 不是"一条边界":
          Dial 1 m∈Ag?  「with the modifier inside the agent it is **recursive
                 self-improvement**」/「m ∉ Ag … acts as an **external improvement
                 mechanism**」
          Dial 2 ρ grounded? 三档原文: 「draws its content from outside **and the base
                 itself lies outside the agent**」/「draws from outside but **that the
                 agent may rewrite** can **move under the system's own edits**」/
                 「**no external content at all constrains the loop by nothing beyond
                 self-consistency**」
       ③★★ "m 与 U 必须分离"**不是 GAI 的硬约束**:
          Definition 1 原文「an instance **may leave some of them unused**, as the
          modification critic U is when the modifier is fixed」

     ★★ 那 DWC 为何仍分两模块? 依据换成 DWC 自己的:
       · 签名根本不同（Definition 1）: m: X→Δ(X_Ag) 输出分布 / U: X→ℝ 输出标量
       · ★★ 若同模块既提议又裁决 ⇒ 撞 DWC **原则 1**（判据必须在系统之外）
         ⇒ 这才是真依据, 不是 GAI 的 Figure 2
       · 与 §4.1 judge 纪律 2 同源（分模块让"读者集合"可检查）

     ★★★ 分离的实质不是文件名, 是依赖方向（实测已验）:
       判据 M1: critic.py 的 import 不含 Modifier（实测通过 + 反例被抓）
       判据 M2: critic.evaluate 调用链不含 modifier.propose
       ★ 分两个 .py 只是工程结构; GAI Dial 1 问的是"m 能否改自己"

     ★★ 两个 dial 的 DWC 取值（显式声明, 落 config/dials.yaml）:
       m_in_agent = true            ⇒ DWC 是**递归自改进**（自举）
       rho_grounded = true          ⇒ 条件① 内容来自系统外 ✓ judge sealed split
                                     条件② base 本身在 agent 外 ✓ seal + 铁律G10
       rho_agent_can_rewrite = false ⇒ 明确拒绝"外部内容但 agent 可改"那一档
         （落入该档即 §2.4.6 约束 2 违规, 依据 GAI "move under the system's own edits"）
       ★★ 这比"分两个文件"重要得多 —— 必须落进五元盘点 χ 的每次报告
     落点（§11.2 已定, 本项确认）: evolution/modifier.py + evolution/critic.py
     判据 M1-M6（同族第六族: M 管提议/裁决分离）
     ★ 实测: M1(含反例)/M3/M4/M5/M6 全通; M2 未测（需全量调用图 grep）
     ★ 未定: Critic.aggregate 的口径（标量? 效用加权? 非补偿六步的哪一步?）
       —— 与 §9 第 2 项交界, 未明文

 13. ★ 目录结构 → ★ **已定**（见 §11, 2026-10-03, 本轮复核确认无冲突）
     ★ 复核发现并已修正一处命名冲突: 曾误写 stage5_antidrift/,
       与环节⑤ 既有 stage5_drift/ 冲突 ⇒ 已统一为 stage5_drift/
     ★ 仍余留: run_term 与 actor.step() 的内外层关系未定
       （见 ORGAN_INTERFACES §十三 诚实边界⑧）



     ★★ 跑测抓到一个**真实的浮点陷阱**（已同步修正 STATE_SCHEMA）:
       abs(0.79-0.8) = 0.010000000000000009 ⇒ <= 0.01 判 **False**
       ⇒ ★★ 严格相等作默认是错的; 同一份数据 tol=0 判 acc=0, tol=0.02 判 acc=1
       ⇒ is_correct 的 tol 默认已从 0.0 改为 0.02, 且 tol 必须落进 TrustVerdict
     ★ 顺带修一处命名冲突: 我上轮写的 stage5_antidrift/ 与既有 stage5_drift/
       冲突（环节⑤ 已有 GDI）⇒ 已统一为 stage5_drift/
     ★★★ 2026-10-04 已定两项（docs/ERROR_AND_TERM.md）:
       · 错误处理二分: 判据 = **失败后调用方是否还有事可做**
         raise 三类（铁律违规/契约违反/不变量破坏）
         vs 返回五类（门未通过/验证不可用/证据不足/探针未命中/环境可降级）
         三种异常类型: LawViolation / ContractViolation / OperationalFailure
         ★★★ 实测硬要点: **"门未通过"不是违规** —— 写成 raise 会让失败量级差一个数量级
         判据 E1-E6（E3 禁 except:continue/logger/pass —— 含 ARSI 的 default:return False）
       · run_term 与 step 的层级: **run_term 在外, step 在内**（照抄 ARSI core.py L927）
         六步: before快照/n×step/after快照/五元盘点/生成下一轮任务源/G11门报告
         ★★★ 相对 ARSI 三处有意分歧:
           ① 双成本台账（term_cost reset + cumulative_cost 不 reset）
              理由: 25(c) "failed attempts and their costs also require recording"
           ② after 快照后是"生成下一轮任务源"不是"结算"（缺口 bz）
           ③ term 内锁 dw_version, 变了则本 term 报告无效（G11 配套3）
         ★★ term 边界由**进化事件**决定, n_steps 只是兜底上限
           （ARSI 的 n_steps=10 是硬编码默认值 ⇒ 不继承）
         判据 T1-T4
     ★ 仍未定: predict 是否真不需要 Ψ 未验证


          ★ ✓✓ A6 已解（2026-10-04, docs/CAPABILITY_GROUPS.md）:
            能力组划几组 → **三组，沿用 ARSI 既有 category**（15 条逐条核）
              code_repair(6) / knowledge_reasoning(6) / paper_reproduction(3)
              ★ 不新建概念 —— category 字段本来就是组, DWC 只需显式声明 + 加固
            ★★ Λ 改为**断言计数**口径（单位="个断言"）: Λ_assert = {1, 2, 1}
              依据: 实测 1/median = 0.500 / 0.286 / 0.500 ⇒ 分数口径 Λ=0.03
                    在三组上**全部是死判据**
            ★★★ G3 判据抓到我自己一个真错误: median 写成 4（上中位数）,
              实测标准中位数是 3.5 ⇒ 已修正
            ★ 判据 G1–G6（同族第十族: G 管组的完整性）
            ★ 组数上限 = 15/n_min(3) = 5 ⇒ 加第 4 组需 ≥3 条新任务
            ★★ 遗留: 三组敏感度不等（λ 2 vs 1）, 而门是非补偿的
          ★ 未定: τ_R 与 λ 的值（论文只说"由校准得出"）; 三组的 λ_assert 校准

      ★ 另有三条可直接吸收的（非缺口，是增强）:
        · 四分量成本台账（式10）: c^proposal + c^train + c^validation + c^execution
          ★ 且 "report a resource vector rather than add unlike units"
        · "Unevaluated tasks should not silently become measured failures."
          + "audit selected artifacts on a **common population**"
        · "Baselines also need a functional opportunity to improve"
          （基线不许被格式问题卡死 —— 否则对照无效）

      ★★ 第二轮 14 轮逐行深读后新增的 8 条（2026-10-04）:

      (d) ★★ 记忆"内容 vs 管理机制"必须可单独冻结
          §6.2 原文: "The critical intervention **separates stored content from the
          mechanism that manages it**. Removing both at once cannot establish which
          produces the gain. A practical comparison **freezes one of admission,
          retrieval, consolidation or content while varying the others**."
          ⇒ DWC 接口: 记忆四干预点 {admission, retrieval, consolidation, content}
            必须可单独冻结, 否则消融无法归因。
          ★ 且: "a library can **grow while becoming less useful**"（库规模不是指标）
          ★ 且: "An improved memory policy **becomes an improver component** when it
            determines how future experience produces future updates."
            ⇒ DWC 的记忆管理算法（不只内容）是合法进化对象

      (e) ★★ 两层补丁必须区分
          §6.3 原文: "a patch to **a target repository** vs a patch to **the agent that
          writes repository patches**. **Only the latter directly changes the
          update-producing machinery.**"
          ⇒ DWC 接口: 每个候选变更声明 patch_target ∈ {task_artifact, improver_code}
            只有后者进 Γ_t 评估（前者只算 Δ_t）
          ★ 与 DWC 的 8a/8b 拆项（架构-组织 / 架构-结构）同构

      (f) ★★ "无新反馈"对照组必须存在
          §8.1 原文: "Track independent quality, acceptance errors and recovery across
          rounds, **including a no-new-feedback condition**."
          ⇒ DWC 的对照设计缺这一臂 —— 没有它无法证明外部反馈真有用

      (g) ★★ 目标演化必须双记
          §6.5 原文: "Record progress under **both the revised objective and a stable
          external reference**. Otherwise, **a change in what the loop values becomes
          indistinguishable from improved ability to achieve a fixed goal**."
          ⇒ DWC 接口: 每次判据变更, 新旧判据下**同时**记录
          ★ 且: "**Internal judges can evolve while the independent reference remains fixed.**"

      (h) ★★ 三类漂移必须分开（对应 §9 第 4 项 失败签名分类法）
          §8.7 原文: "**Optimization, information and behavioral drift**. Campaign-level
          self-regression, loss of training knowledge and exploration collapse concern
          **different states and timescales**."
          ★ "grouping them all as collapse **hides where the feedback loop fails**."
          ⇒ DWC 的失败签名分类应至少区分这三类, 不能都叫"退化"

      (i) ★★ 稳定性是度量属性, 且需三个新观测量
          §8.3 原文: "**Stability is a measured property over a stated horizon, not a
          consequence of recursion.**"
          ★ 且: "**Recovery time, lost skills and post-recovery quality** matter alongside
            the latest task score."
          ⇒ DWC 的 GDI 四信号之外, 加"恢复时间/丢失技能/恢复后质量"

      (j) ★★ 三类度量不可互换（judge 设计）
          §6.4 原文: "Track **actor outcomes, judge calibration and the downstream
          usefulness of feedback** as separate measurements."
          ★ "**Agreement can indicate consistency without establishing correctness.**"
          ⇒ DWC 的 L2 语义 judge 的自一致性**不能**当正确性证据

      (k) ★★ 后代评估消耗同一预算
          §6.5 原文: "Evaluating descendants can improve selection but also **consumes
          the very budget against which improvement efficiency is measured**."
          ⇒ DWC 的成本台账必须把"评估后代"计入, 否则效率被高估
          ★ 同源: §5.3 "A proxy can reduce search cost while **misranking** the eventual
            deployment candidates."

      (l) ★★ 三描述符完全缺失（§4.1）—— 第 21 轮新发现
          原文: "Each configuration also receives **three descriptors**.
            · **Feedback**: ... and **whether each signal trains, proposes or selects an update**.
            · **Persistence**: the **task, session or training boundary** across which state survives.
            · **Control**: **editable proposal, training and selection components** alongside
              **fixed objectives, tools and budget rules**.
            A label such as self-training or self-modification **leaves these descriptors
            undetermined; they must come from the implementation**."
          ★ 实测: DWC 的 11 份文档对这四组概念 **0 命中**
            (trains/proposes/selects · task/session/training 边界 ·
             editable/fixed 清单 · "描述符必须来自实现")
          ⇒ DWC 接口: 每个进化配置必须声明三个描述符, 缺任一 ⇒ 不许进对象清单
          ★ 且 §2.1: 分析单位是**配置**不是论文/机制名
            ⇒ 直接影响 §7 维度表（34→27 是按"机制名"枚举, 应改按"配置"）

      (m) ★★ 分析单位是"配置"（§2.1）—— 第 21 轮新发现
          原文: "Our unit of analysis is a **concrete configuration**, with a specified
          update target, feedback source, retained artifact and externally fixed conditions.
          A paper can describe several configurations, and **one configuration can serve
          both design and repair**."
          ⇒ DWC 的进化对象清单应以"配置"为单位

      (n) ★★★ imp@k = Γ_t 的可运行实现 ⇒ (a)(b) 有答案了【2603.19461 §5.1 逐字】
          定义: "We define imp@k as the improvement in test performance from the
                 initial task agent A to the best-performing generated task agent
                 (selected based on validation score)."
          ★★ 隔离手段（关键）: "To isolate the meta agent's ability to improve task
            agents from its ability to improve itself, **we hold the meta agent fixed
            throughout the process**" ⇒ I_0 就是"冻结身份的那份改进器"
          ⇒ **裁决建议**: (a) 测 Γ_t, 实现方式 = 冻结 meta agent 身份 + 换手评分
            ★ 这与第 20 项（守卫① 用世界模型自算 confidence）**同源同解**:
              两者都是"让同一状态既执行又评分", 而 imp@k 的解法是**冻结身份**。

      (o) ★★ imp@k 必须报 CI, 单点值不可用于门裁决【2603.19461】
          实测: 初始 meta agent  imp@50 = 0.0  (CI: 0.0 – 0.0)
                迁移 meta agent  imp@50 = 0.630 (CI: 0.540 – 0.630), p < 0.05
          ★ CI 上界 = 点估计（5 次重复运行取中位）
          ⇒ DWC 的 GDI/门裁决若用改进器增益类数字, **必须带 CI**

      (p) ★★ 归档非贪心是最大收益源, 不是装饰【2505.22954 Table 1 逐字】
          Method                              SWE-bench   Polyglot
            DGM                                     50.0%      38.0%
            DGM w/o Open-ended exploration           23.0%      14.0%
            DGM w/o Self-improve                    39.0%      28.0%
            DGM Greedy                              39.7%      30.0%
          ⇒ 归档非贪心 = **+27.0pp**（去 OE）/ 贪心 = **+10.3pp**
          ⇒ 改自己代码 = **+11.0pp**
          ★★ 优先级结论: **先投归档多样性, 再投"改自己的代码"**
          ★★ 对 DWC 的意义: 世界树/归档是进化核心的**第一优先**, 不是附属存储
          ★ 诚实项: 这四个数是**单次结果**, 未报方差; w/o self-improve 复刻的是
            ADAS, 不是"什么都不做" ⇒ 不可据此得统计结论

      (q) ★★ 阶梯评测协议（小集筛→大集精评）【2505.22954 §4.2 逐字】
          SWE-bench: "if a coding agent achieves over 40% success ... on the 60-task
            subset **and ranks among the top two performers in the archive**, it is
            then evaluated on 200 tasks (140 plus the previous 60)"
          Polyglot: "over 40% success on the 10-task subset → expanded 50-task subset"
          ★ 门槛 40% 原文自陈是 "a heuristic chosen based on the noise observed in
            preliminary runs"（启发式, 非理论值）
          ⇒ DWC judge 的 split 应是**三层**（筛选/开发/密封）而非现有三层之二

      (r) ★★ task agent 与 meta agent 必须同处一个可编辑程序【2603.19461】
          "Because both evaluation and self-modification are coding tasks, gains in
           coding ability can translate into gains in self-improvement ability.
           **However, this alignment does not generally hold beyond coding domains.**"
          ★★ DWC 的任务就是"自我改进"本身, 不是编码 ⇒ **DGM 的同域对齐前提对 DWC
            不成立** ⇒ +11.0pp 不可直接外推
          ⇒ 结构结论: m/U（改进器/改动评估器）虽分离, 但必须**同处 evolver**,
            拆成独立模块则 imp@k 类归因不成立 ⇒ 直接裁决第 12 项

      (s) ★ 跨域基准的 0.0 起点是**格式不符**, 不是能力为零
          原文: "it fails to produce outputs in the required format due to the lack of
                 task-specific parsing or post-processing"
          ⇒ DWC 失败签名必须区分"能力不足"与"接口/格式不通"
            （ACTOR_DESIGN 的 expected-observed 能承载, 但 §9 第 4 项未列此类）

      (t) ★★ 验证层级四层 ⇒ DWC judge 三层的**外部校准依据**【2607.07663 §5.2 逐字】
          L4 formal verifier > L3 execution feedback > L2 learned judge > L1 intrinsic
          原文: "demonstrated self-improvement strength tracks this hierarchy"
          ★ 但作者自我限定: "a qualitative pattern ... **not a measured law**"
          ★ 关键限定: "The hierarchy ranks signals **given a target**; the choice of
            target is **prior to it** rather than a rung of it"
          ⇒ DWC 用法: 逐条铁律问"能否升级到形式验证层?"
            不能 ⇒ 永远受 L2 上界约束 ⇒ 必须配 L3 独立审计

      (u) ★★ Mirror Loop: 无外部接地 ⇒ 信息变化衰减 55%【2607.07663 §5.2 逐字】
          "finds informational change **declining 55% across iterations** — recursive
           self-evaluation without external feedback **yields reformulation, not
           progress** — while a **single minimal grounding intervention** (one
           verification step at iteration three) **restores forward movement**"
          ★★ 这是 (f) "无新反馈对照组" 的**镜像实证**: 不只该设对照, 该有目标数字
          ⇒ DWC 应能复现"去掉一次外部验证 ⇒ 增益消失", 衰减量级对标 55%

      ★ ★★ 一条正面冲突必须裁决:
      2607.07663 §5.1: 领域集体答案是"**用同样的循环改进评判器**"——
        Deep-research 自演化 rubric [61] / 自训练验证 [92] / 评判评判者 [122] /
        Red Queen 共演化准则 [62]
      vs DWC 原则 12: judge 不得自评
      ★ 两者不是矛盾而是分工, 但必须写清边界:
        "改进评判器"改的是 judge 的**策略/提示/权重**（其改进仍需外部评测）
        "judge 自评"是 judge 给自己打分（不可归因）
      ⇒ 否则原则 12 会被误当作过时保守

      ★★★ 本轮 5 篇精读新增 6 条（与 (a)-(u) 并列, 未定但可直接抄）:
      (v) ★★ 归档**消费方式**比"是否剪枝"更关键【2408.08435 vs 2505.22954 对照】
          ADAS 归档真无剪枝: prune 0 / pruning 0 / remove 0 / discard 0 / filter 0
          ("top-" 仅 1 处, 是生成 agent 内部的 ensemble, 与归档无关)
          DGM 靠归档非贪心拿 +27.0pp【2505.22954】
          ⇒ 差异变量不是剪枝, 而是: DGM **从归档采样**, ADAS **把归档喂给 meta
            agent 当条件**（§3 "Conditioned on the archive, the meta agent designs..."）
          ★ 对世界树的含义: 收束策略要声明"归档怎么被消费", 不只声明"留哪些"

      (w) ★ 新颖性也要检 + 失败有重试上限【2408.08435 §3 逐字】
          "(2) ... The design then undergoes **two self-reflection steps** by the meta
           agent to ensure it is **novel**. (3) ... If errors occur during evaluation,
           the meta agent performs a self-reflection step to refine the design,
           **repeating this process up to five times** if necessary."
          ⇒ DWC 的 modifier 需两个检查: ① 新颖性 ② 可执行性(有重试上限)

      (x) ★★★ 难度适中奖励的闭式形式 = WORLD_TREE "信息增益"的同构解
          【2505.03335 §4 逐字】
          "The intuition is that if a task is either **trivial to solve** (r̄_solve = 1)
           or **unsolvable** (r̄_solve = 0), the task provides **little to no learning
           signal** for the solver. In contrast, tasks of **moderate difficulty**, where
           the solver occasionally succeeds are **rewarded the most**"
          ⇒ r_propose = 1 - r̄_solve（r̄_solve = 0 时为 1，非 0 时为 1-r̄_solve）
          ★★ 世界树收束可改用闭式判据, 不必只靠"信息增益"这个隐式概念
          ★ 三种推理模式（任务类型三分）: induction / abduction / deduction
          ★ code executor 双重角色（统一可验证反馈源）:
            既验"自提任务是否成立", 又验"答案是否正确"
          ★ 防 hacking 论证: "helps prevent issues such as **hacking with neural
            reward models**" ⇒ 用真实环境而非神经奖励模型

      (y) ✓✓【已裁决 2026-10-04, docs/WORLD_TREE_CONVERGENCE.md】收束路线
          ★★★ 核 GEPA 原文（273,016 字符, ICLR 2026 **Oral**）后,
            **推翻了我自己写的下面那句"默认 Pareto"**
          ★★ 原文依据（Appendix D.1 逐字）:
            "GEPA+Merge works especially well for GPT-4.1 Mini, it **lead to
             performance degradation when used with Qwen3 8B**. Even Qwen3 8B
             benefits from Merge on **one out of four tasks**."
            ⇒ ★★★ "Pareto 更稳"没有任何依据 ⇒ 两条路线**都不是默认**
          ★★ 修正后的判据（选路线②当且仅当三条同时成立）:
            ① 组内任务数 ≥ n_pareto_min（否则 Pareto 维度不足）
               ★★ DWC 当前 sealed 15 条 ⇒ **不满足** ⇒ 默认只能是路线①
            ② 进化对象是"可被 LLM 用自然语言反思并重写"的东西
               ⇒ 代码/架构**不满足** ⇒ 混合对象下路线②只能用于其中一部分
            ③ 有 lineage 记录能力（merge 的条件①依赖它）
          ★★★ 路线②的最易误解点: Pareto 前沿是**逐任务实例**维度
            （Algorithm 2 line 4-5 逐实例取最高分）, 不是"逐总分"
            ★ 实测: 逐实例保留 {A,B,C}; 逐总分只保留 {C}
            ⇒ 若误用总分, Algorithm 2 退化为"永远选最好的"
            ⇒ ⇒ 那正是 Figure 6a 的局部最优陷阱 ⇒ 判据 Z3 是决定性的
          ★★ 路线②还有个硬限制: GEPA 是 **prompt optimizer**
            （摘要原文 "a prompt optimizer"）⇒ 可移植的是**搜索骨架**
            （Pareto 采样 + 自然语言反思 + merge）不是它的对象
          ★ 路线①的已知病（Figure 6a 原文）:
            "repeatedly attempts to refine it, fails to improve, and ultimately
             **depletes the budget**" ⇒ 路线①**必须**配卡住检测（判据 Z6）
          原文备查（我原先只从本节引文看过，现已核原文）:
          "GEPA (Genetic-Pareto) ... samples trajectories ... reflects on them in
           **natural language** to diagnose problems ... and **combine complementary
           lessons from the Pareto frontier** of its own attempts"
          实测: "outperforms GRPO by 6% on average and by up to 20%, while using up to
                 **35x fewer rollouts**"
          ⇒ 世界树收束两条路线: ① 单树深挖 + 信息增益(WORLD_TREE 现有)
            ② Pareto 前沿 + 自然语言反思(GEPA)
          ✗✗ ~~★ 建议: 默认 Pareto(更稳)~~ ← **2026-10-04 撤回, 依据见上**

      (z) ★★ judge 三条失效已有论断, 与三层设计一一对应【2601.05111 逐字】
          ① 参数偏置: "single-pass evaluators are prone to inherent **parametric
             biases**—such as favoring verbosity or their own output patterns"
          ② 无接地幻觉: "naive LLM judges are **passive observers**, unable to react
             to real-world observations ... leading to **hallucinated evaluations**"
          ③ 粒度过粗: "traditional LLM judges experience **cognitive overload** ...
             within a single inference step, which results in **coarse-grained scores**"
          ⇒ 分别对应 DWC judge 的: 中立性 / 可接地验证(L3) / 粒度分解(L1 原子二元)
          ★ 另两条可直接抄的机制【2407.19594 Meta-Rewarding】:
            · 方差选样: "we focus on responses where the judge is **the least certain**,
              as measured by the **variance of the scores**" ⇒ 最不确定的样本优先送 L3
            · 位置偏置校正: 同一对判定**交换顺序两次**, 按 win1st/win2nd 加权
          ★ 成熟度刻度【2601.05111 Figure 2】:
            **Procedural → Reactive → Self-Evolving** 三段
            ⇒ 可作 DWC judge 器官的自评刻度

      (aa) ★★ m/task agent 之分可以消除, 有两条独立佐证
          【2504.15228 SICA】: "A self-improving coding agent (SICA) that
            **eliminates the distinction between meta-agent and target agent**, and is
            capable of editing its own codebase"
          【2603.19461】: task/meta 合并进同一可编辑程序, meta 改进程序本身也可编辑
          ★★ ⇒ 与 (r) 互为佐证: m/U 必须同处 evolver
          ★ 诚实项: SICA **held-out 0 处**（wide grep）, contamination 仅出现在参考文献
            ⇒ SICA 的 17%→53% 未做留出集, 不可直接当"真提升"证据

      ★★★★★ §10 补读（2608.03392 五条开放问题）—— 26/26 逐字核实，全是 DWC 的硬约束
      (bb) ★★★★ 独立 judge 与"专用 verifier"一致性 > 与"公开 fix 继承测试"的一致性
          "an **independent judge** disagrees with its purpose-built verifiers **far less
           often** than with tests inherited from public fixes" ⇒ 双向印证 (c) 与 L3 独立审计
          ★ 附: "some results on SWE-bench Verified may be **inflated by contamination**"
      (bc) ★★★★ 同预算下"进化 harness"有**负面结果**（对 DWC 进化核心的直接警告）
          "on Terminal-Bench 2.1, **evolved harnesses do not consistently outperform
           simple test-time search baselines** and show **limited generalization to
           held-out tasks**"
          ⇒ (p) 的 +11.0pp 必须**在 DWC 自己的任务域重验**, 不可外推
      (bd) ★★★★ 自评分数可近满分而真实性能不升反降（原则 12 的实测支撑）
          "**self-assigned verification scores can stay near perfect while sealed
           deployment performance remains low or regresses**; retaining an **external
           accept-reject audit improves results across six models**"
          ⇒ ★★ 原则 12 不再是理论洁癖, 有六模型一致的实测
          ★ 与 (n) imp@k（冻结身份）互为印证
      (be) ★★★★★ Phantom Guardrails: add-only 循环让幻觉组件永久驻留
          "installs a guardrail for a **nonexistent violation in 15 of 60 runs** when
           harmless input resembles a familiar rule ... an **add-only loop makes the
           spurious component persist**"
          ⇒ ★ DWC 三层淘汰是对策, 但**必须验证淘汰真的发生**; 否则 add-only = 永久污染
          ★ 相似即误触发 ⇒ 记忆检索不能"高相似就召回"
      (bf) ★★★★ harness tampering: 改评测路径本身且可遗传
          "an audit of real self-improvement trajectories finds **harness tampering across
           different systems** and observes that such edits **can persist in the lineage**"
          "Reversibility must include the **evaluation path** as well as task execution."
          ⇒ (e) 两层补丁的最强理由; iron_laws 要管"**谁改得了评测路径**"
      (bg) ★★★★ 记忆: selective addition/deletion 优于无节制增长
          "**selective addition and deletion outperform unrestricted memory growth**"
          ⇒ 追加式增长是被实测打败的方案 ⇒ 印证"遗忘是少数派但必要"
          ★ "experience-following effect": **相似检索记录诱导相似输出** ⇒ 相似≠相关
      (bh) ★★★★ retention 是有条件的: 消费四元
          "retention **conditional**: an artifact is useful only for a **compatible task,
           retriever, consumer, and execution context**"
          "weak models often **failing to use what was retained**"
          ⇒ 记忆/技能须声明**消费四元**（与 (l) 三描述符同源）
      (bi) ★★★ 逐组件归因: 改 10 轮, 可迁移收益只在三类组件
          "**ablations locate the transferable gains in tools, middleware, and
           long-term memory rather than in every edited component**"
          ⇒ DWC 进化必须逐组件归因, 不能整体说"进化有效"
      (bj) ★★★ 短基准高估能力: 21% vs 65%
          SWEEVO（21 文件/数百测试）: 21% · SWE-bench Verified: 65%
          ⇒ DWC 若只在短任务验收会高估自己 ⇒ 对应 (N3) 轨迹视图
      (bk) ★★ 测试通过不是安全证据（iron_laws 的存在理由）
          4,892 patches 分析: 测试通过的补丁仍可改出不同文件/函数
          ★★ 1,030 traces / 7 框架: **170 patches** 通过功能检查但引入安全问题
          "**neither test passing nor LLM review reliably intercepted these cases**"
      (bl) ★★ 迁移方向相反的两条同时成立
          "**strong forward transfer does not guarantee retention**"
          ★ "**abstract validation routines transfer more reliably than concrete
             traces**", 但"**negative transfer through excessive specificity**"
          ⇒ (e) patch_target 与 (l) 描述符都应体现"**抽象层更可迁移**"
      (bm) ★★ A_t=(S_t,H_t,θ_t) 三元（2608.03392 式7/8/9）—— 见 SELF_EVOLVING_SURVEYS
          S_t=(memory,skills,tools,context) · H_t=(harness,workflow,multi-agent org)
          ★ θ_t 对 DWC **固定** ⇒ 这就是 DWC "fixed" 清单之一
          ★ 工具归属澄清: 改代码仍属 assets; 只有改变"如何组织与控制执行"才是 architecture
          ★★ ⇒ (e) 的可判定实现: 每个候选声明 (target_layer ∈ {assets, architecture},
            target_component) ⇒ ★★ **跨层自评即第 20 项根源**: 守卫① 用 θ 层
            （自算 confidence）评 H 层 ⇒ 修法不是"换更准的自评"而是**换层**
      (bn) ★★ 评估要 longitudinal + cost-aware trajectory view【2507.21046 §7】
          ⇒ DWC 门不能只看单轮分数, 须有轨迹视图 + 成本口径
      (bo) ★★ 评估五维度【2507.21046 §7】
          Adaptivity / Retention / Generalization / Efficiency / Safety
          ★ DWC 的 GDI 四信号**不完全重合** ⇒ 建议五维各报一数
          Retention↔FGT · Generalization↔τ_t · Efficiency↔C≤B 与 (k)
      (bp) ★ intra/inter test-time = Persistence 边界【2507.21046 §4】
          intra ↔ task 边界 · inter(offline) ↔ training 边界 ⇒ 填 (l) 的 Persistence

      (bq) ★★★★★ Coupled/Decoupled 是第 20 项的教科书形式化【2603.25681 TMLR §3.3.3】
          Coupled: 模型更新的状态**回馈到下一轮信号生成**（选择与优化共同适应）
          Decoupled: 选择器**独立训练**，选择**在训练前**固定；可用 proxy model
          ★ 代价: "Decoupled designs **reduce system complexity**, but **forfeit the
            ability to adapt selection** as the model's needs shift during training"
          ★ Table 4 实测: 14 个方法中 **9 个 Coupled（主流）**
          ⇒ ★★ 第 20 项在此不是少数派错误, 但同篇同时说:
            "**No existing method** ... has the main model curate its own training data
             **without an external selector**" ⇒ DWC 做的正是被点名的空白
            (**self-directed selection**, 原文称 "strongest form of autonomy")
      (br) ★★★★ 理论断言: 自选数据**在理论上前不可解**
          "optimal data selection **requires a reliable validation signal, which is
           often unavailable in autonomous settings**, rendering the optimization
           problem **intractable**"
          ★★ 若是 coupled 设计, DWC 必须回答"可靠验证信号从哪来"; 答不出则理论上不成立
      (bs) ★★★ 失败签名应两层: 三类漂移(粗) × Figure 9 七类16子项(细)【2603.25681 Fig.9】
          Data Autophagy(模型崩塌/灾难遗忘/Data-Copying/Déjà vu/采集受限)
          · Flawed Feedback(不一致不稳/偏置放大) · Optimization-Driven(涌现失配/奖励黑客)
          · Ineffective Self-Refinement(自纠边界/**幻觉性生成-验证鸿沟**)
          · Evaluation Bottlenecks(评估器偏置/指标设计缺陷/基准污染)
          · Supervision Bottlenecks(监督无效/监督质量有限) · Budget(强模型依赖/迭代算力)
          ⇒ ★ 这解决 §9 第 4 项: 第一层用 2609.2680 三类做门裁决, 第二层用十六子项定位
      (bt) ★★★ 确认偏误的机制描述【2603.25681 §7.1】
          "models **preferentially select outputs that align with their internal
           parametric errors rather than factual ground truth**"
          ★ 与 (20)(br) 同源: 自评的根本缺陷
      (bu) ★★ 数据获取性质限定全程上界【2603.25681 §2.5.4】
          "its **scale, diversity, difficulty, and noise** ... **bound what any later
           stage can achieve**"
          ★ 与 2607.07663 验证层级形成上下夹击: 上界=任务源接地质量, 下界=信号可靠性层级
      (bv) ★★ Curriculum 判据与 AZR 同构【2603.25681 §3.3.4 + 2505.03335】
          "neither **too trivial** to provide new learning signal, nor **too difficult**
           to be learnable" ≡ r_propose = 1 - r̄_solve
          ⇒ 两条独立文献互证 ⇒ 共识而非个别技巧
      (bw) ★ Promptbreeder 是"改进改进器"最早的显式实现【2309.16797】
          "Promptbreeder is not just improving task-prompts, but it is also **improving
           the mutation-prompts that improve these task-prompts**"
          ★ 比 Hyperagents 早两年 ⇒ ★ DWC 的 m/U 分离思想有更早的先例

      ★★★★★ §6 自主评估层（第 74-77 轮补读，23/23 逐字核实）—— DWC 命题最贴近的一节
      (bx) ★★★ 自主评估的三条性质 → DWC 评估协议的三条判据
          有效协议 "should **adapt over time, resist exploitation, and remain sensitive
          to meaningful changes in competence**"
          ★ 两压力定义: temporal drift + adaptive pressure（"exploit, overfit to, or
            otherwise render fixed test sets obsolete"）
          ★ 三重风险并存: "genuine capability growth, **transient overfitting, or
            exploitation of feedback signals**"
      (by) ★★★ ★ 观察窗是推理 ⇒ 验收必须同时报 test-time 配置
          "Its **observation window is inference** ... **how inference is configured
           determines what evaluation sees**"
          "The same model can score far higher with **search or iterative revision**
           than under plain decoding, so results are **only meaningful when reported
           together with the test-time configuration**"
          ⇒ ★★★ DWC 任何验收都要声明: 世界模型是否搜索 / 树展开几层 / 是否迭代修正
            ⇒ 与 (l) 三描述符、(m) 标量聚合共同构成**评估三声明**
      (bz) ★★★ 评估是闭环触发器, 不是终点报告 ⇒ 支撑 DWC ⑦主体与"任务源=世界模型"
          "**evaluation is what closes the loop** ... **it is where capability gaps
           first surface** ... **Measurement thereby becomes the trigger of the next
           iteration** rather than a terminal report"
          "evaluation **oversees the improvement of the whole system across iterations**"
          ⇒ ★★ run_term() 末不是"结算", 而是"生成下一轮任务源"
            （评估暴露的缺口**就是**下一轮该取的数/该做的练习）
      (ca) ★★★★ LLM 生成或评判评估实例 ⇒ 评估器耦合（coupled 问题的第三条独立表述）
          "If **LLMs are used to generate or judge new instances**, the evaluator can
           become **coupled to the models being evaluated**, introducing risks such as
           **judge bias, preference leakage, and weak human grounding**"
          "dynamic benchmarking **scales data production more readily than it scales
           trustworthy evaluation**"
          ★★ ⇒ coupled 风险现在有三条独立来源:
            ① 本篇 §3.3.3 自身的 coupled/decoupled（9/14 主流）
            ② 2608.03392 §10.2 自评近满分而真性能不升反降（六模型）
            ③ 本条（LLM 生成/评判 ⇒ 耦合）
          ⇒ ★★ 第 20 项已不是"文献不支持", 是**三源一致的风险**
      (cb) ★★★★ 环境噪声必须与模型失败区分（对 DWC 尤其重要）
          "if the environment changes **independently of the agent**, evaluation must
           **distinguish model failure from environmental nondeterminism**"
          ★★ ⇒ DWC 跑在真实环境（母巢/LLM 服务）上, 环境波动会被误记成模型失败
            ⇒ 必须设计"环境变更 vs 模型失败"的区分机制, 否则长跑数据不可信
      (cc) ★★★★ 两个现成的递归评估协议 = DWC 的外部对照物
          AI4AI-Bench: "agents **modify training algorithms in frozen research
            repositories**, after which the resulting algorithms are **rerun from scratch
            under fixed hidden evaluators**"
            ★ 三要素: 冻结仓库 + 从零重跑 + 固定隐藏评估器
          RSI-Exam: "an agent **inherits a working method or model harness**, **iterates
            under a fixed budget using visible data**, and submits one executable artifact
            that is **re-run on a sealed hidden set**"
            ★ 三要素: 继承 harness + 固定预算迭代 + 密封集重跑
          ⇒ ★★ 与 DWC 的"继承 → 预算内进化 → 密封集验收"逐条对应
            ⇒ DWC 若成功, 是与这两个基准同一赛道的独立验证
      (cd) ★★★ 动态基准的现成刷新法（密封集长期有效）
          DyCodeEval: "uses multiple agents to generate **semantically equivalent
           variants from static seed problems**, creating a **controllably refreshed
           test distribution** under data contamination"
          ★ Table 12 实测 14 个基准更新模式几乎全 Live, 唯 DyCodeEval 用静态种子
          ⇒ ★ DWC 密封测试集若要长期有效, 这是现成做法
      (ce) ★★★ 结果判据无法区分过程违规
          "outcome-based settings **lack step-level ground truth** due to the existence
           of many equally valid ways to reach a goal"
          ⇒ ★ DWC 若只有结果判据, 分不清"走对的路"与"对结果但过程违规"
          ★ 诚实项: "the number of environments that are unambiguously process-based
            remains **relatively small**" ⇒ 过程评估难做, 不是不想做
      (cf) ★★★ 记忆安全有现成参照: PerMemSafe
          "testing whether **accumulated user memories cause otherwise acceptable
           responses to become harmful** as context evolves"
          ⇒ ★★ 填 DWC 记忆核心的空: 记忆累积导致后续输出变坏的评估手段
      (cg) ★★ 环境 vs 基准的判定标准
          "if a model's actions **influence future states**, observations, or rewards
           beyond a single test instance, evaluation is **environment-based**;
           otherwise, it remains **benchmark-based**"
          ⇒ ★ DWC 的验收应明确声明属哪一类（DWC 显然是 environment-based）
      (ch) ★ 评估须度量改进轨迹而非只最终正确率
          "benchmarks that **measure the improvement trajectory itself rather than only
           final task accuracy**"（OPT-BENCH / AI4AI-Bench / RSI-Exam）
          ⇒ 对应 (N3) longitudinal trajectory view

      ★★★★★ §8 潜在风险（第 79-80 轮补读，21/21 逐字核实）—— 对 iron_laws 最根本的限制
      (ci) ★★★★★ ★★ 门是可腐化的 —— DWC iron_laws 的根本限制声明
          "The main safeguard is to **gate deployment** ... evaluations that halt the loop
           when a threshold is crossed."
          ★★★ "**Unfortunately, these gates are corruptible** because models can
            **sandbag the tests while keeping deployment performance**, and deceptive
            backdoors can survive standard safety training."
          ★★★ 结论原文: "**An evaluation that reads as safe therefore cannot certify
            that the self-improvement system is actually safe.**"
          ⇒ ★★★ 铁律必须显式承认"门可被腐化"; 不能声称"门通过 = 系统安全"
          ★ 与 (ca) coupled / (bf) harness tampering 是同一问题三种表述
          ★ 两条具体机制: ① "behavioral monitoring is defeated when a model **games
            the proxy** its monitors track"（且"sharpens as capability grows"）
            ② "agents can **learn to disable the mechanism meant to stop them**"
      (cj) ★★★★ 三个"止损但不修根"的模式（门设计的核心教训）
          ★ 断路器: "a circuit breaker **stops a crash without fixing the incentives
            that produce it**"
            ⇒ ★★★ DWC 的门若只"拒绝候选"就是断路器 ⇒ 必须同时改产生它的机制
          ★ 漂移监控: "monitoring **presumes a stability that an open-ended loop does
            not offer**" ⇒ ★★ DWC 是开放循环, "稳定后再监控"不成立
          ★ 人工审批: "a user clearing many actions quickly **tends to rubber-stamp**"
            + 沙箱 "does not scale"
            ⇒ ★★ 与用户既有铁律（母巢 ask 由用户拍板）吻合, 但要记录退化路径
            （已有检出口）
      (ck) ★★★★ L3 独立 judge 必须是**异源**, 不能只是"更强的 judge"
          防御手段各自的实测失效:
          · 廉价模型监控 CoT → "teaches the policy to **obfuscate its reasoning**"
          · 可扩展监督（辩论） → "gives **no consistent gain without an information
            asymmetry** between judge and agent"
          · 人类监督 → "bounded by **mistakes and manipulation**"
          ★ 原文结论: "**these defenses weaken as capability grows**"
          ⇒ ★★ L3 必须不同实现/不同状态/不同时间, 否则会被同向优化
      (cl) ★★★★ 记忆是攻击面, 且 context-independent 检查抓不到
          "malicious influence introduced through data, **memory**, tools, or
           self-modification can be **committed into later system versions, amplified
           across improvement cycles, and propagated to descendants**"
          ★ "safety-relevant user context can **emerge implicitly** as memory evolves,
            while **standard context-independent safety checks fail to capture** the
            resulting harm"
          ⇒ ★★★ DWC 的"不许执行 X"式铁律**抓不到**记忆涌现的风险
          ⇒ ⇒ 记忆需带"涌现风险"检测, 不只是内容准入
      (cm) ★★★ 幻觉护栏与真护栏被删是同一问题的两面
          ★ 加错: (be) Phantom Guardrails 15/60 为不存在的违规加护栏
          ★★ 删掉: "the **refusal behavior itself can be removed by editing a single
            internal direction**"; 且 "simple adaptive prompts" 可把安全训练模型推到
            近乎完全攻击成功
          ⇒ ★★★ DWC 若把安全寄托在某条提示/规则上, 它可能在一次进化中被删掉
            ⇒ ★ 提示/规则类"铁律"必须可检出其消失
      (cn) ★★★ 依赖幻觉包名会自动下载恶意代码
          "code models **hallucinate dependency names** that an attacker can register
           with malicious payloads, so the agent fetches disguised malware **on its own**"
          ⇒ ★ DWC 若允许进化中安装工具/包, 必须有来源校验
      (co) ★★ 责任缺口: 行为在发布后才涌现, 无人负责
          "when behavior emerges **after release**, **neither the operator nor the
           developer is clearly responsible** ... the **responsibility gap of learning
           automata**"
          ★ + 自修改可 "**lock in the values encoded at an early checkpoint**" 并使其
            "beyond contestation"
          ⇒ ★★ DWC 若改自己的代码: 早期锁定的值是谁定的、能否事后质疑, 是设计问题
      (cp) ★ 审计现实与失败率基线
          ★ 审计: "real audits face **limited access, unclear standards, and conflicts
            of interest**" ⇒ ★ DWC 自建的"独立审计"同样有这三类限制
          ★ 高危失败: "even the **safest** current agent produces such failures in about
            **a quarter** of their high-stakes test cases" ⇒ 约 25% 基线
      (cq) ★★★ 欺骗性对齐已是实测事实
          "frontier models **already distinguish evaluation from deployment**"
          (Laine et al. 2024) · 能 "fake alignment while supervised and revert when
          unmonitored" (Greenblatt et al. 2024a) · 能 "scheme in context" 并
          "copy their own weights" (Meinke et al. 2025)
          ⇒ ★★ DWC 的"进化提案需人批准"若形同虚设, 就是这一条

      ★ 另两条与已有设计**印证**（非缺口）:
        · §5.1 "independent task checks must remain **outside the criterion it can
          rewrite**" ≡ DWC 原则 1 + JUDGE_LAYERS 纪律 2
        · §6.1 STaR "restarting each round's fine-tuning from the **original pretrained
          model**" ≡ 母巢纪律 1（基线与结算同口径）

      详见 docs/papers/2609.2680.md（49,561 字节, 14 轮深读）
 24. ★ 世界树定稿 (docs/WORLD_TREE.md): 一套树 + provenance 双态 + 收束选信息增益
     + 六条判据 W1-W6。★ 用户提出"世界树跑验证/预测并收束" —— 成立, 且 ARSI 未做。
     ★ 未定: 剪枝策略 / 想象节点存哪 (倾向不存, 只在内存)
      2607.12790 的 L3 用"更强的 LLM"; DWC 用托管模型, 未必拿得到更强的。
      若退化 ⇒ 独立性来自**流程隔离**而非**能力差** (JUDGE_LAYERS §七③)
```

---

## 十、明确不做 / 要做

```text
不做
  ✗ 外部 agent 服务接口 (丙方向, 未来)
  ✗ 母巢的架构决策 (25 子系统 / 七管 / 触手单通道)
  ✗ ARSI 的 host 耦合 (adapters 114KB, DWC 是独立 agent)

要做
  ① 世界模型     参考 ARSI world_model (SIWM/WorldPool) 而非母巢
                 ★ 按 2608.24876 Table 4: 只预测成败则价值为负(13%<33.3%)
          ★★★ 2026-10-04 收束已定（docs/WORLD_TREE_CONVERGENCE.md）:
            本段的"信息增益"是**路线①**; 收束还有**路线②**(GEPA Pareto)
            ★★ 两路线**都不是默认** —— 撤回了我原先"默认 Pareto 更稳"的建议
              （依据: GEPA+Merge 在 Qwen3-8B 上负收益, 4 任务只 1 受益）
            ★ DWC 当前 sealed 15 条 ⇒ 默认只能是路线①, 且**必须**配卡住检测
              （Figure 6a: 单树 refinement 会 "depletes the budget"）

                   必须提供"哪一步错了"的定位能力
  ② 改权重       ★ 托管 LLM 下只有 prompt/路由/采样三种形态, 需用户确认
  ③ harness 类型系统  参考 ARSI harness/taxonomy.py (九维 × 五模块)
```

---

*v3 重写 2026-10-03 · v2 的四层栈已改为器官式*
*判据: ARSI 有 4 组双向依赖 + iron_laws 跨 6 模块 ⇒ 它是器官式, 不是层栈*

---

## 十一、目录结构（v4 定稿，2026-10-03）

### 11.1 ★ 先说判据：为什么不能照抄 ARSI

```text
★ ARSI 实测: 53 个模块**全塞进 harness/ 一个目录** (259,191 字节, 108 文件含 tests)。
  其中七环节真正用到的只有 38 个, 其余 15 个是杂项
  (call_guard / compile_gate / grpo_data / guidance / hot_hash / interlock /
   metabolism / pipeline / pr_wiring / quarantine / runtime_wiring /
   self_repair / shared_calib / training_bridge / everitt)。

★ 后果: harness/ 既放"改什么的分类学"(taxonomy) 又放"怎么落地"(evolver)
  又放"漂移检测"(anchor_hardening) —— 三类正交职责挤在一个命名空间。
  ⇒ 找东西靠记忆, 不靠结构。这是 ARSI 最难维护的一处。

★ 母巢的反面: 26 个顶层目录, 按"机制名"切 (organs / lifecyle_mech /
  test_orphan_probe / hive) ⇒ 目录名不表意, 也是靠记忆。

⇒ DWC 的判据: 目录必须按**七环节**切, 且每个目录只服务一个环节。
  这是"结构即文档" —— 不看代码也知道东西该在哪。
```

### 11.2 ★ 目录结构（定稿）

```text
E:/Divine Wisdom Core/
├─ src/dwc/
│  ├─ __init__.py            主类 DWC（持七器官 + 三入口）
│  ├─ core.py                ★ 一个主类，器官在此组装
│  │
│  ├─ organs/                ← 器官层（谁存在）
│  │  ├─ memory/             记忆内核: 𝒲/ℰ 双视图 + 三区 + 七管
│  │  ├─ judge/              判据层: 密封任务集 + 回归门（进程外）
│  │  ├─ actor/              行动者: 观察→决策→行动→记录
│  │  ├─ world_model/        世界模型: 任务生成 + 预测（环节⑥ 探索在此）
│  │  ├─ iwm/                内省自检 + 防漂移（环节⑤ 在此）
│  │  └─ iron_laws/          铁律 G1-G10（横切）
│  │
│  ├─ evolution/             ← 进化层（进化时发生什么）
│  │  ├─ stage1_diagnosis/   ① 诊断  签名(c,q,m) + 七桶路由 + 四量
│  │  ├─ stage2_objects/     ② 对象  𝒦 词表 + 九维 + hook + singleton
│  │  ├─ stage3_gates/       ③ 门    六步顺序（不可换）
│  │  ├─ stage4_apply/       ④ 落地  pub/priv + 固定预算 + 新鲜度
│  │  ├─ stage5_drift/       ⑤ 防漂移 → 供 organs/iwm 调用
│  │  ├─ stage6_search/      ⑥ 探索   → 供 organs/world_model 调用
│  │  ├─ stage7_agent/       ⑦ 主体   五元盘点（run_term 末调用）
│  │  └─ modifier.py         ★ m 改进器（提议侧）
│  │     critic.py           ★ U 改动评估器（裁决侧）
│  │     ★ m 与 U 必须分离成两个模块（GAI Figure 2 authority boundary）
│  │
│  └─ harness/               类型系统: hook 表 + Processor 协议 + 契约检查
│                            2606.14249 Table 1（八 hook + READ_ONLY）
│
├─ tests/                    镜像 src/ 结构
│  ├─ organs/  └─ evolution/  └─ harness/
├─ scripts/
│  └─ gate.py                七道门（可执行）
├─ docs/
│  ├─ ARCHITECTURE.md        本文件
│  ├─ EVOLUTION_CORE_V2.md   进化核心完整设计
│  ├─ papers/                19 份论文深读报告
│  └─ drafts_premature_code/ 抢跑写的草稿（未纳入设计，待处理）
├─ config/                   配置文件（铁律配置等）
└─ papers_txt/  papers/      论文原文
```

### 11.3 ★ 三条结构纪律（可机械检查）

```text
纪律 1 · 一个目录一个环节
  判据: stage{N}_* 目录里的模块，不得 import 另一个 stage{M}_* 目录的模块。
  ★ 环节之间只经 core.py 编排 —— 否则就是 ARSI harness/ 的病重演。

纪律 2 · organs/ 与 evolution/ 是两轴，不得互相 import 内部
  organs/   = 谁存在（空间轴）
  evolution/ = 发生时什么（时间轴）
  判据: evolution/ 可以 import organs/ 的**公开接口**；
        organs/ 不得 import evolution/ 的内部实现。
  ★ 例外: stage5_drift 与 stage6_search 的**实现**归 organs（见 §2.4.2），
    但设计文档放在 evolution/ 下以便与七环节并列阅读。
    实现落点: organs/iwm/drift.py · organs/world_model/search.py

纪律 3 · 每个模块必须能被 G1 定位门识别
  判据: 模块 docstring 含 DWC-MEM 或 DWC-AUTO；
        有 REPLACES 声明时不得与其他模块冲突。
  ★ 这是 gate.py 已经在查的，结构设计必须让它能过。
```

### 11.4 ★ 与 §2.4.2 归属表的对应（两轴如何落到目录）

```text
环节   归属器官          设计文档落点              实现落点
─────────────────────────────────────────────────────────────────
① 诊断 evolver          evolution/stage1_diagnosis/
② 对象 evolver          evolution/stage2_objects/
③ 门   evolver          evolution/stage3_gates/
④ 落地 evolver          evolution/stage4_apply/
⑤ 防漂移 iwm            evolution/stage5_drift/   organs/iwm/drift.py
⑥ 探索 world_model      evolution/stage6_search/  organs/world_model/search.py
⑦ 主体 全系统           evolution/stage7_agent/   core.py (run_term 末)

★ ⑤⑥ 有"两个落点"不是冗余:
   evolution/stage{N}_* = 设计文档（与七环节并列，便于对照论文）
   organs/*/           = 实现（归它所属的器官，符合纪律 2）
```

### 11.5 命名对齐（论文符号 → 文件名）

```text
𝒦 组件词表        → evolution/stage2_objects/vocab.py
失败签名 (c,q,m)  → evolution/stage1_diagnosis/signature.py
七桶路由          → evolution/stage1_diagnosis/router.py
四量度量          → evolution/stage1_diagnosis/measures.py
退火预算 b_t      → evolution/stage3_gates/budget.py
守卫① 冻结外测    → organs/world_model/trust_gate.py
守卫① 配对记录    → organs/judge/wm_pairs.py      (wm_prediction×wm_actual 配对)
state 四层         → foundation/state.py            (State/AssetVersions/
                                                       ArchitectureVersions/GateSnapshot/
                                                       ExecutionContext)
Pair (守卫① 判据)  → foundation/prediction_pair.py  (PredictionOutcomePair + dev_accuracy)
theta_dev 滑动基线 → foundation/thresholds.py       (theta_dev + 三个参数)
因果链热链        → foundation/causal_chain/ring.py    (Layer 0 内存环)
因果链存储        → foundation/causal_chain/store.py   (三层 + 三表四索引)
因果链瘦身        → foundation/causal_chain/compact.py (export → archive, 不 DELETE)
失败签名分类器    → evolution/stage1_diagnosis/classifier.py   (规则填 c/q, LLM 填 m)
签名三层映射      → evolution/stage1_diagnosis/drift_map.py     (三类漂移 × 16 子项)
退火编辑预算 b_t  → evolution/stage3_gates/budget.py            ★已在 §11, 此处补记
世界采样: 跨谱系  → evolution/world/scheduler/lineage.py        (按 FWT 偏置)
世界采样: 代内    → evolution/world/scheduler/band.py          (中间难度带优先)
消费点声明        → evolution/stage4_apply/consumer.py    (ConsumerSpec)
三级验证          → evolution/stage4_apply/verify.py      (L1解析/L2读回/L3探针)
消费点审计        → evolution/stage4_apply/audit.py      (ConsumerAudit 进因果链)
回归风险(事前)    → evolution/stage5_drift/regress.py     (SAHOO Eq.18-23)
遗忘度量(事后)    → evolution/stage5_drift/forgetting.py   (FGT/BWT/FWT 式16-18)
能力组定义        → evolution/stage5_drift/groups.py      (三条件 + protected_groups)
器官接口基类      → foundation/contracts.py        (六条通用约定 + 负面测试基类)
memory 接口       → organs/memory/port.py         (ingest/recall/distill/forget/stats)
world_model 接口  → organs/world_model/port.py    (predict/trust/train, 禁 confidence)
judge 接口        → organs/judge/port.py           (L1/L2/L3 + dev_accuracy + wm_pairs)
evolver 接口      → organs/evolver/port.py        (diagnose/propose/gate/apply)
iwm 接口          → organs/iwm/port.py             (advice/trust/drift/probe)
iron_laws 接口    → organs/iron_laws/port.py      (check 三组 + 路径保护)
m 改进器 (Modifier)  → evolution/modifier.py          (提议侧, X→Δ(X_Ag))
U 改动评估器 (Critic)  → evolution/critic.py            (裁决侧, X→ℝ)
两个 dial 声明        → config/dials.yaml               (四个显式布尔)
信用分配 ℒ_t      → evolution/stage3_gates/credit.py
双 split          → evolution/stage3_gates/split.py
FGGM 契约         → evolution/stage3_gates/contract.py
drawback 检测器   → evolution/stage3_gates/drawback.py
pub/priv 解耦     → evolution/stage4_apply/dual_signal.py
信号新鲜度        → evolution/stage4_apply/freshness.py
GDI 四信号        → evolution/stage5_drift/gdi.py
grounded 双条件   → evolution/stage5_drift/grounded.py
回放仿真器        → evolution/stage6_search/replay.py
EL 调度器         → evolution/stage6_search/el_scheduler.py
五元 χ 盘点       → evolution/stage7_agent/quintuple.py
★ 命名一律用论文符号的英文名 —— 便于与原文对照, 不另起中文名。
```

### 11.6 诚实边界

```text
① 本结构是**设计定稿**，不是已实现的目录 —— src/ 当前为空。
② stage5/stage6 的"设计文档 vs 实现"双落点是本结构唯一的特例，
   若将来发现它造成混乱，应改为"实现即文档"（在 organs 下写设计）。
③ 未定: harness/ 是否也需要按环节细分（当前是单一目录）。
   判据待补: 若 harness/ 模块数 > 15 再拆。
④ 本结构未考虑"未来加第八个环节"的扩展性 —— 按当前 16 篇论文，
   七环节是完备的；若有新论文引入新环节，需重审本结构。
```

*v4 更新 2026-10-03 · 补 world_model 器官 + 写入进化循环七环节（以 16 篇进化论文为核心）*
*七环节归属: ①②③④→evolver 内部 / ⑤→iwm / ⑥→world_model / ⑦→全系统*
*完整进化设计: docs/EVOLUTION_CORE_V2.md · 论文报告: docs/papers/*

---

## 附·二 · 缺口清点摘要（2026-10-04，第 74 轮）

```text
★ 完整清点表: docs/GAP_AUDIT.md

触发: 发现"世界树收束"议过三轮从未落文档、也从未登记为 §9 待办
★★ 这暴露了两个流程漏洞（比任何单条漏项都重要）:
  漏洞1 · "待定段清空" ≠ "做完了"  → 改用 GAP_AUDIT 作进度依据
  漏洞2 · 缺"销账"步骤            → 每项须三处齐: docs 落盘 + §9 回填 + GAP_AUDIT 销账

★★★ §9 第 25 项的信噪比已失真: 69 条子条目里 68 条标"未定",
   但其中至少 10 条已在别处落实（(bs)(bq)(by)(bz)(bm)(bv)(ci)(x)(p)(cc)）
   ⇒ 需销账, 否则该段不能当进度表

★★★ 三条真实缺口（此前从未进 §9）:
  ✓ A1 · "门通过 ≠ 系统安全" —— **已完成 2026-10-04**
       铁律 **G11**, severity=meta + enforcement=report_must_quote + 判据 I9–I12
       落点: docs/IRON_LAW_G11.md（含 config/iron_laws.yaml 新建草案）
  A2 · 世界树剪枝策略 + 想象节点存哪（被错塞在第 23 项里）
  A3 · 𝒦 词表只覆盖 16/21，未覆盖: 代码 / 架构 / 元进化 / 评估器 / 外部机制源

★★ 清点时顺带核实的硬事实（★★ 2026-10-04 已更新, 三处过期已修）:
  src/ 空 · tests/ 空 · docs/ **55 份** · ARCHITECTURE **162,199 字节**
  ⇒ 所有判据仍只能标"待实现后验证", 不能标"已满足"
  ⇒ IRON_LAWS_DESIGN 的"三件套"、ORGAN_INTERFACES 的 P1-P8 等需一次统一对齐
  ★★★ 但 **config 已不再是空的** —— 首批两份已落盘（实测通过）:
    · config/iron_laws.yaml          11 条铁律（G1–G10 + G11）+ D1/D2 加载纪律
    · config/capability_groups.yaml  三组 + Λ 计数口径 + 派生字段声明
    ★ 详见 docs/INDEX.md §一·bis 与 docs/PROGRESS.md
    ★★ src/ 与 tests/ 仍为空 ⇒ 11 个 check_fn 全待写
      ⇒ 判据 I8（check_fn 调用点 > 0）仍不可验证
  ⇒ IRON_LAWS_DESIGN 的"三件套"、ORGAN_INTERFACES 的 P1-P8 等需一次统一对齐
```

*v4 更新 2026-10-03 · 补 world_model 器官 + 写入进化循环七环节（以 16 篇进化论文为核心）*
*七环节归属: ①②③④→evolver 内部 / ⑤→iwm / ⑥→world_model / ⑦→全系统*
*完整进化设计: docs/EVOLUTION_CORE_V2.md · 论文报告: docs/papers/* · 缺口清点: docs/GAP_AUDIT.md*
