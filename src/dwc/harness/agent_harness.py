"""agent_harness · 可进化的 agent 外壳（Phase B3 · 2026-10-19）

DWC-AUTO 定位声明（器官 · 判据 G1 定位门）
  ★ 服务环节③（提案）的**运行期基质**: 把"LLM 想改什么"变成"可执行变异"
    的完整回合编排，并在 HarnessX 的 8 个点 fire 处理器。
  ★ 不抢位: 本模块只编排回合 + fire hook；具体的 prompt 构造 / 输出解析 /
    文件选择 / 错误反馈全部由 `dwc.organs.processors` 的 Processor 提供，
    本模块不内嵌任何策略逻辑。

★★★ TRUTH_SOURCE（判据 G2）
  成功判据 = 注入的 `run_tests` 回调返回的 `all_passed`；
  本模块不生成 label、不自评、不猜测试结果。

★★ G4 生灭门说明
  本模块不做候选生成/淘汰（无 generate/evolve 语义）——它只按 Policy
  编排一次求解回合；选择与淘汰由上层 evolver 负责（职责分离，不抢位）。

=== 为什么需要它（Phase A 审计的结论）===
  `organs/hook.py` 的 8-hook 协议实现了，但零生产接线；
  `benchmark_fitness` 的信号无人消费；`evolver` 实例化但 step 分发未接线。
  根因是 agent 的求解回合没有"可挂载的契约面"——本模块就是那个面。

=== 依赖方向（重要）===
  本模块**不 import scripts/**。基准相关的 I/O（checkout / pytest / LLM）
  全部通过 `HarnessDeps` 注入，保持 src/dwc 不反向依赖工具脚本。
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any

from dwc.organs.hook import HOOKS, HookRegistry

# ══════════════════════════════════════════════════════════════════
# 1. Policy —— 可进化的策略面（Phase D 会把它移到 organs 下的 policy 模块）
# ══════════════════════════════════════════════════════════════════

@dataclass(frozen=True)
class Policy:
    """一次求解回合的策略参数。

    ★ 这些字段就是 genotype：变异一个字段 = 一个候选策略。
    ★ 具体 patch 是 phenotype，由 policy × LLM 在运行时产生，不进化。
    """

    localization: str = "keyword"     # keyword | llm_select
    patch_format: str = "json"        # json（Phase F 加 codeact/diff）
    max_rounds: int = 3
    context_chars: int = 1500
    verifier: bool = True
    max_tokens: int = 2000
    system: str = "You are a software engineer. Output valid JSON only. No explanation."

    def mutate(self, field: str, value: Any) -> Policy:
        if field not in self.__dataclass_fields__:
            raise KeyError("Policy 无字段 %r（可变异面 = %s）"
                           % (field, "/".join(self.__dataclass_fields__)))
        return replace(self, **{field: value})


# ══════════════════════════════════════════════════════════════════
# 2. 依赖注入面
# ══════════════════════════════════════════════════════════════════

@dataclass
class HarnessDeps:
    """求解回合需要的外部能力（全部由调用方注入）。

    ★ 只放"做动作"的能力，不放"判断"的能力——
      判断在 run_tests / verify 回调里，本模块只搬运结果。
    """

    call_llm: Callable[[str, str, int], str]
    list_files: Callable[[], list[str]]
    read_file: Callable[[str, int], str | None]
    apply_edit: Callable[[str, str, str], tuple[str | None, str]]
    write_file: Callable[[str, str], None]
    check_syntax: Callable[[str], tuple[bool, str]]
    run_tests: Callable[[], dict[str, Any]]
    verify: Callable[[str, str, str], tuple[str, str]]


# ══════════════════════════════════════════════════════════════════
# 3. 结果
# ══════════════════════════════════════════════════════════════════

@dataclass
class HarnessResult:
    success: bool
    rounds: int
    hooks_fired: list[str] = field(default_factory=list)
    last_action: dict[str, Any] | None = None
    last_tool_result: dict[str, Any] | None = None
    previous_error: str = ""
    history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "rounds": self.rounds,
            "hooks_fired": list(self.hooks_fired),
            "last_action": self.last_action,
            "last_tool_result": self.last_tool_result,
            "previous_error": self.previous_error,
        }


# ══════════════════════════════════════════════════════════════════
# 4. 主类
# ══════════════════════════════════════════════════════════════════

class AgentHarness:
    """按 Policy 编排一次求解回合，在 8 个点 fire hook。

    回合内 hook 顺序（HarnessX Table 1 原文顺序）:
      task_start → [ step_start → before_model → after_model →
                     before_tool → (动作) → after_tool → step_end ] × N
      → task_end

    ★ step_end / task_end 是只读 hook（`hook.py:145` 的契约），
      fire 时传 `writes=None`，任何处理器想写都会被立即抛异常。
    """

    def __init__(self, deps: HarnessDeps, registry: HookRegistry | None = None,
                 policy: Policy | None = None):
        self.deps = deps
        self.reg = registry or HookRegistry()
        self.policy = policy or Policy()
        self.fired: list[str] = []

    # ── 内部: 一次 fire（记录 + 契约）──────────────────────────
    def _fire(self, hook: str, state: dict[str, Any],
              writes: list[str] | None = None) -> list[Any]:
        self.fired.append(hook)
        return self.reg.fire(hook, state, writes=writes)

    # ── 主入口 ────────────────────────────────────────────────
    def solve(self, problem_statement: str,
              f2p_tests: list[str] | None = None) -> HarnessResult:
        """求解一个 instance。

        ★ 不做"是否成功"的判断——只读 `run_tests` 回调的 all_passed。
        """
        pol = self.policy
        state: dict[str, Any] = {
            "problem_statement": problem_statement,
            "f2p_tests": list(f2p_tests or []),
            "policy": pol,
            "deps": self.deps,          # processors 通过 state 取注入能力
            "iteration": 0,
            "target_files": [],
            "file_contents": {},
            "prompt": "",
            "raw_response": "",
            "action": None,
            "parse_failed": False,
            "tool_result": None,
            "previous_error": "",
            "done": False,
            "history": [],
        }

        self._fire("task_start", state)

        result = HarnessResult(success=False, rounds=0, hooks_fired=self.fired)

        for i in range(max(1, int(pol.max_rounds))):
            state["iteration"] = i
            state["parse_failed"] = False
            state["guard_failed"] = False
            state["action"] = None
            state["tool_result"] = None

            self._fire("step_start", state)

            # before_model: PromptBuilder 组装 prompt
            self._fire("before_model", state)
            if not state.get("prompt"):
                state["previous_error"] = "prompt 为空（PromptBuilder 未注册或未产出）"
                self._fire("step_end", state, writes=None)
                continue

            # ── 模型调用（唯一的外呼点）──
            raw = self.deps.call_llm(pol.system, state["prompt"], pol.max_tokens)
            state["raw_response"] = raw or ""

            # after_model: OutputParser 解析成 action
            self._fire("after_model", state)
            if state.get("parse_failed") or not state.get("action"):
                state["previous_error"] = (
                    "LLM 未产出可解析的 action（原文前 300 字：%s）"
                    % (state["raw_response"][:300] or "(空)"))
                self._fire("step_end", state, writes=None)
                result.rounds = i + 1
                continue

            # before_tool: ActionGuard 校验目标文件
            self._fire("before_tool", state)
            if state.get("guard_failed"):
                self._fire("step_end", state, writes=None)
                result.rounds = i + 1
                continue

            # ── 动作执行（编辑 + 语法 + 测试 + 验证）──
            tool_result = self._execute(state)
            state["tool_result"] = tool_result

            # after_tool: ErrorFeeder 决定下一轮喂什么
            self._fire("after_tool", state)

            self._fire("step_end", state, writes=None)
            result.rounds = i + 1
            result.last_action = state.get("action")
            result.last_tool_result = tool_result
            result.previous_error = state.get("previous_error", "")

            if tool_result.get("ok"):
                result.success = True
                break

        self._fire("task_end", state, writes=None)
        result.hooks_fired = list(self.fired)
        result.previous_error = state.get("previous_error", "")
        result.last_action = state.get("action") or result.last_action
        result.last_tool_result = state.get("tool_result") or result.last_tool_result
        return result

    # ── 动作执行 ──────────────────────────────────────────────
    def _execute(self, state: dict[str, Any]) -> dict[str, Any]:
        """应用编辑 → 语法检查 → 跑测试 → 独立验证。

        ★ 任一步失败都回滚文件，并把原因写进 state["previous_error"]。
        ★ 不做"成功"判断：ok 只表示 run_tests.all_passed 且 verifier 未拒。
        """
        action = state["action"]
        path = action.get("file", "")
        old = action.get("old_string", "")
        new = action.get("new_string", "")

        out: dict[str, Any] = {
            "file": path, "applied": False, "syntax_ok": False,
            "f2p": {}, "verdict": "", "findings": "", "ok": False,
        }

        original = self.deps.read_file(path, 10 ** 9)
        if original is None:
            state["previous_error"] = "文件不可读: %s" % path
            return out

        new_content, msg = self.deps.apply_edit(original, old, new)
        if new_content is None:
            out["apply_error"] = msg
            state["previous_error"] = "patch 落地失败: %s" % msg
            return out
        out["applied"] = True

        self.deps.write_file(path, new_content)

        ok, err = self.deps.check_syntax(path)
        out["syntax_ok"] = bool(ok)
        if not ok:
            self.deps.write_file(path, original)      # 回滚
            out["syntax_error"] = err
            state["previous_error"] = "语法检查失败（已回滚）:\n%s" % err[:500]
            return out

        tests = self.deps.run_tests()
        f2p = tests.get("f2p") or tests      # 兼容旧回调（直接返回 f2p 形态）
        p2p = tests.get("p2p") or {}
        out["f2p"] = f2p
        out["p2p"] = p2p

        verdict, findings = "", ""
        if state["policy"].verifier:
            diff = self._diff(path, old, new)
            test_output = "F2P: %s/%s" % (f2p.get("passed"), f2p.get("total"))
            if p2p and not p2p.get("skipped"):
                test_output += " | P2P: %s/%s" % (p2p.get("passed"), p2p.get("total"))
            verdict, findings = self.deps.verify(
                state["problem_statement"], diff, test_output)
        out["verdict"], out["findings"] = verdict, findings

        passed = bool(tests.get("all_passed"))
        rejected = verdict == "FAIL"
        out["ok"] = passed and not rejected

        if not passed:
            self.deps.write_file(path, original)      # 回滚
            state["previous_error"] = "测试未通过（已回滚）: F2P %s/%s" % (
                f2p.get("passed"), f2p.get("total"))
        elif rejected:
            self.deps.write_file(path, original)
            state["previous_error"] = "验证器拒绝（已回滚）: %s" % findings[:500]
        else:
            state["previous_error"] = ""

        return out

    @staticmethod
    def _diff(path: str, old: str, new: str) -> str:
        return ("--- a/%s\n+++ b/%s\n@@ ... @@\n-%s\n+%s"
                % (path, path, old[:400], new[:400]))


__all__ = ["HOOKS", "AgentHarness", "HarnessDeps", "HarnessResult", "Policy"]
