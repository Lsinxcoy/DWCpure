# DWC v2.0 成本感知 Harness 自进化 · 落地验收

> 轮次：R439–R446 ｜ 基线：R438（v1「能不能自进化」）
> 本版本回答的问题：**进化得值不值** —— 成本成为与通过率并列的一等目标。
> 来源：HarnessPro（arXiv 2610.26770）、Harness²（arXiv 2610.14224）、
> Cache Engineering for Agents（arXiv 2610.28577）。

---

## 0. 一句话结论

九项计划全部落地，**其中四项在实现过程中被实测推翻并改成了更诚实的版本**。
没有为了让计划好看而写假门、假测量、假复用。

| # | 项 | 状态 | 一句话 |
|---|---|---|---|
| P0-0 | compaction 实测 | ✅ | 论文的 1.85× 对 DWC **不适用**（cached_tokens 全 0） |
| P0-a | 成本记账 | ✅ | 三档计价 + 无 usage 不写 0 + 未知模型不兜底 |
| P0-b | 输出压缩 | ✅ | 未超限一字不改且不落盘；超限头+尾+**可读路径** |
| P1-a | 三段式预算 | ✅ | economy→strict→finalize，`tool_choice` 硬约束收尾 |
| P1-b | 成本归因 | ⚠️ 改写 | 原计划"双目标 fitness"是假门，改为回溯归因 |
| P1-c | 逐例对比 | ⚠️ 半撤回 | 对比探针做了；"纠正继承"经核实**不成立**，撤回 |
| P2 | 按任务选档 | ⚠️ 改数 | 原计划 finalize 到 68，但循环硬上限只有 15 |
| P3 | 三档 Pareto | ⚠️ 只观测 | 一轮只有一个候选 + 只有一种部署形态 ⇒ 不接管决策 |
| P4 | 改进库 | ✅ 半 | 落地即入库（三要素强制）；**库还没被读** |

---

## 1. P0-0 · 论文结论对 DWC 不适用（实测推翻）

**方法**：scratch 隔离（`DWC_VAR_DIR` / `DWC_USAGE_PATH` 指向临时目录），
跑真实任务 `execute_user_task("读取 config/llm.json 的 model 字段…", max_rounds=4)`。

| 调用 | prompt | completion | cached |
|---|---|---|---|
| 1 | 2140 | 41 | **0** |
| 2 | 193 | 64 | **0** |
| 3 | 2554 | 36 | **0** |

**结论**：服务端既不命中也不回报前缀缓存 ⇒ **DWC 今天没有缓存收益可以失去**。
Cache Engineering 的 trim=1.85× 来自 serving 层 re-prefill，不适用于 DWC。
compaction 在 token 上是净省，真正的风险是信息损失掉分（论文：summary −5pp）。

> 由此 P0-b 的"前缀稳定性"目标从"省钱"降级为"为将来缓存做准备"。

---

## 2. P0-a · 成本记账（`src/dwc/llm/cost.py`）

三条纪律，全部有测试：

| 纪律 | 为什么 |
|---|---|
| 无 usage ⇒ **不出现 usage 键**（不是 0） | 0 会被下游当成"这次免费" |
| 未知模型 ⇒ `cost_usd=None`，tokens 照记 | 不许拿别的模型价格兜底 |
| 落盘失败只 stderr 留痕 | 记账坏不许掀翻 LLM 调用 |

接线：`client.py` 四个 `LLMResult(ok=True)` 返回点 + 流式回退都搬 `usage`/`cost_usd`。
`load_pricing()` 读 `config/llm.json` 的可选 `pricing` 段 —— **当前没有**，
所以 `cost_usd` 全为 None（不编价格）。

---

## 3. P0-b · 输出压缩（`src/dwc/llm/tool_raw.py`）

| 情形 | 行为 |
|---|---|
| 未超限 | **一个字都不改，也不落盘**（不给磁盘塞垃圾） |
| 超限 | 头 60% + 尾 + 可读路径提示；按 sha1 去重 |
| 落盘失败 | 仍截断，但提示必须写"原文保存失败（本行不提供路径）" |

接线：`task_exec.py` 三处裸切片（`stdout[:4000]` / `out[:6000]` / `json.dumps(obs)[:6000]`）。

---

## 4. P1-a · 三段式工具预算（`src/dwc/llm/budget.py`）

```
economy(6) ──提醒──> strict(10) ──每 3 步重复──> finalize(15) ──硬阻断──> 收尾
```

- `normalized()` 保证 `economy ≤ strict ≤ finalize`（倒序配置不许把阶段语义倒过来）
- 提醒**只追加到本轮 prompt**，不重写系统提示（保 cache 前缀）
- `finalize` 用 API 层 `tool_choice` 硬约束
- 强制收尾文案**按原因分支**：预算用完 vs 动作重复（改前一律说"重复 N 次"= 说假话）

实跑探针：`economy=2/strict=3/finalize=4` ⇒ 三阶段依次触发、任务 3 轮完成；
`1/2/2` ⇒ 第 2 轮硬阻断并给出答案。

---

## 5. P1-b · 成本归因（原"双目标 fitness"的诚实改写）

**原计划**：`scalar = realization × outcome × (1 − w·Δcost)` + `no_cost_regression` 门。

**为什么没写**：

> trial 确实会调 LLM（`_peer_held_out_code`）—— 我第一版说"trial 是纯沙箱"是**错的**。
> 但那部分是**评测开销**：两臂都付、`max_tokens` 固定、prompt 只差一个 `hint_code`。
> 它衡量"评测花了多少"，不是"这条规则上线后多贵"。
> 拿它当成本门，就是拿噪声当信号 ⇒ 门只会恒假或恒真，两者都是假门。

**实际落地**：回溯归因。

| 组件 | 作用 |
|---|---|
| `cost.set_tag / clear_tag` | 任务期间的调用记到该 task_id（线程本地） |
| `dwc_agent.py` | 接单前后 set/clear（try/finally） |
| `organs/cost_attribution.py` | `per_task` / `mean_tokens_per_task` / 增量 `snapshot` / `trend` |
| `dwc_evo_round.py` | 每轮写 `var/cost_ledger.jsonl`，报告出 `cost_attribution` 块 |

实跑：`n_tasks=0 / mean_total=null / trend=unknown` —— 当前确实没有带标签的用量，
**如实为空，不填 0**。

---

## 6. P1-c · 逐例对比（`src/dwc/organs/contrast.py`）

把 `in_score` 一个标量拆成 `n_cases / n_failed / failed[]`。
"修好 3 例、弄坏 3 例"和"什么都没改"分数一样，但前者是**回归** —— 分数看不见。

**实测踩到的坑（已写进模块头）**：

```
obs_skeleton() 产出 [[args, None], ...] —— 故意不带 expected（只给判分器看）
第一版拿骨架里的 None 去比 ⇒ BUGGY 与 GOOD 都 n_failed=2（全判失败）
```

探针抓到后改成从 anchor 的 `checks` 取期望值：

| 代码 | in_score | n_failed | failed |
|---|---|---|---|
| `sum(range(n))`（错） | 0.0 | 2 | expected 6/15, actual 3/10 |
| `sum(range(1,n+1))`（对） | 1.0 | 0 | — |

**诚实缺席**：`regressed: None` + 原因"anchor 不含原始实现" —— 没有基线逐例结果，
就不许编"消失/新增"。

**半撤回**：原计划说"`Mutator.propose` 把上轮 `p.code` 当起草起点 = 继承"。
逐行核实后**不成立**：`p.code` 只在 trial 成功时作为 **peer 翻译 hint**（peer 函数名不同），
属库式选择性复用。该条修正不写代码。

---

## 7. P2 · 按任务选档（`src/dwc/llm/profile.py`）

| profile | 推理力度 | economy | strict | finalize | 触发 |
|---|---|---|---|---|---|
| compact | 继承 | 3 | 5 | 8 | ≤40 字且无多交付物标记 |
| lean | 继承 | 5 | 8 | 12 | ≤120 字 |
| standard | 继承 | 6 | 10 | 15 | 兜底（= R441 默认） |
| deep | 继承 | 8 | 12 | 15 | 审计/重构/架构/调用链… 或 >600 字 |
| research | 继承 | 8 | 12 | 15 | 调研/检索/搜索/论文… |

**两处改计划**：

1. 计划写 finalize 最高 68，但循环硬上限是 `NATIVE_TOOLS_MAX_ROUNDS=15`
   ⇒ 68 是永远不会到来的轮次（幻影预算）。全部压到 ≤15。
2. 计划让 deep/research 用 `low` 推理档，但 R411 实测「越高越差」
   ⇒ 五档全部继承全局。改力度必须走 A/B，不许在路由规则里夹带。

**优先级**：`进化改过的值 > profile 先验 > 模块默认`。
用 `_MISSING` 哨兵区分"没这个键"与"设成了默认值"——否则进化写过 6 就永远盖住先验。

---

## 8. P3 · 三档 Pareto（`src/dwc/organs/pareto.py`）

`J = a·d_perf² + b·d_cost²`，三档权重 lite(1,2) / medium(1,1) / heavy(2,1)。

**三条纪律（有测试锁定）**：

- 成本缺失 ≠ 0（0 会被选成"最便宜"）
- 成本全等 ⇒ 退化为最高分（与现状一致）
- 无可测点 ⇒ `select` 返回 None（调用方保持原行为）

**为什么不接管 landing**：

1. `dwc_evo_round.py:512` 是 `if _ok is True ... break` ⇒ **一轮只有一个成功候选**，
   单点前沿选谁都一样。
2. DWC 只有一种部署形态（`auto_apply: true`），没有"按预算挑档"的部署位。

⇒ 本步是**数据结构的准备**，不是决策机制。

---

## 9. P4 · 改进库（`src/dwc/organs/library.py`）

Harness² 四条硬规则 → DWC：

| 规则 | 落地 |
|---|---|
| 三要素缺一不入库 | `validate()` 返回原因，`add()` 不写半条 |
| 写库前无判分结论 | 只取 `rationale` + 真实 trial 分数，不抄 expected |
| 只留当前任务之前 | `before(rows, ts)` |
| 存整棵树不存摘要 | 存 `rationale` 全文 + 完整 evidence |

**真实回填**（证据来自 `var/evolution_ledger.jsonl` 的 `trial` 字段）：

| cue | in | ho | baseline |
|---|---|---|---|
| `E_VALUE:wrong_magnitude:fibonacci` | 1.0 | 1.0 | 1.0 |
| `E_VALUE:wrong_magnitude:average` | 1.0 | 1.0 | 1.0 |

报告实测：`n_entries=2, families=["E_VALUE:wrong_magnitude"]`。

**★ 诚实缺口**：库**只写不读**。起草仍走 `rules.json` 的 `hint_code`，
`select_family()` 今天只有报告在用。Harness² Figure 7：k=1 只能拉回基线，
要正增益需 k≥5 —— DWC 现在 2 条。

---

## 10. 回归与门禁

| 项 | 结果 |
|---|---|
| 全量测试 | **2817 passed / 369.85s**（`var/pytest_r446_full2.log`） |
| `scripts/gate.py` 八门 | 每次提交前全绿 |
| 唯一重锚 | `test_d2_envelope.py`：旧断言要求 `tokens` 出现 "unmeasured"，但 token 现在**真的记了** ⇒ 改为断言**不出现**且指向 `cost_attribution` |

> 重锚而非删除：行为语义变了，断言必须跟着变成**更强**的那一条。

---

## 11. 交付物清单

**新增源码**

| 文件 | 行数 | 作用 |
|---|---|---|
| `src/dwc/llm/cost.py` | 187+ | 用量解析 / 三档计价 / 落盘 / 线程 tag |
| `src/dwc/llm/tool_raw.py` | 97 | 输出压缩 + 原文落盘 |
| `src/dwc/llm/budget.py` | — | 三段式预算 |
| `src/dwc/llm/profile.py` | 100+ | 五档 + 规则选择器 |
| `src/dwc/organs/cost_attribution.py` | 186 | 按任务聚合 / 增量快照 / 趋势 |
| `src/dwc/organs/contrast.py` | 130+ | 逐例对比 |
| `src/dwc/organs/pareto.py` | 120+ | 非支配集 + 三档选择 |
| `src/dwc/organs/library.py` | 180+ | 改进库（四规则） |

**测试**：`test_r439_cost`(15) / `test_r440_tool_raw`(7) / `test_r441_budget`(9) /
`test_r442_cost_attribution`(12) / `test_r443_contrast`(11) / `test_r444_profile`(16) /
`test_r445_pareto`(12) / `test_r446_library`(13) —— 共 **95 条新增**。

**文档**：`docs/DWC_V2_HARNESS_EVOLUTION_PLAN.md`（每阶段都有"原计划 vs 实际"对照）、
`docs/P0_0_COMPACTION_MEASUREMENT.md`、三篇论文 deep report + intake。

---

## 12. 没做完的（明确记账，不装作完成）

> **R447/R448 更新**：缺口 1（库复用）、缺口 3（档位归因）、缺口 4（上下文可观测）
> 已在 R447–R448 补齐，见 §13。下表只剩真正没做完的。

| 项 | 缺什么 | 为什么现在不做 |
|---|---|---|
| 候选级成本门 | 需要"用候选真跑任务"的测量通道 | trial 成本是评测开销；生产 A/B 跨天 |
| 选档的收益验证 | 需要 ≥3 天带档位的生产用量 | 数据还没攒出来（归因已就位，等流量） |
| 上下文三元组进化 | 需要 selector 的第二个形态 + 对照数据 | 先有了分布（R448）才知道该 A/B 哪两个 |
| `cost_usd` | mcgrox 价目 | 不知道就不编，用 token 当代理 |

---

## 13. 缺口补齐（R447–R448）

### 13.1 缺口1 · 库复用（R447）

`library.hint_for(cue)` → `"\n[同族经验]\n- …"` → 拼进 `learned_hint` →
流进 `propose_from_cluster` 的起草提示。

| 纪律 | 实现 |
|---|---|
| **只注 lesson，绝不注 code** | `hint_for` 只读 `lesson` 字段（有测试锁死 `code` 不出现） |
| 最多 3 条 / 每条 300 字 | `limit=3, max_chars=300` |
| 防未来泄漏 | `before(rows, now)` |

实测：`hint_for("E_VALUE:wrong_magnitude:average")` → 430 字、2 条；
异族 cue → `""`。

### 13.2 缺口3 · 档位归因（R447）

`cost.set_profile()` / `record()` 写 `row["profile"]`；`by_profile()` 聚合。
**不拼进 tag**（拼进去会毁掉按 task_id 的聚合）。

报告字段：`cost_attribution.by_profile = {档位: {calls, tokens, n_tasks, mean_total}}`。
当前 `{}` —— 还没有带档位的生产用量，如实为空。

### 13.3 缺口4 · 上下文可观测（R448）

`llm/context_log.py`：每次压缩写 `{round, trigger, selector, reposition,
n_kept, n_compressed, falsified, before_chars, after_chars}`。
只记计数与长度，**不记正文**。

**实测压缩率（真实 4 轮任务）**：

| round | before | after | 比例 |
|---|---|---|---|
| 3 | 758 | 70 | 9.2% |
| 4 | 1536 | 91 | 5.9% |
| 5 | 2345 | 172 | 7.3% |
| 6 | 3221 | 275 | 8.5% |

⇒ 前情摘要只剩原文的 **6–9%**（压缩 ~92%）。

> 这个数把风险定位说清了：P0-0 已证明 DWC 没有缓存收益可失去，
> 所以压缩的风险从来不是 token 成本，而是**信息损失**。现在它第一次被量化。
