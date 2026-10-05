> ⚠️ **本文件已被 `RESUME_2026-10-04_NIGHT.md` 取代**（深读 81 轮后的续接点）。
> 本文件保留 10-03 夜的 ARSI 硬缺陷审计记录（带行号），仍是有效证据。

# DWC 续接点 · 2026-10-03 夜（历史版本，ARSI 审计）

> 用途：跨会话续接。早晨开工先读本文件，再读 `ARCHITECTURE.md`。
> 状态：架构设计阶段（**未写承重代码**，src/ 为空 —— 见 §五）

---

## 一、这一夜做完了什么（7 份文档 + 1 份架构）

```text
ARCHITECTURE.md  45,835 → 75,974 字节 (v4)   gate.py 7 门全绿 rc=0

新增 7 份设计文档 (全部落 docs/):
  JUDGE_DESIGN.md          19,392  判据层三件套 + 三 split + 判据 J1-J6
  ACTOR_DESIGN.md          26,551  行动者三段式 + 痕迹新 schema + 判据 A1-A7
  JUDGE_LAYERS.md          15,360  判据三层 L1/L2/L3 + 三条纪律 + J7-J13
  IRON_LAWS_DESIGN.md      23,565  铁律数据驱动三件套 + 十条 check_fn + I1-I8
  CAUSAL_CHAIN_VS_BUS.md   15,482  事件总线裁决: 不要总线要单链 + C1-C5
  WORLD_MODEL_AUTHORITY.md 13,493  世界模型能否全权负责 + 守卫①矛盾
  WORLD_TREE.md            19,452  世界树: 一套树 + provenance 双态 + W1-W6
```

**六个器官全部深入完毕**（§4.x 字数对照）：

```text
§4.1 judge       350 → 2,678 字符   + JUDGE_DESIGN / JUDGE_LAYERS
§4.2 actor       204 → 2,779 字符   + ACTOR_DESIGN
§4.3 memory      787 字符           + MEMORY_SYSTEM / MEMORY_CONTENT (原有)
§4.4 evolver     920 字符           + EVOLUTION_CORE_V2 (31,338 字节)
§4.5 iwm         921 字符           + 防漂移三来源
§4.6 iron_laws   618 → 3,025 字符   + IRON_LAWS_DESIGN
§4.7 world_model 1,309 字符         + 任务源 / 世界树
§4.8 主体        981 字符           + 五元盘点
+ 因果链 (非器官, 是连接件)          + CAUSAL_CHAIN_VS_BUS
```

---

## 二、★ 核心发现（这一夜挖出的 ARSI 硬缺陷，全部带行号/宽口径复核）

```text
judge (sealed_eval)
  ① G10 保护是死的     enforced_laws.py:244 定义 check_sealed_access,
                       全仓调用 **0 处**
  ② 只在脚本里跑       SealedEvaluator 唯一调用点 scripts/baseline_eval.py:45
  ③ ★ 零分辨率         _verify_behavior 的 fallback:
                       score = 0.5 if has_function else 0.2; if has_return: += 0.2
                       ★ 实测: 正确实现与完全错误实现**同得 0.7**

actor (core.py)
  ④ remember 硬编码    L556-558  exec_ok = False (无条件)
  ⑤ effect 二值        L572  effect=0.6 if exec_ok else 0.2
  ⑥ 决策阈值硬编码     L491  pre_result["confidence"] > 0.1
  ⑦ evolve 是占位符    L722  docstring "(placeholder)", effect 固定 0.0

iron_laws
  ⑧ ★ 两套实现, 生产用弱的
     iron_laws.py      IronLaws          ← core.py:208 用这套 (只实现 2/10)
     enforced_laws.py  EnforcedIronLaws  ← 只有 tests 用 (真实现 G5/G6/G10)
  ⑨ warn 级从不检查    L90  if law.severity == "block"  ⇒ 6 条 warn 永不检查
  ⑩ ★ G10 读不存在的属性  L110  hasattr(state, "sealed_tasks_accessible")
                       全仓只有 tests/test_integration.py:217 设置它 ⇒ 永不触发
  ⑪ validate_policy 0 调用  L114
  ⑫ 标签错标           L127  raise "G10: budget allocation too concentrated"
                       (预算集中度实为 G2)
  ⇒ 净结果: 生产里 10 条铁律实际生效 **0 条**

世界模型
  ⑬ ★ confidence 与 accuracy 解耦
     dynamics.py TransitionModel.predict 原文:
       confidence = min(1.0, count / 20.0)   # 全置信
     ⇒ "这个动作见过多少次 / 20", 与世界模型准不准无关
  ⑭ 自述实测 (vitals_ledger.py docstring):
     "Long-run data: eta≈0, self_trust=0, live_layer1=0 while holdout=0.94"
     ★ 且 holdout 的严格评分 ARSI **已经修了** (siwm.py L455-456 时间正序 +
       L470 use_majority_fallback=False) ⇒ 94% 是修复后的严格分
     ⇒ 问题不在测量, 在**规则不迁移**

世界树
  ⑮ ★ CounterfactualSimulator (前瞻模拟) **只被构造, 从不调用**
     宽口径 grep 4 种方法名 → 0 命中
  ⑯ ★ 无树搜索: MCTS/monte/beam/alpha_beta/minimax/a_star/bfs/tree_search → 全 0
     (dfs 4 处 = 遍历; rollout 4 处 = 论文术语, 已逐行核实)
  ⑰ ARSI 全部的"收束" = 内部节点取子节点 max (后向聚合, 非搜索)
  ⑱ 三套树 (DiscoveryTree 29 次 / ReplayWorld 24 次 / Counterfactual 3 次)
```

---

## 三、★ 架构层面的两个新结论

```text
结论 A · 不要事件总线, 要单一因果链 (用户质疑驱动)
  用户: "世界模型才是驱动时间推进的动力, 不是吗" ⇒ 成立。
  ★ 正交两轴: 驱动时间 (世界模型) vs 记录因果 (原"事件层")。
  裁决: 五环共用 chain_id (决策→行动→痕迹→经验→变更), **只记录不驱动**。
  ★ 更正: 我先前说"母巢 EventBus 0 调用"是错的 —— 宽口径后确认它确实接线;
    但 chain_id 靠传, default_factory=uuid4() ⇒ 漏传即断链。

结论 B · 世界树成立, 且 ARSI 未做 (用户提出)
  一套树 + provenance ∈ {observed, simulated} + 收束**选信息增益**(非最高分)
  ★ 三条约束: ①想象节点不许进 judge ②收束判据不许用世界模型自算 confidence
    ③树只提供候选, 决策仍归世界模型
  ★ 与"影子"的区别: 想象节点不观测真实机制, 无"等待期/转正"形态。
```

---

## 四、★ §9 待定项（早晨从这里挑）

```text
★ 最该先裁决的 (架构内部矛盾, 不是"未定"):
  20. 守卫① 的内在矛盾
      原则 12 说"守卫不许来自世界模型自身", 但守卫① 用的 confidence
      就是世界模型自算的 (min(1.0, count/20.0)) ⇒ 严格说违反原则 12 自己。
      ★ 三条候选修法已列, 我倾向**乙**: 改用 judge 在 dev split 上的滑动准确率
        (真外部 + 不引入新组件 + dev 本就是"唯一有监督信号")

其余待定:
  2.  提案粒度          建议甲 (一次改一个), 用 RRSI 退火预算 b_t 而非固定值
  4.  失败签名分类法    2609.06396 附录 D 的 6 类可直接用
  5.  消费点如何验证    写入后读回的具体判据
  6.  器官接口契约      judge + actor 已定; memory/evolver/world_model/iwm 未定
  7.  世界采样策略      建议甲 (按 lineage pass-rate), EL 调度器给了零依赖答案
  12. m 与 U 的实现形态 都归 evolver, 目录已定 (modifier.py/critic.py), 接口未定
  21. state 的 schema   未定 ⇒ 阻塞 iron_laws 的不变式验证 (需喂违规 state)
  22. 因果链存储形态    未定 (追加日志? 表? 内存环?) ARSI 是 capacity=200 内存环
  23. L3 独立审计退化是否可接受  未验证 (DWC 未必有"更强的 LLM")
  24. 世界树的剪枝策略 + 想象节点存哪  未定
```

---

## 五、★ 纪律状态（重要）

```text
★ src/ 为空 —— 架构定稿前不写承重代码。
  2026-10-03 曾抢跑写过 4 个文件, 已移出至
  docs/drafts_premature_code/ (未删, 可回退), 并附 README 记教训。
  用户当时的原话: "这就开始写代码了？我们还没有完全搞定架构啊"

★ 本轮全程只改 .md 文档 + 只读审计 ARSI/母巢源码, **未改任何生产代码**。

★ 否定性结论一律宽口径复核 (本轮犯了两次, 已更正):
  · "母巢 EventBus 0 调用" → 窄 grep 漏了, 宽口径后确认接线
  · "ARSI 有 2 处 publish" → 是 "unpublished" 假阳性, 宽口径 0 命中
```

---

## 六、早晨开工建议顺序

```text
第 1 步  裁决 §9 第 20 项 (守卫① 矛盾) —— 它是唯一"已定原则与已定实现冲突"的项
第 2 步  定 §9 第 21 项 (state schema) —— 它阻塞 iron_laws 的不变式验证
第 3 步  收 §9 第 2/4/5/7 项 (都有建议答案, 可批量裁决)
第 4 步  定 §9 第 12 项 (m/U 接口) + 第 6 项 (其余器官接口契约)
第 5 步  世界树的两个未定 (剪枝 / 存储)
```

**入口**：`E:/Divine Wisdom Core/ARCHITECTURE.md`（§9 待定清单 + §11 目录结构）
**门**：`python scripts/gate.py`（7 门，当前全绿）
