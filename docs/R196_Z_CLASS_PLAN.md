# R196 · Z 类 6 项全落地方案（用户令"我想把这六类全部落地 深度思考 给我一个方案"）

日期: 2026-10-12 · 前置: R195(git 206, pytest 1355) · **本文件是方案，未动一行代码**

---

## 〇、先纠三处**我自己账上的错**（这决定方案的正误）

本轮取证（打开 57 篇 woff 逐篇 regex）发现 R193 对账的**第三、第四次误判**——不是"漏判"，
是**引错论文**：

| R193 原记 | 实测 | 性质 |
|---|---|---|
| dual ← 2606.06350 "privacy" | 该论文的 `privacy` 指 **Private-Science 数据集许可**（数据不可公开），**不是**"公开/私有两套动作空间"的机制。57 篇全文 **grep `public[- ]private` = 0 命中** | **出处错** |
| state ← 2609.06396 "(𝒟,θ,𝒽) 三元组" | 该论文的 `𝒟` 是 **数据集 dev set**（`𝒢_fixed(ℳ⁺;x,𝒟_dev)`），**不是世界状态三元组**；`θ/𝒽` 在该论文无此三元组。57 篇 **grep `world state` 仅命中 DWC 自己的 `_snapshot_worlds`** | **出处错** |
| coupling ← "2608.10299 三条件是多机制前提" | ✅ 这条**对**：Stage1/2/3 taxonomy 逐字在场（§2.3 Figure 2），Stage 3 判据"机制修订必须由下层联合轨迹诱导"逐字在场（§5.1） | 引用正确 |

⇒ **推论（本方案的地基）**：

> dual / state / freshness 三项，**在 DWC 已落档的 57 篇里没有论文依据**。
> 它们不是"论文有据但搬不动"，是**没有论文据**。
> 按 R73「无据不发明」+ 用户"六类全部落地"的指令，正确形态只能是：
> **DWC 自定义能力**，且**必须显式标注"无论文依据"**——不许冒充论文机制。

这一条比"做不做"重要得多：**冒充论文依据 = 假声称 = G5 声称门要拦的东西**。

---

## 一、六项分三类，落地形态各不相同

### 甲类 · 有论文据，可**照搬机制**（2 项）

#### A1 `coupling` —— 2608.10299 §2.3 三阶段 taxonomy（唯一硬据）

论文原文三段递推（本方案逐字引用，不再转述）：

```text
Stage 1 Agent–Agent    A^{t+1} = ({a_i^{t+1}}_{i=1..n}, Π^{t+1}) = Ω(A^t, E, τ^t)
                       环境固定，"Co-evolution begins when an agent no longer
                       learns against a static counterpart"
Stage 2 Agent–Environment  (A^{t+1}, E^{t+1}) = Ω(A^t, E^t, τ^t)
                       "When the environment remains fixed, it limits the new
                        experiences and pressures"
Stage 3 Meta           Ω^{t+1} = Γ^t(S^t, Ω^t, τ^t), then S^{t+1} = Ω^{t+1}(S^t, τ^t)
                       "In Stage 2, the evolution mechanism remains human-designed,
                        so the system can change its contents but not how they change"
```

**DWC 现状定位（实测）**：DWC 现在在 **Stage 0**（论文 taxonomy 之前）：
judge/metric_loop/direction/evolver 四机制**各管一段，互不触发**——
metric 选出新 op 不会让 direction 重排 fallback 序；direction 换向不会让
metric 重估树。**单机制、单向、无 mutual adaptation**。

**落地形态（R196-A）**：`src/dwc/harness/coupling.py` —— **机制间压力传播面**

```python
#: 只登记"谁给谁压力"的边，不产生压力本身（G2: 判据在别处）
COUPLING_EDGES: Tuple[Tuple[str, str, str], ...] = (
    ("metric_loop",  "direction",  "op_verdicts_changed"),
    ("direction",    "metric_loop", "direction_switched"),
    ("evolver",      "judge",      "proposal_landed"),
    ("judge",        "evolver",    "verdict_distribution_shifted"),
)
def pressures_from(subsystem: str) -> List[Tuple[str, str]]
def decoupled_pairs() -> List[Tuple[str, str]]   # 尚未登记的边 ⇒ 如实报 Stage 0
def stage_of(dwc_edges) -> int                   # 0/1/2/3 的**记账**判定（不是能力判定）
```

★★★ **四条边界（防止做成假的）**：
1. **只记账不触发**——第一版绝不自动调用对方。压力传播=**写入 ledger + 由既有
   `_dir_ledger_append` / `credit_entries` 消费**。自动触发是 Stage 1 的行为，
   得先有 Stage 0 的账才谈得上（不跳级）。
2. **不新增常量表**（A1 纪律，R194 vocabulary 同款）：边表是**登记**，不是判据。
3. **`stage_of` 返回的是"账记账到第几阶段"，不是"系统有多先进"**——DWC 自报
   `stage_of(...) == 0` 是**如实的**，不是缺陷（论文说 "Only limited work
   currently meets our definition of Stage 3"）。
4. **测试锁**：`decoupled_pairs()` 非空 ⇒ 断言其**原因串**含"Stage 0"（防将来
   有人把边表填满就自报 Stage 3）。

#### A2 `quintuple` —— R193 结论对但记得太浅，**补机械验收**

实测（run_term.py:458）：`Quintet(m/rho/pi/V/U)` **5 项全有填值**：
`m`=wire_and_memory ✅ · `rho`=config/dials.yaml ✅ · `pi`=Evolver ✅ ·
`V`=Judge ✅ · `U`=`select_winner` **已实现但未接本盘点**（R141 如实标 partial）。

**落地形态（R196-B）**：**不新写盘点**（那会成第二口径），只做两件事：
1. 把 R141 的 partial 判定**升级为机器可测**：`Quintet.to_dict()` 已有
   `unimplemented` / `partial` 双列表（R141 就写了）⇒ 测试锁
   `partial == ["U"]`（**U 是唯一 partial，不许变多也不许消失**——变了说明
   有人接线或有人删，都得显式）。
2. 在 `docs/` 注明：`run_term.py:458` 是**唯一盘点出口**（防第二口径）。

---

### 乙类 · 无论文据，按 **DWC 自定义能力**落地，显式标注（3 项）

★★★ 共同纪律：三者的 docstring **第一行必须写"无论文依据（R193 引错出处已更正）"**，
且**不许出现"论文说"字样**。这是 G5 声称门的延伸。

#### B1 `state` —— DWC 自定义"轮次状态投影面"

不是搬 𝒟/θ/𝒽（那个出处本身是错的）。做的是 R194 已经铺好一半的东西：
16 个 `_last_*` 痕迹是**单轮快照**，缺的是**跨轮序列的机械面**。

```text
src/dwc/harness/trajectory.py
  snapshot(loop) -> dict         # 从 Loop._last_* 取一次投影（只读, 不判分）
  append(archive_path, snap)     # jsonl 追加（与 direction_ledger 同格式纪律）
  read(archive_path) -> List     # 回读（机械面, 可 diff 可算）
```

**为什么这是真缺口（机器证据）**：现在"R190 的三层洞在 R193 如何被证伪"
这类跨轮问题只能翻 `knowledge3_*.json`（人写的），**没有机器轨迹**。
落了这一条，`archive/trajectory.jsonl` 就是答案。

★★★ 边界：**只投影已登记字段**（`consume_points.CONSUME_POINTS` 的键），
不新增 `_last_*`。新增字段要走 R194 的登记测试（那才是防漂移的门）。

#### B2 `freshness` —— 依附 B1，比 state 更窄

不是"数据新鲜度衰减"（那个更无论文据，且 DWC 无时间衰减的语义）。
做的是**轨迹面的 staleness 记账**：每条 snapshot 记 `gen` 与 `age_rounds`，
`read()` 时能答"最近 n 轮有没有动过"。

★★★ 边界：**不设阈值**（无据可设）。只提供 `age_rounds(gen)` 查询。
判"多久算陈旧"是**调用方的语义**，不是本模块的（G2 同族）。

#### B3 `dual` —— DWC 自定义"双账：声称面 vs 实测面"

不是搬 pub/priv 动作空间（出处错）。但"声称 vs 实测"是 DWC **自己的核心纪律**
（G5 声称门、记忆里的铁律）——把它从"散在注释里的纪律"变成**可机的双账面**：

```text
src/dwc/harness/attestation.py
  claim(round_gen, subsystem, text) -> str        # 登记一条声称（写 archive/claims.jsonl）
  attest(claim_id, evidence_ref, measured) -> None # 挂实测证据
  unattested(round_gen) -> List[dict]              # 声称了但没挂实测的 ⇒ G5 观察面
```

★★★ 边界（**三条硬约束**）：
1. **不是门**——它只做观察面（未挂实测 ⇒ 列出），**不拦合入**。拦合入是 gate 的活，
   再造一个门 = 第三口径。
2. **不许自动生成声称**——声称只能由人或轮次流程显式写。自动造声称然后自己认证
   = 自证预言（R188 已记的坑）。
3. **只对 DWC 自身**：不是给外部系统用的审计框架。

---

### 丙类 · **不是能力，是纪律的显式化**（1 项）

#### C1 `autonomy` —— 不建模块

"autonomy" 是论文的功能**描述词**，不是该有同名模块的东西（R195 刚用它做过
"问法本身错了"的判例——autonomy 是这个判例的第二次）。

DWC 的自主性已在三处**如实记账**，R196 只做**把账汇到一个可查面**：
`run_term` 六层链（run_term.py）+ 三方向自主换向（`_dir_pick_candidates`）+
自链知识档（knowledge3_*.json gen 硬值）。

落地形态 = **在 trajectory.py 的 snapshot 里带 `autonomy_markers` 字段**：
记"本轮哪些自主事件发生过"（换向/全败记账/固化采纳），值全部来自已登记痕迹，
**零新判据零新常量**。

---

## 二、总落地清单（R196，一个提交）

```text
src/dwc/harness/coupling.py        A1  Stage 0 记账面（COUPLING_EDGES + 3 查询）
src/dwc/harness/trajectory.py      B1  轮次状态投影（snapshot/append/read + age_rounds）
src/dwc/harness/attestation.py     B3  声称/实测双账（claim/attest/unattested）
src/dwc/harness/run_term.py        A2  只加注释"唯一盘点出口"（零逻辑改动）
tests/test_r196_z_class_landing.py 六项验收（每项含"无论文据"锁 + 边界锁）
docs/R196_Z_CLASS_PLAN.md          本文件（升级为落地记录）
docs/CODE_DEBT_RECONCILIATION_R193.md  追加"双出处错"更正段
```

**明确不做**（写进文档，防将来越界）：
- 不自动触发跨机制调用（Stage 1 行为，须先跑够 Stage 0 的账 + 用户拍板）
- 不设 freshness 阈值（无据）
- 不新建 autonomy 模块（描述词不是模块）
- 不写 Quintet 第二盘点（唯一出口已在 run_term.py:458）

---

## 三、每项的验收（不测"做了什么"，测"为什么重要"）

| 项 | 关键断言 | 它防什么 |
|---|---|---|
| A1 | `decoupled_pairs()` 非空 **且** 原因串含 "Stage 0"；`stage_of(满边)==3` 也**不得**自报先进 | 边表填满就自吹 Stage 3 |
| A2 | `Quintet.to_dict()["partial"] == ["U"]`（唯一 partial） | 有人改盘点却不知这是唯一出口 |
| B1 | snapshot 的键 ⊆ `CONSUME_POINTS` 的键（**不许新增** `_last_*`） | 绕过 R194 登记面加痕迹字段 |
| B2 | `age_rounds` 不设阈值，只返 int | 无据设阈值 |
| B3 | `unattested()` 列出但**不抛异常、不返回 False**（观察面不是门） | 做成第三道门 |
| C1 | `autonomy_markers ∈ {换向, 全败记账, 固化采纳, ...}` 全来自已登记痕迹 | 造"自主性"新指标 |

---

## 四、风险与我的判断

| 风险 | 我的处置 |
|---|---|
| 六项一次落地会不会太散 | 四个文件都在 `harness/` 同一层，共一个测试文件共一个提交；**共享一份"乙类无论文据"的标注纪律** |
| coupling 边表会不会变成摆设 | 第一版就是摆设——**但它至少把"现在互不触发"这件事变成可数的**（R192 LEGACY 的原话：A 类现在做的第一条就是"consume 显式化"，这是同一条纪律的延续） |
| trajectory.jsonl 会膨胀 | 每轮一行，与 direction_ledger 同纪律（运行产物，`.gitignore` 已覆盖 archive 的 jsonl） |
| attestation 会不会变成"自己给自己开证明" | 三条硬约束 + 测试锁"未挂实测不抛异常"（观察面不是门） |

**一句话**：这一轮不是"把论文机制搬进来"，是**把 DWC 自己已经做对的事变成可机数的账，
并把三处我引错的论文出处诚实更正**。前者是能力，后者是纪律——**纪律不做，前面全是沙**。

---

## 五、待你拍板的两件（不阻塞开工，但影响后续方向）

1. ** attribution：coupling 的边表第一版 4 条边**（metric↔direction, evolver↔judge）。
   你若认为该加/删边，说一声；不说就按这 4 条 + `decoupled_pairs()` 如实暴露缺口。
2. **attestation 的粒度**：按 `(round_gen, subsystem)` 记，还是细到 `(round_gen, claim)`？
   我倾向后者（一条声称一行），因为粗粒度会让人把多个声称打包成一条蒙过去。
