# ARSI 作为 DWC 基础 · 可行性评估

> 日期：2026-10-03 · 判据：只报实测，区分「设计/实现/落地」
> 问题：DWC 的架构可不可以从 ARSI 的基础上做文章

---

## 一、结论

**可以，但不是"继承 ARSI"，而是"取 ARSI 的一个部件"。**

```text
ARSI 值得拿的         Mnemosyne 三区记忆（22KB，最小可读）
ARSI 不能拿的         它的进化机制（不落地，且方向与 DWC 原则 2 冲突）
ARSI 必须剥离的        host 耦合（它现在服务 3 个宿主，DWC 是独立 agent）
```

---

## 二、ARSI 实测画像

```text
规模        源码 214 py / 1,424 KB · 测试 72 py / 385 KB
git         有未提交改动 30+ 文件, 5 个新模块未提交
            最新 commit: "fix: production hardening"
结构        模块            文件   体积
            harness          54    253 KB   ← 最重
            world_model      15    185 KB
            adapters          9    114 KB   ← host 耦合
            iwm              11     84 KB
            meta             11     82 KB
            governor          7     62 KB
            empowerment       5     61 KB
            foundation       20    110 KB
            mnemosyne         4     22 KB   ← 记忆只有这么大
```

**harness(253KB) : mnemosyne(22KB) = 11.5 : 1**

★ 这直接说明 ARSI 的重心在**进化侧**，不在记忆侧。而 DWC 的定位是**记忆 + 自进化**双核。

---

## 三、ARSI 的进化：实测不落地

### 3.1 evolver 明确不自动改核心

```
src/arsi/harness/evolver.py 原文:
  "Every candidate must pass scope fence + critic before status=accepted.
   **Does not auto-edit core** — manifests are reviewable artifacts
   (HarnessX Change-Manifest discipline)."
```

### 3.2 梦境评估 delta 实测 42.8% 为零

```
archive/eval/compare_log.jsonl  1095 行实测:
  delta_score == 0.0       469 / 1095  (42.8%)
  dream_avg == fixed_avg   469 / 1095  (42.8%)
  recommendation:  DREAM_OK 897  (82%)
                   ROLLBACK_LIVE_REGRESSION 17

★ 42.8% 的"梦境评估"得出与固定评估完全相同的分数 ⇒ 梦没有带来差异
★ 且 17 次 rollback 全部是 LIVE_REGRESSION（真实退化），不是"梦比现实好"
```

### 3.3 增益样本的真相

```
非零 delta 626 个, 但抽样全部形如:
  delta=0.0975  fixed=-3.8025  dream=-3.705  rec=ROLLBACK_LIVE_REGRESSION

★ delta 是负数区间内的微小差（-3.8025 → -3.705），且同值反复出现
★ live_avg 已经掉到负数 ⇒ 系统在退化，不是进化
```

### 3.4 与母巢同病

```
母巢    best_genes → str() → 存进 branch_merges (167,753 行) → 无人消费
ARSI    manifest → 文件 (reviewable artifact) → 不自动应用
★ 两者都是"进化产物不落地"，只是形式不同:
  母巢是"落了但没人读"，ARSI 是"根本不落"
```

---

## 四、ARSI 的价值点：Mnemosyne 三区记忆

**这是 ARSI 唯一值得 DWC 直接拿的东西**（22KB，最小完整实现）：

```python
class MemoryZone(str, Enum):
    SELF       = "self"        # ARSI 身份 (永不删除, 改进算子不能重写核心)
    EXPERIENCE = "experience"  # 提炼的智慧 (跨 agent 共享, 可归档)
    PROXY      = "proxy"       # 宿主原始轨迹 (喂料, 蒸馏后可清理)
```

**三个配套机制（都有真实实现）：**

```
① DopamineGate    写入门 — "不是所有轨迹都值得存"
   should_consolidate(record) → record.importance >= 0.6
   score = importance*0.6 + surprise*0.4

② UtilityDecay    效用遗忘 — "忘掉无用的，不是忘掉旧的"
   new_utility = utility - decay_rate * (1 - freshness)
   低于 min_utility(0.05) → archive
   ★ 注释原文: "A memory accessed 5 times in 3 days is 'younger' than
                a 1-day-old memory never accessed."

③ EdgeDiscovery   主动关联发现 (语义检索优先, tag 交集兜底)
```

**★ 这与 DWC 的 D4（记忆可淘汰）直接对应，且已经实现了。**

---

## 五、ARSI 与 DWC 原则的冲突（必须处理）

| DWC 原则 | ARSI 现状 | 冲突 |
|---|---|---|
| **原则 2 · 判据必须在记忆之外** | ARSI 的 Grader/`drawback.py` 与记忆同在 `harness/` 下，且 evolver 可改 harness | ★ **直接冲突** |
| 原则 3 · 单一真值源 | ARSI 记忆在 SQLite，checkpoint 在 json，world_pool 在 json | ★ 真值源分散 |
| 原则 4 · 进化是独立子系统 | ARSI 的进化散在 harness/meta/world_model 三处 | ⚠️ 需重构 |
| D5 · 失败签名 (c,q,m) | ARSI 有 `terminal_subtypes.py`(13KB) + `digest.py` 失败聚类 | ✅ **可复用** |

**最关键的一条**：ARSI 的 `taxonomy.py` 写着 `c7 control/safety = Iron Laws — frozen`，但**判据（Grader/评分器）不在冻结名单里**。DWC 原则 2 要求的正是"判据必须冻结"，ARSI 没做到。

---

## 六、我建议的做法（三条路，选一）

### 甲 · 只取 Mnemosyne（推荐）

```
做法  DWC 自己写记忆内核, 只借鉴 ARSI 的三区 + 三道门的设计
      (不复制代码, 因为 ARSI 记忆基于它自己的 schema/store)
代价  要重写 22KB, 但换来干净的真值源
收益  避免 ARSI 的 host 耦合与判据混装
```

### 乙 · 复制 Mnemosyne 代码

```
做法  直接拿 mnemosyne/ 4 个文件 + foundation/schema.py 的 MemoryZone
代价  schema.py 里混着 EmpowermentDimension/BehaviorTrace 等 ARSI 专属类型,
      必须裁剪; store.py 也是 ARSI 的
收益  省 2-3 天
风险  ★ 会把 ARSI 的 host 假设带进来
```

### 丙 · 以 ARSI 为骨架改

```
做法  fork ARSI, 拆掉 adapters/host 耦合, 重构进化侧
代价  214 py / 1.4MB 的存量, 且 git 有 30+ 未提交改动
风险  ★★ 最高 —— 这正是母巢的老路（"在旧骨架上改"）
★ 我不建议
```

---

## 七、如果选甲，DWC 从 ARSI 具体拿什么

```
直接借鉴设计 (重写, 不复制代码):
  ① 三区隔离 SELF / EXPERIENCE / PROXY
     ★ 但 DWC 要加一条: 判据单独成区, 且不进任何可进化范围
  ② DopamineGate 写入门 (importance*0.6 + surprise*0.4)
  ③ UtilityDecay 效用遗忘 (不是时间遗忘)
  ④ EdgeDiscovery 主动关联

可直接复用 (代码级, 无 host 依赖):
  ⑤ terminal_subtypes.py (13KB) — 失败签名细分类
     ★ 对应 DWC 的 D5 (c,q,m), 且是 ARSI 里少见的"真实现"
  ⑥ digest.py (12KB) — 轨迹 → 失败聚类 (规则优先, 无 LLM)
     ★ 对应 DWC 原则 1 (进化养料来自记忆)

不拿:
  ✗ adapters/ (host 耦合, DWC 是独立 agent)
  ✗ meta/ + world_model/ (进化侧, 且实测不落地)
  ✗ harness/ 的大部分 (判据与进化混装, 违反原则 2)
```

---

## 八、一个必须先回答的问题

```
DWC 要不要保留 ARSI 的"多宿主"设计?
  ARSI 现在服务 hermes / mimo-desktop / synthex-mothernest 三个宿主,
  它的 quarantine.py 甚至专门隔离过 synthex(母巢) — "synthex produced 100%..."

  但 DWC 的定位是 "独立 agent, 自带 LLM 调用"
  ★ 如果 DWC 不做宿主服务, adapters/ 整块(114KB)都不需要
```

**这一点决定"取 ARSI"的规模：不做宿主 ⇒ 只拿记忆层（甲）；做宿主 ⇒ ARSI 的 adapters 有参考价值，但要小心把它的耦合带进来。**
