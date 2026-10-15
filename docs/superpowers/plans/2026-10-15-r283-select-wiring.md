# R283 Select 接线 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让 DWC 生产里第一次出现"用预测/打分做选择"的真决策（现在全是固定单＋轮换抽单）。

**Architecture:** 分三档——P0 只跑验证（0 行新码），P1 小手术接 deterministic 候选，P2 只记账不动（缺生产决策循环是前提，硬接就是造壳）。

**Tech Stack:** Python 3.11, pytest, stdlib only（predictor/bench/select 全是 stdlib，无新依赖）

## Global Constraints

- Python >= 3.11
- No new dependencies（全链 stdlib，bench.py 的 yaml 读 drift.yaml 仅 --select predictor 模式，nightbench 不触发）
- 中文注释/输出（R268 纪律延续）
- 测试零真 LLM（fake 对象，`pytest.raises` ≥ 5%）
- 不动生产链语义（只增调用不改判定；bench 默认 `--select full` 不变）
- 双副本纪律（E: 改完 md5 同步 `.dwc/scripts` + `tests`）
- 落盘默认关（`--apply` 才写；P0 全程只读＋跑批）

---

## 深度思考结论（先看再做）

### 反转 1：R275"predictor 零 observe"是误报，真相是"答错了地方"

- `scripts/dwc_bench.py:234-243`（R231 接线）每单跑完就 observe `bench:{tid}`＋`rung:`＋`fail:`——代码在。
- 但生产 88 行观测（E: 81 行＋.dwc 7 行）**全是 inbox: 键**，一个 bench: 都没有——因为生产从没跑过 bench 这条路（nightbench 走自己单子）。
- 所以不是"没人答"，是"答题的人（bench）从没上过考场"。P0 就是把它送上考场。

### 反转 2："select"有 4 个，不是一个

| # | select | 输入→输出 | 调用方现状 |
|---|--------|-----------|-----------|
| S1 | `world_model.select`（world_model.py:537） | 世界树候选节点→信息增益排序 | 零调用（需探索循环，Loop 零调用是前提） |
| S2 | `metric_loop.select`（metric_loop.py:461＋loop.py:1085） | dev_points→开发点 | loop 里已调，但 Loop 生产零调用 |
| S3 | `bench_select`（dwc_bench.py:252） | bench 任务→p̂+λu 排序 | 已实现，`--select predictor` 显式开，无人开过 |
| S4 | `evolver.select_winner`（evolver.py:438） | 已评估提案→赢家 | 进化链内已用 |

"P1 接 select"指 S3 转正＋S4 复用；S1/S2 没有生产调用场景，硬接就是造第 7 个壳。

### 反转 3：candidates 的搭档不是 diagnose，是 applier

- `candidates.generate`（candidates.py:203，R31 纪律④基线复现断言）产的是**进化 patch 候选**，R275"被绕过"成立（loop 走 `_dir_generate→diagnose`）。
- 但 R278 新链（LLMMutator）产的也是提案——两者是**双轨关系**（deterministic 规则 vs LLM 起草），不是替代关系。
- P1 就是把 deterministic 这轨接回 applier 落地前（多一个候选源），与 LLM draft 并存。

### 键命名空间现状（第三次分裂预警）

- `bench:` 问（S3）——无答（生产没跑 bench）
- `inbox:` 答 88 行——无人问（predict() 从没被问过 inbox: 键）
- `task:` 答（R280 刚接，daemon 重启后才有数）——S3 不问它
- **决策：不强统**（bench 任务池与 anchor 任务池是两池，硬统是编造对应关系）。P0 让 bench: 自问自答闭环；task: 走 run_term 自闭环；Brier 分开算。YAGNI。

---

## Task 1：P0 —— bench predictor 选择转正验证（0 行新码）

**Files:**
- Modify: 无
- Test: 无（跑批验证，非 pytest）
- Run: `scripts/dwc_bench.py --select predictor` vs `--select full` 同一任务池

**Interfaces:**
- Consumes: `bench_select(tasks, lam)`（dwc_bench.py:252，已存在）；λ 读 `config/drift.yaml:drift.bench.explore_lambda`（已存在）
- Produces: 两轮跑批报告（stdout JSON：`select_mode/select_lambda/n/pass/pass_rate`）＋ `var/dwc_predictor.jsonl` 新增 bench: 观测行

- [ ] **Step 1: 干跑 full 基线（后台，约 10 分钟）**

```bash
C:/Users/41228/.dwc/.venv/Scripts/python.exe scripts/dwc_bench.py --select full > C:/Users/41228/AppData/Local/Temp/r283_full.log 2>&1
```

Expected: EXIT=0，stdout 尾行 JSON `select_mode=full`，`pass_rate` 数字。

- [ ] **Step 2: 干跑 predictor 选择（后台，约 10 分钟）**

```bash
C:/Users/41228/.dwc/.venv/Scripts/python.exe scripts/dwc_bench.py --select predictor > C:/Users/41228/AppData/Local/Temp/r283_pred.log 2>&1
```

Expected: EXIT=0，`select_mode=predictor`，`select_lambda` 非空（读 drift.yaml 成功）。

- [ ] **Step 3: 对账三数**

```bash
C:/Users/41228/.dwc/.venv/Scripts/python.exe -c "
import json
from dwc.organs.predictor import OutcomePredictor
import sys; sys.path.insert(0, 'src')
p = OutcomePredictor()
print('BRIER:', p.calibrate()['brier'])
print('BENCH_KEYS:', [k for k in p._counts if k.startswith('bench:')][:5])
"
```

Expected: `BENCH_KEYS` 非空（第一轮全是先验 0.5 也算数——诚实记录）；BRIER 是数字不是 None。
Success 标准：predictor 轮 pass_rate 不低于 full 轮（允许 ±1 单方差，两轮任务池相同）。

- [ ] **Step 4: daemon 重启吃 R280（predictor task: 回灌上线）**

```bash
# 先 Stop 老 daemon（按 pid 白名单，不用宽匹配），再起 start --llm
```

Expected: 新 heartbeat pid，`task:` 键在下一轮出现。
Note: 重启是生产操作，执行前需用户拍板（本计划批准≠重启批准）。

## Task 2：P1 —— candidates deterministic 轨接回 applier 落地前（小手术）

**Files:**
- Modify: `src/dwc/organs/evolver.py`（`diagnose` 后增一路 deterministic 候选合并，约 20 行，adjusted: ×3 → ~60 actual）
- Test: `tests/test_r283_candidates_rail.py`（约 60 行，fake diffs＋fake baseline，`pytest.raises` ≥ 5%，adjusted: ×2 → ~120 actual）
- Modify: `scripts/dwc_evo_round.py`（`run_round` 里合并 deterministic 候选与 LLM draft，约 15 行）

**Interfaces:**
- Consumes: `candidates.generate(sig, diffs, baseline_source, fn_name) -> Dict`（candidates.py:203，已存在；diffs 必须来自 `judge._diff`，手拼即编造——测试用真 `_diff` 产出，不手拼）；
  `Mutator.propose(sig) -> Optional[Proposal]`（evolver.py，已存在）
- Produces: `diagnose()` 返回新增 `deterministic` 字段（List[Dict]，可为空）；下游 `run_round` 试跑时 deterministic 候选与 LLM draft 同跑同判，分记 `trial_det/trial_llm`

- [ ] **Step 1: 写红测（deterministic 轨输出结构）**

```python
def test_det_rail_present(tmp_path):
    from dwc.organs.evolver import Evolver
    sigs = [{"c": "E_VALUE", "q": "wrong_magnitude", "m": "",
             "fn": "zzz_det_fn", "task": "t"}]
    d = Evolver().diagnose(sigs)
    assert "deterministic" in d  # 红：字段不存在
```

Run: `pytest tests/test_r283_candidates_rail.py -q`
Expected: FAIL（`deterministic` KeyError 缺字段）。

- [ ] **Step 2: 最小实现（diagnose 尾部增一路，不动原有 proposals/unmapped 口径）**

```python
# evolver.py diagnose() return 前增：
det = []
try:
    from dwc.organs.candidates import CandidateGenerator
    _cg = CandidateGenerator()
    for s in signatures:
        _r = _cg.generate(s, diffs=_diffs_for(s), baseline_source=_base_for(s))
        if _r.get("cands"):
            det.extend(_r["cands"])
except Exception:
    det = []  # deterministic 轨坏了不掀诊断（留痕由调用方记 reason）
out_dict["deterministic"] = det
```

（`_diffs_for/_base_for` 取数细节在实现时按 judge._diff 真签名补，禁手拼 diffs——R31 纪律④。）

- [ ] **Step 3: 跑绿＋相关回归**

Run: `pytest tests/test_r283_candidates_rail.py tests/test_r279_evo_round.py tests/test_r278_llm_mutator.py -q`
Expected: 全 PASS（diagnose 原有 `proposals/n_unmapped` 口径零改，旧测全绿）。

- [ ] **Step 4: evo_round 双试跑（deterministic 与 LLM 同跑同判）**

`run_round` 里每个簇：LLM draft 照旧；deterministic 候选如有则同样 `trial_fn` 跑一遍，结果分记。落盘只落试跑通过者（先到先落，同过则 LLM 优先——理由写进注释：deterministic 规则 R1/R2 只覆盖两类，LLM 覆盖面广）。

- [ ] **Step 5: Commit＋双副本同步＋push**

```bash
git add src/dwc/organs/evolver.py tests/test_r283_candidates_rail.py scripts/dwc_evo_round.py
git commit -m "R283 candidates deterministic轨接回"
git push origin master
# cp 同步 .dwc/scripts＋tests，md5 对齐
```

## Task 3：P2 —— S1/S2＋direction 三件套记账（不动代码）

**Files:**
- Modify: 无（只在 evo_round 每日报告里加 `adopt` 负事件行——`rep["not_wired"] = ["world.select", "metric.select→adopt", "direction.next_action"]`，约 5 行，算 Task 2 附带，不单独立测）

**Interfaces:**
- Consumes: QUALITY_GATE Γ 纪律（"本应调用但未调用"负事件）
- Produces: 每日 04:00 报告自带"未接线清单"，Loop 生产调用之日即摘牌之时

- [ ] **Step 1: 报告加负事件行＋commit**

前置条件（硬门，不满足就永远 P2）：Loop.round 生产调用（daemon/nightbench 任一）。门不满足前 S1/S2 任何接线 PR 一律拒——防造壳。

---

## Self-Review

1. **Spec 覆盖**：用户要"select 交点"——S3 转正（Task 1）、deterministic 轨（Task 2）、S1/S2 记账（Task 3），candidates/planner/select 三壳各有交代。planner（契约合成）不在 select 交点上，未排——诚实缺口，已在 plan 外注明，不硬塞。
2. **Placeholder 扫描**：Task 2 Step 2 的 `_diffs_for/_base_for` 是唯一待实现时补全点——已标红线（禁手拼 diffs，真签名实现时贴），非空话。
3. **类型一致**：`diagnose` 返回 dict 加 `deterministic: List[Dict]`；`run_round` 结果项加 `trial_det/trial_llm`——Task 2 Step 4 与 Step 1 的字段名一致。
