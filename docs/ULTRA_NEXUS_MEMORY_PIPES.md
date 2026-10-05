# Ultra / Nexus 记忆系统与七管 —— 实测对照

> 2026-10-03 · 判据：只报实测，区分设计/实现/落地
> 触发：用户称"ultra 和 nexus 的记忆系统和七管系统运作的更好"
> ★ 本文含一处对前文的更正（母巢零引用计数口径错误）

---

## 〇、先说一处更正（我的错误）

```text
我在《母巢记忆系统实测》里报: "记忆机制 59 个, 32 个零生产引用 (54%)"
★ 那个数字用的是宽正则 (\b模块名\b), 会把同名变量也算进去。

用与 Ultra/Nexus 完全相同的严格标准 (memory.X / from ..memory import X) 重测:
  母巢: 零引用 4 个 (6.8%)   ← 不是 32
  仅测试引用、无生产引用: 29 个

★ 更正后的正确数字:
  母巢 59 模块: 有生产引用 30 (50.8%) / 仅测试引用 29 / 完全零引用 4
```

**保留原数字在文档里的做法是错的，已在本表统一口径。**

---

## 一、三边同一标准对照

```text
              模块数   零引用    有生产引用
母巢            59      4 (6.8%)   30 (50.8%)
Ultra           26      0 (0.0%)   26 (100.0%)
Nexus           26      0 (0.0%)   26 (100.0%)

★ Ultra/Nexus 的 memory 模块 100% 有生产引用 —— 这一点确实优于母巢。
★ 但要注意: Ultra/Nexus 各只有 26 个模块 (母巢 59), 
  且两边 memory/ 内容同源 (mempo 37KB / four_network 33KB 逐字节同规模)
```

**用户说"运作更好"，在"机制接线率"这一项上成立。**

---

## 二、七管：Ultra/Nexus 的核心改进 = CNS 条件触发链

### 2.1 母巢的七管：每轮全跑

```text
母巢 cns/dag_scheduler.py:
  _DEP_EDGES = { recall:[remember], learn:[recall], reflect:[learn],
                 evolve:[reflect], dream:[learn], maintain:[dream,recall] }
  run_all(): for stage in self._order: await fn(ctx)
★ 七管每轮全部执行, 无选择
```

### 2.2 Ultra/Nexus 的七管：条件触发链（★ 这就是"更好"的地方）

```text
Ultra/Nexus lifecycle/cns_orchestrator.py (25.8KB / 27KB):

  """Design principles:
     - Condition-based triggers, not always-on (avoids wasted cycles)
     - Circuit breaker prevents infinite loops via max depth + min intervals
     - State machine visible for observability"""

  订阅全部 7 个管道的完成事件:
    remember_completed / recall_completed / learn_completed /
    reflect_completed / evolve_completed / dream_completed / maintain_completed

  触发规则 (阈值驱动):
    learn 完成 + nodes≥1        → reflect
    reflect 完成 + score<0.5    → evolve
    reflect 完成 + score>0.8    → dream (不 evolve)
    evolve 完成 + delta>0.02    → dream (巩固成果)
    dream 完成 + patterns≥1     → maintain
    remember + 每100节点         → 检查 reflect

  熔断: _MAX_AUTO_DEPTH = 6, 最小间隔 {reflect:30s, evolve:60s, dream:120s, maintain:60s}
```

**★ 这是关键设计**：不是"全跑"，也不是"选一个"，而是**事件驱动 + 阈值条件 + 熔断**。

### 2.3 与 DWC 刚讨论的"七管 × 5动作结合"的关系

```text
我上一轮给的结合方案:  governor 选动作 + recall/reflect 无条件跑
Ultra 的实际做法:     事件订阅 + 阈值条件触发 + 熔断

★ Ultra 的做法比我给的方案更细:
  它不需要一个"governor"来选 —— 触发条件本身就是决策
  例: reflect 出来 score=0.4 ⇒ 自动触发 evolve (不是 governor 选的)

★ 而且它解决了 DWC 方案里的一个隐患:
  我写"recall/reflect 每轮无条件跑" ⇒ 会浪费周期
  Ultra 的做法: remember 累计到 100 节点才检查 reflect ⇒ 省周期
```

### 2.4 Ultra/Nexus 的驱动源：心跳线程

```text
life.py: "# 自发心跳线程 — 每60分钟自动触发 learn，CNS 链完成剩余管道"
  self._heartbeat_interval = 3600
  self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)

  _heartbeat_loop(): 每 3600s → self.learn(source="web", query=hb_query)
                     然后 CNS 自动链式触发 reflect→evolve→dream→maintain
  ★ 有 focus_topics 时优先扫长期关注主题, 而非固定 "auto heartbeat"
```

**★ 这解决了 DWC 的 §9.1（actor 任务源）**：

```text
ARSI: actor 不做任务 (等宿主 ingest_trace)
Ultra: 心跳线程每 60min 自己发起 learn —— ★ 有自发任务源
★ DWC 可直接采纳: 心跳 + focus_topics
```

---

## 三、但实测数据不支持"运作更好"的全部结论

### 3.1 Ultra 生产库实测（runner.db / prometheus_ultra.db）

```text
runner.db  (06-30 08:43 ~ 07-13 15:58, 319 小时)
  nodes               1,835      edges 12,968
  evolution_log      30,843      dream_log 9,290
  maintenance_log    21,611
  ★ failure_log           0      ← 零失败记录

  access_count = 0:  1,835 / 1,835  (★ 100.0%)
  content 样本: 'C1 fact 0: neural networks evolve through gradient'
                'quantum networks evolve through attention'   ← 测试数据

prometheus_ultra.db (07-01 ~ 07-17)
  nodes               1,967
  ★ access_count=0:  1,739 / 1,967 (88.4%)
  content 样本: 'AAAAAAAAAA...' / 'burst test 0' / 'burst test 1'  ← 测试数据
```

### 3.2 evolution_log 的实质：两条硬编码

```text
strategy 分布:  maintain 21,611  |  dream 9,232  |  ★ evolve 0

log_evolution 全仓只有 2 个调用点:
  self.store.log_evolution(cycle_id, 0.0, patterns/len(nodes), "dream")
  self.store.log_evolution("maintain", 0.5, 0.6, "maintain")   ← ★ 常量 0.5→0.6

实测 delta:
  maintain  n=21,611  min=0.1000 max=0.1000 avg=0.1000   ← ★ 全部恰好 0.1 (硬编码)
  dream     n=9,232   avg=0.0036
(before,after) 组合 top: (0.50, 0.60) × 21,611            ← ★ 同一对常量

★ evolve() 函数内 0 处 log_evolution ⇒ 进化真的跑过也不留痕
★ 这跟母巢"op 只有 evolve 一个值"是同一个病: 日志不反映真实进化
```

### 3.3 CNS 是否真跑过 —— 无证据

```text
- 全仓无 CNS 运行时落盘文件 (无 chain/trigger 日志)
- 唯一日志文件 src/wal_logs/wal.log, 无 Heartbeat/CNS 字样
- 库文件 mtime: runner.db 2026-07-13, ultra.db 07-17, nexus.db 07-21 ⇒ 已停
- CNSOrchestrator 生产接线仅 3 处 (life.py / cerebral_cortex.py / __init__.py)
★ CNS 代码质量高, 但"真跑过且效果好"无实测证据
```

### 3.4 dream 用独立 `_memories`，不读 store（用户自己的文档已指出）

```text
docs/multi_type_kb_seven_pipe_evolution.md (用户设计文档, 原文):

  "T3/T4 产物在 store 外: 机制草案存 MechanismRegistry (独立 dict),
   技能存 skill_registry —— 与 store 三分裂, 违反'七管道共享记忆和知识积累'"

  "dream 用独立 _memories list (dream_cycle.py:44), 不读 store 的多类型节点"

  "recall/maintain/reflect 假设均匀节点: 113 处读节点无类型区分"

实测确认: dream_cycle.py 里 _memories 出现 14 次, self.store 出现 0 次
★ 七管"共享记忆"在 Ultra/Nexus 也未做到 —— 用户自己已经写下来了
```

### 3.5 recall 不递增 access_count（与母巢同一个病）

```text
Ultra life.py recall(): touch 0 次 / access_count 0 次 / store.update 0 次
⇒ recall 取回记忆但不落"被用过"的痕迹

实测: runner.db access_count>0 = 0/1835 (100% 未用)
      ultra.db  access_count>0 = 228/1967 (88.4% 未用)
★ 与母巢 98.8% 未访问是同一类病, 只是程度轻
```

---

## 四、结论：哪些确实更好，哪些不成立

### 确实更好（可直接采纳进 DWC）

```text
① CNS 条件触发链 (★ 最有价值)
   事件订阅 + 阈值条件 + 熔断(max_depth=6 + min_interval)
   ★ 比我上一轮给的"governor 选 + recall/reflect 无条件跑"更细, 更省周期

② 心跳线程 = 自发任务源
   每 3600s 自动 learn, CNS 链完成剩余
   ★ 直接解 DWC §9.1 (actor 任务源未定)

③ 记忆机制 100% 接线 (26/26)
   vs 母巢 50.8% 有生产引用

④ 阈值可运行时调整 (update_threshold) + 状态机可见 (get_state)
```

### 不成立（用户判断与实测有出入）

```text
✗ "进化跑得更好"
  evolution_log 里 evolve = 0 条; maintain 全是常量 (0.5,0.6) 硬编码
  evolve() 内不写日志 ⇒ 与母巢同病

✗ "记忆被更好地使用"
  access_count>0: runner 0% / ultra 11.6%  ← 比母巢 1.2% 好, 但仍是绝大部分未用
  recall() 不递增 access_count (代码级)

✗ "七管共享记忆"
  用户自己的设计文档已指出: store / skill_registry / MechanismRegistry 三分裂
  dream_cycle 用独立 _memories (实测 14 次引用, self.store 0 次)

✗ "运作更好"无运行证据
  无 CNS 运行落盘; 库已停更 (07-13 / 07-17 / 07-21); failure_log 0 行
```

---

## 五、对 DWC 的三条直接采纳

```text
采纳 1 · 七管调度形态改用 CNS 式条件触发链
  不用"每轮全跑"(母巢), 也不用"选一个"(ARSI)
  用"事件 + 阈值 + 熔断":
    learn_done + nodes≥1     → reflect
    reflect_done + score<0.5 → evolve
    reflect_done + score>0.8 → dream
    evolve_done + delta>0.02 → dream
    dream_done + patterns≥1  → maintain
    remember + 每N节点        → 检查 reflect
  熔断: max_depth=6 + 各管最小间隔
  ★ 依据: Ultra CNS 25.8KB 实现, 设计原则写明 "not always-on (avoids wasted cycles)"

采纳 2 · 心跳线程作为自发任务源 (解 §9.1)
  每 3600s 自动发起一次 learn, 由 CNS 链完成剩余
  有 focus_topics 时优先扫长期关注主题
  ★ 依据: Ultra life.py _heartbeat_loop

采纳 3 · 机制接线率作为硬判据
  Ultra/Nexus 26/26 (100%) vs 母巢 30/59 (50.8%)
  ★ 并入原则 8: 机制零引用即违规 (严格正则口径)
```

### 一条不采纳 + 一条要修

```text
✗ 不采纳: Ultra 的 evolution_log 写法 (常量 + evolve 不留痕)
  ★ DWC 必须: evolve 真跑就留痕, 且 before/after 必须是实测值

★ 要修: recall 必须递增 access_count 并落库
  Ultra 与母巢都没做 ⇒ DWC 原则 7 必须代码级强制
```

---

## 六、三边总表

| 维度 | 母巢 | Ultra | Nexus | DWC 采纳 |
|---|---|---|---|---|
| 记忆模块数 | 59 | 26 | 26 | — |
| 有生产引用 | 30 (50.8%) | 26 (100%) | 26 (100%) | ★ 采纳判据 |
| 七管调度 | 全跑 (DAG run_all) | ★ 条件触发链 | 条件触发链 | ★ 采纳 Ultra |
| 熔断 | 有 (SGH 计划/恢复) | max_depth=6 + 间隔 | 同 | ★ 采纳 |
| 自发任务源 | 无 (等宿主) | ★ 心跳 3600s | 同 | ★ 采纳 |
| 共享同一 store | 是 (但 32 模块未接线) | ✗ 三分裂 | ✗ 三分裂 | ★ 必须统一 |
| recall 落 access | ✗ | ✗ | ✗ | ★ 必须修 |
| evolve 留痕 | op 单值 | ✗ 0 条 | ✗ | ★ 必须修 |
| 真实运行证据 | 44 天留痕 | 319h 但已停 | 已停 | — |
