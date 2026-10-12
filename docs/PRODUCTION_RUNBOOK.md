# DWC 生产 Runbook（R207 · 2026-10-12）

> 定义「DWC 投入生产」的运行边界、组件、巡检、故障处置与人工门。
> 配套：`docs/IRON_LAW_PRODUCTION.md`（铁律豁免清单）、
> `docs/AUDIT_R202_PRODUCTION.html`（深度审计报告）。

## 一 · 生产形态定义

**当前生产 = 受监督的定时多 term 轮 + 人工观察台账**，非无人值守自主进化：

| 组件 | 机制 | 频率 | 健康判据 |
|---|---|---|---|
| 生产运行 | cron `91603dba7d05` → `dwc_prod_run.py`（默认 3 terms × 2 steps） | 每 6h | rc0 空 stdout |
| 健康探针 | cron `303b2054e9ea` → `dwc_prod_health.py` | 每 2h | 静默=健康；异常→飞书直推 |
| 备份 | cron `d103c2624824` → `dwc_backup.py` | 每日 03:00 | rc0；缺对象 rc1 |
| 锚漂移监控 | cron `f3e18d04b90f` → `dwc_anchor_drift_watch.py` | 每 2h | 有建议即推；24h 节流 |

**状态与台账**：库 `var/dwc_prod.sqlite`（持久）· 逐轮台账
`var/dwc_prod_log.jsonl`（append-only，event 行分段）· 备份
`var/backup/<ts>/`（保留 7 份）。全部在 `.gitignore var/` 下，绝不入库。

**健康=silence 契约**（hermes-cron-feishu）：所有 no_agent 脚本正常
rc0 空 stdout；异常走脚本内飞书 API 直推或 rc1+stderr。
**CRON RUNS THE COPY**：cron 跑 `%LOCALAPPDATA%/hermes/scripts/` 副本，
仓库改动必须 md5 同步（`test_cron_copies_in_sync` 锁死）。

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

## 六 · 当前生产就绪清单（2026-10-12 终验）

- P0 全落：常驻运行器 ✓ · 持久化 ✓ · 真 LLM 通道实测 ✓ · 回填自动化 ✓
- P1 全落：健康探针（2h cron）✓ · 备份（每日 cron + 7 份滚动）✓ ·
  铁律豁免清单 ✓（11=2 真判+1 na+8 豁免，无静默）
- P2 全落：e2e 六公开方法全覆盖 + 多 term 段 ✓ · 本文档 ✓
- 验证基线：pytest 1451（R207 后实测见 PROGRESS）· gate 8/8 ·
  双 e2e rc=0 · 四 cron 在排 · 备份快照实测 5 对象全在
