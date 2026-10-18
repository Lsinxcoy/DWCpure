# 17 项落地计划（Cai 2609.08175 ＋ 18813 companion 合并去重）

> 立项：2026-10-18 · 来源：三卡回读（18813-5 续读、 Cai-1 查账已销项不在列）
> 顺序：P0 → P1 → P2 → P3 · 状态机：todo / doing / done

## P0（先查·零成本）—— 2026-10-18 已完成

| 项 | 结论（一行） | 决定下游 |
|---|---|---|
| B2 observe 区分度核查 | **observe 的锅**：559 fails→55 distinct sigs，top-10 各 18×逐字相同；346/559=62% 是 E_NO_RESULT"压根没跑这个函数"；test_math_002 20 fails→2 sigs，reasoning_001 20→2。执行通道系统性没让目标函数被跑过，不是任务真同质 | B1、B3 成立，开工 |
| E1 anchor 污染自查 | **指控成立一半**：dev＋sealed 的 fn/args 形态都进过 trial/peer prompt（obs_skeleton 只曝形态不曝 expected；R299 hint 成功码喂 peer）。held_out=配对复测（形态见过、答案没见过），不是盲测 | held_out 叙事降级；A1 fresh 集硬约束：fn/args/checks 全程不进任何 prompt |
| A5 基线刷新纪律 | **无需新机制**：R299-b 快照=每 trial 现拍 live，无"首落"概念；_land_adopted 只写 RULES 不记分，下一 trial 自动以 adopt 前末 point 为对照（treatment-vs-control 天然成立）；生产零 adopt（rules.json 缺席＋ledger 零 landed:true），纪律暂空转 | A5 闭项，记注释纪律即可 |

取数命令：
- `python -c` 读 config/anchors/evidence.jsonl（559/55/346，见 R311 档）
- `sed -n '380,420p' scripts/dwc_evo_round.py`（sealed 进 prompt 实证）
- `sed -n '2262,2300p' src/dwc/organs/evolver.py`（adopt 不记分）＋ `ls config/anchors/rules.json`（缺席）

## P1（小成本/零成本）

| 项 | 依赖 | 状态 |
|---|---|---|
| D1 execution variation（spread 常驻 report） | 无 | done（R311：--repeat N＋spread，3测绿/2096回归绿） |
| A3 小 Δ 熔断（Δ＜spread 直接不验） | D1 | done（R312：_evo_spread＋双路熔断，4测绿/2100回归绿） |
| A2 门参数 (λ,δ,γ) 显式化（注释级） | 无 | todo |
| A4 J 保护机器化（gate 加"evo 写 judge/anchor 即红"） | 无 | todo |
| A6 peak-picking 禁令（纪律） | 无 | todo |
| C2 carried 率（ledger 扩展） | 无 | todo |
| C3 RULES provenance＋withdraw | 无 | todo |
| D2 envelope 声明（report 声明 calls/rounds/tokens） | 无 | todo |
| D4 术语改名 run_round 四段 | 无 | todo |
| B3 火力转 code_fix 组（决策） | B2 done | todo |

## P2（中成本）

| 项 | 依赖 | 状态 |
|---|---|---|
| B1 code_fix_007 独立成簇＋换 ξ（单发试跑） | B2 done | todo |
| B4 候选池 N 扩大（多 proposal 并行） | 无（LLM 预算） | todo |

## P3（大成本）

| 项 | 依赖 | 状态 |
|---|---|---|
| A1 fresh 独立验证集＋accept 门 Eq.8 四数 | E1 硬约束（形态不进 prompt） | todo |
| C1 RULES lineage 选择（archive→adopt 两步） | 无 | todo |
| D3 crossed evaluation（双向 cross） | 无（双倍评估） | todo |

## 收官纪律

- 每项一轮一知识档（R311 起，断档不再犯）＋同批提交
- 三层验证 pytest＋gate＋e2e；破坏验证打中核心声称
- 本文件逐项翻状态：todo→doing→done
