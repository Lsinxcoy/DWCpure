# R436 · 提示词 A/B 全池 × 2 轮（进行中）

> 状态文件：跨会话续接用。开始 2026-10-22 23:32，**结束 2026-10-23 07:10（已出结论）**。

## 目的

给 `task_exec` 的候选 v2（v1 + 一条「取证优先」硬规则）做**正式晋升判定**。
之前 6 单 smoke 跑了两次，结论互相矛盾（一次 1 赢 1 输，一次 0 赢 1 输），
说明单轮单题是噪声 —— 需要全池 + 重复。

## 配置

| 项 | 值 |
|---|---|
| 候选 | `prompts/task_exec.v2.md`（v1 + 1 条规则，2006 B） |
| 对照 | `stable=v1` |
| 题池 | **52 单**（`config/eval_tasks.jsonl` 全量） |
| 波次 | `--wave 4`（4 单并发） |
| 每波等待 | 15 分钟 |
| 轮数 | **2**（串行） |
| 判定 | 赢 ≥2 且**零退化**才 promote；infra 不计分母 |

## 运行方式

agent 以并发 4/4、预算 1000/1000 启动（否则 52 单会撞 `daily_limit`）：

```bash
DWC_HTTP_CONCURRENCY=4 DWC_TASK_CONCURRENCY=4 \
  python <scratch>/restart_agent.py --terms-per-day 1000 --budget-day 1000
```

两轮串行（后台）：

```bash
python scripts/dwc_prompt_ab.py --name task_exec --candidate v2 \
  --ids <52 单> --wave 4 --wait-min 15 --min-tasks 40 --min-wins 2
```

## 产出

| 文件 | 内容 |
|---|---|
| `var/prompt_ab_full_r1.log` / `r2.log` | 两轮控制台日志 |
| `var/prompt_ab_task_exec_v2_<ts>.json` | 每轮的逐题两臂明细 |
| `var/prompt_force.json` | 钉版本（跑完自动删除） |

## 预期耗时

52 单 ÷ 4 = 13 波 × 2 臂 × ~5.5 分钟 ≈ **2.4 小时/轮**，两轮 ≈ **4.8 小时**。

## 跑完要做

1. 聚合两轮：逐题看「两轮都赢 / 一轮赢一轮平 / 有任一输」
2. 判定：**任一题任一轮退化 ⇒ reject**；两轮合计赢 ≥2 且零退化 ⇒ promote
3. `--promote` 写 manifest（`stable=v2, candidate=null, pct=0`）
4. **把 agent 恢复生产默认**（HTTP=1 / TASK=2，预算 96/80）
5. 证据归档到 `docs/data_r410/`，更新 `R410_PROGRESS_SNAPSHOT.md` §2.8

## 中途失败怎么办

- 某轮日志出现 `EXIT=1`：先看是判据错还是超时
- `?` 标记 = infra（502 等），已在分母外；重跑该轮即可
- agent 挂了：`restart_agent.py` 同样参数拉起，再重跑该轮

---

## 结果（2026-10-23 07:10 完成）

| 轮 | 有效题 | stable | candidate | 判定 |
|---|---|---|---|---|
| R1 | 36（16 单 infra） | **88.9%** | 86.1% | INSUFFICIENT（赢 2 / 输 3） |
| R2 | 52 | **90.4%** | 86.5% | REJECT（赢 3 / 输 5） |

逐题：两轮都赢 **0**、两轮都输 **0**、方向翻转 1（`cl08`）、两轮同结果 26/36（72%）。

**结论：候选 v2 无效，不晋升。** manifest 保持 `stable=v1, candidate=null, pct=0`。
两轮聚合方向一致（候选低 2.8 / 3.9pp），但逐题零稳定信号 ⇒ 28% 的题会翻转，
单轮单题不可引用。

## 额外产出

- **跨臂「任务记忆」泄漏**：`recall_sources` 按任务文本召回历史 findings，
  两臂同题 ⇒ stable 臂的答案被 candidate 臂注入。已加 `var/sources_off`
  开关（A/B 期间两臂同等关闭），见 R436 提交。
- **502 定性**：23:31–23:41 上游短时故障，非并发问题（复测宽度 1/2/4 全 4/4）。
