# Phase B3 · Hook 接线报告（2026-10-19）

> 一句话：**8-hook 协议从「只在测试里」变成「在基准 harness 里真跑」，一次成功求解 fire 8 次。**

---

## 一、目标（来自 Phase A 审计）

Phase A 的结论是"进化机制实现了但没激活"：

```
organs/hook.py            TEST     ← 8 协议零生产接线
organs/benchmark_fitness  SCRIPT   ← 无生产消费者
harness/loop.py           TEST     ← 进化主循环零生产调用
```

B3 的目标不是一次修完，而是**先给进化系统一个可验证的基质**：
把 SWE-bench 求解回合改造成"可挂 hook 的 harness"，
在沙箱里证明"hook + 策略 + 执行"这条环能转。

---

## 二、做了什么

### 2.1 新增 `src/dwc/harness/agent_harness.py`（约 300 行）

| 组件 | 作用 |
|------|------|
| `Policy` | frozen dataclass，**可进化的策略面**（localization / patch_format / max_rounds / context_chars / verifier / max_tokens） |
| `HarnessDeps` | 依赖注入面：LLM / 文件 / 编辑 / 语法 / 测试 / 验证，全部由调用方注入 |
| `AgentHarness` | 回合编排：在 8 个点 fire hook，按 Policy 迭代，失败回滚 |
| `HarnessResult` | 结构化结果（success / rounds / hooks_fired / last_tool_result / previous_error） |

**依赖方向**：本模块**不 import `scripts/`**。
基准相关的 I/O 全部通过 `HarnessDeps` 注入，保持 `src/dwc` 不反向依赖工具脚本。

### 2.2 新增 `src/dwc/organs/processors.py`（约 350 行）

五个 Processor，每个对应一个 hook，**构造参数就是 genotype 字段**：

| Processor | hook | 可变异参数 |
|-----------|------|-----------|
| `file_selector` | `step_start` | `mode`: keyword / llm_select |
| `prompt_builder` | `before_model` | `include_f2p` / `include_files` |
| `output_parser` | `after_model` | `mode`: json（Phase F 加 codeact/diff） |
| `action_guard` | `before_tool` | 结构校验（无参数） |
| `error_feeder` | `after_tool` | `mode`: full / truncated / assertion_only |

**G7 留痕**：JSON 解析失败不静默——`note_parse_miss()` 计数 + `parse_miss_last()` 可查。

### 2.3 `scripts/dwc_agent_patch.py` 降级为 CLI 薄壳（307 → 216 行）

- 只做 I/O 接线（checkout / pytest / LLM / 报告）
- 求解逻辑全部搬进 `AgentHarness`
- 新增 `--policy k=v,...` 参数（可外部切换策略）
- CLI 接口不变：`python dwc_agent_patch.py <instance_json>`

---

## 三、验证（真实执行，非声称）

### 3.1 8-hook 接线锁

`tests/test_r370_agent_harness.py`（5 条）：

```
test_all_eight_hooks_fire_once_on_success   PASS
test_read_only_hooks_reject_writes          PASS
test_failed_tests_roll_back_and_retry       PASS
test_unparseable_response_does_not_crash    PASS
test_policy_mutate_and_reject_unknown_field PASS
```

断言内容：
- 一次成功求解里 `set(fired) == set(HOOKS)`（8/8）
- 顺序：`task_start` 最先、`task_end` 最后；`step_start < before_model < after_model < before_tool < after_tool < step_end`
- 文件真的被改（`return 1` → `return 2`）
- 测试失败时文件回滚，8 个 hook 在每轮都 fire

### 3.2 真实 SWE-bench 回归（11143）

```
Instance: pytest-dev__pytest-11143
Policy: localization='keyword', patch_format='json', max_rounds=3,
        context_chars=1500, verifier=True
Repo: ...\dwc_agent_work\pytest-dev__pytest__6995257c
test_patch apply: True
Hooks fired: 8
Rounds: 1
F2P: {'passed': 1, 'failed': 0, 'total': 1, 'all_passed': True}
Verifier: PASS
Final: SUCCESS
```

**重构前后行为一致（1 轮 PASS），但现在是 8 个 hook 真 fire。**

### 3.3 激活状态变化

| 模块 | B3 前 | B3 后 |
|------|-------|-------|
| `organs/hook.py` | TEST | **SCRIPT** |
| `organs/processors.py` | — | **SCRIPT**（新增） |
| `harness/agent_harness.py` | — | **SCRIPT**（新增） |

全仓：97 模块 / 59 PRODUCTION / 21 SCRIPT / 16 TEST / 1 ORPHAN。

**说明**：`SCRIPT` 而非 `PRODUCTION` 是**正确的**——
B3 是沙箱接线，尚未接进常驻 agent。这正是 B1/B2 要做的。

---

## 四、诚实边界

1. **只激活了基准沙箱，没有激活生产**。
   常驻 agent 走 `DWC.run_term`，不经过 `AgentHarness`；
   `core.py:352` 的 `evolve` 分支仍然 `dispatched: False`。
2. **`patch_format` 只实现 `json`**。
   `codeact` / `diff` / `whole_file` 在 `output_parser` 里显式拒绝并留痕，
   不是静默降级。
3. **`localization=llm_select` 未在真实 instance 上验证**。
   只做了单元级行为（未产出时回退 keyword）。
4. **`Policy` 尚未接进 evolver**。
   现在可以手工 `--policy` 切换，但还没有"变异 → 评测 → 选择"的闭环（Phase D/E）。
5. **全量测试**：19 条旧红灯仍在（与 B3 无关，隔离运行同样失败）。

---

## 五、下一步

| 段 | 内容 | 判据 |
|----|------|------|
| **B1** | `core.py` 的 `evolve` 分支真调 `evolver.diagnose` | `dispatched: True` + evolver 收到真实失败签名 |
| **B2** | 常驻 agent 周期性触发 `Loop.round` | `var/` 出现进化产物 |
| **C** | `benchmark_fitness` 分级（6 级）+ evolver 消费 | 每个失败可归到具体一级 |
| **D** | `Policy` 接进 `candidates` | 两个 policy 产生不同行为 |
| **E** | A/B 证明 | 策略差异显著（非噪声） |

**建议顺序：C → D → E → B1 → B2。**
先在沙箱里把"分级 fitness + 策略选择"跑通（C/D/E），
再动生产分发（B1/B2）——这样生产改动有沙箱证据支撑，不是盲改。
