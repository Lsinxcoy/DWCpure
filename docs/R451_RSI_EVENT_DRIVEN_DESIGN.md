# R451 · 从「定时进化」到「事件驱动进化」

> 结论先行：**P0 已落地**（规则热加载，闭合 RSI 回路最后一米）。
> **P1 是事件门控**（不是"每 tick 起草"）。
> **P2 被实测重定义了**——真正的瓶颈不是"行为车道不可学"，而是
> **系统已经没有失败了**：最近 30 个 term 的 `pass_rate` 全是 1.0。

---

## 1. 现状（逐行核实）

| 环节 | 驱动方式 | 代码位置 |
|---|---|---|
| 观察（跑 term） | tick（interval=600s，实测约 30min/term） | `dwc_agent.py` 主循环 |
| 诊断（失败签名→提案） | **每 term 结束立刻** | `core.py:518` → `core.py:570` `diagnose()` |
| 提案落盘 | 每 term | `core.py:588` → `var/evo_proposals.jsonl` |
| 起草→试跑→落地 | **cron 04:00，独立进程** | `scripts/dwc_evo_round_cron.py` |
| 落地后同进程生效 | ✅ | `evolver.py:2645` `reload_learned()` |
| 落地后**其他进程**生效 | ❌ 改前永不重载 | `evolver.py:2970` 只在 import 加载 |

所以准确说法是：**观察是 tick 驱动，行动是 cron 驱动，而行动的结果对运行中的系统不可见**。

---

## 2. P0 · 规则热加载（已实现）

### 2.1 API

```python
# src/dwc/organs/evolver.py
Mutator.reload_if_changed() -> int   # 返回**新增**键数
```

语义（每条都有测试锁）：

| 情况 | 返回 | 理由 |
|---|---|---|
| 文件不存在 | 0，不抛 | 没学到过是常态 |
| mtime 没变 | 0，只做一次 stat | 每 tick 都调，必须便宜 |
| mtime 变了、有新键 | 新键数 | 正常热加载 |
| mtime 变了、无新键 | 0 | 规则只增不改，谎报"加载 N 条"会让日志失真 |
| JSON 坏 | 0，不抛，且记下 mtime | 避免每 tick 刷日志 |

### 2.2 接线

```python
# scripts/dwc_agent.py 主循环（每 tick，在 maybe_dispatch_reading() 之后）
from dwc.organs.evolver import Mutator as _MuReload
_n_new = _MuReload.reload_if_changed()
if _n_new:
    _log({"event": "rules_reloaded", "n_new": _n_new})
```

失败只写 `rules_reload_error` 台账，**不掀 tick**。

### 2.3 测试

`tests/test_r451_rule_reload.py`（5 条）：缺失文件 / 未变 / 新键 / 同内容新 mtime / 坏 JSON。

---

## 3. P1 · 事件门控（完整设计）

### 3.1 事件源必须选对

| 候选 | 能不能用 | 原因 |
|---|---|---|
| `failure_sig` 表 | ❌ | 只有 `(c, q, m, node_id)`——**没有时间、任务、fn**，无法回答"自上次以来新增了什么" |
| `evo_proposals.jsonl` | ✅ | 有 `ts / term_id / chain_id / key / sig{fn,task}`，且每 term 追加 |

**结论：事件源 = `var/evo_proposals.jsonl` 里 `kind=unmapped` 且未被消费的记录。**

### 3.2 新模块

`src/dwc/organs/evo_trigger.py`

```python
DEFAULTS = {
    "min_cluster_sigs": 3,      # 一个 (c,q) 至少 3 条才值得起草
    "cooldown_s": 1800,         # 两轮之间至少 30 分钟
    "max_rounds_per_day": 6,    # 每天最多 6 轮（预算硬顶）
    "stale_lock_s": 7200,       # 锁超过 2h 视为陈旧，可抢占
}

def pending(path, since_ts=0.0) -> Dict[str, Dict[str, Any]]:
    """{key: {"n_sigs": n, "tasks": [...], "sigs": [...]}}，只收未消费的 unmapped。"""

def decide(now, pending, state, cfg) -> Tuple[bool, str]:
    """返回 (是否启动, 原因)。原因字符串必须能直接进日志。"""

def acquire_lock(path, now) -> bool:
    """O_CREAT|O_EXCL 建锁；已存在则读 pid+ts，pid 死了或超时 ⇒ 抢占。"""

def release_lock(path) -> None: ...

def launch(root, python, args) -> int:
    """detached 起子进程跑 dwc_evo_round.py --from-proposals ...，返回 pid。"""

def maybe_launch(now=None) -> Dict[str, Any]:
    """agent tick 的唯一入口：读盘 → decide → launch/release，返回决策记录。"""
```

### 3.3 门控条件（全绿才起）

| # | 条件 | 默认 | 为什么 |
|---|---|---|---|
| 1 | 存在 `n_sigs >= 3` 的待起草簇 | 3 | 1 条签名不是"簇"，是噪声 |
| 2 | 距上次启动 ≥ cooldown | 1800s | 防止故障时疯狂重启 |
| 3 | 今日轮次 < max_rounds_per_day | 6 | 成本硬顶 |
| 4 | 今日 token < max_tokens_per_day | 60000 | 与 `by_profile` 同口径计量 |
| 5 | 能拿到锁 | — | 防并发双跑（已有教训：两个 `--deep-task` 同时落同一键） |

任一条不满足 ⇒ 返回原因并写一行决策日志，**不起进程**。

### 3.4 状态与锁

```
var/evo_trigger_state.json
  {"day": "2026-10-24", "rounds": 2, "tokens": 3900,
   "last_launch_ts": 1792..., "last_reason": "ok"}

var/evo_round.lock
  {"pid": 40584, "ts": 1792..., "round_id": "..."}
```

跨日重置：`day` 变化时 `rounds/tokens` 归零。

### 3.5 为什么用 detached 子进程，而不是进程内起草

| 方案 | 问题 |
|---|---|
| agent 进程内起草 | agent 是 `use_llm=false`，要注入 LLM；起草会阻塞 tick；崩溃拖垮主循环 |
| **detached 子进程** | 已有 `--from-proposals` 入口；崩溃隔离；tick 只花一次 stat+读小文件 |

子进程用 `.hermes-runtime` 的 python 3.11（与 cron 一致），`DETACHED_PROCESS | CREATE_BREAKAWAY_FROM_JOB`。

### 3.6 幂等

- `pending()` 排除已标记 `consumed` 的记录（现有机制：`consumed: 0/8 簇已落地并标记`）。
- 同一 `key` 每自然日最多尝试 1 次（`_done` 集合，`dwc_evo_round.py` 已有）。
- 试跑失败 ⇒ 记录 `last_attempt[key]=ts`，冷却期内不再试同一 key。

### 3.7 可观测

新增 `var/evo_trigger.jsonl`，每次决策一行：

```json
{"ts": ..., "decision": "launch|skip", "reason": "cooldown",
 "n_pending": 4, "n_eligible": 1, "rounds_today": 2, "tokens_today": 3900}
```

报告里加 `trigger` 块，与 `cost_attribution` 并列。

### 3.8 测试清单（12 条）

1. 无 pending ⇒ skip，原因 `no_pending`
2. pending 但都 < 3 条 ⇒ skip，`below_min_cluster`
3. cooldown 未过 ⇒ skip
4. 今日轮次超限 ⇒ skip
5. 今日 token 超限 ⇒ skip
6. 锁被活进程持有 ⇒ skip
7. 锁的 pid 已死 ⇒ 抢占并 launch
8. 锁超时 ⇒ 抢占并 launch
9. 全绿 ⇒ launch 被调用一次（monkeypatch launch，断言参数含 `--from-proposals`）
10. 跨日 ⇒ rounds/tokens 归零
11. `pending()` 排除 consumed
12. `pending()` 按 key 聚合并统计 tasks

### 3.9 验收标准

- 连跑 24h，`evo_trigger.jsonl` 里 **launch 次数 ≤ 6**，且每次都有对应 round 台账。
- 无锁冲突（同一时刻只有一个 round 进程）。
- tick 增加耗时 < 5ms（实测 `stat` + 读 335KB jsonl 需缓存；用 mtime 缓存，见下）。

> 性能细节：`evo_proposals.jsonl` 会到几十万行。`pending()` 必须**按 mtime 缓存**
> 上次读到的 offset，只读新增尾部，不许每 tick 全量 parse。

### 3.10 ★ 诚实前提

**现在这条门永远不会打开**：`var/evo_proposals.jsonl` 最后一条是 **10-23**，
10-24 全天零新增（见 §4.1）。P1 建好之后会一直报 `no_pending`。

所以 P1 的价值是"有信号时立刻响应"，**不是"制造信号"**——那是 P2。

---

## 4. P2 · 信号供给（设计，且被实测重定义）

### 4.1 证据链

| 事实 | 数据 |
|---|---|
| 最近 30 个 term 全部通过 | `pass_rate` 分布 `{'1.0': 30}` |
| 今日每个 term 的 `evo_feed` | `n_sigs: 0`（"本 term 无可用失败签名"） |
| `evo_proposals.jsonl` 新增 | 10-20:155 / 10-21:343 / 10-22:520 / 10-23:164 / **10-24:0** |
| `failure_sig` 表 | 2107 行，**全部** `llm_asserted:*`（历史积累） |
| 任务池规模 | `DEV_POOL` = 16（code_fix 9 + reasoning 4 + reproduce 3） |
| 未使用的 split | `fresh.json` 6 条（judge 读它，但没有喂进池） |

**结论：不是"行为车道不可学"，而是"已经没有失败了"。**

一个 16 任务的池子被跑了几千轮，全过——此时无论 cron 还是 tick，
进化都只能空转。这正是 RSI 的边界条件：**改进速度受限于新问题的供给速度**。

### 4.2 设计目标

让系统**持续产生"刚好不会做"的任务**，而不是让它在已会的事情上刷分。

### 4.3 新模块

`src/dwc/organs/task_supply.py`

```python
SATURATION_WINDOW = 30
SATURATION_PASS = 0.95

def saturation(terms, window=SATURATION_WINDOW) -> Dict[str, Any]:
    """最近 window 个 term 的 pass_rate 均值与饱和判定。"""

def ladder_step(current_level) -> int:
    """难度阶梯：0=池内原题, 1=参数扰动, 2=fresh split, 3=新函数族。"""

def propose_tasks(level, n=3, anchors=None) -> List[Dict[str, Any]]:
    """按等级产候选任务（带 provenance，标明来源与难度）。"""

def admit(task, path) -> bool:
    """写进待跑队列（不进 DEV_POOL 常量——池子是代码，队列是数据）。"""

def maybe_escalate(terms, path) -> Dict[str, Any]:
    """饱和 ⇒ 升一级并 admit；未饱和 ⇒ 不动（不猜）。"""
```

### 4.4 难度阶梯（四级，每级都有验收口径）

| 级 | 内容 | 来源 | 为什么这一级 |
|---|---|---|---|
| L0 | 池内原题 | `DEV_POOL` | 基线，已饱和 |
| L1 | 原题参数扰动（n、边界、类型） | 模板 | 不改题型，只改难度；能测"是否真会" |
| L2 | `fresh.json` 6 条未用锚 | 已有数据 | 现成、干净、未污染 |
| L3 | 新函数族（同 c/q 分类下的新 fn） | anchors 扩展 | 真正的新分布 |

**升级判据**：最近 30 term `pass_rate` 均值 ≥ 0.95 ⇒ 升一级；升级后若连续 30 term
均值 ≤ 0.6 ⇒ 降一级（防止难度失控）。

### 4.5 与进化系统的接口

- 新任务进**待跑队列**（`var/task_queue.jsonl`），`select_task` 优先取队列。
- 新任务同样产出失败签名 → 走现有 `_feed_evolver` → `evo_proposals` → P1 事件门控。
- **不需要改判分器**：`judge` 用 anchors 的 `checks`，新任务带自己的 checks。

### 4.6 行为车道的定位（保留，但降级为消费者）

2093 条行为签名说明：当 executor 在跑时，行为失败是**主流**。
P2 完成后失败会重新出现，届时：
- 代码车道：`probe_signatures` 命中 ⇒ 起草补丁（现有路径）。
- 行为车道：不产代码，产 **lesson**（`library.add`，只注 lesson 不注 code，R447 已就绪）。
- 两者共用 `hint_for` 注入起草提示。

### 4.7 测试清单

1. `saturation()` 对全 1.0 返回 `saturated=True`
2. 混合通过率不误判饱和
3. `ladder_step` 单调、有上下界
4. L1 扰动任务与原任务 `checks` 形态一致（否则 judge 判不了）
5. L2 只取 `fresh.json` 未用过的条目
6. `admit` 幂等（同 task 不重复入队）
7. `maybe_escalate` 未饱和时**不动**（不猜、不预生成）
8. 队列空时 `select_task` 行为逐字节不变（回归锁）

### 4.8 风险

| 风险 | 缓解 |
|---|---|
| 自造任务判分不公 | 新任务必须带可执行的 `checks`；无 checks 不入队 |
| 难度失控 | 双向判据（0.95 升 / 0.6 降） |
| 任务污染训练集 | 新任务标 `split="supply"`，不进 `train/dev` 统计 |
| 生成成本 | L1 用模板（零 LLM），L3 才用 LLM 且受日预算约束 |

---

## 5. 实施顺序（与上一轮建议不同，已按实测调整）

| 顺序 | 项 | 依赖 | 价值 |
|---|---|---|---|
| ✅ 已完成 | P0 热加载 | — | 让"落地"真的生效 |
| **1** | **P2 信号供给** | — | **没有它，P1 永远不触发** |
| 2 | P1 事件门控 | P2 有信号 | 把失败→学习的延迟从 24h 降到分钟级 |
| 3 | 行为车道 lesson 化 | P1 + 信号 | 让 2093 类行为失败可学 |

> 上一轮我说"P0 → P1 → P2"，那是**按依赖排的**。
> 按**价值**排，P2 必须在前——否则 P1 只是一个永远 `no_pending` 的空门。

---

## 6. 明确不做

- ❌ 不在 agent tick 里起草（阻塞 + 无 LLM + 预算不可控）
- ❌ 不做"每 tick 一轮"（144 轮/天 × 3 簇 ≈ 576k token/天，且 99% 空转）
- ❌ 不用 `failure_sig` 表做增量判断（它没有时间列）
- ❌ 不为了"有信号"而降判分标准（那是自欺）
