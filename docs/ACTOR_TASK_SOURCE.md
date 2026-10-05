# DWC · actor 的任务源（§9 第 1 项）

> 2026-10-03 · 判据：只报实测，区分设计/实现/落地
> 问题：DWC 是独立 agent，`actor` 做什么任务？没有真实任务源，actor 就是空壳。
> ★ 2026-10-03 更新：用户决策 —— **任务源由世界模型生成**（见 §六）

---

## 一、先说结论

**ARSI 的 `actor` 不做任务，只观测宿主。** DWC 不能照抄这一点。

```text
ARSI 的实际形态:
  ingest_trace(agent_id, action, outcome, effect)   ← 宿主喂数据
  actor 的 5 个候选动作, 逐个实测:
    dream      真实现 (DreamPipeline)
    learn      真实现 (蒸馏 PROXY→EXPERIENCE)
    maintain   真实现 (记忆巩固)
    evolve     ★ 占位符: note = "mutation_attempted_unanchored", effect=0.0
    remember   ★ 空操作: note = "waiting for new traces"

  ⇒ ARSI 的 actor 是"记忆维护员", 不是"任务执行者"
```

**★ 但 ARSI 的"世界模型"是例外 —— 它真的在生成任务**（见 §六）。

---

## 二、`evolve` 是占位符——这是 "生 0 死 0" 的代码级根因

```python
# ARSI core.py _execute_evolve 原文
def _execute_evolve(self, state: WorldState) -> dict:
    """Evolve: attempt mechanism mutation (placeholder)."""
    exp_count = state.phi.storage_stats.get("experience_count", 0)
    if exp_count < 5:
        return {"type": "evolve", "note": f"insufficient experience ({exp_count}/5)"}

    # External effect anchor required (S5): placeholder cannot self-score as verified
    from arsi.foundation.effect_anchor import record_external_effect
    anchor = record_external_effect(
        self.store, mechanism="evolve_attempt",
        effect=0.0, source="internal_score", evidence_ref="",
    )
    return {"type": "evolve", "note": "mutation_attempted_unanchored",
            "effect": 0.0, "effect_anchor": anchor.to_dict()}
```

**★ docstring 第一行就写了 `(placeholder)`；它诚实标成 unanchored，effect 固定 0.0。**

---

## 三、ARSI 做对了一件事：`effect_anchor` 的判定表

```python
# arsi/foundation/effect_anchor.py 原文
"""External effect anchor — SYNTHEX P0/S5 + G5 hardening.
Effects used for evolution/policy claims must come from outside the
mechanism being scored (eval_loop, sealed task, host outcome), not
from the mechanism declaring its own value."""

EXTERNAL_SOURCES = frozenset({
    "eval_loop", "sealed_eval", "host_outcome", "quality_gate",
    "manifest_live", "behavior_trace", "layer1_holdout", "loop_trial",
})
INTERNAL_PLACEHOLDERS = frozenset({
    "placeholder_mutation", "self_eval", "internal_score", "",
})
```

**★ 这是 DWC 原则 1（判据必须在系统之外）的代码级实现。机制不能给自己打分，连"尝试过"都不算。**

---

## 四、ARSI 的 sealed_tasks（种子任务集）

```text
config/sealed_tasks.yaml 实测: 15 任务 / 3 类 / 2 档 verifier
  code_repair          6 条  verifier_rung=1
  knowledge_reasoning  6 条  verifier_rung=1  (keyword_match)
  paper_reproduction   3 条  verifier_rung=3  (expected_values + tolerance)

★ 三档 verifier 的意义: rung 越高越难作弊
  rung=1  关键词匹配     最弱, 但可自动化
  rung=3  数值容差比对   最强, 有唯一正确答案
★ DWC 判据层应按 rung 分层报告, 不是混成一个 success_rate

★ 关键: ARSI 把 sealed_tasks 只用在判据层 (G10 保护路径),
  没给 actor 用 —— 这是它的缺口, DWC 要补
```

---

## 五、三种任务源的评估（§9 第 1 项的前置分析）

```text
甲 观测宿主（ARSI 的做法）
   任务源 = 外部 agent 的轨迹
   ★ 缺点: DWC 定位是"独立 agent" —— 不做宿主服务就没源
   ★ 且 ARSI 实测: 这条路走到最后 evolve 仍是占位符

乙 自造任务（自己给自己出题）
   任务源 = DWC 生成任务, 自己做, 判据层判
   ★ 风险: 出题者和答题者是同一个 —— 撞原则 1
   ★ 除非出题权在判据层(进程外), 但那就不是"自造"了

丙 真实外部任务
   任务源 = 带客观对错的真实任务流
   ★ 例: 代码修复(有测试)、数值计算(有标准答案)、检索(有 ground truth)
   ★ 这正是 ARSI sealed_tasks.yaml 的形态
```

**★ 三者都漏了一个：世界模型自己生成任务（内生源）。见下节。**

---

## 六、★ 用户决策：任务源由世界模型生成

### 6.1 ARSI 的实测依据（世界如何生成任务）

**ReplayWorld 是"可探测的发现树"**：

```python
"""Replay World — paper-faithful Dream-RSI discovery-tree simulator.
Based on arXiv:2609.14858 §3 + Appendix B.2.

Key formalism:
- Eligible A(T) = {root} ∪ {v ∈ T : v is a leaf of observed prefix}
- Action C ⊆ A(T; W), |C| ≤ W
- Child(v; T_full, T_obs):
    v ≠ root: unique recorded child, if still unrevealed
    v = root: earliest-created child not yet in observed (branch opening)
- Replay is deterministic and prefix-only: unrevealed scores stay unknown
"""
```

**世界如何给出"可执行动作"（★ 这就是任务生成）**：

```python
def legal_actions(self) -> list[str]:
    return self._eligible()

def _eligible(self) -> list[str]:
    """A(T_obs) = {root} ∪ leaves of observed prefix that still have unobserved children."""
    if not self._observed:
        return ["root"] if "root" in self._full else []
    eligible = []
    if "root" in self._full and self._has_unrevealed_root_child():
        eligible.append("root")
    for nid in self._observed:
        ...
        children = node.get("children", [])
        if any(c not in self._observed for c in children):
            eligible.append(nid)
    return eligible

def probe_batch(self, cells) -> list[Observation]:
    """Deterministically reveal recorded children (paper Child() semantics)."""
    batch = [c for c in cells if c in self._eligible()][: self.max_parallelism]
    for cell_id in batch:
        for cid in self._child(cell_id):
            self._reveal(cid)
            if cid in self._obs_cache: revealed.append(self._obs_cache[cid])
    self._probes += 1
```

**★ 机制清楚了**：

```text
世界 = 一棵发现树 (已知 + 未揭示的分支)
legal_actions() = "还没探索过的叶子"   ⇒ ★ 这就是任务列表
probe_batch()   = "执行一批探索"       ⇒ ★ 这就是 actor 执行
每个 Observation 带回 score            ⇒ ★ 这就是任务结果

★ 任务不是外部给的, 是"世界的未知边界"自己产生的。
```

**世界池（历史世界集合）**：

```python
"""World Pool — Dream-RSI history H_t = (T_1, ..., T_t).
Every online term/rollout appends one completed discovery tree as a replay world.
Policy improvement dreams across ALL worlds, not just the latest one
(arXiv:2609.14858 §3).

Environment Evolution (arXiv:2609.04128):
- Each world carries off-policy D_T difficulty components
- Worlds are tagged into evolution lineages (seed generation 0+)
- WorldEvolver produces children (scenario/skill/length) with Oracle+Invalid
- ELScheduler samples by lineage pass-rate instead of random full-pool
"""
```

**世界演化器（生成"新世界"= 新任务空间）**：

```python
"""WorldEvolver — off-policy environment evolution (arXiv:2609.04128).
Three directions on ARSI discovery worlds:
  - scenario: swap agent/host / context labels (novelty)
  - skill:   swap actions / fail_class / operator tags (rarity)
  - length:  insert extra (agent, action) steps (horizon)

Verifiers:
  - Oracle: evolved world retains at least one success-scored node
  - Invalid-test: empty/no-op world must fail (never accepted)
  - Quality: min nodes, has outcomes, difficulty > seed (high/max)
"""
DIRECTIONS = ("scenario", "skill", "length")
EFFORTS = ("low", "high", "max")
```

**实测运行证据**：

```text
E:/ARSI/archive/world_pool_snapshot.json (schema: arsi.world_pool.v2)
  el: {tau: 0.75, batch: 8, advances: 46, lineages: 33 个}
  env_cfg: {enabled: True, effort: 'high', evolve_every_n: 1, min_seed_nodes: 3}
  evolution_log: 50 条, accepted=50 / rejected=0
    verifier: {oracle_ok: True, invalid_rejected: True, quality_ok: True}

★ 世界演化真在跑, 但三处缺陷:
  · generation 全 = 1 (只推 1 代; 33 lineages 中 28 个停在 g0)
  · 只用 scenario 一个方向 (skill / length 未用)
  · accepted 50/50 = 100% ⇒ 门可能太松
```

### 6.2 DWC 的任务生成链

```text
┌──────────────────────────────────────────────────────────────┐
│ ① 世界集合 𝒲 = {W_1, ..., W_n}                               │
│    每个 W = 一棵发现树 (已知分支 + 未揭示分支)                │
│    初始播种: sealed_tasks 的 15 条任务 (复用 ARSI, 补齐 rung2)│
├──────────────────────────────────────────────────────────────┤
│ ② 任务生成: W.legal_actions()                                │
│    返回 = "未揭示的叶子" = 待探索任务列表                     │
│    ★ 这就是 actor 的任务源                                    │
├──────────────────────────────────────────────────────────────┤
│ ③ 采样: 按 lineage pass-rate 采样 (不是随机全池)              │
│    ★ ELScheduler 形态 (ARSI world_pool 原文)                  │
├──────────────────────────────────────────────────────────────┤
│ ④ actor 执行: probe_batch(选中的 cells)                       │
│    产出 Observation{score, cost, ...} → 写 memory PROXY       │
├──────────────────────────────────────────────────────────────┤
│ ⑤ 世界更新: 揭示的分支标为 observed                            │
│    → legal_actions() 变化 → 任务列表变化                      │
├──────────────────────────────────────────────────────────────┤
│ ⑥ 世界演化: WorldEvolver 生成新世界 (scenario/skill/length)   │
│    ★ 三方向都要用 (ARSI 只用 scenario)                        │
│    ★ 必须有代际推进 (ARSI generation 全 = 1)                  │
└──────────────────────────────────────────────────────────────┘
```

### 6.3 与"世界模型驱动决策"（原则 9）的接口

```text
原则 9 要求世界模型门控决策。任务生成正是它的第一个门控点:

  世界模型 → legal_actions()  → 这轮有哪些任务可做
           → 采样 + 难度评估 → 选哪个任务
           → actor 执行      → 任务变成痕迹
           → 结果回写世界     → 下轮任务列表变化

★ 这条链路一通, 原则 10 的"内生事件源"就落地了:
  事件不是外部扫描来的, 是"世界的未知边界"产生的
```

### 6.4 actor 循环与失败痕迹（保留前版）

```text
actor 的循环:
  取任务 → 决策(预测/LLM/启发式) → 行动 → 记录痕迹
  ★ 痕迹必须带 outcome, 且 no-op/waiting/skipped 不算成功
    (ARSI is_meaningful_success 的判据)

★ 与 ARSI 的关键差异:
  ARSI: actor 只观测宿主, 任务在判据层
  DWC:  世界模型生成任务 → 喂 actor(做) + 喂 judge(判)
        ⇒ actor 有真实产出, judge 有真实判据, 两者不重合
```

### 6.5 对 ARSI 三处缺陷的修法

```text
缺陷 1 · 只推 1 代 (generation 全 = 1)
  修法: WorldEvolver 的 children 必须进下一代 lineage
        判据: lineage.generation 应随 advance 递增

缺陷 2 · 接受率 100% (50/50)
  修法: 设拒绝率下限 (如 ≥15%)
        理由: 全接受说明 verifier 三道门没筛掉东西

缺陷 3 · 只用 scenario 一个方向
  修法: scenario / skill / length 三方向都要跑
        判据: 三个方向的产出数都要 > 0
```

---

## 七、actor 的产出怎么变成"进化养料"

```text
链路: 世界模型生成任务 → actor 做 → 痕迹进 memory → evolver 消化失败
      → 提案 → 过门 → 应用 → 新痕迹回写世界

参照 DWC D5 (失败签名 c,q,m):
  c = 终止级原因 (来自外部真值源, 枚举)
  q = 因果角色 (root / contributing / symptom)
  m = 抽象机制名 (跨轮可比的稳定标识)

★ 举例: actor 做 code_repair 失败
   c = TEST_FAILED          (外部真值源: 测试执行器)
   q = root                 (是这次失败的主因)
   m = context_assembly     (抽象成"上下文组装"这个机制)
   ⇒ evolver 的提案目标: 改 context_assembly 这个机制
   ⇒ ★ 消费点: actor 的上下文组装参数

★ 这条链路一旦通, "进化养料来源于记忆" 就落地了。
```

---

## 八、三项目任务源对比（含本次决策）

| 维度 | 母巢 | Ultra/Nexus | ARSI | **DWC** |
|---|---|---|---|---|
| 任务从哪来 | 外部扫描 | 外部扫描 + 心跳 | **世界模型 legal_actions** | **世界模型** |
| 有无世界模型 | ✓ 但不用 | ✗ | ✓ | ✓ |
| 世界演化 | ✗ | ✗ | ✓ 46 advances | ✓ |
| 代际推进 | — | — | ✗ 只 g1 | ★ 要修 |
| 拒绝率 | — | — | ✗ 0% | ★ 要修 |
| 任务源类型 | 外生 | 外生 | **内生** | **内生** |

---

## 九、已定 / 待定

```text
已定:
  Q1 任务源        → 世界模型生成 (§六, 用户决策 2026-10-03)
  Q2 种子任务集    → 复用 ARSI 15 条起步, 补齐 rung 2 (§四)

待定:
  Q3 提案粒度: 甲 一次改一个机制 / 乙 一次改一类   → 建议甲
  Q4 世界采样: 甲 按 lineage pass-rate / 乙 按难度  → 建议甲 (照 ARSI)
```
