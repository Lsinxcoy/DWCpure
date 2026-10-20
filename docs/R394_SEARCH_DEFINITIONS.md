R394 · search_code 定义置顶（grep 把 def 埋在几十行引用里）

═══ 现场（2026-10-20 20:19 全池）═══
cl01「execute_user_task 定义在哪个文件」被判 incomplete：

    复读熔断: 连续 3 轮同动作同结果
    （run / ['grep','-rn','--include=*.py','--exclude-dir=.git',…]）

动作日志：**第 1 轮 grep ok=True，之后 3 轮全 ok=False**。

═══ 根因 ═══
`grep -rn <symbol> src` 返回的是**所有引用**（几十行）——
定义行 `def execute_user_task` 被埋在几十个调用点中间。
模型读不出"哪个是定义"，只好换个词再搜，越搜越窄 ⇒ 最后搜不到 ⇒ 熔断。

═══ 修法 ═══
`search_code` 改 Python 实现，输出分两段：

    === DEFINITIONS (1) ===
    src\dwc\llm\task_exec.py:1076:def execute_user_task(task: str, *, llm: Any, ...
    === REFERENCES (6) ===
    src\dwc\llm\step_judge.py:43:#: 现场：cl01「execute_user_task 定义在哪个文件？」...

· 定义（def/class <pattern>）**置顶**，最多 20 行
· 引用**限流** 30 行（高频词不再淹没上下文）
· 搜不到时明确输出 `DEFINITIONS (0)` / `REFERENCES (0)`（不是空串）

实测：
    execute_user_task → 1 条定义（task_exec.py:1076）
    MemoryKernel      → 1 条定义（memory.py:223）

═══ 验证 ═══
· TDD：R394（7 条）—— 定义置顶/class 识别/顺序/限流/无命中信号/readonly/非 grep
· 重锚 `test_r384_native_tools::test_search_code_tool_exists`
  （原断言"必须是 grep" ⇒ 改为"搜索真能命中定义"）
· 定向：R394 + R393 + R391 + R386 = 44 passed

═══ 诚实边界 ═══
1. 只扫 `.py` 文件（其它语言/配置文件不覆盖）。
2. `def/class` 前缀匹配依赖缩进正则；装饰器行不算定义。
3. 全池效果待测（R394 只在单点验证过）。
