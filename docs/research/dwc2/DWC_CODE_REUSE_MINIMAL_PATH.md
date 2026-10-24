# 四论文机制落到 DWC 当前代码：重复、冲突与最小实现路径

> 审计对象：只读 `Z:\DWC pure`，HEAD `5769a125d1a370f9b3fc2c41d0d2fcbeef6d095e`（本机 `git rev-parse` 实测；`git status --short` 无输出）。
> 四论文研究结论沿用共享报告；以下“当前事实”均重新核当前源码，而非照抄旧计划。本文所有新增文件名/字段均为拟建设计，不表示已存在。
> 实测：`uv run --no-project --with pytest --with pyyaml python -B -m pytest` 对 8 个既有测试文件运行，**122 passed / 14.47s**。首次不带 PyYAML 收集有 2 个 import error，补依赖后通过；未运行全量测试，未运行会写 `archive/gate_trace.jsonl` 的 `gate.py`（遵守只读要求）。pytest 初始不可用，使用 uv 临时环境，没有写仓库虚拟环境。

## 1. 总判断：最小路径不是“再造四个子系统”

四篇论文应压进既有 W1–W5 的五层结构：

1. **W1 测量**：在 `LLMClient → task_exec/evo_round/run_term` 现有调用链上补 usage、调用身份、任务聚合。新增一个指标/计价模块即可。
2. **W2 选择**：新增一个纯函数双目标选择模块，向 `Loop._run_one_task` 的 replay 选择面与 `dwc_evo_round.run_round` 的 trial/accept 面提供**另一层评价结果**；不要替换 `evolver.accept` 六门，也不要改写 `replay.select_policy` 的数学语义。
3. **W3/W4 证据与候选**：复用 `failure_sig`、`session jsonl`、`actions_log`、`evo_proposals`、RULES/dream/skill_store，新增一个 rollout 诊断模块和一个意图/范围计划模块；Probe 仍走现有 trial，Compose 只组合受控产物，最终仍过固定评价与门。
4. **W5 运行时**：扩 `task_exec` 的预算参数与返回报告，复用 `evo_targets` 注册表；`effort.py` 只保留 replay 探索预算语义，不拿来充当任务画像。AKV 与模型训练均保持条件扩展。

**真正的最小新增 src 文件集合建议为 5 个**：`observability/task_metrics.py`、`harness/pareto_select.py`、`harness/rollout_diagnostics.py`、`harness/intent_candidates.py`、`llm/task_profiles.py`。其余应在现有文件扩展；不要为 pricing、candidate_metrics、Compose、TIMR、pair identity 各造一个文件。

## 2. 当前真实可复用点与具体扩展点

| 当前文件/位置 | 当前代码事实 | 四论文可复用点 | 最小扩展，不另造平行实现 |
|---|---|---|---|
| `llm/client.py:143-155 LLMResult` | 已有 `ok/text/source/error/meta`，失败与成功可区分 | 原始响应证据的载体 | `meta` 增加 `usage` 与 `usage_status`；不要改 dataclass 必填字段，旧测试/桩不受影响 |
| `llm/client.py:354-545 complete` | 非流式正文和 tool-call 成功路径；429/5xx/传输重试，`n_calls/n_retries/n_ok/n_fail` | HarnessPro 全调用账、CoEvo 接口兼容 | 在解析 `data` 后保存 `data.get("usage")`，正文、tool_calls、reasoning_only、empty、parse/HTTP 失败均按可见程度记；重试递归透传同一调用关联上下文 |
| `llm/client.py:547-691 complete_stream` | SSE delta；失败回退 `complete`；目前 fallback meta 会丢原 `fb.meta` | 流式 usage 与 fallback 成本 | 聚合 SSE 顶层 `usage`（包括无 choices 的末帧，当前代码会跳过）；fallback 合并而非重建 meta，保留 stream 失败与 fallback 两段账 |
| `llm/client.py:417,454-481,693-699` | `n_calls` 是逻辑调用入口计数，retry 另计；未配置提前返回不计 n_calls | 真实调用总量 | 明确 `attempt_count = n_calls+n_retries` 的口径，不在旧 `n_calls` 上偷偷改义；新增按 attempt 的事件账 |
| `llm/executor.py:138-198` | behavior 观测执行器，返回 Receipt；`stats` 只计 calls/parsed/errors | 进化评价的 solver 调用入口 | Receipt.detail 增加 `measurement_ref`，从 `res.meta` 透传 usage/调用 id；不要让 `parse_llm_observed` 兼做评价真值 |
| `llm/task_exec.py:1495-2364 execute_user_task` | 真实用户任务主运行时，产出 task_id/status/rounds/actions_log，session 留痕 | W1 任务聚合、W3 轨迹、W5 画像的主接点 | 建局部 measurement collector；所有 return 汇到统一 finalize helper，写 task metrics 与原始证据引用；在 prompt 构造前 shadow 选画像 |
| `llm/task_exec.py:1711-1758` | native/JSON 两路，429/5xx/transport 标 `[infra]`；tool_calls 转内部 step | 三态测量与 TIMR | 保留 `infrastructure_error`；TIMR 在**转换前**记录 unknown tool、参数 JSON/schema、空协议，恢复另记，不等同任务失败 |
| `llm/task_exec.py:1093-1140` | 原生工具只取 `tool_calls[0]`，未知名/坏参数返回 None；名称映射后复用 `_do_action` 白名单 | CoEvo 工具协议适配 | 最小第一版不要改单工具语义；给 converter 返回结构化 mismatch reason，否则在 task_exec 侧补诊断，不能把 None 当零违规 |
| `llm/task_exec.py:1143-1150,1641-1701,2272-2293` | 15 轮硬顶、同目标 4 次、同 obs 3 次、强制 final；QA 还有独立收敛 | HarnessPro 阶段收敛与运行时硬约束 | 画像只给这些既有常量提供每次任务的覆盖值；保留硬上限与 best-effort final，区分 stage hint 与 hard stop |
| `llm/task_exec.py:1421-1492,2326-2364` | 失败后任务级 revision 二跑；旧 log 两轮滑动窗口+摘要 | 辅助调用成本、AKV 对照基线 | revision/delegate/judge/expansion 归父任务但保留独立 rollout；文本 compaction 是普通 context policy，不能标 cache drop |
| `harness/run_term.py:207-261 CostLedger` | term/cumulative/rejected/history 抽象成本；`step_cost=1.0` | 抽象执行成本与拒绝候选成本已有语义 | 保持类与字段不动；TermReport 追加可选 `measurement_ref/metrics`，禁止把 token/USD 塞进 `term_cost` |
| `harness/run_term.py:305-376 TermReport` | judgement/router/measure4/gate_chain/activity 已集中成报告 | W1 汇总出口 | 只加可选引用/指标；不要改 `score_delta` 或 judgement 三态 |
| `harness/run_term.py:726-756` | judge pass/fail + term_cost → 七桶 router | 成本问题进入议程 | 新 router 输入可由真实 task metrics 构造，但旧 `CostLedger` 路径保留作 legacy；缺 usage 应 unknown，不能默认 efficient |
| `harness/loop.py:513-752 _run_one_task` | 当前实现与提案 trial，current 必入，replay 单标量 argmax，随后六门+pipeline | W2 接入点、incumbent 保底 | 在 `_v` 构造后增加 candidate metric 评价与 Pareto shadow；切换前仍调用六门。不要删除 `shortlist_candidates/select_policy`，旧语义与其他调用者仍需要 |
| `harness/replay.py:142-250` | `replay_score` 单标量 V；`select_policy` 强制 current；`select_with_val_fallback` 处理 val 空/平票 | 基线保底、确定性 tie-break、搜索/验证分离 | 新 Pareto 模块复用“current 必含、确定 tie-break、不可比显式”的纪律，不把二维向量强塞成 float；replay 本身不是 HarnessPro Pareto |
| `scripts/dwc_evo_round.py:291-661 run_round` | 聚簇→propose→多次 trial→accept→可选落地；`envelope.llm_calls/tokens` 明确 unmeasured | HarnessPro 搜索成本、三意图候选与父代竞争 | `clusters` 外部注入已存在；给每个 attempt 附 measurement_refs/intent/parent；trial dict 增 metrics，不破坏 bool/None 兼容；消除 envelope 的 unmeasured 但保留历史行 |
| `scripts/dwc_evo_round.py:773-933 _real_trial` | dev + held-out、baseline 前置快照、小 Δ 熔断、agent/code/report 多路 | Probe 与固定评价复用 | candidate 在同一冻结协议下跑，不在每候选后改 anchors；辅助 peer 写码也入账；model/harness 不一次同时晋升 |
| `organs/credit.py` | 固定七元组、append-only、旧 `{entry:...}` 信封读兼容 | 编辑归因与采纳账 | **不要给 CreditEntry 加 usage/pair 字段**，避免破坏七元组测试；用 edit/hunk 关联 task metrics sidecar。`delta_c` 仍按旧抽象口径，不能改义成 USD |
| `organs/router.py` | 七桶含 all_pass_wasteful 与 infra_only | 成功但浪费、环境失败不进化 | 直接复用桶和动作；新增 task-metrics 投影函数即可，不能拿 TIMR 低替代 pass/fail |
| `organs/effort.py` + `core.py:801-817` | gain 节流/冲刺纯函数，且已实际接入 **dream replay K2**，不是“完全未接生产” | 搜索预算调度 | 保持 replay 专用；任务画像另建参数结构。旧计划“未接生产”的描述已过时，应修正为“已接 replay，未接 task_exec” |
| `organs/evo_targets.py` | 五类白名单产物、schema、defaults、备份、原子写、读回、rollback/smoke | 受控 harness/profile/cache policy 落地面 | 新增 component spec（如 `runtime_profile`）而非允许任意 JSON；shadow 阶段只 read/validate，不 apply |
| `organs/evo_driver.py` | 目前只由第一页 read truncated 驱动 read_default_lines，24h 防抖、有界调整 | 证据驱动参数调整参考 | 不要把 Pareto selector 直接接到此 driver；它当前是单信号即时调参，与 W2 固定复评冲突。受控晋级应走评价结果→人工批准→ET.apply |
| `organs/memory.py` | SQLite WAL、FTS、failure_sig、MemoryKind、access/effect、旧列 ALTER 兼容 | Harness² 经验库、CoEvo 历史检索原料 | 经验条目不复制完整 harness；优先新 JSONL sidecar 存 cue/scope/evidence/confounded/source refs，召回后再验证；不要为本次改动强迁主库 |
| `harness/trajectory.py` | Loop `_last_*` 轮次快照 jsonl，schema=1 | 跨轮证据引用 | 可链接 rollout metrics，但它不是逐工具轨迹，不能代替 task_exec session/actions_log |
| `scripts/gate.py` | G1/G2/G4/G7/G8 静态契约门，主入口固定写 trace | 新模块防重复、真值、池上限、静默与判据不可写 | 新模块 docstring 带 DWC-AUTO；selector/diagnostics 声明 TRUTH_SOURCE；候选池 cap+overflow；异常可观测。验收时运行 gate 是预期写 archive，不属于本次只读审计 |

## 3. 重复与冲突：必须在总计划中写清

### 3.1 `replay.select_policy` ≠ Pareto；`evolver.accept` ≠ 候选排名

- replay 是固定历史上的单标量策略选择，其“不劣”保证不等于在线性能保证；Pareto 是新纯函数层。
- `evolver.accept` 和 `harness/gates.py` 管“能否采纳/落地”，不是 performance-cost 排序。最小结构是：**测量 → Pareto/基线过滤 → 六门/accept → 人工/受控落地**，而不是让任一旧组件兼任全部职责。
- `Loop` 当前只实际 trial `proposals[0]`，不是多父代、多意图并行评价；不能因 `cands` 列表存在就声称已有候选池竞争。

### 3.2 `CostLedger`、`CreditLedger`、`evo_round.envelope` 是三种不同账

- `term_cost` 是抽象步骤成本；`delta_c` 是编辑归因成本；`envelope.search_cost` 是搜索面说明。三者不能互换，更不能直接当 token/USD。
- 新 task metrics 应以 call event 为明细、task/candidate 为聚合；Credit 通过 id 关联，不再复制 usage。
- `dwc_evo_round.run_round` 的 `llm_calls/tokens=unmeasured` 是明确缺口，不是已有计量。

### 3.3 `effort.py` 已被 `core.dream` 消费，任务画像是另一件事

旧研究报告称 effort 只有 simulate 引用，与当前 HEAD 不符。当前 `core.py:801-817` 已根据 replay `v_star` 增益调 K2。W5 不应复用这个增益公式做任务难度分类；只需共享“有界、可审计、首轮 unknown”的工程纪律。

### 3.4 Harness² Compose/经验库与现有 RULES、skill、dream、prompt OTA 重叠

- 不新增永久完整 harness 仓库。经验条目只存 `cue/applicable_scope/component/operation/supporting_contrasts/confounded/evaluation_version/source_harness_ref`。
- `no_change/KEEP_BASE` 与 replay current 保底一致；但 Compose 的 kept_base 不能替代最终候选池 base。
- “意图（cost/balanced/performance）×范围（invariant/domain）”是正交标签，只给有证据的格子出提案，不机械生成 6 份。

### 3.5 CoEvo 的模型继承与当前远程 API 冲突

当前没有 checkpoint/TIES/SFT 控制权。最小可行对象只是 `(model_route, reasoning_effort, harness_hash, tool_schema_version, cache_policy_version, evaluation_version)` 的受控配对身份。历史 pair 的分数不可跨 harness 直接比较；模型与 harness 候选要分臂评价。TIMR 只能辅助诊断，不参与补偿任务质量。

### 3.6 AKV 与当前 client/remote endpoint 冲突

- `LLMClient` 每次发送完整 messages，当前没有 drop/reposition、操作历史、server capability 或 cache observation；不能加请求字段就宣称生效。
- 现有 task_exec 文本摘要/compaction 会改变逻辑上下文，和 AKV“保留文本、改变 active KV”不同，应保留为 unsupported 时的独立基线。
- 第一版只在 task metrics 预留可选 `cache_observation`：`policy_decided/request_sent/server_accepted/usage_status/unsupported_reason/evidence_ref`。不满足服务端、模型与真实 usage 条件时 `unsupported_remote`，不进入 W2 自动候选。
- 若未来实现，cache identity 必须含 message prefix、operation history、model/rendering/tools 配置，不可只用文本 hash。

## 4. 最小数据契约与迁移兼容

### 4.1 明细、聚合分离

建议 `task_metrics.py` 同时容纳两类记录，避免多个小模块：

```text
CallEvent v1:
  schema_version, call_id, parent_call_id, task_id, rollout_id
  candidate_id, parent_candidate_id, term_id, call_role, attempt_index
  model_route, harness_hash, tool_schema_version, reasoning_effort
  started_at, wall_time_ms, finish_reason, transport_status
  usage_status, usage_raw_ref
  input_tokens, cached_input_tokens, output_tokens, reasoning_tokens
  infrastructure_status, evidence_ref

TaskMetrics v1:
  schema_version, task_id, rollout_id, candidate_id, parent_id
  measurement_status, pass, pass_rate, evaluator_id/version, task_set_id
  llm_calls, llm_attempts, tool_calls, rounds, wall_time_ms
  token sums + coverage flags
  provider_cost_estimate, pricing_version, abstract_step_cost
  call_event_refs[], pair_identity, cache_observation(optional)
```

规则：token 缺失为 None，聚合必须带 `usage_coverage`；usage 不完整时成本为 `undefined/not_comparable`，在 Pareto 中不得当 0 或“无限便宜”。CoEvo 报告建议的“缺 usage 当无限成本”可用于**保守拒绝排序**，但不应写成一个伪精确 USD 数字。

### 4.2 旧数据兼容

- 新 JSONL 一律 `schema_version=1`，读端允许旧行缺字段：缺失是 `not_reported/unknown`，不能补 0。
- `var/credit_ledger.jsonl` 继续支持七元组平铺和旧信封；新任务账放独立 `var/task_metrics.jsonl` 与 `var/llm_call_events.jsonl`，避免主 SQLite 迁移和双写旧账。
- `TermReport/LLMResult/trial dict` 只加可选字段，保留现有构造器和 bool/None trial 分支。
- `config/pricing.json` 与 `config/validation_protocol.json` 是拟新增文件；无文件只禁用估算/标记未配置，不改旧默认。
- 新 profile/cache spec 的 defaults 必须与 task_exec 当前硬编码一致；缺产物走旧行为。

## 5. Windows 原子写与并发风险

1. **固定 `p+".tmp"` 会互相覆盖**：`evo_targets.apply` 在并发 candidate/进程下同路径写临时文件，可能 replace 冲突、内容错配、PermissionError。应改同目录唯一临时文件（`mkstemp`，关闭原生句柄后再写），finally 清理；整个 read-merge-write 需锁，不只是 rename。
2. **`os.replace` 只保证同卷替换语义，不保证丢更新/持久化**：目标被其他进程/杀软/编辑器打开时 Windows 可失败；需可观测重试和错误态，不能当成已 apply。至少 file `flush+fsync`；不要照搬 POSIX `O_DIRECTORY`/目录 fsync。
3. **备份名只有秒级时间戳**：同 component 同秒两次 apply 会撞名；backup 需唯一 id，并记录内容 hash。首次创建无 before 文件时，rollback 应表示“删除新建文件/恢复 defaults”的显式策略，而非无备份假成功。
4. **rollback 当前 `shutil.copy2` 非原子**：崩溃可留下半截配置；应与 apply 共用同一安全写函数并读回。
5. **JSONL 多写者不原子**：新 call/task metrics、credit、evo ledger 均可能多进程 append。Windows 不能默认一条 `write` 跨进程绝对不交织；最小路径是单 writer/进程锁，或 SQLite WAL 新表，不能靠 os.replace 解决 append。
6. **在途读者缓存**：`task_exec.TASK_TOOLS` 在 import 时合并，运行时改 client_tool 不会刷新既有进程；`_policy` 虽按内容 hash 缓存，但 TASK_TOOLS 是模块级快照。profile candidate 的 smoke 必须验证新进程或显式 reload，不可把 ET.read 成功当消费者已生效。
7. 新增测试必须在 tmp_path 注入 ROOT/ledger/session 路径，禁止像旧生产函数那样默认写真实 `var/config`。

## 6. 分阶段最小实施与可执行测试

> 以下命令是解冻后实施时的验收设计，不是本次已执行结果。每个阶段先跑定向，再跑相关旧测试、全量与 gate；失败必须真实报告，不能用静态检查冒充运行验证。

### 阶段 0：冻结基线与测试骨架（不改行为）

- 固定 8 个当前测试为 smoke baseline：`test_llm_candidates.py test_r237_stream.py test_r384_native_tools.py test_replay.py test_r155_credit.py test_r252_effort.py test_r143_router_wiring.py test_evo_driver.py`。
- 增加 fake transport 响应样本（正文/tool_calls/空/推理耗尽/SSE usage 末帧/429→成功/流式→整段 fallback），全部不触网。
- 验收：当前 122 项保持绿；采集全量 collect-only 与全量 pytest 基线。

### 阶段 1：W1 usage 与任务测量，只观测

**改动点**：`client.py` 全返回路径；`task_exec` 统一 finalize；`executor.py`、`_real_trial`、evo `run_round` 透传 refs；`run_term.TermReport` 可选 ref；新增 `task_metrics.py`。

**新增测试**：
- `tests/test_llm_usage.py`：每类响应 usage 原样保留；缺 usage=None/not_reported；retry 的每次 attempt 独立；fallback 不重复/不丢账；凭证不进事件。
- `tests/test_task_metrics.py`：同一 task 的 solver/revision/delegate/judge/diagnosis 聚合；token sums 由明细计算；0 成功 CoP=undefined；infra error 与 task fail 分开；缺 usage 不进入可比成本排序。
- `tests/test_task_exec_metrics.py`：每个 early return 都能写恰好一条 task 汇总；native/JSON/plain_text/incomplete/revision/delegate 路径覆盖。
- 兼容：既有 `LLMResult`、stats、retry、stream、native tools 测试不变。

**验收命令**：
```bash
uv run --no-project --with pytest --with pyyaml python -B -m pytest tests/test_llm_usage.py tests/test_task_metrics.py tests/test_task_exec_metrics.py tests/test_llm_candidates.py tests/test_r237_stream.py tests/test_r384_native_tools.py -q -p no:cacheprovider
```

### 阶段 2：W2 固定协议 + Pareto 离线选择

**新增 `pareto_select.py`**：candidate record、identity/version 校验、baseline filter、dominance、三模式 deterministic tie-break 同文件完成。输入只来自 W1；held-out 只做最终验收。

**新增测试 `test_pareto_select.py`**：基线保留、父代不退出、支配/反支配、同分/重复、PR 或成本 range=0、空集、缺 usage、infra error、版本不一致、held-out 不可进入 selector。已知候选集手算前沿。

**接入测试 `test_loop_pareto_shadow.py`**：当前 replay 结果保持不变时只输出 shadow；启用新选择后仍过六门；current 与全部有证据候选同池，不只评 proposals[0]。

### 阶段 3：W3 多 rollout 诊断 + TIMR + 经验索引

**新增 `rollout_diagnostics.py`**：纯函数读取多次 task metrics/session 摘要；输出 correctness/waste/instability/infrastructure、frequency、事件区间、first_effective_step、confounded/unknowns；TIMR 带 coverage，绝不生成综合质量分。

**新增测试**：稳定失败/偶发失败/成功但重复/infra 四类；多工具同 turn 只记一次 mismatch；恢复单独计；trace 不完整 coverage<1；behavior_changed/adopted 不推导 verified_improvement；无证据经验不写。

### 阶段 4：W4 意图×范围候选、Probe/Compose、shadow

**新增 `intent_candidates.py`**：计划 schema 与证据校验；复用 `evo_proposals`/Mutator 生成；`clusters` 注入与 `_real_trial` 做 Probe；Compose 只允许 ET 白名单组件、保留 base/no_change；每 attempt 记录改进成本。

**新增测试**：三类意图不是改名字复制；无证据格子不生成；父代总在最终池；多组件变更标 confounded；model-only/harness-only/pair 分臂；候选无权写 evaluator/held-out/gates；结束只产 shadow，不调用 ET.apply。

### 阶段 5：W5 规则画像与运行时收敛

**新增 `task_profiles.py`**：unknown→standard，给出 max_rounds/repeat_limit/reasoning_effort/final reserve/stage hints 及理由；先 shadow 只记录，后经 ET spec 有界应用。AKV 只保留 capability/observation 接口，不作为本阶段依赖。

**新增测试**：画像默认值等于当前 15/4 等硬约束；分类失败回退；硬上限不能被提示词绕过；final 保留预算；长输出原文可恢复；服务端不支持 AKV 时不得发送 drop/reposition，cache_mode=unsupported_remote。

### 阶段 6：独立验收与受控落地

- 同 task_set/model/harness/evaluator version 比 base、候选、必要 pair 分臂，报告 PR/C/CoP/L、样本量/方差、infra/invalid/usage coverage。
- held-out 和人工反例通过后才允许人工批准调用 `ET.apply`；验证 backup→readback→consumer smoke→rollback 全链。
- 最后跑 `python -B -m pytest tests -q -p no:cacheprovider` 与 `python -B scripts/gate.py --json`；记录实际计数，gate 的 archive 写入属于明确验收动作。

## 7. 最小文件清单（冻结后）

**新增 src（5）**
- `src/dwc/observability/task_metrics.py`（CallEvent/TaskMetrics/聚合/pricing 纯函数）
- `src/dwc/harness/pareto_select.py`（candidate record/protocol identity/Pareto）
- `src/dwc/harness/rollout_diagnostics.py`（rollout/waste/TIMR/confounded）
- `src/dwc/harness/intent_candidates.py`（意图×范围计划、Compose/no_change）
- `src/dwc/llm/task_profiles.py`（规则画像与运行时参数，不含 AKV 服务端实现）

**扩展现有**：`llm/client.py`、`llm/executor.py`、`llm/task_exec.py`、`harness/run_term.py`、`harness/loop.py`、`scripts/dwc_evo_round.py`、`organs/evo_targets.py`；`credit.py/replay.py/router.py/effort.py/memory.py` 原则上不改或只做只读投影，避免语义漂移。

**新增配置/测试**：`config/pricing.json`、`config/validation_protocol.json`；上述各阶段测试文件及 `test_atomic_evo_targets.py`。不新增 AKV/SFT/TIES 训练文件，不新增完整 harness 经验仓库。
