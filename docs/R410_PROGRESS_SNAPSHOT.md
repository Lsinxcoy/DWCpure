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

### 2.1 R411 · 生产切 `none` 后的全池复测（2026-10-21 15:52）

配置改为 `reasoning_effort=none`（其余不变）后跑全池：
`var/nightbench_r411.log` — **47/54 = 87.0%**，**总通过数持平**，但构成变化：

| 类别 | `none` (R411) | `low` (R410) | 变化 |
|---|---|---|---|
| read-fact | 12/14 | 12/14 | — |
| code-locate | 9/10 | 9/10 | — |
| **run-verify** | **7/10** | 8/10 | **−1** |
| **analyze** | **10/10** | 9/10 | **+1** |
| write | 8/8 | 8/8 | — |
| historical | 1/2 | 1/2 | — |
| **总计** | **47/54** | 47/54 | **0** |

逐单变化（净 0）：

- **`rf12` ✗ → ✓**：TUI 主题名，`none` 3 轮直接摘出 `deep`（A/B 预测命中）
- **`an03` ✗ → ✓**：arXiv 编号，`none` 反而给全了
- **`rf08` ✓ → ✗**：修订保留键答成 `prev`（正确是 `_rev_prev`）—— `none` 不够严谨
- **`rv08` ✓ → ✗**：没执行 `git log -1`（`none` 更少主动跑命令）

**结论：`none` 与 `low` 在总数上是平手（47/54），差异在噪声范围内；
唯一稳健差异是速度 —— 全池 70 分钟 vs 约 90 分钟（快约 22%）。**

> 诚实边界：两次都是 n=1。单次 ±2 单的构成变化不足以证明任一档位更优。
> 若要定论，需每档重复 3 次取均值。

### 2.2 R412 诊断 · run-verify 3 单失败**全是判据/策略误判，不是模型问题**

（2026-10-21 15:59，只做了取证，**代码未改**）

原始报告：`var/dwc_reports/nb_1021_151839_28.json`（rv06）、
`nb_1021_151949_29.json`（rv07）、`nb_1021_152159_30.json`（rv08）。

| 单 | agent 实际做了什么 | 判据要求 | 结论 |
|---|---|---|---|
| **rv06** | `python -c "import os;print(sum(1 for r,_,fs in os.walk('src/dwc') for f in fs if f.endswith('.py')))"` → 输出 `98` | 另一条 `python -c "...print('PYFILES',n)"` → 也是 `98` | **答案正确、取证真实**，仅命令串不同 ⇒ 判据误判 |
| **rv07** | `read scripts/gate.py` 成功（981 行），随后 3 次 `run python scripts/gate.py` **全部 `R5_blocked`** | `python scripts/gate.py` 输出含"全部通过" | **产品 bug**：任务被误判为 qa_mode ⇒ 只读闸拦掉了任务本身要求的执行 |
| **rv08** | `git log -1` → `182d5d6e…`（当时正确） | `git log -1 --format=%h` | **答案正确、取证真实**，仅命令形式不同 ⇒ 判据误判 |

**rv07 根因链（已定位到行）：**

1. `step_judge.py:68` `_QA_Q` 含 `"是否"` ⇒ 命中；
2. `step_judge.py:69` `_QA_X` = `("执行","跑","修","查","写","落盘","搜","读","改","删","建","起草","试跑","重启","备份")`
   —— **没有 `"运行"`** ⇒ 任务「**运行**门禁脚本…报告**是否**全部通过」被判 `qa_mode=True`
   （实测：`is_qa_task(rv07)=True`，rv06/rv08 均为 False）；
3. `step_judge.py:58` `_READONLY_BREAKERS` 含 `"python"` ⇒ qa_mode 下
   `run(['python','scripts/gate.py'])` 被 `_is_readonly_run` 判非只读 ⇒ `R5_blocked`。

**rv06 / rv08 根因**：`scripts/dwc_bench2.py` 的 `rc_and_contains` 只认
**命令串精确匹配**（R397 的"等价方法不算证据"）。但这两单 agent 的答案
**来自它自己跑出来的输出**，不是猜的 —— 判据把"真取证"和"猜对了"一起判死了。

**待落地的修法（尚未实施）：**

- **R412**：`_QA_X` 补 `"运行"`（以及 `"启动"/"调用"/"统计"/"输出"` 等执行动词），
  让「运行脚本…」不再进 qa_mode。★ 需配回归测试：rv06/rv07/rv08 三类句式
  必须 `is_qa_task=False`，而真问答句（"…是什么/叫什么"）仍为 True。
- **R413**：`rc_and_contains` 在精确匹配失败后，增加**证据等价**判据 ——
  agent 的**成功 run 输出**里出现了最终答案（归一化后），即视为取证成立。
  这仍能挡住"没跑就猜"（猜的人输出里没有答案），但不再误杀等价命令。
  ★ 需补反面测试：零动作 + 答案正确 ⇒ 仍然判失败。
- **rv07 的第二层**：`python <仓库内 .py 脚本>` 是否该放行只读闸，
  需要单独决策（gate.py 可能写报告文件，不宜无脑放行）。

> 注意：以上是**诊断结论**，代码一行未改；下一步按 R412 → R413 → 重跑全池。

---

### 2.3 R412/R413/R414 落地 + R415 全池（2026-10-21 20:56）

**结果：bench 自记 49/54 = 90.7%；用修好的判据离线复算 50/54 = 92.6%。**

| 类别 | R415 | R411 | 变化 |
|---|---|---|---|
| write | **8/8 = 100%** | 8/8 | — |
| read-fact | **13/14 = 93%** | 12/14 | **+1**（rf12 稳定 ✓） |
| code-locate | 9/10 = 90% | 9/10 | — |
| run-verify | **9/10 = 90%** | 7/10 | **+2**（rv06/rv08 修好） |
| analyze | 9/10 = 90% | 10/10 | −1（an03 只找到 2/3 篇） |
| historical | 1/2 = 50% | 1/2 | — |
| **合计** | **50/54 = 92.6%** | 47/54 = 87.0% | **+5.6pt** |

三个提交：

| 提交 | 内容 |
|---|---|
| `e2d436c` | R412 `_QA_X` 补「运行/启动」；R413 证据等价；G7 静默门 |
| `5aae4a6` | **R414 派发即登记 running** —— 修「同一单被派发 1080 次」 |
| `6aa355e` | R413-b 解释器路径不参与匹配 + 锚点相关性 |

**R414 是本轮最严重的问题**（不是模型问题，是并发缺陷）：
`running:` 标记写在信号量内部 ⇒ 槽位占满时新线程永远走不到登记
⇒ 轮询每 3s 重投同一单 ⇒ 任务 42 被派发 **1080 次**、线程无限堆积
⇒ 后续 6 单全部 timeout。修法：派发点同步登记 + 进程内在飞集合。

**R415 剩余 4 个真失败**（R416 复核后：**2 个是坏题/窄判据，2 个是真能力问题**）：

| 单 | 现象 | 复核结论 |
|---|---|---|
| `rf09` | 编造不存在的 `DWC_*` 变量名 | **真能力**（六档 reasoning 全错） |
| `cl08` | 搜到 `cli_main.py:78` 仍坚持 `task_router.py` | **真幻觉** |
| `an03` | 三篇 arXiv 只找到两篇 | **坏题** —— 目录现有 54 篇，前提失效 |
| `hs01` | 答案不含任何期望关键词 | **判据过窄** —— 答案正确，缺「探索/导航」 |

R416 修正后（`aa39c9e`）：
- `an03` 改为「最新深读的三篇（按编号最大）」→ 复跑 **✓ 6 轮**
- `hs01` 判据补 `探索/导航/世界树` → 复跑 **✓ 2 轮**

**修正后口径：52/54 = 96.3%**（剩余 `rf09` / `cl08` 为真模型能力问题）。

**演进轨迹**：79.6% → 81.5% → 85.2% → 87.0% → 92.6% → **96.3%**（修正坏题后）

> ★ 诚实说明：49 vs 50 的差就是 rv07。跑池的进程加载的是旧判据，
> 它把"用绝对路径 python 跑 gate.py"判成零证据；`6aa355e` 修好后
> 用同一份报告复算为 ✓。两个数字都列出，不取好看的。



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

## 五、运行时状态（2026-10-21 21:00）

| 项 | 值 |
|---|---|
| HEAD | `6aa355e`（R413-b） |
| agent 进程 | **运行中**，pid 9940（19:41:49 启动，`--llm --interval 20`） |
| `reasoning_effort` | **`none`**（R411 起生效；`max_tokens` 仍 4096） |
| bench | R415 已结束（49/54 自记，50/54 复算） |
| 工作区 | 仅 `archive/gate_trace.jsonl` 运行时改动 |

**gateway 重启后需要做的第一件事：确认 agent 是否还活着。**

```bash
cd "E:/Divine Wisdom Core"
PYTHONIOENCODING=utf-8 "C:/Users/41228/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe" -c "
import psutil
for p in psutil.process_iter(['pid','cmdline']):
    cl=[str(x) for x in (p.info.get('cmdline') or [])]
    if '-c' in cl: continue
    if any(x.endswith('dwc_agent.py') for x in cl): print('agent', p.pid)
"
```

若不在：

```bash
PYTHONIOENCODING=utf-8 "C:/Users/41228/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe" \
  "C:/Users/41228/AppData/Local/hermes/cache/scratch/restart_agent.py"
```

> 注意：**不要**在删 `__pycache__` 的同时重启（08:38/08:52 两次
> `ModuleNotFoundError: dwc.agent_quality`，干净重启即消失）。

---

## 六、待决事项

**R412 / R413 / R414 / R413-b / R416 已全部落地并复测（修正坏题后 52/54 = 96.3%）。**

剩余 2 单，都是**真模型能力**，判据已复核无误：

| 单 | 现象 | 性质 |
|---|---|---|
| `rf09` | 编造不存在的 `DWC_*` 变量名 | 六档 reasoning 全错，模型上限 |
| `cl08` | 搜到 `cli_main.py:78` 仍答 `task_router.py` | 幻觉，需更强反幻觉闸 |

**下一步候选（按性价比）：**

1. **`cl08` 反幻觉闸**：R407 只拦"标识符零取证"，拦不住"有证据仍坚持
   不存在的文件名"。可加：答案里的文件名若在仓库中**不存在**，强制打回。
2. **跑一轮官方全池**：当前 52/54 是"50/54 复算 + 2 单单独复跑"拼出来的，
   不是同一次运行；要对外口径就重跑一轮。
3. **`rf09` 六档全错**：属模型能力，除非换模型，否则不动。
4. **任务级超时**（R414 遗留）：单任务跑太久会占满 2 个并发槽；
   目前不会雪崩（不再重投），但会拖慢整轮。建议加 per-task deadline。

**次要事项（暂缓）：**

- `reasoning_effort` 定论需每档重复 3 次（当前 n=1）。
- 两个坏 cron：`3c630a7186a1`（nightbench 3600s 超时）、`efda640ea187`（`No module named 'yaml'`）。
- `evidence.jsonl` 的 `_ref` 撞号风险（写入端未改，只做了读侧容错）。


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
