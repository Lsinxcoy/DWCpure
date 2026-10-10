# direction 选择器 · 前沿论文搜索结果（R186 — 用户指令: 覆盖本地论文库 + 网络全部）

日期: 2026-10-11 · 搜索范围: docs/papers/ 53 篇本地论文（grep 全文）+ arXiv 网络（多组检索词, 每词 top5）

## 一、结论先行: 三处直接可用的「有据」策略 + 一处训练路线

DWC 的 FORWARD/LATERAL/REVERSE 三方向 =  exploitative refinement / divergence / retreat。
R73 裁「设计零策略描述 ⇒ 不发明」**半错**: 本地库 2609.04128 §5.5 原文就有策略,
R73 只核了 EVOLUTION_CORE_V2/ALL_REPOS 没核论文正文。**本报告即修正依据。**

---

## 二、本地论文库命中（53 篇 grep 全文 — 含 direction 一词的仅 8 篇, 逐篇核过）

| 编号 | 命中内容 | 对 DWC 的可用性 |
|---|---|---|
| **2609.04128** ★★★ | §5.5 原文: "each generation, we **randomly order** the three evolution directions. If the Plan Reviewer rejects a plan or the repair budget for the current direction is exhausted, we **fall back to the next direction**... **The branch terminates only when all three directions fail.**" | **直接可用** — 随机序 + 单方向修复预算耗尽即换向 + 全败终止。Table 1 还有三方向各自的 Δ Pass Rate / mutation 成本（length: 最小 mutation 拿最大 pass-rate 降幅 ⇒ 成本效率最高）|
| 2603.25681 | 「self-directed selection 是被点名的空白」★★★★★ — 单一模型同时做 selector + learner = 自主最强形态, 尚无人做 | **方向选择本身就被论文点名为 open problem** — DWC 做这个 = 填空白, 但也意味着没有标准答案可抄 |
| 2607.12790 | 仅 1 处 direction（verifier evolution 语境, 无选择策略）| — |
| 2607.26117 / 2607.27201 / 2608.10299 / 2609.13406 / 2609.14858 | 零星提及, 无策略描述 | — |

### 2609.04128 的三方向 ≠ DWC 三方向 — 必须先辨析

- 2609.04128: length/scenario/**skill** — 环境难度分解（改序列的**编辑型**）
- DWC: FORWARD/**LATERAL**/REVERSE — 提案演化的**策略型**（改进/换向/回退）
- **结构同构**: "当前方向失败 ⇒ 回灌下一个 ⇒ 全败终止" 的控制流可直接迁移;
  Table 1 的**成本-收益数据不可直接迁移**（那是环境难度的量, 不是策略成败的量）。

---

## 三、网络搜索命中（ arXiv, 2026-08 前后）

### ★★★ 1. Astar: Learning to Propose Evolution Directions (arXiv:2608.27287, 2026-08-27, cs.IR)

**最直接命中** — "direction 选择器" 这个 topic 本身的前沿工作。

- 定位: 训练**专门模型**从系统自身迭代历史（commits）学「提什么方向」。
- 关键数: S@1 = **0.6786** vs 人类专家 0.3229 vs GPT-5.5 0.3071（真执行验证）;
  闭环 20 轮迭代离线 Hitrate@200 +23.6%, 线上 GMV +4.86% / 广告收入 +1.82%。
- 四大挑战 C1-C4: 监督稀疏 / 噪声样本 / 方向空间巨大 / 验证昂贵。
- 核心手段: ①pairwise 样本扩展（任意两版本配对, 二次方级）②规则+LLM 双重去噪
  ③**三级 taxonomy 分层提示** (Level-1 粗方向 → Level-2 修改动作 → Level-3 具体计划)
  ④**reward model 当 surrogate evaluator**（把几天的验证压成秒级预测, 兼作 RL 奖励与候选排序）。
- Level-1 标签实例: Model structure / Loss design / Optimization strategy / Training engineering / RL strategy / Data processing / Code refactoring。
- **对 DWC 的可迁移性**: 训练专门模型 = DWC 无此算力（要 SFT+RL）。
  可迁移的是 **三级 taxonomy + surrogate 排序** 思想 — DWC 已有 κ=10 加权/replay
  选择, surrogate 相当于给候选一个「预筛分」; taxonomy 相当于把三方向再分层。

### ★★★ 2. EvoTS-Agent (arXiv:2608.17933, 2026-08-18, cs.AI)

**三算子与 DWC 三方向同构度最高。**

- Revision = 在当前最优上 exploit ≈ **FORWARD**
- Alternative Strategy = **progress 停滞时**探索根本不同的方向 ≈ **LATERAL**
- Recombination = 末步综合强轨迹的互补部分 ≈ **（DWC 未有的第四算子）**
- **切换判据（原文）**: "A revision is marked **stagnant** if it is **invalid or its
  improvement is no greater than a threshold**. The next non-final step then tries a
  substantially different direction, including an untried detector."
  ⇒ **停滞判定 = 无效 或 增益 ≤ 阈值** —— 这是**可判定、可迁移**的规则。
- 结果: 4 基准全部超 LLM-agent 基线, 100% 执行成功率。

### ★★ 3. 相关但间接的佐证（都印证「stuck⇒换向」结构）

- **2602.10233 ImprovEvolve**: basin-hopping = 三算子（initialize / **improve** / **perturb**）交替, improve 卡住 ⇒ perturb 踢出新盆地。
- **2601.20539 PathWise**: 防 premature convergence 两招 — 时变探索率 ε(ℓ) 衰减 + state shuffling（打 LLM 位置偏置）; 把搜索建成 entailment graph + policy agent 规划演化动作。
- **2606.15545**: NK 双目标地形上五 heuristic 对照 — 其中 **Alternate: "pursue one goal until **stuck**, then switch"** — 学术上叫 alternate/bandit-style switching。
- 2507.21046 survey: self-evolving strategy 形式化 f: (system, τ, r) → system'; 分型 (what/when/how)。

---

## 四、综合裁决: DWC 该抄哪一条（按有据强度排）

| 方案 | 出处 | 机制 | DWC 落地成本 | 判定 |
|---|---|---|---|---|
| **A. 停滞判定 + fallback 链** | EvoTS×04128（互补） | 停滞 = 无效 或 增益≤阈值(噪声带 0.01 同源) ⇒ 换向; 每任务三方向随机序轮换, 全败终止记账 | 低（Loop 已有 score 序列/噪声带/ℒ_t 台账）| **首选 — 两篇独立互证, 判据可判定可复现** |
| B. 三级 taxonomy 分层 | Astar | 三方向→细动作→具体计划 的分层收窄 | 中（要设计 DWC 自己的 taxonomy, 但要人工列举）| 备选 — 收窄方向空间, 依赖人对任务面的先验 |
| C. surrogate 预筛分 | Astar | 学一个 reward model 替代完整试跑 | 高（DWC 无训练面; 且引入第二个预测器=新失败面）| **不推荐现阶段** — 与 DWC「判据在系统外」纪律张力 |
| D. 训练专门 direction 模型 | Astar 主路线 | SFT+RL 出 8B 专门模型 | 不可行（无算力）| 排除 |

---

## 五、诚实物

- 本地库 53 篇逐篇 grep, 不是抽样; 含 direction 的 8 篇逐篇读命中行。
- 网络搜索做了 5 组不同检索词（方向选择/停滞切换/开式探索/训练提向/三算子）。
- Astar 与 EvoTS 均**未落本地库** — 若采纳方案 A/B, 应先落 docs/papers/ 再动代码。
- 本报告本身不含任何 DWC 代码改动 — 等用户裁决方案后动手。
