# HarnessPro → DWC pure 2.0 代码级融合清单（补充/纠偏）

> 审计日期：2026-10-25。对象：论文 arXiv:2610.26770v1 全文；公开仓库提交 `8ae622eb4a4923dbb4b515be7ded614f88fd4f38`；DWC `Z:\DWC pure` 提交 `5769a125d1a370f9b3fc2c41d0d2fcbeef6d095e`。只读研究，未改 DWC/HarnessPro 的源码、配置或测试。
>
> 证据标签：**[P] 论文声称**、**[C] 公开代码事实**、**[D] DWC 当前事实**、**[R] 拟建设计**。所有 `[R]` 文件、函数和字段均尚未存在；不得写成当前能力。

## 0. 对既有报告与计划的裁决

1. 原报告主线“真实测量 → 固定评价/基线/Pareto → 多 rollout 失败与浪费诊断 → 三意图 → 运行时”正确，保留。最重要的新增不是更多提示词，而是公开 runner 已实现的**评价有效性、身份/可恢复执行、辅助调用成本、失败重试隔离**。[C][R]
2. **论文方法 ≠ 发布代码**。发布物没有 analyzer/planner/editor/test-synthesizer 的进化驱动，没有固定合成测试生成器，也没有 Eq.7–9 的基线过滤、Pareto、归一化加权平方距离实现；`src/rho/protocols.py` 中的 `Diagnosis`/`OptimizeStrategy` 只是协议类型，不能当作论文实现。九套 harness、policy、hooks、runner 与评测适配器才是可直接核验的代码。[P][C]
3. **五档不是所有产物的共同运行协议**。TB2/SWE 的若干 policy 配 `compact/lean/standard/deep/research`，ProgramBench 有固定单档；有些模式无 classifier，规则为空时默认档生效。`fresh_review`、`adjuster`、多样本和跨 effort 分歧处理虽在通用运行代码中支持，但九份当前 policy 并未全部启用，不能称为九套产物共同行为。[C]
4. `harnesses/.../policy.json` 是该产物运行真值；rubric 是自然语言选择依据，不是阈值真值。旧报告所指 medium rubric 的“38”与 policy 的“44”不一致属实。转移时只借**机器校验、默认/回退、审计**，不借数字。[C]
5. CoP 在论文 Table 3 为“总执行成本/成功任务数”；`C` 则是**每任务平均成本，失败任务也在分母中**。二者不可混用；0 成功时 CoP 未定义。公开 `qualification.py` 用 `observed_cost/passed`，0 成功返回 `None`，与此一致；但它不是 Pareto 实现。[P][C]
6. DWC 当前 `auto_apply: true` 是现有行为事实（`config/evolution.yaml`），不代表新 W4 候选可沿用自动落地。新候选必须独立 `shadow` 命名空间、批准门和回滚，不能借旧开关绕过 2.0 约束。[D][R]
7. 本地复跑 `.venv/Scripts/python.exe -B -m unittest discover -s tests -v`：9 项，3 通过、6 error，主要因 Windows 无 `fcntl`；与旧报告一致，不构成 Linux 功能证伪，也没有复跑论文 benchmark。[实测]

## 1. 全部 36 项机制清单

“拟建文件”是建议落点，不是要求新增平行系统。测试均加入现有 `tests/`，实施后还须跑全量测试与 `gate.py`。

| ID | 可借鉴机制与证据 | DWC 文件级接口/字段（拟建） | 最小测试与不可照搬边界 |
|---|---|---|---|
| M01 | **usage 原子记录**：[C] `observability.extract_usage` 汇总 `turn.completed`，区分 input/cached/cache-write/output；[D] `llm/client.py` 成功、tool-call、stream 均未保留 usage。 | 改 `src/dwc/llm/client.py` 的 `LLMResult.meta`；新增 `observability/usage_events.py:UsageEvent`。字段 `call_id,parent_call_id,task_id,term_id,candidate_id,rollout_id,attempt_id,call_role,model_actual,endpoint_class,usage_raw,usage_status,provider_trace_id,observed_at`。 | 非流式/tool-call/SSE 末帧/重试/流式回退均有覆盖；同一 logical request 不双计。不得用 `n_calls` 推 token；不把缓存输入再算进 uncached。 |
| M02 | **完整成本而非部分成本冒充总数**：[C] `trajectory_cost_summary` 只有全轨迹有 usage 且有价格才给正式总额，另列 observed lower bound。 | `task_metrics.py` 的 `usage_complete,pricing_complete,estimated_cost,observed_cost_lower_bound,missing_usage_call_ids,unpriced_call_ids`。 | 一次缺 usage/未知模型价 ⇒ 正式 `C/CoP=None` 或 `indeterminate`，下界另报；禁止 0 代替。不要照搬 `usage_summary` 会产生部分美元总额的展示方式做裁决。 |
| M03 | **按实际路由模型计价**：[C] `extract_usage_by_model`、`trajectory_estimated_cost` 分组，混合模型任一未定价则整体成本未知。 | 每条 UsageEvent 带 `requested_model,actual_model,pricing_version,pricing_source,pricing_as_of,rates`；聚合 `by_model/by_role`。 | 多模型混合、fallback 到不同模型、同名别名、未知价格；不按 self._model 猜实际服务模型。论文模型价格表不是 DWC 配置。 |
| M04 | **cached/uncached/cache-write 分拆**：[C] `pricing.py` 明确计算并夹取边界。 | `usage_pricing.py:normalize_usage()` 输出 `regular_uncached,cache_write,cached,output,reasoning`。 | cached>input、cache-write>uncached、缺失字段、reasoning 是否已含 output 的 provider adapter 测试；不能全局假设 reasoning 独立收费。 |
| M05 | **辅助调用也归任务账**：[C] classifier/review 轨迹按 kind/stage 汇总；[D] memory expansion、judge/QA/revision/task_exec 分散调用。 | `call_role ∈ solver,judge,retry,fallback,expansion,diagnosis,planner,editor,classifier,review,test_synthesis`；`cost_scope ∈ solve_execution,evolution_search,evaluation,deployment`；所有 LLMClient 调用由 context 注入归属。 | 每个生产调用点有归属测试；review/classifier 的成本计入任务执行，analyzer/planner/editor 计入搜索预算，不能“免费”。 |
| M06 | **中断调用 usage 对账**：[C] runner `_reconcile_transport_usage` 将 provider 总量减轨迹已见量，只补差；小于轨迹时留异常不篡改。 | `usage_reconcile.py:reconcile(provider,observed)`，字段 `reconciliation_status,delta_event_ref,conflict_details`。 | 中断、迟到 usage、完全匹配、provider 小于轨迹、重复对账；不得重复累计或覆盖原始事件。 |
| M07 | **物理尝试与逻辑 rollout 分离**：[C] TB2/ProgramBench 保留 attempts、选定 formal attempt、排除 infra；[D] 当前三态不足。 | `attempt_id,rollout_id,attempt_class ∈ model_result,invalid_candidate,infrastructure,evaluation_error`；`selected_formal,formal_exclusion_reason,cost_inclusion ∈ formal,excluded_infra,search`；`measurement_status` 不压缩所有情况。 | 超时是模型耗尽预算还是 provider 故障要按证据分；失败任务仍计执行成本。基础设施重试不得变成任抽到最好结果，也不得全部丢弃已发生费用。 |
| M08 | **pass rate 与分数语义分 benchmark**：[P] TB2/SWE 为全测试通过，ProgramBench 是每题测试分数的宏平均；[C] ProgramBench `parse_evaluation` 同分支测试身份对账。 | `outcome_kind ∈ binary_pass,macro_test_score`；`passed,score,resolved_tests,total_tests,pass_rate_completed,pass_rate_all_requested`；Pareto 单一 protocol 内禁止混指标。 | 部分通过、0 测试、not_run、重复 test id、缺/多 branch、数量相同但身份不同；不把宏平均改名 binary pass。 |
| M09 | **C 与 CoP 并列**：[P] 平均任务成本含失败，CoP 分母是成功数。 | `candidate_metrics.py:summarize()` 输出 `mean_cost_per_task,cost_of_pass,completed_tasks,successful_tasks,requested_tasks`；0 成功为 `None + reason=zero_successes`。 | 含失败昂贵任务、0 成功、缺正式成本时不得给可比较 CoP；搜索/训练/部署三种 cost scope 分开报告。 |
| M10 | **延迟分层**：[P] 求解 wall time 不含 grading，L 仅辅助；[C] ProgramBench 区分环境/setup/solver/verifier/provider wait。 | `solver_wall_ms,grader_wall_ms,environment_setup_ms,transport_wait_ms,pacer_wait_ms,retry_backoff_ms,effective_agent_ms`；缺段为 `None`。 | 不把并发总运行时间当每题延迟；不把 grader 偷算进论文口径；不得无证据从 wall 减等待制造“有效时间”。 |
| M11 | **固定评价协议身份**：[P] train/val/test 隔离、test 最终一次、生成测试固定；[C] run config 保存 hashes 和 resume identity。 | `config/validation_protocol.json`：`protocol_id,task_manifest_sha256,train_ids,val_ids,heldout_ids,evaluator_id,evaluator_version,evaluator_artifact_sha256,synth_test_sha256_by_task,rollouts_train,rollouts_val,seed_policy,generation_config,environment_profile,created_before_candidate_id`。 | 候选后改任务/测试/模型/decoding/环境则 protocol_id 必须变化，旧分数不混；heldout 出现在 planner 输入即拒绝。G=3、10-task 是论文实验设置，不是默认。 |
| M12 | **合成测试构建/可靠性**：[P] 仅由任务描述+h0 初始轨迹生成一次；直接 LLM judge 初步失败召回 41.7%→83.3%不是无漏报证明。 | `evaluation/synth_tests.py`（条件扩展）：`source_task_hash,seed_harness_id,seed_trajectory_ref,generator_model,prompt_hash,test_artifact_hash,known_counterexamples,uncovered_behaviors,validation_status`；planner 只拿 task/test refs，不拿 val/test。 | 已知失败反例、测试自验证、空测试、同盲点、过拟合、候选修改测试、独立 held-out；合成通过不等于真实完成。公开仓库没有生成器，不能声称照抄实现。 |
| M13 | **结果集完整性先于裁决**：[C] `qualification.py` 的 pass/fail/indeterminate；ProgramBench 缺测试/not_run/system_error 均不形成 model result。 | `evaluation/completeness.py:qualify_run()` 输出 `status,result_set_complete,expected_task_ids,completed_task_ids,pending_task_ids,infra_failed_ids,unexpected_task_ids`。 | 空结果、重复任务、pending、infra、意外任务、0 测试；缺数据的候选不得因 pass=0/cost=0 被支配或被选中。 |
| M14 | **评价器产物与依赖锁定**：[C] SWE evaluator 固定官方 commit，ProgramBench submission/evaluator manifest 校验。 | `evaluator_bundle {source_uri,commit,artifact_sha256,dependency_manifest_sha256,container_digest,command_contract}`；`candidate_artifact_sha256` 评分前后不变。 | evaluator 改动、评分期间提交物变化、环境 fallback 版本、缓存陈旧；不能把官方测试/隐藏答案喂候选。 |
| M15 | **基线/no-change 真正在最终池**：[P] 父子同池、PR≥PR(h0)；但论文 Eq.7 并未保证 h0 永不因被支配而删除。 | `pareto_select.py:select(pool,baseline_id,protocol_id)`；输入无有效 baseline 即 `indeterminate`；`retained_ids` 强制包含 baseline，另记 `pareto_front_ids,filtered_below_floor,dominated_by`。 | 全部子代更差、baseline 被更优支配、baseline infra、无候选；不得只“父代参加”却在最后 selector 丢 no-change。 |
| M16 | **Pareto 过滤**：[P] 两目标不更差且至少一个严格更好。 | 纯函数 `dominates(a,b)`，目标 `(-performance,cost)`，只接收同 protocol 且正式测量完整的候选。 | 相等不支配、单维改善、未知成本、NaN、重复候选；微小单次差异不能直接当稳定能力。 |
| M17 | **归一化加权平方距离**：[P] Eq.8–9，极值来自当前过滤集，lite/medium/heavy `(1,2)/(1,1)/(2,1)`。 | `normalized_deviations(),representative_points(weights,tie_break='candidate_id')`；保存 `normalization_set_id,p_min/max,c_min/max,d_perf,d_cost,J_by_mode`。 | max=min 时该维偏差显式设 0（并记录 `degenerate_dimension`）、同分确定 tie、同一候选可对应多 mode、非支配点不足 3；权重是待校准初值。 |
| M18 | **每轮候选上限与历史比较边界**：[P] 每轮最多三个代表继续；不是完整历史全保留。 | `epoch_id,parent_ids,active_pool_ids,frontier_snapshot_ref,search_budget_spent`；跨 epoch 比较必须注明 normalization set 改变。 | 不把某轮 J 跨轮直接比；不能宣称保留全 Pareto 历史；预算不足允许 no-change 而非硬凑候选。 |
| M19 | **多 rollout 对齐**：[P] 每候选每训练任务 G=3，联合看轨迹+Pass/cost/latency/token/tool；[D] `evo_proposals` 仅签名簇。 | `diagnosis/rollout_groups.py:group(task_id,candidate_id,protocol_id)`；`rollout_count,pass_pattern,cost_by_rollout,outcome_pattern`；`frequency=n_observed/n_rollouts`。 | 稳定失败、 flaky、稳定成功、成功但浪费、infra-only；不同 harness/config 不得混组；G=3 不是可靠性充分保证。 |
| M20 | **浪费诊断以事件证据为准**：[P] analyzer 查无产探索/冗余计算，输出影响、来源、轨迹路径和事件范围。 | `diagnosis/waste.py` 输出 `problem_type,first_effective_event_ref,redundant_event_ranges,repeated_action_keys,state_change_refs,evidence_excerpt_refs,cost_impact_estimated,confidence,unknowns`。 | 重复命令但状态已变、无新信息读取、重复验证、长输出、恢复/收尾、首有效步；不把重复文本自动判浪费，不凭摘要虚构成本。 |
| M21 | **长诊断压缩而不丢追溯**：[P] 汇总超 64K tokens 才摘要，planner 默认不读全轨迹、可按路径回查。 | `diagnosis_bundle {raw_refs,summary_ref,summary_trigger,summary_input_hash,event_index}`；`planner_input` 只带 bundle+metrics+diff。 | 摘要后任意诊断仍能定位原始事件；缺 usage 降级 unknown；64K 不是 DWC 阈值。 |
| M22 | **三意图显式生成**：[P] 每父 cost/balanced/performance 三计划，balanced 不是两方案平均。 | `evolution/intents.py:plan(parent,diagnoses,peer_evidence,intent)`；字段 `intent,diagnosis_refs,modified_component,change_description,expected_effects,regression_risks,preserved_behavior,predicted_vs_measured_status`。 | 同改动换名不算三候选；performance 不能全局加预算；cost 不能削必要验证；预测与实测分栏。 |
| M23 | **peer diff + 指标证据**：[P] planner 看其他候选的代码 diff、诊断和指标。 | `peer_evidence[] {peer_id,diff_ref,diff_sha256,diagnosis_refs,metrics_ref,comparison_scope,confounders}`。 | 同任务/protocol 的关联才可引用；多组件同时变不得声称单点因果；不能跨模型/harness 直接搬历史分数。 |
| M24 | **独立 workspace、Git commit、白名单落地**：[P] editor 独立 workspace+commit；[D] `evo_targets.apply` 已有白名单/备份/读回/回滚。 | `evolution/candidate_workspace.py` 产出 `candidate_id,parent_id,workspace_ref,commit_id,artifact_manifest,rollback_handle`；shadow 产物不直接用生产 `config/`；最终只经 `evo_targets`。 | 候选不可改 evaluator/heldout/gates；不能给全仓自动编辑权限；workspace 删除前保留 diff/raw evidence。 |
| M25 | **聚焦、可泛化、无改动合法**：[P] planner 指令要求 focused/generalizable、不能放弃难任务；不需要机械产生优化。 | `plan_status ∈ proposed,no_evidence,no_change,unsupported`；`generalization_scope,task_specific_identifiers,overhead_estimate`；无证据走 no-change。 | 空诊断不造提案；personal assistant 不能写 task-id 专用规则；有证据不足必须停止，不强制三份。 |
| M26 | **画像只看公开任务特征**：[C] classifier 禁工具/历史结果，按 rubric gates；[D] 当前只有 reasoning 可配和固定执行上限。 | `runtime/profile_select.py`：`public_task_features,profile_requested,profile_effective,selection_source,confidence,rationale,fallback_reason,classifier_call_id`；先规则 shadow，后模型评审。 | 历史成绩/隐藏测试/任务指纹不得进输入；未知默认 standard；五档及 0.9 阈值不照搬，分类器成本必须抵消节省才保留。 |
| M27 | **画像请求≠实际执行**：[C] confidence override、cross-effort disagreement、adjuster 都可能改变 effective profile；[D] 需要避免只记分类名。 | `requested_profile,classified_profile,effective_profile,execution_adjustment,override_rule,adjuster_action,vote_counts,actual_model,actual_reasoning_effort`；候选身份含 effective config hash。 | 只记录“选了 lean”而实际 standard 的用例；override 后候选不可冒用原分数。通用 adjuster/多票不是当前九产物共有证据，不优先引入。 |
| M28 | **保守共识/失败回退**：[C] `_classifier_consensus` plurality、无多数回默认；`fallback_selection` 保留原因。 | `classifier_samples_requested/observed,vote_counts,consensus_status,invalid_attempts,fallback_reason`；缓存键含 policy+rubric+模型+prompt。 | 平票、schema 越界、超时、部分样本、缓存后 rubric 改变；多样本会增费，不能作为默认必做项。 |
| M29 | **三阶段预算收敛**：[C] hook economy 提醒合并/去重，strict 停止广泛探索但具体失败仍修，finalize 后 deny；policy 校验阈值严格递增。 | `runtime/budget_controller.py`：`economy_after,converge_after,hard_tool_cap,reminder_every,final_reserved_calls,stage,deny_count,completion_status`；软提示和硬拒绝分开。 | 阈值排序、硬 cap、具体失败/变异交付物不能提前 final、超限 best-effort 且 incomplete；14/26/44 不搬；不能绕开 DWC ask/权限门。 |
| M30 | **预算用尽后停止 denial 循环**：[C] hook 硬拒，Claude adapter 可将重复 budget denial 转 session stop，保留产物评分。 | `budget_exhausted,denial_count,stop_reason,best_effort_final,artifacts_preserved`；接到 `task_exec` 的 repeat/final 机制而非新进程协议。 | 第一次 deny、重复 deny、非预算 deny 不得停、最终未完成如实；不能只发提示不执行上限。 |
| M31 | **可恢复输出压缩**：[C] 连续重复行折叠+head/tail，原文写 `.rho_runtime/raw`，提示定点读取；adapter 保留结构化图片。 | `runtime/output_compaction.py`：`raw_ref,raw_sha256,original_chars,compacted_chars,omitted_range,content_kind,compaction_version`；保存于任务工作区外受控 evidence 区。 | 恢复省略中段、重复行、二进制/图片/密钥隐私、raw 不可写时 fail-open 要标未压缩；不能压掉验证证据或让 agent 重跑整条命令。 |
| M32 | **RTK 只能条件性、白名单重写**：[C] TB2 hook 排除 heredoc/重定向/命令替换、`rg --files`、find 危险语义，只有指定命令族；ProgramBench RTK=false。 | 若未来实验，`tools/output_rewriter.py`：`rewrite_allowed,reason,command_before_hash,command_after,rtk_version,rewrite_status`；原生 Bash 协议不能搬。 | 每个允许/禁止命令做语义等价测试；Windows 无捆绑可用二进制，不作为依赖；输出压缩的收益不能全归 RTK。 |
| M33 | **有界 fresh review/二次会话**：[C] `_FreshReviewAgent` 可由短执行、置信度或 profile 范围触发，合并两段 usage/events/diff/wall；`ContractReviewAgent` 共享剩余时间且新 trace。 | 条件扩展 `runtime/completion_review.py`：`trigger_reason,initial_call_ids,review_call_ids,review_budget,remaining_budget,review_outcome,final_artifact_ref`；两段 UsageEvent 不可合并丢失。 | 未触发、成功/失败 review、超时、剩余预算≤下限、最终 diff 取实际最终状态；不能无条件二次调用、重复计费或失败 review 冒充初段成功。当前九 policy 未启用 fresh_review。 |
| M34 | **失败优先调度仅改顺序、不泄漏**：[C] `evaluation_order.failure_first_schedule` 要完整 baseline+hash，所有题重新评，baseline 结果不进 solver。 | `evaluation/schedule.py` 输出 `ordered_task_ids,baseline_run,baseline_result_hashes,scope`；protocol 声明 schedule seed/顺序，选择器读取全量而非流式早停。 | 不完整 baseline 拒绝、全题仍执行、模型输入无 baseline outcome；不能把 failure-first 变成只测失败题或动态加权。 |
| M35 | **可恢复、原子、身份一致执行**：[C] `_write_json` 临时文件替换、run-dir identity mismatch 拒绝、harness tree hash 碰撞复查、任务 attempts 不覆盖。 | `execution/run_store.py`：`run_id,config_hash,artifact_hash,attempt_history,final_result_ref,resume_compatible,write_status`；复用现有原子写思路。 | 中途崩溃、重跑改 config、重复 task id、hash 冲突、坏 JSON、旧 infra 重分类；不能拿 mtime 当身份，不能覆盖旧 attempt。 |
| M36 | **训练核心集多样性（后置）**：[P] 难度加权 DPP、抽象失败指纹去任务名、贪心最大 det、k=10，val/test 不参与。 | 条件扩展 `evaluation/coreset.py`：`difficulty_source,fingerprint,embedding_model_version,kernel_hash,selected_ids,selection_seed,heldout_exclusion_proof`。 | 先在现有 c/q/m 和成本桶构造无 embedding 多样性基线，再与 DPP 比；小样本/零向量/重复指纹；不搬 ε/θ/k，不让 val/test 泄漏。 |

## 2. 必须落到计划的统一数据与算法契约

### 2.1 三条记录，不要把 `TaskMetrics` 做成混合大表

[R] 建议以 `UsageEvent`（每次 provider 调用）、`AttemptRecord`（每次物理尝试）、`CandidateEvaluation`（同 protocol 的正式聚合）三层组成；`TaskMetrics` 是 Attempt/Rollout 的视图。每行都带 `schema_version,evidence_ref`，成本聚合只从明细计算。

```text
UsageEvent:
  call_id, task_id, candidate_id, rollout_id, attempt_id, call_role, cost_scope
  requested_model, actual_model, endpoint_class, provider_trace_id, observed_at
  usage_raw, usage_status, input/cached/cache_write/output/reasoning_tokens
  pricing_version, pricing_status, estimated_cost, evidence_ref

AttemptRecord:
  attempt_id, task_id, candidate_id, parent_id, rollout_id, protocol_id
  attempt_class, selected_formal, formal_exclusion_reason
  passed, score, outcome_kind, evaluator_id/version, artifact_hash
  solver/grader/environment/provider_wait timings
  llm_call_ids[], tool_events_ref, raw_trajectory_ref, profile_effective_hash
  execution_cost, execution_cost_status, infrastructure_cost_excluded

CandidateEvaluation:
  candidate_id, baseline_id, protocol_id, epoch_id
  expected/completed/pending/infra/invalid counts, result_set_complete
  performance_kind, performance, mean_cost_per_task, cost_of_pass
  n_rollouts, variance/sample_stddev, cost_scope_breakdown
  measurement_status, usage_complete, pricing_complete
```

[R] 选择接口固定为 `select_candidate_pool(attempts, baseline_id, protocol, weights) -> SelectionReport`；先按 protocol 分组和完整性资格，再算 C/CoP，再 baseline floor/Pareto，最后才归一化。不得将 `infra_failed` 当任务失败，也不得让它们从成本史消失。正式候选比较的 C 只含同一 formal scope；`excluded_infra_cost`、`search_cost`、`evaluation_cost` 另列，以免通过反复重试隐藏账单。

### 2.2 固定协议与“冻结什么”

[R] `validation_protocol.json` 至少冻结：任务身份与 split、初始 harness/轨迹引用、合成测试 artifact、evaluator 与依赖、模型/端点类别、decoding、工具/环境、rollout 规则、价格版本、种子和预算。改动任一影响测量可比的字段必须生成新 `protocol_id`；旧结果仅作历史参考。价格更新可以重算展示成本，但必须保留原测量和 `repriced_from`，不得悄悄改历史裁决。

[P] 验证每候选每任务一次是论文实验协议，不是抗噪声的通用答案。[R] DWC 应先在相同 paired seeds/环境重复 baseline 估计噪声带，再决定 val rollout 数；未达样本量时 `measurement_status=insufficient`，不可把轻微 PR 差写成提升。基线必须先于候选完整测得；基线无效，整个候选池不可裁决。

### 2.3 归一化和保留的确定规则

[R] 对 degenerate range 建议 `d=0`，并记录该维没有区分度；若两维都退化，所有候选按 `candidate_id` 确定性 tie，不随机。模式权重只影响非支配集代表点，不重新允许 below-floor 候选。`representatives` 是 mode→candidate 映射，`unique_parent_pool` 去重，所以可能少于三个父代。no-change baseline 单独保存在部署回滚位，不依赖数学上的非支配性。

### 2.4 失败/浪费 rollout 诊断的最小真值

[R] 一条诊断必须引用至少一个 `trajectory_ref + event_range`；频率分母是同组已观察 rollout，不是 planner 猜测。重复 action 只有在 `state/evidence digest` 未变且后续未产生新决策信息时才候选为 waste；人工/规则诊断先给出 `candidate_waste`，模型解释再标注为推断。成功 rollout 同样进入诊断。跨候选只形成 `association`，单组件变更+paired trial 才可进入较强归因；多组件编辑必须列 `confounders`。

### 2.5 画像与运行时的候选身份

[R] `candidate_id` 应覆盖最终生效的 prompt、工具集、memory/context policy、profile 选择器、effective profile 参数、hooks、模型与 decoding；仅记录 classifier 原始输出不足。profile shadow 阶段输出 `would_select` 但不改变执行；启用后记录 `requested/classified/effective/actual` 四层。默认 standard 是 DWC 的设计选择，不是 HarnessPro 证明的五档最优；规则失败、未知输入、无效分类一律 conservative fallback 并留痕。

## 3. 明确不能照搬或不能作为已实现声称的内容

1. **不能从公开仓库复制“完整 HarnessPro 进化算法”**：代码不存在；Eq.1–12 和伪代码只能作为纸面设计依据。Pareto、test synthesis、DPP、三意图须在 DWC 自行实现和测试。
2. **不能把论文数值当 DWC 预期提升**：10-task coreset、G=3、1 次 val、3/4 epoch、2–3 次 final run、特定模型/CLI/Docker/价格，均限制外部效度；GLM evolved snapshots 未发布。
3. **不能把一次验证 PR 当可靠率保证**：需噪声、小样本和 paired baseline；基础设施排除/重试要保留完整账，不得择优重试。
4. **不能把九套 prompt/rubric、五档名、14/26/44、0.9、64K 当通用常量**；它们是 benchmark 产物。也不可将 `fresh_review/adjuster/多样本` 通用代码能力说成所有产物实际启用。
5. **不能照搬 RTK 或命令重写**：Linux x86-64 二进制、Bash hook、Unix `fcntl` 和 Codex/Claude payload 都依赖其生态；DWC Windows/原生 tool loop 应实现自己的受控压缩与并发安全计数。RTK 会改变命令语义的风险已被其 allowlist 注释证实。
6. **不能用“提示进入 strict”代替硬预算**，也不能在硬 cap 时隐藏未完成；DWC 的 ask/权限、安全、artifact 保留优先于收敛提示。
7. **不能把压缩、低 reasoning、少工具、fresh review 单独当收益来源**：论文消融更支持组合协同；每个机制需独立 shadow 和组合成本核算。
8. **不能让 candidate 修改评价器/heldout/质量门，不能让 planner 看 val/test**；合成测试不是 ground truth，judge 的自报不是完成证据。
9. **不能把 replay/offline 的历史重放当新在线性能**，也不能跨模型、harness、工具、cache、decoding、evaluator、价格直接比较旧分数。
10. **不能把新选择器直接接现有自动落地**。`select_winner`、`world_tree` 的 Pareto 字样、`replay` 的 baseline retention 各自只覆盖局部语义；新增 selector 与现有六门/evo_targets 串接，先 shadow、人类批准、备份读回、canary/rollback。

## 4. 给 DWC 2.0 主计划的精确补丁建议

### P0（必须补入 W1/W2）

- W1 增加三层 UsageEvent/Attempt/CandidateEvaluation、`cost_scope`、formal/excluded 双账、actual model、late usage reconcile、C 与 CoP 的完整性条件、分段延迟。**这是后续所有裁决的硬前置。**
- W2 增加 `protocol_id` 全身份冻结、结果集完整性 qualification、binary pass 与 macro score 不混、baseline/no-change 最终池保留、无效 baseline 整池 indeterminate、退化归一化/同分/重复代表点的确定规则。
- 固定合成测试作为**条件性扩展**，补 artifact hash、反例、未覆盖行为、生成者/候选隔离；不创造已有实现的假象。

### P1（应补入 W3/W4）

- rollout group 键必须含 `task_id+candidate_id+protocol_id`，成本/成功轨迹同入；诊断输出事件引用、证据状态、unknown/confounders。
- 三意图计划增加 `no_change/no_evidence/unsupported`、peer diff scope、predicted/measured 分离、搜索与部署成本分账。
- 独立 workspace 不等于许可全仓修改；candidate artifact 的身份、回滚句柄和 evaluator 不可变要进入测试。

### P2（应补入 W5，均先 shadow）

- 画像记录 requested/classified/effective/actual 四层和分类成本；默认规则先行，通用 adjuster/多票不是一期依赖。
- 三阶段提示+硬 cap+best-effort incomplete+denial 停止组成一个状态机；raw 可恢复压缩与内容类型白名单先于任何 RTK 试验。
- fresh review 仅条件扩展，必须两段用量、剩余预算、最终实际 artifact 合并，不为“复杂任务”无条件加一次 LLM 调用。

### 新增验收测试组（拟建）

```text
tests/test_usage_events.py             # M01–M06，所有 client 路径和归属
tests/test_attempt_accounting.py       # M07–M10，formal/excluded、C/CoP、timing
tests/test_candidate_protocol.py       # M11–M14，冻结、隔离、hash、完整性
tests/test_pareto_select.py            # M15–M18，baseline、支配、零范围、tie、重复 mode
tests/test_rollout_diagnosis.py        # M19–M21，稳定/flaky/成功浪费/证据追溯
tests/test_intent_candidates.py        # M22–M25，三意图/no-change/confounder/rollback
tests/test_profile_selection.py        # M26–M28，未知回退、effective identity、缓存失效
tests/test_budget_convergence.py       # M29–M30，软/硬阶段、deny、incomplete
tests/test_output_compaction.py        # M31–M32，恢复、图片、危险命令不 rewrite
tests/test_completion_review.py        # M33，条件扩展、双账、最终 artifact、预算
tests/test_evaluation_resume.py        # M34–M35，只重排不泄漏、崩溃/身份/原子恢复
tests/test_coreset_selection.py        # M36，条件扩展、去重和 held-out 排除
```

（文件名、字段、接口和测试均为拟建建议。）

## 5. 证据索引与实测边界

- [P] 论文全文：<https://arxiv.org/html/2610.26770v1>，重点 §3–5、Algorithm 1、Eq.1–12、Appendix A–D。
- [C] 发布范围：`README.md:12,20–38,134–153`；`docs/evaluation.md:21–28,119–138`。
- [C] 测量：`src/rho/observability.py:104–192,274–442`；`src/rho/pricing.py:127–211`；`src/rho/qualification.py:17–168`。
- [C] 固定执行/可靠性：`src/rho/evaluation_order.py`；`src/rho/stores/harness.py`；`src/rho/agent/cache.py`；`scripts/run_tb2_harness_eval.py:1353–1406,2360–2386,2889–3151`；`scripts/run_programbench_eval.py:140–211`；`src/rho/datasets/programbench/results.py:175–316`。
- [C] 运行时：`src/rho/harness_runtime.py:15–190,847–1106`；九份 `harnesses/*/*/runtime/policy.json`；TB2/SWE `runtime/hook.py`；`src/rho/agent/claude_code_hook_adapter.py`；`src/rho/agent/contract_review.py`。
- [D] DWC 对照：`src/dwc/llm/client.py:143–155,417–545,547–691`；`src/dwc/harness/run_term.py:207–261,459`；`src/dwc/organs/evolver.py:441–493`；`src/dwc/organs/effort.py`；`src/dwc/organs/router.py`；`src/dwc/harness/evo_proposals.py`；`src/dwc/organs/evo_targets.py`；`config/evolution.yaml`。
- 公开测试实测仅覆盖 Windows 当前环境的 9 个 offline cases；未运行 Linux/Docker/模型/benchmark，未复现论文性能数字。此报告验证的是**代码路径与设计映射**，不是性能收益证明。
