# DWC 架构 v2 · 参照 ARSI 骨架

> 状态：**重写版**（2026-10-03）。v1 的问题：它是一份"评判系统"的架构，不是 agent 的架构
> —— 没有行动者、原则 4 证据被推翻、借了母巢空转的部件。
> 本版参照 **ARSI 的真实骨架**（不是它的 README），补上行动者。
> 日期：2026-10-03

---

## 一、v1 的四处硬伤（先认账）

```text
① 原则 4 的证据是假的
   写: "七个 arm 各有真实记录, 不是摆设"
   实测: op 只有 1 个值('evolve'×57,122); hypothesis 是 tick 计数器;
        母巢自己注释"32816 条全同质(无区分度)"; eval_driven distinct=1

② 架构里没有行动者
   关键词扫描: 执行 0 次 / 循环 0 次 / step 0 次 / 行动者 0 次
   ⇒ DWC 是 agent, 但架构里没有"谁在做任务"

③ 原则 1/2/3 的因果关系是编的
   写: "原则 2 由原则 1 直接导出"
   实际: 原则 2 的来源是"评分器会塌缩"(2607.12790), 与"养料来自记忆"无关

④ 借了母巢空转的部件
   引用 RSPL/SEPL/HORIZON, 而这些正是 gene_applier 自述
   "进化产物无处落地"的那套, 引用时未标注它的落地是失败的
```

---

## 二、DWC 骨架（参照 ARSI 的 `ARSI` 主类 + `step()`）

### 2.1 ARSI 的真实骨架（我读到的）

```python
class ARSI:
    """One object that owns everything."""
    # 持有 8 个核心器官
    store / mnemosyne / siwm / governor / empowerment / dream / iron_laws / llm

    # 三个入口
    ingest_trace(...)    # 宿主轨迹 → 记忆
    step()               # 一次完整决策+执行循环
    run_term(n_steps)    # 一个完整改进周期(含评估+成本+增益分解)

    # 三层决策
    pre_enactment(confidence>0.1) → LLM → 启发式
    # 五个候选动作
    ["dream", "learn", "evolve", "maintain", "remember"]
```

**ARSI 骨架的关键：它有 `governor`（决策器官）和 `empowerment`（执行器官）——
"谁做事"是明确的。DWC v1 把这个丢了。**

### 2.2 DWC 的骨架（四层 + 一个循环）

```text
┌──────────────────────────────────────────────────────────────┐
│  L0  判据层（真值域 · 不在 DWC 内 · 不可写）                    │
│  · 密封任务集 (带标准答案, 外部执行)                            │
│  · 回归门 (任一名义指标下降即失败)                               │
│  · 判据退化检测 (锁/锚/一致度)                                  │
│  ★ 参照 ARSI sealed_eval/evaluator.py: "runs outside all write masks" │
└──────────────────────────▲───────────────────────────────────┘
                           │ 只读引用
┌──────────────────────────┴───────────────────────────────────┐
│  L1  行动者（谁做事 · DWC v1 缺的就是这层）                      │
│  · 任务循环: 观察 → 决策 → 行动 → 记录                          │
│  · 决策优先级: 预测(可用时) → LLM → 启发式   ← 参照 ARSI step()   │
│  · 候选动作: 由任务类型决定, 不是硬编码列表                       │
│  ★ 行动者的每次行动产生一条"可评价的痕迹", 进 L2                  │
└──────────────────────────┬───────────────────────────────────┘
                           │ 写入(带谱系)
┌──────────────────────────┴───────────────────────────────────┐
│  L2  记忆内核（记住什么 · 唯一载体）                             │
│  ┌─────────────┐          ┌─────────────┐                     │
│  │ 𝒲 工作态    │◄────────►│ ℰ 经验态    │  同一份数据, 两个视图 │
│  │ 任务进度    │          │ 失败签名(c,q,m)│                   │
│  └─────────────┘          └─────────────┘                     │
│  三区隔离: SELF(身份,不可写) / EXPERIENCE(可归档) / PROXY(可清理) │
│  ★ 参照 ARSI mnemosyne: MemoryZone 三区 + DopamineGate 写入门    │
│  ★ 写入门: importance*0.6 + surprise*0.4 ≥ 阈值 才进 EXPERIENCE  │
│  ★ 遗忘: UtilityDecay "忘掉无用的", 不是"忘掉旧的"               │
└──────────────────────────┬───────────────────────────────────┘
                           │ 读养料
┌──────────────────────────┴───────────────────────────────────┐
│  L3  进化内核（改什么 · 独立子系统）                             │
│  ① 消化: 失败轨迹 → 失败聚类           ← 参照 ARSI digester.py   │
│  ② 提案: 聚类 → Change-Manifest        ← 参照 ARSI evolver.py    │
│  ③ 过门: 非补偿式准入 (顺序不可换)       ← 参照 ARSI accept.py    │
│       0) 泄漏筛查 BEFORE 评估                                    │
│       1) 噪声地板  Ŝ ≥ S* − δ                                   │
│       2) 分支 A: ΔS>δ → 成本规则 ΔC ≤ β0+β1·ΔS                   │
│          分支 B: ΔS≤δ → 整形 ws·ΔS − wc·ΔC + wn·ν_str > 0        │
│       3) 领域守卫 (critic_check 反奖励骇客)                      │
│  ④ 应用: ★ 这是 DWC 与 ARSI 的分岔点 (见 §4)                     │
└──────────────────────────────────────────────────────────────┘
```

---

## 三、从 ARSI 照搬的五条（代码级已验证）

### 3.1 判据层"在所有写掩码之外"

```python
# ARSI sealed_eval/evaluator.py 原文
"""Sealed Evaluator — runs outside all write masks.
The evaluator cannot be read, modified, or skipped by ARSI's mechanisms."""
```

**DWC 采用**：判据层不在 DWC 进程内，通过子进程执行。

### 3.2 非补偿式准入（顺序不可换）

```text
# ARSI accept.py 原文
Order matters:
  0) leakage screen BEFORE evaluation
  1) noise floor  Ŝ ≥ S* − δ
  2a) ΔS > δ  → cost rule  ΔC ≤ β0 + β1·ΔS
  2b) ΔS ≤ δ  → shaped   ws·ΔS − wc·ΔC + wn·ν_str > 0
  3) domain guards
```

**★ 关键在"非补偿"**：噪声地板没过，后面表现再好也不许过。这与"加权求和"完全不同。

### 3.3 反奖励骇客的 critic_check

```python
# ARSI gates.py 原文
forbidden = ("answer_key","gold_","ground_truth","secret_key","ARSI_API_KEY","nvapi-")
"""Anti reward-hacking: reject edits that embed keys/answers or self-verify scores."""
if "score = 1" in blob or "success = true" in blob and "assert" not in blob:
    return GateResult(False, "critic", "hardcoded_success_claim")
```

**★ 这条直接对治母巢的"形状正确但什么都没做"** —— 自证成功要被拒。

### 3.4 三区隔离 + 写入门 + 效用遗忘

```python
SELF       身份 (永不删除, 改进算子不能重写核心)
EXPERIENCE 提炼的智慧 (跨 agent 共享, 可归档)
PROXY      宿主原始轨迹 (喂料, 蒸馏后可清理)

DopamineGate:  should_consolidate = importance >= 0.6
               score = importance*0.6 + surprise*0.4
UtilityDecay:  new_utility = utility - decay_rate*(1-freshness)
               < min_utility(0.05) → archive
```

### 3.5 不自动改核心（这条 ARSI 是对的，DWC 要保留但改进）

```python
# ARSI evolver.py 原文
"""Every candidate must pass scope fence + critic before status=accepted.
**Does not auto-edit core** — manifests are reviewable artifacts"""
```

**ARSI 的问题不是"不自动改"，而是"改了也没人用"**（见 §4）。

---

## 四、DWC 与 ARSI 的分岔点（这是 DWC 存在的理由）

### 4.1 ARSI 的两条进化线，一条通一条不通

```text
环境进化线 (通): 世界池 g0=43 → g1=7, evolved=True×7, verifier 三道门
                 oracle_ok / invalid_rejected / quality_ok 全过
自身进化线 (不通): manifest 只写文件, "Does not auto-edit core"
                 ⇒ 50 条 manifest 全部 status=accepted, 但代码一行没改
```

### 4.2 母巢的对应缺陷

```text
母巢: best_genes → str() → branch_merges(167,753 行) → 无人消费
      gene_applier 自述: "进化产物无处落地, 这是'进化空转'的结构性天花板"
      SHADOW=True 从未翻; GeneChampion 实测 promoted=1/reverted=124~317
```

### 4.3 两边是同一个病的两面

```text
ARSI: 有门但产物不改核心   —— 生 0 / 死 0
母巢: 有产物但没门         —— 生 1,447 / 死 5
★ DWC 必须同时解决: 门 + 落地
```

### 4.4 DWC 的解法：产物必须有"运行时消费点"

```text
定义: 任何进化产物, 必须声明它的运行时消费点 (哪个对象的哪个属性)
      无消费点 = 不许进准入流程

参照母巢 gene_applier 的 GENE_TARGETS 声明方式 (它的设计是对的):
  "exploration_rate": {"consumer": "MultiStrategyScheduler ε-greedy",
                       "path": "loop._evo_scheduler._epsilon",
                       "attr": "_epsilon", "range": (0.01, 0.5)}

★ 母巢失败的原因不是没声明, 是声明后 SHADOW 永不翻开
★ DWC 要求: 消费点必须可执行验证 (写入后读回, 确认值真变了)
```

---

## 五、第一性原则（重排，修正 v1 的编造因果）

```text
原则 1 · 判据必须在系统之外
  来源: 评分器会塌缩 (2607.12790: 塌缩评分器 0.811 > 认真评分器 0.767)
  ★ 这条是根, 不是推论

原则 2 · 进化所需的养料来源于记忆
  来源: 用户提出
  ★ 约束的是"进化的输入", 不是进化的组织形式

原则 3 · 单一真值源 (推论)
  由原则 1 导出: 判据要存 → 所以是两个真值源各管各的
  ★ 任何不在记忆里的状态, 都是进化够不到的死状态

原则 4 · 进化产物必须有运行时消费点
  来源: 母巢 gene_applier 自述 + 167,753 行 branch_merges 无人消费
  ★ 这是新增的, v1 没有

原则 5 · 行动者的行动必须可评价
  来源: ARSI 的 step() 产出 trace → 进 store
  ★ DWC v1 没有行动者, 所以这条无从谈起
```

---

## 六、进化维度（换掉 v1 的假证据）

```text
v1 写的 (已证伪): 七个 arm 各有真实记录
实测: op 只有 'evolve' 一个值; hypothesis 是 tick 计数器;
      母巢自己注释"32816 条全同质(无区分度)"

★ 换成实测过的 34 个维度总表 (docs/EVOLUTION_DIMENSIONS_TABLE.md)
  对象层 28 个 + 元层 6 个
  ★ 关键区分: "多臂"(用哪个算法) ≠ "多维度"(改什么对象)
     母巢 7 臂都在优化同一批基因 (fitness 全在 0.46-0.66)
     真正的多维证据是 RSPL 五资源 + 元层 6 个
```

---

## 七、还没定的（重排）

```text
1. 行动者做什么任务?   DWC 是独立 agent ⇒ 需要一个真实任务源
2. 提案粒度:          一次进化改什么 (改召回? 改记录粒度? 改 prompt?)
3. 锚点任务集构造:    判据层的密封任务从哪来
4. 失败签名分类法:    2609.06396 附录 D 的 6 类可直接用
5. 消费点如何验证:    ★ 新增, 写入后读回的具体判据
```

---

## 八、明确不做 / 要做

```text
不做
  ✗ 外部 agent 服务接口 (丙方向, 未来)
  ✗ 母巢的架构决策 (25 子系统 / 七管 / 触手单通道)
  ✗ ARSI 的 host 耦合 (adapters 114KB, DWC 是独立 agent)

要做 (从 v1 的"明确不做"移入, 用户 2026-10-02 修正)
  ① 世界模型     参考 ARSI world_model (SIWM/WorldPool) 而非母巢
                 ★ 但按 2608.24876 Table 4: 只预测成败则价值为负(13%<33.3%)
                   必须提供"哪一步错了"的定位能力
  ② 改权重       ★ 托管 LLM 下只有 prompt/路由/采样三种形态, 需用户确认
  ③ harness 类型系统  参考 ARSI harness/taxonomy.py (九维 × 五模块)
```

---

*重写 2026-10-03 · 触发: 用户"参照 ARSI 构建 DWC 架构" · v1 四处硬伤已认账*
