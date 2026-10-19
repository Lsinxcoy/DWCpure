# 18 条长期红灯清零（2026-10-19）

> 一句话：**18 条失败全部归因并修复 —— 1 条真产品 bug（gate.py 崩溃）、1 条测试污染生产、16 条陈旧断言/夹具。**

---

## 总表

| 文件 | 条数 | 根因 | 类型 |
|------|-----|------|------|
| `test_gate_n_a.py` | 4 | **G8 契约门 `open()` 无存在性检查** ⇒ src 为空时 gate.py 整个崩溃、输出为空 | **产品 bug** |
| `test_r208_agent.py` | 1 | 测试假设"没有 agent 在跑"，但生产常驻 agent 活着 ⇒ `_alive()` 正确返回 True | 测试污染生产 |
| `test_b1_deep.py` | 2 | 夹具 `propose_from_cluster` 缺 `operator` 参数（R338 加的） | 陈旧夹具 |
| `test_b4_pool.py` | 1 | 同上 | 陈旧夹具 |
| `test_d2_envelope.py` | 1 | 同上 | 陈旧夹具 |
| `test_r309_resume.py` | 3 | 同上 | 陈旧夹具 |
| `test_r310_budget.py` | 3 | 同上（两处夹具） | 陈旧夹具 |
| `test_r305_wire.py` | 1 | 夹具簇签名缺 `c/q/fn`（R338 的 `key_for` 需要） | 陈旧夹具 |
| `test_c3_provenance.py` | 1 | 断言精确 dict，产品已加 `temporal_scope`（R340） | 陈旧断言 |
| `test_r290_p1_trial_score.py` | 1 | 断言精确 dict，产品已加 `activated/mechanism_ran/partial`（R346/R343） | 陈旧断言 |

---

## 一、真产品 bug：G8 契约门崩溃（4 条）

### 症状

`test_gate_n_a` 的四个用例输出全是空串：

```
assert out.count("[○ N/A ]") == 5   → 0 == 5
json.loads(out)                     → JSONDecodeError: Expecting value: line 1 column 1
```

### 根因（探针实证）

```
Traceback (most recent call last):
  File "scripts/gate.py", line 800, in gate8_contract
    rt_src = open(rt_path, encoding="utf-8").read()
FileNotFoundError: 'E:\\Divine Wisdom Core\\src\\dwc\\harness\\run_term.py'
```

测试把 `src/dwc` 暂存走（造"空 src"场景）⇒ G8 直接 `open()` 一个不存在的文件 ⇒
**整个 gate.py 崩掉** ⇒ stdout 为空 ⇒ 四道门的 N/A 断言全红。

**这是「什么都通过」与「门崩了」无法区分的同族病（R10）。**

### 修法

```python
rt_src = _read(rt_path) if os.path.isfile(rt_path) else ""
if not os.path.isfile(rt_path):
    violations.append({"file": "src/dwc/harness/run_term.py",
                       "rule": "K31 载体缺失", ...})
elif "synthetic: bool = False" not in rt_src:
    ...
```

修复后：5 道门如实报 `[○ N/A ]`，G8 报 FAIL（载体缺失），gate.py 正常退出。

---

## 二、测试污染生产：watchdog 判活（1 条）

### 症状

```python
assert W._alive() is False     # 实际 True
```

### 根因

`_alive()` 先 `psutil.process_iter` 扫 `dwc_agent.py` 真进程。**生产常驻 agent 确实在跑**（pid 1356 / 13708）⇒ 测试断言的是"环境里没有 agent"，而不是被测判据。

### 修法

```python
monkeypatch.setattr(psutil, "process_iter", lambda *a, **k: iter([]))
```

并且 **pid 文件改为"读出 → 删除 → finally 写回"**（原实现删了不恢复，
会把生产 pid 留在缺失状态，可能诱发守夜人误判拉活第二实例）。

---

## 三、陈旧夹具：`propose_from_cluster` 缺 `operator`（10 条）

R338 给 `Mutator.propose_from_cluster` 加了 `operator` 参数（OpenRSI 原子算子），
但六个测试文件的 `_Mu` 替身没跟上：

```python
# 产品签名
def propose_from_cluster(self, sigs, context="", max_attempts=3,
                         want_code=False, learned_hint="",
                         operator="improve")

# 旧夹具（缺 operator）⇒ TypeError ⇒ run_round 的 except 捕获 ⇒ _fatal ⇒ 不试跑
def propose_from_cluster(self, sigs, context, want_code=False, learned_hint="")
```

症状是 `calls == []`（trial_fn 从未被调）—— 看起来像产品不工作，实际是夹具签名过时。

**修法**：六个文件统一加 `operator="improve"`。

`test_r305_wire` 另有一处：stub 簇签名 `{"task": "code_fix_009"}` 缺 `c/q/fn`，
R338 的 `Mutator.key_for` 需要三元组 ⇒ 补齐。

---

## 四、陈旧断言：精确 dict 相等（2 条）

### `test_c3_provenance`

产品 R340 起 provenance 带 `temporal_scope` 四字段（RSI 审计纪律：
无回滚触发条件的改进不算可持久）。旧断言是精确 dict 相等 ⇒ 加键即红。

**改为逐字段 + 更强断言**：

```python
ts = prov["temporal_scope"]
assert set(ts) == {"effective_from", "scope", "rollback_trigger", "expires"}
assert ts["rollback_trigger"], "回滚触发条件不许为空"
```

### `test_r290_p1_trial_score`

产品 R346/R343 起 `_real_trial` 返回 `activated/mechanism_ran/partial`。
旧断言精确 dict 相等 ⇒ 加键即红。

**改为逐键锁语义**（比精确相等更强：锁的是"LLM 挂 ⇒ 不编分数"，不是键的个数）。

---

## 五、验证

| 项 | 结果 |
|----|------|
| 10 个受影响文件定向 | **58 passed** |
| gate | **8/8 全通过** |
| 全量 pytest | 见 `var/pytest_green.log` |

---

## 六、诚实边界

1. **`_alive()` 的生产行为没改** —— 它本来就该检出真进程。改的是测试隔离。
2. **G8 的 `n_a` 口径没变** —— `NEED_FILES={1,2,3,4,7}` 仍不含 G8；
   空 src 时 G8 报 FAIL（载体缺失），这是对的：G8 检的是脚本/配置/契约，
   不只是 `src/dwc`。
3. **`operator` 参数在夹具里只是占位** —— 测试不验证算子选择逻辑
   （那是 `test_r338` 家族的职责），这里只保证签名兼容。
4. **没有新增测试** —— 本轮修的是既有红灯；新增断言已并入对应旧测试。
