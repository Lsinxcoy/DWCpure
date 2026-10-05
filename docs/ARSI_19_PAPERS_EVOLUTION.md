# ARSI 的 19 篇论文：多少篇关于进化

> 2026-10-03 · 判据：逐篇读标题 + 摘要 + ARSI 源码里的引用位置，不按文件名推断
> 口径：`E:/Divine Wisdom Core/papers_txt/` 下 19 篇 = ARSI 引用的论文集合

---

## 一、答案

```text
★ 19 篇中 16 篇关于进化, 3 篇不是。

  A 类 (关于进化)          16 篇  ← 84%
  B 类 (非进化: 世界模型/认知) 3 篇  ← 16%

★ 而且: 3 篇非进化的论文在 ARSI 里也不是"进化支柱", 而是"世界模型支柱"(L3)。
  ARSI README 的六层架构里:
    L3 Introspective World + Vitals ← 来源正是这 3 篇 (SIWM/ODEWorld/CTM)
    其余 L0/L1/L2/L4/L5 全部来自 A 类 16 篇
```

---

## 二、A 类 · 关于进化的 16 篇（逐篇）

### 2.1 RSI 框架/形式化（4 篇）

| arXiv | 标题 | 进化主题 |
|---|---|---|
| 2609.13406 | Generalized Agent Iteration: One Formal Framework for Iterative Policy Improvement and Recursive Self-Improvement | RSI 形式化框架 |
| 2609.06396 | MetaRSI（loop kernel + three operators + 五序可行） | RSI 框架 + **调度器自改进** |
| 2609.11873 | The Last AI Built by Humans: Toward Genuine Recursive Self-Improvement | RSI 综述（自主性分级 B0/L1/L2） |
| 2609.26457 | Recursive self-improvement of AI research agents | 研究 agent 的 RSI（AIDE²） |

### 2.2 harness 自我改进（4 篇）

| arXiv | 标题 | 进化主题 |
|---|---|---|
| 2606.14249 | HarnessX: A Composable, Adaptive, and Evolvable Agent Harness Foundry | 可进化 harness + AEGIS（Digester/Planner/Evolver/Critic） |
| 2606.09498 | Self-Harness: Harnesses That Improve Themselves | harness 自改进（弱项挖掘→提案→回归验证） |
| 2609.14857 | ModularRSI: Modular and Generalizable Recursive Harness Self-Improvement | 模块化 harness RSI |
| 2609.24972 | RRSI: Regularized Recursive Self-Improvement of Agent Harnesses | 正则化 harness RSI（非补偿式准入） |

### 2.3 协同/环境/记忆/评估器进化（4 篇）

| arXiv | 标题 | 进化主题 |
|---|---|---|
| 2608.10299 | Co-Evolution in Agentic Systems: Toward Self-Directed Evolution Beyond Human Design | 协同进化三阶段（agent-agent / agent-env / meta） |
| 2609.04128 | Environment Evolution for Terminal Agents | **环境进化**（序列引导的环境演化） |
| 2608.24876 | Recursive Experiential–Working Memory Evolution for Long-Horizon Agent Harnesses | **记忆递归进化**（验证门控补丁准入） |
| 2607.12790 | Who Grades the Grader? Co-Evolving Evaluation Metrics and Skills for Self-Improving LLM Agents | **评估器协同进化**（double ratchet） |

### 2.4 RSI 安全/验证/后训练（4 篇）

| arXiv | 标题 | 进化主题 |
|---|---|---|
| 2603.06333 | SAHOO: Safeguarded Alignment for High-Order Optimization Objectives in Recursive Self-Improvement | RSI 对齐安全（GDI/CAR 漂移指标） |
| 2603.25111 | SEVerA: Verified Synthesis of Self-Evolving Agents | 自进化 agent 的**形式化验证**（FGGM） |
| 2609.08183 | NeoHorse-1: Towards Recursive Self-Improvement via Agentic Post-Training with Routing Harness | RSI via 后训练 + 路由 harness |
| 2609.14858 | Dream-RSI: Recursive Self-Improvement through Evolving Worlds | RSI via **进化世界**（回放目标 V^{m⋆}≥V^0） |

---

## 三、B 类 · 非进化的 3 篇（逐篇）

| arXiv | 标题 | 主题 | 在 ARSI 的位置 |
|---|---|---|---|
| 2505.05522 | Continuous Thought Machines | 认知架构（内部 tick 循环推理） | L3 世界/自我 |
| 2607.27201 | Mental World Modeling | 心智世界模型（ToM/联合状态） | L3 世界/自我 |
| 2607.27924 | ODEWorld: A Continuous Predictive Architecture via Physical-Time Flow | 连续预测世界模型 | L3 世界/自我 |

**★ 判据（为什么这 3 篇不算"关于进化"）**：

```text
它们的核心贡献是"如何建模世界/如何做内部推理", 不是"系统如何改变自己"。
摘要里没有 evolve / self-improve / RSI / co-evolve 的动作语义。

★ 但它们在 ARSI 里承担关键角色 —— L3 层 "世界/自我如何流":
  README 原文: "L3 | Introspective World + Vitals | SIWM/ODE/CTM + SAHOO | 世界/自我如何流, 何时漂"
  ★ 即: 它们是"世界模型"支柱 (决策核心), 不是"进化"支柱。
```

---

## 四、★ 交叉验证：与 ARSI 六层架构对账

```text
ARSI README 的六层 (2026-09-23 二次研读后升格):
  L0 Anchored Constitution   ← GAI 2609.13406            [A 类]
  L1 Contracted Computation  ← SEVerA 2603.25111         [A 类]
  L2 Regularized MetaRSI     ← RRSI 2609.24972 × AIDE² 2609.26457  [A 类]
  L3 Introspective World     ← SIWM/ODEWorld/CTM + SAHOO [★ B 类 3 篇 + A 类 1 篇]
  L4 Dream-RSI               ← 2609.14858                [A 类]
  L5 Evaluative Epistemology ← Grader 2607.12790         [A 类]

★ 6 层里 5 层来自 A 类, L3 是唯一的混合层 (3 篇 B 类 + 1 篇 A 类 SAHOO)。
★ 即: 进化是 ARSI 的绝对主线, 世界模型是辅助线。
```

---

## 五、★ 一个值得注意的分布

```text
按主题分:
  RSI 框架/形式化       4 篇
  harness 自我改进      4 篇
  协同/环境/记忆/评估器  4 篇
  RSI 安全/验证/后训练   4 篇
  ────────────────────────
  合计                 16 篇  (★ 四类各 4 篇, 分布极均匀)

★ 这个 4×4 分布说明: ARSI 的论文选择不是"围绕一个点", 而是
  把"进化"拆成了四个正交问题:
    ① 怎么形式化 (框架)
    ② 改什么 (harness)
    ③ 和谁一起进化 (协同/环境/记忆/评估器)
    ④ 怎么不出事 (安全/验证)

★ 对照 DWC 的进化核心设计, 这四类正好对应:
    ① → DWC 的"顺序约束 + 离线回放"
    ② → DWC 的"21 个可进化对象 + 落地器"
    ③ → DWC 的"事件源三层 + 记忆核心"
    ④ → DWC 的"门 + 骨骼区 + 不可违反约束"
```

---

## 六、诚实边界

```text
① "19 篇"的口径 = DWC/papers_txt/ 下的 19 个 .txt。
   我核实了这 19 个编号全部在 E:/ARSI 仓库里被引用 (1~22 个文件不等)。
   但 ARSI 自己有没有一份"官方 19 篇清单", 我未找到 (README/PROGRESS 里只有 11 个编号)。
   ⇒ 若你说的"19 篇"另有所指, 请指出出处, 我按那个口径重算。
② 分类是"主题判据"(标题+摘要的进化语义), 不是"论文是否可用于进化"。
   B 类 3 篇的世界模型方法在原理上也能用于"进化世界" (如 Dream-RSI 就用了回放世界),
   但论文本身的主题不是进化。
③ 2609.06396 的标题我未从原文直接读到 (摘要段被图表说明占据),
   按 README 的 "MetaRSI" 支柱与 2609.06396 的对应关系判定。
```

---

## 附：存证

```text
脚本: scripts/extract_abstracts19.py  scripts/classify_papers19.py
数据: .cache/papers19_abstracts.txt  .cache/papers19_classify.json  .cache/papers19_final.json
源码: E:/Divine Wisdom Core/papers_txt/*.txt  (19 篇)
引用: E:/ARSI/ (19 个编号全部命中, 逐编号文件数已核)
```
