# DWC 进度

> 每条进度须**声称 / 实测 / 取数命令** 三栏。
> "分析过了 / 设计好了 / 读过了" **不算进度**。

| 项 | 声称 | 实测 | 取数命令 |
|---|---|---|---|
| 立项 | 定位已定：独立 agent，记忆 + 自进化 | README.md 3,648 B | `wc -c README.md` |
| 边界澄清 | DWC 不沿用母巢架构 | README/QUALITY_GATE/lessons 已标注定位 | `grep -rn 母巢 docs/ \| head` |
| 论文研究 | RSI 全文深读 | **30 份报告落盘**（2026-10-04 实测） | `ls docs/papers/*.md \| wc -l` |
| 数字核验 | 报告数字可溯源 | VERIFICATION.md 存在 | `ls docs/papers/VERIFICATION.md` |
| 质量门 | 7 道门可执行 | **`gate.py` rc=0 · 7 门全绿**（2026-10-04 实跑） | `python scripts/gate.py` |
| ★ 架构 | **架构设计已定稿**（§1–§11 + 七环节 + 19 族判据） | **ARCHITECTURE.md 161,952 B** | `wc -c ARCHITECTURE.md` |
| ★ 缺口销账 | **11 项已销账**（A1–A7 · §二①②③ · C3'） | `docs/GAP_AUDIT.md` 内 11 项全标 ✓ | `grep -c "【已做" docs/GAP_AUDIT.md` |
| ★ 世界树收束 | 两条路线并列 + A2（剪枝策略 / 想象节点存哪） | `docs/WORLD_TREE_CONVERGENCE.md` 15,502 B | `ls -l docs/WORLD_TREE_CONVERGENCE.md` |
| ★ 全量核对 | 声称 vs 实测已核一轮 | `docs/FULL_AUDIT_2026-10-04.md` 落盘 | `ls docs/FULL_AUDIT*` |
| ★ 测试 | **首份测试已固化**（12 项） | `tests/test_gate_n_a.py` · 变异验证 3/3 抓到破坏 | `python -m pytest tests/ -q` |
| ★ 质量门 | **三态化**（pass / fail / **n_a 无可检对象**） | 空仓库下 5/7 道报 n_a，`rc=1` | `python scripts/gate.py` |
| ★ config | **首批两份已落盘** | `config/iron_laws.yaml` + `config/capability_groups.yaml` | `ls -l config/` |
| 承重代码 | — | **0 行**（刻意为空） | `find src -name '*.py' \| wc -l` |
| 测试代码 | — | **0 行**（刻意为空） | `find tests -name '*.py' \| wc -l` |

---

## 阶段

**架构设计已定稿；承重代码 0 行（刻意为空）。**

★ 承重代码为空的依据：`ARCHITECTURE.md` 原则区「架构定稿前不写承重代码」。

---

## ★ 目录导航

```text
docs/INDEX.md —— ★ 开工先看这个（26 份核心设计 + 6 个子目录 + 2 个 4 MB 原始产物）
★ 别通读 docs/：docs/repos/_all.json 是 3.4 MB 的仓库全文抓取
```

---

## ★ 续接点（跨会话必读）

```text
docs/RESUME_2026-10-04_FINAL.md  ← 当前有效
★ RESUME_2026-10-04_EARLY / NIGHT 均已过期（早于本轮 11 项销账）
  ★★ 但 EARLY 里的 ARSI 硬缺陷审计（带行号）仍是有效证据, 别删
```

---

## 下一步

1. ~~写 config/ 第一批~~ ✓ **已完成**（2026-10-04）:
   · `config/iron_laws.yaml`（11 条 = G1–G10 + G11；含 D1/D2 两条加载纪律）
   · `config/capability_groups.yaml`（三组 + Λ 计数口径 + 派生字段声明）
   · 两者均已实测：G1–G6 与 I10–I12 全部通过
2. **实现 `src/dwc/foundation/contracts.py`**（六条通用约定 + 负面测试基类）
3. 实现 `check_fn` —— 按 `iron_laws.yaml` 里声明的 11 个函数名逐个写
   ★ 判据 I8 要求每个 check_fn 的**调用点 > 0** ⇒ 写完须 grep 验证
   ★ D2 纪律（anti_stall）要求 check_fn 不得是已知空转名
4. 实现能力组加载器（重算派生字段 `lambda_floor_ratio = 1/median`）
5. 每落一族，同步写它的**阳性测试**（喂违规输入断言 raise）

★ 不要先写 `world_model`：它的 `predict` 不许返回 `confidence`（判据 P4），
  而这条现在只是设计推理，尚无代码可 grep 验证。

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
★ 本轮教训: 本文件曾落后实际进度 21 倍（架构 7,640 B vs 实际 161,952 B），
  而它是全项目唯一强制"声称 vs 实测"的文档
  ⇒ ⇒ 一个自己规定了取数命令的文档，自己的数字必须可复跑
```

---

> 注：`docs/papers/` 下报告的 §5「可迁移」是**研究结论**，
> 不是设计依据。它们回答"论文能提供什么机制"，
> 不回答"DWC 该采用哪个机制"。

*本表最后实测：2026-10-04 · 上一版实测约在 2026-10-03（ARCHITECTURE 7,640 B 时）*