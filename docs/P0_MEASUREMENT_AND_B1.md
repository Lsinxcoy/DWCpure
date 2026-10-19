# P0 两项：可比口径 + P2P 测量 + B1 进化分发（2026-10-19）

> 一句话：**测量口径修到可比，P2P 接进分级 fitness，`evolve` 分支从「硬编码 False」变成「真调 evolver.diagnose」。**

---

## 一、P0-1a · `compare_policies`（可比口径）

### 问题

Phase C 实测踩中：`fitness_breakdown` 的 `outcome` 分母随 realization 变化。

```
策略 A: 5103 语法失败 ⇒ f2p 未测 ⇒ outcome 分母 = 2
策略 B: 5103 语法通过 ⇒ f2p 测得失败 ⇒ outcome 分母 = 3
⇒ A = 2/2 = 1.0, B = 2/3 = 0.667
⇒ 看起来 B 变差，实际是 B 测得更全
```

**直接比 scalar 会得出反向结论。**

### 修法

新增 `compare_policies(policy_records)`：

1. `common_instances` = 所有策略都有记录的 instance_id 交集
2. 每一级再取「所有策略都测到该级」的子集（None 不进分母）
3. 各策略在**同一子集**上算 rate ⇒ realization / outcome / scalar 可比

### 验证

`test_compare_policies_uses_common_measured_set`：

```
A: 11143 ✓ / 5103 syntax✗(f2p 未测) / 5227 ✓
B: 11143 ✓ / 5103 syntax✓(f2p ✗)   / 5227 ✓

断言:
  f2p 共同测量集 n=2（排除 5103）
  outcome: A == B          ← 不再虚降
  realization: B > A       ← 如实反映 B 能编译
  scalar: B > A
```

另两条：单策略 ⇒ `comparable=False`；无交集 ⇒ `scalar=None`。

---

## 二、P0-1b · P2P 测量接线

### 问题

harness 的 `run_tests` 只跑 F2P ⇒ `outcome` 实际只有 f2p + verifier 两项，
`p2p_ok` 永远是 None。

### 修法

**契约变更**：`HarnessDeps.run_tests` 返回

```python
{
  "all_passed": bool,   # f2p 通过 AND (p2p 通过 OR p2p suspect)
  "f2p": {...},         # 原始 F2P 结果
  "p2p": {...},         # 原始 P2P 结果（含 skipped/suspect）
  "passed": int, "total": int,
}
```

`AgentHarness._execute` 兼容旧回调（`tests.get("f2p") or tests`）。

P2P 纪律（沿用 adapter 既有口径）：

| 情况 | 处理 |
|------|------|
| P2P 为空 | `skipped=True, reason=no_p2p` ⇒ `p2p_ok=None` |
| P2P > 100 条 | `skipped=True, reason=p2p_too_large_N` ⇒ `p2p_ok=None` |
| pytest 集合失败（rc=4 / not found） | `suspect=True` ⇒ 视为 harness 问题，不算 agent 失败 |
| 正常 | `p2p_ok = all_passed` |

### 验证

- `test_record_from_harness_reads_p2p`：p2p 失败 ⇒ `p2p_ok=False`
- `test_record_from_harness_p2p_skipped_is_none`：跳过 ⇒ `p2p_ok=None` 且不进分母

---

## 三、P0-2 · B1：`evolve` 真分发

### 改前（`core.py:352`）

```python
dispatch = {"kind": "evolve", "dispatched": False,
            "why": "not_dispatched: 器官已实现(evolver.Evolver) 但 step 分发未接线"}
```

**`evolve` 是 `ACTIONS` 里的合法动作，但选了也永远不执行。**

### 改后

```python
elif action == "evolve":
    _sig = (judgement or {}).get("failure_signature")
    if not _sig:
        # 诚实 False：没有诊断对象，不编造
    elif not all(_sig.get(k) for k in ("c", "q", "fn")):
        # 诚实 False：diagnose 的查询键是 c/q/fn，缺一即抛
    else:
        _diag = self.evolver.diagnose([_sig])
        dispatch = {"kind": "evolve", "dispatched": True,
                    "n_signatures": 1,
                    "n_proposals": ..., "n_unmapped": ..., "n_clusters": ...}
```

### 三条分支都有锁

| 测试 | 断言 |
|------|------|
| `test_learn_not_dispatched_but_evolve_dispatches` | 有签名 ⇒ `dispatched=True` + `n_signatures=1` + `n_proposals` 是 int |
| `test_evolve_not_dispatched_without_signature` | 无签名 ⇒ `dispatched=False` + "无失败签名" |
| `test_evolve_not_dispatched_when_signature_incomplete` | 缺 q/fn ⇒ `dispatched=False` + "缺 c/q/fn" |

旧锁 `test_learn_evolve_not_dispatched_with_reason` 按行为语义变更**重锚**
（不是删除）：`learn` 仍无器官，`evolve` 改为真分发，并补了三条行为级断言。

另两处同步重锚（B1 改变了它们的判据面）：

| 旧锁 | 新语义 |
|------|--------|
| `test_r139_appendix_audit.py::test_routing_semantic_coverage` | `dispatched_true_branches` 2→3（remember/dream/evolve），`uncovered` 3→2（learn/maintain）；仍非全覆盖 ⇒ 判据口径不变 |
| `test_r141_quintet_truth.py::test_core_dispatch_why_corrected` | 从「断言 why 含『器官已实现』」改为「断言真调 `evolver.diagnose` + 旧『未接线』文字必须消失」 |

---

## 四、验证

| 项 | 结果 |
|----|------|
| 定向测试 | 25 passed（fitness 12 / harness 5 / routing 9） |
| gate | 8/8 全通过 |
| 11143 真实回归 | 见下 |

---

## 五、诚实边界

1. **B1 只让 `evolve` 可分发，没让它被调用** —— `DWC.step()` 在常驻 agent 路径上仍不可达
   （Phase A 审计结论）。要真正跑起来还需 B2（把 Loop/step 接进 `dwc_agent.py`）。
2. **`judgement` 只带一条签名** —— `_judge_and_backfill` 每次只产出一个
   `failure_signature`，所以 `diagnose` 的聚类能力当前用不上（n_signatures 恒为 1）。
   要发挥聚类，需要把 term 内的多条签名聚合后再分发。
3. **P2P 只在小集合（≤100）上验证** —— 大集合仍走 skipped，`p2p_ok=None`。
4. **`compare_policies` 只做比较，不做选择** —— 它输出可比数字，
   谁赢由调用方（未来的 evolver）决定。
