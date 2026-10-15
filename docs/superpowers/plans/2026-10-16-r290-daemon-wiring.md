# R290 · daemon 主循环接线方案（立项，只方案不动码）

> 目标：把 not_wired 清单（world.select / metric.select→adopt / direction.next_action）
> 和 legacy 退役条件①②，一次画全依赖再动手。不接假线。

## 一、现状实测（2026-10-16）

### 1.1 daemon 主循环（scripts/dwc_agent.py）

```
select_task（上轮 next_task_source.world_tree_action[0] ｜ DEV_POOL 轮询）
  → run_term(TermRunner) → report → _log/飞书 → 下一轮
```

- 任务源已通：`_next_task_source`（run_term.py:1111）产 dead/wire＋recall＋
  world_model.legal_actions＋R77δ排序＋R101组序 → select_task 消费 nodes[0]。
- **world.select 不在环上**：legal_actions 是"未揭示叶子枚举"，
  select（信息增益排序＋不回退，world_model.py:537）零调用。

### 1.2 三条未接线的真身

| # | 名 | 实现 | 需方 | 缺口 |
|---|---|---|---|---|
| ○-1 | world.select | 全（信息增益＋不回退保证） | _next_task_source 只调 legal_actions | **排序口径替换**：wta 排序从 δ/组序换成 information_gain？还是叠加？需决策 |
| ○-2 | metric.select→adopt | metric_loop.select（R177 选优树）全；accept 门全 | accept 要 baseline/current 两份判分＋held_out | **两块砖**：trial 回布尔无分数；held_out 缺失→accept 写死 blocked（test split 未落地） |
| ○-3 | direction.next_action | 全（R1/R2 fallback＋R3 记账，direction.py:281） | run_term 只剩 hint 字符串（:1269） | **轮内失败无方向切换**：step 失败→停滞→整轮失败，无 fallback |
| 半 | select_winner | evolver.py:449 全 | run_term 274/655/672 三处自首未接 | **盘点面**：改动评估器 U 未进盘点 |

### 1.3 legacy 退役条件（R289 已复核列齐）

- ① trial_fn 返回分数（现 `_real_trial` 回布尔；cron 同）
- ② accept 拿真 baseline/current（现占位 `{}` 必 not_evaluated；
  真输入要 metric.select→adopt，即 ○-2）
- ⇒ **legacy 退役 ＝ ○-2 摘牌之日**。○-2 又卡在 test split。

## 二、依赖图

```
test split 落地（大）
  └→ held_out 可算 → accept 可判 → ②齐
_trial 分数化（中：_real_trial 回判分 dict，success 照旧派生）
  └→ baseline（打 patch 前）/current（打后）两份数 → ①齐
①＋②齐 → ○-2 摘牌 → legacy 删分支 → adopt 门真判
world.select 接入（小—中：_next_task_source 排序口径决策＋替换）
direction.next_action 接入（中：run_term 轮内 step 失败→fallback→terminal 记账）
select_winner 接入（小：盘点 U 面调用 L449）
```

## 三、分阶段（严格按序，后阶段以前阶段验收为前提）

### P0 · 世界树排序口径（不动判定，只换任务源顺序）

- 决策（用户拍板二选一）：
  - A：wta 排序键换 information_gain（R77δ/组序降级为 tie-break）
  - B：information_gain 做第一排序键，δ/组序保留叠加
- 改点：`_next_task_source` 排序段（run_term.py:1140-1170 附近）
- 约束：集合不变只换序（R77 叠加承诺）；legal_actions 不动；select 不回退保证继承
- 验收：旧测试全绿＋新测（排序键=信息增益，current 必在集）＋生产一轮任务源顺序变化留痕

### P1 · trial 分数化（①）

- 改点：`_real_trial`（evo_round.py:150）回判分 dict
  `{success, in_score, detail}`，调用方 `t is True` 改 `r.success`
  （cron 同改；bool 派生不断旧语义）
- 验收：R279/R285 试跑测试全绿＋`TRIAL_SUCCESS` 口径不变

### P2 · direction 起草环 fallback（○-3）【接线点已修正】

- ~~run_term 轮内 step~~ → 真接线点=LLMMutator.propose_from_cluster
  （_step 无失败语义，硬接=造语义；起草全废才是真"方向无对象" R1 形态③）
- 改点：起草前 `next_action(history, 0, task)` 选方向；成功记 n=1/全废记
  n=0；三耗尽抛 DirectionError（run_round 已隔离，单簇留痕不掀轮）
- 约束：方向不进 prompt（prompt 方向化是 P4+）；state 实例级（每轮新
  实例，三方向额度，max_clusters=3 刚好）
- 验收：新测（首选＋记账／全废换向／三耗尽抛）＋R278/R279 旧全绿

### P3 · select_winner（○-半 → 判无场景，不接线）

- 核实（2026-10-16）：`select_winner(evolver.py:449)` 要 `(candidate, score,
  passed_gate)` 判分竞争池。run_term 盘点是 term 五元 χ，无候选池 ——
  空池调即报错（硬要求①），喂池即编造竞争。metric_loop.select 是候选
  **树**选优（S 分语义），与判分＋过门语义错配，硬套即造语义。
- 结论：生产无"多 proposal 比分"场景（adopt 门一次一 proposal）⇒
  **P3 无真接线点，不做假线**。U 保持 R141 partial 如实＋R196 锁不动。
- 真场景出现之日（多 proposal 同轮竞争）再接 —— 本 plan 不预支。

### P4 · test split 立项（大，另起 plan）

- 内容：dev/tasks 切 train/test（held_out 口径）→ accept 可判→②齐→○-2 摘牌→legacy 删
- 本 plan 不展开，只定前置：P1 的分数是 split 的输入（先有分数才有 split 可切）

## 四、全局约束（R287 纪律沿用）

- 测试零真 LLM（fake＋raises≥5%）；不动生产判定只增调用；
- anchor 只增不改；双副本 md5 同步；落盘默认关；
- evidence_ref 带 task 名；credit 单笔坏隔离不掀轮；
- 无根因更新打回；禁全文件 sed 批量改数。

## 五、Review Focus

- P0 决策 A/B 请用户拍板（排序口径是行为变更，虽不动判定但动任务源顺序）
- P1 的 dict 回值是否破坏 cron/daemon 其他消费方（grep 全仓 `t is True` 式消费）
- P2 state 生命周期（轮内累积 vs 跨轮，方向污染边界）
- P4 test split 是否真有必要（替代：accept 降级口径？—— R73 禁止改判定迁就，需拍板）
