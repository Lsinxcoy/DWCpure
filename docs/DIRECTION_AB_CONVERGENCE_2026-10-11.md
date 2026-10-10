# A 与 B 的共同性深度分析（R187 — 用户指令: "A和B其实好像有共同性"）

日期: 2026-10-11 · 前置: R186 搜索报告（docs/papers/DIRECTION_SELECTOR_SEARCH_2026-10-11.md）

## 一、先摆结论: 共同性是**真的**, 且比"都涉及方向"深两层

表层看: A = 何时换向（控制流）· B = 向哪里换（空间结构）——一"时间"一"空间", 像两个正交件。

**但两者在决策点上汇合**: 它们都必须回答同一个问题:

> **在哪个候选项上, 施加哪个方向的算子?**

这个问句里同时含 A 的"哪个方向"与 B 的"哪个候选/哪个子空间"。**谁单独实现都会把另一个硬编码掉**:

- 只做 A（换向时机）而不做 B（候选生成）⇒ 换向时**没有可换的对象**——DWC 现在的形态:
  `proposals` 空了才调 `propose_lateral` 泛化, 泛化也空 ⇒ `unfixable_now`。**换向动作是" fallback 到空"**。
- 只做 B（taxonomy 分层）而不做 A（停滞判据）⇒ 候选永远从**最细一层**出, 没有"何时上溯/何时下钻"的控制 ⇒ 分层退化成静态枚举。

⇒ **共同性的本质: A 和 B 是同一个器的两个面**——我把它命名为 **方向算子-候选面 (direction-operator × candidate-space)**。

---

## 二、三层共同性（逐层给出代码/论文证据）

### 第 1 层 · **触发同源** — 都由"当前候选失败/停滞"点火

| | 点火信号 | 证据 |
|---|---|---|
| A | "invalid or its improvement is no greater than a threshold" | EvoTS 2608.17933 原文 |
| A' | "Plan Reviewer rejects a plan or the repair budget for the current direction is exhausted" | 2609.04128 §5.5 原文 |
| B | Astar 的 hint 生成条件 = system context + **evolution history**（哪些有效哪些无效）| 2608.27287 §2.2 语料就是从历史 commits 配对学出来的 |

**在本仓库的形态**: `_run_one_task` 里 `if not proposals:` → `propose_lateral`。
**这就是 A 和 B 已经在悄悄合体的地方**——DWC 的 LATERAL 泛化（R173）同时做完了两件事:
它**既是换向动作**（换到同族别的 fn）**又是候选生成**（同族 patch）= A∩B 的最小实例。

▸ **推论**: R73 说"选择策略未做"其实也不全对——R173 已经实现了 A∩B 的一个**特例**（同族泛化）, 只是它是硬编码的特例, 不是可判定的机制。

### 第 2 层 · **结构同构** — 分层换向 = 树上游走

Astar B 方案的三级 taxonomy（**L1 粗方向 → L2 修改动作 → L3 具体计划**）与 A 的 fallback 链共用同一个结构:

```
              ┌─ L1-FORWARD（在本 component 内改）
              ├─ L1-LATERAL （换 L2: 换 component/换 fn）
              └─ L1-REVERSE （换 L1: 回退简化）
```

**关键**: "fall back to the next direction"（A）与 "progressively narrow the search space"（B）在不同层上做**同一件事——沿一个树移动, 每步要么下钻（收窄）要么上溯/横移（换向）**。

▸ 对 DWC 的意义: **判据树本身就是那个层级结构**。R177-R183 刚落地的 `mechanical_candidates()`
（current + 每 op 单叶 + root∧op 对）就是一棵**两层的候选树**：
- 换 op = 第 2 层的横移（≈LATERAL 的子操作）
- root∧op vs bare op = 第 2 层内的不同粒度（≈evolution effort 的 low/high）

**⇒ B 的 taxonomy 无需新建: DWC 的候选树已经在那个位置, 只缺一个"何时在这棵树上走哪一步"的控制面（=A）**。

### 第 3 层 · **目的同源** — 都是把"换向"从随机变可判定

| 论文的随机性 | 可判定化手段 | DWC 已有什么 |
|---|---|---|
| 04128: "randomly order the three directions" | — （它就是随机） | — |
| EvoTS: 三算子固定流程, **停滞判据决定何时切** | invalid ∨ 增益≤阈值 | `score` 序列 + **噪声带 0.01**（R185 adopt 同源口径）✓ |
| Astar: 三级 hint 收窄空间 | 历史配对学出的方向质量 | replay 选择面（R174: argmax V ≥ V(current)）✓ |

**⇒ 三者的共同方向是同一个工程命题: 用便宜的可判定信号, 替代昂贵的试跑验证。**
A 用"分数不动了"（便宜）替代"这个方向错了"（贵）;
B 用"层级"（便宜）替代"搜全空间"（贵）。
**DWC 两者素材都已在场**（噪声带 + 候选树 + replay argmax）。

---

## 三、合并方案 A+B = 一个器: **方向控制器 (DirectionController)**

### 3.1 器的一个决策函数

```
pick_direction(state) -> (direction, candidate)
```

输入 state（全部已在场的量, 不发明新事实）:
- 该任务的 score 序列（replay 面已有）
- 候选树（mechanical_candidates 已有）
- 上轮方向的成败（新增: 一小块账本 — ℒ 族台账已有先例）

输出:
- direction: FORWARD / LATERAL / REVERSE（direction.py 已有枚举, 锁 3）
- candidate: 树上的一步（一个 Node 或一个 Proposal）

### 3.2 判定规则（三条, 每条都有论文出处 + DWC 在场实现）

| 规则 | 判据 | 出处 | DWC 素材 |
|---|---|---|---|
| **R1 停滞即换** | score 两轮增益 ≤ 0.01（噪声带）或本方向提案被门拦 ⇒ 当前方向标记 stagnant | EvoTS 原文 | score 序列 ✓ 噪声带 ✓ gate blocked ✓ |
| **R2 序内 fallback** | 每任务三方向随机序（可复现: 按 round 号 hash 定序, 不用真随机）; 序内方向失败 ⇒ 下一个 | 04128 §5.5 原文 | round_no 在手 ✓ |
| **R3 全败记账终止** | 三方向全败 ⇒ 该任务记入台账（unfixable_now 族）+ **不硬生成第四方向** | 04128 "branch terminates only when all three directions fail" + DWC"None 是合法结果"纪律 | _last_skip ✓ |

### 3.3 覆盖 DWC 现有三处方向动作（**不新造轮子**）

1. **FORWARD** = 现有 propose（签名命中规则 ⇒ 本 fn 的修法）— R30 起就在
2. **LATERAL** = 现有 propose_lateral（同 (c,q) 近亲 fn 泛化）— R173 起就在
3. **REVERSE** = **新增**: 同 component 回退到更简单 target（如降 verifier_rung / 简化 patch）
   —— 这个是真的缺, 但也不是凭空造: evolver.RULES 里凡有"简化/重写"类 target 的即可,
   没有则 None（unfixable_now — 不放水）

▸ **⇒ A+B 合并后 DirectionController 不新增任何器官, 只新增一个 200 行内的调度面**:
把散在 `_run_one_task` 的 `if not proposals → propose_lateral` 硬编码, 换成
R1/R2/R3 的可判定调度 + 台账。

---

## 四、诚实的边界（不掩盖）

1. **R3 的"全败终止"在 DWC 有一个歧义**: 04128 的 branch 指一条演化谱系; DWC 的
   同任务多轮会**再点火**（dev 任务轮转 R172）⇒ 终止应理解为"本轮记
   unfixable_now", 不是永久拉黑。我按后者实现（与 R172 轮转语义一致）。
2. **Astar B 的 taxonomy 收窄, 本合并方案只取其"分层", 不取其内容**——DWC 的
   分层用候选树不是 LLM hints（无 LLM 成本、可复现）。这是**迁其结构非其手段**。
3. **两篇论文都不是为 DWC 的三方向写的**: 04128 的三方向是环境难度分解
   （length/scenario/skill）, EvoTS 的三算子是轨迹算子。**共同性是我分析的,
   不是论文说的**—— 我在做的是同构映射, 已在报告里逐条标注了 ≠ 辨析。
4. **未与论文作者/第二人复核**（DWC 一贯纪律）。

---

## 五、给用户的裁决请求

合并方案落地形如:
```
src/dwc/organs/direction.py     +3 处: REVERSE 候选钩子 + 控制器判定（纯函数, 可单测）
src/dwc/harness/loop.py         改 1 处: if not proposals 硬编码 ⇒ pick_direction(state)
config/ 或 archive/              新账本: direction_ledger.jsonl（每任务每方向的成败 1 行）
tests/                           test_r187_direction_controller.py（R1/R2/R3 + 三处覆盖 + 反例锁）
```

**三个可选项**:
1. **全做**（R187 一个轮次落完, 含测试）
2. **只做 R1+R2**（停滞判定+fallback 序; REVERSE 候选留待下轮 — 最小可验证闭环）
3. **先只落纯函数 + 测试**（direction 控制器判定逻辑, 不接 Loop — 验证判据本身, TDD）

（我推荐 2：闭环最小且三条规则都有真实数据会走到; REVERSE 留单独一轮可以对着
RULES 真内容设计, 不拍脑袋。）
