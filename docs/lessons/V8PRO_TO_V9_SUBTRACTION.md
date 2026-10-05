# V8pro → V9 · 你已经做过一次的减法

> 来源：GitHub `Lsinxcoy/prometheus-v9` README（2026-09-29 抓取）
> **这是本项目最重要的一份先验经验** —— 不是母巢的失败，是你自己已经走通的减法路径。

---

## 一、你自己写下的减法对比

```text
维度        V8pro          V9
─────────────────────────────────────────────────
文件数      120            26              ↓ 78%
代码行      18,120         ~4,300          ↓ 76%
进化层      12 层(10 层空壳) 4 层(全部实现)★ 空壳层直接删掉
向量搜索    hash 伪向量     sentence-transformers 真嵌入
测试        3/10           63/63 通过      ★ 测试从"3个"变成"全过"
断路器全局单实例           Per-Tool/Per-Provider 隔离
遗忘曲线    简单 Weibull    Weibull + Cognitive Sleep Cycle
CORAL       随机策略        UCB1 Bandit 策略
```

## 二、三条可直接迁移到 DWC 的判断

### ① 空壳层要删，不是要补
V8pro 的 12 层里有 **10 层是空壳**。V9 的做法是**删掉**，
只留 4 层且"全部实现"。

> 对应母巢 445 万行台账 / 526 个抢位冲突 —— 同一个病，
> 但你早在 V9 就给出过解法：**删掉空壳层，不给它补实现**。

### ② 测试从 3/10 到 63/63，比代码量减少更重要
代码删了 76%，测试反而全过。说明**之前的代码里有大量无法被测试触及的部分**
（空壳层不会被测到）。

> 这条对 DWC 的直接含义：**测试覆盖率不是补出来的，是删出来的。**
> 空壳删掉了，剩下的自然可测。

### ③ 伪实现要换掉，不是要容忍
`hash 伪向量` → `sentence-transformers 真嵌入`。
不是"先凑合用着"，是换真的。

> 对应 DWC：任何"形状正确但零实质"的东西（母巢的行为占位符）
> 要么换成真实现，要么删掉。**不接受"占位但可运行"这种中间态。**

---

## 三、V9 的架构（六层）与 DWC 的对照

```text
V9 六层:              DWC:
L5 Services           ── DWC 第一版不做（丙方向）
L4 Governance         ── 待定
L3 Safety             ── 待定
L2 Evolution(4层)    ── ★ 进化内核（独立子系统）
L1 Memory            ── ★ 记忆内核
L0 Foundation         ── Schema + Config
```

**注意**：V9 把 Memory(L1) 与 Evolution(L2) 分成**相邻但独立的两层** ——
这正好印证你这次的修正：**进化是独立子系统，与记忆平级**。

---

## 四、V9 的四层进化引擎（可直接参考）

```text
L0  Thompson Sampling      随机性探索
L1  AST变异                代码级变异
L2  Playbook 演化           策略演化（源自 ACE 论文）
L3  架构健康                评估架构本身
```

**四层对应四个"进化什么"**，与母巢 `evolution_op.py` 的
RSPL 资源（prompt/agent/tool/memory/policy）思路一致，但粒度更实。

---

## 五、V9 的论文支撑（与 DWC 已读的 19 篇重叠情况）

| V9 组件 | 论文 | DWC 的 19 篇里有没有 |
|---|---|---|
| Weibull + Sleep Cycle | Decay in AI Memory Systems | ✗ 没有（记忆衰减，不在 19 篇里） |
| RRF 三路融合 | TREC 2025 RAG Track | ✗ 没有 |
| Playbook 演化 | ACE: Agentic Context Engineering | ✗ 没有 |
| Per-Tool 断路器 | AppScale 2026 | ✗ 没有 |
| 置信度加权 | CISC (arXiv:2502.06233) | ✗ 没有 |
| 去中心化记忆 | DecentMem (arXiv:2605.22721) | ✗ 没有 |

★ **19 篇 RSI 论文里没有一篇讲记忆检索/衰减/融合。**
这是这次调研的一个真空——**DWC 的"记忆"那一半，19 篇提供不了，
需要靠 Prometheus 12 代 + MSTAR 线的经验。**
