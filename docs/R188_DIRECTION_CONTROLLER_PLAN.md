# 时空统一之答 + R188 DirectionController 施工设计（方案 1 全做）

日期: 2026-10-12 · 前置: R186/R187 · 用户指令: "这样时间和空间是不是就统一了？我选择全做"

---

## 一、答「时间和空间是不是就统一了」——分两层, 一层是, 一层我要收紧口径

### ✅ 是的那一层: 决策函数统一了

R187 的结论复述一句: A(何时换向)与 B(向哪里换)汇合于**同一个决策点**:

```
pick_direction(state) -> (direction, candidate)
                  ↑ 时间面           ↑ 空间面
```

- "时间"被**收窄成一个可判定事件**: 停滞（无效 ∨ 增益≤噪声带）——EvoTS 原文
- "空间"被**收窄成一棵可枚举的树**: 候选树/组件层/同族 fn——Astar taxonomy 的同构物

⇒ 两者不再是"时间维度 vs 空间维度", 而是**同一个器的输入和输出**。
用一句可证伪的话说: **在 DWC 里, 时间序列的价值被折平成一次方向选择,
候选树的价值被折平成一个候选——它们在同一处相遇。**

### ⚠️ 我要收紧口径的那一层: 别把"都叫 direction"当成"统一了"

三重限定（缺一条就是吹）:

1. **折平是有损的**。时间序列（r1→r6 的完整分数轨迹）含**趋势信息**,
   折平成"停滞/未停滞"一个 bit 就丢了——比如"降但未停滞"和"微升"都非停滞。
   EvoTS 的原文判据就是这个 bit, 所以我按原文做, 但要如实标注:
   **这是按论文把时间降维, 不是时间维的完整保留**。
2. **候选树不是同质的**。DWC 的树跨两层（单 op 叶 vs root∧op 对）,
   而 A 的 fallback 链指的是**同层三方向轮换**。把两者焊死成一个 walker
   会混淆"换粒度"和"换方向"——所以实现上分开两个字段:
   `direction`（三方向轮换链）与 `granularity`（树上钻哪层）**各自记账**。
3. **04128 的"三方向"不是 DWC 的三方向**（R187 已记）: 它的三方向是
   环境难度分量。共同性是**控制流**共同（随机序+fallback+全败终止）,
   不是**本体**共同。别在文档里写成"论文规定 DWC 这么做"。

## 二、R188 施工前的最后取证（实测, 非推断）

### 2.1 REVERSE 的真实可用度 = 0（诚实记账）

```text
RULES: 7 条, component∈{prompt:4, control_flow:3}, target_layer 全 = assets
7 条 target = average/factorial/sum_first_n/reasoning_001-004
全部是"向前修"（补 range(n+1) / 补关键词族）—— 无一条是简化/回退
broken_dev 10 任务: code_repair 6 + knowledge_reasoning 4
```

⇒ **REVERSE 候选生成器在本任务面如实返回 None**。
R188 落 REVERSE 的形态因此定为三件, **不含硬造候选**:
a) 判定（REVERSE 入场条件: 同 component 上 FORWARD/LATERAL 都 stagnant）
b) 候选钩子（`reverse_candidates(sig)` — 表驱动, RULES 无 ⇒ None, 留**真实
   扩展位**; 将来有人加"简化"类 target 时这里是唯一登记点）
c) 台账痕迹（direction=REVERSE + candidates=0 一行, 不静默吞）

### 2.2 时序张力（实测后才敢定的接线点）

```text
loop.round(): sel = [self._pick_task(tasks)]   # 每轮只选 1 个任务
_run_one_task(): if not proposals -> propose_lateral  # 方向切换是任务内的二级步骤
```

04128 的 fallback 链是"一个 plan 失败 ⇒ 按序换下一个方向"（**任务内**）,
DWC 的现状正是**任务内换向**——接线点就是 `_run_one_task` 里那个 if。
✓ **同粒度, 不需要改 round 的结构**（最小手术保持结构完整性）。

---

## 三、R188 实现设计（三条规则全落）

### 3.1 新文件 `src/dwc/organs/direction_ctl.py`（纯函数, 可单测, 无副作用）

```python
DirectionState(round_no, attempts: Tuple[DirectionAttempt, ...])
DirectionAttempt(direction, stagnant: bool, score_gain: Optional[float],
                 verdict: str, n_candidates: int)

fallback_order(round_no, task_id) -> (EditDirection, ...)   # R2
    # 04128 "randomly order" — DWC 用 sha256(f"{round_no}|{task_id}")
    # 派生全序 ⇒ 可复现（不用真随机 — R? 纪律: 同输入同输出）
    # ★ 三方向全在内的排列（不全败不终止）

stagnant_of(attempt) -> bool                                 # R1
    # EvoTS 原文: invalid OR gain <= threshold
    # DWC 映射: verdict in blocked/error (invalid) OR gain <= 0.01 噪声带
    # DWC 映射: n_candidates == 0（无候选——本任务面的 unfixable_now）
    # ★ gain is None（首试/无前值）⇒ 不算停滞（没信息不下判 — fail-closed）

next_action(state) -> DirectionDecision                      # R1+R2
    # 沿 fallback_order 找第一个未试过的方向 ⇒ attempt
    # 全试过 ⇒ ALL_EXHAUSTED（R3 — 记台账, 不造第四方向）

reverse_candidates(sig, rules_index) -> List[Proposal]        # R3 的 REVERSE 半边
    # 表驱动: RULES 里 component 相同但"更简单"类的 target
    # ★ 当前 RULES 无此类 ⇒ 如实 []（不是 None 也不是 fabricated）
```

### 3.2 `direction.py` 增补（不删不改现有语义）

- `DecayLedgerEntry` / `DECAY_*`? **不, 不加新枚举**。
- 只加: `@dataclass DirectionAttempt` + `DirectionDecision` + `next_action`
  + `fallback_order` — 在 direction.py 内（同处存放, 防漂移; DirectionError 复用）

▸ **裁决: 全部放进 direction.py, 不新建 organ 文件** —— R187 说过"不新增器官",
`direction.py` 就是那个器官; 内部加件符合"结构完整性优先"（用户问过"开发别打乱结构"）。

### 3.3 `loop.py` 接线（**只改一处** — `_run_one_task` 的 if not proposals）

```python
# 现: if not proposals: → propose_lateral → 空 ⇒ blocked/return
# 新: state = DirectionState(round_no, attempts=self._dir_attempts[tid])
#     dec = direction.next_action(state)         # R1+R2
#     if dec.kind == "terminal":                  # R3 全败
#         self._dir_ledger_append(tid, dec)       # 台账
#         return blocked                          # 与现语义对齐
#     cand = generate(dec.direction, sig)         # FORWARD/LATERAL/REVERSE 三族
#     if not cand: 记 attempt(stagnant=True, n=0) ⇒ 继续 fallback（链不回退）
```

▸ **后置执行不改**: 候选仍走 replay 选择 + 六门复试（R174/R181 原样）。
   DirectionController 只决定"试哪个方向", 不判"能不能落地"（分工不变）。

### 3.4 台账 `archive/direction_ledger.jsonl`（每方向每候选 1 行, append-only）

```json
{"round": 1, "task": "code_fix_001", "direction": "LATERAL",
 "stagnant": false, "score_gain": 0.0, "verdict": "blocked", "n_candidates": 1,
 "why": "fallback_order[0]=FORWARD 未试 => 先试 FORWARD"}
```

▸ 台账是 **观察面**（自吞异常留痕不冒泡 — G7 同族纪律, 与 evidence 类一致）。

### 3.5 测试 `tests/test_r188_direction_controller.py`（≥5% raises 覆盖）

| # | 测什么 | 为什么重要 |
|---|---|---|
| 1 | fallback_order 可复现 + 三方向全在内 | 不用真随机 ⇒ 跨会话可重放 |
| 2 | fallback_order 不同 (round,task) 不同序 | 不是常量序（04128 要 vary） |
| 3 | stagnant: 无效/增益≤0.01/gain=None 三态 | EvoTS 判据的 bit 精度 |
| 4 | next_action 沿序推进 + 全试⇒terminal | R1+R3 闭环 |
| 5 | **REVERSE 表空 ⇒ 如实 [] 不 fabricated** | R188 唯一诚实点 |
| 6 | 反例锁: 三方向耗尽后**不造第四方向** | ensure_direction 值锁 |
| 7 | 接线后 loop blocked 语义不变（回归锁） | 行为面冻结 |

---

## 四、三层验证 → 知识档 R188 → git + README 自洽（+1 公式）
