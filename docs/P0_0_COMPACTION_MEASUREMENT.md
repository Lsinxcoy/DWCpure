# P0-0 · compaction 成本实测（R439 附带）

> 日期：2026-10-24
> 目的：在动 P0-b 之前，先回答"**DWC 现在的上下文压缩到底是在省钱还是在烧钱**"。
> 结论：**论文的 1.85× 不适用于 DWC —— 因为 DWC 根本没有前缀缓存可失去。**

---

## 1. 方法

用真实任务跑一轮，读 `var/llm_usage.jsonl`（P0-a 刚落地的记账）。

```python
# var 与 usage 都指到 scratch，不污染生产
os.environ["DWC_VAR_DIR"] = "<scratch>/p00/var"
os.environ["DWC_USAGE_PATH"] = "<scratch>/p00/usage.jsonl"

execute_user_task("读取 config/llm.json 的 model 字段，只回答模型名",
                  llm=LLMClient(), max_rounds=4)
```

---

## 2. 结果

任务结果：`status=done` / `rounds=2` / 答案正确。

| 调用 | prompt_tokens | completion_tokens | **cached_tokens** |
|---|---|---|---|
| 1 | 2,140 | 41 | **0** |
| 2 | 193 | 64 | **0** |
| 3 | 2,554 | 36 | **0** |
| **合计** | **4,887** | **141** | **0** |

`cost_usd` 全为 `None` —— `config/llm.json` 还没有 `pricing` 段（不知道 mcgrox 的价目，
**不编造**）。

---

## 3. 结论

### 3.1 论文的 1.85× 不适用

Cache Engineering 的 1.85× 来自**serving 层**：改前缀 ⇒ 保留部分的 KV cache 失效 ⇒
重新 prefill。DWC 走远程 API，**三次调用的 cached_tokens 都是 0**：

- 要么服务端没有开启前缀缓存；
- 要么它不回报缓存命中。

两种情况的实践含义相同：**DWC 今天没有任何前缀缓存收益可以失去**。

所以"DWC 的 compaction 正在烧钱"这个推断**不成立**，必须撤回。

### 3.2 compaction 在 token 上是净省的

更早的轮次被压成 ~80 字摘要，输入 token 确实变少。
在没有缓存收益的前提下，**压缩 = 净节省**。

### 3.3 真正的风险不是成本，是信息损失

论文里与 DWC 处境对应的那一条是：

> Summary（48K 阈值）：成本 −7%，**精度 −5pp**。

DWC 的 compaction 是同一类做法（滑动窗口 + 摘要），所以它要防的是**掉分**，
不是"变贵"。这解释了 R221 当初为什么要做它（旧形态只带上一步，长任务反复重读同一文件）。

---

## 4. 对计划的修正

| 项 | 原表述 | 修正后 |
|---|---|---|
| P0-0 | 量"开 vs 关 compaction 哪个更贵" | **已量完**：无缓存可失去，压缩净省 token；风险在精度 |
| P0-b 前缀稳定性 | "把重新渲染改成稳定前缀 + 追加"以省钱 | 目标改为：**为将来缓存命中做准备 + 减少无谓重建**；当前不产生直接成本收益 |
| §11.3 "DWC 同时踩了三条" | 三条并列 | 第 ① 条（重建 prompt）**降级**：当前无成本代价，但是缓存友好的前提 |

**没有撤回的**：Harness² 那条（继承 `p.code` ⇒ −10.2）仍然成立，P1-c 优先级不变。

---

## 5. 遗留

| 项 | 状态 |
|---|---|
| `cost_usd` | 全为 `None`（缺价目表）。P0-0 用 token 作代理；用户提供价目后自动生效 |
| 样本量 | 1 个任务 / 3 次调用 —— 只够判定"缓存是否存在"，不够做分布 |
| 生产 agent | 仍跑旧代码（重启后才开始记账） |

---

## 6. 复现

```bash
cd <scratch>/p00
DWC_VAR_DIR=<scratch>/p00/var DWC_USAGE_PATH=<scratch>/p00/usage.jsonl \
  python probe.py
python -c "import json,io; [print(json.loads(l)) for l in io.open('usage.jsonl')]"
```
