# DWC 进度

> 每条进度须**声称 / 实测 / 取数命令** 三栏。
> "分析过了 / 设计好了 / 读过了" **不算进度**。

| 项 | 声称 | 实测 | 取数命令 |
|---|---|---|---|
| 立项 | 定位已定：独立 agent，记忆 + 自进化 | README.md「当前状态」节（R58 刷新） | `wc -c README.md` |
| 边界澄清 | DWC 不沿用母巢架构 | README/QUALITY_GATE/lessons 已标注定位 | `grep -rn 母巢 docs/ \| head` |
| 论文研究 | RSI 全文深读 | **30 份报告落盘** | `ls docs/papers/*.md \| wc -l` |
| 数字核验 | 报告数字可溯源 | `docs/papers/VERIFICATION.md` 3.4K | `wc -c docs/papers/VERIFICATION.md` |
| 质量门 | **8 道门（G1–G8）**可执行 | **`gate.py` rc=0 · 8 门全 PASS**（2026-10-08 实跑） | `python scripts/gate.py` |
| ★ 架构 | **架构 v4 定稿**（器官式骨架 + 进化循环七环节 + 判据族） | **ARCHITECTURE.md 169,406 B** | `wc -c ARCHITECTURE.md` |
| ★ 缺口销账 | **11 项已销账**（A1–A7 · §二①②③ · C3'） | `docs/GAP_AUDIT.md` 内 11 项全标 ✓ | `grep -c "【已做" docs/GAP_AUDIT.md` |
| ★ 世界树收束 | 两条路线并列 + A2（剪枝策略 / 想象节点存哪） | `docs/WORLD_TREE_CONVERGENCE.md` 15,502 B | `wc -c docs/WORLD_TREE_CONVERGENCE.md` |
| ★ 全量核对 | 声称 vs 实测已核一轮 | `docs/FULL_AUDIT_2026-10-04.md` 10.1K | `wc -c docs/FULL_AUDIT_2026-10-04.md` |
| ★ 测试 | 首份 12 项（10-04）→ **现 760 项全过** | `760 passed in 18.2s` rc=0（2026-10-08） | `python -m pytest tests/ -q` |
| ★ 质量门三态 | pass / fail / **n_a 无可检对象** | `tests/test_gate_n_a.py` 20.1K 在 | `wc -c tests/test_gate_n_a.py` |
| ★ config | 首批两份 → **现 7 项**（iron_laws/dials/difficulty/capability_groups/llm.json/drift.yaml/anchors/） | `ls config/` 实列 7 项 | `ls config/` |
| ★★★ 承重代码 | **29 个 .py / 12,088 行**（R18 建 git 起，从 0 写到 R86） | 12088（2026-10-08 实测） | `find src -name '*.py' -exec cat {} + \| wc -l` |
| ★★★ 测试代码 | **35 文件 / 713 函数 → pytest 收集 760 项** | 同「测试」行实测 | `ls tests/*.py \| wc -l` · `grep -rho 'def test_' tests/ \| wc -l` |
| ★★★ 七器官 | **7/7 全齐**：memory·judge·actor·evolver·world_model·iwm·iron_laws ✓ | `organs/` 13 文件（含 __init__；applier/candidates = evolver ④ 支撑体；weakness/el_sched/direction/replay = ⑥ search/ 四件全落 R69-R74） | `ls src/dwc/organs/` |
| ★★★ 七环节 | **7/7 全齐**：①②③④(evolver)+⑤防漂移(iwm,R61)+⑥探索(world_model)+⑦盘点 ✓ | iwm.drift 已接 run_term 3.5 步并消费为 drift_degrade 任务 | `grep -n '环节⑤\|环节⑥' src/dwc/harness/run_term.py` |
| ★★★ 三入口 | **3/3 全齐**：ingest·step·run_term 收拢进 core.py 主类（R62） | `grep -c 'def ingest\|def step\|def run_term' src/dwc/core.py` = 3；共享记忆有测试 | `grep -n 'def ingest\|def step\|def run_term' src/dwc/core.py` |
| ★★★ 记忆对照实验 | **R67 终局判读（事前规则, repeat=4, 64 trial）**: none 0.688 / guidance 0.812 / replay 0.750 — **两检验对两口径全部 |Δ|≤2 = 噪声**; R66 的 n=1 翻转未复现（002 上 replay 0P4H, 其口径B 1.000 是幸存者偏差）; 易题三臂恒全过零区分度+端点 8 次挂 ⇒ **实验线终局: V1 与论文方向在单步修复任务族未获支持** | `python src/dwc/experiments/mem_guidance_vs_replay.py` |
| ★★★ 端到端 | e2e **三段绿**（LLM / land / retire） | rc=0 · `LLM_SEGMENT=passed · LAND_SEG=landed · RETIRE_SEG=retired`（2026-10-08） | `python scripts/e2e_loop.py` |
| ★★★ LLM 真端点 | 候选生成走真 LLM（非 mock，需 config/llm.json） | e2e step9 `LLM_SEGMENT=passed` | 同上 |
| ★★★ δ 拍板 | R58：δ=0.15 落地 + 纪律锁值同步 | 破坏 δ→0 ⇒ 2 条纪律测试红 ⇒ 恢复绿；`NOISE_DELTA = 0.15` | `grep -n "NOISE_DELTA = " src/dwc/organs/evolver.py` |
| ★★★ 轮次 | R1–R163 · 每轮一知识档 | **172 commits** · `archive/knowledge3_R*.json` | `git rev-list --count HEAD` |

---

## 阶段

**代码已进主干：进化内核（①诊断 ②对象 ③门 ④落地）闭环，判据 / 记忆 / 铁律 / 因果链 / 五元盘点建成。**

```text
七器官 **7/7** · 七环节 **7/7** · 三入口 **3/3** —— 架构形态三线全齐（R62 收拢）。
★ 当前形态 = 「一个能被当 agent 使用的组装体」: `DWC(depth_limit, max_nodes)` 造出,
  ingest/step/run_term 三入口可用, 器官共享同一份记忆（有测试锁）;
  决策第一层（dynamics 预测）诚实缺席、动作分发只通 remember —— 见 core.py 诚实边界。
★ 仍欠的深度（全齐 ≠ 全深）: Z4/Z5 · δ_θ · ECE · Appendix D 概率回归 ·
  coupling · 动作分发全路由 · contracts.py 老债。
★ 依据: 上表「七器官 / 七环节 / 三入口 / 端到端」四行（取数命令可复跑）。
★ 旧依据（10-04）「架构定稿前不写承重代码」已完成使命 —— 代码自 R18 起进主干。
```

---

## ★ 目录导航

```text
docs/INDEX.md —— ★ 开工先看这个（26 份核心设计 + 6 个子目录 + 2 个 4 MB 原始产物）
★ 别通读 docs/：docs/repos/_all.json 是 3.4 MB 的仓库全文抓取
```

---

## ★ 续接点（跨会话必读）

```text
docs/RESUME_2026-10-04_FINAL.md  ← 设计侧有效；代码侧已被 R18–R58 超越, 以本表为准
★ RESUME_2026-10-04_EARLY / NIGHT 均已过期（早于本轮 11 项销账）
  ★★ 但 EARLY 里的 ARSI 硬缺陷审计（带行号）仍是有效证据, 别删
```

---

## 下一步

1. ~~写 config/ 第一批~~ ✓ **已完成**（2026-10-04；现 config/ 共 6 项）
2. ~~建 `world_model` 器官~~ ✓ **R60 已完成**（2026-10-08）:
   · 一套树(23 条新测试: W1–W6 判据 + 行为 + 环节⑥接线) + 任务源已接 `_next_task_source`
   · Z6 卡住检测读 config/world_tree.yaml（Z1–Z3 由 dial 生效中）
   · ★ 仍未做（下轮候选）: δ_θ 残差难度（路线丙）· 三方向枚举 ·
     EL 完整调度器 · **Z4 候选持久化 / Z5 merge**（config 声明待落）
3. ~~建 `iwm`~~ ✓ **R61 已完成**（2026-10-08）:
   · 四方法对齐 ORGAN_INTERFACES §六（drift/self_trust/governor_advice/probe）
   · GDI 四信号（semantic 缺席显式+归一）· CAR · 回归（judge）· grounded（dials）
   · 环节⑤ 已接 run_term 3.5 步, drift_degrade 消费点与 over_tau 一致（原则 9）
   · 顺带落地 foundation/state.py（STATE_SCHEMA 四层 frozen = I6 构造面）
   · ★ 仍未做（下轮候选）: ECE 惩罚（需 Advice 加自报置信字段）·
     Appendix D 概率回归 · coupling 三条件 · Δ_semantic 的嵌入源
4. ~~class DWC 主类三入口~~ ✓ **R62 已完成**（2026-10-08）:
   · core.py 主类（§11.2 落点）: 七器官组装 + ingest/step/run_term 三入口
   · run_term 委托 TermRunner（六步不重写）; 入口与 runner **共享同一 memory**（破坏验证）
   · step 三层决策诚实降级: pre_enactment 显式缺席 · LLM 层可降级留痕 · heuristic 兜底
   · `from dwc import DWC` 惰性导出（PEP 562, 防循环导入）
   · ★ 仍未做: 动作分发全路由（learn/dream/evolve 只记录）· 决策 dynamics 层
5. `foundation/contracts.py` **仍未建**（2026-10-08 核实: `ls src/dwc/foundation/contracts.py` → 不存在）
   + `check_fn` 调用点 > 0 的 I8 核验 —— 老债保留，别当已完成
6. 能力组加载器派生字段 `lambda_floor_ratio = 1/median`：文件已有（capability_groups.py 247 行）
   但功能**未核** ⇒ 下次核
7. 每落一族，同步写它的**阳性测试**（喂违规输入断言 raise）

★ 写 `world_model` 的硬约束（PROGRESS 老条目, 仍有效）:
  `predict` **不许返回 `confidence`**（判据 P4）—— 守卫① 的 conf 已裁决:
  用 judge 在 dev split 上**外测**的世界模型准确率，评估时冻结，不听自报。

---

## ★ 两条仍在的诚实边界（做实现时会撞上）

```text
① action_gate 的归因混淆**未解决**（docs/LEVEL3_PROBE.md 诚实边界③）
   ⇒ iwm 的维护动作频率本身可能是另一个基因的效果
   ⇒ 前 b_t 轮（多编辑）无法归因，只有退火后的单编辑轮可判

② Γ_t 降级为"报告量"的论证**已被削弱**（docs/CLAIM_SEPARATION.md §七）
   ⇒ 原先"对齐成本随历史线性增长"已撤回（实测发现是空转循环造成的假象）
   ⇒ 现只剩"memory 工作态不可复现"一条理由
   ⇒ ★ 若将来发现 memory 可快照复现，Γ_t 也许能算 ⇒ 该裁决需翻案
```

---

## 引用约定（★ 新增，防再犯）

```text
★ 任何写进 ARCHITECTURE 的"已定"，必须同时满足三条:
  ① 落 docs/<FILE>.md（就地定稿需在 §9 该项下注明"就地定稿"）
  ② 落 §9 待定段的销账标记
  ③ 本表加一行 + 取数命令
⇒ ⇒ 缺任一条 ⇒ 视为未完成（★ 这正是本文件此前违反的规则）
★ 本文件已两次落后实际:
  第一次 落后 21 倍（架构 7,640 B vs 实际 161,952 B —— 10-04 抓到）
  第二次 停在"代码 0 行"而实际已 8,428 行（R18–R58 期间没跟 —— 10-08 刷新）
  ⇒ ⇒ 教训升级: **每次大轮次收官, 顺手重跑本表的取数命令列**
```

---

> 注：`docs/papers/` 下报告的 §5「可迁移」是**研究结论**，
> 不是设计依据。它们回答"论文能提供什么机制"，
> 不回答"DWC 该采用哪个机制"。

*本表最后实测：**2026-10-08（R58 · 从 0 行到 8,428 行后的首次全表刷新）** · 上一版 2026-10-04*