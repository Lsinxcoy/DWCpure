# 跨项目记忆系统审计 → DWC pure 强化建议

> 2026-10-25 · 对象：GitHub `Lsinxcoy` 全部 45 个仓库。
> 方法：按“独立记忆设计”归并血脉，逐个读记忆相关模块/文档；同版本复制不重复分析。
> 证据边界：代码事实按 clone 的 commit 核验；未逐个跑全量测试；生产统计来自 `~/.dwc/var/dwc_prod.sqlite` 当前样本（24 条，样本小，不能外推长期）。

## 1. 仓库覆盖

| 血脉 | 仓库 | 判定 |
|---|---|---|
| DWC | `divine-wisdom-core-pure`、`divine-wisdom-core` | 七管 + SQLite/FTS5 + RRF/MMR；DWC 主线 |
| ARSI | `ARSI` | 三区 Mnemosyne + 工作记忆 checker + 信任治理 |
| Prometheus X/Y/Z | `Prometheus-X`、`Prometheus-Y`、`Prometheus-Z` | 三种不同代际：信念记忆 / 4-tier 记忆库 / 图记忆 |
| Prometheus Omega | `Prometheus-Omega`、`Prometheus-Omega-Genesis`、`Prometheus-Omega-Omega` | 四网络、事件流、偏好/信念、时间 KG |
| Prometheus Ultra | `Prometheus-Ultra`、`Prometheus-Ultra-MultiTypeKB`、`prometheus-nexus` | 50+ 记忆模块的工具箱；含写入门、层级/双通路、Hebbian、MemPO |
| Prometheus v5–v11 | `prometheus`、`prometheus-v3`…`v11`、`prometheus-v8pro`、`prometheus-v9pro` | 向量/KB/工作流/Mnemosyne 逐代演进；v9pro 实为 v10 包副本 |
| MSTAR | `mstar`、`hermes-mstar`、`MSTAR-Pro-V4.0`、`MSTAR-Pro-V4.0-Clean`、`Hermes-MSTAR-V2.0`、`mstar-pro` | 记忆程序、5 路路由、可解释遗忘、经验轨迹召回 |
| Protogonos | `Protogonos` | 3 层进化记忆 + Minerva 向量适配 |
| SYNTHEX | `SYNTHEX-Autopoiesis`、`SYNTHEX-Autopoiesis-pure` | 5 个活跃记忆件 / 23 个孤儿件；有 consolidation 方案 |
| 非独立记忆设计 | `-hermes`、`hermes-personal-backup`、`hermes-agent`、`hermes-agent-backup`、`hermes-skills`、`hermes-scripts`、`CIP-*`、`hermes-kanban-cip`、`hermes-collective-intelligence`、`PPT.SKILL`、`PPTPRO.SKILL` | 备份、技能包、协作协议或 PPT 工具；不作为记忆架构样本 |

核验 commit：ARSI `89ccfa8`、X `fea69b8`、Y `bad1d96`、Z `0d9e7fd`、Omega-Omega `c538b89`、Ultra `becc24c`、MultiTypeKB `43c7a0e`、Nexus `b9cadc2`、v11 `4baa62a`、MSTAR-Clean `fe26375`。

## 2. 各血脉的真实机制与可借点

| 来源 | 代码里真实存在的机制 | 对 DWC 的价值 | 不照搬 |
|---|---|---|---|
| ARSI | `DopamineGate`（importance/surprise 写入门）、`UtilityDecay`（按效用遗忘）、`EdgeDiscovery`（标签/语义关联）、TF-IDF `SemanticRetriever`、`WorkingState` + checker（done 必须有环境证据）、`SyncWorkingMemory`、记忆信任治理 | SELF 保护区、工作态证据门、关联发现、无 embedding 的 TF-IDF 召回、记忆信任分级 | `DopamineGate` 只看 importance 自评；TF-IDF 全量重建索引；三区命名与 DWC 不完全同义 |
| Prometheus-X | SQLite store 带 FTS/edges/beliefs/feedback；MARS 三层 `EventBuffer → PreferenceMemory → ProfileMemory`；多源摄入；文本 transform/slop 分析 | 偏好/画像记忆、边表、反馈账、多源输入分层 | MARS 用关键词抽偏好，质量弱；不能把关键词当信念 |
| Prometheus-Y | 4-tier `MemoryBank` + Weibull retention + gravity + migration；`DopamineWriteGate` 自适应阈值；`ConsolidationEngine`；`PolyphonicRetriever`；`VeracityEngine` 贝叶斯可信度；`ExplainableForgetting` 四策略；`HallwayTracker` 共现；`DynamicMemorySwitcher`；`DreamCycle`；`MemoryRouter`；`SHMR` | 可解释遗忘、可信度、共现走廊、记忆池切换、4-tier 晋升 | 按年龄删除、固定阈值、全量扫描式共现；DWC 不应做年龄淘汰 |
| Prometheus-Z | `GraphMemory` 四层（KeyNode/Topic/PersonalEvent/EpisodeEvent）；`ConsolidationGuard`（巩固只新建语义节点，绝不改原 episode）；`CodeKnowledge` AST 单元/依赖；`KnowledgeGap` | 图结构、巩固保护、代码知识、知识缺口 | 完整图数据库/LLM 重建；DWC 先做轻量边表即可 |
| Omega / Genesis / Omega-Omega | `FourNetworkMemory`（world facts / experiences / summaries / beliefs）；`MemoryStream`（recency×importance×relevance + reflection）；`DispositionLearner`（用户偏好）；`NodeFeedbackTracker`/`FailureLogTracker`；`PolyphonicRetriever` 5 路；`TemporalKnowledgeGraph`；`Scratchpad`；`ToolCallingReasoner` | 偏好/信念层、事件流评分、时间 KG、外部 scratchpad、成功/失败反馈 | 四网络全量复制；规则式 reflection 冒充 LLM 洞察；把 adopted/行为变化当正确性 |
| Ultra / MultiTypeKB / Nexus | `MemPO`（学习型效用策略/GRPO）、`RLNavigator`（HORMA 层级导航）、`HebbianMemory`（边权/枢纽/扩散激活）、`HierarchicalMemory`（root/task/episode/action/raw）、`DualPathwayMemory`（逐字+压缩）、`ExternalNotebook`、`ContextIsolator`、`ForbiddenPatternDetector`、`KnowledgeBridge`、`MemoryWriteGuard`（4 通道信任 + 注入/二进制/重复检测）、`SemanticLearner`、`KnowledgeRumination`、`EVAF` | 写入门、层级/双通路、边权、代码知识、记忆反刍 | 50+ 模块多数是孤儿；MemPO/RL 无数据不启用；ExternalNotebook 只在多 agent 有意义 |
| Prometheus v5–v11 | 向量后端（numpy/sqlite-vec/HNSW）、知识层/知识缺口/效用跟踪、工作流记忆、Mnemosyne v11（SQLite+sqlite-vec+FTS5、中文 CJK 分词、HybridSearch RRF/加权/CombMNZ、生命周期、WAL、事件总线、MCP） | 中文 FTS 分词、混合检索、检索质量指标（MRR/NDCG）、记忆操作 WAL/事件账 | 引入 embedding/向量依赖前必须先证明词法召回不足；MCP 服务化不是当前需求 |
| MSTAR | `MemoryProgram`（fitness/lineage/episodes/failure_type/lifecycle）、5 路 `MemoryRouter`、可解释遗忘、MARS 信念、`ExperienceRecall`（轨迹召回 + stitching + meta-controller） | 记忆程序 fitness/谱系、轨迹拼接、按记忆类型路由 | 固定 fitness 权重、无验证的轨迹拼接；DWC 已有 skill 卡，不必另造程序层 |
| Protogonos | 3 层 `EvolutionMemory` + Minerva adapter | 分层晋升/降级、向量适配接口 | 简单 LRU/年龄淘汰；无证据的自动管理 |
| SYNTHEX | 5 个活跃件 / 23 个孤儿件的真实盘点；MemoryFacade；写时去重；consolidation 保护原 episode | **最重要的反面教材：机制数量不等于能力**；写时准入；原 episode 不可覆盖 | 大量 orphan 模块；为“全量实现”而实现 |

## 3. DWC 当前真实状态

生产库 `~/.dwc/var/dwc_prod.sqlite`（2026-10-25）：

```text
memory_node = 24
  trace = 17（17 条被访问，11 条有 effect）
  skill = 7（7 条 access=0 / effect=0）
failure_sig = 0
```

`memory.py` 已有：四区、七管、SQLite WAL、FTS5 trigram、LIKE、中文 2-gram、LLM 查询扩展、RRF、Weibull 排序、importance、MMR、learn/dream/maintain、effect 证据、`skill_store`、`memory_view`。

问题不在“没有记忆”，在“记忆没有被正确消费和验证”：

1. **skill 召回不记 access**：`executor.memory_text()` 实际能返回 7 条 skill 中的匹配项，但只读 `memory_node`，不更新 `access_count/last_access`。所以 `access=0` 不能证明“没人用”，是测量链断了。
2. **skill 不是过程**：`skill_writer.from_term()` 从模型自述的 `★method` 取内容；生产 6/7 条是最终答案/事实（如阶乘定义、求和公式），不是“先做什么、用什么工具、怎么验证”的可复用过程。
3. **failure_sig = 0**：生产任务当前多为通过；DWC 的 dream 只聚失败签名，成功路径没有形成“成功做法”的对比学习，导致负样本为零时学习链空转。
4. **trace 太薄**：`{action, task, step}` 没有工具名、参数、观察、结果、diff、耗时/成本；无法从轨迹抽过程，也无法做浪费诊断。
5. **没有边**：只有 `chain_id`，没有 `memory_edge`；无法回答“这条技能和哪次失败/哪个任务/哪条修订相关”。
6. **没有 SELF / 偏好 / 信念层**：身份与规则在 `config/dwc_self.md` 静态文件里，不在记忆区；没有用户偏好、纠正、长期决策的受保护记忆。
7. **没有写入门**：工具输出/网页/检索上下文可直接进 trace/skill；没有来源信任、注入/二进制/重复检测。
8. **没有检索质量指标**：没有 hit rate、zero-result、MRR/NDCG、召回后 effect 转化；无法判断记忆是否真的帮助任务。

## 4. 强化路线（M0–M3）

### M0 · 先修“测量与消费”（1–2 天）

- `memory_text()` 返回命中的 skill 时，统一走 `recall_many` 或显式 `UPDATE access_count`，并记 `retrieval` 事件（query、命中 ID、rank、score）。
- `task_recall` 读失败/技能统计时，不把“读统计”当 access；只有真正进入 prompt/决策的才记 access。
- 新增 `memory_retrieval` 事件表/JSONL：query、route、hits、selected_ids、later_effect。
- 审计现有 7 条 skill：标记 `procedural / factual / chat`；factual 不进入“可复用技能”统计。
- 验收：一次真实任务后，被 prompt 使用的 skill `access_count` 增加；看板能显示 skill 使用率，而不是 0。

### M1 · 把“成功答案”升级成“可执行过程”（3–5 天）

- 扩展 trace payload：`tool_name, args_digest, observation_digest, outcome, diff_digest, latency_ms, cost`（不存原始大对象，存 ref/hash）。
- 新增 skill schema：
  ```text
  scene, preconditions, steps[], tools[], verification[],
  failure_modes[], recovery_strategies[], evidence_ref, source
  ```
- `from_term` 只在“过程证据完整”时写 skill；只有最终答案/事实的 `_method` 标 `factual`，不进入过程技能库。
- 对成功/失败同题做对比：成功轨迹 + 失败签名 → “差异步骤”技能；这是 DWC 当前 dream 缺的另一半。
- 验收：新 skill 至少 3 个步骤、1 个验证、1 个失败模式；能从 `evidence_ref` 回溯到轨迹；不再出现“阶乘=120”这种答案卡。

### M2 · 加结构：边、SELF、偏好、上下文预算（1–2 周）

- `memory_edge(source_id, target_id, relation, weight, evidence_ref)`：
  - `task → failure_sig`、`skill → invalid_condition`、`skill → recovery`、`episode → skill`、`entity → event`。
  - 先做 SQLite 邻接表 + 2 跳召回，不引入图数据库。
- `SELF` 保护区：身份、长期规则、用户明确指示；只允许版本化修订，不允许 evolver 覆盖；每次读取记 access。
- `PREFERENCE/BELIEF` 记忆：偏好、纠正、长期决策；字段 `confidence, evidence_refs, support_count, contradict_count, source_trust`；用户纠正时旧信念降权而不是删除。
- `MemoryContextAssembler`：按 token 预算组装 `SELF → 当前任务 → 相关 skill → 最近 episode → 原始 trace`；逐字/摘要双通路，摘要必须带 `raw_ref`。
- 验收：能回答“为什么召回这条”“它和哪次失败相关”；用户纠正后偏好变化可追溯；上下文不超预算且不丢原始引用。

### M3 · 维护、质量与条件扩展（有数据后再做）

- 可解释维护：`KEEP / ARCHIVE / MERGE / DELETE`，删除必须同时满足“未访问 + 无 effect + 非唯一签名”；不做年龄淘汰。
- 检索质量：hit rate、zero-result、MRR/NDCG、skill 复用率、召回组 vs 未召回组成功率（A/B）。
- 中文检索：先 benchmark 现有 trigram/LIKE/2-gram/LLM 扩展；不足再考虑 v11 的 CJK 分词/BM25，不先引入 embedding。
- 条件扩展：向量/混合检索、MemPO、RLNavigator、ExternalNotebook 只在有真实消费点和对照数据时启用；否则保持关闭。

## 5. 不应做的事

- 不要把 Ultra/Nexus 的 50+ 模块整包搬进 DWC；SYNTHEX 已证明 23 个孤儿模块是债。
- 不要把“写入门”做成自评分；必须有来源信任和可审计证据。
- 不要用年龄删除记忆；DWC 的 maintain 已明确“价值而非年龄”。
- 不要把最终答案当技能；技能必须是过程 + 验证 + 失效条件。
- 不要在没有 hit rate/effect 数据前引入向量库或 RL 策略。
- 不要用 memory 节点数量当强化成果；要看“被召回、被使用、改变行为”的转化。

## 6. 验收指标（基线相对，不拍绝对阈值）

```text
write → recall → effect 转化率
skill 复用率（access>0 / 可用 skill）
retrieval hit rate / zero-result / MRR
过程技能合格率（steps/verification/failure_modes 齐全）
注入/二进制/重复写入拒绝率
每次召回 token 成本
召回组 vs 未召回组任务成功率差（A/B）
```

最终判断标准：**记忆是否让任务更容易成功、成本更低、错误更少**；不是“存了多少条”。
