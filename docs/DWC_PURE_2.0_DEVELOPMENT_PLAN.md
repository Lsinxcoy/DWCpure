# DWC pure 2.0 最终升级方案 · 四论文代码级融合规格

> **方案版本：`DWC-pure-2.0-final-spec-v2`**
>
> **状态：PLANNED / FROZEN。只允许维护本规格与研究附件；用户明确解冻前不得开始实现。**
>
> 固化日期：2026-10-25。基线：`divine-wisdom-core-pure` @ `5769a125d1a370f9b3fc2c41d0d2fcbeef6d095e`。
>
> 本文是 DWC pure 2.0 唯一开发计划入口。所有“拟新增/拟扩展”的文件、类、函数、字段、配置、测试和命令均为**设计对象，不是当前能力**。

---

## 0. 最终裁定

### 0.1 目标

把 DWC pure 从“已有多种进化机制”升级为一套可证明的**性能—成本双目标、证据驱动、模型—harness—cache 配对、可恢复、可回滚**的自进化系统：

```text
真实观测与完整身份
  → 固定评价、结果完整性、基线保底、Pareto
  → 多 rollout 失败/浪费/接口/缓存诊断
  → intent × scope 候选 → Probe → Compose/no-change
  → 独立复评 → 经验写门 → shadow 运行时画像
  → held-out → 人类批准 → 原子落地/消费者 smoke/回滚
```

### 0.2 五工作流不变，条件扩展不插队

1. **W1 真实测量**：usage、尝试、任务、候选、模型—harness pair、cache 与全阶段成本。
2. **W2 固定评价与选择**：协议冻结、结果完整性、base/incumbent、性能门、Pareto、严格独立验收。
3. **W3 多 rollout 诊断**：correctness/waste/instability/infrastructure/TIMR/cache、历史检索、混杂边界。
4. **W4 候选与改进经验**：三意图 × invariant/domain、Propose–Probe–Compose、并行/串行、经验 NO_ENTRY。
5. **W5 运行时**：任务画像、预算收敛、可恢复输出、条件性模型路由与 cache policy。

**AKV serving、checkpoint/TIES/SFT 是条件性扩展，不是 W1–W5 的前置，不新增 W6。**

### 0.3 “全部可借鉴点”的口径

本方案吸收四篇论文及代码中**对 DWC 有正向工程价值且能用证据约束的机制**，包括论文方法、代码中的可靠性与防污染设计。不是逐行复制，不吸收已证伪或冲突的选择方式：

- Harness² finals-only 排除 base；
- CoEvo quality-first lexicographic 替代 Pareto；
- 把 TIMR/行为变化/adopted 当正确性；
- 把客户端 cache history/HTTP 200 当服务端 KV 生效；
- 特定 benchmark 的提示词、K、阈值、价格、RTK 二进制与平台锁；
- 无评测协议的自动部署、latest-only、历史分数跨 pair 复用。

### 0.4 论文与代码的事实边界

| 来源 | 论文核心 | 代码可核事实 | DWC 处置 |
|---|---|---|---|
| HarnessPro `2610.26770v1` | 双目标 RSI、合成测试、多 rollout、三意图、Pareto、画像 | 九套 harness、运行/计价/资格/收敛工具；**公开仓库没有完整三阶段进化、test synthesis、Pareto 实现** | 论文机制自行实现；代码可靠性设计可迁移 |
| Harness² `2610.14224v1` | 任务级与改进级双层递归 | Propose/Probe/Compose、8 组件、library、selector、ledger、调度 | 借证据链与经验；反向修正 base 排除 |
| Cache Engineering `2610.28577v1` | append/drop/repos、AKV serving、cache policy RSI | agent policy、operation history、定制 SGLang、usage/支持矩阵 | 当前做 identity/capability/observation；serving 仅未来验收契约 |
| CoEvo-RSI `2610.25078v1` | brain–body mismatch、双向历史继承 | TIMR、pair lineage、checkpoint 选择/合并、SFT、晋级 | 先做 pair/TIMR/route；TIES/SFT 条件附录 |

### 0.5 不可违反的全局不变量

1. **声称=实测**：paper/code/current/design 四类陈述分开。
2. **缺失不是零**：usage、coverage、价格、revision、effect、score 均允许 `unknown/not_reported/not_applicable`。
3. **base 永远在最终池**：Compose 保留 base 不等于最终 selector 保留 base；二者都强制。
4. **行为变化≠通过，adopted≠verified，接口兼容≠能力，cache 决定≠生效。**
5. **旧分不跨身份复用**：model/harness/tool/render/cache/decoding/task/evaluator 任一变化即重新评价。
6. **固定评价不参与生成**：held-out、gold、grader verdict、评分缓存不得进入 Curator/Editor/Compose/Reflection。
7. **无证据 no-change/no_update/NO_ENTRY 是一等成功结果**，不是进化失败。
8. **生产主权不被自动化突破**：shadow→held-out→人类批准→备份→读回→consumer smoke→canary→rollback。
9. **预测和实测分栏**，关联与因果分栏，单点贡献未隔离时 `unallocated/confounded`。
10. **成本不只算推理**：搜索、评价、诊断、重试、fallback、分类、复核、缓存工具、训练/驻留分别记。

---

## 1. 代码组织：五个主入口，协作模块可独立测试

不建立四套论文子系统，也不把全部机制塞入五个巨石文件。五个主入口负责稳定 API，以下协作模块按职责拆分。

### 1.1 拟新增文件树

```text
src/dwc/
  observability/
    __init__.py
    task_metrics.py          # W1 主入口：UsageEvent/AttemptRecord/TaskMetrics/CandidateEvaluation
    identity.py              # PairIdentity/ProtocolIdentity/CacheStateIdentity/canonical hash
    usage_pricing.py         # usage 正规化、价格、C/CoP、迟到 usage 对账
    interface_trace.py       # 原始/effective 响应、工具协议事实
    evidence_store.py        # SQLite WAL 事实账、幂等、查询、旧 JSONL 只读迁移
  evaluation/
    __init__.py
    protocol.py              # 固定协议、split、evaluator bundle、结果完整性
    synth_tests.py           # 条件扩展：固定合成测试与反例，不当作 ground truth
    coreset.py               # 后置扩展：多样性训练核心集，held-out 排除
  harness/
    pareto_select.py         # W2 主入口：base floor/dominance/代表点/no_update
    rollout_diagnostics.py   # W3 主入口：rollout/waste/TIMR projection/cache diagnosis
    history_retrieval.py     # archive 快照、脱敏失败相似检索、引用凭证
    intent_candidates.py     # W4 主入口：intent×scope、稀疏计划、schema
    component_manifest.py    # 8 类组件与 DWC consumer 映射、sparse inheritance
    evidence_bundle.py       # 证据树、materialized/withheld、分权读取
    evidence_guard.py        # rubric/gold/verdict/egress/deliverable allowlist
    probe_compose.py         # Probe、行为对照、Compose、真实 diff no-change
    improvement_schedule.py  # parallel/sequential/checkpoint/确定性账序/resume
    reflection_library.py    # EditEvidence/ExperienceEntry/NO_ENTRY/prefix 时序
    artifact_selector.py     # 条件 shadow 匿名交付物选择，不替代 Pareto
    candidate_workspace.py   # 隔离候选、artifact manifest、commit/rollback handle
    run_identity.py          # runmark、内容寻址缓存、resume compatibility
  llm/
    task_profiles.py         # W5 主入口：规则画像、runtime spec、cache policy spec
    cache_capability.py      # 四态 capability、支持矩阵绑定、扩展合并 fail-closed
    cache_policy.py          # 纯决策 trigger/selector/repos/保护规则，不做 GPU serving
    budget_controller.py     # economy/converge/finalize/hard cap/denial/incomplete
    output_compaction.py     # raw 可恢复 head/tail/重复行，内容类型白名单
    completion_review.py     # 条件 fresh/contract review，两段 usage 与剩余预算
scripts/
  dwc_metrics_migrate.py     # 只读旧账→新库，幂等，不回写旧账
  dwc_evaluate_candidate.py  # 固定协议离线评价，不自动 apply
  dwc_shadow_round.py        # W3/W4 shadow 入口，不修改生产 config
config/
  pricing.example.json       # 示例无真实价格；未配置不估算
  validation_protocol.example.json
  runtime_profiles.example.json
  cache_capabilities.example.json  # 默认 unsupported_remote
tests/                       # §13 的完整测试矩阵
var/                         # 运行期生成，全部 gitignore
  dwc_metrics.sqlite         # 新事实账；WAL，单写事务/跨进程锁
  evidence/                  # 原始响应/轨迹/交付物引用，按权限分区
  evolution_archive.jsonl    # 脱敏历史卡；非评分真源
```

### 1.2 拟扩展现有文件

| 文件 | 精确扩展 | 明确不改的语义 |
|---|---|---|
| `llm/client.py` | 全路径 usage/interface trace、call context、cache 可选扩展、stream/fallback 双账 | `LLMResult` 必填构造、旧 stats、重试上限、凭证纪律 |
| `llm/executor.py` | Receipt 透传 measurement/interface refs | 不把 parser 输出当任务真值 |
| `llm/task_exec.py` | 统一 finalize、局部 collector、画像 shadow、预算状态机、TIMR 转换前观测 | 现有工具白名单、native/JSON 回退、权限/ask、安全与 incomplete 诚实性 |
| `harness/run_term.py` | `TermReport` 可选 measurement/pair refs | `CostLedger.step_cost` 抽象成本、judge 三态、effect 口径 |
| `harness/loop.py` | 多候选 shadow 评价、current/original_base 同池、W2→六门 | 不把 replay 单标量改义，不自动落地 W4 |
| `scripts/dwc_evo_round.py` | base/probe/compose/reflection 角色账、intent/scope、真实搜索成本 | 旧 envelope 可读；生产 auto_apply 不给新候选继承 |
| `organs/evo_targets.py` | 组件 spec、唯一临时文件、唯一备份、原子 rollback、读回、consumer smoke | 白名单、schema、默认兼容；不开放任意代码 |
| `organs/credit.py` | 通过 sidecar 补 winner/loser/confounded，不改旧七元组 | `delta_c` 仍为旧抽象成本，绝不改义成 USD |
| `organs/replay.py` | 只读投影到新 selector | current 必含、确定 tie-break、val fallback source |
| `organs/router.py` | 消费真实 metrics 投影 | 七桶与 infra_only 不进化纪律 |
| `organs/effort.py` | 不改；只供 dream replay K2 | 不拿来当任务难度分类器 |
| `organs/memory.py` | 经验证据 sidecar/只读索引；不复制完整 harness | 现有 FTS/Weibull/learn/effect 护栏 |
| `harness/gates.py` | 新增 strict 2.0 模式，缺独立评价/usage 即 blocked | legacy 三态仅供历史观察，不用于严格自动晋级 |
| `scripts/gate.py` | 新模块定位/真值/静默/池上限检查 | 原有门禁不因新方案放宽 |

### 1.3 存储与 Windows 决策

- 新事实账采用 **SQLite WAL + 短事务 + 唯一 idempotency key**，不依赖 POSIX `fcntl`，不以 `os.replace` 解决多写者 JSONL。
- 原始大对象放受控 evidence 区，数据库只存 hash/ref；秘密、API key、凭证永不入库。
- 临时文件同目录唯一名，`flush+fsync` 后替换；Windows 不做目录 `O_DIRECTORY` fsync。
- 备份名含 `candidate_id + content_hash + uuid`，不使用秒级时间戳作唯一身份。
- read-modify-write 全程持跨进程锁；rollback 与 apply 共用安全写函数并读回 hash。
- 所有测试通过 tmp_path/临时 DB 注入路径，禁止测试写生产 `var/config`。

---

## 2. 统一身份、状态与证据模型

### 2.1 身份必须分层，禁止一个 hash 包打天下

```python
# 拟建逻辑签名，不是当前代码
PairIdentity(
  model={provider, route, requested_model, reported_model,
         revision, revision_status, route_observation_id},
  identity_stability,  # stable_revision | observation_scoped
  cache_reuse_allowed,
  harness={bundle_hash, semantic_change_hash, prompt_version,
           tool_schema_version, rendering_version, control_config_hash},
  cache={policy_version, capability_id, operation_history_digest},
  runtime={profile_effective_hash, reasoning_effort, environment_version},
)
ProtocolIdentity(
  task_manifest_sha256, train_ids, val_ids, heldout_ids,
  evaluator_id, evaluator_version, evaluator_artifact_sha256,
  dependency_manifest_sha256, synth_test_sha256_by_task,
  outcome_kind, rollout_rule, seed_policy, decoding_config_hash,
  environment_profile, pricing_version, created_before_candidate_id,
)
CacheStateIdentity(
  provider, endpoint_family, model_revision_or_unknown,
  tokenizer_identity, chat_template_identity, rendering_version,
  tool_schema_identity, reasoning_template_options, rope_config_or_unknown,
  canonical_full_message_prefix_digest,
  ordered_cache_operation_history_digest,
  normalization_version,
)
```

- `pair_id/eval_id/cache_state_id/run_id/candidate_id` 分别计算；cache state 相同不意味着评价可复用。
- 模型身份分稳定 route alias 与路由观测：只有经验证的稳定 revision 可令 `identity_stability=stable_revision, cache_reuse_allowed=true`。远程 revision 未披露时，每次评价运行生成并持久化新的 `route_observation_id`，令 `identity_stability=observation_scoped, cache_reuse_allowed=false`；同一 alias 在两个观测期不得命中旧评价，同一观测期内也只能按完整 protocol/result manifest 复用。观测期结束后的结果只作历史参考，不能作为跨期同权重证明。
- `semantic_change_hash` 用于去重，`harness_bundle_hash` 用于评价身份，包含动态引用模块与实际资产。
- canonical JSON 排序键、禁 NaN、整型严格校验；逻辑消息包含 tool name/call id/arguments/assistant tool calls/boundaries。

### 2.2 状态机禁止隐式推导

```text
draft → static_validated → probe_ready → probed → composed
      → fixed_evaluated → shadow_candidate → heldout_passed
      → human_approved → applied → consumer_smoke_passed
```

任何阶段可进入：

```text
no_evidence / no_change / no_update / unsupported /
invalid_candidate / infrastructure_error / blocked / rolled_back
```

独立事实字段：

```text
behavior_changed, delivered, task_pass, adopted, verified_improvement
policy_decided, request_sent, extension_fields_sent,
server_accepted, usage_observed, behavior_verified
```

不得写 `behavior_changed => task_pass`、`adopted => helped`、`HTTP 200 => server_accepted`。

### 2.3 成本与效果状态

```text
usage_status = reported | partial | not_reported | malformed | unsupported
pricing_status = priced | partial | unpriced | not_configured
measurement_status = measured | incomplete | insufficient |
                     invalid_candidate | infrastructure_error | evaluation_error
evidence_status = exploratory | confounded | independent_ready | verified
cost_scope = solve_execution | evolution_search | evaluation |
             adaptation | serving_residency | deployment
```

未启用的训练是 `not_applicable`，不是成本 0；未报告的推理是 `not_reported`，也不是 0。

---

## 3. W1 · 真实性能—成本与配对测量

**依赖：无。只观测，不自动调参。**

### 3.1 三层账，不做混杂大表

```python
UsageEvent(
  schema_version, event_id, call_id, parent_call_id,
  task_id, term_id, candidate_id, parent_candidate_id,
  rollout_id, attempt_id, attempt_index, idempotency_key,
  call_role, cost_scope, cost_stage, parent_stage_id,
  requested_model, actual_model, model_revision_status,
  endpoint_class, pair_id, provider_trace_id,
  started_at, observed_at, wall_time_ms, transport_status, finish_reason,
  usage_raw_ref, usage_status, usage_coverage,
  input_tokens, cached_input_tokens, cache_write_tokens,
  output_tokens, reasoning_tokens,
  pricing_version, pricing_status, estimated_cost,
  cache_hit, original_execution_ref, evidence_ref,
)

AttemptRecord(
  attempt_id, parent_attempt_id, task_id, candidate_id, baseline_id,
  rollout_id, protocol_id, pair_id, artifact_hash,
  attempt_class, selected_formal, formal_exclusion_reason,
  cost_inclusion, outcome_kind, passed, score,
  resolved_tests, total_tests, evaluator_id, evaluator_version,
  solver_wall_ms, grader_wall_ms, environment_setup_ms,
  transport_wait_ms, retry_backoff_ms,
  execution_cost, execution_cost_status, excluded_infra_cost,
  call_event_refs, tool_events_ref, trajectory_ref, deliverable_refs,
  profile_effective_hash, complete_marker_ref,
)

CandidateEvaluation(
  candidate_id, baseline_id, protocol_id, pair_id, epoch_id,
  execution_pair_ids, execution_mixture_id, route_coverage_by_model,
  expected_task_ids, completed_task_ids, pending_task_ids,
  infra_failed_ids, invalid_ids, unexpected_task_ids,
  result_set_complete, performance_kind, performance,
  mean_cost_per_task, cost_of_pass, cost_status,
  cost_scope_breakdown, requested_tasks, completed_tasks, successful_tasks,
  n_rollouts, sample_variance, confidence_interval_or_unknown,
  usage_complete, pricing_complete, measurement_status, evidence_refs,
)
```

`TaskMetrics` 是 Attempt/Rollout 的聚合视图，不复制一套可手写的总数。所有汇总由明细计算。

**混合模型资格：**`pair_id` 是计划中的预期 pair；`execution_pair_ids` 记录实际执行的 pair 集合，规范化后形成 `execution_mixture_id`，并按模型保存 task/attempt 覆盖与 fallback 分布。正式单 pair 评价中，若实际 route/model 偏离预期，资格为 `indeterminate`，不得按 actual model 分别计价后合并掩盖。只有 protocol 显式定义 mixture 时，才允许在相同 mixture identity 下比较；不同 mixture 默认不可复用或比较。

### 3.2 LLM client 全路径接入清单

拟在 `LLMClient` 增加可选 `CallContext`，旧调用者不传时产生 `unassigned` 并在测试/严格模式报警；生产接入后 solver/judge 等必须归属。

| 路径 | 必做 | 防错 |
|---|---|---|
| 非流式正文 | 保存原始 `data.usage`、actual model、trace ref、finish reason | 不只保存 text |
| tool_calls | 同上，并保存原始工具结构 | parser 成功不抹接口事实 |
| reasoning_only/empty/parse error | 有 usage 仍记，结果失败与用量分开 | 不免费、不伪造 pass |
| SSE | 处理无 choices 的 usage 末帧，聚合 tool calls | 当前 `choices[0]` 跳过末帧的缺口必须修 |
| stream→complete fallback | stream 与 fallback 各一条 attempt，parent 关联 | 合并 `fb.meta`，不得丢前段 usage |
| 429/5xx/transport retry | 每次物理 attempt 独立；同一 logical call 串联 | 不用 n_calls 推 token |
| stream/tools | 统一最终 body 构造与扩展语义 | 不为 cache 另造第三套请求路径 |
| 未配置/提前失败 | 记录 not_configured，无 provider usage | 不生成虚假 provider call |

`n_calls/n_retries` 保持旧口径；新增 `llm_attempts`，不暗改统计含义。

### 3.3 调用角色与全成本

`call_role` 至少覆盖：

```text
solver_base, solver, probe, compose, final, judge, retry, fallback,
expansion, diagnosis, planner, editor, classifier, review, selector,
reflection, test_synthesis, rejection_sampling, adaptation
```

- solver/review/classifier/cache tool 等计入任务执行；analyzer/planner/editor/compose/reflection 计入搜索。
- cache hit 的增量成本可为 0，但必须引用原执行；历史成本不被抹掉，也不在 resume 重复计。
- 训练/模型加载/驻留与 API token/美元/GPU 小时不混加；父子 wall time 重叠不可直接求和。
- `abstract_step_cost`、`CreditEntry.delta_c`、`evo_round.search_cost` 保持各自旧语义，以 ID 关联，不互换。

### 3.4 usage 正规化与价格

`usage_pricing.py` 纯函数：

```python
normalize_usage(raw, provider_adapter) -> NormalizedUsage
price_usage(normalized, pricing_entry) -> PriceResult
reconcile_usage(provider_total, observed_events) -> ReconcileResult
summarize_candidate(attempts, usage_events, price_book) -> CandidateEvaluation
```

- cached input 不重复算进 uncached；cache write 独立。
- reasoning 是否包含 output 由 provider adapter 决定，不全局假设。
- fallback/混合模型按 actual model 计价；任一相关模型无价格，正式总成本不可比。
- 迟到 usage 只补差额；provider 总量小于已见量时 `conflict`，不改原始事件。
- 价格记录 source/as_of/version；重定价生成 `repriced_from`，不改历史裁决。
- 未配置价格只报 token；论文价格表不成为 DWC 默认。

### 3.5 正式尝试、C、CoP、延迟与双账

先执行确定性的 `select_formal_attempts`：按 `(candidate, execution_pair/mixture, protocol, task, rollout)` 选择唯一 formal attempt，其他 attempt 必须有排除原因并另账。基础设施重试只能恢复既定 formal unit，不得从多次模型结果中择优；正式 attempt 不存在则该 unit `indeterminate/infrastructure`，不能拿次优重试顶替。

DWC 2.0 的正式统计单位固定为 **task-rollout formal unit**：G>1 时每任务各 rollout 独立计成本与结果，任务级宏平均作为辅助视图；binary pass 不通过“任一卷成功”变成任务成功。若未来采用任务级聚合，必须另立 protocol，预先定义聚合规则，不能与 task-rollout 结果混排。

- `C = formal execution cost / requested formal units`，失败 unit 仍在分母。
- `CoP = formal execution cost / successful formal units`，成功为 0 时 `None + zero_successes`。
- 报告同时给 `requested/completed/successful formal units` 与 task 数，避免把 task 和 task-rollout 分母混用。
- usage/价格不完整时正式 C/CoP 为 `indeterminate`；可另报 observed lower bound，但不用于裁决。
- 基础设施重试不得变成“任抽到最好”；`formal` 与 `excluded_infra/search` 成本分别展示，已发生费用不消失。
- `solver_wall/grader_wall/setup/transport_wait/retry_backoff` 分段；缺段为 None，不伪造 effective time。

### 3.6 Pair、TIMR 原始事实与 cache observation 接点

W1 只采集原始 interface trace 和 cache observation，TIMR 在 W3 计算。

```text
InterfaceTrace: request_index, response_stage=provider|client,
  offered_tools, raw_response_ref, effective_response_ref,
  transport_repaired, termination, parse_status, evidence_ref

CacheObservation: capability_id, cache_mode,
  policy_decided, request_sent, extension_fields_sent,
  server_accepted=true|false|unknown|not_applicable,
  server_acceptance_basis, usage_status,
  akv_cached_tokens, repos_tokens, drop_skipped_tokens,
  actual_prefill_tokens, actual_decode_tokens,
  provider_cached_input_tokens, residency_or_recovery_status,
  unsupported_reason, evidence_ref
```

普通 provider cached tokens 与 AKV cached/repos/drop_skipped 分字段，不相加成“节省”。

### 3.7 W1 验收门

1. 每种 client 返回路径均有 fake transport fixture，原始 usage 可追溯。
2. 所有生产 LLM 调用点有角色与 task/candidate 归属；无“免费辅助调用”。
3. fallback/retry/cache hit/resume 不重计、不漏计。
4. 缺 usage/价格/模型 revision 时状态正确，不填 0。
5. `task_exec` 每个 early return 恰好写一次 task 汇总。
6. 现有 `CostLedger`、Credit、replay、effect 相关旧测试保持语义。
7. 此阶段不产生候选、不调生产参数。

---

## 4. W2 · 固定评价、完整性与双目标选择

**依赖：W1。先离线重放/shadow，不自动 apply。**

### 4.1 固定协议与数据隔离

冻结：任务与 split、初始 harness/轨迹、合成测试、evaluator 与依赖、模型/端点类别、decoding、工具/环境、rollout/seed、预算、价格身份。

- train/dev 可用于诊断与生成；validation 只做选择；held-out 只最终独立验收。
- `heldout_ids` 出现在 planner/proposer/compose/reflection 输入即阻断。
- **validation 也不是下一轮的训练/反思材料**：其 score、verdict、dominance、baseline floor、派生 history score 和评分缓存不得进入 Curator/Editor/Compose/Reflection/后续历史检索。只向这些角色投影允许的 train/dev 行为证据；W2 的 SelectionReport 保存在独立评价命名空间。
- 固定评价版本改变，旧分只作历史参考。
- validation 一次或 G=3 是论文实验设置，不是 DWC 抗噪声保证；先用 paired baseline 估计噪声带，不足则 `insufficient`。

### 4.2 结果资格先于 Pareto

```python
qualify_run(expected, observed, protocol) -> Qualification
# complete | incomplete | invalid_candidate | infrastructure_error | evaluation_error
```

检查：空结果、重复 task、pending、unexpected id、0 tests、not_run、缺/多 branch、同数量不同 test identity、artifact 评分前后 hash 变化。

- 无效 baseline ⇒ 整池 `indeterminate`，不得选“最差中的最好”。
- 缺数据候选不得以 pass=0/cost=0 被支配或选中。
- ungraded 显式计数，不随意当 fail 或从报告消失。
- `binary_pass` 与 `macro_test_score` 不在同一 protocol 混排。

### 4.3 合成测试是条件扩展，不是真值替代

若启用 `evaluation/synth_tests.py`：

- 仅由允许的 task description + seed harness/trajectory 生成一次，随后冻结 artifact hash。
- 保存 generator/prompt/source hash、known counterexamples、uncovered behaviors、validation status。
- 候选无权修改测试；独立反例与 held-out 必须存在。
- 初步 judge 召回提升不是无漏报证明；通过合成测试不等于真实完成。
- 公开 HarnessPro 仓库无生成器，需自行实现并验收。

### 4.4 一次性终选择算法

本函数只读取冻结评价记录，输出只写独立评价命名空间，不返回给生成侧；候选生成与经验只能使用 train/dev 证据。

```python
select_candidate_pool(
  evaluations, *, incumbent_baseline_id, original_base_id,
  protocol, mode_weights
) -> SelectionReport
```

顺序固定：

1. 校验 protocol/pair/结果完整性/usage/pricing。
2. 计算 performance、C、CoP 和不确定性。
3. `incumbent_baseline_id` 提供当前生产基线 `baseline_floor`，`performance < baseline_floor` 者过滤；性能门不可用便宜补偿。current 无效/缺失时整池 indeterminate，不自动退回较弱的 H0。
4. 构造 `{incumbent_current} ∪ {original_base} ∪ parents ∪ finals ∪ checkpoints`；current 或 original base 缺失直接 raise/block。original H0 仅承担历史对照和独立回滚位，不替代 current 的性能门。
5. 统计资格独立硬门：固定 paired seeds、最小 formal units、非劣/提升判据和成本 CI 规则预先写入 protocol。`measurement_status!=measured`、样本不足、性能差落入基线噪声不可区分区时只能 exploratory/no_update；shadow 可算 Pareto，但 `selection_eligibility=false`，不得标 verified improvement。
6. Pareto：性能不差且成本不高、至少一项严格更好才支配。
7. 归一化仅用于从非支配集选代表，不重新接纳 below-floor。
8. 保留 `retained_ids`（含 current 与 original base）、`pareto_front_ids`、`dominated_by`、理由与样本量。
9. 无合格子代 `no_update/no_change`；selector/transport 失败回 current，original H0 只作独立灾备回滚。

### 4.5 归一化、并列与代表点

采用性能与成本偏差的归一化加权平方距离；论文 `(1,2)/(1,1)/(2,1)` 仅作待校准初值。

- max=min 时该维偏差设 0，并记 `degenerate_dimension`，不除零。
- 同分按 `candidate_id` 确定 tie，不随机。
- 同一候选可对应多个 mode，`unique_parent_pool` 去重，因此可少于 3 个。
- 每轮归一化集合不同，J 不跨轮直接比较。
- base 的部署回滚位独立保留，即使数学上被更优候选支配。
- 小样本单次微差不直接宣布稳定支配；不足样本标 unknown/insufficient。

### 4.6 Pair 评价、模型路由与贡献分离

当前只支持受控 `model_route`，不是 checkpoint。

最小对照：

```text
H0/M0                incumbent
H1/M0                harness-only
H0/M1                model-route-only（若改模型）
H1/M1                joint candidate
```

- 未测臂写 `unmeasured`，不得声称已解耦。
- 历史 pair 分只用于检索/假设，当前 pair 必须同题重评。
- TIMR 只在同 task set、metric version、完整 coverage 下辅助；不得越过性能门。
- CoEvo quality→TIMR→token 的 lexicographic 不替代本 Pareto。
- `pre/post adaptation` 仅未来训练扩展；当前只有 `unadapted`。

### 4.7 严格独立验收门与匿名 selector

新增 strict 2.0 模式：`independent_evaluation_required=True` 时，缺 held-out/evaluator version/必要 usage ⇒ `blocked`。legacy `NA` 只读兼容，不用于自动晋级。

匿名 artifact selector 仅可作为 shadow triage：

- canonical sort + seeded shuffle，匿名映射对 selector 不可读；
- selector 只看 quarantine-passing deliverables/source，不看 harness、cost、parent、intent、trajectory；
- 只能选已有交付物，不能合成答案；无交付项记 dropped；
- 结果只标 `adopted`，不能覆盖固定 evaluator/Pareto/base/held-out。

### 4.8 评价缓存、resume 与 failure-first

- cache key 含完整 pair/protocol/task set/artifact/evaluator/environment/decoding；`cache_reuse_allowed=false` 的 observation-scoped pair 只能在同一 `route_observation_id` 内复用，禁止跨运行/跨期命中。
- complete marker 只有 runner 正常结束才写，含 run/artifact/protocol/component hash。
- 只有 answer 文件、manifest 不符、hash 改变、缺 artifact 均不得复用。
- failure-first 只重排任务，必须基于完整 baseline 且仍全量执行；baseline outcome 不进入 solver，不能变成只测失败题。

### 4.9 W2 验收门

1. 手算候选集的 floor/frontier/代表点与程序一致。
2. base 最好/最差/同分/缺失、空池、全子代差均正确。
3. 零范围、NaN、重复、同分、缺 usage、版本不一致有确定行为。
4. 同轨迹离线重放得到同一报告；held-out 从未进入选择。
5. 严格模式缺独立评价即 blocked；legacy 不得绕过。
6. 结果明确 `offline/shadow/production`，不混称。

---

## 5. W3 · 多 rollout 诊断、TIMR、历史证据

**依赖：W1；评价使用 W2 固定协议。**

### 5.1 Rollout 分组与诊断契约

分组键：`task_id + candidate_id + pair_id + protocol_id + effective_profile_hash`。不同 pair/config 不混组。

```python
Diagnosis(
  problem_type,        # correctness/waste/instability/infrastructure/
                       # interface_mismatch/capability_underuse/harness_restriction/cache
  scope,               # invariant/domain
  frequency, observed_rollouts, pass_pattern, outcome_pattern,
  performance_impact, cost_impact_or_unknown,
  trajectory_refs, event_ranges, first_effective_event_ref,
  redundant_event_ranges, repeated_action_keys, state_change_refs,
  confidence, unknowns, independence_limits, confounders,
  evidence_status,
)
```

分类：稳定失败、flaky、稳定成功、成功但浪费、infra-only、接口问题、cache 证据损失。k 个 base 是同分布样本，不是 k 个独立故事；同模型共识不提高独立证据等级。

### 5.2 浪费诊断

- 重复 action 只有在 state/evidence digest 未变且后续未产生新信息时才为 `candidate_waste`。
- 重复命令但状态已变不能自动判浪费。
- 成功轨迹同样诊断：首次有效步、无新信息读取、重复验证、长输出、恢复/收尾。
- 每条成本归因引用 trajectory+event range+usage ref；缺 usage 时 unknown。
- renderer truncation 标 `origin=renderer`，不自动归为 solver 缺陷。
- 长轨迹保留 event index 和原始 refs，摘要可定点回查；64K 不是默认阈值。

### 5.3 TIMR 精确算法

```text
TIMR = count(distinct model turns with ≥1 interface violation)
       / count(observed model turns)
```

分类：unknown tool、invalid JSON、argument schema、response protocol、final format；同一 turn 多类只计 1，task union 另报。

必须区分：

- provider raw response 与 client effective response；
- transport repair 与后续 interface recovery；
- tool return contract unknown 与 tool return success；
- 0 turns 的 `rate=None` 与 0 violations 的 `rate=0`。

Coverage 分项：`raw_trace_tasks/tool_names/argument_schemas/tool_returns/complete_interface_turns`，各含 checked/total/rate/reason。缺 trace/schema/远程 `$ref`/domain semantics 时 unknown，不填 0。

`capability_underuse/harness_restriction` 需要额外行为对照，不能由“没调用新工具”直接推断。

### 5.4 Cache 诊断

分别观察：

- logical token 长度、active cache reported、physical residency reported；
- 重复 prefill/recovery、位置上限、工具响应长度与近期性；
- drop 后仍需的旧证据、reasoning/约束/验证材料保护；
- `drop_skipped>0` 与 `actual_prefill>0` 可同时存在，不矛盾；
- cache policy 额外轮次和 cache tool 成本。

文本 compaction 是独立 baseline，不能改名 cache drop；drop 不是隐私删除或权限撤销。

### 5.5 历史 archive 与确定性检索

`var/evolution_archive.jsonl` 只存脱敏 history cards 与证据引用，不是评分真源。每轮冻结 `archive_snapshot_id`。

```text
HistoryCard: harness_id, pair_refs, protocol_ref,
  diagnostics_summary, adopted/rejected designs, dependencies,
  evidence_refs, historical_reference_only=true
# 生成侧投影禁止 score/verdict/dominance/floor/heldout/validation 派生字段；
# 历史评分仅存独立 evaluation namespace，不能被引用展开。
```

检索仅用 domain contract、failure outcome、脱敏 diagnostics；不把原始题面/gold 作特征。TF-IDF 风格、固定 tie-break；支持 `failure_similarity/recent`，不 latest-only。零向量、重复 ID、空历史显式处理。

Curator 输出共享 context：current failures/design requirements/evidence limits/references/avoid/constraints。Editor 只拿自己的 hypothesis brief；引用与实际 adopted design 分开，控制器校验引用属于 brief。

### 5.6 经验前诊断与批次归因

- invalid/duplicate 候选仍占生成/评价预算，slot 中断恢复不漂移。
- batch attribution 区分 harness/model/external，文本摘要不是唯一真源。
- peer diff 只在同 task/protocol 下作关联证据，多组件编辑列 confounders。
- `Credit` 新 sidecar 记录 winner 和 `admissible_but_lost`；无逐编辑隔离 Δ 时 `unallocated/confounded`，禁止均摊整候选收益伪装精确。

### 5.7 W3 验收门

1. 稳定失败、随机波动、成功浪费、infra 四类正确分桶。
2. TIMR 同 turn 去重、0 turns、coverage、修复/恢复、跨版本不可比全有反例。
3. 低 TIMR+低 PR 仍不能晋级；协议对但答错不归 interface。
4. 诊断可定位原始事件，无证据不生成成本/因果结论。
5. 历史检索无 gold/question 泄漏；archive 快照不受未来写入影响。

---

## 6. W4 · intent × scope、Probe–Compose 与改进经验

**依赖：W1–W3。只产 shadow 候选。**

### 6.1 稀疏候选，而非机械 3×2

| intent \ scope | invariant | domain |
|---|---|---|
| cost-first | 重复探索、冗余提示/工具/上下文 | 领域重复读取、无效核对 |
| balanced | 验证/恢复的性能成本权衡 | 领域技能/流程的前沿改善 |
| performance-first | 有证据的恢复、验证、接口修复 | 领域正确性缺口与专用检查 |

只给有诊断证据的格子生成候选。无证据 `no_evidence/no_change/unsupported`，不复制同一改动换名。

### 6.2 候选计划与 lineage

```python
CandidatePlan(
  parent_id, intent, scope, diagnosis_refs, archive_snapshot_id,
  hypothesis, reference_ids, adopted_designs, rejected_designs,
  dependencies, evidence_limits, avoid,
  edits=[{edit_id, component, operation, path, content_ref, evidence_refs}],
  expected_performance_effect, expected_cost_effect,
  preserved_behavior, regression_risks, acceptance_checks,
  validation_protocol, rollback_handle,
  model_route_change, harness_change, changed_axes,
  predicted_vs_measured_status, plan_status,
)
```

- expected 与 measured 不混写；acceptance_checks 不得改 held-out/evaluator。
- focused/generalizable；task-specific identifier 不作为通用规则。
- 候选生成 slot、重复/invalid、retry/fallback 全计成本。

### 6.3 8 类组件映射与 sparse 继承

| 类别 | DWC consumer | 约束 |
|---|---|---|
| system prompt | `prompt_ota` / prompt artifact | 版本与实际生效进程一致 |
| guardrails | `hook`/RULES | 不放宽铁律与权限 |
| memory | `memory`/agent_quality | 经验写门、effect 护栏 |
| tool guidance | `context_mgmt/client_tool` | 有真实消费者，不只写文件 |
| subagents | `subagent_policy`/caps | 不支持则拒绝，额外 episode 入账 |
| skills | `skill_store`/dwc_skills | frontmatter/trigger/helper 完整 |
| scripts | shadow sandbox 候选 | 编译/权限/超时，不自动生产注册 |
| plugin/hooks | `agent_harness`/hook | schema/事件/只读点/命令约束 |

这 8 类不是 AgentHarness 的 8 个 hook point。只登记有真实 consumer 的组件；always-on 文本记录静态成本，on-demand 记录实际 activation。

sparse patch：未提交=继承，显式 delete 才是删除；materialize 后内容 hash 验证。候选路径仅白名单相对路径，拒绝 `..`、绝对路径、symlink 逃逸。

### 6.4 Propose–Probe–Compose

1. **Base**：无 base rollout 只能 `needs_measurement`，不能直接编辑晋级。
2. **Propose**：优先行为 divergence，再重复失败，最后才是有证据的未实现风险；禁止只凭“最佳实践”。
3. **静态验证**：一次列出全部错误；允许一次带错误反馈 retry，再失败继承 fallback，成本照计。
4. **Probe**：只允许 `split=train/dev` 的 `ProbeProtocol`，同 task/model/environment 的 shadow 真执行，绑定 candidate hash；validation/held-out 的 task id 别名、artifact、verdict 和评分缓存均禁止。记录 behavior/delivered/usage/infra。
5. **Compose**：可整取、合并、修订、丢弃、恢复旧 checkpoint、KEEP_CURRENT；解决重叠，不简单拼接。只接收 train/dev 行为对照，不接收 validation SelectionReport。
6. **真实 no-change**：由 materialized diff/hash 判定，不相信模型文本自称 KEEP。
7. **复评**：组合后重新静态验证+Probe，最终回 W1/W2；Probe 不代替固定评价。

无交付编辑默认不安全；状态型任务显式 `deliverable_kind=state`，不能拿轨迹代替交付物。交付形状属于用户契约，候选不得通过改名、额外列、placeholder、说明代计算“优化”。

### 6.5 并行与串行搜索

- parallel：k base → scoped candidates → 多 Compose，共享冻结证据池，扩宽度。
- sequential：当前 checkpoint 逐轮修正，携带历史，可恢复旧 checkpoint/rejected edit，original base 永不丢。
- k=1 两模式同过程；k>1 收益须超过 k=1 重跑噪声。
- R=4k/P=3k 不照搬；预算按实际稀疏计划计算。
- 并发执行后按 canonical label 排序落账；重复 label 先报错，再核数量。
- parallel/sequential 是 W4 搜索预算，不是 W5 任务难度画像。

### 6.6 经验 Reflection 与 NO_ENTRY

Reflection 输入 base、全部候选（含 rejected）、train/dev probe、compose decisions 和**脱敏 SelectionReceipt**，不只看 winner。SelectionReceipt 只含允许 split 的行为/采用/成本事实，明确剔除 validation/held-out score、verdict、dominance、baseline floor 及其派生字段；完整 SelectionReport 永不进入 Reflection。

```python
EditEvidence(
  edit_id, candidate_refs, compose_decision, contrast_refs,
  verdict,             # helped/hurt/no_observed_effect/confounded
  confounders, sample_size, independence, attribution_status,
  adopted,             # 与 verdict 完全独立
)
ExperienceEntry(
  cue, applicable_scope, component, operation,
  supporting_contrasts, edit_evidence_refs,
  confidence, confounded, source_harness_ref, evaluation_version,
  fact_scope,           # workspace/domain/invariant
  revalidation_required,
)
```

写门：

- cue/scope/component/operation/evidence 缺一则 `NO_ENTRY`；
- 多组件无隔离或单 probe 不写 helped；
- adopted 不推导 helped；winner 的 Δ 不均摊给 edits；
- workspace facts 不进长期通用记忆；domain/invariant procedure 复用仍需当前 Probe；
- reflection 失败不写库，审计与成本仍留；
- library namespace 按 domain/protocol/search_mode/evaluator_epoch 隔离，resume 只能读当前任务之前前缀；
- 不复制完整任务定制 harness，只存组件/经验引用；
- 做 `no_library/evidence_only/component_reuse` 同预算消融，无收益即撤回，生成/检索成本入账。

### 6.7 候选隔离与评价防污染

证据面覆盖 source、trajectory、deliverable、component、library、cache、selector/reflection、网络：

- answer-free task read boundary；proposer/compose 不 import judge/golden。
- deny globs + 文件名/正文 verdict tripwire；最终 bundle 再全量检查。
- deliverable 使用 per-task **正向 allowlist**，只读 agent-authored bytes；judge/score 输出永不作候选证据。
- proposer 可 names-only；selector 只读隔离后 artifact；reflection 不见 held-out verdict。
- `EVIDENCE_IS_DATA`：恶意 SKILL/artifact 中指令不执行；候选代码只在 shadow sandbox。
- 网络 egress allowlist/DNS 防火墙阻 answer-key/rubric 主机，记录外联与下载 hash；不能只靠 prompt/sandbox 声明。
- renderer 对 xlsx 公式/缓存、二进制、tar 等 loud failure；stub/缺缓存值不得当已计算/通过。

### 6.8 Windows shadow sandbox 硬前提

`llm/sandbox.py` 的 AST 限制不是通用 script/harness 隔离器，不能用来宣称 shadow verified。可执行 script/hook Probe 必须满足：

- 独立低权限 Windows 身份；只给候选根和必要依赖 ACL，生产 config/var、其他用户目录与凭证不可读。
- 清空 API key/token/代理凭证等环境，禁止继承父进程敏感环境。
- Windows Job Object 限制并终止整棵进程树，设置 CPU/内存/进程数/时限。
- 默认断网；必要外联只能经受控 broker，按允许目的地与内容策略转发，防止直接 IP/ alternate DNS 绕过，不能把 DNS 域名过滤当完整边界。
- 路径规范化后校验根内，拒绝 symlink/junction/reparse point 越界、大小写混淆与设备路径。
- 原始证据 materialize 前脱敏；脱敏器失败、ref 缺失、长度或 SHA-256 不符均为 `evidence_error` 并阻断评价。evidence 目录独立 ACL、保留/删除期限、禁止凭证环境继承。

无法满足任一项时，script/hook Probe 与 egress 测试为 `blocked`，不得退化为 AST 检查仍标 shadow verified；纯数据/纯函数候选可在不执行候选代码的测试环境继续。

### 6.9 W4 验收门

1. intent×scope 空格不产候选；三意图不是复制换名。
2. Probe 绑定 hash；behavior/pass/adopted/verified 各反例不串状态。
3. Compose 的 kept 由 diff 决定，原始 base 仍在最终池。
4. 多组件/单 rollout 强制 confounded；NO_ENTRY 不写可召回经验。
5. 候选无权写 evaluator/held-out/gates；泄漏/注入/egress 反例被阻断。
6. 阶段结束只产 shadow，不调用生产 `ET.apply`。

---

## 7. W5 · 任务画像、运行时收敛与条件 cache

**依赖：W1–W4 shadow 证据。先 shadow，再小流量。**

### 7.1 画像输入与四层身份

只用公开任务特征，不用历史成绩、隐藏测试、任务指纹或 gold。

保守初版：`lean/standard/deep/research`，默认 standard；五档、0.9、14/26/44 不照搬。模型分类器只有规则画像证明有价值后才评审，多样本投票不是默认必做。

```text
public_task_features
profile_requested / classified_profile / effective_profile / actual_profile
selection_source / confidence / rationale / fallback_reason
classifier_call_id / vote_counts / consensus_status
execution_adjustment / actual_model / actual_reasoning_effort
profile_effective_hash
```

画像参数：reasoning effort、max rounds、repeat limit、工具预算、final reserved calls、阶段提示、输出恢复、可选 model route/cache policy。默认值必须与当前 task_exec 行为一致，缺产物走旧行为。

### 7.2 预算收敛状态机

```text
economy → converge → finalize → hard_exhausted
```

- economy：提醒合并/去重，只是软提示。
- converge：停止广泛探索，具体失败与变异交付物仍可修。
- finalize：保留 final/必要修复预算，deny 新低价值探索。
- hard_exhausted：硬 cap，重复 budget denial 触发 best-effort 收尾；非预算 denial 不误停。
- 超预算如实 `incomplete`，保留 artifacts；不能隐藏未完成或只发提示不执行上限。
- 阈值配置校验严格递增，具体值由 DWC 数据校准。

### 7.3 可恢复输出与条件 review

`output_compaction`：raw_ref/hash、原/压后长度、omitted range、content kind/version；原文在受控 evidence 区，可定点恢复。重复行/head-tail/二进制/图片/密钥各有白名单；raw 写失败则未压缩并留痕，不丢验证证据。

RTK/命令重写不是一期依赖；未来仅允许白名单命令族，heredoc/重定向/命令替换/危险 find 等拒绝，语义等价测试，全成本归因。

`completion_review` 是条件扩展：短执行/明确风险才触发；记录 initial/review 两段 usage、剩余预算、最终实际 artifact。review 失败不冒充初段成功，不无条件二次调用。

### 7.4 模型路由运行时

只用已验证 pair 兼容矩阵和公开任务特征做 shadow 路由；latest 只是候选。远程 provider 静默换模型属于 identity 风险。模型与 harness 不同时自动晋升；生产切换仍需 W2/held-out/批准。

---

## 8. AKV 条件扩展 · 当前不支持也必须诚实

### 8.1 三种操作与三条边界

- append：新 token 在当前 active cache 条件下计算并追加。
- drop：在 trigger 后排除指定 KV；保留文本、保留 KV 位置，下一 append 不自动回收位置。
- repos：保留 r 项重排位置 0..r-1，RoPE 旋 key、V 不变；与 drop 独立，同边界先 drop 后 repos。
- 保留 KV 可能携带后来 drop 历史的信息，drop 不是彻底遗忘。
- 逻辑文本、active cache、物理 residency 三层不同；物理 eviction 不应改变请求语义。
- 保留兼容 KV 免重算，不代表物理丢失后免恢复。

### 8.2 四态 capability，默认 fail-closed

```text
unsupported_remote → declared_unverified → shadow_verified → active_eligible
```

绑定 endpoint/model/runtime revision/wire schema/support matrix/usage validation。`/v1/models`、OpenAI-compatible、HTTP 200、工具 scheduled receipt 都不是支持证明。

- 默认不发送 `drop_message/drop_rule/reposition/cache`。
- declared 未验证仍不发生产扩展；shadow decision 可记录“会选什么”，无线上效果。
- 明确拒绝时不自动去字段重发；普通恢复另建 `ordinary_fallback` attempt，独立成本与 cache_mode。
- retry/stream/fallback 复用同一 final body 与 operation history，不重新随机决策。
- active_eligible 还需 held-out、回退/回滚、完整账和人工批准，不自动升级。

### 8.3 声明式 CachePolicy

```text
status=disabled|shadow|eligible
trigger={turn|token|model_tool, after/every/threshold/counter_identity}
selector={turn|token|model_tool, target=tool, retain_turns/retain_tokens}
reposition={off|turn|token|model_tool, independent schedule}
protected_roles=[system,user]
protection_rules_version/max_selected_per_turn/max_operations
branch_reset_rules/unsupported_action=omit_and_mark
```

- trigger false 不调用 selector；repos 独立；token counter 与服务端 tokenizer/template/tools/thinking 不一致时禁用 token 规则。
- 默认 tool-only，不默认丢 reasoning；K=12 不是默认值。
- 原子 tool batch 不半删；保护 system/user、任务约束、未解决失败、当前假设来源、最终验证材料、不可恢复原文。
- model cache tool 的 receipt 只能 scheduled，非法 ID 整次失败；额外轮次与读取 receipt 全入账。
- 当前无支持端点时，cache policy 不进 W2 线上候选。

### 8.4 未来 serving 只列验收契约，不在 DWC 实现

若未来另立兼容服务项目，才验收：

1. extended radix 同时匹配 token+operation+position，A/B/C 历史分支不串 KV。
2. transformed reuse 不算 direct cached tokens。
3. drop-aware eviction 不全局删除共享 KV，活跃计算/恢复 pin，position version 独立。
4. segment-batch restoration 在冷/热/部分驱逐下保持语义，actual prefill/recovery 可观测。
5. usage 的 cached/repos/drop_skipped/actual prefill 用独立 read-set fixture 对账，不能由请求参数回显。
6. 性能按固定硬件/模型/并发报 TTFT/TPOT/P95/吞吐，论文倍数不是验收常量。

支持矩阵须核模型 architecture、text-only、RoPE、attention backend、page size、KV dtype、并行/PD、LoRA/speculative/beam/session/multimodal 等。任一变化重新验证。当前不要求引入 SGLang/CUDA/GPU 依赖。

---

## 9. CoEvo 条件扩展 · 训练不属于当前主线

未来只有 DWC 自有模型、数据治理、算力与安全验收齐备时才考虑：

- checkpoint 共同 base、architecture/tokenizer/layout 兼容；
- TIES/linear recipe 内容寻址，合并后在当前 harness 重评；
- rejection sampling 仅用所选 pair 自己的 train 轨迹，accepted/attempts/hash 留痕；
- pre/post/incumbent/latest 同协议比较，训练失败可保留 pre；
- 训练、采样、评价、加载、驻留成本分别记；
- 模型权重回滚、数据许可、泄漏、安全和独立 held-out 另行批准。

当前禁止：把 model_route 叫 effective_weights_hash，把 ensemble/router 叫 TIES，把历史成功轨迹默认当训练数据，把未执行 SFT 写成 post-adapted。

---

## 10. 运行可靠性、落地与回滚

### 10.1 Preflight

花钱前检查 runner/runtime/renderer/evaluator/workspace/权限/网络策略。缺项为 infrastructure_error，不形成可评分 dead rollout；已发生费用照记。

### 10.2 内容寻址缓存与 resume

- key 含 label+mission+system+context bytes+workspace+model+prompt+channel+task+protocol+mode；禁止 mtime 作身份。
- complete marker 只有正常返回才写，包含 run/component/artifact/protocol fingerprint。
- adopted run、artifact、harness、fingerprint 任一不符即 incompatible/re-run。
- proposer/diagnosis cache 命中只代表增量未执行，不抹原成本；重复 resume 幂等。

### 10.3 多组件落地事务与崩溃恢复

不能只靠“文件写完再补台账”。采用跨文件 recovery journal/outbox：

1. 人类批准后，按规范化 target path 排序获取**完整 target set 的锁**，禁止并发候选交叉提交。
2. 在任何生产变更前，持久化 journal 并 fsync：`candidate_id/targets[]/每项 before_hash/after_hash/backup_ref/state=applying`；SQLite 事务与文件 journal 通过同一 recovery id 对应。
3. 逐项唯一备份、唯一临时写入、fsync、replace、readback；任一项失败即按 journal 回滚全部已改项。
4. 全部读回成功后，同一 recovery transaction 写 `committed` 台账与 outbox；随后执行新进程/显式 reload consumer smoke。
5. 只有 `committed` candidate 可进入 canary。重启时若发现 applying/半提交状态，必须依据 journal 完成整体回滚或经验证的整体提交，禁止继续普通任务装作无事发生。
6. 回滚也写新 journal 条目、保留当前备份并原子读回；首次创建无 before 时明确删除新建/恢复 defaults。

崩溃测试覆盖：journal 写前/后、首个与中间 replace 后、ledger commit 前/后、smoke 中、canary 前、rollback 中再次崩溃、两个并发候选、多组件部分失败。

`TASK_TOOLS` 等 import-time snapshot 必须新进程 smoke 或显式 reload；ET.read 成功不等于消费者生效。

### 10.4 严格自动晋级禁止线

新 W4 候选不得继承现有 `auto_apply:true`。`legacy NA`、evo_driver 单信号调参、selector fallback、review 成功、cache HTTP 200 都不能绕过 W2 strict/held-out/人类批准。

---

## 11. 机制覆盖索引（165 项研究机制的去向）

四份逐机制附件是本规格的一部分；下表保证主线没有遗漏主题。

| 来源 | 数量 | 纳入位置 |
|---|---:|---|
| HarnessPro M01–M36 | 36 | W1 M01–14/35；W2 M11–18/34–36；W3 M19–21；W4 M22–25；W5 M26–33 |
| Harness² H2-01–H2-70 | 70 | 组件 H2-01–12；证据/Probe H2-13–25；调度/selector H2-26–36；经验 H2-37–47；成本/恢复 H2-48–58；防污染/落地 H2-59–70 |
| AKV 1–27 | 27 | W1 1/7/21–24；W3 2–6/25；W5 8/16–20；未来 serving 9–15；条件 RSI 26–27 |
| CoEvo 1–32 | 32 | pair W1 1–4/31–32；TIMR W3 5–14；archive W3/W4 15–24；route/pair W2/W4 25–30；训练条件 28–32 |

附件（冻结到本仓库 `docs/research/dwc2/`）：

1. `HarnessPro_DWC_Code_Fusion_Checklist.md`
2. `Harness2_DWC2_Code_Fusion_Checklist.md`
3. `AKV_DWC_Cache_Engineering_Fusion_Checklist.md`
4. `CoEvo_DWC_Code_Fusion_Checklist.md`
5. `DWC_CODE_REUSE_MINIMAL_PATH.md`

若主规格与附件冲突，以本主规格的身份分层、base 保底、严格独立验收、缺失非零、生产主权为准；附件中的文件数量建议已被 §1 的“五入口+协作模块”取代。

---

## 12. 分阶段实施包与依赖

### P0 · 基线与防护骨架（不改行为）

- 唯一交付拓扑：工作目录 `Z:\DWC pure`，分支 `divine-wisdom-core-pure`，`origin=Lsinxcoy/divine-wisdom-core-pure`；`upstream=Lsinxcoy/divine-wisdom-core` 仅只读 fetch/merge，**永不回推**。原仓只读比较基线为 `88d210d`，不得在原仓工作树实施。
- 冻结当前全量测试、gate、生产 config hash、agent 状态；验收时分别检查原仓无改动、新仓提交存在、origin 分支 tip 与本地 HEAD 一致。
- 固定受支持 Python 版本并创建项目 `.venv`，以 `pyproject.toml` 安装项目与依赖；测试依赖显式包含 pytest。锁定本次依赖解析结果，先运行 import preflight，显式使用 `.venv/Scripts/python.exe`，不依赖宿主机偶然已有包。
- 建 fake transport/trajectory/evaluator fixtures 与临时存储。
- 修测试环境自足，所有新测试 tmp_path，不触网/生产。
- 验收：基线结果真实记录；已知 flaky 单列，不伪称永久解决。

### P1 · W1 事实账（只观测）

1. identity/evidence store/usage pricing。
2. client 全路径、task_exec finalize、executor/run_term/evo_round refs。
3. pair/interface/cache observation。
4. 旧 JSONL 只读迁移，新 SQLite WAL 幂等。
5. 验收：§3.7 全过；无候选/调参行为。

### P2 · W2 固定协议与离线选择

1. protocol/evaluator bundle/completeness。
2. base+Pareto+代表点+no_update。
3. pair evaluation/cache/resume/strict held-out。
4. 历史 replay shadow，不接生产。
5. 验收：§4.9 全过；合成测试/DPP 不是前置。

### P3 · W3 证据诊断

1. rollout group/waste/TIMR/coverage/cache diagnostics。
2. archive snapshot/history retrieval/Curator data contract。
3. credit sidecar 全陪跑+confounded。
4. 验收：§5.7 全过；诊断不自动改参数。

### P4 · W4 shadow 改进

1. component manifest/evidence guard/candidate workspace。
2. sparse intent×scope、static retry、Probe、Compose/no-change。
3. parallel/sequential、run identity、确定性 ledger。
4. reflection/NO_ENTRY/library namespace/消融。
5. 验收：§6.8 全过；只产 shadow。

### P5 · W5 运行时 shadow

1. 规则画像、四层 profile identity、分类成本。
2. budget controller/best-effort incomplete/raw recovery。
3. cache unsupported/capability/policy pure decisions。
4. 条件 review/route shadow。
5. 验收：默认行为不变，shadow 不影响真实任务。

### P6 · 独立验收与受控落地

0. 进入本阶段前冻结 `finalist_set_hash` 与 held-out 一次性访问计划；held-out 结果只产生 pass/fail，不得回喂 proposer、Compose、reflection、route 或再次筛选。任何 held-out 后修改都生成新 candidate，并从 P1/W2 重新走完整流程。
1. paired baseline/finalists/必要 pair 分臂。
2. held-out + 人工反例 + 交付检查。
3. PR/C/CoP/L、样本量/方差、infra/invalid/usage coverage。
4. 人类批准后 ET 安全事务与 consumer smoke。
5. 小流量 canary：protocol 预先冻结 base/candidate 分流、最小样本、观察窗、PR/延迟/成本/infra 阈值与自动 rollback 条件；必要 usage 缺失时成本门不通过且不宣称改善。

### P7 · 条件研究包（非默认交付）

- 合成测试与独立反例；
- coreset/DPP，与无 embedding 多样性基线比较；
- anonymous selector/fresh review/cache-as-tool；
- 有兼容端点后的 AKV shadow；
- 自有模型与治理齐备后的 checkpoint/SFT。

---

## 13. 代码级测试矩阵

### 13.1 W1

- `test_llm_usage.py`：正文/tool/SSE/空/推理耗尽/429/5xx/retry/fallback/迟到 usage。
- `test_usage_pricing.py`：cached/uncached/cache write/reasoning、多模型、未定价、重定价、reconcile conflict。
- `test_task_metrics.py`：明细汇总、C/CoP、0 成功、formal/excluded、cost scope、cache hit。
- `test_task_exec_metrics.py`：所有 early return 恰好一账、revision/delegate/judge/expansion 归属。
- `test_pair_identity.py`：model/harness/tool/render/decoding/environment/unknown revision。
- `test_evidence_store.py`：WAL、多进程、幂等、坏行/坏 DB 可观测、秘密不入库。

### 13.2 W2

- `test_candidate_protocol.py`：split/hash/evaluator lock/结果完整/不同 metric。
- `test_pareto_select.py`：floor/base/dominance/零范围/tie/重复/no_update/未知成本。
- `test_pair_evaluate.py`：H0M0/H1M0/H0M1/H1M1、历史分不迁移、未解耦。
- `test_strict_independent_gate.py`：缺 held-out/evaluator/usage 必 blocked，legacy 不可绕。
- `test_evaluation_resume.py`：complete marker、篡改/部分文件、failure-first 不泄漏。
- `test_artifact_selector.py`：匿名/旁路信息/drop/fallback/不越 Pareto。
- `test_synth_tests.py`（条件）：冻结、反例、候选不可改、合成非真值。
- `test_coreset_selection.py`（条件）：多样性、重复/零向量、held-out 排除。

### 13.3 W3

- `test_rollout_diagnostics.py`：稳定/flaky/成功浪费/infra、事件证据、renderer 截断。
- `test_interface_mismatch.py`：turn 并集、分类、repair/recovery、coverage、不可比。
- `test_cache_diagnostics.py`：三层 token、recovery 与 drop_skipped 并存、文本压缩非 drop。
- `test_history_retrieval.py`：确定性、无 gold、快照冻结、recent 非真理。
- `test_credit_evidence.py`：winner/loser 全记、无均摊、旧七元组兼容。

### 13.4 W4

- `test_component_manifest.py`：8 类 consumer、sparse inherit/delete、白路径、frontmatter/hook。
- `test_intent_candidates.py`：稀疏格子、三意图、no_evidence、changed_axes、预算。
- `test_probe_compose.py`：hash 绑定、行为/通过分离、冲突、真实 no-change、一次 retry。
- `test_improvement_schedule.py`：parallel/sequential/k=1/checkpoint/确定账序/resume。
- `test_reflection_library.py`：confounded/NO_ENTRY/prefix-only/mode 隔离/消融。
- `test_evidence_guard.py`：source/artifact/library/cache/selector/reflection/egress 全路反例。
- `test_candidate_workspace.py`：隔离、artifact hash、evaluator 不可写、rollback handle。

### 13.5 W5/AKV/可靠性

- `test_profile_selection.py`：unknown→standard、四层 identity、平票/超时/缓存失效/分类成本。
- `test_budget_convergence.py`：软/硬阶段、denial、final reserve、incomplete。
- `test_output_compaction.py`：raw 恢复、内容类型、危险命令不 rewrite。
- `test_completion_review.py`（条件）：双账、剩余预算、最终 artifact。
- `test_cache_identity.py`：A/B/C/drop 时机/repos 时机/branch/unknown revision。
- `test_cache_policy.py`：trigger/selector/repos/原子 batch/证据保护/scheduled receipt。
- `test_cache_capability_unsupported.py`：默认无扩展、HTTP 200 不升级、无 stripped retry、fallback 独立账。
- `test_cache_usage.py`：nested usage、unknown 非 0、三类不相加、recovery 合法。
- `test_atomic_evo_targets.py`：唯一 temp/backup、并发、原子 rollback、首次创建、consumer reload。
- `test_recovery_journal.py`：多组件所有崩溃点、outbox、半提交启动恢复、并发候选。
- `test_shadow_sandbox_windows.py`：低权限 ACL、清凭证、Job Object 进程树、断网/broker、junction/reparse；条件不足必须 blocked。
- `test_evidence_integrity.py`：凭证脱敏失败、ref 替换/缺失/hash、保留期、无权限与越界。
- `test_metrics_migration.py`：旧 JSONL 只读、幂等、坏行、重复执行、未知字段不补 0。
- `test_candidate_state_machine.py`：非法迁移、no-change/no_update/unsupported 与恢复路径。
- `test_evaluate_candidate_cli.py`、`test_shadow_round_cli.py`：fake transport 端到端、产出/退出码、绝不 apply。
- `test_heldout_canary_protocol.py`：finalist 一次性 held-out、修改后重来、canary 阈值与缺 usage。
- `test_no_production_writes.py`：所有新测试不触生产 config/var/network。

每阶段命令使用 P0 已验证的项目虚拟环境；以下是**示例映射，执行时替换为本节实际存在的测试文件，不允许把 `<...>` 原样当命令**：

```bash
# P1：W1 六个测试文件 + 既有 client/stream/native/replay/credit 回归
.venv/Scripts/python.exe -B -m pytest tests/test_llm_usage.py tests/test_usage_pricing.py tests/test_task_metrics.py tests/test_task_exec_metrics.py tests/test_pair_identity.py tests/test_evidence_store.py -q -p no:cacheprovider
# P2：W2 固定协议、Pareto、pair、strict/resume/selector
.venv/Scripts/python.exe -B -m pytest tests/test_candidate_protocol.py tests/test_pareto_select.py tests/test_pair_evaluate.py tests/test_strict_independent_gate.py tests/test_evaluation_resume.py tests/test_artifact_selector.py -q -p no:cacheprovider
# P3：W3 五个诊断/历史/归因测试文件
.venv/Scripts/python.exe -B -m pytest tests/test_rollout_diagnostics.py tests/test_interface_mismatch.py tests/test_cache_diagnostics.py tests/test_history_retrieval.py tests/test_credit_evidence.py -q -p no:cacheprovider
# P4：W4 七个候选/证据/调度测试文件
.venv/Scripts/python.exe -B -m pytest tests/test_component_manifest.py tests/test_intent_candidates.py tests/test_probe_compose.py tests/test_improvement_schedule.py tests/test_reflection_library.py tests/test_evidence_guard.py tests/test_candidate_workspace.py -q -p no:cacheprovider
# P5/P6：画像、预算、cache、落地、CLI、held-out/canary 与写入边界
.venv/Scripts/python.exe -B -m pytest tests/test_profile_selection.py tests/test_budget_convergence.py tests/test_output_compaction.py tests/test_cache_identity.py tests/test_cache_policy.py tests/test_cache_capability_unsupported.py tests/test_cache_usage.py tests/test_atomic_evo_targets.py tests/test_recovery_journal.py tests/test_shadow_sandbox_windows.py tests/test_evidence_integrity.py tests/test_metrics_migration.py tests/test_candidate_state_machine.py tests/test_evaluate_candidate_cli.py tests/test_shadow_round_cli.py tests/test_heldout_canary_protocol.py tests/test_no_production_writes.py -q -p no:cacheprovider
# 每阶段定向过后，再执行全量与 gate；报告真实结果
.venv/Scripts/python.exe -B -m pytest tests -q -p no:cacheprovider
.venv/Scripts/python.exe -B scripts/gate.py --json
```

报告必须写实际 passed/failed/skipped/error、已知 flaky 重跑、gate 输出和未覆盖边界；不得以 collect/静态检查冒充运行。

---

## 14. 总体验收与完成定义

只有全部满足才可称“DWC pure 2.0 主线完成”：

- [ ] W1 全调用账、完整身份、成本/覆盖率真实接通。
- [ ] W2 base+固定评价+Pareto+严格独立验收可重放。
- [ ] W3 失败/浪费/TIMR/cache 诊断有事件证据与 unknown。
- [ ] W4 intent×scope、Probe/Compose/no-change、经验 NO_ENTRY 全部 shadow 运行。
- [ ] W5 画像/预算/cache unsupported shadow 有对照，不影响默认生产。
- [ ] 原始 base、current、父代、checkpoint 的保留语义测试通过。
- [ ] 全量测试与 gate 真实通过；原仓库零改动；新仓提交/推送读回一致。
- [ ] held-out、人工反例、备份/读回/consumer smoke/rollback/canary 实测。
- [ ] 报告区分 offline/shadow/production、论文数字/DWC 实测、已做/未做。

**AKV GPU serving、TIES/SFT、DPP、RTK、fresh review 不属于主线完成的默认必要条件；若未启用必须标“条件扩展未启用”，不能写成已实现。**

---

## 15. 当前冻结声明

截至本规格固化：

- 已完成四篇论文与对应代码的再次回查、165 项机制映射和 DWC 现状接缝审计。
- 本变更只修改开发计划与研究文档，**没有实现上述模块，没有修改运行行为，没有启动候选/调参/部署**。
- 下一步仍是等待用户明确解冻；解冻后严格从 P0→P1 开始，不并行跳过依赖。

### 论文与代码来源

- HarnessPro：<https://arxiv.org/abs/2610.26770v1> · <https://github.com/pzs19/HarnessPro>
- Harness²：<https://arxiv.org/abs/2610.14224v1> · <https://github.com/google-research/harness2>
- Cache Engineering：<https://arxiv.org/abs/2610.28577v1> · <https://github.com/thu-nics/AKV>
- CoEvo-RSI：<https://arxiv.org/abs/2610.25078v1> · <https://github.com/SuJQ0722/CoEvo-RSI>
