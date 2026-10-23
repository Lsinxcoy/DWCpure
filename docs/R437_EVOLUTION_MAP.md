# DWC 进化系统全图（R437 审计）

> 审计时间 2026-10-23 09:00。方法：静态调用面统计（`src/` `scripts/` `tests/` 全量符号计数）+ 运行时台账（`var/evo_proposals.jsonl`、`var/dwc_lessons.jsonl`、`var/dwc_prod.sqlite`）+ cron 真实输出。
> 结论以**代码与数据**为准，不以注释/文档自述为准。

---

## 一、结论先行

代码里存在 **4 条"进化"通路**。其中：

- **1 条完整闭环，但只在测试里跑**（生产零调用）
- **1 条每天定时跑，但输入被过滤成 0**（结构性空转）
- **1 条只有加载器，没有变异/选择**（提示词）
- **1 条只记录不晋升**（lessons）

**当前生产上没有任何一条通路会改变系统行为。**

| # | 通路 | 输入 | 变异 | 评估 | 落地 | 触发 | 真实状态 |
|---|---|---|---|---|---|---|---|
| 1 | live term loop<br>`src/dwc/harness/loop.py` | judge 失败签名 | `evolver.diagnose` → `propose` | `_trial_run` + replay | 六门 + `applier` | 每 term | **未接线**：`build_round_fn` 生产零调用；落地 target 是内存 box |
| 2 | daily evo round<br>`scripts/dwc_evo_round_cron.py` | `failure_sig` 表 | `Mutator` / `LLMMutator` | `_real_trial` | `apply=False` 硬编码 | cron 04:00 | **空转**：2034 条签名 100% 被过滤 |
| 3 | prompt OTA<br>`src/dwc/llm/prompt_ota.py` | 无 | 手工脚本 | 手工 A/B | 手工 promote | 无 | **只加载**：manifest 9 条全 `pct: 0` |
| 4 | lessons<br>`src/dwc/agent_quality.py` | 任务失败 | `record_lesson` | `score_lesson_quality` | `promote_lessons` | 失败即写 | **只写不晋升**：`promote_lessons` 生产零调用 |

---

## 二、进化对象（动作空间）

`evolver.editable_vocab()` 返回 **12 类**组件：

```
architecture, client_tool, code, config, context_mgmt, control_flow,
memory, meta_evolution, output_plumbing, prompt, skill, subagent
```

`k1_coverage()`：21 个盘点项全覆盖，**7 项归属有争议**（知识→memory、观测→output_plumbing、
执行环境→config、控制/安全→control_flow、模型选择→config、训练桥→external_source、
行为/工作流→control_flow）。

**关键澄清**：词表里的 `prompt` **不是** `prompts/*.md` 系统提示词，而是"文本/答案面"。
证据：`RULES` 表里 10 条 `component="prompt"` 的 patch 全是 `reasoning_001` /
`reproduce_001` 这类演示任务的**答案文本**（`evolver.py:1779-1882`）。

**约束**：`Proposal._assert_single_change()` 强制"一处干预"（target + patch 只能一处），
否则任何测量都无法归因。

---

## 三、四条通路逐条核实

### 通路 1 · live term loop（完整闭环，未接线）

`harness/loop.py` 的 `Loop.round()` 是一条完整链路：

```
judge 失败签名 → evolver.diagnose → proposals
  → _trial_run（合成 patch 后复判）
  → replay 选择（argmax，不劣于 current 才继续）
  → gate_all（六门）
  → run_round(applier=..., target=_MemoryTarget())
  → landed = bool(res.landing)
```

**但生产不跑它**：

- `build_round_fn`（唯一构造入口）在 `src/` `scripts/` **只有定义本身**，测试里 1 处。
- 落地 target 是 `_MemoryTarget`（`loop.py:1364`），注释原文：
  "循环本身只证明『落地链路在轮里真跑过』⇒ 用内存 target（不写脏盘）"。
- 真正的可写面 `_RulesTarget`（`loop.py:1337`）**全仓库零引用**。

⇒ 这条通路的能力是真的，但它是一条**演示链路**。

### 通路 2 · daily evo round（每天跑，输入恒空）

cron `DWC evo收尾每日`（`0 4 * * *`，`last_status: ok`，已完成 8 次）调用
`dwc_evo_round_cron.py`：

```
diagnose（collect_unmapped）→ propose（propose_from_cluster）
  → assess（_real_trial：真 LLM + 真 judge）
  → apply=False
```

**2026-10-23 04:01 的真实输出**：

```json
{ "n_clusters": 0, "results": [], "trial_rounds": 0,
  "filtered_nonreproducible": 68,
  "triage": {"total": 0, "landed": 0} }
```

`filtered_nonreproducible: 68` 说明签名全被 `reproducible_only` 分流掉了。
查库：

```
failure_sig 总行 2034 | m LIKE 'llm_asserted%' 2034 | 可复现 0
```

**2034 / 2034 全部是 `llm_asserted*`**。而 `collect_unmapped` 的过滤条件是：

```python
_filtered_nonrepro = [s for s in sigs if s["m"].startswith("llm_asserted")]
sigs = [s for s in sigs if not s["m"].startswith("llm_asserted")]
```

⇒ 过滤后 **0 条** ⇒ 0 簇 ⇒ 0 试跑 ⇒ 0 落地。**每天都是空转。**

根因链：`judge.py:1041/1071` 产出的每条失配签名都是 `m="llm_asserted:%r"`。
R328 的设计意图是"执行侧自断言归 agent_quality 回路，evo 只吃 verifier 可复现簇"——
但**判据从未产出可复现簇**，于是 evolver 永远收不到输入。

另有一处 SQL 缺陷（同一份 cron 输出）：

```
N1 route warn: OperationalError('no such column: task')
```

`dwc_evo_round_cron.py:126` 查询 `SELECT DISTINCT task FROM failure_sig`，而该表只有
`(c, q, m, node_id)` 四列 —— **这条把执行侧失败路由回 agent 的通道从未成功执行过**。

### 通路 3 · prompt OTA（只有加载器）

- 加载面：`core.py` / `executor.py` / `task_exec.py` / `candidates.py` / `evolver.py` / `planner.py` 共 6 处接入，生产在用。
- 变异面：`scripts/dwc_prompt_candidate.py` —— 生产引用仅来自 `dwc_prompt_ab.py`。
- 评估面：`scripts/dwc_prompt_ab.py` —— 生产零外部引用。
- 选择面：`--promote` 手工参数。
- `prompts/manifest.json` 9 条全部 `{"stable": "v1", "candidate": null, "pct": 0}`。

⇒ 灰度机制存在，但**从来没有人设置过 candidate**。

### 通路 4 · lessons（只写不晋升）

`agent_quality.py` 有完整生命周期：

```
record_lesson → score_lesson_quality → promote_lessons(use_threshold=5)
  → touch_lessons → lesson_contrast
```

台账：`var/dwc_lessons.jsonl` **1205 条**，字段含 `tier` / `use_count` / `utility` / `quality`。

但调用面：

| 函数 | 生产调用点 |
|---|---|
| `record_lesson` | agent_quality 自身（chat）、`dwc_bench.py`、`dwc_nightbench.py` |
| `touch_lessons` | agent_quality 检索命中时 |
| `lesson_contrast` | agent_quality 检索时 |
| **`promote_lessons`** | **零**（只有定义 + 1 个测试） |

⇒ 教训会被写入、被检索、被注入，但**永远不会晋级**，`tier` 字段形同虚设。

---

## 四、断点清单（10 条，全部有证据）

| # | 断点 | 证据 |
|---|---|---|
| 1 | 完整闭环生产零调用 | `build_round_fn` 仅 `loop.py` 定义 + 1 测试 |
| 2 | 可写面从未使用 | `_RulesTarget` 全仓库 **0** 引用 |
| 3 | 每日轮永不落地 | `dwc_evo_round_cron.py:80` `apply=False` |
| 4 | 落地目标不存在 | `config/anchors/rules.json` **文件不存在** |
| 5 | 胜者选择未接线 | `select_winner` 只在注释/字符串里被提到 |
| 6 | 候选归档未接线 | `promote_archived` / `archive_candidate` 生产仅定义 |
| 7 | 技能进化未接线 | `skill_evolve_from_sig` 生产仅定义 |
| 8 | 教训晋升未接线 | `promote_lessons` 生产仅定义 |
| 9 | 提示词闭环未接线 | `dwc_prompt_ab` 生产引用仅来自自身 |
| 10 | 执行侧路由 SQL 坏 | `no such column: task`（表只有 4 列） |

---

## 五、生产上"进化"实际在做什么

| 动作 | 频率 | 产出 | 是否改变行为 |
|---|---|---|---|
| `run_term` 失败 → `evolver.diagnose` | 每 term | 写 `var/evo_proposals.jsonl`（1094 unmapped + 45 proposals） | **否** |
| daily evo round | 每天 04:00 | 0 簇报告 | **否** |
| `record_lesson` | 每次失败 | `dwc_lessons.jsonl`（1205 条） | 间接（注入 prompt） |
| anchor drift watch | 每 2h | 告警 | **否** |
| prompt OTA | 每单 | 读 manifest，全 `pct: 0` | **否** |

**45 条 proposal 的结局**：只被写进台账，没有任何一条进入 trial / gate / 落地。
台账里连 `state` 字段都没有 —— 无法回答"它后来怎么了"。

---

## 六、修复优先级（建议）

| 优先级 | 修什么 | 为什么 |
|---|---|---|
| **P0** | 让通路 2 有输入：判据产出**可复现**签名（或把 `llm_asserted` 之外的签名单独入库） | 没有输入，后面全是空转；这是唯一的"零号问题" |
| **P0** | 修 `SELECT DISTINCT task` 的 SQL | 执行侧失败回流的唯一通道，从未跑通 |
| **P1** | 建 `config/anchors/rules.json` + 给 cron 加 `--apply`（默认仍 False，先手动跑一轮验证） | 让"能落地"这件事至少被证明一次 |
| **P2** | 把 `promote_lessons` 接进每日轮 | 1205 条教训有 tier 字段却永不晋级 |
| **P3** | prompt 作为第 13 个组件接进通路 2（复用 R434 三件套） | 提示词进化才有归宿 |
| **P4** | 通路 1 复活或归档 | 按"僵尸先复活不删"铁律：先接一个真实 Target，跑一轮 e2e 证明 |

---

## 七、验证方法（修完后怎么证明真的通了）

1. **输入侧**：`select count(*) from failure_sig where m not like 'llm_asserted%'` > 0
2. **诊断侧**：daily round 报告 `n_clusters > 0`
3. **试跑侧**：`trial_rounds > 0` 且 `envelope.by_mode` 非空
4. **落地侧**：`config/anchors/rules.json` 出现新键，且 `git diff` 可见
5. **行为侧**：落地前后同一 anchor 的 pass_rate 有可测差异（且过噪声带）

任一步为 0，就说明链路仍断在该处 —— 不许用"报告里有数字"代替"行为变了"。
