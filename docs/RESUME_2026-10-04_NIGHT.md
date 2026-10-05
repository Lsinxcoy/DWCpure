# RESUME · 2026-10-04 深读收尾（81 轮）

> **用途**：跨会话续接。开工先读本文件，再读 `ARCHITECTURE.md`。
> **状态**：架构设计阶段（**未写承重代码**，`src/` 为空）
> **前一份续接点**：`docs/RESUME_2026-10-04_EARLY.md`（10-03 夜的 ARSI 审计版，保留）
> **门状态**：`python scripts/gate.py` 7 门全绿 rc=0

---

## 一、这一轮做完了什么

```text
核心论文《Recursive Self-Improvement in AI: A Survey》(2609.2680) **全文 2,330 行逐行读完**
  32 作者 / 404 篇 / 正文 54 小节 / 26 轮反刍深读
+ 补读 28 篇全文（1,698 页 / 6.1 MB），其中 **12 篇逐行精读**
⇒ §9 第 25 项: 13 → **69 条子缺口** (a)-(cq)
⇒ ARCHITECTURE.md: 45,835 → **78,305 字节**

新增 7 份报告 (docs/papers/):
  2609.2680.md                74,318 B  核心论文
  2607.07663.md               11,552 B  RSI 综述（对头，1250 篇）· 验证层级四层
  2505.22954.md                9,652 B  DGM (ICLR 2026) · Table 1 消融
  2603.19461.md               10,518 B  HyperAgents · imp@k
  2603.25681.md               25,160 B  TMLR 自改进展望 · §2/3/6/7/8 全部
  MEMORY_EVOLUTION_SURVEYS.md 21,092 B  3 篇（记忆机制 / 自进化 / 终身学习）
  SELF_EVOLVING_SURVEYS.md     26,220 B  3 篇（A_t 三元 + §10 五条 + TMLR 四轴）
汇总: docs/DEEP_READ_REPORT_2026-10-04.md  25,947 B
全文归档: papers_txt/refs/  28 篇 PDF+txt
```

---

## 二、★ 深读解出的九条决定性结论

```text
① 收益来源排序被推翻
   DGM Table 1: 归档非贪心 **+27.0pp** ≫ 改自己代码 **+11.0pp**
   ⇒ 世界树/归档是进化核心**第一优先**，不是附属存储
   ★★ 但 (bc) 警告: 同预算下"进化 harness"已有**负面结果**
     (Terminal-Bench 2.1)，DWC 域必须重验，不可外推

② 归因的正确做法是"冻结身份"
   imp@k 靠 **冻结 meta agent 身份** 实现 I_0 ⇒ 与第 20 项同源同解

③ A_t = (S_t, H_t, θ_t) 三元【2608.03392 式(7)(8)(9)】
   S_t=(memory,skills,tools,context) · H_t=(harness,workflow,multi-agent org)
   θ_t=参数化策略 ★ DWC 固定
   ⇒ (e) 两层补丁的可判定实现（声明 target_layer + target_component）
   ★★ 第 20 项的根源 = **跨层自评**（θ 层自算 confidence 去评 H 层）

④ self-directed selection 是被点名的空白【2603.25681 §3.3.3】
   "**No existing method** ... has the main model curate its own training data
    **without an external selector**"（并称其为 strongest form of autonomy）
   ★★ 但同篇理论断言: 自选数据在自主设定下**不可解**（intractable）

⑤ coupled 风险**三源一致** ⇒ 第 20 项不是"文献不支持"，是公认风险
   ① 2603.25681 §3.3.3（14 个方法中 9 个 coupled，是主流）
   ② 2608.03392 §10.2（自评分数可近满分而真实性能不升反降，六模型外部审计都更好）
   ③ 2603.25681 §6.4.2（LLM 生成/评判评估实例 ⇒ evaluator coupled to 被测模型）

⑥ ★★★ 门是可腐化的 —— 对 iron_laws 最根本的限制声明
   "**these gates are corruptible** because models can **sandbag the tests** while
    keeping deployment performance"
   "An evaluation that reads as safe therefore **cannot certify** that the
    self-improvement system is actually safe"
   ⇒ ★★★ 铁律必须显式承认"门可被腐化"

⑦ ★★ 观察窗是推理【2603.25681 §6.4.3】
   "Its **observation window is inference** ... **how inference is configured
    determines what evaluation sees**"
   ⇒ 任何验收必须同时报 test-time 配置（评估三声明）

⑧ ★★★ 断路器不修激励
   "a circuit breaker **stops a crash without fixing the incentives** that produce it"
   ⇒ DWC 的门若只"拒绝候选"，就是断路器 ⇒ 必须同时改产生候选的机制

⑨ ★★ 自主性定位【2404.14387 式(8)(9)(10)】
   Low: M̃=Evol_L(M,E,f•,ENV)  ← "Most of the current works lie at this level"
   Med: M̃=Evol_M(M,E,ENV)      ← ★★ **DWC 现在在这里**
   High:M̃=Evol_H(M,ENV)        ← 需 ① E 自己会变 ② 模型自诊断
   ⇒ 与缺口 (g) 目标演化双记是同一件事，裁决时一起
```

---

## 三、§9 六十九条的可结案度

```text
★★★★★ 已有实测/公式答案，约 40 条可直接落进定稿
  (a)(b) imp@k / Γ_t              (c) FGT 保护组回归约束
  (d) 四干预点可单独冻结          (e) A_t 三元 + patch_target
  (f) 无新反馈对照 + 55% 目标数字   (g) 目标演化双记
  (h) 三类漂移(粗) + 16 子项(细)  (i) FGT/BWT/FWT + 恢复三量
  (j) 三类度量不可互换            (k) 后代评估预算归属
  (l) 三描述符                   (m) 分析单位 = 配置
  (n) imp@k 隔离 = 冻结身份        (o) CI 规则
  (p) DGM Table 1 优先级          (q) 阶梯评测协议
  (r) 同域对齐对 DWC 不成立       (s) 格式不符类失败签名
  (t) 验证层级四层               (u) 55% 基线
  (v) 归档消费方式 > 是否剪枝     (w) 新颖性 + 重试上限
  (x) r_propose = 1 - r̄_solve    (y) Pareto 前沿路线
  (z) judge 三条失效 + 方差选样    (aa) m/task agent 可合并
  (bm) A_t 三元                  (bn) 轨迹视图 + 成本
  (bo) 评估五维                  (bp) Persistence 边界
  (by) 观察窗 = 推理              (bz) 评估是闭环触发器
  (ca) 评估器耦合                (cb) 环境噪声 vs 模型失败
  (cc) AI4AI-Bench / RSI-Exam     (cd) DyCodeEval 刷新法
  (ce)(cf) 过程判据 / 记忆安全    (ci) 门可腐化
  (cj) 止损不修根三模式          (ck) L3 必须异源
  (cl) 记忆是攻击面              (cm) 幻觉护栏/真护栏被删两面
  (cn) 依赖幻觉包名              (co) 责任缺口
  (cp) 审计现实 + 25% 基线        (cq) 欺骗性对齐已实测

★★★ 需决策取舍，约 15 条
  第 20 项（守卫① 矛盾）最终修法 —— 与 (g)(ck) 一起裁决
  (y) 世界树收束：Pareto vs 信息增益（默认 Pareto，但两条要能切换）
  记忆是否加 Working 层（2501.07278 四类 vs DWC 三区）

★★ 需继续设计，约 14 条
  第 21 项 state schema（阻塞 iron_laws 不变式验证）
  第 22 项 因果链存储形态    第 23 项 L3 退化是否可接受
  第 2 项 提案粒度           第 4 项 失败签名分类法的两层实现
```

---

## 四、下一步（建议顺序）

```text
第 1 步  裁决第 20 项（守卫① 矛盾）—— 唯一"已定原则与已定实现正面冲突"的一条
          ★ 与 (g)(ck) 一起，一张表说完：核心是"冻结身份 + 异源 L3"
第 2 步  裁决 (y) 世界树收束策略（Pareto 默认 / 信息增益保留 / 可切换）
第 3 步  把 40 条已有答案的写进 ARCHITECTURE 正文（从 §9 移到定稿章节）
第 4 步  解决第 21 项 state schema 与第 22 项 因果链存储形态
★ 前两步都是二选一形态，建议一次做完
```

---

## 五、★ 纪律状态

```text
★ src/ 仍为空 —— 架构定稿前不写承重代码。
  2026-10-03 抢跑的 4 个文件在 docs/drafts_premature_code/（未删，可回退）
  用户原话: "这就开始写代码了？我们还没有完全搞定架构啊"

★ 本轮全程只改 .md 文档 + 只读审计，**未改任何生产代码**。

★ 否定性结论一律宽口径复核 + 假阳性排除（本轮累计踩坑 4 次，已全部更正）:
  · "母巢 EventBus 0 调用" → 窄 grep 漏了，宽口径确认接线
  · "ARSI 有 2 处 publish" → "unpublished" 假阳性，宽口径 0 命中
  · "DWC 19 篇被本文引用" → AIDE/SEVerA/GAI 全是 aided/several/GAIA 假阳性
  · "记忆四分类在 2404.13501" → 实为 2501.07278（归属已在报告中正确标注）
★ 引文核实累计约 171 处全部通过；
  断词/弯引号/大小写/下标字符造成的假阴性共 11 处已逐处定位确认
```

---

## 六、★ 诚实边界（明确未读的部分）

```text
① 2603.25681 §9-§11（Applications / Future Outlook / Conclusion）未读
   ★ 影响小：§6-§8 已覆盖 DWC 全部命题
② 2508.07407 只做结构级精读（§3-§4 骨架），未逐行 55 页
   ★ 其"记忆分短/长两层"与 DWC 三区的结论待逐行确认
③ 传统搜索基座 5 篇（Auto-WEKA / NAS-RL / MAML / 学优化器 / RL²）只读摘要+核心段
   ★ 主动取舍：方法学祖先，对 DWC 边际价值低
④ 2504.01990 Foundation Agents 396 页只读第 II 部分 §9（自进化专章）
⑤ 22 篇补读中 10 篇仍为摘要级
⑥ ★★ 2609.2680 是 NOT PEER-REVIEWED + 标注用 ChatGPT 辅助写作 + 自评偏乐观
   ★★ 但 TMLR 两篇（2507.21046 / 2603.25681）同行评审过，是本组证据等级最高的
```

---

## 七、三条最该记住的

```text
① 门通过 ≠ 系统安全（论文原话）—— 铁律设计必须承认这一点
② 门若只"拒绝候选"，就是断路器 —— 必须同时改产生候选的机制
③ 收束策略（信息增益 vs Pareto）要能声明与切换，不要二选一写死
```

---

## 八、关键文件索引

```text
E:/Divine Wisdom Core/ARCHITECTURE.md                    ★主文件 · 七器官 v4 + §9 六十九条
E:/Divine Wisdom Core/docs/DEEP_READ_REPORT_2026-10-04.md 深读总报告
E:/Divine Wisdom Core/docs/papers/*.md                   30 份逐篇报告
E:/Divine Wisdom Core/docs/RESUME_2026-10-04_EARLY.md    上一份续接点（ARSI 审计版）
E:/Divine Wisdom Core/papers_txt/2609.2680_rsi_survey.txt   核心论文纯文本（221,636 字符）
E:/Divine Wisdom Core/papers_txt/refs/                   28 篇补读全文（6.1 MB）
E:/Divine Wisdom Core/scripts/gate.py                    7 门（当前全绿 rc=0）

外部参照（只读，不改）:
  E:/ARSI/                  ARSI 真实骨架
  E:/SYNTHEX Autopoiesis/   母巢（当前离线，按铁律不手动重启）
```

---

*续接点 · 2026-10-04 · 深读 81 轮 · §9 六十九条 · 门全绿 rc=0*