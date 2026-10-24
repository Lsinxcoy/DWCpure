# Cache Engineering / AKV → DWC pure 2.0：全文与代码级融合契约

> 状态：**研究、拟建设计，未实现、不解冻、不要求现在实现 GPU serving**。论文核验 *Cache Engineering for Agents* v1；AKV 本地提交 `c567a429a058f1abce3b2879e69978b09e0fda4c`；DWC 本地提交 `5769a125d1a370f9b3fc2c41d0d2fcbeef6d095e`（两者均由本机 `git rev-parse` 复核）。[1][2]
>
> 证据标签：`论文`＝论文声称；`AKV代码`＝提交级本地源码事实；`DWC现状`＝当前源码事实；`拟建`＝建议写入总计划，当前不存在。本文不重复把论文均值当 DWC 收益，也不把客户端策略执行当 GPU 验证。

## 0. 总结裁定

1. **保持 W1–W5，不新增 W6。** W1 采集 cache 事实，W2 在固定协议下比较 cache policy，W3 诊断证据损失与浪费，W4 将 policy 作为条件性候选，W5 仅在已验证能力的端点 shadow 后启用。
2. **当前远程端点默认 `unsupported_remote`，不是 `supported_but_untested`。** OpenAI-compatible 只说明基础路径兼容，不能推出 `drop_message/drop_rule/reposition` 被解析，更不能推出扩展 radix、drop-aware eviction 或 segment-batch restoration 存在。
3. **最小复用边界**：近期只扩 `llm/client.py` 的可选请求扩展点和 usage 原样透传、`observability/task_metrics.py` 的 cache identity/observation、`llm/task_profiles.py` 的规则 policy；不新增 SGLang、CUDA、GPU 依赖，不新增完整 AKV 服务端文件。
4. **三条不可混淆的线**：文本 trimming/summary 改变逻辑轨迹；drop 只改变后续 attention 可见 KV；物理 eviction 只改变驻留，不应改变请求规定的输出分布。当前 DWC 的文本压缩只能作独立 baseline，不能改名 cache drop。[1]
5. **默认不发送扩展字段、不自动探测后降级重发、不把缺失 usage 填 0。** 有服务能力时必须由人工/受控配置绑定到具体 endpoint/model/runtime revision，并经过小样本真实响应验证；`/v1/models` 或 HTTP 200 本身均不构成能力证明。

## 1. 机制总表（27 项）

| # | 机制 | 论文/代码精确含义 | DWC 拟建落点与测试 |
|---|---|---|---|
| 1 | **逻辑轨迹 ≠ active cache ≠ 物理驻留** | 论文分别定义逻辑 token 序列、后续 attention 可用 KV、物理 residency；active 不是“显存里还在”。[1] | W1 三字段分账：`logical_tokens/active_cache_reported/physical_residency`；未报后两项为 `not_reported`，不能从文本长度或 cached_tokens 推断。 |
| 2 | **append** | 新 token 在当前 active cache 条件下计算并追加 KV；位置默认递增，prompt/tool/output 都可 append。[1] | identity 以完整消息与操作序列为源；测试 append-before-drop 与 drop-before-append 不共用 cache id。 |
| 3 | **drop 的 operate-after 语义** | 在 trigger message **之后**排除指定 active KV；保留 KV、其位置、逻辑文本均不变，也不回收下一 append 的位置。[1] | `CacheOperation(trigger_id, drop_ids, reposition=False)`；测试 trigger 自身可在此前计算、后续才不可见，drop 后逻辑 messages 完全不变。 |
| 4 | **drop 不等于彻底遗忘** | 保留 KV 计算时可能已见过后来被 drop 的内容，因此仍可能携带其信息。[1] | 禁止把 drop 用于隐私擦除、权限撤销或安全边界；测试/文档明确“后续不可直接 attend”而非信息消除。 |
| 5 | **repos** | 保留 r 项按逻辑顺序编码到 `0..r-1`，下一 append 位置 r；RoPE key 旋转，V 不变。[1] | 独立 `reposition` 决策；不得因 drop 自动开启。测试 drop-only 位置有洞，repos-only 无 drop 也有效。 |
| 6 | **同边界先 drop 后 repos** | 操作序列确定状态；同一 message 边界 drop 先于 repos。[1] | 规范化器固定顺序；乱序构造、重复 trigger、未来 id、重复 drop 均拒绝。 |
| 7 | **cache identity 的历史依赖** | 相同最终 token/保留位置也可因 append/drop/repos 顺序不同而有不同 KV；普通 prefix match 不足。[1] | `cache_state_id=H(model_cache_config, canonical_full_prefix, operation_history)`；不能仅 hash 最终 active messages。 |
| 8 | **stateless interface, stateful serving** | 客户端每次发送完整 messages 与累积操作；服务器决定复用、驱逐、恢复，客户端不跟踪物理 KV。[1] | `CacheOperationHistory` 按 conversation branch 持有；重试必须带同一已发送操作，不得重新随机决策。 |
| 9 | **extended radix：drop nodes** | Δ 节点记录 trigger 与范围；token+operation prefix 同时匹配才直接复用；空物理节点仍可定位后代。[1][2] | 只作为未来 serving 契约；DWC 客户端用 A/B/C 不同 drop 时机 fixture 验证 id 不碰撞，不在客户端实现 radix。 |
| 10 | **extended radix：position/reposition nodes** | token key 含当前编码位置；reposition 节点保留计算历史，避免后来旋转掩盖早先计算差异。[1] | identity 不能省略 repos 时机；测试“最终位置相同、D 计算前 repos 不同”不命中。 |
| 11 | **exact 与 retrigger matching** | exact 比 token、position、operation；retrigger 仅投影掉存储位置，仍保留所有操作，源 KV 可复制旋转而不重算 hidden state。[1] | 服务端未来验收分 `direct_reuse/transformed_reuse/recovery`；不得把 transformed reuse 算 direct cached_tokens。 |
| 12 | **drop-aware eviction** | 仅无活跃计算/恢复需求时回收；drop KV 优先于已完成请求普通 KV；释放物理页但保留树占位。[1][2] | 不要求客户端管理页；未来服务端测试共享前缀隔离、恢复需求 pin、后代仍可命中。 |
| 13 | **position version 独立驱逐** | 不同 position 的 KV 版本分别管理；复制/旋转不覆盖仍在使用源版本。[1] | identity 与 observation 记 `position_version`，测试源/目标并发引用不互删。 |
| 14 | **segment-batch restoration** | 物理 KV 缺失时按 drop/repos 边界分段 query；各段看其历史可见集，FFN 整批，单次 model forward 恢复而非逐操作 forward。[1] | “无需 re-prefill”仅限兼容保留 KV；未来测试全冷/部分驱逐/全命中产生同一语义计划，当前无 GPU 不声称验证。 |
| 15 | **request isolation** | 输出分布须独立于物理驻留和其他请求的 cache 操作。[1] | 未来 serving 必测同 token prefix、不同操作分支并发；当前远程没有证据则 capability 不通过。 |
| 16 | **客户端 trigger/selector/reposition 解耦** | `CachePolicy` 三个 callable 独立；缺省无操作，只有新消息才产生当前操作。[2] | W5 profile 同三分结构；测试 trigger=False 不调用 selector，repos 可独立触发，旧 operations 保留。 |
| 17 | **Turn/Token trigger** | Turn 按完成逻辑边界调度；Token 以渲染 prompt 减 hidden tokens，严格 `> threshold`。[2] | 阈值相等不触发；token counter 与端点 rendering 不一致时禁用 token policy，而非近似猜。 |
| 18 | **Turn/Token selector 与原子 tool batch** | 可保留最近完整 turns 或 retained-token budget；assistant 只有其 tool batch 全部 expired 时才可随目标过期。[2] | DWC 先只选 tool role；保护 user/system/约束/验证证据；多工具 batch 不半删，测试 tool_call_id 完整性。 |
| 19 | **Turn/Token reposition** | Turn 独立调度；Token 根据上次 repos 前已 compact tokens 与本轮新 hidden/selected 比较，不是简单 active token 阈值。[2] | repos 阈值独立评测；无新增可 compact 量不重复 repos；位置上限与 active cache 长度分别测。 |
| 20 | **cache-as-tool** | `DropContextTool` 只调度下一次请求操作，receipt 不是服务端确认；invalid id 整次调用失败，`read_result` 不重新执行工具。[2] | 模型工具仅条件候选；receipt 状态 `scheduled` 不可写 `applied`；fake receipt 篡改、重复读、非法 id 均测试。 |
| 21 | **连续性/digest 校验** | AKV 校验原消息 prefix、model/tools/chat_template/reasoning_effort/api_style、递增边界与不重复 drop。[2] | DWC 另加 provider route、tokenizer/template revision、tool schema version；branch rewind 必须新建 history，禁止复用旧 branch。 |
| 22 | **token ownership/render 一致性** | agent token policy 要用服务端一致 tokenizer/chat template/tools/thinking；需核 message 边界与 generation prefix。[2] | `counter_identity/status` 进 identity；远程模板不可见时只用 turn policy 或禁用，不从 provider usage 反推每条 message token。 |
| 23 | **usage 来自完成 read set** | `cached_tokens` 是驻留且实际读取且未转换；`repos_tokens` 是实际读取且转换；`drop_skipped_tokens` 排除历史修复 query；实现另有 actual prefill/decode。[2] | 原样保留 nested usage；三项不是账单，不相加成“节省”；provider 普通 cached tokens 与 AKV 计数分字段。 |
| 24 | **恢复与 usage 不矛盾** | drop 可在 KV 已驱逐时仍减少后续 query；先计算再 drop 的历史修复不算节省；恢复本身仍产生实际 prefill。[2] | 测试 `drop_skipped>0` 与 recovery 同时存在合法；不能据此宣称零 prefill 或零成本。 |
| 25 | **策略任务效果非普遍** | 论文有平均收益，也存在 xbench/BCP 不回退或回退；reasoning drop 消融更差，cache-as-tool 在 MiniMax 成本反升。[1] | W2 每任务/模型分层报告，reasoning drop 默认禁；模型工具轮次、token、成本全入账。 |
| 26 | **RSI cache policy** | 论文 20 BCP 优化、100 held-out，报告相对专家策略再降 7.1% 成本；不是 DWC 已验证协议。[1] | 只进化受控 policy 参数/代码，复用 W1/W2/W4，不另建 RSI 框架；父代保底、搜索成本入账、held-out 不参与生成。 |
| 27 | **支持矩阵是硬门** | 当前代码限定模型、RoPE/attention/KV/config；不支持请求在 API 拒绝，普通请求不走 Context 限制。[2] | capability 必须绑定 endpoint+model+runtime config+API schema+usage；任一 unknown 即不可生产启用，缺矩阵不能默认支持。 |

## 2. 必须写进总计划的语义精化

### 2.1 操作序列与 identity，不是一个“最终上下文 hash”

论文定义固定模型下 cache 由完整操作序列决定，而非只由当前 active token 集决定。[1] 拟建两个不同 id，禁止混用：

```text
CacheStateIdentity v1（拟建；物理状态等价所需）
  schema_version = 1
  provider / endpoint_family / requested_model / reported_model
  model_revision / revision_status                 # unknown 不伪造成固定 hash
  tokenizer_identity / chat_template_identity / rendering_version
  tool_schema_and_format_identity
  reasoning_and_template_options                  # 影响渲染时必填
  rope_and_position_config_identity               # 服务端不可见时 unknown，不能宣称兼容
  canonical_message_prefix_digest                 # 完整逻辑前缀，含 protocol 字段与 boundary metadata
  cache_operation_history_digest                  # 有序 trigger/drop ids/repos，含空操作规范化规则版本
  normalization_version
  cache_state_id = canonical_hash(above)

PairIdentity / EvaluationIdentity（另报告已有设计）
  另含 harness、decoding、task set、evaluator 等；不得因 cache_state_id 相同就复用任务评分。
```

规则：
- 操作历史是**有序累积指令**；`policy_version` 相同但产生不同 operations，cache id 必须不同。只改策略名而未改操作时，可以共享 cache state id，但候选/evaluation id 仍不同。
- `canonical_message_prefix_digest` 不能漏 assistant `tool_calls/reasoning_content`、tool `name/tool_call_id`、role、原始 content 顺序及逻辑 boundaries；AKV 的 digest 是可借鉴下限，不是远程模型权重身份的充分证明。[2]
- no-op 是否可归一删除必须单独定义 `normalization_version` 并做等价证明；第一版保守保留客户端实际操作序列，避免“看似无操作”错误复用。
- `unknown` 是显式值，不允许把空串、`latest`、路由别名当稳定 revision。远程 revision 不可见时，结果只绑定该次路由观测。
- 对话分支、编辑历史、重排消息、切换模型/tools/template、改变 reasoning rendering 后不得沿用旧 history；应创建新 branch id。AKV 客户端当前以拒绝连续性错误保护这一点。[2]

**最小无 GPU 测试**：构造 A/B/C 三例（C 计算后 drop A；C 前 drop A；无 A）；最终 active B/C 相同但 id 不同。再构造“D 前 repos 不同、最终位置相同”例；原 messages 任意一项变化；JSON 键序变化但语义相同；NaN/非 int/bool 冒充 id；跨 branch replay。全部可在纯 Python 测，不需要 AKV server。

### 2.2 Stateless interface 的正确职责分配

`AKV代码` 的 `CacheOperationHistory` docstring 明说它是 chosen instructions，不是 server acknowledgement 或 GPU data。[2] 因而拟建记录必须分：

```text
CachePolicyDecision（本地纯决策）
  decision_id / branch_id / policy_id / policy_version
  trigger_kind / selector_kind / reposition_kind
  candidate_message_ids / protected_message_ids / selected_message_ids
  decision_reason / evidence_refs / counter_identity / counter_status
  new_operations / cumulative_operation_history_digest

CacheRequestAttempt（实际线上事实）
  request_id / attempt_index / decision_id / cache_state_id
  cache_mode / wire_schema / extension_fields_sent[]
  request_payload_ref / request_sent_at
  response_status / rejection_class / response_ref

CacheObservation（服务端可见证据，未知不补值）
  policy_decided = true|false
  request_sent = true|false
  extension_fields_sent = true|false
  server_accepted = true|false|unknown
  server_acceptance_basis = explicit_schema|explicit_rejection|inferred|none
  usage_status = observed|partial|not_reported|malformed|unsupported
  cached_tokens / repos_tokens / drop_skipped_tokens = int|null
  actual_prefill_tokens / actual_decode_tokens = int|null  # 仅服务端实际提供时
  provider_cached_input_tokens = int|null                  # 不与上面 cached_tokens 合并
  residency_or_recovery_status = reported|not_reported
  behavior_verified = true|false                            # 只由独立固定评价填
  unsupported_reason / evidence_ref
```

`server_accepted` 只能来自协议明确的接受/拒绝证据，不能从 HTTP 200 或文本正常推断。没有 capability 时，`server_accepted=unknown/not_applicable` 必须按统一枚举定义；建议未发送时为 `not_applicable`，已发送但无确认时为 `unknown`。`behavior_verified` 不能由 usage 自动赋值。

### 2.3 Extended radix / eviction / restoration 是服务端验收项，不是 DWC 当前待办

`AKV代码` 的 `ContextLayout` 使用 token/delta/reposition records，且 shared boundary 先 drop 后 reposition；`ContextKeyData.match` 只有完整 TOKEN records 相同才计 KV 命中，事件不匹配不能误算后一 token。[2] `DropEvictionCandidates` 先弹 proven Drop heap，再普通 leaf；`proven_skip_ranges` 只允许 matched path 上的 Delta 授权释放祖先 KV。[2] `plan_recovery` 反向闭合“后续 live query 是否仍需要缺失 KV”的依赖，而非简单地从首个 hole 全部重算。[2]

因此总计划应写成**未来兼容服务的接口要求**，不是让 DWC 实现这些结构：
- exact match 必须包括 token、operation 和 position；可转换复用必须保留完整操作历史。
- 任何请求 drop 不得全局物理删除共享 KV；eviction 只释放物理内容，保留可恢复语义。
- 冷启动、部分驱逐、完全命中、源 position version 被驱逐，都不得改变请求语义；恢复是服务端成本，不是客户端“drop 失败”。
- 恢复只保证一次 model forward 的设计目标，不等于零 prefill、零 TTFT 或固定吞吐；`actual_prefill_tokens` 与恢复区间必须可观测后才可优化。
- 不要求当前实现 GPU serving，也不在 Windows 上移植 Linux/SGLang/C++20/Rust 运行时。可以用纯数据 fixture 检查 identity/usage/plan serialization，但不能标 serving verified。

## 3. Policy：trigger / selector / reposition / model tool 的可执行边界

### 3.1 当前可借鉴的规则组合

`AKV代码`：`TurnTrigger(after,every)` 只在新逻辑 turn 且 schedule 命中时选择；`TokenTrigger` 用 `prompt_tokens - hidden_tokens > threshold`。selector 可按最近完整 turn 数或 retained token budget 选择旧 tool messages；`TokenReposition` 与 drop selector 解耦，考虑上次 reposition 前已压缩的量。[2]

DWC 第一版只允许**声明式规则 policy**：
```text
CachePolicySpec（拟建，放 task_profiles.py 的受控 spec，不新增运行时框架）
  policy_id / schema_version / status=disabled|shadow|eligible
  trigger = {kind=turn|token|model_tool, after?, every?, threshold?, counter_identity?}
  selector = {kind=turn|token|model_tool, target=tool, retain_turns?|retain_tokens?}
  reposition = {kind=off|turn|token|model_tool, after?|every?|threshold?}
  protected_roles = [system,user]
  protection_rules_version / max_selected_per_turn / max_operations
  branch_reset_rules / unsupported_action=omit_and_mark
```

- 默认 `disabled`；`shadow` 只计算 decision，不改 payload；`eligible` 也只是允许进入受控 shadow，不表示生产 active。
- token counter 未验证时 `token` trigger/selector 不可用；模型/tokenizer/template/thinking/tools 任一不一致即 `counter_status=mismatch`。
- 默认 `target=tool`，不复制 `target=both/assistant`；论文 reasoning-drop 消融不支持 DWC 默认丢 reasoning。[1]
- trigger 只决定“是否考虑”，selector 决定“丢什么”，repos 独立；repos 不是降低 active KV 数量的替代品。
- 每 turn 操作数、候选数、policy 计算时间、cache tool 额外轮次均有硬上限；超限 `policy_status=budget_exhausted` 并保留 base，不静默截断后声称完整执行。

### 3.2 Selector 必须有任务证据保护，而非 K=12 照搬

K=12 是论文主实验设置，不是 DWC 默认值。[1] 每个 drop candidate 需结构化 reason 和可恢复证据：
```text
RetentionEvidence（拟建）
  message_id / role / tool_call_id / atomic_batch_id
  recency_rank / bytes_or_verified_tokens
  referenced_by_open_hypothesis / referenced_by_unresolved_failure
  contains_task_constraint / contains_final_verification / contains_source_identity
  superseded_by_message_id / duplicate_of_message_id
  original_artifact_ref / artifact_recovery_status
  decision=keep|drop_candidate / reason / rule_version
```

硬保留：system/user 原始要求、任务约束、最终交付契约、未解决错误及对应输出、当前假设依赖的来源/文件/数字、最终验证材料、原子 tool batch 的未完整过期部分、没有可恢复原文引用的证据。drop 只影响 active attention，不能代替 DWC 已有可恢复 head/tail 文本策略或 artifact 管理。

### 3.3 Model tool 不是“免费自主管理”

`DropContextTool` 的 receipt 为 `scheduled`，工具说明明确下一请求才生效；invalid ID 整次拒绝，`read_result` 对成功 receipt 与参数同时校验且不重新执行。[2] 论文 cache-as-tool 在 GPT-OSS BCP 分数/成本较好，但 MiniMax 因更多轮次成本由 5.4 升至 5.9 cents。[1]

拟建测试：模型自造不存在 id、已 hidden id、protected prefix id、future id、bool/float id、多余字段、超过 64 id、坏 JSON、receipt 被篡改、同 receipt 重读、多 tool calls 同 turn、成功 scheduled 但下一次请求未发送、服务端拒绝。工具调用、读取 receipt、下一次 request、server response 是四个独立事件。模型工具 prompt/schema/额外轮次全进 harness hash 和成本；未证明优于规则 policy 前不启用。

## 4. 当前远程端点 `unsupported` 的代码级契约

### 4.1 现状事实

`DWC现状`：`llm/client.py:398-415` 构造普通 chat body，只有 model/messages/max_tokens/temperature、可选 response_format/tools/reasoning_effort；无 cache capability、cache operation history 或扩展字段。`:488-545` 解析正文/tool calls 但不保存 `data.usage`；`:627-633` SSE 直接取首个 choice，无 choices 的 usage 末帧被跳过；`:654-662` fallback 成功重新构造 meta，丢 `fb.meta` 中 usage（未来补 usage 时必须一起修）。所以“远程已支持 AKV”没有任何当前代码证据。

### 4.2 四态 capability，而非布尔猜测

```text
CacheCapability（拟建配置/证据对象）
  capability_id / endpoint_family / requested_model / reported_model
  runtime_identity / runtime_revision_status
  wire_schema = none|akv_legacy_v1|akv_drop_rule_v1
  features = {message_drop, reposition, extended_rules, usage_details}
  support_matrix_ref / validation_ref / validated_at / expires_or_recheck_rule
  state = unsupported_remote|declared_unverified|shadow_verified|active_eligible
  unsupported_reason / prohibited_features[]
```

- 默认 `unsupported_remote`：不发送 `drop_message/drop_rule/reposition/cache`；可本地算 shadow decision，但 `request_sent=false`、`extension_fields_sent=false`、`usage_status=unsupported`；W2 不把该 decision 当已测 cache 候选。
- `declared_unverified`：运营方提供明确声明但未验证；仍不得发生产请求，只可准备 fake transport conformance。
- `shadow_verified`：在指定 endpoint/model/runtime 上明确接受扩展 schema，返回结构可辨的 AKV usage，且小规模固定任务独立评价完成；只允许受控 shadow 流量。
- `active_eligible`：还需支持矩阵、回退/回滚、成本账、held-out 与人工批准；不是自动状态，也不表示必须启用。

不得通过一次发送私有字段后“没报错”来升级。若提供方静默忽略未知字段，HTTP 200 恰好是危险假阳性；没有明确 usage/协议确认则仍 `declared_unverified`。

### 4.3 Client 最小扩展，保持旧调用者兼容

不建议现在复制 AKV transport；解冻后最小改法是：
1. 提取私有 `_build_chat_body(...)` 供 complete/stream 共用，增加**可选关键字** `message_history=None, request_extensions=None, capability=None`；旧 `prompt/system/images/tools` 路径原样。
2. 扩展合并器 `merge_cache_extensions(body, decision, capability)` 为纯函数：默认拒绝所有非空 cache 扩展；只有 capability schema 与 decision 匹配才返回新 dict，绝不原地污染重试 body。
3. 非 cache 扩展不在本任务放开，避免任意 `extra_body` 绕过；`request_extensions` 只接受明确 schema。`extra_body` 若未来支持，必须在合并后、发送前校验最终 payload，AKV agent 也要求 final HTTP payload 而非 SDK 未合并形式。[2]
4. retry 捕获 `final_body_digest/operation_history_digest`，递归重试必须复用同一 final body；不可在 retry 重新跑 selector。stream→complete fallback 同样透传 tools、capability、final extensions，当前 stream 本就没有 tools，不能把 cache 单独接成第三套语义。
5. 保存每次 attempt 的请求扩展字段名和原始响应 usage 引用；HTTP/parse/empty/reasoning_only/tool_calls 成功各路径都保留。禁止凭证、完整敏感 prompt 进 metrics。
6. 服务端明确 4xx 不支持：记 `rejected_unsupported`、该 request 失败，**不自动去字段重发**。去字段重发会改变实验条件、重复计费并混淆“cache 生效”；只有任务层另建显式 `ordinary_fallback` attempt，带 parent id、独立成本与 `cache_mode=ordinary_fallback` 才可恢复用户任务。

### 4.4 不支持时仍允许做什么

- 运行纯规则 policy 的 offline/shadow 决策，记录“若支持会选什么”，但不生成线上效果、usage 或成本节省。
- 保留现有普通 full-context、文本 compaction、可恢复 head/tail baseline；其指标标 `context_mode=text_compaction`，不是 cache drop。
- 收集普通 provider `usage.prompt_tokens_details.cached_tokens`，但标 `provider_cached_input_tokens`，不可当 `drop_skipped/repos`。
- 用 fake transport 做协议测试、用论文公开数据作研究依据；两者都不能升级为 `shadow_verified`。

## 5. 条件性未来扩展验收（无 GPU 也可先完成的契约测试）

### 5.1 单元/属性测试（拟建，未执行）

**`tests/test_cache_identity.py`**
- A/B/C 操作时机、repos 时机、position version、model/render/tools/branch 改变均不碰撞；语义相同 JSON 键序规范化一致。
- messages 完整保留，drop ids 排序去重，trigger 严格递增，future/重复/负值/bool/int64 越界拒绝。
- no-op canonicalization、history 序列化 round-trip、unknown revision 不伪造稳定性。
- cache_state_id 相同不意味着 evaluation id 相同。

**`tests/test_cache_policy.py`**
- trigger false 不 select；threshold 等于不触发；turn schedule after/every；repos 独立；累积旧 operations 不丢。
- 最近完整 tool batch；多 tool result 原子性；protected messages 永不选；未解决失败和 final evidence 保留。
- token counter mismatch 禁用 token 规则；policy budget 超限显式 unknown/base。
- cache tool receipt scheduled≠accepted；无效调用无部分操作；read_result 无副作用。

**`tests/test_cache_capability_unsupported.py`**
- 默认/None/unknown/declared_unverified 均让 outgoing body 不含 cache keys，旧 body 与当前完全一致。
- shadow decision 存在也不发送；metrics `unsupported_remote` 而非 success。
- supported capability 与 wire schema 不匹配 fail closed；model route 改变使 capability 不命中。
- fake 200 静默忽略不能升级；fake 明确 400 记拒绝且不隐式 stripped retry；普通 fallback 独立计费。
- non-stream/stream/fallback/retry 所有路径 operation digest 一致、扩展不丢、不重复。

**`tests/test_cache_usage.py`**
- 完整 nested usage、缺 usage、null、字符串数字、负数、超 int、部分字段、无 choices SSE 末帧、流式中途失败+fallback。
- 保留 `cached/repos/drop_skipped` 原值与 coverage；unknown 不补 0；三类 token 不相加为节省或 USD。
- `drop_skipped>0` 且 `actual_prefill>0` 合法；repos 是读取转换量，不是输出 token，也不自动按 cache-hit 价计费。
- 多次 attempt、cache tool 额外轮次、summary/revision/diagnosis 全归任务总账；usage raw 与账单 estimate 分来源。

### 5.2 只有未来有兼容服务时才执行的 serving 验收

不要求现在实现，也不得以这些未执行项宣称完成：
1. **语义等价**：相同完整操作序列在全冷、全命中、随机逐出、不同并发下输出分布在固定协议下等价；保留 trace 与统计不确定性。
2. **历史隔离**：A/B/C 和 reposition-divergence fixtures 共享 token prefix 但不共享错误后代 KV；一个请求 drop 不影响另一请求。
3. **恢复正确性**：随机 residency mask 下，恢复 query 的 visible set 与操作序列一致；历史段可读后来 drop 的 KV，后续段不可读；repos 恢复各阶段原位置。
4. **usage 对账**：由独立 query/read-set fixture 手算 cached/repos/drop_skipped/actual prefill，包含 recovery、SWA（若服务声明支持）、PD transfer；服务返回值不得由请求参数直接回显。
5. **eviction 生命周期**：active computation/restoration pin；drop-first；空占位后代可定位；position 源/目标版本独立回收；并发无 use-after-free。
6. **性能另测**：固定 trajectory replay、并发、硬件与模型，报 TTFT/TPOT/P95/input/output throughput/recovery；论文 1.18×/1.51× 不是验收常量。[1]

## 6. W1–W5 的 RSI 缓存策略与评价门

### 6.1 候选空间

W4 只生成白名单 policy：turn/token trigger、tool-only selector、独立 repos、可选 model tool；每次候选含 `policy_id/parent_id/intent/diagnosis_refs/spec_diff/capability_id/counter_identity/search_cost_refs`。不进化 evaluator、任务集、支持矩阵、服务端配置，不允许候选自己声明 capability。

三意图示例：
- `cost-first`：较早 turn trigger、较严格 retained budget，但证据硬保护不变。
- `balanced`：保留更多 unresolved/final evidence，按已验证 token counter 调阈值。
- `performance-first`：drop 更保守，可 full-context/only-repos/no_change；不是“所有消息都 drop 更少”换名复制。

`no_change`、当前普通 context baseline、full-context（位置允许时）、当前 Standard-like compaction 都入池。K=12、48K/96K、20/100 任务数只能作为论文实验参照，DWC 通过 W1 长度分布与成本校准。[1]

### 6.2 搜索/评价/held-out 纪律

- dev 上多 rollout 诊断与候选生成，固定 validation 做选择，held-out 只最终一次独立验收；不能把 20 个优化任务的表现或 best generation 直接当泛化。
- 每候选同 model route、model/render identity、harness、tool schema、decoding、task set、evaluator、capability/runtime；不同 runtime 的成本不直接比。
- 先 correctness/infra/invalid 三态与 baseline 性能门，再 performance/cost Pareto；低 token 不能补偿准确率回退。每模型×任务分层报告，不只报平均。
- 成本包括主 agent、summary、cache tool 额外轮次、policy 生成/评价/诊断、失败/拒绝/普通 fallback。repos 计费采用实际 provider 账单；若仿论文按 cache-hit 保守估计，必须标 `pricing_assumption`，不能写成真实账单。[1]
- usage coverage 不完整则 cost `undefined/not_comparable`，不能补 0；任务 pass 不可从 cache usage 推断。
- incumbent 永远在最终池；无合格候选 `no_update`。policy RSI 只产生受控 shadow candidate，仍过 Probe、独立复评、人工批准和回滚，不自动 ET.apply。

### 6.3 建议最小证据报表

```text
CachePolicyEvaluation（拟建）
  policy_id / parent_id / pair_id / evaluation_protocol_id / capability_id
  split / task_set_digest / rollout_count / completion_status
  pass_rate / per_task_scores / latency / rounds / invalid / infrastructure
  logical_input / active_input_reported / output / reasoning tokens + coverage
  provider_cached / akv_cached / repos / drop_skipped / actual_prefill + coverage
  cache_tool_calls / summary_calls / recovery_observed / fallback_attempts
  billed_cost_estimate / pricing_version / pricing_assumptions / search_cost
  baseline_comparisons / per_model_task_regressions / evidence_refs
  decision = incomparable|reject|shadow_candidate|eligible_for_heldout
```

`logical_input` 可包含已 drop token；论文 input throughput 也如此计数，故它不等于实际计算量。[1] active input、actual prefill、provider billed input 必须分栏。

## 7. 支持矩阵与限制（提交级，不得泛化）

`AKV代码` `capabilities.py` 是硬校验来源；README 是较粗公开说明。以下按代码补齐容易漏掉的限制：[2]

| 维度 | 当前 AKV Context Drop/Reposition 条件/限制 |
|---|---|
| 模型 architecture | `QWenLMHeadModel`、`Qwen2ForCausalLM`、`Qwen2MoeForCausalLM`、`Qwen3ForCausalLM`、`Qwen3MoeForCausalLM`、`GptOssForCausalLM`、`MiniMaxM2ForCausalLM`；只列 model family 不够，需 resolved architecture。 |
| 模态/精度 | text-only、非 multimodal，模型 FP16/BF16；未量化 FP16/BF16 KV（`auto/float16/bfloat16`）；query KV scale 也不可存在。 |
| RoPE/attention | 不支持 DualChunk RoPE；MiniMax 要 full attention、合法 even partial RoPE；native causal MHA/GQA，非 cross-attention；绑定需 native NHD KV、合法 rotary、同 device/layout。 |
| backend/page | `page_size=1`；prefill 和 decode 均须 `triton/flashinfer/fa3`；FA4 代码注释明确尚需硬件验证，不能因 adapter 存在算支持。 |
| 并行/调度 | TP 可；PP/CP/DCP=1；非 speculative/dLLM；不支持 deterministic batch-invariant attention；beam width>1 不可。 |
| cache/adapter | 不支持 HiCache、external linker、HiSparse、LMCache、FlexKV、session radix、非 native unified radix backend、LoRA、session KV reuse、input embeds/mm input；需原始 input_ids。 |
| PD | 仅 Mooncake；不支持 staging buffer、KV offload、KV checksum；prefill/decode worker 必须相同 system revision。 |
| API rules | legacy `drop_message` 与 `drop_rule` 不能同时给；reserved internal fields 拒绝；message/text/keep-text/thinking drop 各有 grammar，不代表所有远程 AKV 声明都支持扩展 rules。 |
| 平台/构建 | system 需 SGLang 运行环境、Rust/Cargo、C++20 CPU JIT warmup、可写编译 cache；agent 包本身仅 stdlib、可无 GPU，二者不可混为“已验证系统”。[2] |
| 论文限制 | 更多策略、在该 scheme 下训练 agent、linear attention 支持是 future work；不能宣称任意 attention 架构可用。[1] |

**矩阵失效即重新验证**：endpoint、模型 architecture/revision、tokenizer/template、backend、page/KV dtype、parallel/PD、LoRA/session/speculative/beam、wire schema 任一变化，capability 不命中。普通无 Context 请求不受这些限制，但那不是 Context 支持证据。

## 8. 总计划应补的关键句与禁止项

### 8.1 建议直接吸收的关键增补

1. “AKV 条件扩展第一交付是 identity/capability/observation 契约与 unsupported 测试，不是 GPU serving；默认远程不发送 cache 扩展字段。”
2. “cache identity 必须覆盖完整逻辑前缀与有序 drop/repos 历史、模型/render/tools/RoPE 配置；最终 active token 或文本 hash 不足。”
3. “保留 KV 无需重 prefill，不等于物理 cache 丢失后无需恢复；恢复成本、实际 prefill 与 drop skipped 分开计量。”
4. “usage 缺失是 unknown；cached/repos/drop_skipped 不相加成账单或节省；普通 provider cache usage 不冒充 AKV evidence。”
5. “policy_decided/request_sent/server_accepted/usage_observed/behavior_verified 五级证据独立；HTTP 200 和工具 scheduled receipt 都不是服务端生效证明。”
6. “selector 默认 tool-only、原子 batch、证据可恢复；K=12 不照搬，reasoning drop 不默认，cache-as-tool 的额外轮次全入账。”
7. “RSI 只进化受控 cache policy，复用 W1/W2/W4 固定协议和 Pareto；当前 unsupported 不允许作为线上候选，也不自动落地。”
8. “支持矩阵绑定具体 runtime/config；未列模型、量化 KV、多模态、session/LoRA/speculative 等不得默认支持。”

### 8.2 禁止项

- 禁止现在引入 AKV system/SGLang/CUDA 为 DWC 依赖，禁止把 GPU serving 列为 W1–W5 前置。
- 禁止把 drop 当摘要、trim、隐私删除或物理 eviction；禁止把文本 token 减少直接当 KV 节省。
- 禁止在 capability unknown 时发送扩展“试试看”，失败后静默 stripped retry；禁止仅凭 OpenAI compatibility、HTTP 200、模型名宣称支持。
- 禁止仅用最终 messages hash、prefix cache hit 或客户端 history 证明 KV 正确复用。
- 禁止把 `repos_tokens` 当输出、把 `cached_tokens` 当全部命中、把缺失 usage 当 0；禁止按论文价格假设生成伪真实账单。
- 禁止默认丢 user/system/任务约束/未解决失败/最终验证证据，禁止半删 tool batch，禁止让模型工具 receipt 绕过服务端证据。
- 禁止把论文平均 27.7%、1.7 分、RSI 7.1%、1.18×/1.51× 当 DWC 预期承诺；其模型、任务、价格、硬件与协议均特定。[1]
- 禁止以 fake transport/纯 Python 测试声称 extended radix、drop-aware eviction、segment-batch attention 或吞吐已验证。

## 9. 最小落地顺序（解冻后，仍条件性）

1. **W1**：先实现 usage 全路径捕获与 `CacheObservation`；默认 unsupported 测试全绿。此步无 AKV 请求行为变化。
2. **W1/W3**：实现 CacheStateIdentity 与 policy shadow decisions，接入 task metrics/diagnostics；只离线分析，不进线上选择。
3. **W5**：声明式 turn policy、证据保护、capability registry 纯配置；token/model-tool 等 counter/协议未齐时保持不可用。
4. **未来有明确兼容端点**：fake conformance → 小样本明确 schema/usage 验证 → dev 固定评价 → W2 Pareto → held-out/人工批准；任何一步失败回 unsupported/base。
5. **未来 serving 若另立项目**：才验 extended radix/eviction/restoration；不是当前 DWC 实现范围，也不由本清单要求交付。

## Sources

[1] https://arxiv.org/html/2610.28577v1
[2] https://github.com/thu-nics/AKV/tree/c567a429a058f1abce3b2879e69978b09e0fda4c
