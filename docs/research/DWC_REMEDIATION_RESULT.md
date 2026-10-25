# DWC pure 审计修复结果（P0–P3）

- 日期：2026-10-26
- 开发仓：`Z:\DWC pure`，分支 `divine-wisdom-core-pure`
- 开发 HEAD：`6debd57`（P0–P3 修复链）
- 生产：`C:\Users\41228\.dwc`，代码对应 `6debd57`，agent `--llm` 常驻
- 原则：只写实测；未做的明确标“未做”

---

## 1. 最终验证

| 项 | 实测 |
|---|---|
| 开发仓全量 | `3334 passed / 9 skipped / 0 failed`（610s） |
| 生产全量 | `3334 passed / 9 skipped / 0 failed`（606s，部署 `e185051` 后） |
| 定向回归 | 最新 allowlist 收窄后 `39 passed`；trusted marker `24 passed` |
| 质量门 | `python scripts/gate.py --json` = **8/8** |
| CI lint | `ruff check src scripts --select F821,F841,F811,B023,S102` = **All checks passed** |
| 生产 config | `config/llm.json`、`config/capabilities.yaml` sha256 前后一致 |
| 生产 agent | pid `1142048`，心跳 alive，RPC 8802 |

> 默认全量仍是“非真端点集”：7 个 `live` 测试默认 skip；`r208 lifecycle` 真端点仍可能超时，未伪装成全绿。

---

## 2. P0：已封

| 项 | 修复 | 证据 |
|---|---|---|
| `run_command` 黑名单绕过 | 新增 `src/dwc/llm/exec_policy.py`：allowlist + 审批态；`python -c` 默认拒绝；`find/grep/cat/ls` 等文件读取命令移出 allowlist | `tests/test_exec_policy.py` 24 passed；`test_r400b` 伪造 `_from_tool` 被拒 |
| `_from_tool` 可伪造 | 改为进程内 `TRUSTED_TOOL = object()` 哨兵；模型 JSON 只能给 bool，无法构造同一对象 | `test_model_cannot_forge_private_from_tool` |
| `actor` 无沙箱 `exec` | 改用 `sandbox.build_guarded_code(..., allow_for=True, allow_while=True)`；禁 import/open/dunder；受限 builtins | `tests/test_code_exec_sandbox.py`；`import os`/`open`/`__class__` 全拒 |
| `candidates` 无沙箱 `exec` | 同上，基线源码先过 AST 门卫 | 同上 |

**诚实边界**：allowlist 不是 OS 沙箱；`python -m pytest`、`ruff`、`git` 仍会在当前用户权限下执行/读仓库。actor 为兼容基准实现允许 `while`，靠外层任务超时兜底，不是强隔离。

---

## 3. P1：已修

| 项 | 修复 | 证据 |
|---|---|---|
| `web_read` SSRF | 新增 `net_policy.check_url`：scheme/userinfo/DNS 私网/loopback/link-local 拒绝；禁用自动重定向 | `tests/test_net_policy.py` 8 passed |
| `_guard_path` 前缀/符号链接 | `realpath` + `commonpath`；写路径按 ROOT 解析后检查 WORK；符号链接拒绝 | `tests/test_path_guard.py` |
| 复读熔断重试不可达 | `_fail`/`_revision_retry` 移到 `return` 前 | `test_dup_breaker_calls_revision` |
| `dwc_evo_round` 未定义 `judge` | `run_round(..., judge=None)`；显式 `_forbidden_expected`；缺失时报告 `unavailable`，`apply=True` fail-closed；两个调用方都传 `judge` | `test_dedup_judge_blocks_expected_behavior`、`test_dedup_without_judge_fails_closed_on_apply` |
| QA 未找到标 done | 两处改 `status=incomplete, why=qa_no_evidence`；qa 不做环境证据门 | `test_r302_final_refs`、`test_r301_qa_loop` |
| 12 项机制测试专用 | 已接：M1.7 `working_state`（非 qa done 前）、M2.3 偏好/信念、M2.4 `memory_context`、M3.1 `maintain`、M3.4/MEM-18/MEM-03/MEM-14 只读 `dwc memory-stats` | `test_memory_fts_concurrency`、`test_memory_context`、`test_core`、CLI 实测 |
| 技能注入 0 | `from_task_result` 仍只认真实 `run/test/check`；不造假技能 | **未解决**：生产任务集没有可验证 code_repair，`skill_prompt` 仍 0 命中 |
| FTS 每实例 rebuild | `PRAGMA user_version` 迁移标记，只 rebuild 一次；`dwc_agent` 进程内复用 `MemoryKernel` | `test_fts_not_rebuilt_when_in_sync` |

**诚实边界**：`skill_prompt` 命中仍为 0。原因不是代码没接，而是生产没有“带成功 run/test/check 的任务”可提炼；靠注入 factual 技能填数会违反 M1.3，不做。

---

## 4. P2：已做

| 项 | 修复 |
|---|---|
| SQLite 并发 | `busy_timeout=5000` + `threading.RLock` 串行化写路径；10 线程×20 写测试 |
| 原子写 | `foundation/atomic_io.py`（tmp + fsync + `os.replace`）；token/frozen/inbox/rules/learned/archive/ask 已替换 |
| CI | `.github/workflows/ci.yml`：compileall + 选中 ruff + pytest + gate |
| lint | `pyproject.toml` ruff 配置；F821/F841/F811/B023/S102 清零 |
| License/lock | `LICENSE`（MIT）、`requirements.lock` |
| 文档对账 | README 改 3334/9、R458、633 commits；删除“ruff/bandit 清零”失真表述 |
| 仓库卫生 | `archive/gate_trace.jsonl` 移出索引并 ignore；`tmp/` ignore |
| 文档声称 | `harness/__init__.py` 删除“三入口”宣传，明确 step/ingest 未实现 |

**未做**：`_execute_user_task_impl`（232 行）与 `_do_action`（77）未拆；`bandit` 77 条未进 CI；113 处写文件只替换了高风险簇，不是全量。

---

## 5. P3：已做

- 弱哈希加 `usedforsecurity=False`：`tool_raw.py`、`memory.py`、`skill_writer.py`、`task_supply.py`。
- F821 注解补 `Dict/List/Optional`。
- 删除 `evolver.py` 的 `if delta_c is None and False`。
- `scan_*.py` 的 `ros` 笔误改 `os`。
- `task_exec.py` 的 paper 分类改 `urlsplit(...).hostname`，不再用子串。
- B023 循环闭包绑定/改名。

---

## 6. 仍然存在的边界与消除路径

### A. 工程可继续解，但需要更强隔离

1. **命令执行不是 OS 沙箱**
   - 现状：allowlist 只决定“允许哪些程序”，不限制程序能力；`pytest` 可执行仓库内任意测试代码。
   - 消除：低权限账户/容器/Windows AppContainer + Job Object 超时 + 只读挂载；或把 `run` 降级为固定工具集（pytest/ruff/git 只读）并禁止任意 argv。
2. **actor `while` 可能挂住**
   - 现状：为兼容基准实现允许 `while`；靠外层任务超时。
   - 消除：actor 调用放入子进程/线程 + 硬超时 + CPU/内存限额；Windows 用 Job Object，Unix 用 `setrlimit`。
3. **SSRF DNS TOCTOU**
   - 现状：解析后检查 IP，实际连接可能重新解析（DNS rebinding）。
   - 消除：解析结果钉到 IP，HTTP Host 头保留域名；或强制走 egress 代理白名单。
4. **路径符号链接竞态**
   - 现状：`realpath` 检查与 `open` 之间仍可被替换；Windows junction/reparse 未全测。
   - 消除：`CreateFile` 带 `FILE_FLAG_OPEN_REPARSE_POINT`，句柄相对路径；或只允许 `read`/`write` 走已打开目录句柄。
5. **FTS 损坏不自愈**
   - 现状：`user_version` 只保证迁移一次；索引损坏不会自动 rebuild。
   - 消除：启动/定时 `INSERT INTO memory_fts(memory_fts) VALUES('integrity-check')`，失败 rebuild。
6. **原子写不是跨文件事务**
   - 现状：单文件原子；inbox + done + 报告多文件仍可能半提交。
   - 消除：journal/两阶段提交，恢复时按 journal 回放。
7. **复杂度未拆**
   - 现状：`_execute_user_task_impl` 232 行、`_do_action` 77；行为正确但维护成本高。
   - 消除：按 `prepare/loop/apply/qa/finalize/metrics` 拆，配 golden tests；不要一次大重写。

### B. 需要真实数据，不能靠代码消除

8. **技能注入 0**：需要真实 code_repair 任务产生成功 `run/test/check`；不能用 factual 技能凑数。
9. **记忆效果**：`memory_edge=0`、`SELF=0`、`failure_sig` access=0；需要长期真实任务与配对样本，不能自报。
10. **长期稳定性**：单次 10 分钟全量通过 ≠ 7×24 稳定；需要持续心跳/日志/回归观察。
11. **r208 live**：真端点短跑仍可能 >300s；保持 live skip，不伪装通过。

### C. 外部环境不可解

12. **AKV serving**：当前远程 OpenAI 兼容端点无 `drop_message/reposition`，无 SGLang/GPU 控制权。
13. **TIES/SFT**：无 checkpoint/训练控制权。
14. **Windows 低权限沙箱**：需要真实低权限账户/容器，代码只能 fail-closed。
15. **价格**：无真实费率，保持 `pricing_status=not_configured`，成本 `indeterminate`，不填 0。
16. **上游前进**：`upstream` 只读；后续 R459+ 需重新 fetch/审查合并，绝不回推。

---

## 7. 结论

P0 的两条任意执行路径已封；P1 的正确性缺陷与主要消费链已修；P2/P3 的工程化与低风险清理已落地。  
仍不能声称“无边界”：命令执行、actor 超时、SSRF、路径竞态属于**隔离强度**问题；技能注入、记忆效果、长期稳定性属于**真实数据**问题；AKV/TIES/SFT/价格/Windows 沙箱属于**外部环境**问题。  
下一步优先级：**低权限/Job Object 隔离 → SSRF 钉 IP → 技能真实产出 → 复杂度拆分 → 长期观察**。
