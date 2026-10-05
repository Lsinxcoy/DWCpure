# 既有项目实测教训 · 母巢（SYNTHEX Autopoiesis）

> ## ⚠ 这是**反面案例库**，不是 DWC 的设计依据
>
> 本文件记录的是母巢的**实测事实**（坑真实存在）。
> 它**不规定** DWC 该长什么样 —— DWC 是全新项目，不沿用母巢架构。
> 引用本文件时请区分两件事：
>
> | 可以用 | 不该用 |
> |---|---|
> | "这个坑真实存在，设计时要检查" | "所以 DWC 必须有 X 组件" |
>
> 架构的正确来源是 **目标 + 约束 + 选择**，不是别人的失败。

---

---

## L1 · 定位外的东西不许进承重区

**实测**：母巢 25 个顶层子系统，7.06 MB 代码。用户定义的定位是 **2 件事**。

| 子系统 | 体积 | 是否在两件事内 |
|---|---|---|
| memory | 733 KB | ✓ 第①件事 |
| evolution | 932 KB | ✓ 第②件事 |
| **safety** | **751 KB** | ✗ **比记忆底座还大** |

`safety` 最大的承诺 `SeccompSandbox`（递归自指沙箱）**全仓零实现**。

> 取数：
> ```bash
> python scripts/score_subsystems.py     # 母巢仓库根目录，五维质量评分
> ```

---

## L2 · 自我评价必须从系统外部来

**实测**：母巢 5 个 P0 缺陷，同一个根因 —— "每一层都在声明自己工作正常，
而没有任何一层去验证这个声明"。

| 缺陷 | 声明 | 实测 |
|---|---|---|
| P0-1 | 机制 wired 了 | 登记的是 `effect=0.0` |
| P0-2 | 图更新完成 | `pass` 空实现 |
| P0-3 | 记忆已存 | 返回 `ok=True`，零副作用 |
| P0-4 | 熔断器探测过 | 硬编码 `return True` |
| P0-5 | 打分 0.7 | 与输入完全无关的常数 |

**母巢 3,808 个产物的 effect**：非零率 76.8%，但只有 **17 个不同取值** ——
多样性极低，说明"分数"本身缺乏分辨力。

**对照（ARSI 的做法）**：
```text
sealed_eval        26 个文件实现   ← 外部真值
verifier 三道门:oracle_ok / invalid_rejected / quality_ok
  其中 invalid_rejected 强制"空/无操作的世界必须失败"
  ★ 这正是母巢缺的:拒绝"形状正确但什么都没做"
```

> 取数：
> ```bash
> python -c "import sqlite3;c=sqlite3.connect('file:E:/SYNTHEX Autopoiesis/archive/synthex_main.db?mode=ro',uri=True);\
> print(c.execute('SELECT COUNT(*) FROM compile_log').fetchone())"
> ```

---

## L3 · 没有淘汰机制的系统必然变成屎山

**实测**（`selection_gate_log` + `mechanism_state`）：

```
编译成功(生)        1,447
编译失败(自然筛掉)   1,997
gate promote       3,284
gate hold          9,050    ← 占 71.1%，判定完什么都不做
gate prune           389    ← 判汰
★ 实际 enabled=0        5    ← 只有 5 个真被停用
淘汰/新增比 = 5 / 1,447 = 0.0035
```

且这 5 个是手写安全机制被门主动关的（`weibull_forgetting` / `thermodynamic` /
`g7_lyapunov` / `g8_attribution` / `g9_entropy`）——
**没有一个编译产物被淘汰过**。

**抢位冲突**：从 3,029 个落盘产物源码抽 `REPLACES` 字段：

```
声明要替代某机制的产物: 1,202个
抢位冲突（同一目标被多产物同时声称）: 1,062 个
★ active_compressor    526 个产物同时声称替代它
★ consolidation_engine  176 个
★ consolidation           96 个
```
没有任何重复检测机制，526 个全部 enabled。

**机制池增长**：09-29 +33 → **09-30 +734**（单日翻 6 倍）→ 10-01 +180。

---

## L4 · presence ≠ activity

**实测**：母巢 `MechanismHealth.snapshot()` 只返回三个字段：

```python
{"call_count": ..., "is_healthy": ..., "last_called": ...}
```

判据是 `obj is not None`。而 `check_all()` 里：

```python
if entry.call_count == 0:
    stale.append(name)     # ★ 把"从未被调用"说成"曾经活跃过"
```

本项目修复时补了六层 + `never_called` 独立分类（见母巢
`tests/test_mechanism_health_layers_20260930.py`，17 条锁，含破坏性对照）。

---

## L5 · 声称与实测必须分开报告

**实测**：母巢世界模型立项文档（`WORLD_MODEL_WIRING_PLAN.md`, 2026-07-29）
设计的核心三件，今天**一件都没落地**：

| 当时设计 | 2026-10-02 实测 |
|---|---|
| `_world_model_simulate` | ★ 不存在 |
| `_verify_world_model` | ★ 不存在 |
| `_wm_predictions` / `5D_scores` | ★ loop.py 里 0 次 |

**论文投入 vs 落地率**：深读 14 篇世界模型论文
（`docs/paper_deep/`，2026-09-15 "质变视角重读"批次），
核心机制落地 **7/13**；未落地的 6 篇里包含：

```
2609.14858  Dream-RSI 递归自我改进   ★ 最能解决当前问题的一篇
2608.17956  采样-验证危险律★ 第二关键
```

**同时**：母巢 `mwm_invocation` 445 万行（最大表），
`mother_world_model.py` 124 KB。而它真正实现的���
是"记账 + 预测 effect 数值"，不是"模拟动作选最优"。

> **母巢最贵的教训**：读了 14 篇、写了两轮深读、建了 445 万行台账，
> 而立项时想解决的那个问题（"只有 1 个候选，无法比较"）**至今没有实现**。

---

## L6 · 做加法容易，做减法没有纪律

**实测**（`git log --shortstat`，1,139 commits）：

```
2026-07   +96,804     -949       ratio=102.0    42 commits
2026-08   +1,218,418 -541,629ratio=  3.4   596 commits
2026-09   +258,914    -202,337   ratio=  1.3   501 commits
累计       +2,196,436  -744,915   ratio=  2.95
```

按删除量排前五的提交，**88% 的删除量（658,567 行）是仓库卫生**：

```
-262,063  git: archive 运行时产物移出版本控制   ← 文件还在磁盘
-205,420  B9-G03 恢复 D09← 恢复被误删的文档
-114,038  chore: 停止跟踪 >5MB 运行时产物         ← 文件保留本地
- 39,108  chore(P30b): 编译产物出库              ← 磁盘文件全留
- 37,938  chore(hygiene): G3 收口已跟踪∩.gitignore 清零  ← 同上
```

**剩下 11.1% 的删除（8.6 万行）里，最大的一笔是"纯机械搬移"**
（`loop.py Phase-Mixin 拆分 7500→2480 行`，功能未减）。

> **结论**：仓库干净了，产品复杂度没降。
> **产品层面 ≈ 只加不减。**

---

## L7 · 编译产物必须有外部真值才算数

**实测**：3,029 个落盘产物（`archive/compiled_mechanisms/`）静态扫描：

```
真正的代码占位符 (pass/TODO/stub)   0.6%    ← 编译器很老实
空 dict 常量                      43.5%
中位 92 行 / 最长 443 行
```

**但抽样读源码暴露了真相**—— 问题是**行为占位符**，不是代码占位符：

```python
# mech_ext_6521557d5cfbdd54.py —— 14 行
def run(self, context=None) -> dict:
    seed = sum(ord(c) for c in str(context)) | 1        # 输入字符串求和
    state = (1664525 * seed + 1013904223) % 2**32        # 线性同余
    return {'ok': state % 2 == 0, 'value': ...}
# ★ 有实现、能跑、返回符合 BEHAVIOR 的结构，但对任何输入都是伪随机数
```

这类产物**最容易通过"跑通了吗"的检查**，因而把编译成功率撑到 **96%**。

**更致命的是抢位**：
```python
# mech_ext_3b7f73dffbcc2042.py 与 mech_ext_d631971fd583b84f.py
REPLACES = 'consolidation_engine'     # ★ 两个都声称替代同一个机制
nodes = store.query('memory') if hasattr(store, 'query') else []
nodes = store.query('memory_node') or []# ★ 且第二个还写错了方法名
# try/except 包住, 失败就 nodes = [] → 永远返回"成功但什么都没做"
```

---

## 附：母巢的正面结论（不是全盘否定）

母巢静默前实测仍在正常运行，这些是真的：

```
记忆          208,039 节点
机制池        2,428 个（97% enabled）
编译成功率    40% → 96%（自动收敛，无人干预）
effect 账本   1,458,818 行
mwm 台账      4,452,989 行
测试          5,442 passed / 0 failed
```

**DWC 要继承的是它做对的部分**：
`MemoryFacade` 直连接管（不经HTTP）、触手单通道、七管 DAG、
编译→测→修→验证 的闭环骨架。**要避免的是它长歪的那部分。**