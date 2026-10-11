# DWC 论文深读 · 索引

**26 篇**报告（RSI 递归自我改进 + direction 选择器专项，2026-10-12 起后者并入同库）。**全部基于全文**，非摘要。
★ 其中 2609.2680 是**协议层上位框架**，建议优先读。

## 读法

| 文件 | 用途 |
|---|---|
| **`COMPARISON.md`** | ★ **先读这个** —— 24+2 篇横向对比表，按"递归施加在什么上"分类 |
| `REPORT_SPEC.md` | 报告规范（六节骨架 + 五条诚实条款） |
| `VERIFICATION.md` | 数字溯源核验记录（含我自己犯的两个错） |
| `../RSI_PAPERS.md` | 19 篇清单（标题 + 摘要，按主题分组） |
| `../papers/` | 原始 HTML 全文 |
| `../papers_txt/` | 纯文本全文（**不入库** — `.gitignore` 显式排除，本地留存；引用时以各篇报告头部注明的抓取路径为准） |

## 19 篇报告

| arXiv | 简称 | 递归对象 | 读到范围 |
|---|---|---|---|
| [2608.24876](2608.24876.md) | Recuris | 记忆控制层 | 全文 |
| [2606.09498](2606.09498.md) | Self-Harness | harness 协议 | 全文 |
| [2609.14857](2609.14857.md) | ModularRSI | harness 模块 | 全文 |
| [2606.14249](2606.14249.md) | HarnessX | harness 结构 | 全文 |
| [2609.24972](2609.24972.md) | RRSI | harness 正则 | 全文 |
| [2609.14858](2609.14858.md) | Dream-RSI | 探索策略 | 全文 |
| [2609.04128](2609.04128.md) | Environment Evolution | 环境难度 | 全文 |
| [2608.27287](2608.27287.md) | **Astar**（Lazada 广告） | **进化方向提出**（三级 taxonomy） | 全文 |
| [2608.17933](2608.17933.md) | **EvoTS-Agent** | **停滞判据 + 三算子**（z_k 公式） | 全文 |
| [2607.12790](2607.12790.md) | Who Grades the Grader? | 评估函数 | 全文 |
| [2609.26457](2609.26457.md) | AIDE² | agent 程序 | 全文 |
| [2607.27201](2607.27201.md) | Mental World Modeling | 世界模型 | 全文 |
| [2607.27924](2607.27924.md) | ODEWorld | 世界模型 | 全文 |
| [2609.08183](2609.08183.md) | NeoHorse-1 | 模型权重 | 全文 |
| [2505.05522](2505.05522.md) | Continuous Thought Machines | 权重/连续思考 | 全文 |
| [2603.06333](2603.06333.md) | SAHOO | 护栏/漂移 | 全文 |
| [2603.25111](2603.25111.md) | SEVerA | 形式正确性 | 全文 |
| [2609.13406](2609.13406.md) | Generalized Agent Iteration | 元层形式 | 全文 |
| [2609.06396](2609.06396.md) | MetaRSI / RSI² | 元层代数 | 全文 |
| [2608.10299](2608.10299.md) | Co-Evolution 综述 | 判据 | 全文 |
| [2505.22954](2505.22954.md) | Darwin Gödel Machine (ICLR 2026) | 归档非贪心 +27.0pp；改自己代码 +11.0pp；阶梯评测 60→200 |
| [2603.19461](2603.19461.md) | HyperAgents | imp@k/imp@50（Γ_t 可运行实现）；冻结 meta agent 隔离 |
| [2607.07663](2607.07663.md) | RSI: Bounded Self-Refinement → Autonomous Research Loops | 验证层级四层；Mirror Loop 55% 衰减 |
| [2609.11873](2609.11873.md) | The Last AI Built by Humans | 自主等级综述 | 正文主干（References/附录未读，已标注） |
| ★ [2609.2680](2609.2680.md) | **RSI in AI: A Survey**（2026-10-04 新增） | ★ **协议层上位框架** | **全文**（58 页 / 221,636 字符，五轮反刍） |

## ★ 2026-10-04 新增：2609.2680（第 20 篇，也是**上位框架**）

```text
★ 这不是"第 20 篇同级论文", 是前 19 篇的**协议层上位框架**。
  来源: Preprints.org doi:10.20944/preprints202609.2680.v1, 2026-09-30
  32 位作者 / 404 篇书目 / NOT PEER-REVIEWED / 标注使用 ChatGPT 辅助写作

★ 它的 §3.3 / §3.4 / §7 把 DWC 已有的机制重新组织成一个统一协议:
  DWC 已采的机制                  本文中的位置
  ──────────────────────────────────────────────────
  2609.24972 非补偿四判据       →  §7.2 式9 的 Δ̂_val 项（部分）
  2609.24972 退火预算 b_t       →  §7.3 式10 成本台账 + 式9 的 C ≤ B
  2607.12790 三 split / 独立判官 →  §7.2 dev/val/sealed 分离（同源）
  2603.06333 停止规则 / GDI     →  §7.5 quality vs cumulative cost
  2608.24876 Eq.9 三段隔离      →  §3.3 式4 的 R_t（验证与保留机制）
  2609.13406 grounded 双条件    →  §3.3 的 C（外部固定条件）
  2609.14858 Dream-RSI 回放     →  §5.3 archives / §7.5 replay
  2609.11873 五元 χ 盘点        →  互补: 那篇给"谁在改", 这篇给"怎么验证在改"

★ 它比 DWC 已有 19 篇更完整的三处（DWC 应吸收）:
  ① ★ 三主张分离: Δ_t（任务增益）/ ρ,τ（保留迁移）/ Γ_t（改进器增益）
     原文: "Neither positive Δ_t nor positive τ_t isolates the improver."
     ⇒ 直接命中 DWC §9 第 20 项（守卫① 矛盾）与 JUDGE_LAYERS 的 L3 设计
  ② ★ 配对探针 Γ_t（式 8）: 同一 held-out 起始求解器 + 同预算, 比 I_t 与 I_0
     ⇒ DWC 的 L3 独立审计应采用此形式, 而非简单滑动准确率
  ③ ★ 保护组回归约束: r̂_{t,j} ≤ ϵ_j ∀j  —— ★ DWC 当前完全没有这一项

★ 它自陈的不足（DWC 要注意）:
  ① "Current evidence leaves unrestricted, indefinitely sustained or reliably
      accelerating RSI unestablished."
  ② "This is a narrative survey, not an exhaustive systematic review or a meta-analysis."
  ③ 只对 8 个工作做了 protocol coding（其余 12 个 "not protocol-coded here"）
  ④ Table 1 自评九维全 ✓（自评偏乐观）
```

## 三句话总结这 19 篇

```text
1. 递归的对象可以是记忆、harness、策略、环境、评估函数、权重 ——
   但 19 篇里只有 4 篇在 DWC 的模型条件下真能执行（零闭源依赖）。

2. "门必须是外部的、有回归锚点的"这条，被三篇互不引用的论文独立证实。

3. 领域的真实成色：多数核心结论缺方差报告或消融。
   A 类（有区间估计+失败案例）5篇，B 类（不可依赖数字）6 篇。
```

---

*深读完成 2026-10-02 · 19/19 · 数字溯源全部核实*
*2026-10-04 新增 2609.2680（第 20 篇，上位框架）· 21/21 数字核实*

**第二轮精读**（选乙：吃透再推进，12 篇逐行/结构级）：

| 论文 | 为什么读 | 关键产出 |
|---|---|---|
| [2608.03392](SELF_EVOLVING_SURVEYS.md) 自进化编码 agent | ★★★ `A_t=(S_t,H_t,θ_t)` 三元 + §10 五条硬约束 | 跨层自评=第20项根源；15/60 幻觉护栏；add-only 持久 |
| [2603.25681](2603.25681.md) 自改进展望（TMLR 09/2026） | ★★★ Coupled/Decoupled 形式化 | self-directed selection 是被点名的空白；理论断言 intractable |
| [2404.13501](MEMORY_EVOLUTION_SURVEYS.md) 记忆机制综述 | 记忆三操作 + 三评估指标 | Reference Accuracy(F1)；领域无记忆基准 |
| [2404.14387](MEMORY_EVOLUTION_SURVEYS.md) 自进化综述 | 自主性三档公式(8)(9)(10) | DWC=Medium；"三轮后不再进步" |
| [2501.07278](MEMORY_EVOLUTION_SURVEYS.md) 终身学习路线图 | 记忆四分类 + 五评估公式 | FGT/BWT/FWT 直接填缺口 (c)(i) |
| [2507.21046](SELF_EVOLVING_SURVEYS.md) 自进化 agent 综述（TMLR 01/2026） | What/When/How/Where 四轴 | intra/inter test-time = Persistence 边界 |
| [2504.01990](SELF_EVOLVING_SURVEYS.md) Foundation Agents(396页) | 第 II 部分 100 页自进化专章 | holistic optimization = 改架构层；三轴成本口径 |

★ **全部深读总结**：[`../DEEP_READ_REPORT_2026-10-04.md`](../DEEP_READ_REPORT_2026-10-04.md)
