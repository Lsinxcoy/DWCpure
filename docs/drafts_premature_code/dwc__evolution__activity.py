# -*- coding: utf-8 -*-
"""DWC-AUTO · 活性六层 + 四量度量 —— V2 器官①（诊断）的度量部分。

## 两个来源（取证，非推断）

### 一、活性六层 —— 来自 HarnessX (arXiv:2606.14249) 的 hook 契约检查

HarnessX §3.2 原文要求 run loop 在每次调用后校验 hook 契约：
    "违规（如修改 read-only 字段）**立即抛异常**，而不是静默传播损坏状态。"
⇒ 本模块的六层是**逐层独立**的布尔，不是"一个健康度分数"。

六层（自下而上，弱判据不得越级点亮强判据）：

    present          文件/注册表里存在
    registered       登记表里有它
    called           Γ 中出现调用事件
    succeeded        外部回执匹配
    produced_effect  下游可观测产物
    feedback_closed  回到判分器

★ 层名与顺序取自 Recuris (arXiv:2608.24876) 的 Structured Trace Γ 与
  Table 4 的故障定位协议：
    "An invocation fault is a **non-event**: nothing appears in the transcript
     where a skill should have been injected"
  ⇒ Γ 必须记录"**本应调用但未调用**"（负事件），不能只记发生过的事。
  本模块用 `expect()` 显式登记"应调用"，从而能判出 non-event。

### 二、四量度量 —— 来自 The Last AI Built by Humans (arXiv:2609.11873)

原文（§5.1）：
    "a relevant skill may never be retrieved, or an agent may retrieve it
     without following it correctly"

⇒ 必须**分别**度量四个量，不能合成一个：
    update_quality      写得对不对
    activation          会不会被检索到
    faithful_use        检索到会不会照做
    downstream_benefit  照做有没有用

★ 这四量直接治母巢的病：母巢只测 update_quality，于是
  98.8% 未访问（activation=0）无人发现。

## TRUTH_SOURCE 声明（gate.py G2 要求）

TRUTH_SOURCE = "behavior_trace" —— 四量的取数来自行为轨迹（外部回执），
不来自模块自评。`downstream_benefit` 必须由调用方传入**系统外**的观测，
本模块不自己打分。

## 本模块不做什么

- 不产生候选（那是 m）
- 不裁决改动（那是 U）
- 不把六层合成一个"健康分"（那正是母巢 MechanismHealth 的病：
  只有 3 个字段 call_count / is_healthy / last_called，把"从未调用"
  塞进 stale）
"""
from __future__ import annotations

__all__ = [
    "TRUTH_SOURCE",
    "LAYERS",
    "ActivityRecord",
    "ActivityLedger",
    "four_measures",
]

# ── gate.py G2 要求的真值源声明 ───────────────────────────────────
TRUTH_SOURCE = "behavior_trace"

# ── 六层（自下而上，顺序即单调性约束） ─────────────────────────────
LAYERS = ("present", "registered", "called", "succeeded",
          "produced_effect", "feedback_closed")

# 弱判据：这些层只能由对应的**外部证据**点亮，不得由调用方随手置 True。
_WEAK_ONLY = frozenset({"present", "registered"})
_STRONG = frozenset({"succeeded", "produced_effect", "feedback_closed"})


class ActivityRecord:
    """一个组件的活性记录 —— 六层布尔 + 负事件登记。

    与母巢 MechanismHealth 的区别：
      母巢: call_count / is_healthy / last_called（3 字段，"从未调用"混入 stale）
      本类: 六层独立 + expected 负事件 + 每层自带证据串
    """

    __slots__ = ("name", "layers", "evidence", "expected", "calls", "rejections")

    def __init__(self, name: str):
        self.name = name
        self.layers = {k: False for k in LAYERS}
        self.evidence = {k: "" for k in LAYERS}
        self.expected = 0      # 本应调用的次数（负事件分母）
        self.calls = 0         # 实际调用次数
        self.rejections = []   # 被拒的越级点亮尝试（可观测，不静默）

    # ---- 负事件：登记"本应调用" ------------------------------------
    def expect(self, n: int = 1) -> None:
        """登记 n 次"本应调用"。用于判出 Recuris 的 ρ 类 non-event。"""
        try:
            n = int(n)
        except (TypeError, ValueError):
            return
        if n > 0:
            self.expected += n

    # ---- 逐层点亮（带单调性强制） ----------------------------------
    def mark(self, layer: str, evidence: str = "") -> bool:
        """点亮某一层。返回是否成功。

        规则（HarnessX 的契约检查形态 —— 违规不静默，记录并拒绝）：
          ① layer 必须在 LAYERS 内
          ② 强判据（succeeded 及上层）不得在弱判据未亮时点亮
             —— 这是 Recuris 的因果单调性，也是母巢"弱判据越级"的反例
          ③ 每次成功点亮都留 evidence（空证据也记，不伪造内容）
        """
        if layer not in self.layers:
            self.rejections.append(("unknown_layer", layer))
            return False
        idx = LAYERS.index(layer)
        for lower in LAYERS[:idx]:
            if not self.layers[lower]:
                # 越级：不抛异常（这是数据问题不是程序错误），但**必须记录**
                self.rejections.append(("not_monotonic", layer, lower))
                return False
        if layer == "called":
            self.calls += 1
        self.layers[layer] = True
        if evidence:
            self.evidence[layer] = str(evidence)[:200]
        return True

    # ---- 派生量 ----------------------------------------------------
    @property
    def highest_layer(self) -> int:
        """已点亮的最高层下标；一层未亮 ⇒ -1。"""
        h = -1
        for i, k in enumerate(LAYERS):
            if self.layers[k]:
                h = i
        return h

    @property
    def is_monotonic(self) -> bool:
        """六层是否满足单调（低层为真 ⇒ 更高层为真也需低层为真）。"""
        seen_false = False
        for k in LAYERS:
            if not self.layers[k]:
                seen_false = True
            elif seen_false:
                return False
        return True

    @property
    def non_events(self) -> int:
        """本应调用但从未调用的次数 —— Recuris 的 ρ 类故障。

        ★ 这是母巢 98.8% 未访问能被发现的**唯一**方式：
          母巢只看 calls==0，但 calls==0 既可能是"不需要"也可能是"该调没调"。
          有了 expected，两者可分。
        """
        if self.layers["called"]:
            return 0
        return self.expected

    @property
    def status(self) -> str:
        """五态 —— **"从未调用"单列，不混入 stale**。

        对齐 gate.py G3 的规则与母巢 P2-3 的反例。
        """
        if not self.layers["present"]:
            return "absent"
        if not self.layers["registered"]:
            return "unregistered"
        if not self.layers["called"]:
            return "never_called" if self.expected else "not_yet_called"
        if not self.layers["feedback_closed"]:
            return "active_open"          # 调了但回路未闭
        return "healthy"

    def to_dict(self) -> dict:
        return {"name": self.name, "status": self.status,
                "highest_layer": self.highest_layer,
                "layers": dict(self.layers), "evidence": dict(self.evidence),
                "calls": self.calls, "expected": self.expected,
                "non_events": self.non_events,
                "is_monotonic": self.is_monotonic,
                "rejections": list(self.rejections)}


class ActivityLedger:
    """活性台账 —— 六层记录 + 四量度量。

    上限与淘汰（对齐 gate.py G4 的"生成能力必须配套淘汰判据"）：
    台账有 `POOL_LIMIT`，超限时按 `OVERFLOW` 策略处理，
    并必须有 `evict` 路径 —— 不允许只增不减。
    """

    POOL_LIMIT = 4096          # 台账上限
    OVERFLOW = "evict_stalest"  # 超限行为：淘汰最久未动者

    def __init__(self, pool_limit: int | None = None):
        self._recs: dict[str, ActivityRecord] = {}
        self._order: list[str] = []        # 近似 LRU（确定性）
        self.limit = int(pool_limit or self.POOL_LIMIT)

    # ---- 基本操作 --------------------------------------------------
    def touch(self, name: str) -> ActivityRecord:
        """取或建记录。超限时先淘汰。"""
        if name not in self._recs:
            self._maybe_evict()
            self._recs[name] = ActivityRecord(name)
        if name in self._order:
            self._order.remove(name)
        self._order.append(name)
        return self._recs[name]

    def _maybe_evict(self) -> None:
        """超限 ⇒ 淘汰最久未动者（非"最旧" —— 母巢教训：忘掉无用的不是忘掉旧的）。"""
        while len(self._recs) >= self.limit and self._order:
            victim = self._order.pop(0)
            self._recs.pop(victim, None)

    def evict(self, name: str) -> bool:
        """显式淘汰。返回是否真的删掉了。"""
        self._recs.pop(name, None)
        if name in self._order:
            self._order.remove(name)
            return True
        return False

    def get(self, name: str) -> ActivityRecord | None:
        return self._recs.get(name)

    def by_status(self) -> dict:
        """按状态分组计数 —— `never_called` 单列，不混 stale。"""
        out: dict[str, list[str]] = {}
        for n, r in self._recs.items():
            out.setdefault(r.status, []).append(n)
        return {k: sorted(v) for k, v in out.items()}

    def non_event_report(self) -> dict:
        """负事件报告 —— 哪些组件"该调没调"。"""
        bad = {n: r.non_events for n, r in self._recs.items()
               if r.non_events > 0}
        return dict(sorted(bad.items()))

    def __len__(self) -> int:
        return len(self._recs)


def four_measures(*, update_quality=None, activation=None, faithful_use=None,
                  downstream_benefit=None) -> dict:
    """四量度量 —— 分别返回，**不合成一个分数**。

    The Last AI Built by Humans (arXiv:2609.11873) §5.1 原文：
        "a relevant skill may never be retrieved, or an agent may retrieve it
         without following it correctly"

    ⇒ 四个量分别可测，缺任一个就缺一个诊断维度。

    诚实边界：`None` 表示**不可测**，保留 None 不填 0
    （填 0 会把"没测"伪装成"测出来是 0"，这是母巢的病）。
    """
    def _keep(x):
        if x is None or isinstance(x, bool):
            return None
        try:
            v = float(x)
        except (TypeError, ValueError):
            return None
        if v != v or v in (float("inf"), float("-inf")):   # NaN / inf
            return None
        return v

    m = {"update_quality": _keep(update_quality),
         "activation": _keep(activation),
         "faithful_use": _keep(faithful_use),
         "downstream_benefit": _keep(downstream_benefit)}
    measured = [k for k, v in m.items() if v is not None]
    m["measured_count"] = len(measured)
    m["unmeasured"] = sorted(k for k, v in m.items()
                             if v is None and k != "measured_count")
    m["TRUTH_SOURCE"] = TRUTH_SOURCE
    return m
