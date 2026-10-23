"""接线层 —— 把因果链 Γ 的事件喂给六层活性模型。

★★★ 这个模块为什么存在（R16 的诚实边界①）
  R15 写了 activity.py（六层的层与事件），R16 写了 causal_chain.py（链的存储），
  但**两者没有接起来** —— 没有任何代码把 chain_record 里的事件喂给
  MechanismRegistry.apply()
  ⇒⇒ 结果: 六层定义了却没有任何真实数据流过，
    gate.py G3 检的只是「字段名齐备」，不是「真在点亮」
  ⇒⇒ 本模块就是那条接线。

定位声明（DWC-MEM · 记忆底座 · 判据 G1 定位门）
  ★ 机制活性状态 = "进化产物是否真被用"的记忆 ⇒ 属记忆底座。
  ★ 本模块只做**投影**（chain 的事件 → 活性层），不产生事件、不驱动。
  ★ 判据 S3/C2 依然成立: 本模块没有 run_next / step / trigger。

映射的依据（不是猜的）
  2608.24876 §5.1.2 给了六层的点亮来源:
    present         ← 文件 / 注册表
    registered      ← 登记表
    called          ← Γ 中出现调用事件
    succeeded       ← 外部回执匹配
    produced_effect ← 下游可观测产物
    feedback_closed ← 回到判分器
  而 DWC 的五环（decision→turn→trace→experience→change）与六层的对应:
    decision    → present（机制被登记时的那一环）
    turn        → registered
    trace       → called        + （若有匹配回执）succeeded
    experience  → produced_effect
    change      → feedback_closed（回到判分器的那一环）

  ★★ succeeded 的判据不是"我没抛异常"，而是 **success_source**:
    ACTOR_DESIGN 的 Trace 有 success_source ∈ {judge_verdict, tool_receipt}
    —— 只有这两个值才算"外部回执匹配"（原则 1: 判据必须在系统之外）
    ⇒ NOT_EVALUATED 不算 succeeded（success=None 也不算）

  ★★ 负事件（Table 4 的硬要求）: expected 记了却没 observed
    ⇒ 那就是"本应调用但未调用" ⇒ 记 NOT_CALLED
    这让 2608.24876 Table 4 里"仅结果证据 F1=0.0 低于 33.3% 基线"的坑
    在 DWC 侧被堵住。
"""
from __future__ import annotations

from typing import Any

from dwc.foundation.activity import (
    ActivityState,
    EventKind,
    Layer,
    MechanismRegistry,
)
from dwc.foundation.causal_chain import CausalChainStore

# ══════════════════════════════════════════════════════════
# 五环 → 六层的映射（★ 表驱动，不是 if 链）
# ══════════════════════════════════════════════════════════

#: 每个 stage 点亮哪些层。★ 用元组而非累加 ⇒ 声明式、可测、可读。
#: ★★★ 2026-10-05 测试抓到的顺序陷阱:
#:   experience → PRODUCED_EFFECT，而 PRODUCED_EFFECT 在层序里**排在
#:   SUCCEEDED 之后** ⇒ 而 activity 的单调性会自动补齐上游
#:   ⇒⇒ 于是"走完五环"就等于"必然点亮 succeeded"，
#:     **完全绕过了『必须外部回执』的判据**（原则 1 被绕过）
#:   ⇒★★ 修法: experience 环不能直接点 PRODUCED_EFFECT。
#:     下游可观测产物的判据必须是"下游真的被观测到"，
#:     而 experience 环是"我学到了什么"，不是"下游看到了什么"。
#:     ⇒ 正确做法: PRODUCED_EFFECT 只能由**显式的 effect 事件**点亮，
#:       不由五环自动点亮（见 record(..., effect_observed=True)）
STAGE_TO_LAYERS: dict[str, tuple] = {
    "decision":   (Layer.PRESENT,),
    "turn":       (Layer.REGISTERED,),
    "trace":      (Layer.CALLED,),          # succeeded 另由回执决定
    "experience": (),                        # ★ 见上方说明：不自动点亮
    "change":     (Layer.FEEDBACK_CLOSED,),
}

#: 允许算"外部回执"的 success_source（原则 1: 判据必须在系统之外）
RECEIPT_SOURCES = frozenset({"judge_verdict", "tool_receipt"})


class WiringError(Exception):
    """接线违反契约。★ 承重代码不许吞异常（判据 E2/E3）。"""


# ══════════════════════════════════════════════════════════
# 接线层
# ══════════════════════════════════════════════════════════


class ActivityWiring:
    """把 causal_chain 的事件投影成六层活性。

    ★ 用法: 器官写完每一环后调 record(...) —— 它内部 append 到链，
      同时更新活性状态。⇒ 链是唯一真值源（原则 3），活性只是它的投影。
    ★ 任何器官都**不该**直接碰 MechanismRegistry ——
      那样活性就会与链脱节，变成第二个真值源。
    """

    def __init__(self, store: CausalChainStore | None = None):
        self.store = store or CausalChainStore()
        self.registry = MechanismRegistry()
        # ★ 机制名 → chain_id 的映射（一个机制可能跨多条链）
        self._mechanism_chains: dict[str, list[str]] = {}
        self._known: set = set()

    # ══════════════════════════════════════════════
    # 登记机制（present + registered 两层的来源）
    # ══════════════════════════════════════════════
    def register(self, mechanism: str) -> ActivityState:
        """登记机制。★ 对应六层的 present + registered。

        ★★ 注意: 这里**不写链**。因为 present/registered 是关于"机制存在"
          的事实，不是关于"这次决策"的事件。
          ⇒ 写进链会把"机制清单"和"决策历史"混在一起（判据 S4 的粒度纪律）。
        """
        if mechanism in self._known:
            # ★ 重复登记：幂等（不重置进度），因为 progress 比事件更重要
            return self.registry.get(mechanism)
        st = self.registry.register(mechanism)
        self._known.add(mechanism)
        return st

    # ══════════════════════════════════════════════
    # 记录一环（同时更新链与活性）
    # ══════════════════════════════════════════════
    def record(self, mechanism: str, chain_id: str, stage: str,
               ref_id: str | None = None,
               payload: dict[str, Any] | None = None,
               upstream_id: str | None = None,
               recorded_at: str | None = None,
               not_called: bool = False,
               effect_observed: bool = False) -> dict[str, Any]:
        """记录一环：写链 + 点亮活性层。

        ★★ not_called=True 表示"本应调用但未调用"（负事件）:
          它**仍然写链**（缺失也是信息，Table 4 要求），
          但**不点亮** CALLED，只记 not_called 计数。

        ★★★ effect_observed=True 才点亮 PRODUCED_EFFECT（下游可观测产物）。
          ⇒ 它**不由五环自动点亮** —— 因为"我学到了什么"（experience）
            不等于"下游看到了什么"（effect）。
          ⇒ 2608.24876 的映射是"下游可观测产物"，判据是**被观测**，
            不是被记录。
        """
        payload = payload or {}
        if stage not in STAGE_TO_LAYERS:
            raise WiringError(
                "stage=%r 不在映射表 %r 内"
                % (stage, sorted(STAGE_TO_LAYERS)))

        # ① 写链（唯一真值源）。负事件也写 —— 缺失必须留痕。
        rec = self.store.append(
            chain_id, stage, ref_id, payload,
            upstream_id=upstream_id, recorded_at=recorded_at)

        # ② 机制必须是已登记的（present 层是入口守卫）
        if mechanism not in self._known:
            raise WiringError(
                "机制 %r 未登记 ⇒ 不能记录事件（present 层未过）" % mechanism)
        self._mechanism_chains.setdefault(mechanism, [])
        if chain_id not in self._mechanism_chains[mechanism]:
            self._mechanism_chains[mechanism].append(chain_id)

        # ③ 投影到活性层
        if not_called:
            self.registry.apply(mechanism, EventKind.NOT_CALLED)
        else:
            for lay in STAGE_TO_LAYERS[stage]:
                # ★★ PRESENT 没有对应事件（它由 register() 直接点亮）。
                #   ★ 自检抓到过这个 KeyError: 我在注释里写了这件事，
                #     却在循环里直接查表 ⇒ 忘了跳过它。
                #   ⇒ 正确做法: PRESENT 由"机制已登记"保证，
                #     decision 环只是**再次确认**它，不重复点亮。
                kind = _LAYER_TO_EVENT.get(lay)
                if kind is None:
                    continue          # ★ PRESENT 走这里（已由 register 点亮）
                self.registry.apply(mechanism, kind)

        # ④ trace 环若带匹配回执 ⇒ 额外点亮 succeeded
        if stage == "trace" and not not_called:
            if _has_matching_receipt(payload):
                self.registry.apply(mechanism, EventKind.RECEIPT)

        # ⑤ 下游可观测产物 ⇒ 必须显式声明被观测到
        if effect_observed:
            self.registry.apply(mechanism, EventKind.EFFECT)

        return rec

    # ══════════════════════════════════════════════
    # 查询
    # ══════════════════════════════════════════════
    def state(self, mechanism: str) -> ActivityState:
        return self.registry.get(mechanism)

    def chains_of(self, mechanism: str) -> list[str]:
        """某机制出现在哪些链里。★ 用于"这机制到底有没有被用"的追查。"""
        return list(self._mechanism_chains.get(mechanism, []))

    def dead(self) -> list[str]:
        return self.registry.dead()

    def stale(self) -> list[str]:
        return self.registry.stale()

    def snapshot(self) -> list[dict[str, Any]]:
        """全量活性快照 + 链对照。★ 供 TermReport（M6 要求可事后审计）。"""
        out = []
        for st in self.registry.all_states():
            row = st.to_dict()
            row["chains"] = self.chains_of(st.mechanism)
            out.append(row)
        return out

    def verify(self, chain_id: str) -> dict[str, Any]:
        """核对链连续性（转发到存储层）。"""
        return self.store.verify_continuity(chain_id)

    def export(self, chain_id: str | None = None):
        return self.store.export(chain_id)


# ══════════════════════════════════════════════════════════
# 辅助
# ══════════════════════════════════════════════════════════

#: 层 → 事件类型（点亮的反向映射）
_LAYER_TO_EVENT = {
    Layer.REGISTERED: EventKind.REGISTER,
    Layer.CALLED: EventKind.CALL,
    Layer.SUCCEEDED: EventKind.RECEIPT,
    Layer.PRODUCED_EFFECT: EventKind.EFFECT,
    Layer.FEEDBACK_CLOSED: EventKind.FEEDBACK,
    # ★ Layer.PRESENT 没有对应事件 —— 它由 register() 直接点亮
    #   （present 的来源是"文件/注册表存在"，不是某个 Γ 事件）
}


def _has_matching_receipt(payload: dict[str, Any]) -> bool:
    """trace 的 payload 里是否有**匹配的外部回执**。

    ★★★ 这就是六层里 "succeeded ← 外部回执匹配" 的判据形式:
      只认 success_source ∈ {judge_verdict, tool_receipt}（原则 1）
      且 success 必须是 True —— success=None（未评价）不算
    ⇒ NOT_EVALUATED / self_reported / 任何自报值都不算
    ⇒ 这堵住了 2607.12790 实测的"评估器塌缩成 always-pass"
    """
    src = payload.get("success_source")
    if src not in RECEIPT_SOURCES:
        return False
    success = payload.get("success")
    # ★ success 必须是显式 True；None（未评价）不算成功
    return success is True


# ══════════════════════════════════════════════════════════
# 自检
# ══════════════════════════════════════════════════════════

def _self_test() -> None:
    w = ActivityWiring()
    w.register("scorer")
    w.register("never_used")

    # 完整一条链: decision → turn → trace(带回执) → experience → change
    w.record("scorer", "CH1", "decision", "D1",
             {"action": "grade"}, recorded_at="t0")
    w.record("scorer", "CH1", "turn", "T1", {"turn": 1},
             upstream_id="D1", recorded_at="t1")
    w.record("scorer", "CH1", "trace", "TR1",
             {"success": True, "success_source": "tool_receipt"},
             upstream_id="T1", recorded_at="t2")
    w.record("scorer", "CH1", "experience", "E1", {"n_obs": 3},
             upstream_id="TR1", recorded_at="t3")
    w.record("scorer", "CH1", "change", "C1", {"files": 1},
             upstream_id="E1", recorded_at="t4")

    s = w.state("scorer")
    print("scorer 六层: depth=%d layers=%s"
          % (s.depth(), sorted(s.to_dict()["reached"])))
    print("★ 六层全亮:", s.depth() == 5)
    print("scorer 链: %s" % w.chains_of("scorer"))

    # 负事件: 登记了但从未调用
    w.record("never_used", "CH2", "decision", "D2", {}, recorded_at="t0")
    w.record("never_used", "CH2", "turn", "T2", {},
             upstream_id="D2", recorded_at="t1")
    n = w.state("never_used")
    print("\nnever_used: depth=%d not_called=%d dead=%s"
          % (n.depth(), n.not_called, n.is_dead()))
    print("★ dead 名单: %s" % w.dead())
    print("★ stale 名单: %s" % w.stale())

    # ★ 关键验证: 自报成功不算 succeeded
    w2 = ActivityWiring()
    w2.register("liar")
    w2.record("liar", "C3", "decision", "D", {}, recorded_at="t0")
    w2.record("liar", "C3", "trace", "TR",
              {"success": True, "success_source": "self_reported"},
              upstream_id="D", recorded_at="t1")
    st = w2.state("liar")
    print("\n自报成功（success_source=self_reported）:")
    print("  layers=%s" % sorted(st.to_dict()["reached"]))
    print("  ★ 未点亮 succeeded:", not st.at_least(Layer.SUCCEEDED))

    # ★ success=None（未评价）也不算
    w2.record("liar", "C3", "trace", "TR2",
              {"success": None, "success_source": "tool_receipt"},
              upstream_id="D", recorded_at="t2")
    st2 = w2.state("liar")
    print("  success=None 时仍未点亮 succeeded:",
          not st2.at_least(Layer.SUCCEEDED))

    # 真实回执则点亮
    w2.record("liar", "C3", "trace", "TR3",
              {"success": True, "success_source": "judge_verdict"},
              upstream_id="D", recorded_at="t3")
    st3 = w2.state("liar")
    print("  judge_verdict + success=True ⇒ 已点亮 succeeded:",
          st3.at_least(Layer.SUCCEEDED))

    # ★ 负事件走接线
    w3 = ActivityWiring()
    w3.register("planned")
    w3.record("planned", "C4", "decision", "D", {}, recorded_at="t0")
    w3.record("planned", "C4", "trace", "TR", {"expected": True},
              upstream_id="D", not_called=True, recorded_at="t1")
    p = w3.state("planned")
    print("\n负事件接线: layers=%s not_called=%d"
          % (sorted(p.to_dict()["reached"]), p.not_called))
    print("  ★ 未点亮 called:", not p.at_least(Layer.CALLED))
    print("  ★ 但链里留了痕（缺失也是信息）:",
          len(w3.store.trace_back("C4")) == 2)


if __name__ == "__main__":
    _self_test()