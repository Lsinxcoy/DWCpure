# 管道可借鉴，驱动归世界模型 —— 对不对？

> 2026-10-03 · 判据：只报实测
> 用户判断：「管道的设计可以借鉴，但是驱动应该用世界模型来负责」
> 结论：方向对，但"驱动"必须拆成两层，否则会重犯母巢的错误

---

## 一、先说结论

```text
✓ 对的部分: 管道的"形态"可借鉴, 管道的"触发时机"应由世界模型决定
✗ 需要修正: "驱动"不是一个东西, 是两层 —— 混在一起会出事

  驱动① 决策层: 这轮该干什么 (选动作/选相位)   ← ★ 世界模型负责
  驱动② 数据层: 记忆怎么流转 (取用/巩固/遗忘)   ← ★ 管道自己负责

★ 母巢的错误正是把这两层混了:
  它用"固定顺序"代替决策层 (tick 里写死 explore→compile)
  同时让管道全跑 (run_all) 代替数据层调度
```

---

## 二、实测：两边"驱动"分别在哪

### 2.1 母巢：**没有决策层**，相位是写死的

```python
# agent_core/loop.py — tick() 实测
_explore_result = _reg_learn.invoke("explore", _ctx_explore)   # 固定
...
_flow = self._phase_compile()                                   # 固定

实测 tick() 内:
  调用的 phase: _phase_explore → _phase_compile   (只有两个, 顺序固定)
  _mwm            0 处     ← ★ 世界模型完全不参与 tick 决策
  world_model     0 处
  predict_effect  0 处
```

**★ 母巢的"驱动"是硬编码顺序，不是决策。** MWM 虽在 `registry.invoke` 里被调用，但只用于记账（predict → 直接 run，不门控）。

### 2.2 ARSI：**世界模型主导决策**

```python
# governor/pre_enactment.py
def evaluate_candidates(self, state, candidates):
    flow_bonus = self._flow_action_bonuses()
    for action in candidates:
        pred = self.dynamics.predict_transition(state, action)   # ★ 世界模型 Layer 2
        score = self._score_prediction(pred, state)               # ★ 打分主力
        bonus = float(flow_bonus.get(action, 0.0) or 0.0)
        score = score + bonus                                     # 只 nudge
        evaluated.append({..., "flow_bonus": round(bonus, 4), ...})

def _flow_action_bonuses(self):
    """Map negative-velocity organs / z_subgoal to small action score bonuses.
       Keep small so dynamics score remains primary; only nudge ties."""   ← ★ 原文
```

**★ ARSI 的原文自己写了**：`dynamics score remains primary; only nudge ties`
—— 世界模型是打分主力，其他信号只做微调。

### 2.3 但 ARSI 的世界模型驱动是**有条件的**（关键）

```python
# core.py step() 三层决策
pre_result = self.pre_enactment.select_best_adaptive(state, candidates)
if pre_result["confidence"] > 0.1:
    decision = pre_result                       # Layer A: 世界模型
    result["decision_source"] = "pre_enactment_adaptive"
else:
    llm_decision = self.llm_governor.decide(state, candidates)
    decision = llm_decision                     # Layer B: LLM
    result["decision_source"] = "llm" or "heuristic"   # Layer C: 启发式
```

```text
★ confidence > 0.1 才用世界模型 —— 阈值极低, 但存在
★ 三层兜底: 世界模型 → LLM → 启发式
★ 依据: IWM 六问 Q6 calibrate 不可信则降级回 baseline
```

---

## 三、所以"驱动归世界模型"要加三个限定

### 限定 1 · 世界模型驱动的是**决策**，不是**数据流**

```text
世界模型负责:  这轮选哪个动作 / 哪个相位
管道负责:      选中之后, 记忆怎么取用/巩固/遗忘/流转

★ 若让世界模型管数据流, 会变成"世界模型即全能中枢", 违反器官式原则
★ 母巢的反面: 管道全跑 (run_all) + 无决策层 ⇒ 数据流和决策混成一层
```

### 限定 2 · 世界模型必须有**兜底**，不能是唯一驱动

```text
ARSI 的三层: 世界模型(conf>0.1) → LLM → 启发式

★ 理由: 世界模型有冷启动问题
  ARSI 的 dynamics 需要样本才可信 (iwm/calibrate.py: degrade_below=0.35, min_samples=5)
  母巢的 MWM 自陈 "min_samples: int = 3", 且"所有推断字段都是假设"

★ 只有世界模型驱动 ⇒ 冷启动期无动作可选
```

### 限定 3 · 世界模型的输出**必须能门控**（母巢的教训）

```text
母巢实测:
  MWM 46 个方法, 但 publish 0 / subscribe 0
  predict → 直接 m.run(context), 门控关键词 0 处
  selection_gate 里 MWM_WEIGHT_CAP = 0.1, dyna 默认关

★ 母巢是"有世界模型但不让它驱动" (矫枉过正)
★ DWC 纪律: 世界模型输出必须至少有一处门控决策的消费点
  (否则违反原则 4 产物必须有运行时消费点)
```

---

## 四、修正后的 DWC 分层

```text
┌─────────────────────────────────────────────────┐
│  决策层 (世界模型负责)                            │
│    世界模型 → 预测各动作后果 → 选动作/相位        │
│    ★ 兜底: conf < 阈值 → LLM → 启发式            │
│    ★ 消费点: 决策必须改变"这轮跑什么"            │
├─────────────────────────────────────────────────┤
│  执行层 (管道负责)                                │
│    选中动作 → 触发对应管道 → 记忆取用/巩固/流转   │
│    ★ recall 与 reflect 无条件跑 (数据完整性)     │
│    ★ 其余管道由动作触发 (不全跑)                 │
├─────────────────────────────────────────────────┤
│  事件层 (总线负责)                                │
│    管道完成 → 事件 → 因果链 → 记账               │
│    ★ chain_id 必须进信封 (母巢有字段没用)        │
└─────────────────────────────────────────────────┘

★ 世界模型驱动"选什么", 管道负责"怎么做", 总线负责"传什么"
★ 三层各司其职, 不越界 —— 这是器官式的必然要求
```

---

## 五、一句话回答

```text
问: 管道设计可借鉴, 驱动用世界模型负责, 对吗?

答: 对, 但要精确到:
  · 管道的"形态"借鉴母巢七管 ✓
  · 管道的"触发时机"由世界模型决策 ✓  (不是固定顺序, 也不是全跑)
  · 管道的"内部数据流"仍归管道自己 ✗ 不能让世界模型越界
  · 世界模型必须有兜底 (世界模型 → LLM → 启发式), 不能唯一驱动
  · 世界模型必须真门控 (母巢的 MWM 有 46 方法但不门控, 是反面教材)
```
