# DWC · Divine Wisdom Core

> **自进化常驻 agent** — 两大核心能力: **记忆**（拥有并有效使用）+ **自改进**（改进自身从而更强）。
> 七器官 · 八质量门 · 全屏 TUI · 999 轮任务执行核 · 一行安装。

[![pytest](https://img.shields.io/badge/pytest-2717%20passed-brightgreen)](#开发)
[![rounds](https://img.shields.io/badge/rounds-R1%E2%80%93R438-FFB86B)](docs/PROGRESS.md)
[![commits](https://img.shields.io/badge/commits-547-blue)](docs/PROGRESS.md)

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
| [ARCHITECTURE_MAP.html](docs/ARCHITECTURE_MAP.html) | 架构图（浏览器打开） |
| [DESIGN_RATIONALE.md](docs/DESIGN_RATIONALE.md) | 设计理据 · 与母巢的关系 · 九条实测陷阱 |
| [PRODUCTION_RUNBOOK.md](docs/PRODUCTION_RUNBOOK.md) | 生产运维手册 |
| [REPORT_RSI_JEPA.html](docs/REPORT_RSI_JEPA.html) | RSI/JEPA 研究报告 |

## 开发

四层验证每轮必过: `pytest`（2717 全绿）· `gate.py`（8/8）· `e2e_loop.py` · `e2e_core.py`。
纪律: 声称=实测（每个数字可复跑）· Layer-22（判据错修判据）· R73 无设计不发明 · G7 静默门。

> ★ 2026-10-23 审计修复完成（R审计-P0~P2）: 全量基线 **2717 passed / 0 failed / 4 skipped**。
> 修复内容: 371 处硬编码路径相对化 · 依赖声明补齐 · 沙箱资源守卫三层纵深 ·
> F821/ruff/bandit 清零 · gate.py 八门全过 · 缓存竞态改内容哈希 · 测试环境自足。

```bash
git clone https://github.com/Lsinxcoy/divine-wisdom-core.git && cd divine-wisdom-core
pip install -r requirements.txt && pip install -e .
python -m pytest tests -q        # ~3 分钟（2717 全绿）
```

---

*R1–R438 · 547 commits · 2026-10-23（审计修复后基线 · 全量全绿）*
