# DWC · `judge`（判据层）设计

> 2026-10-03 · 判据：ARSI sealed_eval 逐行实测 + 16 篇论文原文，不按 README 推断
> 定位：原则 1（判据必须在系统之外）的**唯一载体**；V2 约束 2 的落地形态
> 前置：`ARCHITECTURE.md` §4.1（原 350 字符）· `docs/EVOLUTION_CORE_V2.md` 门③④

---

## 一、先说结论

```text
★ ARSI 的 sealed_eval 是唯一实现, 但它有三处硬缺陷, 全是"门在但没接":

  缺陷 1 · G10 保护是死的
     enforced_laws.py:244 定义 check_sealed_access
     ★ 全仓调用点: 0 处 (只有 tests/test_enforced_laws.py:174 测它)
     ⇒ "任务集和评分规则在所有写掩码之外"这句话, 代码里从未被强制执行

  缺陷 2 · sealed_eval 只在脚本里跑
     SealedEvaluator 调用点: 只有 scripts/baseline_eval.py:45
     ★ core.py 只 import 了 gain_decomposition, 没有 SealedEvaluator
     ⇒ 它是"离线基准工具", 不是"每轮判据"

  缺陷 3 · ★ 最严重: 评分器会给"语法对但功能错"的代码打高分
     evaluator.py _verify_behavior 的 fallback:
       score = 0.5 if has_function else 0.2
       if has_return: score += 0.2
     ⇒ 一个只含 def + return 的空壳函数得 0.7 分 (SUCCESS 阈值 >0.7)
     ★ 这正是母巢 ScoreChannel 恒 0.7 的同款病 —— 而且它藏在"密封评估器"里

★ 所以 DWC 的 judge 不能照抄 ARSI, 要修这三处 + 补 16 篇论文的四件事。
```

---

## 二、ARSI sealed_eval 的完整实测

### 2.1 结构（4 文件）

```text
sealed_eval/
  __init__.py          141 字符
  evaluator.py       9,837 字符   SealedEvaluator — 密封评估执行器
  code_verifier.py   9,837 字符   CodeVerifier — 子进程隔离的真实代码执行
  gain_decomposition.py 8,524 字符 GainDecomposer — 增益三分解
```

### 2.2 evaluator.py 的核心不变量（原文）

```python
class SealedEvaluator:
    """Sealed evaluation executor.

    Invariants:
    - Task set is loaded read-only from config
    - Scoring rules cannot be modified by ARSI
    - Every result carries evidence (never blind SUCCESS)
    """
```

```text
★ 三条不变量写得对 —— 问题在实现:
   ① "loaded read-only"   → 代码是 yaml.safe_load, 但无写保护 (缺陷 1)
   ② "cannot be modified" → 无机制强制 (缺陷 1)
   ③ "never blind SUCCESS"→ 被 _verify_behavior 的 fallback 违反 (缺陷 3)
```

### 2.3 三种 verifier rung（sealed_tasks.yaml 实测 15 条）

| rung | 类别 | 条数 | 判分方式 | 实测判据 |
|---|---|---|---|---|
| 1 | `code_repair` | 6 | `verify_python_code` 子进程执行断言 | `sum_first_n(3)==6` 等 |
| 1 | `knowledge_reasoning` | 6 | `verify_keyword_match` | `expected_keywords: ["pivot","递归","最坏"]` |
| 3 | `paper_reproduction` | 3 | `verify_values` + tolerance | `mean: 6.00, tolerance: 0.1` |

```yaml
# 逐字样本
- id: code_fix_001
  category: code_repair
  verifier_rung: 1
  prompt: "修复 sum_first_n 函数中的 off-by-one 错误，使其计算 1 到 n 的和"
  expected_behavior: "sum_first_n(3)==6 and sum_first_n(5)==15"
```

**★ rung 的意义（DWC 要继承）**：rung 越高，判据越硬。

```text
rung 1 keyword_match  → 最弱 (关键词命中, 可被"说对话"骗过)
rung 1 code_execution → 中   (真跑断言)
rung 3 expected_values→ 最强 (数值 + tolerance)
★ 15 条里 rung 3 只有 3 条 (20%) —— 硬判据太少。
```

### 2.4 ★ 缺陷 3 的代码级证据

```python
# evaluator.py _verify_behavior 的 fallback (原文)
        # Fallback: extract code and check syntax + basic structure
        extracted = verifier._extract_code(output)
        if not extracted:
            return 0.0, {**evidence, "reason": "no_code_found"}
        try:
            import ast
            ast.parse(extracted)
            has_function = "def " in extracted
            has_return = "return" in extracted
            score = 0.5 if has_function else 0.2
            if has_return:
                score += 0.2
            return min(score, 1.0), {..., "method": "syntax_check", ...}
```

```text
★ 实测 (2026-10-03, 复刻该分支逻辑逐例跑; SUCCESS 阈值 score > 0.7):

   输入                                  score   判定
   ─────────────────────────────────────────────────
   空壳 "def f(): return None"            0.7    PARTIAL
   空壳 + 注释                            0.7    PARTIAL
   ★ 完全错但结构对 "return -999"          0.7    PARTIAL   ← ★★
   ★ 正确实现 "return n*(n+1)//2"          0.7    PARTIAL   ← ★★
   只有 def 无 return                     0.5    PARTIAL

★★ 实测结论比我原推演更严重:
   不是"给空壳打高分", 是 **完全零分辨率** ——
   正确的实现和完全错误的实现**得同一个分 (0.7)**。
   ⇒ 这个 fallback 根本不能区分对错, 它的分数不含任何关于正确性的信息。

★ 与母巢纪律 3 完全同构 (gene_champion 原文):
   "真因: score_in 是量化阶梯函数, 同一台阶内基因无分辨率 ⇒ gain 恒 0,
    降门槛无用。4/7 轮回退的 gain 恰为 0.0 (逐位相同)。"
   ⇒ 同一个病, 两处独立出现 (母巢 score_in / ARSI 的 fallback)。

★ 补充: 0.7 恰好等于阈值 (不 > 0.7), 所以判 PARTIAL 而非 SUCCESS ——
   这是**巧合**, 不是设计。若 has_function 权重是 0.6, 空壳就是 0.8 = SUCCESS。
   把正确性判定托付给一个"恰好卡在阈值上"的常数, 是运气不是保证。

★ 什么时候会走到 fallback? 当 _parse_test_cases(expected_behavior) 返回空时。
   ⇒ 只要 expected_behavior 格式稍微不标准, 判分就退化成结构检查。
   ★ 这是静默降级 —— 而 ARSI 没有记这件事发生了几次。
```

---

## 三、16 篇论文给 judge 的四件事

### 3.1 ★ 三 split：train / dev / test（2607.12790）

```text
# Who Grades the Grader? §2.2 原文
三个**互不相交**的 split:

  train    大、无标签   暴露候选 metric 何时分歧或弃权; train task 上不附任何参考
  dev      ★ 恒为 10 条  每条带 golden reference; teacher 对其发 soft pass/fail 标签
           ★ "the only supervised signal any loop reads"
  test     locked       "no part of metric evolution reads it"

★ 论文明确说明保证的非对称性:
  "Metric-validity numbers are strictly out of sample"
  "Skill-side task scores are not out of sample in the same sense:
   they are the pass rate of a loop that rolls back on that set"

★ 为什么 dev 这么小 (原文):
  "fresh labels in deployed systems arrive as a trickle of demos and
   incident reviews, not as a labeled corpus."
```

**★ DWC 的映射**：

```text
DWC 的 judge 需要三个 split, 不是一组:
  dev(锚点)  = ARSI 的 sealed_tasks 15 条  → 但它不是"dev", 是全部
  test(锁定) = 必须另建, 且 metric 演化不许读
  train      = 无标签的大集合

★ 当前 ARSI 只有一组 15 条 ⇒ 无法判定"可复用改进 vs 过拟合"
  (这正是 V2 约束 3: "只有一组 split 就没有判定能力")
```

### 3.2 ★ drawback 检测器：不认证正确，只找缺点（2607.12790）

```text
# §2.1 原文
"we rarely know what good is, but given an output we can usually find drawbacks,
 so a clean verdict means no known drawback was found, not certified correctness.
 That is what makes bootstrap possible."

配套设计理由:
"mostly deterministic detectors, which fail differently from the LLM being graded,
 resist the shared-blind-spot collusion a bare LLM judge invites."
```

```text
★ 两层含义:
  ① 判据方向反转: 不测"多好", 测"有没有已知缺点"
  ② 检测器必须与被评分者**失效模式不同** (防共谋盲点)

★ DWC 的落地:
  op(t, y, c) ↦ {drawback, clean, abstain}
  "checking exactly one failure class and abstaining otherwise"
  ★ 三类成本层: static ops (解析) / execution ops (真跑) / judge ops (问 LLM)
  ★ 每族有一个**固定的、不进化的 root**:
    "validates basic structure (code parses, a report has a title) and caches the ..."
```

### 3.3 ★ FGGM 契约 + 已验证 fallback（2603.25111）

```python
# SEVerA §2.2 原文伪代码
requires Φ_l(x1,…,xn) {
    var p := f_p(x1,…,xn), y;
    for i = 1..K {                      # K = 5
        y := L_Θ(p);
        if check(x1,…,xn, y) return y;  # (1) 拒绝采样
    }
    return f_d(x1,…,xn, y_f);           # (2) 已验证的 fallback
}
```

```text
★ 四条声明性质 (§4.2):
  1 Flexibility                       — 契约由 planner LLM 现场合成
  2 Parameter-Independent Correctness — 对任意 θ ∈ Θ 都成立
  3 Local Learning Objective          — 契约顺手抽出局部学习目标
  4 fallback 的必要性                  — 没有 fallback 拒绝采样器可能耗尽样本

★ ★ 关键: fallback 本身也必须满足同一条契约
  (validateFGGM 第 26 行: Verify(∀x…,y. Φ_l(x…) ⟹ Ψ_l(x…, f_d(x…,y))))
```

**★ 这一条直接治缺陷 3**：

```text
ARSI 的 fallback 是"结构检查"(有 def/return 就给分) —— 它**不满足**"判定任务是否解决"这条契约。
FGGM 要求: fallback 必须能被自动判定为"满足它替代的能力的契约"。
⇒ DWC 的 judge: 任何 fallback 若不满足同契约, 不许注册。
```

### 3.4 ★ grounded 双条件（2609.13406）

```text
# GAI §2.2 原文
grounded 的两个条件 (AND, 缺一不可):
  ① 内容来自系统外 (世界与目标)
  ② base 本身在 agent 外

★ 可落成 gate 断言: {Q*, T_seal, release_rule, ℒ} ∩ W_i = ∅ ∀i

★ Remark 2 原文:
  "判别标准问的是『标准坐在哪里』, 不是『它多忠实于目标』。"
  ⇒ 弱评估器 + 密封 = 合法;  强评估器 + 在可写面内 = Goal Drift
```

**★ 这给了 DWC 一个更简单的合法性判据**：

```text
不需要问"judge 准不准", 只需要问"judge 在不在可写面内"。
⇒ 可机械检查: judge 的所有输入/输出路径, 是否与任何可写面相交。
```

---

## 四、DWC 的 judge 设计

### 4.1 形态：三件套

```text
┌──────────────────────────────────────────────────────────────────┐
│  judge（判据层）· 进程外, 不可写                                   │
│                                                                   │
│  ① 密封任务集 sealed_set/                                         │
│     ├─ dev/    锚点任务 (带 golden reference)   ← 恒小, 唯一有监督  │
│     ├─ test/   锁定任务 (metric 演化不许读)      ← 2607.12790     │
│     └─ train/  无标签大集合 (暴露分歧/弃权)                       │
│     ★ 每个任务带 verifier_rung (1/2/3), rung 越高判据越硬          │
│                                                                   │
│  ② 判定器 verifier/                                               │
│     ├─ code_exec    子进程执行断言         rung 2                 │
│     ├─ values       数值 + tolerance       rung 3                 │
│     ├─ drawback     op(t,y,c) → {drawback,clean,abstain}          │
│     └─ ★ 无 keyword_match (最弱, 见 §4.3 裁决)                     │
│                                                                   │
│  ③ 封印 seal/                                                     │
│     ├─ 路径保护 (G10 落地, 修缺陷 1)                              │
│     ├─ 契约校验 (每个 verifier 声明 Φ/Ψ, 修缺陷 3)                 │
│     └─ grounded 断言 ({Q*,T_seal,release_rule,ℒ} ∩ W_i = ∅)       │
└──────────────────────────────────────────────────────────────────┘
```

### 4.2 ★ 修缺陷 1：G10 从"定义"变成"每轮执行"

```text
ARSI 的病: check_sealed_access 定义在 enforced_laws.py:244, 全仓调用 0 处。

DWC 的修法: 封印不是"提供接口等人调用", 而是**在 judge 的每个入口强制**:

  judge.load_task_set()   → 先 seal.assert_readable(path, caller="judge")
  judge.score(...)        → 先 seal.assert_contract(verifier)
  judge.release(...)      → 先 seal.assert_grounded(registry)

★ 判据 (可机械检查): seal.assert_* 的调用点数 == judge 的公开方法数
  —— 少一个就是漏了。这条可以写进 gate.py (见 §4.7)。
```

### 4.3 ★ 修缺陷 3：禁 keyword_match 作主判据

```text
★ 裁决: keyword_match 不得作为**主判据**。

理由 (两条):
  ① 2607.12790 原文: 判据必须与被评分者**失效模式不同**。
     keyword_match 正是 LLM 最容易骗过的形态 (说对话就行)。
  ② ARSI 实测: 6/15 条 (40%) 用 keyword_match, 而 rung 3 只有 3 条 (20%)
     ⇒ 硬判据占比过低。

DWC 规则:
  · 每个任务必须声明 verifier_rung
  · 主判据必须是 rung ≥ 2 (code_exec / values / drawback)
  · keyword_match 只允许作**辅助信号**, 且必须与主判据**同时**通过
  · 任务集里 rung 3 的占比不得低于 40% (ARSI 是 20%, 太低)

★ 并且: 任何 fallback 必须声明它满足哪条契约 (FGGM validateFGGM 第 26 行)。
  结构检查 (有 def/return 给分) **不是**合法 fallback —— 它不满足
  "判定任务是否解决"这条契约。
  ★ 实测佐证: 该 fallback 对"正确实现"与"完全错误实现"给同一分 0.7
    ⇒ 零分辨率 ⇒ 它连"判定任务是否解决"的信息都不含。
```

### 4.4 修缺陷 2：judge 从"离线脚本"变成"每轮判据"

```text
ARSI 的病: SealedEvaluator 只在 scripts/baseline_eval.py 调用一次。

DWC 的修法: judge 进 run_term 的固定位置 (见 ARCHITECTURE §2.4.4):

  run_term 开始 → judge.evaluate(split="dev")   ← 前测 (基线)
  run_term 结束 → judge.evaluate(split="dev")   ← 后测 (结算)
  ★ 两次必须**同口径** (母巢纪律 1: base 与 current 必须同一口径)

★ 与 V2 器官④落地的接口:
  U (改动评估器) 的裁决输入 = judge 的 held-out 分数
  U 只读 r_priv (judge 的输出), 绝不读 r_pub (agent 可见的)
```

### 4.5 ★ 新增：三 split 的构造与维护

```text
① dev/ 锚点任务 (恒小)
   DWC 起步: 复用 ARSI sealed_tasks 15 条 (补齐 rung 2)
   ★ 为什么不照抄"恒 10 条": 15 条已是现成资产, 且 ARSI 实测可跑。
     但**必须保持"小"** (原文理由: fresh labels 是涓流不是语料库)。
   ★ 维护规则: 只能**增**不能减 (2606.14249 的守门人单调性:
     "只能加新探针、不能删旧探针" —— 防 agent 通过让旧探针失效来降低严格度)

② test/ 锁定任务
   ★ 必须另建, 且 metric 演化**不许读** (原文: "no part of metric evolution reads it")
   判据: test/ 的路径必须出现在 seal 的保护列表里, 且 judge 的
        "改进提案" 路径不得有读 test/ 的代码。

③ train/ 无标签
   暴露候选判据何时分歧或弃权。★ train task 上不附任何参考。
```

### 4.6 ★ 新增：judge 自己的审计（防"门失效"）

```text
★ 2606.14249 的教训 (用自己的实验证伪了自己的门: −14.0%):
  门本身会失效, 必须定期测。

DWC 的 judge 自检 (照 2608.24876 Table 4 的故障定位协议):
  注入已知故障到组件 A/B/C, 问固定 judge "哪个坏了"
  ★ 若"仅结果"证据的准确率低于恒定猜测基线 (三选一 = 33.3%)
    ⇒ judge 的健康视图不可用, 必须报红

  ★ 2608.24876 实测 (三类证据的准确率):
    仅结果        13.0%   ← ★ 低于恒定猜测 33.3%
    原始轨迹      37.0%
    结构化 trace  64.8%
  ⇒ DWC 的 judge 必须喂**结构化 trace**, 不是"仅结果"。
```

### 4.7 ★ 可机械检查的判据（写进 gate.py 的候选）

```text
J1 · 封印调用点完整
   seal.assert_* 调用点数 == judge 公开方法数
   依据: ARSI check_sealed_access 调用 0 处

J2 · 无结构检查冒充功能检查
   judge 目录下不得出现"按形状给分"的 fallback
   判据: 正则匹配 has_function|has_return|len(.*)>.*score +=
   依据: ARSI _verify_behavior 的 0.5+0.2 fallback

J3 · rung 占比
   rung 3 (expected_values + tolerance) 的任务占比 ≥ 40%
   依据: ARSI 实测 3/15 = 20%

J4 · 三 split 齐备
   dev/ test/ train/ 三个目录都存在, 且 test/ 在 seal 保护列表里
   依据: 2607.12790 §2.2

J5 · grounded 断言
   {Q*, T_seal, release_rule, ℒ} ∩ W_i = ∅  (可写成集合运算断言)
   依据: 2609.13406 §2.2 + 2609.06396 Eq.30

J6 · judge 不进递归
   改进提案的代码路径不得 import judge 的可写面
   依据: 2608.24876 Eq.9 "𝒢_fixed 不能进递归"
```

---

## 五、诚实边界

```text
① ARSI 的 sealed_eval 我只做了静态审计 (读码 + grep 调用点), 未运行它的评估。
   "check_sealed_access 调用 0 处" 是 grep 结果, 若有动态调用 (getattr) 会漏。
   已用两种口径查过 (grep 函数名 / grep 模块名), 结论一致。

② ★ 已实跑验证 (2026-10-03): 复刻 _verify_behavior 的 fallback 逻辑逐例跑,
   结果见 §2.4 —— 空壳与正确实现**同分 0.7**, 即零分辨率。
   ★ 更正: 我初稿写"再加一点点就 >0.7 ⇒ SUCCESS"是**错的** ——
     0.5+0.2=0.7 已封顶, 加不上去。实测后改为"零分辨率"这个更准确的结论。
   ★ 未验证的部分: 未在 ARSI 里真跑 SealedEvaluator (只复刻了该分支逻辑),
     因为 DWC 尚未写码, 不想改 ARSI。分支逻辑是逐行照抄的。

③ "三 split" 中 dev 恒 10 条是 2607.12790 的做法, DWC 未必要照抄数字。
   我建议 15 条 (复用 ARSI 资产), 但**保留"小"这个性质**。

④ keyword_match 的裁决 (禁作主判据) 是我基于两条理由的判断, 不是论文原文明说。
   论文只说"检测器必须失效模式不同", 是我把它推到了"keyword_match 不合格"。

⑤ judge 的子进程隔离/通信协议/超时处理**未定** —— 本轮只定了形态与判据,
   实现细节 (IPC 方式、崩溃恢复) 留给实现阶段。
```

---

## 六、§9 第 6 项（器官接口契约）的进展

```text
judge 这一轮顺带解决了原则 6 的一部分:

★ judge 的接口契约 (可检查):
   输入:  sealed_set (只读) + agent 的输出
   输出:  Verdict {score, evidence, split, truth_source}
   ★ 不许: judge 读任何可写面 (grounded 双条件)
   ★ 不许: 其他器官 import judge 的内部实现 (只经 judge.evaluate())

★ 其余器官的接口契约仍未定 (memory / actor / evolver / world_model / iwm)。
```

---

## 附：存证

```text
ARSI 源码: src/arsi/sealed_eval/{evaluator,code_verifier,gain_decomposition}.py
           src/arsi/foundation/enforced_laws.py (G10)
           config/sealed_tasks.yaml (15 条)
论文报告:  docs/papers/2607.12790.md · 2603.25111.md · 2609.13406.md · 2608.24876.md
```
