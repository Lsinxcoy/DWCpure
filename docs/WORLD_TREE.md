# DWC · 世界树（World Tree）：前瞻模拟与收束

> 2026-10-03 · 用户提问："有没有可能设计类似世界树一样的设计，用来跑验证或者预测，
> 最后收束成最好的选择"
> 判据：ARSI world_model/ 14 文件实测 + 全仓调用点 grep + 论文原文
> 前置：`ARCHITECTURE.md` §2.3 / §4.7 · 原则 9 / 原则 12 · `docs/WORLD_MODEL_AUTHORITY.md`

---

## 一、★ 先说结论：想法成立，而且**ARSI 已经做了三套，但没做"收束"**

```text
★ 用户的想法 = 前瞻模拟 (world tree) + 收束 (选最好的)。
  ★ 实测: ARSI 有三套树, 但**全部是"回放"而不是"前瞻"**, 且**没有收束**。

三套树的实测定位:
  DiscoveryTree            全仓提及 29 次   记录已发生的探索 (回放)
  ReplayWorld              全仓提及 24 次   回放已记录的世界
  CounterfactualSimulator  全仓提及  3 次   ★ 前瞻模拟 —— 但**只被构造, 从不调用**

★ 决定性证据 (宽口径 grep counterfactual.simulate|compare_interventions|
  adaptive_depth|stats, 全 src/ 递归): **命中 0 处**。
  core.py:110  self.counterfactual = CounterfactualSimulator(...)   ← 唯一提及
  ⇒ 前瞻模拟器在 ARSI 里是一个**构造了但从未使用的组件**。

★ 而"收束"更没有:
  grep MCTS → **0 处**;  grep UCB → 2 处 (只在 harness/strategy_bandit.py);
  grep monte → 0 处
  ⇒ ARSI 在 world_model 里**没有任何树搜索/收束算法**。
```

---

## 二、三套树各自的机制（逐文件实测）

### 2.1 DiscoveryTree — 记录已发生的探索（回放）

```python
# discovery_tree.py 原文 docstring
"""Discovery Tree — structured tree from behavior traces.
Inspired by Dream-RSI (arXiv:2609.14858):
- Each node = one attempt with parent, children, outcome, score
- Tree structure enables replay simulation
- Alternative policies can navigate the recorded tree
"""
```

**★ 节点字段（DiscoveryNode 原文）**：

```python
    id: str
    parent_id: Optional[str]
    action: str
    agent_id: str
    outcome: str
    score: float
    cost: float              # execution cost (tokens, time, etc.)
    parallel_group: int      # which parallel batch this belonged to
    depth: int
    timestamp: str
    metadata: dict
    children: list[str]
```

**★ 收束机制的真相（`_compute_scores` 原文）**：

```python
    def _compute_scores(self) -> None:
        """Compute aggregate scores for internal nodes."""
        for node_id in reversed(list(self.nodes.keys())):
            node = self.nodes[node_id]
            if node.children:
                child_scores = [self.nodes[cid].score for cid in node.children if cid in self.nodes]
                if child_scores:
                    # Internal node score = max of children (best discovery)
                    node.score = max(child_scores)
```

```text
★★ 这就是 ARSI 全部的"收束": **内部节点 = 子节点的 max**。
   · 不是搜索, 是**后向聚合** (自底向上取最大)
   · 没有前瞻, 没有剪枝, 没有回传
   · get_best_path() 也只是"沿 max 链回溯到根"

★ 而且它有个硬缺陷: `reversed(list(self.nodes.keys()))` 依赖 dict 插入序 ——
  节点是按 traces 顺序插入的 (父子同批), 所以 reversed 恰好是从叶到根。
  ⇒ 这是**隐式依赖插入顺序**的算法, 不是显式的拓扑排序。
    若节点插入顺序变化 (如分批构建), 聚合会出错。
```

**★ 回放机制（`replay_alternative` 原文）**：

```python
        for round_num in range(max_rounds):
            eligible = self._get_eligible(observed)
            if not eligible: break
            batch = policy_fn(list(eligible), observed)
            if not batch: break
            for nid in batch:
                node = self.nodes[nid]
                for child_id in node.children:
                    if child_id not in observed and child_id in self.nodes:
                        observed.add(child_id)
                        child = self.nodes[child_id]
                        total_cost += child.cost
                        explored_nodes.append(child_id)
        ...
        beta1 = 0.1  # cost penalty
        beta2 = 0.05  # parallelism bonus
        replay_score = best_score - beta1 * total_cost + beta2 * parallelism
```

```text
★ 关键: "Replay returns recorded outcomes (**no re-execution**)":
  它不重新执行, 只"揭示"已记录的节点。
  ⇒ 这是**回放仿真器**, 不是前瞻模拟。
★ 用途 (2609.14858 §5.1 的负面结果): 回放**优于**把历史当 prompt guidance。
```

### 2.2 ReplayWorld — 论文忠实的发现树模拟器

```python
"""Replay World — paper-faithful Dream-RSI discovery-tree simulator.
Based on arXiv:2609.14858 §3 + Appendix B.2.

Key formalism:
- Eligible A(T) = {root} ∪ {v ∈ T : v is a leaf of observed prefix}
- Action C ⊆ A(T; W), |C| ≤ W
- Child(v; T_full, T_obs):
    v ≠ root: unique recorded child, if still unrevealed
    v = root: earliest-created child not yet in observed (branch opening)
- Replay is deterministic and prefix-only: **unrevealed scores stay unknown**
"""
```

```text
★ 与 DiscoveryTree 的差别: 它严格实现论文的 A(T) 与 Child() 语义,
  且"未揭示的分数保持未知" —— 这防止了"偷看未来"。
★ 但本质仍是回放 (deterministic + prefix-only)。
```

### 2.3 ★ CounterfactualSimulator — 前瞻模拟（但从未被调用）

```python
"""SIWM Layer 3 — Counterfactual Simulator.
Uses Layer 2 dynamics to iteratively expand multi-step predictions.
Enables Governor's high-risk decision simulation.
"""
```

```python
    def simulate(self, state, intervention, depth: int = 3) -> list[dict]:
        current = state
        for step in range(depth):
            pred = self.dynamics.predict_transition(current, intervention)
            if pred.get("confidence", 0) <= 0:
                trajectory.append({..., "predicted": False, "reason": "no_dynamics_data"})
                break
            delta = pred.get("predicted_delta", {})
            new_eta = max(0.0, min(1.0, current.eta + delta.get("eta", 0)))
            ...
            current = current.model_copy(update={"phi": new_phi, "eta": new_eta})

    def compare_interventions(self, state, interventions, depth: int = 2) -> list[dict]:
        for intervention in interventions:
            trajectory = self.simulate(state, intervention, depth)
            ...
            eta_improvement = state.eta - final_eta
            score = eta_improvement * avg_conf
        results.sort(key=lambda x: x["score"], reverse=True)
        return results
```

```text
★★ 这个才接近用户的想法 (前瞻 + 比较 + 排序)。但:

  ① ★ 它**从未被调用** (grep 0 处)
  ② ★ 它只做**单链展开** (一个 intervention 展开 depth 步), 不是**树**
     —— 没有分支, 没有回溯, 没有跨 intervention 的共享节点
  ③ ★ 它的 score = eta_improvement × avg_conf, 而 avg_conf 就是那个
     "样本数/20" 的假置信度 (见 WORLD_MODEL_AUTHORITY §二)
     ⇒ 前瞻结果的排序**建立在不含正确性信息的置信度上**
  ④ ★ 它在 confidence ≤ 0 时直接 break —— 而 confidence=0 意味着
     "这个动作没见过", 恰好是**最需要前瞻**的时候
     ⇒ 越是不确定的地方, 它越不模拟
```

---

## 三、★ 用户的"世界树"想法：成立，但要加三条约束

```text
★ 用户的提法: "类似世界树, 用来跑验证或者预测, 最后收束成最好的选择"
  = 前瞻模拟 (展开未来) + 收束 (选最优)

★ 这个方向是对的, 而且比 ARSI 更进一步:
  ARSI 有前瞻模拟器 (未用) 但**没有树**; 有树 (DiscoveryTree) 但**只是回放**。
  用户要的是**两者的结合**: 前瞻展开成树 + 收束选优。
```

### ★ 但必须加三条约束（否则会重犯已知的病）

```text
约束 1 · ★ 树必须是"想象的", 不能冒充"发生的"
  依据: ARSI 的 DiscoveryTree 节点带 score/cost/outcome —— 那是**已发生**的。
        若前瞻树用同样字段, 会与真实痕迹混淆。
  ⇒ DWC 的想象节点必须显式标记 provenance="simulated", 且**不许进 judge**
    (judge 只判真实执行结果, 不判模拟结果 —— 否则违反原则 1)

约束 2 · ★ 收束的判据不能来自世界模型自己
  依据: ARSI 的 compare_interventions 用 avg_conf 排序, 而 avg_conf 是
        "样本数/20" 的假置信度 (WORLD_MODEL_AUTHORITY §二 实测)。
  ⇒ 世界树可以**生成候选**, 但"哪个候选更好"必须由外部判据定:
     甲 用 judge 在 dev split 上的真实分数 (推荐)
     乙 用"想象树与真实回放树的差异"作为不确定性度量, 而非直接排序
     ★ 禁: 用世界模型自算的 confidence 当收束判据

约束 3 · ★ 树必须与"回放树"共用结构, 不另起一套
  依据: ARSI 已有三套树 (DiscoveryTree 29 次 / ReplayWorld 24 次 /
        CounterfactualSimulator 3 次), 前两套高度重叠。
  ⇒ DWC 只许**一套树结构**, 通过字段区分"真实节点"与"想象节点"。
     ★ 判据: grep "class .*Tree" 结果数 == 1
```

---

## 四、★ DWC 的世界树设计（提案）

### 4.1 一套树，两种节点

```text
┌────────────────────────────────────────────────────────────────────┐
│  world_tree/   (唯一树结构)                                        │
│                                                                    │
│  WorldNode                                                        │
│    id / parent_id / children[]                                     │
│    action / action_params                                          │
│    ★ provenance:  "observed" | "simulated"   ← 关键字段            │
│    ★ confidence_source:  "judge_dev" | "dynamics" | "none"          │
│    score: Optional[float]      ← observed 才有真值                  │
│    cost: float                                                     │
│    depth / parallel_group / timestamp                              │
│    ★ branch:  从哪个真实节点分叉出来的 (simulated 节点必填)          │
└────────────────────────────────────────────────────────────────────┘

★ observed 节点  = 真实执行过 (来自 actor 痕迹, 见 ACTOR_DESIGN)
★ simulated 节点 = 前瞻想象 (来自世界模型展开)
★ 两者**同一结构**, 靠 provenance 区分 —— 满足约束 3
```

### 4.2 ★ 收束：三段式（而不是"max of children"）

```text
ARSI 的收束 = max of children (后向聚合, 无搜索)
DWC 的收束 = 三段:

  ① 展开 (expand)
     从当前真实节点出发, 用世界模型展开候选动作
     ★ 展开深度由 iwm 决定 (ARSI 的 adaptive_depth 思路:
        eta 高 → 深度短; 但它的阈值 0.15/0.30/0.50 是硬编码的, DWC 要外部化)

  ② 评估 (evaluate)  ← ★ 关键: 判据来源
     observed 节点: 用真实分数 (judge / tool_receipt)
     simulated 节点: 用**不确定性**而非"预测分数"
       ★ 理由: 模拟的分数不可信 (约束 2)
       ⇒ 模拟节点只提供 "这条路可能通向什么" + "多不确定"
         不提供 "这条路更好"

  ③ 收束 (select)
     ★ 不是选"模拟分数最高的", 而是选**信息增益最大**的:
       哪个候选动作能最大程度减少不确定性?
     ★ 依据: 2609.04128 的 EL 调度器 (B=8, τ=6/8) 就是"按信息量选"
       + 2609.24972 的 ν_t(H') 新颖度奖励 (噪声带内靠新颖度换取接受)
```

### 4.3 ★ 为什么收束要选"信息增益"而不是"最高分"

```text
★ 三条理由 (都有实测支撑):

理由 1 · 模拟分数不可信
  ARSI 的 compare_interventions 用 avg_conf 排序, 而 avg_conf 不含正确性信息
  (WORLD_MODEL_AUTHORITY §二: confidence = count/20)。
  ⇒ 用模拟分数收束 = 用一个不含正确性信息的数排序。

理由 2 · 有论文级依据: 噪声带内微小提分不足以被接受
  2609.24972 式 17 原文:
    w_s·ΔS − w_c·ΔC + w_n·ν_t(H') > 0
  ★ "a score increase that remains within δ cannot by itself make a
     coding candidate admissible" (coding instance 设 w_s = 0)
  ⇒ 收束要靠**新颖度/降成本**, 不是靠模拟出来的微小提分。

理由 3 · EL 调度器已是"按信息量选"的现成答案
  2609.04128: 按 lineage pass-rate 采样, 而非随机全池
  ★ 零模型依赖 (只需 8 次布尔观测)
  ⇒ 收束的判据可以用同一套: 哪个分支的 pass-rate 最不确定, 先探它。
```

### 4.4 ★ 与"世界模型驱动决策"的接口（不越界）

```text
★ 世界树的职责边界 (呼应 §2.3 三层驱动):

  世界树 → 产出候选动作 + 各自的不确定性
       ↓
  世界模型 → 门控决策 (选哪个)  ← ★ 决策仍在世界模型
       ↓
  actor → 执行真实动作
       ↓
  真实结果 → 回填 observed 节点 → 树生长

★ 判据: 世界树**不许自己决定执行哪个动作** ——
  它只提供"候选集 + 不确定性", 决策由世界模型 + 守卫做出。
  ⇒ 这样它不会变成"第二决策核心" (违反原则 6 / 原则 12)。
```

### 4.5 ★ 与 judge 的接口（约束 1 的落地）

```text
★ 硬规则: judge **只判 observed 节点**, 不判 simulated 节点。

  依据: 原则 1 —— judge 的判据必须来自系统之外。
        模拟结果不是"外部事实", 它是世界模型的输出。
        让 judge 判模拟结果 ⇒ judge 在判世界模型的想象 ⇒ 间接自评。

★ 判据 (W3): judge 的输入不得含 provenance="simulated" 的节点。

★ 但 simulated 节点**可以**通过一个合法路径获得真值:
  当它被 actor 真实执行后 ⇒ provenance 从 simulated 改为 observed
  ⇒ ★ 这时它才进 judge。
  ★ 判据: 节点只能单向 simulated → observed, 不可逆。
```

### 4.6 ★ 可机械检查的判据（gate.py 候选，6 条）

```text
W1 · 只有一套树结构
   grep "class .*Tree" 结果数 == 1
   依据: ARSI 三套树 (29/24/3 次提及), 前两套高度重叠

W2 · 节点必带 provenance
   每个 WorldNode 必须有 provenance ∈ {observed, simulated}
   依据: ARSI DiscoveryTree 的节点无此字段 ⇒ 想象与真实混淆

W3 · judge 不判想象节点
   judge 输入不得含 provenance="simulated"
   依据: 原则 1 (判据在系统之外)

W4 · 收束判据不来自世界模型自算
   收束函数的输入不得含 dynamics 的 confidence
   依据: ARSI compare_interventions 用 avg_conf 排序 (假置信度)

W5 · 想象节点只能单向转真实
   provenance 只许 simulated → observed, 不许反向
   依据: 防"用想象冒充已发生"

W6 · 展开深度外部化
   树的展开深度不得硬编码
   依据: ARSI adaptive_depth 的 0.15/0.30/0.50 是硬编码阈值
```

---

## 五、★ 与已有决定的衔接（不冲突检查）

```text
① 与 §4.7 world_model (环节⑥ 探索) 的关系
   世界树是环节⑥ 的**实现形态** —— 探索 = 在树上展开 + 收束。
   ★ 不新增器官, 是 world_model 内部的一个模块。

② 与"不要影子"的关系 ★ 重要
   世界树的"想象节点"**不是影子** —— 区别:
     · 影子: 观测真实机制, 等它转正 (永久搁置)
     · 世界树: 不观测任何真实机制, 它生成**候选**供决策
   ★ 判据: 世界树不许有"等待期/转正"形态。
     它的 simulated 节点要么被执行 (转 observed), 要么被丢弃 (不进任何账)。

③ 与因果链 (CAUSAL_CHAIN_VS_BUS) 的关系
   世界树的节点 id 进因果链: decision_id → turn_id → trace_id
   ★ 但 simulated 节点**不进链** —— 链只记真实发生的。
   依据: 原则 11 (因果链) 的前提是"真的发生了因果"。

④ 与 judge 三层 (JUDGE_LAYERS) 的关系
   世界树的不确定性度量可以喂给 L3 独立审计 (作为"该查哪里"的线索)
   ★ 但 L3 的输出仍不许做训练信号。
```

---

## 六、诚实边界

```text
① "CounterfactualSimulator 从未被调用" 是宽口径 grep 结果
   (counterfactual.simulate|compare_interventions|adaptive_depth|stats,
    全 src/ 递归, 命中 0 处)。
   ★ 未验证: 若有动态调用 (getattr) 会漏。已用 4 种方法名各查一遍, 结论一致。

② ★ 已宽口径复核 (13 种搜索算法名): beam / best_first / alpha_beta / minimax /
   negamax / a_star / astar / bfs / tree_search / search_tree 全部 **0 命中**;
   · "dfs" 4 处 —— 逐行核实后是 continuous_dream.py 的**树遍历** (`_dfs(nid)`
     递归走 parent→children), 不是搜索算法
   · "rollout" 4 处 —— 逐行核实后是论文术语 (core.py:1085 "after a rollout,
     tree T_t is appended to history" / taxonomy.py:62 描述 ModularRSI 的采样)
   ⇒ "ARSI 在 world_model 里无树搜索" 结论**确认**。

③ ★ 已核实一致性: _compute_scores 把内部节点设为 max(children),
   get_best_path 则 `max(leaves, key=score)` 后沿 parent_id 回溯 ——
   两者**一致** (内部节点分 = 最优子叶分, 所以沿最大叶回溯即最优路径)。
   ★ 但发现另一处: get_best_path 回溯用 `current.parent_id`, 而
     _compute_scores 用 `reversed(list(self.nodes.keys()))` 隐式依赖插入序 ——
     两者**算法依据不同** (一个用显式 parent 链, 一个用 dict 序)。
     在当前构建方式下结果相同, 但若分批构建会不一致。

④ 世界树的设计 (§四) 是我的提案, 不是论文的。
   ★ 但三条约束各有实测依据 (ARSI 的具体缺陷)。
   ★ "收束选信息增益"有 2609.04128 EL 调度器 + 2609.24972 式17 两条依据。

⑤ ★ 未定: 树的**剪枝策略** (什么时候停止展开) —— 我只给了"深度由 iwm 定",
   没给具体判据。ARSI 的 adaptive_depth 是 3 档硬编码, 不可直接抄。

⑥ ★ 未定: 树与记忆七管的接口 —— 想象节点存哪? (PROXY? 不存?)
   我倾向"不存" (只在内存, 执行后才进链), 但这需要确认。
```

---

## 附：存证

```text
ARSI 源码: src/arsi/world_model/discovery_tree.py (DiscoveryNode + _compute_scores
             + replay_alternative 全文)
           src/arsi/world_model/replay_world.py (docstring + 21 个方法签名)
           src/arsi/world_model/counterfactual.py (simulate / compare_interventions 全文)
           src/arsi/world_model/siwm.py (三层结构)
           src/arsi/core.py:47/48/110/114/1072/1149/1621/1654 (树的全部提及)
           ★ 宽口径 grep: counterfactual.* 调用 0 处 / MCTS 0 处 / monte 0 处
论文报告:  docs/papers/2609.14858.md (§3 发现树 + §5.1 replay 优于 guidance)
           docs/papers/2609.04128.md (EL 调度器 B=8 τ=6/8)
           docs/papers/2609.24972.md (式17 新颖度奖励)
前置文档:  ARCHITECTURE.md §2.3 / §4.7 / 原则 9 / 原则 12
           docs/WORLD_MODEL_AUTHORITY.md · docs/CAUSAL_CHAIN_VS_BUS.md
```
