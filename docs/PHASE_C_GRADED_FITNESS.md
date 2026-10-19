# Phase C · 分级 fitness 与首次归因（2026-10-19）

> 一句话：**分级 fitness 把"二值失败"拆成了"落地失败 / 结果失败"，
> 第一次能说清 5 个 instance 各自卡在哪一级。**
> 结论是：机械层（解析/落地/语法）已基本修好，**瓶颈移到了"补丁对不对"**。

---

## 一、做了什么

### 1.1 `organs/benchmark_fitness.py` 新增分级 fitness

保留原 `fitness_signal()`（向后兼容），新增：

| 函数 | 作用 |
|------|------|
| `fitness_breakdown(records)` | 六元组 → 逐级通过率 + realization/outcome/scalar |
| `record_from_harness(report)` | 把 `dwc_agent_patch` 报告转成一条分级记录 |

六级定义：

| 级 | 含义 | 归因方向 |
|----|------|---------|
| `parse_ok` | LLM 产出可解析的 action | 交互层 |
| `apply_ok` | old_string 找到并对齐、替换落地 | 交互层 |
| `syntax_ok` | 修改后 `py_compile` 通过 | 交互层 |
| `f2p_ok` | 目标测试通过 | 策略层 |
| `p2p_ok` | 无回归 | 策略层 |
| `verifier_ok` | 独立验证器认可 | 策略层 |

合成公式：

```
realization = mean(parse, apply, syntax)     # 变异有没有落地
outcome     = mean(f2p, p2p, verifier)       # 问题有没有解决
scalar      = realization × outcome          # 落地是前提
```

**未测的级（None）不进分母** —— 未填 ≠ 测得零。

### 1.2 `scripts/dwc_graded_bench.py`（新增）

逐 instance 跑 `dwc_agent_patch` → 收集报告 → 汇总分级 fitness → 落 `var/graded_bench.json`。
支持 `--policy k=v,...`，A/B 结果按 policy 分文件保存。

---

## 二、首次测量（Policy A: context_chars=1500）

| instance | parse | apply | syntax | f2p | verifier | 归因 |
|----------|-------|-------|--------|-----|----------|------|
| 11143 | ✅ | ✅ | ✅ | ✅ | ✅ | 通过 |
| 5227 | ✅ | ✅ | ✅ | ✅ | ✅ | 通过 |
| 11148 | ✅ | ✅ | ✅ | ❌ | ❌ | **环境**（`ImportError: cannot import name 'importlib'`） |
| 5103 | ✅ | ✅ | ❌ | — | — | **语法**（IndentationError rewrite.py:739） |
| 5221 | ✅ | ✅ | ❌ | — | — | **语法**（IndentationError fixtures.py:57） |

汇总：`realization=0.867 / outcome=0.667 / scalar=0.578`，resolved 2/5 = 40%。

**这是第一次能说清：3 个失败里 2 个卡在语法层，1 个是环境问题——没有一个是"策略选错文件"。**

---

## 三、两个机械层修复（Phase C2）

### 3.1 缩进对齐（`reindent_to_match`）

**问题**：9 层匹配器里的 `_indentation_flexible` 能在缩进不同时找到 old_string，
但替换时把 `new_str` 原样插入 ⇒ 基准缩进错位 ⇒ IndentationError。

**修法**：替换前把 `new_str` 的基准缩进对齐到 `actual` 的基准缩进（空行保留、相对缩进保留）。

**验证**：`tests/test_r372_reindent.py` 6 条（加缩进/减缩进/同缩进/空行/端到端/失败路径）。

### 3.2 行对齐校验（`_aligned`）

**问题**：修完缩进后，5103/5221 变成另一类语法错误：

```
setattr(node, name, new) enumerate(field):     ← 5103
)pytest.python.Class,                          ← 5221
```

根因：LLM 给的是**行内片段**（如 `for name, new in`），`search in content` 命中，
替换后后半行残留 ⇒ invalid syntax。

**修法**：
1. `apply_replacement` 只接受**整行对齐**的匹配（允许跳过行首缩进，拒绝行内片段）
2. `read_file_content` 按行边界截断（不在行中间切，避免 LLM 抄到半行）
3. prompt 加硬约束："old_string must be a WHOLE-LINE block"

**验证**：`test_inline_fragment_is_rejected` + `test_whole_line_block_still_applies`。

### 3.3 修复后的变化

| instance | 修复前 | 修复后 |
|----------|--------|--------|
| 5103 | syntax=False（IndentationError） | **syntax=True, f2p=False** ← 失败从机械层移到结果层 |
| 5221 | syntax=False（invalid syntax） | **apply=False**（片段被拒，3 轮都没给整行） |

**5103 的失败层级下降了一级**，这是修复生效的直接证据。
**5221 仍卡在 apply**：模型没有根据错误反馈改成整行，是模型能力问题，不是机械问题。

---

## 四、A/B 实验（Policy A vs Policy B: context_chars=8000）

| instance | A (1500) | B (8000) |
|----------|----------|----------|
| 11143 | 全过 | 全过 |
| 5227 | 全过 | 全过 |
| 11148 | real=1.0 / out=0.0 | real=1.0 / out=0.0 |
| 5103 | real=1.0 / out=0.0 | real=1.0 / out=0.0 |
| 5221 | real=0.333 | real=0.333 |
| **汇总** | real=0.867, out=0.667, scalar=0.578 | real=0.867, out=0.5, scalar=0.433 |

### 4.1 结论：没有稳定差异

在**共同测量集**（11148 / 5227 / 11143，三个都测到 f2p 的实例）上：
A 和 B 都是 2/3 = 0.667，**完全相同**。

B 的 `outcome` 显示 0.5 是因为 5103 从"未测"变成了"测得失败"——
**分母变大导致比率下降，不是性能变差**。

### 4.2 这次实验暴露了度量本身的一个缺陷

`scalar` 在"测量集随策略变化"时**不可比**：

```
Policy A: 5103 syntax 失败 ⇒ f2p 未测 ⇒ outcome 分母 3
Policy B: 5103 syntax 通过 ⇒ f2p 测得失败 ⇒ outcome 分母 4
⇒ outcome 从 2/3 变 2/4，看起来变差，实际是测得更全
```

**修法（待做）**：策略比较时用**共同测量集**，或同时报
`outcome_measured`（当前口径）与 `outcome_on_common_set`（可比口径）。

### 4.3 另一个诚实发现：单次运行不可比

5221 单独跑 `context_chars=8000` 时 realization=1.0，
批量跑同样参数时 realization=0.333 —— **LLM 采样噪声**。

⇒ 单次对比不能作为策略优劣的证据；E 阶段必须**重复 ≥2 次**。

---

## 五、当前的真实瓶颈

| 层 | 状态 | 证据 |
|----|------|------|
| 交互层（parse/apply/syntax） | **基本修好** | realization 0.867；5103 已从 syntax 失败转为 f2p 失败 |
| 策略层（选文件） | 未验证 | 所有 instance 都选对了文件（keyword 匹配足够） |
| **结果层（补丁对不对）** | **瓶颈** | 5103/5221/11148 的 f2p 都失败 |
| 环境层 | 1 个 instance 坏 | 11148 的 `ImportError` 与 agent 无关 |

**结论：`localization` 和 `context_chars` 都不是瓶颈。
真正卡住的是"模型生成的补丁是否正确"——这需要更强的模型或更好的交互（CodeAct）。**

---

## 六、诚实边界

1. **样本只有 5 个 instance，1 个还是环境坏的**——有效样本 4 个，不足以做统计结论。
2. **A/B 只跑了 1 次**，且已证实单次结果有采样噪声。
3. **`p2p_ok` 从未测量**——harness 当前只跑 F2P，所以 outcome 实际是 f2p+verifier 两项平均。
4. **11148 的失败是环境问题**（repo checkout 的 `_pytest._py.importlib` 导入失败），
   不应算作 agent 能力。
5. **`scalar` 在测量集变化时不可比**（见 4.2）。

---

## 七、下一步建议

| 优先级 | 动作 | 理由 |
|--------|------|------|
| **P0** | 修 `scalar` 的可比口径（共同测量集） | 否则后续所有 A/B 都不可信 |
| **P0** | 补 P2P 测量（`run_tests` 跑 p2p 或标 None 并在 outcome 里排除） | outcome 现在只有 2 项 |
| **P1** | 换更强模型跑同一 5 instance（重复 2 次） | 瓶颈在补丁质量，不在策略 |
| **P1** | 修 11148 的环境（`_pytest._py` 导入）或从评测集剔除 | 环境坏会污染结论 |
| **P2** | `localization=llm_select` A/B | 目前 keyword 全对，预期无增益 |
| **P3** | CodeAct（Phase F） | 需要更强模型才值得做 |

**不建议现在做 Phase F（CodeAct）**：机械层已修好，
瓶颈是模型生成补丁的质量，换交互格式不会自动提升质量。
