# -*- coding: utf-8 -*-
"""DWC 六层活性模型的载体 —— Γ 事件级机制活动追踪。

★★★ 这个模块为什么现在写
  2026-10-05 用户裁决：**DWC 采用六层活性模型**（2608.24876 §2.2.3 的 Γ 结构）。
  而六层的正确载体是 Γ 事件上的机制/组件，不是 Python 文件
  ⇒ 所以 gate.py 的 G3 需要一个真正的实现来"点亮"，否则永远是"待实现"。

定位声明（DWC-MEM · 记忆底座 · 判据 G1 定位门）
  ★ 机制活动状态 = "进化产物是否真被用"的记忆 ⇒ 属记忆底座。
  ★ 本模块只提供数据契约与单调性校验，不做任何 IO、不决定进化。

六层与点亮来源（2608.24876 §5.1.2 原文映射）
    present         ← 文件 / 注册表存在
    registered      ← 进入登记表（机制注册表）
    called          ← Γ 中出现调用事件
    succeeded       ← 外部回执匹配（★ 不是"我没抛异常"）
    produced_effect ← 下游可观测产物
    feedback_closed ← 回到判分器

★★★ Table 4 的硬要求（本模块的核心设计约束）
  论文实测: 仅结果证据的故障定位 Macro-F1 = 0.0，**低于恒定猜测基线 33.3%**；
  原始轨迹条件下 Macro-F1 = 61.1。
  ⇒⇒ Γ **必须记录"本应调用但未调用"**（负事件），否则 DWC 会重犯
     母巢"调用失败看不出"的错（MechanismHealth 只有 call_count/is_healthy/
     last_called 三字段，把"从未调用"塞进 stale）。
  ⇒⇒ 所以本模块有第三个事件类型 `NOT_CALLED`，它**不是**异常路径，
     而是**一等公民**：没调用是重要信息，不是缺失。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple

# ══════════════════════════════════════════════════════════
# 六层
# ══════════════════════════════════════════════════════════


class Layer(str, Enum):
    PRESENT = "present"
    REGISTERED = "registered"
    CALLED = "called"
    SUCCEEDED = "succeeded"
    PRODUCED_EFFECT = "produced_effect"
    FEEDBACK_CLOSED = "feedback_closed"


#: ★★ 2026-10-05 第二次更正（接线层测试逼出来的，第二次）
#:   改掉"自动补齐"之后，暴露出第二个我强加的语义:
#:   我把六层做成了**单向有序链**（点了 produced_effect 就必须先有 succeeded）。
#:   ⇒⇒ 但核 2608.24876 §5.1.2 原文（已逐字核）:
#:     它只说 "G3 活性门的六层可直接从 Γ **逐层点亮**",
#:     给了六个**并列**的来源（文件/登记表/Γ 事件/外部回执/下游产物/回到判分器），
#:     **从未说下游蕴含上游，也从未说它们必须按序点亮**。
#:   ⇒⇒★ 实测反证（比推理更硬）:
#:     一次调用若"没外部回执但下游确实观测到了产物"
#:     （例如产物由 side-channel 产生），在有序链模型下**无法表达**
#:     —— 而这是真实存在的情况。
#:   ⇒⇒⇒ 正确模型: 六层是**六份并列证据**，不是一条链。
#:     ORDER 只保留给 depth() 报告"证据有几份、最深到哪"，不施加顺序约束。
ORDER: Tuple[Layer, ...] = (
    Layer.PRESENT,
    Layer.REGISTERED,
    Layer.CALLED,
    Layer.SUCCEEDED,
    Layer.PRODUCED_EFFECT,
    Layer.FEEDBACK_CLOSED,
)

#: ★ 某层点亮所**要求**的证据集合（空集 = 该层可独立成立）。
#:   只有 present 有要求（机制必须存在）；其余层各自独立取证。
REQUIRES: Dict[Layer, frozenset] = {
    Layer.PRESENT:            frozenset(),
    Layer.REGISTERED:         frozenset({Layer.PRESENT}),
    Layer.CALLED:             frozenset({Layer.PRESENT}),
    Layer.SUCCEEDED:          frozenset({Layer.CALLED}),
    Layer.PRODUCED_EFFECT:    frozenset(),   # ★ 下游产物可独立被观测到
    Layer.FEEDBACK_CLOSED:    frozenset(),   # ★ 回到判分器可独立发生
}

ORDER_INDEX: Dict[Layer, int] = {lay: i for i, lay in enumerate(ORDER)}


# ══════════════════════════════════════════════════════════
# Γ 事件（★ 三类，第三类是负事件）
# ══════════════════════════════════════════════════════════


class EventKind(str, Enum):
    REGISTER = "register"        # ← registered
    CALL = "call"                # ← called
    RECEIPT = "receipt"          # ← succeeded（外部回执匹配）
    EFFECT = "effect"            # ← produced_effect（下游可观测产物）
    FEEDBACK = "feedback"        # ← feedback_closed（回到判分器）
    NOT_CALLED = "not_called"    # ★★★ 负事件：本应调用但未调用


#: 事件类型 → 它点亮哪一层。★ NOT_CALLED 不点亮任何层（它记录"缺失"）
EVENT_TO_LAYER = {
    EventKind.REGISTER: Layer.REGISTERED,
    EventKind.CALL: Layer.CALLED,
    EventKind.RECEIPT: Layer.SUCCEEDED,
    EventKind.EFFECT: Layer.PRODUCED_EFFECT,
    EventKind.FEEDBACK: Layer.FEEDBACK_CLOSED,
    # EventKind.NOT_CALLED → None（负事件，见上文 Table 4 硬要求）
}


class LayerError(Exception):
    """违反层单调性。★ 承重代码不许静默降级（判据 E2/E3）。"""


# ══════════════════════════════════════════════════════════
# 机制活动状态（immutable snapshot）
# ══════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ActivityState:
    """一个机制在某时刻的活性快照。★ frozen ⇒ 不可变（判据 I6 同款）。

    ★★★ 2026-10-05 重大更正（接线层测试逼出来的）
      原实现在 `lit()` / `stamp()` 里**自动补齐上游层**，
      我当时把它当成"单调性"的实现。
      ⇒★ 但那其实是两件不同的事，我把它们混成了一件:

        单调（monotonic）: 弱判据**不得越级点亮**
          —— 语义: 你不能只声明 succeeded 而不声明 present/called
        蕴含（entailed）: 声明了下游 ⇒ 上游必然成立
          —— 语义: 走到 feedback_closed 就说明 succeeded 已被观测

      ⇒⇒★ 而六层要的只是前者，**不要后者**:
        "闭环回到判分器了" 并不证明 "外部回执匹配过"
        （评分器可能没看 receipt 就闭环，也可能 receipt 是伪造的）
      ⇒⇒ 错误的后果（实测）: 点亮最深的 FEEDBACK_CLOSED 会自动补齐
        present..succeeded 全亮 ⇒ 『必须外部回执』的判据形同虚设
        ⇒ 原则 1（判据必须在系统之外）被绕过，而门还会报全绿。

      ⇒★★ 修法: 取消自动补齐。每层只能由**它自己的证据**点亮。
        单调性检查也改成只检查"不能凭空跳级声明"——
        即：若声明了某层，必须同时声明它的直接上游（防止乱序输入），
        但**不因为声明下游而推断上游**。
    """

    mechanism: str
    #: 已点亮的层（每层各有自己的证据）
    reached: frozenset = field(default_factory=frozenset)
    #: ★ 负事件计数：本应调用但未调用的次数（Table 4 要求）
    not_called: int = 0
    #: 该机制从 present 起是否已进注册表（present 层的来源）
    exists: bool = True

    def __post_init__(self):
        # ★ 校验: 每层**要求的证据**必须齐（REQUIRES 表）。
        #   ★ 不是"直接上游"，也不是"整条前缀" ——
        #     produced_effect / feedback_closed 不要求任何其他层
        #     （它们可被独立观测到，见 REQUIRES 的注释）。
        reached = set(self.reached)
        for lay in reached:
            need = REQUIRES.get(lay, frozenset())
            missing = [x.value for x in need if x not in reached]
            if missing:
                raise LayerError(
                    "机制 %r 声明了层 %r 但缺其必要证据 %r"
                    % (self.mechanism, lay.value, missing))

    # ── 查询 ──
    def at_least(self, layer: Layer) -> bool:
        """是否已达某层。"""
        return layer in self.reached

    def depth(self) -> int:
        """已达的最深层级（0 = 未点亮）。"""
        if not self.reached:
            return 0
        return max(ORDER_INDEX[x] for x in self.reached)

    def is_dead(self) -> bool:
        """死机制判定：registered 但从未 called，或有负事件。

        ★★ 不把"从未调用"混进 stale（G3 判据之一，母巢 P2-3 同款）。
          母巢的 MechanismHealth 只有 call_count/is_healthy/last_called，
          把"从未调用"塞进 stale ⇒ 这正是论文 Table 4 判定为低效的做法。
        """
        if not self.at_least(Layer.REGISTERED):
            return False
        return not self.at_least(Layer.CALLED) or self.not_called > 0

    def to_dict(self) -> Dict:
        """序列化。★ 供 TermReport / 五元盘点快照使用（M6 要求）。"""
        return {
            "mechanism": self.mechanism,
            "reached": sorted(x.value for x in self.reached),
            "depth": self.depth(),
            "not_called": self.not_called,
            "dead": self.is_dead(),
        }


# ══════════════════════════════════════════════════════════
# 构造器 —— 唯一合法地"点亮"层的方式
# ══════════════════════════════════════════════════════════


def lit(*layers: Layer, exists: bool = True,
        not_called: int = 0) -> ActivityState:
    """构造一个 ActivityState，自动补齐上游层。

    ★ 为什么自动补齐: 六层是**单调**的（弱判据不得越级）。
      若要求调用方手动补齐，每个调用点都要重复写一遍 —— 迟早有人漏。

    ★★ 2026-10-05 两次更正（都由测试逼出来）:
      ① 切片原写作 ORDER[:i]（不含第 i 层）⇒ lit(REGISTERED) 漏掉自己
      ② 改成 ORDER[:i+1] 后发现**更严重的问题**: 自动补齐上游
         ⇒ 点亮 FEEDBACK_CLOSED 会连带点亮 succeeded
         ⇒ 『必须外部回执』的判据被绕过（详见 ActivityState 的 docstring）
      ⇒★ 最终形态: **只点亮传入的层**，不推断任何未点亮的层。
        若调用方只传 SUCCEEDED，构造器会因缺直接上游而 raise
        —— 这是有意的：它逼调用方说清"凭什么认为 succeeded 成立"。
    """
    reached: Set[Layer] = set(layers)
    if exists:
        reached.add(Layer.PRESENT)
    else:
        reached.discard(Layer.PRESENT)
    return ActivityState(mechanism="", reached=frozenset(reached),
                         not_called=not_called)


def stamp(state: ActivityState, kind: EventKind) -> ActivityState:
    """把一个 Γ 事件打到状态上，返回新状态（★ 不改原状态）。

    ★ 负事件（NOT_CALLED）不点亮任何层，只累加 not_called 计数。
    """
    if kind is EventKind.NOT_CALLED:
        return ActivityState(
            mechanism=state.mechanism,
            reached=state.reached,
            not_called=state.not_called + 1,
            exists=state.exists)
    lay = EVENT_TO_LAYER.get(kind)
    if lay is None:
        raise LayerError("未知事件类型: %r" % kind)
    # ★★ 只点亮这一层，不补齐任何其他层。
    #   必要证据由 ActivityState.__post_init__ 按 REQUIRES 表校验
    #   （而不是这里按层序校验 —— 六层是并列证据，不是有序链）。
    reached = set(state.reached)
    reached.add(lay)
    return ActivityState(mechanism=state.mechanism,
                         reached=frozenset(reached),
                         not_called=state.not_called,
                         exists=state.exists)


# ══════════════════════════════════════════════════════════
# 机制注册表 —— 六层的前两层的载体
# ══════════════════════════════════════════════════════════


class MechanismRegistry:
    """机制注册表。★ present/registered 两层的数据源。"""

    def __init__(self):
        self._states: Dict[str, ActivityState] = {}

    def register(self, name: str) -> ActivityState:
        """登记机制 ⇒ 点亮 present + registered。"""
        st = ActivityState(mechanism=name,
                           reached=frozenset({Layer.PRESENT,
                                              Layer.REGISTERED}))
        self._states[name] = st
        return st

    def apply(self, name: str, kind: EventKind) -> ActivityState:
        """把事件打到已登记机制上。"""
        st = self._states.get(name)
        if st is None:
            raise LayerError(
                "机制 %r 未登记 ⇒ 不能记录 %r 事件（present 层未过）"
                % (name, kind.value))
        new = stamp(st, kind)
        self._states[name] = new
        return new

    def get(self, name: str) -> ActivityState:
        st = self._states.get(name)
        if st is None:
            raise LayerError("机制 %r 未登记" % name)
        return st

    def dead(self) -> List[str]:
        """死机制名单。★ 与"stale"（曾经活跃后失效）**分开**。"""
        return sorted(n for n, s in self._states.items() if s.is_dead())

    def stale(self) -> List[str]:
        """曾活跃后失效：已达 CALLED 但未达 SUCCEEDED。"""
        return sorted(
            n for n, s in self._states.items()
            if s.at_least(Layer.CALLED) and not s.at_least(Layer.SUCCEEDED))

    def all_states(self) -> List[ActivityState]:
        return [self._states[k] for k in sorted(self._states)]

    def snapshot(self) -> List[Dict]:
        """全量快照。★ 供 TermReport 落盘（M6 的 snapshot 要求）。"""
        return [s.to_dict() for s in self.all_states()]


if __name__ == "__main__":
    # 自检：四场景
    reg = MechanismRegistry()
    a = reg.register("mech_a")
    print("登记后: depth=%d layers=%s" % (a.depth(), sorted(a.to_dict()["reached"])))

    reg.apply("mech_a", EventKind.CALL)
    reg.apply("mech_a", EventKind.RECEIPT)
    s = reg.get("mech_a")
    print("调用+回执后: depth=%d layers=%s dead=%s"
          % (s.depth(), sorted(s.to_dict()["reached"]), s.is_dead()))

    reg.register("mech_b")
    reg.apply("mech_b", EventKind.NOT_CALLED)
    reg.apply("mech_b", EventKind.NOT_CALLED)
    b = reg.get("mech_b")
    print("负事件×2后: not_called=%d dead=%s" % (b.not_called, b.is_dead()))

    print("\ndead 名单: %s" % reg.dead())
    print("stale 名单: %s" % reg.stale())
    print("★ 两者不重叠: mech_b 是『从未调用』(dead)，mech_a 是『调用成功』(非 dead)")

    # 越级必须 raise
    try:
        ActivityState(mechanism="x", reached=frozenset({Layer.SUCCEEDED}))
        print("★ 越级未被拦 —— 有 bug")
    except LayerError as e:
        print("\n✓ 越级被拦: %s" % e)