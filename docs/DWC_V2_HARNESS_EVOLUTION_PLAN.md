# DWC v2.0 · 成本感知的 Harness 自进化 —— 版本开发计划

> **状态**：规划中（等论文池攒够后统一开工）
> **上游**：R438 十九项落地（v1 完成"能不能自进化"）
> **本版本要回答**：**进化得值不值**
> **首个来源论文**：HarnessPro（arXiv 2610.26770）· 详见 `docs/HARNESSPRO_DEEP_REPORT.html`

---

## 0. 一句话

v1 让 DWC 学会了自己改自己；v2 要让 DWC 学会**算账**——把「每次任务花多少钱」变成与「通过率」并列的一等目标，从而在**不掉分**的前提下持续降本。

---

## 1. 版本边界

### 1.1 做

| # | 能力 | 一句话验收 |
|---|---|---|
| V2-1 | 成本可观测 | 每一次 LLM 调用都有 token 记账，可按任务/按轮汇总出美元成本 |
| V2-2 | 输出可回溯 | 工具输出截断后，原文落盘且模型可按路径定向回读 |
| V2-3 | 预算可约束 | 每任务有 economy→strict→finalize 三段预算，finalize 后硬阻断 |
| V2-4 | 双目标进化 | fitness 同时含 pass_rate 与 cost，任一退化即 reject |
| V2-5 | 按任务选档 | 按任务特征选 profile（推理力度 + 预算档），而非全局一个值 |
| V2-6 | 三档产物 | 一轮进化产出 lite / medium / heavy 三套可切换策略 |

### 1.2 不做（红线）

| 不做 | 理由 |
|---|---|
| label-free（放弃 ground truth） | DWC 有真实评测池（池 A 53/54 = 98.1%），主动放弃真值是倒退 |
| 多候选并行（3 计划 × G=3 rollout） | 一轮 90 次调用会吃光日预算（96/80） |
| 全 harness 重写 | 19 个对象已按维度隔离，全放开会破坏结构完整性 |
| CoP 当唯一 fitness | 成功数为 0 时发散；DWC 失败样本少，噪声爆炸 |
| 引入新的重型依赖 | 预算/压缩/路由全部用 stdlib + 现有依赖实现 |

---

## 2. 全局约束（继承 R438，全部生效）

1. **配置必填无默认**：新开关不许 `get(..., False)` 兜底，缺键即报错。
2. **开关变更同轮改测试留痕**：改一个开关，必须同轮补/改测试。
3. **降级与成功必须可区分**：无 usage 就记 `None`，不许猜、不许记 0。
4. **基础设施故障与模型失败必须可区分**：502/超时不进成本分母，但要单独记。
5. **生产数据文件容忍坏行 + 原子写入**。
6. **测试不许污染生产状态**：pid/state/ledger 一律"读旧→写→finally 还原"。
7. **不许写恒真放水断言**（`... or True`）；`tests/test_no_watering.py` 会抓。
8. **注释即语料**：`src/` `scripts/` `docs/` `tests/` 里不许出现不存在的文件名/标识符。
9. **同一件事两种写法必须有归一化入口**；同一份规则不许写两遍。
10. **改文件后行为没变 ⇒ 先查 `__pycache__` 与 kernel 持久化**。
11. **单轮全池不可引用**，对外只报两轮均值 + 极差。
12. **落地定义四项**：有产物文件 + 有消费者读它 + 有试验能判好坏 + 能回滚。

### 2.1 本版本新增约束

13. **成本必须可归因**：每笔成本要能回答"哪个任务、哪一轮、哪个环节"。
14. **截断不许丢信息**：任何截断都必须留下可回读的原文路径。
15. **预算提醒不许改前缀**：只允许追加到 tool result，不许重写 system prompt（否则 cache 失效，越省越贵）。
16. **成本不进分母**：失败/超时任务的成本单独统计，不与成功任务混算均值。

---

## 3. 阶段划分

```
P0-a 成本记账 ──┐
                ├─→ P1-b 双目标 fitness ─→ P2 任务路由 ─→ P3 三档 Pareto
P0-b 输出可回溯 ─┘         ↑
                    P1-a 三段预算
```

依赖关系：**P0-a 是一切的前提**（没有成本数据，P1-b/P2/P3 都无从比较）；P1-a 与 P1-b 可并行，但 P1-b 的验收依赖 P1-a 的成本数据。

---

## 4. 阶段详规

### P0-a · 成本记账（R439）

**目标**：让每一次 LLM 调用都留下 token 与美元成本。

**Files**
- Modify: `src/dwc/llm/client.py`（`LLMResult` 已有 `meta` 字段，直接复用）
- Create: `src/dwc/llm/cost.py`（价目表 + 折算）
- Modify: `src/dwc/llm/task_exec.py`（把 usage 写进任务结果）
- Create: `tests/test_r439_cost.py`
- Modify: `config/llm.json`（新增 `pricing` 段，**必填**）

**接口**

```python
# src/dwc/llm/cost.py
@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int = 0

def parse_usage(data: dict) -> Optional[Usage]:
    """从 API 响应解析 usage。缺失/畸形 ⇒ None（不许猜 0）。"""

def cost_usd(model: str, u: Usage, pricing: dict) -> Optional[float]:
    """按价目折算。model 不在价目表 ⇒ None（不许用别的模型价格兜底）。"""
```

**验收**
- 跑一轮池 A，`var/task_scores.jsonl` 每行含 `tokens` 与 `cost_usd`。
- 无 usage 的响应 ⇒ 两字段为 `null`，且 `usage_missing: true`。
- 价目缺失的模型 ⇒ `cost_usd: null`，但 `tokens` 照记。

**测试**
- `test_parse_usage_missing_returns_none`
- `test_parse_usage_cached_tokens`
- `test_cost_unknown_model_returns_none_not_zero`
- `test_llmresult_meta_carries_usage`

---

### P0-b · 输出可回溯（R440）

**目标**：截断但可回读。

**Files**
- Modify: `src/dwc/llm/task_exec.py`（`_cap_answer` / 工具返回处）
- Create: `src/dwc/llm/tool_raw.py`（落盘 + 读回）
- Create: `tests/test_r440_tool_raw.py`

**行为**
```
if len(text) > output_max_chars:
    path = var/tool_raw/<sha1[:16]>.json
    写原文（原子写）
    返回 head(N) + "\n…[truncated %d chars; full: %s]\n" + tail(M)
```

**验收**
- 超限输出：模型看到的字符串含原文路径；该路径可读回完整原文。
- 未超限：不落盘（不许把每次输出都写成文件）。
- 同一内容重复出现：路径相同（sha1 去重），不重复写。

**测试**
- `test_truncate_keeps_head_and_tail`
- `test_truncate_writes_raw_and_path_readable`
- `test_short_output_not_persisted`
- `test_same_content_dedup_path`

---

### P1-a · 三段式预算（R441）

**目标**：把"无限探索"变成"有节奏地收敛"。

**Files**
- Modify: `src/dwc/llm/task_exec.py`（原生工具循环）
- Modify: `src/dwc/organs/evo_targets.py`（新增 `tool_budget` 目标）
- Create: `tests/test_r441_budget.py`

**三档语义**

| 阶段 | 触发 | 行为 |
|---|---|---|
| economy | 计数 ≥ economy_after | 追加提醒："批量独立检查、别重复读、别叙述过程" |
| strict | 计数 ≥ strict_after，每 N 次重复 | 追加提醒："停止发散，只查与当前失败直接相关的证据" |
| finalize | 计数 > finalize_after | **拒绝新工具调用**，要求基于现有证据给最终答案 |

**配置（`config/evo_targets` 白名单内）**
```json
{"tool_budget": {"economy_after": 18, "strict_after": 38,
                 "finalize_after": 60, "strict_reminder_every": 8}}
```

**硬性**
- 提醒只能追加到**工具结果**，不许改 system prompt。
- finalize 之后必须仍允许"给出最终答案"（不是把模型锁死）。

**验收**
- 池 A 通过率 ≥ 98.1%（不退化）。
- 平均工具调用数下降 ≥ 20%。
- 关掉开关（配置缺失即报错，不静默关）后行为回到基线。

---

### P1-b · 双目标 fitness（R442）

**目标**：进化不再只看"过不过"，还要看"贵不贵"。

**Files**
- Modify: `src/dwc/organs/evolver.py`（fitness 计算）
- Modify: `scripts/dwc_evo_round.py`（新增门 `no_cost_regression`）
- Modify: `config/evolution.yaml`（新增 `cost_weight`，必填）
- Create: `tests/test_r442_dual_objective.py`

**fitness**
```python
scalar = realization * outcome          # 现有
scalar = scalar * (1 - cost_weight * normalized_cost_delta)   # 新增
```

**新门**

| 门 | 判据 |
|---|---|
| `cost_measured` | 本轮所有候选都有 `cost_usd`，否则 fail-closed |
| `no_cost_regression` | `cost(candidate) ≤ cost(baseline) * (1 + tolerance)` |

**验收**
- 构造"分数不变但成本翻倍"的候选 ⇒ 必须 reject。
- 构造"分数 +2pp、成本 +5%"（在 tolerance 内）⇒ 可 accept。
- 台账每条同时含 `score` 与 `cost_usd`。

---

### P2 · 按任务选档（R443–R444）

**目标**：简单题别用牛刀，难题别省子弹。

**Files**
- Create: `src/dwc/llm/profile.py`（profile 定义 + 选择器）
- Create: `src/dwc/llm/profile_rules.py`（规则优先，无 LLM 依赖）
- Modify: `src/dwc/llm/task_exec.py`（按 profile 取 `reasoning_effort` 与预算）
- Create: `tests/test_r443_profile.py`

**五档（借 HarnessPro，但阈值由 DWC 实测确定）**

| profile | 推理力度 | economy | strict | finalize |
|---|---|---|---|---|
| compact | none | 4 | 8 | 14 |
| lean | none | 10 | 22 | 36 |
| standard | none | 18 | 38 | 60 |
| deep | low | 20 | 42 | 68 |
| research | low | 16 | 36 | 60 |

> 注意：DWC 的 R411 实测「推理档越高越差」，所以这里**不照抄论文的 high**，而是以 `none` 为基线，只在 deep/research 上试 `low`，并由 A/B 决定。

**选择器**
- 第一层：**规则**（任务长度、是否含代码块、是否需要多文件、是否有明确 oracle）→ 覆盖 ≥ 80% 流量。
- 第二层：规则无法判定 ⇒ 默认 `standard`（**不许**为了"智能"引入 LLM 分类器作为默认路径）。

**验收**
- 规则覆盖率 ≥ 80%（统计日志）。
- 池 A 不退化。
- 单任务平均成本下降 ≥ 15%（相对 P1 基线）。

---

### P3 · 三档 Pareto（R445+）

**目标**：一轮进化产出三套策略，部署时按预算选。

**Files**
- Create: `src/dwc/organs/pareto.py`（归一化 + 加权平方距离）
- Modify: `scripts/dwc_evo_round.py`（产出三档而非单条）
- Modify: `config/evolution.yaml`（`modes: {lite: [1,2], medium: [1,1], heavy: [2,1]}`，必填）
- Create: `tests/test_r445_pareto.py`

**选择**
```python
d_perf = (P_max - P) / (P_max - P_min)
d_cost = (C - C_min) / (C_max - C_min)
J_m    = a_m * d_perf**2 + b_m * d_cost**2
pick   = argmin(J_m)
```

**验收**
- 三档产物的 pass_rate 与 cost 满足 `lite.cost ≤ medium.cost ≤ heavy.cost`。
- 三档都过 `PR ≥ PR(h0)` 地板。
- 可单独启用某一档（不必三档一起上）。

---

## 5. 论文接入协议（本版本的核心机制）

既然要"攒几篇论文一起动手"，每篇论文必须走同一条流水线，否则会变成拍脑袋堆功能。

### 5.1 七步吸收

| 步 | 动作 | 产物 |
|---|---|---|
| 1 | 全文精读（正文 + 附录口径） | 研读报告 HTML |
| 2 | 提取机制清单（一条机制一行） | 机制表 |
| 3 | 映射到 DWC 19 对象 | 映射表（命中/未命中） |
| 4 | 判定可复现性（仓库有没有代码） | 可复现 / 仅产物 / 不可复现 |
| 5 | 定阶段（P0–P3 或新增 P4） | 阶段归属 |
| 6 | 写验收（怎么算做成） | 验收条目 |
| 7 | 登记台账 | 本文件 §5.2 |

### 5.2 论文台账

| # | 论文 | 年份 | 核心机制 | 归属阶段 | 采纳 | 理由 |
|---|---|---|---|---|---|---|
| 1 | HarnessPro (2610.26770) | 2026 | 成本作为一等目标 | P0-a / P1-b | ✅ | DWC 零成本度量，缺口最大 |
| 1 | 同上 | | 三段式工具预算 | P1-a | ✅ | 最可直接抄，纯 stdlib |
| 1 | 同上 | | 输出压缩 + 原文落盘 | P0-b | ✅ | DWC 截断即丢信息 |
| 1 | 同上 | | profile 路由 | P2 | ✅ | 但阈值按 DWC 实测重定 |
| 1 | 同上 | | 三档 Pareto | P3 | ✅ | 需先有成本指标 |
| 1 | 同上 | | 多候选并行 | — | ❌ | 日预算吃不下 |
| 1 | 同上 | | label-free | — | ❌ | DWC 有真值，放弃是倒退 |
| 1 | 同上 | | LLM 当裁判 | — | ❌ | 论文自证失败召回仅 41.7% |
| 2 | （待填） | | | | | |

### 5.3 判定规则

一篇论文的机制要被采纳，必须同时满足：
1. **缺口真实**：DWC 当前确实没有，且不是"有但没接"。
2. **可落地**：有明确落点文件，不需要引入重型依赖。
3. **可验证**：能写出一个会失败的测试。
4. **不破坏结构**：不要求放开 19 对象的隔离边界。

任一不满足 ⇒ 记入台账"拒绝"，并写明理由（**不许静默丢弃**）。

---

## 6. 版本 KPI

| 指标 | 基线（v1 / R438） | v2 目标 | 测法 |
|---|---|---|---|
| 成本可见率 | 0% | **100%** | 有 usage 的调用 / 总调用 |
| 池 A 通过率 | 98.1%（53/54） | **≥ 98.1%** | 两轮均值 |
| 单任务平均成本 | 未知 | **−15%** | 相对 P1 基线 |
| 工具调用数 | 未知 | **−20%** | 平均每任务 |
| 截断可回溯率 | 0% | **100%** | 截断处含可读路径 |
| 三档可切换 | 无 | **有** | 三档各自可单独启用 |
| 进化台账双指标 | 只有 score | **score + cost** | 每条台账 |

---

## 7. 风险与对策

| 风险 | 后果 | 对策 |
|---|---|---|
| 成本噪声大（单次波动 ±20%） | 误判"变贵了" | 用两轮均值 + 极差；单轮结论不引用 |
| 预算过紧导致掉分 | 通过率跌破地板 | `PR ≥ PR(h0)` 硬地板；finalize 后仍允许作答 |
| 分类器误判 | 难题被分到 compact | 规则优先；无法判定 ⇒ 默认 standard |
| 成本记账引入延迟 | 每轮多一次解析 | 纯本地解析，无额外网络调用 |
| 原文落盘撑爆磁盘 | 磁盘满 | sha1 去重 + 单文件上限 + 定期清理（保留 7 天） |
| 三档产物维护成本 | 配置爆炸 | 三档共用同一份对象定义，只差参数 |

---

## 8. 交付物清单

| 阶段 | 产物 | 验收证据 |
|---|---|---|
| P0-a | `src/dwc/llm/cost.py` + 测试 | 池 A 跑完，每行有 tokens/cost |
| P0-b | `src/dwc/llm/tool_raw.py` + 测试 | 截断路径可读回 |
| P1-a | 预算三档 + 配置目标 | 工具调用数下降 ≥20%，池 A 不退化 |
| P1-b | 双目标 fitness + 新门 | "分数不变成本翻倍"被 reject |
| P2 | `profile.py` + 规则选择器 | 规则覆盖 ≥80%，成本 −15% |
| P3 | `pareto.py` + 三档产出 | 三档成本单调 + 都过地板 |
| 全程 | 台账 + 文档 | 每阶段一份 HTML 验收记录 |

---

## 9. 开工条件

本计划**不立即开工**，等满足以下条件后统一执行：

1. 论文池 ≥ 3 篇（当前 1 篇：HarnessPro）。
2. 每篇都已走完 §5.1 七步，台账登记完毕。
3. 机制之间没有冲突（若有，先在本文件"冲突裁决"节写明二选一及理由）。
4. 用户确认版本范围（尤其 P2/P3 是否纳入本版本）。

### 冲突裁决（预留）

| 冲突 | 选项 | 裁决 | 理由 |
|---|---|---|---|
| （待填） | | | |

---

## 10. 与既有路线的关系

| 既有 | 关系 |
|---|---|
| R438 十九对象 | v2 不改对象划分，只在既有对象上增加"成本"维度 |
| `auto_apply_max_per_round: 1` | P1-b 之后仍然保留，避免一轮落太多 |
| `prompt_evolve_weekday: 6` | 不受影响 |
| 热力学智能 / I_δ | 成本数据是 I_δ 量化的基础输入，P0-a 完成后才可能真正进 fitness |
| 进化双锚（thermo / 北极星） | v2 不改锚，只给 thermo 锚提供成本信号 |

---

*本计划为版本级规划，各阶段开工前需再产出对应的 R 轮实现计划（含逐任务 TDD 步骤）。*
