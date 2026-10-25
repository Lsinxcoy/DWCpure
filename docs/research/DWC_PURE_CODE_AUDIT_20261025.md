# DWC pure 代码严格审计报告

- 审计对象：`Z:\DWC pure`
- 审计提交：`af89f24`（代码基线 `ee754aa`，HEAD 仅文档同步）
- 审计日期：2026-10-25
- 审计方式：默认全量测试 + 行覆盖 + ruff + bandit + vulture + radon + pip-audit + 导入烟测 + 生产 SQLite 只读读回 + 受控纯函数探针
- 原则：**声称=实测**；代码存在 ≠ 已激活；测试通过 ≠ 安全边界成立

---

## 0. 结论摘要

DWC pure 是一个**功能测试很强、但安全边界和运行时激活明显不足**的代码库。

| 维度 | 实测 | 评级 |
|---|---|---|
| 可构建 / 导入 | `compileall` 通过；156/156 子模块导入成功 | A |
| 测试 | 3294 collected；**3285 passed / 9 skipped / 0 failed** | A- |
| 行覆盖 | **86.9%**（16912/19459）；157 个源文件 | B+ |
| 质量门 | `gate.py` **8/8** | A- |
| 静态质量 | ruff **3736** 条（src+scripts）；bandit **77** 条 | D |
| 安全 | 2 个 P0 任意代码/命令执行面；1 个 SSRF；1 个路径前缀绕过 | F |
| 正确性 | 1 处不可达重试；1 处未定义变量被吞；1 处 `done` 语义错误 | C- |
| 机制激活 | 19 项记忆中仅 **5 项热路径活跃**，2 项部分，12 项测试/脚本专用 | D |
| 性能 / 可维护性 | 54 个 D/E/F 复杂度块；最高 `_execute_user_task_impl` 复杂度 **232** | C- |
| 可运维性 | agent 存活、RPC 正常、gate 通过；无 CI / 无 lint 配置 / 无锁文件 | B- |
| 文档一致性 | README 仍写 3273 passed、R438、547 commits，并声称 ruff/bandit/F821 清零 | D |
| 依赖安全 | pip-audit：25 个依赖，**无已知漏洞**；但无 lock file | B- |

**总体判定：可以作为受控开发/实验系统继续使用，但不能按当前状态宣称为“生产级安全 agent”。**  
最优先不是加功能，而是先封住 `run_command` 和 `exec` 两条任意代码执行面，再修正不可达重试和未激活机制。

---

## 1. 证据快照

| 项目 | 证据 |
|---|---|
| 测试 | `3285 passed, 9 skipped in 661.07s`（带 coverage 的默认全量） |
| 收集 | `3294 tests collected` |
| 覆盖 | `coverage.json`：`percent_covered=86.91`，`covered_lines=16912`，`missing_lines=2547` |
| 质量门 | `gate.py --json`：8 项，8 pass |
| 导入 | `pkgutil.walk_packages`：156 个模块导入，0 失败 |
| 静态 | `ruff check src scripts`：3736 diagnostics；`tests`：2594 diagnostics |
| 安全扫描 | bandit：77 results；HIGH 5（B324），MEDIUM 18（B608 8 / B310 7 / B102 3） |
| 依赖 | pip-audit：25 dependencies，`No known vulnerabilities found` |
| 复杂度 | radon：1581 blocks，平均 B（6.10），D/E/F 54 个 |
| 生产读回 | `memory_node=37`、`skill=8`、`trace=27`、`failure_sig=2`、`memory_edge=0`、`memory_quarantine=0` |
| 生产 agent | pid `1015496`，RPC 8802，心跳 alive |

原始扫描产物：

- `C:/Users/41228/AppData/Local/hermes/cache/scratch/ruff_dwc.json`
- `C:/Users/41228/AppData/Local/hermes/cache/scratch/bandit_src.json`
- `C:/Users/41228/AppData/Local/hermes/cache/scratch/dwc_coverage.json`
- `C:/Users/41228/AppData/Local/hermes/cache/scratch/pip_audit.json`
- `C:/Users/41228/AppData/Local/hermes/cache/scratch/dwc_gate_audit.json`

---

## 2. P0 · 任意代码 / 命令执行面

### SEC-01 · `run_command` 黑名单可被普通命令绕过

**证据**

- `src/dwc/llm/task_exec.py:38-47`：危险命令是**子串黑名单**，注释自己写明“不是完备沙箱，是护栏”。
- `src/dwc/llm/task_exec.py:620-626`：只做 `joined` 子串匹配。
- `src/dwc/llm/task_exec.py:647-676`：通过后直接 `subprocess.run(cmd, cwd=ROOT, ...)`，没有容器、chroot、用户隔离或路径限制。
- 受控探针（未执行破坏命令）：
  - `python -c "import shutil; shutil.rmtree('x')"`：`_FORBIDDEN` 无命中，`_ask_level()` 返回 `None`。
  - `powershell -Command Remove-Item x`：同样无命中、无 ask。
  - `rm  -rf x`（双空格）只命中 `_ASK` 的 `rm `，不是硬拒。

**影响**

- 收件箱任务、网页内容或模型输出中的提示注入，可让 agent 以当前用户权限执行任意命令。
- `read`/`write` 的 `_guard_path` 只约束工具动作，不约束 `run_command` 子进程；写白名单和读仓库限制可被 shell 绕过。
- 这是 **P0**：不是“理论风险”，是当前代码路径的真实能力。

**建议**

1. 生产默认禁用 `run`，或改为**命令 allowlist**（只允许明确的测试/构建命令）。
2. 需要执行时，放进低权限子进程/容器，限制工作目录、网络、环境变量和可写路径。
3. 所有非 allowlist 命令一律拒绝，不依赖子串黑名单；黑名单只能作为额外告警，不能作为安全边界。
4. 增加回归测试：`python -c os.remove`、PowerShell、`cmd /c`、换行拼接、路径前缀、大小写/空格变体都必须被拒。

### SEC-02 · `actor` / `candidates` 对模型代码执行无 AST 防护的 `exec`

**证据**

- `src/dwc/organs/actor.py:477-482`：`exec(compile(body, ..., "exec"), ns)`，`ns` 是普通空字典，**没有受限 `__builtins__`**。
- `src/dwc/organs/candidates.py:178-184`：`exec(compile(src, "<baseline>", "exec"), ns)`，同样没有 AST 门卫。
- 受控探针：向 `PureFunctionExecutor` 传入 `import os; def probe(n): return os.getcwd()`，构造成功并返回 `Z:\DWC pure`，证明 `import` 可执行。
- `src/dwc/llm/sandbox.py` 已有 `_Guard`（禁 Import/ImportFrom、禁双下划线、禁 while、资源上限），但 `actor.py` 没有使用它。

**影响**

- 候选/修复代码来自 LLM 或外部任务时，`import os`、`subprocess`、文件读写、网络访问都可执行。
- 这与 `sandbox.py` 的安全模型不一致：一个模块做了 AST 防护，另一个热路径完全绕过。
- 这是 **P0**，与 SEC-01 同属“模型输出 → 宿主执行”。

**建议**

1. `PureFunctionExecutor` 和 `_baseline_reproduces` 统一走 `sandbox` 的 AST 门卫 + 受限 builtins。
2. 禁止 `Import`/`ImportFrom`/`__` 属性/`open`/`exec`/`eval`/`compile`；只允许纯函数子集。
3. 更高保证：在低权限子进程中执行，父进程只接收 JSON observation；超时/内存/文件描述符硬限制。
4. 增加 escape 测试：`import os`、`__builtins__`、`getattr`、`open`、`subprocess`、`().__class__`、大循环/大内存。

---

## 3. P1 · 高优先级正确性 / 安全 / 激活问题

### COR-01 · 复读熔断后的修订重试是死代码

**证据**

- `src/dwc/llm/task_exec.py:2440-2445`：先 `return {"status": "incomplete", ...}`。
- `src/dwc/llm/task_exec.py:2446-2452`：之后才构造 `_fail` 并调用 `_revision_retry(...)`。
- vulture：`task_exec.py:2446 unreachable code after 'return' (100% confidence)`。

**影响**

- “连续 3 轮同动作同结果”触发时，永远直接返回 incomplete，**不会走任务级修订重试**。
- 端到端上，只有“达轮数上限未 final”的尾部路径会走 `_revision_retry`；复读熔断这条最常见失败路径没有第二次机会。
- 这也会让 M3.3 轨迹拼接的消费场景比预期少。

**建议**

- 把 `_fail`/`_revision_retry` 块移到 `return` 之前；保留“先强制 final”分支。
- 增加回归测试：连续重复动作 → 断言 `_revision_retry` 被调用且可返回第二段结果。

### COR-02 · `dwc_evo_round.py` 未定义 `judge`，泄漏防护被 broad except 吞掉

**证据**

- `scripts/dwc_evo_round.py:502-514`：`for _a in (judge.anchors or {}).values():`。
- 该函数 `run_round(...)` 的签名没有 `judge` 参数；文件内也没有在该作用域定义 `judge`。
- `except Exception: pass` 把 `NameError` 吞掉，`_forbidden` 保持空集，patch 泄漏检查永远不生效。

**影响**

- 注释声称的 “patch 不得包含 benchmark expected_behavior” 防泄漏门实际不执行。
- 这是**静默失效**：没有日志、没有计数、没有告警。

**建议**

- 从调用方传入 `judge`，或从 `trial_fn`/`Judge` 实例取 anchors；不要在未定义变量上 broad except。
- 失败时写 `dedup_check_error` 事件，并 fail-closed（无法检查 ⇒ 拒绝该 patch）。
- 增加测试：带 `expected_behavior` 的 patch 必须被拒；`judge` 缺失时必须报错而不是放行。

### COR-03 · QA “未找到答案”被标成 `status=done`

**证据**

- `src/dwc/llm/task_exec.py:2434-2439`：`status: "done"`，但 `answer` 是“经多轮取证仍未能定位确切依据……未找到直接答案”。

**影响**

- 任务台账、预测器、后续统计会把“未解决”计为 done。
- 如果未来放宽 `result_verified()` 或接其他消费者，可能把“未找到”当成成功样本。
- 与项目自己的“未测≠0、未找到≠通过”纪律冲突。

**建议**

- 改为 `status="incomplete"`，并加 `why="qa_no_evidence"`；如果产品需要“已处理”状态，另设 `processed=True`，不要复用 done。

### ACT-01 · M0–M3 有 12 项“代码/测试存在但生产未激活”

**证据**

以下模块在 `src/` 与 `scripts/` 中没有任何生产 import，只有测试 import：

| 模块 | 机制 | 生产引用 |
|---|---|---|
| `src/dwc/organs/working_state.py` | M1.7 工作态证据门 | 无；仅 `tests/test_memory_working_state.py` |
| `src/dwc/organs/memory_context.py` | M2.4 token 预算组装 | 无；仅测试 |
| `src/dwc/organs/memory_maintenance.py` | M3.1 维护建议 | 无；仅测试 |
| `src/dwc/organs/memory_bench.py` | MEM-18 词法基线 | 无；仅测试 |
| `src/dwc/organs/memory_policy.py` | M3.4 条件扩展 gate | 无；仅测试 |
| `src/dwc/organs/preference.py` | M2.3 偏好/信念 | 无；仅测试 |
| `src/dwc/organs/revision.py` | 记忆修订消费 | 无；仅测试 |

另外：

- `memory.retrieval_stats()`、`memory.retrieval_quality()`：无生产调用方。
- `memory.link/neighbors/multi_hop`：生产只被 `revise`/`preference` 调用，而这两者本身是测试专用；生产 `memory_edge=0`。
- `memory.revise_self()`：无生产调用方；生产 `SELF` zone 节点为 0。
- `core.py:373-380`：`learn` 返回 `not_dispatched: learn 器未实现`；`maintain` 返回“前置=巩固调度触发器（尚未接线）”。
- `src/dwc/harness/__init__.py:4-6`：`step.py`、`ingest.py` 仍标“待实现”，文件不存在。

**影响**

- 机制矩阵里的 `adopt` 只证明“有代码 + 有测试”，**不证明生产在用**。
- 记忆系统的实际热路径仍是旧的 `memory_text` + `recall_many`；M2/M3 的大部分能力没有进入 agent 执行链。
- 这与“已全部落地”的对外表述不一致，必须降级为“代码完成、激活未完成”。

**建议**

- 要么把模块接入真实消费点（如 `executor.memory_text` 接 `memory_context`、`core.maintain` 接 `memory_maintenance`、`task_exec` 接 `working_state`），要么在状态文档中明确标 `implemented_unwired`，不要标 adopt。
- 为每个机制增加“生产调用方”断言测试（grep 只能做辅助，最好有集成测试）。

### ACT-02 · 技能注入实际为 0：8 条技能全是 factual/chat，被 M1.3 过滤

**证据**

- `src/dwc/llm/executor.py:169-204`：`include_factual=False` 时跳过 `factual/chat`。
- 生产读回：`skill=8`，分类为 `7 factual + 1 chat + 0 procedural`。
- 生产 `memory_retrieval`：`skill_prompt` 路由 4 次，`n_hits=0` 4 次；`recall_many` 有命中。
- 生产日志：`task_skill_written=0`；`skill_promoted` 有 7 次，但没有新的过程技能。

**影响**

- 当前每个任务的技能 prompt 实际是空的；记忆系统对任务执行的“技能注入”贡献为 0。
- M1.3 的过滤本身是合理的（不注入最终答案），但没有 procedural 技能供给，等于把技能通道关死。
- 这是“机制存在但效果为 0”的典型：不能拿 `skill=8` 当记忆有效的证据。

**建议**

- 先让 `from_task_result()` 在真实任务中产出 procedural 技能；如果任务没有 `run/test/check` 验证动作，明确记 `not_instrumented`，不要为了填充而放宽门。
- 观测 `skill_prompt` hit rate；在 hit rate > 0 之前，不要声称技能注入有效。
- 可考虑把 `factual` 中“可执行步骤”重分类，而不是整体跳过；但这需要真实任务样本，不能凭感觉改阈值。

### PERF-01 · 每个 `MemoryKernel` 构造都重建 FTS，`from_task_result` 每单新建内核

**证据**

- `src/dwc/organs/memory.py:441-452`：`MemoryKernel.__init__` 每次都执行 `INSERT INTO memory_fts(memory_fts) VALUES('rebuild')`。
- `scripts/dwc_agent.py:710-720`：每个 done 任务都 `MemoryKernel(DB)`，然后 `from_task_result()`，最后 `close()`。

**影响**

- 当前 37 条记忆无感；万级库时，每个任务一次全量 FTS rebuild，延迟和写放大都会变成问题。
- 与注释“启动时 rebuild 一次”不一致；实际是“每个实例一次”。

**建议**

- 只在首次建库/迁移时 rebuild；用 `PRAGMA user_version` 或 meta 表记录 schema 版本。
- 复用长生命周期 `MemoryKernel`，不要在每单内新建连接。
- 加性能测试：1 万条节点下构造时间、单任务写入时间。

### SEC-03 · `web_read` 允许任意 http/https，存在 SSRF

**证据**

- `src/dwc/llm/task_exec.py:483-495`：只校验 `http://` / `https://`，没有 host/IP allowlist，也没有禁止 loopback/私网/link-local。
- `src/dwc/harness/evidence_guard.py:88-92` 有 `enforce_egress()`，但生产没有调用；它本身也总是拒绝（“broker enforcement is not implemented”）。

**影响**

- 模型可让 agent 访问 `127.0.0.1:8802`、内网服务、云元数据地址；虽然 RPC 需要 token，但其他本地服务不一定有。
- 结合 SEC-01，网页内容可进一步驱动命令执行。

**建议**

- 解析 URL 后做 DNS/IP 检查：拒绝 loopback、私网、link-local、组播、保留地址；禁止重定向到私网。
- 生产使用 egress broker/allowlist；`enforce_egress` 要么真正实现，要么不要作为“已有防护”展示。

### SEC-04 · `_guard_path` 前缀判断可被同前缀目录绕过

**证据**

- `src/dwc/llm/task_exec.py:79-91`：读路径用 `p.startswith(ROOT)`，没有分隔符边界，也没有 `realpath`。
- 受控探针：`ROOT=Z:\DWC pure`，`../DWC pure_evil/x` 归一化为 `Z:\DWC pure_evil\x`，被判定为仓库内并返回。
- 符号链接未解析，链接指向仓库外时仍可通过前缀检查。

**影响**

- 读路径可越界到同前缀目录；符号链接可进一步越界。
- 写路径用了 `w + os.sep`，前缀边界较好，但符号链接仍未处理。

**建议**

- 使用 `os.path.realpath` + `os.path.commonpath` 或 `Path.is_relative_to`；拒绝符号链接/重解析点。
- 增加测试：同前缀目录、`..`、符号链接、UNC 路径、大小写差异。

---

## 4. P2 · 中优先级问题

### QUA-01 · 静态质量远未“清零”

- `ruff check src scripts`：**3736** 条；`tests`：**2594** 条。
- 主要类别：`UP031` 1979、`UP006` 409、`SIM115` 163、`UP020` 132、`BLE001` 126、`I001` 121、`RUF100` 117、`UP035` 111、`UP009` 107、`UP045` 104。
- 真正需要看的：`F821` 28、`F401` 40、`F841` 13、`F811` 4、`B023` 9、`S102` 2。
- README 第 90-92 行声称“F821/ruff/bandit 清零”，与实测不符。

### QUA-02 · 静默异常 / broad except 数量大

- `S110`（try-except-pass）：**50** 条；`S112`（try-except-continue）：**17** 条；`BLE001`：**126** 条。
- `src/` 内也有 15 个 S110、11 个 S112、86 个 BLE001。
- 典型：`src/dwc/organs/applier.py:576-583` 注释写“不吞”，实际 `except: pass` 无计数；`src/dwc/llm/task_exec.py:578-584` 信号坏直接 pass。
- 不是所有都错（有些明确是“不拦任务”），但缺少统一失败计数/日志，无法区分“设计内跳过”和“机制坏了”。

### QUA-03 · 113 处直接写文件，只有 45 处原子写

- `open(..., "w")` / `write_text()`：**113** 处；`os.replace`/`tempfile`：**45** 处。
- 高风险：`src/dwc/agent_rpc.py:174` 写 `INBOX_DONE`、`:181` 写 `FROZEN`、`:336` 写 token；`src/dwc/organs/evolver.py:1385/1590/3100` 写学习/归档/rules；`src/dwc/llm/task_exec.py:590` 写任务文件、`:1322` 写 `ASK_ANSWERS`。
- 崩溃/并发下可能留下半截文件；状态文件没有统一 tmp+fsync+replace。

### QUA-04 · 复杂度集中在少数巨型函数

- radon：1581 blocks，平均 B（6.10），**54 个 D/E/F**。
- 最高：`task_exec.py:1593 _execute_user_task_impl` 复杂度 **232（F）**；`usage_pricing.py:204 summarize_candidate` 85；`task_exec.py:434 _do_action` 77；`memory.py:675 recall_search` 61；`run_term.py:1225 _next_task_source` 61；`client.py:721 complete_stream` 58。
- 这些函数同时是安全/计费/记忆的核心路径，测试难覆盖、修改风险高。

### OPS-01 · SQLite 并发策略不明确

- `src/dwc/organs/memory.py:428`：`sqlite3.connect(..., check_same_thread=False)`，但 `MemoryKernel` 没有显式锁，也没有设置 `busy_timeout`。
- 生产 agent 主线程、收件箱 worker、`from_task_result` 都可能写同一库；WAL 允许并发读，但写入仍可能 `database is locked`。
- 建议设置 `PRAGMA busy_timeout`，写路径串行化或使用单写线程。

### OPS-02 · 工程基础设施缺失

- 没有 `.github/workflows` CI。
- 没有 `ruff.toml` / `[tool.ruff]`、mypy、pre-commit、coverage 配置。
- `pyproject.toml` 没有 `license` 字段，仓库根没有 `LICENSE`。
- `requirements.txt` 只有下限（`>=`），没有 lock file；同一提交在不同时间可能装出不同依赖。
- `pytest-cov`、`ruff`、`bandit` 不在项目依赖中，审计/覆盖率不可由仓库自身复现。

### DOC-01 · README 与实测不一致

- `README.md:6`：badge `3273 passed`；实测 **3285 passed / 9 skipped**。
- `README.md:7`：`R1–R438`；上游已到 **R458**。
- `README.md:8`：`547 commits`；当前 `git rev-list --count HEAD = 621`。
- `README.md:87`：`3273 passed`，且“r208 lifecycle 单独超时”。
- `README.md:90-92`：声称“F821/ruff/bandit 清零”；实测 ruff 3736、bandit 77、F821 28。
- `README.md:102`：`R1–R438 · 547 commits · 全量全绿`。
- `docs/DWC_PURE_2.0_IMPLEMENTATION_STATUS.md` 的数字是 3285/9，与代码一致；README 没有同步。

### DOC-02 · 设计文档声称的模块不存在

- `src/dwc/harness/__init__.py:4-6`：`step.py`（内层决策/执行/痕迹）、`ingest.py`（摄入入口）标“待实现”，目录中没有这两个文件。
- `core.py:373-380`：`learn` 未实现、`maintain` 未接线。
- `src/dwc/foundation/retention.py` 只有 `tests/test_r233_retention.py` 引用，没有生产 import；配置校验存在，但模块本身未激活。

### DATA-01 · 生产记忆数据说明“激活不足”，不是“记忆很强”

- `memory_node=37`：`trace=27`、`skill=8`、`failure_sig=2`。
- `skill` 总 access=3，effect=0；8 条中 7 条 access=0。
- `failure_sig=2`，access=0、effect=0。
- `memory_edge=0`、`memory_quarantine=0`、SELF=0。
- `memory_retrieval`：`skill_prompt` 4 次全 0 命中；`recall_many` 7 次全命中。
- `task_skill_written=0`。
- 这些是“机制代码存在但未被消费”的直接数据证据，不能拿节点数当效果。

### REPO-01 · 仓库卫生

- `archive/gate_trace.jsonl` 被 gate 追加后处于 modified 状态；每次跑 gate 都会弄脏工作区。文件 3.75MB，已跟踪。
- `docs/repos/_all.json` 3.4MB，已跟踪；是抓取语料，不是运行代码。
- 工作区 250MB，其中 `var/` 68MB、`.venv/` 33MB、`.venv-audit/` 104MB 都是忽略项；不影响提交，但说明本机审计环境很重。
- 没有发现被跟踪的 `config/llm.json`；本地真实 key 文件被 `.gitignore` 正确排除。未发现被跟踪的 API key/私钥模式（`docs/repos/_all.json` 扫描 0 命中）。

### PORT-01 · 仍有旧机器绝对路径

- `scripts/supply_checkpoint.py:27`：`REPO = r"E:/Divine Wisdom Core"`，无环境变量覆盖。
- `scripts/dwc_agent_patch.py:46-54`：默认 Python/工作目录/报告路径写死 `C:\Users\41228\...`（有 env 覆盖）。
- `scripts/dwc_graded_bench.py:35`、`scripts/dwc_benchmark_adapter.py:203`：默认用户目录路径。
- `src/dwc/foundation/dial_config.py:131`：import 失败时回退 `E:/ARSI/...`。
- 测试中的大量绝对路径多数是 sentinel/反例，不应批量替换；需要逐项看。

---

## 5. P3 · 低优先级 / 需确认

| 项 | 证据 | 说明 |
|---|---|---|
| 弱 SHA1 | bandit B324 ×5：`tool_raw.py:54`、`memory.py:1143`、`skill_writer.py:93`、`task_supply.py:88/306` | 用于 ID/指纹，不是密码学安全；建议加 `usedforsecurity=False` 或换 SHA256，消除扫描噪声 |
| 类型注解未定义 | F821：`client.py:374/378/379` 的 `Dict`；`sandbox.py:200-202` 的 `Dict/List/Optional` | 有 `from __future__ import annotations`，运行时不炸；但 `typing.get_type_hints()` 会失败。补 import 或改内建泛型 |
| 脚本 F821 | `scripts/dwc_bench.py:276 Optional`、`scripts/dwc_evo_round.py:504 judge`、多个 `scan_*.py` 的 `ros` | `ros` 是明显笔误（应为 `os`），这些扫描脚本不可直接运行 |
| B023 闭包 | `core.py:732/735/754/755`、`task_exec.py:2023`、`scripts/ga_duel.py:209-211` | 循环变量闭包捕获；可能取到最后一轮值，需逐个确认 |
| 死条件 | `src/dwc/organs/evolver.py:350` `if delta_c is None and False` | 明确占位，当前行为等于不校验；建议删除或改成真实策略 |
| 空实现 | `src/dwc/organs/evo_targets.py:337` “未实现 smoke” | 返回 `ok=False`，属于诚实边界；不要当成已实现 |
| SQL/B310 告警 | bandit B608 ×8、B310 ×7 | 逐条看过：SQL 都是固定片段 + 参数/白名单；URL 多数固定端点。属于扫描噪声，但 `web_read` 的 SSRF 是真实问题（SEC-03） |
| 测试路径 | 93 个测试绝对路径命中 | 多数是 sentinel/反例/临时目录；不应按“硬编码路径”批量改 |

---

## 6. 机制激活矩阵（比矩阵 CSV 更严格）

矩阵 CSV 的 `adopt` 只代表“代码 + 测试存在”。按生产调用方重新判定：

| ID | 机制 | 生产调用方 | 激活判定 |
|---|---|---|---|
| MEM-01 | skill 召回 access | `executor.memory_text` | **活跃** |
| MEM-02 | retrieval 事件账 | `memory_text` / `recall_many` | **活跃** |
| MEM-03 | retrieval_stats | 无 | 测试专用 |
| MEM-04 | skill_kind 分类 | `skill_writer` / `memory_text` | **活跃** |
| MEM-05 | procedure / from_task_result | `dwc_agent.run_user_task` | **部分**（有验证动作才写；生产 task_skill_written=0） |
| MEM-06 | task trajectory | `task_exec.execute_user_task` | **活跃** |
| MEM-07 | working_state 证据门 | 无 | 测试专用 |
| MEM-08 | 巩固保护 | `revision.py` 仅测试；`learn` 未实现 | 测试专用 |
| MEM-09 | 写入门 | `skill_writer` / `memory.remember` | **活跃** |
| MEM-10 | 边 / 多跳 | `revise`/`preference` 仅测试；生产 edge=0 | 未激活 |
| MEM-11 | SELF 区 | `revise_self` 无生产调用；SELF=0 | 未激活 |
| MEM-12 | 偏好/信念 | `preference.py` 无生产 import | 测试专用 |
| MEM-13 | 上下文预算 | `memory_context.py` 无生产 import | 测试专用 |
| MEM-14 | 检索质量 | `retrieval_quality` 无生产调用 | 测试专用 |
| MEM-15 | 维护建议 | `memory_maintenance.py` 无生产 import | 测试专用 |
| MEM-16 | 成功/失败对比 | `contrast.py` 仅 `dwc_evo_round` 脚本；无配对样本 | 脚本专用 |
| MEM-17 | 轨迹拼接 | `task_exec._revision_retry` | **部分**（复读分支不可达，见 COR-01） |
| MEM-18 | 词法基线 | `memory_bench.py` 无生产 import | 测试专用 |
| MEM-19 | 条件扩展 gate | `memory_policy.py` 无生产 import | 测试专用 |

**统计：5 项活跃（01/02/04/06/09），2 项部分（05/17），12 项未激活/测试或脚本专用。**  
这比“18 adopt / 1 conditional”更接近生产事实。

---

## 7. 维度明细

### 7.1 构建 / 导入

- `compileall src scripts`：通过。
- 156 个 `dwc.*` 子模块全部可导入，0 失败。
- `python -m dwc.cli_main --help`：可运行，返回 0。
- 结论：没有导入级坏模块；问题在运行时行为和安全边界，不是“装不起来”。

### 7.2 测试

- 3294 个用例，3285 通过，9 skip，0 fail。
- 9 skip：7 个 live（`--run-live` 才跑），2 个常规环境 skip。
- 真端点实测：`test_r178` + `test_r185` 的 6 个 live 用例通过；`test_r208_agent.py::test_agent_lifecycle_short_run` 仍会超过 300s，保持 live skip。
- 覆盖 86.9%，但分布不均：
  - `llm/sandbox.py` **56.2%**（安全模块覆盖不足）
  - `cli_main.py` **40.9%**
  - `foundation/updater.py` **45.7%**
  - `agent_rpc.py` **64.8%**
  - `organs/actor.py` **78.5%**
  - `llm/task_exec.py` **84.4%**
  - `organs/memory.py` **87.9%**
- 81 处 FakeLLM/测试替身；测试“接线通过”不等于真实端点/真实安全边界通过。

### 7.3 静态 / 安全

- ruff 3736（src+scripts），主要是风格/现代化；真正需要处理的是 F821/F841/F811/B023/S102/S110/S112/BLE001。
- bandit 77：5 HIGH 全是弱 SHA1（非密码学用途），3 MEDIUM B102 是 `exec`（真实风险），8 B608/7 B310 多数是扫描噪声。
- pip-audit：25 个依赖无已知漏洞。
- 没有发现被跟踪的明文 API key/私钥；本地 `config/llm.json` 被正确忽略。
- RPC 绑定 `127.0.0.1` + token（`src/dwc/agent_rpc.py:330-391`），比公网暴露好；但 token 比较不是常量时间，且本机其他进程可读 token 文件（低风险）。

### 7.4 正确性

- 除 COR-01/02/03 外，还发现：
  - `memory.py:428` 共享连接无锁、无 busy_timeout。
  - `MemoryKernel.__init__` 每次 rebuild FTS（PERF-01）。
  - `task_exec` 的 `run_command` 黑名单不是安全边界（SEC-01）。
  - `actor`/`candidates` 的 `exec` 无 AST 防护（SEC-02）。
- 未发现 SQL 注入：B608 命中处均为固定 SQL 片段 + 参数/白名单。
- 未发现被跟踪的凭证泄漏。

### 7.5 架构 / 激活

- 157 个源文件，18 个“静态 orphan 候选”；逐项核对后多数是动态 import（`from dwc.organs import x`），真正没有生产引用的集中在记忆 M1.7/M2.3/M2.4/M3.1/M3.4/MEM-18。
- `harness/__init__.py` 声称的 `step.py`/`ingest.py` 不存在；`core.learn`/`core.maintain` 未接线。
- 结论：**“代码资产”很多，“被执行的机制”少**；这是当前最大的架构风险，不是缺模块。

### 7.6 性能 / 可维护性

- 54 个 D/E/F 复杂度块；`_execute_user_task_impl` 232 是极端值。
- 巨型文件：`evolver.py` 190KB、`task_exec.py` 140KB、`memory.py` 90KB、`judge.py` 84KB、`run_term.py` 82KB。
- FTS rebuild 每实例一次；`from_task_result` 每单新建内核。
- 113 处直接写文件，只有 45 处原子写。
- 这些会放大并发、崩溃恢复和后续修改风险。

### 7.7 可运维性 / 文档

- 生产 agent 存活、RPC 8802、心跳 alive；gate 8/8。
- 没有 CI、没有 lint 配置、没有 lock file、没有 LICENSE。
- README 的数字和“ruff/bandit/F821 清零”声明已过期/不实；状态文档 `docs/DWC_PURE_2.0_IMPLEMENTATION_STATUS.md` 反而更准确。
- `archive/gate_trace.jsonl` 每次 gate 都变脏；建议改为 ignored/append-only artifact。

---

## 8. 修复路线（建议顺序）

### 立即（P0，先于任何新功能）

1. **封 `run_command`**：默认禁用；或 allowlist + 低权限子进程/容器；不再用子串黑名单当边界。
2. **封 `actor`/`candidates` 的 `exec`**：统一走 `sandbox._Guard` + 受限 builtins，或子进程隔离；补 escape 测试。
3. **修 SSRF**：`web_read` 做 DNS/IP 私网拦截；实现 egress broker 或明确禁用。
4. **修路径前缀/符号链接**：`realpath` + `commonpath`/`is_relative_to`。

### 紧随（P1，正确性/激活）

5. 修 COR-01 不可达重试；补“重复动作 → revision retry”测试。
6. 修 COR-02 未定义 `judge`；泄漏检查 fail-closed + 计数。
7. 改 COR-03 QA 未找到为 incomplete。
8. 决定 M1.7/M2.3/M2.4/M3.1/M3.4/MEM-18 是接入还是标 `implemented_unwired`；不要继续标 adopt。
9. 解决技能注入为 0：产出 procedural 技能，或调整分类/过滤，并用 hit rate 验收。
10. 把 FTS rebuild 改为迁移时一次；复用 MemoryKernel。
11. 加 `busy_timeout` / 单写线程。

### 随后（P2，工程化）

12. 建 CI：pytest + gate + ruff + bandit + coverage 门槛；把 ruff/bandit/pytest-cov 写入 dev requirements。
13. 收敛 F821/F841/F811/B023/S102/S110/S112/BLE001；不要一次性 `ruff --fix` 全库（会碰测试源码字符串和 gate 正则）。
14. 关键状态文件统一 tmp+fsync+replace。
15. 拆 `_execute_user_task_impl` / `_do_action` / `recall_search` 等巨型函数。
16. README 与状态文档对齐：数字、轮次、commit 数、live skip、lint/bandit 现状。
17. 补 LICENSE、lock file、pre-commit。

---

## 9. 复现命令

```bash
cd "Z:/DWC pure"

# 默认全量（live 自动 skip）
.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider

# 行覆盖
.venv/Scripts/python.exe -B -m pytest -q -p no:cacheprovider \
  --cov=src/dwc --cov-report=term:skip-covered \
  --cov-report=json:coverage.json

# 静态
.venv-audit/Scripts/python.exe -m ruff check src scripts --statistics
.venv-audit/Scripts/python.exe -m bandit -r src -q -f json -o bandit.json

# 复杂度 / 死代码
.venv-audit/Scripts/python.exe -m radon cc -s -a src
.venv-audit/Scripts/python.exe -m vulture src --min-confidence 80

# 依赖
.venv-audit/Scripts/python.exe -m pip_audit -r requirements.txt

# 质量门
.venv/Scripts/python.exe -B scripts/gate.py --json
```

---

## 10. 审计局限

- 未做完整渗透测试；SEC-01/02 是受控探针证明“能力存在”，没有执行破坏性命令。
- 覆盖率为行覆盖，不是分支覆盖；不能证明异常分支都被测到。
- 7 个 live 测试默认 skip；本次只确认 6 个 planner live 通过，r208 仍超时，未做长时间端点稳定性测试。
- 生产数据只读；没有修改生产库，也没有重新跑真实任务集。
- 依赖漏洞基于 pip-audit 当前数据库；不等于供应链完全可信。
- 机制激活判定基于静态 import/call 搜索 + 生产读回；动态反射调用可能造成少量漏判，但 5 个明确 test-only 模块的结论是逐项 grep 过的。
