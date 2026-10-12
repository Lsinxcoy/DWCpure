# DWC 生产 Runbook（R207 · 2026-10-12）

> 定义「DWC 投入生产」的运行边界、组件、巡检、故障处置与人工门。
> 配套：`docs/IRON_LAW_PRODUCTION.md`（铁律豁免清单）、
> `docs/AUDIT_R202_PRODUCTION.html`（深度审计报告）。

## 一 · 生产形态定义（R208 修正: 独立 agent）

**DWC 生产 = 独立常驻 agent**（`dwc_agent.py`）：自主循环——感知（judge
判分/漂移）→ 决策 → 行动（actor/evolver）→ 记忆 → **自己触发下一轮**
（任务源取上轮 `next_task_source` 的 `world_tree_action.node`，"measurement
becomes the trigger of the next iteration" 的进程级落地）。cron 不喂食，
只守夜：

| 组件 | 机制 | 频率 | 角色 |
|---|---|---|---|
| **agent 主体** | `dwc_agent.py` 常驻（interval 600s 自主节奏；日限 terms=48/budget=40 超限优雅停，次日守夜人拉活自动复位） | 常驻 | 自主循环本体 |
| 守夜人 | cron `b402a1b4a098` → `dwc_agent_watch.py`（pid+心跳判活；死→后台拉活+飞书告警；冻结中不干预） | 每 2h | 拉活，不喂食 |
| 健康探针 | cron `303b2054e9ea` → `dwc_prod_health.py`（db/台账/停滞/真值源） | 每 2h | 报告 |
| 备份 | cron `d103c2624824` → `dwc_backup.py` | 每日 03:00 | 快照 |
| 锚漂移监控 | cron `f3e18d04b90f` → `dwc_anchor_drift_watch.py` | 每 2h | 建议推送 |

★ 冻结（人工最高门）: `python scripts/dwc_agent.py --freeze`（agent 下轮
  优雅停，守夜人不拉活）；`--unfreeze` 解冻，`--status` 查 pid/心跳/冻结态。
★ 批处理工具 `dwc_prod_run.py` 保留为手动单发（与 agent 互斥——同 db 双写
  会锁冲突；其 cron 已撤）。

**状态与台账**：库 `var/dwc_prod.sqlite`（持久）· 逐轮台账
`var/dwc_prod_log.jsonl`（append-only，event 行分段）· 备份
`var/backup/<ts>/`（保留 7 份）。全部在 `.gitignore var/` 下，绝不入库。

**健康=silence 契约**（hermes-cron-feishu）：所有 no_agent 脚本正常
rc0 空 stdout；异常走脚本内飞书 API 直推或 rc1+stderr。
**CRON RUNS THE COPY**：cron 跑 `%LOCALAPPDATA%/hermes/scripts/` 副本，
仓库改动必须 md5 同步（`test_cron_copies_in_sync` 锁死）。

## 一B · 怎么给它下任务（R209 接单面 — agent 优先消费收件箱）

```bash
# 方式1: CLI 投单（最直接）
python scripts/dwc_agent.py --submit "你的任务描述" --id T_my01

# 方式2: 说给我（Hermes），我代投 —— 你说任务，我写 inbox，结果回你

# 方式3: 直接追加 var/dwc_inbox.jsonl（一行一个 JSON: id/task/ctx）
```

- **消费**: agent 主循环**收件箱优先**（用户委托 > 自我改进锚任务），每
  600s 检查一次；任务经 LLMTaskExecutor 多轮执行（read/write/run/final
  四动作白名单，写限 `var/inbox_work/`，危险命令黑名单，60s/命令超时）。
- **结果**: 报告 `var/dwc_reports/<id>.json` + **飞书通知**（done 给结论,
  incomplete 给原因——不静默装完成）。真实首单实测: 3 轮 23.5s done。
- 边界: 收件箱任务必须 LLM 通道（agent 自带 LLMClient, 不依赖启动参数）;
  max 4 轮未 final ⇒ incomplete 如实报。

## 二 · 能力通道（诚实声明）

- 默认执行器 = `execute_task` 真断言执行（golden checks 真跑）；
  `--llm` = R126 `LLMExecutorFactory(LLMClient())` 真 LLM 通道
  （2026-10-12 实测：端点活，1 term completed，pass_rate=0.0 如实入账）。
- **当前真实能力状态：dev 6 behavior 任务 0/6 通过**——台账每轮记录
  pass_rate，这是能力现状不是故障；退化崩塌护栏只在「曾经 >0.1 后连续
  2 轮 <0.1」时停机告警（冷启动全败不误伤）。
- 真值源（dev.json/iron_laws.yaml/epoch ledger）agent 只读；
  锚替换权在人（`record_epoch` 单调锁 + 文件权限双保险）。

## 三 · 巡检节奏

1. **每日**：看 `var/dwc_prod_log.jsonl` 尾段（pass_rate 趋势 / drift GDI /
   advice 触发 / iron_block 空否）；确认无飞书告警。
2. **每周**：`git log` 知识档链（R20x 每轮一档六段过 validate）；
   确认备份目录滚动正常（7 份）；`scripts/gate.py` 8/8。
3. **每轮改动**：三层验证强制（pytest 全绿 + gate 8/8 + e2e_loop/e2e_core
   rc=0），缺一不提交。

## 四 · 故障处置

| 症状 | 处置 |
|---|---|
| 飞书「agent 已拉活」 | 守夜人重启留痕：查台账尾 `agent_stopped` 事件定位死因（freeze/daily_limit/collapse/term_error） |
| agent 冻结中不起来 | 预期行为：`--unfreeze` 后等守夜人下个 tick 或手动启动 |
| 手动跑过批处理后 agent 锁冲突 | 双写同 db 禁止：先停批处理（kill）再放 agent；台账有 sqlite locked 报错即查此因 |
| 飞书「生产健康告警」 | 按告警项定位：db/台账/停滞/真值源；恢复后探针自动静默 |
| 台账 stopped_collapse | 看倒数第二轮 pass_rate 跌幅；比对 `git diff` 近期改动；必要时 `git revert` + 从 `var/backup/` 恢复 db |
| 台账 stopped_budget | 预算内正常停；调 `--budget` 或查单 term 成本异常 |
| term error 行 | 错误类型入台账；W5/provenance 类先查回填口径（Layer 22：修判据不改纪律） |
| 备份 rc1「对象缺失」 | 真值源被移位/删除——立即人工介入（这是最高级告警） |
| LLM 端点失败 | llm/client 自带 retries=1+超时；连续失败回退默认执行器轮次 |

**回滚标准动作**：
```bash
# 从最近备份恢复（例）
cp var/backup/20261012_030000/dwc_prod.sqlite var/dwc_prod.sqlite
cp var/backup/20261012_030000/anchors/dev.json config/anchors/dev.json
# 代码回滚
git revert <bad-commit>   # 知识档链保留（继承可追溯）
```

## 五 · 人工门（agent 永不自动）

1. **锚/真值源替换**：只增不改由机器锁；替换权在人（含 epoch 换代）。
2. **冻结开关**：G3 数据面未落地前，冻结=人工停 cron（`cronjob_manage pause`）。
3. **三层验证失败的合入**：任何红灯先判噪声再判回归（Layer 22 修判据）。
4. **LLM 端点/凭证更换**：`config/llm.json`（gitignore，永不入库）。
5. **铁律豁免收紧**：豁免表任一条数据面落地后，同轮接真判并删表行。

## 六 · 当前生产就绪清单（2026-10-12 终验 · R208 agent 形态）

- 形态修正：**独立常驻 agent**（自主任务源闭环 + 守夜人拉活 + 冻结人工门）
  ✓ —— 批处理 cron 已撤，agent 实跑心跳 alive
- P0 全落：常驻（agent 形态）✓ · 持久化 ✓ · 真 LLM 通道实测 ✓ · 回填自动化 ✓
- P1 全落：健康探针（2h cron）✓ · 备份（每日 cron + 7 份滚动）✓ ·
  铁律豁免清单 ✓（11=2 真判+1 na+8 豁免，无静默）
- P2 全落：e2e 六公开方法全覆盖 + 多 term 段 ✓ · 本文档 ✓
- 验证基线：pytest 1451（R207 后实测见 PROGRESS）· gate 8/8 ·
  双 e2e rc=0 · 四 cron 在排 · 备份快照实测 5 对象全在
