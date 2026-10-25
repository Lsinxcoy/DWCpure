# DWC pure 记忆系统强化 M0–M3 · 代码级方案

> 版本：2026-10-25 · 依据：`docs/research/MEMORY_CROSS_PROJECT_AUDIT.md` + 9 个参考仓库 commit（`docs/research/memory_sources.json`）。
> **落地状态（2026-10-25）**：M0、M1.1、M1.2、M1.4、M1.6 已实现；M1.3、M1.5、M1.7、M1.8 及 M2–M3 仍为设计，不得写成已实现。
> 实测：主仓非真端点（排除 r208 lifecycle）`3228 passed / 2 skipped`；另有被忽略文件的本地子集 `5 passed`；gate `8/8`；生产 8 条 skill 分类 = `7 factual + 1 chat + 0 procedural`。
> 本文是**实施规格 + 当前落地记录**；状态以代码/测试/生产读回为准。
> 机制矩阵：`docs/research/memory_mechanism_matrix.csv`（MEM-01–MEM-19）。

## 0. 最终裁定

DWC 的记忆底座已经够用，当前瓶颈是**消费链**和**技能质量**，不是机制数量。

优先级固定：

```text
M0 测量与消费闭环
  → M1 过程技能 + 轨迹 + 写入门
  → M2 边 / SELF / 偏好信念 / 上下文预算
  → M3 维护、检索质量、条件扩展
```

不新增 W6；不把向量库、RL、MemPO、多 agent notebook 作为前置。任何新机制必须有真实消费者、测试、失败语义；没有就 `conditional` 或 `reject`。

## 1. 当前事实（2026-10-25 生产读回）

```text
memory_node = 24
  trace = 17（17 条 access>0，11 条 effect>0）
  skill = 7（7 条 access=0，effect=0）
failure_sig = 0
```

三个硬事实：

1. `executor.memory_text()` 能召回 skill（实测 factorial 技能返回 771 字符），但只读 `memory_node`，不更新 `access_count`。
2. 7 条 skill 中 6 条是最终答案/事实（阶乘定义、求和公式），不是过程。
3. `run_term._step()` 的 trace 只有 `{action, task, step}`，不是工具执行轨迹；M1 的过程抽取必须先补轨迹，不能从现有 trace 编步骤。

## 2. 与 W1–W5 的映射

| 工作流 | 本方案落点 |
|---|---|
| W1 真实测量 | M0 的 retrieval 事件、access/effect 转化、token 成本 |
| W2 固定评价 | M1 的技能质量分级、M3 的检索质量指标 |
| W3 诊断 | M1 的成功/失败对比、M2 的边与多跳证据 |
| W4 候选与经验 | M1 的过程技能、M2 的偏好/信念、M3 的经验写门 |
| W5 运行时 | M2 的上下文预算、M3 的条件检索策略 |

身份分层沿用 DWC 现有 `pair/run/candidate/attempt`；记忆侧新增 `retrieval_id`、`skill_kind`、`evidence_ref`，不发明第二套身份。

## 3. M0 · 测量与消费闭环（先做）

### M0.1 `MemoryKernel.record_retrieval()`

文件：`src/dwc/organs/memory.py`

```python
def record_retrieval(
    self,
    query: str,
    route: str,
    node_ids: list[str],
    scores: list[float] | None = None,
    source: str = "",
    touch: bool = True,
) -> str:
    """记录一次检索；touch=True 时同时增加 access_count/last_access。"""
```

规则：

- `node_ids` 去重保序；空列表也记录（用于 zero-result）。
- `touch=True` 只更新真实进入 prompt/决策的节点；`touch=False` 供 `recall_many` 已自行更新时使用。
- 一次检索写一行 `memory_retrieval`，字段：`retrieval_id, query, route, source, n_hits, selected_ids, scores, created_at`。
- 不记录原始大对象；query 截断 500 字符。

### M0.2 `memory_retrieval` 表

文件：`src/dwc/organs/memory.py:SCHEMA`

```sql
CREATE TABLE IF NOT EXISTS memory_retrieval (
    retrieval_id TEXT PRIMARY KEY,
    query        TEXT NOT NULL,
    route        TEXT NOT NULL,
    source       TEXT,
    n_hits       INTEGER NOT NULL,
    selected_ids TEXT NOT NULL DEFAULT '[]',
    scores       TEXT NOT NULL DEFAULT '[]',
    created_at   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_retrieval_route ON memory_retrieval(route, created_at);
```

老库启动时 `CREATE TABLE IF NOT EXISTS` 自动补表，不需要迁移脚本。

### M0.3 `MemoryKernel.retrieval_stats()`

```python
def retrieval_stats(self, route: str | None = None) -> dict:
    """返回 n_retrievals / n_with_hits / n_zero / hit_rate / n_selected / n_unique_nodes。"""
```

口径：

- `hit_rate = n_with_hits / n_retrievals`；无检索时 `None`，不是 0。
- `n_unique_nodes` 从 `selected_ids` JSON 解析；坏行跳过并计数 `n_bad_rows`，不静默。
- 按 route 分组返回 `by_route`。

### M0.4 `recall_many` 记事件

文件：`src/dwc/organs/memory.py:recall_many`

在现有 access 更新后调用：

```python
self.record_retrieval(scene, "recall_many", ids, touch=False,
                      source="run_term")
```

禁止重复 +1：`recall_many` 已更新 access，事件只记账。

### M0.5 `executor.memory_text()` 记 skill 使用

文件：`src/dwc/llm/executor.py:memory_text`

- 查询改为 `SELECT node_id, payload`。
- `skills` 保存 `(node_id, payload, bigrams)`；`scored` 保存 `(node_id, cov, hit_count, payload_json)`。
- 渲染完成后，若有选中节点，调用：

```python
memory.record_retrieval(task, "skill_prompt", ids, scores,
                        source="memory_text", touch=True)
```

- 无命中时也调用 `record_retrieval(task, "skill_prompt", [], [], source="memory_text")`，用于 zero-result。
- 用 `getattr(memory, "record_retrieval", None)` 守卫 fake memory；不要因测量失败中断 prompt 构造。

### M0.6 测试

新增 `tests/test_memory_retrieval.py`：

1. `test_memory_text_records_access_and_event`：写入 D6 完整 SKILL，按同任务调用 `memory_text`；断言 `access_count == 1`，`retrieval_stats()["n_with_hits"] == 1`，`selected_ids` 含该 node。
2. `test_memory_text_zero_hit_is_recorded`：无关任务；断言 access 仍 0，`n_zero == 1`，`hit_rate == 0.0`。
3. `test_recall_many_records_event_without_double_access`：写入 TRACE，调用 `recall_many`；断言 access 恰为 1，事件 1 条。
4. `test_retrieval_stats_empty`：空库；断言 `n_retrievals == 0`、`hit_rate is None`。
5. `test_record_retrieval_dedupes_ids`：同一 node 重复传入；断言 access +1、selected_ids 唯一。

### M0 验收

- 真实任务后，被 prompt 使用的 skill `access_count > 0`。
- `memory_retrieval` 有 query/route/hits；zero-result 可查。
- 现有全量测试不回归。
- 不把 dashboard 读取、审计脚本读取算作 access。

## 4. M1 · 过程技能 + 轨迹 + 写入门

### M1.1 `skill_writer.classify_skill_kind()`

文件：`src/dwc/organs/skill_writer.py`

```python
def classify_skill_kind(scene: str, method: str) -> str:
    """返回 procedural / factual / chat。"""
```

判据（先规则、可审计，不引 LLM）：

- `procedural`：含步骤/动作词（先、然后、步骤、读取、定位、修改、运行、验证、检查、执行、diff、test）且至少 2 个动作，或含 `steps`/`tools` 字段。
- `factual`：方法主要是定义/公式/最终数值/单句答案，且没有动作序列。
- `chat`：长对话式回答、含“我认为/你可以/建议”等，且没有任务过程。
- 不确定 ⇒ `factual`（保守，不冒充过程）。

`from_term()` 增加 `skill_kind` 字段；`lesson_to_payload()` 同样带 `skill_kind`。先只加元数据，不删旧数据；M1.2 再按 kind 过滤。

### M1.2 过程字段（已实现）

文件：`src/dwc/organs/skill_writer.py`

```python
def procedure_from_actions(actions_log, evidence_ref="") -> dict:
    """只从真实 phase=obs 动作抽 steps/tools/verification/failure_modes。"""

def from_task_result(memory, task, prompt, result, passed, quality=None) -> str | None:
    """已判分通过 + 有真实 actions_log ⇒ 写过程技能；否则 None。"""
```

`from_term(..., procedure: dict | None = None, evidence_ref: str = "")`：

```python
payload = {
  "scene": ..., "method": ...,
  "preconditions": procedure.get("preconditions", []),
  "steps": procedure.get("steps", []),
  "tools": procedure.get("tools", []),
  "verification": procedure.get("verification", []),
  "failure_modes": procedure.get("failure_modes", []),
  "recovery_strategies": ...,
  "evidence_ref": evidence_ref,
  "skill_kind": classify_skill_kind(scene, method),
  ...
}
```

没有 `procedure` 时：`skill_kind=factual`，仍可写但 `memory_text` 默认不把它当过程技能（M1.3）。

### M1.3 `memory_text` 过滤

- 增加 `include_factual: bool = False`。
- 跳过 `skill_kind == "factual"`；旧数据没有字段 ⇒ 视为 `legacy`，先保留，迁移脚本再分类。
- 迁移脚本 `scripts/audit_memory_skills.py`：列出每条 skill 的 `skill_kind`、access/effect；`--mark` 只写元数据，不删除。

### M1.4 轨迹记录（已实现）

文件：`src/dwc/llm/task_trajectory.py`

真实工具轨迹在 `task_exec._do_action()` 的 `actions_log`，不在 `run_term._step()`（后者是进化周期回执）。`execute_user_task()` 统一收尾时调用：

```python
record_task_trajectory(result) -> {
  "trajectory_ref": "<path>#TRJ_...",
  "trajectory_path": ..., "trajectory_id": ...,
  "trajectory_steps": N, "trajectory_sha256": "sha256:...",
  "trajectory_status": "recorded",
}
```

规则：

- 只存 `args/obs/answer/why` 的 sha256 与字符数，不内联原文；原始对象仍由 session/tool_raw 负责。
- 空 `actions_log` ⇒ `n_steps=0`，不编步骤；坏 entry 计 `n_bad_steps`，不静默丢。
- 写失败 ⇒ `trajectory_status=error` + `trajectory_error`，不掀任务。
- `trajectory_ref` 进入 `task_metrics.trajectory_ref`，供 M1.2 过程技能引用。

没有真实工具调用的 term 标 `trajectory_status=not_instrumented`，不编步骤。

### M1.5 成功/失败对比

- 同一 task 的失败签名 + 成功轨迹 ⇒ `contrast` 记录：`first_divergence_step`、`changed_action`、`verification`。
- 只有成对证据才写“差异技能”；单边成功/失败不写因果。
- 进入 `dream` 的候选必须带 `evidence_ref`。

### M1.6 `MemoryWriteGuard`（已实现）

文件：`src/dwc/organs/memory_guard.py`

```python
CHANNEL_TRUST = {
  "tool_output": 0.15, "llm_self_report": 0.35,
  "lesson_ledger": 0.60, "task_trajectory": 0.60,
  "user_message": 0.80, "system_summary": 0.50,
}

def validate(content, source="unknown", context=None) -> dict:
    """passed/reason/channel/trust_score/checks/quarantine。"""
```

检查：空内容、超长（120k）、控制字符、注入模式、重复填充。

接入：

- `MemoryKernel.remember(..., source_channel=None)`：默认不校验，旧调用零变化；显式通道才 enforce。
- 失败 ⇒ `memory_quarantine`（hash/键名/原因/字符数，不存原文）⇒ 抛 `MemoryQuarantineError`。
- `skill_writer` 三条通道：`from_term="llm_self_report"`、`promote_pending="lesson_ledger"`、`from_task_result="task_trajectory"`。
- `promote_pending` 的 `n_quarantined` 是 `n_skip` 子计数，`n_seen = n_written + n_dup + n_skip` 仍成立。

未做：不判断内容真假、不调用 LLM 分类器、不删除已入记忆；这些留给 M3。

### M1.7 `WorkingState` 证据门

文件：`src/dwc/organs/memory.py` 或新 `src/dwc/organs/working_state.py`

```python
class WorkingState:
    def propose_update(self, goal_id, status, evidence, claimed=False): ...
```

规则：`done` 必须有非空 evidence；`blocked` 必须有 blocker；claim-only 返回 `truth_bounce_no_env_evidence`。与 ARSI `checker_evidence_required` 同构，但不复制其类名。

### M1.8 `ConsolidationGuard`

- `dream()` 保持只读；`learn()` 只写新节点；`revise()` 保留旧节点 + `_revised_to`。
- 新增 `memory_edge(relation="consolidates_to")` 记录“新技能来自哪些旧节点”。
- 测试：巩固前后原节点 payload 哈希不变。

### M1 验收

- 新 skill 至少 3 个步骤、1 个验证、1 个失败模式，或明确 `factual`。
- 过程技能能从 `evidence_ref` 回溯到轨迹。
- 工具输出注入/二进制/重复写入被 quarantine 并可审计。
- `done` 无证据被拒。
- 原节点在巩固/修订中不被覆盖。

## 5. M2 · 边 / SELF / 偏好 / 上下文预算

### M2.1 `memory_edge`

```sql
CREATE TABLE memory_edge (
  edge_id TEXT PRIMARY KEY,
  source_id TEXT NOT NULL,
  target_id TEXT NOT NULL,
  relation TEXT NOT NULL,
  weight REAL NOT NULL DEFAULT 1.0,
  evidence_ref TEXT,
  created_at REAL NOT NULL
);
```

API：

```python
MemoryKernel.link(source_id, target_id, relation, weight=1.0, evidence_ref="")
MemoryKernel.neighbors(node_id, relation=None, depth=1) -> list[dict]
MemoryKernel.multi_hop(node_id, max_depth=2) -> list[dict]
```

关系：`task→failure_sig`、`skill→invalid_condition`、`skill→recovery`、`episode→skill`、`entity→event`。先 SQLite 邻接表，不引图数据库。

### M2.2 `Zone.SELF`

- 新增 `Zone.SELF`；`MemoryKind.IDENTITY` / `STANDING_RULE`。
- `protected=True`：evolver/候选不得覆盖；只允许 `revise()` 版本链。
- `remember()` 对 SELF 强制 `source_channel=user_message` 或 `maintainer`；工具输出不得写 SELF。
- 读取记 access；SELF 不参与普通淘汰。

### M2.3 `PREFERENCE` / `BELIEF`

- 新 kind：`PREFERENCE`、`BELIEF`。
- 字段：`topic, stance, confidence, evidence_refs, support_count, contradict_count, source_trust, last_confirmed`。
- `observe_preference(topic, stance, evidence_ref, source)`：强化/弱化，不覆盖历史。
- `revise_belief(node_id, new_stance, evidence_ref)`：旧信念保留，新增 `_revised_to`；矛盾计数增加。
- 只有用户明确纠正/确认、或可验证事件才能改；模型自评不算。

### M2.4 `MemoryContextAssembler`

文件：`src/dwc/organs/memory_context.py`

```python
assemble(task, budget_tokens, *, include_self=True, include_skills=True,
         include_episodes=True) -> dict:
    {"text": str, "used_ids": [...], "tokens": int, "truncated": bool,
     "raw_refs": [...]}
```

顺序：SELF → 当前任务 → 相关 skill → 最近 episode → 原始 trace。逐字/摘要双通路；摘要必须带 `raw_ref`；超预算先裁摘要，不裁证据引用。

### M2.5 检索质量指标

- `retrieval_stats` 增加 MRR/NDCG（需要 labeled relevance；没有标签时返回 `None`，不伪造）。
- `memory_retrieval` 增加 `later_effect`（后续是否 effect）；由 `record_effect` 回填。
- 看板：hit rate、zero-result、skill 复用率、召回组 vs 未召回组成功率。

## 6. M3 · 维护、质量与条件扩展

### M3.1 可解释维护

`maintain()` 增加策略：

```text
KEEP / ARCHIVE / MERGE / DELETE
```

删除条件必须同时满足：`access_count == 0`、`effect_count == 0`、不是唯一签名、非 SELF。禁止年龄淘汰。每条决策写 `memory_maintenance` 事件（reason/evidence）。

### M3.2 成功/失败对比

`contrast.py`：

```python
compare(failure_sig_id, success_trajectory_id) -> {
  first_divergence_step, changed_action, verification, evidence_refs, confidence
}
```

只有成对证据才写“差异技能”；单边不写因果。

### M3.3 轨迹拼接 / 记忆程序

- 只在有真实 `TrajectoryRecorder` 数据后做 stitching；`fitness` 用任务成功/成本/验证覆盖，不用自评分。
- `MemoryProgram` 若引入，必须有 lineage、episodes、failure_type、lifecycle；否则不做。

### M3.4 条件检索

- 先 benchmark 现有 FTS5 trigram/LIKE/2-gram/LLM 扩展：hit rate、zero-result、token 成本。
- 不足再考虑 CJK 分词/BM25（v11）或 TF-IDF（ARSI）；向量库/混合检索最后。
- MemPO/RLNavigator/ExternalNotebook 保持关闭，除非有配对 effect 数据和真实消费点。

## 7. 分阶段实施包与机制覆盖索引

| ID | 阶段 | 去向 |
|---|---|---|
| MEM-01 | M0 | skill access 记录 |
| MEM-02 | M0 | retrieval 事件表 |
| MEM-03 | M0 | retrieval stats |
| MEM-04 | M1 | skill kind 分类 |
| MEM-05 | M1 | 过程字段 |
| MEM-06 | M1 | trace 富化 |
| MEM-07 | M1 | WorkingState 证据门 |
| MEM-08 | M1 | ConsolidationGuard |
| MEM-09 | M1 | MemoryWriteGuard |
| MEM-10 | M2 | memory_edge |
| MEM-11 | M2 | SELF 保护区 |
| MEM-12 | M2 | PREFERENCE/BELIEF |
| MEM-13 | M2 | 上下文预算/双通路 |
| MEM-14 | M2 | MRR/NDCG |
| MEM-15 | M3 | 可解释维护 |
| MEM-16 | M3 | 成功/失败对比 |
| MEM-17 | M3 | 轨迹拼接/程序谱系 |
| MEM-18 | M3 | CJK/混合检索 benchmark |
| MEM-19 | M3 | MemPO/RL 条件关闭 |

## 8. 测试矩阵

| 测试 | 覆盖 | 断言 |
|---|---|---|
| `test_memory_retrieval.py` | M0 | access/事件/zero-hit/dedupe |
| `test_skill_quality.py` | M1.1 | procedural/factual/chat；过程字段 |
| `test_skill_procedure.py` | M1.2 | 真实 actions_log 抽步骤；无动作不编 |
| `test_task_trajectory.py` | M1.4 | refs/hash；坏 entry 计数；任务接线 |
| `test_memory_guard.py` | M1 | 注入/二进制/重复拒绝；quarantine |
| `test_memory_working_state.py` | M1 | claim-only done 被拒 |
| `test_consolidation_guard.py` | M1 | 原节点哈希不变 |
| `test_memory_edges.py` | M2 | 2 跳召回与关系证据 |
| `test_memory_self.py` | M2 | evolver 不能覆盖 SELF |
| `test_memory_belief.py` | M2 | 纠正降权、矛盾计数 |
| `test_memory_context.py` | M2 | token 预算、raw_ref |
| `test_memory_maintenance.py` | M3 | 删除四条件 |
| `test_memory_contrast.py` | M3 | 成对证据才写差异 |

## 9. 验收指标

```text
write → recall → effect 转化率
skill 复用率（access>0 / 可用过程 skill）
retrieval hit rate / zero-result / MRR
过程技能合格率（steps/verification/failure_modes）
注入/二进制/重复写入拒绝率
每次召回 token 成本
召回组 vs 未召回组成功率差（A/B）
```

全部相对基线；不拍绝对阈值，不把节点数量当成果。

## 10. 风险与回滚

- `memory_retrieval` 是新增表，不改旧表；回滚只需停止写入并保留表（只读）。
- `memory_text` 记录 access 可能让旧测试看到 access 变化；用 fake memory 守卫，测试显式断言。
- `MemoryWriteGuard` 默认 `unknown` 不阻断旧调用；先 shadow，再按 channel 启用。
- `SELF`/`PREFERENCE` 只允许版本链，不允许物理删除；回滚用 `_rev_prev`。
- 轨迹只存 ref/hash，不存原始大对象；失败时标 `not_instrumented`，不编步骤。

## 11. 冻结声明

- 本方案只做设计/规格，M0 代码落地另行提交；M1–M3 未实现前不得写成已实现。
- 参考仓库 commit 冻结在 `docs/research/memory_sources.json`。
- 任何新机制进入主线前必须满足：有消费者、有测试、有失败语义、有回滚。

### 来源

- 跨项目审计：`docs/research/MEMORY_CROSS_PROJECT_AUDIT.md`
- 机制矩阵：`docs/research/memory_mechanism_matrix.csv`
- 参考 commit：`docs/research/memory_sources.json`
