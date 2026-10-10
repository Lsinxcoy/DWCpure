# B 步施工方案（R189-B — train split 真无标签面扩容 + 无标签判据口径修洞）

日期: 2026-10-12 · 前置: A 步组件对账（R189-A, docs/COMPONENT_AUDIT_R189.md）

## 一、根因（机器取证, 不是猜）

R184 实测 `A_train = 1.0`（n=3 输出）。**退化根因不是集合小**——是口径洞:

```text
_train_outputs_consensus() 构造的 ctx（loop.py:729-736）:
  {"judge_success": None,      # 无标签 — 不喂判定
   "pass_rate":    None,
   "candidate_diff": "<observation 文本>",
   "vocabulary":   (),
   "component":    None,
   "parsed_ok":    True}
```

对 6 个 op 逐个算三态（ops.py 逐行核过）:

| op | 判据键 | train ctx 值 | 三态 |
|---|---|---|---|
| root_parse_ok | parsed_ok | True | **clean** |
| judge_verdict | judge_success | None | **abstain**（没判过⇒不知道） |
| nonempty_diff | candidate_diff | 非空文本 | **clean** |
| component_known | component+vocabulary | None+() | **abstain** |
| golden_leak | leakage_hits | **不在 ctx** | **abstain** |
| pass_rate_weak | pass_rate | None | **abstain** |

⇒ **每一条 train 输出都得到 {root_parse_ok: clean, nonempty_diff: clean, 其余 abstain}**
⇒ `a_train_weighted` 的 Σw·clean/Σw（abstain 不进分子分母）**恒等于 1.0**。

**这是 2607.12790 语义被架空的形态**: 论文的 A_train 是"ε 与 op 池在**无标注输出**上的一致度"——
现在 op 池在无标签面上**只有 2/6 能说话, 且这两个判的是"有没有输出"而不是"输出对不对"**
⇒ 一致度恒 1 = 该指标在本面**零分辨力**。

## 二、两个修法（按论文纪律裁决）

| # | 修法 | 内容 | 代价 |
|---|---|---|---|
| **F1** | **扩输入判据面（口径修洞）** | 无标签 ctx 补 3 个**不依赖 label** 的键: `exec_error`(执行异常名/None) / `n_checks`(观测到的断言数) / `output_chars`; op 池加 2 个**无标签面可判**的 op: `exec_ok`(无执行异常) + `evidence_rich`(候选 diff 信息量 ≥ 阈值) | 中 — ops 是判据面, 加 op 要有据。**依据**: 论文 2607.12790 的 op 定义是"原子检测器", drawback 检测**不认证正确**; 检测"执行有没有炸"与"证据有没有含量"是两个纯静态判据, 不引入 label ⇒ 语义合规 |
| **F2** | **扩题面** | train.json 6 → **15 条**: behavior 12（6 fn × 2 args 组合, **args 刻意选在 broken 初值上会炸/会错的**）+ keyword 3（impl_store 有文本才跑） | 低 — 纯数据 |

**为什么 F1 是主修**: 不修 F1, F2 扩到 50 条 A_train 还是 1.0（op 在该面无分辨力是结构性的）。修 F1 后, 扩题才有信号。

## 三、诚实的边界（不掩盖）

1. **F1 新加的 2 个 op 判"质量代理"不是判"正确性"**——`exec_ok` 只抓执行炸, `evidence_rich`
   只抓输出太短。它们**不能**让 A_train 变成"ε 在 train 上多对"的度量。如实标注:
   A_train 在新口径下 = "ε 与 op 在**可判质量代理**上的一致度", 仍不是真一致度
   （真一致度要 label, 而 train 无标签是论文前提）。
2. **不加 `judge_verdict` 的 train 面版本**——那等价于给 train 喂 label, 违反 R184 定的纪律。
3. **新的 2 个 op 进 DEFAULT_POOL ⇒ 影响既有 1298 测试的门③面**（树候选族从 21 → 29 个）⇒
   必须全量回归; 若破坏面大 ⇒ op 不进 DEFAULT_POOL, 改为 `TRAIN_POOL` 只喂 train 面
   （风险隔离, 但那样门③仍然只有 6 个 op — 分工: 门判"能不能用", train 判"无标签共识"）。

### 我选 **【TRAIN_POOL 隔离方案】——先落它，全量回归后再评是否升 DEFAULT_POOL**

理由: ① 门③是已绿 8/8 的行为面, 1298 测试锁着它的候选族尺寸 ⇒ 动它有回归风险 ② train 面加 op 只影响 `_train_outputs_consensus` 一条路 ⇒ 风险面天然隔离 ③ 若隔离版实测有效, 再走"是否升 DEFAULT_POOL"的单独立项（那时有数据支撑, 不是拍脑袋）。

## 四、施工清单

```text
src/dwc/organs/ops.py          + op_exec_ok, op_evidence_rich（无标签面 op, TRAIN_POOL src）
src/dwc/harness/loop.py        _train_outputs_consensus: ctx 补 exec_error/n_checks/output_chars;
                                池 = TRAIN_POOL（fallback 缺省）; _last_a_train_why 如实记 op 数
config/anchors/train.json      6 → 15 条（behavior 12 刻意含 broken 会炸的 args + keyword 3）
tests/test_r189_train_extended.py   ≥ 8: 两 op 三态全分支 + TRAIN_POOL 尺寸 + ctx 新键
                                       + A_train 不再恒 1 的实证（含负例）+ 旧纪律不回归
                                        （evaluate raise / 带 golden raise / dev∩train=∅）
```

## 五、验收

```text
pytest 1298 → 1306+ · gate 8/8 · e2e RC=0 · 知识档 R189 · git + README(+1 公式)
实测: A_train 在 15 条盘上 **不再恒 1.0**（有 positive/negative 混合）; 若仍恒 1 ⇒ 如实报"该面
零分辨" + 原因, 不放水
```
