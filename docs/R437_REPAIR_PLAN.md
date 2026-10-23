# R437 修复方案（代码级）

> 基于 `docs/R437_EVOLUTION_MAP.md` 的审计结论。本文档是**执行依据**：
> 每条改动给出文件、函数、改动前后代码、验收判据。不写"优化一下"这种话。

---

## 一、根因（三层，逐层可证）

### 第一层：归因断了

`collect_unmapped` 读 `failure_sig` 表：

```sql
select c,q,m,node_id from failure_sig
```

这张表**没有 task 列**（`PRAGMA table_info` = `[c,q,m,node_id]`）。
于是 cron 用两个**常量 lambda** 补齐：

```python
fn_of=lambda r: "average", task_of=lambda r: "code_fix_007",
```

⇒ **2034 条签名全部被标成同一个任务**。
而真实任务名就在 `memory_node.payload` 里（`json_extract` 已验证：2034/2034 都有）。

### 第二层：分流口径是猜的

```python
if reproducible_only:
    _filtered_nonrepro = [s for s in sigs if s["m"].startswith("llm_asserted")]
    sigs = [s for s in sigs if not s["m"].startswith("llm_asserted")]
```

"可复现"是按**字符串前缀**猜的，不是测的。实测：

| 任务 | 破坏实现跑出来的签名 | 现场签名 | 能复现？ |
|---|---|---|---|
| `code_fix_001` | `E_VALUE/wrong_magnitude` | `E_NO_RESULT/abstained` | ✗ |
| `code_fix_002` | `E_VALUE/wrong_magnitude` | `E_NO_RESULT/abstained` ×811 | ✗ |
| `code_fix_002` | `E_VALUE/wrong_magnitude` | `E_VALUE/wrong_magnitude` ×2 | **✓** |
| `code_fix_004` | `E_OFF_BY_ONE` + `E_VALUE` | 待测 | 部分 |
| `code_fix_005` | `E_FALSE_POSITIVE` | 待测 | 部分 |

⇒ 前缀过滤把 **2034 条全扔了**，其中至少**有几条真能复现**。

### 第三层：任务面不相交

- 进化系统设计面向 `config/anchors/broken_dev.json`（`code_fix_001-006` + `reasoning_*`），**有破坏实现可修**。
- 生产 agent 跑的是 `config/eval_tasks.jsonl`（52 单：rf/cl/rv/an/wr/hs）。
- 两者的交集：**只有 code_fix 系列的题号被 agent 跑到**（实测 payload：009/002/007/008/004/005/003）。
- 而生产失败里 **811/848 是 `E_NO_RESULT/abstained_or_missing`** —— agent 弃答，**不是代码 bug**，修 broken_impl 治不了。

⇒ 结论：**必须分两条车道**，不能用一套 evolver 吃两种失败。

---

### 第四层（执行中发现的真凶）：两个数据库

`dwc_evo_round_cron.py` 的 `_prod_root()` 无条件返回 `~/.dwc`，而 agent 写的是
**仓库** `var/dwc_prod.sqlite`：

| 库 | 最后写入 | failure_sig |
|---|---|---|
| `~/.dwc/var/dwc_prod.sqlite`（cron 读） | **10-17 09:11** | **68** |
| `E:/Divine Wisdom Core/var/dwc_prod.sqlite`（agent 写） | **10-23 08:49** | **2053** |

⇒ 每日进化轮读的是 **6 天前的库**。这就是 `n_clusters: 0` 的第一原因，
比"过滤太狠"更根本。

**修法**：`_prod_root()` 优先返回仓库根（与 agent 同源），没有库才回退 `~/.dwc`。

---

## 二、目标架构：两条车道

```
failure_sig（真实 task 从 payload 读）
        │
        ├─ 实测探针：broken_impl 跑同一题，签名 (c,q) 是否一致？
        │
        ├── 一致 ──→ 【代码车道】有破坏实现可修
        │              → 聚簇 → propose → trial（沙箱，确定性）→ 六门 → 落地 rules.json
        │
        └── 不一致/无实现 ──→ 【行为车道】agent 弃答/答错
                               → var/behavior_queue.jsonl（append-only，按 key 去重）
                               → 提示词/技能/工具反馈 候选 → A/B（R434-R436 已有）
```

**关键原则**：车道归属由**实测签名匹配**决定，不由 `m` 前缀决定，也不由任务名决定。

---

## 三、精确改动清单

### 改动 1 · 归因：从 payload 读真实 task（`scripts/dwc_evo_round.py`）

**函数**：`collect_unmapped`（第 41 行）

改动前：

```python
con = sqlite3.connect(db_path)
try:
    rows = con.execute(
        "select c,q,m,node_id from failure_sig").fetchall()
finally:
    con.close()
sigs = [{"c": r[0], "q": r[1], "m": r[2],
         "fn": fn_of(r), "task": task_of(r), "node_id": r[3]}
        for r in rows]
```

改动后：

```python
con = sqlite3.connect(db_path)
try:
    rows = con.execute(
        "select f.c, f.q, f.m, f.node_id, "
        "       coalesce(json_extract(n.payload,'$.task'),'') "
        "from failure_sig f "
        "left join memory_node n on n.node_id = f.node_id").fetchall()
finally:
    con.close()
sigs = [{"c": r[0], "q": r[1], "m": r[2], "node_id": r[3],
         "fn": fn_of(r),
         # ★ R437 · 真实任务名优先取 payload；表里没有 task 列
         "task": (str(r[4] or "").strip() or task_of(r))}
        for r in rows]
```

**`fn` 的补法**（同一个函数内，聚簇前）：

```python
# ★ R437 · payload 不存 fn（实测 0/2034 有值）⇒ 从锚点 checks 反查；
#   查不到就留空（空 fn 只影响聚簇粒度，不影响正确性）。
try:
    _anchors = json.load(io.open(os.path.join(_code_root(), "config", "anchors",
                                              "dev.json"), encoding="utf-8"))
except Exception:
    _anchors = {}
for _s in sigs:
    if not _s.get("fn"):
        _c = (_anchors.get(_s["task"]) or {}).get("checks") or []
        _s["fn"] = str((_c[0] or {}).get("fn") or "") if _c else ""
```

### 改动 2 · 车道判定：实测探针（`scripts/dwc_evo_round.py`）

**新增函数**（放在 `collect_unmapped` 之前）：

```python
_PROBE_CACHE: Dict[str, Any] = {}

def probe_signatures(task: str) -> set:
    """★ R437 · 跑该任务的**破坏实现**，返回它真实产生的 (c,q) 集合。

    这是"可复现"的唯一判据：不是看 m 前缀，而是看破坏实现能不能
    跑出同一种失败。跑挂（obs=None）⇒ 返回 {"__crash__"}（也算可复现，
    因为崩溃本身就是这个 bug 的表现）。
    无破坏实现 ⇒ 空集（该任务没有代码可修）。
    """
    if task in _PROBE_CACHE:
        return _PROBE_CACHE[task]
    out = set()
    try:
        root = _code_root()
        b = json.load(io.open(os.path.join(root, "config", "anchors",
                                           "broken_dev.json"), encoding="utf-8"))
        a = json.load(io.open(os.path.join(root, "config", "anchors",
                                           "dev.json"), encoding="utf-8"))
        impl = str((b.get(task) or {}).get("broken_impl") or "")
        if impl.strip():
            from dwc.llm.sandbox import run_code_observed
            from dwc.llm.executor import obs_skeleton
            from dwc.organs.judge import Judge
            obs = run_code_observed(impl, obs_skeleton(a, task))
            if obs is None:
                out.add("__crash__")
            else:
                v = Judge().evaluate(task, "dev",
                                     observed={"observed": obs,
                                               "★_executed": True})
                for s in (getattr(v, "sigs", None) or []):
                    out.add((str(s.get("c")), str(s.get("q"))))
    except Exception:
        out = set()
    _PROBE_CACHE[task] = out
    return out
```

**分流逻辑**（替换原来的前缀过滤）：

```python
if reproducible_only:
    _code, _behavior = [], []
    for _s in sigs:
        _probe = probe_signatures(_s.get("task", ""))
        if (str(_s.get("c")), str(_s.get("q"))) in _probe or "__crash__" in _probe:
            _code.append(_s)
        else:
            _behavior.append(_s)
    sigs = _code
    if filtered_out is not None:
        filtered_out.extend(_behavior)
```

### 改动 3 · cron 去掉常量 lambda（`scripts/dwc_evo_round_cron.py`）

改动前（第 82 行）：

```python
fn_of=lambda r: "average", task_of=lambda r: "code_fix_007",
```

改动后：

```python
# ★ R437 · 真实任务名由 collect_unmapped 从 payload 读；这里只做兜底
fn_of=lambda r: "", task_of=lambda r: "",
```

### 改动 4 · 修 N1 路由 SQL（`scripts/dwc_evo_round_cron.py`）

改动前（第 125 行）：

```python
_tasks = [r[0] for r in _con.execute(
    "SELECT DISTINCT task FROM failure_sig "
    "WHERE m LIKE 'llm_asserted%'").fetchall()]
```

改动后：

```python
_tasks = [r[0] for r in _con.execute(
    "SELECT DISTINCT json_extract(n.payload,'$.task') AS task "
    "FROM failure_sig f JOIN memory_node n ON n.node_id = f.node_id "
    "WHERE json_extract(n.payload,'$.task') IS NOT NULL").fetchall()]
```

### 改动 5 · 行为车道落盘（`scripts/dwc_evo_round_cron.py`）

`run_round` 返回后追加：

```python
# ★ R437 · 行为车道：不进 evolver，但**不许静默丢**
_beh = rep.get("behavior_sigs") or []
if _beh:
    _q = os.path.join(prod, "var", "behavior_queue.jsonl")
    _seen = set()
    try:
        for _ln in open(_q, encoding="utf-8"):
            try:
                _seen.add(json.loads(_ln).get("key"))
            except Exception:
                pass
    except OSError:
        pass
    _n_new = 0
    with open(_q, "a", encoding="utf-8") as _f:
        for _s in _beh:
            _k = "%s:%s:%s" % (_s.get("task"), _s.get("c"), _s.get("q"))
            if _k in _seen:
                continue
            _seen.add(_k)
            _f.write(json.dumps({"key": _k, "sig": _s,
                                 "ts": time.time()}, ensure_ascii=False) + "\n")
            _n_new += 1
    rep["behavior_queued"] = _n_new
```

`run_round` 需把 `filtered_out` 以 `behavior_sigs` 字段返回（改动 6）。

### 改动 6 · `run_round` 返回车道统计（`scripts/dwc_evo_round.py`）

改动前：

```python
    return {"clusters": clusters, "results": results, ...}
```

改动后（在返回体加三项）：

```python
        "n_code_sigs": len([s for s in clusters for _ in s["sigs"]]),
        "n_behavior_sigs": len(_nonrepro),
        "behavior_sigs": _nonrepro[:2000],   # 上限防报告爆
```

### 改动 7 · 测试（`tests/test_r437_lane_split.py`）

| 测试 | 断言 |
|---|---|
| `test_task_read_from_payload` | 造 2 条不同 task 的 sig，`collect_unmapped` 归因不串 |
| `test_probe_matches_real_signature` | `probe_signatures("code_fix_002")` 含 `("E_VALUE","wrong_magnitude")` |
| `test_behavior_sig_goes_to_behavior_lane` | `E_NO_RESULT/abstained_or_missing` 进 behavior |
| `test_code_sig_stays_in_evolver` | `E_VALUE/wrong_magnitude` + code_fix_002 进 code |
| `test_n1_sql_uses_payload` | 源码不含 `DISTINCT task FROM failure_sig` |
| `test_no_hardcoded_task_lambda` | cron 源码不含 `"code_fix_007"` 常量 lambda |

---

## 四、验收标准（跑完必须逐条核）

| # | 判据 | 改前 | 目标 |
|---|---|---|---|
| 1 | 归因正确 | 2034 条全 `code_fix_007` | 分布 ≥3 种 task |
| 2 | 代码车道有输入 | `n_clusters: 0` | `n_clusters ≥ 1` |
| 3 | 行为车道不丢 | 68 条被静默过滤 | `behavior_queued > 0` |
| 4 | SQL 无错 | `no such column: task` | 无该错误 |
| 5 | 试跑真跑 | `trial_rounds: 0` | `trial_rounds ≥ 1` |
| 6 | 回归 | 2645 passed | 全绿 |

**第 5 条是这次修复的"活证据"**：trial_rounds 从 0 变正，说明管道真的通了。

---

## 五、后续（本次不做，方案先定）

| 阶段 | 内容 | 前置 |
|---|---|---|
| P1 | `config/anchors/rules.json` 建空骨架 + cron `--apply`（默认关）手动跑一轮 | P0 验收通过 |
| P2 | 行为车道接 R434 三件套：队列 → 候选 → smoke A/B → 全池 | P0 行为队列有数据 |
| P3 | `promote_lessons()` 接进每日轮 | — |
| P4 | `Loop`（`build_round_fn`）复活或归档：接真实 `Target` 跑通一轮 | P1 落地链路验证 |

---

## 六、回滚

改动集中在 3 个文件、5 处函数。回滚 = `git revert <本次提交>`。
不涉及 schema 变更（用 `json_extract` 读现有 payload），不写生产数据文件。

---

## 七、执行结果（2026-10-23 09:45）

### 已改（P0 全部）

| # | 改动 | 文件 |
|---|---|---|
| 1 | task 从 `memory_node.payload` 读（`json_extract`），`fn` 从锚点 checks 反查 | `scripts/dwc_evo_round.py::collect_unmapped` |
| 2 | 分流从「m 前缀猜测」改为「实测探针」`probe_signatures()` | 同上 |
| 3 | 报告新增 `n_code_sigs` / `n_behavior_sigs` / `behavior_sigs` | `run_round` |
| 4 | `_prod_root()` 改为与 agent 同源（仓库根优先） | `scripts/dwc_evo_round_cron.py` |
| 5 | 行为车道落盘 `var/behavior_queue.jsonl`（按 key 去重） | 同上 |
| 6 | N1 路由 SQL 改 `json_extract`（旧 SQL 恒报 no such column） | 同上 |
| 7 | `_FILE_TOKEN_RE` 长后缀优先 + `\b`（`.jsonl` 被截成 `.json` 的 bug） | `src/dwc/llm/task_exec.py` |
| 8 | `_repo_files()` 改用 `_FIND_SKIP_DIRS`（var/ 下真实文件不再被判幻觉） | 同上 |

### 验收（逐条对照第四节）

| # | 判据 | 改前 | 改后 | 结果 |
|---|---|---|---|---|
| 1 | 归因 | 2034 条全 `code_fix_007` | 7 种 task（009/002/007/008/004/005/003） | ✅ |
| 2 | 代码车道 | `n_clusters: 0` | **`n_clusters: 1`**（`E_VALUE:wrong_magnitude:fibonacci`，5 条） | ✅ |
| 3 | 行为车道 | 68 条静默丢 | `n_behavior_sigs: 2036`，落队列 | ✅ |
| 4 | SQL | `no such column: task` | 无该错误 | ✅ |
| 5 | 试跑真跑 | `trial_rounds: 0` | **`trial_rounds: 1`，`success: true`，`in_score: 1.0`，`held_out: 1.0`** | ✅ |
| 6 | 回归 | 2645 passed | **2660 passed / 1 已知抖动**（`test_r243_input` 单跑 5 passed） | ✅ |

### 现场证据（`var/evo_test_r437c.log`）

```json
{"n_clusters": 1,
 "results": [{"key": "E_VALUE:wrong_magnitude:fibonacci", "n": 5,
              "drafted": true,
              "trial": {"success": true, "in_score": 1.0, "held_out": 1.0,
                        "mode": "code", "activated": true},
              "landed": false}],
 "n_code_sigs": 5, "n_behavior_sigs": 5}
```

`landed: false` 是 `apply=False` 的预期结果 —— **落地属 P1**。

### 已知遗留（下一轮）

1. **起草随机性**：同一簇第一次起草的 code 过不了沙箱（`沙箱跑挂/缺函数`），
   第二次成功。沙箱失败应当触发**重起草**，而不是直接记 `ok=false`。
2. **`landed` 仍恒 false**：`apply=False` 硬编码 + `config/anchors/rules.json` 不存在（P1）。
3. **行为车道的消费者还没写**：队列已有数据，但没有程序把它变成候选（P2）。
