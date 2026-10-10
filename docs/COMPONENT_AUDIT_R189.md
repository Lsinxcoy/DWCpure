# 组件对账表 · A 步交付物（R189 — 用户指令 A-B-C 逐步推进的第一枚）

日期: 2026-10-12 · 方法: **机器**扫 docs/EVOLUTION_CORE_V2.md L621-666 组件树（`[├└]` 两前缀都抓）+ 符号级 grep（def/class/真实字段名）。散文叙述不算数，一切以机扫表为准。

---

## 一、机械计数（终值）

```text
树点名独立组件: 26（机扫树块, 含 └ 前缀 — 首版只抓 ├ ⇒ 漏 3 个, 已修）
已有独立文件 : 12（router/dimension/hook/leakage/contract/drawback/noncomp/budget/weakness/el_sched/replay/direction）
缺独立文件  : 14
判决分布     : EMBEDDED 2 · PARTIAL 2 · ABSENT 10
```

**机器判决表**（终值，逐行可验；修订记录: §一 首版只抓 `├` 漏了 `└` 行 ⇒ 11→14, 已在 §一 注明）:

| 组件 | 判决 | 证据（符号级 grep, def/class/真实字段名） |
|---|---|---|
| signature | **EMBEDDED** | `weakness.py:118 def z_id_from_signature` + `judge.py` `failure_signature` 字段 + `core.py:247` ingest 不变量**真代码**校验 |
| grounded | **EMBEDDED** | `leakage.py` ρ 读写分离检查 + `foundation/dial_config.py:173` G10+grounded 条件② 校验在跑 |
| gdi | **PARTIAL** | `foundation/causal_chain.py:72 gdi_snapshot REAL` 是真 DB 列（存储面在），但 `(def\|class)(Gdi\|GDI\|Drift)` **0 hits** ⇒ **无四信号计算函数** |
| split | **PARTIAL** | `harness/gates.py:188 def _g4_split` 在场（门④真在跑），但论文的 **Δ_in/Δ_ho 双 split 接受**只是 `evolver.py:2015` 的 inline 片段 ⇒ 有行为、无独立组件 |
| vocab | **ABSENT** | `(def\|class)(Vocab\|K_str)` **0 hits**；𝒦(9)+𝒦_str(4) 只在 `evolver.py:58` 注释里被引用 |
| dual | **ABSENT** | `pub_priv\|private_ctx\|PUBLIC_` **0 hits** |
| budget_ledger | **ABSENT** | `(def\|class)(BudgetLedger\|four_resource)` **0 hits** |
| state | **ABSENT** | `non_commut\|three_tuple` **0 hits** |
| freshness | **ABSENT** | `(def\|class)Freshness` **0 hits** |
| granularity | **ABSENT** | `(def\|class)(Granularit\|turn_boundary)` **0 hits** |
| consume | **ABSENT** | `(def\|class)(Consume\|consumer_decl)` **0 hits** |
| coupling | **ABSENT** | `(def\|class)(Coupling\|co_evolution)` **0 hits** |
| quintuple | **ABSENT** | `(def\|class)Quintuple` **0 hits** |
| autonomy | **ABSENT** | `(def\|class)(Autonomy\|autonomy_level)` **0 hits** |

---

## 二、FILE_EXISTS 12 个（机器列 — organs 37 + harness 11 目录实扫）

▸ 本节只声明"机器扫的, 没手抄"。

---

## 三、10 个 ABSENT 的逐个理由（R73 纪律：每条都要有据，不是懒）

| 组件 | 未做原因（可判定的设计事实） |
|---|---|
| vocab (𝒦9+𝒦_str4) | 2609.24972 的词表在 DWC 的对应物是 `dimension.py`(九维 D1-D9)+`evolver.py:58` 的 𝒦_meta(5 项) —— **离散实现已散在两处, 未收口成 𝒦(9)**。这不是"没做"是"未收口" |
| dual (pub/priv) | DWC 单机单主体, 无 pub/priv 双信号场景; 论文 2609.26457 的前提是多主体共享 |
| budget_ledger (四资源) | `budget.py` 的退Annealing b_t+ℒ_t 是**另一种**预算形态（信用分配, 非固定四资源）——两者设计目的不同, 未合并且未二选一裁决 |
| state (三元组非对易) | 2609.06396 的 S=(𝒟,θ,𝒽) 在 DWC 没有对应物（dev/test 双 split 不是 𝒟/θ/𝒽）⇒ 需要设计映射, 无据不发明 |
| freshness (capability_altering) | 依赖上面的 state 面（信号新鲜度是对 S 的量化）⇒ state 未做则 freshness 无锚 |
| granularity (三层+turn_boundary) | 2609.08183 的粒度概念与 DWC 的 candidate 树重叠（R177 candidates 已有层级）⇒ 需先判"复用 vs 新造" |
| consume (消费点声明) | 记账 schema 非判定逻辑; DWC 现有 `_last_skip`/ledger 已是事实上的消费点记录, 但未按 {consumer,path,attr,range,verify} 五元组显式化 |
| coupling (协同进化三条件) | 2608.10299 的三条件针对**多机制**协同; DWC 当前单链（dev→train + 单 Metric Loop）⇒ 无协同对象 |
| quintuple (χ=π,V,m,U,ρ) | 2609.13406 的五元是**主体自省框架**; DWC 从未声明主体五元 ⇒ 属⑦agent 大件, 非补丁级 |
| autonomy (B0→L2) | 自主性等级**需要外部裁决**（用户侧定级）, 已在多处纪律记录"未定级" |

---

## 四、Comments-as-implementation 审计（本步最重要的副产物）

`src/dwc/core.py`（690 行 / 17 def）里, 有 **多个组件的中文名/论文号只出现在注释里**——R73/R186/R187 已在 direction 上栽过"注释里有≠代码在跑"。逐个机器判:

| 词 | core.py 命中性质 | 判决 |
|---|---|---|
| failure_signature | L247/249 **真代码**（ingest 不变量校验失败抛错） | ✓ 真在跑 |
| `gdi` / `grounded` / `quintuple` / `VOCABULARY` 等 | **全在 docstring/注释里**（L230/367/370 也是取字段不是定义） | ✗ 注释冒充风险 |

**纪律补丁**（写回 PROGRESS.md §9）: 任何架构文档里"X 已实现"的声明, 必须能回答"宿主文件:行号 + 符号名"——答不出就是注释, 不算数。（这正是 MEMORY 里"目录罗列会被当场驳回'没实际分析代码'"的机制化成表。）

---

## 五、A 步结论 + 交给 B 步的输入

1. **不需要补 14 个文件**：2 EMBEDDED（收口即可）、2 PARTIAL（补计算/组件面）、10 ABSENT 有据未做。
2. **本步不改代码**（纯审计, R189 的一部分）。
3. **B 步输入**: A_train 退化根因是集合太小（train.json 6 条, 其中 behavior 3 条在真无标签面）, 与组件对账无关 ⇒ B 步独立推进。
4. **留给用户拍板的两件**（不阻塞 B/C, 下轮再问）: ① budget_ledger vs budget.py 是否统一（设计二选一） ② granularity 复用候选树 vs 新造
