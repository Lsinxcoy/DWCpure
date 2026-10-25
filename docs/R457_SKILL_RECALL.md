# R457 · skill 记忆产出 + recall 进任务选择

> 记忆单薄的根因不是"写得少"，是**读端没有消费者**：
> `recall()` 生产零调用，选择器按 `pool[terms % len]` 轮转，
> 而 `memory_text()` 只读 `kind='skill'` —— 生产里 skill = **0 条**。

## 1. 病根（R457 前的实测）

| 事实 | 数字 |
|---|---|
| `memory_node` 总数 | 5,073 |
| 其中 skill | **0** |
| `failure_sig` 被取回 | 4 / 2,108 = **0.2%** |
| 从未被取回 | 83.7% |
| `var/dwc_lessons.jsonl` 里的 success_pattern | **905 条**（904 条带"成功做法（…）"） |

系统一直在学成功做法，**只是从未把它们变成可检索的记忆**。
于是 `memory_text()` 恒返回空 ⇒ 模型 prompt 里的"已知参考资料"永远是「（无）」。

## 2. 修法

### 2.1 `src/dwc/organs/skill_writer.py`（新，157 行）

把 lessons 里的成功做法写成 SKILL 节点：

| 字段 | 来源 |
|---|---|
| `scene` | lesson.task |
| `method` | lesson.detail（"成功做法（answer contains 'x.py'）：…"） |
| `boundary` | lesson.fail_mode（`success_pattern:*`） |
| `invalid_conditions` | 由 fail_mode 派生：任务不属于该类时不适用 |
| `recovery_strategies` | 系统真实行为：失效 ⇒ 本轮失败签名进 evolver 重新诊断 |
| `src_key` | sha1(task + method)，去重键 |

**fail-closed**：非 `success_pattern`、task/detail 过短（<4 / <12 字，实测台账里
混进过 `任务X / 假答案` 的测试残留）一律不写。

### 2.2 近重复合并让位于显式身份键

`MemoryKernel._near_duplicate` 用 difflib 比对整条 payload，`MERGE_TAU=0.90`。
实测同一模板下不同任务的 payload 相似度 **0.92** ⇒ 71 条做法会被合并成几条。
修法：payload 带 `src_key` 且两键不同 ⇒ 不参与模糊合并（显式身份优先）。

### 2.3 `src/dwc/organs/task_recall.py`（新，104 行）

记忆第一次成为**选择的输入**：

```
1. 跑过且有失败签名  ⇒ 最该再试（失败是唯一的学习信号）
2. 从没跑过          ⇒ 覆盖优先
3. 跑过且没失败      ⇒ 最久没碰的优先（LRU）
冷却中的题一律让位；全在冷却 ⇒ 返回空，调用方回退轮转。
```

接线：`select_task(..., stats=_MEM_STATS)`；`_MEM_STATS` 在启动与每个 term 后
由 `_refresh_mem_stats()` 重算（一次全扫，毫秒级）。

### 2.4 `memory_text()` 改成按任务召回（不是全量倾倒）

旧实现把库里**全部** SKILL 渲染进 prompt：71 条 = **29,952 字符**。

新实现：

- 用任务文本与 `scene+method` 的 2-gram 覆盖率 `cov` 排序
- 先剔除库内高频 gram（df > 30%，"的""函数"这类）
- 阈值 `cov ≥ 0.45` 且命中 ≥3 个信息 gram
- top-k=5，总量封顶 1,800 字符
- **没有相关做法就返回空**

阈值是实测标定的，不是拍脑袋：

| 情形 | cov |
|---|---|
| 同一任务原文 | **1.000** |
| 无关任务 | **0.081** |

## 3. 实测

### 提升（生产库副本预演，0.3s）

```
提升前 skill: 0
promote: {'n_seen': 1213, 'n_written': 71, 'n_dup': 833, 'n_skip': 309}
提升后 skill: 71
```

### 生产（21:56:33 重启）

```
{'event': 'skill_promoted', 'n_written': 71, 'n_dup': 833,
 'n_skip': 309, 'skill_total': 71}
{'event': 'agent_started', 'mode': 'llm'}
{'agent_term': 1, 'task': 'fresh_range_sum', 'mode': 'llm', 'pass_rate': 0.0}
```

记忆库结构变化：

| 维度 | 前 | 后 |
|---|---|---|
| `kind=skill` | 0 | **71** |
| tube `learn` | 0 | **71** |
| tube `reflect` | 2,108 | 2,109 |
| zone `experience` | 2,109 | **2,180** |

### recall 的诚实边界

对 **函数实现类**题目（`fresh_*` / `code_fix_*`）召回结果是 **0 命中** ——
因为已有的 71 条做法全部来自**收件箱任务**（"某文件在哪 / 某常量是几"），
与"实现一个函数"没有共同的 2-gram 面。

这不是失败，是**如实为空**：没有相关经验就不许往 prompt 里塞无关内容。
等函数类任务自己产出 success_pattern 之后，这条通道才会点亮。

## 4. 验收

- `tests/test_r457_skill_recall.py`：13 条
  - D6 五字段齐 / 失败类不写 / 过短不写
  - 写入幂等（重复跑不增长）
  - 记账四数对平（seen = written + dup + skip）
  - `memory_text` 按任务召回、无关任务返回空
  - 选择口径：失败优先 / 未跑其次 / LRU 最后 / 冷却让位
- 全量 **2914 passed / 389.75s / EXIT=0**
- `scripts/gate.py` 八门全绿
- 生产真身 14072，`mode=llm`，skill 71 条

## 5. 还没做的

1. **函数类任务的做法来源**：现在只有收件箱任务会产 success_pattern。
   term 循环失败后只写 failure_sig，不写"下次怎么修"。
2. **skill 不参与选择**（`n_skill` 已统计但排序未用）：等有了 term 级做法再启用。
3. `memory_text` 的召回是词面匹配，不是语义检索（无 embedding / 无 FTS）。
