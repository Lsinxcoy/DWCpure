# DWC 消费点验证判据（§9 第 5 项）

> **状态**：设计定稿（**未写代码**，`src/` 仍为空）
> **日期**：2026-10-04
> **前置已定**：原则 4「进化产物必须有运行时消费点」；
> §4.4 已定消费点声明形态（`consumer/path/attr/range/verify`）与三条纪律。
> **本文件只补一件事**：**`verify` 的具体判据体系** —— 写入后如何证明它真的生效了。
> **参照（已逐行核）**：
> `E:/SYNTHEX Autopoiesis/src/synthex_autopoiesis/evolution/gene_applier.py`（6,886 字符）
> `E:/ARSI/src/arsi/empowerment/engine.py` L170（`record_empowerment` 调用点）

---

## 一、★ 母巢的实测缺陷（本项存在的理由）

### 1.1 GENE_TARGETS 有五项，但**没有 verify**（逐行核 gene_applier.py L44-73）

```python
GENE_TARGETS: dict[str, dict[str, Any]] = {
    "exploration_rate": {"consumer": "MultiStrategyScheduler ε-greedy 探索率",
                         "path": "loop._evo_scheduler._epsilon",
                         "attr": "_epsilon", "range": (0.01, 0.5)},
    "learning_rate":    {"consumer": "MemPO GRPO 记忆效用更新步长",
                         "path": "loop._mempo._grpo_lr", ...},
    "temperature":      {"consumer": "ThermodynamicIntelligence 温度", ...},
    "memory_weight":    {"consumer": "MemoryFacade TRS 可靠性权重 η", ...},
    "stability_factor": {"consumer": "分支合并门阈值 (经 merge_threshold_from 映射)",
                         "path": "loop._merge_gate_threshold", "range": (0.5, 1.0)},
}
```

★ 五项都有 `consumer/path/attr/range`；**ARCHITECTURE 说"DWC 多一个 verify"—— 核实为真**。

### 1.2 ★★★ 决定性证据：`apply_genes` 只写不读（L171-206 逐行核）

```python
for _e in _plan["mapped"]:
    if not _e["found"]: continue
    _obj, _attr = _resolve(loop, GENE_TARGETS[_g]["path"])
    if _obj is None: continue          # ← 对象解析失败, 静默跳过, 不计入任何错误
    try:
        setattr(_obj, _attr, _new)
        _applied += 1                   # ← 写完就记成功
    except Exception as _err:
        _errors[_g] = str(_err)[:60]    # ← 抛了只截 60 字符
```

★★ **三条硬缺陷**：

```text
D1 · 写完即算成功: `_applied += 1` 在 setattr 之后, **没有任何读回**
    ⇒ setattr 对一个 property 生效了、或对 dataclass frozen 字段静默失败, 都算成功

D2 · 对象解析失败被静默吞掉: `_obj is None: continue`
    ⇒ 路径写错（重构改了属性名）→ 这个基因永远不生效, 且**不报错**、
      不进 `_errors`、不进 `need_setter`
      ★ 这就是"写了没人消费"的**生成机制** —— 不是没接, 是接不上且不吭声

D3 · 错误只截 60 字符: 排障时看不到上下文
```

### 1.3 一次成功的假象：`stability_factor` 走映射（L74-90）

```python
def merge_threshold_from(stability_factor):
    """stability_factor ∈[0.5,1.0] → 合并门阈值 ∈[0.5,0.75]"""
    _sf = max(0.5, min(1.0, float(stability_factor)))
    return round(MERGE_GATE_BASE + 0.5 * (_sf - 0.5), 6)
```

★ **候选值 ≠ 写入值**（基因是 0.9，门阈值是 0.70）。
⇒ ★★ **这直接决定了 verify 的形态**：读回比对时必须比**变换后的值**，
   不能比候选原值。ARCHITECTURE §4.4 现有的 verify 写法
   `abs(actor._policy._epsilon - candidate) < 1e-9` **只对直写型成立**。

---

## 二、★★ 三级验证（缺一级则对应缺陷复发）

```text
Level 1 · 解析验证（防 D2）—— 写之前
  能不能走到目标对象? 走不到 ⇒ 报错, 不许 continue
  判据: resolve(path) 返回非 None, 且 getattr(obj, attr) 不抛
  ★ 这一级把"静默跳过"变成"显式失败"

Level 2 · 写后读回（防 D1）—— 写之后立即
  读回值 == 期望值（期望值 = 变换后的值, 不是候选原值）
  不等 ⇒ 报错 + 自动回滚 + 记 errors

Level 3 · 行为验证（防"接线但没生效"）—— 下一轮运行时
  ★ 这一级是本设计新增的, 母巢与 ARSI 都没有
  判据: 该消费点在**下一个决策点**上真的读到了新值
  ★ 依据: 原则 9「世界模型必须门控决策」的血泪 ——
    "有世界模型但不让它驱动, 是矫枉过度"（母巢 MWM_WEIGHT_CAP=0.1, dyna 默认关）
    ⇒ ★ 读回成功只证明"写进去了", 不证明"有人在用"
```

### Level 3 为什么必须单独一级

```text
★ 两种"写进去了但没用"：
  L1 成功 + L2 成功 + L3 失败 = 死基因（写了、读回了、没人消费）
    ⇒ 这正是母巢 branch_merges 167,753 行的形态

  ★ 而 L3 的判据可直接复用原则 9 的判据形式:
    原则 9: "世界模型的输出必须至少有一处'门控决策'的消费点"
    L3   : 每个基因必须至少有一处"决策点"的消费点
  ★★ 二者是同一条纪律在两个对象上的应用 ⇒ 不新增概念，只新增检查对象
```

---

## 三、★★ verify 的判据形态（按"是否经变换"二分）

```python
@dataclass(frozen=True)
class ConsumerSpec:
    consumer: str                    # 人读的说明: "策略选择 ε-greedy 探索率"
    path: str                        # "loop._evo_scheduler._epsilon"
    attr: str                        # "_epsilon"
    range: tuple[float, float]       # (0.01, 0.5)
    transform: Optional[str] = None  # ★ None=直写; 否则是变换函数名（如 merge_threshold_from）
    verify: str                      # 读回表达式（见下）
    # ★★ 新增三字段（母巢没有的）
    decision_probe: str = ""         # Level 3: 在哪个决策点能观察到影响
    expected_readback: str = ""      # Level 3: 期望读到什么（如 "epsilon_used=0.42"）
```

### 3.1 直写型 vs 变换型（★ 由 1.3 的发现驱动）

```text
直写型 (transform=None):
  读回比对: |readback − candidate| < tol
  母巢五个基因里 exploration_rate / learning_rate / temperature / memory_weight
  属此类 ⇒ ARCHITECTURE 现有的 verify 写法对它们成立

变换型 (transform="merge_threshold_from"):
  ★ 读回比对: |readback − transform(candidate)| < tol
  ⇒ 候选原值永远比不上 ⇒ 若照现有写法, stability_factor 会**恒定失败**
  ⇒ ★★ 这是本设计纠正的第一个实质错误
```

### 3.2 tol 的取法（★ 不能一律 1e-9）

```text
依据纪律 3 的教训: "打分器没分辨率时, 调门槛是自欺"
⇒ 同理, **tol 的取法取决于值域, 不取决于"精度越高越好"**:

  浮点连续量 (temperature, epsilon):  tol = 1e-9        （Python float 精确表示）
  经映射的量 (merge_threshold):        tol = 1e-6        （round(…, 6) 的粒度）
  整数/枚举量:                          tol = 0, 用 ==
  ★ 若被验证的属性内部做了 clamp（母巢 _clamp 就是）, 期望值必须用 **clamp 后的值**:
      expected = clamp(candidate, *spec.range)
    ⇒ 否则落在 range 外的候选会恒定"验证失败", 而实际写入是对的
```

---

## 四、★★ 三态结果（不许把失败当成功，也不许把未验证当成功）

```python
@dataclass(frozen=True)
class ApplyResult:
    gene: str
    outcome: str          # "applied" | "verified" | "rejected" | "unverified" | "failed"
    readback: Any         # 实际读回值
    expected: Any         # 期望值（含 transform + clamp 之后）
    error: str = ""       # 失败原因，不截断（修正 D3）
    probe_seen: Optional[bool] = None   # Level 3 结果，未跑到下一轮时是 None
```

```text
★ 五个 outcome 的语义（★ 关键的坑在最后两个）：

  applied    写入成功且读回一致，但 Level 3 还没跑到
  verified   三级全过
  rejected   候选被门拒（不是验证失败, 是流程正常拒绝）
  failed     写入或读回出错（Level 1/2 失败）⇒ 已自动回滚
  unverified ★★ Level 3 没观察到消费 ⇒ **死基因**
            ★ 它不是 failed —— 系统没出错, 但这条进化白做了
            ★★ 必须与 failed 分开统计, 否则"死基因"会被混进"技术失败"里看不见
            ⇒ 依据原则 4: 无消费点的产物 = 不许进准入流程
```

---

## 五、★★ 记录格式（让死基因事后可查）

```python
@dataclass(frozen=True)
class ConsumerAudit:
    """每条基因每轮一条，进因果链（CAUSAL_CHAIN_STORAGE §三 chain_record 的 payload）。"""
    chain_id: str
    gene: str
    outcome: str
    expected: Any
    readback: Any
    probe_target: str      # decision_probe 的值
    probe_observed: Any    # 下一轮实际读到的
    probe_match: Optional[bool]
    generation: int
    recorded_at: str
```

```text
★ 为什么必须是结构化记录而不是日志行:
  「死基因」要能被**聚合查询** —— "近 20 轮里有多少条基因 outcome==unverified"
  ⇒ 依据原则 8 的判据形式（严格口径: import 次数 + invoke 次数都算）
  ⇒ 这里同构: 一个基因的"消费"= writeback 成功 + probe_match == True
```

---

## 六、可机械检查的判据（gate.py 候选，V1–V6）

```text
V1 · ConsumerSpec 的 transform 与 verify 表达式一致
   若 transform 非 None, 期望值必须用 transform(candidate), 不得用 candidate
   ★ 依据: §1.3 stability_factor 的反例（候选 0.9 → 写入 0.70）

V2 · Level 1 解析失败必须 raise, 不许 continue
   grep: 消费点模块里 "is None: continue" 且该 continue 处于 resolve 之后 ⇒ 违规
   ★ 依据: D2（母巢 _obj is None: continue）

V3 · setattr 之后必须有 readback, 且 counted as applied 必须在 readback 之后
   ★ 依据: D1（母巢 _applied += 1 紧跟 setattr）

V4 · range 之外的候选必须 clamp 后再验证
   ★ 依据: 母巢 _clamp 的存在（gene_applier L138）

V5 · outcome 五态齐全, 且 unverified 单独统计
   ★ 依据: 原则 4（无消费点 = 不许进准入）

V6 · ConsumerAudit 进因果链, 且有聚合查询（按 outcome 分组计数）
   ★ 依据: §五 —— 没有聚合查询就查不出死基因
```

---

## 七、诚实边界

```text
① 本设计**未写代码**，`src/` 仍为空 —— 符合"架构定稿前不写承重代码"的纪律。
② 未验证: V1–V6 全是设计推理，尚无实现可跑。
③ ✓✓【已解 2026-10-04】Level 3 的可行性: **可实现**（docs/LEVEL3_PROBE.md）
   ★★★ 核实结果: 当初"决策点形态未定稿"的阻塞理由**不成立** ——
     决策点形态已隐含在 §4.2（actor 三段式 + 决策优先级 + 三分离）里:
       ① sample_gate  ← §4.2 ① 段「legal_actions() → 采样（EL 调度器）」
       ② source_gate  ← §4.2 ② 段 decide「预测（有门控）→ LLM → 启发式」
       ③ action_gate  ← §4.2 ② 段 act（甲任务动作 / 乙维护动作）
     ⇒ ★ 不必新造"决策点"概念, 探针挂在这三处即可
   ★★ 三个真问题（难点不在"能不能写探针"）:
     问题1 归因混淆: |本轮编辑集|>1 ⇒ 判 unverified + reason="multi_edit"
       （不新增第六态 —— 新增会破坏 outcome 的可聚合性）
     问题2 窗口长度: window_rounds 的上限 = term 边界（A5 已定）
       ⇒ ★★ A5 成为 L3 的依赖 ⇒ 依赖链闭合
     问题3 观察≠因果: 判据只要求"在决策中被读到", 不要求"决定了决策"
       ★★ 因为 §9 第 7 项已定 FWT 只作偏置不作闸门 ⇒ 强形式不可证
       ⇒ 这是**有意的保守不足**
   ★ unverified 的四种 reason: multi_edit / window_expired
     / probe_missing / gate_silent
   判据 L1–L6（同族第十二族: L 管探针的存活性）
   ★★ 未解决: action_gate 的归因混淆（iwm 的频率本身可能是另一基因的效果）
   ★ 未定: window_rounds 的具体值（只定了上限来源）
④ ★ tol 的三个具体值（1e-9 / 1e-6 / 0）来自 Python 语义推理，
   未在真实值上测过。母巢没有 verify ⇒ 无实测可参照。
⑤ transform 目前只规划了一个函数名（merge_threshold_from，来自母巢）。
   ★ DWC 的落地器是否需要更多变换，取决于第 12 项（m 与 U 的实现形态）。
⑥ 未核实: 母巢是否有**别处**在别的地方做了读回验证
   （我只核了 gene_applier.py 一个文件 6,886 字符 + grep GENE_TARGET 命中 5 文件，
     后 4 个是 tests 与 production_benchmark，未逐行读）。
   ★ 若别处已有读回, 则 D1 的结论需下调为"该文件内无读回"。
⑦ Level 1/2/3 的名字是我的命名，不是论文术语。
```

---

## 八、★ 实测记录（已跑通，并证实两个实质错误）

```text
✓ 直写型: 候选0.3/读回0.3 → True; 读回0.31 → False
✓ 变换型: 候选0.9 → 期望写入 0.70（merge_threshold_from 生效）
✓ 越界:   候选0.99 → clamp 后期望 0.5
✓ 五态可构造; unverified(probe_seen=False) 与 failed(probe_seen=None) 可分离

★★★ 实测证实: ARCHITECTURE §4.4 现有的 verify 写法有**两个实质错误**
  错误一 · 变换型基因恒失败:
    现有写法: abs(readback − candidate) < 1e-9
    实际:     候选0.9 写入 0.70 ⇒ |0.70−0.9| = 0.20 > tol ⇒ **恒判失败**
    ⇒ stability_factor 这个基因在母巢是活的, 照现有写法搬到 DWC 会立刻失效
  错误二 · 越界候选被误判为失败:
    候选0.99（range 上界 0.5, 母巢会 clamp 到 0.5）
    现有写法: |0.5 − 0.99| > tol ⇒ 判失败, 但**实际写入是对的**
    ⇒ 正确期望值必须走 clamp(candidate) 再 transform, 顺序不可换

★ 修正后: expected = transform(clamp(candidate))
  —— 顺序有讲究: 先 clamp 语义边界, 再做语义映射
  （母巢 _clamp 作用于基因值, merge_threshold_from 也作用于 clamp 后的值, 已核 L138+L191）

★ 另一次自测失败是我**自测逻辑错**（verify() 内部已用期望值,
  我又让它用候选原值还期望 False）—— 不是代码错, 已改为显式写两个函数对照。
```

---

## 九、诚实边界（补）

```text
⑧ 实测覆盖: expected_value / tol_for / 两种 verify 写法 / 五态构造。
   **未测**: Level 1 的 resolve 路径解析、Level 3 的探针机制、
   ConsumerAudit 的聚合查询 —— 三者都需要真实对象图才能跑。
⑨ ★★ 本设计纠正了 ARCHITECTURE §4.4 的现有 verify 写法（两个错误）。
   ⇒ 那是已定内容, 修改需在 §4.4 标注更正, 本文件不擅自改已定段落。
```

---

*设计定稿 · 2026-10-04 · 三级验证 + 两型 verify + 五态结果 · 参照母巢 gene_applier.py 6,886 字符逐行核 · 未写代码*