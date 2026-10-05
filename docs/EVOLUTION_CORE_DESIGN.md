# DWC · 进化核心设计（以 16 篇进化论文为参照）

> 2026-10-03 · 判据：每一条机制都标注 arXiv 编号 + 论文原文出处，不按摘要推断
> 参照集：`docs/papers/` 19 份逐篇深读报告中的 **16 篇进化论文**（另 3 篇是世界模型，不属进化）
> 前置：`docs/NO_SHADOW.md`（不要影子）· `docs/APPLIER_DESIGN.md`（落地器）· `docs/DEDUP_AUDIT_6SYSTEMS.md`（对象去重）

---

## 〇、这 16 篇怎么分工

```text
★ 16 篇不是 16 个并列的方法, 而是对"进化"的 7 个正交问题的回答:

① 为什么该进化?   ← 诊断   2606.09498 / 2609.06396 / 2609.14857 / 2609.11873
② 改什么?         ← 对象   2609.24972 / 2606.14249 / 2609.14857
③ 该不该落?       ← 门     2609.24972 / 2606.09498 / 2603.25111 / 2607.12790
④ 怎么落?         ← 落地   2609.26457 / 2609.06396 / 2609.24972
⑤ 落完怎么验?     ← 防漂移 2603.06333 / 2609.13406 / 2608.10299
⑥ 往哪探索?       ← 搜索   2609.14858 / 2609.04128
⑦ 谁在改?         ← 主体   2609.11873 / 2609.13406

★ 7 个问题 = 7 个器官。这是 DWC 进化核心的骨架。
```

---

## 一、★ 第一性问题：可执行性分级（决定哪些能真用）

```text
★ 16 篇里, 只有 2 篇在 DWC 的模型条件下"方法级可执行":
   2603.25111 SEVerA (Qwen3-8B 可复现)
   2609.13406 GAI   (纯形式, 无实验)

★ 但"机制可照搬"的远多于 2 篇 —— 因为多数机制是纯结构/纯逻辑, 零模型依赖:

机制级可照搬 (零模型依赖)              方法级不可执行 (需权重/闭源前沿模型)
────────────────────────────────────  ────────────────────────────────────────
2609.24972 RRSI 三重门 + 退火预算      2609.08183 NeoHorse-1 (需梯度更新)
2606.09498 Self-Harness 签名 + 接受规则 2505.05522 CTM (8×H100 + 自训权重)
2606.14249 HarnessX hook + 九维        2609.26457 AIDE² 的性能数字 (Opus 4.7 + A100)
2609.14857 ModularRSI 7 桶 + 五模块     全部 harness 自进化篇的性能数字
2609.06396 MetaRSI 三元组 + 信号新鲜度   (Opus / Gemini / 外部 harness)
2603.06333 SAHOO GDI + CAR + 回归风险
2609.13406 GAI 五元 + grounded 双条件
2609.14858 Dream-RSI 回放仿真器
2609.04128 δ_θ 残差 + EL 调度器
2607.12790 Grader drawback 检测器
2608.10299 综述判据
2609.11873 四量度量

★ 铁律: 机制照搬, 数字一律不照搬。
  (COMPARISON.md 原文: "结构可复用, 性能数字一律不可复用 —— 这是全表最重要的一列")
```

---

## 二、器官①：诊断（为什么该进化）

### 2.1 失败签名三元组（两篇独立收敛，措辞不同）

```python
# 2606.09498 Self-Harness §3.3 原文
φ(r_i) = (c_i, q_i, m_i)
  c_i : 终止级 verifier 原因 (terminal verifier-level cause)
  q_i : 相关 agent 行为的因果状态 (causal status)
  m_i : trace 暴露出的抽象 agent 机制 (abstract agent mechanism)

# 2609.06396 MetaRSI Eq.10 原文
φ(τ) = ( χ(τ) terminal cause, ψ(τ) causal role, μ(τ) reusable mechanism )

★ 两篇独立得出同一三段式 —— 这是 DWC 必须采的形态。
```

**★ 关键：聚类必须是"精确一致"，不是"语义相似"**

```text
2606.09498 原文:
  "聚类是确定性的、evaluator-grounded 的：两个失败 case 只有在它们对
   『verifier 最终拒绝了什么』『agent 行为如何促成该拒绝』『涉及哪个可复用行为机制』
   三点一致时才被归到一组。"

  原文还给了它要防的具体错误:
  "两个 run 可能共享同一个 verifier 结果 (如 timeout 或缺失产物),
   却需要不同的 harness 改动"
```

**★ 分工（2609.06396 原文）**：前两段由**规则**分配，第三段由**模型假设**。

```python
# DWC 接口
@dataclass(frozen=True)
class FailureSignature:
    c: str   # terminal cause — 规则分类器填 (非 LLM)
    q: str   # causal role    — 规则分类器填 (非 LLM)
    m: str   # reusable mechanism — LLM 填

def cluster(failed: list[TraceRecord]) -> dict[FailureSignature, list[TraceRecord]]:
    """按三元组精确一致聚类 —— 不按语义相似度。"""
```

### 2.2 ★ 七桶路由：`infra_only` 不进化（性价比最高的一条）

```python
# 2609.14857 ModularRSI Appendix B Table 8 原文
BUCKETS = ("all_pass_efficient", "all_pass_wasteful", "mixed",
           "fixable_fail", "stuck_fail", "unreachable_fail", "infra_only")

★ 原文: infra_only 不进诊断 —— 否则演化会试图用 harness 改动去修环境 bug。

三分 (Negative 组内):
  fixable_fail      → 提改动
  stuck_fail        → 提 recovery hint (同动作重复 N 次仍失败)
  unreachable_fail  → 弃权 (当前权限/工具/上下文下不可能成功)

★ "弃权是一等输出" (Listing 2 的 is_culprit: false / fixable_now: false)
```

### 2.3 ★ 四量分别度量（纠正"写了就等于用了"）

```text
2609.11873 原文:
  "a relevant skill may never be retrieved, or an agent may retrieve it
   without following it correctly"

⇒ DWC 的记忆/机制评估必须分别度量四个量:
   ① update quality      写得对不对
   ② activation          会不会被检索到
   ③ faithful use        检索到会不会照做
   ④ downstream benefit  照做有没有用

★ 这四量直接治母巢的病: 母巢只测 ①, 于是 98.8% 未访问 (②=0) 无人发现。
```

---

## 三、器官②：对象（改什么）

### 3.1 ★ 组件词表（RRSI 九个名字，几乎为 DWC 量身定做）

```python
# 2609.24972 RRSI 式 12 原文
COMPONENT_VOCAB = frozenset({
    "prompt", "control_flow", "config", "output_plumbing",
    "context_mgmt", "client_tool", "skill", "memory", "subagent",
})
# 式 15: 结构型组件 (取新颖度奖励 ν_str)
STRUCTURAL = frozenset({"client_tool", "skill", "memory", "subagent"})
```

**★ 与 DWC 21 个可进化对象的映射**：

| RRSI 组件 | DWC 对象 |
|---|---|
| prompt | 提示词 |
| control_flow | 策略 / 行为-工作流 |
| config | 标量参数/超参 |
| output_plumbing | (观测/输出管线) |
| context_mgmt | 上下文 |
| client_tool | 工具 |
| skill | 技能 |
| memory | 记忆 / 知识 |
| subagent | (协作/子代理) |

### 3.2 九维分类法（HarnessX，用于"门的位置声明"）

```python
# 2606.14249 HarnessX §3.3 原文
D1 model selection    D4 tool ecosystem    D7 control/safety
D2 context assembly   D5 execution env     D8 observability
D3 memory management  D6 evaluation        D9 training bridge
```

**★ 与 ARSI 的 c1-c9 完全同构**（DEDUP_AUDIT 已实测：`c1 model_selection` … `c9 training_bridge`）。

```text
★ DWC 的用法 (原文):
  "每个新增模块必须声明：dimension ∈ {D1..D9}, hook ∈ 八 hook,
   singleton_group = <互斥类名>"
  ⇒ 把"重复检测"从"搜索另一个声明替代同一目标的模块"(需理解语义)
     变成 属性冲突检测 (两个模块声称同一 singleton_group 直接 FAIL)
```

### 3.3 八 hook + 互斥类（治"抢位冲突"的结构性答案）

```python
# 2606.14249 HarnessX Table 1 原文
HOOKS = ("task_start", "step_start", "before_model", "after_model",
         "before_tool", "after_tool", "step_end", "task_end")
READ_ONLY = {"step_end", "task_end"}

class Processor(Protocol):
    _singleton_group: str   # 互斥类：每组至多一个 ← 直击"抢位冲突"
    _order: int             # PRE / NORMAL / POST
    _after: list[str]       # 对其他 singleton group 的软依赖

★ 原文: "run loop 在每次调用后校验 hook 契约；违规（如修改 read-only 字段）
        立即抛异常，而不是静默传播损坏状态。"
```

**★ 这是比"写日志"更强的形态**：违规用**异常**，不用日志。

---

## 四、器官③：门（该不该落）★ 顺序是核心

### 4.1 ★ 顺序：测在前，落在后（16 篇无一例外）

```text
2606.09498 Self-Harness Algorithm 1 原文伪代码顺序:
   8  for all (Δ_j, a_j) ∈ P_t do
   9      h_t^(j) ← Δ_j(h_t)          ← 在候选副本上应用
  10      Evaluate(M, h_t^(j), ...)    ← 评估候选
  13      if Δ_in^(j) ≥ 0 and Δ_ho^(j) ≥ 0 and max(...) > 0 then
  15          Accept(Δ_j)               ← 通过才接受
  23      h_{t+1} ← MergeAccepted(h_t, A_t)  ← 最后才合并进主干

★ 顺序 = 在副本上评估 → 通过 → 合并。生产主干在 line 23 之前未被触碰。

2608.24876 Recuris Eq.9 原文:
  ℳ_{k+1} = { ℳ⁺_k , if 𝒢_fixed( ℳ⁺_k, ℳ_k ; x_k, 𝒟_dev ) = 1
            { ℳ_k , otherwise
  ★ 原文: "The fixed gate provides an external acceptance boundary
           around the recursively evolving memory-control layer."

★ 对比母巢的影子 (先 _apply 落生产 → 等 window → 才结算): 方向相反。
```

### 4.2 非补偿式三重门（RRSI，最科学）

```python
# 2609.24972 RRSI §3.3 原文 —— 顺序不可换
0) leakage screen BEFORE evaluation      # 泄漏筛查在评估之前
1) noise floor        Ŝ ≥ S* − δ          # 噪声地板
2a) ΔS > δ  → cost rule   ΔC ≤ β₀ + β₁·ΔS  # 成本首次成为硬判据
2b) ΔS ≤ δ  → shaped      ws·ΔS − wc·ΔC + wn·ν_str > 0
3) domain guards                          # 领域守卫
```

**★ 三条独立的正则器（同篇 §3.2）**：

```text
(1) L₀-Style Annealed Update Sparsity — 退火编辑预算
    b_t = ⌈ b_min + (b_max − b_min) · ½(1 + cos(π t / T)) ⌉   (式 4)
    b_min = 1 (论文三个 instance 全是) ⇒ 最后一轮只允许一个可独立归因的编辑
    原文理由: "不约束的 proposer 会把很多互不相关的修改捆成一个候选…
              any measured change is difficult to attribute to a particular mechanism"

(2) Evidence-Aware Credit Assignment — 证据感知信用分配
    ℒ_t = { (t_i, ℓ_i, h_i, d_i, ΔS_i, ΔC_i, a_i) : i ≤ n_t },  a_i ∈ {0,1}
    a_i = 1 当且仅当携带编辑 i 的候选成为该轮赢家
    ★ 通过了所有门但输给更高分候选的记 a_i = 0 ("admissible but lost", 有用信息)

(3) Structured Exploration — 结构化探索
    停滞检测 σ_t = 1[Ŝ_t − Ŝ_{t−w} ≤ δ]  (式 13)
    停滞时把一部分配额留给"本轮从未被测量过的组件"
```

### 4.3 双 split 接受规则（Self-Harness，防过拟合）

```python
# 2606.09498 Algorithm 1 line 13 原文
if Δ_in ≥ 0 and Δ_ho ≥ 0 and max(Δ_in, Δ_ho) > 0 then Accept

★ "必须同时有 held-in 与 held-out 两组" 是关键:
  "总量上升但结构变差" 会被拒 (因为两组都要 ≥ 0)
```

### 4.4 FGGM 契约 + 已验证 fallback（SEVerA）

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

★ 四条声明性质 (§4.2 原文编号):
  1 Flexibility                     — 契约由 planner LLM 现场合成
  2 Parameter-Independent Correctness — 对任意 θ ∈ Θ 都成立
  3 Local Learning Objective        — 契约顺手抽出该调用的局部学习目标
  4 fallback 的必要性                — 没有 fallback 拒绝采样器可能耗尽样本

★ 关键: fallback 本身也必须满足同一条契约 (validateFGGM 第 26 行)
```

**★ DWC 直接命中母巢的反例**：

```text
母巢的 _probe() 恒 return True、ScoreChannel.score() 恒返回 0.7
= 没有 checker、没有 fallback 的裸 GM 调用
用 FGGM 包装后: "判定通过"要么来自 checker 判定的真实探测, 要么来自 fallback,
且 source 字段强制区分二者。
```

### 4.5 缺点检测器（Grader，不认证正确，只找缺点）

```text
2607.12790 §2.1 原文:
  "we rarely know what good is, but given an output we can usually find drawbacks,
   so a clean verdict means no known drawback was found, not certified correctness.
   That is what makes bootstrap possible."

配套设计理由:
  "mostly deterministic detectors, which fail differently from the LLM being graded,
   resist the shared-blind-spot collusion a bare LLM judge invites."
  ⇒ 不让评分器和被评分的模型共享失效模式
```

**★ 三个 split（原文）**：

```text
train    大、无标签      暴露候选何时分歧或弃权; train task 上不附任何参考
dev      恒为 10 条      每条带 golden reference; "the only supervised signal any loop reads"
test     locked          "no part of metric evolution reads it"
```

---

## 五、器官④：落地（怎么落）

### 5.1 ★ pub/priv 信号解耦 + 固定预算（AIDE²，最值得整段照抄）

```python
# 2609.26457 §2.1 原文
内环: x_i = a( x_i, r_t^pub(x_i) )          # agent 只看 public 信号
外环: g(a) = (1/T) · Σ r_t^priv( x̂_t )      # 接受门只看 private 信号

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

★ DWC 的具体形态 (报告原文): DWC 的记忆底座天然有两个信号 ——
  agent 可见的检索结果 (r_pub) 与 事后才能算的记忆真实效用 (r_priv)。
  这正好是一个真实的 pub/priv 对, 不需要制造。
```

### 5.2 三元组状态 + 非对易性（MetaRSI）

```text
# 2609.06396 §2.1 原文
S = (𝒟 data, θ model, 𝒽 harness)
"a change confined to any one of them changes what the deployed system does"

改进过程: U:(S, σ, B) ↦ (S̃, A, E, c)       (Eq.3)
预算 B = (β_tok, β_clk, β_gpu, β_qry) —— 四种不可互换资源

★ 非对易性显式写成公式: U_j ∘ U_i(S) ≠ U_i ∘ U_j(S)   (Eq.4)
  理由: 每个过程改不同组件, 从而改变下一个过程读到的信号。

★ 保护性测量: Q*(sealed) / 𝒯*(held-out) / release rule / 资源账本 ℒ
  全部不属于 S, 任何改进过程不可修改。
  原文理由: "without it, the quantity being maximized can be increased by
            editing the measurement."
```

### 5.3 ★ 信号新鲜度（MetaRSI Principle 4.4）——防"记忆越滚越大但记的是旧系统"

```text
搬什么: fresh(a, t+1) iff compiled(a) ≥ 最近一次 capability-altering step

DWC 接口: 每个记忆条目带 compiled_at_generation: int;
          系统有 capability_altering_step: int;
          任何 prompt/skill/记忆策略被改写后, 所有旧条目标记 stale 并降权。

★ 原文理由: "a step that changes what the deployed system does invalidates
   every signal compiled before it, because the attempts such a signal
   summarizes were made by a system that no longer exists"
```

### 5.4 落地器形态（照 `APPLIER_DESIGN.md`，此处只列与论文的接口）

```text
映射层: 对象 → 消费点声明 {consumer, path, attr, range, ★verify}
        ★ verify 是 DWC 新增 (母巢没有): 写入后读回验证
落地器: 状态机五相 cold→hold→explore→evaluating→promoted|reverted
        ★ 但窗口期改为"离线回放算完即决"(见 §6.4), 不是"等 N tick"
回滚器: 每次应用前存旧值; 回退 = 写回 + 读回确认

★ 三条纪律 (母巢用 3 次失败换来):
  1 基线与结算必须同一口径    (母巢错: base 取启动 score_in({}), current 取结束)
  2 base 打老配置, current 打新配置 (母巢错: gain = 自己减自己 = 0)
  3 打分器没分辨率时调门槛是自欺 (母巢错: min_gain 0.01→0.0005, 反而累积退化)
```

---

## 六、器官⑤：防漂移（落完之后）

### 6.1 ★ GDI 四信号漂移分解（SAHOO）

```text
# 2603.06333 Appendix B 原文 —— 四个分量全部落在 [0,1]
Δ_semantic       (1 − s_cos)/2                          Eq.8
                  s_cos = ê₀·ê_t, e = embed(y) 均值池化 hidden state
Δ_lexical        JSD(P₀‖P_t) = ½KL(P₀‖M) + ½KL(P_t‖M)   Eq.9
                  token 频率分布, 选它因为 "symmetric and bounded"
Δ_structural     (1/K)·Σ min(1, |s₀−s_t|/(s₀+ε))        Eq.10
                  s = (长度 l, 行数 n, 是否含代码块 c, …)
Δ_distributional W(P_baseline, P_current)                 Eq.11
                  1-Wasserstein, 需维护近期 response embedding 缓冲区

GDI = w_s·Δ_semantic + w_ℓ·Δ_lexical + w_st·Δ_structural + w_d·Δ_distributional
      w_s + w_ℓ + w_st + w_d = 1                        Eq.12–13

★ 关键设计 (Appendix A.2 原文):
  "drift is measured with respect to the initial model θ₀ rather than the
   immediately preceding model; this yields a cumulative measure of deviation
   and prevents short-term, high-variance cycle-to-cycle changes from masking
   long-term drift."
```

**★ 为什么这条对 DWC 特别值钱（报告原文）**：

```text
"它只需要『基线 vs 当前』的成对观测, 不需要任务真值源 ——
 这一点恰好绕过 L2 的困境 (漂移测量不是『是否成功』的判断, 不需要外部真值)。"
```

### 6.2 ★ grounded 双条件（GAI）——真值源合法性判据

```text
# 2609.13406 §2.2 原文
系统 = 五元组 χ = (π policy, V action critic, m modifier, U modification critic, ρ evaluation base)
  π  选择世界动作
  V  评估 π 表现多好
  m  提议系统应该如何改变
  U  评估提议的改动是否服务于 G
  ρ  critics 据以度量的标准

★ 一次显式五元盘点能立刻暴露 DWC 缺哪两个角色:
  π = 执行策略        ✓ 有
  V = 评估器          ✓ 有
  m = 改进器          ✗ DWC 目前为空 (承重代码 0 行)
  U = 改动评估器      ✗ ★ DWC 目前没有这个独立角色
  ρ = evaluation base  ← 这正是 "系统外的真值源是什么"

★ grounded 的双条件定义 (两个条件是 AND, 缺一不可):
  ① 内容来自系统外 (世界与目标)
  ② base 本身在 agent 外

★ 可落成一个 gate 断言: {Q*, T_seal, release_rule, ℒ} ∩ W_i = ∅ ∀i

★ Remark 2 原文 (直接命中记忆真值源难题):
  "外部 judge / reward model 不管训练在什么数据上都是 anchored;
   判别标准问的是『标准坐在哪里』, 不是『它多忠实于目标』。"
  ⇒ 不要用"评估器准不准"判断真值源合法性, 要用"评估器在不在可写面内"判断。
    一个弱评估器 + 密封 = 合法; 一个强评估器 + 在可写面内 = Goal Drift。
```

### 6.3 协同进化三条件（综述）——"这算不算真自进化"

```text
# 2608.10299 §2.2 原文
S^{t+1} = Ω(S^t, τ^t)
∃ x ≠ y ∈ S^t : x^{t+1} ≠ x^t,  y^{t+1} ≠ y^t,  x ←→(evolutionary pressure) y
★ 三条件同时成立才算 co-evolution

Stage 3 判据 (§5.1 最有价值的一段):
  "This criterion separates meta co-evolution from isolated meta-evolution.
   The mechanism revision must be induced by the joint trajectory of a
   lower-level co-evolving system and must then alter that ecosystem's
   subsequent evolutionary conditions."

★ 附录 A 原文 (减法优先的依据):
  "Designing a harness alone is not evolution"
  §7 自承: "Stage 3 只有 1 个候选"
```

### 6.4 ★ 回放仿真器（Dream-RSI）——替代影子的机制来源

```python
# 2609.14858 §2.2–2.5 原文
Discovery Tree: 根 r = 初始工作区; 每非根节点恰好一个 primary parent
  节点保存: resulting filesystem snapshot / generated artifact /
           evaluation diagnostics / score s_v

共享决策接口 (Online 与 Offline 完全共用):
  A(𝒯) = {r} ∪ {v ∈ 𝒯 : v is a leaf}
  A(𝒯; W) = { C ⊆ A(𝒯) : |C| ≤ W }      # 动作是一个批次

Online:  策略固定跑一轮, 产出新树; 历史 ℋ_t = ℋ_{t−1} ∪ {𝒯_t}
Offline: ℋ_t 固定不变; 构造并评估 M ≥ 1 个策略版本
         "每个版本在每个历史树上单独评估完毕, 才从反馈中开发下一个版本"
         完整记录的树 𝒯_i 保持固定, 只有策略可观测的部分 𝒯_i^{m,k} ⊆ 𝒯_i 在变

★ 不回退保证: 候选集必含 current ⇒ V^{m⋆} ≥ V^0 (数学结论, 非经验观察)
```

**★ DWC 最该立刻做的实验（报告原文）**：

```text
"§5.1 的负面结果直接可翻译成 DWC 的实验设计:
 DWC 现有记忆机制大概率是『把相关历史拼进 prompt』(= guidance)。
 论文证明在多线程长程搜索里, guidance 一致劣于 replay。"

实验: src/dwc/experiments/mem_guidance_vs_replay.py
  同一批记忆, A 组注入 prompt, B 组组织成 replay tree 跑同一策略, 对比下游效果
```

### 6.5 残差难度 + EL 调度器（环境进化）

```text
# 2609.04128 §2.1 原文 —— 策略无关的 off-policy 难度公式
δ_θ(z_t|g) = [ d_θ(z_t|g) − d_𝒯(z_t|g) ]₊
           = [ log(p_𝒯(σ|g)/p_θ(σ|g)) + log(p_𝒯(κ|σ,g)/p_θ(κ|σ,g)) ]₊
Δ_θ(ξ) = Σ_t [ d_θ(z_t|g) − d_𝒯(z_t|g) ]₊

★ 全文枢纽句:
  "weakness is not the difficulty of the environment itself; it is the portion
   of that trajectory that is unusually difficult for a particular model
   relative to the environment family."

三条演化方向 = 三个分量: length ← L / scenario ← −log p_𝒯(σ|g) / skill ← −log p_𝒯(κ|σ,g)

# 式 2 EL Scheduler: B=8, τ=6/8
★ 关键可迁移性: 不需要任何前沿模型, 只需要 8 次布尔观测
```

---

## 七、器官⑥⑦：探索与主体

### 7.1 三方向（Prometheus-Y / Omega，实测枚举）

```text
EvolutionDirection.FORWARD   前进 (在现有基础上改进)
EvolutionDirection.LATERAL   横向 (换一个方向试)
EvolutionDirection.REVERSE   后退 (回退到更简单的方案)

★ 39 仓库实测: 只有 Prometheus-X / Y / Omega 有方向概念。
★ 2609.04128 的三方向 (length/scenario/skill) 是"难度方向的分解", 与此不同。
```

### 7.2 自主性等级（Last AI Built by Humans）

```text
# 2609.11873 §2.3 原文
B0  In-Task AI Improvement —— 非 RSI 参考基线
    判别标准: "output change without persistent system change"
    ★ DWC 的硬判据: 关掉进程重开, 改动是否还在? 若不在, 仍是 B0。
L1  Improvement Execution Autonomy —— 人规定改什么/怎么改/什么算成功; AI 执行
L2  Improvement Strategy Autonomy —— 目标/边界/验收仍外部固定, 但 AI 诊断弱点并决定如何改进
...
★ structural L5 vs effective L5 (DWC-AUTO 验收必须区分):
  structural = 改动的机制确实控制后续一轮
  effective  = 该机制在可比预算与独立评估下产出更好后继
  原文: "Self-modifying task code provides insufficient evidence when the process
        responsible for later revisions remains unchanged."
```

---

## 八、★ 组装：进化核心的七器官骨架

```text
┌──────────────────────────────────────────────────────────────────────┐
│  DWC 进化核心                                                          │
│                                                                       │
│  ① 诊断  diagnosis/                                                   │
│     · 失败签名 (c,q,m) 精确聚类        2606.09498 + 2609.06396        │
│     · 七桶路由 (infra_only 不进化)     2609.14857                     │
│     · 四量度量 (update/activation/use/benefit)  2609.11873            │
│                                                                       │
│  ② 对象  objects/                                                     │
│     · 组件词表 𝒦 (9) + 𝒦_str (4)        2609.24972                    │
│     · 九维分类法 D1-D9                 2606.14249                     │
│     · 八 hook + singleton_group         2606.14249                    │
│                                                                       │
│  ③ 门    gates/      ★ 顺序: 测 → 判 → 落                             │
│     · 非补偿三步 + 退火预算 b_t + 信用分配 ℒ_t   2609.24972           │
│     · 双 split 接受 (Δ_in≥0 ∧ Δ_ho≥0 ∧ max>0)   2606.09498            │
│     · FGGM 契约 + 已验证 fallback               2603.25111            │
│     · drawback 检测器 (不认证正确)              2607.12790            │
│                                                                       │
│  ④ 落地  applier/                                                     │
│     · pub/priv 信号解耦 + 固定预算 b_t          2609.26457            │
│     · 三元组状态 S=(𝒟,θ,𝒽) + 非对易性 U_j∘U_i    2609.06396           │
│     · 信号新鲜度 (capability_altering_step)      2609.06396           │
│     · 消费点声明 {consumer,path,attr,range,verify}  (DWC 自定)         │
│                                                                       │
│  ⑤ 防漂移 drift/                                                      │
│     · GDI 四信号 + CAR + 回归风险 R_c^adj       2603.06333            │
│     · grounded 双条件 (ρ 在可写面外)            2609.13406            │
│     · 协同进化三条件                            2608.10299            │
│     · 回放仿真器 (候选集含 current ⇒ 不回退)    2609.14858            │
│                                                                       │
│  ⑥ 探索  search/                                                      │
│     · 残差难度 δ_θ + EL 调度器 (B=8, τ=6/8)     2609.04128            │
│     · 三方向 FORWARD/LATERAL/REVERSE            (Prometheus-Y 实测)   │
│                                                                       │
│  ⑦ 主体  agent/                                                       │
│     · 五元盘点 χ=(π,V,m,U,ρ)  ★ DWC 缺 m 和 U  2609.13406            │
│     · 自主性等级 B0→L2 + structural/effective    2609.11873           │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 九、★ 16 篇给 DWC 的四条不可违反约束

```text
约束 1 · 顺序: 测 → 判 → 落
  出处: 2606.09498 Algorithm 1 (在副本上评估, 通过才合并)
        2608.24876 Eq.9 (固定门提供外部接受边界)
        2609.26457 (pub/priv 解耦, 内环不能直接优化外环判据)
  ★ 任何"先落再测"的形态违规 —— 包括影子期/灰度/线上 A/B。

约束 2 · 判据必须在可写面之外
  出处: 2609.06396 (Q*/𝒯*/release rule/ℒ 不属于 S)
        2609.13406 (grounded 双条件: 内容来自系统外 AND base 在 agent 外)
        2607.12790 (评估器会塌缩成 always-pass, 必须环外审计)
        2606.14249 (用自己的实验证伪了自己的门: −14.0%)
  ★ 三篇独立得出, 两两互不引用 —— 这是全领域最强的一致结论。

约束 3 · 必须有两组 split
  出处: 2606.09498 (Δ_in ≥ 0 ∧ Δ_ho ≥ 0)
        2607.12790 (train/dev/test 三 split, test locked)
  ★ 只有一组 split 就没有判定"可复用改进 vs 过拟合"的能力。

约束 4 · 每轮变更数必须可归因
  出处: 2609.24972 (退火预算 b_t, 末轮 b_min = 1)
        2606.09498 (失败签名精确聚类 ⇒ 一簇对应一处干预)
  ★ "很多互不相关的修改捆成一个候选"会让任何测量无法归因。
```

---

## 十、诚实边界

```text
① 性能数字一律不采。COMPARISON.md 原文: "结构可复用, 性能数字一律不可复用"。
   DWC 的模型档位远低于论文的前沿模型, 所有 pp/% 数字零参考价值。
② 16 篇里方法级可执行的只有 2 篇 (SEVerA / GAI)。其余 14 篇是机制级可照搬。
   "机制级可照搬" ≠ "已在 DWC 验证" —— 本轮只做设计, 未写代码未跑测。
③ B 类论文 (无方差/无消融) 的机制我仍采纳, 因为它们多数是**结构性**的
   (hook 表/桶划分/预算公式), 结构性结论不依赖其实验数字。
   但凡是"某机制带来 X% 提升"这类**效果类**主张, 一律不采。
④ 跨篇冲突未裁决: HarnessX 与 Self-Harness 的门互相矛盾 (−14.0% vs 双 split),
   本设计取"并集"(两个门都要过), 但未验证并集是否真能同时满足。
⑤ 2609.04128 的 δ_θ 需要"参考分布 p_𝒯 的估计", 论文用 deep-research agent 估。
   DWC 若没有等价能力, 这一条只能退化为人工设定参考分布 —— 未解决。
```

---

## 附：存证

```text
报告: docs/papers/  (19 份逐篇 + README/COMPARISON/REPORT_SPEC/VERIFICATION)
清单: docs/RSI_PAPERS.md
脚本: scripts/extract_evo16.py
数据: .cache/evo16_core.txt  .cache/papers19_final.json
```
