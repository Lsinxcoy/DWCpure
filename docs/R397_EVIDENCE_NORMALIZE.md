R397 · run-verify 证据匹配误判（字符串命令 vs argv 列表）

═══ 现场（2026-10-20 22:15 全池，R396 后）═══
run-verify 有 3 单被判 `no-agent-evidence`，但 agent 其实跑了：

    判据 cmd:   python -c "import os;n=sum(...)"
    agent cmd:  ['python', '-c', 'import os;n=sum(...)']
    JSON 形态:  ["python", "-c", "import os;n=sum(...)"]

═══ 根因 ═══
R388 的 `_agent_ran()` 用 **needle 子串匹配**：

    needle = cmd.strip()[:40]          # 含空格和引号
    if needle in blob: ...             # blob 是 argv 的 JSON

`python -c "import os;...`（带引号+空格）永远不可能出现在
`["python", "-c", "import os;..."]` 里 ⇒ **3 单误判为"未执行"**。

═══ 修法 ═══
两边都归一化后再比：去掉所有非字母数字/非中文的字符

    _norm('python -c "import os;n=sum(1 for _,_,fs') → pythoncimportosnsum1forfs
    _norm('["python", "-c", "import os;n=sum(1 for _,_,fs') → pythoncimportosnsum1forfs...

⇒ 前缀命中。

═══ 验证 ═══
· TDD：新增 2 条
  - argv 列表 vs 字符串命令 ⇒ 必须匹配上（rv06/rv07/rv08 的现场）
  - 归一化不能变成"什么都能匹配"（跑的是别的命令仍 ✗）
· 用修正后的判据**重算本轮全池**：run-verify **7/10 → 8/10**
  （rv08 恢复；rv06/rv07 是真没跑指定命令，判 ✗ 正确）
· 全量 pytest：**2479 passed / 0 failed / EXIT=0**（283.55s）

═══ 诚实边界 ═══
1. 归一化是**字符级**的：`print(1)` 与 `print 1` 会被视为相同
   （命令语义上确实等价，可接受）。
2. 仍要求"跑了**同一条**命令"：agent 用等价方法验证（如用
   `glob.glob` 代替 `os.walk` 数文件）**不算证据** —— 这是有意的
   严格：run-verify 考的是"按指定方式验证"，不是"碰巧答对"。
3. rv06/rv07 因此仍是 ✗（agent 换方法 / 没跑）。
