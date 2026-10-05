# DWC 错误处理二分 + run_term 层级（缺口 A4 + A5）

> **状态**：设计定稿（**未写代码**，`src/` 与 `config/` 均空）
> **日期**：2026-10-04 · **来源**：`docs/GAP_AUDIT.md` 缺口 A4 / A5
> **参照（已逐行核）**：
> `E:/ARSI/src/arsi/core.py` —— `run_term` L927–1010 / `step` L433
> `E:/ARSI/src/arsi/foundation/enforced_laws.py` —— 5 处 raise 全文
> `E:/SYNTHEX Autopoiesis/src/synthex_autopoiesis/loop/coala_architecture.py` —— `_term_` 8 处
> **前置**：`docs/ORGAN_INTERFACES.md`（六条通用约定 + 七条签名）· `docs/GAP_AUDIT.md`

---

## 一、A4 · 错误处理二分（何时 raise / 何时返回 error 字段）

### 1.1 ★ 先说 ARSI 的现状：两种混用，且无区分原则

```text
实测 E:/ARSI/src 全仓:
  raise        15 处
  "error": 键   16 处
⇒ ★★ 几乎 1:1，但没有一条规则说明"何时用哪个"
⇒ ARSI 的 raise 分布（逐处核）:
    enforced_laws.py   5   ← 全部是铁律违规（G5×2 / G10×3）
    world_evolver.py   2   · host_empower.py 1 · iron_laws.py 1
    llm.py 1 · store.py 1 · drawback.py 1 · variants.py 1
    beta_sweep.py 1 · cognitive_map.py 1
⇒ ★ 可观察的规律: **enforced_laws 的 5 处 raise 全是 block 级铁律**,
   且都 raise 自定义异常 IronLawViolation
⇒ ★ 而 error 键散在 llm / multiagent / sealed_eval / world_model 等
   —— 即"运行期失败"用 error 字段，"铁律违规"用 raise
⇒ ★★ 这条规律**没有写进任何文档** ⇒ DWC 必须把它明文化
```

### 1.2 ★★ DWC 的二分规则（三条，按"谁能恢复"分）

```text
★★ 分二分的唯一判据: **失败之后, 调用方是否还有事可做。**

┌─ raise（异常）────────────────────────────┬─ 返回 error 字段 ──────────────────┐
│ 判据: 调用方**无事可做**，必须中止        │ 判据: 调用方**仍有事可做**        │
│                                          │                                     │
│ ① 铁律违规（G1–G10 block 级）             │ ① 门未通过（rejected）             │
│    → 状态被污染，继续跑等于带病运行        │    → 记录，换下一个候选             │
│    ★ 依据: ARSI enforced_laws 的 5 处     │                                     │
│    ★★ 必须 raise 自定义异常               │ ② 验证不可用（not_evaluated）       │
│      IronLawViolation，不是裸 ValueError   │    → 计入覆盖率，不转成负面          │
│                                          │    ★ 依据: §4.1 judge 纪律 3        │
│ ② 契约被违反（参数类型/不变量/前置条件）    │                                     │
│    → 这是**编程错误**，不是运行期失败      │ ③ 未证实的信号（evidence 不足）      │
│    ★ 依据: ORGAN_INTERFACES 约定⑥          │    → 同上，不得当失败也不得当通过    │
│      "负面测试断言 raise"                 │                                     │
│                                          │ ④ 探针未命中（unverified / L3 未跑） │
│                                          │    → 五态之一，不是异常              │
│                                          │    ★ 依据: CONSUMER_VERIFICATION §四  │
│ ③ 器官不变量被破坏                        │                                     │
│    → 同 ①，越界即中止                     │ ⑤ 环境不可用（LLM 服务超时/离线）    │
│                                          │    → 降级路径存在 ⇒ 返回              │
│                                          │    ★ 依据: 守卫① 的降级三档          │
└──────────────────────────────────────────┴─────────────────────────────────────┘
```

### 1.3 ★★ 为什么这条二分能机械检查

```text
★ 判据 E1 · 每个 raise 都能归入 §1.2 左栏三类之一（代码审查 + 注释标注）
★ 判据 E2 · 每个 error 字段的返回点, 调用方确实有恢复路径
          （★ 否则它应是 raise —— "返回了但没人处理" = 静默失败）
★ 判据 E3 · 没有"捕获后只 log 不处理"的 raise:
          grep `except.*:\s*pass` 与 `except.*:\s*logger.` 必须 0 命中
          ★★ 这直接对应 GAP_AUDIT 里的老教训:
            母巢 gene_applier 的 `_obj is None: continue`（静默跳过）
            ARSI 的 `_check_law` 的 `default: return False`（恒不违规）
          ⇒ 两种都是"吞掉异常继续跑"
★ 判据 E4 · IronLawViolation 的捕获点集合 ⊆ {orchestrator 的中止路径}
          ★ 即: 铁律异常只允许在最外层被接住并中止，不许在中间器官被吞
          ★ 与判据 P8（L3 调用点 ⊆ {audit}）同款思路
```

### 1.4 ★ 异常类型（三个，不多不少）

```text
class LawViolation(Exception):        # G1–G10 block 级 ⇒ 调用方无事可做
class ContractViolation(Exception):   # 编程错误（类型/不变量/前置条件）
class OperationalFailure(Exception):  # 环境不可用且**无降级路径**
    ★ 若有降级路径 ⇒ 不用这个，改为返回 error 字段（§1.2 右栏⑤的反面）
★ 不设裸 ValueError/Exception: 与 ARSI 的差异是**类型即语义**
  ⇒ 调用方 catch 哪个类型，决定了它能否继续跑 —— 这就是二分的类型化
```

---

## 二、A5 · run_term 与 step 的层级关系

### 2.1 ★ ARSI 的现成答案（逐行核 core.py L927–1010）

```python
def run_term(self, n_steps: int = 10) -> dict:
    """Run a full improvement term with gain decomposition and cost tracking."""
    self._term_count += 1
    term_id = f"term_{self._term_count}"
    ...
    self.cost_ledger.reset()          # ★ 成本台账在 term 内重置
    before_eval = self.run_evaluation()
    results = []
    for i in range(n_steps):
        result = self.step()          # ★★★ step 是 run_term 的内层循环体
        results.append(result)
    after_eval = self.run_evaluation()
    ...
    decomposition = self.gain_decomposer.decompose(before_eval, after_eval, term_traces)
    cost_benefit = self.cost_ledger.cost_benefit(decomposition.get("total", 0))
    ...
    self.operator_scheduler.mark_capability_change()
    manifest = self.manifest_store.next_manifest(kind="run_term", ...)
```

```text
★★★ 层级关系是明确的: **run_term 在外, step 在内**（n_steps 次）
★ 而且 run_term 承担了三件 step 不做的事:
  ① before/after 两次评估 ⇒ 增益分解（ARSI: gain_decomposer）
  ② 成本台账的重置与结算
  ③ 调度器标定本 term 的算子（plan_next_grid / operator_scheduler）
★ ⇒ 这与 DWC 环节⑦「主体 = run_term 末的五元盘点」**完全吻合**
```

### 2.2 ★★ DWC 的定稿（照抄 ARSI 的层级，只改三处）

```text
run_term(n_steps)                    ← 外层：一个 term = n_steps 次 step + 一次盘点
  │
  ├─ 0. 预算与调度: b_t（退火编辑预算）+ 世界采样（跨谱系/代内）
  ├─ 1. before 快照: GateSnapshot + State 的 S_t/H_t 版本
  ├─ 2. for i in range(n_steps): step()
  ├─ 3. after 快照
  ├─ 4. ★ 环节⑦ 五元盘点 χ=(π,V,m,U,ρ) + 两条 dial 声明
  ├─ 5. ★ 生成下一轮任务源（不是"结算"）
  └─ 6. G11 门报告: certification_limit 必填 + wm_version/dw_version

step()                               ← 内层：一次决策 + 一次执行 + 一条痕迹
  ├─ 守卫①: judge.wm_pairs → world_model.trust → pass? predict : LLM : heuristic
  ├─ 执行
  ├─ → Trace → memory.ingest + causal_chain.append
  └─ 消费点验证（三级）的 L1/L2 部分
```

**★ DWC 相对 ARSI 改的三处**：

```text
改动1 · 成本台账不在 term 内 reset
   ★ 依据: §9 第 25 项(c) "failed attempts and their costs also require recording"
     ⇒ 若 reset, 被拒候选的成本就丢了
   ⇒ ★ 两个台账: term_cost（reset）+ cumulative_cost（不 reset）
     ★ 门看 cumulative —— 因为原则 4「产出必须有消费点」是跨 term 的
   ★ 这是对 ARSI 的**有意分歧**，不是抄漏

改动2 · after 快照之后不是"结束"，而是"生成下一轮任务源"
   ★ 依据: §9 缺口 (bz) "Measurement thereby becomes the trigger of the next
     iteration rather than a terminal report"

改动3 · before/after 之间必须锁住 dw_version
   ★ 依据: G11 配套 3（篡改可遗传）+ 判据 I12
   ⇒ 若 term 内 dw_version 变了（有人在 term 中途落地了变更）⇒ 本 term 报告无效
```

### 2.3 ★★ term 的边界由什么决定（ARSI 用固定 n_steps=10，DWC 不该照抄）

```text
★★★ ARSI 的 n_steps=10 是硬编码默认值，且被 hard_max 夹住:
   n_steps = max(1, min(int(n_steps), max(hard, 1)))
   hard = hard_max_branch_count × hard_max_refine_count
   ★ 这是**运行参数**，不是设计决定 ⇒ DWC 不继承

★★ DWC 的 term 边界应由「进化事件」而非「步数」决定:
   term 在以下任一条件成立时结束:
     ① 一次完整的七环节跑通（诊断→提案→门→落地 至少各一次）
     ② 预算耗尽: C_{≤t+1} ≥ B
     ③ 保护组回归触发: r̂_{t,j} ≤ ϵ_j 不满足（§9 第 25 项 (c)）
     ④ 停止规则命中（2603.06333 §2.7 的五条）
   ★★ 理由: 步数是任意的，进化事件才是有意义的边界
   ★ n_steps 只作为**上限**（防跑飞），不是终止条件:
     n_steps = min(预算允许的上限, hard_max)
   ⇒ 与 §9 第 2 项的 b_t 呼应: b_t 限"每轮改几个", term 限"跑多久"
     两者都不是固定值，都随退火变化
```

---

## 三、可机械检查的判据（gate.py 候选，E1–E6 / T1–T4）

> ★★ **命名空间声明（2026-10-04 加）**
> 本文件的 **T1–T4 = term 层级判据**（run_term 六步齐 / term 边界 / dw_version 锁 / 双成本台账）。
> ★ 它们**不与** `TASK_SCORE_TRACKING.md` 的判据同号 —— 后者已于同日改名为 **TS1–TS5**
>   （TS = Task Score，见该文件 §五）。
> ⇒ 起因: R5 门可信度审计发现两族编号撞车，且 `ERROR_AND_TERM.T1` 与
>   `TASK_SCORE_TRACKING.T1` 语义完全不同 ⇒ 若按编号写检查器必有一半指错对象。
> ★★★ 另注: `T1–T4` 在 `docs/lessons/` 与 `DEDUP_AUDIT_6SYSTEMS.md` 里还大量出现，
>   但那是 **Ultra/Nexus 的「四轨」术语**（参数/语义/GitHub机制/论文机制），
>   是对外部项目的原文引用，**与 DWC 判据无关**，一律不改。

```text
—— 错误处理 (E) ——
E1 · 每个 raise 点都标注了它属 §1.2 左栏哪一类
E2 · 每个返回 error 字段的点, 至少有一个调用方有恢复路径
   ★★ 无恢复路径却返回 ⇒ 那是静默失败, 应改 raise
E3 · `except: pass` 与 `except: logger.` 命中数 == 0
   ★ 直接对应母巢 continue 与 ARSI default-return 两处经典静默失败
E4 · LawViolation 的捕获点 ⊆ {最外层中止路径}
   ★ 禁止中间器官 catch 后继续

—— term 层级 (T) ——
T1 · run_term 内必含: before 快照 / n×step / after 快照 / 五元盘点 / 下一轮任务源
   ★ 缺任一 ⇒ term 不完整（ARSI 的 run_term 缺第五项）
T2 · term 边界由进化事件决定, n_steps 只是上限
   ★ 判据: 代码里不许有 "if steps == 10: break" 这类硬编码
T3 · before/after 之间 dw_version 被锁
   ★ 变了 ⇒ 本 term 报告无效（G11 配套 3）
T4 · 两个成本台账并存: term_cost(reset) + cumulative_cost(不 reset)
   ★ 只有 term_cost ⇒ 被拒候选的成本丢失（违反 25(c) 的记录要求）
```

---

## 四、诚实边界

```text
① 本设计**未写代码**，`src/` 与 `config/` 均空。
② 未验证: E1–E6 / T1–T4 全是设计推理，尚无实现可 grep。
③ ★★ 我对 ARSI 的观察（raise 15 vs error 键 16）来自**文本计数**，
   不是逐个调用点的语义判定 ⇒ "raise 全是铁律"这个规律可能过于概括。
   ★ 我逐字读了 enforced_laws 的 5 处（确认全是 IronLawViolation），
     但其余 10 处 raise 未逐处核语义。
④ ★ "term 边界由进化事件决定"是我的判断，**ARSI 与母巢都没有这个做法**
   （母巢 coala_architecture 的 _term_ 我只做了 grep 计数 8 处，未读实现）。
   ⇒ ★ 这是本设计里风险最高的一条: 若进化事件迟迟不发生，term 会不结束。
   ⇒ ★ 缓解: n_steps 上限仍然存在（§2.3），但那条是兜底不是主路径。
⑤ ★ 改动1（双成本台账）与 ARSI 分歧，理由是 25(c) 的记录要求 ——
   但那条要求原文是 "failed attempts and their costs also require recording"，
   ★ 它没说"台账不能 reset" ⇒ 我的推论是"reset 会导致被拒候选成本丢失"，
   这步推理合理但**是我的推论**，不是论文明文。
⑥ ★ 异常类型只定三个，但 §1.2 右栏的"未证实信号"（②③）是否也该有异常类型，
   我选了"不" —— 因为它们不是失败，是**状态**。★ 这个区分未与人核。
⑦ 未核实：母巢 coala_architecture.py 的 term 实现（只 grep 计数）。
⑧ ★ 本设计未处理并发：一个 term 内若有两个 step 并发，T3 的 dw_version 锁
   会立即失效 ⇒ 需要 term 级串行保证，未定。
```

---

## 五、★ 实测记录（rc=0 全通，并暴露一处语义要点）

```text
✓ E1 四个 raise 标签都能归类（iron_law_block/organ_invariant→LawViolation,
      contract→ContractViolation, no_fallback_env→OperationalFailure）
  ✓ 未归类的 raise 被拒: "未归类的 raise: 随便一个 raise"
✓ E2 恢复方检查: rejected→evolver.gate / not_evaluated→judge覆盖率 /
      unverified→iwm.probe, 三者都有恢复路径
  ★★ failed 的恢复方是**无** ⇒ 它必须由 raise 承载，不作为 error 字段返回
✓ E3 三种静默吞异常形态全被抓: `except: continue`（母巢式）/
      `except: logger.warning`（ARSI 式）/ `except: pass`（裸吞）
      ⇒ ★ ARSI 的 `default: return False` 是**第四种**，E3 判据要能覆盖它
✓ T1 run_term 六步齐（ARSI 只有前三项 + 成本结算）
✓ T2 四场景: 进化事件终止 / 预算耗尽终止 / n_steps 上限终止（兜底）/ 继续
✓ T3 term 内 dw_version 从 v1→v2 ⇒ 本 term 报告 valid=False
✓ T4 双台账: 第一 term cum=3.0, reset 后第二 term cum=8.0
  ⇒ ★ 被拒候选的成本仍留在 cum（ARSI 只留 term ⇒ 会丢）

★★★ 实测暴露的语义要点（比我原稿说得更硬）:
  ★★ **"门未通过"不是违规**。
    若有人把 rejected 写成 iron_law_block（铁律违规），
    语义会从"换下一个候选"漂移成"整轮中止"。
  ⇒ ⇒ 这就是分二分的实质, 不只是"抛不抛异常":
      同一件事写成 raise 会让**失败的后果量级差一个数量级**。
  ⇒ ★★ 所以 E2 的"有恢复路径才返回"是硬判据:
      rejected 有恢复路径 ⇒ 必返回; failed 无恢复路径 ⇒ 必 raise。
```

---

## 六、诚实边界（补）

```text
⑨ 实测覆盖: E1/E2/E3 的分类器与正则 / T1/T2/T3/T4 的逻辑
   **未测**: 与真实实现的接驳（无 src/ 可接）; 并发场景（T3 的锁会失效）
⑩ ★★ T3 与并发的冲突: 本设计要求 term 内 dw_version 锁死,
   但一个 term 内若有**两个 step 并发执行落地**, 锁会立即失效
   ⇒ 需 term 级串行保证，属实现约定，未在设计中强制
   ★ 这条我在正文诚实边界⑧提过, 实测后确认它不是理论问题
```

---

*设计定稿 · 2026-10-04 · A4 错误处理二分（raise 三类 vs error 五类 + 三种异常类型）+ A5 term 层级（照抄 ARSI 层级、相对 ARSI 有三处有意分歧）· 未写代码*