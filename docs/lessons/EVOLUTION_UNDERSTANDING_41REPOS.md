# 作者对「进化」的理解 · 41 仓库对照表

> 底稿：`pro_evolution_vocabulary.md` / `omega_lineage_vocabulary.md` /
> `hermes_mstar_vocabulary.md`（三份深读，共 97KB）+ 母巢 186KB 思辨笔录 v21 清单 96 条。
> 每条带原文引用，**区分「设计写了」与「代码实现了」**。

---

## 一、最重要的发现：你在 12 代里把「架构可进化」拿掉了

```text
v6  README 的 12 层表:  | L10 | Collaboration | 协作进化 |
                       | L11 | Architecture  | 架构进化 |   ★ 写了
v7  同一份架构图改成:   | L10 | Quota → L11 | Budget |（推理预算）
    v7 对外宣称「统一引擎，12/12 层完整」
    ★ 补齐的表述与被移除的对象同时发生，README 无一字说明

v9  教训表第一行:  12层进化10层空壳 | V3-V6 | 只实现4层进化，每层必须可运行
    L11 架构进化 正是那 12 层之一
    V9 把它改写成: L3: ArchitectureHealth — 代码架构健康监控
    产出是「超阈值触发修复建议」—— 测，不是改

X   自评表把 L11Architecture 判 5/10，理由「仅调整 parallelism/cache_size/timeout 参数」
    修复史记为「L9/L11 空壳」
```

**这是一条清晰的下行线**：架构进化从"第 12 层能力" → 被静默移除 → 被降级为"监控健康度" → 被自评为空壳。

**唯一的无条件主张在 Prometheus-Y**：

```text
Prometheus-Y / DESIGN.md 〇、设计声明:
  「不是'更好的框架'，是一个能自己进化自己的有机体。
    有新陈代谢、有记忆寿命、有社会性、能自己改自己架构。」
```

**而 Y 恰好是自评里问题最集中的仓库**（见 §4）。

---

## 二、你在三处明写了「架构/结构可进化」，但条件各不相同

| # | 位置 | 原文 | 边界 |
|---|---|---|---|
| 1 | `prometheus-v6/README.md` | `L11 \| Architecture \| 架构进化` | 无条件主张，但 v7 移除 |
| 2 | `Prometheus-Y/DESIGN.md` 〇 | `能自己改自己架构` | 无条件主张，且 Y 预写了利益冲突声明 |
| 3 | ARSI `src/arsi/harness/pillars.py` | `stage3_may_change_structure_never_organization` | ★**唯一有代码执行的一处**：组织(ρ铁律)冻结，结构(Ω harness/宿主策略)可改 |
| 4 | `SYNTHEX_EVOLUTION_INSIGHTS.md` §23 第23条 | `变化分流矩阵：表达/策略/流程/模型/概念各落对应边界，概念变化才许碰内核` | 概念变化才许碰内核 |
| 5 | 同上 v22 第66条 | `内核演化12信号分类器（os_series_08）` | 内核演化的判定信号 |
| 6 | 同上 §23 第14条 | `先画"无机/有机分区图"，骨骼区禁演化` | 骨骼禁入 |

**ARSI 那一处是全部 41 个仓库里唯一「架构可进化」有真实代码执行的**：

```text
src/arsi/harness/pillars.py  常量:
  "organization=rho_iron_laws_sealed_goals"
  "structure=omega_harness_host_policies"
  "stage3_may_change_structure_never_organization"
配套: anchored_meta_ok() + tests/test_coevo_fidelity.py::test_anchored_meta_blocks_rho
     ★ 该测试真的执行，证明组织被冻结
taxonomy.py: c7 control/safety = Iron Laws — frozen, never an evolution target
```

---

## 三、检索「架构可进化」的阴性结果（这部分同样是结论）

```text
Ω 系列 8 仓库 README:
  架构本身/自身架构/元进化/meta-evolution/结构本身/自我修改/self-modif
  修改自身/自身代码   →  全部 0 命中

Hermes+MSTAR+CIP 线 14 个仓库约 220 万字符:
  架构可进化/架构本身/自身架构/结构进化/重写自己/自我重构/架构演化
  拓扑演化/改变架构/修改架构/架构重构  →  全部 0 命中

v11 的 32,614 字符设计文档:
  元进化/架构操作/ADD_LAYER  →  0 命中
  进化被定义成评估协议：「先定义 eval 再进化; pass@3>90% 才 apply」
```

**最接近但不是的三处**：

```text
CIP 的 L4 底层代码 = 算法/数据结构
  ★ docstring 自述「风险等级: 最高」，且实际是从预置字典换算法
  hermes-collective-intelligence/mutation_handler.py 的 L4 是真 open(file,'w').write(patched_code)
  ★ 但没有一处把它写成「架构可进化」这句话

Darwin「学习如何设计更好的实验策略」
  ★ 元层提升，但五实例与六个事件类型在 v7.0→v9.0 之间固定

RSPL/SEPL 协议（母巢 evolution_op.py）
  对象是 SkillMetadata（注册/版本/回滚），不是系统结构
```

---

## 四、进化对象：三个家族线三种答案（实测）

| 家族线 | 进化对象 | 原文 |
|---|---|---|
| **MSTAR 线**（6 仓） | 记忆程序 / skill | `基于适应度的程序变异与淘汰机制`（mstar/README.md） |
| **Hermes 主线** | skill + memory 的**内容** | `Skills self-improve during use`（hermes-agent/README.md） |
| **CIP 线** | 配置→技能→工作流→底层代码 L1-L4 | `evolution_layers.py` docstring：`L1 配置层 \| L2 技能层 \| L3 行为层 \| L4 底层代码` |
| **Ultra 后期**（立场修订） | **为宿主 agent 进化** | `Ultra 不再"为自身进化"，而是"为宿主 agent 进化"`（v2_host_agnostic_evolution.md），理由是自陈的 `当前系统是一只"在笼中自转"的生命体` |
| **母巢 v21 清单** | 96 条，主干是**前置条件与边界** | 见下 |

**母巢 186KB 思辨笔录的 96 条**不是"进化什么"的分类，而是六组前置条件：

```text
A 度量根基  1 T-convergence 一等指标 / 4 检索召回≠检索有益
B 记忆是载体 3 ★原始记忆层只读，演化发生在可丢弃上层视图
             32 ★原则库必须 on-policy
C 进化协议 9 ★固定种子重放+守门人，progression 不提升不提交
            10 ★self-induced update operator
D 边界分区 14 骨骼区禁演化 / 23 变化分流矩阵 / 66 内核演化12信号
E 失败模式 42 检索缺失型静默失败 / 50 虚假记忆率FMR
F 判据要严 46 ★FGT≈0 只说明没退化，BWT>0 才是真协同演化
```

---

## 五、你自己的项目里三处硬矛盾（我照实报，不调和）

```text
① v9 教训表「12层进化10层空壳」 vs v7「12/12层完整」
   补齐与空壳同时声明。

② Y 的机制注册表标 M22「Harness元进化 9种架构操作 ✅属实」
   出处指向 BREAKTHROUGHS_v2.md，但 V11_DESIGN.md 对
   ADD_LAYER/ADD_ORGAN/RECONFIGURE 零命中；
   实测源文件 preflection.py（19,173字符）9个操作符与
   architecture 全部 0 命中 —— 该文件实为 Preflection Engine。
   ★ Y 在同一份 DESIGN.md 预先写了利益冲突声明。

③ MSTAR-Pro-V4.0/README.md 与 hermes-agent-backup/README.md 逐字节相同
   仓库内容是真 MSTAR（mstar_core/、mstar_fitness.db），README 却是 Hermes 主线的
   ★ 该仓库的"自述定位"是假的
```

---

## 六、总体趋势：可进化对象逐代收窄

```text
v1/v6   12 层枚举（架构 = 第12层）
v7      统一 12 层（架构静默移除）
v9      4 层全实现，文件数 -78%（架构降级为"健康监控"）
v11     评估协议（进化 = 先定义 eval 再进化）
Z       最终定性: 「过去30个仓库的根本问题：闭环始终没闭合」
```

**Z 的这句话是 41 个仓库里对"进化"最凝练的判断** —— 问题不在能进化什么，
在于「变异→挂载」有，「执行→评估→选择」后半环没有。

Ultra 侧的对照判据：
`有"变异→挂载"，无"执行→评估→选择"后半环` / `四轨产物是僵尸机制（激活后不到生产）` /
`无"激活后行为真变"断言`

---

## 七、数据缺口（必须说明，不是"文档没写"）

```text
· prometheus-v9pro / prometheus-v10：README 与 md 均未抓到
· Prometheus-Omega-Genesis / Protogonos：README=0、md=0，本地 E:/ 无副本
  ★ 这两个仓库本次零可引原文，文中涉及其名处均为他库二手描述
· E:/HERMES_Collective_Intelligence.txt（原始设计文档）不在 GitHub，
  而 verify_design_compliance.py 依赖它存在
· prometheus-v8pro 的 README 与 v8 逐字节相同，无 pro 专属内容
```
