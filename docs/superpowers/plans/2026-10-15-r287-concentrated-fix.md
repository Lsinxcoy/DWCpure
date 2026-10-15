# R287–R289 Concentrated Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 一次性收束普查抓到的全部问题（R280 一票否决＋adopt 无调用方＋credit 零 record＋28 个 anchor 过期断言）。

**Architecture:** 四个独立 Task（B/C/D/E），依赖关系：B→D（credit.record 的首个生产调用点就在 B 的喂数循环里）；C 独立；E 独立。B 是 P0，其余 P1。

**Tech Stack:** Python 3.11, pytest, stdlib only

**Spec:** docs/REPORT_R286_REAUDIT2.html（问题来源＋灯板）

## Global Constraints

- Python >= 3.11
- No new dependencies
- 中文注释/输出
- 测试零真 LLM（fake 对象，`pytest.raises` ≥ 5%）
- 不动生产链语义（只增调用不改判定；anchor 真值源只增不改，旧记录字节一致）
- 双副本纪律（E: 改完 md5 同步 `.dwc/scripts`＋`src`＋`tests`）
- 落盘默认关（`--apply` 才写；B/C/D 全程只读＋跑批，E 只改测试不断言生产）

## Review Focus

- 逐 task 喂数时 evidence_ref 必须带 task 名，否则 Brier  schmear 回"恒 0.5"（R280 原 bug 的镜像）。
- adopt 落地执行者必须幂等（同一 proposal 调两次不落两条规则），否则 rules.json 会长双胞胎。
- credit.record 的 CreditEntry 七元组缺字段即抛（CreditError），B 的喂数循环必须单条 try/except 隔离，不许一笔坏掀整轮。
- E 的断言更新只许改期望值，不许改被测逻辑；每个更新必须注根因"anchor+3（007/008/009 rung1）"，无根因的更新一律拒。
- E 不许"全文件 sed 批量改数"——逐条跑、逐条认、逐条注。

---

### Task B: R280 整轮一票否决 → 逐 task 喂数（P0）

**Files:**
- Modify: `src/dwc/harness/run_term.py:899-916`（回灌块，约 18 行 → 约 25 行）
- Test: `tests/test_r280_predictor.py`（append 2 测，约 40 行）

**Interfaces:**
- Consumes: `verdict.details: List[{task, success}]`（已有）；`OutcomePredictor(log_path).observe(key, ok, evidence_ref)`（已有，predictor.py）
- Produces: 每轮 `task:` 键观测数 ＝ 本轮 success 非 None 的 task 数（混合轮部分喂，不再整轮跳过）

- [ ] **Step 1: 写红测（混合轮部分喂）**

```python
def test_mixed_round_feeds_decided_only(tmp_path):
    from dwc.harness.run_term import _feed_predictor  # 若无此函数先跳 Step 3 再回
    ...
```

（若回灌逻辑是内联块无函数名：先把内联块提成 `_feed_predictor(details, db_path, task)` 纯函数——提炼本身不改语义，旧测照过。然后红测调它：details=[{success True},{success None}] ⇒ observe 被调 1 次且 key 正确。）
Run: `pytest tests/test_r280_predictor.py -q`
Expected: FAIL（整轮跳过 ⇒ 0 次）。

- [ ] **Step 2: 确认红因正确**

Expected: 失败是"observe 0 次"，不是 import 错。`not any(success is None)` 整轮门就是凶手（run_term.py:899-916）。

- [ ] **Step 3: 最小实现（逐条独立判定）**

```python
for d in _ds:
    _s = d.get("success")
    if _s is None:
        continue  # ★ 未评价跳过该 task（R280 纪律保留，粒度从轮降到条）
    _op280.observe("task:" + str(d.get("task") or task), _s is True,
                   evidence_ref="term_verdict:%s" % (d.get("task") or task))
```

（`_op280` 构造移出循环；`:memory:`/目录 guard 保留在外层。）

- [ ] **Step 4: 跑绿＋相关回归**

Run: `pytest tests/test_r280_predictor.py tests/test_r277_verdict_log.py -q`
Expected: 全 PASS。

- [ ] **Step 5: 生产验证（daemon 下一轮 task: 键入库）**

等 daemon 一轮后查 `dwc_predictor.jsonl` 新增 `task:` 行。N=0 ⇒ 回来查 guard（db_path 目录）。

- [ ] **Step 6: Commit＋双副本同步＋push**

### Task C: adopt 接调用方＋第五态下游落地（P1）

**Files:**
- Modify: `src/dwc/organs/evolver.py`（`adopt()` 后新增 `_land_adopted()`，约 30 行）；`scripts/dwc_evo_round.py`（试跑通过后调 adopt→land，约 15 行）
- Test: `tests/test_r287_adopt_land.py`（新建，约 80 行，tmp rules＋fake trial）

**Interfaces:**
- Consumes: `Evolver.adopt(baseline, current, eps)` → `{decision}`（已有，evolver.py:2224-2256）；`_land(rules_path, key, entry, backup_dir)`（已有，dwc_evo_round.py）
- Produces: `adopted_not_implemented` → 落盘一条 rules＋backup；幂等（同 key 调两次只落一条，第二次返回 `already_landed`）

- [ ] **Step 1: 写红测（第五态落盘＋幂等）**

```python
def test_adopted_not_implemented_lands_once(tmp_path):
    ...adopt 返回 adopted_not_implemented 的 proposal 调 _land_adopted 两次...
    assert 落盘 1 条且第二次 outcome == "already_landed"
```

Run: `pytest tests/test_r287_adopt_land.py -q`
Expected: FAIL（`_land_adopted` 不存在）。

- [ ] **Step 2: 实现 `_land_adopted(proposal, rules_path, backup_dir)`**

决策：复用 `_land` 的 key/entry/backup 契约（与 R278 落盘同口径，不另起格式）；落前查 key 已存在 ⇒ `already_landed`（幂等门）。

- [ ] **Step 3: evo_round 接线（试跑通过 → adopt → 落盘）**

只在 `trial success is True` 分支后调；adopt 返回非 `adopted_not_implemented` ⇒ 留痕不落（decision 进 item，不掀轮）。

- [ ] **Step 4: 跑绿＋回归＋commit 同步 push**

Run: `pytest tests/test_r287_adopt_land.py tests/test_r279_evo_round.py -q`

### Task D: credit 首个生产 record 调用（P1，前置 B）

**Files:**
- Modify: `src/dwc/harness/run_term.py`（B 的喂数循环内追加，约 10 行）
- Test: append `tests/test_r280_predictor.py`（1 测：fake ledger 收到条目，字段七元组齐）

**Interfaces:**
- Consumes: `CreditLedger.record(CreditEntry(t, edit, layer, hunk, dimension, delta_s, delta_c, adopted))`（已有，credit.py:86；字段缺即抛）
- Produces: 每轮每 task 一笔内存账（落盘文件是下一步，不在本 Task——先让账有数，再谈持久化；诚实边界写进注释）

- [ ] **Step 1: 写红测**（fake ledger 断言收到 `task:` 同名条目，adopted 与 success 一致）
- [ ] **Step 2: 实现**（单条 try/except 隔离，一笔坏不掀轮；ledger 实例挂 run_term 上，缺席则跳过留痕——不硬建文件）
- [ ] **Step 3: 跑绿＋commit 同步 push**

### Task E: 28 个 anchor 过期断言更新（P1，纯测试）

**Files:**
- Modify: 16 个测试文件（只改期望值，不改被测逻辑，见下表）

**Interfaces:**
- Consumes: 实测值（`N_TASKS=16`，`RUNG_MIX={1:13,3:3}`——已实测；其余执行时单文件实测填）
- Produces: 全量失败数 28→0（pre-existing 清零；新失败另算）

28 条清单（`r285_mine.txt` 存档）按根因分组：

| 组 | 测试 | 根因（已实测） | 改法 |
|---|---|---|---|
| A·计数 | test_judge::n_tasks(13→**16**) | anchor+3 | 期望改 16，注根因 |
| A·计数 | r199::rung_mix({1:10}→**{1:13}**) | anchor+3 | 期望改 {1:13,3:3}，注根因 |
| A·计数 | r199::split_mechanical、r165、r160、r176、r198、actor×2、applier | 同族（split 名单含新 task） | 逐条跑单测，按实际改，注根因 |
| B·集合 | r110×2、r117×2、r123、r132×2、r133×2、r134×2、r135×3、r205、run_term×2、r204 | behavior 集合 6+4 口径或任务池变化 | 逐条跑单测，按实际改，注根因 |

- [ ] **Step 1: 逐文件跑单测认领**（`pytest tests/test_XXX.py -q`，一次一文件，不许全量混跑认领）
- [ ] **Step 2: 逐条改期望＋注根因**（无根因的更新视为编造，打回）
- [ ] **Step 3: 全量验证 28→0**（后台 `pytest tests/`，剩新失败另立项）
- [ ] **Step 4: Commit＋push**（纯测试 commit，注明"断言对齐 anchor+3，非行为变更"）

---

## Self-Review

1. **Spec 覆盖**：R286 四个问题 → B/C/D/E 四个 Task，无遗漏。02:30 待验无需方案（明早看数），已注明不硬塞。
2. **类型一致**：B 的 `task:` 键与 R280 同命名空间；C 复用 `_land` 契约；D 的七元组与 credit.py:29 一致。
3. **无编造数字**：E 的 28 个新期望值执行时实测填（A 组两个已实测值写入，其余不写——写即编）。
4. **Proportion**：B/C/D 精确到行，E 给方法＋判据（逐条贴 28 个 diff 会写成代码转录，违 proportion）。
