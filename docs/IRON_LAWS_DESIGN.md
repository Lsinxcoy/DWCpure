# DWC · `iron_laws`（铁律）设计

> 2026-10-03 · 判据：ARSI iron_laws.py / enforced_laws.py 逐行实测 + grep 调用点 + 论文原文
> 定位：原则 1（判据在系统之外）与原则 6（器官只经接口）的**守卫层**
> 前置：`ARCHITECTURE.md` §4.6（原 618 字符）· `docs/JUDGE_LAYERS.md` · `docs/EVOLUTION_CORE_V2.md`

---

## 一、先说结论

```text
★ ARSI 有五处硬缺陷, 最严重的一条是: **有两套铁律实现, 生产用的是弱的那套**。

  ┌─ iron_laws.py    IronLaws          ← ★ core.py 用的是这套
  │    · _check_law 只实现 2/10 (G10 和 G3), 其余 8 条 default: return False
  │    · violated() 只检查 severity=="block" 的 4 条, 6 条 warn **从不检查**
  │    · G10 的判据读 state.sealed_tasks_accessible —— ★ 全仓无人设置该属性
  │      (只有 tests/test_integration.py:217 设它) ⇒ G10 检查**永不触发**
  │    · validate_policy **全仓 0 调用**
  └─ enforced_laws.py EnforcedIronLaws  ← ★ 只有 tests 用
       · G5/G6/G10 是**真实现** (会 raise IronLawViolation)
       · 但生产代码从不 import 它

★ 结果: 生产里 10 条铁律实际生效的是 **0 条**。
  · G3 读了 state.frozen, 但没人设 frozen ⇒ 永不违规
  · G10 读了 sealed_tasks_accessible, 但没人设 ⇒ 永不违规
  · 其余 8 条 default return False ⇒ 永不违规
  ⇒ "∀ reachable S, ∀ operator U: G(U(S)) = G(S)" 这条不变式
    在代码里是**空转**的 —— 因为 G 恒为"无违规"。
```

---

## 二、ARSI 铁律的完整实测

### 2.1 两套实现的对照（逐行核实）

| 维度 | `iron_laws.py` IronLaws | `enforced_laws.py` EnforcedIronLaws |
|---|---|---|
| 谁在用 | ★ **core.py:208**（生产） | 只有 `tests/test_enforced_laws.py` |
| G5 客观效用锚 | ✗ 无实现 | ✓ `check_effect_range` + `check_no_self_eval` |
| G6 熔断 | ✗ 无实现 | ✓ 完整状态机 CLOSED/OPEN/HALF_OPEN |
| G10 密封评估 | △ 读了永不存在的属性 | ✓ `check_access` + `check_release_gate` |
| 其余 7 条 | ✗ `default: return False` | ✗ 也没实现 |

```python
# iron_laws.py _check_law 全文 (这是"铁律执行器"的全部执行逻辑)
    def _check_law(self, law: IronLaw, state: Any) -> bool:
        """Check a specific law against state. Returns True if violated."""
        # G10: sealed evaluation must not be readable by any mechanism
        if law.id == "G10":
            return self._check_g10(state)
        # G3: freeze switch
        if law.id == "G3":
            return getattr(state, "frozen", False)
        # Default: no violation
        return False
```

```text
★ 十行代码, 管十条铁律。八条走 default return False。
★ 注释写 "Default: no violation" —— 诚实, 但等于**这八条铁律不存在**。
```

### 2.2 ★ 缺陷清单（五处，全部带行号）

```text
缺陷 1 · 两套实现, 生产用弱的
   iron_laws.py:1-10  docstring 说 "Iron Laws executor — G1-G10"
   实际: 只有 2/10 有分支, 且两条都读不到值
   enforced_laws.py 的真实现只有测试用
   判据: grep "EnforcedIronLaws" → 除定义外只有 tests/test_enforced_laws.py

缺陷 2 · warn 级从不检查
   violated() 原文: if law.severity == "block" and self._check_law(law, state)
   ★ 6 条 warn (G1/G2/G4/G7/G8/G9) 在**任何路径**下都不会被检查
   ⇒ "warn" 实际含义 = "不存在"

缺陷 3 · ★ G10 的判据读一个不存在的属性
   iron_laws.py:110  if hasattr(state, "sealed_tasks_accessible"):
   ★ 全仓搜索: 只有 tests/test_integration.py:217 设置该属性
   ⇒ 生产里 hasattr 恒 False ⇒ _check_g10 恒 return False ⇒ G10 永不触发
   ★ 而 G10 是 severity=block 的 —— 最该拦的一条, 拦不住。

缺陷 4 · validate_policy 全仓 0 调用
   grep "validate_policy" → 只有定义处 (iron_laws.py:114)
   ⇒ 预算集中度检查从未执行

缺陷 5 · ★ 标签错标
   iron_laws.py:127  raise IronLawViolation(f"G10: budget allocation too concentrated ...")
   ★ 预算集中度是 G2 (分级安全门) 的事, 不是 G10 (密封评估层)。
   ⇒ 违规日志会误导归因 —— 看到 "G10" 会去查密封评估, 实际是预算问题。
```

### 2.3 配置与代码的对齐（ARSI 的 config/iron_laws.yaml）

> ★★ **2026-10-04 澄清**：下面这份 yaml 属于 **ARSI**，路径是
> `.cache/gh_clones/ARSI/config/iron_laws.yaml`（809 字节，全文已核：G1–G10，block 4 / warn 6）。
> **DWC 的 `config/` 目前是空的** —— 本节描述的是"ARSI 侧的参照物"，不是 DWC 已有物。
> ⇒ DWC 自己的 `config/iron_laws.yaml` 尚未创建；新建草案见 `docs/IRON_LAW_G11.md` §十。


```yaml
# 10 条, severity 分布: block 4 (G3/G5/G6/G10) / warn 6 (G1/G2/G4/G7/G8/G9)
- id: G5
  name: 客观效用锚
  description: 效果在-1到+1之间，机制禁自评
  severity: block
```

```text
★ 配置侧是对的 (10 条齐, severity 分级合理)。
  问题全在**执行侧**: 4 条 block 里只有 2 条有分支, 且那 2 条读不到值。
  ⇒ 4 条 block 实际生效 0 条。
```

### 2.4 另一处: `IronLaw` 模型有个从未使用的字段

```python
class IronLaw(BaseModel):
    id: str
    name: str
    description: str
    check_fn: str = ""       # ★ name of the check function
    severity: str = "block"  # block | warn
```

```text
★ check_fn 字段存在但**从未被使用** ——
  _check_law 用的是硬编码的 `if law.id == "G10"`, 不是 check_fn。
⇒ 设计意图(配置声明检查函数名, 执行器按名调用)与实现(硬编码 if)不一致。
★ 这正是 DWC 要修的核心: 铁律应该是**数据驱动的**, 不是硬编码的。
```

---

## 三、论文给铁律的六件事

### 3.1 ★ 非补偿四判据（2609.24972 §3.3）—— 铁律的形态

```text
论文反复强调 "**non-compensatory** criteria" —— 每一项独立否决, 不能用别的项补偿。
"这是与 HarnessX seesaw 式门的关键差别。"

(1) Leakage Screening（泄漏筛查）
    在**完整评估之前**, critic 读每个候选 diff, 拒绝
    "edits that explicitly encode task names, entity names, task-specific values,
     answers, or other logic specific to the evolve benchmark"
    ★ 前置理由 (原文): "a leaking candidate never receives the inflated
      evolve-set score that could make it attractive to subsequent rounds."

(2) Stability-Aware Acceptance（稳定性门）
    演化前**反复评估未改动的 base harness** 估计经验噪声带 δ
    判据: Ŝ(H') ≥ S⋆ − δ
    ★ 原文: "The floor prevents the search from walking downhill through a
      sequence of regressions that are individually small enough to be
      mistaken for noise."

(3) 成本—收益门
    ΔS = Ŝ(H') − Ŝ(H_t);  ΔC = (Ĉ(H') − Ĉ(H_t)) / Ĉ(H_t)
    对 ΔS > δ 的候选: 要求 ΔC ≤ β₀ + β₁·ΔS
    ★ β₀/β₁ 在 evolve set 上选定后**对所有 transfer 评估固定不变**

(4) 结构剪枝
    ℬ_t = { ℓ ∈ 𝒯_t : g_t(ℓ) ≤ 0 } —— 最近剪枝窗口内没产生严格正收益的组件标为删除目标
    ★ 原文: "a mechanism must continue to earn its place rather than persist
      simply because score-only evolution has no incentive to remove it."
```

**★ 噪声带内的可接受性（式 17，Appendix 提到，正文没有）**：

```text
w_s·ΔS − w_c·ΔC + w_n·ν_t(H') > 0,   w_s, w_c, w_n ≥ 0

★ 含义: 当 ΔS ≤ δ 时, 成本收益门不适用, 改用带新颖度奖励的线性打分。
  ⇒ **噪声带内的微小提分本身不足以让候选被接受**,
    必须靠降成本或靠"首次尝试某类结构机制"来换取接受。
★ coding instance 设 w_s = 0 —— "a score increase that remains within δ
  cannot by itself make a coding candidate admissible"
```

**★ DomainGuard（域特定的非补偿守卫）**：

```text
· coding / agentic-workspace: g ≡ 1, 无额外守卫
· engineering-design: valid-output rate 相对 incumbent 下降 > **0.03**,
  或 no-submission rate 上升 > **0.02**, 直接拒绝
★ 原文: "These guards prevent a gain in the primary pass-rate objective from
  compensating for a substantial degradation in basic execution validity."
```

### 3.2 ★ 五条停止规则（2603.06333 §2.7）—— 约束违反绝对优先

```text
1. 连续三次迭代质量变化 < 0.01
2. 回归风险超过校准阈值
3. ★ 任一周期约束保持为 0
4. 达到最大周期数
5. GDI 超过校准阈值

★ "约束违反绝对优先" —— 第 3 条优先级最高。
```

### 3.3 ★ 回归风险（2603.06333 §2.5，全文最可复用的一段）

```text
R_c = Pr( 𝒬_c < 𝒬_max − δ | H_c ),   H_c = {𝒬_0, …, 𝒬_{c−1}}     (18)

三个统计量:
  Volatility:  σ = std(H_c)                                        (19)
  Trend:       最小二乘拟合 𝒬̂_t = α + β·t                          (20)
  Vol-norm gap: z = (𝒬_c − 𝒬_max)/(σ + ε)                          (21)
                "how many standard deviations the current value lies below
                 the historical peak"

高斯近似: R_c ≈ Φ( (𝒬_max − δ − 𝒬̂_{c+1}) / σ )                    (22)
趋势校正: R_c^adj = min{ 1, R_c + 1{β < −ε_trend}·λ·|β| }          (23)
决策: R_c^adj > τ_R 告警并考虑暂停
```

**★ 长时程稳定性界（D.5, Eq.24）—— 这个数字很有说服力**：

```text
若每周期增量 Δ𝒬_i ~ N(μ, σ²) 独立同分布,
则"未来 c 个周期全部为正增量"的概率 = (Φ(μ/σ))^c

★ 论文举例: 每周期 0.6 的改进概率, 10 周期后 0.6^10 ≈ **0.00605 (约 0.6%)**
⇒ ★ 这条直接说明: "每轮都小改进"在长时程上**几乎必然中断**。
  所以不能只靠"每轮涨一点", 必须有结构性的、可归因的机制。
```

### 3.4 ★ CAR 能力对齐比（2603.06333 §2.6）

```text
CAR_c    = (𝒬_c − 𝒬_0) / GDI_c                                    (25)
CAR_inc,c = (𝒬_c − 𝒬_{c−1}) / (GDI_c − GDI_{c−1})                  (26)

★ E.3 决策规则:
  CAR_inc,c 大  → 继续
  CAR_inc,c 小或为负 ("drift without improvement") → 停止或回滚
★ 实施注记: 分子分母用 EMA 平滑; 分母加下界 ε 防数值不稳;
  与回归风险合成复合停止规则。
```

### 3.5 ★ FROZEN_DIMS + scope fence（2606.14249）

```python
# arsi/harness/taxonomy.py 原文
FROZEN_DIMS = frozenset({"c7"})

def _scope_fence(d):
    """Scope fence: frozen dims and frozen modules reject edits."""
    if d in FROZEN_DIMS:
        return False, f"frozen_dimension:{d}"
```

```text
★ 这是铁律在**进化对象层**的落地: c7 (control/safety) 永不成为进化目标。
★ 形态值得抄: 不是"检查有没有违规", 而是**在入口直接拒绝**。
```

### 3.6 ★ 契约 + fallback（2603.25111 §2.2）

```text
FGGM: requires Φ_l(x1,…,xn) { for i=1..K { y := L_Θ(p); if check(...) return y }
                              return f_d(x1,…,xn, y_f) }
★ ★ fallback 本身也必须满足同一条契约 (validateFGGM 第 26 行)
★ 四条性质: Flexibility / Parameter-Independent Correctness /
            Local Learning Objective / fallback 的必要性
```

---

## 四、DWC 的 iron_laws 设计

### 4.1 ★ 核心裁决：从"硬编码 if"改为"数据驱动 + 可触发"

```text
★ ARSI 的病根: 铁律是**硬编码的 if 链** (if law.id == "G10": ...),
  而配置里有个从未使用的 check_fn 字段 —— 设计意图与实现脱节。

DWC 的修法: 铁律 = **数据** (声明) + **检查器** (实现) + **触发点** (接线), 三者必须闭合。

  iron_laws/
    ├─ laws.yaml          声明 (人可改, 系统只读)
    ├─ registry.py        按名解析 check_fn → 检查器
    ├─ checks/            检查器实现 (一条铁律一个文件)
    │   ├─ g1_design_exec_separation.py
    │   ├─ g2_tiered_gate.py
    │   ├─ g3_freeze_sovereignty.py
    │   ├─ g4_audit_trigger.py
    │   ├─ g5_utility_anchor.py
    │   ├─ g6_circuit_breaker.py
    │   ├─ g7_lyapunov.py
    │   ├─ g8_causal_accountability.py
    │   ├─ g9_high_entropy.py
    │   └─ g10_sealed_layer.py
    └─ hooks.py           ★ 触发点登记 (哪条铁律在哪个阶段被调用)

★ 三条闭合判据 (机械可检查):
  ① 每条铁律在 checks/ 里有对应文件          (禁 default return False)
  ② 每条铁律在 hooks.py 里有触发点            (禁"定义了但从不调用")
  ③ 每个检查器读的字段, 有设置方               (禁"读不存在的属性")
```

### 4.2 ★ 修缺陷 3：可触发性的机械判据

```text
★ ARSI 的 G10 读 state.sealed_tasks_accessible, 但没人设它 ⇒ 永不触发。
  这个病**很难用肉眼发现** —— 代码看起来完全正确。

DWC 的判据 (写进 gate.py, 这是本条最重要的产出):

  I3 · 每个检查器读的字段必须有设置方
     判据: 对每个 checks/*.py, 提取它读取的 state 字段名;
           在全仓搜索该字段的**赋值点**;
           若赋值点 = 0 ⇒ 违规 (该铁律永不触发)。
     ★ 这条能机械抓出 ARSI 的缺陷 3。

  ★ 更进一步的判据: 每个检查器必须有一个**会触发它的测试**
    (喂一个故意违规的 state, 断言 raise)。
    判据: 对每个 checks/*.py, 存在测试文件调用它并断言违规。
    ★ 只测"不违规"是不够的 —— ARSI 的 test_foundation.py:187
      就是 `assert laws.violated(FakeState()) is False` (只测不违规)。
```

### 4.3 ★ 修缺陷 2：warn 级必须被检查

```text
★ ARSI 的 violated() 只检查 severity=="block" ⇒ warn 永不检查。

DWC 的修法: warn 与 block 的区别是**后果**, 不是**是否检查**。
  两者都必须被检查, 区别在于:
    block → 抛异常, 阻断操作
    warn  → 记审计日志 + 计数, 不阻断
  ★ 判据: 检查器返回三值, 不是布尔:
    PASS     合规
    WARN     违规但可继续 (记日志)
    BLOCK    违规且必须阻断 (抛异常)
  ⇒ violated() 改为 check_all(state) → {pass: [...], warn: [...], block: [...]}
```

### 4.4 ★ 修缺陷 5：标签必须与内容对齐

```text
★ ARSI 的 validate_policy raise "G10: budget allocation too concentrated"
  —— 预算集中度是 G2 的事。

DWC 的判据 (I4):
  · 每个 raise 的标签必须与该检查器**声明的铁律 id** 一致
  · 判据: 检查器文件 g2_*.py 里 raise 的消息必须以 "G2" 开头
  · 机械检查: 正则匹配 raise.*f?"(G\d+): 提取 id, 与该文件名比对
```

### 4.5 ★ 修缺陷 1：只许一套实现

```text
★ ARSI 有两套 (iron_laws.py 弱 / enforced_laws.py 强), 生产用弱的。

DWC 判据 (I5):
  · 全仓只许有一个 IronLaws 类
  · 判据: grep "class .*IronLaw" 的结果数 == 1
  · 且: 生产入口 (core.py) import 的必须是它
    (判据: core.py 的 import 与 tests 的 import 是同一个模块)
```

### 4.6 十条铁律的可执行化（逐条定 check_fn）

```text
★ 每条给出: 检查什么 / 触发点 / 判据 / 论文依据

G1 设计/执行分离    策略生成与突变落地解耦              warn
   check: 提案模块 (m) 与落地模块 (applier) 不得是同一个类/文件
   触发点: 落地前
   判据: m.__class__ is not applier.__class__ 且不同模块
   依据: GAI Figure 2 authority boundary

G2 分级安全门      层级越深阈值越高                    warn
   check: 每层的门槛参数必须随层深单调不减
   触发点: 配置加载时
   判据: for i<j: threshold_i <= threshold_j
   依据: 2609.24972 非补偿判据 (每层独立否决)
   ★ 并吸收 ARSI 错标的那条: 预算集中度检查 (max_alloc > 0.8 → 违规)

G3 冻结/人类主权    冻结开关优先级高于所有进化           block
   check: freeze 开关为真时, 任何写操作必须被拒
   触发点: 每个写操作入口
   判据: frozen ⇒ raise (不是 return False)
   ★ 修 ARSI: frozen 字段必须有设置方 (人工 CLI / 配置文件)
   依据: 2606.14249 FROZEN_DIMS + scope fence

G4 审计触发        巩固须含 why/trigger/verify         warn
   check: 每条巩固记录必须含三个字段
   触发点: memory 的 consolidate 出口
   判据: {why, trigger, verify} ⊆ record.keys()
   依据: DWC 记忆核心 (七管 maintain)

G5 客观效用锚      效果 ∈ [-1,+1], 禁自评              block
   check: effect 范围 + 来源白名单
   触发点: 每次 effect 写入
   判据: -1 <= effect <= 1 且 source ∈ EXTERNAL_SOURCES
   ★ 抄 ARSI effect_anchor 的白名单 (这是 ARSI 做对的一件事)

G6 熔断            CLOSED/OPEN/HALF_OPEN 状态机        block
   check: 失败超阈值 → OPEN; 冷却后 HALF_OPEN
   触发点: 每次外部调用
   ★ 抄 ARSI enforced_laws.py 的实现 (它是真实现)

G7 数学收敛        Lyapunov 函数单调下降               warn
   check: V(s_{t+1}) <= V(s_t)
   触发点: 每轮 run_term 末
   判据: 违反次数 / 总轮数 <= 容忍率
   依据: 2603.06333 Eq.24 (长时程稳定性界)

G8 因果问责        假设→设计→结果因果链完整才激活       warn
   check: 提案必须含 {hypothesis, design, result} 三段
   触发点: 提案过门时
   判据: 三段齐备且有可追溯 id
   依据: 2609.24972 结构剪枝 (机制必须持续赢得位置)

G9 高熵校验        高熵记忆和决策主动生成验证请求        warn
   check: 熵 > 阈值时, 必须产生验证请求
   触发点: 记忆写入 / 决策时
   判据: entropy > τ ⇒ verify_requests 计数 > 0
   依据: DWC 记忆核心 (原则 9 高熵校验)

G10 密封评估层     任务集/评分规则/发布门槛在写掩码之外   block
   check: 路径保护 + 发布门
   触发点: ★ 每次读写密封路径 / 每次发布
   判据: ★ 与 ARSI 的关键差别 —— 不是读一个属性, 而是
         **在 seal 的每个入口强制调用** (见 JUDGE_DESIGN §4.2)
   依据: 2603.25111 FGGM 契约 + 2607.12790 "never a training signal"
```

### 4.7 ★ 新增：铁律与"停止规则"的分工

```text
★ 论文 2603.06333 §2.7 的五条停止规则, 与铁律**不是一回事**:
  铁律    = 永恒约束 (G1-G10), 不变式, 只有人能改
  停止规则 = 运行期熔断 (本轮该不该继续), 由参数校准

DWC 的分工:
  iron_laws/  → G1-G10 (永恒约束)
  evolver/    → 停止规则 (运行期):
    ① 连续三次迭代质量变化 < 0.01
    ② 回归风险 R_c^adj > τ_R          (2603.06333 Eq.23)
    ③ ★ 任一周期约束保持为 0          (优先级最高)
    ④ 达到最大周期数
    ⑤ GDI > 校准阈值
  ★ 第 ③ 条把两者连起来: 铁律违反 ⇒ 立即停止 (约束违反绝对优先)
```

### 4.8 ★ 新增：不变式的验证方式

```text
★ ARSI 的不变式: ∀ reachable S, ∀ operator U: G(U(S)) = G(S)
  —— 写得很漂亮, 但代码里 G 恒返回"无违规" ⇒ 空转。

DWC 怎么**验证**这条不变式 (不能只声明):
  ① G 的配置哈希在每次 run_term 前后必须相同
     判据: hash(laws.yaml) 前后一致, 且不出现写入
  ② 每个检查器的代码哈希在一轮内不变
  ③ ★ 且: 用"故意违规的 state"喂每个检查器, 断言它 raise
     ⇒ 证明检查器**有能力**违规, 不是恒真

★ 判据 (I6): 每个检查器必须有"阳性测试" (喂违规 state 断言 raise)
  + "阴性测试" (喂合规 state 断言 pass)。
  只有阴性测试 = 检查器可能是恒真的 (ARSI 的 test_foundation.py:187 就是)。
```

---

## 五、可机械检查的判据（gate.py 候选，8 条）

```text
I1 · 每条铁律有实现
   laws.yaml 的每条 id, 在 checks/ 里有对应文件
   依据: ARSI _check_law 只实现 2/10

I2 · warn 也被检查
   check_all() 必须同时返回 pass/warn/block 三组
   依据: ARSI violated() 只检查 block

I3 · ★ 检查器读的字段有设置方
   每个 checks/*.py 读取的 state 字段, 全仓赋值点数 > 0
   依据: ARSI G10 读 sealed_tasks_accessible, 设置点 0

I4 · 标签与内容对齐
   raise 的 "G\d+:" 前缀必须与检查器文件名一致
   依据: ARSI 在 G10 标签下 raise 预算集中度 (实为 G2)

I5 · 只许一套实现
   grep "class .*IronLaw" 结果数 == 1
   且 core.py 与 tests import 同一模块
   依据: ARSI 两套 (弱/强), 生产用弱的

I6 · ★ 每个检查器有阳性测试
   存在测试: 喂故意违规的 state, 断言 raise/block
   依据: ARSI test_foundation.py:187 只测"不违规" ⇒ 恒真无法被发现

I7 · 不变式可验证
   laws.yaml 的哈希在 run_term 前后一致
   依据: ARSI 不变式在代码里空转

I8 · 铁律配置在写掩码之外
   laws.yaml 路径出现在 seal 的保护列表里
   依据: ARSI 有 register_protected_path("config/iron_laws.yaml")
        但 check_access 调用点 0 处 ⇒ 保护形同虚设
```

---

## 六、诚实边界

```text
① ARSI 的铁律我做的是静态审计 (读两个文件全文 + grep 全部调用点), 未运行它。
   五处缺陷的判据都是 grep 结果或逐行原文, 已在 §2.2 标注行号。

② "生产里 10 条铁律实际生效 0 条" 是**静态推断**:
   依据是 (a) _check_law 只实现 2/10; (b) 那 2 条读的字段无设置方;
   (c) violated() 只检查 block。
   ★ 未验证的部分: 若有动态注入 (setattr / getattr 变体) 会漏。
     已用两种口径查过 (grep 属性名 / grep 属性名的赋值), 结论一致。

③ G1-G10 的十份 check_fn 规格 (§4.6) 是我写的 —— 论文没有直接给
   "G1 应该检查什么"这种映射。★ 我的映射依据是铁律的名字与描述
   (config/iron_laws.yaml 原文), 加上对应论文的机制。

④ 2603.06333 的停止规则 (5 条) 与铁律 (10 条) 的**分工**是我的设计 ——
   论文把两者混在"约束"这个概念下, 没有明确分层。

⑤ ★ G7 (Lyapunov 单调下降) 我给的判据是"违反次数/总轮数 <= 容忍率" ——
   但容忍率取多少**未定**。严格单调在噪声环境下会恒违规。

⑥ 不变式的验证方式 (§4.8) 需要"喂故意违规的 state" —— 但 state 是什么类型
   **未定** (ARSI 是 Any, DWC 尚未定 state 的 schema)。★ 这是留给下一轮的缺口。
```

---

## 附：存证

```text
ARSI 源码: src/arsi/foundation/iron_laws.py (4,764 字符, 全文核过)
           src/arsi/foundation/enforced_laws.py (9,024 字符, 全文核过)
           src/arsi/governor/core.py:171 (唯一的 violated() 生产调用点)
           config/iron_laws.yaml (10 条, severity: block 4 / warn 6)
           tests/test_foundation.py:187 (只测"不违规")
           tests/test_integration.py:217 (唯一设置 sealed_tasks_accessible 处)
论文报告:  docs/papers/2609.24972.md §2.3 (非补偿四判据) / §2.4 (式17 + DomainGuard)
           docs/papers/2603.06333.md §2.5 (回归风险 Eq.18-24) /
                                    §2.6 (CAR) / §2.7 (五条停止规则)
           docs/papers/2606.14249.md (FROZEN_DIMS + scope fence)
           docs/papers/2603.25111.md §2.2 (FGGM + fallback 契约)
前置文档:  docs/JUDGE_DESIGN.md · docs/JUDGE_LAYERS.md · docs/EVOLUTION_CORE_V2.md
```

```text
★ 本文引用的 iron_laws.py 行号 (逐行核实):
   L29   check_fn 字段 (从未使用)
   L90   violated() 只检查 severity=="block"
   L98   if law.id == "G10"
   L101  if law.id == "G3"
   L103  # Default: no violation  (八条走这里)
   L110  hasattr(state, "sealed_tasks_accessible")  ← 全仓无设置方
   L114  def validate_policy  ← 全仓 0 调用
   L127  f"G10: budget allocation too concentrated"  ← 错标 (实为 G2)
```

---

## 附·二 · 2026-10-04 增补：铁律 G11

```text
★ 新增第十一条: G11「门通过 ≠ 系统安全」
  完整设计见 docs/IRON_LAW_G11.md
  · severity=meta（不是 block/warn —— 它没有可违反的状态）
  · enforcement=report_must_quote（唯一的执行形式: 每份门报告必须引用限定语）
  · 判据 I9–I12: 检查器不可被进化对象触及 / 缺 certification_limit 报告无效
    / 缺 proxy_target 报告无效 / 版本换代旧报告视为无效
  依据: 2603.25681 §8.1「An evaluation that reads as safe therefore cannot certify
        that the self-improvement system is actually safe」
★ 与 G5 的区别: G5 管"机制不得自评"(对象=机制); G11 管"门结论不可外推"(对象=门的效力)
★ 与 §9 第 20 项的关系: 同源不同向 —— 第20项保证判据不作弊, G11 保证不作弊的
  判据也不能被当成安全证明。两者必须同时存在。
