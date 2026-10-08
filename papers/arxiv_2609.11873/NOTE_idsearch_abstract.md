# RSI 综述 · 无 ID 书目补搜与摘要级扫读（R95, 第 4 层）

> 分层诚实条款（skill §8）: 本清单为**摘要级扫读**（abstract 逐字读, 未逐行全文）;
> 与 23 篇逐行精读（docs/papers/<id>.md）分层标注, 不混深度。

## 一、ID 补齐账（三层来源与命中）

| 来源 | 数量 | 说明 |
|---|---|---|
| 书目 External Links 直提 | **69** | 完整书目重解析（不截断）——最可靠 |
| web_search 精确查 | **9** | f≥3 高频补: C-evolve/SEAgent/STOP/ReasoningBank/AbsZero/OriGene(错配剔)/AFlow/EvoMDT/autoresearch |
| 已读 23 篇（key 重复） | ~6 | Decoevo/Trace2Skill/AutoKernel/SEA-Eval/Evo-memory 等 refmap 双 key 未合 |
| API 批量 | 0 | export.arxiv.org 持续 429（skill 阶梯记录复现）; search-HTML 结果 JS 渲染 curl 不可得 |
| 仍无 ID（f≤5 为主） | ~55 | 非 arXiv 材料（OpenAI/Meta blog、工业报告）+ 低频——书目级覆盖 |

**错配剔除（诚实记录）**: 2602.01550 搜到但实为 S1-NexusAgent ≠ OriGene ⇒ txt/pdf 已删
**待核 2**: EvoMDT(书目) vs OMGs(2602.13793 抓回, MDT 临床对上, 疑发表改名);
  autoresearch(2603.24647 抓回=HPO 评测论文, 综述引的 Karpathy repo 是否同篇待核)

## 二、9 篇摘要级扫读（abstract 逐字, 各一句核心 + DWC 相关点）

| ID | 核心 | DWC 相关（摘要级, 非深度结论） |
|---|---|---|
| 2310.02304 STOP | seed improver 自我改进, LM 提出 beam/遗传/模拟退火策略 | L5 代表（综述 Table7 已深读）; 摘要级确认: **LM 本身不变** |
| 2408.08435 ADAS | meta-agent 生成并评估 agent 存 archive | L2 agent 搜索代表; 摘要级确认固定 benchmark |
| 2410.10762 AFlow | MCTS 在可执行工作流图上生成 | L2 workflow 搜索 |
| 2505.03335 AbsZero | 零数据自博弈推理（proposer/solver 双角色） | B2 自博弈族; 无外部数据的课程自生 |
| 2508.04700 SEAgent | **World State Model 逐步轨迹评估 + Curriculum Generator** 从简到繁自生任务 | 与 DWC 世界树+难度分层同族; L3 |
| 2509.23331 C-Evolve | 岛屿进化保多样性; **fitness=组内投票贡献非个体分** | 多目标/群体评价与 DecoEvo Pareto 族同线 |
| 2509.25140 ReasoningBank | 推理记忆扩展 agent 自进化 | L4 记忆族（Trace2Skill 对照组） |
| 2602.13793 OMGs? | 临床 MDT 多 agent 协商 + SPEAR 五维评估 | S4 医疗域; EvoMDT 待核 |
| 2603.24647 HPO vs LLM | **经典 CMA-ES/TPE 持续胜 LLM agent**（固定预算, LLM 追不住优化状态） | **诚实提醒**: 自动化搜索不必优于成熟经典法——DWC 的"外部判据优先"同向 |

## 三、覆盖对账（用户要求"全部论文材料"的最终口径）

- **逐行精读**: 23 篇（f≥3 有 ID 全覆盖）→ docs/papers/<id>.md 六节
- **摘要级扫读**: 9 篇（R95 新抓）→ 本清单
- **书目级覆盖**: 其余 ~105 条（含 f<3、非 arXiv 工业材料）→ refmap.json 全清单
  （频次+引用语境+完整书目）+ 综述本体各节引用处语境
- **三份综述笔记**: NOTE_survey(本体 §1-3+§7) / NOTE_sec4_5(§4-5) / NOTE_appendix(附录逐格)
