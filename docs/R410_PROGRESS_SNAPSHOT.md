# R410 · 进度快照（gateway 重启前固化）

> 写入时间：2026-10-21 11:18 (+08:00)
> 用途：Hermes gateway 手动重启前落盘，重启后照此续接，不丢进度。

---

## 一、代码状态

| 项 | 值 |
|---|---|
| HEAD | `4d41b5c` **R407-R408 · read-fact：标识符类必须取证 + 有证据不许拒答** |
| 上一提交 | `15a687a` eval: 修正 rf12 的期望值 |
| 工作区 | 仅 `archive/gate_trace.jsonl` 有运行时改动（非本轮核心，未提交） |
| 全量 pytest | **2533 passed / 0 failed**（`var/pytest_r410.log`，366.89s） |
| 提交内容 | 5 files, +488 / −1 |

本轮提交的五个文件：

```
src/dwc/llm/task_exec.py            R407 / R407-b / R408 / R408-b
src/dwc/harness/anchor_drift.py     R409 读侧容错
tests/test_r407_ident_evidence.py   5 条
tests/test_r408_refusal_with_evidence.py  4 条
tests/test_r409_evidence_tolerant.py      2 条
```

---

## 二、全池基线（最新）

`var/nightbench_r410.log` — **47/54 = 87.0%**（上一轮 46/54 = 85.2%）

| 类别 | 本轮 | 上轮 |
|---|---|---|
| write | 8/8 = 100% | 8/8 |
| analyze | 9/10 = 90% | 9/10 |
| code-locate | 9/10 = 90% | 9/10 |
| **read-fact** | **12/14 = 86%** | 11/14 = 79% |
| run-verify | 8/10 = 80% | 8/10 |
| historical | 1/2 = 50% | 1/2 |
| **总计** | **47/54 = 87.0%** | 46/54 = 85.2% |

54/54 `done`，零 incomplete、零超时、零重复执行。

**演进轨迹**：79.6% → 81.5% → 85.2% → 85.2% → **87.0%**

剩余 7 单：`rf09`（编造变量名）、`rf12`（证据在手仍拒答）、`cl08`（无符号名幻觉）、
`rv06`/`rv07`（等价方法不算证据，有意严格）、`an03`（少 2 个 arXiv 编号）、
`hs01`（any-of 空）。

---

## 三、reasoning_effort 六档 A/B（本轮新增实验）

### 3.1 端点能力

| 项 | 结果 |
|---|---|
| 接受的 `reasoning_effort` | `none` / `minimal` / `low` / `medium` / `high` / `xhigh` **全部 200 OK** |
| 可接受的 `max_tokens` 上限 | **65536**（8192/16384/32768/65536 逐级探到顶） |
| 代码层校验 | **无白名单**，`client.py:397` 原样透传 |

### 3.2 真实任务 A/B（rf05 对照 + rf09 + rf12，max_tokens=65536，每格 n=1）

| 档位 | 通过 | 平均耗时 | rf05 | rf09 | rf12 |
|---|---|---|---|---|---|
| **`none`** | **2/3** | **25s** | ✓ | ✗ | **✓** |
| `minimal` | 1/3 | 27s | ✗ | ✗ | **✓** |
| `low`（当前生产） | 1/3 | 40s | ✓ | ✗ | ✗ |
| `medium` | 1/3 | 50s | ✓ | ✗ | ✗ |
| `high` | **0/3** | 66s | ✗ | ✗ | ✗ |
| **`xhigh`** | **0/3** | 65s | ✗ | ✗ | ✗ |

**核心发现：档位越高越差，且越慢。**

- **rf12（证据就在手里）通过分布单调**：
  `none ✓ / minimal ✓ / low ✗ / medium ✗ / high ✗ / xhigh ✗`
  —— 越低档越肯用现成证据；越高档越爱怀疑"证据不足"转而拒答。
- **`xhigh` ≈ `high`**：同样 0/3、同样 ~65s、拒答措辞几乎一致 ⇒
  基本可判定端点把 `xhigh` 钳到了 `high`，不是独立更高档。
- **`none` 同时最快（25s）和最准（2/3）**。
- **rf09 六档全错**：模型对该变量名有强先验幻觉，与档位无关。

### 3.3 原始数据（`var/` 不进 git，故在此留表）

- `var/effort_ab.jsonl` — none / low / medium / high
- `var/effort_ab_xhigh.jsonl` — xhigh
- `var/effort_ab_minimal.jsonl` — minimal
- `var/effort_probe.jsonl` — 轻量探针（arith / evidence / json 三类题）
- 日志：`var/effort_ab.log`、`var/effort_ab_xhigh.log`、`var/effort_ab_minimal.log`、`var/effort_probe.log`
- 脚本：`C:/Users/41228/AppData/Local/hermes/cache/scratch/effort_ab.py`（支持 `AB_LEVELS` / `AB_OUT` 环境变量）、`effort_probe.py`

### 3.4 诚实边界

- **每格 n=1，方差大**（历史上 cl02 出现过 ✓✗✗✓）。
- "none 最好"目前是**强提示**，不是统计结论；但通过率单调 2→1→1→0、
  耗时单调 25→40→50→65s，方向一致。
- 轻量探针（放开 max_tokens 后）：算术题六档全对；JSON 格式六档全合法；
  证据题只有 `medium` 给出精确单词答案（n=1）。

---

## 四、当前配置（已还原）

```json
{
  "base_url": "https://www.mcgrox.top/v1",
  "model": "deepseek-v4.1-flash",
  "timeout": 120,
  "max_tokens": 4096,
  "reasoning_effort": "low"
}
```

> 实验期间曾临时改为 `max_tokens=65536`，脚本 `finally` 已自动还原，
> 已核验为 4096 / low。

---

## 五、运行时状态（重启前）

| 项 | 值 |
|---|---|
| agent 进程 | **未运行**（心跳 `var/dwc_agent_heartbeat.json` 停在 10:57:20，pid 36460 已不在） |
| bench | 无运行中任务 |
| 后台实验 | 全部结束 |

**gateway 重启后需要做的第一件事：拉起 agent。**

```bash
cd "E:/Divine Wisdom Core"
PYTHONIOENCODING=utf-8 "C:/Users/41228/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe" \
  "C:/Users/41228/AppData/Local/hermes/cache/scratch/restart_agent.py"
```

> 注意：**不要**在删 `__pycache__` 的同时重启（08:38/08:52 两次
> `ModuleNotFoundError: dwc.agent_quality`，干净重启即消失）。

---

## 六、待决事项（重启后续接点）

1. **是否把生产切到 `none`？**（推荐）
   - 改动：`config/llm.json` 的 `reasoning_effort` 一行
   - 验证：跑一次全池，对比 87.0%；掉分就退回 `low`
   - 预期：rf12 可过 ⇒ read-fact 12→13，总 47→48（88.9%），耗时降 40%

2. **是否放开 `max_tokens`？**
   - 数据显示 `none` 档 completion tokens 只有 96–341，4096 完全够用
   - 只有 `high`/`xhigh` 会打满预算（因此返回空答案）
   - 建议：**保持 4096**，除非切到高档位

3. **剩余弱项**：run-verify 8/10、historical 1/2 尚未深挖；`rf09` 六档全错，
   需要判据层硬拦（当前 `_r302_strikes < 2` 两次后就放行）。

---

## 七、复现命令

```bash
# 全量测试
cd "E:/Divine Wisdom Core"
PYTHONIOENCODING=utf-8 "C:/Users/41228/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe" \
  -m pytest tests/ -q --no-header -p no:cacheprovider

# 全池评测
PYTHONIOENCODING=utf-8 "C:/Users/41228/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe" \
  scripts/dwc_nightbench.py --all --wait-min 8 --no-saturate

# 单档 A/B 复测
AB_LEVELS="none" AB_OUT="effort_ab_none.jsonl" \
PYTHONIOENCODING=utf-8 "C:/Users/41228/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe" \
  "C:/Users/41228/AppData/Local/hermes/cache/scratch/effort_ab.py"
```
