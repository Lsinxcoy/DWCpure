# Phase B2 · 失败签名喂给 evolver（2026-10-19）

> 一句话：**生产 term 的失败签名第一次真正流进进化系统** —— 之前它们只回灌 EXPERIENCE 记忆，evolver 在生产上零输入。

---

## 一、缺口

B1 让 `DWC.step()` 的 `evolve` 分支可以真分发，但 `DWC.step()` **不在常驻 agent 路径上**。

常驻 agent 的真实路径（`scripts/dwc_agent.py:688`）：

```
d.run_term(task) → DWC.run_term → TermRunner.run_term → 六层链 → judge
```

`TermRunner._backfill_failures()` 把 `success is False` 的签名写进 `self.memory`
（EXPERIENCE），**到此为止**。`Evolver` 在生产上没有任何输入 ——
`scripts/dwc_evo_round.py` 是另一个独立脚本，不在 agent 循环里。

⇒ 结论：**进化系统有器官、有提案能力，但生产上没有燃料。**

---

## 二、接线点为什么在 `DWC.run_term`

| 候选层 | 有 `rep`？ | 有 `evolver`？ | 结论 |
|--------|-----------|---------------|------|
| `TermRunner` | 有 | **无**（run_term.py 自陈不持有 evolver） | 不可用 |
| `DWC.step` | 有 | 有 | 不在生产路径上（B1 已修可分发，但仍无调用方） |
| **`DWC.run_term`** | **有** | **有** | **唯一两边都拿得到的层** |

```python
rep = self.runner.run_term(task, n_steps=n_steps, **kwargs)
self._snapshot_worlds()
rep.evo_feed = self._feed_evolver(rep)      # ★ B2
return rep
```

---

## 三、灰度开关

新增 `config/evolution.yaml` + `load_evolution()`：

```yaml
version: 1
evolution:
  feed_from_terms: false      # 必填 · 无默认（灰度默认关）
  max_sigs_per_term: 50       # 必填 · 无默认
```

**两个键都必填无默认** —— 不许代码里 `get(..., False)` 兜底，
否则「配置文件缺失」与「显式关闭」不可区分。

关着的时候 `evo_feed` 仍然写进 `TermReport`：

```json
{"enabled": false, "why": "feed_from_terms=false（灰度默认关）"}
```

⇒ **「关」也是可审计状态，不是静默缺席。**

`scripts/dwc_agent.py` 的 `agent_term` 日志新增 `evo_feed` 字段，
生产日志里能直接看到每轮喂了多少、产了多少提案。

---

## 四、签名提取口径

从 `rep.judgement["details"]` 里取：

| 条件 | 处理 |
|------|------|
| `success is not False` | 跳过（`None` = 未评价，不是失败 —— Verdict 纪律） |
| 缺 `c` 或 `q` | 跳过（记忆口径不全） |
| 缺 `fn` | 用观测的 `task_id` 兜底；两者都缺 ⇒ 跳过（`diagnose` 的查询键是 c/q/fn） |
| 超过 `max_sigs_per_term` | 截断，截掉的条数如实记 `n_dropped` |

---

## 五、真跑证据（不是单测）

探针：真 `DWC` + 真 `TermRunner` 六层链 + 真失败执行体（所有 behavior 锚点回错值）。

```
=== details: 16 | success=False: 9
=== sig: [{"c": "E_NO_RESULT", "q": "abstained_or_missing",
           "fn": "sum_first_n", "m": "llm_asserted:None", ...}]
=== diagnose called: 1 times
=== sigs fed: [{"c": "E_NO_RESULT", "q": "abstained_or_missing",
                "fn": "sum_first_n", "m": "llm_asserted:None"},
               {"c": "E_VALUE", "q": "wrong_magnitude",
                "fn": "average", "m": "llm_asserted:999.0"}]
=== evo_feed: {"enabled": true, "n_sigs": 9, "n_dropped": 0,
               "n_proposals": 1, "n_unmapped": 8, "n_clusters": 3}
```

**9 条真签名 → 1 个提案 / 3 个簇 / 8 条未映射。**

另一个探针（无执行体 ⇒ 全 `success=None`）验证诚实边界：

```
=== details: 16 | success=False: 0
=== diagnose called: 0 times
=== evo_feed: {"enabled": true, "n_sigs": 0, "why": "本 term 无可用失败签名（c/q/fn 齐）"}
```

⇒ 没测到失败就不编造，`diagnose` 一次都不调。

---

## 六、测试

`tests/test_r373_evolve_feed.py` —— **12 条**：

| # | 锁 |
|---|-----|
| 1 | 灰度关 ⇒ 不调 diagnose，但 `enabled=False` + why 在位 |
| 2 | 灰度开 ⇒ 真调，`fn`/`m` 搬运正确 |
| 3 | sig 无 fn 且无 task_id ⇒ 不喂 |
| 4 | sig 缺 c/q ⇒ 不喂 |
| 5 | `success` 为 True/None ⇒ 不喂 |
| 6 | 超限截断 + `n_dropped` 计数 |
| 7 | `diagnose` 抛异常 ⇒ 留痕不崩 |
| 8-10 | 配置契约：缺键 / 非 bool / 零上限 ⇒ `DialError` |
| 11 | **生产配置当前必须是关**（打开要用户拍板） |
| 12 | **接线级**：`DWC.run_term` 真的调 `_feed_evolver` |

另：`tests/test_dial_config.py::test_validate_all_includes_retention`
按新语义重锚（四份 → 五份），并加「`evolution` 键必须由校验器真产出」的强化断言。

---

## 七、诚实边界

1. **默认关** —— 生产上这条通路还没打开。打开 = 改 `config/evolution.yaml` 一行，
   但会开始产提案，**要用户拍板**。
2. **只诊断，不落地** —— `diagnose` 产提案，提案到落地还要走 trial/accept
   （`scripts/dwc_evo_round.py` 的链）。B2 只负责把燃料送进炉子。
3. **提案质量未评估** —— 9 条签名产 1 个提案、8 条未映射，说明现有 RULES
   覆盖面窄。这是规则库的问题，不是接线的问题。
4. **`n_clusters` 语义** —— 该字段来自 `diagnose` 返回，本模块不解释其算法，
   只如实搬运。
5. **未验证长跑影响** —— 单 term 喂 9 条签名的开销可忽略；但常驻 agent 每天
   几十轮、每轮上百条签名时，`diagnose` 的耗时未测。`max_sigs_per_term=50`
   是保守初值，**不是实测校准值**。
