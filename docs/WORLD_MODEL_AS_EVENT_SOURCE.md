# 世界模型作为事件源：实测

> 2026-10-03 · 判据：只报实测，区分设计/实现/落地
> 用户指出：世界模型被设计出来，有一项工作就是驱动事件
> ★ 本文更正《EVENT_DRIVEN_COMPARISON.md》漏算世界模型这一事件源

---

## 〇、更正

```text
上一份文档里我写:
  "Nexus 先进 / 事件源是空的 (dynamic_names=[])"

★ 漏了: 事件源不只是"动态机制", 还有世界模型 (World Model)。
  世界模型的核心职能之一就是"生成预测/反事实/想象 rollout" ⇒ 驱动事件。

★ 更正后: 四项目在世界模型上差异极大 ——
  母巢有 MWM (117KB) / ARSI 有完整 world_model/ (14 文件) / Ultra 与 Nexus 完全没有
```

---

## 一、谁有世界模型

```text
母巢  ★ cognition/mother_world_model.py   117,717 字符  (MWM v1)
      + cognition/mental_world_model.py      8,065 字符
      + cognition/agency_detector.py        11,346 字符
ARSI  ★ world_model/ 14 个文件:
      siwm.py 22,014 / world_pool.py 30,078 / capability_flow.py 32,379 /
      replay_world.py 17,520 / world_evolver.py 14,266 / dynamics.py 13,404 /
      dream_rsi_deep.py 12,467 / discovery_tree.py 10,744 /
      continuous_dream.py 8,866 / counterfactual.py 5,318 / ...
Ultra ✗ 无 (0 个文件)
Nexus ✗ 无 (0 个文件)
```

**★ Ultra/Nexus 完全没有世界模型。** 这是我上一轮漏掉的最大差异。

---

## 二、母巢 MWM：能力全，但**不驱动事件**

### 2.1 它有什么（源码实测，46 个方法）

```text
预测类:   predict / predict_effect / predict_method / simulate / simulate_for
状态类:   observe_tick / target_observation / refresh_from_store / snapshot
校准类:   calibrate_beta / calibrate_uncertainty_threshold / sync_ema
检测类:   detect_hallucination / detect_cost_surface_collapse / detect_candidate_margin /
          detect_degradation / detect_edit_failure / detect_disagreement_explosion
反事实:   commit_transition / mark_last_transition_outcome /
          mark_last_transition_counterfactual / build_effect_carrier / verify_carrier
Dyna:     dyna_collect / dyna_replay
统计:     compute_prediction_stats / mwm_quality / mwm_diag / get_join_stats
```

### 2.2 但它不驱动事件（★ 实测）

```text
MWM 文件内实测:
  publish         0 处
  emit            0 处
  PipelineEvent   0 处
  EventBus        0 处
  chain_id        0 处
  subscribe       0 处
  dispatch        0 处

★ MWM 从不发布事件, 也不订阅事件。它是一个被动的"账本 + 预测器"。
```

### 2.3 它的输出被谁消费

```text
9 个文件消费 MWM:
  agent_core/loop.py              observe_tick, attach_store, artifact_summary, mwm_diag, set_mwm
  mechanisms/registry.py          ★ predict_effect, simulate, commit_transition,
                                     build_effect_carrier, compute_prediction_stats
  evolution/selection_gate.py     ★ mwm (10 处) / _mwm (4 处)
  agent_core/health_gate.py       mwm_diag
  agent_core/loop_phases/ruminate_mixin.py  dyna_replay
  cognition/method_hub.py         predict_method
  lifecycle/cns_orchestrator.py   mwm_quality
```

### 2.4 ★ 关键实测：MWM 预测**不门控执行**

```python
# mechanisms/registry.py — invoke() 里的 MWM 接线

_mwm = getattr(self, "_mwm", None)
if _mwm is not None:
    _predicted = _mwm.predict_effect(name)          # ① 预测
    _mwm_action = WorldAction(actor=name, intent="invoke", ...,
                              expected_effect=_expected, ...)
    _mwm_prediction = _mwm.simulate(_mwm_action)     # ② 模拟
...
before = snapshot_system(...)
res = m.run(context)                                 # ③ ★ 直接执行 —— 预测未参与
```

**实测 `predict → run` 之间 1,145 字符，门控关键词全部 0 处**：

```text
  if _predicted        0
  if _mwm_prediction   0
  continue             0
  return None          0
  raise                0
  skip / block / refuse / gate   全部 0

★ 预测产出后代码直接 m.run(context) ⇒ MWM 预测不门控执行
```

### 2.5 MWM 在 selection_gate 里被**主动限权到 0.1**

```python
# evolution/selection_gate.py
# P7 (2026-08-21): 有限 gated MWM 信号 — 权重上限 0.1 (roadmap 铁律).
# prediction_error 不直接 enable/disable; safety veto / 客观 effect
self.MWM_WEIGHT_CAP: float = 0.1
self._mwm_degraded: bool = False     # 自动降级开关 (True = baseline-only)

# 已废除 — 权重违反 roadmap 铁律 mwm≤0.1 且 physical/social 是现有信号换皮。

if (mwm_signal is not None and not self._mwm_degraded
    and -1.0 <= float(mwm_signal) <= 1.0):
    cand = (1.0 - _w) * cand + _w * (cand + float(mwm_signal))   # _w ≤ 0.1
```

**★ 母巢把 MWM 的权重**硬性**限制在 0.1**（roadmap 铁律），并写明"prediction_error 不直接 enable/disable"。

### 2.6 MWM 的 dyna 也是关的

```python
def dyna_replay(self) -> dict:
    """失败重放: 只更新在线权重 (critic/ensemble/scorer), 不切换决策源.
       开关默认关. maintain 旁路每 _dyna_every_ticks 调一次."""
    if not bool(getattr(self, "_dyna_enabled", False)):
        return {"replayed": 0, "reason": "disabled"}
```

**★ `_dyna_enabled` 默认关。** MWM 的"想象 rollout"不生效。

### 2.7 母巢 MWM 的自我声明

```python
"""Minimal, inspectable Mother World Model (MWM v1).

This module stores auditable state and transitions; it does not claim to learn
physical or human mental dynamics.  All inferred fields remain hypotheses.
"""
```

**★ 它自己说"只存可审计状态与迁移，不声称学到动力学，所有推断字段都是假设"。**

---

## 三、ARSI 的世界模型：**真驱动环境演化**

### 3.1 world_model/ 的完整结构（14 文件）

```text
world_pool.py        30,078  Dream-RSI 历史 H_t = (T_1, ..., T_t)，每次 rollout 追加
capability_flow.py   32,379  Capability Velocity Field (arXiv:2607.27924 PT-Flow)
siwm.py              22,014  SIWM 三层: Behavior Predictor / Dynamics / Counterfactual
replay_world.py      17,520  paper-faithful Dream-RSI discovery-tree 模拟器
world_evolver.py     14,266  ★ off-policy 环境演化 (arXiv:2609.04128)
dynamics.py          13,404  SIWM Layer 2 — 状态转移函数 T(Φ_t, a) → Φ_{t+1}
dream_rsi_deep.py    12,467  Dream-RSI 六机制 (arXiv:2609.14858)
discovery_tree.py    10,744  从行为轨迹构建的结构化树
continuous_dream.py   8,866  P-R2 连续梦境合成器
counterfactual.py     5,318  SIWM Layer 3 — 反事实模拟器
cognitive_map.py      5,059  C2-3 认知地图
kernel_flow.py        5,033  C2-2 核回归速度场
opf_discipline.py     5,478  JEPA-Anything 启发的 OPF 纪律
nlm_filter.py         4,516  NLM 式私有历史滤波器 (CTM arXiv:2505.05522)
```

### 3.2 world_evolver：世界模型**主动生成新环境**（这就是"驱动事件"）

```python
"""WorldEvolver — off-policy environment evolution (arXiv:2609.04128).

Three directions on ARSI discovery worlds:
  - scenario: swap agent/host / context labels (novelty)
  - skill:   swap actions / fail_class / operator tags (rarity)
  - length:  insert extra (agent, action) steps (horizon)

Verifiers (adapted):
  - Oracle: evolved world retains at least one success-scored node
  - Invalid-test: empty/no-op world must fail (never accepted)
  - Quality: min nodes, has outcomes, difficulty > seed (high/max)
"""
DIRECTIONS = ("scenario", "skill", "length")
EFFORTS = ("low", "high", "max")
```

**★ 这是"世界模型驱动事件"的真实现**：世界演化器生成**新环境**（新的事件空间），不是被动等事件。

### 3.3 ★ 实测：它真的在跑（world_pool_snapshot.json）

```text
E:/ARSI/archive/world_pool_snapshot.json (schema: arsi.world_pool.v2)

  max_worlds: 50
  el: {tau: 0.75, batch: 8, advances: 46, lineages: 33 个}
  env_cfg: {enabled: True, el_tau: 0.75, effort: 'high',
            evolve_every_n: 1, max_evolved_per_harvest: 1, min_seed_nodes: 3}

  evolution_log: 50 条
    accepted = 50 / rejected = 0        ← ★ 100% 接受率
    direction: scenario 50 (全部)
    generation: 1 (全部)                ← ★ 全部只推 1 代
    verifier: {oracle_ok: True, invalid_rejected: True, quality_ok: True}

★ 环境演化真的在跑 (46 advances, 33 个 lineage), 但:
  · 只推 1 代 (generation 全 = 1)
  · 只用一个方向 (scenario, skill/length 未用)
  · 接受率 100% ⇒ 门可能太松
```

### 3.4 ARSI 的 lineage 代数分布

```text
lineages 33 个, generation 分布:
  generation=0: 28 个
  generation=1:  5 个 (lin_T36 / lin_T48 / lin_T46 / lin_T38 / lin_T50)

★ 只有 5 个 lineage 推到了第 1 代, 其余 28 个停在第 0 代
```

---

## 四、更正后的对比：世界模型作为事件源

| 维度 | 母巢 MWM | ARSI world_model | Ultra | Nexus |
|---|---|---|---|---|
| 有无世界模型 | ✓ 117KB | ✓ 14 文件 166KB | **✗ 无** | **✗ 无** |
| 发布事件 | **✗ 0 处** | ✓ 生成新环境 | — | — |
| 订阅事件 | ✗ 0 处 | — | — | — |
| 预测门控执行 | **✗ 预测后直接 run** | ✓ confidence>0.1 才用 | — | — |
| 预测权重 | **✗ 硬限 0.1** | ✓ 主导决策 | — | — |
| 想象 rollout | **✗ 默认关** | ✓ 连续梦境 | — | — |
| 反事实 | ✓ commit_transition | ✓ counterfactual.py | — | — |
| 真运行证据 | 账本在写 | ✓ 46 advances / 50 log | — | — |
| 自我声明 | "不声称学到动力学" | "off-policy 环境演化" | — | — |

---

## 五、结论：世界模型作为事件源，ARSI 最先进

```text
① ARSI   ★ 世界模型真驱动事件
   世界演化器主动生成新环境 (scenario/skill/length 三方向)
   实测在跑: 46 advances / 50 条 evolution_log / 33 lineages
   世界池 H_t 追加每次 rollout ⇒ 事件源持续增长

② 母巢   ⚠ 世界模型是"账本", 不是事件源
   46 个方法, 但 publish/emit/subscribe 全 0
   预测不门控执行 (predict → 直接 run)
   权重被硬限 0.1, dyna 默认关
   自我声明"不声称学到动力学"
   ★ 设计上就有, 但被主动限权/关闭

③ Ultra/Nexus  ✗ 完全没有世界模型
   它们的事件源只有"外部扫描 (web/arxiv/github)"与"动态机制编译"
   ⇒ 事件源是外生的, 系统自身不产生事件
```

### ★ 这一条回答了你最初的判断

```text
你说: "世界模型被设计出来, 有一项工作就是驱动事件"
实测: 
  · ARSI 做到了 (world_evolver 主动生成环境 ⇒ 驱动事件)
  · 母巢做了但关掉了 (MWM 有 46 方法, 不发布事件, 权重限 0.1, dyna 默认关)
  · Ultra/Nexus 根本没做 (无世界模型)

★ 所以从"事件驱动"这个角度看:
  我上一轮把 Nexus 排第一是错的 —— Nexus 连世界模型都没有。
  正确的排序应是: ARSI (世界模型驱动事件) > 母巢 (有但关掉) > Ultra/Nexus (无)
```

---

## 六、对 DWC 的修正

```text
修正 1 · 事件源必须包含世界模型 (不只是外部扫描 + 动态机制)
  DWC 的事件源三层:
    ① 外生: 外部扫描 (web/arxiv/github) —— 学 Ultra/Nexus
    ② 内生: 世界模型生成的预测/反事实/想象 rollout —— 学 ARSI
    ③ 编译: 机制编译产物 (T3/T4) —— 学 Nexus
  ★ 缺 ② 则系统只能被动响应, 不能主动探索

修正 2 · 世界模型必须能"驱动事件", 不能只是账本
  母巢的反面教训: 46 方法 / publish 0 / 预测不门控 / 权重限 0.1 / dyna 默认关
  DWC 纪律: 世界模型的输出必须至少有一处"门控决策"的消费点
    (否则违反 DWC 原则 4 "产物必须有运行时消费点")

修正 3 · 采纳 ARSI 的 world_evolver 形态
  三方向 (scenario/skill/length) + 三验证器 (Oracle/Invalid-test/Quality)
  ★ 但必须修 ARSI 的两处:
    ① 只推 1 代 ⇒ 要有代际推进机制
    ② 接受率 100% ⇒ 门太松, 要有拒绝率下限

修正 4 · 世界模型与记忆的接口
  ARSI: world_pool H_t = (T_1, ..., T_t), 每次 rollout 追加
  DWC: 世界模型的想象 rollout 应写入 memory 的 PROXY 区, 供 reflect 归因
  ★ 这条把"世界模型"与"记忆驱动进化"接起来
```
