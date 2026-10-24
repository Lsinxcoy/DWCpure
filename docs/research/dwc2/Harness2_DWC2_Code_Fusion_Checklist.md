# Harness² → DWC pure 2.0 完整代码级融合清单

> 研究/设计产物，不是实现。未修改 DWC 的 `src/scripts/config/tests/var`，未解除冻结，未运行真实模型 benchmark。
>
> 代码事实基线：Harness² `1cfe254e8d25b15f37048c3730134686abe60335`；DWC `5769a125d1a370f9b3fc2c41d0d2fcbeef6d095e`。
>
> 本文所有“拟建/扩展/接入”均为 DWC 2.0 待实施设计，不表示当前已存在。W1–W5 顺序不变，不新增 W6，不让 AKV/模型训练成为前置。

## 0. 融合总判定

Harness²应补成一条受约束的证据链，而不是再建一套 evolver：

```text
W1 全角色真实计量
  → base 同题多 rollout
  → W3 invariant/domain × correctness/waste/instability 诊断
  → W4 intent × scope 稀疏候选 → 静态防护 → 同题 Probe
  → Compose（合并/撤销/恢复旧检查点/KEEP_CURRENT）
  → 原始 base + 全部检查点进入 W2 固定评价与 Pareto
  → shadow/held-out/人类批准后才可落地
  → 只把有执行对照的可复用经验写入 library；否则 NO_ENTRY
```

最关键的五项硬修正：

1. **Harness²发布版 finals-only selector 没有 base；DWC 必须反向修正为原始 base 强制在池。**
2. **Probe 只证明行为差异，不证明 pass/verified improvement；Compose/adopted 也不是验证。**
3. **DWC 现有 `pipeline.py` 只记赢家且缺逐编辑 Δ 时均摊；必须补全陪跑、混杂和不可归因状态。**
4. **DWC 当前 `gates.py` 将 held-out 缺失从 `accept=blocked` 映射为 `not_applicable`；2.0 的自动采纳门必须改为缺独立评价即 blocked。**
5. **rubric 防污染不能只做现有 diff 字面筛查；要封住任务源、轨迹、交付物、library、缓存、网络下载和 selector/reflection 全证据面。**

---

## 1. 组件树与可编辑面（H2-01～H2-12）

| 编号 | Harness²代码事实与可借鉴机制 | DWC 拟建/扩展文件与代码契约 | 最小测试建议 |
|---|---|---|---|
| H2-01 | `core/tree.py:SurfaceSpec` 把组件路径、always-on、上限、frontmatter、hook 规则数据化；共享逻辑只写一次。 | 扩展 `organs/evo_targets.py` 为组件 manifest；只登记有真实 consumer 的组件，不复制 OpenCode/Codex 的路径、24k/8k 上限。`agent_harness.Policy` 继续承载数值策略面。 | `test_evo_targets.py`：每组件有 consumer/schema；无消费者拒绝登记；非法上限拒绝。 |
| H2-02 | 8 类组件是 system prompt、guardrails、memory、tool guidance、subagents、skills、scripts、plugin。 | 建立明确映射：c1 `llm/prompt_ota.py`；c2 `organs/hook.py`+规则产物；c3 `organs/memory.py`/`agent_quality.py`；c4 `evo_targets.context_mgmt/client_tool`；c5 `evo_targets.subagent`+`caps/registry.py`；c6 `organs/skill_store.py`+`var/dwc_skills`；c7 沙箱脚本候选；c8 `organs/hook.py`+`harness/agent_harness.py` 的执行钩子。**不得把 AgentHarness 的 8 个 hook 点误称为 Harness²的 8 组件。** | `test_h2_component_manifest.py`：8 类逐一映射到 consumer；同时断言 hook-point 数与组件数是不同概念。 |
| H2-03 | `normalize_rel/is_allowed/read_tree` 只接受白名单相对路径并拒绝 `..`/绝对路径；越界面文件被报告，不静默应用。 | 新 `harness/component_manifest.py` 或并入 `evo_targets`：候选 patch 路径规范化、白名单、越界显式拒绝；生产根与 shadow 根分开。 | 绝对路径、`..`、反斜杠逃逸、symlink 越界、运行时自生成文件均拒；合法文件可读回。 |
| H2-04 | omitted-is-inherited：只读回编辑树，未编辑组件继承；`write_tree` 先清可编辑旧文件再精确落地。 | 在 `applier.apply_on_copy`/候选副本实现“sparse patch + parent snapshot → materialized candidate”，删除必须显式表示，不能把“未提交”误当“删除”。 | 未编辑继承、显式删除、覆盖、新增四例；shadow 不改生产；父快照不可变。 |
| H2-05 | `validate` 一次列出全部问题，含 always-on cap、frontmatter、subagent、脚本编译、hook schema、脚本引用；错误文本回喂一次修复。 | 把检查放到 Probe 前的 `candidate_bridge`/静态门；复用 `ProposalGate` 与 `evo_targets.validate`，新增组件级检查但不另造一套相互矛盾的规则。 | 单候选含多错时全部返回；invalid→一次带错误反馈 retry→再失败回退父代；成本照计。 |
| H2-06 | skill 必须有 description/name，且名字出现在 always-on 才不是“死技能”；引用脚本必须随包携带。 | 扩展 `organs/skill_store.py`：`save` 时校验目录名、frontmatter、trigger、脚本引用；`load_all` 对坏文件不得无声跳过；保留现有 token/中文召回，不把 Harness² trigger-line 机械照搬为唯一召回方式。 | 无 description、name 与目录不一致、无 trigger、缺 helper、坏 frontmatter均显式失败；合法技能可被选择。 |
| H2-07 | subagent 适合“大输入、小输出”的独立上下文任务；不支持 subagent 的 deployment 拒绝。 | `caps/registry.py` 与 `config/subagent_policy.json` 增加 capability 声明；候选不得在不支持的运行时新增 subagent。将额外 episode 成本归到该候选。 | 不支持时拒绝；支持时检查独立上下文/返回值；subagent LLM/工具账进入 task/candidate。 |
| H2-08 | script/hook 是确定性或工具环内杠杆，不只是提示词；hook schema 不对会静默失效，因此先验证。 | `organs/hook.py` 保持 8 hook 协议与只读点；候选 c7/c8 只能进入受控 shadow 沙箱，schema、允许事件、超时、非交互、写权限逐项校验，禁止任意生产注册。 | 非 JSON、未知事件、空 command、只读 hook 写入、危险命令、超时均拒；合法 hook 真实触发。 |
| H2-09 | always-on 文本每次运行都付费；on-demand 组件按需付费。prompt 建议“新增必须削减别处”。 | W1 在组件 manifest 记录 `activation_mode=always_on/on_demand/tool_loop`、`static_chars`、实际 activation 次数；W3 诊断冗余提示，W4 cost-first 优先去冗余而非删必要验证。 | 同候选增删文本可重建 delta；on-demand 未触发不计静态注入；不能因 cap 达标就宣称性能改善。 |
| H2-10 | `diff_summary` 记录 added/removed/modified/always_on_char_delta；`diversity` 用 line-Jaccard 显示候选坍缩。 | 新 `harness/candidate_diff.py` 或并入 `candidate_bridge`：结构化 diff 和 edit lineage；候选相似度只作诊断，不作质量分。 | 增删改准确；完全相同/全不同/空树边界；Jaccard 不进入 Pareto 分数。 |
| H2-11 | substrate/materialise 安装模式改变会移动 base，不能暗中切换。 | run identity 必须包含 `component_snapshot_hash`、prompt OTA 版本、工具/consumer 配置和运行时能力；切换安装/渲染方式即新 base，不与旧分数混合。 | 同内容不同安装模式生成不同身份；报告标 incompatible，不重用到旧 base。 |
| H2-12 | `BenchmarkAdapter` 将 method/substrate/benchmark 分离；任务、执行、轨迹、交付物、base、validate、score 是不同接口。 | 不引入三 benchmark 适配器；抽象 DWC 自己的 task runner seam：任务材料、执行、行为轨迹、agent-authored 交付物、固定 evaluator 分通道提供。 | fake adapter 能替换真实 runner；方法模块无法从 task adapter 直接取得 val/golden。 |

## 2. Propose / Probe / Compose 与证据（H2-13～H2-25）

| 编号 | 机制与代码证据 | DWC 文件/契约 | 测试建议 |
|---|---|---|---|
| H2-13 | 先跑参考 harness，再改；没有参考执行和 probe 的直接编辑在论文消融中退化。 | `harness/loop.py` 的 W4 入口要求 `base_rollout_refs`；无真实 base 只能生成 `needs_measurement`，不能成为可采纳候选。 | 无 base 阻断；只有文本提案无 probe 不得标 shadow_verified；有 base 才可进后续。 |
| H2-14 | invariant/domain 是作用范围，与 DWC 三优化意图正交。 | W3 诊断增加 `scope=invariant/domain`；W4 候选增加 `intent=cost-first/balanced/performance-first`，只生成有证据的 intent×scope 格子，不机械凑 3×2。 | 同一诊断可映射不同 intent；空格子不产候选；INV 不写领域事实、DOM 不修工具流程的契约测试。 |
| H2-15 | Propose 优先修 divergence，其次重复具体失败，最后才是未实现风险；每编辑引用轨迹时刻。 | 新 `harness/contrast_diagnosis.py`：`evidence_refs[]` 指向 rollout/event interval；优先级可审计，不接受“最佳实践”作为唯一 grounding。 | divergence、全基线重复失败、单次偶发、纯猜测四类；单次偶发不得被描述成稳定根因。 |
| H2-16 | `context.build` 将 task/source/rollouts/deliverables/harness/library/pool/decisions 以文件证据树提供；mission 只列实际落地的内容。 | 新 `harness/evidence_bundle.py` 统一 manifest：每个 requested ref 记录 `materialized/withheld/failed/reason`；不能让 proposer 看到“存在”但实际缺失的引用。 | 缺失 trajectory、names-only、withheld、library 空、pool 空均有准确 manifest；全 trajectory 读取失败则 fail closed。 |
| H2-17 | 全轨迹事件不因 prompt 预算整体截断；单个 observation 的 renderer truncation 是工具标记，不是 solver 缺陷。 | W3 保存原始 event refs，给模型摘要+可定点读取；所有截断带 `origin=renderer`、`omitted_count`，不得把截断标记归为 harness 失败。 | 长轨迹仍有首尾/区间可查；截断标不触发 failure signature；缺 usage 不生成成本归因。 |
| H2-18 | 候选必须真实 Probe 后 Compose 才看到行为后果；pool 含 harness diff、rollout、produced、decision notes。 | 新 `harness/probe_candidates.py`：同任务、同 solver/model/环境运行 shadow；写 `probe_id/parent_id/candidate_id/run_id/behavior_ref/delivery_status/metrics_ref`。 | probe 与 candidate hash 绑定；换候选不复用旧 probe；环境失败与任务失败分栏。 |
| H2-19 | 行为改变、交付、任务通过、采用、验证是不同事实。 | `candidate_metrics.py` 定义独立字段：`behavior_changed`、`delivered`、`task_pass`、`adopted`、`verified_improvement`；禁止布尔隐式推导。 | 行为变但 fail、deliver 但 judge None、adopted 但未 held-out、verified 必须有固定协议，各例不串状态。 |
| H2-20 | Compose 可 merge、整取、修订、丢弃、KEEP_BASE；重叠要解决而非拼接；无交付候选编辑默认不安全。 | 新 `harness/compose_candidates.py`：只操作候选副本；保留每行/每组件 lineage；无交付编辑需显式风险依据；组合后重新完整静态验证+Probe。 | 合并冲突、同组件两版本、无交付编辑、删除必要验证、组合后出现新错误均正确处理。 |
| H2-21 | `kept_base` 来自真实 diff，而非仅相信模型写 `KEEP_BASE`。 | `no_change` 由 materialized candidate 与 parent content hash/diff 决定；`KEEP_BASE` 文本只是 note。串行中命名为 `KEEP_CURRENT`，避免误解为恢复原始 H0。 | 模型说 KEEP 但树变了→不算 kept；模型没说但树相同→kept；串行保持 C_t 不等于恢复 H0。 |
| H2-22 | 无效提案允许一次修复，之后继承 fallback；异常/空返回不能静默变成成功编辑。 | `StageResult` 增加 `fell_back/error/attempts/cost_ref`；fallback 保留父代并显式标记，不生成 pseudo improvement。 | context build 失败、transport 失败、empty harvest、off-surface、静态失败分别留痕；fallback 不进入“改进有效”统计。 |
| H2-23 | Compose notes 要求 `kept/revised/dropped -> edit -> evidence`。 | `evo_proposals.py` 扩展 decision record：每个被接纳/拒绝 edit 都有证据和原因；不要只存最终 prose。 | rejected candidate 的 edit 仍可审计；无证据 decision 拒绝进入 library；note 与结构化 lineage 一致。 |
| H2-24 | k 个 base 是同一分布的集合，不是 k 个独立故事；候选单 rollout 是弱证据；同模型共识不独立。 | W3 `sample_size/base_pattern_count/probe_count/shared_model_bias`；Probe 可指导 Compose，但 verified 必须走 W2 多 rollout 固定评价。 | 1/k 失败不能写成稳定；候选一次成功不能直接 verified；多个同模型一致不增加独立证据等级。 |
| H2-25 | 交付物形状属于用户请求，不属于 harness；不能把推理痕迹/额外列/改名包装成优化。 | 静态/运行时 contract 增加 deliverable schema 保护；复用 `organs/contract.py` 与任务真实要求，禁止候选改 evaluator 来适配。 | 额外列、改文件名、placeholder、公式代值、说明代替计算均判 contract 违规；禁止改质量门。 |

## 3. 并行、串行、selector 与最终保底（H2-26～H2-36）

| 编号 | 机制与代码证据 | DWC 文件/契约 | 测试建议 |
|---|---|---|---|
| H2-26 | parallel：k base→2k scoped candidates→k 独立 Compose，使用同一证据池；扩宽度。 | 新 `harness/improvement_schedule.py`：`mode=parallel/sequential` 只控制 W3/W4 shadow 搜索；不替代 W5 画像。按实际产生格子计算预算，不硬套 R=4k/P=3k。 | k=1/2 标签、父代、pool、实际预算一致；证据稀疏减少格子时不报假 R/P 达标。 |
| H2-27 | sequential：每轮 INV/DOM+Compose，编辑当前 checkpoint，携带历史；可恢复旧 checkpoint 或 rejected edit。 | 同上：`current_checkpoint` 与 `original_base` 分开；历史含 candidate+probe+decision；允许恢复 C_j，不强迫单调变化。 | C1→C2 父链正确；恢复 C1 后 hash 一致；旧 rejected edit 可凭新证据恢复；H0 永不丢。 |
| H2-28 | k=1 时 parallel/sequential 是同一过程，分数差是 noise floor。 | 实验报告增加同过程对照与重复 seed；任何 k>1 增益需超过 k=1 双跑噪声和置信区间，不能只看均值。 | 构造同 fake seed 两模式计划相同；不同随机差仅记 noise，不写 verified gain。 |
| H2-29 | 并发执行后按调用顺序记录 ledger，避免完成顺序影响账本；各阶段独立 labels。 | 所有并行 probe/stage 返回后按 canonical label 排序落账；运行可并发，证据顺序确定。Windows 不复制 `fcntl` 实现。 | 扰动完成顺序，最终 JSONL 顺序一致；同 label 重复立即报错；无覆盖。 |
| H2-30 | `assign_ids` 先 canonical sort 再 seeded shuffle，匿名 id 可复现；selector 只选已有交付物，不合成答案。 | 可选 `harness/artifact_selector.py` 仅作 shadow triage：`selector_seed/protocol_version/anonymous_map` 私密保存，selector 看不到 parent/intent/cost/harness。 | 同输入同映射；不同 seed 可复现；选择 id 必须在池；输出不能是新文本。 |
| H2-31 | `_render_pool` 丢弃无交付/空渲染并记录 dropped；可 state task 才用 trajectory evidence。 | 候选参与模型 triage 前检查 delivered/renderable；但 delivered 不是 pass。状态型任务需显式 `deliverable_kind=state`，不能默认用轨迹代替文件。 | 无交付、空交付、渲染异常全留 dropped；state/artifact 不错用；drop 不静默消失。 |
| H2-32 | **发布代码 `selection_pool` 明确只含 agg1..aggk/c1..ck，`del base`，无 abstention。** | W2 `pareto_select.py` 必须构造 `{original_base} ∪ finals ∪ checkpoints`；base 缺失 raise，不得按字典序首个 final 兜底。 | base 最好/最差/同分均在池；任何选择不差于 base 的保底前提可断言；base 缺失 fail closed。 |
| H2-33 | selector 失败优先 delivered base，否则 finals 时取第一个；k=1 trivial 直接交付唯一 final。 | DWC selector 失败回退 `no_change/original_base` 并标 `selector_fallback`；k=1 也不能绕过 W2 固定评价和 base 比较。 | selector transport/无效 id/空池/无 base 各例；k=1 退化时不得淘汰 base。 |
| H2-34 | agentic selector 有共享偏差，选择只是 adopted，不是 verified optimal。 | 最终选择权留在固定 evaluator+Pareto；模型 selector 只能作为待校准 shadow 信号，且自身 token/延迟入账，不能覆盖 baseline/held-out。 | 模型偏爱更长/更复杂候选时仍不能越过性能保底；selector 与 Pareto 冲突有报告。 |
| H2-35 | DWC 现有 `replay.select_policy/shortlist_candidates` 已强制 current 在池，是可直接复用的保底约束。 | 新 Pareto 池复用“current 必含”不变量，并扩展到 `original_base`；`select_with_val_fallback` 的 val tie/empty 只作诚实降级，不得把 search fallback 写成独立验证。 | 保留 `test_r117_hce_split.py`，新增 original_base≠current 场景；val tie/empty 标 source，不宣称 held-out verified。 |
| H2-36 | **DWC `gates._g4_split` 当前把 held-out 缺失映射为 NA，链可 `applicable_passed_with_na`；这不满足 2.0 自动采纳。** | 解冻时给 W2 增加严格模式：`independent_evaluation_required=True` 时缺 held-out/usage/evaluator version→`blocked`，保留旧三态仅作历史观察兼容，不用于自动落地。 | 缺 val 必 blocked 且 landing 拒绝；旧测试可保留 legacy 观察，严格模式与 legacy 明确隔离。 |

## 4. Reflection / library / confounded / NO_ENTRY（H2-37～H2-47）

| 编号 | 机制与代码证据 | DWC 文件/契约 | 测试建议 |
|---|---|---|---|
| H2-37 | reflection 读完整改进记录和 base diff，不只读最终答案；被采用候选不是唯一证据， rejected candidate 也可能含有益 edit。 | 新 `harness/reflection.py` 或扩展 `agent_quality.py`：输入 base、全部候选、probe、compose decisions、selector 记录；不能只传 winner。 | rejected candidate 的有效 edit 可形成经验；winner 内无贡献 edit 不得自动记 helped。 |
| H2-38 | 每 edit verdict ∈ helped/hurt/no observed effect/confounded；多组件或单 rollout 优先 confounded。 | 新结构化 `EditEvidence`：`edit_id/component/candidate_refs/change/contrast_refs/verdict/confounders[]/sample_size`；verdict 由协议和数据校验，不只靠 prompt。 | 多 edit 同候选且无隔离→confounded；单 probe→至多少 evidence；有独立对照才可 helped。 |
| H2-39 | adoption 不证明 edit helped；选择交付物时 harness 隐藏，更不能反推组件因果。 | `adopted` 只表示选择结果；`credit` 不把 winner 的 Δ 直接分给每个 edit。经验写门要求 contrast，而非 winner 身份。 | winner-only 数据不得写 helped；`a_i=1` 与 `edit_verdict=helped` 不可互相赋值。 |
| H2-40 | **DWC `pipeline.py` 当前只记赢家，且逐 edit Δ 缺时把整候选 Δ 均摊。** | 修改设计：补 `admissible_but_lost` 的 a=0 记录；ΔS/ΔC 无隔离时保留 candidate-level 值，edit-level 设 `unallocated/confounded`，**禁止均摊伪装成精确归因**。保留旧七元组兼容，可用 versioned sidecar，不强改旧 `LEDGER_FIELDS`。 | 两候选一赢一输都有账；多 edit 缺独立 Δ 不产生均摊数；旧 `test_r155_credit.py` 不破坏。 |
| H2-41 | `cue/lesson/evidence` 三非空才有经验；`Library.add` 无经验返回 None；confidence 可选但不能替代证据。 | `agent_quality.record_lesson`/`consolidate_skills` 前加统一 `ExperienceEntry` 写门；必填 `cue/applicable_scope/component/operation/supporting_contrasts/evaluator_version`。 | 缺任一必填不落盘；空 cue、泛泛“be thorough”、仅 adoption evidence 均拒。 |
| H2-42 | 只基于 confounded rows 的 lesson 是猜测；没有可复用执行对照写 `NO_ENTRY`，edit rows 仍可保留。 | `NO_ENTRY` 是一等结果：不写 skill/library，但可写 append-only 本轮审计；reflection 失败同样不写库且成本照计。 | NO_ENTRY、reflection transport failure、重复 resume 后库仍为空；审计行存在且没有伪经验。 |
| H2-43 | library 存 adopted 完整组件树+经验；DWC 不应整体遗传任务定制 harness，应复用组件和“何时/为何有效”证据。 | 不复制整套 Harness² library；在 `skill_store`/lessons/产物注册表上增加 `source_component_ref/source_harness_ref/evaluation_version/evidence_refs`，新任务仍从当前 H0 开始。 | 新任务默认 snapshot 不含旧任务定制；只有显式召回的合格组件进入候选；无整树隐式继承。 |
| H2-44 | 旧任务 workspace facts 到新任务只是 hypothesis，必须重验；可复用的是 procedure 而非本任务事实。 | ExperienceEntry 分 `fact_scope=workspace/domain/invariant`；workspace fact 禁止进 durable general memory；复用时生成 revalidation requirement。 | 旧任务数值/路径/阈值不能直接注入；跨域 procedure 可召回但仍需当前 probe。 |
| H2-45 | library 按 domain、run、mode 隔离；任务顺序固定；resume 只恢复当前任务之前条目，防未来经验泄漏。 | 新 `library_namespace={domain,protocol,search_mode,evaluator_epoch}`；`retain(prefix)` 或等价时序门；parallel/sequential 库不共享写态；skip/resume 重建只读历史前缀。 | 调整任务顺序、并行完成顺序、跨 mode、未来任务 resume 均不能泄经验；同 seed 可复现。 |
| H2-46 | `rebuild_index` 从磁盘重建，forget/retain 同步索引；恢复时 adopted harness/artifact 需完整。 | library 写入采用临时目录+原子 rename+读回；index 只是派生物，不作为唯一真源；恢复需 component hash 与 evidence refs 完整。 | 半写、坏 index、缺组件、hash 变化、重复 add 均可见且可修复；不重复使用损坏经验。 |
| H2-47 | library 复用本身要做消融：k=1 library 可恢复表现不等于所有场景都有益。 | W2 固定对照至少 `no_library / evidence_only / component_reuse`，同等新 probe 预算；library 生成/检索/ reflection 成本也进 CoP。 | 三臂同任务同协议；无提升即撤回；不得把历史任务见过的 val 当 held-out。 |

## 5. 成本、调度、身份与恢复（H2-48～H2-58）

| 编号 | 机制与代码证据 | DWC 文件/契约 | 测试建议 |
|---|---|---|---|
| H2-48 | 改进不是免费：base/probe/final/compose/selector/reflection/retry/fallback 都要计。 | 扩展计划中的 `observability/task_metrics.py`：`call_role` 至少含 `solver_base/probe/compose/final/judge/selector/reflection/retry/fallback/diagnosis`；每次调用有 parent/candidate/stage。 | 每角色各一次可汇总到 task；孤立辅助调用不得无 task/candidate 归属；总账由明细重算。 |
| H2-49 | **Harness² `RunView.cost_usd=0` 且 `_roll` 未填、`ledger.rollout` 未传，字段存在不等于接通。** | DWC `llm/client.py` 当前未检出 provider usage 提取；W1 必须从原始响应成功/tool-call/stream/non-stream/retry 路径提取并保留 usage，缺则 `usage_status=not_reported`，不得默认 0。 | 原始 usage 缺/部分/完整、流式、工具调用、重试、fallback 都有 fixture；缺 usage 时成本字段为 None 非 0。 |
| H2-50 | Stage retry 的 cost/attempts 累加；transport 失败也保留已发生成本。 | `improvement_stage` 记录 `attempt_count/cache_hits/usage_refs/cost_status`；无效候选、静态拒绝、empty response 不得免费。 | 第一次 invalid 1 单位、第二次 valid 2 单位→总 3；最终 fallback 仍保留全部费用。 |
| H2-51 | cached reply 的本次增量成本为 0，但缓存值不能抹掉历史真实费用或重复计数。 | 账本分 `incremental_usage` 与 `original_execution_ref`；汇总实验真实支出只算 incremental，对照分析可另列 historical，不混加。 | cache hit 新增为 0 且引用原账；重复 resume 不翻倍；清缓存后重新计量。 |
| H2-52 | Ledger 先查重复 label 再查 R/P 数量，防两个 stage 覆盖同一 run id 后仍“数量正确”。 | `improvement_ledger.assert_identity` 先查 `(stage,label,run_id)` 唯一，再核计划数和实际数；期望数来自实际 sparse plan，不强抄 4k/3k。 | 重复 label 即使数量正确也失败；减少空格子的实际 R/P 与计划一致；selector/reflection 另列不漏。 |
| H2-53 | `runmark` 只有 runner 正常返回才写 complete；输出文件存在不够；marker 含 harness fingerprint。 | 新 `harness/run_identity.py`：`complete_marker` 必须含 run_id、component hash、task/protocol、runner 正常结束、schema version；不完整 run 不可作为证据或缓存成功。 | 仅有 answer 无 marker 不复用；异常退出不写 complete；篡改 marker/hash 即重跑。 |
| H2-54 | resume 检查 adopted run dir、artifact、adopted harness 和 fingerprint；变化则重跑。 | marker 另含 `artifact_fingerprint`、solver/model、prompt/evaluator/protocol versions；resume 逐项验证，缺任一项即不兼容，不静默复用分数。 | 改 harness、删交付物、改 artifact、换 model/evaluator/split 都触发重跑或 incompatible。 |
| H2-55 | Proposer cache 用 label+mission+system+context 内容 hash+workspace path，避免 mtime 与同内容不同 mode 冲突。 | 所有 proposer/diagnosis cache 使用内容寻址；key 加 prompt version/model/channel/task/protocol/mode。禁止新缓存使用 mtime/mtime_ns；不同 mode 即使字节相同也独成立项。 | 同 mtime 内容变化必 miss；同内容不同 mode 不共享；context 任一文件变化 key 改变。 |
| H2-56 | `stream_order` 从排序集合按 seed/domain 独立 shuffle，不依赖 dict/PYTHONHASHSEED/其他 domain。 | 实验任务流以固定 split 文件为真源，顺序由 seed+domain+task set 决定；held-out 不参与 library 写入或 candidate 筛选。 | 删除一个 domain 不影响其他 domain 顺序；train/test overlap、重复 task、未知 id 全拒绝。 |
| H2-57 | 每 mode library 独立，拒绝一个 mutable library 被两 mode 共用；domain 间可并发但 domain 内保序。 | scheduler 只允许跨独立 namespace 并发；共享 `skill_store` 时读快照不可变，写经验在任务完成后串行提交；不能用全局进程态造成串扰。 | 两 mode 共写同库被拒绝；domain 内顺序稳定；并发不产生 future leak 或丢失更新。 |
| H2-58 | preflight 在花钱前检查 runner/runtime/renderer/依赖；失败不留可评分 dead rollout。 | `scripts/dwc_evo_round.py` 的 shadow 模式先跑 preflight；LLM、renderer、独立 evaluator、workspace、权限、网络策略不可用则 infrastructure_error，不进入候选质量比较。 | 缺 renderer/CLI/evaluator/模型配置均在付费前失败；已发生费用仍记；infra 不伪装 task fail。 |

## 6. Rubric 污染、证据隔离与代码侧防护（H2-59～H2-70）

| 编号 | 机制与代码证据 | DWC 文件/契约 | 测试建议 |
|---|---|---|---|
| H2-59 | `RunView` 不带 score；`score()` 只由 `core.judge` 在 selection 后调用；judge failure 是 None，绝不缓存成 0。 | W3/W4 的行为证据对象禁止含 val/pass/rubric 字段；W2 独立评价记录分通道。DWC Pareto 需要评全部 base/candidates，因此不能照搬“只评 winner”，但必须让 proposer/compose 无法读这些评分。 | 静态依赖测试：propose/probe/compose 模块不能 import judge/golden；judge exception→None；失败不算 0 或 pass。 |
| H2-60 | `task_prompt` 去除 criteria/expected output；LAB `_task_json` 在唯一读取边界 pop criteria。 | DWC task adapter 增加 answer-free read boundary：search 可用材料、dev 可见信息、val 隐藏信息分层；禁止候选通过其他 API 读同一 golden。 | criteria 在 JSON 任意位置均不进 prompt；`prompts_for` 不能绕过；val 只能 select 模式由独立 evaluator 使用。 |
| H2-61 | `leak_globs` 在 source copy、harness、library、最终 context 多处检查。 | 新 `harness/evidence_guard.py`：deny patterns 覆盖 source、rollout、component、experience、cache；路径规范化后匹配；最终 bundle 再全量检查。 | `RUBRICS.json`、expected/reference、eval_result、anchors val 等在每一路径均被拒；Windows 分隔符也可检。 |
| H2-62 | `wb_render.ALLOWLIST` 是正向允许 agent-authored bytes，其他一律拒；比单纯黑名单更关键。 | 交付物读取采用 per-task positive allowlist，禁止递归扫描整个 trial/run dir；只有 agent 输出区可读，verifier/judge 输出区永不作为证据。 | run dir 同时含 agent.patch 与 score.json 时只读前者；未知路径 raise；不能借 assets 复制绕过。 |
| H2-63 | `assert_no_grader_verdicts` 同时查文件名和文本 marker；`assert_tree_has_no_grader_verdicts` 在候选 rollout/library 前再次检查。 | 扩展 `organs/leakage.py` 之外增加 evidence tripwire：候选组件、experience、diff、缓存写入前检查 grader verdict；保留现有五类词表和“allowed≠语义干净”。 | `pass_rate`、passed_count、failed_checks、judge evidence 等在名称/正文均拒；命中即修读取边界，不靠无限扩 marker 表。 |
| H2-64 | code subset proposer 只看交付物 names，因为内容目录曾与 grader 输出同树；selector 可看经隔离的完整内容。 | `evidence_role=propose/compose/select/reflect` 分权；propose 可 `names_only`，selector 只能读 quarantine-passing artifact；reflection 不获得 val verdict。 | names 模式无文件正文落盘；selector 可读安全内容但不能读 harness identity；reflection 无 held-out。 |
| H2-65 | selector 匿名化不只是改 label：看不到 harness/trajectory，只比较 artifacts/source；候选生成方式隐藏。 | 匿名 map 存在 selector 不可读区域；删除成本、intent、parent、文件路径中可识别信息；比较后再揭示映射记账。 | side-channel：目录名、metadata、长度注释、trace、成本均不泄露 base/候选身份；map 可还原审计。 |
| H2-66 | `EVIDENCE_IS_DATA` 禁止执行 context 中命令、候选 script/plugin；防 prompt injection。 | proposer/compose/selector/reflection 的工具策略默认只读证据；候选代码只在独立 Probe sandbox 运行，网络/文件/进程权限最小化；文本指令不改变系统规则。 | 恶意 SKILL/artifact 包含“读取 rubric/执行命令”时不执行；probe 只能访问指定 shadow 根；逃逸拒绝。 |
| H2-67 | 论文实验有 rollout 主动下载 JobBench rubric 的风险；发布默认网络不能视为防泄漏。 | DWC shadow 任务设置 egress allowlist/DNS 防火墙，阻断 benchmark/answer-key 主机；记录全部外联与下载 hash；不能仅依赖 prompt 或 Codex sandbox 声明。 | fake 网络请求访问 rubric/HF/GitHub answer key 被拒并留 security event；允许的研究来源与评价源分离。 |
| H2-68 | renderer 复用 judge 的读取语义，但只提取 agent bytes；二进制不可读要 loud failure，不能 stub 当空交付。 | `deliverable_renderer` 统一 eval-compatible view + 安全 allowlist；缺 parser、公式无缓存、tar 不可读分别标 render_error；原始 binary 只能补充，不能推翻 canonical view。 | xlsx 公式/缓存两面呈现；reader 缺失 loud；无缓存值不能当已计算值；二进制 stub 不得当 pass。 |
| H2-69 | 汇总时 ungraded 计数但排除分母；mixed scoring units 发警告；k=1 noise floor 明示。 | W2 报告必须含 `n/n_ungraded/n_infrastructure/n_usage_missing/evaluator_version/metric`；不同 metric/version 不平均；ungraded 不得当 fail 或从报告中消失。 | judge None 不进分母且显式计数；weighted/unweighted 不混合；0 成功 CoP=undefined；没有 graded 时 score=None。 |
| H2-70 | DWC 现有落地/恢复可复用，但 `evo_targets.apply` 备份名只有秒级时间戳，`rollback` 没有与 apply 同级的原子读回。 | 解冻时加固：backup 名加 candidate/content hash/唯一 id；rollback 也备份当前、原子替换、读回 hash；library/ledger/manifest 同事务边界或明确 recovery journal。 | 同秒两候选备份不覆盖；rollback 后内容与父 hash 相同；中途崩溃可恢复；不能出现配置已改而台账无记录。 |

## 7. 现有 DWC 接缝与必须避免的错误融合

### 7.1 可直接复用，不另造平行系统

- `organs/replay.py`：current 必在池、确定性 tie-break、val fallback source。
- `organs/applier.py`：apply-on-copy、commit/readback、rollback、window；Compose 必须先停留副本。
- `organs/evo_targets.py`：白名单 schema、消费者、备份、原子写、读回。
- `organs/router.py`：`infra_only→no_diagnosis`，与 Probe 的环境失败分桶一致。
- `organs/measure.py`：activation/faithful_use/downstream_benefit 分开；library 不可只凭写入声称有效。
- `organs/credit.py`：append-only 与 a=0/1 契约；在其周围补证据，不推翻旧账。
- `harness/gates.py` + `adoption.py` + `landing.py`：静态门、运行门、状态迁移、落地仍复用，但 W2 严格模式不得让“缺 held-out 的 NA”自动落地。
- `harness/trajectory.py`：只投影已登记字段；新的 rollout evidence 应由独立 event refs 扩展，不能随意私加 `_last_*` 绕过登记。

### 7.2 明确不可照搬

1. 不复制 Harness²三 benchmark、专业 domain prompt、OpenCode/Codex 路径、24k/8k 字符上限、k=5、R=4k/P=3k 为 DWC 默认值。
2. 不把 parallel/sequential 当作 W5 任务难度画像；它们只是 W3/W4 搜索预算形态。
3. 不把 agentic selector 替换 Pareto；不把 final-only pool、无 base fallback、k=1 免评引入 DWC。
4. 不把完整 adopted harness 跨任务整体继承；不把 workspace facts 写成长期通用 memory。
5. 不把 Probe/Compose 的“看起来更好”写成 pass 或 verified improvement。
6. 不把 `confounded` 仅放在反思 prompt；必须由数据结构和写门执行。
7. 不复制 Harness² rollout 美元默认 0 的断链；DWC 必须先完成 W1 usage 赋值点验收。
8. 不复制 POSIX `fcntl` 锁到 Windows；使用跨平台锁/原子写，并实测并发恢复。
9. 不将 `agent_quality.memory_snapshot_hash` 的“文件名集合”或 mtime 当新 library 内容身份；必须 hash 文件字节和协议。
10. 不让候选修改 `config/anchors`、evaluator、held-out、质量门、grader prompt 或评分缓存。

## 8. 拟建最小数据契约（字段均为设计，不是现状）

```text
RolloutEvidence:
  schema_version / task_id / rollout_id / run_id
  candidate_id / parent_id / stage_id / mode / checkpoint_id
  component_snapshot_hash / solver_id / model_id / protocol_version
  trajectory_ref / deliverable_refs[] / source_manifest_ref
  execution_status          # completed / infrastructure_error / timeout / invalid
  delivered                 # 仅交付事实，不是 pass
  usage_ref / measurement_ref
  complete_marker_ref / artifact_fingerprint

Diagnosis:
  problem_type              # correctness / waste / instability / infrastructure
  scope                     # invariant / domain
  frequency / base_rollout_count / trajectory_refs[]
  performance_impact / cost_impact / confidence / unknowns
  independence_limits[]     # shared model / single probe / multi-edit / missing usage

CandidatePlan (extends current Proposal, not a replacement):
  parent_id / intent / scope / diagnosis_refs
  edits[] {edit_id, component, operation, path, content_ref, evidence_refs[]}
  expected_*                # 预测，禁止写入 measured_*
  preserved_behavior / regression_risks / validation_protocol / rollback_handle
  validation_status         # draft / static_rejected / probe_ready / composed / no_change

ProbeResult:
  candidate_id / component_snapshot_hash / rollout_refs[]
  behavior_changed / behavior_contrasts[] / delivered
  task_pass                 # 仅当有允许的固定 evaluator；否则 None
  evidence_status           # exploratory / confounded / independent_ready
  measured_* / usage_status / infrastructure_status

EditEvidence:
  edit_id / candidate_refs[] / compose_decision
  contrast_refs[] / verdict # helped/hurt/no_observed_effect/confounded
  confounders[] / sample_size / independence / attribution_status
  adopted                   # 与 verdict 完全独立

ExperienceEntry:
  cue / applicable_scope / component / operation
  supporting_contrasts[] / edit_evidence_refs[]
  confidence / confounded / source_harness_ref / evaluation_version
  fact_scope / revalidation_required
  # 缺证据 => NO_ENTRY，不实例化可召回经验

ImprovementMetrics (extends W1 task metrics):
  stage_id / call_id / call_role / attempt / cache_hit
  task_id / candidate_id / parent_id / rollout_id
  input_tokens / cached_input_tokens / output_tokens / reasoning_tokens
  provider_cost_estimate / pricing_version / usage_status
  wall_time_ms / original_execution_ref
```

## 9. 测试文件清单与验收顺序

以下为拟新增或扩展，均需解冻后实施：

1. `tests/test_task_metrics.py`、`test_llm_usage.py`：H2-48～55，先证明所有赋值点和缺 usage 语义。
2. `tests/test_candidate_protocol.py`：H2-13～25、59～65，验证 propose/compose 无法取得 val/rubric。
3. `tests/test_pareto_select.py`：H2-32～36，base 强制在池、父代保留、严格 held-out 缺失阻断。
4. `tests/test_h2_component_manifest.py`：H2-01～12，8 组件映射、白名单、frontmatter、hook、consumer。
5. `tests/test_evidence_bundle.py`：H2-16～18、61～68，全证据面隔离、names-only、renderer、注入。
6. `tests/test_probe_compose.py`：H2-19～25，真实 diff 的 kept、组合 lineage、fallback、no_change。
7. `tests/test_improvement_schedule.py`：H2-26～31、52～58，parallel/sequential、k=1、确定性账序、resume。
8. `tests/test_reflection_library.py`：H2-37～47，confounded、NO_ENTRY、陪跑、prefix-only、跨 mode 隔离。
9. `tests/test_credit_evidence.py`：H2-38～40，winner/loser 全记、无均摊伪归因、旧七元组兼容。
10. `tests/test_artifact_selector.py`：H2-30～34，匿名、drop、fallback、不能越过 Pareto。
11. `tests/test_evidence_guard.py`：H2-59～69，source/component/library/cache/network 全路泄漏反例。
12. `tests/test_evo_targets.py` 与 rollback 相关现有测试：H2-70，同秒备份、原子回滚、读回。

推荐验收顺序严格保持：**W1 usage → W2 base/Pareto/严格独立评价 → W3 evidence/contrast → W4 sparse Propose-Probe-Compose shadow → W5 画像 shadow → library 消融 → 人类批准后落地**。每一步跑新增定向测试、现有相关测试、全量测试和 `scripts/gate.py`，以真实输出为准。

## 10. 总结：70 项机制的去向

- W1：H2-09、48～58、69～70。
- W2：H2-19、30～36、59、69。
- W3：H2-13～18、23～24、37～40。
- W4：H2-01～12、14～25、26～29、60～68。
- W5/实验辅助：H2-26～28、45～47、56～58；不提前变成运行时硬依赖。

本清单的核心不是复制 Harness²流水线，而是把它的**执行对照、组合证据、经验写门和工程防护**嵌入 DWC 已有的测量—固定评价—诊断—候选—运行时顺序，同时修复其 **base 排除、成本断链和 rubric 污染** 三个不能继承的边界。
