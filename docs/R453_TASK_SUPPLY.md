# R452–R453 · 任务供给（L1/L2/L3）落地记录

> 解决的问题：池子 16 题、最近 30 个 term `pass_rate` 全 1.0、`evo_feed.n_sigs` 全 0
> ⇒ 进化不是"学得不够"，是**没有东西可学**。
> 本模块让系统自己造题，且**题的真值可验证**。

---

## 1. 三个模块

| 模块 | 作用 | 是否用 LLM |
|---|---|---|
| `src/dwc/organs/refimpl.py` | 参考实现登记表（新题期望值的唯一合法来源） | ❌ |
| `src/dwc/organs/task_supply.py` | L1 扰动 / L2 fresh / L3 新函数族 + 队列 + 淘汰 | 仅 L3 |
| `scripts/supply_l3.py` | L3 独立入口（受预算约束，按需跑） | ✅ |

---

## 2. L1 · 参数扰动

**核心难点**：anchor 里只有 `(fn, args, expected)`，**没有原始实现** ——
想扰动参数就必须能重算 expected。

**解法**：`refimpl.py` 登记 11 个函数（dev 6 + fresh 5），并且必须先复现
**现有全部 anchor 检查**才有资格被用于生成。这条门由测试锁死：

```
tests/test_r452_refimpl.py::test_every_existing_check_reproduces
```

实测：dev + fresh 共 **21 条检查全部复现**（含 `average([])==0.0`、
`is_palindrome('Racecar')==True`、`sum_first_n(123456)==7620753696`）。

生成时：
- 每个 fn 一个采样器（int / list[int] / str 各自的合法取值域）
- 同 seed ⇒ 同题（`sha1(task_id|seed)`，**不用 `hash()`** —— 它每进程加盐）
- 新 args 与原 args 相同 ⇒ 该题作废（不把同一题抄一遍）

实测产出：9 道（`code_fix_001..009` 各一道扰动）。

## 3. L2 · fresh 接入

`fresh.json` 的 5 道现成题直接搬进队列（`level=2`，期望值文件自带，不改判分口径）。

## 4. L3 · 新函数族（两份独立实现）

**协议**（这是整块最关键的设计）：

```
第 1 次 LLM：出题 → {fn, prompt, impl_A}
第 2 次 LLM：**只给题面**（不给 impl_A）→ impl_B
逐输入跑 A/B：两边都成功且值相等 ⇒ 记一条 check
一致样本 ≥ 3 ⇒ 收题；否则拒收
```

**为什么第二份只给题面**：给了第一份就是抄，两份必然"一致"，
那种一致证明不了题面可判定。

### 踩到的三个坑（都已修）

| 坑 | 现象 | 修法 |
|---|---|---|
| 一次跑一批输入 | 任一输入类型不匹配 ⇒ 整批 None | 逐输入跑，单项失败不影响其他 |
| 返回 None 被当答案 | 造出"正确答案是 None"的垃圾题 | 观测值为 None ⇒ 该输入作废 |
| LLM 爱写 `while` | 沙箱 AST 层直接拒收 ⇒ B 永远 0 一致 | 出题提示里明写"禁止 while，只能用 for" |

### 实测产出率

| 轮次 | 结果 |
|---|---|
| 修 while 前 | 0/3（`agree=0`，B 全被沙箱拒） |
| 修 while 后 | **1/2**（`supply_collapse_runs` 10 checks；`supply_staircase_sum` 5 checks） |

> 产出率不高是**设计如此**：门是"两份独立实现逐输入一致"，
> 过不了说明题面有歧义或实现不合规 —— 那种题收进来只会污染判分器。

## 5. 队列与生灭（G4）

| 项 | 值 |
|---|---|
| 上限 `MAX_POOL` | 40 |
| 淘汰① | 连续 ≥2 次 pass_rate=1.0 ⇒ solved，淘汰 |
| 淘汰② | 14 天未解决 ⇒ 过期，淘汰 |
| 超限行为 | 先淘汰再封顶；收不下的**直接拒收**并写 stderr（不许悄悄扩容） |

## 6. 接线

```
agent 启动      _supply_sync(d)  → 队列里的题注入 judge.anchors（判分找得到）
每 tick         pool = tuple(供给题) + DEV_POOL   ← 新题优先
每 term 后      记录 pass_rate → 饱和(≥0.95/30轮) ⇒ 造 L1+L2（零 LLM）
```

`_seed_recent()` 从 `var/dwc_prod_log.jsonl` 尾部恢复最近 30 个 pass_rate，
重启后判据不失忆。

**实测**（16:16 那轮）：agent 直接选中 `fresh_range_sum`（L2 题），
`pass_rate=1.0` —— 说明队列真的进了轮转，不是只写不读。

## 7. 当前状态

```
var/task_queue.jsonl：15 道（L1=9 / L2=5 / L3=1）
```

## 8. 难度阶梯（R454 · 已接进循环）

状态文件 `var/supply_level.json`：

```json
{"level": 2, "since": 1792831806.7, "terms": 0, "why": "saturated"}
```

每个 term 调一次 `step_level(sat)`：

| 条件 | 动作 |
|---|---|
| 饱和（窗口均值 ≥ 0.95）且 `terms ≥ 3` 且过冷却 | 升一级 |
| 太难（均值 ≤ 0.60）且 `terms ≥ 3` 且过冷却 | 降一级 |
| 其余 | 原地不动，`terms += 1` |

**为什么必须有 `min_terms` + `cooldown` 双闸**：饱和判据看的是**整窗**通过率，
刚升到 L2 时窗里还是 L1 的成绩 —— 立刻再升就会一路窜到 L3，
那不是阶梯，是电梯。

各级动作（`plan_batch` 纯函数，可单测）：

| 级 | 动作 |
|---|---|
| L1 | 只造参数扰动 |
| L2 | 扰动 + fresh |
| L3 | **只写请求** `var/supply_escalate.json`，不起草 |

**为什么 L3 只写请求**：agent 是 `use_llm=false`，tick 里起草会阻塞主循环、
成本不可控。请求由带 LLM 的入口消费：

```
agent tick  →  var/supply_escalate.json
                    ↓ （消费即删除，一次性）
scripts/supply_l3.py            ← 手动
scripts/dwc_evo_round_cron.py   ← 04:00 进化轮开头自动跑
```

队列满（≥8 道未跑）时**连 L3 也不请求** —— 先把手里的题跑完，不然只是堆题。

实测：16:50 那轮 agent 从 L1 升到 L2 并落盘（`level=2, terms=0`），
请求→消费链路单独验过（写请求 → `supply_l3.py` 打印"消费升级请求：n=1" →
文件被删除 → `var/supply_l3_last.json` 记 `from_request: true`）。

L3 实测产出率约 **1/3**（失败时补一次"禁止 while"的重问后从 0/3 提到 1/3）。

## 9. 选择状态持久化（R455 · 让造出来的题真的被跑到）

**实测发现**：队列 15 道题，**只有 1 道跑过**（`fresh_range_sum` 跑了 3 次全 1.0），
其余 14 道从未执行。

**根因**（`scripts/dwc_agent.py`）：

```python
_sel = {"last": None, "streak": 0, "used": [], "cooldown": {}}
_day = {"key": ..., "terms": 0, "cost": 0.0}
...
cand = pool[_day["terms"] % len(pool)]
```

两个都是**内存变量**，从不落盘。进程一重启 `terms` 归零 ⇒ 永远回到 `pool[0]`。
当天重启 6 次 = 同一道题被喂了 6 遍。

**修法**：

| 件 | 说明 |
|---|---|
| `src/dwc/organs/selection_state.py` | `save/load` + `pick_with_supply` 纯函数 |
| `var/agent_sel.json` | `{sel: {last,streak,used,cooldown}, day: {key,terms,cost}}` |
| 落盘点 | `select_task()` 返回前 + 每个 term 计数后 |
| 加载点 | `main()` 启动时 `_load_state()` |
| 覆盖优先 | 队列里还有**从未跑过**的题 ⇒ 先跑它；全覆盖后回归正常轮转 |

**跨天语义**：只重置 `terms`/`cost`，`used`/`cooldown` 保留 ——
覆盖进度不能因过夜清零，否则第二天又从 `pool[0]` 开始。

**坏文件语义**：返回默认值，绝不抛 —— 选择器不该因台账损坏停摆。

**守卫的牙齿（变异验证）**：去掉 cooldown 过滤 / 去掉"已选保留" /
去掉跨天判断 / 去掉坏文件兜底 / 去掉池外过滤 —— 五个变异各自让对应测试变红，
还原后 12 passed。

## 10. 还没做的

| 项 | 说明 |
|---|---|
| 供给题的难度验证 | 实测 L1/L2 题仍被 1.0 通过 ⇒ 难度还不够，"新题"≠"难题" |
| L3 产出率 | ~1/3（两份独立实现一致才算数，门是硬的） |
| 降级路径实测 | `too_hard` 分支有单测，但生产还没出现过（一直是饱和） |

> ★ 最后一条是诚实的边界：`fresh_range_sum` 一次就做对。
> 供给解决了"没有新题"，难度阶梯解决了"按需加难"，
> 但**加难 ≠ 真难** —— L1/L2 的扰动题对现有能力仍然太浅。
> 真难度只能靠 L3 的新函数族，而 L3 受两份实现一致性的硬门约束（~1/3 产出率）。
