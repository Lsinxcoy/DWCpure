# Phase B3 · 提案落盘 + evo_round 消费（2026-10-19）

> 一句话：**B2 产出的提案不再丢** —— 写进 append-only 账本，`dwc_evo_round` 从账本读未映射簇起草。

---

## 一、B2 留下的洞

B2 让 `DWC.run_term` 每轮调 `evolver.diagnose`，但产物只在内存里返回一次：

```python
self._seen.add(p.key())     # Evolver.diagnose 内部
```

⇒ 同一个 proposal 第二次不会再返回。**没人消费 = 第一条之后就永久丢失。**

---

## 二、为什么不直接用 DB 的 `failure_sig` 表

| | `failure_sig` 表 | live 签名（B2 路径） |
|---|---|---|
| `c` / `q` / `m` | ✅ | ✅ |
| `fn` | ❌ **无此列** | ✅（judge 的 sig 自带） |
| `task` | ⚠️ 只在 `memory_node.payload` 里，需 join | ✅（`task_id`） |

`dwc_evo_round.py` 因此只能用硬编码参数（R279 自陈）：

```python
ap.add_argument("--fn", default="average")
ap.add_argument("--task", default="code_fix_007")
```

⇒ **落盘比读库更准**：live 路径天然带 `fn` 与 `task`。

---

## 三、账本形态（`var/evo_proposals.jsonl`，append-only）

```json
{"kind":"proposal","ts":...,"term_id":"T_4cb2d600","chain_id":"CH_4413ee03c6",
 "key":"E_VALUE:wrong_magnitude:average",
 "sig":{"c":"E_VALUE","q":"wrong_magnitude","fn":"average","m":"...","task":"code_fix_002"},
 "proposal":{"proposal_id":"...","component":"...","target":"...",
             "patch":"...","rationale":"...","operator":"debug","target_layer":"..."}}

{"kind":"unmapped","ts":...,"term_id":"...","chain_id":"...",
 "key":"E_NO_RESULT:abstained_or_missing:sum_first_n","sig":{...}}

{"kind":"consumed","ts":...,"keys":["E_VALUE:wrong_magnitude:average"]}
```

消费语义：`consumed` 里出现过的 key ⇒ `pending_unmapped` 不再返回。

**只在 `landed is True` 时标记消费** —— 起草了但没过门的下轮重试，不静默丢弃。

---

## 四、接线

### 写入端（`DWC._feed_evolver`）

```python
diag = self.evolver.diagnose(sigs)
recs = [proposal_record(meta, p.failure_signature, p) for p in diag["proposals"]]
recs += [unmapped_record(meta, s) for s in diag["unmapped"]]
n_persisted = evo_proposals.append_records(evo_proposals.DEFAULT_PATH, recs)
```

`evo_feed` 新增两个字段：`n_persisted` / `path`；写盘失败记 `persist_error`（不掀 term，但留痕）。

### 消费端（`scripts/dwc_evo_round.py`）

```bash
python scripts/dwc_evo_round.py --from-proposals var/evo_proposals.jsonl
```

- `--from-proposals` 给了 ⇒ `pending_unmapped` → `group_by_key` → 作为 `clusters` 注入 `run_round`
- `run_round(..., clusters=None)` 是新增参数：`None` = 老路读库（**默认零变**），给了 = 不读库

---

## 五、真跑证据

真 `DWC` + 真六层链 + 真失败执行体：

```
evo_feed: {enabled:true, n_sigs:9, n_dropped:0, n_proposals:1,
           n_unmapped:8, n_clusters:3, n_persisted:9, path:...}

落盘记录: 9 | proposal: 1 | unmapped: 8

首条: {"kind":"unmapped","term_id":"T_4cb2d600",
       "key":"E_NO_RESULT:abstained_or_missing:sum_first_n",
       "sig":{"c":"E_NO_RESULT","q":"abstained_or_missing",
              "fn":"sum_first_n","m":"llm_asserted:None","task":"code_fix_001"}}

evo_round 入口: 5 簇 / 8 签名
   key=E_NO_RESULT:abstained_or_missing:sum_first_n  sigs=3  task=code_fix_001  fn=sum_first_n
   key=E_VALUE:wrong_magnitude:average               sigs=2  task=code_fix_002  fn=average
   key=E_NO_RESULT:abstained_or_missing:fibonacci    sigs=1  task=code_fix_004  fn=fibonacci

消费 1 簇后 pending: 4 簇
```

**8 条未映射签名 → 5 个簇（频次 3/2/1…），每簇带 task 与 fn。**

CLI 空账验证（不触发 LLM）：

```
$ python scripts/dwc_evo_round.py --from-proposals <empty>
from-proposals: 0 簇 / 0 签名
无待起草簇 —— 不跑本轮
```

---

## 六、测试

`tests/test_r374_evo_proposals.py` —— **11 条**：

| # | 锁 |
|---|-----|
| 1 | append / read 往返 |
| 2 | 文件不存在 ⇒ 空列表 |
| 3 | 坏行跳过 + 计数（不 raise、不静默） |
| 4 | consumed key 被排除 |
| 5 | pending 不去重（保留频次），group_by_key 合并 |
| 6 | sig 缺 c/q/fn ⇒ 跳过 |
| 7 | `proposal` 记录不混进 pending |
| 8 | 簇形态与顺序 |
| 9 | proposal 记录带全审计字段 |
| 10 | **注入 clusters ⇒ 不读库**（monkeypatch `collect_unmapped` 抛错） |
| 11 | **clusters=None ⇒ 仍读库**（老路零变） |

`tests/test_r373_evolve_feed.py` 加 autouse 隔离 fixture：提案落盘指向 tmp
（否则测试会写进生产 `var/evo_proposals.jsonl`）。

---

## 七、诚实边界

1. **开关已打开**（`feed_from_terms: true`，2026-10-19 用户拍板）——
   生产 term 现在会产提案并落盘；起草（evo_round）仍不排 cron。
2. **只落盘，不自动起草** —— evo_round 仍是独立调用（手动或 cron），
   agent 循环内不会自己发起 trial。这是刻意的：起草要花 LLM 预算。
3. **消费标记只在 landed** —— 起草失败/未过门的簇会一直留在 pending，
   每轮重试。没有退避或次数上限，长期可能反复烧预算。
4. **账本无轮转** —— append-only 会一直长。当前量级（每 term ≤50 条）可控，
   但长跑数月后需要归档策略，本轮未做。
5. **未验证真实 LLM 起草** —— `--from-proposals` 的 LLM 起草段（`LLMMutator`）
   本轮只验证了「空账短路」路径，没有真跑一次起草。
