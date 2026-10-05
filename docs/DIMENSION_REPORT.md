# DWC 调研报告 · 你一共设计过多少进化维度

> 底稿：GitHub 43 仓库（41 可读，306 万字符）+ 母巢 186KB/26轮/96条清单 + 本地 E盘 8 仓库
> 核实：关键原文引用已逐条回原文比对
> 日期：2026-10-02

---

## 一、答案：**你设计过 5 套不同的进化维度体系**

不是一套改来改去，是**五条线各自设计了一套**。

| # | 体系 | 维度数 | 出处 | 时间 |
|---|---|---|---|---|
| **D1** | **v6 的 12 层进化架构** | **12** | `prometheus-v6/README.md` | 2026-05 |
| **D2** | Ultra 四轨 | **4** | `Prometheus-Ultra` L1-L4（作者原话：「四轨进化解决"进化什么"」） | 2026-07 |
| **D3** | CIP 分层进化 | **4** | `hermes-collective-intelligence/evolution_layers.py` docstring | 2026-05 |
| **D4** | ARSI 九维 + 双 Ω | **9 + 2** | `ARSI/src/arsi/harness/taxonomy.py` + `unified_credit.py` | 2026-09 |
| **D5** | 母巢 v21 综合清单 | **96 条/6 组** | `SYNTHEX_EVOLUTION_INSIGHTS.md` | 2026-09 |

---

## 二、D1 · v6 的 12 层进化架构（最完整的一次枚举）

**原文**（`prometheus-v6/README.md`「🔄 进化系统 → 12层进化架构」）：

```text
| 层级 | 名称      | 功能        |
|------|-----------|-------------|
| L0   | MetaParams  | 元参数进化  |
| L1   | Strategy   | 策略进化    |
| L2   | Skill      | 技能进化    |
| L3   | Config     | 配置进化    |
| L4   | Code       | 代码进化    |
| L5   | MetaEvolution | 元进化   |
| L6   | Prompt     | 提示词进化  |
| L7   | Tool       | 工具进化    |
| L8   | Memory     | 记忆进化    |
| L9   | Knowledge  | 知识进化    |
| L10  | Collaboration | 协作进化 |
| L11  | Architecture  | ★架构进化 |
```

**同页还有一个正交的 3 方向体系**：

```text
Forward  正向进化 - 优化当前轨迹
Lateral  横向迁移 - 探索替代方案
Reverse  逆向回滚 - 恢复历史版本
```

**★ 这是你唯一一次把"架构进化"和其余 11 个维度并列写进同一张表。**
12 = 1(元参数) + 9(内容层) + 1(协作) + 1(架构)。

### 但它没有活下来

```text
v7  README 同一位置换成: L0 MetaParams / L1 Strategy / L2 Direction / L3 Selection /
      L4 Mutation / L5 Crossover / L6 Fitness / L7 AST / L8 Validation /
      L9 Memory / L10 Quota / L11 ReasoningBudget
      ★ 12 个"进化对象"变成了 12 个"进化机制"
      ★ Architecture 消失
    v7 对外宣称「统一引擎，12/12层完整」—— 补齐与移除同时发生，README 无一字说明

v9  教训表第一行「12层进化10层空壳 | V3-V6 | 只实现4层进化」
      L11 架构进化 正是那 12 层之一
      L11 被改写成: L3: ArchitectureHealth — 代码架构健康监控
      产出是「超阈值触发修复建议」—— 测，不是改
```

---

## 三、D2 · Ultra 四轨

**原文**（`Prometheus-Ultra`，全仓唯一一处把「进化什么/进化落在哪」对举成术语）：

```text
T1 参数
T2 语义
T3 GitHub机制
T4 论文机制

同文自陈: 「四轨进化解决了'进化什么'，但没解决'进化落在哪'」
```

**后期立场修订**（`Prometheus-Ultra-MultiTypeKB/docs/v2_host_agnostic_evolution.md`）：

```text
「Ultra 不再"为自身进化"，而是"为宿主 agent 进化"」
理由是自陈的: 「当前系统是一只'在笼中自转'的生命体」
```

---

## 四、D3 · CIP 分层进化

**原文**（`hermes-collective-intelligence/evolution_layers.py` docstring）：

```text
L1 配置层 | L2 技能层 | L3 行为层 | L4 底层代码
对应:    阈值/参数 |  技能改进 | 工作流重构 | 算法/数据结构
```

**★ 这是全部 41 个仓库里唯一写到「底层代码/算法/数据结构」这一层的。**

**但它的实现强度两处不一致**：

```text
hermes-collective-intelligence/mutation_handler.py 的 L4:
  open(file_path,'w').write(patched_code)  ← 真改 Hermes 源文件
  硬门控 fitness >= 0.95（docstring 自述"风险等级: 最高"）

CIP-Zhazhazhu/evolution/code_mutator.py 的 L4:
  在抽象 CGP 基因组上变异，不碰源文件

L4 阈值漂移: HCI 一处写 0.5、一处写 0.95
```

**★ 没有任何一处把它写成「架构可进化」这句话**（15 个精确短语全文 0 命中）。

---

## 五、D4 · ARSI 九维 + 双 Ω

**九维可进化面**（`ARSI/src/arsi/harness/taxonomy.py` 的 `DIMENSIONS`）：

```text
c1-c6 行为规则（prompt / processor / tool / config / control …）
c7    ★ control/safety = Iron Laws — frozen, never an evolution target
```

**★ 唯一一处「架构可进化」有代码执行的**（`ARSI/src/arsi/harness/pillars.py`）：

```text
"organization=rho_iron_laws_sealed_goals"      组织 = ρ 铁律，冻结
"structure=omega_harness_host_policies"        结构 = Ω harness/宿主策略，可改
"stage3_may_change_structure_never_organization"
```

配套真跑：`anchored_meta_ok()` + `tests/test_coevo_fidelity.py::test_anchored_meta_blocks_rho`

**双 Ω**（`ARSI/src/arsi/harness/unified_credit.py`）：`双 Ω = policy + harness 两个各自递归的改进环`

**边界**（`evolver.py`）：`Does not auto-edit core — manifests are reviewable artifacts`

---

## 六、D5 · 母巢 96 条（不是维度枚举，是前置条件）

```text
A 度量根基  T-convergence / 检索召回≠检索有益
B 记忆是载体 ★原始记忆层只读，演化发生在可丢弃上层视图
             ★原则库必须 on-policy
C 进化协议  ★固定种子重放+守门人 / ★self-induced update operator
D 边界分区 骨骼区禁演化 / 变化分流矩阵 / 内核演化12信号分类器
E 失败模式 检索缺失型静默失败 / 虚假记忆率FMR
F 判据要严 ★FGT≈0 只说明没退化，BWT>0 才是真协同演化
```

**★ 这 6 组不是"进化什么"的分类，是"进化的前置条件与边界"。**
这也是我前两次答错的原因——我一直在找维度枚举，而你的母巢阶段根本不按维度组织。

---

## 七、维度并集（去重后的完整清单）

把五套体系的对象合并去重：

```text
1  元参数 MetaParams      v6-L0
2  策略 Strategy          v6-L1
3  技能 Skill             v6-L2
4  配置 Config            v6-L3
5  代码 Code              v6-L4
6  进化机制自身 MetaEvolution  v6-L5 ★ 元进化
7  提示词 Prompt          v6-L6
8  工具 Tool              v6-L7
9  记忆 Memory            v6-L8
10 知识 Knowledge         v6-L9
11 协作 Collaboration     v6-L10
12 架构 Architecture      v6-L11 ★
13 参数（独立算）         Ultra-T1
14 语义                   Ultra-T2
15 外部机制库             Ultra-T3/T4
16 行为/工作流            CIP-L3
17 组织 vs 结构           ARSI pillars
18 policy / harness 双环   ARSI unified_credit
19 演化方向 Forward/Lateral/Reverse   v6 正交 3 方向
```

**★ 你设计过 12 个并列维度（v6）+ 3 个正交方向 + ARSI 的结构/组织二分。**
**并集去重后 19 个可命名对象。**

---

## 八、这个数字意味着什么（我的判断，非原文）

```text
① 12 个维度只在 v6 存在过一代，之后再没被完整重提
② 你在 2026-05（v6/CIP）→ 2026-09（ARSI）之间，
   「维度枚举」这个组织方式本身被放弃了
③ ARSI 的做法不是"再列一批维度"，而是：
   先划死不可动的（c7 Iron Laws），再在剩下的里选九个
   ★ 这是从"穷举维度"转向"先圈禁地再开放"
④ 母巢 96 条更进一步：不再枚举对象，改为枚举
   「进化的前置条件与失败模式」
   ★ 三阶段的组织方式：穷举维度 → 圈禁地后开放 → 枚举前置条件
```

---

## 九、必须说明的数据缺口

```text
· prometheus-v9pro / prometheus-v10        README 与 md 均未抓到
· Prometheus-Omega-Genesis / Protogonos   README=0、md=0，本地 E:/ 无副本
  ★ 这两个仓库零可引原文，文中涉及其名处均为他库二手描述
· E:/HERMES_Collective_Intelligence.txt（原始设计文档）不在 GitHub，
  而 verify_design_compliance.py 依赖它存在
· prometheus-v8pro 的 README 与 v8 逐字节相同，无 pro 专属内容
```

---

## 十、三处硬矛盾（照实报，未调和）

```text
① v9 教训表「12层进化10层空壳」 vs v7「12/12层完整」—— 同时声明
② Y 的机制表标「9种架构操作 ✅属实」，但源文件 preflection.py 实为
   Preflection Engine，9 个操作符与 architecture 全部 0 命中
   （而 Y 在同一份 DESIGN.md 写了利益冲突声明）
③ MSTAR-Pro-V4.0/README.md 与 hermes-agent-backup/README.md 逐字节相同
   —— 仓库内容是真 MSTAR，README 却是 Hermes 主线的
```
