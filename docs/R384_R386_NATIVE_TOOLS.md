R384–R386 · 原生 tool calling（全池零动作 94% → 0%）

════════════════════════════════════════════════════════════
一、起点：全池 52 单跑出来的假数字
════════════════════════════════════════════════════════════
`dwc_nightbench.py --all --no-saturate` 报 **28/54 = 51.9%**，
但 **51/54 = 94% 的报告 `actions_log` 为空** —— agent 全程没调过工具。

通过的全是"不需要工具"的：
  historical 100%（纯概念题）/ read-fact 71%（事实题可以猜）
  run-verify 90%（判据 `rc_and_contains` **自己重跑 pytest**，agent 不做事也能过）

写类只有 1/8 = 12%，而且 5 单报"旧文件"——模型在 answer 里写
「已写入 `var/inbox_work/list.md`」而文件根本没写（R383 已修）。

════════════════════════════════════════════════════════════
二、双重根因
════════════════════════════════════════════════════════════
① `task_exec` 用**手工拼 JSON 提示词**（`llm.complete(prompt,
   json_mode=True)`），逼模型在散文里输出 `{"op":"read",...}`。
   模型不照做 ⇒ 输出纯文本/XML（`<read path="..."/>`）。

② **更致命**：即使模型想调工具，client 也把它扔了 —— 端点返回
   `tool_calls` 时 `msg["content"]` 是**空串**，而 `complete()` 里
   `if not text.strip()` 直接判 `kind="empty"` ⇒ **tool_calls 被当空响应丢弃**。

实测端点原生 tool calling 完全正常：
    finish=tool_calls  tool_calls=1
      → read_file {"path": "src/dwc/llm/task_exec.py"}

════════════════════════════════════════════════════════════
三、R384 · 原生 tool calling 接线
════════════════════════════════════════════════════════════
· `client.complete(tools=, tool_choice=)` —— 进请求体；不传则无该键（老调用方不变）
· **响应含 `tool_calls` ⇒ `ok=True` 且 `meta["tool_calls"]` 透出**
  （在"空内容判死"**之前**拦下 —— 这是 94% 零动作的致命一环）
· 重试路径也透传 `tools`（否则重试后丢工具）
· `TASK_TOOLS` = read_file / write_file / run_command / list_dir /
  search_code / final_answer
· `_tool_calls_to_step()` 只做**转换**，复用既有 op 白名单/沙箱/审计
· 原生模式走非流式（tool_calls 需整段解析），JSON 路径保持流式
· 不支持 tools 的端点/provider ⇒ **诚实回退**，报告记 `tool_mode`

════════════════════════════════════════════════════════════
四、R385 · 死循环防护（rf01 实测 140 轮 / 625 秒）
════════════════════════════════════════════════════════════
现场：rf01「PowerShell TrimStart 字符码」在 `max_rounds=999` 下跑
**140 轮 / 278 动作 / 625 秒**，最后 answer 为空、判 ✗；
同批 rf02 只要 2 轮 6.5 秒。

修：
· `NATIVE_TOOLS_MAX_ROUNDS = 15`（原生模式硬上限，不再用 999）
· `NATIVE_TOOLS_REPEAT_LIMIT = 4`：同一 (op,target) 重复 4 次 ⇒ 强制 final
· 强制指令**追加**而不是覆盖 prompt（qa 的取证上限提示要保留，
  覆盖会让两套收敛信号互相抵消 —— test_r301f 抓到过）
· 到上限仍无答案 ⇒ `incomplete`（不许假装 done）

════════════════════════════════════════════════════════════
五、R384-fix · 三个"工具明明能用却用不了"的坑
════════════════════════════════════════════════════════════
① `run` op 要求 **argv 列表**，而 `run_command(cmd: string)` 传字符串
   ⇒ 所有命令 `ok: False`（an01 的 `ls -la` 连挂两次）。
   修：`_argv_of()` 用 shlex 拆。

② **`shlex.split(posix=False)` 在 Windows 上保留引号** ⇒ grep 收到
   `'"def execute_user_task"'`（带字面引号）⇒ 永远搜不到。
   修：search_code/list_dir **直接构造 argv 列表**，不走字符串。

③ **`qa_mode` 把只读命令也拦了**（R301-D 硬约束只许
   read/ask/web_read）⇒ `search_code` 转成的 `run(grep)` 每轮被 R5
   拦（`target: "R5_blocked"` ×4）⇒ cl01 答"未能确认定义文件"。
   而 grep 一行就能定位。**拦 grep 等于把"查证"本身禁了。**
   修（R386）：`READONLY_CMDS` 白名单（grep/ls/find/cat/head/tail/
   wc/stat/tree…）+ `_READONLY_BREAKERS`（禁 `>`/`|`/`rm`/`python` 夹带）；
   qa 下只读 run 放行，改状态命令仍拦。
   另：search_code 默认搜 `src`（全仓 grep 实测 189s 超时），
   排除 .git/var/archive/node_modules/__pycache__。

════════════════════════════════════════════════════════════
六、效果（实测）
════════════════════════════════════════════════════════════
| 指标 | 修复前 | 修复后 |
|---|---|---|
| 全池零动作任务 | **51/54 = 94%** | **0/8 = 0%** |
| rf01 轮数/耗时 | 140 轮 / 625s / 空答案 | 5 轮 / 27s / **答对** |
| 写文件（真写） | 声称已写、文件不存在 | **actions=51，文件真写入** |
| cl01 定位 | R5 连拦 4 轮，答不出 | **2 轮 / 41s / 答对** |
| 平均轮数 | — | 4.5–5.8 |
| 平均耗时 | — | 22–27s |

════════════════════════════════════════════════════════════
七、验证
════════════════════════════════════════════════════════════
· TDD：R384（12 条）+ R385（5 条）+ R386（20 条），RED 全部确认
· 重锚旧测试（**改断言不删除**）：
  - `test_r237_stream::test_token_events_reach_progress` —— 流式只在
    JSON 路径；新增 `test_native_tools_mode_is_not_streaming_but_reports_rounds`
  - `test_r301_qa_loop::test_r301e_r5_blocked_no_exec` —— 改用 pip install
    测 R5；新增 `test_r386_readonly_grep_is_allowed_in_qa`
  - `test_r380` / `test_r383` —— 加 autouse fixture 显式关原生模式
    （它们锁的是 JSON 回退路径语义）
· 全量 pytest：**2396 passed / 0 failed / EXIT=0**（306.31s）

════════════════════════════════════════════════════════════
八、诚实边界
════════════════════════════════════════════════════════════
1. **全池 52 单还没用新链路重跑** —— 28/54 那个数字作废，新数字未测。
2. 8 个样本里可判任务正确率 3/6，样本太小，不能当能力基线。
3. `run-verify` 的**假通过**（判据自己重跑 pytest 给 agent 记功）**本轮未修**。
4. 写类 wr01 仍要 15 轮 / 118 秒（模型反复自证），偏慢但能完成。
5. agent 静默死因仍未查明（今天 3 次）；`dwc_watchdog.py` 只能"死了发现并拉起"。
6. 原生模式**不流式**（逐字动画没了）—— 这是为正确性做的明确取舍。
7. `_READONLY_BREAKERS` 是黑名单式防夹带，不是完备沙箱。
