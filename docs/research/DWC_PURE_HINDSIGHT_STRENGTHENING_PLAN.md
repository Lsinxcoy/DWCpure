# DWC pure × Hindsight 记忆强化方案（1+1>2）

> 版本：2026-10-26 · 范围：只改 DWC pure 的记忆子系统，不引入 Hindsight 运行时/数据库/API。
> 依据：Hindsight 当前 main（`5fc7af3`）代码与文档；DWC pure 生产库 `~/.dwc/var/dwc_prod.sqlite` 读回。
> 原则：只吸收 Hindsight 明确强于 DWC 的机制；DWC 已经领先的部分不重写；每个改动有消费者、测试、失败语义。
>
> **落地状态（2026-10-26，代码级）**：P0–P4 核心已实现，新增测试覆盖数据契约、knowledge page、consolidation、脱敏、factual 迁移。
> 新增命令：`dwc memory-stats`（含 contract 段）、`dwc knowledge build/check/list/search`、`dwc memory consolidate [--apply]`、`dwc memory migrate-factual [--apply]`。
> **生产已执行**：开发提交 `fdaf5b0` / 生产提交 `7e4bc51`；11 条 factual SKILL → REFERENCE，1 条 chat 保留审计，生成 6 个 knowledge page；生产全量 `3363 passed / 9 skipped`，gate 8/8；agent pid `1287392`。

---

## 0. 结论

DWC pure 的记忆系统不是“缺机制”，而是：

> **流程重、数据粗。**

七管、五区、九种 kind 都在，但节点主要是 `payload JSON + access/effect`；没有统一的有效时间、证据计数、派生类型和拉取式消费。结果是：

- `skill_prompt` 20 次全 0 命中；
- 12 条 skill 中 4 条 factual、8 条未标 kind、0 条显式 procedural；
- factual 被 `memory_text` 正确过滤后，没有第二个消费入口；
- `memory_edge = 0`，图检索没有对象；
- `retrieval_quality` 没有 labels，MRR/NDCG 为 `None`。

Hindsight 的强项恰好是数据契约：

- 原子 fact + 派生 observation；
- `occurred_start/end` + `mentioned_at`；
- `source_memory_ids` + `proof_count` + history；
- 后台 consolidation；
- knowledge page / mental model 的拉取式消费；
- 写入时密钥/PII 脱敏；
- 有标注的长期记忆评测。

**1+1>2 的公式：**

```text
DWC 的生命周期/编排/质量门
  × Hindsight 的数据契约（类型、时间、证据、投影）
  = 可审计的进化输入 + 可消费的知识
```

不是“再加几管”，而是让现有七管拿到**可信、可失效、可引用**的数据。

---

## 1. 机制对照：只列 Hindsight 更强或互补的部分

| # | 维度 | Hindsight | DWC pure 现状 | 判断 | DWC 落点 |
|---|---|---|---|---|---|
| H1 | 记忆粒度 | 原子 fact + 派生 observation | task-level node，payload 整块 | Hindsight 强 | `derived_kind` + `source_ids`，不建第二套 fact 库 |
| H2 | 类型 | world / experience / observation | zone + kind + tube；SKILL 混装事实与过程 | Hindsight 强 | 新增 `REFERENCE`，SKILL 只放过程 |
| H3 | 时间 | occurred_start/end + mentioned_at | 只有 `created_at` / `last_access` | Hindsight 强 | `observed_at` / `valid_from` / `valid_to` / `source_commit` |
| H4 | 证据 | `source_memory_ids` + `proof_count` + history | `evidence_refs` 部分有；版本链有 | Hindsight 强 | 统一 `source_ids` / `proof_count` / `supersedes` |
| H5 | 巩固 | 后台 observation 合并/更新，保留历史 | `dream` 只处理失败签名；`learn` 只回写 importance | Hindsight 强 | 离线 `consolidate`，dry-run + 保留原节点 |
| H6 | 消费 | recall / reflect / knowledge page / MCP 工具 | `memory_text` 推送；factual 无出口 | Hindsight 强 | knowledge page + 拉取式 `knowledge_search` |
| H7 | 安全 | regex 密钥/PII 脱敏 | 通道信任/注入/重复检查，无密钥扫描 | 互补 | `memory_guard.redact()` 全通道 |
| H8 | 评测 | LongMemEval / LoCoMo + 公开 runs | 词法 bench；无 labels 时 `None` | 方法强，数字不可搬 | 真实任务 labels + A/B 消融 |
| H9 | 时间/图检索 | 时间解析 + 图扩展 | RRF/MMR 已有；图无对象 | 部分强 | 先加 validity 过滤；图等实体边 |
| H10 | 多租户 | bank/tags | 单用户单库 | 不需要 | 暂不做 |
| H11 | reflect/disposition | agentic 回答 + 人格参数 | 任务循环 + QA 证据门 | 不需要 | 不引入 |
| H12 | 向量/cross-encoder | pgvector + reranker | SQLite FTS + 本地端点 | 条件 | 词法基线不够再评估 |

### 同名不同义，不能 1:1 对标

| 名字 | DWC pure | Hindsight | 结论 |
|---|---|---|---|
| remember / retain | 确定性写节点 | LLM 抽原子 fact | 数据粒度不同 |
| recall | 四路 + RRF + MMR + Weibull | 四路 + RRF + cross-encoder | DWC 融合不弱 |
| learn | 回写 importance | 无同名；consolidation 合成 observation | 不可直接对照 |
| reflect | 失败归因 | agentic 回答 | 同名不同义 |
| dream | 失败签名重组 | consolidation 的一种 | 范围窄 |
| maintain | 归档/删除门/稀有保护 | invalidate/soft-retire | DWC 更强 |
| self | 身份/长期规则 | mental model/directives | 近似但用途不同 |

---

## 2. 目标与非目标

### 目标

1. **让事实有事实的家**：factual 不再写成 SKILL，不进入 skill prompt。
2. **让技能只放过程**：SKILL 必须有步骤、验证、失效条件、证据。
3. **让时间可失效**：旧技能在新 commit/新事实后不再被召回。
4. **让证据可审计**：每条派生记忆能说出“由哪些证据、几条证据支撑”。
5. **让知识可拉取**：agent 通过 knowledge page 主动取事实，而不是每轮推送。
6. **让进化输入可信**：evolver 只吃 `valid` + `proof_count` 足够的 SKILL/BELIEF。
7. **让安全边界前移**：密钥/PII 在写入记忆前脱敏。

### 非目标

- 不引入 Postgres/pgvector/cross-encoder。
- 不引入 Hindsight 的 bank/tenant/tags 多租户模型。
- 不引入 disposition（skepticism/literalism/empathy）。
- 不新增完整 reflect agent；DWC 的任务循环已经覆盖。
- 不自动删除任何旧节点；只失效/归档。
- 不让模型自评置信度；`proof_count` 只数证据，不是概率。
- 不抄 LongMemEval/LoCoMo 分数。

---

## 3. 目标数据契约

### 3.1 新增字段（`memory_node`）

```sql
ALTER TABLE memory_node ADD COLUMN derived_kind TEXT NOT NULL DEFAULT 'raw';
ALTER TABLE memory_node ADD COLUMN observed_at REAL;
ALTER TABLE memory_node ADD COLUMN valid_from REAL;
ALTER TABLE memory_node ADD COLUMN valid_to REAL;
ALTER TABLE memory_node ADD COLUMN source_ids TEXT NOT NULL DEFAULT '[]';
ALTER TABLE memory_node ADD COLUMN proof_count INTEGER NOT NULL DEFAULT 1;
ALTER TABLE memory_node ADD COLUMN source_commit TEXT;
ALTER TABLE memory_node ADD COLUMN supersedes TEXT NOT NULL DEFAULT '[]';

CREATE INDEX IF NOT EXISTS ix_node_valid
    ON memory_node(valid_from, valid_to);
CREATE INDEX IF NOT EXISTS ix_node_derived
    ON memory_node(derived_kind);
```

### 3.2 字段语义

| 字段 | 语义 | 约束 |
|---|---|---|
| `derived_kind` | `raw` / `fact` / `procedure` / `observation` / `pattern` / `rule` | 写入时必填；不能由模型自由发挥 |
| `observed_at` | DWC 何时学到/观察到 | epoch 秒；TRACE 用任务结束时间 |
| `valid_from` | 该知识从何时起为真 | epoch 秒；默认 `observed_at` |
| `valid_to` | 该知识到何时失效 | `NULL` = 当前有效；失效只写时间，不删除 |
| `source_ids` | 支撑证据 | JSON 数组；节点 ID 或 `traj:<id>#step`；不得为空（`raw` 除外） |
| `proof_count` | 独立证据条数 | `>=1`；按 `source_ids` 去重计数；**不是置信度** |
| `source_commit` | 代码版本 | git SHA 或 `NULL`；用于 stale 判断 |
| `supersedes` | 被本节点替代的旧节点 | JSON 数组；旧节点保留，写 `valid_to` |

### 3.3 类型与 zone 映射

| MemoryKind | Zone | derived_kind | 消费者 |
|---|---|---|---|
| TRACE | PROXY | raw | recall / trajectory |
| WORKING_STATE | PROXY | raw | working-state gate |
| FAILURE_SIGNATURE | EXPERIENCE | pattern | recall / dream |
| SKILL | EXPERIENCE | procedure | `memory_text`（仅 procedural） |
| PROPOSAL | EXPERIENCE | observation | evolver |
| BELIEF | EXPERIENCE | observation | context / knowledge page |
| PREFERENCE | EXPERIENCE | observation | context |
| IDENTITY / STANDING_RULE | SELF | rule | system prompt |
| **REFERENCE（新增）** | **REFERENCE（新增）** | **fact** | **knowledge page** |

> `REFERENCE` 不参与 evolver、不参与 Weibull 淘汰、不进入 `memory_text`。它只被 knowledge page 投影和 `knowledge_search` 读取。
> 短期若不想新增 zone，可先映射到 `PROXY`，但必须标记 `non_evolution=True`；中期独立成区。

### 3.4 写入校验

```text
SKILL:
  skill_kind == "procedural"
  steps 非空
  verification 非空
  invalid_conditions 非空
  source_ids 非空
  proof_count >= 1
  proof_count == 1 ⇒ status="candidate"，不进 prompt
  proof_count >= 2 或 (1 成功 + 1 失败对比) ⇒ status="active"

REFERENCE:
  claim 非空
  source_ids 非空
  observed_at / valid_from 非空
  不允许 method 字段（防止伪装成技能）

BELIEF:
  保留现有 topic/stance/confidence/evidence_refs
  新增 proof_count；confidence 不由 proof_count 自动推导

TRACE:
  task_id / observed_at 必填
  raw 允许 source_ids 为空
```

**硬规则：**

- factual 不允许写 `SKILL`；`skill_writer` 在写入前分流到 `REFERENCE`。
- `proof_count` 只能由代码从 `source_ids` 去重计算，不能由模型填写。
- `valid_to` 只能由 `supersede()` / `consolidate()` 写，不能由模型直接改。
- 任何派生节点不得引用自己；`source_ids` 里的节点必须存在或为外部 ref。

---

## 4. 分阶段实施

### P0 · 基线与仪表（不改行为）

**目的**：先证明现状，避免“修了但不知道修了什么”。

改动：

1. `memory-stats` 增加：
   - `skill_kind` 分布；
   - `derived_kind` 分布；
   - `valid` / `stale` / `invalid` 数量；
   - `proof_count` 分布；
   - `knowledge_page` 读取次数（route=`knowledge_page`）。
2. 给 8 条未标 `skill_kind` 的 skill 回填分类并持久化。
3. 从现有 trace 里选 20–50 个真实任务，建 labels 骨架：
   ```json
   {"query": "...", "relevant_node_ids": ["..."]}
   ```
   只建集，不声称指标。

验收：

- `memory-stats` 数字与 SQL 读回一致；
- 回填不改变任何 prompt 行为；
- labels 文件存在，但 `mrr/ndcg` 仍可为 `None`（未跑）。

---

### P1 · 数据契约 + 分类路由（核心）

**目的**：让 factual 和 procedural 各回各家；让旧技能可失效。

改动：

1. `src/dwc/organs/memory.py`
   - 加字段/索引/迁移；
   - `MemoryKind.REFERENCE` + `Zone.REFERENCE`；
   - `remember()` 校验 `derived_kind/source_ids/proof_count/valid_*`；
   - `supersede(old_id, new_id, at)`：旧节点写 `valid_to`，新节点 `supersedes` 加旧 ID；
   - `recall_search()` 默认 `valid_from <= now AND (valid_to IS NULL OR valid_to > now)`；
   - `retrieval_stats()` 增加 `valid/stale` 计数。
2. `src/dwc/organs/skill_writer.py`
   - `classify_skill_kind()` 结果落库，不只运行时分类；
   - `factual/chat` 不写 `SKILL`，改写 `REFERENCE`；
   - `procedural` 必须有 `steps/verification/invalid_conditions/source_ids`；
   - `from_task_result()` 写 `source_ids=[trajectory_ref]`、`observed_at`、`source_commit`；
   - 单条证据写 `status="candidate"`，不直接 active。
3. `src/dwc/llm/executor.py`
   - `memory_text()` 只查 `kind='skill' AND status='active' AND valid`；
   - 不改 `include_factual=False` 的默认值；
   - 无 procedural 时返回空，不用 factual 凑数。
4. `src/dwc/organs/memory_context.py`
   - 不把 `REFERENCE` 全量注入；最多注入 knowledge page 的标题索引（可选，默认关闭）。

测试：

- `tests/test_memory_schema_v2.py`：字段、迁移、幂等；
- `tests/test_memory_validity.py`：旧技能失效、历史查询、`supersedes`；
- `tests/test_skill_routing.py`：factual 不进 SKILL、procedural 缺证据拒绝、candidate 不进 prompt；
- `tests/test_memory_text.py`：只注入 active procedural。

验收：

- 生产 12 条 skill 中 factual 全部迁到 `REFERENCE`；
- `skill_prompt` 不再出现 factual；
- 过程任务上 `skill_prompt` 命中率 > 0（若仍为 0，说明还没有 procedural，不是检索 bug）；
- 旧技能在 `valid_to` 后不被 `recall_search` 返回。

---

### P2 · Knowledge page + 拉取式消费

**目的**：给 factual 一个真正的消费入口，解决“存了但 agent 看不到”。

改动：

1. 新模块 `src/dwc/organs/knowledge_page.py`
   - `build(memory, scope=None)`：从 `REFERENCE` / `BELIEF` / active `SKILL` 生成页面；
   - 默认输出 `var/knowledge/<slug>.md`；`export` 可写 `docs/knowledge/`；
   - 每页 frontmatter：
     ```yaml
     page_id: ...
     title: ...
     scope: ...
     sources:
       - node_id: ...
         derived_kind: fact
         observed_at: ...
     refreshed_at: ...
     valid_for_commit: ...
     stale: false
     ```
   - 内容用确定性模板：`Summary` / `Current facts` / `Procedures` / `Failure patterns` / `Sources`；
   - 可选 LLM 只做摘要，必须保留 source 引用；无 source 的句子丢弃。
2. `src/dwc/cli_main.py`
   - `dwc knowledge build [--scope]`
   - `dwc knowledge check`：source 失效/commit 变化则标 `stale: true`
   - `dwc knowledge list`
3. 消费工具
   - 新增 `knowledge_search(query)` 工具：只搜页面，返回标题/摘要/source IDs；
   - 或复用 `search_code` 搜 `var/knowledge/`，但要有独立 route 记录；
   - 不把页面内容每轮 push 进 prompt。
4. 记录
   - `record_retrieval(query, "knowledge_page", ids, source="knowledge_search")`；
   - 页面读取计入 access，但不计入 `skill_prompt`。

测试：

- `tests/test_knowledge_page.py`：build/check/stale/无 source 丢弃；
- `tests/test_knowledge_search.py`：只返回页面、记录 route；
- `tests/test_knowledge_no_push.py`：`memory_text` 不包含 REFERENCE 正文。

验收：

- agent 能通过 `knowledge_search`/`read` 找到 factual 知识；
- 页面可删除重建；
- `knowledge_page` 有真实读取记录；
- `skill_prompt` token 成本不升。

---

### P3 · 离线巩固（consolidation）

**目的**：把重复的 skill/fact 合成一张卡，保留原节点和证据。

改动：

1. 新模块 `src/dwc/organs/consolidate.py`
   - 候选：`derived_kind in (fact, procedure, observation)` 且 `valid_to IS NULL`；
   - 聚类键：`(derived_kind, normalized scene/topic, tool/command, error signature)`；
   - 近重复：token Jaccard ≥ 0.85（初值，待校准）；
   - 规则（借鉴 Hindsight，但不照抄 prompt）：
     - 一个节点一个 facet；
     - 同 canonical fact 优先 update，不创建近似重复；
     - 冲突时保留历史，写 `valid_to` / `supersedes`；
     - 不做算术、不做逻辑推导；
     - 时间比较先于内容合并；
     - 不删除原节点。
   - LLM 只用于生成合并后的措辞；确定性门槛决定 create/update/skip；
   - 无 `source_ids` 或 `proof_count` 不足 ⇒ fail-closed，不合并。
2. CLI
   - `dwc memory consolidate --dry-run`：输出 `create/update/merge/skip`；
   - `--apply`：写新节点 + `supersedes`，旧节点保留；
   - 幂等：同输入重复跑不新增。
3. 测试
   - 重复 skill 合并；冲突时间；无证据拒绝；原节点不变；重复跑幂等。

验收：

- 重复 skill 数量下降；
- 所有合并节点有 `source_ids`，`proof_count == len(unique(source_ids))`；
- 原节点仍可查；
- dry-run 与 apply 的决策一致。

---

### P4 · 写入脱敏 + 标注评测

**目的**：补安全边界；让“有没有变好”可测。

改动：

1. `src/dwc/organs/memory_guard.py`
   - 新增 `redact(text)`：API key、Bearer、私钥块、密码字段、连接串；
   - `remember()` 无论 `source_channel` 是否为空，都先 redact；
   - 命中类型写 `memory_quarantine.checks` 或 payload `redactions`；
   - 不把原文写日志。
2. 评测
   - 用 P0 的 labels 跑 `retrieval_quality`；
   - A/B：baseline / P1 validity / P2 knowledge page / P3 consolidation；
   - 指标：hit@5、MRR、NDCG、任务成功率、prompt tokens、latency；
   - 无 labels 时输出 `None`，不填 0。

测试：

- `tests/test_memory_redaction.py`：密钥/PII 不入库；
- `tests/test_memory_bench_labels.py`：有 labels 才算 MRR/NDCG；
- `tests/test_memory_ablation.py`：开关组合不崩，结果带 `n_labeled`。

验收：

- 密钥测试全过；
- 每个结论带 `n_labeled` 和配置；
- 没有标签就不声称提升。

---

## 5. 文件级改动清单

| 文件 | 改动 |
|---|---|
| `src/dwc/organs/memory.py` | 字段/索引/迁移；`REFERENCE`；`remember` 校验；`supersede`；validity 过滤；stats |
| `src/dwc/organs/skill_writer.py` | factual 分流；procedural 证据门槛；`skill_kind` 落库；`source_ids/observed_at/source_commit` |
| `src/dwc/llm/executor.py` | `memory_text` 只取 active procedural；不改默认过滤事实 |
| `src/dwc/organs/memory_context.py` | 不注入 REFERENCE 正文；可选标题索引 |
| `src/dwc/organs/knowledge_page.py`（新） | build/check/export；frontmatter；stale |
| `src/dwc/organs/consolidate.py`（新） | 聚类/合并/dry-run/幂等 |
| `src/dwc/organs/memory_guard.py` | `redact()`；全通道生效 |
| `src/dwc/cli_main.py` | `knowledge build/check/list`；`memory consolidate`；stats 扩展 |
| `scripts/dwc_agent.py` | 技能写入路径接 `REFERENCE` 分流与证据字段 |
| `tests/test_memory_schema_v2.py` | 迁移/字段/幂等 |
| `tests/test_memory_validity.py` | 失效/历史/supersedes |
| `tests/test_skill_routing.py` | factual/procedural/candidate |
| `tests/test_knowledge_page.py` | build/check/stale/无 source |
| `tests/test_knowledge_search.py` | 页面检索与 route |
| `tests/test_memory_consolidate.py` | 合并/冲突/幂等 |
| `tests/test_memory_redaction.py` | 密钥/PII |
| `tests/test_memory_bench_labels.py` | labels/MRR/NDCG |

---

## 6. 评测设计

### 6.1 指标

| 指标 | 口径 | 失败语义 |
|---|---|---|
| `procedural_coverage` | 有 ≥1 条 active procedural 的任务占比 | 无 procedural 时 `0`，不是 `None` |
| `skill_prompt_hit_rate` | 过程任务中 `skill_prompt` 有命中的比例 | 无过程任务时 `None` |
| `stale_skill_regression` | 旧技能在 `valid_to` 后仍被召回的比例 | 应为 0；出现即失败 |
| `knowledge_page_hit_rate` | factual 查询中页面命中的比例 | 无查询时 `None` |
| `evidence_coverage` | 派生节点中有 `source_ids` + `proof_count` 的比例 | 目标 100% |
| `task_success` | 端到端任务通过率 | 同模型、同 prompt，仅记忆变量 |
| `prompt_tokens` | `memory_text` + page 注入 token | 不应高于 baseline |
| `latency` | recall/build/search P50/P95 | 记录，不设硬门槛 |

### 6.2 A/B 组合

```text
B0 baseline
B1 P1 validity filter
B2 P1 + P2 knowledge page
B3 P1 + P2 + P3 consolidation
```

每组跑同一批 held-out 任务，记录 `n_labeled`、模型、commit、prompt 版本。

### 6.3 结论纪律

- 没有 labels：`mrr/ndcg = None`，不填 0。
- 没有 held-out：不声称泛化。
- 没有对照：不声称“提升”。
- 任何数字必须能由 `memory-stats` / `memory_bench` 复跑。

---

## 7. 风险与回滚

| 风险 | 处理 |
|---|---|
| 迁移失败 | 只加列/索引；SQLite `ALTER TABLE ADD COLUMN`；启动时 `PRAGMA table_info` 幂等检查；失败保留旧库 |
| factual 分流后 prompt 更空 | 预期；先建 knowledge page，再观察任务成功率，不看单一 hit rate |
| 旧技能失效误伤 | `valid_to` 只由显式 `supersede`/`consolidate` 写；默认 NULL |
| 合并错 | dry-run；保留原节点；`source_ids` 可回滚 |
| 页面 stale | `knowledge check` 标 stale；agent 读到 stale 时必须回查 raw |
| 脱敏误杀代码 | 规则窄、测试覆盖；命中只 redact 敏感片段，不整段丢 |
| LLM 成本 | 确定性门槛先做；LLM 只做措辞/摘要；可关闭 |
| 观察自强化 | `memory_guard` 保留；`proof_count` 只数证据；不让模型自评 |
| Hindsight API 变化 | 不依赖其运行时；只借鉴概念；pin commit 仅用于对照 |

**回滚：**

- 代码回滚到上一个 tag；
- 新列保留但忽略，旧代码不受影响；
- `REFERENCE` 节点可迁回 `SKILL`（保留 `source_ids`），不丢数据；
- knowledge pages 是投影，删除即可重建。

---

## 8. 提交顺序

```text
1. docs: add Hindsight strengthening plan
2. feat(memory): add derived_kind/time/evidence columns + backfill
3. feat(memory): route factual to REFERENCE and filter active procedural
4. feat(knowledge): build/check knowledge pages + pull search
5. feat(memory): offline consolidation with provenance
6. feat(security): redact secrets at memory write
7. test(memory): labeled benchmark and ablations
```

每个提交单独跑定向测试；P1/P2/P3 各跑一次全量；生产部署按路径 checkout，保留 `config/`、`var/`、凭证和本地脚本改动。

---

## 9. 1+1>2 的验收定义

不是“功能更多”，而是四个可测结果：

1. **进化输入可信**：evolver 只吃 `valid` + `proof_count` 足够的 SKILL/BELIEF；单条证据不能升级。
2. **技能可失效**：新 commit/新事实后，旧技能不再被召回；历史仍可追溯。
3. **事实可消费**：factual 通过 knowledge page 被 agent 主动读取，不再依赖 `skill_prompt` 命中。
4. **成本不升**：`memory_text` token 不高于 baseline；页面按需读取。

达到这四点，才叫 1+1>2；否则只是“把 Hindsight 的字段抄了一遍”。

---

## 10. 不做什么（明确拒绝）

- 不建 `world/experience/observation` 三张新表；用 `derived_kind` + 现有 zone/kind。
- 不引入 opinion confidence / disposition。
- 不引入完整 reflect agent。
- 不引入 pgvector/cross-encoder；词法基线不够再评估。
- 不引入多租户 bank/tags。
- 不自动删除旧节点。
- 不用 Hindsight 的 benchmark 数字做 DWC 结论。
- 不把 knowledge page 当 source of truth；它只是投影。

---

## 11. 落地记录（2026-10-26）

| 阶段 | 文件 | 验证 |
|---|---|---|
| P0 统计 | `memory.py:memory_stats`、`cli_main.py:memory-stats` | `tests/test_memory_contract_v2.py` |
| P1 数据契约 | `memory.py` 字段/迁移/`supersede`/validity、`skill_writer.py` 分流 | `test_memory_contract_v2.py`、`test_skill_migration.py` |
| P2 knowledge page | `knowledge_page.py`、`cli_main.py:knowledge`、`task_exec.py:knowledge_search` | `test_knowledge_page.py` |
| P3 consolidation | `consolidate.py`、`cli_main.py:memory consolidate` | `test_memory_consolidate.py` |
| P4 脱敏 | `memory_guard.py:redact/redact_obj`、`memory.py` 写入接线 | `test_memory_redaction.py` |

**已明确的边界：**

- 生产库迁移是显式命令，不在启动时自动改数据；`migrate-factual` 默认 dry-run。
- chat 类 SKILL 不迁移到 REFERENCE（对话建议不是持久事实），只保留审计。
- consolidation 默认 dry-run；`--apply` 才写；原节点保留。
- knowledge page 只投影 active procedural SKILL + active REFERENCE/BELIEF；chat/factual SKILL 不投影。
- `proof_count` 由 `source_ids` 去重计数，不是模型自报置信度。
- 生产全量回归和迁移执行结果另行记录，不用本文件的“代码已实现”替代实测。
