# DWC pure 3.0 最终强化方案

> 版本：final-1（2026-10-27）
> 范围：`Lsinxcoy/divine-wisdom-core-pure`，个人使用，不扩散、不商用。
> 证据：36 个代表性 agent 仓库 / 37 个审计条目；Goose 发布包 REA 实证；Claude Code 公开 CLI/类型面 clean-room；Hermes、DeepSeek Harness 源码审计。
> 纪律：声称 = 实测；代码存在 ≠ 已激活；测试通过 ≠ 安全边界成立；`status=done` ≠ 任务完成。

---

## 0. 一句话结论

DWC pure 已经是一个**工程完成度很高的 agent runtime**，但还不是一个**优秀的 agent**。

它缺的不是更多器官，而是四件事：

1. **任务闭环**：`done` 不是模型自述，而是可验证的完成条件。
2. **任务对象**：计划、任务图、产物、证据、失败原因要成为持久对象。
3. **技能闭环**：从真实轨迹提出技能，经审批后保存，再由 curator 维护生命周期。
4. **可恢复执行**：会话、workflow、工具结果、副作用要能 resume / 诊断 / 回放。

3.0 的顺序必须是：**先闭环，再智能；先可验证，再自进化。**

---

## 1. 证据基础

### 1.1 语料

- 33 个第一波仓库：coding agent、agent framework、memory、browser/research、self-improve/eval。
- 第二波 3 个：`NousResearch/hermes-agent`、`deepseek-ai/deepseek-harness`、`anthropics/claude-agent-sdk-python`。
- 共 36 个仓库 / 37 个条目；Claude Code 核心闭源，只审计公开 SDK/CLI/类型面。
- REA 只用于发布包实证：Goose `v1.56.0` Windows x64，`app.asar` 7,497,104 bytes；707,131 text bytes、224,839 AST nodes、62 IPC、0 main handlers；证明“静态语法 ≠ 运行时注册”，不作为 agent loop 证据。

### 1.2 三个最接近 DWC 的参照

| 参照 | 性质 | 最该学的 |
|---|---|---|
| Hermes Agent | MIT，Python，当前宿主 | 每轮 background review、skill bundles、curator 生命周期、subagent lifecycle |
| DeepSeek Harness | MIT，TS，developer preview | 一切皆插件、capability seam、evented loop、session log as source of truth |
| Claude Code / Agent SDK | SDK 开源，核心 CLI 闭源 | 权限分层、plan mode、task graph、workflow resume、ProposeSkills、ProposeGoal、sandbox |

### 1.3 Claude Code clean-room 十项

不反编译 `claude.exe`，不复制提示词。公开面已经足够：

1. 六种 permission mode：`acceptEdits` / `auto` / `bypassPermissions` / `manual` / `dontAsk` / `plan`；`allowedTools` 是 auto-approve，不是可用列表；`disallowedTools` 才阻止。
2. `--restricted` / `--safe-mode` / `--bare`：受限、排障、无自定义三条运行模式。
3. `EnterPlanMode` / `ExitPlanMode`：计划是工具和状态，不是提示词。
4. `TaskCreate/Update/Get/List`：持久任务图，支持 blocks/blockedBy/owner/status。
5. `Workflow`：脚本声明 phases，`agent()/parallel()/pipeline()/phase()`；`resumeFromRunId` 按 `(prompt, opts)` 内容哈希复用已完成调用。
6. `Agent`：默认后台、可寻址、`worktree`/`remote` 隔离、返回 toolStats/usage/status。
7. `ProposeSkills`：1–3 个 proposal，带 evidence 路径和完整 `skillMd`；用户保存才落盘。
8. `ProposeGoal`：完成条件必须能被独立 evaluator 验证，≤500 字符，默认审批。
9. `Bash`：默认 sandbox，`dangerouslyDisableSandbox` 才显式逃逸。
10. 预算/模型/缓存/会话：`--max-budget-usd`、`--effort`、`--fallback-model`、`--autocompact`、`--system-prompt-snapshot`、`--fork-session`、`--no-session-persistence`、`--exclude-dynamic-system-prompt-sections`。

### 1.4 Hermes 四机制

- `background_review`：每轮后 fork 审查 agent，问“该不该写 skill/memory”；不占任务轮次、不破 prompt cache。
- `curator`：`active → stale → archived`，never delete，pinned 豁免，usage telemetry 驱动。
- `skills_index_delta`：技能中途变化通过增量 note 进入下一轮，不重建 system prompt。
- `subagent_lifecycle`：不可变 handle、状态机、超时、取消、allowed/blocked tools、结构化结果。

### 1.5 DSH 三条纪律

- **seam**：Service Definition / Provider / Consumer 三角；换 provider 不改消费者。
- **event**：`agent/pre-step`、`agent/turn-stopping`、`tools/pre-execute/post-execute` 少量稳定 hook。
- **session log**：模型可见请求可从 log 重建；失败/取消 attempt 保留但不进上下文；fork/resume/telemetry 都从 durable settlement 派生。

不借 92k TS、Cordis 运行时、插件市场、preview 依赖。

---

## 2. 六内核

### 2.1 Task Kernel（最高优先级）

```text
TaskContract:
  goal: str
  acceptance: [artifact_exists | verification_ok | answer_nonempty | diff_nonempty]
  artifacts: [path]
  budget: {max_rounds, max_seconds, max_tokens}
  risk: low|medium|high

PlanGraph:
  nodes: [{id, goal, owner, status, blocks, blockedBy}]
  edges: dependency / invalidation
```

规则：

- `done` 只能由 contract evaluator 给出；模型自述不算。
- 写任务必须有非空产物；运行任务必须有成功验证；纯问答只要求非空答案。
- `terminal_reason`：`completed` / `contract_failed` / `max_rounds` / `refused` / `phantom_file` / `exception`。
- `permission_denials`、`structured_output` 必须可回传。
- 失败分类：`no_artifact` / `wrong_result` / `exhausted` / `infra`，不得混成一个“失败”。

### 2.2 Context Kernel

- repo map：文件树 + 符号索引 + 最近修改，不把整仓塞进 prompt。
- verbatim tail：最近 N 轮原文保留；更早轮次摘要；被证伪轮次打标不删除。
- tool output spill：超过阈值的工具输出写文件，返回路径 + 摘要，不静默截断。
- 动态段移出 system prompt：cwd/env/git status/memory paths 放首条 user message，提高 cache 复用。

### 2.3 Action Kernel

- `apply_patch`：exact old/new，replace_all；不整文件重写。
- reflected test loop：写 → 跑测试 → 读失败 → 修 → 再跑；最多 N 次，失败转 observation。
- 并行只读工具；写操作串行。
- 错误转 observation，不抛成任务死亡。
- 默认 sandbox；host 执行必须显式 escape。

### 2.4 Skill Kernel

```text
verified trace → candidate procedure → human review → active skill
                                      ↘ reject / stale / archived
```

- 只从“真实工具轨迹 + 验证通过”提取，不从模型自述提取。
- `ProposeSkills` 式：1–3 个 proposal，带 evidence 路径、完整 SKILL.md、new/improvement。
- 用户保存才 active；`proof_count` 是独立证据条数，不是置信度。
- curator：active/stale/archived；never delete；pinned 豁免。
- 没有真实轨迹就保持 0，不手写假技能。

### 2.5 Memory Kernel

- 事实/过程分流：`REFERENCE` vs `SKILL`；`chat` 不落库。
- 双时间：`observed_at` / `valid_from` / `valid_to`；`supersede` 不删除。
- 证据：`source_ids` / `proof_count`；缺证据标 `missing_evidence`。
- knowledge page 是投影，不是 source of truth；可重建、带 sources。
- 检索指标：无 labels 时 MRR/NDCG 保持 `null`，不填 0。
- 向量/图/RL 是条件扩展；没有消费者就不引入。

### 2.6 Eval Kernel

- 30 题：10 基础 + 10 中等 + 10 难；每题有 oracle / hidden tests / artifact 检查。
- pass@k、失败分类、canary、成本/时延。
- 基准本身要可验证：真值动态计算，不硬编码；过期路径/过期正则必须修。
- 评测与训练分离：bench 题不得成为 agent 的提示词。

---

## 3. 机制优先级

| 机制 | 来源 | 现状 | 优先级 | 消费者 |
|---|---|---|---|---|
| TaskContract + 可验证 done | Claude ProposeGoal / OpenHands critic | 无 | **P0** | task_exec |
| 失败分类 + terminal_reason | Claude result schema | 部分 | **P0** | bench / metrics |
| Turn budget in prompt | goose | 无 | **P0** | task_exec |
| Permission 分层 + restricted | Claude | 部分 | **P0/P4** | exec_policy |
| Plan mode | Claude | 无 | **P1** | task_exec |
| Task graph | Claude | 无 | **P1** | task_exec / UI |
| apply_patch + reflected test | OpenHands / SWE-agent | 部分 | **P1** | task_exec |
| repo map + verbatim tail + spill | opencode / aider / codex | 部分 | **P1** | context |
| Workflow + resume | Claude | 无 | **P2** | orchestration |
| background review + curator | Hermes | 无 | **P2/P3** | skill_writer |
| ProposeSkills 审批流 | Claude | 无 | **P2/P3** | skill_writer |
| seam/event/session log | DSH | 部分 | **P1/P2** | runtime |
| sandbox 默认 | Claude | 无 | **P4** | exec_policy |
| 向量/图/RL | 多源 | 无消费者 | 冻结 | — |

---

## 4. 路线图与验收

| 阶段 | 时间 | 目标 | 硬验收 |
|---|---:|---|---|
| P0 停止假完成 | 0–2 周 | 10 题 ≥7/10；`no_artifact=0` | contract gate + bench 修复 + terminal_reason |
| P1 看得见/改得动 | 2–4 周 | 30 题 ≥18/30 | plan mode + task graph + apply_patch + repo map |
| P2 可恢复/可诊断 | 4–6 周 | resume 100%；重复副作用 0 | workflow resume + session fork + spill |
| P3 学得会 | 6–9 周 | ≥10 active procedural，proof≥2 | background review + ProposeSkills + curator |
| P4 记得准 | 9–12 周 | 50 labels，MRR≥0.70 | labels + fusion + consolidation |
| P5 边界/生态 | 12–16 周 | 沙箱、MCP/A2A、四维成本 | sandbox + protocol adapter + budget |

最终目标：**24/30（80%）**。在 bench 到 80% 前，冻结“agent 改自己代码”，只允许 skill/prompt/policy 自改 + validation-revert。

---

## 5. 不做什么

- 不复制 codex 的 ~125 crates / 1.55M LOC 结构，不引入 `code_mode` V8 子进程。
- 不把 cline 命令黑名单当安全边界。
- 不把“compaction = summarize and hope”当上下文管理。
- 不抄 Claude 的 prompt/工具名/实现；只借契约。
- 不逆向 Claude 二进制，不绕过登录/DRM，不复制专有代码。
- 不手写 procedural skill，不伪造 proof_count，不填 MRR/NDCG 假值。
- 不提前引入向量/图/RL；当前失败不是 recall miss。

---

## 6. P0 执行清单

1. 新增 `TaskContract`：写任务验产物、运行任务验成功、问答验非空。
2. `done` 统一过 contract；失败改 `incomplete` + `terminal_reason=contract_failed`。
3. 轮数过半注入 `[turn-budget]`；耗尽返回 `terminal_reason=max_rounds`。
4. 修 bench：旧路径、过期 README 正则、`classes` 不可能阈值。
5. 测试：contract 正/反例；budget note；bench 真值。
6. 全量测试 + gate + 自测基准复跑；通过后再谈 P1。

---

## 7. 证据文件

- `WAVE2_CLAUDE_HERMES_DSH.md`：Claude/Hermes/DSH 详细对照。
- `findings/coding.md`：14 列主表 + 证据 + reject list。
- `findings/frameworks.md`、`memory.md`、`browser_research.md`、`selfimprove_eval.md`。
- `findings/rea_goose.md`：REA 实证边界。
- 本文件为最终主方案；旧 `DWC_PURE_ULTIMATE_STRENGTHENING_PLAN.md` 保留为历史版本。

---

## 8. P0 实测记录（2026-10-27）

### 8.1 已落地

- `src/dwc/llm/task_contract.py`：`TaskContract` 完成判定。
- `src/dwc/llm/task_exec.py`：最外层接入契约；轮数过半注入 `[turn-budget]`；耗尽 `terminal_reason=max_rounds`。
- `config/task_bench.json`：移除旧 `E:/Divine Wisdom Core` 路径；README 题改为读当前 `passed` 数字。
- `scripts/dwc_bench.py`：README 真值改 `pytest...N passed`；`classes` 阈值改为“命中全部类名”（旧阈值在只有 2 个类时恒为 3，题目不可能通过）。
- `tests/test_task_contract.py`：11 项；`tests/test_r301_qa_loop.py` 一条旧假设改为只测 R4。

### 8.2 实测

| 项 | 结果 |
|---|---|
| 全量测试 | **3376 passed / 9 skipped / 0 failed（219.56s）** |
| 质量门 | **8/8** |
| 自测基准 | **8/10 = 0.800**（旧 5/10） |
| 失败 | `T_b_core_classes`：契约拦截，未交 `core_classes.md`；`T_b_def_count`：`.txt` 为空，且 `python -c` 被命令策略挡住 |
| 关键修复验证 | `T_b_mult3` 由“incomplete 但 verifier 过”改为 `done`；`T_b_readme_test` 由误判“要跑 pytest”改为 `done`；`T_b_def_count` 不再被同名 `.py` 冒充产物 |

### 8.3 诚实边界

- `T_b_def_count` 的失败是**执行策略 + agent 未改用脚本路径**，不是契约误判；当前仍计 `no_artifact`。
- `T_b_core_classes` 是真实能力失败：agent 跑了多次命令但未落盘。
- 契约只覆盖“产物/命令/答案”三类，不覆盖语义正确性；语义仍由 verifier 负责。
- `permission_denials` / `structured_output` 尚未实现，留到 P1。
- 生产已部署 P0：`~/.dwc` 提交 `06ae386`，pid `1418168`，生产全量 3376 passed / 9 skipped，gate 8/8。

---

## 9. P0.5 契约补齐（2026-10-27）

### 9.1 机制

当任务已经有真实动作、但 `final` 不满足完成契约时，给模型**一次**明确补齐机会：

```text
read/run/write … → final（缺产物）
  → contract 打回：缺 artifact_exists
  → 模型补 write/run
  → final → contract 通过
```

限制：

- 只对 `not qa_mode`、`actions_log` 里至少一条 `phase=obs` 的任务生效；
- 最多 1 次，`DWC_CONTRACT_REPAIR=0` 可关；
- 零动作的假完成仍然直接判死，不进入补齐；
- 契约本身抛错时 fail-open（不拦任务），但写 session 留痕。

### 9.2 实测

| 项 | 结果 |
|---|---|
| 全量测试 | **3378 passed / 9 skipped / 0 failed（225.08s）** |
| 质量门 | **8/8** |
| 定向测试 | `test_task_contract_repair` 2 项 + `test_task_contract` 11 项 + 既有 49 项通过 |
| 基准补齐验证 | **未完成**：`T_b_core_classes` / `T_b_def_count` 复跑遇端点 `HTTP 502`，记为 `llm_reject`，不能声称补齐提升 pass rate |

### 9.3 边界

- 补齐是“给一次机会”，不是保证成功；模型仍可能补错或补不出。
- 端点 502 属于 infra，不是 agent 能力；基准结果必须区分 `llm_reject`。
- P0.5 已部署生产：`~/.dwc` 提交 `0cd2fa7`，pid `1432868`，生产全量 3378 passed / 9 skipped，gate 8/8。
