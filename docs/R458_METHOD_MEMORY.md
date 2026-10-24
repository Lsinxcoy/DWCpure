# R458 · 函数类任务的做法来源：成功时把"怎么做的"写进记忆

> R457 之后 skill 从 0 涨到 71，但函数类题目召回仍是 **0 命中** ——
> 因为那 71 条全来自收件箱任务。term 循环里**成功什么都不写**，
> 记忆里永远只有负样本。

## 1. 病根

| 路径 | 写什么 |
|---|---|
| term 失败 | `failure_sig`（c/q/m —— 错在哪） |
| term 成功 | **什么都不写** |

于是 `memory_text()` 在函数题上无话可说。要让它有话说，必须先让
term **产出"怎么做"**。

## 2. 修法

### 2.1 让模型顺带说出做法（同一次调用，零额外成本）

`build_observed_prompt` 加一条输出要求：

```
并在同一对象里加一个键 "_method"，值为一句话（≤80 字）
说明你是怎么得到这些值的（用了什么公式/步骤）。
```

模型返回形如：

```json
{"fresh_range_sum": [[[2,6], 20], [[3,7], 25]],
 "_method": "对区间 [a,b] 内的整数求和：sum = (a+b)*(b-a+1)/2。"}
```

`parse_llm_observed` 会跳过非 `[args, val]` 的键（已验证），所以
`_method` 不干扰观测解析；新增 `parse_method()` 单独抽它。

### 2.2 数据流

```
LLM executor  →  detail = {observed, method}
_build_observations  →  out[tid]["★method"] = method
run_term（判分后）  →  成功且 method 非空 ⇒ skill_writer.from_term(...)
```

### 2.3 只在判分**通过**时落库

`method` 是模型**自述**，未经验证。只有它给出的答案被判分器判为正确，
这条"怎么做"才至少有一次实证背书。

payload 带 `m_source="llm_self_report"` —— 读者能一眼看出它不是人工核定的。
D6 五字段照旧齐备（scene/method/boundary/invalid_conditions/recovery_strategies）。

## 3. 实测

### 真模型三题（临时库）

```
跑前 skill: 0
fresh_fib          pass=1.0  skill_written=e7501a75…
   method: 斐波那契数列 F(1)=1,F(2)=1，递推 F(n)=F(n-1)+F(n-2)，得 F(11)=89, F(12)=144。
fresh_vowel_count  pass=1.0  skill_written=8af0cab8…
   method: 数每个字符串中元音字母 aeiou 的总数（小写、不重复计）
fresh_range_sum    pass=1.0  skill_written=e58818b1…
   method: 对区间 [a,b] 内的整数求和：sum = (a+b)*(b-a+1)/2。
跑后 skill: 3
召回 fresh_fib: 400 字符
```

**闭环成立**：写进去的做法，下一轮同题能召回来。

### 生产（22:22:42 首轮）

```
{'event': 'agent_started', 'mode': 'llm'}
{'agent_term': 1, 'task': 'fresh_range_sum', 'mode': 'llm',
 'pass_rate': 1.0, 'skill': True}
skill 总数: 71 → 72
其中 m_source=llm_self_report: 1
```

## 4. 诚实边界

1. **`method` 是自述，不是验证过的方法**：模型可能在答案正确的同时把
   推理过程说错（"蒙对"）。所以它只作为"参考资料"进入 prompt，
   不作为判据，也不当作已验证知识。
2. **只在通过时写**：失败时只留 failure_sig（错在哪），不写"怎么修" ——
   因为失败的解法没有实证背书。
3. **一题一条**：同一任务多次成功会产生多条不同 method（src_key 不同），
   由 `_near_duplicate` 的显式身份键规则保留。
4. 召回仍是词面匹配（2-gram），不是语义检索。

## 5. 验收

- `tests/test_r458_method_memory.py`：8 条
  - prompt 要求 `_method` / 解析 / 缺失返回空
  - executor detail 带 method
  - 观测带 `★method`
  - 只有通过才写（失败/空做法返回 None）
  - payload 五字段齐 + `m_source` 可辨
  - 写入后能被自己的 prompt 召回
- 全量 **2922 passed / 380.74s / EXIT=0**
- `scripts/gate.py` 八门全绿
- 生产真身 45192，首轮 `skill=True`，skill 71 → 72
