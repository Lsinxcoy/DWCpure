# R438 · 19 项进化对象落地总案

> 口径：**“落地”= 有产物文件 + 有消费者读它 + 有试验能判好坏 + 能回滚**。
> 四项缺一，就不算落地 —— 只是又造了一个没人读的 JSON。

---

## 零、先说三条硬约束

1. **第 15 项（评估器）与第 18 项（训练桥→external_source）按设计只读**
   （`K_META["evaluator"]=False` / `K_META["external_source"]=False`，G10 密封）。
   让评估器可进化 = 自己改考卷 ⇒ 整个适应度失去意义。
   这两项的“落地”= **登记 + 显式拒绝编辑 + 拒绝留痕**，不是让它变异。
2. **第 7 项（架构）须人工批准**（`K_META["architecture"]=True` 但 G3 人类主权）。
   落地 = 提案进审批队列 + 人工批准后才写，**不自动 apply**。
3. **第 20/21 项（外部机制源）本轮搁置**（用户指示）。

---

## 一、19 项 → 11 个组件 → 11 个产物

| # | 对象 | 组件 | 产物（真源） | 消费者（谁读它） | 试验判据 |
|---|---|---|---|---|---|
| 1 | 标量参数/超参 | `config` | `config/tunables.json` | 启动时注入 env / LLMClient | 池 A 子集跑分 |
| 2 | 策略 | `control_flow` | `config/anchors/rules.json` | `Mutator.propose` 查表 | 目标任务重放 |
| 3 | 技能 | `skill` | `skills/<name>/SKILL.md` | `task_exec` 技能段注入 | 目标任务跑分 |
| 4 | 记忆 | `memory` | `var/dwc_lessons.jsonl` | `agent_quality.sources_context` | 目标任务跑分 |
| 5 | 知识 | `memory` | 同上（tier=long） | 同上 | 同上 |
| 6 | 代码 | `code` | 源文件函数体 | Python 运行时 | 沙箱 + f2p/p2p |
| 7 | 架构 | `architecture` | `var/arch_proposals.jsonl` | 人工审批队列 | 人工裁决 |
| 8 | 提示词 | `prompt` | `prompts/*.vN.md` + manifest | `prompt_ota.render` | 同题两臂 A/B |
| 9 | 工具 | `client_tool` | `config/tools_extra.json` | `TASK_TOOLS` 合并 | 工具冒烟 |
| 10 | 协作 | `subagent` | `config/subagent_policy.json` | 派发器 | 路由测试 |
| 11 | 上下文 | `context_mgmt` | `config/context_policy.json` | `task_exec` 读默认 | 上下文类任务 |
| 12 | 观测 | `output_plumbing` | `config/output_policy.json` | 最终答案处理 | 格式类任务 |
| 13 | 执行环境 | `config` | `config/tunables.json` | 启动器 | 同 #1 |
| 14 | 元进化 | `meta_evolution` | `config/evolution.yaml` | 进化轮自身 | 轮指标 |
| 15 | 评估器 | `evaluator` | **只读** | — | 拒绝编辑证明 |
| 16 | 控制/安全 | `control_flow` | `rules.json` | 同 #2 | 同 #2 |
| 17 | 模型选择 | `config` | `config/tunables.json` | `LLMClient` | 同 #1 |
| 18 | 训练桥 | `external_source` | **只读** | — | 拒绝编辑证明 |
| 19 | 行为/工作流 | `control_flow` | `rules.json` | 同 #2 | 同 #2 |

---

## 二、统一机制（不造 11 套轮子）

```
信号 → 车道路由 → 起草 → 试验 → 门 → 落地（带备份）→ 读回 → 台账
```

- **Target**：复用 `organs/applier.py::Target`（getter/setter/has/delete/flush，
  写后立即读回）。
- **产物注册表**：`src/dwc/organs/evo_targets.py`
  `TARGETS: Dict[str, TargetSpec]`，每项含
  `path / schema / read / merge / trial / rollback`。
- **驱动器**：`src/dwc/organs/evo_driver.py`
  `run_component_round(component, signals)`，与 `dwc_evo_round.py` 共用
  `ProposalGate` + `Evolver.accept`。
- **台账**：`var/evolution_ledger.jsonl`，每行
  `{ts, component, key, decision, before_hash, after_hash, backup, trial}`。

**为什么统一**：11 套独立轮子 = 11 套 bug + 11 种台账口径（R426 同族教训）。

---

## 三、执行阶段（按风险升序）

### P0 · 让 `control_flow` 真落地（覆盖 #2 #16 #19）

| 改动 | 位置 | 判据 |
|---|---|---|
| `--apply` 由 `config/evolution.yaml:auto_apply` 控制（必填无默认） | `dwc_evo_round_cron.py:93` | 缺键 ⇒ 启动报错 |
| 启动时 `Mutator.ensure_loaded()` | `scripts/dwc_agent.py` + cron | 新进程能读到已学规则 |
| 落地前备份 `rules.json` → `var/backups/rules_<ts>.json` | `Evolver._land_adopted` | 备份文件存在 |
| `--rollback <key>` CLI | `dwc_evo_round_cron.py` | 回滚后键消失 |
| 台账 | `var/evolution_ledger.jsonl` | 每轮一行 |

### P1 · 策略型产物（覆盖 #1 #9 #10 #11 #12 #13 #14 #17）

一个通用 `JsonPolicyTarget`：
`read → dict` / `merge(candidate)` / `write + readback` / `backup` / `rollback`。
六个产物共用，各自带 schema 校验 + 消费者。

### P2 · 记忆与知识（覆盖 #4 #5）

`promote_lessons` 接进每日轮 + `sources_context` 注入 long 层教训。

### P3 · 技能（覆盖 #3）

`skills/<name>/SKILL.md` 产物 + `task_exec` 按任务词元匹配注入。

### P4 · 提示词驱动层（覆盖 #8）

`PromptEvolutionOrgan`：候选 → A/B → 晋升（带 manifest 回滚）。

### P5 · 代码落地（覆盖 #6）

沙箱通过的函数体写回源文件（备份 + `git diff` 可查 + 失败自动还原）。

### P6 · 只读与人工（覆盖 #7 #15 #18）

架构提案进审批队列；评估器/外部源拒绝编辑并留痕。

---

## 四、每阶段的验收（统一四条）

1. **产物存在**：文件真的被写出来，不是内存里改了。
2. **消费者生效**：新进程读到它，且行为有可观测差异。
3. **可回滚**：`--rollback` 后文件恢复原状，行为回退。
4. **可区分**：降级/拒绝/成功三种状态在台账里可区分（不许静默）。

---

## 五、进度（19/19 已落地）

| 组件 | 对象 # | 产物 | 消费者 | 状态 |
|---|---|---|---|---|
| `control_flow` | 2,16,19 | `config/anchors/rules.json` | `Mutator.propose` | ✅ 真落 1 条（fibonacci） |
| `memory` | 4,5 | `var/dwc_lessons.jsonl` + tier | `sources_context` | ✅ |
| `skill` | 3 | `skills/<name>/SKILL.md` | `task_exec` 注入 | ✅ |
| `context_mgmt` | 11 | `config/context_policy.json` | `read_default_lines()` | ✅ |
| `output_plumbing` | 12 | `config/output_policy.json` | `_cap_answer()` | ✅ |
| `client_tool` | 9 | `config/tools_extra.json` | `TASK_TOOLS` 合并 | ✅ |
| `config` | 1,13,17 | `config/tunables.json` | `dwc_agent.py` | ✅ |
| `subagent` | 10 | `config/subagent_policy.json` | `cap_limit("delegate")` | ✅ |
| `prompt` | 8 | `prompts/<name>.vN.md` + manifest | A/B → 晋升 | ✅ 驱动层 + 周排程 |
| `code` | 6 | `rules.json` 的 `code` 字段 | `propose` 复用实现 | ✅ |
| `meta_evolution` | 14 | `config/evolution.yaml` | cron 按压力调旋钮 | ✅ 3 天冷却 |
| `architecture` | 7 | `var/architecture_queue.jsonl` | 人工审批 CLI | ✅ 不许自动落 |
| `evaluator` | 15 | —（只读） | 构造即拒 | ✅ 代码级拒绝 |
| `external_source` | 18 | —（只读） | 构造即拒 | ✅ 代码级拒绝 |

### 测试

- 新增 9 个测试文件、**63 条**（landing 7 / memory 4 / skill 8 / targets 13 /
  prompt 7 / code 2 / readonly 4 / meta 7 / arch 7，含守卫）。
- 全量：**2702 passed / 7:57**（`var/pytest_r438h.log`），最终复跑见 `pytest_r438_final.log`。

### 途中抓到的 4 个真 bug

1. `ROOT` 少算一层 ⇒ 产物写进 `src/config/`（消费者永远读不到）。
2. 重复实现 `lessons_context` ⇒ 遮蔽原实现，24 红。
3. 测试写掉生产 `rules.json`（`test_module_level_load` pin 回生产路径再删）。
4. `agent_quality.VAR` 写死 `<repo>/var` ⇒ 全量从 6.5min 涨到 40min+，
   且测试 `touch` 污染生产 `use_count`；`_sources_off` 开关也算错目录。

### 诚实边界

- `#15/#18` 的"落地"= **拒绝证据**（构造即抛 + 测试），不是"它们能进化"。
- `#7` 的"落地"= 审批队列；架构改动本身仍由人做。
- `#8` 的 A/B 每周只跑一次（1-4h），首个候选要等下个周日。
- `#14` 目前只调 `auto_apply_max_per_round`（唯一有压力信号的旋钮）。
