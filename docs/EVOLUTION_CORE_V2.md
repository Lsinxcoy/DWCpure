# DWC · 进化核心 V2（以 16 篇进化论文为核心重构）

> 2026-10-03 · V1 = 之前讨论的进化核心（34 对象 → 21 对象 + 应用层 + 无影子）
> V2 = 以 16 篇进化论文为**核心参照**重新构建，**V1 降为背景材料**
> 判据：每条机制标注 arXiv 编号 + 论文原文；V1→V2 逐项给差异，不写"综合/改进"这类空话

---

## 〇、V2 的第一句话

```text
★ V1 的问题: 它的骨架来自"对四个项目的实测归纳" ——
   34 个对象是从母巢/ARSI/Ultra/Nexus 数出来的,
   门是从 ARSI 抄的, 落地器是从母巢 GeneChampion 抄的。
   ⇒ V1 是"归纳", 缺一个第一性的框架。

★ V2 的改法: 16 篇论文先回答"进化必须有哪些部分",
   再用实测的四个项目填进去。
   ⇒ V2 是"演绎 + 实证", 顺序反过来了。

★ 一句话差异:
   V1: 我们数出了 21 个对象和 4 个步骤 → 拼成进化核心
   V2: 16 篇说进化有 7 个正交问题 → 每个问题一个器官, 对象只是器官②的内容
```

---

## 一、★ V1 → V2 总览（九个改动）

| # | 维度 | V1（之前讨论） | V2（以 16 篇为核心） | 依据 |
|---|---|---|---|---|
| 1 | **骨架** | 四步流水线：消化→提案→过门→应用 | **七器官**：诊断/对象/门/落地/防漂移/探索/主体 | 16 篇的 7 个正交问题 |
| 2 | **对象分类** | 21 个对象（6 套体系并集） | 21 个对象 **映射到 RRSI 的 𝒦 词表**（9 组件 + 𝒦_str 4 个） | 2609.24972 式 12 |
| 3 | **诊断** | 失败聚类（无签名定义） | **失败签名 (c,q,m) 精确聚类** + 七桶路由 + 四量度量 | 2606.09498 / 2609.06396 / 2609.14857 / 2609.11873 |
| 4 | **门** | ARSI 非补偿四步（单一门） | **四门并置**：RRSI 三步 + 双 split + FGGM 契约 + drawback 检测器 | 2609.24972 / 2606.09498 / 2603.25111 / 2607.12790 |
| 5 | **落地** | GeneChampion 的 champion/challenger 五相 | **离线回放**（候选集含 current ⇒ 数学保证不回退）+ pub/priv 解耦 | 2609.14858 / 2609.26457 |
| 6 | **防漂移** | ★ 无 | **新增器官⑤**：GDI 四信号 + CAR + 回归风险 + grounded 双条件 | 2603.06333 / 2609.13406 / 2608.10299 |
| 7 | **探索** | ★ 无 | **新增器官⑥**：残差难度 δ_θ + EL 调度器 + 三方向 | 2609.04128 |
| 8 | **主体** | ★ 无 | **新增器官⑦**：五元 χ=(π,V,m,U,ρ) 盘点 | 2609.13406 / 2609.11873 |
| 9 | **影子** | 不要影子（只说"不用"） | **给出替代机制的论文出处** + 一个必须做的实验 | 2609.14858 §5.1 负面结果 |
| 10 | **数据侧** | ★ 无（V1 没讨论轨迹分块） | **三层粒度 + 非对称保留** + `is_turn_boundary` 规则 | 2609.08183 §3.1 |

---

## 二、★ V2 的骨架：7 个器官 = 16 篇的 7 个正交问题

```text
① 诊断   为什么该进化?  2606.09498 / 2609.06396 / 2609.14857 / 2609.11873
② 对象   改什么?        2609.24972 / 2606.14249 / 2609.14857
③ 门     该不该落?      2609.24972 / 2606.09498 / 2603.25111 / 2607.12790
④ 落地   怎么落?        2609.26457 / 2609.06396 / 2609.24972 / 2609.08183
⑤ 防漂移 落完怎么验?    2603.06333 / 2609.13406 / 2608.10299
⑥ 探索   往哪探索?      2609.14858 / 2609.04128
⑦ 主体   谁在改?        2609.11873 / 2609.13406
```

**★ 与 V1 四步的对应关系**：

```text
V1 四步                  V2 七器官
──────────────────────  ──────────────────────────────────────────
① 消化 (失败聚类)    →   ① 诊断 (签名 + 路由 + 四量)          ← 扩了 3 倍
② 提案 (Manifest)    →   ② 对象 (𝒦 词表 + 九维 + hook)       ← 换了分类依据
③ 过门 (非补偿四步)  →   ③ 门 (四门并置)                      ← 从 1 门变 4 门
④ 应用 (champion)    →   ④ 落地 (离线回放 + pub/priv)         ← 换了机制
                     →   ⑤ 防漂移 (V1 完全没有)
                     →   ⑥ 探索 (V1 完全没有)
                     →   ⑦ 主体 (V1 完全没有)
```

---

## 三、器官① 诊断 —— V2 扩了 3 倍

### 3.1 失败签名 (c, q, m)：两篇独立收敛

```python
# 2606.09498 Self-Harness §3.3 原文
φ(r_i) = (c_i, q_i, m_i)
  c_i : 终止级 verifier 原因
  q_i : 相关 agent 行为的因果状态
  m_i : trace 暴露出的抽象 agent 机制

# 2609.06396 MetaRSI Eq.10 原文
φ(τ) = ( χ(τ) terminal cause, ψ(τ) causal role, μ(τ) reusable mechanism )
```

**★ V2 相对 V1 的改动**：V1 只写"失败轨迹 → 失败聚类"，**没定义聚类依据**。

```text
2606.09498 原文明确了聚类规则:
  "聚类是确定性的、evaluator-grounded 的：两个失败 case 只有在它们对
   『verifier 最终拒绝了什么』『agent 行为如何促成该拒绝』『涉及哪个可复用行为机制』
   三点一致时才被归到一组。"

原文还给了它要防的错误:
  "两个 run 可能共享同一个 verifier 结果 (如 timeout 或缺失产物),
   却需要不同的 harness 改动"

★ 分工 (2609.06396 原文): 前两段由规则分配, 第三段由模型假设。
```

### 3.2 七桶路由：`infra_only` 不进化（V2 新增，V1 没有）

```python
# 2609.14857 ModularRSI Appendix B Table 8 原文
BUCKETS = ("all_pass_efficient", "all_pass_wasteful", "mixed",
           "fixable_fail", "stuck_fail", "unreachable_fail", "infra_only")
```

```text
★ 原文: infra_only 不进诊断 —— 否则演化会试图用 harness 改动去修环境 bug。

Negative 组内三分 (处理策略完全不同):
  fixable_fail      → 提改动
  stuck_fail        → 提 recovery hint (同动作重复 N 次仍失败)
  unreachable_fail  → 弃权 (当前权限/工具/上下文下不可能成功)

★ "弃权是一等输出" (Listing 2 的 is_culprit: false / fixable_now: false)
```

### 3.3 四量度量：纠正"写了就等于用了"（V2 新增）

```text
# 2609.11873 原文
"a relevant skill may never be retrieved, or an agent may retrieve it
 without following it correctly"

⇒ DWC 必须分别度量四个量:
   ① update quality      写得对不对
   ② activation          会不会被检索到
   ③ faithful use        检索到会不会照做
   ④ downstream benefit  照做有没有用

★ 直接治母巢的病: 母巢只测 ①, 于是 98.8% 未访问 (②=0) 无人发现。
```

---

## 四、器官② 对象 —— V2 换了分类依据

### 4.1 ★ V2 的分类法：RRSI 的 𝒦 词表（V1 没有）

```python
# 2609.24972 RRSI 式 12 原文
COMPONENT_VOCAB = frozenset({
    "prompt", "control_flow", "config", "output_plumbing",
    "context_mgmt", "client_tool", "skill", "memory", "subagent",
})
# 式 15: 结构型组件 (取新颖度奖励 ν_str)
STRUCTURAL = frozenset({"client_tool", "skill", "memory", "subagent"})
```

**★ V1 的 21 个对象 → V2 的 𝒦 映射（21 个不删，但归入 𝒦 的分类）**：

> ★★★ **2026-10-04 更正：本表的编号与 `EVOLUTION_DIMENSIONS_TABLE.md` 的权威清单不符。**
> 权威清单（以 DIMENSIONS_TABLE 为准，已逐条核）:
>   1标量参数/配置 2提示词 3技能 4记忆 5**工具** 6知识/语义 7**代码** 8**架构/拓扑**
>   9**策略** 10**智能体** 11协作/社会图 12上下文 13**观测** 14**执行环境**
>   15**外部机制源** 16**评估器/奖励** 17置信校准 18推理增强 19harness
>   20**基础设施** 21**元认知**
> ⇒⇒ 下表已按权威编号重写。三处错位已修（见下方★标记）。

| 𝒦 组件 | V1 对象（**按权威编号**） | ★ 更正说明 |
|---|---|---|
| `prompt` | 2 提示词 | ★ 原写"8 提示词"，权威是 2 |
| `control_flow` | 9 策略 · 19 harness | ★ 原写"2 策略 · 19 行为/工作流" |
| `config` | 1 标量参数/配置 · 17 置信校准 · 18 推理增强 | ★ 原写"17 模型选择 · 18 训练桥"（那是九维 D1/D9 的名字, 不是 V1 对象名） |
| `output_plumbing` | 13 观测 | ★★★ 原写"12 观测 · 16 控制/安全" —— **16 是评估器, 不是控制/安全**; 见下方独立行 |
| `context_mgmt` | 12 上下文 | ★ 原写"11 上下文" |
| `client_tool` | 5 工具 · 14 执行环境 | ★ 原写"9 工具 · 13 执行环境" |
| `skill` | 3 技能 | — |
| `memory` | 4 记忆 · 6 知识/语义 | ★★ 原写"5 知识 · 21 外部机制源(论文)" —— 权威里 **21 是元认知, 不是外部机制源**; 外部机制源是 **15** |
| `subagent` | 10 智能体 · 11 协作/社会图 | ★ 原写"10 协作" |
| (未覆盖) | 7 代码 · 8 架构/拓扑 · 16 评估器/奖励 · 15 外部机制源 · 20 基础设施 | ★★★ 五项名字对，但编号全错; 且"外部机制源"应是 **15** 而非 21/20 二选一 |
| ★★ 原表第 21 项（元认知/元进化） | 21 元认知 | ★★★ **原表把 21 标成"外部机制源(论文)"，导致 21 从未出现在未覆盖项里** ⇒ 这是 A3 缺口清单少算一项的原因 |

> ★★★ **三处最严重的错位**（若不改，落地器会写错对象）:
>   ① 第 16 项是**评估器/奖励**，原表映射到 `output_plumbing`（输出管道）
>      ⇒ ★★ 这等于把评估器当成可插拔的输出部件 —— 直接违反 G10 与 grounded 第二条件
>   ② 第 21 项是**元认知**（= meta_evolution），原表写成"外部机制源(论文)"
>      ⇒ ★★ 于是"元进化"从未被列为未覆盖项 ⇒ A3 缺口清单名义是 5 个, 实为 5 个但**编号错位**
>   ③ "外部机制源"在权威清单里只有 **15** 一个; 原表同时用了 21 和 20 两个 ⇒ 重复计数
> ⇒⇒ ★ 这三处错位正是 A3 缺口表述含混的**根因**; 已在本表修正
> ⇒⇒ ★★ 处置（𝒦_meta 五项）见 docs/COMPONENT_VOCABULARY.md

**★ 诚实标注**：RRSI 的 𝒦 只覆盖 16/21 个 V1 对象。**未覆盖的 5 个（代码/架构/元进化/评估器/外部机制源）需要 DWC 自己补**——这是 V2 必须承认的缺口，不能假装 𝒦 是完备的。

### 4.2 九维分类法（HarnessX，与 ARSI c1-c9 同构）

```python
# 2606.14249 HarnessX §3.3 原文
D1 model selection    D4 tool ecosystem    D7 control/safety
D2 context assembly   D5 execution env     D8 observability
D3 memory management  D6 evaluation        D9 training bridge
```

```text
★ 与 ARSI 的 c1-c9 完全同构 (DEDUP_AUDIT 已实测)。
★ V2 用法 (原文): "每个新增模块必须声明：dimension ∈ {D1..D9},
   hook ∈ 八 hook, singleton_group = <互斥类名>"
   ⇒ 把"重复检测"从语义理解变成 属性冲突检测
```

### 4.3 八 hook + 互斥类（治"抢位冲突"）

```python
# 2606.14249 Table 1 原文
HOOKS = ("task_start", "step_start", "before_model", "after_model",
         "before_tool", "after_tool", "step_end", "task_end")
READ_ONLY = {"step_end", "task_end"}

class Processor(Protocol):
    _singleton_group: str   # 互斥类：每组至多一个 ← 直击"抢位冲突"
    _order: int             # PRE / NORMAL / POST
    _after: list[str]       # 对其他 singleton group 的软依赖

★ 原文: "run loop 在每次调用后校验 hook 契约；违规（如修改 read-only 字段）
        立即抛异常，而不是静默传播损坏状态。"
★ V2 采这条: 违规用异常, 不用日志。
```

---

## 五、器官③ 门 —— V2 从 1 门变 4 门

### 5.1 ★ 门①：非补偿三步 + 三个正则器（RRSI）

```python
# 2609.24972 §3.3 原文 —— 顺序不可换
0) leakage screen BEFORE evaluation       # 泄漏筛查在评估之前
1) noise floor        Ŝ ≥ S* − δ
2a) ΔS > δ  → cost rule   ΔC ≤ β₀ + β₁·ΔS
2b) ΔS ≤ δ  → shaped      ws·ΔS − wc·ΔC + wn·ν_str > 0
3) domain guards
```

```text
三个正则器 (§3.2 原文):
(1) 退火编辑预算  b_t = ⌈ b_min + (b_max − b_min)·½(1 + cos(π t / T)) ⌉  式 4
    b_min = 1 ⇒ 最后一轮只允许一个可独立归因的编辑
    原文理由: "不约束的 proposer 会把很多互不相关的修改捆成一个候选…
              any measured change is difficult to attribute to a particular mechanism"
(2) 证据感知信用分配  ℒ_t = { (t_i, ℓ_i, h_i, d_i, ΔS_i, ΔC_i, a_i) : i ≤ n_t }
    a_i = 1 当且仅当携带编辑 i 的候选成为该轮赢家
    ★ "通过了所有门但输给更高分候选" 记 a_i = 0 ("admissible but lost")
(3) 结构化探索  停滞检测 σ_t = 1[Ŝ_t − Ŝ_{t−w} ≤ δ]  式 13
```

### 5.2 ★ 门②：双 split 接受规则（Self-Harness）

```python
# 2606.09498 Algorithm 1 line 13 原文
if Δ_in ≥ 0 and Δ_ho ≥ 0 and max(Δ_in, Δ_ho) > 0 then Accept
```

```text
★ "必须同时有 held-in 与 held-out 两组" 是关键:
  "总量上升但结构变差" 会被拒。
★ 2607.12790 给出更强的三 split: train / dev(恒 10 条) / test(locked)
```

### 5.3 ★ 门③：FGGM 契约 + 已验证 fallback（SEVerA）

```python
# 2603.25111 §2.2 原文伪代码
requires Φ_l(x1,…,xn) {
    var p := f_p(x1,…,xn), y;
    for i = 1..K {                      # K = 5
        y := L_Θ(p);                    # 底层参数化 GM
        if check(x1,…,xn, y) return y;  # (1) 拒绝采样
    }
    return f_d(x1,…,xn, y_f);           # (2) 已验证的 fallback
}
```

```text
★ 四条声明性质 (§4.2 原文编号):
  1 Flexibility                       — 契约由 planner LLM 现场合成
  2 Parameter-Independent Correctness — 对任意 θ ∈ Θ 都成立
  3 Local Learning Objective          — 契约顺手抽出局部学习目标
  4 fallback 的必要性                  — 没有 fallback 拒绝采样器可能耗尽样本
★ 关键: fallback 本身也必须满足同一条契约 (validateFGGM 第 26 行)

★ 直接命中母巢反例: 母巢 _probe() 恒 return True、ScoreChannel.score() 恒 0.7
  = 没有 checker、没有 fallback 的裸 GM 调用
```

### 5.4 ★ 门④：drawback 检测器（Grader，不认证正确）

```text
# 2607.12790 §2.1 原文
"we rarely know what good is, but given an output we can usually find drawbacks,
 so a clean verdict means no known drawback was found, not certified correctness.
 That is what makes bootstrap possible."

配套设计理由:
"mostly deterministic detectors, which fail differently from the LLM being graded,
 resist the shared-blind-spot collusion a bare LLM judge invites."
⇒ 不让评分器和被评分的模型共享失效模式
```

**★ 四门的顺序（V2 强制）**：

```text
① 泄漏筛查 (RRSI 第 0 步) —— 必须在任何评估之前
② FGGM 契约检查 (判定能力是否真可用)
③ drawback 检测 (不认证正确, 只找缺点)
④ 双 split 接受 (Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧ max > 0)
⑤ 非补偿三步 (噪声地板 → 成本规则/整形 → 领域守卫)
⑥ 退火预算 b_t (约束本轮可独立归因的编辑数)

★ 顺序不可换 —— 每一步都建立在前一步的结论上。
```

---

## 六、器官④ 落地 —— V2 换了机制

### 6.1 ★ V1 → V2 的落地机制替换

```text
V1 落地器 (母巢 GeneChampion):
  cold → hold → explore → evaluating(等 N tick) → promoted | reverted
  ★ 问题: "evaluating(等 N tick)" 就是影子的残余

V2 落地器 (2609.14858 Dream-RSI):
  候选集必含 current ⇒ argmax 结果不可能差于现状 (数学结论)
  ★ 算完即决, 无等待期
  A(𝒯) = {r} ∪ {v ∈ 𝒯 : v is a leaf}    ← 候选集定义就含 root
```

### 6.2 ★ pub/priv 信号解耦 + 固定预算（AIDE²，V2 新增）

```python
# 2609.26457 §2.1 原文
内环: x_i = a( x_i, r_t^pub(x_i) )       # agent 只看 public
外环: g(a) = (1/T) · Σ r_t^priv( x̂_t )   # 接受门只看 private

原文两条设计:
  "First, separating the inner loop's optimization signal r_t^pub from the
   outer loop's selection signal g (driven by r_t^priv) prevents the inner-loop
   agent from directly optimizing the criterion used for outer-loop selection.
   Second, evaluating all agents under the same per-task budget b_t constrains
   improvements to arise from a better algorithm rather than from spending
   additional compute."
```

```python
# DWC 接口
@dataclass(frozen=True)
class DualSignal:
    agent_visible: float          # r_pub — 给被改写者看
    selection: float              # r_priv — 给接受门看
    selection_truth_source: str   # 必填

★ DWC 的具体形态: 记忆底座天然有两个信号 ——
  agent 可见的检索结果 (r_pub) 与 事后才能算的记忆真实效用 (r_priv)。
  这正好是一个真实的 pub/priv 对, 不需要制造。
```

### 6.3 三元组状态 + 非对易性 + 信号新鲜度（MetaRSI）

```text
# 2609.06396 §2.1 原文
S = (𝒟 data, θ model, 𝒽 harness)
"a change confined to any one of them changes what the deployed system does"

改进过程: U:(S, σ, B) ↦ (S̃, A, E, c)      Eq.3
预算 B = (β_tok, β_clk, β_gpu, β_qry) —— 四种不可互换资源
非对易性: U_j ∘ U_i(S) ≠ U_i ∘ U_j(S)     Eq.4

★ 信号新鲜度 (Principle 4.4) —— V2 新增, 防"记忆越滚越大但记的是旧系统":
  fresh(a, t+1) iff compiled(a) ≥ 最近一次 capability-altering step
  原文: "a step that changes what the deployed system does invalidates every
        signal compiled before it, because the attempts such a signal summarizes
        were made by a system that no longer exists"
```

### 6.4 ★ 数据侧三层结构 + 非对称保留（NeoHorse-1，V2 新增）

```text
# 2609.08183 §3.1 原文 —— 三个粒度, 且明确每个粒度的用途
Trajectory   一次完整交互 (user requests + responses + tool calls +
             obs + recovery + terminal outcomes)
User turn    从一个 user request 到下一个 user request / 任务终止
             ★ 序列化的基本训练单元
Subscene     共享同一局部目标的相邻 user turns

★ 关键约束 (两条, DWC 必须抄):
  "Tool results and harness-injected messages do not initiate a new user turn."
  ⇒ 工具结果与 harness 注入的消息不切分 user turn 边界

  上下文保留策略: "Within each user-turn record, the current request and its
   interleaved reasoning, tool calls, and observations are retained…
   Earlier visible responses and tool interactions remain available as context,
   whereas reasoning from earlier turns is omitted."
  ⇒ 历史 reasoning 被丢弃, 历史可见响应被保留 (这个不对称是有意的)
```

```python
# DWC 接口
def is_turn_boundary(msg: dict) -> bool:
    # 只有 role == 'user' 的真实请求才是边界。
    # tool_result / harness_injected 一律 False。
    return msg.get("role") == "user" and not msg.get("tool_result") \
           and not msg.get("harness_injected")

★ 这条规则本身就是一个 bug 来源: 若把 tool result 当成新一轮边界,
  user turn 会被切得过碎, reasoning–action–feedback 链被打断。
```

**★ 本篇的方法级可执行性（V2 必须标注）**：

```text
2609.08183 的 §4 三个方法 (式 1/2/3) DWC 一条都执行不了:
  L_SFT 梯度更新      → 需自有权重 + 训练框架
  L_OPD 反向 KL       → 需自有学生权重
  teacher token 分布  → 需访问教师 logits (托管 API 只返回文本)
  SGLang 部署         → 需自建推理栈 + GPU
★ 但 §3 (数据侧) 可执行 —— 因为它只需要记录、分类与排序, 不需要梯度。
```

### 6.5 消费点声明（DWC 自定，V1 保留）

```python
# V2 保留 V1 的形态, 但加 verify
{"consumer": "策略选择 ε-greedy 探索率",
 "path": "actor._policy", "attr": "_epsilon",
 "range": (0.01, 0.5),
 "verify": "abs(actor._policy._epsilon - candidate) < 1e-9"}

★ 三条纪律 (母巢用 3 次失败换来, V2 保留):
  1 基线与结算必须同一口径    (母巢错: base 取启动 score_in({}), current 取结束)
  2 base 打老配置, current 打新配置 (母巢错: gain = 自己减自己 = 0)
  3 打分器没分辨率时调门槛是自欺 (母巢错: min_gain 0.01→0.0005, 反而累积退化)
```

---

## 七、器官⑤ 防漂移 —— V1 完全没有

### 7.1 GDI 四信号（SAHOO）

```text
# 2603.06333 Appendix B 原文 —— 四个分量全部落在 [0,1]
Δ_semantic       (1 − s_cos)/2                          Eq.8
Δ_lexical        JSD(P₀‖P_t) = ½KL(P₀‖M) + ½KL(P_t‖M)   Eq.9
Δ_structural     (1/K)·Σ min(1, |s₀−s_t|/(s₀+ε))        Eq.10
Δ_distributional W(P_baseline, P_current)                 Eq.11 (1-Wasserstein)

GDI = w_s·Δ_semantic + w_ℓ·Δ_lexical + w_st·Δ_structural + w_d·Δ_distributional
      w_s + w_ℓ + w_st + w_d = 1                        Eq.12–13

★ 关键设计 (Appendix A.2 原文):
  "drift is measured with respect to the initial model θ₀ rather than the
   immediately preceding model; this yields a cumulative measure of deviation
   and prevents short-term, high-variance cycle-to-cycle changes from masking
   long-term drift."
```

**★ 为什么对 DWC 特别值钱**：

```text
"它只需要『基线 vs 当前』的成对观测, 不需要任务真值源 ——
 这一点恰好绕过真值源困境 (漂移测量不是『是否成功』的判断, 不需要外部真值)。"
```

### 7.2 grounded 双条件（GAI）—— 真值源合法性

```text
# 2609.13406 §2.2 原文
系统 = 五元组 χ = (π policy, V action critic, m modifier, U modification critic, ρ evaluation base)

★ grounded 双条件 (两个是 AND, 缺一不可):
  ① 内容来自系统外 (世界与目标)
  ② base 本身在 agent 外

★ 可落成 gate 断言: {Q*, T_seal, release_rule, ℒ} ∩ W_i = ∅ ∀i

★ Remark 2 原文:
  "判别标准问的是『标准坐在哪里』, 不是『它多忠实于目标』。"
  ⇒ 不要用"评估器准不准"判断合法性, 要用"评估器在不在可写面内"判断。
    弱评估器 + 密封 = 合法;  强评估器 + 在可写面内 = Goal Drift。
```

### 7.3 协同进化三条件（综述）

```text
# 2608.10299 §2.2 原文
S^{t+1} = Ω(S^t, τ^t)
∃ x ≠ y ∈ S^t : x^{t+1} ≠ x^t,  y^{t+1} ≠ y^t,  x ←→(evolutionary pressure) y
★ 三条件同时成立才算 co-evolution

Stage 3 判据 (§5.1):
  "The mechanism revision must be induced by the joint trajectory of a
   lower-level co-evolving system and must then alter that ecosystem's
   subsequent evolutionary conditions."

★ 附录 A 原文 (减法优先的依据): "Designing a harness alone is not evolution"
```

---

## 八、器官⑥ 探索 —— V1 完全没有

### 8.1 残差难度（环境进化）

```text
# 2609.04128 §2.1 原文 —— 策略无关的 off-policy 难度公式
δ_θ(z_t|g) = [ d_θ(z_t|g) − d_𝒯(z_t|g) ]₊
           = [ log(p_𝒯(σ|g)/p_θ(σ|g)) + log(p_𝒯(κ|σ,g)/p_θ(κ|σ,g)) ]₊
Δ_θ(ξ) = Σ_t [ d_θ(z_t|g) − d_𝒯(z_t|g) ]₊

★ 全文枢纽句:
  "weakness is not the difficulty of the environment itself; it is the portion
   of that trajectory that is unusually difficult for a particular model
   relative to the environment family."

三条演化方向 = 三个分量:
  length   ← 控制 L
  scenario ← 控制 −log p_𝒯(σ|g)
  skill    ← 控制 −log p_𝒯(κ|σ,g)
```

### 8.2 EL 调度器（零模型依赖）

```text
# 2609.04128 式 2: B = 8, τ = 6/8
★ 关键可迁移性: 不需要任何前沿模型, 只需要 8 次布尔观测
  只有被试出 6/8 通过才放行下一代
```

### 8.3 三方向（Prometheus-Y 实测枚举）

```text
EvolutionDirection.FORWARD   前进 (在现有基础上改进)
EvolutionDirection.LATERAL   横向 (换一个方向试)
EvolutionDirection.REVERSE   后退 (回退到更简单的方案)

★ 39 仓库实测: 只有 Prometheus-X / Y / Omega 有方向概念。
★ 与 2609.04128 的 length/scenario/skill 不同 —— 后者是"难度方向的分解"。
```

---

## 九、器官⑦ 主体 —— V1 完全没有

### 9.1 ★ 五元盘点暴露 DWC 缺两个角色

```text
# 2609.13406 §2.2 原文
χ = (π policy, V action critic, m modifier, U modification critic, ρ evaluation base)

  π  选择世界动作
  V  评估 π 表现多好
  m  提议系统应该如何改变
  U  评估提议的改动是否服务于 G
  ρ  critics 据以度量的标准

★ V2 的盘点结果:
  π = 执行策略        ✓ 有
  V = 评估器          ✓ 有
  m = 改进器          ✗ ★ DWC 目前为空 (承重代码 0 行)
  U = 改动评估器      ✗ ★ DWC 没有这个独立角色
  ρ = evaluation base  ← 正是"系统外的真值源是什么"

★ 结论: V2 的器官④(落地) 需要 m, 器官③(门) 需要 U。
  V1 只有"过门→应用"两个动作, 缺 U 这个独立评估角色。
```

### 9.2 自主性等级（Last AI Built by Humans）

```text
# 2609.11873 §2.3 原文
B0  In-Task AI Improvement —— 非 RSI 参考基线
    判别标准: "output change without persistent system change"
    ★ DWC 的硬判据: 关掉进程重开, 改动是否还在? 若不在, 仍是 B0。
L1  Improvement Execution Autonomy —— 人规定改什么/怎么改/什么算成功; AI 执行
L2  Improvement Strategy Autonomy —— 目标/边界/验收仍外部固定, 但 AI 诊断弱点并决定如何改进

★ structural vs effective (验收必须区分):
  structural = 改动的机制确实控制后续一轮
  effective  = 该机制在可比预算与独立评估下产出更好后继
  原文: "Self-modifying task code provides insufficient evidence when the process
        responsible for later revisions remains unchanged."
```

---

## 十、★ V2 的四条不可违反约束

```text
约束 1 · 顺序: 测 → 判 → 落
  2606.09498 Algorithm 1 (在副本上评估, 通过才合并, 主干最后才动)
  2608.24876 Eq.9 (固定门提供外部接受边界)
  2609.26457 (pub/priv 解耦, 内环不能直接优化外环判据)
  ★ 任何"先落再测"违规 —— 影子期/灰度/线上 A/B 一律不行。

约束 2 · 判据必须在可写面之外
  2609.06396 (Q*/𝒯*/release rule/ℒ 不属于 S)
  2609.13406 (grounded 双条件)
  2607.12790 (评估器会塌缩成 always-pass)
  2606.14249 (用自己的实验证伪了自己的门: −14.0%)
  ★ 三篇独立得出, 两两互不引用 —— 全领域最强的一致结论。

约束 3 · 必须有两组 split
  2606.09498 (Δ_in ≥ 0 ∧ Δ_ho ≥ 0)
  2607.12790 (train/dev/test, test locked)
  ★ 只有一组 split 就没有判定"可复用改进 vs 过拟合"的能力。

约束 4 · 每轮变更数必须可归因
  2609.24972 (退火预算 b_t, 末轮 b_min = 1)
  2606.09498 (失败签名精确聚类 ⇒ 一簇对应一处干预)
```

---

## 十一、★ V2 的七器官骨架（可执行形态）

```text
┌──────────────────────────────────────────────────────────────────────┐
│  DWC 进化核心 V2                                                       │
│                                                                       │
│  ① diagnosis/    诊断                                                 │
│     ├ signature.py   失败签名 (c,q,m) 精确聚类   2606.09498/06396      │
│     ├ router.py      七桶路由 (infra_only 不进化) 2609.14857            │
│     └ measure.py     四量度量 update/activation/use/benefit 2609.11873 │
│                                                                       │
│  ② objects/      对象                                                 │
│     ├ vocab.py       组件词表 𝒦(9) + 𝒦_str(4)     2609.24972           │
│     ├ dimension.py   九维 D1-D9                    2606.14249           │
│     └ hook.py        八 hook + singleton_group     2606.14249           │
│                                                                       │
│  ③ gates/        门 ★ 顺序: 泄漏→契约→缺点→双split→非补偿→预算          │
│     ├ leakage.py     泄漏筛查 (必须在评估前)        2609.24972           │
│     ├ contract.py    FGGM 契约 + 已验证 fallback    2603.25111           │
│     ├ drawback.py    drawback 检测器 (不认证正确)   2607.12790           │
│     ├ split.py       双 split 接受 Δ_in/Δ_ho        2606.09498           │
│     ├ noncomp.py     非补偿三步 + 领域守卫          2609.24972           │
│     └ budget.py      退火预算 b_t + 信用分配 ℒ_t    2609.24972           │
│                                                                       │
│  ④ applier/      落地                                                 │
│     ├ dual.py        pub/priv 信号解耦              2609.26457           │
│     ├ budget_ledger.py 固定预算 (四资源不可互换)     2609.26457/06396    │
│     ├ state.py       三元组 S=(𝒟,θ,𝒽) + 非对易性    2609.06396           │
│     ├ freshness.py   信号新鲜度 (capability_altering) 2609.06396         │
│     ├─ granularity.py 三层粒度 + is_turn_boundary    2609.08183           │
│     └ consume.py     消费点声明 {consumer,path,attr,range,verify}        │
│                                                                       │
│  ⑤ drift/        防漂移                                               │
│     ├ gdi.py         GDI 四信号 + CAR + 回归风险     2603.06333           │
│     ├ grounded.py    grounded 双条件 (ρ 在可写面外)  2609.13406           │
│     └ coupling.py    协同进化三条件                  2608.10299           │
│                                                                       │
│  ⑥ search/       探索                                                 │
│     ├ weakness.py    残差难度 δ_θ                    2609.04128           │
│     ├ el_sched.py    EL 调度器 (B=8, τ=6/8)          2609.04128           │
│     ├ replay.py      回放仿真器 (候选集含 current)    2609.14858           │
│     └ direction.py   三方向 FORWARD/LATERAL/REVERSE  (Prometheus-Y)      │
│                                                                       │
│  ⑦ agent/        主体                                                 │
│     ├ quintuple.py   五元 χ=(π,V,m,U,ρ) 盘点         2609.13406           │
│     └ autonomy.py    自主性等级 B0→L2 + struct/eff   2609.11873           │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 十二、★ V2 必须先做的一件事（论文直接给的）

```text
# 2609.14858 §5.1 的负面结果 (Dream-RSI 报告原文)
★ 论文证明: 在多线程长程搜索里, guidance (把历史拼进 prompt)
            一致劣于 replay (把历史组织成可回放树)。

⇒ DWC 现有记忆机制大概率是 guidance 形态。
⇒ V2 必须做的实验:
    src/dwc/experiments/mem_guidance_vs_replay.py
    同一批记忆, A 组注入 prompt, B 组组织成 replay tree, 跑同一策略, 对比下游效果

★ 这个实验的价值: 它是 V2 里唯一"能立刻证伪 V1 假设"的实验。
  V1 假设"记忆写进去就会被用", 这个实验直接测它。
```

---

## 十三、V2 的诚实边界

```text
① 性能数字一律不采。COMPARISON.md 原文: "结构可复用, 性能数字一律不可复用"。
   DWC 模型档位远低于论文的前沿模型, 所有 pp/% 数字零参考价值。
② 16 篇里方法级可执行的只有 2 篇 (SEVerA / GAI); 其余 14 篇是机制级可照搬。
   "机制级可照搬" ≠ "已验证" —— V2 只做设计, 未写代码未跑测。
③ RRSI 的 𝒦 词表只覆盖 21 个 V1 对象里的 16 个。
   未覆盖 5 个 (代码/架构/元进化/评估器/外部机制源) —— 需 DWC 自己补, 本轮未解。
④ 跨篇冲突未裁决: HarnessX 与 Self-Harness 的门互相矛盾 (−14.0% vs 双 split),
   V2 取"并集"(两个门都要过), 但未验证并集是否真能同时满足。
⑤ 2609.04128 的 δ_θ 需要"参考分布 p_𝒯 的估计", 论文用 deep-research agent 估。
   DWC 若无等价能力, 只能退化为人工设定参考分布 —— 未解决。
⑥ B 类论文 (无方差/无消融) 的机制仍采纳, 因为多是结构性的 (hook 表/桶划分/预算公式);
   但凡"某机制带来 X% 提升"这类效果类主张, 一律不采。
```

---

## 附：V1 文档清单（保留为背景材料）

```text
docs/EVOLUTION_CORE_AUDIT.md        四项目实测审计 (V1 的实证基础)
docs/EVOLUTION_DIMENSIONS_TABLE.md  34 个对象总表 (V1 的对象清单)
docs/DIMENSIONS_FEASIBILITY.md      34 个能否塞进来 (V1 的可行性判断)
docs/DIMENSIONS_SCOPE_V1.md         用户 Q1/Q2 裁决 (V1 的范围)
docs/APPLIER_DESIGN.md              落地器设计 (V2 部分继承, 见 §6.4)
docs/NO_SHADOW.md                   不要影子 (V2 在 §8 给了论文级替代)
docs/DEDUP_AUDIT_6SYSTEMS.md        6 套体系去重 → 21 对象 (V2 的对象依据)
docs/EVOLUTION_CORE_DESIGN.md       16 篇机制提取 (V2 的论文依据)
docs/EVOLUTION_CORE_V2.md           ★ 本文 (V2 正式版)
```
