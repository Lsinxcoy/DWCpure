# R456 · 让 term 变真：从"参考答案自判"到"模型作答"

> 一句话：**之前的 term 里没有模型。** 它拿六个参考答案去对自己的期望值，
> 所以 `pass_rate` 恒等于 1.0 —— 不是题简单，是环里没有人答题。

## 1. 病根（代码级）

生产 agent 走 `use_llm = "--llm" in argv` ⇒ 默认 `False`，于是：

```python
# scripts/dwc_agent.py（R456 前）
def exe(task):
    r = execute_task(actor, d.judge, task["task_id"])   # ← 没传 implementation
    return Receipt(...)
```

```python
# src/dwc/organs/actor.py
ex = PureFunctionExecutor(fn_name, source=implementation, ...)
# implementation=None ⇒ 用 REFERENCE（六个正确实现）
```

而 `_build_observations` 对 **judge.anchors 里所有 behavior 题**跑一遍 executor：

| 题 | 结果 |
|---|---|
| 6 道 dev behavior 题 | 跑参考答案 → 判分 → **必过** |
| 全部供给题（L1/L2/L3） | `KeyError`（`REFERENCE` 只有 6 个 fn）→ `executor_raised` → not_evaluated |

`pass_rate` 的分母只算 evaluated ⇒ **恒 1.0**。

实测（R456 前）：

```
最近 20 个 term：{'1.0': 20}
failure_sig 2,107 条，被取回 4 次（0.2%）
```

供给（R453）、难度阶梯（R454）、选择持久化（R455）全建在这个环上 ——
它们能造题、能选题，但**产不出任何信号**。

## 2. 修法

| 改动 | 位置 | 为什么 |
|---|---|---|
| 默认真模型 | `dwc_agent.py` `use_llm = "--selfcheck" not in argv` | 要"真跑"必须是默认；自检要显式声明 |
| 模式记账 | `agent_started` / `agent_term` 加 `mode` | 分数必须能追溯到"谁答的" |
| 自检分数隔离 | `_seed_recent` 只认 `mode=="llm"`；饱和判据只在 `use_llm` 时喂 | 参考答案的 1.0 不许当饱和证据 |
| 观测收窄 | `TermReport.task` + `_build_observations` 只跑当前题 | 全量判 = 每轮 6~20 次模型调用，且别的题会混进本轮分数 |
| 执行体先于注入 | 先 `_supply_sync(d)` 再建 `LLMExecutorFactory(anchors=d.judge.anchors)` | 工厂读构造时的 anchors 快照，先建后注入 ⇒ 供给题永远 `llm_not_enabled` |

## 3. 实测（R456 后）

### 单题路径（生产同款，db 在临时目录）

```
term 完成 3.1s
  rep.task      = fresh_range_sum
  score_delta   = 1.0
  synthetic     = False
  executor 调用 = {'n_calls': 1, 'n_parsed': 1, 'n_errors': 0}
```

一次调用、3 秒、真模型作答。

### 多题分布（真信号出现）

| 题 | pass | k |
|---|---|---|
| fresh_fib | 1.0 | 2/2 |
| fresh_vowel_count | 1.0 | 2/2 |
| **code_fix_001__p1_s20750** | **0.0** | **1/2** |
| supply_staircase_sum_8efd2143 | 1.0 | 5/5 |

### 生产首个真 term（20:35:19）

```
{'event': 'agent_started', 'mode': 'llm', 'pid': 46040}
{'agent_term': 6, 'task': 'code_fix_001__p1_s20750',
 'mode': 'llm', 'pass_rate': 0.0, 'cost': 1.0}
```

连带效果：

- `failure_sig` **2,107 → 2,108**，新签名 `E_VALUE / wrong_magnitude / llm_asserted:668346`
- `memory_node` **5,067 → 5,073**（本轮 trace 写入）
- `llm_usage` 115 行，最近一条 `prompt=125 / completion=23`

**这是这个环第一次产出真实失败信号。**

## 4. 诚实边界（还没做的）

1. **模型只"算输出"，不写代码**：`LLMExecutorFactory` 让模型对给定 args 预测返回值，
   不是生成实现再沙箱执行。真正的代码生成在 `task_exec` 原生工具链（收件箱路径），
   还没接进 term。所以现在的 term 测的是"算得对不对"，不是"写得对不对"。
2. **记忆通道是通的但空的**：`memory_text()` 读 `kind='skill'` 的节点，
   生产里 **skill = 0** ⇒ prompt 里"已知参考资料"永远是「（无）」。
   这是下一步（记忆深化 A 的读端闭环）要填的。
3. **`cost` 仍是合成计数 1.0**，不是真钱；真实用量在 `var/llm_usage.jsonl`，
   `cost_usd` 为 null（缺价目表）。
4. 自检模式保留（`--selfcheck`）但分数隔离 —— 它只用于排障，不参与任何判据。

## 5. 验收

- 新测试 `tests/test_r456_real_term.py`：5 条（报告带 task / 只跑当前题 /
  回退全量 / 自检行不进饱和 / llm 行保留）
- 全量 **2903 passed / 373.14s / EXIT=0**
- `scripts/gate.py` 八门全绿
- 生产真身 46040，`mode=llm`，首轮 `pass_rate=0.0`
