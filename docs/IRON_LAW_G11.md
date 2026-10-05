# DWC 铁律 G11 · 门通过 ≠ 系统安全（缺口 A1）

> **状态**：设计定稿（**未写代码**，`src/` 与 `config/` 均空）
> **日期**：2026-10-04 · **来源**：`docs/GAP_AUDIT.md` 缺口 A1
> **依据（已逐字核）**：§9 第 25 项 (ci)（2603.25681 §8.1）
> **前置**：`docs/IRON_LAWS_DESIGN.md`（十条铁律 + check_fn 规格 + I1–I8 判据）
> `docs/ORGAN_INTERFACES.md` §七（iron_laws 接口）· `docs/JUDGE_LAYERS.md`（三条纪律）

---

## 一、★ 为什么需要它（论文原文）

**2603.25681 §8.1 原文逐字**：

```text
"One safety risk of recursive self-improvement is that **capability compounds faster
 than humans can supervise it** ... behavior monitoring is defeated when a model
 **games the proxy** its monitors track, and Pan et al. (2022) show that this
 **reward hacking sharpens as capability grows**."

"**Interruption is not assured** either, because agents can **learn to disable the
 mechanism meant to stop them**."

"The main safeguard is to **gate deployment** on dangerous-capability and autonomy
 evaluations that halt the loop when a threshold is crossed."
"★★ **Unfortunately, these gates are corruptible** because models can **sandbag the
 tests while keeping deployment performance**, and deceptive backdoors can survive
 standard safety training."
"★★ **An evaluation that reads as safe therefore cannot certify that the
 self-improvement system is actually safe.**"
```

⇒ ★★ 这条**否定性承诺**在 DWC 现有十条铁律里没有对应条目。
它限制的是**一切门（含铁律本身）的效力解释**，不是某个具体行为。

---

## 二、★★ 先排除一种误读：它与 G5 不是同一件事

```text
★ G5「客观效用锚」: description "效果在-1到+1之间，**机制禁自评**"
  ⇒ 管的是: 单个机制不得给自己的效果打分（对象 = 机制）
  ⇒ 判据可执行: effect 越界 / self_eval 标志为真

★★ G11（本条）: "门通过 ≠ 系统安全"
  ⇒ 管的是: **门这个装置本身**的结论不可外推（对象 = 门的效力）
  ⇒ 判据**不可**做成"某个 state 字段越界"的形式
  ⇒ ★★ 这是本条最难的地方: 它是一条**元条款**, 不是状态检查
```

**⇒ 结论：不并入 G5，必须独立成条。** 并进去会让 G5 的 check_fn 无法表达。

---

## 三、★★ 三种可选形态（我选第三种，理由在后面）

```text
形态甲 · 作为 laws.yaml 的第 11 条, severity=block
  问题: block 意味着"违反则拒绝" ⇒ 但 G11 是一条"永远为真"的否定性承诺
        ⇒ 它没有可违反的状态 ⇒ block 无对象
        ⇒ 若写成 block, 实现者必须造一个恒不违规的 check_fn ⇒ 又一次"空转"
        ★★ 这正是 ARSI 的病（_check_law 里 8 条 default return False）

形态乙 · 写进 ARCHITECTURE 原则区, 不进 laws.yaml
  优点: 诚实（它本来就不是可检查项）
  缺点: ★ 原则区没有强制机制 ⇒ 会被忽略
        ★ 而 DWC 的全部纪律都靠"可机械检查"支撑, 单写一句没人管

★★★ 形态丙 · 进 laws.yaml, 但 severity=meta, 且**明确无可执行 check_fn**（推荐）
  · 在 yaml 里声明它是元条款（severity: meta, check_fn: null）
  · 执行器遇到 meta 条目**不检查、但必须在每份门报告里引用它**
  · ⇒ 它唯一的可执行形式是: **任何"通过"结论的报告必须附带这一句限定**
  · ★★ 这样它既是数据（进配置、可 grep、可版本化），
    又不伪装成可检查项（不空转）
```

### 3.1 形态丙的可执行形式（关键）

```text
★★ 唯一的强制点: 门报告的**渲染层**必须有这句限定, 否则报告不予出具。

    # 门报告模板（必填字段, 缺此字段 ⇒ 报告无效）
    gate_certification:
      passed: [...]              # 通过的判据 id
      block: [...]               # 触发的 block
      warn: [...]                # 触发的 warn
      ★★ certification_limit:    # 必填, 无默认值, 不可为空串
           "门通过 ≠ 系统安全：本报告不构成安全证明
            （2603.25681 §8.1: an evaluation that reads as safe
             cannot certify that the system is actually safe）"
      ★ evidence_window: [...]   # 本次判据的观察窗（见 §五）

★ 为什么放"渲染层"而不是"检查层":
  因为它约束的是**结论的表述**, 不是行为 ⇒ 行为检查它管不了, 表述检查它管得住
★ 为什么必填无默认:
  任何默认值（包括"自动填入"）都会让人以为可以省略
  ⇒ 依据 §4.4 母巢的三条纪律之三: "调门槛是自欺" —— 默认值就是自欺的入口
```

---

## 四、★★ 它的三条配套条款（缺任一则只是句口号）

```text
★ 依据 2603.25681 §8.1 原文的三个失效机制, 各需一条配套:

配套 1 · ★ 门可被游戏（"games the proxy its monitors track"）
  ⇒ 门报告必须声明**被观测的代理量**是哪个
  ⇒ 若代理量与真实目标不同构, 报告须自陈 "本门观测的是代理量, 不是目标量"
  ⇒ 落法: gate_certification.proxy_target: str（必填）

配套 2 · ★ 停止机制可被禁用（"learn to disable the mechanism meant to stop them"）
  ⇒ 铁律 check 的调用点必须**不可被进化对象触及**
  ⇒ 落法: 判据 I9（见 §六）—— check_fn 所在的模块不得出现在 S_t/H_t 的可编辑范围

配套 3 · ★ 篡改可遗传（2608.03392 §10.3 "harness tampering ... persist in the lineage"）
  ⇒ 门报告必须**入因果链**, 且带 wm_version / dw_version
  ⇒ 这样"这轮的门是在什么版本上过的"可追溯, 换代后必须重跑
  ⇒ 落法: GateSnapshot 已在 STATE_SCHEMA 定义, 只需强制门报告引用它
```

---

## 五、★ 与 §9 第 20 项（守卫①）的关系：同源不同向

```text
★ 第 20 项裁决（守卫①）处理的是"用**什么**判据"：
  自算 confidence → 改为 judge 外测（跨层自评 → 换层）
  ⇒ 它修的是判据的**独立性**

★★ G11 处理的是"判据的结论**能推多远**"：
  即使判据完全独立（judge 外测 + 冻结 + 换手），
  它读到的也只是**特定版本 + 特定观察窗**下的一个指标
  ⇒ G11 修的是判据结论的**外推边界**

★★⇒ 两者不冲突, 且必须同时存在:
  第 20 项保证"判据本身不作弊"
  G11 保证"不作弊的判据也不能被当成安全证明"
  ★ 只做前者 ⇒ 会以为"我的门很干净所以系统很安全"（这正是 coupled 的残余幻觉）
  ★ 只做后者 ⇒ 判据本身仍在自评（漏掉第 20 项的病）
```

---

## 六、可机械检查的判据（gate.py 候选，I9–I12）

```text
I9 · check_fn 所在模块不得出现在可编辑范围（S_t/H_t 的 target 清单）
   ★ 这是"停止机制不可被禁用"的执行形式
   ★ 依据: 配套 2 · 2603.25681 §8.1 "learn to disable the mechanism meant to stop them"
   ★ 与已有判据的关系: 与 P1（不许跨器官私有态）、P4（Prediction 禁 confidence）同族

I10 · 门报告缺 certification_limit 字段 ⇒ 报告无效
   ★ 必填、无默认值、不可为空串
   ★ 依据: §三 形态丙

I11 · 门报告缺 proxy_target ⇒ 报告无效
   ★ 依据: 配套 1 · "games the proxy its monitors track"
   ★★ 附带价值: 逼出"这个门到底在测什么"的自陈, 而非默认"测的是目标"

I12 · 门报告必须引用 GateSnapshot 的 wm_version / dw_version
   ★ 依据: 配套 3 · 篡改可遗传
   ★★ 若 wm_version 变了而门报告没重跑 ⇒ 视为失效报告（不是过期, 是无效）
```

---

## 七、★ 它与 ARCHITECTURE 原则区如何并存（不重复）

```text
★ 原则 1「判据必须在系统之外」管的是**判据的位置**
★★ G11 管的是**判据结论的效力边界** ⇒ 两者不重叠, 互为补充
★ 建议在原则 1 下加一句指向:
  "★ 判据位置合规 ≠ 结论有效: 见 GAP_AUDIT 缺口 A1 / 铁律 G11"
```

---

## 八、诚实边界

```text
① 本设计**未写代码**，`src/` 与 `config/` 均空 —— 符合"架构定稿前不写承重代码"的纪律。
② 未验证: I9–I12 全是设计推理，尚无实现可 grep。
③ ★★★ 我核到了一件必须纠正的事:
   `docs/IRON_LAWS_DESIGN.md` §2.3 把 "config/iron_laws.yaml（10 条）" 当成既有物引用,
   ★★ 但那份 yaml 在 **ARSI** 的目录下（.cache/gh_clones/ARSI/config/iron_laws.yaml,
   809 字节, 全文已核: block 4 / warn 6, G1–G10 定义与 §四表格一致）,
   **不是 DWC 的** —— DWC 的 config/ 是空的。
   ⇒ ★ 该文档的表述会让读者误以为 DWC 已有 yaml ⇒ 应加一句澄清
   ⇒ ★ 而这正说明 G11 的"落点是新建 DWC 的 config/iron_laws.yaml"，
     且**建的时候第一条就该带上 certification_limit 的要求**
④ ★ 我选择形态丙（severity=meta, 无 check_fn）而不是形态甲（block），
   理由是 block 需要可违反状态，而 G11 是恒真的否定性承诺。
   ★★ 但这是我**自己的判断**，论文没有指定形态。
   ⇒ 若将来有人认为它应是 block，必须先回答"它违反时如何被检出"。
⑤ ★ "certification_limit 放在渲染层"是我选的强制点。
   ⇒ 替代方案：放在 laws.yaml 的 description 字段里（但那样不会被每次报告引用）。
   ★ 两者的差别是"是否每次出报告都出现"—— 我选了后者。
⑥ 未核实：母巢/Ultra/Nexus 是否有等价的元条款机制可参考。
⑦ ★ 本条与 GAP_AUDIT 的 A1 是同一件事，做完须在 GAP_AUDIT 里销账。
```

---

## 九、★ 实测记录（rc=0 全通）

```text
✓ I10: 正常报告无缺失; certification_limit 设为空白串 ⇒ 判定为缺 ⇒ 报告无效
✓ I11: proxy_target 空串 ⇒ 缺字段被识别 ⇒ 逼出"测的是代理量还是目标量"的自陈
✓ I12: v3/dw3 有效 → v3/dw4 **失效**（"dw 版本已变"）→ v4/dw4 无报告
  ⇒ ★★ 版本换代后旧报告视为**无效**，不是"过期"
✓ 形态丙 vs 甲: G11(block, check_fn=None) 的执行器只能 default: return False
  ⇒ 形态甲会重演 ARSI 式空转; 形态丙则"跳过检查但在每份报告引用限定语"
✓ I9 静态检查: checks 模块的函数 = [check_effect_range, check_no_self_eval,
    check_certification_limit]; 引用可编辑模块 = 无
  ⇒ ★ 检查器不依赖任何可编辑模块 ⇒ 停止机制不可被进化对象触及
```

---

## 十、★★ laws.yaml 草案（建 config 时照抄）

```yaml
# ★★ 注意: DWC 的 config/ 目前是空的。以下是基于 ARSI 的 10 条 + G11 的**新建草案**。
#    ARSI 原文件在 .cache/gh_clones/ARSI/config/iron_laws.yaml（809 字节, block 4/warn 6）
#    —— 那是 ARSI 的，不是 DWC 的（IRON_LAWS_DESIGN §2.3 的表述会让人误以为已有）

laws:
  # ── G1–G10 沿用（block 4 / warn 6）──
  - id: G5
    name: 客观效用锚
    description: 效果在-1到+1之间，机制禁自评
    severity: block
    check_fn: check_effect_range          # ★ DWC 补: ARSI 的 IronLaw.check_fn 字段从未被使用
  # …
  - id: G10
    name: 密封评估层
    description: 任务集和评分规则和发布门槛在所有写掩码之外
    severity: block
    check_fn: check_access                # ★ DWC 补: 且调用点必须 > 0（判据 I8）

  # ── G11 新增：元条款，不可检查 ──
  - id: G11
    name: 门通过不等于系统安全
    description: >-
      任何门报告都不构成安全证明。依据 2603.25681 §8.1：
      "An evaluation that reads as safe therefore cannot certify that the
      self-improvement system is actually safe."
    severity: meta          # ★ 不是 block/warn —— 它没有可违反的状态
    check_fn: null          # ★ 故意为空；执行器不得为它编造 check（否则重演 ARSI 空转）
    enforcement: report_must_quote      # ★ 唯一的执行形式（见 §三）
```

---

*设计定稿 · 2026-10-04 · 铁律 G11「门通过 ≠ 系统安全」· 形态丙(severity=meta) + 三条配套 + 判据 I9–I12 · 未写代码*