# DWC · 进化核心审计（四项目实测）

> 2026-10-03 · 判据：只报实测，区分设计/实现/落地
> 问题：进化核心怎么设计？先看四个项目里"进化到底怎么走完一步"

---

## 一、先说结论

```text
四个项目的进化核心, 没有一个走完"消化→提案→过门→应用"全链。

  ARSI     门全 (non-compensatory 四步) 但应用只 2/862
  母巢     产物多 (167,753 行) 但消费点 SHADOW 永不翻
  Ultra    进化日志 30,843 行, 但 strategy 只有 maintain/dream (evolve 0)
  Nexus    进化日志 8 行, 全是常量 (0.5→0.6→delta 0.1)

★ 四种失败各不相同, 但都指向同一处: 应用(apply)这一步没人负责。
```

---

## 二、ARSI：门最完整，应用几乎为零

### 2.1 完整链路（实测源码）

```text
① 消化   harness/digester.py   (12,114 B)  轨迹 → 失败聚类
② 提案   harness/evolver.py    (16,343 B)  landscape → Change-Manifest
③ 过门   harness/accept.py     ( 6,363 B)  non-compensatory 四步
④ 应用   ★ 无 (evolver 明说 "Does not auto-edit core")
```

**Evolver 自我声明（原文）**：

```python
"""Evolver — landscape → Change-Manifest (AEGIS stage 3).
Rule templates first; optional LLM refine.
Every candidate must pass scope fence + critic before status=accepted.
**Does not auto-edit core** — manifests are reviewable artifacts
(HarnessX Change-Manifest discipline)."""
```

### 2.2 准入链：non-compensatory 四步（顺序不可换）

```python
"""RRSI non-compensatory acceptance (arXiv:2609.24972 §3.3 / App.C.3).
Order matters:
  0) leakage screen BEFORE evaluation
  1) noise floor  Ŝ ≥ S* − δ
  2a) ΔS > δ  → cost rule  ΔC ≤ β0 + β1·ΔS
  2b) ΔS ≤ δ  → shaped   ws·ΔS − wc·ΔC + wn·ν_str > 0
  3) domain guards
"""
```

```python
def domain_guard(*, valid_output_rate_before, valid_output_rate_after, ...):
    """RRSI App.C.3 non-compensatory: primary score cannot compensate execution validity."""
    if valid_output_rate_before - valid_output_rate_after > valid_drop_max:
        return False, "valid_output_dropped"
```

**★ 这是四项目里最科学的门设计**：`非补偿式` —— 主分数不能补偿执行有效性的下降。

### 2.3 ★ 实测：862 条 manifest，860 accepted / **2 applied**

```text
E:/ARSI/archive/harness/change_manifests.jsonl  (862 行)
  status: {'applied': 2, 'accepted': 860}

applied 的 2 条:
  CM-fc23371019 | c2 | agent_loop.brief.policy | prompt | applied
    summary: "Require explicit fail_class and recovery step before declaring tool failure"
    diff: "+ ## Fail-handling
           + - On tool failure, set fail_class and attempt one recovery
           + - Do not repeat the identical failing call without a changed precondition."
    inverse_op: "- drop Fail-handling block"

  CM-7b86cd1d1f | c6 | task_completion_detection.sealed_eval.code_verifier | prompt | applied
    summary: "[prompt] Require compile check before accepting generated mechanism code"
    diff: "+ require_compile: true
           + on_compile_fail: reject_and_log"
    inverse_op: "- require_compile: false"
```

**★ 860 条 accepted 里只有 2 条 applied —— 99.77% 卡在"应用"这一步。**

### 2.4 ★ 更严重的问题：862 条只有 41 个唯一提案

```text
唯一 (symbol, edit_type, diff) 组合: 41 / 862

top 重复:
  n=133  empowerment.applier | tool     ← 同一提案提了 133 次
  n=130  sealed_eval.code_verifier | prompt
  n= 76  brief.policy | tool
  n= 76  empowerment.applier | prompt
  n= 63  brief.policy | prompt
  n= 42  empowerment.applier | control
  n= 42  empowerment.applier | tool
  n= 32  sealed_eval.code_verifier | control

symbol 分布: empowerment.applier 432 / sealed_eval.code_verifier 219 /
             brief.policy 155 / verified.claim 32 / mnemosyne.core 24
edit_type:  prompt 323 / tool 272 / control 156 / config 59 / processor 52
时间跨度:   2026-09-23 ~ 2026-10-03 (10 天)

★ 10 天里提了 862 次, 实际只有 41 个不同提案
★ 说明: 去重机制没生效 (源码里有 dry-run dedup, 但只按 (label, edit_type) 去重)
```

---

## 三、母巢：产物最多，但落地被 SHADOW 锁死

### 3.1 规模：88 文件 / 932 KB（极度过剩）

```text
evolution/ 87 个模块 (不含 __init__), 932.1 KB

体积 top:
  evolution_engine.py      83,516 B  12-layer GA engine
  b8_remaining.py          58,154 B  FATE on-policy self-evolution
  b9_remaining.py          49,757 B  Progressive MCGS + EntropyScheduler
  rimrule.py               48,758 B  RIMRULE-MDL 规则归纳
  selection_gate.py        32,098 B  A/B 相对评估 with Bayesian Paired Δ
  dag_scheduler.py         30,142 B  TaskDAG
  experience_bank.py       29,582 B  双层经验银行
  effect_tracker.py        25,737 B  NorthStar + 5D Causal
  tool_fitness.py          23,079 B
  eval_driven.py           21,708 B  population-based
  gepa.py                  21,125 B  Gradient-Enhanced Parameter Adaptation
  ...
```

### 3.2 生产引用率（严格口径）

```text
87 模块: 有生产引用 63 (72.4%) / 仅测试或无引用 24

★ 24 个仅测试/无生产引用:
  ablation_engine, adaptive_strategy, arch_ops, evidence, evolution_state,
  evox_optimizer, harness_merger, harness_spec, km5_archive, km_chem_marker,
  km_cost, km_evo_loop, km_evolver, km_fitness, km_full_loop, km_mutation,
  km_prompt, km_trace_fmt, km_trace_instruction, optimizer, pattern_extractor,
  playbook_inheritance, semantic_to_param, verifier_adapter
```

### 3.3 ★ 核心问题：`SHADOW = True` 从未翻开

```python
"""S5 (2026-09-10) · 基因执行器 — 把进化产物落到真实运行时旋钮上.

诊断链 (全仓检索证据):
    1. 五个基因 (exploration_rate / learning_rate / temperature /
       memory_weight / stability_factor) 的全部出现点都在优化器自己的
       参数表里 (everos/gepa/openspace/semantic_to_param), 无运行时消费点;
    2. best_genes 的唯一去向是 evolve_mixin merge_branch(merged_id=str(...))
       —— 被 str() 成 ID 记进分支表, 参数值丢弃;
    ⇒ 进化产物无处落地, 这是"进化空转"的结构性天花板.
...
影子开关:
    SHADOW=True (默认) → 只出计划与缺口清单, 绝不 mutate.
    生产观测满 20 tick 且 need_setter 清零后, 经
    gene_applier.set_shadow(False) 翻真实应用.
"""
SHADOW = True  # 影子开关: True=只出计划; False=真写运行时旋钮
```

**★ 母巢自己诊断出了"进化空转的结构性天花板"，并写了修复 —— 但开关默认 True，从未翻开。**

### 3.4 五个基因的消费点（设计是对的）

```python
GENE_TARGETS = {
    "exploration_rate": {"consumer": "MultiStrategyScheduler ε-greedy 探索率",
                         "path": "loop._evo_scheduler._epsilon", "attr": "_epsilon",
                         "range": (0.01, 0.5)},
    "learning_rate":    {"consumer": "MemPO GRPO 记忆效用更新步长",
                         "path": "loop._mempo._grpo_lr", "attr": "_grpo_lr",
                         "range": (0.001, 0.1)},
    "temperature":      {"consumer": "ThermodynamicIntelligence._temperature", ...},
    "memory_weight":    {"consumer": "MemoryFacade._reliability_eta", ...},
    "stability_factor": {"consumer": "loop._merge_gate_threshold", ...},
}
```

**★ 设计没问题 —— 每个基因都声明了消费点（原则 4 的雏形）。问题是 SHADOW 锁着。**

---

## 四、Ultra / Nexus：进化日志是假的

### 4.1 Ultra

```text
evolution_log 30,843 行, strategy 只有:
  maintain 21,611  (delta 全 = 0.1, 常量)
  dream     9,232
★ evolve = 0 条

log_evolution 全仓只有 2 个调用点:
  self.store.log_evolution(cycle_id, 0.0, patterns/len(nodes), "dream")
  self.store.log_evolution("maintain", 0.5, 0.6, "maintain")   ← 常量
```

### 4.2 Nexus

```text
evolution_log 8 行, 全部:
  (id, 'maintain', 0.5, 0.6, 0.09999999999999998, 'maintain', ts)
★ 8 行完全相同 (before=0.5, after=0.6, delta=0.1 硬编码)
```

### 4.3 但 Nexus 有 `EffectTracker` + `SelectionGate`（进化经验层）

```python
"""EffectTracker — 机制执行效果量化(Phase 0 共享脊柱).

问题实证:
- nexus.dispatch 只记账 + 转调, 从不量化机制"做了什么"(nexus.py:131).
- nexus.record_effect 已存在存储(_effects), 但 dispatch 从不自动调用它.

本模块负责"执行前后测量"与"candidate vs base 对比", 不重复 record_effect 的存储.
SelectionGate 据此做影子 A/B 选择(优则 promote, 劣则 prune).
"""
```

```python
@dataclass
class ScoringPolicy:
    success_weight: float = 0.4
    efficiency_weight: float = 0.3
    failure_penalty: float = 0.5
    min_samples: int = 5
    def adapt(self, stats: dict) -> ScoringPolicy:
        """根据历史统计数据自适应调整权重。"""
```

**★ 设计对，但实测 `invoke_count` 全 0 ⇒ 无数据可评。**

---

## 五、四项目进化核心对照

| 维度 | ARSI | 母巢 | Ultra | Nexus |
|---|---|---|---|---|
| 进化模块数 | harness/ 53 文件 | **88 文件 932KB** | 26 文件 334KB | 31 文件 417KB |
| 消化 (失败聚类) | ✓ digester 12KB | ✓ 多份 | ✓ b8_remaining | ✓ b8_remaining |
| 提案 | ✓ ChangeManifest | ✓ 基因/机制/架构 | ✓ | ✓ |
| 门 | **✓ non-compensatory 四步** | ✓ 多层 (selection/anti/quality) | ✓ | ✓ |
| **应用** | **✗ 2/862** | **✗ SHADOW=True** | ✗ evolve 0 条 | ✗ 8 行常量 |
| 去重 | ✗ 862→41 唯一 | ? | — | — |
| 回滚 | ✓ inverse_op 862/862 | ✓ CoW worktree | — | — |
| 效果量化 | ✓ effect_anchor 白名单 | ✓ effect_tracker | ✗ | ✓ EffectTracker (无数据) |
| 生产引用率 | — | 72.4% (24 个无) | — | — |
| 真跑证据 | 862 条 manifest | 44 天留痕 | 319h 已停 | api_server.log |

---

## 六、四条实测结论

```text
结论 1 · "应用"是四个项目共同的断点
  ARSI:  860 accepted → 2 applied (0.23%)
  母巢:  SHADOW=True 从未翻; branch_merges 167,753 行无人消费
  Ultra: evolve 0 条
  Nexus: 8 行常量

结论 2 · ARSI 的门最科学, 但门后没有路
  non-compensatory 四步 (leakage → noise floor → cost rule → domain guard)
  ★ 主分数不能补偿执行有效性下降 —— 这是四项目里唯一的非补偿式设计
  ★ 但 evolver 明说 "Does not auto-edit core"

结论 3 · 母巢的诊断是对的, 修复被锁着
  gene_applier 的 docstring 自己诊断出"进化空转的结构性天花板"
  并写了 GENE_TARGETS 五个消费点 —— 设计完全符合 DWC 原则 4
  ★ 但 SHADOW=True 默认, set_shadow(False) 从未调用

结论 4 · Ultra/Nexus 的进化日志不反映真实进化
  strategy 只有 maintain/dream; delta 是硬编码常量
  ★ 与母巢"op 只有 evolve 一个值"是同一个病: 日志 ≠ 进化
```

---

## 七、对 DWC 进化核心的启示（待展开）

```text
① 门的形态: 采纳 ARSI 的 non-compensatory 四步
   顺序: leakage screen → noise floor → cost rule → domain guard
   ★ 关键: 主分数不能补偿执行有效性

② 应用必须是一等公民, 不是最后一步
   ARSI 的病: 门很严, 门后没人管
   母巢的病: 有落地机制, 开关锁着
   ★ DWC: 应用必须有独立的"落地器" + 落地后读回验证 (原则 4)

③ 去重必须在提案层
   ARSI 862 条 41 唯一 (最高重复 133 次) ⇒ 提案层没有真去重
   ★ DWC: 提案前必须查 (symbol, edit_type, diff) 是否已提过

④ 消费点声明 + 影子期 + 翻开关, 三件都要有
   母巢的设计对 (GENE_TARGETS), 缺的是"翻开关的判据"
   ★ DWC: 影子期必须有明确的退出条件 (不是"观测满 20 tick"这种模糊话)
```
