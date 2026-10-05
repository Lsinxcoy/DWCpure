# Nexus 独立审计（更正版）

> 2026-10-03 · 判据：只报实测，区分设计/实现/落地
> ★ 本文更正上一份《ULTRA_NEXUS_MEMORY_PIPES.md》中对 Nexus 的错误陈述
> 触发：用户追问"你看nexus系统了吗" —— 我确实没独立审，是照 Ultra 推的

---

## 〇、我必须更正的四条

```text
上一份文档里我写:
  ① "Ultra/Nexus 两边 memory/ 内容同源"        → 错. Nexus 有 17 个独有文件
  ② "Nexus CNS 与 Ultra 同源"                  → 错. Nexus 多一个 cns/nexus.py (20.5KB) 统一中枢
  ③ "Nexus 无运行证据 / 已停"                   → 错. Nexus 有 api_server.log 真实运行日志
  ④ "access_count>0: ultra 11.6%" 推给 Nexus   → 错. Nexus 是 96.2% 有访问 (3.8% 未访问)

★ 根因: 我只对 Nexus 做了目录扫描 + 与 Ultra 的 hash 对比, 
  没有读它的独有文件、没有读它的日志、没有查它的库。
```

---

## 一、实测：Nexus vs Ultra 的真实差异

```text
源码对比 (逐字节 md5):
  两边都有且完全相同: 149 文件
  两边都有但内容不同: 104 文件
  ★ 仅 Ultra 有: 0
  ★ 仅 Nexus 有: 17 文件

Nexus 独有 17 文件 (这是 Ultra 完全没有的):
  cns/nexus.py                 23,578 B  ★ 神经系统统一中枢
  evolution/experience_bank.py 26,073 B  ★ 双层经验银行 (arXiv 2607.14159)
  evolution/effect_tracker.py  11,167 B  ★ 机制效果量化
  evolution/hindsight_skill.py 10,097 B  ★ 事后技能挖掘
  evolution/selection_gate.py   3,580 B  ★ 影子 A/B 选择门
  evolution/semantic_to_param.py 4,303 B
  harness/case_adaptation.py   11,705 B
  harness/diagnosis.py         10,624 B
  harness/harness_space.py      9,093 B
  integration/host_agent.py    12,617 B  ★ 宿主抽象层 (解任务源)
  integration/capability_inbox.py 7,246 B
  integration/hermes_adapter.py 5,422 B
  integration/llm_config.py     7,023 B
  integration/mechanism_sandbox.py 6,061 B
  mechanisms/handbook.py       14,340 B
  skills/proposer.py            3,203 B
  client.py                     6,433 B
```

**★ 结论：Nexus 是 Ultra 的"神经系统化"版本，不是副本。我上一轮说"同源"是错的。**

---

## 二、Nexus 的核心增量：`cns/nexus.py` 统一中枢

### 2.1 定位（源码原文）

```python
"""Nexus — 神经系统统一中枢.

设计定位(2026-07-19 架构决策):
    Ultra = 外挂记忆 / 自进化生命体的大脑.
    Nexus 是这套神经系统的**统一神经中枢**, 统辖:
      - 机制层: 236 基本盘机制 + 动态层(T3/T4 编译产物)
      - 7 管道: remember/recall/evolve/learn/reflect/dream/maintain
      - 两层共享记忆:
          ① 知识记忆 (MinervaStore, 7管道共享)  —— 数据层, Nexus 引用不替换
          ② 机制经验记忆 (effect 账本)           —— 机制共享"什么有效/有害"
      - 效果路由: 动态机制实战更优则接管基本盘对应功能(fallback 永驻)
      - 突触修剪: 效果账本负向机制自动 deactivate

关键不变量(防回归):
    - Nexus 是**仲裁者**, 不是执行者. 机制执行后端仍是 life.py 的实例(self.x).
      dispatch() 查状态/效果/路由后, 转调 self.x.method(), 绝不双重执行.
    - 不吞并 MinervaStore / ModelRouter (数据层/后端层, 仅引用).
    - 236 基本盘机制全注册, 零丢失.
"""
```

### 2.2 ★ 这是 DWC "两层记忆"的直接原型

```text
Nexus 明确写了"两层共享记忆":
  ① 知识记忆 (MinervaStore, 7管道共享)   ← 数据层
  ② 机制经验记忆 (effect 账本)            ← "什么有效/有害"

★ 对照 DWC 的设计:
  DWC 我写的: EXPERIENCE(经验) / PROXY(痕迹) / SELF(身份)
  Nexus 写的: 知识记忆 / 机制经验记忆
  ★ 两者是同一思路的两套命名 —— Nexus 已经把它跑起来了
```

### 2.3 `dispatch()` 自带效果遥测（★ 解决"记忆是否被使用"）

```python
def dispatch(self, name, method="run", context=None, *args, **kwargs):
    """仲裁调用机制. 不双重执行 — 转调 life.py 实例, 仅记账+路由."""
    # 记账
    self._invoke_count[name] = self._invoke_count.get(name, 0) + 1
    self._last_invoked[name] = time.time()
    entry["invoke_count"] += 1
    entry["last_invoked"] = time.time()
    # Phase 0: 执行前后自动测量效果
    before = self.effect_tracker.snapshot_system(self._store)
    before["output"] = None
    try:
        result = fn(*args, **kwargs)
        after["output"] = ...
```

**★ 这是 DWC 原则 7（记忆必须证明"被使用"）的代码级实现 —— 母巢和 Ultra 都没有。**

### 2.4 `prune_harmful()` 突触修剪

```python
def prune_harmful(self, threshold=-0.3) -> list[str]:
    """效果账本负向机制自动 deactivate(突触修剪). 基本盘不删, 仅动态层可修剪."""
    for name, entry in self._mechanisms.items():
        if not entry.get("is_dynamic", False):
            continue          # ★ 基本盘永驻, 不修剪
        if inv >= 3 and eff <= threshold:
            entry["status"] = "disabled"
            del self._dynamic[name]
            # 同时撤销 route_override
```

**★ 这正是 DWC 要的"淘汰三层判据"的现成实现**：基本盘永驻 + 动态层按效果修剪。

---

## 三、Nexus 有真实运行日志（我上一轮说"无证据"是错的）

### 3.1 api_server.log 实测

```text
文件: E:/Prometheus Nexus/api_server.log  (34,102 B, mtime 07-21 09:31)
行数: 287

关键事件计数:
  learn        155
  T4 compiled    5     ← 论文编译真的在跑
  T4 emitted     5
  沙箱编译返回None 5     ← ★ 全部失败
  reflect       12
  maintain      10
  heartbeat      9
  CNS            8
  evolve         1
  recall         0     ← ★ 零 recall
  dream          0     ← ★ 零 dream
  ERROR          1
  WARNING       31
```

### 3.2 真实运行片段

```text
心跳 (真的在跑):
  INFO: Heartbeat thread started (interval=3600s)
  INFO: Heartbeat: learn OK (1 nodes)
  INFO: Heartbeat: learn OK (1 nodes)
  INFO: Heartbeat: learn OK (1 nodes)
  WARNING: Heartbeat: learn returned empty_scan
  INFO: Heartbeat: learn OK (2 nodes)

CNS (真的在跑):
  INFO: CNSOrchestrator subscribed to all 7 pipeline events
  INFO: CNS: rumination produced knowledge (skills=1 routed=7), triggering maintain
  INFO: CNS: threshold learn_to_reflect_min_nodes updated to 2      ← 运行时调阈值
  INFO: CNS: threshold reflect_to_evolve_max_score updated to 0.4   ← 运行时调阈值
  INFO: CNS: rumination produced knowledge (skills=1 routed=1), triggering maintain

T4 论文编译 (真的在跑, 但全失败):
  INFO:  Omega: T4 compiled mechanism paper_2607_16193v1 from https://arxiv.org/abs/2607.16193v1
  INFO:  Omega: T4 paper_2607_16193v1 emitted to host (accepted=True)
  WARNING: Omega: T4 paper_2607_16193v1 沙箱编译返回 None, 未挂载

learn 提炼技能 (真的在跑):
  INFO: HindsightSkillMiner: learn 提炼 1 条技能 -> Playbook steps=1
  INFO: [Rumination:incremental] 完成 relearned=71 mappings=20 skills=1
  INFO: learn: registered playbook from rumination incremental (1 steps)
```

**★ 我上一轮说 Nexus "无运行证据、已停" —— 错。它跑到 07-21，且 CNS/心跳/T4 编译都在跑。**

---

## 四、Nexus 记忆系统的真实数据（★ 与母巢形成强对比）

### 4.1 生产库实测

```text
src/prometheus_nexus.db (07-21 00:09 ~ 07:27)
  nodes    79   edges 603
  feedback_log 79 / provenance_log 79 / evolution_log 8 / maintenance_log 8

★ access_count = 0:  3 / 79  =  3.8%      ← ★★★
  母巢: 98.8% 未访问
  Ultra runner.db: 100% 未访问

★ 节点内容是真知识 (不是测试数据):
  PAPER      acc=8 u=0.94  "Knowing the Self, Understanding the World: A Dual-Cognition..."
  PAPER      acc=9 u=1.00  "FVAttn: Adaptive Sparse Attention with Runtime Load Balancing..."
  PAPER      acc=9 u=1.00  "Sharp decay estimates for $(2+1)$-dimensional oscillatory..."
  CONCEPT    acc=8 u=0.81  "Machine learning: (ML) is a field of study in artificial..."
  CONCEPT    acc=8 u=1.00  "Attention (machine learning): ...determines the importance..."

类型分布: PAPER 38 / CONCEPT 28 / PROJECT 10 / PROCEDURE 3
★ 有 PROCEDURE 3 条 (母巢 21 万条里只有 9 条)
```

### 4.2 ★ 这是唯一"记忆真被使用"的项目

```text
              access_count=0 比例
母巢              98.8%       (21万条只有2472条被用过)
Ultra runner      100.0%
Ultra main        88.4%
★ Nexus            3.8%       ← 96.2% 的节点被访问过
```

**访问是怎么发生的**（代码级）：`lifecycle/evaf_consolidation.py`

```python
"""EVAF — Surprise-valence gated parametric consolidation.
Based on: "Memory Depth, Not Memory Access" (arXiv:2606.26806, Han 2026)

Key insight: memory depth (durable tendencies) vs memory access (retrieval).
EVAF selects which memories to consolidate based on surprise and valence.
Only 2-3 parametric writes per 200 events needed."""

score = surprise * 0.6 + abs(valence) * 0.4
should_consolidate = (surprise >= threshold and abs(valence) >= threshold ...)
if should_consolidate:
    record.access_count += 1      ← ★ 这里
    record.last_access = time.time()
    depth_after = self._parametric_update(record, surprise, valence)
```

### 4.3 但 evolution_log 仍是硬编码（与 Ultra 同病）

```text
evolution_log (8 行) 全部是:
  (id, 'maintain', 0.5, 0.6, 0.09999999999999998, 'maintain', ts)
★ before=0.5, after=0.6, delta=0.1 —— 8 行完全相同, 常量硬编码
★ evolve = 0 条记录

maintenance_log (8 行) 全部是:
  (id, 'migration', 10, 5.0, ts)   ← 常量 nodes_affected=10, duration=5.0
```

### 4.4 机制账本：246 个机制全部零调用

```text
archive/nexus.json:
  机制总数: 246
  ★ invoke_count > 0:  0 / 246     ← 全部为零
  enabled: 244
  dynamic_names: []                ← ★ 动态层空 (T4 编译全失败)
  route_override: {}               ← 无接管
  selection_gate: {'margin':0.05, 'min_samples':5, 'prune_below':-0.1, 'samples':{}}  ← samples 空
```

**★ 根因链条清楚了**：

```text
T4 论文编译 → 沙箱编译返回 None → 未挂载 → dynamic_names=[] 
  → route_override={} → dispatch 从未被调用 → invoke_count 全 0

★ Nexus 设计了一套完整的"机制经验记忆 + 效果路由 + 突触修剪",
  但动态层是空的 ⇒ 这套机制没有对象可管。
```

### 4.5 host_agent：宿主经验回流（解 DWC §9.1）

```python
"""HostAgentAdapter — 宿主 agent 抽象层 (P1a, 解 B5/B6/B7).

设计动机(实测证据):
- 原 LLMBridge 把宿主焊成 Hermes (env 名 HERMES_LLM_ENDPOINT)
- T4 激活机制零回流宿主 (grep emit_capability|to_host 全空)
- learn() 燃料源仅 ScanSource(web/arxiv/github), 无宿主运行时经验源

本抽象让 Ultra 成为"任意 agent 的外挂记忆 + 自进化生命体":
- llm_complete():      宿主的推理入口
- get_runtime_context(): 宿主的上下文窗口/工具清单/当前任务
- emit_capability():    把 Ultra 进化出的机制导出成宿主可用的能力
- ingest_experience():   宿主运行时经验(行为日志/失败/反馈)回流进 Ultra 进化燃料
"""
```

实测回流数据 `archive/host_experience.json` (7,548 B)：

```text
{"type": "feedback",    "content": "用户纠正了记忆路由", "utility": 0.7, "host_id": "claude_code_main", "timestamp": ...}
{"type": "task_result", "content": "完成数据分析任务",     "utility": 0.9, "host_id": "autogpt_agent_01", "timestamp": ...}
（重复 13+ 次，同一内容同一 host_id）
★ 机制存在且真跑过, 但内容是测试数据
```

---

## 五、更正后的三边总表

| 维度 | 母巢 | Ultra | **Nexus** | DWC 采纳 |
|---|---|---|---|---|
| memory 模块 | 59 | 26 | 26 (+17 独有) | — |
| 有生产引用 | 30 (50.8%) | 26 (100%) | 26 (100%) | ★ 采纳判据 |
| 七管调度 | 全跑 run_all | 条件触发链 | **条件触发链 + 统一中枢** | ★ 采纳 |
| 熔断 | SGH 计划/恢复 | max_depth=6 | max_depth=6 | ★ 采纳 |
| 自发任务源 | 无 | 心跳 3600s | **心跳 + host_agent 回流** | ★ 采纳 |
| 统一中枢 | facade (薄路由) | ✗ | **★ cns/nexus.py (仲裁者)** | ★★ 采纳 |
| 两层记忆 | ✗ | ✗ | **★ 知识记忆 + 机制经验记忆** | ★★ 采纳 |
| 机制效果遥测 | ✗ | ✗ | **★ dispatch 自带 effect_tracker** | ★★ 采纳 |
| 突触修剪 | ✗ | ✗ | **★ prune_harmful 基本盘永驻** | ★★ 采纳 |
| 记忆被使用 | 1.2% | 0-11.6% | **★ 96.2%** | ★★ 采纳 |
| 真实运行日志 | 44 天留痕 | 无 | **★ api_server.log** | — |
| evolve 留痕 | op 单值 | ✗ 0 条 | ✗ 0 条 (同病) | ★ 必须修 |
| 动态层 | — | — | **✗ 空 (T4 编译全 None)** | ★ 必须修 |
| 机制被调用 | — | — | **✗ 246/246 零调用** | ★ 必须修 |

---

## 六、结论

```text
★ 用户判断正确: Nexus 确实比母巢/Ultra 运作得更好 —— 但"更好"在特定维度:

Nexus 真正领先的四处:
  ① 记忆被使用率 96.2% (vs 母巢 1.2%)     ← ★ 最硬的一条
  ② 统一中枢 cns/nexus.py (仲裁者模式)
  ③ 两层共享记忆 (知识 + 机制经验)
  ④ dispatch 自带效果遥测 + 突触修剪

Nexus 同样没解决的四处:
  ✗ evolve 不留痕 (evolution_log 8 行全常量)
  ✗ 动态层空 (T4 编译 5 次全返回 None)
  ✗ 246 个机制 invoke_count 全 0
  ✗ recall 不落 access_count (靠 EVAF 巩固间接递增)

★ 最关键的一条: Nexus 的记忆被使用率高, 不是靠 recall 写回,
  而是靠 EVAF 巩固 (arXiv 2606.26806 "Memory Depth, Not Memory Access")
  ⇒ ★ 这直接反驳了我给 DWC 写的原则 7"必须靠 access_count 证明被使用"
  ⇒ 正确判据应是: 记忆是否驱动了行为改变 (depth), 不是被读了几次 (access)
```

---

## 七、对 DWC 的修正（基于 Nexus 实测）

```text
修正 1 · 原则 7 改口径
  旧: "一条记忆若无 access 记录, 不得被当作有价值"
  新: "一条记忆若无 depth 变化 (未驱动任何行为改变), 不得被当作有价值"
  ★ 依据: 2606.26806 明确区分 memory depth vs memory access
     Nexus 用 EVAF 走 depth 路线, 96.2% 被使用

修正 2 · 新增统一中枢器官 (Nexus 的 cns/nexus.py)
  DWC 六器官 → 七器官: 增加 `nexus` (仲裁者)
  职责: 查状态/效果/路由 → 转调执行后端 → 记账+遥测
  不变量: 仲裁者不执行 (不双重执行)
  ★ 依据: Nexus 源码"关键不变量(防回归)"

修正 3 · 采纳"两层记忆"命名
  ① 知识记忆 (七管共享)      ← 对应 DWC 的 EXPERIENCE
  ② 机制经验记忆 (effect 账本) ← 对应 DWC 的"机制级经验"
  ★ 依据: Nexus cns/nexus.py 原文

修正 4 · 淘汰用 Nexus 的 prune_harmful 形态
  基本盘永驻 + 动态层按效果修剪 (inv>=3 and eff<=-0.3)
  ★ 比我写的三层判据更简洁, 且已有实现
```
