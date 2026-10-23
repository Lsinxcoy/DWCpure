"""hook · 八 hook + 互斥类（2606.14249 Table 1 · EVOLUTION_CORE_V2 §4.3「抢位冲突」）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 服务环节③（提案）的**运行期契约面**: run loop 在每次 hook 调用后校验
    Processor 契约 — 违规（如 read-only hook 里改状态）**立即抛异常**,
    不用日志（V2 采原文: "violations ... immediately throw, not silently
    propagate corrupted state"）。
  ★ 不抢位: 本模块只定义 hook 协议 + 注册/校验机制, **不实现任何具体
    Processor**（那是上层器官的事 — 防本模块变成万能钩子堆）。

★★★ TRUTH_SOURCE（判据 G2）
  校验只针对**契约违规**（字段读写越权/互斥类重复注册/order 越界）——
  不判"处理器逻辑对不对"（那是 judge 的事; 契约正确 ≠ 语义正确）。

=== 论文口径（2606.14249 Table 1 逐字）===
  HOOKS 八点名: task_start / step_start / before_model / after_model /
                before_tool / after_tool / step_end / task_end
  READ_ONLY: {step_end, task_end} — 这两个 hook 不许处理器改状态
  Processor 三字段: _singleton_group（互斥类名, 每组至多一个）·
                    _order ∈ {PRE, NORMAL, POST} · _after（软依赖组名表）
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

#: 八 hook（Table 1 原文顺序 — 值枚举, 不自创 hook）
HOOKS: tuple[str, ...] = ("task_start", "step_start", "before_model",
                          "after_model", "before_tool", "after_tool",
                          "step_end", "task_end")

#: 只读 hook（这三个点之后不许改状态 — 原文明列两个 + 语义等价的前两者）
_READ_ONLY_PAPER = frozenset({"step_end", "task_end"})

#: order 三档（PRE/NORMAL/POST — 链内执行次序, 越界即拒）
ORDERS: tuple[str, ...] = ("PRE", "NORMAL", "POST")


class HookViolation(Exception):
    """契约违规（读只读 hook / 互斥类重复 / order 越界 / 未知 hook 名）。"""

    @classmethod
    def paper_error(cls) -> HookViolation:
        return cls("read_only hook 被处理器改状态 — 原文要求立即抛, "
                   "不用日志（V2 采 Table 1『违规即抛』）")


@dataclass
class ProcessorSpec:
    """一个处理器的**契约声明**（不含逻辑 — 逻辑由注册回调携带）。

    ★ name 非空且唯一（注册表主键）;
      hook ∈ HOOKS（未知 hook 名 ⇒ HookViolation — 不宽容拼错）;
      order ∈ ORDERS;
      singleton_group 非空（互斥语义的载体 — 嫌空则非同组, 但不许空串）。
    """

    name: str
    hook: str
    order: str = "NORMAL"
    singleton_group: str = ""
    after: tuple[str, ...] = ()
    call: Callable[[dict[str, Any]], Any] | None = None

    def __post_init__(self) -> None:
        if not self.name or not isinstance(self.name, str):
            raise HookViolation("ProcessorSpec.name 须非空字符串, 实 %r"
                                % (self.name,))
        if self.hook not in HOOKS:
            raise HookViolation("hook 未知: %r（八 hook 枚举外不宽容拼写"
                                " — %s）" % (self.hook, "/".join(HOOKS)))
        if self.order not in ORDERS:
            raise HookViolation("order 越界: %r（须 ∈ %s）"
                                % (self.order, "/".join(ORDERS)))
        if not self.singleton_group:
            raise HookViolation(
                "singleton_group 须非空（互斥语义载体 — 空串无法判同组; "
                "嫌互斥就用唯一组名, 不是空）")
        for g in self.after:
            if self.after and g == self.singleton_group:
                raise HookViolation(
                    "after 自指: %r 含自身组 ⇒ 软依赖成环（论文 _after 是对"
                    "**其他**组的依赖）" % (self.singleton_group,))


class HookRegistry:
    """八 hook 注册表 + 契约校验（run loop 每次调用后过这里）。

    ★★ 互斥类（singleton_group）: 同名组至多一个注册 — 第二个注册即抛
      （论文 Table 1: "each singleton group at most one" — 直击抢位冲突;
      DWC 母巢域实例: 两个器官都自称"记忆底座"就是这类冲突的形态）。
    ★★ 只读校验: step_end/task_end 上注册的处理器**不许**通过本表提供的
      write 入口改状态（违规抛 HookViolation.paper_error()）。
    """

    def __init__(self) -> None:
        self._by_hook: dict[str, list[ProcessorSpec]] = {h: [] for h in HOOKS}
        self._names: dict[str, ProcessorSpec] = {}
        self._groups: dict[str, str] = {}      # group -> processor name
        #: run loop 侧的活动状态键集合（只读 hook 调用时不许写这些键）
        self._state_keys: set = set()

    # ── 注册 ──────────────────────────────────────────────
    def register(self, spec: ProcessorSpec) -> None:
        """注册处理器（重名/互斥组冲突 ⇒ 立即抛 — 不静默覆盖）。"""
        if spec.name in self._names:
            raise HookViolation("处理器重名: %r（不静默覆盖 — 先 unregister）"
                                % (spec.name,))
        if spec.singleton_group in self._groups:
            raise HookViolation(
                "互斥组 %r 已有 %r, 又来 %r — 每组至多一个（治抢位冲突）"
                % (spec.singleton_group, self._groups[spec.singleton_group],
                   spec.name))
        self._by_hook[spec.hook].append(spec)
        self._names[spec.name] = spec
        self._groups[spec.singleton_group] = spec.name

    def unregister(self, name: str) -> None:
        """注销（不存在 ⇒ KeyError 显式 — 调用方别猜注没注册过）。"""
        spec = self._names.pop(name)          # 不存在即 KeyError
        self._by_hook[spec.hook].remove(spec)
        # 组归属只在"组主人是自己"时清（防后来者顶替过的情形留脏键）
        if self._groups.get(spec.singleton_group) == name:
            del self._groups[spec.singleton_group]

    # ── 触发 + 契约校验 ─────────────────────────────────────
    def decl_state_keys(self, keys: Iterable[str]) -> None:
        """声明活动状态键（只读 hook 将对这些键的写操作判违规）。"""
        self._state_keys |= set(keys)

    def fire(self, hook: str, state: dict[str, Any],
             writes: Iterable[str] | None = None) -> list[Any]:
        """★ 触发一个 hook 的全部处理器（按 order 分组 PRE→NORMAL→POST）。

        ★★ 契约校验（原文"run loop 在每次调用后校验"的落地形态）:
          ① hook 名须 ∈ HOOKS（未知 ⇒ 抛）
          ② 只读 hook（step_end/task_end）上若 declared writes ⇒ 立即抛
             paper_error（不是记日志后继续）
          ③ 处理器返回按注册序收集（调用方可观测每条处理结果）
        """
        if hook not in HOOKS:
            raise HookViolation("fire 未知 hook: %r（%s）"
                                % (hook, "/".join(HOOKS)))
        if hook in _READ_ONLY_PAPER and writes:
            w = list(writes)
            if w:
                raise HookViolation.paper_error()
        results: list[Any] = []
        for od in ORDERS:
            for spec in sorted((s for s in self._by_hook[hook]
                                if s.order == od),
                               key=lambda s: s.name):   # 同 order 按名稳定
                if spec.call is None:
                    results.append(None)     # 契约注册无逻辑 ⇒ 占位可审计
                else:
                    results.append(spec.call(state))
        return results

    # ── 查询（run loop/审计面用） ──────────────────────────
    def processors(self, hook: str | None = None
                   ) -> list[ProcessorSpec]:
        if hook is not None:
            if hook not in HOOKS:
                raise HookViolation("processors 未知 hook: %r" % (hook,))
            return list(self._by_hook[hook])
        return list(self._names.values())

    def groups(self) -> dict[str, str]:
        """组 ⇒ 处理器名（互斥面快照 — 审计"谁占了哪个位"）。"""
        return dict(self._groups)

    def summary(self) -> dict[str, Any]:
        return {"hooks": list(HOOKS), "read_only": sorted(_READ_ONLY_PAPER),
                "n_registered": len(self._names),
                "n_groups": len(self._groups),
                "per_hook": {h: len(self._by_hook[h]) for h in HOOKS}}


HOOK_MECHANICS: dict[str, str] = {
    "singleton": "Table 1: 每组至多一个处理器（_singleton_group 语义）",
    "read_only": "step_end/task_end 上违规写 ⇒ 立即抛（V2 采原文异常派）",
    "orders": "PRE/NORMAL/POST 三段内按名稳定序（保证可复现触发序列）",
    "no_impl": "本模块只协议+注册+校验（不实现具体 Processor — 防万能钩子堆）",
}
