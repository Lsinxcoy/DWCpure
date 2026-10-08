# RSI 综述深读计划（2609.11873）— 跨轮进度文件

> 任务: 深度精读 arxiv.org/abs/2609.11873（"The Last AI Built by Humans: Toward
> Genuine Recursive Self-Improvement"）+ 覆盖全部引用论文全文精读 + 多轮反刍 +
> 结合 DWC 当前实现给强化方向。多轮大任务, 本文件为续接真源。

## 材料清单（已核）

- 综述本体: `papers/arxiv_2609.11873/2609.11873.txt` 318,000 字符（genuine ✓）
  - 正文到 228,927; 书目 157 条; 正文引用 559 次 / 156 key
  - 参考图谱: `refmap.json`（285 rows 归一后 157, freq×arxiv）
- 书目 157 条分层:
  - 23 篇有 arXiv ID → `refs/<id>.pdf` 批量抓取
  - 50 篇无 ID 但 f≥3（含 f=34 Zhang2026/C-evolve、f=18 Li/C-evolve、ADAS、STOP
    等核心文献）→ 需按标题搜 ID 补齐
  - 其余 f<3 或非 arXiv 材料（OpenAI 报告、工业 blog 等）

## 综述结构（第一轮解析）

- §1 背景: 1.1 Scaling / 1.2 From Development… / 1.5 Application Domains /
  1.6 Industrial Evidence
- §2 概念: 2.1 Uneven Capability / 2.2 Conceptual（**2.2.1 Anatomy of an
  Improvement Loop** / 2.2.3 Relation to Neighboring Paradigms）
- §3 ★核心框架: **L1 Execution → L2 Strategy → L3 Experience → L4 Deployment →
  L5 Recursive Improvement**（各层含 "Evaluating L{n} ..." 小节）+ 3.7 Cross-Level
- §4 进化对象: 4.1 Agents/Reflection · 4.2 Skills/Memory/Harness/**World** ·
  4.3 Coding-Agent · 4.4 Clinical/Healthcare
- §5 行业实验室: Lark / Agent-Native Research Lab 等
- 附录 A: RSI Landscape（大表）· 附录 B: Industry Landscape（大表）

## 轮次计划（每轮 commit + 知识档, 同批自洽前瞻法）

- [ ] R93 · 综述本体第一轮精读（§1–3+结论逐段）+ 23 篇抓取 + 无 ID 高频补搜 → 本文件+综述笔记
- [ ] R94 · 批量全文精读第一层（Top 支柱逐行, 子代理并行, 每篇 docs/papers/<id>.md）
- [ ] R95 · 批量第二层（其余分层扫读, 诚实条款标注深度）
- [ ] R96 · 多轮反刍（换视角: 跨篇冲突/否定grep/概念横搜 → 硬结论）
- [ ] R97 · 综合报告九节（材料清单/缺口/硬结论/可抄机制/冲突/三档计数）+ DWC 强化方向

## 深度分层诚实条款（最终报告须含）

- 精读深度将逐篇标注: 逐行 / 章节 / 摘要级（抓到全文≠读过全文）
