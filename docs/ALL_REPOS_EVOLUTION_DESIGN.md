# DWC · 全部 39 个 GitHub 仓库的进化设计全景（实测）

> 2026-10-03 · 判据：39 仓库全部浅克隆到 `.cache/gh_clones/`，逐仓库扫源码，只报实测
> 触发：用户「你不要只关注这几个项目 去我的github 看所有的项目 进化是怎么设计的」

---

## 〇、方法与范围

```text
① 拉取: GitHub API 39 个仓库 (Lsinxcoy), 全部 --depth 1 浅克隆 → 39/39 成功
② 扫描: 每仓库的 evolution/evolv/harness/mutator/gene/accept/gates/rsi 相关 .py
③ 判据: 只报源码可机械查的东西 (类名/方法/常量/顺序序列), 不按 README 推断
④ 存证: .cache/gh_clones/ (源码) + 4 份扫描 JSON + 3 份文本报告
```

---

## 一、★ 最重要的发现：39 个仓库只有 1 个是"先落后测"

### 1.1 顺序判定表（机械判据）

```text
判据 A 先测后落: 源码里有 mutate/generate → validate/verify/gate → apply 的序列
判据 B 先落后测: 源码里有 apply/setattr → observe/await/window/shadow 的序列
```

| 仓库 | 验证符号 | 应用符号 | 影子符号 | 回滚 | 测→落 | 落→观 | 判定 |
|---|---|---|---|---|---|---|---|
| **SYNTHEX-Autopoiesis-pure** | 1230 | 34 | **96** | 70 | 0 | **4** | ★ **唯一先落后测** |
| ARSI | 1261 | 13 | 3 | 62 | 1 | 1 | 先测后落 |
| MSTAR-Pro-V4.0 | 175 | 4 | 0 | 79 | 1 | 0 | 先测后落 |
| MSTAR-Pro-V4.0-Clean | 103 | 3 | 0 | 76 | 1 | 0 | 先测后落 |
| prometheus-v8pro | 172 | 2 | 0 | 10 | 1 | 0 | 先测后落 |
| Prometheus-Ultra | 612 | 8 | 0 | 28 | 0 | 0 | 有回滚 |
| Prometheus-Ultra-MultiTypeKB | 681 | 13 | 1 | 28 | 0 | 0 | 有回滚 |
| prometheus-nexus | 694 | 13 | 5 | 30 | 0 | 0 | 有回滚 |
| Prometheus-Y | 62 | 7 | 0 | 10 | 0 | 0 | 有回滚 |
| Prometheus-Omega-Genesis | 661 | 5 | 1 | 4 | 0 | 0 | 有回滚 |
| Prometheus-X | 57 | 8 | 0 | 1 | 0 | 0 | 有回滚 |
| Prometheus-Omega-Omega | 594 | 5 | 1 | 2 | 0 | 0 | 有回滚 |
| prometheus-v8 / v9pro / v10 | 33~35 | 0~1 | 0 | 5 | 0 | 0 | 有回滚 |
| prometheus-v7 | 93 | 0 | 0 | 1 | 0 | 0 | 有回滚 |
| hermes-agent | 65 | 0 | 0 | 3 | 0 | 0 | 有回滚 |
| hermes-agent-backup | 66 | 2 | 0 | 1 | 0 | 0 | 有回滚 |
| MSTAR 系 (mstar/hermes-mstar/mstar-pro/Hermes-MSTAR-V2.0) | 1~184 | 1~3 | 0 | 0 | 0 | 0 | 未识别 |
| Prometheus-Omega | 228 | 2 | 0 | 0 | 0 | 0 | 未识别 |
| Prometheus-Z | 185 | 0 | 0 | 0 | 0 | 0 | 未识别 |
| Protogonos | 3 | 3 | 0 | 0 | 0 | 0 | 未识别 |
| CIP-Zhazhazhu | 0 | 2 | 0 | 0 | 0 | 0 | 未识别 |
| hermes-collective-intelligence | 2 | 2 | 0 | 0 | 0 | 0 | 未识别 |
| prometheus-v3/v4/v5/v6 | 8~62 | 0~21 | 0 | 0 | 0 | 0 | 未识别 |
| hermes-skills / hermes-scripts / prometheus | 8~16 | 0~2 | 0 | 0~5 | 0 | 0 | 未识别 |
| CIP-KaoKaoJiang / PPT.SKILL / PPTPRO.SKILL / hermes-kanban-cip / prometheus-v9 | 0 | 0 | 0 | 0 | 0 | 0 | **无进化代码** |

### 1.2 ★ 这个表说明了什么

```text
39 个仓库中 (逐项复核 evolution_order.json):
  · 有影子符号的: 6 个
      SYNTHEX-Autopoiesis-pure     96   ← 独占 90%
      prometheus-nexus              5
      ARSI                          3
      Prometheus-Omega-Genesis      1
      Prometheus-Omega-Omega        1
      Prometheus-Ultra-MultiTypeKB  1
    ⇒ 其余 33 个仓库影子符号 = 0

  · "先落后测"序列 (apply→observe/window): 2 个
      SYNTHEX-Autopoiesis-pure  4 处
      ARSI                      1 处 (已核实为命名巧合, 见诚实边界④)
    ⇒ 其余 37 个仓库 = 0

  · 先测后落的明确序列: 4 个 —— ARSI / MSTAR-Pro×2 / prometheus-v8pro
  · 有回滚机制的: 17 个
  · 无进化代码的: 5 个 (PPT 技能包 ×2, CIP-KaoKaoJiang, hermes-kanban-cip, prometheus-v9)

★ 结论 (复核后):
  ① 影子符号 107 处总量中 SYNTHEX 占 96 = 90% ⇒ 高度集中, 不是普遍存在
  ② "先落后测"序列 SYNTHEX 4 处 / ARSI 1 处 (已核实为命名巧合) ⇒ 真正只有 SYNTHEX
```

---

## 二、★ 第二个发现：你的进化设计有**四条清晰的谱系**

### 2.1 谱系一：L 层枚举式（12 层 → 4 层）

**12 层版（Prometheus-Omega / Prometheus-X）** —— 实测类名逐字：

```text
L0  MetaParams      Auto-tune evolution hyperparameters (from CIP_Hermes_v2 L0)
L1  Strategy
L2  Skill
L3  Config
L4  Code
L5  MetaEvolution
L6  Prompt
L7  Tool
L8  Memory
L9  Knowledge
L10 Collaboration
L11 Architecture
```

```python
# Prometheus-X layers.py 原文
"""Prometheus X — 12 Evolution Layers
   Base protocol (EvolutionLayer + result dataclasses) and all 12 concrete layers."""
class L0MetaParams(EvolutionLayer):
    """Auto-tune evolution hyperparameters (from CIP_Hermes_v2 L0)."""
    name = "L0_MetaParams"
    def __init__(self):
        self.mutation_rate = 0.1
        self.crossover_rate = 0.3
```

**4 层版（CIP-Zhazhazhu / hermes-collective-intelligence）** —— 实测：

```text
L1 Config   数值变异（高斯噪声）
L2 Skill    workflow 变异（14种）
L3 Behavior 工作流变异
L4 Code     CGP 遗传编程变异
```

```python
# hermes-collective-intelligence 原文
"""HERMES Full Spectrum Evolution System - Evolution Layers L1-L4全谱进化引擎
   设计来源: E:/HERMES_Collective_Intelligence.txt 第六节 全谱进化
   L1 配置层 │ L2 技能层 │ L3 行为层 │ L4 底层代码
   阈值/参数  │ 技能改进  │ 工作流重构 │ 算法/数据结构"""
```

### 2.2 谱系二：九维枚举式（ARSI）

```text
c1 model_selection        c6 evaluation_and_reward
c2 context_assembly       c7 control_and_safety   ← FROZEN_DIMS = frozenset({"c7"})
c3 memory_management      c8 observability
c4 tool_ecosystem         c9 training_bridge
c5 execution_environment
```

```python
# ARSI taxonomy.py 实测
FROZEN_DIMS = frozenset({"c7"})
```

**★ ARSI 是最"窄"的一个：9 维里冻 1 个（c7），且实测 862 条提案里 c4 tool_ecosystem 用了 434 条。**

### 2.3 谱系三：GA 层式（MSTAR 系）

```text
# hermes-mstar / mstar 原文 —— 15 种变异操作
Schema 变异 (3): field_add, field_remove, field_modify
Logic 变异 (3): read_modify, write_modify, query_add
Instructions 变异 (7): keyword_add/remove/replace, threshold/priority/guidance, crossover, ensemble
随机变异 (1): random_change

# 4 门质量检查 (原文)
1. Compile Gate - 语法检查
2. Runtime Gate - 执行检查
3. Logic Gate - 逻辑检查
4. Quality Gate - 质量检查
```

```text
# MSTAR-Pro-V4.0 进化模块全清单 (实测 12 个文件)
engine.py / evolvemem.py / experience_recall.py / fitness_tracker.py / mutator.py
predictor.py / protocol.py / reflector.py / robustness.py / version_control.py
cantante/__init__.py
```

**★ MSTAR 是唯一有"形式化验证 + 自动回滚"的完整设计**：

```python
# version_control.py 原文
"""每个mutation必须通过形式化验证才能执行
   验证项: 内存安全、类型安全、语义保持
   失败时自动rollback"""
def verify_mutation(self, program_id, mutation_type, mutation_details) -> FGGMContract:
    """验证一个mutation是否安全。执行以下检查:
       1. Memory Safety: 检查是否会导致资源泄漏
       2. Type Safety: 检查参数类型是否匹配
       3. Semantic Preservation: 检查核心逻辑是否保持"""
def rollback_to(self, program_id, target_version_id, reason="") -> Optional[MutationVersion]:
    """回滚program到指定版本。"""
```

### 2.4 谱系四：门控式（Prometheus-Z / Omega）

```python
# Prometheus-Z anti_evolution_gate.py 原文
"""AntiEvolutionGate — Iron Law 2: 4 prerequisites for evolution.
   Evolution is denied unless ALL 4 prerequisites pass:
   1. DEDUP: Is this a novel insight? (not already attempted)
   2. INSIGHT: Does it provide genuine new understanding?
   3. APPLICATION: Can it be applied to improve something?
   4. CONSECUTIVE_GAIN: Will it produce consecutive improvement?
   Any failure = silent rejection (no half-measures)."""
```

```python
# Prometheus-Z iron_law.py 原文
"""VerificationIronLaw — Iron Law 3: 5-step verification gate.
   Steps (mandatory, no skipping):
   1. IDENTIFY — what is the claim?
   2. RUN — execute the test/experiment
   3. READ — collect the output
   4. VERIFY — compare output against expected
   ..."""
```

```python
# Prometheus-Z store/five_gates.py 原文
"""FiveGates — P20: Write → Read → Modify → Consolidate → Execute.
   6 independent systems converged on this architecture
   (SAGE+MemGate+SkillAdaptor+Nautilus+AURA-Mem+TRACE).
   Each gate is a cascading failure circuit breaker — one gate fails → short-circuit return."""
```

```python
# Prometheus-Z compile_to_rule.py 原文
"""CompileToRule — E11: Deterministic compilation of high-fitness patterns.
   When a pattern's fitness > 0.95, it graduates from probabilistic reasoning
   to deterministic execution. This is the "compile" step in the evolution pipeline.
   Compiled rules:
   - Never re-evaluate (saves computation)
   - Never drift (deterministic guarantee)
   - Can be audited (written as explicit code/config)"""
def compile(self, pattern, fitness, branch="main") -> Node | None:
    if fitness < self._config.compile_fitness_threshold: return None
```

**★ `compile_to_rule` 是全部 39 仓库里唯一"把学到的固化成确定性代码"的设计**（阈值 0.95）。

---

## 三、★ 第三个发现：进化对象共 6 套体系（不是 1 套）

| 体系 | 对象数 | 出处 | 实测类名/枚举 |
|---|---|---|---|
| **12 层** | 12 | Prometheus-Omega / Prometheus-X | L0MetaParams…L11Architecture |
| **9 维 c1-c9** | 9 | ARSI | c1 model_selection…c9 training_bridge |
| **4 层 L1-L4** | 4 | CIP-Zhazhazhu / hermes-collective-intelligence | L1Config/L2Skill/L3Behavior/L4Code |
| **4 轨 T1-T4** | 4 | Prometheus-Ultra-MultiTypeKB | T1 参数 / T2 语义 / T3 GitHub / T4 论文 |
| **3 方向** | 3 | Prometheus-Y / Omega | FORWARD / LATERAL / REVERSE |
| **15 变异** | 15 | MSTAR 系 | Schema3 + Logic3 + Instructions7 + 随机1 |

```text
★ 与之前 34 个对象的对照:
   之前总结的 34 = 28 对象层 + 6 元层, 是把 6 套体系"合并去重"的结果。
   现在实测到: 这 6 套体系分别长在 6 个不同仓库里, 是 6 次独立设计。
```

---

## 四、★ 第四个发现：落地形态分三类，且"真写"的极少

### 4.1 真写符号统计（机械）

| 仓库 | 文件 | 真写 | 只提案 |
|---|---|---|---|
| **SYNTHEX** | 115 | 实例赋值 718, 落盘 44, 写文件 43 | propose 13, 需人工审 5 |
| ARSI | 152 | 实例赋值 537, 落盘 67, 写文件 68, apply 3 | **propose 20**, 需人工审 1, manifest 1, status=accepted 2 |
| prometheus-nexus | 56 | 实例赋值 333, apply 2, 落盘 8 | propose 5 |
| Prometheus-Ultra-MultiTypeKB | 51 | 实例赋值 322, apply 2 | propose 5 |
| Prometheus-Ultra | 47 | 实例赋值 306, apply 2 | propose 5 |
| MSTAR-Pro-V4.0 | 18 | 实例赋值 86, 落盘 106, setattr 2 | propose 1, **status=applied 2** |
| Prometheus-Omega-Genesis | 33 | 实例赋值 150 | propose 4 |
| Prometheus-Y | 15 | 实例赋值 87 | propose 1 |
| Protogonos | 5 | setattr 1, 实例赋值 17, 写文件 2 | — |

### 4.2 三类落地形态（实测）

```text
甲 · 只出提案, 明说"不改核心"
    ARSI harness/evolver.py 原文:
    "**Does not auto-edit core** — manifests are reviewable artifacts
     (HarnessX Change-Manifest discipline)."
    → propose 20 处, 需人工审 1 处
    → 实测 862 条 manifest: accepted 860 / applied 2

乙 · 有真写, 但写的是"自己的状态"不是"生产行为"
    SYNTHEX 实例赋值 718 处 (最多) —— 但影子 96 处把真写挡住了
    Prometheus-Ultra/Nexus 实例赋值 300+ —— 但 evolution_log 里 evolve=0

丙 · 形式化验证后才写 + 自动回滚 (MSTAR 独家)
    MSTAR-Pro-V4.0 version_control.py:
      verify_mutation() → FGGMContract (内存安全/类型安全/语义保持)
      失败 → rollback_to() 自动恢复
    ★ 这是 39 仓库里唯一"验证→写→可回滚"三段完整的
```

---

## 五、★ 第五个发现：门的设计有 5 种，按严格度排序

```text
① ARSI non-compensatory 四步 (最科学)
   """Order matters:
      0) leakage screen BEFORE evaluation
      1) noise floor  Ŝ ≥ S* − δ
      2a) ΔS > δ → cost rule  ΔC ≤ β0 + β1·ΔS
      2b) ΔS ≤ δ → shaped   ws·ΔS − wc·ΔC + wn·ν_str > 0
      3) domain guards"""
   ★ 特点: "非补偿式" —— 顺序不可换, 后一步不能补偿前一步

② Prometheus-Z AntiEvolution 4 前置
   DEDUP → INSIGHT → APPLICATION → CONSECUTIVE_GAIN
   ★ 特点: "Any failure = silent rejection (no half-measures)"

③ Prometheus-Z VerificationIronLaw 5 步
   IDENTIFY → RUN → READ → VERIFY → (5th)
   ★ 特点: "Steps (mandatory, no skipping)"

④ MSTAR 4 门
   Compile → Runtime → Logic → Quality
   ★ 特点: 从语法到质量的递进

⑤ Prometheus-Z FiveGates 5 门
   Write → Read → Modify → Consolidate → Execute
   ★ 特点: "Each gate is a cascading failure circuit breaker — one gate fails → short-circuit return"
```

---

## 六、★ 第六个发现：进化方向的设计只有 2 个仓库有

```text
Prometheus-Y / Prometheus-Omega (实测枚举):
  EvolutionDirection.FORWARD   前进 (在现有基础上改进)
  EvolutionDirection.LATERAL   横向 (换一个方向试)
  EvolutionDirection.REVERSE   后退 (回退到更简单的方案)

★ 39 仓库里只有这两个有"方向"概念。
★ 而 DIMENSION_REPORT 里把"进化方向 4 种"列为"过程维度"剔除了 —— 现在实测确认:
  它是 Prometheus-Y/Omega 的真实设计, 但只覆盖 2 个仓库。
```

---

## 七、汇总：39 仓库的进化设计矩阵

```text
                    L层  9维  4层  4轨  方向  15变异  门  落地  影子
Prometheus-Omega    12   ·    ·    ·    ✓     ·     ✓   提案   ·
Prometheus-X        12   ·    ·    ·    ·     ·     ✓   提案   ·
ARSI                 ·   9    ·    ·    ·     ·    ★4步  提案   3
Prometheus-Z         ·   ·    ·    ·    ·     ·    5步   ·     ·
Prometheus-Omega-Gen ·   ·    ·    ·    ·     ·     ✓   提案   1
MSTAR 系             ·   ·    ·    ·    ·    15    4门  ★真写  ·
Prometheus-Ultra     ·   ·    ·    ·    ·     ·     ✓   实例   ·
Ultra-MultiTypeKB    ·   ·    ·   4    ·     ·     ✓   实例   1
prometheus-nexus     ·   ·    ·    ·    ·     ·     ✓   实例   5
Prometheus-Y         ·   ·    ·    ·    3     ·     ✓   实例   ·
hermes-CI            ·   ·   4    ·    ·     ·     ·    ·     ·
CIP-Zhazhazhu        ·   ·   4    ·    ·     ·     ·    ·     ·
Protogonos           ·   ·    ·    ·    ·     ·     ·   promote ·
SYNTHEX-Autopoiesis  ·   ·    ·    ·    ·     ·     ✓   实例  ★96
```

---

## 八、★ 对 DWC 的三条结论

### 结论 1 · 影子是孤例，不是传统

```text
39 仓库复核:
  影子符号: 6 个仓库有, 但 SYNTHEX 独占 96/107 = 90%
  其它 33 个仓库影子符号 = 0
  "先落后测"序列: SYNTHEX 4 处 / ARSI 1 处 / 其余 37 个 = 0
  
★ 即: 影子机制高度集中在 SYNTHEX 一个仓库 (90%)。
  这印证了你上一轮的判断 —— 影子是后来引入的, 不是你的设计传统。
```

### 结论 2 · DWC 应该采四家的长处（各有独家）

```text
ARSI     → 门 (non-compensatory 四步, 顺序不可换)
MSTAR    → 落地 (verify_mutation → 写 → rollback_to, 三段完整)
Prometheus-Z → 固化 (compile_to_rule: fitness>0.95 固化成确定性代码)
Prometheus-Y → 方向 (FORWARD/LATERAL/REVERSE 三方向)
```

**这四家正好互补成一条完整链**：

```text
方向选择 (Y) → 门 (ARSI) → 形式化验证 (MSTAR) → 落地 (MSTAR rollback) → 固化 (Z)
```

### 结论 3 · 进化对象 6 套体系, 但 DWC 只需 1 套

```text
6 套体系实测:
  12层 (Omega/X) / 9维 (ARSI) / 4层 (CIP/CI) / 4轨 (Ultra) / 3方向 (Y) / 15变异 (MSTAR)

★ 这 6 套是 6 次独立枚举, 互不兼容 (层≠维≠轨)。
★ DWC 若照抄任何一套, 都会丢掉另外 5 套覆盖的对象。
  ⇒ 应沿用之前 34 对象的"合并去重"结果 (28 对象层 + 6 元层),
    它正是这 6 套的并集。
```

---

## 九、诚实边界

```text
① 本轮只做静态扫描 (源码 + 类名 + 方法 + 常量), 未运行任何仓库的测试。
   "有真写符号" ≠ "生产真在写" —— 这需要各仓库的运行时数据, 本轮未取。
② 顺序判定用正则序列匹配, 可能漏掉跨函数/跨文件的顺序。
   但"影子符号 96 vs 其它 ≤5"这个差距足够大, 不因正则误差而反转。
③ 5 个仓库 (PPT.SKILL/PPTPRO.SKILL/CIP-KaoKaoJiang/hermes-kanban-cip/prometheus-v9)
   实测无进化代码 —— 它们是技能包/空仓库, 不是"进化设计缺失"。
④ ★ 复核修正: ARSI 也有 1 处 "apply→observe" 序列 (初稿误写为"只有 SYNTHEX")。
   ★ 已逐行核实 (ARSI/src/arsi/harness/drawback.py:169):
     `"""Retire non-positive marginals after grace; promote shadows that raise A_dev."""`
     这是 **drawback op 的生命周期** (shadow→active→retired), 判据是 marginal>0,
     与"影子期/先落后测"无关 —— 是命名巧合, 非影子机制。
   ⇒ 修正后: "先落后测"序列真正只有 SYNTHEX 一个 (4 处), ARSI 0 处。
⑤ 影子符号 107 处总量中 SYNTHEX 占 96 (90%) —— 是"高度集中", 不是"普遍存在"。
④ prometheus-v10/v9pro/Prometheus-Omega-Genesis/Protogonos 在 GitHub 上 readme 为空,
   本轮用源码扫, 补上了之前 _all.json 的缺口。
```

---

## 附：存证位置

```text
源码:  E:/Divine Wisdom Core/.cache/gh_clones/<repo>/     (39/39)
元数据: .cache/gh_repos.json                              (GitHub API 39 条)
扫描:  .cache/evolution_scan.json                          (维度计数)
       .cache/evolution_struct.json                        (模块结构)
       .cache/evolution_design.json                        (设计意图 991 行)
       .cache/evolution_order.json                         (★ 顺序判定)
       .cache/write_vs_propose.json                        (真写 vs 只提案)
       .cache/evolution_objects.json                       (进化对象)
脚本:  scripts/clone_all_repos.sh / scan_evolution*.py / scan_gates_apply.py
       / deep_read_designs.py / scan_write_vs_propose.py / scan_lists.py
```
