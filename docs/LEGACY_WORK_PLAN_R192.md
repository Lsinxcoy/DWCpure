# R192 · 老账总规划（R189 账 + DEV 面老账 + 论文落档）

日期: 2026-10-12 · 前置: R190(git 202) / R191(git 203) · 用户指令: "先做1 然后深度思考 规划R189账上+DEV面老账所有的工作"

**本文件是规划，不是施工记录**。施工按 §五 的批次走，每批独立提交 + 知识档。

---

## 零、先把"1"结清（论文落档 — 本文件前已完成部分）

| 件 | 状态 |
|---|---|
| `docs/papers/2608.27287.md`（Astar） | ✓ 已写（7.2K, 六节 + 数字全录） |
| `docs/papers/2608.17933.md`（EvoTS） | ✓ 已写（7.6K, **z_k 停滞公式逐字**） |
| `docs/papers_txt/{2608.27287,2608.17933}.txt` | ✓ 本地留存 50/49K（**不入库** — `.gitignore` 已排除, README 读法表已注明） |
| README / COMPARISON | ✓ 已更新（24→26 篇, 两行入对比表, 计数口径修正） |

**落档过程抓到的新事实（比 R186 报告更准的）**：
1. **EvoTS 停滞只对 Revision 记**：`z_k ← (op=Revision) ∧ (q_k invalid ∨ q_k−q_(prev) ≤ ϵ)`（§4.2 伪代码 L20 逐字）。DWC `stagnant_of` 对三方向一视同仁 ⇒ **这是 R188 实现与论文的**实际差距**，R192 起可裁决。
2. 早前 R186 报告靠 alphaXiv 摘要（"A revision is marked stagnant if it is invalid or its improvement is no greater than a threshold"）**漏了 `(op=Revision)` 前提** — 这正是"报告里的话 ≠ 全文逐字"的又一实例，已在该篇 §2.2 记明。
3. Astar 三级 taxonomy = L1 Coarse-Grained Direction / L2 Fine-Grained Modification Action / L3 Concrete Modification Plan（**论文未列完整类别表**，只有一个 MoE 实例）⇒ 给 ABSENT 组件 `granularity` 的施工蓝图，但表要 DWC 自己定（不是转抄）。
4. ar5iv 对 EvoTS 首次只回 abs 页 3.2K — **镜像源也会返回摘要页**，全文字符量必须核（本次 48,393 已核 stagnat 9 处/R39 处命中）。

---

## 一、DEV 面老账（本轮的取证结论，比 R180/R183 记的更狠）

### 1.1 机器实测（29 条 dev facts 上逐 op 三态）

```text
component_known  {'abstain': 29}
golden_leak      {'abstain': 29}
judge_verdict    {'abstain': 29}
nonempty_diff    {'abstain': 29}
root_parse_ok    {'abstain': 29}
pass_rate_weak   {'drawback': 27, 'clean': 2}     ← 唯一说话的
```

### 1.2 根因（**R180 的旧判决半错**）

`_facts_from_dev_surface` 注释说 *"candidate_diff 不在 evidence 判据面（R180 实测纪律: 判据与实现分离存储）⇒ None"*。

**实测推翻**：`evidence.jsonl` 每条**都有 `diffs` 字段**（逐 check 的 `{index,kind,fn,kw,args,expected,actual,ok,reason}`）。所以"证据面没有 diff"是假的——**有 diffs, 没有的是"把 diffs 投影成 op 吃的 candidate_diff 文本"这一层**。

R152 原文口径是另一回事：*"candidate_diff None ⇒ ① leakage blocked（不猜）"* — 那是**候选环**的 None 语义；dev 回归环把它当 None 传，是**把"没有候选流"误当成"没有 diff"**。

### 1.3 修法（三选一，我推荐 F1）

| # | 修法 | 内容 | 风险 |
|---|---|---|---|
| **F1** | **补投影层** | `_facts_from_dev_surface` 从 `evidence["diffs"]` 生成候选 diff 文本（首个 notok check 的 `fn(args): expected→actual` 形态，无 notok ⇒ `""`） | 低 — 纯转换，判据面字段本来就在 |
| F2 | 补 ctx 其余键 | 同时填 `judge_success`(evidence.success) / `vocabulary`(vocab 面) / `component`(failure_signature.m) | 中 — 与 R180"判据与实现分离"纪律可能真冲突，需先裁 |
| F3 | 如实记录 | 只更新注释 + e2e 断言"dev 面仅 pass_rate 面有信号" | 零（但不修） |

**F1 为什么站得住**：diffs 是 **judge 自己落的判据面字段**（49 条 evidence 条条有），把它投影成 op 输入文本是"搬形态"不是"发明数据"——与 R183 把 dev 判据点转 TermFacts 同一性质。**不碰** F2 是因为 `vocabulary/component` 涉及判据与实现的耦合边界（R152/R180 的真纪律），要单独裁。

---

## 二、R189 账上 14 项的裁决分级（用户要"所有工作"的规划）

对账终值（R190 提交）+ 本轮新证据（Astar 落档给 granularity 提供了蓝图）后的**行动分级**：

### A 级 · 现在就能做（无设计争议，纯收口/补投影）

| 项 | 是什么 | 动作 |
|---|---|---|
| **vocab 收口** | `dimension.py` 九维 + `evolver.py:58` 𝒦_meta 两处离散实现未收口 | 建 `foundation/vocabulary.py` 暴露单一 `KB_VOCABULARY`（9+4/5 项）+ 两处改为引用，**值不变** |
| **consume 显式化** | `_last_skip`/ledger 已是事实消费点但无五元组 | 建 `foundation/observability.py`：`consume_point(consumer,path,attr,range,verify)` 注册表 + 现有 3 处消费点登记 |
| **gdi 补计算** | DB 列在（`causal_chain.py:72`）但无四信号计算函数 | 补 `gdi_signals(...) -> Optional[float]`（判据: contrad/confirm/qualify/abstain 四态计数）⇒ DB 列有值可写 |
| **split 独立面** | `gates.py:188 _g4_split` 在跑，但 Δ_in/Δ_ho 双 split 接受只是 inline | 抽 `harness/split_gate.py`：`accept(baseline,current,in_delta,ho_delta)` 独立可测，gates.py:188 改为调用 |

### B 级 · 需先过设计门槛（有据但要拍板）

| 项 | 卡点 | 需要裁决什么 |
|---|---|---|
| **budget_ledger vs budget.py** | 两种预算形态（信用分配 ℒ_t / 固定四资源）未二选一 | **问用户**：统一到四资源台账，还是保留双轨记账（各自声明用途） |
| **granularity 三层树** | Astar L1/L2/L3 给了蓝图，但类别表 DWC 没定 | **问用户**：direction=L1 / component+target_layer=L2 / patch=L3 是否采纳；若是则建 `foundation/granularity.py` |
| **dev 面 F1 投影** | R180 注释与 evidence 事实矛盾 | 我判 F1（见 §1.3）——**列入默认执行，若你否掉就转 F3** |

### C 级 · 明确不做（有据，写进档案即可）

| 项 | 不做理由 |
|---|---|
| dual (pub/priv) | DWC 单机单主体，无双信号场景 |
| state (𝒟,θ,𝒽 三元组) | 2609.06396 的 S 在 DWC 无对应物，强映射=发明 |
| freshness | 依赖 state 面，state 不做则无锚 |
| coupling | 单链无协同对象（2608.10299 三条件是**多机制**前提） |
| quintuple | 主体自省框架大件，非补丁级 |
| autonomy | **需要用户外部裁决定级**，DWC 不自封 |

### D 级 · 顺手纪律债（审计副产物）

| 项 | 动作 |
|---|---|
| core.py 注释冒充 | 已在对账里点名（gdi/grounded/quintuple/VOCABULARY 只在 docstring）⇒ 逐处改注释或加"未实现"标注；已在 §4 纪律补丁要求"声称已实现须答宿主文件:行号+符号名" |
| EvoTS 停滞只对 Revision | `stagnant_of` 是否引入"前进类算子才记停滞"细分（R192 裁决，**默认不动** — 改它会动 R188 已绿的链行为，风险 > 收益，除非有实测触发） |

---

## 三、顺序与依赖

```text
批1（R192）: [1结清] 论文落档提交  +  dev 面 F1 投影（低风险, 立即改善回归面信号密度）
批2（R193）: vocab 收口 + consume 显式化（两个 A 级，互不依赖, 可一批）
批3（R194）: gdi 补计算 + split 独立面（两个 A 级，都在 causal_chain/gates 面, 可一批）
批4（R195）: B 级三件（budget_ledger / granularity / dev F1 确认）—— **等用户拍板后再排**
批5（R196）: C/D 级档案化 — 纪律补丁写进 PROGRESS + core.py 注释清理 + R73 复核
```

**为什么 vocab/consume/gdi/split 排前**：全是"收口"性质（已有实现在两处，缺单一真源），符合"实现对齐设计"而不是反向改设计；且不碰进化主链的判据语义（门③⑥的输入口径不变）⇒ 回归风险最低。

---

## 四、每批的完成定义（防"声称=实测"落空）

1. **证据**：改前改后**同输入**的机器对比（如 vocab 收口前后 `KB_VOCABULARY == 旧两处并集`）。
2. **三层**：pytest 全量 + gate 8/8 + e2e rc=0（不接受"单文件过"）。
3. **不留双源**：收口类改动的验收 = 旧引用点**零命中**（grep 4 处全改）。
4. **知识档**：kind ∈ {patch, config_delta, rule}，gen=轮次，parent_state 的 commits/pytest 用**本次提交前**的实测值。
5. **README 自洽**：`T = count+1` 公式一次到位（R185 自指陷阱的教训）。

---

## 五、本轮的下一步（等你一句）

> 规划已摊开：**批1 可在你确认后直接开工**（论文落档提交 + dev 面 F1 投影）。
> 批4 的三件需要你拍板（budget_ledger / granularity / dev F1 是否按我判的做）。
> C 级我建议直接归档为"有据不做"，不再占用施工轮次——除非你要改这个判决。
