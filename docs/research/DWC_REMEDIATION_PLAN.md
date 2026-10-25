# DWC pure 全问题代码级修复方案

- 版本：2026-10-26
- 依据：`docs/research/DWC_PURE_CODE_AUDIT_20261025.md`、Semgrep/CodeQL 实测
- 原则：先封 P0，再修 P1，最后工程化；每个补丁有测试、验收和回滚
- 本文只给方案，不改业务代码

---

## 0. 目标与非目标

### 目标

1. 消除模型/任务输入到宿主命令或代码执行的路径。
2. 修复已确认的正确性缺陷（不可达重试、未定义变量、done 语义）。
3. 让 M1.7/M2.3/M2.4/M3.1/M3.4/MEM-18 从“测试专用”变成“有真实消费方”，或明确降级。
4. 把静态/安全/覆盖率检查变成 CI 门，而不是一次性扫描。
5. 把 README/状态文档与实测数字对齐。

### 非目标

- 不实现向量检索、RL Navigator、MemPO；没有 hit-rate/effect 数据前保持关闭。
- 不实现 AKV serving、TIES/SFT；当前端点没有 serving/checkpoint 控制权。
- 不填价格；没有真实费率前保持 `indeterminate`。
- 不追求 ruff 全库零告警；先修 F821/F841/F811/B023/S102/S110/S112/BLE001，其余按基线管理。

---

## 1. 变更总览

| ID | 优先级 | 问题 | 主要文件 | 验收 |
|---|---|---|---|---|
| SEC-01 | P0 | `run_command` 黑名单可绕过 | `task_exec.py` + 新 `exec_policy.py` | `python -c`/PowerShell 全部 deny |
| SEC-02 | P0 | `actor`/`candidates` 无沙箱 `exec` | `actor.py`、`candidates.py`、`sandbox.py` | `import os`/`open` 全部 ActorError |
| SEC-03 | P1 | `web_read` SSRF | `task_exec.py` + 新 `net_policy.py` | 127.0.0.1/私网/重定向全拒 |
| SEC-04 | P1 | `_guard_path` 前缀/符号链接 | `task_exec.py` | 同前缀目录/链接全拒 |
| COR-01 | P1 | 复读熔断重试不可达 | `task_exec.py` | 3 次重复动作触发 revision |
| COR-02 | P1 | `judge` 未定义、泄漏检查被吞 | `dwc_evo_round.py` | 带 expected_behavior 的 patch 被拒 |
| COR-03 | P1 | QA 未找到标 done | `task_exec.py` | 返回 incomplete |
| ACT-01 | P1 | 12 项机制测试专用 | `core.py`、`executor.py`、`memory_*.py` | 至少 1 条生产调用链 |
| ACT-02 | P1 | 技能注入为 0 | `executor.py`、`skill_writer.py` | `skill_prompt` hit rate > 0 |
| PERF-01 | P1 | FTS 每实例 rebuild | `memory.py`、`dwc_agent.py` | 二次初始化不 rebuild |
| OPS-01 | P2 | SQLite 无锁/无 busy_timeout | `memory.py` | 10 线程写不锁死 |
| QUA-01 | P2 | 静态质量未清零 | `pyproject.toml`、CI | F 类/S102 门通过 |
| QUA-02 | P2 | 静默异常 | 多处 | 失败有计数/日志 |
| QUA-03 | P2 | 非原子写 | 新 `atomic_io.py` | 崩溃注入保留原文件 |
| QUA-04 | P2 | 复杂度 232 | `task_exec.py` | 拆成 ≤5 个函数 |
| DOC-01 | P2 | README 失真 | `README.md` | 数字与实测一致 |
| DOC-02 | P2 | 文档声称模块不存在 | `harness/__init__.py` | 删除或实现 |
| REPO-01 | P2 | gate trace 变脏 | `.gitignore` | `git status` clean |
| PORT-01 | P2 | 旧机器路径 | `scripts/*` | 无 `E:/`/`C:\Users` 默认值 |
| P3 | P3 | 弱哈希/注解/死条件 | 多处 | 扫描噪声清零或标注 |

---

## 2. P0 补丁

### SEC-01 · 命令执行改为 allowlist + 子进程隔离

#### 新增 `src/dwc/llm/exec_policy.py`

```python
"""DWC 命令执行策略。黑名单不是安全边界；这里只允许明确命令。"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass

class CommandDenied(Exception):
    pass

@dataclass(frozen=True)
class RunDecision:
    allowed: bool
    reason: str
    requires_approval: bool = False

_READONLY_GIT = {"status", "diff", "log", "show", "rev-parse", "ls-files"}
_PYTEST_MODULES = {"pytest", "unittest", "compileall"}

def _base(argv0: str) -> str:
    exe = shutil.which(argv0) or argv0
    return os.path.basename(exe).lower()

def check(argv, *, cwd: str, allow_unsafe: bool = False) -> RunDecision:
    if not isinstance(argv, list) or not argv:
        return RunDecision(False, "argv 必须是非空列表")
    if any(not isinstance(x, str) or "\x00" in x for x in argv):
        return RunDecision(False, "argv 含非字符串/NUL")
    name = _base(argv[0])
    if name in {"python", "python.exe"}:
        if len(argv) < 3:
            return RunDecision(False, "python 只允许 -m pytest/unittest/compileall")
        if argv[1] != "-m" or argv[2] not in _PYTEST_MODULES:
            return RunDecision(False, "python -c/脚本执行默认禁止")
        return RunDecision(True, "python -m 测试/编译")
    if name in {"pytest", "pytest.exe"}:
        return RunDecision(True, "pytest")
    if name in {"git", "git.exe"}:
        sub = argv[1] if len(argv) > 1 else ""
        if sub in _READONLY_GIT:
            return RunDecision(True, "git 只读")
        return RunDecision(False, "git 写操作禁止")
    if name in {"ruff", "ruff.exe", "bandit", "bandit.exe"}:
        return RunDecision(True, "静态检查")
    if allow_unsafe:
        return RunDecision(True, "DWC_ALLOW_UNSAFE_RUN 显式开启", True)
    return RunDecision(False, "命令不在 allowlist")
```

#### 修改 `src/dwc/llm/task_exec.py` 的 `run` 分支

替换 `_FORBIDDEN`/`_ASK` 的主判定：

```python
if op == "run":
    cmd = args.get("cmd")
    decision = exec_policy.check(
        cmd, cwd=ROOT,
        allow_unsafe=os.environ.get("DWC_ALLOW_UNSAFE_RUN") == "1")
    if not decision.allowed:
        return {"ok": False, "error": "command_denied",
                "reason": decision.reason, "cmd": cmd[:3]}
    # 只有 allowlist 通过才执行；仍用 argv 列表，不用 shell=True
    r = subprocess.run(
        [str(x) for x in cmd], cwd=ROOT, shell=False,
        capture_output=True, text=True, timeout=60,
        env=exec_policy.safe_env(), stdin=subprocess.DEVNULL)
```

新增 `safe_env()`：

```python
def safe_env() -> dict[str, str]:
    allow = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP",
             "HOME", "USERPROFILE", "PYTHONPATH")
    return {k: os.environ[k] for k in allow if k in os.environ}
```

#### 测试

新增 `tests/test_exec_policy.py`：

```python
@pytest.mark.parametrize("cmd", [
    ["python", "-c", "import os; os.remove('x')"],
    ["powershell", "-Command", "Remove-Item x"],
    ["cmd", "/c", "del x"],
    ["rm", "-rf", "x"],
    ["git", "push"],
])
def test_dangerous_commands_denied(cmd):
    assert not check(cmd, cwd=ROOT).allowed

@pytest.mark.parametrize("cmd", [
    ["python", "-m", "pytest", "tests/test_x.py"],
    ["pytest", "tests/test_x.py"],
    ["git", "status"],
])
def test_readonly_commands_allowed(cmd):
    assert check(cmd, cwd=ROOT).allowed
```

更新 `tests/test_r220_ask.py`：`python -c` 从“允许”改为“拒绝”；`rm` 从 ask 改为 deny。  
新增 `tests/test_run_command_guard.py`：断言 `_do_action("run", ...)` 对 `python -c` 返回 `command_denied`，不创建文件。

#### 验收

- `python -c`、PowerShell、`cmd /c`、`rm`、`git push` 全部 deny。
- `pytest`、`git status`、`ruff` 仍可用。
- `DWC_ALLOW_UNSAFE_RUN` 只在测试/显式开发环境设置，生产不设置。
- Semgrep/CodeQL 的 `args→subprocess` 仍会存在；在自定义查询中把 `exec_policy.check` 标为 barrier，并保留人工审查说明。

---

### SEC-02 · `actor`/`candidates` 改用 AST 门卫

#### 修改 `src/dwc/llm/sandbox.py`，暴露公共 API

```python
def parse_guarded(code: str, filename: str = "<llm>") -> ast.Module:
    tree = ast.parse(code, filename=filename)
    _Guard().visit(tree)
    return tree

def compile_guarded(code: str, filename: str = "<llm>"):
    return compile(parse_guarded(code, filename), filename, "exec")

def safe_globals() -> dict:
    import math
    return {"__builtins__": dict(_SAFE_BUILTINS), "math": math}
```

#### 修改 `src/dwc/organs/actor.py`

```python
from dwc.llm.sandbox import SandboxError, compile_guarded, safe_globals

try:
    code_obj = compile_guarded(body, "<%s>" % self.source_from)
except SandboxError as e:
    raise ActorError("实现 %r 未通过沙箱: %s" % (self.source_from, e))
ns = safe_globals()
exec(code_obj, ns)
```

- 保留 `fn_name` 白名单。
- `source_from` 仍记录 `reference/provided`。
- 失败时抛 `ActorError`，不返回半成品。

#### 修改 `src/dwc/organs/candidates.py`

```python
from dwc.llm.sandbox import SandboxError, compile_guarded, safe_globals

try:
    code_obj = compile_guarded(src, "<baseline>")
    ns = safe_globals()
    exec(code_obj, ns)
except (SandboxError, SyntaxError):
    return None
```

#### 测试

新增 `tests/test_actor_sandbox.py`、`tests/test_candidates_sandbox.py`：

```python
@pytest.mark.parametrize("bad", [
    "import os\ndef f(n): return os.getcwd()",
    "def f(n):\n    return open('x').read()",
    "def f(n):\n    return ().__class__",
    "def f(n):\n    while True: pass",
])
def test_actor_rejects_unsafe_source(bad):
    with pytest.raises(ActorError):
        PureFunctionExecutor("f", source=bad)
```

保留现有 reference 任务测试，确保 6 个纯函数仍可执行。

#### 验收

- `import os`、`open`、`__class__`、`while` 全部拒绝。
- reference 6 函数仍通过。
- Semgrep `exec` 命中仍存在，但代码前有 `compile_guarded`；在审计报告中标注“受门卫保护”，不把命中数当漏洞数。

---

## 3. P1 补丁

### SEC-03 · `web_read` SSRF

新增 `src/dwc/llm/net_policy.py`：

```python
import ipaddress
import socket
from urllib.parse import urlsplit

class EgressDenied(Exception):
    pass

def check_url(url: str, *, allow_hosts=()) -> str:
    p = urlsplit(url)
    if p.scheme not in ("http", "https"):
        raise EgressDenied("只允许 http/https")
    if p.username or p.password:
        raise EgressDenied("URL 不允许 userinfo")
    host = p.hostname
    if not host:
        raise EgressDenied("缺 host")
    if host in allow_hosts:
        return url
    port = p.port or (443 if p.scheme == "https" else 80)
    infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    for family, _, _, _, sockaddr in infos:
        ip = ipaddress.ip_address(sockaddr[0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
            raise EgressDenied("禁止私网/loopback/link-local: %s" % ip)
    return url
```

修改 `task_exec.py`：

```python
if op == "web_read":
    url = str(args.get("url", "")).strip()
    try:
        url = net_policy.check_url(url)
    except net_policy.EgressDenied as e:
        return {"ok": False, "error": "egress_denied", "reason": str(e)}
    # 禁止自动重定向；需要重定向时手动 check 新 URL
    opener = urllib.request.build_opener(_NoRedirect)
```

`_NoRedirect`：

```python
class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None
```

测试：

- `127.0.0.1`、`[::1]`、`10.0.0.1`、`169.254.169.254` 全拒。
- `http://example.com` 允许（mock DNS）。
- 重定向到 `127.0.0.1` 拒绝。
- `file://`、`ftp://`、`http://user:pass@host` 拒绝。

### SEC-04 · `_guard_path` 改为 realpath + commonpath

```python
def _guard_path(path: str, *, write: bool) -> str:
    base = os.path.realpath(WORK if write else ROOT)
    raw = path if os.path.isabs(path) else os.path.join(base, path)
    p = os.path.realpath(raw)
    if os.path.commonpath([os.path.normcase(base),
                           os.path.normcase(p)]) != os.path.normcase(base):
        raise TaskExecError("路径越界: %s" % path)
    if os.path.islink(raw):
        raise TaskExecError("不允许符号链接: %s" % path)
    if write and not (p == base or p.startswith(base + os.sep)):
        raise TaskExecError("写只许 var/inbox_work/ 下: %s" % path)
    return p
```

测试：

- `../DWC pure_evil/x` 拒绝。
- 符号链接指向仓库外拒绝。
- 同前缀目录拒绝。
- `C:` drive-relative、UNC、大小写变体拒绝。

### COR-01 · 复读熔断重试移到 return 前

目标代码：

```python
if len(dup_sigs) >= 3 and len(set(dup_sigs[-3:])) == 1:
    if _use_native_tools() and _ff_used[0] < 1:
        ...
        continue
    if qa_mode and ...:
        ...
        return {"status": "incomplete", "why": "qa_no_evidence", ...}
    _fail = {"status": "incomplete", "why": "复读熔断",
             "actions_log": log}
    if retry_on_fail and _depth == 0:
        _r2 = _revision_retry(task=task, fail=_fail, llm=llm,
                              sid=sid, progress=progress)
        if _r2 is not None:
            return _r2
    return {"status": "incomplete", "why": "复读熔断", ...}
```

关键：`_fail`/`_revision_retry` 必须在 `return` 之前；不要留下任何 `return` 后的代码。

测试：

```python
def test_duplicate_breaker_calls_revision(monkeypatch):
    called = {}
    monkeypatch.setattr(TE, "_revision_retry",
                        lambda **kw: called.setdefault("hit", True) or {"status": "done"})
    # 构造连续 3 次同 op/target/obs 的 step
    out = TE.execute_user_task("...", llm=FakeLLM(...), max_rounds=3)
    assert called.get("hit") is True
    assert out["status"] == "done"
```

### COR-02 · `dwc_evo_round` 显式传 judge，fail-closed

修改 `run_round` 签名：

```python
def run_round(..., judge=None, ...):
```

新增 helper：

```python
def _forbidden_expected(judge):
    if judge is None:
        return None
    return {a.get("expected_behavior") for a in (judge.anchors or {}).values()
            if isinstance(a, dict) and a.get("expected_behavior")}
```

循环内：

```python
_forbidden = _forbidden_expected(judge)
if _forbidden is None:
    item["dedup_status"] = "unavailable"
    if apply:
        item["reason"] = "dedup_unavailable_fail_closed"
        _fatal = True
        break
else:
    item["dedup_status"] = "checked"
    if p is not None and any(f in (p.patch or "") for f in _forbidden):
        item["reason"] = "patch leaks benchmark expected_behavior"
        _fatal = True
        break
```

调用方 `scripts/dwc_evo_round.py:1144`、`scripts/dwc_evo_round_cron.py:178` 都加 `judge=judge`。

测试：

- fake judge with `expected_behavior` + patch containing it ⇒ `_fatal`。
- `judge=None, apply=True` ⇒ fail-closed。
- `judge=None, apply=False` ⇒ `dedup_status="unavailable"`，不静默。

### COR-03 · QA 未找到改 incomplete

把 `task_exec.py` 两处：

```python
return {"status": "done", ... "answer": "经多轮取证仍未能定位..."}
```

改为：

```python
return {"status": "incomplete", "why": "qa_no_evidence",
        "answer": ..., "actions_log": log}
```

涉及行：`2314`、`2435`。`1954` 的纯文本答案仍可保留 done（它不是“未找到”）。

测试：qa 模式连续无命中 → 断言 `status == "incomplete"`，且报告仍写出 answer。

### ACT-01 · 机制接入真实消费点

#### M1.7 `working_state`

在 `task_exec` 的 `done` 返回前加：

```python
from dwc.organs.working_state import check_update
_ev = [f"{e.get('op')}:{e.get('target')}" for e in log
       if isinstance(e, dict) and e.get("phase") == "obs" and e.get("ok")]
if _ev:  # 只有真实动作才检查；纯聊天不误伤
    _ws = check_update(sid, "done", evidence=_ev, claimed=True)
    if not _ws["passed"]:
        return {"status": "incomplete", "why": _ws["code"],
                "answer": ..., "actions_log": log}
```

接入点：`task_exec.py:2264`、`2314`、`2435`。  
测试：done 无 obs ⇒ incomplete；有 run/test obs ⇒ done。

#### M2.4 `memory_context`

在 `executor.memory_text` 里保留现有 skill 相关性筛选，但在渲染前加：

```python
from dwc.organs.memory_context import assemble
ctx = assemble(memory, task, budget_tokens=max(120, max_chars // 3),
               include_self=True, include_skills=False,
               include_episodes=False)
head = ctx["text"]
```

再把选中的 skill 行拼到 `head` 后面；`used_ids` 合并到 retrieval 记录。  
这样 SELF/预算逻辑进入 prompt，且不改变 skill 选择算法。

#### M2.3 偏好/信念

给 `memory_context.assemble` 增加 `include_preferences=True`，在 SELF 后加入 `PREFERENCE/BELIEF`：

```python
for node in memory.by_kind(MemoryKind.PREFERENCE):
    if not add(node): break
for node in memory.by_kind(MemoryKind.BELIEF):
    if not add(node): break
```

`memory_text` 使用该路径；生产至少出现一次 `pref:`/`belief:` 行。

#### M3.1 维护

`core.py` 的 `maintain` 分支改为：

```python
elif action == "maintain":
    from dwc.organs.memory_maintenance import plan
    rep = plan(self.memory)
    dispatch = {"kind": "maintain", "dispatched": True,
                "n_evaluated": rep["n_evaluated"],
                "counts": rep["counts"]}
```

不删除、不写节点；只出建议。测试：`core.act("maintain")` 返回 `dispatched=True`。

#### M3.4 / MEM-18 / MEM-03 / MEM-14

新增只读 CLI（`src/dwc/cli_main.py` 或 `scripts/dwc_memory_stats.py`）：

```bash
dwc memory-stats --db var/dwc_prod.sqlite
```

输出：

- `retrieval_stats()`
- `retrieval_quality()`（无标签时 None）
- `memory_bench.bench(...)`（无标签时 None）
- `memory_policy.status()`（全部 false + 原因）

这样这些模块有生产消费方，但不会改变 agent 行为。

#### M2.2 SELF / M2.1 边 / M1.5 对比

- `revise_self`：在维护者命令/`dwc memory revise-self` 中调用；不在 agent 热路径自动写。
- `link`：由 `revise`/`preference` 触发；先接 `revision.revise_from_outcome` 到 `run_user_task` 的失败分支。
- `contrast`：在 `_revision_retry` 里调用 `contrast.compare(fail, res2)`，把 `contrast` 放进 `res2["revision_pair"]`；没有配对样本时 `comparable=False`。

#### 测试与验收

- `tests/test_memory_activation.py`：monkeypatch `plan`/`assemble`/`check_update`，断言被调用。
- 生产读回：`memory_retrieval` 出现 `skill_prompt` 命中 >0；`task_skill_written` >0；`memory_maintenance` 至少一次 `dispatched=True`。
- 若暂时不接，状态文档必须标 `implemented_unwired`，不能标 adopt。

### ACT-02 · 技能注入从 0 到 >0

1. `from_task_result` 只在有 `run/test/check` 时写；先给 code_repair 任务补一个 `check` 动作，确保真实过程技能能产生。
2. `memory_text` 保留 `include_factual=False`，但增加 `skill_kind="procedural"` 的优先召回；不要为了填数把 factual 注入。
3. 指标：`memory_retrieval` 的 `skill_prompt` 命中率；连续 7 天 >0 才算激活。
4. 测试：构造一个 procedural skill + 匹配任务，断言 `memory_text` 非空且 access +1；8 条 factual 不得被注入。

### PERF-01 · FTS 只在迁移/不一致时 rebuild

`memory.py`：

```python
self._conn.execute("PRAGMA busy_timeout=5000")
self._lock = threading.RLock()
...
n_node = self._conn.execute("SELECT COUNT(*) FROM memory_node").fetchone()[0]
n_fts = self._conn.execute("SELECT COUNT(*) FROM memory_fts").fetchone()[0]
if n_node != n_fts:
    self._conn.execute("INSERT INTO memory_fts(memory_fts) VALUES('rebuild')")
    self._conn.commit()
```

`dwc_agent.run_user_task`：

- 删除每单 `MemoryKernel(DB)`。
- 在 agent 启动时创建一个 `MemoryKernel`，通过参数/闭包传给 `run_user_task`；`from_task_result(memory, ...)` 复用。
- 若必须跨线程，`MemoryKernel` 内部 `RLock` 保护写；不要每单新建连接。

测试：

- 连续两次 `MemoryKernel(path)`，第二次不执行 rebuild（monkeypatch `execute` 计数）。
- 10k 节点初始化耗时基线；写入 100 条后 FTS count 一致。

---

## 4. P2 补丁

### OPS-01 · SQLite 并发

- `PRAGMA busy_timeout=5000`。
- `self._lock = threading.RLock()`。
- `remember/record_retrieval/link/revise/close` 用 `with self._lock:` 包住写+commit。
- `dwc_agent` 单写线程/单例；`from_task_result` 复用。
- 测试：10 线程各写 50 条，0 `database is locked`，总数 500。

### QUA-03 · 原子写

新增 `src/dwc/foundation/atomic_io.py`：

```python
def write_text_atomic(path, text, *, encoding="utf-8", mode=0o600):
    d = os.path.dirname(os.path.abspath(path))
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".dwc-tmp-", dir=d)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
```

优先替换：

- `agent_rpc.py:174/181/336`（done/frozen/token）
- `evolver.py:1385/1590/3100`（learned/archive/rules）
- `task_exec.py:590/1322`（任务文件/ask answers）
- `causal_chain.py:335`（导出）
- `retention.py:112/128`

测试：monkeypatch `os.replace` 抛错 ⇒ 原文件内容不变、tmp 清理；并发写 100 次 JSON 不出现半截。

### QUA-01 / QUA-02 · 静态门

`pyproject.toml` 增加：

```toml
[project.optional-dependencies]
dev = ["pytest>=8", "pytest-cov", "ruff", "bandit"]

[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "B", "S", "SIM", "BLE"]
ignore = ["E501"]  # 先不因行长阻塞
```

分阶段：

1. 先修 `F821/F841/F811/B023/S102`（真实缺陷/安全）。
2. 再修 `S110/S112/BLE001`：每个 `except` 加计数或日志，不删护栏。
3. `UP031` 等风格项用 `per-file-ignores` 或基线文件，不一次性 `ruff --fix`。
4. CI 增加 `ruff check src --select F821,F841,F811,B023,S102`，后续逐步扩大。

### QUA-04 · 复杂度拆分

`_execute_user_task_impl`（232）拆为：

- `_prepare_run(task, llm) -> RunState`
- `_run_loop(state) -> None`
- `_apply_step(state, step) -> dict`
- `_qa_gate(state, step) -> dict | None`
- `_finalize(state) -> dict`
- `_record_metrics(state, result)`

`_do_action`（77）改为 dispatch 表：

```python
_HANDLERS = {
    "read": _do_read,
    "write": _do_write,
    "run": _do_run,
    "web_read": _do_web_read,
    "web_search": _do_web_search,
    "mcp": _do_mcp,
    "final": _do_final,
}
```

`recall_search`（61）拆为 `_candidates` / `_score` / `_mmr`。  
验收：radon 该函数 ≤ C；全量测试不变。

### DOC-01 / DOC-02 / REPO-01 / PORT-01

- README：3285 passed / 9 skipped、R458、621 commits；删除“F821/ruff/bandit 清零”。
- `harness/__init__.py`：删除 `step.py`/`ingest.py` 的“待实现”声明，或补最小实现；不能继续把不存在模块写成三入口。
- `archive/gate_trace.jsonl`：`git rm --cached` + `.gitignore`，改为 CI artifact。
- `docs/repos/_all.json`：移出主仓或改为生成物；不要提交 3.4MB 抓取语料。
- `supply_checkpoint.py`：`REPO = os.environ.get("DWC_ROOT", os.path.dirname(os.path.dirname(__file__)))`。
- `dwc_agent_patch.py`：删除默认用户路径，要求 `DWC_PY38`/`DWC_AGENT_WORK`，缺失时报错。
- `dwc_graded_bench.py`/`dwc_benchmark_adapter.py`：默认值改 env，缺省用 `ROOT/var`。

---

## 5. P3 补丁

| 项 | 代码改动 | 测试 |
|---|---|---|
| SHA1/MD5 | `hashlib.sha1(data, usedforsecurity=False)` 或 SHA256；`memory.py:1143`、`skill_writer.py:93`、`task_supply.py:88/306`、`tool_raw.py:54` | 同 ID 稳定性测试 |
| F821 注解 | `client.py` 加 `Dict`；`sandbox.py` 加 `Dict,List,Optional`；`dwc_bench.py` 加 `Optional` | `python -m compileall` + `typing.get_type_hints` 烟测 |
| 死条件 | 删除 `evolver.py:350` 的 `if delta_c is None and False`，改成真实策略或注释 | 单测覆盖 |
| `ros` 脚本 | `scan_*.py` 的 `ros` 改 `os`；不可修复的旧脚本删除/移入 archive | 脚本 `--help`/compile |
| CodeQL URL 子串 | `task_exec.py:1421` 用 `urlsplit(target).hostname` 判断，不用 `"arxiv.org" in low` | 分类测试 |
| `0o644` | 日志文件改 `0o600` 或保留并注明 Windows ACL | 权限测试 |
| B023 | `core.py:732/735/754/755`、`task_exec.py:2023` 用默认参数绑定循环变量 | 循环值测试 |

---

## 6. 测试矩阵

| 层 | 命令 | 验收 |
|---|---|---|
| 单测 | `pytest tests/test_exec_policy.py tests/test_actor_sandbox.py tests/test_candidates_sandbox.py tests/test_net_policy.py tests/test_atomic_io.py` | 全绿 |
| 回归 | `pytest tests/test_r220_ask.py tests/test_r259_eval.py tests/test_r342* tests/test_r247*` | 全绿 |
| 全量 | `pytest -q -p no:cacheprovider` | ≥3285 passed / 0 failed |
| 门 | `python scripts/gate.py --json` | 8/8 |
| Semgrep | `semgrep scan --config docs/research/semgrep_dwc.yml src scripts` | P0 路径 0（或全部有 policy barrier） |
| CodeQL | 4 个自定义查询 | `args→subprocess`/`source→exec` 0 条，或全部命中 policy/guard |
| 生产 | 重启 agent，读 `memory_retrieval`/`task_skill_written`/`memory_maintenance` | 至少 1 条真实消费 |

---

## 7. 提交顺序与回滚

### 提交 1：P0 命令策略

- 新增 `exec_policy.py`、改 `task_exec.run`、测试。
- 回滚：删除新文件，恢复 `_FORBIDDEN` 分支；`DWC_ALLOW_UNSAFE_RUN` 可临时保命，但生产不设。

### 提交 2：P0 代码沙箱

- 新增 `sandbox.parse_guarded/compile_guarded/safe_globals`、改 `actor`/`candidates`、测试。
- 回滚：恢复直接 `exec`；风险回到 P0，不建议长期保留。

### 提交 3：P1 SSRF/路径

- 新增 `net_policy.py`、改 `web_read`、改 `_guard_path`、测试。
- 回滚：恢复旧 URL/路径检查；旧检查仍有 SSRF/前缀问题。

### 提交 4：P1 正确性

- 修 retry、judge、done 语义；测试。
- 回滚：单文件 revert；这些是独立逻辑。

### 提交 5：P1 激活

- 接 `working_state`/`memory_context`/`maintenance`/CLI；测试。
- 回滚：按 feature flag `DWC_MEMORY_ACTIVATION=0` 关闭新路径，保留旧路径。

### 提交 6：P2 工程化

- FTS/busy_timeout/atomic_io/CI/README；测试。
- 回滚：按文件 revert；CI 不影响运行时。

### 生产部署

- 先 staging：全量 + gate + Semgrep/CodeQL。
- 生产按路径 checkout + 三方合并，保留 `config/llm.json`、`capabilities.yaml`、本地脚本改动。
- 重启 agent 后读心跳、RPC、`memory_retrieval`、`task_skill_written`；失败按 journal/备份回滚。

---

## 8. 最终验收清单

- [ ] `python -c`/PowerShell/`rm`/`git push` 全部 deny。
- [ ] `actor`/`candidates` 的 `import os`/`open`/`__class__`/`while` 全部拒绝。
- [ ] `web_read` 对 loopback/私网/重定向全拒。
- [ ] `_guard_path` 同前缀/符号链接全拒。
- [ ] 复读熔断触发 `_revision_retry`。
- [ ] `dwc_evo_round` 带 `judge` 时泄漏检查生效，缺失时 fail-closed。
- [ ] QA 未找到返回 `incomplete`。
- [ ] 5 个 test-only 模块至少有一个真实生产调用，其余标 `implemented_unwired`。
- [ ] `skill_prompt` 命中率 >0，`task_skill_written` >0。
- [ ] 二次初始化不 rebuild FTS；10 线程写无锁错误。
- [ ] 全量 ≥3285 passed / 0 failed；gate 8/8。
- [ ] README 数字与实测一致。
- [ ] CI 跑 pytest + gate + ruff（F 类/S102）+ bandit + Semgrep 自定义规则。

---

## 9. 不能靠代码消除的边界

这些不应写成“已修复”：

- 向量/RL/MemPO：保持 `memory_policy` 关闭；没有 hit-rate/effect 证据不启用。
- AKV serving、TIES/SFT：远程端点没有 serving/checkpoint 控制权。
- Windows 低权限沙箱：需要真实低权限账户/容器，代码只能 fail-closed。
- 价格：没有真实费率，保持 `indeterminate`。
- `r208` live：真端点仍可能超时，保持 live skip。
- `harness/step.py`/`ingest.py`：要么实现，要么删除文档声明；不能继续写“三入口”。

---

## 10. 一句话执行顺序

**先做提交 1/2（封命令和 exec），再做 3/4（SSRF、路径、retry、judge、done），然后 5（记忆激活），最后 6（FTS、原子写、CI、文档）。**  
不要在 P0 未封之前继续加记忆/进化功能；否则所有自改进都建立在“模型可执行任意代码”的地基上。
