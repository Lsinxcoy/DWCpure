# DWC 效果证明层报告（R259-R261 · 短板 1/2/3 补齐 · 2026-10-14）

## 硬数字（52 单 × A/B · 全机器判 · 验收在 agent 外）

| 臂 | 含义 | 成功率 |
|---|---|---|
| **A（关进化）** | judge off + 无 lessons 注入 + 无修订 | **47/52 = 90.4%** |
| **B（开进化）** | judge on + lessons 注入 + 修订在线（生产路径模拟） | **49/52 = 94.2%** |
| **Δ 进化净收益** | B − A | **+3.8 pp** |

分类型（A→B）: code-locate 9→10 · read-fact 9→10 · run-verify 8→9 · analyze 8→8 ·
write 8→8 · historical 2→2。**B 臂少 2 个失败**（rf08 `_rev_prev` 事实、cl08 CLI
入口 — lessons/judge 救回）。

## 任务集与验收（G2 纪律）

- 52 单分层: read-fact 12 / code-locate 10 / run-verify 10 / analyze 10 / write 8 /
  historical 2（17:12/17:13 原题）。事实全部从仓库真实文件机器抽取。
- **零 LLM 自评**: run 类验收器独立重跑命令（answer 说谎不影响判定）、write 类独立
  读盘、fact 类机器判文本（contains/regex）。`test_r259_eval.py` 锁死。
- **判据 Layer-22 修正 3 处**（rf03 答"3"判据要前缀 / rv10 语义题误用 stdout 锚 /
  an09 真值双合法 config+docs）→ `reverify_eval.py` 用当前判据对两臂统一重验
  （验收可独立重做 — G2）。

## 诚实边界（必须一起读）

1. **绝对值偏乐观**: 任务集合成自仓库自身场景（构造偏差），A/B 差值干净（同批任务
   相消）但 **90.4%/94.2% 不代表困难任务成功率**。真正困难面由 nightbench 真实流量
   持续测量（短板 2）。
2. **Δ=+3.8pp 样本有限**: n=52, 差值在个位数单上翻转（±1 单 ≈ ±1.9pp）。方向为正且
   机制可解释（B 救回的正是 lessons 覆盖的失败类），但**不是大样本统计结论**。
3. 测量层第一天抓到 **1 个真缺陷**: `dwc_self.md` 仍写旧 6 轮上限（R247 改 999 未
   同步）→ agent 用过时自我认知答错任务（rf04 答"6"）。已修 + 加回归锁
   （`test_self_md_current_facts`）。**这本身就是测量价值的实证**。
4. 瞬断教训: 连续快调触发端点限流曾把 A 臂压到 25%（假信号）→ 跑批加节流 3s +
   首轮挂自动退避重跑。**测量基础设施自己的可靠性也是被测对象。**

## 短板 2 · 无人值守回路（已上线）

- `dwc_nightbench.py`（cron `3c630a7186a1` 每日 02:30）: 从 52 单池轮换抽 8 单投
  **inbox**（agent 真实消费路径 — lessons/判别/修订全链在线）→ 机器验收 →
  `success_curve.jsonl` 时间序列。
- `dwc_nightbench_weekly.py`（cron `960775032adb` 周日 08:30）: 周报（成功率曲线 +
  修订回路活动）。**收敛证据从这里积累**（≥1 周）。

## 短板 3 · 选择性工具（已落地）

- `web_read` op（urllib 零依赖）: http/https 白名单 + 20s 超时 + 2MB 上限 +
  HTMLParser 转纯文本。实测三连: html2text 剥 script ✓ / file:// 拒绝 ✓ /
  真抓 example.com ✓。进 step_judge VALID_OPS + 修订校验 + system prompt。
- **明确不做**: 浏览器自动化、MCP 生态追平、连接器（不追平 Hermes — 选择性纪律）。

---

*测量基准 2026-10-14 · 52 单 A/B · 重验后 A 47 / B 49 · 判据修正 3 处已留痕 ·
跑批框架与验收器测试锁 8 个*
