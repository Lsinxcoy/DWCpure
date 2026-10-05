# DWC 器官接口契约（§9 第 6 项）

> **状态**：设计定稿（**未写代码**，`src/` 仍为空）
> **日期**：2026-10-04
> **范围**：七条器官之间的**接口签名**（方法名 / 参数 / 返回 / 不变量）。
> 已在 §4.1–§4.8 定的是"器官做什么"，本文件定的是"它们怎么互相调用"。
> **硬纪律（原则 6）**：器官之间只经接口通信，不经内部状态。
> 判据：`organ_A` 不许出现 `organ_B._private_attr`。
> **前置**：`docs/STATE_SCHEMA.md`（state 四层 + Pair）· `docs/CAUSAL_CHAIN_STORAGE.md`（链三表）
> · §4.4 五段式落地器（消费点声明）· §9 第 5 项（三级验证）· §9 第 25 项 (c)（保护组）

---

## 〇、★ 先说一个真实发现（动笔前查到的）

```text
★ JUDGE_DESIGN.md 与 ACTOR_DESIGN.md 里给出的都是 **ARSI 侧的被审计对象**
  （SealedEvaluator 的 docstring、core.step() 的骨架），
  **不是 DWC 的接口签名**。
⇒ ★ ⇒ 第 6 项的真实内容是"从零落 DWC 的签名", 不是"补两份文档的空缺"。
⇒ 签名必须从已有的三处已定内容里长出来:
  ① §4.4 五段式（落地器的消费点声明 + verify）
  ② STATE_SCHEMA 四层（State / Pair）
  ③ CAUSAL_CHAIN_STORAGE 三表（append / trace_back）
```

---

## 一、★ 六条通用约定（七条接口共同遵守）

```text
① 入参出参一律 frozen dataclass
   依据: STATE_SCHEMA §八"全部 frozen —— 铁律阳性测试要构造违规 state"
   ⇒ 器官的返回值不可被调用方就地改（防止"改了等于没改"）

② 返回值必须带证据, 不许裸成功
   依据: judge "never blind SUCCESS"（§4.1 原文）
   ⇒ 任何返回"成功"的结果都要能回答"凭什么"

③ 不许返回 None 表示失败
   ⇒ 失败用显式的 outcome 字段（第 5 项的五态）
   ⇒ ★ 理由: None 会与"未评价/未运行"混淆（STATE_SCHEMA 的三态问题）

④ 跨器官只传 ID, 不传内部对象
   依据: 原则 3「单一真值源」+ 原则 6
   ⇒ 例如传 chain_id / pair_id, 不传对方的 dataclass 实例
   ★ 收益: 循环 import 被结构性禁止（Python 层即可机械检查）

⑤ 长耗时操作必须可中断且声明预算
   依据: §9 第 2 项的预算 b_t + 式10 四分量成本向量

⑥ 每个接口都要有一条"负面测试"（喂异常输入断言 raise）
   依据: 判据 I6 / S2 的同款纪律 —— 只测通过等于没测
   ★★★ 2026-10-04 补: 何时 raise / 何时返回 error 字段, 规则已定
     —— 详见 docs/ERROR_AND_TERM.md §一。唯一判据:
        **失败后调用方是否还有事可做**。
     ★★★ 实测得到的硬要点: "门未通过"不是违规 ——
        写成 raise 会让失败的后果量级差一个数量级
```

---

## 二、`memory` 的接口（七管是对内流程，对外只暴露五个方法）

```python
# 落点: organs/memory/
class MemoryOrgan:
    def ingest(self, trace: TraceRef, chain_id: str) -> MemoryId
        """remember 管。摄入一条 actor 痕迹。
        不变量: trace 必须带 failure_signature（失败时）或 success is not None
                —— 依据 ACTOR_DESIGN §4.3"没有失败定位的痕迹, 不算合格痕迹"
        返回: MemoryId（不是 MemoryRecord —— 违反约定④）"""

    def recall(self, need: RecallQuery, top_k: int) -> list[MemoryId]
        """recall 管。取回后 access_count +1。
        不变量: 返回的每条都写 access 记录（原则 7: 无 access 不许当有价值）
                ★ 母巢失衡1 = 98.8% access_count=0 ⇒ 这是必修项"""

    def distill(self, proxy_ids: list[MemoryId]) -> ExperienceId
        """learn + reflect 管。PROXY → EXPERIENCE，产出带失败签名 (c,q,m) 的经验。
        不变量: ★ 每条 Experience 必须带 signature（无签名的经验不予沉淀）
                ★ 经验必须登记到 causal_chain（CAUSAL_CHAIN_STORAGE 判据 S1）
        依据: §9 第 4 项已定 FailureSignature = (c, q, m)"""

    def forget(self, budget: ForgetPlan) -> ForgetResult
        """maintain 管。按 Weibull + 稀有保护淘汰。
        不变量: ★ 淘汰前必须检查"每条经验是否有来源"（C3）
                ★ 稀缺保护组不得淘汰（§4.3 的 rarity protect）
        ★★ 必须留痕: 淘汰了什么、为什么 —— 依据 §9 第 25 项
          "failed attempts and their costs also require recording\""""

    def stats(self) -> MemoryStats
        """只读。给门与 iwm 的观测量。
        ★ 含 access_ratio（母巢 98.8% 那个指标必须常驻）"""
```

```text
★ 为什么七管只暴露五个方法:
  七管是**内部流程**（remember→recall→learn→reflect→evolve→dream→maintain），
  对外只暴露五个入口 —— 否则每个调用方都能从任意管切入,
  绕过"写入必须带失败定位""沉淀必须带签名"这两条不变量。
  ★ 这与 §11 的"stage{N}_* 设计文档 vs organs/* 实现"双落点是同一个判断:
    流程可多, 接口要少。
★ 七个方法名与七管名的对应: ingest=remember · recall=recall
  · distill=learn+reflect · forget=maintain · stats=(观测量)
  ★ 未直接暴露的: evolve(归 evolver 器官) · dream(内部)
  ⇒ 若将来要给 dream 开接口, 须先答"它的不变量是什么"
```

---

## 三、`world_model` 的接口（含守卫① —— 第 20 项裁决的落点）

```python
# 落点: organs/world_model/
class WorldModelOrgan:
    def predict(self, ctx: ExecutionContext, candidates: list[str]) -> Prediction
        """第一顺位决策输入。返回 Prediction（不是 dict —— 约定①）。
        ★★ 不变量: Prediction 内**不得含** confidence 字段
           依据: 第 20 项裁决 —— 自算 confidence 是"计数器"（count/20），
                 且违反原则 12（守卫不许来自被门控者自身）
           ⇒ ★ 这一条是本接口最关键的约束, 写进类型定义里"""

    def current_version(self) -> str
        """返回 wm_version。★ 每次 evolve 后 +1（STATE_SCHEMA 的写入方）"""

    def trust(self, pairs: list[PairId], wm_version: str) -> TrustVerdict
        """★★ 守卫① 的判据来源。三个约束在此落地（§9 第 20 项）:
          约束1 冻结: 调用期间本器官**不更新**（内部实现, 对外表现为纯函数）
          约束2 留痕: 每次调用落 (wm_version, dev_accuracy, n, timestamp)
          约束3 换手: pairs 由 judge 传入（world_model 不自己读）
        返回: TrustVerdict{accuracy, n, theta_dev, theta_kind, tol, verdict}
        ★★★ 必须带 **tol**（2026-10-04 跑测追加）:
           实测同一份数据, tol=0 判 acc=0, tol=0.02 判 acc=1
           ⇒ tol 是**语义选择**, 不落进返回值则事后无法解释"当时为什么这么判"
           ★ 这与第 5 项的 tol_for() 是同一个教训（tol 不该是隐式默认）
        ★★ 必须带 n —— 契约约束 (o) 要求报 CI, 少 n 报不了 CI
           ★★ 实测: n=0 时不判 pass（无数据 ≠ 好）
        ★★ verdict ∈ {pass, degrade_to_llm, degrade_to_heuristic}"""

    def train(self) -> TrainResult
        """自训。守卫④ 依赖它（train 不成功 ⇒ 退回 baseline）。
        返回: TrainResult{ok, note} —— ★ 不许返回裸 bool（约定②）"""
```

```text
★ 守卫① 的**调用时序**（谁调谁, 必须固定）:
  evolver 每轮开始:
    pairs = judge.wm_pairs(wm_version)        # judge 提供配对记录
    verdict = world_model.trust(pairs, ver)    # world_model 只算不算, 不找数据
    if verdict.verdict == "pass":  predict = world_model.predict(...)
    else:                          predict = llm_governor.decide(...)
★⇒ world_model 永远不主动去读 judge 的存储 —— 由调用方喂（约定④）
★⇒ 这就是"换手"的接口级体现: 数据流向是单向的（judge → evolver → world_model）
```

---

## 四、`judge` 的接口（三层判据 + 三 split + 守卫① 的配对源）

```python
# 落点: organs/judge/
class JudgeOrgan:
    # ── 三层判据（§4.1 已定, 此处只定签名）──
    def verify_L1(self, trace_ref: TraceRef, rubric: Rubric) -> L1Verdict
        """规则层。确定性, 无 LLM。
        返回: L1Verdict{outcome ∈ {drawback, clean, abstain}, evidence}
        ★ 纪律 3: 缺证据 ⇒ NOT_EVALUATED（不许转成正面判定）"""

    def verify_L2(self, trace_ref: TraceRef, rubric: Rubric) -> L2Verdict
        """语义层。LLM, 窄角色, 证据受限。
        ★ 纪律 1: 不许覆盖 L1 的结论（约定: 传入 L1Verdict 作为只读输入）"""

    def verify_L3(self, pair_ref: PairRef, order: Literal["AB", "BA"]) -> L3Verdict
        """独立最终 judge。★ 必须成对调用两次（AB / BA），都同意才算赢。
        ★★ 纪律 2: L3 从不做训练信号 —— 调用方集合 == {审计报告}
        ★ 调用点须可被静态检查: 全仓 L3 的调用点必须都落在 audit 模块"""

    # ── 三 split（§4.1 已定 dev/test/train）──
    def dev_accuracy(self, split: Literal["in", "dev"], ver: str) -> AccVerdict
        """★ 守卫① 的数据源。返回 {accuracy, n, resolved, unresolved}
        ★★ unresolved 不进分母（STATE_SCHEMA §四 的三态规则）
        ★ 只算指定 ver 的记录（换版本重新计数）"""

    def wm_pairs(self, wm_version: str) -> list[PairId]
        """★ 守卫① 的配对记录读取口。
        ★★ Pair 是 Trace 的投影, 不独立存储（STATE_SCHEMA §五）
        ⇒ 这个方法只做投影查询, 不产生新数据"""

    # ── 封印 ──
    def seal_check(self, path: str, op: Literal["read", "write"]) -> SealVerdict
        """G10 落地。铁律 G10「任务集/评分规则/发布门槛在写掩码之外」
        ★ 返回 allow/deny + reason, 不许直接抛 —— 抛异常会被 except 吞掉"""
```

---

## 五、`evolver` 的接口（七环节对内，对外四个）

```python
# 落点: organs/evolver/
class EvolverOrgan:
    # ── 七环节（内部流程, 对外只四个入口, 同 memory 的判断）──
    def diagnose(self, window: ChainWindow) -> Diagnosis
        """环节①。失败签名 (c,q,m) + 三层漂移分类 + 四量度量。
        ★ 签名: terminal_cause/causal_role 由规则分类器填,
          reusable_mechanism 由 LLM 填（§9 第 4 项已定）"""

    def propose(self, diag: Diagnosis, budget: Budget) -> list[Manifest]
        """环节②。产出变更清单。
        ★★★ 不变量: 每个 Manifest 必须声明 protected_groups（非空）
           依据: §9 第 25 项 (c) 判据 R1 —— 空声明不许进准入
        ★★★ 不变量: |manifest| 受 b_t 约束（第 2 项）
        ★★★ 不变量: 每个 Manifest 必须声明 target_layer ∈ {assets, architecture}
           依据: §9 缺口 (bm) 的 A_t 三元
        ★ Manifest 里的消费点声明: ConsumerSpec（CONSUMER_VERIFICATION §三）"""

    def gate(self, manifests: list[Manifest], evidence: GateEvidence) -> GateOutcome
        """环节③。非补偿三步, 顺序不可换。
        ★★★ 不变量: 必须同时读三样 ——
             ① 非补偿四判据（Δ̂_val）
             ② 保护组回归 r̂_{t,j} ≤ ϵ_j（§9 第 25 项 (c)）
             ③ 成本 C_{≤t+1} ≤ B（b_t）
          ⇒ 漏任何一样 ⇒ 门不完整（判据 A_t 的三项都在）
        ★ 三态保留: accept / 保持现状 / **入 archive 待选**
          ★★ 「入档」不是可选 —— DGM Table 1 的 +27.0pp 靠它"""

    def apply(self, accepted: list[Manifest]) -> ApplyReport
        """环节④。三级验证（L1解析/L2读回/L3探针）+ 回滚。
        ★ 返回五态（applied/verified/rejected/unverified/failed）
        ★★★ unverified = 死基因, 必须与 failed 分开（CONSUMER_VERIFICATION §四）"""
```

---

## 六、`iwm` 的接口（四条守卫的发出方）

```python
# 落点: organs/iwm/
class IwmOrgan:
    def governor_advice(self, state: State, layer: Literal["world_model","llm","all"]) -> Advice
        """★ 守卫②③ 的发出口。
        Advice{degrade_to_baseline, downweight_pre_enactment, forbid_default_dream, reason}
        ★★★ 不变量: 本方法**不得**读 world_model 的内部状态
           依据: 第 20 项裁决的根源 —— 跨层自评是违规的
        ★ iwm 只读 State（STATE_SCHEMA 的公开四层）"""

    def self_trust(self) -> float
        """Q6 内省器自检。
        ★★★ ★ 它度量的是 **iwm 自己**, 不是 world_model
           （ARSI calibrate.py:176 读 iwm_success_rate / baseline_success_rate）
           ⇒ 守卫① **不可**用它（§9 第 20 项已否决候选甲）
        ★ 它有对照臂 + min_samples 下限 + ECE 过置信惩罚 —— 结构是 DWC 该抄的模板"""

    def drift(self) -> DriftSignals
        """环节⑤ 的观测。GDI 四信号 + 保护组回归（FGT/SAHOO R）。
        ★★★ ★★ 输出必须被某处**门控消费**, 不许只做账本
           依据: 原则 9「世界模型必须门控决策, 不许只做账本」
           母巢的反例: MWM_WEIGHT_CAP=0.1 / dyna 默认关"""

    def probe(self, probe_id: str) -> ProbeResult
        """Level 3 行为验证的探针（CONSUMER_VERIFICATION §二）。
        ★★ 若无法实现, 须让 apply() 的 outcome 改名为"仅写入"
           —— 不许把 L1/L2 通过称作 verified"""
```

---

## 七、`iron_laws` 的接口（横切，唯一可拦截所有器官的）

```python
# 落点: organs/iron_laws/
class IronLawsOrgan:
    def check(self, state: State, target: Literal["write", "call", "read"]) -> LawsVerdict
        """★ 横切检查。十条铁律全跑。
        ★★★ 必须同时返回 pass/warn/block **三组**
           依据: 判据 I2 —— ARSI violated() 只检查 block, 6 条 warn 永不检查
        ★★★ 每个检查器读的字段必须有设置方（判据 I3）
        ★ 拦截点: target="write" 时若返回 block, 调用方必须拒绝写入"""

    def register_protected_path(self, path: str) -> None
        """G10。铁律配置与 sealed 集在写掩码之外。
        ★★ 注册后必须有真实检查点 —— ARSI 有注册但 check_access 调用点 0 处
           ⇒ 判据 I8: check_access 的调用点必须 > 0"""

    def report(self) -> LawsReport
        """给门与审计。含 block/warn 的完整列表与证据。"""
```

---

## 八、环节⑦ 主体（`run_term` 末的全系统盘点）

```python
# 落点: evolution/stage7_agent/quintuple.py
def run_term(ctx: ExecutionContext, world: State) -> TermReport:
    """★ 七环节的编排入口（§11 已定 core.py 落点）。
    ★★★ ★★ run_term 末**不是"结算", 而是"生成下一轮任务源"**
       依据: §9 缺口 (bz) "Measurement thereby becomes the trigger of the next
             iteration rather than a terminal report"
    ★ 五元盘点 χ=(π, V, m, U, ρ) —— 谁在改、改了什么、收益多少
    ★ 返回的 TermReport 必须是下一轮 world_model 的输入, 不是归档"""
```

---

## 九、★ 全器官调用图（谁调谁，一次看清）

```text
              ┌──────────────┐
              │ iron_laws    │ ← 横切拦截所有 write/call/read
              └──────┬───────┘
                     │ check(state) 三组返回
   ┌─────────────────┼─────────────────┬──────────────┐
   │                 │                 │              │
┌──▼──────┐   ┌──────▼──────┐   ┌──────▼─────┐  ┌────▼─────┐
│ iwm     │   │  world_model│   │  evolver   │  │  judge   │
│ 守卫②③  │   │  守卫①④     │   │  七环节     │  │ 三层判据  │
└──┬──────┘   └──────┬──────┘   └──┬──────┬──┘  └────┬─────┘
   │  advice        │ trust       │      │         │
   │                ▼             │      │         │
   │          ┌──────────┐        │      │         │
   └─────────►│ predict  │◄───────┘      │         │
              └────┬─────┘   ctx/state   │         │
                   │                     │         │
              ┌────▼─────────────────────▼─────────▼────┐
              │              actor                     │
              │  step() → Trace → memory.ingest()      │
              └──────────────────┬──────────────────────┘
                                 │ TraceRef
                                 ▼
              ┌──────────────────────────────────────────┐
              │ memory (七管内部) + causal_chain(append)  │
              └──────────────────────────────────────────┘

★★ 三条关键的数据流向（都在接口里固定住了）:
  ① 守卫①:  judge.wm_pairs → evolver → world_model.trust
     ⇒ world_model 不主动读 judge 的存储（约定④）
  ② 铁律:   iron_laws.check 被所有器官在 write/call 前调
     ⇒ 但 check 只读 State（公开四层）, 不读任何器官私有态
  ③ 环节⑦:  run_term 的输出 → 下一轮 world_model 的输入
     ⇒ 评估是闭环触发器, 不是终点报告（缺口 bz）
```

---

## 十、可机械检查的判据（gate.py 候选，P1–P8）

```text
P1 · 器官之间不许出现 organ_B._private_attr
   ★ 原则 6 的可执行形式。grep 全 src/dwc/

P2 · 跨器官传参只有 ID, 不传对象实例
   类型注解里出现 dataclass 类型（跨器官）即违规
   ★ 依据: 约定④ + 结构性禁止循环 import

P3 · 返回值不许用 None 表示失败
   grep 各器官 return None ⇒ 必须改成带 outcome 的对象
   ★ 依据: 约定③ + STATE_SCHEMA 的三态问题

P4 · Prediction 类型里不许有 confidence 字段
   ★★★ 这是第 20 项裁决的接口级锁定:
     一旦有人往 Prediction 加 confidence, 守卫① 的矛盾就会回来
   grep "class Prediction" 块内 confidence ⇒ 违规

P5 · iron_laws.check 的调用点 > 0 且覆盖七器官
   ★ 若只在部分器官调 ⇒ 那些器官不受铁律约束
   ★ 依据: ARSI 两套实现（弱/强）生产用弱的, 判据 I5

P6 · 每条"成功"结果都带 evidence 字段
   ★ 依据: judge "never blind SUCCESS" + 约定②

P7 · 每个接口都有负面测试（喂异常输入断言 raise）
   ★ 依据: 判据 I6/S2 的同款纪律

P8 · L3 的调用点全部落在 audit 模块
   ★★★ L3 纪律 2 的可检查形式:
     若 evolver/gate 读了 L3 的输出 ⇒ 违反"从不做训练信号"
   grep "verify_L3" 的调用方集合 ⊆ {audit}
```

---

## 十一、诚实边界

```text
① 本设计**未写代码**，`src/` 仍为空 —— 符合"架构定稿前不写承重代码"的纪律。
② 未验证: P1–P8 全是设计推理，尚无实现可 grep。
③ ★★ 七条签名是**我的设计**, 不是从论文抄的:
   ARSI 与母巢都没有"七器官接口契约"这个东西（ARSI 的器官是 mixin,
   母巢是散装）⇒ DWC 的器官式本身是 DWC 的选择, 接口形态也是。
④ ★ 六条通用约定（frozen / 带证据 / 不用 None / 只传 ID / 可中断 / 负面测试）
   里, 只有"带证据"和"负面测试"有外部依据（judge 原文 + 判据 I6/S2）;
   其余四条是内部一致性判断。
⑤ ★ memory 的七管只暴露五个方法 —— 这个"流程多、接口少"的判断,
   我给了理由（防止绕过不变量）, 但**未验证**它是否够用。
   若 dream 或 recall 的第二个形态确有外部需求, 需重新审视。
⑥ world_model.predict 不接 State 而接 ExecutionContext + candidates:
   ★ 这是我为了让 predict 成为纯函数而做的选择（守卫① 需要冻结时可用）。
   ⇒ 代价: predict 拿不到完整 State ⇒ 若某次预测需要 Ψ（信念）, 得显式传入。
   ★ 未验证: DWC 的决策是否真的不需要 Ψ。
⑦ ★ 未定: 接口的错误处理约定（异常 vs 返回 error 字段）——
   本文件只用"不许 None", 没规定何时 raise。约定⑥ 的负面测试暗示
   参数非法时 raise, 但业务失败返回 error 字段 —— 这个二分尚未明文。
⑧ ✓✓ 2026-10-04 已解决: run_term 与 step 的层级已定
   —— 见 docs/ERROR_AND_TERM.md §二。层级照抄 ARSI core.py L927:
   **run_term 在外, step 在内**; DWC 相对 ARSI 有三处有意分歧。
```

---

## 十二、★ 实测记录（rc=0 全通，并抓到一个真实的浮点陷阱）

```text
✓ P4 锁定: Prediction 字段 = [action, expected_effect, wm_version] ⇒ 无 confidence
✓ 守卫① 数据流向: judge.wm_pairs → evolver → world_model.trust
  ⇒ world_model 不主动读 judge 的存储（约定④）
✓ 异版本独立计数: v1 n=1 / v2 n=1，各自算
✓ n=0 时不判 pass（无数据 ≠ 好）⇒ degrade_to_llm
✓ memory 不变量: 无失败签名的失败痕迹被拒
✓ iron_laws 三组返回: warn=('G7',) 非空 ⇒ 不像 ARSI 那样 warn 永不检查
✓ frozen: TrustVerdict 赋值抛 FrozenInstanceError

★★★ 实测抓到的浮点陷阱（不是我的笔误，是真会咬人的）:
    abs(0.79 - 0.8) = 0.010000000000000009   （不是 0.01！）
    ⇒ 0.010000000000000009 <= 0.01  →  **False**
    ⇒ tol 恰等于"理论误差"时, 浮点表示会让本该判对的判成错
    ⇒ ★★ 所以:
      (1) 守卫① 的 is_correct 不可用"严格相等"作默认（STATE_SCHEMA 的 tol=0.0 要改）
      (2) tol 必须显式落进 TrustVerdict, 不许隐式默认
      (3) 同一份数据 tol=0→acc=0, tol=0.02→acc=1 ⇒ tol 是语义选择
    ⇒ 已把 tol 加入 TrustVerdict 的返回字段

★ 另两次失败是我**自测期望值算错**（把 0.8/0.79 当成"差 0.01 所以 tol=0.01 该过"）
   —— 真跑才知道浮点上不成立。教训: 容差相关的断言必须先打印实际差值。
```

---

## 十三、诚实边界（补）

```text
⑨ ★★ 实测直接推翻了 STATE_SCHEMA 的一处默认: is_correct 的 tol 默认值
   原写"tol 默认 0.0 ⇒ 严格相等", 但实测显示严格相等在浮点误差下极不可靠。
   ⇒ 建议改为: tol 默认取"值域的一个小比例"(如 0.02 for effect∈[-1,1]),
     且必须显式传入, 不留隐式默认。
   ★ 这是跨文档的一致性问题, STATE_SCHEMA 需同步修正（本文件不擅自改）。
⑩ 未测: 七条签名的**组合**（如 gate() 同时读三样判据时的顺序）、
   全器官调用图的循环依赖检测（需要真代码才能 grep）。
⑪ ★ world_model.predict 只接 ExecutionContext + candidates, 不接 State。
   实测时我为此加了 assert 兜住类型, 但"预测是否真的不需要 Ψ"仍未验证。
```

---

*设计定稿 · 2026-10-04 · 七条器官接口 + 六条通用约定 + 全器官调用图 · 未写代码*