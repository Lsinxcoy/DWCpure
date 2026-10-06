# -*- coding: utf-8 -*-
"""DWC actor —— 行动者（器官 3/7）。唯一产生痕迹的器官。

★★★ 这个器官现在为什么最要紧
  R25 接上 judge 后实测: pass_rate=1.00，但那条观测是 run_term **自造**的
  （用 golden 关键词拼，必然通过）⇒⇒ 而"用 golden 制造通过"正是塌缩型评分器
  ⇒⇒ 所以唯一能救的就是**真的执行任务产出观测**的那个器官
  ⇒⇒⇒ actor 缺位时，judge 的观测契约至今没有任何真实实现验证过

定位声明（DWC-MEM · 记忆底座 · 判据 G1 定位门）
  ★ actor 属记忆底座 —— 它唯一职责是**产生痕迹**（原则 3 的输入端）
  ★ 它**不产生记忆**，只把观察交出去（memory 由管道消费）
  ★ 原则 6: 器官之间只经接口，不碰对方的私有态

★★★ 四条纪律（ACTOR_DESIGN 逐条核过，不是自己想的）
  ① §3.3 · actor 的 success **不许自己判**
     三来源（按优先级）:
       ① judge 的 verdict（密封任务集，进程外）
       ② 工具回执（执行器的真实返回）
       ③ ★ 若两者都没有 ⇒ 记 NOT_EVALUATED，**不许记成功**
  ② §3.4 · prediction / decision / outcome **三分离**
     ★ 依据 2609.08183 §3.4: "the tier actually served **as the
       training label**" 是错的 —— outcome 不许进课程
  ③ §4.2 · 两类动作必须分开
     甲 任务动作（做任务，来自世界模型 legal_actions）← 主职
     乙 维护动作（dream/learn/maintain/remember）
     ★ evolve **不进 actor**（进化由 evolver 器官负责）
  ④ 接口 · actor **不得自己造任务**（任务源唯一 = 世界模型）
"""
from __future__ import annotations

#: ★★★ TRUTH_SOURCE（判据 G2: 含判定能力的模块必须声明）
#: ★★ 本模块**不自判成功** ⇒ 它没有自己的真值源
#: ★★ 它产出 observed（证据），而证据的判读在 judge
#: ★★ §3.3② 的「工具回执」是唯一可能的外部来源 —— 而那来自执行器，
#:    执行器只是通道，不是判据的制定者
TRUTH_SOURCE = {
    "本模块不自判": "success 只来自 judge verdict 或工具回执（ACTOR_DESIGN 3.3）",
    "本模块的产出": "observed（证据），不是判分结果",
    "判读位置": "dwc.organs.judge.Judge（真值源 config/anchors/dev.json）",
    "★ 若无外部回执": "记 NOT_EVALUATED —— 不许记成功",
}

#: ★★ 三层粒度（ACTOR_DESIGN §3.1 · 2609.08183 §3.1 原文）
GRANULARITY = ("trajectory", "user_turn", "subscene")

#: ★★ 维护动作（ACTOR_DESIGN §4.2 乙类）。★ evolve 故意不在此列
MAINTENANCE_ACTIONS = ("dream", "learn", "maintain", "remember")

#: ★★ §3.3 第③条: 两者都没有时的唯一合法值
NOT_EVALUATED = "NOT_EVALUATED"

#: ★ 合法 success_source（§3.3 + Trace 结构）
SUCCESS_SOURCES = ("judge_verdict", "tool_receipt", NOT_EVALUATED)

#: ★★ 合法 outcome（ACTOR_DESIGN §3.2: 「outcome: str # ★ 枚举,
#:   不是自由字符串」）—— 自由字符串会让"结果"变成不可分析的自由文本
OUTCOMES = ("returned", "raised", None)

import ast
import io
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


class ActorError(Exception):
    """违反 actor 契约。★ 承重代码不许吞异常（判据 E2/E3）。"""


# ══════════════════════════════════════════════════════════
# Trace（痕迹）
# ══════════════════════════════════════════════════════════


@dataclass
class Trace:
    """★ 结构化痕迹 Γ（ACTOR_DESIGN §3.2 的 Trace 结构）。

    ★★★ 关键: `success` 的类型是 Optional[bool]，None = 未评价
      ⇒ 规则: None 不许当 False 也不许当 True（§4.5）
      ⇒ 而 Actor **不填**它 —— 它由外部回执或 judge 填（§3.3）
    """
    #: ── 三分离（§3.4）──
    prediction: Optional[Dict[str, Any]] = None   # 世界模型的预测
    decision: Dict[str, Any] = field(default_factory=dict)
    outcome: Optional[str] = None                 # ★ 枚举，不是自由字符串

    #: ── 执行 ──
    action: str = ""
    action_params: Dict[str, Any] = field(default_factory=dict)
    state_before: Dict[str, Any] = field(default_factory=dict)
    state_after: Dict[str, Any] = field(default_factory=dict)
    #: ★ expected: 修"失败是非事件"（§3.2）—— 记下本该发生什么
    expected: Dict[str, Any] = field(default_factory=dict)
    observed: Dict[str, Any] = field(default_factory=dict)

    #: ── 证据（ARSI 缺）──
    evidence: Dict[str, Any] = field(default_factory=dict)
    success_source: str = NOT_EVALUATED
    success: Optional[bool] = None

    #: ── 失败定位（Recuris 判据）──
    #: {c: 终止级原因, q: 因果角色, m: 抽象机制名}
    failure_signature: Optional[Dict[str, str]] = None

    #: ── 三层粒度（§3.1）──
    granularity: str = "user_turn"
    trajectory_id: Optional[str] = None
    turn_index: int = 0

    generation: int = 0
    timestamp: float = 0.0

    def __post_init__(self):
        if self.success_source not in SUCCESS_SOURCES:
            raise ActorError(
                "success_source=%r 不在 %r 内"
                % (self.success_source, list(SUCCESS_SOURCES)))
        if self.granularity not in GRANULARITY:
            raise ActorError(
                "granularity=%r 不在 %r 内（ACTOR_DESIGN §3.1）"
                % (self.granularity, list(GRANULARITY)))
        #★★★ R26 修正（测试抓到）: §3.2 原文写着
        #   「outcome: str # ★ 枚举, 不是自由字符串」
        #   ⇒ 而我在 docstring 里抄了这句话，__post_init__ 里却**没校验**
        #   ⇒⇒ ⇒★ 同一个毛病: 声明了纪律但代码没强制（和 R19 那次同族）
        # ⇒ 所以现在补上: 自由字符串一律 raise
        if self.outcome not in OUTCOMES:
            raise ActorError(
                "outcome=%r 不在 %r 内（ACTOR_DESIGN §3.2: "
                "outcome 是枚举，不是自由字符串）"
                % (self.outcome, [x for x in OUTCOMES if x]))
        # ★★ 三分离的纪律: decision 必须写 source（预测/LLM/启发式）
        if self.decision and "source" not in self.decision:
            raise ActorError(
                "decision 缺 source 字段（§3.4: "
                "预测/决策必须可独立分析）")

    # ══════════════════════════════════════════════
    def set_external_verdict(self, success: Optional[bool],
                             source: str) -> "Trace":
        """★ 由**外部**填 success（§3.3: actor 不许自己判）。

        ★★ 这是唯一能设置 success 的路径 —— 所以"actor 自判成功"
          在代码层面就不可能发生。
        """
        if source not in SUCCESS_SOURCES or source == NOT_EVALUATED:
            raise ActorError(
                "只有 judge_verdict / tool_receipt 能定 success"
                "（§3.3），%r 不行" % source)
        if success is not None and not isinstance(success, bool):
            raise ActorError("success 必须是 bool 或 None（§4.5）")
        self.success = success
        self.success_source = source
        return self

    def validate(self) -> "Trace":
        """★ 显式校验（构造后、落库前各调一次）。

        ★★★★ R26 实测修正: __post_init__ 只在**构造那一刻**跑
          ⇒ 而 act() 内部是事后设 tr.outcome（Trace 不是 frozen）
          ⇒⇒ ★★ 所以 __post_init__ 拦不住那些赋值
          ⇒⇒ ⇒★ 纪律只在构造时生效 = 纪律没有生效
          ⇒★ 正确做法: 把校验提成可复用方法，act() 在设完 outcome 后调它
        """
        if self.outcome not in OUTCOMES:
            raise ActorError(
                "outcome=%r 不在 %r 内（ACTOR_DESIGN §3.2: "
                "outcome 是枚举，不是自由字符串）"
                % (self.outcome, [x for x in OUTCOMES if x]))
        if self.success_source not in SUCCESS_SOURCES:
            raise ActorError(
                "success_source=%r 不在 %r 内"
                % (self.success_source, list(SUCCESS_SOURCES)))
        if self.granularity not in GRANULARITY:
            raise ActorError(
                "granularity=%r 不在 %r 内（ACTOR_DESIGN §3.1）"
                % (self.granularity, list(GRANULARITY)))
        return self

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


# ══════════════════════════════════════════════════════════
# 执行器（工具回执的来源）
# ══════════════════════════════════════════════════════════


@dataclass
class Receipt:
    """★ 工具回执（§3.3 第②来源）。

    ★★ Verified Coupling（2608.24876 §2.2）: 完成的条件是
      「写入返回**可验证的回执**」而非"我调用了写入函数"
      ⇒ 所以 Receipt 必须能被**读回校验**（verified 字段）
    """
    ok: bool
    detail: Dict[str, Any] = field(default_factory=dict)
    #: ★ 读回校验的证据（真回执 vs 假返回）
    verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


# ══════════════════════════════════════════════════════════
# Actor
# ══════════════════════════════════════════════════════════


class Actor:
    """★ 行动者。★ 只产生痕迹，不判成功、不造任务、不产生记忆。"""

    def __init__(self, trajectory_id: Optional[str] = None):
        self.trajectory_id = trajectory_id
        self.traces: List[Trace] = []
        self._turn = 0

    # ══════════════════════════════════════════════
    # ★ 任务源：actor 不得自己造任务（接口契约）
    # ══════════════════════════════════════════════
    def legal_actions(self, task_source: Any) -> List[Dict[str, Any]]:
        """★ 取本轮可做的任务（任务源唯一 = 世界模型）。

        ★★ 纪律（ACTOR_DESIGN 的接口契约原文）:
          "actor 不得自己造任务（任务源唯一）"
          ⇒★ 所以这个方法**转发**给 task_source，不做任何筛选或补充
          ⇒⇒ 若 task_source 没实现 legal_actions ⇒ raise，不兜底
        """
        fn = getattr(task_source, "legal_actions", None)
        if not callable(fn):
            raise ActorError(
                "任务源没有 legal_actions() —— ★ actor 不得自己造任务"
                "（ACTOR_DESIGN 接口契约）")
        return list(fn())

    # ══════════════════════════════════════════════
    # ★ 执行：observe → decide → act → record
    # ══════════════════════════════════════════════
    def act(self, task: Dict[str, Any],
            executor: Callable[[Dict[str, Any]], Receipt],
            expected: Optional[Dict[str, Any]] = None,
            prediction: Optional[Dict[str, Any]] = None,
            decision: Optional[Dict[str, Any]] = None,
            trace_hook: Optional[Callable[[Trace], None]] = None,
            ) -> Trace:
        """★ 执行一个任务，返回结构化痕迹。

        ★★★ 关键: 本方法**不判成功**（§3.3）
          ⇒ 若 executor 给了"可验证的回执"（verified=True），
            那就是工具回执来源（§3.3②）—— 不是 actor 自判
          ⇒⇒ 而 verified=False 的回执**不算**回执 ⇒ 落 NOT_EVALUATED
        """
        if "task_id" not in task:
            raise ActorError("任务缺 task_id")
        # ★ expected: 调用前登记（修"失败是非事件"，§3.2）
        exp = expected or task.get("expected") or {}
        dec = decision or {"source": "heuristic",
                           "why": "未提供决策 ⇒ 记启发式（不编造）"}

        tr = Trace(
            prediction=prediction,
            decision=dec,
            outcome=None,
            action=str(task.get("kind", "unknown")),
            action_params={k: v for k, v in task.items()
                           if k not in ("expected",)},
            expected=exp,
            granularity="user_turn",
            trajectory_id=self.trajectory_id,
            turn_index=self._turn,
            timestamp=time.time(),
        )

        # ── 执行（★ 异常不吞：判据 E3）──
        try:
            rc = executor(task)
        except Exception as exc:                       # noqa: BLE001
            # ★ 执行器抛异常 ⇒ 记成失败痕迹（含失败定位），**不是**"没发生"
            tr.outcome = "raised"
            tr.observed = {"exception": type(exc).__name__,
                           "message": str(exc)[:200],
                           "traceback": traceback.format_exc()[-400:]}
            tr.failure_signature = self._signature(exc, task)
            tr.validate()          # ★ 事后赋值也要过纪律（R26）
            self._push(tr, trace_hook)
            return tr
        if not isinstance(rc, Receipt):
            raise ActorError(
                "executor 必须返回 Receipt（§3.3② 工具回执），实为 %r"
                % type(rc).__name__)
        tr.observed = dict(rc.detail)
        tr.evidence = {"receipt": rc.to_dict()}
        tr.outcome = "returned"
        tr.validate()              # ★ 事后赋值也要过纪律（R26）

        # ★★★ 工具回执的唯一门槛: **verified=True**（读回校验过）
        #   ⇒ 而 verified=False ⇒ 只是"调用返回了"⇒ 落 NOT_EVALUATED
        if rc.ok and rc.verified:
            tr.set_external_verdict(True, "tool_receipt")
        else:
            # ★ 不判失败 —— 未验证的返回既不是成功也不是失败（§4.5）
            tr.success = None
            tr.success_source = NOT_EVALUATED
            if not rc.ok:
                tr.failure_signature = self._signature_from_receipt(rc,
                                                                    task)
        self._push(tr, trace_hook)
        return tr

    def _push(self, tr: Trace,
              hook: Optional[Callable[[Trace], None]]) -> None:
        """★ 记录痕迹。★ hook 是"trace_before_persist"的实现点。

        ★★ 而 hook 抛异常 ⇒ 痕迹**不进** list（判据 S5: 注入失败看链是否断裂）
        ⇒ 这是"痕迹必须在落库前拿到"的落地形式
        """
        tr.validate()              # ★ 落库前最后一道（R26）
        if hook:
            hook(tr)
        self.traces.append(tr)
        self._turn += 1

    # ══════════════════════════════════════════════
    # 失败定位（Recuris 判据：没有失败定位的痕迹不算合格痕迹）
    # ══════════════════════════════════════════════
    @staticmethod
    def _signature_from_receipt(rc: Receipt,
                                task: Dict[str, Any]) -> Dict[str, str]:
        """★★ R27 修正（闭环实测暴露）: q 必须是**被改对象**而非 task_id。

        ★★★ 实测: 闭环跑起来后，evolver 的规则键对不上
          · actor 产出 q = 'code_fix_003'（任务编号）
          · evolver 规则要 q = 'factorial'（函数名）
          ⇒⇒ ★★ 两者语义不一致 ⇒ 提案匹配不上 ⇒ 闭环断在诊断这一环

        ★★ 依据（EVOLUTION_CORE_DESIGN §2.1 两篇原文）:
          c_i : 终止级 verifier 原因
          q_i : 相关 agent 行为的**因果状态** —— 即"哪个东西坏了"
          m_i : trace 暴露出的**抽象 agent 机制** —— 即"哪类能力"
        ⇒⇒ ⇒★ 所以 q = 被改对象（task 的 fn 字段），不是任务编号
          ⇒★ 而 task_id 另有其位（Trace 自身有 task 上下文）
        """
        c = str((rc.detail or {}).get("error_code", "executor_rejected"))
        fn = str(task.get("fn") or task.get("target") or "")
        # ★★★ R30: **fn 是定位维度，单独一个字段**
        #   原文三元组 (c,q,m) 是**聚类**语义，不含"要改哪"；
        #   而查 RULES 需要 (c, q, fn)
        #   ⇒⇒ ★ R27 我把 fn 塞进 q 位置 ⇒ 「定位碰巧对、语义错」
        #   ⇒⇒ ★ 而 R27 那条测试 test_failure_signature_q_is_the_changed_object
        #     **锁住了那个错误语义** ⇒ 两侧都改对后它反而成了障碍
        #
        # ★★★★ 更要紧的（结构性，待裁决）:
        #   本签名的 c 来自**回执 error_code**（执行层失败）
        #   而 judge 的 c 来自**实测差异**（verifier 层）
        #   ⇒⇒ ⇒★ 原文 φ(r_i) 的 r_i 是 **verifier 结果** ⇒ evolver 只该收后者
        #     ⇒⇒ ⇒★★ 于是 actor 这条签名**不是 evolver 的输入**，
        #       它属于执行层 trace（诊断执行问题）
        #     ⇒⇒ ⇒★★★ 而 R27 的 test_proposal_matches_signature_from_trace
        #       测的正是 actor→evolver ⇒ **方向错了**（本轮已改）
        return {"c": c,
                # ★ q 仍是 actor 能给的那份（执行层视角的因果状态）
                "q": str(task.get("fn") or task.get("target")
                         or "unknown_object"),
                # ★ 定位维度（非三元组成员，但查询要用）
                "fn": fn,
                "m": str(task.get("kind", "unknown_action")),
                # ★★ 显式标注来源，避免与 verifier 签名混用
                "sig_layer": "executor"}

    @staticmethod
    def _signature(exc: BaseException,
                   task: Dict[str, Any]) -> Dict[str, str]:
        """★ 从异常提取 (c, q, m)。

        ★ c = 终止级原因（异常类型）
        ★ q = 因果角色（这是谁的责任 —— 这里是任务本身）
        ★ m = 抽象机制名（任务种类）
        ⇒ 格式与 D5 一致（ACTOR_DESIGN §3.3 的硬要求）
        """
        # ★★ R27: 同上 —— q 是被改对象（见 _signature_from_receipt 的依据）
        return {"c": type(exc).__name__,
                "q": str(task.get("fn") or task.get("target")
                         or "unknown_object"),
                "m": str(task.get("kind", "unknown_action"))}

    # ══════════════════════════════════════════════
    # 查询
    # ══════════════════════════════════════════════
    def not_evaluated(self) -> List[Trace]:
        """★ 未评价的痕迹（§3.3③ 的可审计出口）。"""
        return [t for t in self.traces if t.success is None]

    def stats(self) -> Dict[str, Any]:
        n = len(self.traces)
        return {
            "n_traces": n,
            "passed": sum(1 for t in self.traces if t.success is True),
            "failed": sum(1 for t in self.traces if t.success is False),
            "not_evaluated": len(self.not_evaluated()),
            "★": ("三数分开报 —— None 不许当 False 也不许当 True"
                  "（§4.5）"),
        }


# ══════════════════════════════════════════════════════════
# 确定性执行器（第一批任务用）
# ══════════════════════════════════════════════════════════


class PureFunctionExecutor:
    """★ 执行 dev 集里那 6 条 behavior 任务（都是纯函数）。

    ★★★ 为什么第一版不做 LLM:
      ACTOR_TASK_SOURCE §一实测: ARSI 的 actor 只做记忆维护、不做任务
      ⇒⇒ 而"让 LLM 写代码再验证"是 ARSI 的路子，它的可验证性依赖 LLM
      ⇒⇒ ★★ DWC 第一版先用**确定性执行器**:
        · 那 6 条判据都是 `fn(args)==expected` 的纯函数断言
        · 直接执行即可得到**可验证的回执**（read-back verified）
        · ⇒ 这样 judge 的观测契约立刻有真实实现，不再是自造的
      ⇒ ⇒ LLM 版留到 actor 稳了之后（诚实边界④）

    ★★★ 回执的 verified 从哪来（★ 不能自说自话）:
      执行完**再读回函数值**，与第一次取的值一致才 verified=True
      ⇒ 那正好治母巢 P0-3（MemoryToolManagement 返回 ok:True 但零副作用）
    """

    #: ★★ 沙箱白名单：只允许这几个函数名（防任意执行）
    ALLOWED = ("sum_first_n", "average", "factorial", "fibonacci",
               "is_palindrome", "reverse_string")

    #: ★ 基准实现（正确版本）。★ agent 的产出要与它对拍
    REFERENCE = {
        "sum_first_n": "def sum_first_n(n):\n    return sum(range(1, n + 1))",
        "average": ("def average(xs):\n"
                    "    return (sum(xs) / len(xs)) if xs else 0.0"),
        "factorial": ("def factorial(n):\n"
                      "    if n <= 1:\n        return 1\n"
                      "    return n * factorial(n - 1)"),
        "fibonacci": ("def fibonacci(n):\n"
                      "    a, b = 0, 1\n"
                      "    for _ in range(n):\n"
                      "        a, b = b, a + b\n"
                      "    return a"),
        "is_palindrome": ("def is_palindrome(s):\n"
                          "    t = s.lower()\n    return t == t[::-1]"),
        "reverse_string": "def reverse_string(s):\n    return s[::-1]",
    }

    def __init__(self, fn_name: str, source: Optional[str] = None):
        """★ source 缺省用 REFERENCE（基准）；可传入**待评的实现**。

        ★★★★ R30 端到端实测发现的断点①:
          execute_task 此前只跑 REFERENCE ⇒ 带 bug 的实现**跑不了**
          ⇒⇒ 而 REFERENCE 是**正确**的 ⇒ 每次 judge 必然 success=True
          ⇒⇒ ⇒★ 也就是说: **agent 的产出从未被评过分**
          ⇒⇒ ⇒★★ 那正是 R26 标过的诚实边界（第 4 条），这次是它卡住了闭环
        ⇒ ⇒★ 修法: 让实现可传入；**缺省仍为 REFERENCE**（不改既有行为）
        ⇒⇒ ⇒★ 但 `source_from` 必须记下这次跑的是谁的实现 ——
          否则"评测的是哪个实现"又变成不可审计（原则 3/7）
        """
        if fn_name not in self.ALLOWED:
            raise ActorError(
                "函数 %r 不在沙箱白名单 %r 内"
                % (fn_name, list(self.ALLOWED)))
        self.fn_name = fn_name
        self.source_from = "reference" if source is None else "provided"
        body = self.REFERENCE[fn_name] if source is None else source
        ns: Dict[str, Any] = {}
        # ★ 只编译白名单里那一个函数（不做任意 exec）
        try:
            exec(compile(body, "<%s>" % self.source_from, "exec"), ns)
        except SyntaxError as e:
            raise ActorError(
                "实现 %r 编译失败（%s）: %s"
                % (self.source_from, fn_name, e))
        if fn_name not in ns:
            raise ActorError(
                "实现 %r 里没有定义 %r（eval 侧缺定义 ⇒ 必然失败）"
                % (self.source_from, fn_name))
        self.fn = ns[fn_name]
        self.calls: List[Tuple[str, Any]] = []

    def __call__(self, task: Dict[str, Any]) -> Receipt:
        """★ 执行并**读回校验**（Verified Coupling）。"""
        args = self._parse_args(task.get("args", ""))
        first = self.fn(args)
        # ★★ 读回: 再取一次，值一致才 verified
        second = self.fn(args)
        verified = (first == second)
        self.calls.append((str(args), first))
        return Receipt(
            ok=True,
            detail={"value": first, "args": str(args)},
            # ★ verified 的依据是"两次取值一致"—— 不是"我返回了"
            verified=verified,
        )

    @staticmethod
    def _parse_args(s: str) -> Any:
        """★ 解析断言里的参数（字面量求值，**限定**在安全字面量）。"""
        try:
            return ast.literal_eval(s.strip())
        except (ValueError, SyntaxError):
            return None


# ══════════════════════════════════════════════════════════
# ★★ actor × judge 的契约：执行一个 dev 任务并产出 judge 可判的观测
# ══════════════════════════════════════════════════════════


def _as_literal(txt: str) -> Any:
    """★ 与 judge._as_literal 同源（契约两侧必须同一套归一规则）。

    ★★ 这是 R26 的核心教训: 观测契约的**两侧**都必须归一，
      只归一一边会得到"值对了但匹配不上"的假失败。
    """
    try:
        return ast.literal_eval(str(txt).strip())
    except (ValueError, SyntaxError):
        return str(txt).strip()


def build_implementation(fn_name: str, base_source: str,
                         patch: str) -> str:
    """★ 用 patch 构建一个**候选实现**（2606.09498 的 line 9）。

    ★★★★ R30 实测: 这一步此前**根本不存在** ⇒ patch 没有消费者
      ⇒⇒ ⇒★ 而我上一轮误把 patch 交给 applier 落地，
        于是撞上 APPLIER_DESIGN §六（丙类·代码替换·第一版只开甲类）
      ⇒⇒ ⇒★★ 但那是**我路由错**，不是设计矛盾:
        · patch 的消费者是**执行器**（构造待评候选）⇒ 属**执行层**
        · applier 落地的是 RULES 条目（元层数据）⇒ 属**甲类**
        · 而"构建候选"≠"落地生产" —— 只有 commit 到生产才是丙类
      ⇒⇒ ⇒★★ 所以 applier **始终不需要碰代码**

    ★★★ patch 的缩进约定（R30 逐条核过三条数据后定的）:
      · patch = 函数体，**第一行相对 def 行缩进 0**，嵌套 +4
      · 应用时所有行 **整体 +4**（因为 def 在 0 列，体在 4 列）
      · ★★ 实测: RULES 第三条此前是 0/8/4 ⇒ +4 ⇒ 4/12/8 ✗
        ⇒ 那是 R27 写数据时的**字面 bug**，
          而因为**没有应用方**一直测不到
        ⇒⇒ ⇒★★ 这是端到端暴出的第三类问题（**数据错误**，非代码错）

    ★★★ 校验（不许静默拼错）:
      · def 行必须存在（否则拼不出）
      · 编译必须通过（否则语法错在落地后才炸）
    """
    lines = base_source.split("\n")
    head = lines[0]
    if not head.strip().startswith("def "):
        raise ActorError(
            "基线实现第一行不是 def: %r" % head)
    if not fn_name + "(" in head:
        raise ActorError(
            "基线实现不是 %r 的定义: %r" % (fn_name, head))
    # ★ 所有 patch 行整体 +4（约定: 第一行相对 def 缩进 0）
    indented = "\n".join(("    " + ln) if ln.strip() else ln
                          for ln in patch.split("\n"))
    body = head + "\n" + indented
    # ★ 编译校验 —— 语法错必须在这里暴露，不许带到落地之后
    try:
        compile(body, "<candidate>", "exec")
    except SyntaxError as e:
        raise ActorError(
            "候选实现编译失败（%s）: %s" % (fn_name, e))
    return body


def execute_task(actor: "Actor", judge: Any, task_id: str,
                 decision_source: str = "heuristic",
                 trace_hook=None,
                 implementation: Optional[str] = None) -> Dict[str, Any]:
    """★ 执行一个 dev 任务，产出 **judge 的观测契约**格式。

    ★★★★ R26 实测发现的契约洞 —— 这次矛盾的根因:
      judge 的观测契约要求覆盖该任务的**全部** checks，
      而我上一轮只让 actor 跑**第一条** ⇒ 少跑 ⇒ judge 判 fail
      ⇒⇒ 而 actor 的 trace.success 却是 True（它只看执行器回执）
      ⇒⇒⇒ ★★ 后果实测: 同一个任务 actor 说成功、judge 说失败，
        两边各说各话 —— 而 judge 是对的
      ⇒⇒⇒ ⇒★ 这正是三分离要防的: **执行成功 ≠ 任务解决**
      ⇒★ 所以这里显式规定: 一个任务 = 跑完它**全部**断言

    ★★ 返回: {"task_id", "observation", "traces", "n_checks"}
    """
    rec = judge.anchors[task_id]
    if rec.get("verifier_kind") != "behavior":
        raise ActorError(
            "execute_task 只支持 behavior 形态（%r 是 %r）"
            % (task_id, rec.get("verifier_kind")))
    checks = rec["checks"]
    fns = {c["fn"] for c in checks}
    if len(fns) != 1:
        raise ActorError(
            "一个任务引用多个函数 %r —— 本执行器只支持单函数任务"
            % sorted(fns))
    fn_name = checks[0]["fn"]

    # ★★★ R30 断点①的修法: 实现可传入（缺省仍是 REFERENCE）
    ex = PureFunctionExecutor(fn_name, source=implementation)
    traces = []
    calls: List[List[Any]] = []
    for c in checks:                 # ★★★ 全部断言，不只第一条
        task = {"task_id": task_id, "kind": "code_repair",
                "fn": fn_name, "args": c["args"]}
        tr = actor.act(task, ex,
                       expected={"value": c["expected"]},
                       decision={"source": decision_source,
                                 "why": "确定性执行器"},
                       trace_hook=trace_hook)
        traces.append(tr)
        #★★★ R26 第二次修正: args 也要传**字面量**，不能传文本
        #   实测: actor 传 ['3', 6]，而 judge 归一后要 [3, 6]
        #     ⇒ 入参匹配失败 ⇒ judge 判 fail（而值其实是对的）
        #   ⇒⇒ 而这正是"契约两侧类型不一致"—— 值侧我已归一，入参侧漏了
        # ⇒★ 源头修: actor 传字面量，与 judge 的 _as_literal 对齐
        calls.append([_as_literal(c["args"]), ex.calls[-1][1]])
    return {"task_id": task_id,
            "observation": {fn_name: calls},
            "traces": traces,
            "n_checks": len(checks),
            # ★ 原则 3/7: 明说评测的是**谁的**实现
            #   （否则"agent 产出 vs 基准" 又混在一起 = R26 那个洞）
            "implementation_source": ex.source_from,
            # ★ 便于调用方用 build_implementation 重建候选（闭环要用）
            "baseline_source": (PureFunctionExecutor
                                .REFERENCE.get(fn_name)),
            "★": ("观测覆盖全部 %d 条断言 —— judge 的契约要求全量"
                  % len(checks))}


def run_dev_suite(actor: "Actor", judge: Any,
                  trace_hook=None) -> Dict[str, Any]:
    """★ 跑完 dev 集里全部 behavior 任务，并把观测交给 judge 判。

    ★★★ 这个函数的意义: 产生**第一批真实观测**
      ⇒⇒ 此前 run_term._build_observations 的那批是自造的
        （用 golden 关键词拼、必然通过）⇒ 而这批是真的跑出来的
    """
    obs: Dict[str, Dict[str, Any]] = {}
    traces: List[Any] = []
    beh = [k for k, v in judge.anchors.items()
           if not k.startswith("_") and v.get("verifier_kind") == "behavior"]
    skipped: List[str] = []
    for tid in sorted(beh):
        try:
            r = execute_task(actor, judge, tid, trace_hook=trace_hook)
        except ActorError as exc:
            skipped.append("%s(%s)" % (tid, str(exc)[:40]))
            continue
        obs[tid] = r["observation"]
        traces.extend(r["traces"])
    score = judge.score("dev", obs)
    return {"observations": obs, "score": score, "traces": traces,
            "n_actor_traces": len(traces), "skipped": skipped}


if __name__ == "__main__":
    from dwc.organs.judge import Judge

    # ★★ 自检的重点: 一条**真链** —— actor 真执行 → judge 真判
    a = Actor(trajectory_id="TRJ_self")
    jj = Judge()
    res = run_dev_suite(a, jj)
    sc = res["score"]
    print("=== ★ actor 真执行 + judge 真判分 ===")
    print("  跑了 %d 条 behavior 任务 · %d 条痕迹"
          % (len(res["observations"]), res["n_actor_traces"]))
    print("  judge: n_tasks=%d pass=%d fail=%d not_evaluated=%d"
          % (sc["n_tasks"], sc["pass"], sc["fail"], sc["not_evaluated"]))
    print("  ★ pass_rate=%s" % sc["pass_rate"])
    for tid, o in res["observations"].items():
        for fn, calls in o.items():
            print("    %-16s %s=%s" % (tid, fn, calls))
    print("  ★ actor 自报成功数=%d"
          % sum(1 for t in res["traces"] if t.success is True))
    print("  ★ judge 判 pass 数=%d  ⇒ ★★ 两者不必相等:"
          % sc["pass"])
    print("     actor 的 success 只说明『执行器回执通过』，")
    print("     judge 的判定才是『任务是否解决』")

    # ── 对照组: 一条真链 —— 任务 → 执行 → 回执 → 痕迹
    a = Actor(trajectory_id="TRJ_1")
    task = {"task_id": "code_fix_001", "kind": "code_repair",
            "fn": "sum_first_n", "args": "3"}
    ex = PureFunctionExecutor("sum_first_n")
    tr = a.act(task, ex, expected={"value": 6})
    print("trace: action=%s outcome=%s" % (tr.action, tr.outcome))
    print("  observed=%s" % tr.observed)
    print("  evidence=%s" % tr.evidence)
    print("  ★ success=%s source=%s"
          % (tr.success, tr.success_source))
    print("  ★ verified 回执 ⇒ tool_receipt（不是 actor 自判）")

    # ★ 对照: 未验证的回执 ⇒ NOT_EVALUATED
    a2 = Actor()

    class Unverified:
        def __call__(self, t):
            return Receipt(ok=True, detail={"value": 1}, verified=False)

    tr2 = a2.act(task, Unverified())
    print("\n未验证回执: success=%s source=%s"
          % (tr2.success, tr2.success_source))
    print("  ★ 未验证的返回既不算成功也不算失败")

    # ★ 异常 ⇒ 记失败痕迹（含失败定位），不是"没发生"
    a3 = Actor()

    class Boom:
        def __call__(self, t):
            raise ValueError("炸了")

    tr3 = a3.act(task, Boom())
    print("\n执行器抛异常: outcome=%s" % tr3.outcome)
    print("  failure_signature=%s" % tr3.failure_signature)
    print("  ★ 失败也有痕迹（修『失败是非事件』）")
    print("  stats=%s" % a3.stats())
    def __post_init__(self):
        # ★★ decision 必须带 source（§3.4 三分离）
        if self.decision and "source" not in self.decision:
            raise ActorError(
                "decision 缺 source 字段（§3.4: "
                "预测/决策必须可独立分析）")
        self.validate()

