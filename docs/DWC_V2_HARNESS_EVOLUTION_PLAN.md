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
                ├─→ P1-b 双目标 fitness ─→ P1-c 对比探针 ─→ P2 任务选档 ─→ P3 三档 Pareto ─→ P4 改进库
P0-b 输出可回溯 ─┘         ↑
                    P1-a 三段预算
```

依赖关系：**P0-a 是一切的前提**（没有成本数据，P1-b/P2/P3 都无从比较）；P1-a 与 P1-b 可并行，但 P1-b 的验收依赖 P1-a 的成本数据；**P1-c 必须先纠正"继承式起草"**（见 §4 P1-c），否则 P4 的库没有意义。

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
- **`cached_tokens` 必须单独记并单独计价**（缓存价与未缓存价可差一个数量级；HarnessPro 与 Cache Engineering 两篇独立论文都用了三档计价）。

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
- **前缀稳定性必须可测**：连续两轮请求的公共前缀长度写入 `var/prefix_stability.jsonl`。
  现状（`task_exec.py:2333` 每轮重建整串 prompt）预期公共前缀极短；改造目标是"稳定前缀在前、易变内容在后"。
  依据：Cache Engineering 实测 trim 反而让成本涨到 **1.85×**，根因就是改前缀触发 re-prefill。

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

### P1-c · 对比式探针 + 纠正继承式起草（R443）

**来源**：Harness²（arXiv 2610.14224）§2.2.1 + §2.3 + Figure 7。

**目标**：把"只比分数"升级为"比行为"，并纠正 DWC 现在做反的一件事。

**两个问题**

| # | 现状 | 论文证据 | 要改成 |
|---|---|---|---|
| 1 | trial 只产出 `success/in_score/baseline_in`，**不比轨迹** | 对比式 Propose-Probe-Compose | 产出结构化行为对比：哪些失败模式消失了 / 未变 / 新增 |
| 2 | `Mutator.propose` 把 `p.code` 当下轮**起草起点** = 继承 | 直接编辑不看参考/探针/库 ⇒ WB-code 73.4→**63.2**（−10.2）、WB-web 69.9→**65.0**（−4.9） | 下轮从基线起，只从库里按 cue **选择性**取用 |

> 这是本版本最重要的一条修正：**DWC 现在的进化方式，正是论文实测会掉分的那种方式。**

**Files**
- Modify: `scripts/dwc_evo_round.py`（trial 增加 `contrast` 字段）
- Modify: `src/dwc/organs/evolver.py`（`propose` 不再默认继承 `p.code`）
- Create: `src/dwc/organs/contrast.py`（行为对比提取）
- Create: `tests/test_r443_contrast.py`

**对比结构**

```python
@dataclass
class Contrast:
    disappeared: list[str]   # 参考里有、候选里没有的失败模式
    persisted:   list[str]   # 两边都有
    introduced:  list[str]   # 候选新增的
    evidence:    dict        # 每条判定的观测依据
```

**验收**
- 同一任务跑参考与候选，产出非空 `Contrast`；三条列表之和 = 失败模式总数。
- `propose` 在无库时**不得**读上一轮的 `p.code`（测试用哨兵值断言）。
- 引入新失败模式的候选，即使分数略高也必须进 `introduced` 并被下游门看到。

---

### P2 · 按任务选档（R444–R445）

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

**上下文策略三元组（来自 Cache Engineering）**

DWC 的 `context_mgmt` 现在只有一种硬编码形态（留最近 2 轮 + 摘要）。借论文的三段分解，让它变成可进化的策略对象：

| 组件 | 含义 | DWC 可选项 |
|---|---|---|
| `trigger` | 何时压缩 | 轮数 / token 数 / 连续失败数 |
| `selector` | 压哪些 | 旧工具响应 / 证伪轮 / 重复读同一文件的轮 |
| `reposition` | 何时重整 | 压缩后是否重建摘要、是否重排 |

**验收**
- 规则覆盖率 ≥ 80%（统计日志）。
- 池 A 不退化。
- 单任务平均成本下降 ≥ 15%（相对 P1 基线）。
- 三元组能独立开关，且关掉后行为回到 P1 基线（可回滚）。

---

### P3 · 三档 Pareto（R446+）

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

### P4 · 改进库：让"改进器"自己进化（R447+）

**来源**：Harness²（arXiv 2610.14224）§2.3 + `core/library.py`。

**目标**：把 R438 #14 的 `meta_evolution`（只调一个旋钮）升级为**带经验的改进器**。

**核心结构（照抄 `library.py` 的形态，不抄它的文件树）**

```
var/improver_library/<domain>/
    INDEX.md                          # 索引：每条一行 cue
    entries/<task_id>/
        harness/                      # 采纳的完整产物（DWC 是规则+配置快照）
        EXPERIENCE.md                 # cue / lesson / evidence / confidence
```

**四条硬规则（全部来自论文实测）**

| # | 规则 | 论文依据 |
|---|---|---|
| 1 | **缺证据不入库**：`cue`/`lesson`/`evidence` 三项任一为空 ⇒ 不写（返回 None，不写半条） | `library.py:43-47` |
| 2 | **防泄漏**：写库前断言产物里没有判据/评分；库只保留**当前任务之前**的条目 | `library.py:101-104,122-123` |
| 3 | **选择性复用**：下轮从基线起，按 cue 从库取用，不自动继承 | §2.3 |
| 4 | **库空时只能"恢复"不能"提升"**：k=1 的库只能把性能拉回基线；要增益必须积累到 k≥5 的探索量 | Figure 7 |

**Files**
- Create: `src/dwc/organs/improver_library.py`
- Modify: `src/dwc/organs/meta_policy.py`（从"调旋钮"扩为"调旋钮 + 读库"）
- Modify: `scripts/dwc_evo_round.py`（轮末写库、轮初读库）
- Create: `tests/test_r447_library.py`

**验收**
- 缺 `evidence` 的条目写不进去（返回 None 且磁盘无变化）。
- 含判据字样的产物被拒。
- 第二轮起草的提示里出现第一轮的 `cue`（证明库被读到）。
- 删掉库 ⇒ 性能回到基线（复现论文的 w/o library −3.1/−1.8）。

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
| 2 | Harness² (2610.14224) | 2026 | 两层递归（执行+改进） | P4 | ✅ | R438 #14 只调一个旋钮，不是"改进器带库" |
| 2 | 同上 | | 对比式 Propose-Probe-Compose | P1-c | ✅ | DWC 只比分数不比行为 |
| 2 | 同上 | | 双候选作用域（通用/领域） | P2 扩展 | ✅ | DWC 不区分能力缺陷与领域知识 |
| 2 | 同上 | | 改进库（全树 + EXPERIENCE.md） | P4 | ✅ | DWC 有 lessons/skills 但无捆绑 |
| 2 | 同上 | | 证据门槛（cue/lesson/evidence 全非空） | P4 | ✅ | 与 DWC "不可复现不进候选" 同源，但更严 |
| 2 | 同上 | | 选择性复用而非继承 | P1-c 前置 | ✅ | **DWC 现在做反了**，论文实测继承会掉分 |
| 2 | 同上 | | 并行递归 k=5 | — | ❌ | 成本 ×5，日预算吃不下 |
| 2 | 同上 | | 8 组件文件级重写 | — | ❌ | DWC 是配置/规则级，改文件树会破坏隔离 |
| 3 | Cache Engineering (2610.28577) | 2026 | cached_tokens 三档计价 | P0-a 补充 | ✅ | 两篇独立论文收敛于同一需求 |
| 3 | 同上 | | 前缀失效诊断（trim = 1.85×） | P0-b 补充 | ✅ | DWC 每轮重建 prompt，缓存几乎不可能命中 |
| 3 | 同上 | | 上下文策略三元组 | P2 扩展 | ✅ | `context_mgmt` 现在只有一种硬编码形态 |
| 3 | 同上 | | 策略 RSI（比专家再省 7.1%） | P4 佐证 | ✅ | 第三份"进化策略而非内容"的证据 |
| 3 | 同上 | | Drop / Repos（KV cache 操作） | — | ❌ | 需自建 SGLang + 改模型内部；DWC 走远程 API |
| 3 | 同上 | | Cache-as-Tool | — | ❌ | 同上，且会新增工具面 |
| 3 | 同上 | | 位置编码解耦 | — | ❌ | DWC 无 RoPE 控制权 |
| 3 | 同上 | | serving 优化（1.36×/1.51×） | — | ❌ | DWC 不拥有推理服务 |
| 4 | （待填） | | | | | |

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
| 行为对比 | 无 | **每轮有 Contrast** | `disappeared/persisted/introduced` 三列表非空 |
| 改进库条目 | 0 | **≥ 10 条且全带 evidence** | `var/improver_library/*/entries/*/EXPERIENCE.md` |

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

1. 论文池 ≥ 3 篇 —— **已满足**（HarnessPro 2610.26770 / Harness² 2610.14224 / Cache Engineering 2610.28577）。
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

## 11. 三篇论文的收敛结论

三篇论文来自不同团队、不同问题，但在三件事上收敛：

### 11.1 收敛点一：**成本必须一等**

| 论文 | 说法 |
|---|---|
| HarnessPro | `min(−PR, C)`，Pareto 三档 |
| Harness² | 报告 #Steps 与总 compute，明确画 compute–performance 前沿 |
| Cache Engineering | 每任务美分成本作为主指标之一，−27.7% |

**DWC 现状：零成本度量。** 这不是"少一个功能"，是少一个目标函数。

### 11.2 收敛点二：**进化的是策略，不是内容**

| 论文 | 进化的对象 | 相对人工设计的收益 |
|---|---|---|
| HarnessPro | prompt / profile / 预算策略 | +2.0pp 且 −26.1% 成本 |
| Harness² | 改进器本身（库） | 去掉库 −3.1 / −1.8 |
| Cache Engineering | cache 策略 | 比专家再省 **7.1%** |

三份独立证据都指向：**手写一次策略，不如让系统自己搜策略**。

### 11.3 收敛点三：**不许破坏前缀 / 不许继承**

| 论文 | 证据 |
|---|---|
| HarnessPro | 阶段提醒追加到 tool result，不重写 system prompt（保 cache 前缀） |
| Harness² | 直接编辑不看参考/探针/库 ⇒ 73.4→63.2（−10.2） |
| Cache Engineering | trim 改前缀 ⇒ 成本 **1.85×** |

**DWC 同时踩了三条**：
1. 每轮重建整串 prompt（前缀必变）
2. `propose` 继承上轮 `p.code`
3. compaction 滑动窗口 + 摘要

> 这三条不是三个独立的小问题，是同一个根因：
> **DWC 的上下文是"重新渲染"的，不是"累积"的。**

### 11.4 实测修正（2026-10-24）

第 ① 条**已实测降级**：真实调用三次，`cached_tokens` 全是 **0**
（详见 `docs/P0_0_COMPACTION_MEASUREMENT.md`）。

- 服务端要么没开前缀缓存，要么不回报 ⇒ **DWC 今天没有缓存收益可以失去**
- 所以论文的 1.85× 不适用；compaction 在 token 上是**净省**
- 它真正的风险是**信息损失掉分**（对应论文的 summary −5pp），不是"变贵"

第 ② 条（继承 `p.code`）**不受影响**，P1-c 优先级不变。

### 11.5 因此 P0 的实际顺序

原计划 P0-a 是"加记账"。三篇论文合起来说明：

| 顺序 | 动作 | 状态 |
|---|---|---|
| **P0-0** | 量一次 compaction 的成本 | ✅ **已完成**：`cached_tokens` 恒 0 ⇒ 无缓存可失去；压缩净省 token |
| P0-a | 加 token 记账（含 cached 三档） | ✅ **已完成**（R439，15 passed） |
| P0-b | 输出压缩 + 原文落盘 | ⏳ 进行中（前缀稳定性度量降级为"缓存友好准备"） |

---

*本计划为版本级规划，各阶段开工前需再产出对应的 R 轮实现计划（含逐任务 TDD 步骤）。*
