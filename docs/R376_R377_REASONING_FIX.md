R376+R377 · 修「一直反馈 DWC 任务未完成」

指令：「一直反馈dwc任务未完成」

════════════════════════════════════════════════════════════
一、谁在报（先定位，不猜）
════════════════════════════════════════════════════════════
· 推送源：`scripts/dwc_agent.py:433-435` 的 `_feishu_notify`，按
  `rep["status"] == "done"` 二分：✅完成 / ⚠️未完成。
· 触发者：**nightbench 每日 02:30 无人跑批**（cron `3c630a7186a1`），
  投 8 单 + 加练，每单一个 term。
· 现场：2026-10-20 02:35–04:11 共 10 单，**9 单 incomplete**。
· 另两个 cron 也在报错（本轮顺带定位，未修）：
  - `efda640ea187` DWC bench daily → `ModuleNotFoundError: No module named 'yaml'`
  - `3c630a7186a1` nightbench → `Script timed out after 3600s`

════════════════════════════════════════════════════════════
二、根因（三层，逐层实测，不是猜）
════════════════════════════════════════════════════════════
9 单的 `why` 全是同一句：
  `LLM 响应非 JSON（容错提取后仍失败）: We need answer task: ...`

① 端点层 —— **正常**
   原始 HTTP 里 `content` 与 `reasoning_content` 是分离的两个键，
   `content` 是干净 JSON。

② 模型层 —— **正常但吃预算**
   `deepseek-v4.1-flash` 是推理模型。同一长 prompt 只改 max_tokens：
     max_tokens=300  → finish=length, content_len=0,   reasoning_len=1039
     max_tokens=1600 → finish=stop,   content_len=121, reasoning_len=1193
     max_tokens=4000 → finish=stop,   content_len=103, reasoning_len=1822
   ⇒ 推理把预算吃光时 `content` 一个字都没有。

③ **客户端层 —— 真 bug（两处）**
   a. `client.py:392-396`：content 空时用 `reasoning_content` 顶替正文，
      返回 **ok=True**。下游 `_extract_json` 拿到英文推理散文 ⇒ 判
      「非 JSON」⇒ 报「任务未完成」，而**真正的失败原因（token 耗尽）
      被彻底掩盖**。
   b. `client.py:496-497`（流式）：`if not piece: piece =
      delta.get("reasoning_content")` —— 把推理 delta 直接拼进正文。
   ⇒ 这就是「降级与成功不可区分」，本项目明令禁止。

④ **配置层 —— 真 bug（静默丢弃）**
   `_load_file_config()` 的白名单只有 4 个键
   （base_url/api_key/model/timeout）。往 `config/llm.json` 写
   `max_tokens` / `reasoning_effort` 会被**静默丢弃** —— 排障时看到的是
   「配了没用」而不是「没配」，最坏的一种静默。

⑤ **硬编码 —— 真 bug**
   `task_exec.py:844/848` 两处 `max_tokens=1600` 写死，与 client 的
   「显式 > env > 文件」口径完全脱节 ⇒ 换模型/端点无法调参。

════════════════════════════════════════════════════════════
三、修法（分两层：先如实报，再真修好）
════════════════════════════════════════════════════════════
【R376 · 诚实层】不许拿推理冒充答案
· `complete()`：content 空 + reasoning 有 ⇒ `ok=False`,
  `meta.kind="reasoning_only"`，透出 `finish_reason` / `reasoning_chars` /
  `content_chars`；错误文案直接说「多半是 max_tokens 被推理吃光」。
· `complete_stream()`：推理 delta **不拼进正文**、不推给 `on_delta`；
  只有推理无正文 ⇒ 同上 `reasoning_only`。
· 两条路径都透出 `meta["finish_reason"]`（排障一眼看出 length）。
· `content` 有内容时行为**完全不变**（回归保护测试锁）。

【R377 · 根因层】让推理别再吃光预算
· `LLMClient` 新增 `max_tokens`（默认 4096，原 1600）与
  `reasoning_effort`，口径与 timeout 一致：**显式 > env > 文件 > 工厂**。
· 新增 env：`DWC_LLM_MAX_TOKENS` / `DWC_LLM_REASONING_EFFORT`。
· `_load_file_config()` 白名单补两键（防再次静默丢弃）。
· 配了才发 `reasoning_effort`，**未配不发**（不猜端点支持什么）。
· `task_exec.py` 删掉两处 `max_tokens=1600`，改从 client 取。
· `config/llm.json` 落地：`max_tokens=4096`、`reasoning_effort="none"`。

为什么 `reasoning_effort="none"` 是对的（实测依据）：
  同一 rf04 任务，只改参数：
    无额外字段                → finish=length, content=0, reasoning=13779
    reasoning_effort=none     → finish=stop,   content=2, reasoning=0
    thinking={type:disabled}  → finish=stop,   content=2, reasoning=0
  端点支持压制推理，压制后 content 直接是答案。DWC 的任务执行体要的是
  「一个紧凑 JSON」，不需要 13000 字的内心独白。

════════════════════════════════════════════════════════════
四、验证（真跑，不是推理）
════════════════════════════════════════════════════════════
· TDD：先写 RED。r376 9 条 → 6 failed（原因正确）；r377 10 条 → 8 failed。
· 修后定向：r376+r377+r237+r226 = **28 passed**。
· **真实任务复现（rf01-rf06，同一 52 任务池）**：
    修复前：2/6 成功（rf04/rf05 等 reasoning_only / 非 JSON）
    修复后：**6/6 成功**，0 条 reasoning_only
· **全 52 任务端到端**（单轮直答，探针无工具）：
    `ok=False` **0 条**，`reasoning_only` **0 条**
    （修复前约 90% 失败）
    通过率 3/52 —— 但这是**探针不给工具**造成的假象（read-fact 类任务
    需要真读文件），**不是任务真实通过率**，不作为结论。
· 全量 pytest：**2293 passed / 0 failed / EXIT=0**（252.51s）。
· gate：**8/8 全通过**。
· 生产：agent 重启（pid 28908, use_llm=true, interval=600）；
  首个 term `code_fix_001` pass=0.78、`sigs=2`（真燃料恢复产出）。

════════════════════════════════════════════════════════════
五、旧锁重锚（不删除，按新语义 + 补更强断言）
════════════════════════════════════════════════════════════
`tests/test_r327_reasoning_key.py::test_r327_reasoning_fallback`
· 旧断言：`r.ok and r.text == "RS-DRAFT"` —— 锁的是「推理冒充答案」。
· 新断言：`ok is False` + `kind=="reasoning_only"` +
  `finish_reason=="length"` + `reasoning_chars==9` + `"推理" in error`。
· 理由写进 docstring：R327 当时的做法在生产上被证伪（10 单 9 挂）。

顺带：`test_no_watering` 抓到我自己写的恒真放水断言
（`assert "max_tokens" in C._load_file_config.__doc__ or True`）——
项目自带的防水门当场发现，已改成 `assert isinstance(got, dict)`。
这条值得记：**放水断言是会被机器抓的**。

════════════════════════════════════════════════════════════
六、诚实边界
════════════════════════════════════════════════════════════
1. **nightbench 的 3600s 超时未修**（cron `3c630a7186a1`）。
   本轮只修了它失败的**根因**（LLM 调用），跑批本身仍可能超时。
2. **`dwc_bench_cron.py` 的 `ModuleNotFoundError: yaml` 未修**
   （cron `efda640ea187`）—— 是 cron 执行环境的 sys.path 问题，
   与本次 LLM 故障无关。
3. **52 任务真实通过率未测**：探针没给工具，3/52 无意义。
   要真值需跑 `dwc_nightbench.py` 全链路。
4. `reasoning_effort="none"` 的代价：模型不再「先想再答」，
   复杂推理类任务质量可能下降。当前 DWC 任务是「查一个事实 / 定位
   一个符号」，不需要长推理，所以这个取舍成立。若将来换成长推理任务，
   应改成 `"low"` 或按任务类型分流。
5. 只有 `deepseek-v4.1-flash` 在这个端点实测过 `reasoning_effort`；
   换端点若返回 400，说明不支持该字段 —— 那时删配置即可（未配就不发）。
