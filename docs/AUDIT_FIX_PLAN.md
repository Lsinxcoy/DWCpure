# DWC 审计修复方案（代码级 · P0–P3 全覆盖）

> 依据：2026-10-23 深度审计报告（2640✓/76✗/5跳过；3,686 lint；72 bandit；371 硬编码路径）
> 分支：divine-wisdom-core-pure · 原则：零功能变更、逐簇验证、可回滚（每次提交独立）

---

## P0-1 · 可移植性：371 处硬编码 E: 盘路径（最高优先）

### 根因
项目从开发机（E: 盘）迁移，路径以字面量写死在 tests/scripts/src 中。

### 修复（统一范式，与仓内已有 87 处一致）
**目标表达式（所有测试文件）：**
```python
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
```
（tests/ 下 dirname×2 = 仓库根；已有 87 处同款，模式已验证）

**逐变体替换表：**

| # | 原句（变体） | 数量 | 替换为 |
|---|---|---|---|
| 1 | `ROOT = r"E:/Divine Wisdom Core"` | 136 | `ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` |
| 2 | `ROOT = r"E:\Divine Wisdom Core"` | 43 | 同上 |
| 3 | `ROOT = "E:/Divine Wisdom Core"` | 24 | 同上 |
| 4 | `ROOT = r"E:/Divine Wisdom Core"`（函数内缩进） | 2 | `    ROOT = ...`（保留缩进） |
| 5 | `ROOT="E:/Divine Wisdom Core"; sys.path.insert(0, os.path.join(ROOT,"src"))` | 7 | 拆两行：`ROOT = ...` + `sys.path.insert(0, os.path.join(ROOT, "src"))` |
| 6 | `ROOT = os.path.join("E:", os.sep, "Divine Wisdom Core")` | 2 | 同 #1 |
| 7 | conftest.py `_R292_ROOT = r"E:/Divine Wisdom Core"` | 1 | `_R292_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))` |

**scripts/（历史工具，一并修）：**
- `classify_papers19.py`：3 处 `E:/Divine Wisdom Core/...` → `os.path.join(SCRIPT_ROOT, ...)`（脚本同级上溯）
- `dedup_audit.py` / `dedup_cross.py` / `deep_read_designs.py`：ROOT/OUT 指向 `.cache/gh_clones`、`docs/` → 相对上溯
- `dwc_anchor_drift_watch.py`：仅注释提及，不改代码

**src/ 生产代码（E:/ARSI 判据文件路径可配置化）：**
- `foundation/capability_groups.py:53`：
```python
# 原：SEALED_PATH = r"E:/ARSI/config/sealed_tasks.yaml"
# 新：env 覆盖 + 仓库内默认 + 找不到时保留 ConfigError 语义（报错信息含查找路径）
_SEALED_ENV = os.environ.get("DWC_SEALED_TASKS", "").strip()
SEALED_PATH = (_SEALED_ENV if _SEALED_ENV else
               os.path.join(ROOT, "config", "sealed_tasks.yaml"))
```
- `foundation/dial_config.py:126`：`_sealed_task_count()` 同样改用 capability_groups.SEALED_PATH 语义（env 优先，缺省仓库 config/，缺失仍 DialError——「无法判定不是通过」语义不变）

### 验证
- `pytest tests/test_capability_groups.py`（13 失败簇应清零或仅剩环境类）
- 全量 pytest 收集 0 error
- `grep -rn "E:/\|E:\\\\" tests scripts src` 仅剩注释/文档说明文字

---

## P0-2 · 依赖声明不一致

| 文件 | 缺失 | 修复 |
|---|---|---|
| requirements.txt | pypdf（pyproject 有） | 补 `pypdf>=4.0` |
| requirements.txt | textual（pyproject optional tui） | 补 `textual>=1.0`（TUI 测试无条件 import，必须在主依赖） |
| test_r422_retry_budget.py | DWC_LLM_BASE_URL 未配 → configured=False 短路 | 测试顶部 `monkeypatch.setenv` 注入假 base_url，使 urlopen 路径可达（验证重试逻辑本体） |

### 验证
- TUI 簇（r239/r243/r244/r245/r264/r271/r272/r273）26 失败 → 应大幅减少
- `python -c "import textual"` 成功

---

## P1-1 · 声称门：README 数据过期

- README badge：`pytest-1598 passed` → 以实际全绿数更新（修复后实测值）
- rounds R1–R253 → R438；commits 274 → 532
- README「四层验证每轮必过: pytest（1598 全绿）」→ 更新

### 验证
- badge 数字 == 本机实测

---

## P1-2 · 沙箱安全（sandbox.py，3 处）

1. **超时线程残留**（`t.join(timeout)` 超时后 daemon 线程继续跑）：
```python
# _run 内加操作计数节流，每 10 万次 ast.Call 检查一次全局 deadline
# 方案：进程级隔离太重，改为「for/range 上限 + 字面量上限 + 超时置标志」
_MAX_ITER = 1_000_000      # for 循环总迭代上限
_MAX_LITERAL = 10_000      # 单项字面量上限（防 [0]*10**9 内存爆）
```
2. `visit_For` 新增守卫：`iter` 为 `range(...)` 时校验 stop 为小字面量；`visit_Constant` 校验大数；`visit_BinOp` 校验 `*` 一侧为小字面量。
3. 清理恒真条件：
```python
# 原：if "dunder" in ("dunder",) and node.attr.startswith("__"):
# 新：if node.attr.startswith("__"):
```

### 验证
- `run_code_observed("for i in range(10**9): pass", ...)` 立刻拒绝（SandboxError）
- 合法纯函数代码不受影响（2639 其余测试回归）

---

## P1-3 · 17 处 F821 undefined name

| 文件 | 行 | 缺名 | 修复 |
|---|---|---|---|
| harness/loop.py | 1114/1141/1148 | Tuple | `from typing import ... Tuple` 补入（或改 `tuple`） |
| llm/client.py | 358/359/384/570/612/613 | List | 补 `List` 入 typing import（有 future import，注解惰性） |
| organs/benchmark_fitness.py | 190 | List | 同上 |
| organs/contracts_builtin.py | 49/58 | FGGM（应为 ContractRegistry） | 返回注解改为 `ContractRegistry`（import 自 dwc.organs.contract） |
| organs/replay.py | 333/336 | Optional | 补入 typing import |
| organs/weakness.py | 206/223 | Any | 补入 typing import |

### 验证
- `python -c "import typing; typing.get_type_hints(dwc.organs.contracts_builtin.budget_window_contract)"` 不炸
- ruff F821 清零

---

## P2-1 · ruff 批量清理

- `ruff check src --fix` → 2,212 自动可修（UP006/UP031 等）
- 剩余手工项抽查：`F401` 未用 import → 补删；`F841` 未用变量 → 删或 `_`
- **不动**：不安全的 auto-fix（871 unsafe 跳过）；`FGGM` 系列已由 P1-3 处理

### 验证
- ruff 错误数 3,686 → 预计 <1,000（遗留多为 UP031 printf 风格，非逻辑）
- 全量 pytest 无新增失败

---

## P2-2 · 安全清洁

- agent_quality.py:287 `hashlib.md5` → `hashlib.sha256`（文件内容哈希）
- prompt_ota.py:179 `hashlib.md5(key)` → `hashlib.sha256`（分桶随机，改后哈希分布不变）
- causal_chain.py B608：动态列名 `"%s" % col` → 列名白名单校验（`_COLS = {...}`，非白名单直接 ValueError）
- executor.py `ast.literal_eval` 路径已是安全字面量（确认，不改）

### 验证
- `pytest tests/test_causal_chain.py` 全绿
- bandit HIGH 6 → 2（md5 项消除）

---

## P2-3 · 仓库卫生

- install.sh:11 `REPO_URL` → 支持 `DWC_REPO_URL` env 覆盖（默认仍指原仓库 master，发布语义不变）；自更新告警逻辑不动
- 删除入库的运行台账：`artifacts_probe*/`（daemon_state.json + rounds.jsonl）、19 个 `.bak_rXX`、根级 `archiveknowledge3_R21x*.json`（与 archive/ 重复）
- `docs/repos/_all.json`（3.5MB）→ git rm 移出版本库（仍留本地）

### 验证
- `git status` 干净；仓库体积下降

---

## P3 · 版本锚定

- 打首个 tag `v0.1.0`（`git tag -a v0.1.0 -m "审计修复后基线"`）+ push 到 origin/divine-wisdom-core-pure
- README 加「版本」段指向 tag

### 验证
- `git tag -l` 有 v0.1.0；`git describe` 可用

---

## 执行顺序与验证门

| 步 | 动作 | 验证门 |
|---|---|---|
| 1 | P0-1 路径替换（脚本批处理） | grep E: 清零于代码；pytest 收集 0 error；capability_groups 簇改善 |
| 2 | P0-2 依赖 + R422 env | textual 可导入；R422 4 失败清零 |
| 3 | P1-2 沙箱 | 恶意样本立即拒 |
| 4 | P1-3 F821 | 反射不炸；ruff F821=0 |
| 5 | P2-1 ruff --fix | lint 降 60%+ |
| 6 | P2-2 md5/SQL | 相关测试全绿 |
| 7 | P2-3 仓库清理 | git 干净 |
| 8 | P1-1 README 更新 | badge 与实测一致 |
| 9 | 全量回归 | 76 → 记录改善量级 |
| 10 | P3 tag + 提交 | 提交链完整（每步一个 commit） |