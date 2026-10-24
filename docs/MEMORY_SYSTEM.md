# DWC · 记忆系统设计（v2 · 采纳母巢七管数据链）

> 2026-10-03 · 判据：只报实测，区分设计/实现/落地
> 前版 `MEMORY_CONTENT.md` 只定了"记什么"；本版补上"怎么流转"。
> ★ 触发：用户指出"母巢的记忆系统借鉴了非常多机制，七条管道一开始都是在记忆系统上做文章"

---

## 一、母巢记忆系统实测（这是 DWC 的正面参考 + 反面教材）

### 1.1 规模：60 个文件，机制密度极高

```text
memory/ 60 个 py, facade.py 单文件 127,804 字节 (11.4 万字符)

按体积排 (前 12):
  facade              127KB  统一记忆路由入口 (薄路由层)
  mempo                48KB  Memory Policy Optimization (GRPO 记忆效用)
  four_network         35KB  4 网络认知记忆
  hela_mem             30KB  Hebbian 联想记忆 (arXiv 2604.16839)
  graph_memory         26KB  情节图记忆 + BFS
  rl_navigator         25KB  RL 策略梯度导航 HORMA
  external_notebook    23KB  外部化私有笔记本 + Lewis 信号博弈
  hierarchical_memory  21KB  HORMA 层级记忆 (arXiv 2606.11680)
  fast_ingest          21KB  Zero-LLM 12 步确定性摄入
  dopamine             19KB  多巴胺写入门
  dual_storage         17KB  逐字 + 压缩双通路
  polyphonic           16KB  多路召回融合
```

### 1.2 七管：真实在跑，44 天连续留痕

```text
七管拓扑 (DAGScheduler, v5 §13.2):
  remember → recall → learn → reflect → evolve → dream → maintain
  max_concurrent = 4

各管职责 (源码 docstring 原文):
  remember  摄入经验 → 持久化节点+边
  recall    四路融合检索 → 重力排序 (四路RRF+重力+reflect+双时间轴)
  learn     乘法门控巩固 + 贝叶斯合并 + 回写 importance
            ★ "对每条记忆做 effect×surprise 巩固, 回写 store 的 importance
               (记忆真的变'更重要'), 而非返回常量"
  reflect   失败归因 + 因果问责 (G8)
  evolve    L1-L4 变异 + NorthStar + 熔断/Lyapunov
  dream     记忆分支沙箱 + 周期反刍 + 热力学
  maintain  Weibull 遗忘 + 稀有保护 + 巩固审计 + 分级门

★ 关键设计 (原文): "管不直接调机制实现, 而是经 registry.invoke (统一接口)"
★ 生产留痕 (08-19 17:08 ~ 10-02 18:15, 44 天连续):
  feedback_log      723,902 行
  provenance_log    732,845 行  (learn 占 297,891)
  maintenance_log   313,990 行
  dream_log         147,909 行
```

**★ 结论：七管不是空壳，是真的在跑。** 这是母巢做得最扎实的一块。

### 1.3 但有两处硬失衡

#### 失衡 1 · 98.8% 的记忆从未被访问

```text
nodes 210,444 条:
  access_count = 0    207,972   ★ 98.8%
  access_count > 0      2,472   (1.2%)

★ 21 万条记忆里只有 2472 条被用过一次以上
```

#### 失衡 2 · 记忆机制 59 个，32 个零生产引用（54%）

```text
被生产引用: 27 个
零引用:     32 个

零引用清单 (含 Recuris 四件核心):
  ★ checker_set          ← Recuris 验证器集合
  ★ execution_trace      ← Recuris 结构化执行轨迹 + 失败定位器
  ★ meta_agent           ← Recuris 固定外部观察者
  ★ provenance_chain     ← Recuris 加密来源链
  activation_decay / adaptive_compression / adaptive_retrieval /
  bank_federation / bank_manager / beam_scoring / bridge / causal_recall /
  confidence_mesh / context_clash / counterfactual_replay / cross_bank_sync /
  diversity_reranker / edge_discovery / fast_ingest / feedback /
  hierarchical_memory / neighborhood_audit / retrieval_tta / scratchpad_converter
```

**★ 最要紧的一条**：Recuris 的四件核心件（`checker_set` / `execution_trace` / `meta_agent` / `provenance_chain`）**全部零引用**——它们不是坏的，是**没接线**。

#### 失衡 3 · 淘汰动作在跑，但淘汰对象是空的

```text
maintenance_log op 分布 (31.4 万):
  evict:0           83,364   ★ "淘汰 0 条"被记了 8.3 万次
  dream:25          34,624
  dream:24          26,509
  weibull_expired:50 10,990
  prune             10,840
  forget:age7d_acc0_l1  10,109

★ 淘汰规则只看 access/age, 而 98.8% 节点 access=0
  ⇒ 淘汰反复触发却无对象, 空转
```

---

## 二、DWC 采纳七管数据链（核心决定）

### 2.1 为什么采纳

```text
① 七管的数据链与两条外部路线**在动作意图上同构**
     母巢七管:  remember→recall→learn→reflect→evolve→dream→maintain
     Recuris:   Working Memory ⇄ Experiential Memory → Skill Memory 更新
   ★ 这两条收敛到同一组动作 —— 仍算强证据
   ⚠★★ 2026-10-05 R20 实测更正: 原论证第三条「ARSI 的 5 动作」**已剔除**
     ⇒ ARSI 侧只有 dream 对得上同名动作，其余五个描述与实测不符
     ⇒ ⇒ "三条收敛"降为"两条收敛"（详见 §2.3 的重写）
   ⇒★ 而这是必要的诚实: 宁可两条真证据，不要三条里有一条是错的

② 母巢七管有 44 天真实留痕, 不是空壳
③ 母巢的失败不在"链的形态", 在"链没有闭环"(写入多、读取少)
```

### 2.2 DWC 的七管（照搬形态 + 补闭环）

```text
DWC 记忆数据链 (七阶段):

  ① remember   摄入: actor 痕迹 → 节点 + 边
               ★ 必须带: 失败定位 (哪个记忆组件)
  ② recall     取回: 多路融合 + 重力排序
               ★ 判据: 取回后 access_count 必须 +1
  ③ learn      巩固: effect × surprise 乘法门控, 回写 importance
               ★ 母巢这条做对了: "记忆真的变更重要, 而非返回常量"
  ④ reflect    归因: 失败 → 失败签名 (c,q,m) + 因果问责
  ⑤ evolve     变异: 基于客观效用 → 提案 → 过门 → 应用
               ★ 这是唯一"改东西"的阶段
  ⑥ dream      反刍: 记忆重组 + 沙箱试演
  ⑦ maintain   维护: 遗忘 + 稀有保护 + 审计
               ★ 母巢在此空转 —— DWC 必须修
```

### 2.3 与 ARSI 的对应 ★★★ 2026-10-05 全文重写（R20 · 逐个核实 E:/ARSI 源码）

```text
★★★ 这张表初版（2026-10-04）**6 行里 5 行不准**。
   实测依据: E:/ARSI/src/arsi/ 286 个 py，按**定义处**（def/class）逐动作定位，
   不按文件名、不按文档转述。

DWC 七管 | ARSI 实际形态（实测）                        | 初版写的
remember  | memory_proxy.py:60 有完整实现                | ★ "空操作" —— 错
          | 写 PROXY zone + native 备份                  |
recall    | memory_proxy.py:58 有 recall(query, k=5)      | ★★★ "无独立召回阶段"
          | NativeMemory Protocol 与 NullNativeMemory     |   —— 大错
          | 也各有一份                                  |
learn     | def learn* 定义点 = **0**                     | ★ "真实现" —— 无同名动作
          | 实际形态 = consolidation(41) + distill(53)    |
evolve    | world_model/world_evolver.py 380 行           | ★★ "占位符" —— 错
          | ×3 个 def evolve*                            |
dream     | pipelines/dream.py 359 行（5 阶段）           | ✓ 对
          | + world_model/continuous_dream.py 263 行      |
maintain  | def maintain* 定义点 = **0**                  | ★ "真实现" —— 无同名动作
          | 实际形态 = prune(19) / UtilityDecay / forget  |
```

```text
★★★ 修正后的结论（这是 R20 唯一能确定的事）
① ★ **"三方同构"不成立** —— ARSI 侧只有 dream 对得上同名动作，
   其余五个要么不存在同名动作、要么形态与初版描述相反
② ★⇒ 因此"ARSI 5 动作"这个提法要谨慎:
   ARSI 不是"五动作系统"，而是**按子系统切分的工程实现**
   （mnemosyne 记忆 / world_model 演化 / pipelines 梦 / harness 门与账）
③ ★★ DWC 采用七管的结论**不变**，但依据换成可核的两条:
   a) 母巢七管有 44 天真实留痕，且**失败点已被定位**:
      写入多、读取少（98.8% access=0）⇒ 要修的是闭环，不是形态
   b) Recuris 的 EM→WM→Skill 耦合同构（这条独立成立）
④ ★★★ ARSI 真正值得 DWC 学的，**不是"五动作"，是它的一处设计**:
   `mnemosyne.core.should_consolidate` = `record.importance >= threshold`
   ⇒ ★★ 纯自评阈值，**无 access 参与**
   ⇒⇒ 而 D7 判据是"无 access 记录不得当作有价值"
   ⇒⇒ ⇒★ 母巢的病 = 写进去没人读（access=0）
       ARSI 的病 = 读了但没留痕，价值由 importance 自评说了算
       两者的交集正是 D7 要修的那个
⑤ ★★ ARSI 的三区实测 = SELF / EXPERIENCE / PROXY
   （mnemosyne/core.py docstring 原文）
   ⇒ 与 DWC 的 EXPERIENCE / PROXY / ARCHIVE / INERT **名字撞两个，
     但不是同一个东西**（DWC 无 SELF，多了 ARCHIVE/INERT）
```

```text
⚠★★ 本节的诚实边界
① 只核了 src/arsi/（286 个 py）；scripts/ 下 32 个 py 未逐一核
② "同名动作 = 0" 的判据是 `def\s+learn\w*\s*\(` 这类正则；
   若它以别名或变量形式存在，本节结论需再修
③ ★★ R19 的 Q1 裁决（选七管）当时用的正是这张错误的表
   ⇒ 依据作废、结论保留，已按 §六 Q1 的更正记录重述依据
```


---

## 三、三条修法（针对母巢的三处失衡）

### 修法 1 · 记忆必须有"被使用"的证据

```text
母巢: 98.8% 节点 access_count = 0
DWC 判据: 一条记忆若在 N 轮内 access_count 仍为 0 ⇒ 它是死记忆

★ 但"死记忆"不等于"该删" —— 要先分类:
  甲 从未被召回   → 检索策略问题 (recall 管要修)
  乙 被召回但未用 → 价值判断问题 (learn 管要修)
  丙 确实无用     → 该淘汰

★ DWC 的 maintain 必须区分这三类, 不能像母巢那样一律 evict
```

### 修法 2 · 机制必须接线（零引用 = 不许存在）

```text
母巢: 32/59 记忆机制零生产引用 (54%)

DWC 纪律: 任何记忆机制, 若在实现后 N 轮内零调用 ⇒ 门报红
  ★ 判据可机械检查: 该模块被 import 次数 = 0 且 被 invoke 次数 = 0
  ★ 这条与 DWC 原则 4 (产物必须有运行时消费点) 同源

★ 特别地: Recuris 四件 (checker_set / execution_trace /
  meta_agent / provenance_chain) 在母巢零引用 —— 
  DWC 要么接线, 要么不实现。不许"实现了放着"。
```

### 修法 3 · 淘汰规则必须基于"价值"而非"年龄"

```text
母巢: evict:0 触发 83,364 次 —— 淘汰规则只看 access/age,
      而 98.8% 节点 access=0 ⇒ 无对象可淘汰, 空转

DWC 的淘汰判据 (三层, 顺序不可换):
  1) 是否曾被召回? (access_count > 0)
     否 ⇒ 进"未验证区", 不淘汰 (可能是检索策略问题)
  2) 被召回后是否改变过行为? (有 effect 记录)
     否 ⇒ 候选淘汰
  3) 淘汰前必须过"稀有保护":
     若该记忆是某类失败的唯一签名 ⇒ 不淘汰

★ 依据: ARSI 的 UtilityDecay "忘掉无用的, 不是忘掉旧的"
```

---

## 四、记什么（前版结论保留 + 补七管归属）

| 内容 | 存在哪管产生 | 存哪个区 | 判据 |
|---|---|---|---|
| 任务痕迹 | remember | PROXY | 必须带失败定位 |
| 失败签名 (c,q,m) | reflect | EXPERIENCE | 按三元组精确聚类 |
| 技能 (场景/方法/边界) | learn 归纳 | EXPERIENCE | ★ 进化的直接对象 |
| 工作态 𝒲 | remember | PROXY 特例 | 必须结构化 |
| 进化提案 + 结果 | evolve | EXPERIENCE | 必须带消费点声明 |

**明确不记的**：纯事实 / 纯概念 / 机械日志 / 自我评价。

---

## 五、新增原则

```text
D6 · EXPERIENCE 只存"能驱动进化的东西"
  判据: 这条记忆能否成为 evolver 的输入?
  不能 ⇒ 留在 PROXY 或归档区, 不占 EXPERIENCE

D7 · 记忆必须证明"被使用"（★ 本版新增）
  一条记忆若无 access 记录, 不得被当作"有价值"。
  依据: 母巢 98.8% 节点 access_count=0, 但 importance 均值 0.747
        —— 自评很高, 实际没人用。这是"自评 ≠ 实测"的记忆版。

D8 · 机制零引用即违规（★ 本版新增）
  任何机制若在 N 轮内零调用, 门报红。
  依据: 母巢 32/59 记忆机制零引用, 含 Recuris 四件核心。
```

---

## 六、已裁决（原「待你拍板」· 2026-10-05 决策）

```text
Q1 七管形态 → ★★ 甲（照母巢七管，补 recall/reflect 闭环）
   ★★★ 2026-10-05 R20 更正依据（结论不变，依据全换）:
      原依据①②③ 建立在 §2.3 那张表上，而该表实测 5/6 行不准 ⇒ 全部作废
   现行依据（每条可核）:
   ① ★ 母巢有 **44 天真实留痕**，且失败点已定位: 写入多、读取少
      （98.8% access_count=0）⇒ 要修的是**闭环**，不是形态
      ⇒⇒ 任何"更简的动作集"都不解决闭环问题
   ② ★ Recuris 的 EM ⇄ WM → Skill 更新 与七管同构
      （独立证据，不依赖 ARSI 那张错表）
   ③ ★★ D7（记忆必须证明被使用）要求 recall 必须留下 access 痕迹。
      实测 ARSI `mnemosyne/core.py` 里 recall / last_used / used_count
      命中均为 **0** ⇒⇒ 无论动作集是五个还是七个，
      **不留痕就执行不了 D7**
      ⇒⇒ 这才是"补 recall/reflect"的真实理由，与 ARSI 有几个动作无关
   ⚠ 原依据①"选乙（ARSI 五动作）等于复制那个病"**已作废** ——
     ARSI 有 recall（memory_proxy.py:58），初版说它没有是错的
   ⇒ 落地: Tube 枚举保留 REMEMBER/LEARN/EVOLVE/MAINTAIN/REFLECT 五类
     （实测写链的五环只用前三个；recall/reflect 是**读侧与归纳侧**，
      已在 MemoryKernel.recall() / by_signature() 落地）

Q2 "死记忆"判据的 N → ★★★ 丙（按 term 计，且必须由 term 边界推导）
   ★★★ 这不是三选一里的偏好题，是**唯一与已定设计相容的选项**:
   ARCHITECTURE 原则 8 原文写着「N = **未定义**，且**不可给默认值**
   （与 K4 / G11 同款纪律）」「★ N 应由 term 边界推导（ERROR_AND_TERM
   已定 term 边界由进化事件决定），而不是拍一个固定轮数」
   ⇒ 而 ERROR_AND_TERM §2.3 已定四个 term 终止条件
     （七环节跑通 / 预算耗尽 / 保护组回归 / 停止规则命中）
   ⇒ ⇒ 选项甲（10 轮）、乙（20 轮）**都违反原则 8 的"不可给默认值"**
     ⇒ ★ 原选项表把正确答案设成了陷阱（它自己矛盾）
   ⇒ 落地: config/retention.yaml 的 dead_after_terms 必填无默认；
     实现 D8 时按 term 计数，不按 step

Q3 淘汰三层判据 → ★ 甲（照用 §3 修法 3，三层顺序不可换）
   依据:
   ① 三层的顺序本身就是判据: 未召回 ≠ 淘汰（可能是检索策略问题），
      召回过但没改变行为才是候选 —— 简掉任何一层都会误杀
   ② 第三层"稀有保护"是**独立的硬否决**，不是加权项 ⇒ 不能简化
   ③ 已落地并有 27 项测试（eviction_candidates 只出证据不删）
```

---

## 七、R审计-P2 · 记忆强化落地记录（2026-10-24）

> 触发: 用户问「其它项目里找 DWCPURE 记忆系统强化方向」。对照 Prometheus-X /
> Prometheus-Ultra-MultiTypeKB 实测（只借真接线部分，不抄设计文档）后执行 P0-P2。

### 7.1 修了什么（按优先级）

| 项 | 内容 | 落地位置 | 验证 |
|---|---|---|---|
| P0-1/2 | failure_sig 补 `scene`（judge.anchors 的 prompt 原文）+ `detail`（verdict.reason + diffs） | `loop.py:_remember_failure` / `run_term.py:_backfill_failures` | test_memory_p0 |
| P0-3 | maintain 接线（24h 防抖 + 台账） | `dwc_agent.py:_maybe_maintain` | test_memory_p0 |
| P0-4 | MemoryKernel.dream 接 evo_round（失败聚簇→技能候选） | `dwc_evo_round.py` 尾部 | 真跑输出 |
| P1-5 | FTS5 trigram 全文索引（external content + 三 trigger） | `memory.py` SCHEMA + recall 路1 | test_memory_p1 |
| P1-6 | Weibull 保留度做排序权重（**不做淘汰**） | `memory.py:retention_of` | test_memory_p1 |
| P2-7 | learn 管（乘法门控 → 回写 importance） | `memory.py:learn` | test_memory_p2 |
| P2-8 | MMR 多样性重排 + 4-tier 语义档位 | `memory.py:_mmr_rerank` / `tier_of` | test_memory_p2 |

### 7.2 实测数据（改前 → 改后）

```text
失败签名召回: 129 条中 8 条被访问（6.2%）
  → 存量 131 条里 66 条补上 scene（anchors 反查, 65 条任务 ID 不在 anchors ⇒ 留空不编）
  → 完整任务文本召回: 命中 3 条（同任务历史失败可召回）
  → ASCII 快查 sum_first_n: 命中 5 条（FTS）

七管接线: remember ✅ / recall ✅ / reflect ✅ / evolve ✅ / dream ✅(P0-4) /
         learn ✅(P2-7) / maintain ✅(P0-3)  ← 此前 learn 不存在、maintain/dream 零调用
```

### 7.3 诚实边界（不夸大）

- **FTS5 trigram 对中文的局限**: 中文无分词 ⇒ 短语查询要求连续子串
  ⇒ 中文查询仍走 SQL LIKE（语义与旧实现等价）；FTS 只加速纯 ASCII/标识符。
  真正的语义召回需要 embedding —— DWC 目前**不引入模型依赖**，标注为未做。
- **learn 参数未校准**: β=0.1 / τ=0.3 是借 Prometheus-X 的初值，
  DWC 无实测支撑 ⇒ 返回值带 `params_status: initial_uncalibrated`。
- **MMR λ=0.7**: 论文标准取值，同样标为初值；相似度用 2-gram Jaccard 近似。
- **4-tier 不存列**: tier 由 kind 纯函数推导，避免与 WEIBULL_BY_KIND 冗余。
