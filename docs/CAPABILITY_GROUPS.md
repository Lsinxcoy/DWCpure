# DWC 能力组划分（缺口 A6）

> **状态**：设计定稿（**未写代码**，`src/` 与 `config/` 均空）
> **日期**：2026-10-04 · **来源**：`docs/GAP_AUDIT.md` 缺口 A6
> **依据（已逐条核，非估计）**：
> `E:/ARSI/config/sealed_tasks.yaml`（3,266 字节，15 条**全部**逐条读过）
> `E:/ARSI/src/arsi/sealed_eval/code_verifier.py`（三 scoring 口径）
> **前置**：`docs/TASK_SCORE_TRACKING.md`（n_assertions 与 Λ 同量纲）·
> `docs/GATE_CONFLICT.md`（第⑦步按组算）· `docs/REGRESSION_GUARD.md`（保护组 r̂_{t,j}）

---

## 一、★★★ 先说结论：三组，且**不需要新建分组概念**

```text
★ 15 条任务的 category 字段**天然就是三个能力组**（逐条核 yaml）:

  code_repair          6 条   scoring=assertion  rung=1  n_checks=[2,2,2,3,2,2]  共13
  knowledge_reasoning  6 条   scoring=keyword    rung=1  n_checks=[3,3,4,4,4,3]  共21
  paper_reproduction   3 条   scoring=value      rung=3  n_checks=[3,2,2]        共7

⇒ ★★★ DWC 不必"划分"能力组 —— ARSI 的 category **已经是**能力组
⇒ ★ 这是本项最省力的一点: 组不是设计出来的, 是**已经在数据里的**
⇒ ⇒ 但需要一次**显式声明 + 加固**, 因为:
  · category 字段目前只是分组标签, **没有任何机制依赖它**
  · 分辨率三组不同（median 2 / 4 / 2）⇒ Λ 不能统一取
```

---

## 二、★★★ 三组的分辨率不同 ⇒ Λ 必须逐组声明

```text
★ 实测（每组的 1/median(n_checks)）:
  code_repair          median=2  ⇒ 1/median = 0.500
  knowledge_reasoning  median=3.5 ⇒ 1/median = 0.286
  paper_reproduction   median=2  ⇒ 1/median = 0.500

★★★ ⇒★ 由 TASK_SCORE_TRACKING §四 的结论直接落地:
  Λ 统一取 0.03 ⇒ 三组**全部**是死判据（0.03 ≪ 0.25）
  ⇒ ★★ 所以 Λ_j 必须逐组声明, 且 ≥ 1/median(n_checks_j)
```

### 2.1 ★★ 换用「断言计数」口径（本设计的推荐）

```text
★ 原口径（分数）: 分数下滑量 > Λ_j，其中 Λ_j ≥ 1/median(n_checks_j)
  ✗ 缺点: Λ 的单位是"分数", 但它的可用性由"断言数"决定 ⇒ 两个量纲混在一处

★★★ 推荐口径（计数）: 窗口 N 轮内, 组 j 的「失败断言数增量」> Λ_assert_j
  ∀j: (本窗口末轮的失败断言数 − 首轮的失败断言数) > Λ_assert_j

  优点:
   ① 单位统一（就是"断言个数"）, 不需要换算
   ② 天然按组自适应（n_checks 不同 ⇒ 绝对容差可不同, 但语义一致）
   ③ 可解释: "这一组比 N 轮前多坏了 1 个断言" —— 人能直接判断
   ④ 与 seesaw 的区别更清晰: seesaw 看"是否跌破阈值", 计数口径看"失败数是否净增"

★ 三组的建议初值（Λ_assert, 单位=个）:
  code_repair          n=6 任务/13 断言 ⇒ Λ_assert = 1
  knowledge_reasoning  n=6/21              ⇒ Λ_assert = 2
  paper_reproduction   n=3/7（rung3, 最严）⇒ Λ_assert = 1
  ★★ 理由: Λ_assert 应随组的断言总量按比例放大（约总量/10）
    13/10≈1 ✓ · 21/10≈2 ✓ · 7/10≈1 ✓
  ★★ 这三个值是**按比例推的**, 无外部依据 ⇒ 须在真实负载上校准
```

### 2.2 ★ 为什么不能把三组合并成一组（组数上限的实测依据）

```text
★ 若只分一组（15 条合并）:
  median(n_checks) = 2 ⇒ 1/median = 0.5 ⇒ 灵敏度**最差**
  ⇒ 且 code_repair 与 knowledge_reasoning 的失败模式无关
     （前者是代码对不对, 后者是关键词命中与否）
  ⇒ 合并 ⇒ 一组退化会被另一组的改善掩盖 —— ★ 这正是第⑦步要防的那件事,
     自己却犯了 ⇒ ⇒ 分组本身就是第⑦步的前提

★★ 组数上限的实测依据:
  每组至少要 n_min 任务才有意义（否则单条任务掉分=整组掉分）
  实测: code=6 · reasoning=6 · reproduce=3
  ⇒ ⇒ n_min 建议 ≤ 3 ⇒ 三组都满足
  ⇒ ★★ 若将来加第四组, 至少要 3 条新任务 ⇒ 评测集从 15 → 18
```

---

## 三、★★ 组的三条定义（A6 的硬约束，来自 REGRESSION_GUARD §三）

```text
★ REGRESSION_GUARD 已定的组定义三条件:
  ① 有稳定的 sealed 评测集
  ② 有历史成绩序列 {J_{j,i}}
  ③ 组之间不可完全重叠（否则 ϵ_j 被重复计罚）

★★ 逐条核验 DWC 现状:
  ① sealed 评测集: ✓ 15 条，三组都有（6/6/3）
     ★★ 但 ARSI 的 category 目前**只是标签** ——
       没有任何 check_fn 或门读它 ⇒ 条件①形式满足、实质未接线
  ② 历史成绩序列: ✗ DWC 还没有（这正是 C3' 刚定的 TaskScorePoint，
       落点在 TASK_SCORE_TRACKING，group_id 字段**已占位**）
  ③ 不重叠: ✓ 三组的 scoring 模式互异（assertion/keyword/value）
     ⇒ 判定方式: 同一任务只能属一个 group_id，由 config 显式声明
```

---

## 四、★★ 落地形态

```yaml
# 落点: config/capability_groups.yaml （新建, 与 sealed_tasks 分离）
#  ★ 为什么分离: sealed_tasks 属 judge 的写掩码之外（G10）,
#    而组的元数据（Λ_assert / 保护等级）属可配置但需版本化
groups:
  - group_id: code_repair
    sealed_task_ids: [code_fix_001, ..., code_fix_006]   # ★ 显式列举, 不靠正则
    n_assertions_median: 2          # ★ 实测值, 必须落 (T1: 无默认值)
    lambda_assert: 1                # ★ 计数口径的容差
    epsilon: 1                      # ★ 保护组回归容差 (25(c) 的 ϵ_j)
    measurable: true                # ★ 条件①的显式自陈
  - group_id: knowledge_reasoning
    sealed_task_ids: [...6 条...]
    n_assertions_median: 3.5   # ★★ 标准中位数(3,3,4,4,4,3 → 3.5), 不是上中位数 4
    lambda_assert: 2
    epsilon: 1
    measurable: true
  - group_id: paper_reproduction
    sealed_task_ids: [...3 条...]
    n_assertions_median: 2
    lambda_assert: 1
    epsilon: 1
    measurable: true
```

```text
★★ 三个必须显式、无默认值的字段:
  n_assertions_median  ← 若不落, Λ_assert 的可用性不可审计（T5）
  lambda_assert        ← 第⑦步的容差, 不可隐式默认
  epsilon              ← 25(c) 的 ϵ_j, 不可隐式默认
★ 与 G11 的 certification_limit / K4 的 editable 同款纪律:
  必填、无默认、不可为空串
```

---

## 五、可机械检查的判据（gate.py 候选，G1–G6）

```text
G1 · 15 条任务每个都恰好属于一个 group_id（无遗漏、无重复）
   ★★★ 注意: "无遗漏"≠"在 𝒦_meta 里" —— 是"在某个 group 里"
   ⇒⇒ 组合起来就是 C3' 的"T4"（任务改断言后历史不可比）的另一面

G2 · 每组至少 3 条任务（n_min）
   ★ 若某组只有 1 条 ⇒ 单条掉分=整组掉分 ⇒ 该组的 ϵ_j 实际是单任务阈值

G3 · n_assertions_median 必须与 sealed_tasks 的实测值一致
   ★ 判据形式: 重新解析 sealed_tasks, 算出每组 median, 与 yaml 比对
   ★★ 这是 TS1+TS5 的可执行形式 —— 防止 yaml 里的中位数与任务集脱节

G4 · lambda_assert ≥ 1/n_assertions_median
   ★★ 否则该组的第⑦步是**死判据**（实测: Λ=0.03 在三组上全部死）
   ★ 这是 TASK_SCORE_TRACKING TS5 的组级形式

G5 · 至少存在一处消费点读 group_id
   ★★★ 否则三组只是标签 —— 条件①"形式满足、实质未接线"
   ★ 消费者至少两处: 第⑦步（累积退化）· 25(c) 的 r̂_{t,j}（保护组回归）
   ★ 与判据 R3 同款纪律: 只被记录不被读 ⇒ 是死指标

G6 · 组数 ≤ 评测集条数 / n_min
   ★ 当前 15/3 = 5 ⇒ 最多 5 组, 现用 3
   ★★ 这条把"能不能加组"变成一个算术问题, 而不是口头共识
```

---

## 六、诚实边界

```text
① 本设计**未写代码**，`src/` 与 `config/` 均空。
② 未验证: G1–G6 全是设计推理。
③ ★★★ "三组"不是我划的, 是 ARSI 的 category 字段**本来就有的** ——
   ⇒ 这是本项最省力的一点, 但也意味着:
   ★ 若 DWC 将来认为这三组不覆盖它的能力面（如"工具使用""长程规划"）,
     需新增任务而非重新划分 ⇒ ★ 新组成本 = 至少 3 条新任务
④ ★★ Λ_assert = {1, 2, 1} 是**按 总量/10 推的**, 无外部依据。
   ★★ 且推导假设了"各组断言难度相当" —— 实际上 code_repair 的断言
     （assert 布尔）与 knowledge_reasoning 的（关键词命中）难度不同
   ⇒ ★ 三个值须在真实负载上校准
⑤ ★★ 最大的隐患: **paper_reproduction 只有 3 条**
   ⇒ 它的 ϵ_j 实际接近"单任务阈值"（掉 1 条 = 掉 33%）
   ⇒ ★ 三组的敏感度天然不等, 而门是非补偿的 ⇒ 小组会被更严地惩罚
   ⇒ ★ 是否该给小组成比例放宽容差, 未定
⑥ ★ 组间"不可完全重叠"（条件③）我只用 scoring 模式互异来判,
   ★ 未核三组任务的**语义**是否真的互斥（如 code_fix_004 的 fibonacci
   ★ 也属"算法推理", 与 knowledge_reasoning 有边界模糊）
⑦ ★ 未评估: 组数对第⑦步计算成本的影响（每组一次窗口扫描）。
⑧ ★ group_id 字段已在 TASK_SCORE_TRACKING 的 TaskScorePoint 里占位,
   ★ 本文件给出了它的取值来源（config/capability_groups.yaml），
   ★ 但两文档的字段定义未做交叉核对。
⑨ ★ REGRESSION_GUARD §三 的组定义三条件里，条件②"有历史成绩序列"
   ★ 目前是空的（依赖 C3' 的 TaskScorePoint 落地）⇒ 三条件只满足 1.5 条
```

---

## 七、★ 实测记录（rc=0 全通，并**被 G3 抓到我自己一个真错误**）

```text
✓ G1 15 条全被覆盖, 无遗漏无重复
✓ G2 每组 ≥ 3 条（6/6/3）
✓ G3 中位数与 sealed_tasks 实测一致 —— ★★ 这里第一次跑就**红了**
✓ G4 λ_assert ≥ 1/median; 反例显示 Λ=0.03 在三组上**全部**是死判据
✓ G5 group_id 有两处消费（第⑦步 / 25(c)）
✓ G6 组数上限 15/3 = 5, 现用 3 ⇒ 加第 4 组需 ≥3 条新任务
✓ 第⑦步计数口径: 三组单位统一为「个断言」, 无需换算
✓ 边界: 净增 == λ 时**不**触发（判据用严格大于 >, 与 25(c) 的 ≤ ϵ_j 互补）

★★★ G3 抓到的真错误（我自己写的）:
  我在 yaml 草案里写 knowledge_reasoning 的 n_assertions_median = 4
  ★★ 实测: 6 条任务的 n_checks = [3,3,4,4,4,3] ⇒ **标准中位数 = 3.5**
  ⇒ 我用的是"上中位数"（sorted[3]=4）, 而 statistics.median 取中间两数均值
  ⇒⇒ ★ 这正是 G3 存在的意义: 若无它, 3.5 vs 4 的偏差会静默留在配置里
  ⇒ ⇒⇒ 已修正为 3.5, 且 1/3.5 = 0.286（不是 1/4 = 0.250）

★★★ 第⑦步计数口径的实测暴露（值得注意）:
  code_repair          失败数 3→5 净增=2, λ=1 ⇒ **违反**
  knowledge_reasoning  失败数 7→9 净增=2, λ=2 ⇒ 未触发
  paper_reproduction   失败数 1→2 净增=1, λ=1 ⇒ 未触发
  ⇒ ★★ 注意后两组: 净增恰好等于 λ 时不触发
  ⇒ ⇒ 这是设计上的选择（严格大于）, 但也意味着"恰好坏了一个断言"不算
  ⇒ ★★ 与 §2.1 的 Λ_assert = {1,2,1} 取值强相关:
     若 knowledge_reasoning 的 λ 取 1 而非 2, 上面那轮就会触发
     ⇒ ★★ 三个值是拍的这一事实, 现在有了**可观察的后果**（见诚实边界④）
```

---

## 八、诚实边界（补）

```text
⑩ 实测覆盖: G1–G6 / 第⑦步计数口径 / 边界条件
   ★★ 未测: 真实负载下的 λ_assert 校准（三个值仍是拍的）
⑪ ★★ 实测让我看到 Λ_assert 的取值**直接决定三组敏感度不等**:
     knowledge_reasoning(λ=2) 与 paper_reproduction(λ=1) 在同一净增下结论相反
   ⇒ ★ 这是 A6 遗留的最大不确定: 三组敏感度不等, 而门是非补偿的
   ⇒ ⇒ 是否给小组成比例放宽容差, 仍是未定（诚实边界⑤）
⑫ ★ G3 修正后, §四 的 yaml 草案里 3.5 是浮点数 —— 若配置用整数类型会失败
   ★ 具体类型未定（yaml 支持浮点, 但若落成 Python 需 float）
```

---

*设计定稿 · 2026-10-04 · 三组沿用 ARSI 既有 category（不新建概念）+ Λ 改断言计数口径 + G1–G6 · 参照 sealed_tasks.yaml 3,266 字节 15 条逐条核 · 未写代码*