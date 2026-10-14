# R269 RSIAgent 营养吸收 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 RSIAgent 的五个机制（经验闭环、对账更新、语义停止、记忆快照、终态机）落地为 DWC 的 lessons 管道＋nightbench 增强，全程机判优先、零固定轮数崇拜。

**Architecture:** 不建新子系统。Lessons 管道（`agent_quality.record_lesson/recall_lessons/lessons_context`＋`var/dwc_lessons.jsonl`）是唯一的记忆写口，五个任务全挂它或 nightbench 循环上；reconcile 默认 dry-run；停止语义只加纯函数＋3 行接线。

**Tech Stack:** Python 3.11+，标准库 only（hashlib/md5 现成），pytest；LLM 只用于 reconcile 一步（按 fail_mode 分组单调用），其余零 LLM。

## Global Constraints

- 机判优先（G2）：成功/停止/终态判定一律代码算，LLM 只做 reconcile 的文本审查，且默认 dry-run 不写。
- 零基线打分（Rule C）：新增分数从 0.0 起；SATURATED 判据用计数，不用"感觉"。
- 测试零真 LLM：reconcile 的 LLM 调用点必须可注入 fake（参数 `llm=None` 即走规则后备——测试只测规则后备与分组逻辑）。
- 精准手术：只动 `scripts/dwc_nightbench.py`（+纯函数＋3 行接线）、`src/dwc/agent_quality.py`（+2 函数＋1 处渲染分支）；不动 `task_exec.py`、`memory.py`、`planner.py`。
- 全量回归必须走 `pytest tests/`（裸 `pytest` 会撞 `scripts/test_candidates.py` 同名——R268 实证，前台 180s 误杀，必须后台）。
- 中文注释/输出；`pytest.raises` ≥5%。

---

### Task 1：nightbench 经验闭环（成功经验也进记忆）

**Files:**
- Modify: `scripts/dwc_nightbench.py`（+`_promote_row(t, ok, how)` 纯函数约 30 行＋主循环接线 3 行）
- Modify: `src/dwc/agent_quality.py:250-266`（`lessons_context` 加 success 分支渲染约 8 行）
- Test: `tests/test_r269_rsi_absorb.py::TestPromote`

**Interfaces:**
- Consumes: `record_lesson(task_id, fail_mode, task, detail)`（agent_quality.py:55，已有，append 写 `var/dwc_lessons.jsonl`）；nightbench 行 `{tid, task_id, kind, ok, verify}`（dwc_nightbench.py:107-111）。
- Produces: `_promote_row(...) -> dict`（写了什么 lesson）；success 行记 `fail_mode="success_pattern:<kind>"`；`lessons_context` 对该 mode 改渲染头"历史成功做法（可复用）："。

**为什么 success 敢进 lessons 表：** `recall_lessons`（agent_quality.py:99）只按任务文本 overlap 捞 top-k，不区分成败；成败由渲染头区分。`lesson_contrast` 加分项对 success 行返回 False（无对照），自然排后——机制自带降权，无需新字段。

- [ ] **Step 1: 写测试** — `_promote_row` 对 ok=True 行返回 `{"mode": "success_pattern:read-fact"}` 且调 `record_lesson`（monkeypatch 记调用）；ok=False 行走原 fail_mode 映射（`classify_fail` 已有？无则用 `"nightbench_fail"` 常量——先 grep，无函数就常量，不发明分类器）；`lessons_context` 对 success 行渲染头含"成功做法"。
- [ ] **Step 2: 跑测试确认失败** — Run: `hermes venv python -m pytest tests/test_r269_rsi_absorb.py -q` Expected: FAIL（函数不存在）。
- [ ] **Step 3: 实现** — nightbench 末尾行落盘后加 `row["lesson"] = _promote_row(...)`；agent_quality 加分支：
```python
if h.get("fail_mode", "").startswith("success_pattern"):
    lines.append("历史成功做法（可复用）:")
    lines.extend("- [%s] %s" % (h.get("task_id"), h.get("detail")) ...)
```
（失败头保持原样，两类分段渲染，先失败后成功。）
- [ ] **Step 4: 跑测试确认通过**。
- [ ] **Step 5: Commit** — `git add scripts/dwc_nightbench.py src/dwc/agent_quality.py tests/test_r269_rsi_absorb.py`（测试文件后续 Task 追加，Task 6 统一提交；本步只跑测试不提交——修正：全计划只在 Task 6 提交一次，避免中间态污染。 TRIAGE：频繁提交 skill 要求 vs 仓库"测试副作用还原"纪律——折中：Task 6 一次提交。）

### Task 2：lessons 对账（reconcile，默认 dry-run）

**Files:**
- Create: `scripts/dwc_lesson_reconcile.py`（约 140 行，adjusted ×3 → ~140；规则＋审计为主）
- Test: `tests/test_r269_rsi_absorb.py::TestReconcile`

**Interfaces:**
- Consumes: `load_lessons()`（agent_quality.py:66）；`LLMClient().complete`（可选注入，`llm=None` 走规则后备）。
- Produces: `_group_by_mode(lessons) -> dict`；`_exact_dupes(group) -> list`（同 task_id＋detail 全等）；`_review_group(mode, items, llm) -> {"keep": [...], "drop": [...], "merge": [...]}`；`main(--dry-run 默认开，--apply 才写)`。

**规则后备（无 LLM 也能跑，测试只测它）：** 同组内 detail 全等即 dupe（drop 留首条）；`task` 全等但 detail 不同即候选 merge（只在 dry-run 里建议，不自动合——合是语义活，不让代码瞎合，Rule 12）。LLM 步：每组一调用，prompt 问"哪些过时/矛盾/超证据"，返回 index 清单；应用前打印 diff，必须 `--apply` 才落盘（原子写 tmp＋os.replace，nightbench 同款纪律）。

- [ ] **Step 1: 写测试** — 构造 5 条 lessons（含 1 对全等 dupe）：`_exact_dupes` 恰抓出那对；`_group_by_mode` 按 fail_mode 分桶数对；`_review_group(mode, items, llm=None)` 规则后备 drop 恰为 dupe；`main` 干跑 fake lessons 不写文件（monkeypatch load_lessons＋tmp VAR）。
- [ ] **Step 2: 跑测试确认失败**。
- [ ] **Step 3: 写脚本** — 含 atomic 写回（只 `--apply`）、G7 式失败计数（写失败 stderr＋计数，不炸）。
- [ ] **Step 4: 跑测试确认通过**。
- [ ] **Step 5: 本地 dry-run** — Run: `python scripts/dwc_lesson_reconcile.py`（读真实 `var/dwc_lessons.jsonl`，只打印不写）Expected: 分组统计＋建议清单，无文件变更（`git status` 干净佐证）。

### Task 3：nightbench 语义停止（SATURATED＋失败加练）

**Files:**
- Modify: `scripts/dwc_nightbench.py`（+`_should_stop(history, k=3)`、`_unseen_fail(ok, how, seen)` 纯函数约 40 行＋主循环接线 5 行）
- Test: `tests/test_r269_rsi_absorb.py::TestStopping`

**Interfaces:**
- Consumes: 主循环行序列（含 ok、verify、lesson mode）。
- Produces: `_should_stop(hist) -> (bool, reason)`：最近 k=3 单"全 ok 且 fail_mode 全见过"即 `(True, "SATURATED")`；`_unseen_fail` 命中未见过 fail 文本即加练标记（整轮至多 +2 单，上限防发散）。

**"见过"的定义（机判，不 LLM）：** 用 `verify` 字符串的首 40 字符作失败签名（nightbench 行的 `how[:60]` 已有，如 `answer contains 'x'`）；ok 单签名记 `"ok"`。k=3 连续 `"ok"` 即停。 ضد自欺：SATURATED 行必须写进 CURVE（`status="saturated_early_stop"`），不能悄悄少跑（Rule 12）。

- [ ] **Step 1: 写测试** — `[ok,ok,ok]` → 停；`[ok,ok,fail]` → 不停；空 history → 不停；加练计数器到 2 封顶（第 3 个 unseen_fail 不加）。
- [ ] **Step 2: 跑测试确认失败**。
- [ ] **Step 3: 实现＋接线** — 主循环 `for i, t in enumerate(picks)` 改为索引 while（支持追加加练单；改动限循环头 5 行，行内逻辑不动）。
- [ ] **Step 4: 跑测试确认通过**。

### Task 4：记忆快照 hash 进跑批

**Files:**
- Modify: `src/dwc/agent_quality.py`（+`memory_snapshot_hash() -> str` 约 15 行）
- Modify: `scripts/dwc_bench2.py`（summary 加 `memory_sha` 1 行）、`scripts/dwc_organ_ablation.py`（同 1 行）
- Test: `tests/test_r269_rsi_absorb.py::TestSnapshot`

**Interfaces:**
- Consumes: `LESSONS`（agent_quality.py:24）＋`SKILLS_DIR`（:124）。
- Produces: `memory_snapshot_hash()`＝md5（lessons 文件字节＋skills 文件名排序串）。文件缺席记 `"empty"` 不炸（新环境）。

- [ ] **Step 1: 写测试** — tmp VAR 下写两行 lessons → hash 稳定（调两次相等）；加一行 → 变；文件删掉 → `"empty"`。（monkeypatch `agent_quality.VAR` 指向 tmp_path——先确认 VAR 是模块级变量可 patch；是：第 24/124 行用法即模块级。）
- [ ] **Step 2: 跑测试确认失败**。
- [ ] **Step 3: 实现** — bench2 `summ` 加 `"memory_sha": memory_snapshot_hash()`（第 152 行处）；ablation 同（其 summ 构造处）。import 已有（bench2 侧需 `from dwc.agent_quality import ...`——ablation 已有 lessons_context 的 try/except 导入模式，照抄）。
- [ ] **Step 4: 跑测试确认通过**。

### Task 5：终态三态机（DONE/FAIL/STALLED＋升级）

**Files:**
- Modify: `scripts/dwc_nightbench.py`（+`_terminal_state(ok, rep) -> str` 纯函数约 15 行＋接线 4 行）
- Test: `tests/test_r269_rsi_absorb.py::TestTerminal`

**Interfaces:**
- Consumes: 行 `{ok, status}`（status 来自 agent 报告或 `"timeout/no-report"` 缺省，dwc_nightbench.py:102）。
- Produces: `ok=True→"DONE"`；`rep 空→"STALLED"`（触发 `_inbox_push("【STALLED升级】%s ..." )`，复用现有 `_inbox_push`，agent 下轮优先消费——owner 即"写进 agent 真实消费路径"，与 nightbench 设计语义一致）；其余→`"FAIL"`。行加 `terminal` 字段进 CURVE。

- [ ] **Step 1: 写测试** — 三分类各一例；STALLED 例断言 `_inbox_push` 被调且文本含原 tid（monkeypatch 记调用，不写真 inbox——R264 纪律：测试禁碰生产 inbox，用 tmp 覆写 INBOX？nightbench 的 INBOX 从 `dwc.agent_rpc` import——conftest 已把 `DWC_VAR_DIR` 指 tmp，agent_rpc.VAR 读它，故测试天然隔离。先确认 agent_rpc.VAR 读 env：R264 conftest 注释即此机制，直接依赖它。）
- [ ] **Step 2: 跑测试确认失败**。
- [ ] **Step 3: 实现＋接线**。
- [ ] **Step 4: 跑测试确认通过**。

### Task 6：回归＋交付（知识档＋提交＋同步）

**Files:**
- Create: `tests/test_r269_rsi_absorb.py`（Task 1–5 累积，目标约 25 tests，raises ≥2）
- Create: `archive/knowledge3_R269_rsi_absorb.json`（走 `validate_inheritance`，gen=269，parent 268）
- Modify: `docs/PROGRESS.md`（R268→R269，287→288 commits）

- [ ] **Step 1: 新测试全绿** — Run: `pytest tests/test_r269_rsi_absorb.py -q` Expected: 全 PASS。
- [ ] **Step 2: 后台全量回归** — Run: background `pytest tests/ -q -p no:randomly > /Temp/pytest_r269.log`，等通知后确认 `passed` 且数＝上轮＋新增（1680＋N），`PYTEST_EXIT=0`。
- [ ] **Step 3: gate＋双 e2e** — Run: 三脚本全 rc=0；副作用文件（epoch_ledger/gate_trace/challenger_duel/dep_scan/table8_status）`git checkout --` 还原。
- [ ] **Step 4: 知识档＋提交推送＋同步 .dwc** — ledger 过 `validate_inheritance`；commit（英文展开式）；push master；cp 改动脚本到 `.dwc/scripts`＋md5 对齐。不重启 agent（全是 eval/记忆管道脚本，不进常驻路径——R268 同例）。
- [ ] **Step 5: 真机 smoke（cron 前验证）** — Run: `dwc_lesson_reconcile.py` dry-run（已 Task 2 做过，跳过）；nightbench 不动（等 02:30 cron 自然跑，新逻辑随首轮上线，次日看 CURVE 的 terminal/saturated 行）。

## Self-Review

- **Spec 覆盖：** ①→Task1，②→Task2，③→Task3，④→Task4，⑤→Task5（范围修正说明见下），回归交付→Task6。无遗漏。
- **范围修正（诚实记录）：** 深度思考消息里"⑤ planner 配三 decision"在钉签名时发现放错了位——planner（planner.py:175 `craft`）是单任务 spec 构建器，lifecycle 语义住在 nightbench 主循环；三态机改落 nightbench，planner 不动。动 planner 才是顺手优化（违反精准手术）。
- **Placeholder 扫描：** 无 TBD；`classify_fail` 存疑点已写明"先 grep，无则常量"；VAR 可 patch 性已逐行确认（agent_quality.py:24/124 模块级）。
- **类型一致：** `record_lesson(task_id, fail_mode, task, detail) -> None`（:55）；`lessons_context(task, k=3) -> str`（:250）；nightbench 行字段（:107-111）；`verify(check, answer) -> tuple`（bench2 原签名）。`_promote_row/_should_stop/_terminal_state/memory_snapshot_hash` 签名全计划统一。
- **行数估计：** 新增约 230 行产品＋约 200 行测试（拼装/接线类，系数 ×3 已含测试），无研究算法，无 5–8× 膨胀风险。
