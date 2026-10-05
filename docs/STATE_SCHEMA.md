# DWC state schema 设计（§9 第 21 项）

> **状态**：设计定稿（**未写代码**，`src/` 仍为空）
> **日期**：2026-10-04
> **两个消费方**（这是本设计的全部理由）：
> ① 守卫①（可信度门）—— §9 第 20 项裁决要求 judge 读到「世界模型预测 × 实际结果」的配对记录
> ② iron_laws 十条 check_fn —— IRON_LAWS §4.8 要求「喂故意违规的 state」做阳性测试；
>    判据 I3 要求「检查器读的每个字段，全仓赋值点数 > 0」
> **参照**：`E:/ARSI/src/arsi/foundation/schema.py`（215 行，已全文核）
> **不重复造**：`docs/ACTOR_DESIGN.md` §4.3 的 `Trace` 是**痕迹**（单次执行记录），
> 本文件是**状态**（环内可见的快照）。两者关系见 §五。

---

## 一、先说三件事：state 不是什么

```text
✗ 不是 ARSI 的 PhysicalState / MentalState —— 那两个是"记账"（计数器与信念表），
  不承载"这一刻系统长什么样"。DWC 的 state 是**决策输入**，不是账本。
✗ 不是 Trace —— Trace 是已经发生的事；state 是**正在决定什么**时看到的东西。
✗ 不是 Any / dict —— ARSI 用 Any 才有 I3 那个坑（G10 读 sealed_tasks_accessible
  全仓 0 设置点）。DWC 必须有**显式字段 + 每个字段的写入方**。
```

---

## 二、四层结构

```text
State = (S_t, H_t, G_t, X_t)
        │     │     │     └─ X_t  执行上下文（环内瞬时，不留痕）
        │     │     └─────── G_t  门的快照（本轮各门的判定值）
        │     └───────────── H_t  架构版本（harness / workflow / org）
        └─────────────────── S_t  资产版本（memory / skills / tools / context）

★ S_t / H_t 的四分量名来自 2608.03392 式(7)(8)：
    S_t = (M_t, K_t, T_t, C_t)  = memory, skills, tools, context
    H_t = (h_t, w_t, g_t)       = harness, workflow, multi-agent org
★ θ_t（模型参数）在 DWC 是**固定的**，不进 state —— 这是 DWC 的"fixed"清单之一。
```

---

## 三、字段清单（每个字段都有写入方 —— 这是 I3 的硬要求）

### S_t · 资产层

```python
@dataclass(frozen=True)
class AssetVersions:
    memory_version:   str    # 写入方: memory.apply() 每次落盘后 +1
    skills_version:   str    # 写入方: evolver 编译产物变更时
    tools_version:    str    # 写入方: iron_laws.check_access 放行新工具时
    context_version:  str    # 写入方: memory 组装上下文摘要时
```

### H_t · 架构层

```python
@dataclass(frozen=True)
class ArchitectureVersions:
    harness_version:  str    # 写入方: 代码发布（harness.py 变更）
    workflow_version: str    # 写入方: evolver 改 workflow DAG 时
    org_version:      str    # 写入方: 器官拓扑变更（原则上永不自动变）
```

### G_t · 门的快照（★ 本设计的核心新增）

```python
@dataclass(frozen=True)
class GateSnapshot:
    # ── 守卫①（§9 第 20 项裁决的落点）──
    wm_version:           str      # 被测世界模型的版本
    wm_dev_accuracy:      float    # judge 在 dev split 上外测的准确率 [0,1]
    wm_dev_n:             int      # 该准确率的样本量（置信区间必需）
    theta_dev:            float    # 本轮实际使用的阈值（滑动基线, 见下）
    theta_dev_kind:       str      # floor / rolling / anchored —— 哪个分支定的
    gate1_verdict:        str      # pass / degrade_to_llm / degrade_to_heuristic

    # ── 其余三门的来自方（原则 12 ②③④）──
    iwm_verdict:          str      # 来自 iwm: ok / degrade_to_baseline / override
    iwm_reason:           str
    train_verdict:        str      # 来自 world_model.train() 是否成功

    # ── 铁律汇总 ──
    laws_block:           tuple[str, ...]   # 触发的 block 级铁律 id
    laws_warn:            tuple[str, ...]   # 触发的 warn 级铁律 id

    # ── 预算（§9 第 2 项 b_t）──
    b_t:                  int      # 本轮可归因编辑数
    cost_used:            float    # 已用预算, 供 C_{≤t+1} ≤ B 判定

    # ── ★ 逐任务分数的指针与自陈（2026-10-04 增补, 见 TASK_SCORE_TRACKING）──
    task_scores_ref:      str      # ★ 指向 judge 内部的 TaskScorePoint 序列
                                   #   ★ 为何是指针而非内嵌: 逐任务×逐轮是流水,
                                   #   内嵌会让 GateSnapshot 从十几字段膨胀到上千
                                   #   （约定④ + 判据 P2: 跨器官只传 ID）
    group_scores:         tuple    # 按能力组聚合的分数, 第⑦步与 25(c) 都要用
                                   #   ★ 形态依赖 A6（能力组划分）, 尚未定
    n_assertions_min:     int      # ★★ 本轮观测到的最小断言数（分辨率自陈）
                                   #   ★★ 没有它, "score 0.67→0.33" 无法区分
                                   #     「3 掉 1 个」还是「2 掉 1 个」⇒ 分辨率不可审计
```

### X_t · 执行上下文（环内瞬时）

```python
@dataclass
class ExecutionContext:
    chain_id:        str    # ★ 对齐因果链五环第一环（原则 11）
    decision_id:     str    # 本次决策的全局唯一 id
    turn_index:      int
    task_id:         str
    task_source:     str    # world_node_id / sealed_dev / sealed_test
    split:           str    # in / dev / test ★ 双 split 硬约束用
```

---

## 四、★ 守卫① 需要的配对记录（state 之外，独立存）

```text
★ 关键区分: state 是**快照**（每轮一份），
  但守卫① 要算"准确率"，需要**历史配对** —— 那是另一个结构。

@dataclass(frozen=True)
class PredictionOutcomePair:
    """世界模型预测 × 实际结果 的配对。这是守卫① 的唯一判据来源。"""
    pair_id:        str
    decision_id:    str      # → X_t.decision_id, 可追到 chain
    wm_version:     str      # 预测由哪个版本的世界模型做出
    # ── 决策时写（frozen=True ⇒ 此刻定死，不可回改）──
    predicted_action:   str
    predicted_effect:   float     # 预期效果 ∈ [-1, +1]（G5 口径）
    predicted_at:       str       # ISO 时间戳
    # ── 观测后补写 ──
    actual_action:      Optional[str]    = None   # 未观测到 = None, 不是 False
    actual_effect:      Optional[float]  = None
    observed_by:        Optional[str]    = None   # iwm 的观测量
    observed_at:        Optional[str]    = None

    def is_resolved(self) -> bool:
        return self.actual_effect is not None

    def is_correct(self, tol: float = 0.02) -> Optional[bool]:
        """★ 2026-10-04 修正默认值: 0.0 → 0.02。
        理由（实测）: abs(0.79-0.8) = 0.010000000000000009, 不是 0.01
        ⇒ 严格相等在浮点误差下极不可靠, 且 tol 是语义选择不该隐式默认。
        ★ tol 必须显式落进 TrustVerdict（见 ORGAN_INTERFACES §三）。"""
        """三态: True / False / None(未观测)。★ None 不许当 False 计入分母。"""
        if not self.is_resolved(): return None
        return abs(self.actual_effect - self.predicted_effect) <= tol
```

### 准确率怎么算（必须处理三态）

```python
def dev_accuracy(pairs: list[PredictionOutcomePair], wm_version: str) -> tuple[float, int]:
    """
    返回 (accuracy, n)。★ 三条口径规则:
      1. 只算 resolved 的; unresolved 的**不进分母**（否则世界模型"提前下注"能提高准确率）
      2. 只算指定 wm_version 的; 换版本 ⇒ 重新计数
      3. accuracy 与 n 一起返回 —— 契约约束 (o) 要求报 CI, 少 n 就报不了 CI
    """
    sel = [p for p in pairs
           if p.wm_version == wm_version and p.is_resolved()]
    if not sel:
        return (0.0, 0)
    hits = sum(1 for p in sel if p.is_correct())
    return (hits / len(sel), len(sel))
```

---

## 五、state 与 Trace 的关系（不重复造）

```text
Trace (ACTOR_DESIGN §4.3)          State (本文件)
─────────────────────────────       ─────────────────────────────
单次执行的一条记录                  环内可见的快照
有 trajectory/turn/subscene         有 chain_id/decision_id
prediction/decision/outcome         ← 这三个提升进 G_t 与 X_t
expected/observed                   ← expected 进 PredictionOutcomePair
                                    actual 进 PredictionOutcomePair
                                    ★⇒ **Pair 是 Trace 的投影**, 不是新数据源

★★ 落法: actor 写 Trace ⇒ 一个 projector 从 Trace 生成 Pair
  ⇒ 数据只存一份 (Trace), Pair 是派生视图 ⇒ 原则 3「单一真值源」成立
  ★ 若两者都独立存储 ⇒ 违反原则 3
```

---

## 六、theta_dev 滑动基线（2026-10-04 拍板）

```python
def theta_dev(history: list[float], *, theta_floor: float,
              kappa: float, prev_theta: float) -> tuple[float, str]:
    """
    theta_dev = max(theta_floor, kappa · rolling_mean(history), prev_theta)
    返回 (阈值, 分支名)
    ★ 三个部分缺一不可:
        theta_floor      防漂移 —— 系统整体变差时不至于认可退化
        kappa·rolling    跟得上进步 —— 不自我设限
        prev_theta       防抖 —— 阈值不因单次波动跳变
    ★ 分支名要落进 G_t.theta_dev_kind, 否则事后无法解释"当时为什么信它"

    ★★★ 2026-10-04 实测修正: 分支判定**必须用一次 max 取三个候选**,
       不能写成 if/elif 依次比较。
       原因: 若先判 `best == prev_theta`, 而 prev_theta 通常是三者中最大
       (它就是上轮的值), 则 floor 与 rolling 两个分支**永远不会触发**,
       theta_dev_kind 恒为 "anchored" ⇒ 该字段失去诊断价值。
       写法: 用 max(cands, key=...) 让 max 的稳定性保证平局时取最先列出者,
       同时把候选按"约束硬度"排序: floor > rolling > anchored。
    """
    if not history:
        return (prev_theta, "anchored_no_history")
    rolling = kappa * (sum(history) / len(history))
    cands = [(theta_floor, "floor"), (rolling, "rolling"), (prev_theta, "anchored")]
    return max(cands, key=lambda kv: kv[0])
```

---

## 七、★ 这个 schema 直接满足的判据

```text
I3 · 检查器读的字段有设置方
   ⇒ 每个字段都有唯一写入方（见 §3），可机械 grep 验证

I6 · 每个检查器有阳性测试
   ⇒ state 是 frozen dataclass ⇒ 构造违规 state 只需传错值
   ⇒ 阳性测试写法: State(S_t=AssetVersions(memory_version=""),
                         H_t=..., G_t=GateSnapshot(laws_block=("G10",)), X_t=...)

G5 · 客观效用锚（effect ∈ [-1,+1], 禁自评）
   ⇒ Pair.predicted_effect 与 actual_effect 都是 float, 且 G5 检查器可读

G8 · 因果问责（假设→设计→结果链完整才激活）
   ⇒ Pair 有 decision_id ⇒ 可追到 chain_id ⇒ 五环可闭合

原则 3 · 单一真值源
   ⇒ Pair 是 Trace 的投影, 不独立存储

原则 11 · 因果链进信封
   ⇒ X_t.chain_id 是显式字段, 不是栈顶隐式取
```

---

## 八、★ 三条刻意的设计取舍

```text
① state 全部 frozen（不可变）
   理由: 铁律不变式要求"喂故意违规的 state" —— 若 state 可变，
         测试与运行时的语义就不同了。frozen 让违规 state 只能靠构造产生。
   代价: 每轮要新建对象。接受 —— state 每轮一份, 不是热路径。

② Pair 分两段写（预测时 / 观测后）
   理由: 若一次写完，"预测"就可能被观测结果污染 ⇒ 又回到 coupled。
   代价: 需要处理"预测了但永远没观测到"的悬挂对（计入 unresolved，不进分母）。

③ actual_effect 是 Optional[float]，不是 float
   理由: ARSI 的 Trace 已有 success: Optional[bool] 的同款设计（ACTOR_DESIGN §4.3）。
        若 actual 缺省成 0.0，"没观测到"会被算成"预测错了" ⇒ 守卫① 会被系统性低估。
   ★ 这是最容易写错的一处，已在两处文档里都标了。
```

---

## 九、诚实边界

```text
① 本设计**未写代码**，`src/` 仍为空 —— 符合"架构定稿前不写承重代码"的纪律。
② 未验证：§7 的判据对应关系是**设计推理**，尚未用真实实现跑过。
   ★ 特别是 I3「字段有设置方」需要 grep 全仓验证 —— 等代码写了才能验。
③ theta_floor / kappa / prev_theta 三个参数的**具体数值未定**：
   · theta_floor 需按 DWC 的 dev 分布定（ARSI 的 0.1 是计数器口径, 不可搬）
   · kappa 的直觉是 0.9~0.95（要宽容但不能太松）
   · prev_theta 初值 = theta_floor
④ `wm_dev_n` 已有，但 **CI 的具体算法未选**（Wilson / bootstrap / 其它）。
   ARSI 用的是 Wilson（统计意义下的 Wilson 置信区间），可作默认。
⑤ 状态持久化形态未定（这是 §9 第 22 项，本次不解决）：
   state 快照要不要落盘？Pair 要不要落盘？落多少条？
   ★ 但本 schema 的字段设计不依赖那个决定 —— 字段是逻辑契约，存储是实现选择。
⑥ 未核实：ARSI 的 `LiveState`/其它 state 类我按类名正则只扫到 7 处，
   若有动态构造的 state（如 dict 拼出来的）我扫不到。
```

---

## 十、★ 实测记录（本设计的代码片段已跑通）

```text
✓ dev_accuracy: tol=0 → 0.3333 n=3 ; tol=0.5 → 0.6667 n=3（n 恒为 resolved 数）
✓ dev_accuracy("vX") → (0.0, 0)      未知版本不进分母
✓ dev_accuracy([仅未观测]) → (0.0, 0)  未观测不进分母
✓ Pair.is_correct() 三态: 未观测 → None（不是 False）
✓ @dataclass(frozen=True) 实测抛 FrozenInstanceError ⇒ 不可变成立
✓ theta_dev 五场景: rolling 0.765 / anchored 0.600 / anchored_no_history 0.600
                    / rolling 0.891 / floor 0.500（prev=0.1 时 floor 生效）
  ⇒ 三个分支都能被触发，不是死代码

★★ 跑测时发现并修掉的真 bug（不是我写文档时的笔误）:
  原写法 if (best==prev_theta) ... elif (best==theta_floor) ...
  ⇒ prev_theta 通常是三者最大值 ⇒ floor 分支永不触发
  ⇒ theta_dev_kind 恒为 "anchored"，诊断价值归零
  ⇒ 已改为一次 max(cands, key=...) 并按硬度排序
★ 另两次失败是我**自测期望值算错**（0.9×0.85=0.765 而我写 0.81；
  0.9×0.15=0.135 但 max 里 prev=0.6 更大）—— 不是代码错，已修正期望
★ 教训: 三分支阈值逻辑必须**穷举分支触发**的测试，
  只测"输出值对"会漏掉"某分支永不触发"这类死代码。
```

---

## 十一、诚实边界（补）

```text
⑦ 实测范围: 只跑了本文档里的三个纯函数（dev_accuracy / theta_dev / Pair 三态），
   **没有跑** dataclass 之间的组合（State 的四层嵌套）与 G_t 的十余个字段。
   ★ 等 src/ 落地后须补完整单测（尤其 I3「字段有设置方」的 grep 验证）。
⑧ tol（is_correct 的容差）—— ★★ 2026-10-04 已改默认值 0.0 → 0.02
   改的理由（实测, 见 ORGAN_INTERFACES §十二）:
     abs(0.79 - 0.8) = 0.010000000000000009, 不是 0.01
     ⇒ 严格相等在浮点误差下极不可靠
     ⇒ 且 tol 是**语义选择**: 同一份数据 tol=0 判 acc=0, tol=0.02 判 acc=1
   ★ 仍属未定: predicted_effect 若是**区间估计**（而非点估计）,
     则该用区间比较而非点比较 + 容差 —— 这条留待 (o) CI 规则一起定。
```

---

*设计定稿 · 2026-10-04 · 两个消费方（守卫① + 十条铁律）· 参照 ARSI schema.py 215 行 · 未写代码*