# R309（①②③⑦）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** DWC 抄 Claude 剩下三课：子代理熔断（①）、MCP 探活缓存（②）、双副本自检（③）、evo 断点续跑（⑦）。

**Architecture:** 全 append-only：治理层只增开关/探针/账本，不改判分、不改 trial、不改落盘口径。默认全开=老路零变。

**Tech Stack:** Python（stdlib＋PyYAML 已有），无新依赖。

**Spec:** 本 plan 即 spec（需求来自 2026-10-17 会话：用户亲定①②③⑦价值高；顺序⑦→①→②→③与 delegate 默认 600s 为默认项，用户可推翻）。

## Global Constraints

- 判分语义零改：只增调用 append-only，Verdict 含 None 跳过不喂。
- 生产库只读；落盘须拍板（R278/R279 纪律沿用）。
- 新测坏输入走返回串断言，不硬凑 raises；零 LLM 调用（fake llm）。
- 测试走 tmp cwd（`monkeypatch.chdir(tmp_path)`＋`DWC_VAR_DIR`），禁碰生产 var（R302 纪律；⑦ ledger 测走 tmp ledger path 显式传参）。
- 裸 `except: pass` 禁止（G7）：一律命名变量＋注释或中央计数。
- `config/llm.json` 的 key 记 [REDACTED]，永不进日志不回显。
- 四层验证：pytest＋`scripts/gate.py` 8/8＋`e2e_loop.py`＋`e2e_core.py` 全 rc=0；双副本 md5 对齐后 commit＋push。

## Review Focus

- delegate 超时杀：子代理正写文件时被杀，半截文件是否留痕可查（期望：obs 记 timeout＋已耗秒数）。
- MCP probe 误判：server 偶发抖被标 down，缓存是否过期自愈（期望：TTL 过后续调重探）。
- 自检误报：E: 改完忘同步是常态，自检告警是否只告警不拦执行（期望：是，R304 纪律）。
- ledger 脏读：上轮 ledger 残留导致本轮跳过新簇（期望：ledger 按日期隔离＋key 含聚簇指纹）。
- 超时值本身：600s 是否过大过小（期望：yaml 可调，测只锁机制不锁值）。

---

### Task 1: ⑦ evo 断点续跑（epoch ledger）

**Files:**
- Modify: `scripts/dwc_evo_round.py:62-200`（`run_round` 签名加 `ledger_path=None, resume=True`）
- Test: `tests/test_r309_resume.py`（新建）

**Interfaces:**
- Consumes: `Mutator.key_for(s)`（`src/dwc/organs/evolver.py` 已有，不发明 key）。
- Produces: `read_ledger(path) -> set[str]`（后任务不用；供人查）。

- [ ] **Step 1: Write the failing test**

```python
def test_resume_skips_done_cluster(tmp_path):
    from scripts_helper import run_round  # 经 importlib 按路径加载，不污染 sys.path
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(json.dumps({"date": "D", "key": "K1"}) + "\n")
    rep = run_round(db=..., clusters=[K1簇, K2簇], ledger_path=str(ledger))
    assert K1未跑 and K2跑了  # trial_fn 调用计数断言
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_r309_resume.py -q`
Expected: FAIL（无 ledger_path 参数）

- [ ] **Step 3: Implement `run_round(..., ledger_path=None, resume=True)` in `scripts/dwc_evo_round.py`**

每簇完成即 append 一行 `{"date","key","proposal_id","ok","ts"}`；启动读当日 ledger，key 命中跳过。`ledger_path=None`＝老路（内存轮，一字不差）。`cron` 包装传 `var/evo_round_ledger.jsonl`（默认开＋`--no-resume` 可关）。

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_r309_resume.py -q`
Expected: PASS（另加坏 ledger 行跳过测＋缺文件全跑测）

- [ ] **Step 5: Commit**

```bash
git add scripts/dwc_evo_round.py scripts/dwc_evo_round_cron.py tests/test_r309_resume.py
git commit -m "R309-⑦ evo断点续跑：epoch ledger+resume（N测绿）"
```

### Task 2: ① delegate 生命周期治理

**Files:**
- Modify: `config/capabilities.yaml`（加 `delegate.timeout_s: 600`＋`delegate.max_rounds` 沿用 999）
- Modify: `src/dwc/llm/task_exec.py:849` 附近 delegate 分支（超时熔断＋存活 obs）
- Modify: `src/dwc/caps/registry.py`（加 `cap_limit(name) -> dict` 读超时等数值项，缺省回 600）
- Test: `tests/test_r309_delegate.py`（新建；fake llm＋挂钟短超时锁机制）

**Interfaces:**
- Consumes: `is_enabled`（Task 已有，R308-②）。
- Produces: `cap_limit`（Task 3 不用；供人调）。

- [ ] **Step 1: Write the failing test**

```python
def test_delegate_timeout_kills_and_reports(monkeypatch):
    # fake 子代理 sleep 5s；cap_limit 打桩 timeout_s=1；断言 obs 含 timeout 且轮次继续
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_r309_delegate.py -q`
Expected: FAIL（无熔断，轮次卡住或无 timeout 串）

- [ ] **Step 3: Implement 熔断 in delegate 分支**

`time.monotonic()` 计时；`concurrent.futures` 跑子调用（stdlib，无新依赖）；超 `cap_limit("delegate").get("timeout_s", 600)` 即弃、obs 记 `{"ok": False, "error": "delegate 超时（N.Ns>600s）已弃"}`＋进下一轮。关（enabled=false）老逻辑不动。

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_r309_delegate.py -q`
Expected: PASS（含超时值可调测：改 yaml 值即生效）

- [ ] **Step 5: Commit**

### Task 3: ② MCP 探活＋发现缓存

**Files:**
- Modify: `src/dwc/llm/task_exec.py`（mcp 分支：先 probe，工具列表进程内缓存＋TTL）
- Modify: `src/dwc/caps/registry.py`（`cap_limit("mcp")` 读 `probe_ttl_s`，缺省 300）
- Test: `tests/test_r309_mcp.py`（新建；fake mcp server 计数调用次数）

**Interfaces:**
- Consumes: `cap_limit`（Task 2 产出）。
- Produces: 无（终端任务）。

- [ ] **Step 1: Write the failing test**

```python
def test_mcp_probe_cached_second_call_no_redial():
    # 连调两次同一 server，断言底层连接只建一次；TTL 过期后重建
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_r309_mcp.py -q`
Expected: FAIL（每次都重连）

- [ ] **Step 3: Implement probe＋cache**

`_MCP_CACHE = {server: (tools, ts)}`；TTL 内命中直接用；probe 失败→obs 留痕＋fail-open 走直连（坏不断任务，沿 R305 纪律）。

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_r309_mcp.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

### Task 4: ③ 双副本自检＋收尾

**Files:**
- Modify: `scripts/dwc_agent.py`（启动自检：E:↔.dwc 白名单 md5，异则留痕告警不拦）
- Modify: `scripts/sync_hermes_scripts.py`（白名单加 R309 新文件：caps/*, test_r309*, ledger 相关）
- 全量四层验证＋双副本 md5＋commit＋push

**Interfaces:**
- Consumes: 白名单 FILES（`sync_hermes_scripts.py` 已有）。
- Produces: 无（收尾任务）。

- [ ] **Step 1: Write the failing test**

```python
def test_startup_check_warns_on_stale(tmp_path):
    # 造两侧 md5 不一致，断言自检返告警串且 rc 仍 0（不拦执行）
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_r309_selfcheck.py -q`
Expected: FAIL（无自检函数）

- [ ] **Step 3: Implement `startup_selfcheck()`**

只告警（print＋trace）不抛错；`--no-selfcheck` 可关。

- [ ] **Step 4: 四层验证**

Run: `pytest tests/ -q`（后台，~6min）→ `scripts/gate.py`（8/8）→ `e2e_loop.py`＋`e2e_core.py`（双 0）→ 双副本 md5 全同 → commit＋push。

- [ ] **Step 5: Commit**
