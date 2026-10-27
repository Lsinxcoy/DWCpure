# DWC · Divine Wisdom Core

> **自进化常驻 agent** — 两大核心能力: **记忆**（拥有并有效使用）+ **自改进**（改进自身从而更强）。
> 七器官 · 八质量门 · 全屏 TUI · 999 轮任务执行核 · 一行安装。

[![pytest](https://img.shields.io/badge/pytest-3384%20passed%20%2F%209%20skipped-brightgreen)](#开发)
[![rounds](https://img.shields.io/badge/rounds-R1%E2%80%93R458-FFB86B)](docs/PROGRESS.md)
[![commits](https://img.shields.io/badge/commits-audit%20remediated-blue)](docs/PROGRESS.md)

---

## 一行安装

```powershell
# Windows（PowerShell 5.1+）
(irm https://raw.githubusercontent.com/Lsinxcoy/divine-wisdom-core/master/install.ps1).TrimStart([char]0xfeff) | iex
```

```bash
# macOS / Linux / WSL
curl -fsSL https://raw.githubusercontent.com/Lsinxcoy/divine-wisdom-core/master/install.sh | bash
```

自动完成: clone 到 `~/.dwc` → venv → 依赖 → 注册 `dwc` 命令 → 冒烟自检。
**重跑同一行 = 更新到最新版。**

## 快速开始

```bash
dwc setup           # 首次配置向导（LLM 端点/key 遮蔽输入, 真实冒烟）
dwc                 # 全屏 TUI（消息卡片 · 命令面板 Ctrl+P · 文件树 · / 与 @ 补全）
dwc start --llm     # 常驻 agent（后台自触发循环, watchdog 守护）
dwc status          # 实时状态; dwc ask "任务" 单发派单
```

## DWC pure 2.0

2.0 的实现状态、真实测量证据、shadow-only 边界和未启用项，统一见
[docs/DWC_PURE_2.0_IMPLEMENTATION_STATUS.md](docs/DWC_PURE_2.0_IMPLEMENTATION_STATUS.md)。
设计规格见 [docs/DWC_PURE_2.0_DEVELOPMENT_PLAN.md](docs/DWC_PURE_2.0_DEVELOPMENT_PLAN.md)。

## 能力一览

| 能力 | 形态 |
|---|---|
| **任务执行核** | 999 轮自主循环 · read 翻页(offset) · 复读熔断(3 连同→硬出口) · 危险命令 ask 人工授权 · delegate 并行子代理 · 失败现场全留痕 |
| **原生 TUI** | 深空设计语言(白字+琥珀) · 消息卡片+Markdown · 思考 spinner · Ctrl+P 命令面板 · 文件树侧栏 · 智能滚动(不打断阅读) |
| **七器官** | memory · judge · evolver · loop · world_tree · predictor · world_model |
| **八质量门** | 定位/真值/活性/生灭/声称/加减/静默/契约 — `scripts/gate.py` |
| **自更新** | `dwc update` 从 GitHub ff-only 拉取 + 依赖变更检测 + agent 自动重启(心跳验证) |
| **常驻体** | inbox 接单 · 独立指令集/RPC(:8802) · watchdog 崩溃拉活+飞书告警 · cron 健康/备份/漂移巡检 |

## 常用命令

```bash
dwc                  # TUI           dwc --plain         # 旧版 REPL
dwc doctor           # 七项自检       dwc update [--check] # 自更新
dwc start --llm      # 起 agent       dwc stop            # 停 agent
dwc ask "任务"        # 单发派单       dwc status          # 状态/队列
dwc memory-stats     # 记忆契约/检索统计（只读）
dwc knowledge build  # 记忆 → var/knowledge/*.md（可重建）
dwc memory consolidate        # 近重复合并 dry-run；--apply 才写
dwc memory migrate-factual    # factual SKILL → REFERENCE dry-run；--apply 才写
```

TUI 内: `/help` · `/new` · `/update` · `/bg`(异步投单) · `/fg`(同步直驱) · `@` 文件补全 · `↑` 历史。

## 架构

[架构图 ARCHITECTURE_MAP.html](docs/ARCHITECTURE_MAP.html) · [设计理据 DESIGN_RATIONALE.md](docs/DESIGN_RATIONALE.md)

```text
记忆唯一载体 · 判据在记忆之外 — 所有进化都生长在记忆之上
七器官: memory · judge · evolver · loop · world_tree · predictor · world_model
进化循环七环节 · 三入口(dwc 主类收拢) · 真值源 agent 结构上只读
```

## 文档

| 文档 | 内容 |
|---|---|
| [PROGRESS.md](docs/PROGRESS.md) | 轮次账 R1–R250（每轮一知识档 archive/knowledge3_R*.json） |
| [DWC_PURE_2.0_DEVELOPMENT_PLAN.md](docs/DWC_PURE_2.0_DEVELOPMENT_PLAN.md) | **2.0 唯一开发计划入口** · 四论文代码级最终融合规格 · PLANNED / FROZEN |
| [ARCHITECTURE_MAP.html](docs/ARCHITECTURE_MAP.html) | 架构图（浏览器打开） |
| [DESIGN_RATIONALE.md](docs/DESIGN_RATIONALE.md) | 设计理据 · 与母巢的关系 · 九条实测陷阱 |
| [PRODUCTION_RUNBOOK.md](docs/PRODUCTION_RUNBOOK.md) | 生产运维手册 |
| [REPORT_RSI_JEPA.html](docs/REPORT_RSI_JEPA.html) | RSI/JEPA 研究报告 |

## 开发

四层验证每轮必过: `pytest`（3384 passed / 9 skipped，非真端点；r208 lifecycle 单独超时）· `gate.py`（8/8）· `e2e_loop.py` · `e2e_core.py`。
纪律: 声称=实测（每个数字可复跑）· Layer-22（判据错修判据）· R73 无设计不发明 · G7 静默门。

> ★ 2026-10-26 审计修复完成（P0–P3）: 全量基线 **3384 passed / 9 skipped / 0 failed**（P0 TaskContract 11 项 + P0.5 契约补齐 2 项 + P1 apply_patch 6 项）。
> 修复内容: 命令 allowlist · actor/candidates AST 沙箱 · SSRF/路径门 · 复读重试可达 ·
> judge 泄漏检查 · QA 诚实状态 · FTS 一次性迁移 · SQLite 锁/超时 · 原子写 · CI。
> F821 已清零；ruff/bandit 按 CI 选中规则门禁，不再声称“全库清零”。

```bash
git clone https://github.com/Lsinxcoy/divine-wisdom-core-pure.git && cd divine-wisdom-core-pure
pip install -r requirements.txt && pip install -e .
python -m pytest tests -q        # ~11 分钟（3384 passed / 9 skipped，非真端点）
```

---

*R1–R458 · 2026-10-26（审计修复后基线 · 全量全绿）*
