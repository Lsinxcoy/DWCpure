# docs/ 目录索引

> **日期**：2026-10-04 建 · **触发**：全量核对发现 `docs/` 无索引，且 6 个子目录与 54 份顶层 .md 无导航
> **用法**：先查本文件定位，再打开对应文档。**不要通读 `docs/`**（含 4.2 MB 原始抓取产物）

---

## 一、★ 读文档的顺序（跨会话开工必读）

```text
1. docs/RESUME_2026-10-04_FINAL.md   ← 当前有效续接点（★ 旧的 EARLY/NIGHT 已过期）
2. docs/PROGRESS.md                   ← 进度表（三栏：声称/实测/取数命令）
3. ARCHITECTURE.md                    ← §1–§11；§9 是销账区，§11 是目录结构
4. docs/GAP_AUDIT.md                  ← ★ 进度依据（不是 §9 待定段）
★ docs/papers/*.md 是研究结论，不是设计依据
```

---

## 一·bis、★★ `config/` —— 已落盘两份（2026-10-04）

```text
config/iron_laws.yaml            11 条铁律（G1–G10 + G11）
                                  含 D1/D2 两条加载纪律（meta 纪律 + anti_stall）
                                  ★ G1–G10 抄自 ARSI，G11 是本项目新增
config/capability_groups.yaml    三组（沿用 ARSI category）+ Λ 计数口径
                                  ★ derived_fields 声明: lambda_floor_ratio 由 loader 重算
★ 两份均已实测通过（G1–G6 / I10–I12）；src/ 仍为空 ⇒ check_fn 全待写
```

---

## 二、★★ 核心设计文档（26 份 · DWC 的架构本体）

```text
器官设计
  ACTOR_DESIGN.md          actor 六维 / 三段式 / 决策优先级
  MEMORY_SYSTEM.md         记忆系统
  MEMORY_CONTENT.md        记忆的内容分类
  JUDGE_DESIGN.md          judge 设计
  JUDGE_LAYERS.md          judge 三层（判据 J7–J13）
  WORLD_TREE.md            世界树
  WORLD_TREE_CONVERGENCE.md  ★★ 收束裁决（两条路线 + A2 的答案）
  NO_SHADOW.md             不设影子世界
  CAUSAL_CHAIN_STORAGE.md  因果链存储
  CAUSAL_CHAIN_VS_BUS.md   因果链 vs 事件总线
  MODIFIER_CRITIC.md       m 与 U（提议/裁决分离，判据 M1–M6）
  APPLIER_DESIGN.md        落地器
  STATE_SCHEMA.md          状态 schema + PredictionOutcomePair
  ORGAN_INTERFACES.md      七器官接口（判据 P1–P8）

进化核心
  EVOLUTION_CORE_V2.md     ★ 七环节 + 12 个模块（当前主设计）
  EVOLUTION_CORE_DESIGN.md 进化核心（早期版）
  EVOLUTION_DIMENSIONS_TABLE.md  21 个权威对象清单
  COMPONENT_VOCABULARY.md  ★★ 𝒦 / 𝒦_meta（缺口 A3）
  CAPABILITY_GROUPS.md     ★★ 能力组三组 + Λ 计数口径（缺口 A6）
  TASK_SCORE_TRACKING.md   ★★ 逐任务分数序列（C3'）
  LEVEL3_PROBE.md          ★★ Level 3 三类探针（缺口 A7）
  GATE_CONFLICT.md         ★★ 跨篇门冲突裁决（门第⑦步）
  RESIDUAL_DIFFICULTY.md   ★★ δ_θ 与 p_𝒯（路线丙，缺口 §二②）
  REGRESSION_GUARD.md      保护组回归约束

守卫与质量
  IRON_LAWS_DESIGN.md      十条铁律 + ARSI 五处硬缺陷审计
  IRON_LAW_G11.md          ★★ 铁律 G11「门通过 ≠ 系统安全」（缺口 A1）
  QUALITY_GATE.md          7 道质量门
  ERROR_AND_TERM.md        ★★ 错误处理二分 + term 层级（缺口 A4/A5）
  CONSUMER_VERIFICATION.md ★★ 三级验证 + Level 3 可行性
  CLAIM_SEPARATION.md      ★★ 三主张分离 + Γ_t 裁决（第 23 项 + 25(a)(b)）
```

---

## 三、★ 分析与审计（8 份 · 结论型，非设计）

```text
  DEDUP_AUDIT_6SYSTEMS.md        六体系去重审计（九维同构实测）
  DIMENSIONS_SCOPE_V1.md         维度范围 v1
  DIMENSIONS_FEASIBILITY.md      维度可行性
  DIMENSION_REPORT.md            维度报告
  EVENT_DRIVEN_COMPARISON.md     事件驱动方案对照
  PIPE_VS_WORLDMODEL_DRIVING.md  管道 vs 世界模型驱动
  WORLD_MODEL_AS_EVENT_SOURCE.md 世界模型作为事件源
  ULTRA_NEXUS_MEMORY_PIPES.md    Ultra/Nexus 记忆管道
  EVOLUTION_CORE_AUDIT.md        进化核心审计
```

## 四、★ 缺口与进度（4 份）

```text
  GAP_AUDIT.md             ★★★ 缺口清点表（进度依据）
  FULL_AUDIT_2026-10-04.md ★ 全量核对报告（含三处自我更正）
  PROGRESS.md              ★★ 三栏进度表
  RSI_PAPERS.md            RSI 论文汇总
```

---

## 五、★★ `docs/lessons/` —— **反面案例库，不是设计依据**

> ⚠ 本目录的定位（`MOTHERNODE_LESSONS.md` 首行已自陈）：
> **"这是反面案例库，不是 DWC 的设计依据"**
> 母巢的实测事实说明"哪些坑真实存在"，**不说明 DWC 该长什么样**。
> 架构的正确来源是 **目标 + 约束 + 选择**，不是别人的失败。

```text
  lessons/MOTHERNODE_LESSONS.md      母巢实测教训（L1–L9）
  lessons/EVOLUTION_UNDERSTANDING_41REPOS.md  41 仓库演化理解
  lessons/V8PRO_TO_V9_SUBTRACTION.md  v8pro→v9 的减法
  lessons/hermes_mstar_vocabulary.md       Hermes/M★ 词表
  lessons/omega_lineage_vocabulary.md       Omega 谱系词表
  lessons/pro_evolution_vocabulary.md       PRO 演化词表

  ★ 他项目审计（198 KB · 与 DWC 设计无关，只在需要借鉴时读）
  lessons/prometheus_lineage/Prometheus-Omega-Omega.md   66,602 B
  lessons/prometheus_lineage/Prometheus-Z.md            48,784 B
  lessons/prometheus_lineage/prometheus-v11.md           45,188 B
  lessons/prometheus_lineage/Prometheus-Y.md            29,899 B
  lessons/prometheus_lineage/Prometheus-X.md             8,579 B
```

---

## 六、★★ `docs/repos/` 与 `docs/lessons/` 里的原始抓取产物（勿读）

```text
  docs/repos/_all.json        ★★ 3,564,065 B (3.4 MB)
     41 个仓库的 README/文档**全文** JSON（keys: repo / md / readme）
     ⇒ 是 corpus 抓取的原始产物, 不是设计文档
  docs/lessons/_tmp_hits.txt  ★★ 743,708 B (726 KB)
     4,345 行 grep 命中输出（1,603 个 URL, 24 处 arxiv 提及）
     ⇒ 一次性检索的原始输出

★★★ 这两个文件合计 **4.0 MB**，占 `docs/` 的绝大部分体积
⇒ ★ 它们不是文档，**不要通读**
⇒ ★ 是否删除需你定（可能是 corpus 的原始缓存，删了要重新抓）
```

---

## 七、★ 其余子目录

```text
  docs/adr/                   架构决策记录（ADR）
  docs/archive/               归档
  docs/drafts_premature_code/ 过早写的草稿代码（★ 刻意留存作为反面证据）
  docs/papers/                ★★ 30 份论文报告（研究结论，非设计依据）
```

---

## 八、诚实边界（本索引自身）

```text
① 本索引按**文件名与首段**分类，未逐份读全部 54 份 ⇒ 归类可能有误
② ★ `docs/adr/` `docs/archive/` `docs/drafts_premature_code/` 的内容未核
③ ★ 两个原始抓取产物的去留**未定**（§六）—— 我只登记，不擅自删除
④ ★★ 建索引时我**误列**了一份 `WORLD_MODEL.md`（§二 器官设计段）
   —— 实测 docs/ 顶层**没有**它（54 份清单已核）⇒ 已从 §二 删掉
   ⇒ ★ 世界模型器官的当前设计在 EVOLUTION_CORE_V2.md 内（12 个模块之一）
   ⇒ ★★ 记此: 建索引时我照记忆写了文件名, 没核 —— 与本轮第 3 条同型
⑤ 本索引不替代 PROGRESS.md（进度看它）与 GAP_AUDIT.md（缺口看它）
```

*索引 · 2026-10-04 · 覆盖 docs 顶层 54 份 + 6 个子目录 · 含两个 4 MB 原始产物的登记*