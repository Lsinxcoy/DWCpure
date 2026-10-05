# 事件驱动设计：四项目对比（判据 + 实测）

> 2026-10-03 · 判据：10 条机械可测的事件驱动判据，只报实测
> 问题：从事件驱动设计角度，母巢 / Ultra / Nexus / ARSI 哪个更先进、更科学

---

## 一、先定判据（不凭感觉）

```text
事件驱动架构 (EDA) 的成熟度，机械可测的 10 条:

 ① 因果链标识   chain_id / trace_id / parent_id   —— 事件能否串成因果链
 ② 死信队列     dead_letter / dlq                  —— 处理失败的事件去哪
 ③ 历史/回放    history / replay                   —— 能否重放
 ④ 优先级       priority                           —— 订阅者调用顺序
 ⑤ 订阅者过滤   filter_fn                          —— 谁能收
 ⑥ 环检测/熔断  max_depth / circuit                —— 链会不会无限递归
 ⑦ 重试/退避    retry / backoff                    —— 失败恢复
 ⑧ 幂等/去重    dedup / seen_ids                   —— 重复事件
 ⑨ 背压/上限    maxsize / Semaphore / max_history  —— 会不会撑爆
 ⑩ 失败隔离     except handler / dead_letter       —— 一个订阅者挂了会不会拖垮全局
```

---

## 二、实测：事件基础设施

### 2.1 有没有事件总线

```text
母巢   ✓ cns/event_bus.py (1,614 字符, ★主总线, 40 行)
       + collaboration/event_bus.py (8,968 字符, 标 @legacy 已归档)
Ultra  ✓ collaboration/event_bus.py (6,511 字符)
Nexus  ✓ collaboration/event_bus.py (8,768 字符)
ARSI   ✗ 无事件总线 (0 个文件含 pub/sub 定义 ≥2)
```

### 2.2 十条判据逐文件命中

```text
文件                        字符    命中
母巢 cns/event_bus (主)     1,614   3/10
母巢 cns/dag_scheduler      6,138   3/10
Ultra event_bus             6,511   6/10   ← 最高
Ultra cns_orchestrator     25,849   4/10
Ultra dag_scheduler        23,600   4/10
Nexus event_bus             8,768   6/10   ← 最高
Nexus cns_orchestrator     27,024   4/10
Nexus dag_scheduler        27,402   4/10
Nexus cns/nexus (中枢)     20,568   1/10
Nexus dag_executor         18,926   3/10

★ 关键: Ultra/Nexus 的 event_bus 6/10 (有死信队列/回放/优先级/过滤/背压/失败隔离)
        母巢主总线 3/10 (只有优先级 + 背压 + 失败隔离)
```

### 2.3 母巢主总线只有 40 行（全文）

```python
@dataclass
class PipelineEvent:
    pipeline: str
    data: dict
    chain_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    at: float = 0.0

class EventBus:
    def __init__(self): self._subs: dict[str, list[Callable]] = {}
    def subscribe(self, pipeline, cb, priority=0.5): ...
    async def publish(self, ev): ...
    def publish_sync(self, ev): ...
```

**★ 无死信队列 / 无历史回放 / 无重试 / 无去重。** 母巢把带死信队列+回放的版本标成了 `@legacy` 归档。

---

## 三、决定性差异：因果链是否真连

### 3.1 母巢：有 `chain_id` 字段，但链是断的

```python
# cns/event_bus.py 定义
chain_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
```

```text
★ 实测: 7 处 PipelineEvent(...) 构造, chain_id 传递 = 0 处

  agent_core/loop.py   PipelineEvent(pipeline=_pipe, data=...)              chain_id=False
  agent_core/loop.py   PipelineEvent(pipeline=_alias, data=..., via=...)     chain_id=False
  agent_core/loop.py   PipelineEvent(pipeline="remember", data=...)          chain_id=False
  agent_core/loop.py   PipelineEvent(pipeline="tick_complete", data=...)     chain_id=False
  cns/nexus.py         PipelineEvent(pipeline=name, data=res_dict, ...)      chain_id=False
  cns/nexus.py         PipelineEvent(pipeline=name, data=..., at=...)        chain_id=False
  lifecycle/cerebral_cortex.py  PipelineEvent(...)                           chain_id=False

⇒ 每个事件 default_factory 自动生成新 uuid, 从不继承父链
⇒ chain_id 字段存在但从不使用 ⇒ 因果链断裂
```

### 3.2 Ultra/Nexus：链上下文经 SignalFusion 真传递

```text
★ 实测: 两边 event_bus 里 chain_id 出现 0 次 —— 不走信封, 走 SignalFusion

signal_fusion.py (Ultra 18,958 / Nexus 19,030 字符, 逐字相同):

  def chain_start(self, trigger: str) -> str:
      """启动一条新的触发链。使用栈结构支持嵌套。"""
      cid = f"{time.time_ns()}_{uuid.uuid4().hex[:6]}"
      self._chain_stack.append(cid)                    ← ★ 栈结构, 支持嵌套
      self._chains[cid] = {"trigger": trigger, "started_at": ..., "snapshots": []}

  def chain_end(self, cid): ... 记录 ended_at, 移入 _chain_history (上限 50)

  def set_chain_context(self, pipe, signals):
      """CNS 在触发下游管道前调用。将触发管的完整信号挂到当前链。
         增强：自动融合 CC 洞察 + AR 健康状态到上下文中。"""

  def get_chain_context(self) -> dict | None:
      """下游管道在开始时调用。获取触发管的结构化信号。"""
      if not self._chain_stack: return None
      active_id = self._chain_stack[-1]               ← ★ 取栈顶 = 当前链
      return self._chain_context.get(active_id)

★ 链闭合实测:
  母巢  chain_start 1 / chain_end 1   ✓ 开=关
  Ultra chain_start 6 / chain_end 6   ✓ 开=关
  Nexus chain_start 6 / chain_end 6   ✓ 开=关
```

**★ 结论**：母巢的 `chain_id` 是**装饰性字段**（有字段、无传递）；Ultra/Nexus 的链上下文是**真传递**（栈 + 上下文 + 取值）。这是两者在事件驱动上的**根本差异**。

### 3.3 但 Ultra/Nexus 的链也有缺陷

```text
✗ chain_id 不出现在事件信封 ⇒ 事件本身无因果标识
  链靠"栈顶"隐式确定 ⇒ 并发场景下会串链
  (栈是实例级, 多链并发时 get_chain_context 取栈顶可能取错)

✗ chain_history 上限 50 ⇒ 早期链丢失
✗ _trim_chains() 会裁掉链 ⇒ 无法完整回放
```

---

## 四、四项目事件驱动总表

| 判据 | 母巢 | Ultra | Nexus | ARSI |
|---|---|---|---|---|
| 事件总线 | ✓ 40 行主总线 | ✓ 6.5KB | ✓ 8.8KB | **✗ 无** |
| 死信队列 | ✗（标 @legacy 归档） | ✓ | ✓ | — |
| 历史/回放 | ✗ | ✓ | ✓ | — |
| 优先级 | ✓ | ✓ | ✓ | — |
| 订阅者过滤 | ✗ | ✓ | ✓ | — |
| **因果链** | **字段有/传递无** | **真传递（栈+上下文）** | **真传递** | ✓ provenance |
| 环检测/熔断 | ✓（DAG 计划） | ✓ max_depth=6 | ✓ max_depth=6 | ✓ |
| 重试/退避 | ✓（SGH recover） | ✓ | ✓ | ✓ |
| 幂等/去重 | ✗ | ✗ | ✗ | ✗ |
| 背压/上限 | ✓ Semaphore | ✓ max_history | ✓ max_history | — |
| 失败隔离 | ✓ | ✓ | ✓ | — |
| **条件触发** | ✗ 全跑 run_all | **✓ 阈值+事件** | **✓ 阈值+事件** | ✗ 单动作 |
| **统一中枢** | ✗ | ✗ | **✓ cns/nexus.py** | ✓ core.py |
| 运行证据 | ✓ 44 天 | ✗ 无日志 | ✓ api_server.log | — |

---

## 五、结论：谁更先进

### 排名（按事件驱动设计科学性）

```text
① Nexus     —— 最先进
   事件总线 6/10 + 因果链真传递 + 条件触发 + 统一中枢(仲裁者) + 效果遥测
   ★ 唯一同时具备"事件驱动 + 统一仲裁 + 效果闭环"的项目

② Ultra     —— 与 Nexus 同源, 但少一个统一中枢
   事件总线 6/10 + 因果链真传递 + 条件触发
   ★ 缺 cns/nexus.py (仲裁者), 无运行日志

③ 母巢       —— 有 DAG 调度, 但事件层薄
   主总线 40 行 3/10 + chain_id 装饰性 + 无死信/回放
   ★ 强在 DAG 计划与 SGH 恢复协议, 弱在事件基础设施

④ ARSI      —— 无事件总线
   不走事件驱动, 走"每步选一个动作"的命令式循环
```

### 但"更先进"要加三个限定

```text
限定 1 · Nexus 的先进是"设计层", 不是"运行层"
  246 个机制 invoke_count 全 0 / dynamic_names=[] / T4 编译 5 次全返回 None
  ★ 事件驱动骨架搭好了, 但事件源(动态机制)是空的

限定 2 · Ultra/Nexus 的链有并发缺陷
  chain 靠"栈顶"隐式确定, 多链并发会串链
  母巢虽然链断, 但它的 DAG 计划是显式的 (PlanNode + 依赖边)
  ★ 显式 DAG 在并发安全上优于隐式栈

限定 3 · 母巢的"全跑"其实不是缺点
  母巢 run_all 每轮跑七管 —— 对"记忆巩固"这类必须周期性做的事是对的
  Ultra/Nexus 的条件触发省周期, 但需要事件源稳定
  ★ 两者适用场景不同: 周期任务 vs 响应式任务
```

---

## 六、对 DWC 的采纳建议

```text
采纳 1 · 事件总线用 Ultra/Nexus 的形态 (6/10)
  死信队列 + 历史回放 + 优先级 + 订阅者过滤 + 背压 + 失败隔离
  ★ 不用母巢 40 行版

采纳 2 · 因果链用 Ultra/Nexus 的"栈 + 上下文"形态, 但补并发安全
  ① chain_id 必须进事件信封 (母巢有字段没用, Ultra 没字段)  ← 两者取长
  ② 链上下文不用栈顶隐式取, 用显式 chain_id 查表 (避免并发串链)
  ③ chain_history 不设 50 上限, 或落盘

采纳 3 · 环检测用 Ultra/Nexus 的 max_depth + min_interval
  ★ 同时保留母巢的显式 DAG 计划 (PlanNode + 依赖边 + 恢复协议)

采纳 4 · 统一中枢用 Nexus 的 cns/nexus.py 形态
  仲裁者不执行 + dispatch 自带效果遥测 + prune_harmful 突触修剪
  ★ 但要补 Nexus 没做的: 动态层必须有事件源 (否则 invoke_count 全 0)

★ 一句话总结 DWC 该学的:
  事件层学 Ultra/Nexus, 调度层学母巢的显式 DAG, 仲裁层学 Nexus 的中枢,
  并把母巢的 chain_id 字段真正用起来 (进信封 + 查表取链)
```
