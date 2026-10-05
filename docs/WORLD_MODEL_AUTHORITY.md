# DWC · 世界模型能否全权负责决策/驱动/验证？（讨论记录）

> 2026-10-03 · 用户提问："你觉得世界模型能够全权负责决策/驱动/验证这些工作吗"
> 判据：ARSI world_model/ 逐文件实测 + vitals_ledger 自述数字 + 论文原文
> 前置：`ARCHITECTURE.md` §2.3 / 原则 9 / 原则 12 · §9 第 20 项

---

## 一、★ 直接结论：不能。三个职责要分开答

```text
┌──────────┬──────────────────────────────────────────────────────────────┐
│ 职责     │ 世界模型能否全权负责?                                         │
├──────────┼──────────────────────────────────────────────────────────────┤
│ 决策     │ ⚠ 第一顺位可以, 但**必须有守卫** (原则 12 已定)               │
│          │   理由: confidence 与 accuracy 解耦 (代码级证据见 §二)        │
├──────────┼──────────────────────────────────────────────────────────────┤
│ 驱动     │ ⚠ 可以驱动"下一轮做什么", 但**不能驱动"记忆的取用/巩固/遗忘"** │
│          │   理由: 那会变成全能中枢, 撞原则 6                           │
│          │   ★ 已定边界: "世界模型驱动决策, 不是数据流"                  │
├──────────┼──────────────────────────────────────────────────────────────┤
│ 验证     │ ❌ **绝对不行**。这是最硬的一条。                             │
│          │   理由: 原则 1 —— 判据必须在系统之外                          │
│          │   世界模型是"被评分者" (eta 就是它的误差), 让它验证 = 自证     │
└──────────┴──────────────────────────────────────────────────────────────┘

★ 一句话: 决策可以 (带守卫), 驱动可以 (限决策层), 验证绝对不行。
```

---

## 二、★ 代码级证据：confidence 与 accuracy 是解耦的

### 2.1 完整公式（`world_model/dynamics.py` TransitionModel.predict 原文）

```python
        if not self._trained or action not in self._avg_deltas:
            return {
                "action": action,
                "predicted_delta": {},
                "confidence": 0.0,
                "reason": "no_training_data" if not self._trained else f"unknown_action:{action}",
            }

        avg_delta = self._avg_deltas[action]
        count = self._counts[action]

        # Confidence based on sample size and consistency
        confidence = min(1.0, count / 20.0)  # Full confidence
```

```text
★★ 这就是全部: confidence = "这个动作见过多少次 / 20", 上限 1.0。
   ⇒ 见过 20 次以上的动作, confidence 恒 = 1.0 —— **与预测准不准完全无关**
   ⇒ 见过 100 次的**错误**预测: confidence = 1.0
   ⇒ 没见过但能推对的:            confidence = 0.0

★ 而 core.py L491 用它作决策门:
    if pre_result["confidence"] > 0.1:
        decision = pre_result
  ⇒ 实际判据 = "这个动作见过 >2 次", 与世界模型准不准**无关**。
```

### 2.2 模型本身是"平均增量"，不是"预测"

```python
# TransitionModel.fit 原文
        for action, transitions in self._transitions.items():
            avg_delta = {}
            keys = transitions[0]["delta"].keys()
            for k in keys:
                avg_delta[k] = sum(t["delta"].get(k, 0) for t in transitions) / len(transitions)
            self._avg_deltas[action] = avg_delta
```

```text
★ 它学的是 "这个动作平均让各特征变化多少" —— 一个**动作的均值统计**,
  **不看当前状态** (predict 收 state 参数但 fit 里没用到 state 作为条件)。
  ⇒ 严格说它不是"世界模型", 是"动作的平均效果表"。
  ★ 这解释了 eta≈0: 预测不含状态信息 ⇒ 与实际偏差无结构 ⇒ 误差不下降。
```

### 2.3 ★ ARSI 自己的记账（`vitals_ledger.py` docstring 原文）

```text
"P-vitals: why eta / self_trust / live_layer1 are flat — accounting ledger.
 Long-run data: **eta≈0, self_trust=0, live_layer1=0 while holdout=0.94**.
 This module does NOT change scores; it records *why* so L3 can be fixed
 with evidence instead of guesswork."
```

```text
★★ 翻译: 世界模型在**历史数据上 94% 准**, 在**实盘上 0% 准**。

★ 而且系统自己记了原因 (v.reasons 原文):
  "eta_near_zero: prediction_error_stream_empty_or_layer1_too_accurate_on_categories"
  "self_trust_pinned_zero_by_success_rate_and_ece"
  "layer1_holdout_high_live_zero: rules_do_not_transfer_or_live_evaluate_not_called"
  "layer1_holdout_live_gap: historical majority-fallback or inverted temporal
   split inflated holdout"

★ 修复建议原文:
  "score holdout STRICT (no majority fallback); fit past→test future;
   compare like-for-like with live"

★★ 但 —— **ARSI 已经修了** (本轮核实 siwm.py L455-484 原文):

   L455:  # store returns DESC; reverse to time-forward for honest temporal split
   L456:  traces = list(reversed(raw))
   L459:  split = max(3, int(len(traces) * 0.8))
   L460:  train, test = traces[:split], traces[split:] or ...
   L469:  # STRICT primary score (rules only); majority is diagnostic
   L470:  holdout = self.layer1.holdout_accuracy(test, use_majority_fallback=False)
   L471:  holdout_maj = self.layer1.holdout_accuracy(test, use_majority_fallback=True)
   L484:  "split": "forward_temporal_chronological",

  ⇒ ★ 两条修复都已落地: ①时间正序切分 ②STRICT 主分 (majority 只作诊断)
  ⇒ ★ 所以 "holdout=0.94" 这个数是**修复后**的严格分。

★★ 这改变了结论的分量: 不是"94% 是吹出来的",
   而是"**在严格评分下 94% 准, 但实盘 0% 生效**" ——
   这说明问题不在测量, 而在**规则不迁移**
   (vitals 原文: "rules_do_not_transfer_or_live_evaluate_not_called")。
```

---

## 三、为什么"验证"绝对不行 —— 三重理由

```text
理由 1 · 原则 1 (判据在系统之外)
  世界模型的预测是**被评估对象** (eta 就是它的误差)。
  让它验证 = 让考生自己批卷。

理由 2 · grounded 双条件 (2609.13406 §2.2)
  要求: ① 内容来自系统外 ② base 本身在 agent 外。
  世界模型是 agent 内部组件 ⇒ 不满足条件②。

理由 3 · ★ 有实证 (2607.12790 Figure 3)
  论文实测: 用下游表现证明评估器有效性 ⇒ 会把"全通过的假评估器"认证为最好:
    量法                      anchored        co          co naive
    Task score (缩放轴)      0.802 ± 0.024  0.767 ± 0.015  0.811 ± 0.015
    Metric validity (0-1)    0.830 ± 0.012      —         fail-open / 塌缩
    ★ "the worthless grader is the higher of the two co-evolved arms"
  世界模型比"下游表现"离被判对象更近 ⇒ 风险更高。
```

---

## 四、★ 由此发现的一处内在矛盾（§9 第 20 项）

```text
★ 原则 12 说: "守卫不许来自世界模型自身 (否则撞原则 1)"。
  但守卫① (可信度门) 用的是 pre_result["confidence"]
  —— 而 §二 已证明这个 confidence 就是世界模型自算的。

⇒ 守卫① 形式上来自 core.py (外部), 实质上来自 world_model (内部)。
  ★ 严格说它**违反了原则 12 自己**。

★ 这是 v4 架构里的一处内在矛盾, 之前没发现。
```

### 三条候选修法

```text
甲 · 守卫① 改用 iwm 的 self_trust
   ✓ 真外部器官
   ✗ 实测 self_trust=0 (恒定, 见 vitals_ledger) ⇒ 等于"永远不信任" ⇒ 退化

乙 · ★ 守卫① 改用 judge 在 dev split 上的滑动准确率  (倾向此条)
   ✓ 真外部, 符合原则 1
   ✓ 不引入新组件 (同一个 judge, 见 JUDGE_DESIGN)
   ✗ 需 judge 参与每轮决策 ⇒ 成本高

丙 · confidence 本身改成滑动准确率
   ✗ 最小改动, 但仍是世界模型自算 ⇒ 没解决原则 12 的问题
```

**★ 我倾向乙，理由**：

```text
① 它是唯一真正符合原则 1 的方案 (判据在系统之外)
② 复用已有的 judge, 不新增组件 —— 符合原则 6 (器官只经接口)
③ 判据来源清晰: "世界模型在 dev split 上最近 N 轮的预测准确率"
④ ★ 且它顺手解决了另一个问题: dev split 本来就是"唯一有监督信号"的
   (2607.12790 §2.2 原文: "the only supervised signal any loop reads")
   ⇒ 用它来判"该不该信世界模型", 语义上完全对齐
```

**★ 乙的成本问题与缓解**：

```text
成本: judge 每轮都要跑 dev split ⇒ LLM 调用 + 时间
缓解 (三条, 供讨论):
  ① dev 本来就"恒小" (2607.12790: 恒 10 条) ⇒ 成本可控
  ② 不必每轮跑 —— 可以每 N 轮 (N 由 iwm 的 advice 决定, 不硬编码)
  ③ ★ 滑动准确率可以复用已有数据: 世界模型每轮本来就在预测,
     把它的预测与 judge 的判定对比即可 ⇒ 不需要额外调用 judge
```

---

## 五、★ 正确的分工：三权分立

```text
              ┌─────────────────────────────────────────┐
              │  决策 (选哪个动作/相位)                   │
              │  ★ 世界模型第一顺位, 但可被撤销            │
              │  守卫: iwm(整体否决/动作改写) + 可信度门    │
              │  ★ 可信度门的判据应改为 judge 的滑动准确率  │
              └──────────────┬──────────────────────────┘
                             │ 提出决策
                             ▼
   ┌─────────────────┐   ┌─────────────────────────────────┐
   │ 驱动 (什么让下一轮)│   │ 验证 (做得对不对)                │
   │ ★ 世界模型生成任务 │   │ ★ judge 负责, 进程外, 不可写       │
   │ legal_actions()  │   │ 世界模型**不参与**                │
   └─────────────────┘   └─────────────────────────────────┘

★ 三条理由 (都有实测):
  ① 决策与验证必须分开 —— 否则自证 (原则 1)
  ② 驱动与验证必须分开 —— 否则"我生成的任务我自己判"
  ③ 决策与驱动可以合一 —— 因为任务生成本来就是"预测哪些叶子值得探索"
     ★ 这是世界模型的**本职**, 不是越权
```

---

## 六、诚实边界

```text
① "eta≈0 / self_trust=0 / live_layer1=0 / holdout=0.94" 是 ARSI
   vitals_ledger.py docstring 的**原文自述**, 不是我的推断。

② ★ confidence = min(1.0, count / 20.0) 是 dynamics.py 的**完整原文**
   (本轮已读到完整行, 不再是截断)。上一轮我写的"count/..."已补全。

③ TransitionModel "不看当前状态" 是我读 fit/predict 全文后的判断 ——
   predict 收 state 参数, 但 _avg_deltas 的键只有 action (不含 state 特征)。
   ★ 未验证: _extract_features 是否间接用到了 state (它用于算 delta, 但
     不作为条件索引)。若有更细的用法, 结论需修正。

④ ★ 已核实并更正: siwm.py 的 holdout 严格评分**已经落地**
   (L470 use_majority_fallback=False 作主分, L471 majority 只作诊断;
    L455-456 时间正序切分; L484 "forward_temporal_chronological")。
   ⇒ 我初稿写的"94% 是多数回退吹出来的"是**错的** —— 那是**修复后**的严格分。
   ★ 但仍未逐行审: capability_flow 32KB / world_pool 30KB / cognitive_map /
     kernel_flow / nlm_filter / opf_discipline。它们可能改变上述判断。

⑤ "三权分立"是我的提法, 不是论文的。

⑥ §四 挑明的矛盾是否真的构成违规, 可争论:
   有人说 confidence 是"预测的副产品"而非"自评"。
   ★ 我倾向认为它构成违规 —— 因为 confidence 决定了"是否采用自己的预测",
     这正是自评的形态 (自己判断自己该不该被信任)。
```

---

## 附：存证

```text
ARSI 源码: src/arsi/world_model/dynamics.py (TransitionModel.fit / predict 全文)
           src/arsi/world_model/siwm.py (三层结构 + 方法签名)
           src/arsi/iwm/vitals_ledger.py (docstring 自述数字 + reasons)
           src/arsi/governor/pre_enactment.py (evaluate_candidates)
           src/arsi/core.py:491 (confidence > 0.1 决策门)
论文报告:  docs/papers/2607.12790.md §3.5 (Figure 3) · §2.2 (三 split)
           docs/papers/2609.13406.md §2.2 (grounded 双条件)
前置文档:  ARCHITECTURE.md §2.3 (三层驱动) / 原则 9 / 原则 12 / §9 第 20 项
```
