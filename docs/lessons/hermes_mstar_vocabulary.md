# Hermes 线 / MSTAR 线 / CIP 线 —— 作者对「进化」是怎么理解的

> 本文只报原文实际写了什么。每条结论带「仓库名 + 文件路径 + 原文引用」三元组。
> 不用论文框架重新归纳。设计与实现分开标注。
>
> 数据源：`E:/Divine Wisdom Core/docs/repos/_all.json`（41 仓，README 全文 + 已抓 md）
> 补充源：GitHub API / raw（Lsinxcoy 账号），用于抓 `_all.json` 中抓空的两个仓库，以及线上最新版 README。
> 抓取时间戳：GitHub `created_at` / `pushed_at`（2026 年）。

---

## 0. 一句话结论

作者口中的「进化」在这 17 个仓库里**有三套互不相同的对象**：
MSTAR 线进化的是 **记忆程序（MemoryProgram / skill）**；
Hermes 主线进化的是 **skill + memory 的内容**；
CIP 线进化的是 **配置→技能→工作流→底层代码**（L1→L4 四层）。

只有 CIP 线明确写出「L4 底层代码 / 算法 / 数据结构」这一层；
但即使 CIP，也没有一处把「架构/结构本身可进化」作为**表述**写出来 —— 详见 §5。

---

## 1. 时间线：17 个仓库按 GitHub 创建时间排序

> 注：`hermes-personal-backup` 与 `-hermes` 在 GitHub API 上已 404（私有或已删），无法取 `created_at`，
> 用「—」标注，内容仍来自 `_all.json` 抓取。

| # | 创建日 | 仓库 | 自述定位（README 开头 / 仓库描述原文） |
|---|--------|------|--------------------------------------|
| 1 | 2026-04-15 | `hermes-skills` | "Lsinxcoy's custom skill library for Hermes Agent (NousResearch/hermes-agent)" / "This repository contains custom skills that extend Hermes Agent's capabilities." |
| 2 | 2026-05-12 | `hermes-mstar` | "Hermes MSTAR - Self-Evolving Memory System for Hermes Agent" / "**Hermes MSTAR** is a self-evolving memory system that combines genetic programming evolution with production-grade reliability tracking." |
| 3 | 2026-05-12 | `mstar` | "MSTAR - Memory System with Task-based Memory Architecture" / "**MSTAR**: 基于 MSTAR 论文的自我进化 AI 记忆系统" / "*基于 Karpathy's MSTAR 架构的自我进化记忆框架*" |
| 4 | 2026-05-13 | `hermes-agent` | "Lsinxcoy Hermes Agent configuration | forked from NousResearch/hermes-agent | includes custom skills, hermes-mstar integration, SkillClaw, and local modifications" |
| 5 | 2026-05-14 | `hermes-scripts` | "Hermes Agent 的自动化脚本集合，包含三系统进化循环（MSTAR + SkillClaw + Homunculus）…" |
| 6 | 2026-05-15 | `hermes-agent-backup` | "Hermes Agent full backup ( NousResearch/hermes-agent fork with local modifications)" |
| 7 | 2026-05-15 | `mstar-pro` | "MSTAR Pro v3.0 - Self-Evolution Engine for AI Agents | AI Agent 自进化引擎" / "**MSTAR Pro** 是一个无需外部依赖的自进化引擎…" |
| 8 | 2026-05-15 | `Hermes-MSTAR-V2.0` | "Hermes MSTAR Evolution System V2.0 based on M* Paper" / "**Hermes M* Paper Implementation — Production Grade**" |
| 9 | 2026-05-17 | `MSTAR-Pro-V4.0` | "MSTAR Pro V4.0 for Hermes Agent - Self-Evolution System" |
| 10 | 2026-05-18 | `MSTAR-Pro-V4.0-Clean` | "MSTAR Pro v4.0 — Self-Evolving AI Agent. DDTree 加速、FitnessTracker 多维适应度追踪、实时 Dashboard、遗忘机制。一键安装: bash <(curl …install.sh)" |
| 11 | 2026-05-26 | `hermes-collective-intelligence` | "HERMES Collective Intelligence 全谱进化系统" |
| 12 | 2026-05-28 | `CIP-Zhazhazhu` | "HERMES Collective Intelligence Protocol - 炸炸宝实现版 (Darwin模式)" |
| 13 | 2026-05-28 | `hermes-kanban-cip` | "Hermes Kanban CIP - 烤烤酱 CIP implementation" |
| 14 | 2026-08-28 | `PPT.SKILL` | "Hermes Agent PPT 生成技能流水线：document-toolkit + pptx-render-verify + render_pptx.py" |
| 15 | 2026-09-15 | `PPTPRO.SKILL` | "PPT generation agent-skill bundle: Anthropic pptx toolchain + optimized python-pptx/Windows…" |
| 16 | — (API 404) | `hermes-personal-backup` | 内容与 `hermes-agent-backup` 同构（README 逐字相同） |
| 17 | — (API 404) | `-hermes` | "烤烤酱的 Hermes" / "这是烤烤酱（Kaokaooo）的 Hermes Agent 个人实例备份。" |

### 1.1 这条线怎么演进（按原文可证的先后关系）

1. **2026-04-15 → 05-12**：先有 `hermes-skills`（技能库），再从 MSTAR 论文长出记忆进化引擎
   （`mstar`、`hermes-mstar` 同日创建）。
   - `mstar/README.md`："> **MSTAR**: 基于 MSTAR 论文的自我进化 AI 记忆系统"、徽章 `version-1.0.0`
   - `hermes-mstar/README.md`："> Based on [M*: Every Task Deserves Its Own Memory Harness](https://arxiv.org/abs/2604.11811)"

2. **2026-05-13**：`hermes-agent` fork 落地，把 hermes-mstar 集成进真实 agent。
   仓库描述原文：`"includes custom skills, hermes-mstar integration, SkillClaw, and local modifications"`

3. **2026-05-14**：`hermes-scripts` 把进化从「库」变成「定时跑的循环」。

4. **2026-05-15**：MSTAR 线一天三个版本（`mstar-pro` v3.0、`Hermes-MSTAR-V2.0` v2.0、
   `hermes-agent-backup`）。这是一次**并行分叉**，不是线性升级。

5. **2026-05-17 → 05-18**：`MSTAR-Pro-V4.0` → `MSTAR-Pro-V4.0-Clean`。

6. **2026-05-26 → 05-28**：从「记忆进化」跃迁到「全谱进化」+「多智能体协同」。
   - `hermes-collective-intelligence`（05-26）：五实例全谱进化
   - `CIP-Zhazhazhu`（05-28）：CIP v9.0 五实例 + Redis EventBus，标题带 **`(Darwin模式)`**
   - `hermes-kanban-cip`（05-28）：CIP 落到「看板编排」

7. **2026-08-28 → 09-15**：转向 PPT 技能流水线，**不再谈进化**（见 §6）。

---

## 2. ★ MSTAR 线六仓逐个定位 + 「进化改进什么」原文

### 2.1 `mstar`（2026-05-12，v1.0.0）

**自述定位**：
- `mstar/README.md` 标题："> # MSTAR - Memory System with Task-based Memory Architecture"
- 徽章 `version-1.0.0`；落款 `*基于 Karpathy's MSTAR 架构的自我进化记忆框架*`

**进化什么** —— 特征表原文：
> - **🎯 任务专用化**: 自动识别任务类型，智能路由到最佳记忆程序
> - **🧬 自我进化**: 基于适应度的程序变异与淘汰机制
> - **📊 健康监控**: 实时系统健康检查与趋势分析
> - **🔄 自动快照**: 支持版本回滚与历史追溯

架构图里进化被单列为第四层（`Evolution Layer`）：
> `Evaluate → Quality Gates → Reflect → Mutate & Evolve`

进化落点模块（原文表格）：
> | `mutator/` | 11 种程序变异类型 |
> | `population_manager/` | 程序池管理 + 选择策略 |
> | `forgetting/` | 低价值程序自动淘汰 |
> | `evaluator/` | 任务表现评估 + 质量门禁 |

**进化对象 = 记忆程序**，明确不碰代码架构：
> 核心思想：
> - 专门化记忆架构 > 通用化
> - 基于适应度的进化程序选择
> - 任务感知的记忆路由

落款一句：`*"专门化记忆 > 通用化"*`

**设计 vs 实现**：README 给了完整 CLI（`mstar_cli.py evolve`）、cron 配置
（`0 9 * * * python3 /path/to/mstar_evolution_cron.py`），但仓库目录全是空壳占位
（README 「目录结构」列了 20+ 个模块，`CONTRIBUTING.md` 仅 908 字节）。**设计文档级**。

---

### 2.2 `hermes-mstar`（2026-05-12，v2.0.0）

**自述定位**：
> "**Hermes MSTAR** is a self-evolving memory system that combines genetic programming
> evolution with production-grade reliability tracking. It integrates into Hermes Agent
> as a built-in provider"

**进化什么** —— 六条能力原文（README Overview 列表）：
> - **Multi-factor fitness tracking** across 55 dimensions (EMA smoothing, time decay, token efficiency)
> - **15 mutation operators** (keyword/field/logic modification, crossover, ensemble, random)
> - **4-layer quality gates** (Python syntax, Shell script, PowerShell, YAML validation)
> - **RTK token optimization** (3-tier caching: hot/warm/cold)
> - **Automatic forgetting mechanism** (archive/merge/delete cold skills)
> - **Bidirectional SelfImproving bridge** (corrections → mutations, reinforcements → evolutions)

**进化对象 = skill / memory program**：
> `evolution/quality_gates.py` — 4-layer quality validation
> `evolution/forgetting.py` — Archive/Merge/Delete cold skill strategies

进化触发是**自适应节奏**，不是定时：
> `evolution/evolution_engine.py` — Adaptive evolution (3-50 session intervals)

**关键：桥接点写得很清楚，进化信号来自 agent 的人工纠正**：
> 2. **SelfImprovingBridge** connects `~/.hermes/self-improving/corrections.md` to MSTAR mutation engine
> 3. **ForgettingMechanism** integrated into Hermes curator for cold skill handling

**设计 vs 实现**：有 fitness 公式、目录树、import 示例；README 无验证数字（对比 V2.0 有 `46 PASS / 0 BUG`）。**设计 + 部分实现**。

---

### 2.3 `Hermes-MSTAR-V2.0`（2026-05-15）

**自述定位**：
> "**Hermes M* Paper Implementation — Production Grade**"
> "基于论文 [M* (arXiv:2604.11811)](https://arxiv.org/abs/2604.11811) 实现的自主进化 Skill 系统，
> 已集成到 Hermes Agent v0.40.0。"

**进化什么** —— 论文对齐表原文：
> | Phase | 组件 | 文件 | M* Paper 对应 |
> | P1 | PopulationPool (τ=0.15, max=20) | `population_pool.py` | Softmax Selection + 种群池 |
> | P2 | ValidationSet (k=25, 7维特征) | `validation_set.py` | k-means Validation Set |
> | P3 | LLMReflector (GPT-4驱动) | `reflector_agent.py` | LLM-driven Reflection |
> | P4 | QualityGates 3× Repair Loop | `quality_gates.py` | Automated 3× Fix |
> | P5 | Task-Specific Fitness (4域) | `task_domain.py` | Domain-Aware Fitness |

**进化对象写死为 Skill**：
> "已集成到 Hermes Agent v0.40.0"

进化 = **失败驱动**：
> `reflector_agent.py` — LLMReflector: GPT-4 driven failure analysis
> `validation_set.py` — Rotating validation set to prevent overfitting

**★ 这个仓库把「前版有什么问题」写在文件结构表的方括号里** —— 是 MSTAR 线唯一一处自述前版缺陷：
> ├── population_pool.py    # [NEW] Softmax Selection Pool
> ├── validation_set.py     # [NEW] k-means Validation Set
> ├── reflector_agent.py    # [NEW] LLM Reflector
> ├── task_domain.py         # [NEW] Task-Specific Fitness
> ├── quality_gates.py       # [重写] 3× Repair Loop
> ├── mutator.py             # [Bug Fix] MutationResult.success=True
> ├── evolution_engine.py    # [改造] 集成 PopulationPool
> ├── fitness_tracker.py     # [扩展] _load_recent_events()

并单列 **Bug Fixes** 段：
> - `MutationResult.success`: 从无默认值 → `True` (class variable)
> - `FitnessTracker.get_all_skills()`: 从空列表 → 返回9个活跃skill

> 注：这里的「Bug Fix」是修 `hermes-mstar`（2.2 节），不是修 MSTAR 论文。

**设计 vs 实现**：README 给了验证命令与结果 `python verify_full.py   # 46 PASS / 0 BUG`。**实现 + 验证**。

---

### 2.4 `mstar-pro`（2026-05-15，v3.0）

**自述定位**：
> "**MSTAR Pro** 是一个无需外部依赖的自进化引擎，通过持续追踪 AI Agent 程序的适应度（Fitness），
> 自动识别低性能程序并触发变异（Mutation）、归档（Archive）或删除（Delete）操作，
> 实现 AI Agent 系统的自主进化。"

**进化什么** —— 核心特性表原文：
> | 特性 | 说明 |
> | **适应度追踪** | 多维度 EMA 评分：成功率、质量得分、延迟、Token 效率、置信度等 |
> | **自动进化** | 低于阈值的程序自动触发变异，支持 4 种变异策略 |
> | **遗忘管理** | 长期低性能程序自动归档或删除，防止资源浪费 |
> | **血缘追踪** | 记录每个程序的进化链（Lineage），支持回溯分析 |
> | **Dashboard** | Web UI 实时监控：`http://localhost:18792/dashboard.html` |
> | **零外部依赖** | 纯 Python 标准库实现（除 Dashboard 可选 Flask） |

进化是**阈值驱动的四路决策**（原文表）：
> | 策略 | 条件 | 操作 |
> | `random_change` | 极低适应度 | 随机修改代码/配置 |
> | `focused_improvement` | 低适应度+高质量token | 针对薄弱维度改进 |
> | `archival` | 长期低性能 | 移至归档区 |
> | `deletion` | 极低+无改进空间 | 彻底删除 |

阈值原文：
> ```python
> threshold_low = 0.35      # 低适应度阈值
> threshold_archive = 0.25   # 归档阈值  
> threshold_delete = 0.15    # 删除阈值
> mutation_rate = 0.1        # 变异概率
> max_lineage_depth = 10    # 最大血缘深度
> ```

**★ 唯一一处「进化 = 减少自身」**：长期低性能 → 删除。遗忘不是附属功能，是进化的组成部分。

**设计 vs 实现**：README 带完整 Python 用法与目录树，但 License 段写
> `MIT License - 仅供个人研究使用。`

**设计级**（无验证数字）。

---

### 2.5 `MSTAR-Pro-V4.0`（2026-05-17） —— ★ 这个仓库名是误导

**事实一：README 与 `hermes-agent-backup/README.md` 逐字节相同。**
我做了字符串相等判定：`MSTAR-Pro-V4.0` README == `hermes-agent-backup` README == `True`。
也就是说，**V4.0 仓库的 README 就是 Hermes 主线的 README**，没有一句 MSTAR 内容。

**事实二：但仓库内容确实是 MSTAR。** GitHub tree（`main`，4121 个文件）顶层含：
> `'mstar_core'`、`'mstar_dashboard.html'`、`'mstar_dashboard.pid'`、`'mstar_fitness.db'`、
> `'mstar_observability'`、`'failed_trajectories.jsonl'`

GitHub description：
> "MSTAR Pro V4.0 for Hermes Agent - Self-Evolution System"

**事实三：作者自述前版问题 = commit message，不是 README。** 这是本任务里唯一直接回答
「前版有什么问题」的作者原话：
> `2026-05-17T18:50:32 | MSTAR Pro V4.0 - Fix 6 bugs: forgetting score, dual-write, JSON ser, rollback, predictor learning, evolution p...`
> `2026-05-17T19:06:06 | MSTAR Pro V4.0 - Fix 4 remaining limitations: ML trainer, LLM Judge config, episodes/failure tracking, DB pers...`

配合 `2026-05-17T18:37:03 | MSTAR Pro V4.0 - Phase 0-7 complete`。

**设计 vs 实现**：这是**实现**（Phase 0-7 + 10 个 bug 修复），README 却错配成 Hermes 的。

---

### 2.6 ★★ `MSTAR-Pro-V4.0-Clean`（2026-05-18）—— 「Clean」到底指什么

**先说事实：这个仓库的 README 里没有一句解释「Clean」的含义。**
我逐行读过抓取版（5034 字符）和线上最新版（6564 字符），都没有「Clean」的理由陈述。
**作者没有用文字说明 Clean 版清理了什么。**

**可从原文/结构反推的三条（每条标注证据等级）：**

**证据 A（结构事实，强）**：`MSTAR-Pro-V4.0` 仓库里有 `backups/v3_backup_20260516_032931/`，
里面是 **5 个被改动过的 Hermes 核心文件**：
> `backups/v3_backup_20260516_032931/run_agent.py` (818447)
> `backups/v3_backup_20260516_032931/context_engine.py` (8090)
> `backups/v3_backup_20260516_032931/memory_manager.py` (20823)
> `backups/v3_backup_20260516_032931/model_tools.py` (37729)
> `backups/v3_backup_20260516_032931/plugins.py` (61364)

而 `MSTAR-Pro-V4.0-Clean` **没有这个目录**，改为标准三件套：
> `mstar_core/`、`plugins/context_engine/mstar/`、`tools/mstar_tools.py`、`run_agent.py`

且 `MSTAR-Pro-V4.0-Clean/.gitignore` 里明确排除了运行期产物：
> ```
> *.db
> *.sqlite
> *.sqlite3
> mstar_dashboard.pid
> mstar_observability/
> ```

→ **推断（中高置信）**：「Clean」= 去掉 v3 的 Hermes 核心文件改写残留（改写前的备份）、
去掉入库的 db/pid 等运行期垃圾，让 MSTAR 可以作为干净的可复制单元部署。

**证据 B（部署模型，强）**：Clean 版 README 的核心是**3 步复现到新实例**，而不是改现有实例：
> "MSTAR Pro V4.0 设计为**零外部依赖**（仅需 numpy + yaml），
> 可通过 3 步快速部署到任意 Hermes Agent 实例。"
> "### Step 1：复制 MSTAR 核心模块
> 把以下目录/文件复制到目标 Hermes Agent 的安装目录（与 `run_agent.py` 同级）："
> "**总计：mstar_core/ 仅 36 个 .py 文件，无需单独安装。**"

并且承认目标实例可能缺钩子：
> "> **如果目标 Hermes Agent 的 `run_agent.py` 中没有这段代码**，
> 需要在 `AIAgent.__init__` 的适当位置（内存 provider 初始化后）插入上述代码块。"

→ 上一版是「我已经改过你的 run_agent.py」，Clean 版是「你自己插 23 行」。

**证据 C（commit，强）**：
> `2026-05-18T11:50:13 | MSTAR Pro V4.0 - Initial commit`
> `2026-05-18T13:08:35 | docs: add replication guide to README`
> `2026-05-18T13:18:36 | feat: add one-command install script`

作者后两个 commit 全是**部署能力**，没有「删除/重构/清理」类 commit。
→ **推断（高置信）**：「Clean」的重点是**可复制部署**，不是代码清理。

**Clean 版的进化定位原文**（标题行）：
> "**M**ulti-**S**trategy **T**ask-**A**ware **R**eflection — Phase 0-7 全链路自进化系统"

**「进化什么」—— 6 个能力表原文：**
> | 能力 | 文件 | 说明 |
> | DDTree 加速 | `mstar_core/acceleration/dd_tree.py` | 400-700% 性能提升 |
> | 遗忘机制 | `mstar_core/memory/forgetting.py` | 低价值轨迹自动归档 |
> | FitnessTracker | `mstar_core/evolution/fitness_tracker.py` | 适应度追踪 (5 维度) |
> | EvolutionEngine | `mstar_core/evolution/engine.py` | 智能触发自进化 |
> | Dashboard | `mstar_core/observability/dashboard_server.py` | 实时观测 (port 18792) |
> | 安全沙箱 | `mstar_core/security/sanitizer.py` | 输入验证 + 内存清洗 |

**★ Clean 版出现「协议层」—— 这是 MSTAR 线第一次有「结构」概念**（README 项目结构表）：
> │   ├── evolvemem.py              #   EvolveMem 检索自进化
> │   ├── experience_recall.py      #   经验回溯
> │   ├── predictor.py              #   LLMJudgePredictor / RuleBasedPredictor
> │   ├── protocol.py               #   RSPL / SEPL 协议
> │   ├── robustness.py             #   Bootstrap CI / 扰动测试
> │   └── version_control.py        #   FGGM 版本控制

我抓了这两个文件的源码头（线上 raw），原文如下 —— **这是全部 17 个仓库里最接近
「结构本身有协议」的一句**：

`mstar_core/evolution/protocol.py`（模块 docstring 原文）：
> ```
> MSTAR Pro v4.0 - Phase 7: RSPL/SEPL Protocol Layer
> 参考: Autogenesis
>
> RSPL (Registry Skill Protocol Language):
> - Skill注册、注销、查询协议
> - 定义skill的元数据格式
> - 版本控制和依赖管理
>
> SEPL (Skill Evolution Protocol Language):
> - Skill进化协议
> - 定义mutation的提交流程
> - 版本控制和回滚协议
> ```

`mstar_core/evolution/version_control.py`（模块 docstring 原文）：
> ```
> MSTAR Pro v4.0 - Phase 3: Version Control + FGGM Contracts
> 参考: SEVerA (2603.25111) + Autogenesis
>
> FGGM (Formally Verified Genetic Mutations):
> - 每个mutation必须通过形式化验证才能执行
> - 验证项: 内存安全、类型安全、语义保持
> - 失败时自动rollback
> ```

**注意：RSPL/SEPL 的作用域是 skill（"Skill注册""Skill进化协议"），不是架构。**

**Clean 版的技术规格原文（进化节律）：**
> - **触发条件**: 每 10 个 session 触发一次进化评估（可通过 `fitness_dimensions` 调整）
> - **遗忘阈值**: 适应度 < 0.3 且 30 天无改进，自动归档

**设计 vs 实现**：**实现**（仓库含全部 36 个 mstar_core 源文件、install.sh、run_agent.py）。

---

## 3. `hermes-collective-intelligence` 指向什么

### 3.1 事实：该仓库**没有 README、没有 md 文件**

`_all.json` 里：
> `{"repo": "hermes-collective-intelligence", "md": [], "readme": null}`

我进一步核对了 GitHub：`git/trees/master?recursive=1` 返回的文件树里
**只有 `.py` 和 `dashboard/index.html`，没有任何 `.md`**。
`raw.githubusercontent.com/.../main/README.md` 与 `/master/README.md` 均 **404**。

→ 所以「仓库名指向什么」只能靠 **GitHub description + 源码 docstring**，不能靠 README。
这一点必须在任何引用中标注，否则就是编造。

### 3.2 仓库名/description 原文

> description: `"HERMES Collective Intelligence 全谱进化系统"`

**「全谱」（Full Spectrum）= 从配置一直进化到代码。**
词源在源码里写死了（`evolution_layers.py` docstring 原文）：

> ```
> HERMES Full Spectrum Evolution System - Evolution Layers
> L1-L4全谱进化引擎
>
> 设计来源: E:/HERMES_Collective_Intelligence.txt 第六节
>
> 全谱进化目标:
> ┌─────────────────────────────────────────────────────┐
> │  L1 配置层  │  L2 技能层  │  L3 行为层  │  L4 底层代码 │
> │  阈值/参数  │  技能改进   │  工作流重构  │  算法/数据结构│
> └─────────────────────────────────────────────────────┘
>
> 北极星指标:
>   - 成本更低: 更少工具调用、更短流程、更低资源消耗
>   - 标准更高: 更高质量产出、更稳定的执行
>   - 速度更快: 响应延迟降低、执行时间缩短
> ```

**★「北极星指标」是这条线对「进化得好不好」的唯一明确定义** —— 不是适应度最大化，
而是三句话：成本更低、标准更高、速度更快。
`NorthStarMetrics.calculate_overall()` 把它落成权重（源码原文）：
> ```python
> return (quality_score * 0.3 + stability_score * 0.3 +
>         cost_score * 0.2 + speed_score * 0.2)
> ```

### 3.3 「collective」指向：五个独立实例用事件总线协作，不是单体自改

`orchestrator.py` docstring 原文：
> ```
> HERMES Full Spectrum Evolution System - Orchestrator
> 全谱进化系统编排器
>
> 设计来源: E:/HERMES_Collective_Intelligence.txt
>
> 五实例协作流程:
> ┌──────────────────────────────────────────────────────────────────────────┐
> │   饕餮(Taotie)     女娲(Nuwa)       达尔文(Darwin)   进化池(EP)  Production │
> │   分析因果 ──► 接收边界 ──► 接收设计 ──► 接收计划 ──► 执行实验 ──► 快照     │
> │         发布Design ──► 订阅Design    验证结果发布◄──│  Validation│
> │                  ◄──── 失败学习 (ExperimentResult)  │
> │   ◄─────────── ProductionState (系统状态) ─────────────────────────►│
> └──────────────────────────────────────────────────────────────────────────┘
>
> 睡眠机制:
>   - 达尔文可以睡觉: Darwin.sleep() → 停止生成新策略
>   - 进化池继续执行: 达尔文睡觉时，进化池仍执行pending计划
>   - 达尔文醒来: Darwin.wake_up() → 恢复生成策略
>
> 自愈机制:
>   - 进化池崩溃 → Production快照 → 重建进化池
>   - 五实例独立: 任一实例崩溃不影响其他实例
> ```

`instance_base.py` docstring 原文（五实例分工）：
> ```
> 五实例:
>   1. 饕餮 (Taotie) - 因果发现专职
>   2. 女娲 (Nuwa) - 大胆假设专职
>   3. 达尔文 (Darwin) - 进化策略设计专职(不执行)
>   4. 进化池+验证 (EvolutionPool) - 激进实验+安全门控
>   5. Production - 绝对保护+快照自愈
> ```

**★ DarwinInstance docstring 里有一段罕见的自述设计变更**（原文）：
> ```
>     职责边界:
>       - 达尔文只设计进化策略，不执行任何实验
>       - 进化池是执行者，达尔文是军师
>       - 达尔文从进化池的失败中学习，改进下一轮策略设计
>       - 达尔文可以"睡觉"(暂停生成新策略)，但进化池继续执行已有方案
>
>     关键区别于v7.0:
>       - v7.0里达尔文=进化池本身(既设计又执行)
>       - 你的设计中达尔文只设计，进化池执行
>       - 这样达尔文可以从大量实验结果中学习"如何设计更好的实验策略"
>
>     学习机制:
>       实验失败 → 失败原因分析 → 改进策略设计 → 新方案 → 实验
> ```

「关键区别于 v7.0」+「你的设计中」是作者（对 AI 说「你的设计中」）留下的**版本对照**。
这说明 v7.0 存在，且「进化」对象的层级被上移了：**从「执行变异」变成「学习如何设计变异实验」**。

**★ 保护级别 = 允许进化的深度**（`InstanceProtection` 枚举原文）：
> ```python
> class InstanceProtection(Enum):
>     ABSOLUTE = "absolute"    # Production - 最高保护
>     HIGH = "high"            # 达尔文
>     MEDIUM = "medium"        # 进化池、女娲
>     LOW = "low"              # 饕餮
> ```

### 3.4 ★★ 「L4 底层代码」在真实 Hermes 里落地了 —— 这是最硬的「结构可进化」证据

`mutation_handler.py` docstring 原文：
> ```
> HERMES Full Spectrum Evolution System - Hermes Mutation Handler
> Hermes配置/技能/行为/代码变异真正落地
>
> 设计来源: E:/HERMES_Collective_Intelligence.txt 第2.4节 + 第六节
>
> L1-L4层变异在真实Hermes环境中执行:
>   L1_CONFIG: 修改Hermes config.yaml中的阈值/参数
>   L2_SKILL:  修改skills启用状态/优先级
>   L3_BEHAVIOR: 修改agent行为策略
>   L4_CODE: 修改底层代码（需最高安全阈值）
>
> 达尔文-进化池分离原则:
>   - 达尔文只设计策略（输出EvolutionPlanEvent）
>   - 进化池执行突变（接收EvolutionPlanEvent，执行L1-L4变异）
>   - 进化池双重职责：激进实验 + 安全门控
> ```

`HermesMutationHandler` 类 docstring 原文：
> ```
>     职责:
>       1. L1_CONFIG变异: 修改Hermes config.yaml参数
>       2. L2_SKILL变异: 修改skills配置
>       3. L3_BEHAVIOR变异: 修改agent行为参数
>       4. L4_CODE变异: 修改底层Python代码（最高安全阈值）
>
>     安全门控:
>       - 所有变异经过安全检查
>       - L4变异需要0.95+适应度阈值
>       - 变异前备份，失败可回滚
> ```

L4 的实现是真的**改文件**（源码原文，非 docstring）：
> ```python
> def mutate_L4_code(
>     self,
>     file_path: str,
>     patch_func: Callable[[str], str],
>     original_snippet: str,
>     fitness: float = 0.5
> ) -> Dict[str, Any]:
>     """
>     L4代码层变异 - 修改底层Python代码
>     ⚠️ 最高安全阈值：需要fitness >= 0.95
>     """
> ...
>             # L4强制安全检查
>             if fitness < self.l4_fitness_threshold:
>                 result['error'] = f"L4 blocked: fitness {fitness} < threshold {self.l4_fitness_threshold}"
> ...
>                 with open(file_path, 'w', encoding='utf-8') as f:
>                     f.write(patched_code)
> ```
> ```python
> self.l4_fitness_threshold = 0.95  # L4变异需要0.95+适应度
> self.l3_fitness_threshold = 0.85
> self.l2_fitness_threshold = 0.70
> self.l1_fitness_threshold = 0.50
> ```

**L4 变异的内容 = 算法与数据结构**（`evolution_layers.py` 原文）：
> ```
> class L4CodeMutator:
>     """
>     L4底层代码变异器 - 算法策略/数据结构变更
>
>     职责:
>       - 算法替换 (sorting, searching, etc.)
>       - 数据结构变更 (list -> tree, etc.)
>       - 接口契约调整
>       - 代码逻辑重构
>
>     风险等级: 最高
>     需要最严格的安全门控
>     """
> ```
> ```python
> self.algorithm_choices = {
>     'sort': ['quicksort', 'mergesort', 'heapsort', 'bubblesort'],
>     'search': ['binary_search', 'linear_search', 'hash_lookup'],
> ```

**L3 = 工作流重构**（同文件原文）：
> ```
> class L3BehaviorMutator:
>     """
>     L3行为层变异器 - 工作流重构
>
>     职责:
>       - 工作流步骤重排
>       - 工具调用链优化
>       - 并行化改造
>       - 串行改并行
>       - 决策树调整
>
>     变异策略:
>       - 激进: 重新设计工作流
>       - 保守: 微调步骤顺序
>     """
> ```

**★ 层级准入随风险升高**（同文件原文）—— 这是作者对「能进化多深」的唯一安全判据：
> ```python
> self.layer_fitness_thresholds = {
>     'L1': 0.2,   # L1可以容忍更低适应度
>     'L2': 0.3,
>     'L3': 0.4,
>     'L4': 0.5,   # L4需要更高适应度才执行
> }
> ```
> ```
> if layer.upper() == 'L4' and fitness < threshold:
>     return EvolutionResult(
>         success=False,
>         layer=layer,
>         original_value=target,
>         mutated_value=target,
>         error=f"L4 requires fitness >= {threshold}"
>     )
> ```
> ```python
> warnings.append("L4 mutation modifies core code - highest risk")
> ```

**★ 两处阈值不一致（如实记录，不调和）**：
`evolution_layers.py` 说 L4 阈值 **0.5**，而 `mutation_handler.py` 说 **0.95**。
两个文件都在同一仓库；后者是真正落地到 Hermes 文件的那个。
这是文档与实现漂移的直接证据。

**设计 vs 实现**：
`orchestrator.py`、`mutation_handler.py`、`evolution_layers.py`、`instance_base.py`、
`metrics_collector.py` 是**实现**；
但 `verify_design_compliance.py` 依赖一个仓库外文件（原文）：
> ```python
> design_file = Path('E:/HERMES_Collective_Intelligence.txt')
> if not design_file.exists():
>     print("✗ 设计方案文件不存在: E:/HERMES_Collective_Intelligence.txt")
> ```
→ **真正的设计文档（`E:/HERMES_Collective_Intelligence.txt`）不在 GitHub 仓库里**，
未被抓取。这是本次深读的数据缺口，必须说明。

---

## 4. `CIP-Zhazhazhu`：L1-L4 的第二个实现，标题写「Darwin模式」

### 4.1 事实：同样**没有 README**

`_all.json`：`{"repo": "CIP-Zhazhazhu", "md": [], "readme": null}`
GitHub tree 里 `hermes_cip/` 下全是 `.py`（含误提交的 `__pycache__/*.pyc`），无 `.md`。

GitHub description（唯一自述定位）：
> `"HERMES Collective Intelligence Protocol - 炸炸宝实现版 (Darwin模式)"`

包 docstring 原文（`hermes_cip/__init__.py`）：
> ```
> HERMES CIP — Collective Intelligence & Persistence
> HERMES Collective Intelligence 全谱进化系统 v9.0
> ```

版本号原文（`hermes_cip/version.py`）：
> ```python
> __version__ = "9.0.0"
> ```

→ **同一个「全谱进化系统」在 05-26（`hermes-collective-intelligence`）和 05-28（`CIP-Zhazhazhu`）
被实现两次，版本号从无标注变成 v9.0。** 前者是无版本号的五实例实现，后者是 v9.0 的工程化重做。

### 4.2 L1-L4 在 CIP 里的定义（源码 docstring 原文）

`hermes_cip/evolution/full_spectrum.py`：
> ```
> hermes_cip/evolution/full_spectrum.py
> FullSpectrumScheduler — L1-L4 四层联动变异调度器
> 设计文档规格：v9.0 CIP FullSpectrumScheduler
>   · L1: Config 数值变异（高斯噪声）
>   · L2: Skill workflow 变异（14种）
>   · L3: Behavior 工作流变异
>   · L4: Code CGP 遗传编程变异
>   · 层级联动 + 优先级调度 + 变异链追踪
> ```

`MutationLevel` 枚举原文：
> ```python
> class MutationLevel(Enum):
>     """变异层级枚举"""
>     L1_CONFIG   = "L1_CONFIG"    # 配置参数级（高斯噪声）
>     L2_SKILL    = "L2_SKILL"     # Skill workflow 级（14种变异）
>     L3_BEHAVIOR = "L3_BEHAVIOR"  # Behavior 工作流结构级
>     L4_CODE     = "L4_CODE"      # Code CGP 遗传编程级
>
>
> # 层级优先级（数字越小优先级越高）
> LEVEL_PRIORITY = {
>     MutationLevel.L1_CONFIG:   1,
>     MutationLevel.L2_SKILL:    2,
>     MutationLevel.L3_BEHAVIOR: 3,
>     MutationLevel.L4_CODE:     4,
> }
> ```

**★ L1-L4 是「联动」的，且有继承规则**（`ChainContext` + `_enhance_target_from_prev` 原文）：
> ```python
> class ChainContext:
>     """
>     变异链上下文
>     · 在 L1→L2→L3→L4 联动变异时传递信息
>     """
> ```
> ```
> """L1→L2→L3→L4 联动变异（按优先级顺序执行）"""
> ```
> ```
> """
> 根据前一层变异结果增强当前层目标
> · L2 继承 L1 的配置变化
> · L3 继承 L2 的 workflow 变化
> · L4 基于前三层的综合信号
> """
> ```

### 4.3 ★ CIP 的 L4 与 HCI 的 L4 不是一回事（重要区分）

`hermes_cip/evolution/code_mutator.py` docstring 原文：
> ```
> hermes_cip/evolution/code_mutator.py
> CodeMutator — L4 Code 变异器
>   · CodeCGP — 笛卡尔基因编程（Cartesian Genetic Programming）
>   · FullSpectrumMutator — 全谱变异器（集成 L1-L4）
> 设计文档规格：v9.0 CIP L4 Code 变异
> ```

`CodeCGP` 类 docstring 原文：
> ```
> class CodeCGP:
>     """
>     笛卡尔基因编程（CGP）
>     · 节点：function nodes（数学运算、比较、条件等）
>     · 连接：每个节点有多个输入
>     · 变异：随机修改节点或连接
>     · 适应度：由 NorthStarMetrics 评估
>     """
> ```

**★ 关键区别**：CIP 的 L4 是**在一个抽象 CGP 基因组上变异**（函数集合
`add/sub/mul/div/sqrt/abs/neg/gt/lt/eq/and/or/not/const`），
**不是改 Hermes 的源文件**；HCI 的 L4 是 `open(file_path,'w')` 真改 Python 文件。
同名 L4，两种实现强度。前者是设计，后者是落地。

### 4.4 CIP 的适应度定义（两处不一致，如实记录）

`hermes_cip/evolution/fitness.py` docstring 原文：
> ```
> hermes_cip/evolution/fitness.py
> NorthStarMetrics — 进化指标
> 设计文档规格：v9.0 CIP NorthStar 指标
>   · 适应度函数：fitness = w1·Q + w2·S - w3·L - w4·E
>   · Q = 质量（任务完成度）
>   · S = 速度（响应时间）
>   · L = 资源消耗（内存/CPU）
>   · E = 错误率
> """
> ```
> ```python
> DEFAULT_WEIGHTS = {
>     "quality":   0.4,   # w1
>     "speed":      0.3,   # w2
>     "latency":    -0.2,  # w3（资源惩罚）
>     "error_rate": -0.1,  # w4（错误惩罚）
> }
> ```

`hermes_cip/evolution/north_star.py` docstring 原文 —— **同名类，两套权重**：
> ```
> hermes_cip/evolution/north_star.py
> NorthStarMetrics — 北极星指标体系（成本/质量/速度三维度）
> 设计文档规格：v9.0 CIP NorthStar 指标
>   · Cost维度：资源消耗（CPU时间、内存峰值、API调用成本）
>   · Quality维度：输出质量（任务完成度、准确性、稳定性）
>   · Speed维度：响应速度（延迟、吞吐量、首次响应时间）
>   · 综合适应度 = w_cost·Cost + w_quality·Quality + w_speed·Speed
> """
> ```
> ```python
> DEFAULT_WEIGHTS = {
>     NorthStarDimension.COST:    -0.25,  # 成本（负权重，越小越好）
>     NorthStarDimension.QUALITY:  0.45,  # 质量（正权重）
>     NorthStarDimension.SPEED:    0.30,  # 速度（正权重）
> }
> ```
> 但 `north_star.py` 顶部写着：
> ```python
> from hermes_cip.evolution.fitness import NorthStarMetrics
> ```
> —— **导入即自我遮蔽**：`north_star.py` 里的 `NorthStarMetrics` 类从未被它自己的
> `main.py` 路径用到，`main.py` 也不 import 它。v9.0 里存在两个同名类，权重不同，
> 只有 `fitness.py` 那个真正生效。

### 4.5 「CIP」缩写展开的原文

唯一展开在 `hermes_cip/__init__.py` 第一行：
> `HERMES CIP — Collective Intelligence & Persistence`

**注意：不是 `Protocol`。** 仓库 description 写 `Collective Intelligence Protocol`，
包 docstring 写 `Collective Intelligence & Persistence`。两处不一致。

而 `CIP` 全名最权威的一次出现在私人备份仓库（`-hermes/README.md` 原文）：
> - `hermes_kanban_cip_code.md` - CIP 核心代码文档

### 4.6 CIP 的工程化部分（与「进化」无关，但定义了运行边界）

`hermes_cip/main.py` docstring 原文：
> ```
> hermes_cip/main.py
> CIP v9.0 主入口 — 一键启动五实例 + EventBus + HealthServer + Dashboard
> 设计文档规格：v9.0 CIP Main Entry
> 用法：
>     python -m hermes_cip.main
> ```
> ```
> # 1. EventBus
> eb = EventBus(instance_name="production", redis_url=redis_url)
> # 2. CausalEventBus
> ceb = CausalEventBus(instance_name="production", redis_url=redis_url)
> # 3. Collective 模块
> kg = CausalKnowledgeGraph(redis_url=redis_url)
> ca = CollectiveAttention(event_bus=eb, redis_url=redis_url)
> ```

`hermes_cip/collective/` 包名即 `collective` 的落点 —— 因果事件总线 + 因果知识图谱 + 集体注意力。
**「collective intelligence」在这里是可执行的组件名（知识图谱/注意力/共识），不是修辞。**

默认端口（源码原文）：health 8766、dashboard 8767、redis `redis://localhost:6379/0`。

---

## 5. ★ 有没有「架构/结构本身可进化」的表述

### 5.1 结论：**没有任何一处把「架构/结构本身可进化」写成表述。**

我用了 15 个精确短语对全部 14 个有内容的仓库（README + 所有已抓 md，共约 220 万字符）
做全文搜索，**全部 0 命中**：

> `架构可进化` 0 ｜ `架构本身` 0 ｜ `自身架构` 0 ｜ `结构的进化` 0 ｜ `结构进化` 0
> `重写自己` 0 ｜ `改写自己` 0 ｜ `自我重构` 0 ｜ `架构演化` 0 ｜ `拓扑演化` 0
> `架构变` 0 ｜ `改变架构` 0 ｜ `修改架构` 0 ｜ `架构的进化` 0 ｜ `架构层` 0 ｜ `架构重构` 0

**必须明确说找不到。** 唯一出现「架构」二字的地方是 `verify_design_compliance.py` 里一句验证输出：
> ```python
> print("\n[核心验证 1] 五实例架构 (饕餮/女娲/达尔文/进化池/Production)")
> ```
> —— 指的是「本系统自己被设计成这个架构」，不是「架构可被进化」。

### 5.2 最接近的三处，及其**为何不构成**该表述（逐条排除）

**(a) CIP/HCI 的 L4 —— 进化的对象包含算法与数据结构，但没说「结构」是可进化的对象**

原文（`evolution_layers.py::L4CodeMutator` docstring）：
> `- 数据结构变更 (list -> tree, etc.)`
> `- 接口契约调整`
> `- 代码逻辑重构`

**为何不构成**：L4 的 docstring 自述「风险等级: 最高 / 需要最严格的安全门控」，
并用 `fitness >= 0.95` 硬门控。作者把 L4 归为**需要极高适应度才放行的危险动作**，
而不是一个常规的、与 L1/L2/L3 平级的进化维度。而且实际变异内容是从
**固定字典里换算法**（`self.algorithm_choices` 里预置 quicksort/mergesort/heapsort/bubblesort），
不是在设计新结构。**是「在既有选项中重选」，不是「结构可进化」。**

**(b) MSTAR V4.0-Clean 的 RSPL / SEPL —— 有「协议」，但协议的对象是 skill**

原文（`mstar_core/evolution/protocol.py`）：
> `RSPL (Registry Skill Protocol Language):`
> `SEPL (Skill Evolution Protocol Language):`

**为何不构成**：RSPL 管的是 `SkillMetadata`（`skill_id`/`version`/`dependencies`/`output_schema`，
源码可见），SEPL 管的是 mutation 的「提交流程 + 版本控制 + 回滚协议」。
**两者都是 skill 的注册与版本协议，不是系统结构的协议。**
而且 README「项目结构」表里 `protocol.py` 的自述注释只有 6 个字：`#   RSPL / SEPL 协议`，
没有把它定位成结构层。

**(c) Darwin 「学习如何设计更好的实验策略」—— 进化的是策略，不是被进化的架构**

原文（`instance_base.py::DarwinInstance` docstring）：
> `- 这样达尔文可以从大量实验结果中学习"如何设计更好的实验策略"`
> `学习机制: 实验失败 → 失败原因分析 → 改进策略设计 → 新方案 → 实验`

**为何不构成**：这是一个**元层提升**：v7.0 里 Darwin 既设计又执行，v9.0 拆开后
Darwin 专职「设计实验」。但它学习的是「怎么设计变异实验」——
**这仍然是策略层，不是结构层。** 结构（五实例、事件类型、L1-L4 分层）在两版之间是**固定的**：
HCI 和 CIP 的五实例名字、六个事件类型完全一致（`verify_design_compliance.py` 逐项核对的就是这六项）。

### 5.3 一句话回答

**在这 17 个仓库的原文里，「进化」的最大明确边界是 CIP/HCI 的 L4「底层代码 / 算法 / 数据结构」。
作者从未写下「架构或结构本身可进化」这一表述 —— 一次也没有。
最接近的 RSPL/SEPL 协议层，其对象是 skill 注册与版本，不是系统结构。**

---

## 6. 附带发现：2026-08 之后这条线不谈进化了

`PPT.SKILL`（2026-08-28）与 `PPTPRO.SKILL`（2026-09-15）README 全文中，
**进化类词汇（自我进化/自适应/适应度/变异/反思/闭环之外的进化义）几乎归零**，
`PPTPRO.SKILL` 里出现的「迭代优化」是工作流打磨的意思，不是自我进化：

> `PPT generation agent-skill bundle: … optimized python-pptx/Windows…`
> `来自长期实战迭代优化后的 PowerPoint 自动化工作流。`

`PPT.SKILL` 里唯一接近「闭环」的是视觉验收闭环，与进化无关（README 原文）：
> `**铁律**：python-pptx / PptxGenJS 只保证「有字」，看不见版式。
> 生成后必须转图、逐页目检（严禁抽检），这是「盲写版式」的唯一闭环。`

**这条线在 2026-05-28（CIP-Zhazhazhu / hermes-kanban-cip）之后就停止了自进化方向的公开产出，
转去做能力型技能流水线。** 这是时间线事实陈述，不是解读。

---

## 7. 数据完整性与缺口（如实记录）

| 仓库 | README | md 文档 | 备注 |
|---|---|---|---|
| `hermes-collective-intelligence` | **无** | **无** | GitHub 无任何 .md；只能引 description + 源码 docstring |
| `CIP-Zhazhazhu` | **无** | **无** | 同上；含误提交的 `__pycache__/*.pyc` |
| `hermes-personal-backup` | 有 | 14 | 与 `hermes-agent-backup` 内容同构；GitHub API 404 |
| `-hermes` | 有（358 字符） | 14 | GitHub API 404；含插件级 README |
| `MSTAR-Pro-V4.0` | 有（但 = Hermes README） | 14 | 仓库内容是真 MSTAR，README 错配 |
| `MSTAR-Pro-V4.0-Clean` | 有（线上 6564 vs 抓取 5034） | 1 | 已抓线上最新版核对，差异仅尾部 |
| 其余 11 仓 | 有 | 有 | 全文已读 |

**两个真实缺口**：
1. `hermes-collective-intelligence` 与 `CIP-Zhazhazhu` 的**原始设计文档
   `E:/HERMES_Collective_Intelligence.txt` 不在 GitHub**（源码 docstring 引用它，
   `verify_design_compliance.py` 依赖它存在）。CIP 侧对应的规格文档同样只在 docstring 里
   被引用为「设计文档规格：v9.0 CIP …」，实体未抓取。
2. 「Clean」的含义**作者从未用文字说明**，§2.6 的三条推断均已标注证据等级。

---

## 8. 词汇表（作者实际用过的词，按出现仓库归类）

| 词/短语 | 出现处（仓库 :: 文件） | 原句 |
|---|---|---|
| self-improv / 自我改进 | `hermes-agent` :: README.md | "**The self-improving AI agent** built by Nous Research" |
| closed learning loop / 闭环学习 | `hermes-agent` :: README.md | "**A closed learning loop** — Agent-curated memory with periodic nudges." |
| self-improve during use | `hermes-agent` :: README.md | "Skills **self-improve during use**." |
| 自进化 AI 代理 | `hermes-agent` :: README.zh-CN.md | "**由 Nous Research 构建的自进化 AI 代理**" |
| 自己维护自己 | `hermes-agent` :: RELEASE_v0.12.0.md | "**The Curator release — Hermes Agent now maintains itself.**" |
| 自我改进循环 | `hermes-agent` :: RELEASE_v0.12.0.md | "The **background review fork** (the core of Hermes' self-improvement: after each turn it decides what memories/skills to save or update)" |
| 自我进化 | `mstar` :: README.md | "基于适应度的**程序变异**与淘汰机制" |
| 专门化记忆 > 通用化 | `mstar` :: README.md | "*\"专门化记忆 > 通用化\"*" |
| self-evolving memory system | `hermes-mstar` :: README.md | "combines **genetic programming evolution** with production-grade reliability tracking" |
| SelfImproving bridge | `hermes-mstar` :: README.md | "**SelfImprovingBridge** connects `~/.hermes/self-improving/corrections.md` to MSTAR mutation engine" |
| 自主进化 Skill 系统 | `Hermes-MSTAR-V2.0` :: README.md | "实现的**自主进化 Skill 系统**" |
| 自适应进化 | `hermes-mstar` :: README.md | "evolution_engine.py — **Adaptive evolution** (3-50 session intervals)" |
| 自进化引擎 | `mstar-pro` :: README.md | "**MSTAR Pro** 是一个无需外部依赖的自进化引擎" |
| 进化链（Lineage） | `mstar-pro` :: README.md | "记录每个程序的**进化链（Lineage）**，支持回溯分析" |
| 全链路自进化系统 | `MSTAR-Pro-V4.0-Clean` :: README.md | "**Phase 0-7 全链路自进化系统**" |
| 检索自进化 | `MSTAR-Pro-V4.0-Clean` :: README.md | "evolvemem.py — **EvolveMem 检索自进化**" |
| Skill进化协议 | `MSTAR-Pro-V4.0-Clean` :: `mstar_core/evolution/protocol.py` | "SEPL (Skill Evolution Protocol Language)" |
| 形式化验证的遗传变异 | `MSTAR-Pro-V4.0-Clean` :: `mstar_core/evolution/version_control.py` | "FGGM (Formally Verified Genetic Mutations)" |
| 全谱进化系统 | `hermes-collective-intelligence` :: GitHub description | "HERMES Collective Intelligence **全谱进化系统**" |
| 全谱进化引擎 | `hermes-collective-intelligence` :: `evolution_layers/evolution_layers.py` | "L1-L4**全谱进化引擎**" |
| L4 底层代码 / 算法/数据结构 | `hermes-collective-intelligence` :: `evolution_layers/evolution_layers.py` | "L4 底层代码 │ 算法/数据结构" |
| 工作流重构 | `hermes-collective-intelligence` :: `evolution_layers/evolution_layers.py` | "L3BehaviorMutator — **L3行为层变异器 - 工作流重构**" |
| 北极星指标 | `hermes-collective-intelligence` :: `evolution_layers/evolution_layers.py` | "北极星指标: 成本更低 / 标准更高 / 速度更快" |
| 修改底层代码（需最高安全阈值） | `hermes-collective-intelligence` :: `mutation_handler.py` | "L4_CODE: **修改底层代码（需最高安全阈值）**" |
| 进化策略设计专职（不执行） | `hermes-collective-intelligence` :: `instances/instance_base.py` | "3. 达尔文 (Darwin) - **进化策略设计专职(不执行)**" |
| 关键区别于 v7.0 | `hermes-collective-intelligence` :: `instances/instance_base.py` | "v7.0里达尔文=进化池本身(既设计又执行)" |
| 四层联动变异调度器 | `CIP-Zhazhazhu` :: `hermes_cip/evolution/full_spectrum.py` | "FullSpectrumScheduler — **L1-L4 四层联动变异调度器**" |
| 笛卡尔基因编程（CGP） | `CIP-Zhazhazhu` :: `hermes_cip/evolution/code_mutator.py` | "CodeCGP — **笛卡尔基因编程**（Cartesian Genetic Programming）" |
| Darwin模式 | `CIP-Zhazhazhu` :: GitHub description | "炸炸宝实现版 **(Darwin模式)**" |
| 三系统进化循环 | `hermes-scripts` :: README.md | "包含**三系统进化循环（MSTAR + SkillClaw + Homunculus）**" |
| Darwin skill 自动优化 | `hermes-scripts` :: README.md | "SkillClaw低分 → **darwin优化**" |
| 自我改进 | `hermes-skills` :: `autonomous-ai-agents/.../hermes-agent/SKILL.md` | "**Self-improving through skills** — Hermes learns from experience by saving reusable procedures as skills." |
| 自我进化记忆（Phase 1完成） | `hermes-skills` :: README.md | "\| `mstar` \| MSTAR **自进化记忆**（Phase 1完成） \|" |
| MSTAR 自进化记忆系统 | `hermes-skills` :: README.md | "\| `mstar/` \| MSTAR **自进化记忆系统** \|" |
| 本能触发 | `hermes-scripts` :: README.md | "Homunculus (**本能生成**) ↓ 本能触发 ↓ MSTAR FitnessTracker (program fitness boost)" |
