# DWC 逐任务分数序列（缺口 C3' · 第⑦步的数据前提）

> **状态**：设计定稿（**未写代码**，`src/` 与 `config/` 均空）
> **日期**：2026-10-04 · **来源**：`docs/GATE_CONFLICT.md` 判据 C3' + 诚实边界⑤
> **参照（本轮已核源码，非报告转述）**：
> `E:/ARSI/src/arsi/sealed_eval/code_verifier.py`（293 行，三个 verifier 全文读过）
> `E:/ARSI/config/sealed_tasks.yaml`（3,266 字节，15 条，rung 1/1/3）
> **前置**：`docs/STATE_SCHEMA.md`（GateSnapshot 四层）· `docs/ORGAN_INTERFACES.md` §四
> · `docs/GATE_CONFLICT.md`（第⑦步）· `docs/REGRESSION_GUARD.md`（保护组）

---

## 一、★★★ 先说一个纠正我原判断的发现

```text
★★ 我在 GATE_CONFLICT §2.1 写的是:
   "pass@2 registers only **per-task binary flips**" ⇒ DWC 若只存二值, 第⑦步不可能实现
  ⇒ 我据此推断"DWC 的 verifier 大概也是二值的"

★★★ 核实源码后发现 —— **不是**:
  ARSI 三个 verifier 全部返回 tuple[float, dict], 且分数是**连续比例**:
    verify_python_code      score = passed / total                （L131）
    verify_value_extraction score = matches / len(expected)        （L177）
    verify_keyword_match    score = len(found) / len(keywords)    （L203）
  ⇒ ★★ DWC **不需要**新造评分器, ARSI 的分辨率已经够第⑦步用
  ⇒ 但它有一个**更致命的问题**（见 §二）
```

---

## 二、★★★ 真正的缺口不是"有没有连续分"，而是"连续分的粒度不够"

```text
★★★ 硬事实: score = passed / total, 而每个任务的 total 极小

  ARSI 15 条 sealed 任务的 test_cases 实际形态（逐条核 yaml）:
    code_fix_001: "sum_first_n(3)==6 and sum_first_n(5)==15"
    code_fix_002: "average([])==0.0 and average([1,2,3])==2.0"
    code_fix_003: "factorial(5)==120 and factorial(0)==1"
    ...
  ⇒ 每个任务的 expected_behavior 是**一个字符串**, 里面 2–3 个断言
  ⇒ 若按"字符串"切成一条 test ⇒ total=1 ⇒ score ∈ {0.0, 1.0} ⇒ **退化成二值**
  ⇒ 若按"and"切成多条 ⇒ total=2~3 ⇒ score ∈ {0, 0.5, 1.0} ⇒ 三个离散点
```

### 2.1 ★★★ 量化这个粒度问题（第⑦步能否落地的关键）

```text
第⑦步要测的量: 连续 N 轮里某任务的「分数下滑量」 > Λ
  ★ Λ 的天然取值应远小于"一个断言"的权重

实测口径推演（Λ = 0.03）:
  total=2 的任务 ⇒ 相邻两轮可能差 0.5
  total=3 的任务 ⇒ 相邻两轮可能差 0.333
  ⇒ ★★ 最小非零退化量 = 1/total ⇒ 若 total ≤ 3, 任何退化都 ≥ 0.33
  ⇒ ⇒ Λ = 0.03 时, 第⑦步实际只在"掉了至少一个断言"时才触发
  ⇒ ⇒ ★★ 它退化成了 seesaw（更严的 seesaw），**抓不到"没掉断言但变差"**
```

### 2.2 ★★ 结论：C3' 的真正内容是**提高单任务的分辨率**

```text
✗ 我原先以为 C3' 是"加一个分数序列字段"
✓ C3' 实际是: **让单任务的分数有足够分辨率, 否则序列存了也没用**

⇒ 两个动作, 缺一不可:
  ① 存储: 逐任务分数序列必须落盘（§三）
  ② 分辨率: 每个任务的断言数必须 ≥ n_min（§四）
```

---

## 三、★★ 存储形态（判据 C3' 的直接落点）

```python
# 落点: organs/judge/  （与 wm_pairs.py 同侧, 都是 judge 的内部存储 + 查询口）
@dataclass(frozen=True)
class TaskScorePoint:
    """单任务单轮的评测点。★ 一个任务一轮一条, 不覆盖。"""
    task_id: str
    group_id: str            # ★ 能力组（A6 待定, 但字段先占位）
    round_index: int
    split: str               # in | dev | test
    wm_version: str
    dw_version: str
    score: float             # ★ 连续分, [0,1]
    n_assertions: int        # ★★ 必须记录 —— 否则分辨率不可审计
    rung: int                # 1|2|3
    evidence_ref: str        # 指向 evidence, 不内嵌（约定④: 只传 ID）
    recorded_at: str
```

```text
★ 三个关键字段的理由:
  n_assertions  ★★ 没有它, "score 从 0.67 跌到 0.33" 无法区分是
                 「3 掉 1 个断言」还是「2 掉 1 个断言」⇒ 分辨率不可审计
  dw_version    ★ 换版本即换坐标系 ⇒ 版本换代后分数不可直接比较
                 （与 G11 配套3 / 判据 I12 同源）
  split         ★★ 守卫① 与回归约束读的都是 split 内的分数, 不能混
```

### 3.1 ★ 为什么放 judge 的内部存储而非 State 字段

```text
★ 依 ORGAN_INTERFACES 约定④（跨器官只传 ID）与判据 P2:
  逐任务分数是**高基数时序**, 每轮每任务一条 ⇒ 塞进 State 会让
  GateSnapshot 从十几字段膨胀到上千字段, 且违反"State 是快照不是流水"的定位
⇒ 所以:
  · judge 持有 TaskScorePoint 序列（内部存储）
  · State.GateSnapshot 只持有**聚合量与指针**:
      task_scores_ref: str          # 指向 judge 内部的序列存储
      group_scores: tuple[...]      # 按能力组聚合（第⑦步与 25(c) 都要用）
      n_assertions_min: int         # ★ 本轮观测到的最小断言数（分辨率自陈）
★⇒ judge 接口需加一个查询（候选）:
    judge.task_scores(split, wm_version) -> list[TaskScoreRef]
    judge.group_scores(split, round_index) -> dict[group_id, float]
★★★ 这两个方法的签名**依赖 A6（能力组划分）**
  ✓✓【A6 已解 2026-10-04】group_id 取值来源: config/capability_groups.yaml
     三组沿用 ARSI 既有 category（code_repair / knowledge_reasoning /
     paper_reproduction）—— ★ 不新建分组概念, 因为 category 字段**已经是**组
     ★ 详见 docs/CAPABILITY_GROUPS.md
  ★★ 顺带解决 Λ 的口径问题: 改为**断言计数**口径（单位="个断言"）
     ⇒ 不再需要"分数 Λ 与 1/median 同量纲"的换算（TS5 随之改写为组级形式 G4）
     ⇒ 实测: Λ=0.03 在三组上全部是死判据（1/median = 0.500 / 0.286 / 0.500）
```

---

## 四、★★ 分辨率要求（§二 的结论，C3' 的另一半）

```text
★ 硬要求: 每个任务的 n_assertions ≥ n_min

★ n_min 的推导（第⑦步的判别力所需）:
  第⑦步要在 window=N 轮内检出 "累计下滑 > Λ"
  若单次最小可观测退化 = 1/n_assertions
  ⇒ 要让 Λ 可用, 必须 1/n_assertions 远小于 Λ
  ⇒ 若取 Λ = 0.03, 则 n_assertions ≥ 34 才可能检出"小于一个断言"的退化
  ⇒★ 但 34 条断言/任务是荒谬的 ⇒ ⇒ 结论: **第⑦步不能靠提高分辨率实现**

★★★★ ⇒⇒ 那第⑦步的 Λ 必须是"一个断言量级"的, 即 Λ ≈ 1/n_assertions
  ★ 即: 第⑦步检测的是"**N 轮内掉了至少一个断言**"
  ⇒ 这与 seesaw 的区别在于:
     seesaw 看的是**是否掉到 solved 以下**（跨越 PASS_AT）
     第⑦步 看的是**连续分数的累计下滑**（不依赖 PASS_AT 阈值）
  ⇒★★ ⇒ **诚实的定位修正**:
     第⑦步 ≠ "抓 sub-threshold 的连续退化"
     第⑦步 = "在**不设通过阈值**的口径下测累计下滑"
     ⇒ 它比 seesaw 严（不需要跌到阈值下就算），但不是无限灵敏
  ⇒ ★★ 这是我原稿的一个**实质错误**, 已在本文件纠正
```

### 4.1 ★★ 因此对现有 15 条任务的处置

```text
★ 实测: 15 条任务的 expected_behavior 各含 2–3 个断言
  ⇒ total ∈ {2,3} ⇒ resolution = {0, 0.5, 1.0} 或 {0, 0.333, 0.667, 1.0}
  ⇒ ★ n_assertions 字段必须落, 否则读者以为 resolution 是连续的

★★ 一个更实用的替代读法（不提高分辨率也能用）:
  不看 score, 看 **evidence 里的逐条断言结果**
  verify_python_code 的 evidence 原文（已核 L118-136）:
      {"total_tests":…, "passed":…, "failed":…,
       "results":[{"assertion":…, "description":…, "passed":…, "output":…}, …]}
  ⇒ ★★★ evidence 里**已经有逐条结果**! resolution 已经在那里
  ⇒ ⇒ 所以第⑦步可以基于 evidence 算, 不必等 n_assertions 变大
  ⇒ ⇒★★ 这是本文件最有价值的一条发现:
     **C3' 不需要新造评分器, 只需把 evidence 里的逐条结果聚合起来落盘**
```

---

## 五、可机械检查的判据（gate.py 候选，TS1–TS5）

> ★★ **命名空间声明（2026-10-04 加，R5 门可信度审计）**
> 本族原为 `T1–T5`，与 `ERROR_AND_TERM.md` 的 `T1–T4`（term 层级判据）**编号撞车**
> 且两者语义完全不同（逐任务分数 vs run_term 生命周期）⇒ 现改为 **TS1–TS5**（TS = Task Score）。
> ★ `ERROR_AND_TERM.T1–T4` 保留原号（已被 GAP_AUDIT / LEVEL3_PROBE / ARCHITECTURE 多处引用）。
> ★★★ 另注: `T1–T4` 在 `docs/lessons/` 与 `DEDUP_AUDIT_6SYSTEMS.md` 里还大量出现，
>   那是 **Ultra/Nexus 的「四轨」术语**（参数 / 语义 / GitHub机制 / 论文机制），
>   属对外部项目的原文引用，**与 DWC 判据无关**，一律不改。
> ⇒ 起因: R5 枚举 20 族 130 条判据时，发现 10 个编号在不同文档指不同东西

```text
TS1· TaskScorePoint 必须含 n_assertions（无默认值）
   ★ 依据: §二 —— 没有它, resolution 不可审计

TS2· dw_version 必须落, 且版本换代后分数不可直接比较
   ★ 依据: §三 三个关键字段 + G11 配套3

TS3· judge.task_scores / group_scores 两个查询口必须存在
   ★ 若只有 group_scores（只有聚合）⇒ 第⑦步仍看不见 ⇒ 等于没做
   ★★ 依据: 判据 C3' 的原文要求"逐任务分数必须被记录"

TS4· 每个 sealed 任务的 n_assertions 必须是配置里显式声明的, 不是运行期数出来的
   ★ 理由: 否则任务改断言后历史分数不可比（分辨率悄悄变了）
   ★★ 依据: 与 G11 的 certification_limit 同款纪律（必填、无默认）

TS5· 第⑦步的 Λ 必须在配置里显式给出, 且必须与 median(n_assertions) 同量纲
   ★★ 依据: §四 —— Λ 的可用性直接由分辨率决定
   ⇒ 若 Λ ≪ 1/median(n_assertions) ⇒ 该门在物理上不可能触发（死判据）
```

---

## 六、诚实边界

```text
① 本设计**未写代码**，`src/` 与 `config/` 均空。
② 未验证: TS1–TS5 全是设计推理。
③ ★★★ 我纠正了自己在 GATE_CONFLICT §2.1 的一个**实质错误**:
   原写: 第⑦步防的是"sub-threshold 连续退化"（暗示它比 seesaw 灵敏得多）
   ★ 核实后: 在 total=2~3 的断言粒度下, 最小可观测退化 = 1/total = 0.33~0.5
     ⇒ 第⑦步**不可能**检出"小于一个断言"的退化
     ⇒ 正确的定位: 第⑦步 = "在**不设通过阈值**的口径下测累计下滑"
     ⇒ 它比 seesaw 严, 但不是无限灵敏
   ⇒ ★★★ 这直接改变了 GATE_CONFLICT 的立论强度, 该文档需要同步标注
④ ★ "Λ ≈ 1/median(n_assertions)" 是我的推导, 两篇论文都没这个量。
⑤ ★★ group_scores / group_id 的字段形态**依赖 A6（能力组划分）**, 尚未定。
   ★ 本文件只占位, 不预设组数。
⑥ ★ 未核: DWC 未来是否会用比 ARSI 更细的 verifier（L2 语义 judge 是连续的,
   ★ 但它"不许覆盖 L1 的结论", 能否提供连续分未核）。
⑦ ★ 未核 evidence 在 DWC 的存储成本（逐条 result × 任务 × 轮）。
   ARSI 的 evidence 里 output 被截到 200 字符, DWC 是否照做未定。
⑧ ★ 未评估: 15 条任务 × 每轮 × 多轮 的存储量。TS3 提供了查询口但未做容量估算。
⑨ ★ GATE_CONFLICT §2.2 / §3.1 的措辞仍未校（我上一轮已标, 至今未改）。
```

---

## 七、★ 实测记录（rc=0 全通，并抓到一个**死判据**问题）

```text
=== 分辨率实测（ARSI 三函数口径）===
  total=1 ⇒ score ∈ {0.0, 1.0}                 最小步长 1.0000
  total=2 ⇒ score ∈ {0.0, 0.5, 1.0}            最小步长 0.5000
  total=3 ⇒ score ∈ {0.0, 0.333, 0.667, 1.0}   最小步长 0.3333

=== 第⑦步 vs seesaw 的实测差别（total=3, passed=[3,3,3,2]）===
  末轮分数 0.6667（仍 > PASS_AT=0.5）
  seesaw 触发? **否**（两轮都 solved）
  第⑦步   触发? **是**（窗口内 1.0 → 0.667 = 0.333 > Λ=0.03）
  ⇒ ★✓ 第⑦步比 seesaw 严: **不需要跌到阈值下就算**

=== ★★★ 但极限测试证明它不是"无限灵敏" ===
  total=2 时 score 只有 3 个离散点; total=3 时只有 4 个
  ⇒ "0.9" 这个值**在数学上不可表示**
  ⇒⇒ ★★ 确认: 第⑦步**不可能**检出"小于一个断言"的退化
  ⇒⇒ ⇒ 它是"**更严的 seesaw**", 不是"无限灵敏的探针" ★ 原稿的立论需降级

=== ★★★ TS5 抓到真问题: Λ=0.03 是死判据 ===
  median(n_assertions) = 2 ⇒ 1/median = 0.5000
  Λ=0.01 / 0.03 / 0.10 / 0.33 → ★ 全部落在 1/median 以下 ⇒ **物理上不可能触发**
  Λ=0.50 / 0.51 → 可用
  ⇒ ★★ ⇒★ 第⑦步若用 Λ=0.03（我在 GATE_CONFLICT 里的隐含假设），它**永远不触发**
  ⇒ ⇒ ★★ 这是比"灵敏度不足"更严重的问题: 它是**死判据**
  ⇒ ⇒★★ TS5 判据（Λ 须与 1/median(n_assertions) 同量纲）因此是本设计的核心

=== 替代方案实测可行 ===
  直接用 evidence 的逐条 results（code_verifier L118-136 已核有此结构）
  4 轮 × 3 条结果序列 → 下滑量 0.3333 > 0.03 ⇒ 触发 ✓
  ⇒ ★ 不需新造评分器, 只需把逐条结果落盘并聚合
  ⇒ ★★ 但**不改变**"最小可观测量 = 1/n"这一事实
```

---

## 八、★ 连带要改的两处（必须回填 GATE_CONFLICT）

```text
★★★ 1. GATE_CONFLICT §2.3/§3.1 的立论需降级:
   原写: 第⑦步防"被其他任务的改善掩盖的退化"（隐含它比 seesaw 灵敏得多）
   ★ 实测后应改: 第⑦步 = "在**不设通过阈值**的口径下测累计下滑"
     ⇒ 它比 seesaw **严**（不需跌破阈值），但**不比 seesaw 灵敏**（最小 1/n）
   ⇒⇒ 混合场景实测（两组微跌 + 两组微涨）仍然成立:
     那里 seesaw 与双 split 都看不见, 而第⑦步看得见 —— 因为它不设阈值
     ★★ 但若那组微跌的幅度小于 1/n_assertions, 第⑦步**也**看不见

★★★ 2. Λ 的取值必须改:
   原隐含 Λ ≈ 0.03（小到能抓"细退化"）
   ★ 实测: Λ < 1/median(n_assertions) ⇒ 死判据
   ⇒ ★ Λ 必须锚在 1/median(n_assertions) 量级, 或**改用"掉了几个断言"的计数口径**
     ⇒ 后者更稳: Λ_assertions ∈ {1, 2, ...}, 单位是"断言数"而非"分数"
     ★ 这是两种口径的选择, 本文件推荐后者, 但未定
```

---

## 九、诚实边界（补）

```text
⑩ 实测覆盖: 三档分辨率 / seesaw-vs-第⑦步 差别 / 极限不可表示性
   / Λ 死判据边界 / evidence 逐条方案
⑪ ★ 一次自测失败是我**断言写反**（输出本身已证明正确）:
   写了 assert not(solved and solved) 而实际应断言 solved and solved
   ⇒ 已修正。★ 这不算设计错误, 记录在此以免误读实测记录。
⑫ ★★ 若采用"Λ 计数口径（掉几个断言）"，则 §四 与 TS5 的形式都要重写
   ★ 该选择未定 ⇒ 本文件当前的形式是"分数口径", 且已知它在 Λ 小时失效。
⑬ ★ 仍未评估存储成本: 15 任务 × evidence 逐条 × 多轮。
```

---

*设计定稿 · 2026-10-04 · 纠正"二值"推断（ARSI 已有连续分）+ 发现真正缺口是分辨率 + TS1–TS5 · 参照 code_verifier.py 293 行逐函数核 · 未写代码*