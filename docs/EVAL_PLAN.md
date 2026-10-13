# DWC 短板补齐计划（R259-R261 · 2026-10-14 用户拍板"动手补齐1 2 3"）

## 总原则（深度思考定稿）

- **短板 1（效果证明度）→ R259 测量层先行**：没有基线就无法证明短板 2 补齐了。
- **短板 2（独立执行脆弱）→ R260 无人值守跑批回路**：真实流量验证 R258 修订回路本身。
- **短板 3（工具面窄）→ R261 选择性补**：只补最疼的网页抓取；浏览器自动化/MCP 生态/连接器**明确不做**（不追平 Hermes——那是别人主场）。
- 每步深度思考的结论直接写在各节"设计决策"里。

---

## R259 · 测量层（短板 1）

### 目标产出（两个可外示硬数字）

1. **真实任务成功率**（分类型分解）
2. **进化净收益** = B臂（进化开）成功率 − A臂（进化关）成功率

### 设计决策（深度思考记录）

- **任务集来源**：合成任务集从**仓库真实内容**抽事实（README/PROGRESS/代码——不凭空编）+ 已有真实事故任务（17:12/17:13）。
  - 构造偏差风险（自己出题自己考）→ **A/B 设计消除**：同一批任务两臂对比，构造偏差在两臂间相消。测量目的是 DWC 自身进化前后差，不是绝对排名。
- **验收标准 G2 纪律**：**禁止 LLM 自评成功**。每单带机器可验 check（contains/regex/rc_and_contains/file_exists_contains）。构造时每单先自测 check（对预期答案=true，对空=false）。
- **A/B 唯一变量 = 进化面**：
  - A臂：judge off（DWC_STEP_JUDGE=0）+ 无 lessons 注入（ctx=None）+ 无修订——**bench 直调 execute_user_task 天然绕过 agent 的 lessons/revision**（task_exec 不碰 memory/agent_quality）
  - B臂：judge on + lessons_context 注入 + 修订 on（R258 主路径模拟）
  - 轮数对齐（两臂同 max_rounds——防轮数混淆变量）
- **顺序依赖诚实标注**：A→B 跑；B 臂在线进化（修订发生在跑批期间=B 的真实语义"进化开着的系统"）；A 无修订不污染 B。
- **成本**：50 单 × 2 臂 × ~8 轮 ≈ 800 次 LLM 调用 ≈ 50 分钟（后台）。
- **修订质量评分**（R258 gap 一次性还清一半）：修订对 grounded 率（AEWM FActScore 式——修订内容是否忠于源教训/源证据），counterfactual 重跑留待后续（贵）。

### 交付物

- `config/eval_tasks.jsonl`（50 单，分层：read-fact 12 / run-verify 10 / code-locate 10 / analyze 10 / write 8）
- `scripts/dwc_bench2.py`（A/B 跑批 + 规则验收 + 报告）
- `scripts/score_revisions.py`（修订 grounded 率）
- `docs/EVAL_REPORT.md`（两个硬数字 + 分解 + 诚实边界）

---

## R260 · 无人值守跑批回路（短板 2）

- cron 定时从任务集抽样投单 inbox → agent 无人执行 → 失败回流 lessons/修订（R258）→ 成功率曲线 `var/eval/success_curve.jsonl` + 飞书周报。
- 任务轮换：每周换 1/3 防记忆过拟合。
- 与 R259 跑批框架复用。
- 验证目标：修订对数量/固化数/修订后任务表现（R258 回路被真实流量压测）。

## R261 · 选择性工具补（短板 3）

- **web_read op**（研究类任务最疼）：http 抓取 + html2text 轻量提取（无浏览器依赖；超时+大小限制+白名单纪律对齐 task_exec）。
- **明确不做**：浏览器自动化、MCP 生态追平、连接器。

---

## 完成判据

- [ ] R259：两个硬数字产出并推送；验收规则全机器可判（无 LLM 自评）
- [ ] R260：跑批 cron 上线 ≥1 周有成功率曲线；修订回路有真实流量数据
- [ ] R261：web_read 进 task_exec 白名单 + 测试锁；研究类任务实测可抓
