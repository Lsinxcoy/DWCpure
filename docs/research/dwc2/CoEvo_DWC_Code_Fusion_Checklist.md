# CoEvo-RSI → DWC pure 2.0：完整代码级融合清单

> 状态：**拟建设计，尚未实现**。本清单不改变 W1–W5、不新增 W6、不解冻。论文是 *When Harnesses Evolve, Which Models Should Follow?* v1；代码核验提交 `b9928a973af68781f0ea7fccfbb8a6ee7af0f3f1`；DWC 核验提交 `5769a125d1a370f9b3fc2c41d0d2fcbeef6d095e`。[1][2]
>
> 证据标记：`论文` = 论文声称；`CoEvo代码` = 本地源码事实；`DWC现状` = 当前源码事实；`拟建` = 建议写入总计划但当前不存在。

## 0. 核心裁定

CoEvo 对 DWC 的主要增量不是 SFT，而是：**把观测与晋级的对象从单独 harness 改为模型—harness pair；历史分数只在原 pair/协议下有效；兼容性缺失不可当 0；旧 incumbent、未适配 pair、适配后 pair 分开比较。**[1]

DWC 当前 `harness/loop.py` 以候选实现和 judge 分数选择，`llm/client.py` 有模型名、tool_calls、重试与流式路径，但没有完整 pair 身份、TIMR 或模型历史矩阵。因此先做 W1/W2/W3 的契约，再让 W4 生成受控联合候选；TIES/SFT 只保留条件性附录。

## 1. 可借鉴机制总表（32 项）

| # | 机制与代码证据 | DWC 落点（全部拟建） | 必须写的测试 |
|---|---|---|---|
| 1 | **Pair 是一等评价对象**：`round_runtime.evaluate` 将模型 hash、harness hash、split、环境、decoding 等合成 eval id。 | W1 `observability/pair_identity.py`；W2 `candidate_metrics.py` 增 `pair_id`。 | 改模型/harness/decoding/task set 任一字段，pair id 改变且旧缓存不命中。 |
| 2 | **完整身份而非模型别名**：源码把 weights、tokenizer、layout、环境包与执行配置纳入身份。 | `model_identity={provider,route,requested_model,reported_model,revision_status}`；远程未知 revision 明写 unknown，不伪造 hash。 | 同名远程路由、reported model 缺失、revision 不可见均不报错也不冒充固定权重。 |
| 3 | **完整 harness bundle hash**：CoEvo 评价 hash 包含动态引用模块与运行资产，语义 hash 仅用于去重。 | `harness_bundle_hash` 与 `semantic_change_hash` 分开；prompt、工具 schema、rendering、loop 控制参数均入 bundle 身份。 | 注释/报告是否纳入按 DWC 明确定义；动态 import、YAML/prompt 资产改变必须使评价身份改变。 |
| 4 | **缓存身份与完整任务集绑定**：评价必须覆盖冻结 task ids，防部分结果当完整结果。 | W2 评价缓存 manifest 增 `task_ids_digest, expected_task_count, observed_task_count, completion_status`。 | 缺一条、重复 id、顺序变化、部分恢复都不能标 full。 |
| 5 | **Brain/body mismatch 双向诊断**：harness 可能要求模型不会的行为，也可能遮蔽已有能力。 | W3 `problem_type` 下增加 `interface_mismatch / capability_underuse / harness_restriction / correctness / infrastructure`；后两者需独立证据。 | “协议正确但答错”不得归 interface；“没调用新工具”不得直接证明 capability_underuse。 |
| 6 | **TIMR 是 turn 级并集**：同一 turn 多违规只计一次，分母为 observed model turns。 | W3 `observability/interface_mismatch.py`，输出 `interface_mismatch_turn_count/observed_model_turn_count/rate`。 | 同 turn unknown_tool+schema error 计数 1；0 turns 时 rate=None 而非 0。 |
| 7 | **TIMR 分类维度**：protocol、argument、final_format 分开；task-level union 仅辅助。 | `mismatch_turn_categories` 与 `interface_mismatch_task_rate` 分字段，不混为一个 TIMR。 | 分类并集、task 去重、final 错误归 turn 的确定测试。 |
| 8 | **观测发生在修复前**：`ObservedModel` 保留 provider/client 原始接口与 effective response。 | 在 `llm/client.py` 的完整、tool-call、流式、fallback、retry 路径增 `interface_trace`；记录 `response_stage=provider/client`。 | transport 修复后仍能看见原始错误；不得把 client 自动修复算成模型零错误。 |
| 9 | **修复与恢复不是同一概念**：transport repair 是客户端修补；interface recovery 是后续成功完成。 | `transport_repaired_response_count` 与 `recovered_after_mismatch` 独立；恢复不能抹掉原 TIMR。 | 修复后任务失败、未修复后恢复、最终格式仍错三例。 |
| 10 | **工具名/参数/schema 覆盖率分开**：CoEvo 分别统计 tool_names、argument_schemas、tool_returns checked/total。 | `coverage.{tool_names,argument_schemas,tool_returns,raw_trace_tasks,complete_interface_turns}` 每项 `{checked,total,rate,reason}`。 | 无 schema、远程 `$ref` 不可解析、tool return 契约未知均降低相应 coverage。 |
| 11 | **None 表示未观测**：无返回契约、无 finished/final-format 语义时 CoEvo 返回 None。 | 禁止默认 `finished=True/final_format_error=False/tool_return_error=0`；增加 `observability_status=observed/partial/unavailable`。 | 缺 parser、缺 trace、空请求、domain contract 不支持均输出 unknown。 |
| 12 | **TIMR 不替代正确性**：Model-only 消融近零 TIMR 仍任务能力受限；代码也只让它 tie-break。 | W2 明确 TIMR 不进 PR 的替代项、不补偿质量回退；W3 才作诊断。 | 低 TIMR+低 PR 候选仍被基线门淘汰；高 TIMR+基础设施错误分账。 |
| 13 | **TIMR 比较协议**：仅同 task set、metric version、完整 coverage 时比较。 | `comparable={status,reasons[]}`；比较函数返回 unknown，不擅自按 0/∞ 排序。 | coverage .99、不同 task digest、不同 metric version 均不可比。 |
| 14 | **质量先于 TIMR/成本，容差不作并列带**：CoEvo ranking 先原始质量向量，再 TIMR，再 token。 | 只借“诊断不能覆盖质量门”；DWC 主选择仍是 W2 PR 保底+Pareto，不照抄 lexicographic。 | 质量差但 TIMR 低/便宜者不能晋级；容差内较小真实 PR 不被诊断分反转。 |
| 15 | **共享 archive 快照**：冻结当轮历史，archive 存 models、harnesses、rounds、incumbent。 | W2 `var/evolution_archive.jsonl`（append-only）+ `archive_snapshot_id`；记录 pair 评价和 lineage，不另造生产注册表。 | 中断恢复仍使用原 snapshot；新历史不会 retroactively 改当轮检索。 |
| 16 | **历史卡保存条件性证据**：源码、model_ids、scores、accepted/status、adopted/rejected designs、dependencies。 | `history_card={harness_id,pair_refs,protocol_ref,scores,diagnostics_summary,designs,evidence_refs}`；旧分标 `historical_reference_only`。 | 不同 pair 的分不得填入当前 candidate measured_scores；缺证据字段保留 null。 |
| 17 | **确定性失败相似度检索**：TF-IDF 风格、固定 tie-break，不用原始题面/gold 作特征。 | W3 `diagnostics/history_retrieval.py`，仅用 domain contract、failure outcome、脱敏诊断；输出 ranking receipt。 | 输入顺序不变性、空历史、重复 id、零向量、无 gold/question 字段的泄漏测试。 |
| 18 | **recency 是可选检索策略而非真理**：完整方法允许旧设计恢复。 | `retrieval_strategy=failure_similarity/recent`，默认待 shadow 校准；禁止 latest-only 硬编码。 | 旧 harness 在相关失败下能被选中；最近但无关者不必优先。 |
| 19 | **Curator/Editor 分工**：Curator 每轮共享 context，Editor 各拿独立 brief 并实际编辑。 | W4 复用现有 evolver，不新增平行 agent 框架；拟建 `candidate_context` 与 `candidate_brief` 纯数据契约。 | brief 数量、唯一 hypothesis、未知 ref 拒绝、每候选只看到自己的 brief。 |
| 20 | **Context packet 结构**：target(current_failures/design_requirements/evidence_limits)、references、avoid、constraints。 | 扩展 W4 计划字段：`evidence_limits[]`、`reuse/applicability/dependencies/code_refs`、`avoid{item,basis,condition_if_revisited}`。 | 缺 evidence_limits、永久 ban、无证据引用、引用不存在均 schema 拒绝。 |
| 21 | **Brief 是可验收假设**：hypothesis/reference_ids/evidence_refs/constraints/expected_effect/acceptance_checks。 | 与已有 `intent/diagnosis_refs/validation_protocol` 合并，避免两套候选计划。 | expected 与 measured 不混写；acceptance_checks 不得改 held-out/evaluator。 |
| 22 | **引用不等于采用**：Editor lineage 另记 adopted/rejected designs，控制器校验 references 属于 brief。 | `lineage={reference_ids,adopted_designs,rejected_designs,dependencies}`；仅在 diff 有证据时记 adopted。 | 引用了旧卡但无对应改动，不得声称 adopted；越界 reference 拒绝。 |
| 23 | **批次失败摘要反馈下一批**：按重复拒绝原因排序，区分 harness/model/external。 | W3/W4 `batch_attribution` 作为可选摘要，原始结构化证据为真源；文本摘要不得成为唯一依据。 | 无候选、全失败、共享修改、外部错误分类；摘要缺数字不能伪造 delta。 |
| 24 | **失败和无效候选仍耗预算**：生成 slot 先持久化，重复/invalid 占预算。 | W4 `candidate_attempt={slot,status,valid,reason,cost_refs}`，预算含生成、评价、诊断。 | duplicate/invalid 不免费消失；中断后 slot 不漂移、不重复计费。 |
| 25 | **模型历史独立搜索**：对新 harness 可重评旧 checkpoint，而非默认最新。 | 当前映射为 `model_route` 历史重评：每个入选新 harness 对 allowed routes 做同题矩阵；latest 只是一个候选。 | 旧 route 在新 harness 胜出可被选择；未评 route 不得凭旧分 select。 |
| 26 | **动作/评价/合并预算**：agent 只能选择已评价、可评价、admissible pair，预算耗尽显式 fallback。 | W2/W4 增 `search_budget={max_actions,max_pair_evaluations}`、`selection_source=agent/rule/budget_fallback`。 | 超预算、非法 route、未测 select 均拒绝；fallback 有 reason，不崩溃也不假装 agent 选中。 |
| 27 | **内容寻址评价与 lineage 恢复**：journal 冻 identity，已完成昂贵操作复用。 | W1/W2 所有 measurement/evaluation/search receipt 采用 idempotency key；禁止仅凭文件存在判完成。 | 部分文件、manifest 不符、代码/数据改变、重复执行均正确拒绝或复用。 |
| 28 | **未适配与适配 pair 分开**：`pre`/`post` phase；训练后同 harness 重评。 | 条件性扩展 `adaptation_phase=unadapted/adapted`；当前远程模型只用 unadapted，不虚构 post。 | pre/post 同 pair 身份除 model 外一致；post 不可比时 delta=None。 |
| 29 | **SFT 前后贡献与 latest 对照**：保存 pre/post quality/TIMR deltas，另比较 selected vs latest trained。 | `contribution_report={incumbent,unadapted,adapted,latest_baseline,comparability,deltas}`。 | harness 改动贡献、适配贡献、合计贡献可区分；缺 latest 或 coverage 不全时未知。 |
| 30 | **Incumbent 保底与 no_update**：没有合格 pair 时 winner 仍为 incumbent，训练失败可保留 pre。 | W2 终池始终含 incumbent，输出 `no_update/no_passing_child/no_admissible_pair`；保留多 Pareto 运行点而非只留 winner。 | 全子代更差、训练失败、空池、评价失败都不删除 incumbent。 |
| 31 | **阶段化成本账**：curator/editor/evaluation/rejection_sampling/SFT/model_load/model_residency/training_path 分开；重叠时间不可直接相加。 | W1 增 `cost_stage`、`parent_stage_id`、`wall_time_semantics=summed/overlapping/end_to_end`、`cache_hit/new_rollouts`。 | cache hit 无新 rollout；父/子阶段时间不相加成总时长；所有失败尝试仍入账。 |
| 32 | **训练与推理成本分账**：论文分别报告进化/训练与 full-eval inference，不以小模型部署价代替全部成本。 | `cost_scope=generation/evaluation/diagnosis/adaptation/serving_residency/inference`；训练条件未启用时为 not_applicable，不是 0。 | 报告不能用 inference 单价声称总进化成本；GPU 小时、API estimate、token 不混加。 |

## 2. 建议写入 DWC 的具体文件/字段（均为拟建）

### 2.1 W1：`src/dwc/observability/pair_identity.py` + `task_metrics.py`

```text
pair_identity:
  schema_version
  model: {provider, route, requested_model, reported_model, revision, revision_status}
  harness: {bundle_hash, prompt_version, tool_schema_version, rendering_version, control_config_hash}
  cache_policy_version
  evaluation: {protocol_id, evaluator_id, evaluator_version, task_set_id, task_set_sha256,
               decoding_config_hash, rollout_rule_version}
  environment_version
pair_id = canonical_hash(pair_identity)   # 任一语义字段 unknown 时不得当成固定已知值
```

`task_metrics` 增加 `pair_id / measurement_id / attempt_id / parent_attempt_id / cost_stage / parent_stage_id / cache_hit / new_rollouts / cost_scope / wall_time_semantics`。远程 `revision_status=not_disclosed` 时结果只绑定该次路由观测，不声称跨时间同权重。

### 2.2 W3：`src/dwc/observability/interface_trace.py` + `interface_mismatch.py`

```text
interface_trace:
  trace_version / request_index / response_stage / offered_tools
  raw_response / effective_response / transport_repaired / error_type / termination
interface_mismatch:
  metric_version / pair_id / task_set_sha256
  interface_mismatch_turn_count / observed_model_turn_count / rate
  counts{unknown_tool,invalid_json,argument_schema,response_protocol,final_format}
  mismatch_turn_indexes[] / mismatch_turn_categories
  transport_repaired_response_count / recovered_after_mismatch / unfinished
  coverage{raw_trace_tasks,tool_names,argument_schemas,tool_returns,complete_interface_turns}
  observability_status / unknowns[] / evidence_refs[]
```

`llm/client.py` 只负责事实捕获，不在 client 内计算质量或做晋级。流式聚合必须保留最终 tool-call 结构；retry 是不同 attempt，不能把第一次接口错误从台账删除。

### 2.3 W2：`src/dwc/harness/pair_evaluate.py` + `candidate_metrics.py`

```text
pair_evaluation:
  pair_id / eval_id / phase=unadapted|adapted
  split / task_scope / expected_task_count / observed_task_count / completion_status
  scores / token_cost / usage_status / infrastructure_status
  mismatch_ref / artifact_refs / comparability
```

规则：历史 pair 分数永不直接迁移到当前 pair；只有完整 identity 命中才可复用测量。DWC 仍执行 PR 基线门→性能/成本 Pareto；TIMR 仅诊断或严格并列辅助，且不替代小样本波动处理。

### 2.4 W3/W4：`src/dwc/diagnostics/history_retrieval.py` + archive/candidate 契约

建议 `var/evolution_archive.jsonl` 只存脱敏卡与证据引用，不把私有 val/test 原轨迹广播给生成者。`archive_snapshot_id` 固定当轮输入。候选计划沿用 W4 的 `parent_id/intent/diagnosis_refs/...`，新增：

```text
model_route_change / harness_change / changed_axes[]
archive_snapshot_id / reference_ids / adopted_designs / rejected_designs / dependencies
evidence_limits / avoid[] / acceptance_checks
selection_source / search_budget / candidate_attempt_status
```

`changed_axes` 用来防止同轮模型与 harness 同时改却声称单点因果。联合候选允许，但贡献报告必须配 `H_old+M_old`、`H_new+M_old`；远程路由变更另配 `H_old+M_new`，复杂任务成本过高时明确标 `unmeasured`，不得写“已解耦”。

### 2.5 W2/W4：incumbent 晋级与远程路由

晋级输出建议：

```text
decision=no_update|untrained_pair|adapted_pair   # adapted 仅条件扩展
winner_pair_id / incumbent_pair_id / reason / admission_report
contribution_report_ref / rollback_pair_id / evaluation_protocol_id
```

不能照抄 CoEvo `finalize` 的自动发布：DWC 仍需 held-out、人类批准、备份读回台账。远程模型选择就是 `model_route` 候选，不是 checkpoint；provider 静默换模型属于 identity 风险，不可当可控 SFT。

## 3. TIES/checkpoint 与 SFT：条件性设计，不进入当前实现主线

**可留作未来机制**：共同 base、architecture/tokenizer/layout 兼容检查；recipe 内容寻址；合并后必须当前 harness 重评；rejection sampling 仅用所选 pair 自己的 train 轨迹；pre/post/incumbent 同池；训练失败保留 pre。[2]

**当前不能照搬**：DWC 使用远程模型时无 dense weights、共同初始化证明、tokenizer/layout 控制权、verifier 训练数据治理和 GPU 训练预算。不得将 `model_route` 重命名成 `effective_weights_hash`，不得将 ensemble/router 说成 TIES，不得把历史成功轨迹默认当可训练数据。未来启用前另需模型安全、数据许可、泄漏、算力和回滚评审。

SFT 贡献报告至少包括：所选未训练 pair 的验证证据、训练数据来源与 hash、采样 attempts/accepted、adapted pair 同协议重评、pre−post delta、相对 incumbent 的总 delta、与 latest baseline 的对照、训练/采样/评价成本。缺任一可比条件就 unknown。

## 4. 不能照搬清单（融合计划应明确禁止）

1. **quality-first lexicographic 替换 Pareto**：CoEvo `rank_pairs` 是质量→TIMR→token；DWC W2 是性能保底+性能/成本双目标。
2. **tolerance-only admission 冒充提升**：CoEvo Who&When prefilter 可接受“不低于容忍区间”；DWC 还需非支配/部署价值，且基线性能门优先。
3. **TIMR 当综合质量或 brain/body 全部测量**：低 TIMR 不代表正确，也测不出未利用模型强项。
4. **coverage 缺失填 0，usage 缺失填免费**：两者都是 unknown；是否允许排序按 DWC 的保守规则，不得暗中修复数据。
5. **旧 archive 分跨 pair 比较**：旧分只能检索/提假设，当前选择必须重评。
6. **latest-only、固定 top-K、K=8、density=.2、两轮训练等超参数**：全是待校准实验设置，不是 DWC 默认值。
7. **Editor 自由改代码/自动部署**：DWC 白名单、隔离、独立验收、人类主权不可被 CoEvo `finalize` 覆盖。
8. **CoEvo 的 fcntl/Landlock/Linux 依赖**：当前 Windows 不可直接复用；应使用现有持久化/隔离能力，测试不得把 POSIX skip 写成通过。
9. **论文 22×/38× 成本外推**：依赖 OpenRouter 定价、垂直 benchmark 与 full-eval 口径，不是 DWC 实测。[1]
10. **将 remote route 历史当 checkpoint lineage**：provider 内部权重不可见，必须标 not_disclosed，并防路由漂移。
11. **文本 prompt 约束代替结构化校验**：gold 禁止、ref 白名单、预算、selection admissibility 都要控制器执行。
12. **把 archive 文本摘要当真值**：检索/摘要是生成辅助；结构化原始测量和 evaluator 才是选择依据。

## 5. 总计划最小增补顺序与验收

1. **W1 先加 pair identity、原始 interface trace、cost_stage**：只观测，不生成联合候选。
2. **W2 加 pair evaluation manifest、完整任务集校验、incumbent/no_update**：同协议离线重放。
3. **W3 加 TIMR/coverage/comparability、失败相似历史检索**：先回放，低 TIMR/高错误等反例必须过。
4. **W4 才允许 `model_route×harness` 联合 shadow 候选**：预算和 changed_axes 落盘，分别验收贡献。
5. **W5 后续 shadow 路由**：仅用当前任务可观察特征与已验证兼容矩阵，不自动生产切换。
6. **TIES/SFT 保持条件性附录**：不新增硬依赖，不进入默认 gate。

端到端最小夹具应覆盖：`H0/M0` incumbent、`H1/M0` 仅 harness、`H1/M_old_route` 历史路由、`H0/M_new_route` 仅模型；同题同协议下验证父代保留、Pareto、不可比 TIMR、usage unknown、联合改动未解耦、no_update 回滚。之后才做真实 API 小样本 shadow，并明确远程 revision 不可见造成的限制。

## Sources

[1] https://arxiv.org/html/2610.25078v1 — 方法、TIMR、消融与成本口径。
[2] https://github.com/SuJQ0722/CoEvo-RSI — 本清单所列 `src/diagnostics/mismatch.py`、`src/meta_evolver/{round_runtime,lineage,model_inheritance,inheritance,context,merging,weights,costs}.py`、`src/training/*` 的本地提交级代码核验。
