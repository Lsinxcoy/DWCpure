# R399 · 最终基线（两轮独立样本）

> 2026-10-21 01:15 · HEAD `c933a78`(476) + 本文档
> 判据：R388 三重证据 + R389/R392 猜测检测 + R397 归一化匹配（严格）

## 一、总表

| 类型 | R390 基线 | 第 1 轮 | 第 2 轮 | 变化 |
|---|---|---|---|---|
| read-fact | 8/14 = 57% | 12/14 = 86% | 12/14 = 86% | **+29pt** |
| code-locate | 2/10 = 20% | 5/10 = 50% | 6/10 = 60% | **+30~40pt** |
| run-verify | 4/10 = 40% | 8/10 = 80%¹ | 8/10 = 80% | **+40pt** |
| analyze | 7/10 = 70% | 9/10 = 90% | 9/10 = 90% | +20pt |
| write | 8/8 = 100% | 8/8 = 100% | 8/8 = 100% | 持平 |
| historical | 1/2 = 50% | 1/2 = 50% | 1/2 = 50% | 持平 |
| **总计** | **30/54 = 55.6%** | **43/54 = 79.6%¹** | **44/54 = 81.5%** | **+24~26pt** |

¹ 第 1 轮跑批原始数字是 42/54（77.8%），其中 3 单 run-verify 被 R397
  的字符串/argv 匹配缺陷**误判**，修正判据后复核为 43/54（rv08 恢复）。
  rv06/rv07 是真没跑指定命令，判 ✗ 正确。

**两轮均值 43.5/54 = 80.6%，极差 79.6%~81.5%（1.9pt）。**

## 二、状态分布

| 指标 | R390 基线 | 第 1 轮 | 第 2 轮 |
|---|---|---|---|
| `done` | 47/54 | **54/54** | **54/54** |
| `incomplete` | 7 | **0** | **0** |
| `timeout/no-report` | 0 | 0 | 0 |

失败归因只剩一类：**D. 答完了但答案不对**（10 单），不再有"中途放弃"。

## 三、失败明细（第 2 轮，10 单）

```
rf09  read-fact     answer contains 'DWC_STEP_JUDGE'
rf12  read-fact     answer contains 'dwc-deep-space'
cl02  code-locate   answer contains 'memory.py'
cl04  code-locate   answer contains 'effort.py'
cl07  code-locate   answer contains 'revision.py'
cl08  code-locate   answer contains 'cli_main.py'
cl10  code-locate   answer contains 'agent_quality.py'
rv06  run-verify    no-agent-evidence（换了等价方法，没跑指定命令）
rv07  run-verify    no-agent-evidence（没跑 gate.py）
hs01  historical    答案不对
```

**全部是"答案错"，没有一单是"没做完"。**

## 四、本轮修复链（8 个提交）

| 提交 | 内容 | 效果 |
|---|---|---|
| `81a589c` R394 | `search_code` 换 Python，定义置顶 | 模型能读出 `def X` 在哪 |
| `e8541f1` R395 | store 容忍坏行 + `os.write` 原子追加 | 修 59 failed + 37 errors |
| `9cc354d` R396 | 卡住时 `tool_choice` 强制 `final_answer` | incomplete 10→0 |
| `651c53f` R397 | 证据匹配归一化（字符串 vs argv） | 恢复 1 单误判 |
| `c933a78` R398 | 收件箱心跳 + 重取上限 3 次 | 修"一单重跑 52 次" |
| （前序）R391 | `find` → Python（Windows `find.exe` 冲突） | code-locate 解锁 |
| （前序）R393 | 工具层 step 带 `readonly:True` | 修 R391 的回归 |
| （前序）R392 | 猜测检测改句子级 | read-fact 57%→86% |

## 五、诚实边界

1. **只有 2 个样本**，无置信区间；两轮间隔 1 小时，端点状态不同。
2. 第 1 轮跑批中途端点变慢（3 单 analyze 超时）—— 已用第 2 轮重跑验证，
   第 2 轮 0 超时。
3. `code-locate` 是唯一有明显波动的类（50% vs 60%），其余完全稳定。
4. **10 单失败全是答案错**，其中 5 单 code-locate 是真定位错（不是工具问题）。
5. `rv06/rv07` 的 ✗ 是**判据选择**（要求跑指定命令），不是能力缺陷 ——
   若改为"接受等价验证"，会 +2 单。
6. `MAX_REPICK=3`、`NATIVE_TOOLS_MAX_ROUNDS=15` 等阈值都是拍的数，
   没有调参实验支撑。
