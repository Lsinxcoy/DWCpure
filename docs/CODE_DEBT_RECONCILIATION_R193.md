# 代码债务总清算（R193 — 用户令"究竟有多少代码债务 哪些真实存在 哪些是你的误判"）

日期: 2026-10-12 · 前置: R190 对账（14 项）· R192 规划（A/B/C/D 分级）
**方法**：不复用 R189/R192 的结论，**逐项重新 grep + 打开文件核行号**。下面每一行都可复跑。

---

## 零、总账（先给数字）

```text
R189 对账表列了 14 项"缺/半缺"  →  逐项机器复核后：
  R189 判错（把已实现判成缺）      : 2 项   ← gdi / split
  R189 判半错（缺一部分说成全缺）   : 2 项   ← consume / vocab
  真实存在且未做                   : 6 项   ← dual/state/freshness/coupling/quintuple/autonomy
  不是代码债（设计未到/单主体无关） : 6 项
  本轮取证的**新债**（R189 没列）   : 1 项   ← dev 面 diff 投影层断裂
```

**⇒ 真实代码债务 = 6 项未做 + 1 项新债 = 7 项；但其中 5 项"需要设计输入"而不是"缺代码"。**

---

## 一、我的误判（4 项 — 逐条认）

### 误判① gdi「无四信号计算函数」——**错得最实的一个**

| R189 判 | 实测 |
|---|---|
| "`(def\|class)(Gdi\|GDI\|Drift)` **0 hits** ⇒ 无四信号计算函数" | `iwm.py` **482 行专做这件事**：`IwmOrgan.drift()`（L~430）+ 四个信号函数全在 |

```text
src/dwc/organs/iwm.py
  L99  semantic_delta(e0, e1)          ← 四信号之一
  L113 _normalize(freq)
  L120 lexical_delta(p0, pt)            ← 四信号之二
  L143 structural_delta(s0, st)         ← 四信号之三
  L160 distributional_delta(xs, ys)     ← 四信号之四
  class IwmOrgan: drift() / grounded() / record_round() / self_trust() / governor_advice() / probe()
```

**我错在哪**：grep 只搜了 `(def|class)(Gdi|GDI|Drift)` **函数名**，而实现用的是**信号名**（`semantic_delta` 等）。**"函数名不含关键词"≠"没实现"**——这正是 MEMORY 里"挂载点必验词法归属(AST)查字符串≠会跑"的反面：**查字符串也得查对字符串**。

**接线也真的在**（R189 连这个也没核）：
```text
core.py:165   self.iwm = IwmOrgan(baseline=...)
core.py:206   TermRunner(..., iwm=self.iwm, ...)    ← 生产注入
run_term.py:446 rep.drift = self.iwm.drift(self._drift_current())   ← 真调用
dial_config.py:254 load_drift()（Σweights==1 硬校验, tau_gdi∈(0,1]）   ← 配置面在
```

**残留真债（小）**：`semantic_delta` 缺嵌入源 ⇒ 该信号缺席（函数已实现、probe 覆盖、缺数据源——docstring 已如实标注"权重运行期归一到其余三路"）。**这是数据源债不是算法债。**

### 误判② split「Δ_in/Δ_ho 只是 evolver.py:2015 inline 片段」——同款错

| R189 判 | 实测 |
|---|---|
| "有行为、无独立组件" | `Evolver.accept()` **L1969 起的完整 staticmethod**，R27 打磨过三代 |

```text
evolver.py:1969    def accept(p, baseline, current, eps=0.0)
  判据 2606.09498 Alg.1 L13 逐字: Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧ max(...) > 0
  R27 实修: 原签名收两个数, 语义自相矛盾 ⇒ 改成收两份判分、增量自己算
  ho 缺席 ⇒ blocked（不许只凭 in-sample 采纳 — 2606.14249: 只用一组 −14.0%）
  gates.py:188 _g4_split 门④在跑（链级真消费）
```

**我错在哪**：看到 "2015 行附近有 inline 片段" 就判"没有独立函数"——**没往上找宿主 def**。教训：grep 命中行必须**向上滚动到宿主函数**再判。

**残留真债（小）**：门④（`_g4_split`）与 `Evolver.accept` 是**两份 split 逻辑**（的功能重叠）——R189 想说的"无单一真源"才是真问题，只是位置说错了。

### 半错③ consume「未按五元组显式化」

实测：五元组 schema **在场**——
```text
applier.py:75  TARGETS = {"mutation_rule": {"consumer","path","attr","verify"}}   ← 五字段齐
```
但只登记 **1 个**消费点（mutation_rule）。`loop._last_skip` / `_dir_ledger_append` / `_last_metric_pick` 等**事实消费点未登记**。
⇒ **不是 ABSENT，是"登记覆盖 1/N"**。

### 半错④ vocab「两处离散未收口」

实测：文档真源在（`docs/COMPONENT_VOCABULARY.md` 462 行）、代码两张表：
```text
evolver.py:50  COMPONENT = frozenset(9 项)     ← 𝒦(9)
evolver.py:58+ K_META = {5 项, 每项 editable}   ← 𝒦_meta
```
⇒ R189 说"两处"对。**但 R189 把 `dimension.py` 九维也算作词表散点——那是误认**：`DIMENSIONS` 是**模块声明维度**（ModuleDeclaration / declares_valid_hook / find_conflicts），与 RRSI 𝒦 组件词表**不同物**。收口时不能把它并进去（R189 的"三处"含一个假的）。

---

## 二、真实存在的债务（7 项，按"是否缺代码"分两类）

### 类 X：缺代码，且**不需要设计输入**（我能直接做）

| # | 债 | 证据 | 工作量 |
|---|---|---|---|
| **X1** | **dev 面 diff 投影层断裂** | 29 条 dev facts 上 6 op 中 5 个全 abstain；`evidence.jsonl` 条条有 `diffs` 字段（49/49），`_facts_from_dev_surface` 却因 R180 旧注释填 None | 小（纯投影函数） |
| **X2** | split 双实现无单一真源 | `Evolver.accept`（L1969）与 `gates._g4_split`（L188）各写一份 | 小（抽公共函数，两处改调） |
| **X3** | consume 登记覆盖 1/N | applier.TARGETS 只 1 条；loop 的事实消费点（_last_skip/_dir_ledger/_last_metric_pick/_last_replay_pick/_last_a_train）零登记 | 小（补表 + 4 处登记） |
| **X4** | 𝒦(9)/𝒦_meta 无代码层单一入口 | 两个 frozenset/dict 在 evolver.py 内并列，外层文档是唯一汇总面 | 小（建 vocabulary.py 薄封装，**值一字不动**） |

### 类 Y：缺代码，但**卡在设计输入**（不是我能单方面定的）

| # | 债 | 卡在哪 |
|---|---|---|
| **Y1** | budget_ledger vs budget.py | `credit.py` CreditLedger（归因 ℒ_t，论文 2609.24972 §3.3）与 `budget.py`（退火 b_t，式4）**是两个不同论文机制、两个不同门**——R189 说"未二选一裁决"，实测**它们其实不对立**（一个管归因记账、一个管预算约束）⇒ **可能根本不存在"二选一"，是我 R189 自己造的岔路** |
| **Y2** | granularity 三层树 | Astar 给了 L1/L2/L3 名字，**类别表论文没给**；DWC 已有 `mechanical_candidates` 两层候选树 |
| **Y3** | EvoTS 停滞只对 Revision | 论文公式 `z_k ← (op=Revision) ∧ …`；DWC `stagnant_of` 三方向一视同仁 |

## 三之二、Y1 结案（R193 — **"二选一"是我 R189 造的岔路**）

机器证据（两文件 docstring 原文）:

```text
credit.py  : "证据感知信用分配 ℒ_t（2609.24972 §3.3 正则器(2)）…
             每轮把候选的编辑 i、层级 ℓ_i、hunk h_i、维度 d_i、收益 ΔS_i、
             成本 ΔC_i、以及采纳标志 a_i 记成一笔"
budget.py  : "退火编辑预算 b_t（2609.24972 式 4 · 设计稿门⑥「归因粒度」）…
             约束本轮可**独立归因**的编辑数 b_t（cos 退火）"
```

⇒ **两者是同一论文的两个不同机制、服务两个不同门**：
`ℒ_t` 记"这笔编辑赚了多少"（**归因**，横向记账）,
`b_t` 限"本轮最多几笔"（**预算**，纵向约束）。
R189 把它们列成"budget_ledger vs budget.py 二选一"是**把不同物当成互斥项**—

同一个错误在 R189 犯过两次（另一次是把 dimension.py 当词表散点）。

**结案三条**（写入本文即生效, 无代码改动）:
1. `CreditLedger`（organs/credit.py）= **归因台账** ⇒ 组件树里的 `budget_ledger`
   对应物**就是它, 不缺文件**（R189 判 ABSENT 是错判的文件级表现）。
2. `budget.py` = **退火预算约束** ⇒ 对应组件树里 `budget`（FILE_EXISTS 12 之一）。
3. **无需二选一, 也无需统一** — 但要防的是第三态: 将来若有人想加"固定四资源
   台账", 必须先裁决它与 ℒ_t 的分工, **不许并列两套**（这正是 R189 担心的
   真问题, 只是位置说错了）。

### 类 Z：有据不做（不是债，是"设计没到/前提不成立"）

| 组件 | 为什么不是债 |
|---|---|
| dual (pub/priv) | DWC 单机单主体，论文前提是多主体 |
| state (𝒟,θ,𝒽) | 2609.06396 三元组在 DWC 无对应物，强映射=发明 |
| freshness | 依附 state，state 无则无锚 |
| coupling | 单链无协同对象（2608.10299 三条件是**多机制**前提） |
| quintuple | run_term.py:458 已有 `Quintet(m,rho,pi,V,U)` 盘点面（R141，如实标 partial）——**不是零，是 partial** |
| autonomy | 需用户外部裁决定级 |

---

## 二之一、Y2/Y3 结案（R195 — 用户令"你来深度思考 做出最好的决策"）

### Y2 granularity — **不新造, 收口成查询面**（R189 第二次同款误判修正）

R189 判 ABSENT 的依据是 `(def|class)(Granularit|turn_boundary)` 0 hits。实测：**三层一直在场**，
只是散在 `Proposal` 字段里（没有一个叫 granularity 的函数而已）:

```text
L1 = Proposal.direction            （R78 加 · ensure_direction 校验 · R188 补控制器）
L2 = Proposal.component + target_layer（A1 唯一入口 check_component · layer_of — R38 逐项）
L3 = Proposal.target + patch       （约束 4: 一处干预）
```

与 Astar 2608.27287 §2.2.1 三级 taxonomy（Coarse-Grained Direction / Fine-Grained Action /
Concrete Plan）**逐层同构**。⇒ 落地 `foundation/granularity.py`：**零常量、零新判据、纯查询**
（`granularity_of` / `level_of` / `is_coarser` / `coarsest`）。诚实边界: Astar 全文**未给完整
类别表**（只一个 MoE 实例）⇒ DWC 不虚构类别枚举。

### Y3 停滞只对前进类 — **R192 的"风险>收益"预估错了, 如实记账**

R192 写"默认不动 — 改它=动已绿链行为"。实测 grep 全库: **`stagnant_of` 生产调用数 = 0**
（只有 tests/r188 用）; `next_action` 用的是 `tried_all`（"试过"≠"停滞"）⇒ 不动链条。
⇒ 它是一个**已定义已测试却从未被消费**的判据函数, 改它 = 纯判据面对齐论文, 零链行为变更。

落地: `stagnant_of` 加 `direction == FORWARD` 前提（EvoTS 2608.17933 §4.2 L20 逐字:
`z_k ← (op=Revision) ∧ (q_k invalid ∨ q_k−q_prev ≤ ϵ)`）。LATERAL/REVERSE 失败 =
"该方向本身失败", **不记停滞**（对应 EvoTS 的 Alternative Strategy — 被停滞触发的算子,
它自己失败不是停滞）。测试锁 `next_action` 仍把 LATERAL 计入 tried_all（不回退不循环）
+ `test_zero_production_call_sites_for_stagnant_of` 防将来接线时忘重评。

### 两次误判的共同根因（第三次不会再栽）

**用函数名 grep 代替打开文件**。gdi/split（R189）与 granularity（R195）三次同款。
纪律已固化: 判"有没有"必须答出**宿主文件:行号 + 符号名**（不是关键词命中数）。

## 三、对用户问题的正面回答

> **「究竟有多少代码债务」**：**4 项能直接做**（X1–X4，都是小手术，不碰判据语义）；**3 项等你裁定**（Y1 可能是我造的岔路、Y2 要定类别表、Y3 默认不动）。

> **「哪些是你的误判」**：**4 项**——gdi 与 split 是**确凿误判**（已实现已接线，我 grep 搜错了字符串/没找宿主函数）；consume 与 vocab-dimension 是**半错**（把 partial 说成 absent、把不同物当同物）。

> **「误判为什么发生」**：两次都栽在同一个模式——**用函数名 grep 代替打开文件**。R189 的对账表我标称"符号级 grep（不靠关键词猜）"，实际执行的却是**用关键词猜函数名**。这条已进 MEMORY 的"挂载点必验词法归属"纪律的反面（查字符串也得查对字符串 + 命中行必须回溯宿主函数）。

---

## 四、建议的施工序（等你一句）

```text
R193: X1（dev 面投影层）— 立刻改善回归面信号密度 29 facts 上 5/6 op 从 abstain 变有判
R194: X2 + X3（split 真源收敛 + consume 登记补齐）
R195: X4（vocabulary 收口）+ Y1 结案（我判"非二选一", 你认了就写进设计文档结案）
R196: Y2/Y3 档案化（结论 + 默认不动的原因）
```

**每批完成定义不变**：改前改后机器对比 + pytest 全量 + gate 8/8 + e2e rc=0 + 知识档 + README 自洽。
