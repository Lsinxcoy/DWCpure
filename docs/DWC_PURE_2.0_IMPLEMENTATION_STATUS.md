# DWC pure 2.0 实现状态（诚实边界）

本文件只记录**已实测**的实现状态，不把设计、单元测试或 shadow 结果写成生产已启用。

## 1. 当前证据

| 项目 | 结果 |
|---|---|
| 全量测试 | `3391 passed, 9 skipped`（7 个 `live` 真端点测试默认 skip；2 个常规 skip；无 deselect；P0 TaskContract 11 项 + P0.5 契约补齐 2 项 + P1 apply_patch 6 项 + P1 TaskGraph 5 项 + P1 plan mode 2 项） |
| 质量门 | 8/8 通过（`scripts/gate.py --json`） |
| 基线方案提交 | `881c2215e86d9cad214de802b944d3895992eeb7` |
| 实现检查点 | `9c308bd` W1/W2–W6 核心；`b5775ab` 评价/shadow/apply 入口；`f5cc00f` 合并上游 R439–R458；`58524a9` W5 单一真源；`7b09f0f` agent term 级任务账；`c850809` 记忆 M0–M3；`5543f42` A 类边界（总 deadline/live 隔离/验证门/轨迹消费）；`ee754aa` 流式总 deadline |
| 生产部署 | `~/.dwc` 本地提交 `ae3bf4b`（代码对应 release `890bb39`）；agent `--llm` 常驻 pid `1483560`，RPC 8802；生产全量 `3389 passed / 9 skipped`，gate 8/8 |
| 工作分支 | `divine-wisdom-core-pure` |
| 原仓库 | `upstream/master` 保持只读，不推送 |

真实 LLM 测量（探针进程，不是常驻生产 agent）：

- 普通正文：`prompt=2648 / completion=18 / total=2666 / cached=0`
- 带缓存：`prompt=2509 / cached=1159 / completion=20 / total=2529`
- native tool：`prompt=2338 / cached=1116 / completion=37 / total=2375`，`finish_reason=tool_calls`
- 2026-10-25 复验：`prompt=2192 / completion=15 / total=2207 / cached=0`，`measurement_status=measured`，真实 `record_id` 落库
- 合并上游后复验：`prompt=2124 / completion=37 / total=2161 / cached=0`，`finish_reason=tool_calls`，`measurement_status=measured`
- 生产 canary（`~/.dwc` 代码 + 生产 `config/llm.json`，3 道只读问答）：3/3 `done`、1 轮、`measured`；usage `2218/9`、`2214/37`、`2217/66`，`cached=0`，`pricing_status=not_configured` → `cost_status=indeterminate`
- 生产常驻 agent 首轮（`code_fix_001__p1_s20751`）：`task_metrics=measured`，`input=153 / output=49 / cached=0`，与唯一 `llm_attempt` 一致；`cost_status=indeterminate`（未配价格，不填 0）

## 2. 已接入生产代码路径

| 能力 | 状态 | 证据 |
|---|---|---|
| LLM 每次物理 attempt 的 usage/interface 观测 | active | `src/dwc/llm/client.py`、`tests/test_llm_usage.py` |
| stream→fallback→retry 父子链 | active | `tests/test_llm_usage.py::test_stream_fallback_retry_keeps_original_parent_chain` |
| SSE 混合正文 + tool call、malformed 参数 | active | `tests/test_llm_usage.py` |
| 任务级统一收尾、真实 `record_id`、`incomplete` 诚实状态 | active | `src/dwc/llm/task_exec.py`、`tests/test_task_exec_metrics.py` |
| agent term 级 `task_metrics`（按本轮时间窗聚合） | active | `scripts/dwc_agent.py`、`src/dwc/observability/context.py`、`tests/test_agent_term_metrics.py` |
| SQLite WAL 证据账、幂等、脱敏、raw ref+hash | active | `src/dwc/observability/evidence_store.py`、`tests/test_evidence_store.py` |
| 正式尝试、C/CoP、缺 usage 不填零 | active | `src/dwc/observability/task_metrics.py`、`usage_pricing.py` |
| 辅助角色归属（revision/planner/executor 等） | active | `tests/test_auxiliary_measurement_roles.py` |
| 规则任务画像（四层身份、`execution_adjustment=shadow`） | active-shadow | `src/dwc/llm/task_exec.py`、`tests/test_runtime_profile_shadow.py` |
| 上游 R439 成本账 / 三档计价 | active | `src/dwc/llm/cost.py`、`tests/test_r439_cost.py` |
| 上游 R440 工具输出压缩 + 原文落盘 | active | `src/dwc/llm/tool_raw.py`、`tests/test_r440_tool_raw.py` |
| 上游 R441 三段式工具预算 | active | `src/dwc/llm/budget.py`、`tests/test_r441_budget.py` |
| 上游 R444 规则选档（只调预算） | active | `src/dwc/llm/profile.py`、`tests/test_r444_profile.py` |
| 上游 R457/R458 skill 记忆与做法来源 | active | `src/dwc/organs/skill_writer.py`、`tests/test_r457_skill_recall.py`、`test_r458_method_memory.py` |
| 记忆检索事件账（M0：access + retrieval + zero-hit） | active | `src/dwc/organs/memory.py`、`src/dwc/llm/executor.py`、`tests/test_memory_retrieval.py` |
| skill 质量分类元数据（M1.1：procedural/factual/chat） | active | `src/dwc/organs/skill_writer.py`、`tests/test_skill_quality.py`；生产 12 条 = 4 factual + 8 未标 + 0 显式 procedural；`memory_text` 已按 kind 过滤 |
| 过程技能字段（M1.2：steps/tools/verification/evidence_ref） | active-api | `src/dwc/organs/skill_writer.py`、`tests/test_skill_procedure.py`；尚未接生产判分器 |
| 记忆数据契约（H1/H3/H4：derived_kind/observed_at/valid_from/valid_to/source_ids/proof_count/supersedes） | active | `src/dwc/organs/memory.py`、`tests/test_memory_contract_v2.py`；旧库加法式迁移 |
| factual → REFERENCE（H2） | active | `src/dwc/organs/skill_writer.py:migrate_factual`、`tests/test_skill_migration.py`；`dwc memory migrate-factual --apply` |
| knowledge page 投影（H6） | active | `src/dwc/organs/knowledge_page.py`、`tests/test_knowledge_page.py`；`dwc knowledge build/check/search`，不进每轮 prompt |
| 离线 consolidation（H5） | active-api | `src/dwc/organs/consolidate.py`、`tests/test_memory_consolidate.py`；默认 dry-run，保留原节点 |
| 写入脱敏（H7） | active | `src/dwc/organs/memory_guard.py:redact_obj`、`tests/test_memory_redaction.py`；全通道生效 |
| 任务轨迹落盘（M1.4：actions_log → refs/hash） | active | `src/dwc/llm/task_trajectory.py`、`src/dwc/llm/task_exec.py`、`tests/test_task_trajectory.py` |
| 记忆写入门（M1.6：通道信任 + 注入/控制字符/重复/超长 → quarantine） | active | `src/dwc/organs/memory_guard.py`、`src/dwc/organs/memory.py`、`tests/test_memory_guard.py`；旧 `remember()` 不传通道时零变化 |
| skill 过滤（M1.3：factual/chat 不进 prompt） | active | `src/dwc/llm/executor.py`、`tests/test_skill_filter.py`；legacy 无 kind 现场分类 |
| 工作态证据门（M1.7） | active-api | `src/dwc/organs/working_state.py`、`tests/test_memory_working_state.py`；尚未接生产任务收尾 |
| 巩固保护（M1.8） | active | `src/dwc/organs/memory.py:revise/learn/dream`、`tests/test_consolidation_guard.py` |
| 成功/失败对比（M1.5/M3.2） | active-api | `src/dwc/harness/contrast.py`、`tests/test_memory_contrast.py`；无生产配对样本 |
| 记忆边（M2.1） | active | `src/dwc/organs/memory.py:link/neighbors/multi_hop`、`tests/test_memory_edges.py` |
| SELF 保护区（M2.2） | active | `src/dwc/organs/memory.py:Zone.SELF/revise_self`、`tests/test_memory_self.py` |
| 偏好/信念（M2.3） | active | `src/dwc/organs/preference.py`、`tests/test_memory_belief.py` |
| 上下文预算（M2.4） | active-api | `src/dwc/organs/memory_context.py`、`tests/test_memory_context.py` |
| 检索质量 MRR/NDCG（M2.5） | active-api | `src/dwc/organs/memory.py:retrieval_quality`、`tests/test_memory_retrieval_quality.py`；无标签返回 None |
| 可解释维护（M3.1） | active-api | `src/dwc/organs/memory_maintenance.py`、`tests/test_memory_maintenance.py`；只出建议，不自动删 |
| 轨迹拼接（M3.3） | conditional | `src/dwc/harness/trajectory_stitch.py`、`tests/test_trajectory_stitch.py`；无生产消费方 |
| 条件扩展 feature gate（M3.4/MEM-19） | active-off | `src/dwc/organs/memory_policy.py`、`tests/test_memory_non_goals.py`；向量/RL/MemPO 默认关 |
| 原子组件更新 `update()` 与跨进程锁 | active | `src/dwc/organs/evo_targets.py`、`tests/test_atomic_evo_targets.py` |

## 3. 已实现且有入口，但默认 shadow-only

| 能力 | 入口 | 边界 |
|---|---|---|
| 固定协议、Pareto/双基线选择 | `scripts/dwc_shadow_round.py` | 只读冻结评价，不自动晋级 |
| 多 rollout 诊断 | `scripts/dwc_shadow_round.py` | 只输出诊断，不改执行 |
| intent×scope 稀疏计划、静态校验 | `scripts/dwc_shadow_round.py` | 不生成代码、不调用模型 |
| Probe/Compose | `scripts/dwc_shadow_round.py` | Compose 返回 `needs_reprobe`；不替代固定评价 |
| 离线候选评价 | `scripts/dwc_evaluate_candidate.py` | 只读 attempts/usage/pricing，不调用 LLM |
| 多组件安全落地 | `scripts/dwc_apply_candidate.py` | 必须显式 root + `--confirm APPLY`；生产根需 `--allow-production`；已做生产根可逆事务 canary，真实候选未落地 |
| recovery journal / canary | `src/dwc/harness/recovery_journal.py` | 先持久化 undo，再写目标；只发布 committed |
| 历史卡片/经验库 | `src/dwc/harness/history_retrieval.py`、`reflection_library.py` | 脱敏、namespace 隔离；未接入生产演化轮 |
| 预算/输出压缩/条件 review | `src/dwc/llm/budget_controller.py` 等 | 单元测试通过；尚未改变 `task_exec` 行为 |
| cache 身份与 fail-closed 策略 | `src/dwc/llm/cache_policy.py`、`cache_capability.py` | 当前端点未验证，默认不发送 cache 扩展 |

## 4. 尚未完成 / 明确未启用

1. **生产已切换但仍是“受控运行”**：`~/.dwc` 已按路径三方合并到 release `6debd57`，本地提交 `3a4147c`；`config/llm.json` 已切到可用的 DWC 端点，旧 403 配置备份为 `config/llm.PRE_DEPLOY_403.json`。agent `--llm` 常驻 pid `1015496`，RPC 8802；cron 副本指向 `~/.dwc`。未做的是“长期稳定性观察”；生产根事务回滚已单独演练。
2. **W5 运行时已单一真源**：`task_profiles.py` 只做投影，预算/选档委托 `dwc.llm.budget` + `dwc.llm.profile`；`budget_controller.py`、`output_compaction.py`、`completion_review.py` 仅供评价/证据，不进入运行时。
3. **真实 shadow round 未跑生产任务集**：入口已在临时目录端到端验证，尚未对真实任务集执行。
4. **生产根事务已演练，真实候选未落地**：2026-10-25 在 `~/.dwc` 用 `read_default_lines 250→251` 执行 `--allow-production --confirm APPLY`，journal `committed`、canary 通过，随后按 journal 回滚，文件哈希恢复为 `1d8d193…`。这是事务 canary，不是改进候选；真实候选仍需评价/审批后再落地。
5. **Windows 低权限沙箱未验证**：script/hook Probe 仍应 `blocked`，不能宣称 shadow verified。
6. **AKV serving 未启用**：当前远程 OpenAI 兼容端点不支持 `drop_message/reposition`；无定制 SGLang/GPU 实测。
7. **TIES/SFT 未启用**：无 checkpoint/训练控制权，只能作为未来条件扩展。
8. **synth_tests/coreset 未实现**：属于条件扩展，不作为真值替代。
9. **价格未配置**：生产 usage 已真实记账，但 `pricing_status=not_configured`，成本一律 `indeterminate`；不填 0、不估算美元。
10. **上游仍会前进**：本次已合并到 `9aaa6f8`（R458）；之后若上游再更新，需要重新 fetch/审查合并，绝不回推原仓。
11. **M0–M3 已部署生产，边界已按类型处置**：`from_task_result()` 已接 `scripts/dwc_agent.py::run_user_task`，默认门 `result_verified()`（done + 至少一次成功 run/test/check），不是生产判分器；`trajectory_ref` 已进任务结果并用于写过程技能；`trajectory_stitch` 已接 `_revision_retry` 修订对；成功/失败对比仍无生产配对样本；向量/RL/MemPO 由 `memory_policy.py` 默认关闭。7 个真端点 live 测试默认 skip（`--run-live` 才跑）；`test_r208_agent.py::test_agent_lifecycle_short_run` 标为 live，不再用 deselect。`LLMClient` 已加总 deadline（默认 ≤90s，普通与流式/回退共用同一 deadline），端点不可用时是有界失败，不再无限挂主线程。全量 `3365 passed / 9 skipped` 是默认集，不能写成“真端点也全绿”。

## 5. 复现命令

```bash
# 全量（live 自动 skip）
.venv/Scripts/python.exe -B -m pytest tests -q -p no:cacheprovider

# 真端点 live（会触网；端点不可用时应有界失败）
.venv/Scripts/python.exe -B -m pytest tests -q -p no:cacheprovider --run-live

# 机制矩阵审计（19 项代码/测试落点）
.venv/Scripts/python.exe -B scripts/audit_memory_plan.py

# 质量门
.venv/Scripts/python.exe -B scripts/gate.py --json

# 离线评价
.venv/Scripts/python.exe -B scripts/dwc_evaluate_candidate.py \
  --attempts attempts.json --usage usage.json --pricing config/pricing.example.json \
  --out report.json --require-measured

# shadow 轮（只读）
.venv/Scripts/python.exe -B scripts/dwc_shadow_round.py \
  --bundle bundle.json --out shadow.json

# 受控 apply（示例；生产必须另行审批）
.venv/Scripts/python.exe -B scripts/dwc_apply_candidate.py \
  --root /tmp/dwc-root --journal /tmp/dwc-root/var/recovery.json \
  --patches patches.json --confirm APPLY
```
