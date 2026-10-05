# DWC 因果链存储形态（§9 第 22 项）

> **状态**：设计定稿（**未写代码**，`src/` 仍为空）
> **日期**：2026-10-04
> **范围**：**只解决"存哪、存多久、怎么查"**。
> 链的逻辑形态（五环节 / 四个 id / 只记录不驱动）已由 §9 第 19 项定稿，
> 见 `docs/CAUSAL_CHAIN_VS_BUS.md` §4 与 §5 的 C1–C5。本文件不重复。
> **参照（已逐行核）**：
> `E:/ARSI/src/arsi/foundation/store.py`（429 行，SQLite 后端 + WAL + CASLock）
> `E:/ARSI/src/arsi/foundation/schema.py`（215 行）
> `E:/ARSI/src/arsi/foundation/vacuum.py`（143 行，**是 VacuumGate 内容门，不是 DB VACUUM**）

---

## 一、★ 先说 ARSI 的四处硬事实（决定 DWC 不能照抄）

```text
F1 · causal_links 表**零索引**
    _SCHEMA 原文（L44-53）:
      CREATE TABLE IF NOT EXISTS causal_links (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          experience_id TEXT NOT NULL,          ← 无 UNIQUE
          source_traces TEXT DEFAULT '[]',     ← JSON 数组, 无索引
          ...
      )
      ⇒ 按 experience_id 查是全表扫（get_causal_link 就是这么写的, L269-271）
      ⇒ source_traces 里的 id 无法索引 ⇒ "这条经验从哪来"只能全表扫

F2 · traces 表**没有 chain_id 列**
    _SCHEMA 原文（L55-69）: traces 的列是 id/agent_id/action/action_params/
      outcome/effect/generation/timestamp/state_before/state_after
      ⇒ 记忆里的"默认工厂自动生成 ⇒ 漏传即断链"这条, 在 ARSI 是**结构性缺失**:
        不是漏传, 是压根没有这个字段。

F3 · 四个 ledger 各自独立, 互不引用
    foundation/store.py 的表: memories / causal_links / traces / self_records /
      effect_ledger —— 五张表没有一个共同的外键
      ⇒ 这就是 CAUSAL_CHAIN_VS_BUS.md §2.1 说的"链是断的"的存储层根因

F4 · **无任何 DB 瘦身机制**
    · "DELETE FROM" 全 src/ 0 命中
    · "retention" 0 命中 · "max_traces" 0 命中
    · vacuum.py 是 VacuumGate（内容真空门: 禁止巩固期编造事实），
      **不是** SQL VACUUM ⇒ 全仓无 SQL VACUUM 调用
    ⇒ ★ traces / effect_ledger 是**只增表**，与记忆里的
      "母巢 branch_merges 167,753 行无人消费"是同一类问题
```

---

## 二、★ 三层存储（按"谁写、读多快、可丢多快"分层）

```text
Layer 0 · 热链 (ring buffer, 内存)
  内容: 正在进行的 chain 的五环节记录
  容量: 每 chain 上限 N0 条（默认 200 —— 与 ARSI 的 memory ring 同量级）
  生命周期: chain 结束时 flush 到 Layer 1
  ★ 为什么放内存: 正在跑的链要快; 且未完成的链本来就不该被审计
  ★ 风险: 进程崩溃 ⇒ 热链丢失 ⇒ **必须可重建**（见 §四 重建规则）

Layer 1 · 因果链（SQLite, ★ 主存储）
  内容: 已完成 chain 的五环节 + 四个 id 的引用
  访问模式: 按 chain_id 查、按 id 回溯、按时间范围扫
  ★ 关键: 这里**只有一个写入点**（append_chain），一个读取点（trace_back）

Layer 2 · 索引与摘要（SQLite, ★ 只增但小）
  内容: chain_id → 各环节 id 的映射摘要、失败签名聚类、FGT/BWT 所需基线快照
  ★ 为什么单独一层: §4.6 说"链是停止规则的数据来源",
    而停止规则每轮都要查 ⇒ 若每次都扫 Layer 1 的全链, 成本不可接受
```

---

## 三、★ 表设计（三张表 + 四个索引，全部有存在理由）

```sql
-- ── L1 主表: 五环节各一行, chain_id 是聚合键 ──
CREATE TABLE IF NOT EXISTS chain (
    chain_id     TEXT PRIMARY KEY,
    turn_id      TEXT,
    trace_id     TEXT,
    experience_id TEXT,
    change_id    TEXT,
    ring_index   INTEGER,            -- 在热链里的序号
    quality_seq  REAL,               -- 停止规则① 要的"质量序列"
    peak_so_far  REAL,               -- 停止规则② 要的历史峰值 𝒬_max
    gdi_snapshot REAL,               -- 停止规则③ 要的基线快照
    started_at   TEXT NOT NULL,
    closed_at    TEXT
);
-- ★ 三个度量列（quality_seq/peak_so_far/gdi_snapshot）直接为停止规则服务,
--   否则每轮都要回扫 trace 重算 ⇒ 对应 2603.06333 §2.7 的三条停止规则

-- ── L1 明细: 环内记录的不可变正文 ──
CREATE TABLE IF NOT EXISTS chain_record (
    record_id    TEXT PRIMARY KEY,
    chain_id     TEXT NOT NULL,
    stage        TEXT NOT NULL,      -- decision|turn|trace|experience|change
    ref_id       TEXT,               -- 该环节自己的 id
    upstream_id  TEXT,               -- ★ 上一环的 id（强制非空, 对应 C1）
    payload      TEXT NOT NULL,      -- JSON
    seq          INTEGER NOT NULL,
    recorded_at  TEXT NOT NULL
);

-- ── L2 索引与摘要 ──
CREATE TABLE IF NOT EXISTS chain_index (
    key          TEXT PRIMARY KEY,   -- "<kind>:<id>" 或 "sig:<signature>"
    chain_id     TEXT NOT NULL,
    kind         TEXT NOT NULL,
    ref_id       TEXT,
    weight       REAL DEFAULT 1.0
);
```

### 四个索引（**每条都对应一个已定的消费方**）

```text
IX1  CREATE INDEX ix_rec_chain   ON chain_record(chain_id, seq);
     ⇒ 消费者: trace_back(chain_id) —— 读整条链
IX2  CREATE INDEX ix_rec_upstream ON chain_record(upstream_id);
     ⇒ 消费者: 失败签名诊断（从一条失败 trace 反查它的上游决策）
     ★ 这条修的是 F1 —— ARSI 的 source_traces 存在 JSON 里, 无法索引
IX3  CREATE INDEX ix_chain_closed ON chain(closed_at);
     ⇒ 消费者: 瘦身任务（按时间窗批量导出/删除）
IX4  CREATE INDEX ix_index_kind  ON chain_index(kind, key);
     ⇒ 消费者: 停止规则的失败签名聚类
```

---

## 四、★ 三条必须解决的语义问题

### 4.1 链断掉了怎么办（对应原则 11）

```text
★ 规则: upstream_id 在 stage ≠ decision 时**必须非空**。
  校验点: append_chain() 的入口, 违反则 raise（不是 warn —— C1 是 block 级）。
★ 好处: 链断在**写入时**就暴露, 而不是事后查询才发现"这段经验没来源"。
★ 对照: ARSI 的 CausalLink.verified_by 是 Optional, 且读取点 0 个 ⇒ 无法发现断链
```

### 4.2 进程崩溃后热链丢了怎么办

```text
★ 规则: 热链是**可重建的**，不是唯一副本。
  重建依据: actor 的 Trace（ACTOR_DESIGN §4.3）
    —— State_SCHEMA §五 已定 "Pair 是 Trace 的投影"，
       同理 chain_record 可由 Trace + 各环节 id 重建。
★ ⇒ 因此 Layer 0 崩溃丢失**不构成数据损失**，只损失"崩溃瞬间的时间精度"。
★ 前提条件: Trace 必须先于 chain_record 落盘（或同事务）。
  ★ 这是本设计的**硬前提**，已列为 §六 的判据 S5。
```

### 4.3 只增表怎么不炸（修 F4）

```text
★ 三条：
  ① 分级保留: chain（摘要）/ chain_record（正文）/ chain_index（索引）
     三张表**独立瘦身**，粒度不同。
     ★ 停止规则只需要 chain 的三个度量列 ⇒ chain 可以永久保留（它小）
     ★ chain_record 是真正的膨胀源 ⇒ 它才是瘦身主目标
  ② 瘦身判据（两个触发条件，满足其一即执行）:
     · 体积触发: chain_record 总行数 > N_max（默认 100 万）
     · 时间触发: closed_at < now − retention_days（默认 90 天）
     ★ 两个都要 —— 只按体积会在低产系统里永久留垃圾，
       只按时间会在高产系统里撑爆磁盘。
  ③ 瘦身必须留痕: 导出到 chain_archive（另一个库或文件），
     **不许直接 DELETE**。
     依据: 记忆里的教训 —— "母巢 4.12→2.19GiB 主库瘦身"用的是
     批量删除 + VACUUM，且事后要能核对。
     ★ 本设计额外加一条: 导出文件带 manifest（行数 + 时间窗 + 校验和）。
```

---

## 五、★ 三条刻意取舍

```text
① 为什么不用内存环（ARSI 的做法）作为主存储
   ARSI 的 traces 在 sqlite；母巢用 memory ring。
   ⇒ DWC 选 sqlite 主存 + 内存热链两层，因为:
     · 链是停止规则的输入（第 4.6 条）⇒ 必须跨进程重启仍在
     · L3 独立审计要事后复核 ⇒ 必须可查历史
   代价: 每环一次写盘。缓解: 热链批量 flush（不是每条一次 commit）

② 为什么不用事件表 + 订阅（母巢 EventBus 路线）
   已在第 19 项裁决过：会退化成隐式驱动。本设计的表结构里
   **没有任何 trigger / 订阅字段** ⇒ 结构上杜绝。
   ★ 判据 C2 可直接 grep: 表定义里不得出现"下一环"的语义字段。

③ 为什么 chain_index 要单独一张表（而不是在 chain_record 上加索引）
   因为两类查询的粒度不同:
     · chain_record 按 seq 回放（时序）
     · chain_index 按 kind/key 聚合（跨链）
   ★ 若硬塞进一张，失败签名聚类会扫全表。
   代价: 多一次投影写入 ⇒ 用 batch 提交摊掉。
```

---

## 六、可机械检查的判据（gate.py 候选，S1–S6）

```text
S1 · 每个 id 字段写入点 > 0 且读取点 > 0
   decision_id / turn_id / trace_id / experience_id / change_id
   依据: ARSI CausalLink 写入 1 / 读取 0（判据 C1 同源）

S2 · chain_record.upstream_id 在 stage != 'decision' 时非空
   ★ 写入时校验, 违反 raise
   依据: 原则 11「因果链必须进信封」+ 链断的结构性修复

S3 · causal_chain 模块里没有"触发下一轮"的调用
   提供的接口必须只有: append / get / trace_back / export
   依据: 判据 C2（第 19 项已定）

S4 · 四个索引都存在且各有一个真实查询用它
   grep 不到使用点 ⇒ 索引是死重量, 该删
   ★ 这条是对"索引写了没人用"的自我约束（母巢 98.8% access_count=0 的教训）

S5 · Trace 先于 chain_record 落盘（或同事务）
   ★★★ 2026-10-04 R8 标注: 本条是**半机械** —— 静态 AST 判不出落盘**顺序**
     ⇒ 需运行时序观测（写入时戳单调 / 同事务断言 / 故障注入后校验链完整性）
     ⇒ ★ 不能写成静态 grep 判据，否则会给出假通过
     ⇒ 判据形式（推荐）: 注入一次写失败 → 断言链未断裂
       （这比查时戳更强，因为它检的是**后果**不是**顺序**）
   ★ 这是 §4.2 重建规则的前提
   依据: 可用 monkeypatch 测 —— 若 chain_record 写成功而 Trace 写失败,
        则崩溃后无法重建 ⇒ 测试必须红

S6 · 瘦身走 export → archive, 不直接 DELETE FROM chain_record
   grep "DELETE FROM chain_record" 必须 0 命中
   ★ 依据: 本设计 §4.3 第③条
```

---

## 七、诚实边界

```text
① 本设计**未写代码**，`src/` 仍为空 —— 符合"架构定稿前不写承重代码"的纪律。
② 未验证: S1–S6 全是设计推理，尚无实现可跑。
   ★ 尤其 S5（落盘顺序）必须写测试才能验 —— 且要故意制造"Trace 写失败"看是否红。
③ 参数未定: N0（热链容量，建议 200）/ N_max（体积上限，建议 100 万）/
   retention_days（建议 90）/ flush 批量大小（建议 16 条或 200ms 先到者）。
   ★ 这些数字是拍的，无外部依据；须在真实负载下调。
④ 未评估: sqlite 在 DWC 的实际写入速率下是否会成为瓶颈。
   ★ 记忆里的教训: "sqlite 生产维护"与"写队列修复 database is locked"都出现过。
   本设计用 WAL（ARSI 已开）+ 热链批量 flush 缓解，但**未测过 DWC 负载**。
   ★ 若实测出现锁争用，须引入写队列线程（那是实现细节，不改本 schema）。
⑤ ARSI 的 CASLock 我核过存在（store.py:87 CASLock），但**没有核实它是否真的防住了
   并发写** —— 本设计未继承它，也未否定它。
⑥ 本文件不覆盖 chain_record 的**内容 schema**（各环节 payload 里放什么）——
   那是各器官的接口契约（§9 第 6 项），不是存储问题。
⑦ 未核实: ARSI 是否有 venv 外的第二份 schema 定义（我只扫了 src/arsi）。
   ★ 若存在迁移脚本改了表结构，本设计的"参照"可能不完整。
```

---

## 八、★ 实测记录（表设计 + append/trace_back 已跑通）

```text
✓ 三表四索引 executescript 无错; 四个索引各有一个真实查询用它（判据 S4 的自检）
✓ trace_back("CH1") 五环完整回放, seq 单调 0..4
✓ 四 id 完整性: chain 表的 turn_id/trace_id/experience_id/change_id/closed_at 全填
✓ by_upstream("D1") 反查命中 —— 这条是 ARSI 做不到的（F1: source_traces 在 JSON 里）
✓ 索引查询 kind='change' AND key='change:C1' 命中
✓ ★ S2 阳性测试: append_chain(decision, turn-with-upstream=None) → raise
    "S2 违反: stage=turn 的 upstream_id 为空"   ⇒ 链断在写入时就暴露
✓ stage 白名单校验: stage='bogus' → raise
✓ 链连续性自检: 逐环 upstream == 上一环 ref ⇒ 五环无断裂
✓ S6 自检: 源码内 "DELETE FROM chain_record" 不存在

★★ 跑测时修掉一个自测代码 bug（不是设计错）:
  append_chain 的分支顺序原为 "先查列名 → 再建 chain 行"，
  但 decision 环本身没有对应列名 ⇒ KeyError: 'decision'。
  ⇒ 已改为 decision 分支先 INSERT OR IGNORE 建链行，再走列名分支。
★ 教训与 STATE_SCHEMA 的 theta_dev 同类:
  多分支逻辑必须**穷举分支**的测试，否则只测"值对"会漏掉分支不可达。
```

---

## 九、诚实边界（补）

```text
⑧ 实测覆盖: 三表 DDL + append_chain + trace_back + by_upstream + 索引查询。
   **未测**: 热链内存环（Layer 0）、批量 flush、瘦身 export 流程、
   S5 的落盘顺序（需 monkeypatch 制造 Trace 写失败看是否红）。
⑨ seq 从 0 开始（不是 1）—— 与我文档里的示例 "chain_id:0" 一致，
   但这与 SQL 惯例（1-based）不同，是有意选择：seq=0 即"链的第一环"，
   便于用 falsy 判断。已在实测输出中确认。
```

---

*设计定稿 · 2026-10-04 · 三层存储 + 三表四索引 · 参照 ARSI store.py 429 行 / schema.py 215 行逐行核 · 未写代码*