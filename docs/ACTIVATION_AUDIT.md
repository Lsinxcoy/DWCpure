# DWC 激活审计报告（Phase A · R369 · 2026-10-19）

> 一句话：**95 个模块里 36 个（37.9%）不在常驻 agent 的执行路径上**，
> 其中包含整个进化循环家族。这不是"机制缺失"，是"机制未激活"。

---

## 一、为什么要做这个审计

`gate.py` 的 K34 判据长这样（`scripts/gate.py:757-765`）：

```python
_src = open(_bf, encoding="utf-8").read()
if "def fitness_signal" not in _src:
    violations.append({... "K34 fitness_signal 缺失"})
```

它检查的是"**源码里有没有这行字**"，不是"**有没有人调用它**"。

后果：**"1,563 项测试全绿" 和 "0% 生产接线" 可以同时成立。**
单测直接 import 模块，绕过了生产路径，所以测试永远发现不了孤儿。

本审计补的就是这个维度：**从生产入口出发的可达性**。

---

## 二、方法

`scripts/activation_audit.py`（静态 AST 分析，零副作用）：

1. 收集 `src/dwc/**/*.py` 全部模块（95 个）
2. AST 解析每个文件的 `import` / `from ... import`（含相对导入 `from ..x import y` 的层级解析）
3. 从**生产入口**做 BFS 可达性
4. 四态分类

### 生产入口白名单

```python
PRODUCTION_ENTRIES = [
    "scripts/dwc_agent.py",        # 常驻 agent 本体（每轮 d.run_term）
    "src/dwc/harness/run_term.py", # 主循环（TermRunner 六层链）
    "src/dwc/core.py",             # 装配核心（DWC）
]
```

### 四态

| 状态 | 含义 |
|------|------|
| `PRODUCTION` | 从上述入口可达（真生产链） |
| `SCRIPT` | 仅从工具脚本可达（批处理 / CLI，非常驻路径） |
| `TEST` | 仅被 `tests/` 引用（单测绿 ≠ 生产接线） |
| `ORPHAN` | 无人引用 |

### 复现命令

```bash
python scripts/activation_audit.py          # 只打非生产链
python scripts/activation_audit.py --all    # 全表
```

---

## 三、结果

```
modules: 95 | PRODUCTION 59 | SCRIPT 18 | TEST 17 | ORPHAN 1
非生产链: 36 / 95 = 37.9%
```

### 进化器官的实际状态

| 模块 | 状态 | 被谁引用 | 判读 |
|------|------|---------|------|
| `organs/evolver.py` | **PRODUCTION** | `core.py` | 实例化 ✅，但见下方铁证 |
| `organs/candidates.py` | **SCRIPT** | `e2e_loop.py`, `real_llm_candidate.py` | 进化候选生成不在生产链 |
| `organs/applier.py` | **SCRIPT** | `harness/loop.py`（本身是 TEST）, `e2e_loop.py` | 落地器不在生产链 |
| `organs/benchmark_fitness.py` | **SCRIPT** | `dwc_benchmark_calibrate.py` | fitness 信号无生产消费者 |
| `organs/hook.py` | **TEST** | `test_r145_hook.py`, `test_r146_dimension.py` | 8-hook 协议零生产接线 |
| `organs/metric_loop.py` | **TEST** | `harness/loop.py`（TEST） | 指标回路不在生产链 |
| `organs/metrics.py` | **TEST** | `harness/loop.py`（TEST） | 同上 |
| `organs/revision.py` | **TEST** | `test_r258_revision.py` | 修订器零生产接线 |
| `organs/dimension.py` | **TEST** | 两个测试 | 9 维分类零生产接线 |
| `harness/loop.py` | **TEST** | 5 个测试文件 | **进化主循环零生产调用** |
| `harness/pipeline.py` | **SCRIPT** | `loop.py`, `e2e_loop.py` | 流水线不在生产链 |
| `harness/landing.py` | **SCRIPT** | `loop.py`, `pipeline.py` | 落地不在生产链 |
| `harness/adoption.py` | **SCRIPT** | `pipeline.py` | 采纳不在生产链 |
| `harness/exploration.py` | **SCRIPT** | `e2e_loop.py` | 探索不在生产链 |
| `harness/splitfeed.py` | **SCRIPT** | `loop.py`, `e2e_loop.py` | 双 split 不在生产链 |
| `harness/consume_points.py` | **TEST** | `trajectory.py`（TEST） | 消费点登记不在生产链 |
| `harness/attestation.py` | **TEST** | 1 个测试 | 存证零生产接线 |
| `harness/coupling.py` | **TEST** | 2 个测试 | 耦合检查零生产接线 |

**执行器官（run_term / judge / iwm / world_model / el_sched / actor）全部 PRODUCTION。
进化器官（loop / candidates / applier / hook / metric_loop）几乎全部非生产。**

---

## 四、三条铁证（代码自陈，不是推断）

### 铁证 1：`evolve` 分支被硬编码为 `dispatched: False`

`src/dwc/core.py:352-355`：

```python
if action == "evolve":
    dispatch = {"kind": "evolve", "dispatched": False,
                "why": "not_dispatched: 器官已实现"
                       "(evolver.Evolver) 但 step 分发未接线"
                       "（缺失败签名输入链）— R141 如实修正"}
```

**代码自己写着"器官已实现但 step 分发未接线"。**

### 铁证 2：TermRunner 不持有 evolver

`src/dwc/harness/run_term.py:662-665`：

```
★ TermRunner 不持有 evolver 实例（它只编排六层链）
  ⇒ π 的填值语义 = **角色已实现**（盘点面, 不是运行时接线面）;
  U 的 select_winner(evolver.py L449) 已实现但**本盘点不接**
```

**五元盘点里的 π（进化策略）只是"角色名"，不是运行中的组件。**

### 铁证 3：`DWC.step()` 在 production 零调用

```
$ grep -rnF ".step(" src/dwc scripts/dwc_agent.py | grep -v "def step"
src/dwc/core.py:653:  new_obs = sim.step(observed, {pick})   # 世界模型模拟，不是 DWC.step
```

常驻 agent 走的是 `dwc_agent.py:688 → d.run_term(task)`，不是 `d.step()`。
而 `remember / dream / evolve / learn / maintain` 的动作分发**只在 `DWC.step()` 里**。

⇒ **动作分发层（含 dream 与 evolve）在常驻 agent 路径上完全不可达。**

---

## 五、生产链的真实形状

```
dwc_agent.py
  └─ DWC.run_term(task)
       └─ TermRunner.run_term(task)          ← 六层链
            ├─ _step() × N                    ← 记忆写 → 读回校验
            ├─ judge                          ← 判分
            ├─ iwm.drift                      ← 漂移
            └─ Quintet 盘点                    ← π/V/m/U/ρ（π 只是字符串）

✗ Loop.round            （进化循环，TEST only）
✗ evolver.diagnose      （失败签名 → 提案，未接线）
✗ candidates            （候选生成，SCRIPT only）
✗ applier               （落地，SCRIPT only）
✗ hook                  （8 协议，TEST only）
✗ benchmark_fitness     （外部 fitness，SCRIPT only）
✗ DWC.step              （动作分发，production 零调用）
```

**结论：常驻 agent 会"执行任务 + 写记忆 + 判分"，但不会"进化"。**

---

## 六、对原方案的影响

原 Phase B 计划是"把 hook 接进 `scripts/dwc_agent_patch.py`"。
审计显示这个计划**方向正确但不够**——它只给基准 agent 装了 hook，
常驻 agent 的进化链仍然是断的。

修订后的 Phase B 应拆成两段：

| 段 | 内容 | 风险 | 说明 |
|----|------|------|------|
| **B1** | `core.py` 的 `evolve` 分支真调 `evolver.diagnose` | 低（3 行） | 先把"分发未接线"这条铁证消掉 |
| **B2** | `dwc_agent.py` 周期性触发 `Loop.round`（或 `DWC.step`） | 中 | 让进化循环真跑；需灰度 + 回滚开关 |
| **B3** | hook 接进基准 harness | 低（沙箱） | 原计划，作为"进化在沙箱里可证"的试验田 |

**推荐顺序：B3 → B1 → B2。**
先在沙箱里证明"hook + fitness + 选择"这条环能转，
再动生产分发，最后把 Loop 接进常驻 agent。

---

## 七、已有红灯（与本轮无关）

全量 pytest：**2,194 passed / 19 failed**。
失败全部集中在旧轮次文件，且**在隔离运行时同样失败**（已用
`pytest tests/test_r309_resume.py tests/test_r310_budget.py tests/test_r305_wire.py` 单跑验证）：

```
test_b1_deep.py (2)          test_gate_n_a.py (4)
test_b4_pool.py (1)          test_r208_agent.py (1)
test_c3_provenance.py (1)    test_r243_input.py (1)
test_d2_envelope.py (1)      test_r290_p1_trial_score.py (1)
test_r305_wire.py (1)        test_r309_resume.py (3)
test_r310_budget.py (3)
```

本轮只新增 `scripts/activation_audit.py` + `tests/test_r369_activation_audit.py`，
未改任何 `src/dwc/**`，与上述红灯无因果关系。

gate 8/8 全通过。

---

## 八、交付物

| 文件 | 作用 |
|------|------|
| `scripts/activation_audit.py` | 激活审计工具（AST 可达性，四态分类） |
| `tests/test_r369_activation_audit.py` | 分类逻辑行为锁（4 条） |
| `var/activation_audit.json` | 机器可读审计结果（95 模块全量） |
| `docs/ACTIVATION_AUDIT.md` | 本报告 |

---

## 九、下一步

Phase B 按修订顺序执行：**B3（hook 接沙箱）→ B1（evolve 真分发）→ B2（Loop 接生产）**。

判据：
- B3：8 个 hook 全部 fire，11143 回归 PASS
- B1：`dispatched: True` 且 evolver 收到真实失败签名
- B2：常驻 agent 连续 N 轮后，`var/` 出现进化产物（提案/落地记录）
