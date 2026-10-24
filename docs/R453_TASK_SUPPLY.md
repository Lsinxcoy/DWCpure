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

## 8. 还没做的

| 项 | 说明 |
|---|---|
| 难度自动升降 | `next_level()` 已实现但没接进循环（现在只造 L1/L2） |
| L3 常态化 | 需 LLM，目前手动跑 `scripts/supply_l3.py` |
| 供给题的难度验证 | 实测 L1/L2 题仍被 1.0 通过 ⇒ 难度还不够，"新题"≠"难题" |

> ★ 最后一条是诚实的边界：`fresh_range_sum` 一次就做对。
> 供给解决了"没有新题"，还没解决"新题不够难"。
> 真难度要靠 L3（新函数族）+ 阶梯升级接进循环。
