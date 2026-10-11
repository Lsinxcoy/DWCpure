# R195 · Y2/Y3 落地 — granularity 三层显式化 + 停滞只对前进类（用户令"你来深度思考 做出最好的决策"）

日期: 2026-10-12 · 前置: R194(git 205)

**两件事都先取证再判，结论与 R192 规划时的预估有一处实质差异（Y3 的风险估价反了）。**

---

## 一、Y3 决策：停滞只对**前进类**记（采纳 EvoTS 原文口径）

### 1.1 论文依据（本轮落档的 2608.17933 §4.2 伪代码 L20 逐字）

```text
z_k ← (op = Revision) ∧ (q_k is invalid ∨ q_k − q_(prev) ≤ ϵ)
```

⇒ **停滞是 Revision（默认/前进算子）专属的**。EvoTS 的算子分工：

| EvoTS 算子 | 语义 | DWC 对应 |
|---|---|---|
| Revision | 精化当前最优（同 modeling direction） | **FORWARD**（同 component 签名命中） |
| Alternative Strategy | 换一个根本不同的 direction（**停滞触发**） | **LATERAL** |
| Recombination | 末步综合强轨迹 | **REVERSE**（DWC 的第三方向是"后退"，非重组 — R188 已记的差异） |

### 1.2 我在 R192 的预估**错了**（如实记账）

R192 规划写："Y3 默认不动 — **改它=动已绿链行为，风险>收益**"。

**实测推翻**（grep 全库 + 读调用点）：

```text
stagnant_of 生产调用数 = 0（只有 tests/test_r188_direction_controller.py 用）
next_action       用的是 tried_all（"试过"≠"停滞"）⇒ 不依赖 stagnant_of
loop._dir_pick_candidates 直接记 DirectionAttempt（stagnant 字段缺省 False）⇒ 不调 stagnant_of
```

⇒ **它是一个已定义、已测试、却从未被生产消费的判据函数**。改它 = 纯判据面语义对齐，**零链行为变更**。风险不是"高"，是"低"——我之前把"改判据函数"默认想成"动链条"了。

### 1.3 落地形态

```python
def stagnant_of(attempt) -> bool:
    """R1 · 一次尝试是否「停滞」（EvoTS 判据的 DWC 三态映射）。

    ★★★ R195 · EvoTS 原文口径落地: **只有前进类（FORWARD）尝试记停滞**
      （2608.17933 §4.2 L20: z_k ← (op=Revision) ∧ (invalid ∨ gain≤ϵ)）
      ⇒ LATERAL/REVERSE 的失败**不记"停滞"**——那是"该方向本身失败"
      （换向后仍失败 ≠ 原方向停滞; 两个布尔位独立, 与 EvoTS 的
      "Acceptance 与 stagnation 独立"同构）。
    ★ 为什么这不改链行为: R195 实测 stagnant_of 零生产调用
      （tried_all 管"试过", stagnant 管"停滞" — 两回事, 论文也分两位）。
    """
```

**验收测试**（新增，含一条论文出处锁）：
- `stagnant_of(FORWARD + verdict="blocked")` → True（原行为不变）
- `stagnant_of(LATERAL + verdict="blocked")` → **False**（新口径 — R195 之前会误报 True）
- `stagnant_of(REVERSE + score_gain=-0.4)` → False（同）
- 反向锁：`next_action` 仍把 LATERAL 失败计入 `tried_all`（不回退不循环）⇒ 链行为逐字节不变

---

## 二、Y2 决策：**不新造 granularity 组件，把隐式三层显式化**（收口，非发明）

### 2.1 取证 — DWC 早有 Astar 三层，只是没名字

```text
L1 方向层   Proposal.direction（R78 加的 Optional[str], ensure_direction 校验）
           + direction.py 三方向枚举（R188 DirectionController）
L2 组件层   Proposal.component（𝒦 9 ∪ 𝒦_meta 5, A1 唯一入口 check_component）
           + proposal.target_layer（LAYER_BY_ITEM: assets / architecture — R38 逐项裁决）
L3 干预层   Proposal.target + Proposal.patch（约束 4: 一 proposal 一处干预）
```

**Astar 的三级是 `(L1) Coarse-Grained Direction / (L2) Fine-Grained Modification Action / (L3) Concrete Modification Plan`** —— 与上面三行**逐层同构**。

### 2.2 为什么不新造 `granularity.py`

- R189 把 granularity 记成 ABSENT（"无 `(def|class)(Granularit|turn_boundary)`"）——**同款误判第二次**：它查函数名，而 DWC 的三层是**散在 Proposal.dataclass 字段里**的（没有叫 granularity 的函数）。
- 新造一个组件 = 第二真源（"A1 多来源"病的翻版）。R194 刚用 vocabulary.py 示范了正确做法：**收口成查询面，值不动**。

### 2.3 落地形态（新增 `foundation/granularity.py`，纯查询 + 零常量）

```python
GRANULARITY_LEVELS = ("L1_direction", "L2_component", "L3_intervention")

def granularity_of(proposal) -> Tuple[str, str, str]:
    """proposal ⇒ (L1, L2, L3) 三层记账（**只读字段, 不重算不新造**）。

    ★ 与 Astar 2608.27287 三级 taxonomy 的映射（论文给名字, DWC 已有字段）:
      L1 = direction（未声明 ⇒ "undeclared" 如实 — None 不是第四方向）
      L2 = component + ":" + target_layer（layer_of 缺 ⇒ raise 交调用方）
      L3 = target + "@" + patch 首 24 字符（记"改哪", 不记全文 — 防账本膨胀）
    """
def level_of(name: str) -> str: ...      # "L1"/"L2"/"L3" 或 raise
def is_coarser(a: str, b: str) -> bool:  # L1 < L2 < L3 全序（比较用, 不碰选优）
```

**不做的**（诚实边界，写进 docstring）：Astar 论文**未给完整类别表**（只一个 MoE 实例）⇒ DWC 不虚构类别枚举；本模块只做**已有字段的三层记账**，类别表等论文补或用户裁。

**验收测试**：
- `granularity_of` 对真 Proposal 返回三层，第三层含 `@` 分隔
- L1 未声明 ⇒ `"undeclared"`（**不**用 None 冒充——R188 "None 不是第四方向"同族）
- `is_coarser("L1","L2")` True / `("L2","L1")` False / 同级 False
- 防漂移锁：Proposal 若加/改粒度相关字段 ⇒ 本测试的字段清单断言红

---

## 三、两项的共同决策逻辑（为什么这么做）

| 判据 | Y2 | Y3 |
|---|---|---|
| 论文有据 | Astar 三级 taxonomy 给了名字 | EvoTS z_k 公式给了 `(op=Revision)` 前提 |
| DWC 已有 | **有**（Proposal 三组字段, 隐式） | **有**（stagnant_of 三态, 判据面） |
| 正确形态 | 收口成查询面（不新造组件） | 判据函数加 direction 前提（不动链） |
| R189 误判修掉 | 第二次"查函数名≠没实现" | "改判据=动链"想反 |

**两条都遵循同一条纪律**：**先取证"已有物是什么形态"，再决定"补"还是"收口"**——R189 已经在这栽过两次（gdi/split 查函数名），不能再栽第三次。

---

## 四、落地清单（R195）

```text
src/dwc/organs/direction.py          stagnant_of 加 FORWARD 前提 + docstring（EvoTS 口径）
src/dwc/foundation/granularity.py    新：三层记账查询面（纯函数, 零常量, 零新判据）
tests/test_r195_granularity_and_stagnation.py  新：两份验收 + 论文出处锁 + 防漂移锁
docs/CODE_DEBT_RECONCILIATION_R193.md  Y2/Y3 结案段（含"R192 预估错"的记账）
```
