# -*- coding: utf-8 -*-
"""actor（organs/actor.py）的契约测试。

★★★ 这个器官的测试必须包含**负面验证**
  R26 实测发现的坑: 只测通过路径时, judge 与 actor 两边都报"成功",
  看不出任何问题 —— 而一旦有错实现, 才知道 judge 真的能判 fail
  ⇒⇒ 所以这里的核心是: 故意做错, 断言必须被抓住

★ 逐条纪律（ACTOR_DESIGN 逐条核过）
  ① §3.3 · actor 不许自己判成功（三来源 + NOT_EVALUATED）
  ② §3.4 · prediction / decision / outcome 三分离
  ③ §4.2 · evolve 不进 actor
  ④ 接口 · actor 不得自己造任务（任务源唯一）
  ⑤ Verified Coupling · 回执必须读回校验
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
import dwc.organs.judge as J  # noqa: E402
from dwc.organs.actor import (  # noqa: E402
    GRANULARITY, MAINTENANCE_ACTIONS, NOT_EVALUATED, SUCCESS_SOURCES,
    Actor, ActorError, PureFunctionExecutor, Receipt, Trace,
    execute_task, run_dev_suite,
)
from dwc.organs.judge import Judge  # noqa: E402


@pytest.fixture
def j():
    return Judge()


@pytest.fixture
def a():
    return Actor(trajectory_id="TRJ_t")


def _task(fn="sum_first_n", args="3", tid="code_fix_001"):
    return {"task_id": tid, "kind": "code_repair", "fn": fn, "args": args}


# ══════════════════════════════════════════════════════════
# ①★★ actor 不许自己判成功
# ══════════════════════════════════════════════════════════

def test_actor_has_no_self_judging_interface(a):
    """★★★ 意图: Actor 上不许有任何判分/打分接口。"""
    for banned in ("verdict", "judge", "score", "evaluate", "grade",
                   "is_correct"):
        assert not hasattr(a, banned), \
            "Actor 出现 %r —— §3.3: actor 的 success 不许自己判" % banned


def test_success_only_via_set_external_verdict(a):
    """★★★★ 意图: success 的唯一填写路径是 set_external_verdict。

    ⇒⇒ ★★ 这条在代码层面保证了"actor 自判成功"不可能发生
    """
    tr = Trace(action="x", decision={"source": "heuristic"})
    assert tr.success is None, "新建痕迹不许有 success"
    with pytest.raises(ActorError):
        tr.set_external_verdict(True, NOT_EVALUATED)
    tr.set_external_verdict(True, "tool_receipt")
    assert tr.success is True and tr.success_source == "tool_receipt"


def test_default_success_source_is_not_evaluated(a):
    """★★★ 意图: 默认 success_source = NOT_EVALUATED（§3.3 第③条）。"""
    assert Trace(action="x", decision={"source": "h"}).success_source \
        == NOT_EVALUATED


def test_verified_receipt_gives_tool_receipt(a):
    """★★★ 意图: verified 回执 ⇒ tool_receipt（§3.3②）。"""
    ex = PureFunctionExecutor("sum_first_n")
    tr = a.act(_task(), ex, expected={"value": 6})
    assert tr.success is True
    assert tr.success_source == "tool_receipt"
    assert tr.evidence["receipt"]["verified"] is True


def test_unverified_receipt_is_not_evaluated(a):
    """★★★★ 意图: 未验证的返回**既不算成功也不算失败**。"""
    class Unverified:
        def __call__(self, t):
            return Receipt(ok=True, detail={"value": 1}, verified=False)
    tr = a.act(_task(), Unverified())
    assert tr.success is None, "未验证的返回不许当成功"
    assert tr.success_source == NOT_EVALUATED


def test_unstable_executor_loses_receipt_on_second_call(a):
    """★★★★ 意图: 不稳定的实现 ⇒ 第二次不再算回执（读回校验抓到了）。"""
    class Flaky:
        def __init__(self):
            self.n = 0

        def __call__(self, t):
            self.n += 1
            return Receipt(ok=True, detail={"v": self.n},
                           verified=(self.n == 1))
    f = Flaky()
    t1 = a.act(_task(), f)
    t2 = a.act(_task(), f)
    assert t1.success is True
    assert t2.success is None, "第二次不一致 ⇒ 不算回执"


def test_exception_leaves_trace_with_signature(a):
    """★★★★ 意图: 执行器抛异常 ⇒ 记失败痕迹（修"失败是非事件"）。

    ★ Recuris 判据: 没有失败定位的痕迹不算合格痕迹
    """
    class Boom:
        def __call__(self, t):
            raise ValueError("炸了")
    tr = a.act(_task(), Boom())
    assert tr.outcome == "raised"
    assert tr.failure_signature is not None
    assert set(tr.failure_signature) == {"c", "q", "m"}
    assert tr.failure_signature["c"] == "ValueError"
    assert a.traces, "失败也必须留痕（不是没发生）"


def test_rejected_receipt_gets_signature(a):
    """★★ 意图: 回执 ok=False ⇒ 有失败定位，但 success 仍是 None。"""
    class Reject:
        def __call__(self, t):
            return Receipt(ok=False, detail={"error_code": "E_X"},
                           verified=True)
    tr = a.act(_task(), Reject())
    assert tr.success is None, "未验证的失败不许当 False（§4.5）"
    assert tr.failure_signature["c"] == "E_X"


def test_executor_must_return_receipt(a):
    """★★ 意图: executor 返回别的类型必须 raise（不许默默接受）。"""
    class Bad:
        def __call__(self, t):
            return {"ok": True}
    with pytest.raises(ActorError):
        a.act(_task(), Bad())


# ══════════════════════════════════════════════════════════
# ② 三分离（§3.4）
# ══════════════════════════════════════════════════════════

def test_decision_requires_source():
    """★★★ 意图: decision 必须带 source（预测/决策可独立分析）。"""
    with pytest.raises(ActorError):
        Trace(action="x", decision={"why": "没说来源"})


def test_outcome_is_enum_not_free_text(a):
    """★★ 意图: outcome 是枚举（returned / raised），不是自由字符串。"""
    ex = PureFunctionExecutor("sum_first_n")
    tr = a.act(_task(), ex)
    assert tr.outcome in ("returned", "raised")
    #★★★★ R26 修正（我这测试写法也错了）:
    #   __post_init__ 只在构造那一刻跑 ⇒ 事后赋值它拦不住
    #   ⇒ 而 Trace 不是 frozen（act() 内部就要事后设 outcome）
    #   ⇒★ 所以纪律必须由 validate() 显式执行，而不是只靠构造
    #   ⇒★★ 而「只在构造时生效」等于「没生效」
    with pytest.raises(ActorError):
        Trace(action="x", decision={"source": "h"}, outcome="随便写的")
    with pytest.raises(ActorError):
        tr.outcome = "随便写的"
        tr.validate()


def test_prediction_and_decision_are_separate_fields(a):
    """★★★ 意图: prediction 与 decision 是两个独立字段（§3.4 三分离）。"""
    ex = PureFunctionExecutor("sum_first_n")
    tr = a.act(_task(), ex, prediction={"demand": 0.8},
               decision={"source": "llm", "why": "预测不许当决策"})
    assert tr.prediction == {"demand": 0.8}
    assert tr.decision["source"] == "llm"
    assert tr.prediction is not tr.decision


def test_expected_is_recorded_before_execution(a):
    """★★★ 意图: expected 必须存在（修"失败是非事件"，§3.2）。"""
    ex = PureFunctionExecutor("sum_first_n")
    tr = a.act(_task(), ex, expected={"value": 6})
    assert tr.expected == {"value": 6}


def test_granularity_is_restricted():
    """★★ 意图: 三层粒度限定（§3.1）。"""
    assert GRANULARITY == ("trajectory", "user_turn", "subscene")
    with pytest.raises(ActorError):
        Trace(action="x", decision={"source": "h"}, granularity="随便")


# ══════════════════════════════════════════════════════════
# ③ evolve 不进 actor（§4.2）
# ══════════════════════════════════════════════════════════

def test_evolve_not_in_maintenance_actions():
    """★★★ 意图: evolve **不进** actor（进化由 evolver 器官负责）。"""
    assert "evolve" not in MAINTENANCE_ACTIONS
    assert MAINTENANCE_ACTIONS == ("dream", "learn", "maintain", "remember")


# ══════════════════════════════════════════════���═══════
# ④ actor 不得自己造任务
# ══════════════════════════════════════════════��═════════

def test_legal_actions_requires_task_source(a):
    """★★★ 意图: 任务源没有 legal_actions ⇒ raise（不兜底、不自造）。"""
    class NoSource:
        pass
    with pytest.raises(ActorError) as e:
        a.legal_actions(NoSource())
    assert "不得自己造任务" in str(e.value)


def test_legal_actions_forwards_unchanged(a):
    """★★ 意图: 只转发，不筛选不补充。"""
    tasks = [{"task_id": "t1"}, {"task_id": "t2"}]

    class Src:
        def legal_actions(self):
            return list(tasks)

    got = a.legal_actions(Src())
    assert [g["task_id"] for g in got] == ["t1", "t2"]


# ══════════════════════════════════════════════════════════
# ★★★ 负面验证: 故意做错, judge 必须抓住
# ══════════════════════════════════════════════════════════

def test_wrong_implementation_is_judged_fail(j):
    """★★★★★ 核心负面验证: off-by-one 实现 ⇒ judge 判 fail。

    ★★★ 只测通过路径时看不出问题 —— 这一条才证明 judge 真的在判
    """
    class Broken(PureFunctionExecutor):
        def __call__(self, task):
            args = self._parse_args(task.get("args", ""))
            wrong = self.fn(args) + 1
            self.calls.append((str(args), wrong))
            return Receipt(ok=True, detail={"value": wrong}, verified=True)

    ex = Broken("sum_first_n")
    calls = []
    for c in j.anchors["code_fix_001"]["checks"]:
        ex(_task(args=c["args"]))
        calls.append([J._as_literal(c["args"]), ex.calls[-1][1]])
    v = j.evaluate("code_fix_001", "dev", observed={"sum_first_n": calls})
    assert v.success is False, "错实现必须被判 fail"


def test_partial_observation_is_fail(j):
    """★★★ 意图: 只跑部分断言 ⇒ fail（观测必须覆盖全部）。"""
    ex = PureFunctionExecutor("sum_first_n")
    ex(_task(args="3"))
    v = j.evaluate("code_fix_001", "dev",
                   observed={"sum_first_n": [[3, 6]]})     # ★ 只一条
    assert v.success is False, "少跑断言不该算过"


def test_actor_and_judge_can_disagree(a, j):
    """★★★★ 意图: actor 说成功、judge 判 fail —— 两者独立（三分离）。"""
    ex = PureFunctionExecutor("sum_first_n")
    tr = a.act(_task(), ex, expected={"value": 6})
    assert tr.success is True, "执行器回执通过 ⇒ actor 说成功"
    v = j.evaluate("code_fix_001", "dev", observed={"sum_first_n": [[3, 6]]})
    assert v.success is False, "但 judge 判 fail（少跑一条）"
    # ★★ 这不是矛盾，是两件不同的事
    assert tr.success_source == "tool_receipt"


def test_string_typed_assertion_passes(j):
    """★★★★ 意图: 字符串型断言要能过（R26 修的就是这个）。"""
    ex = PureFunctionExecutor("reverse_string")
    r = execute_task(Actor(), j, "code_fix_006")
    v = j.evaluate("code_fix_006", "dev", observed=r["observation"])
    assert v.success is True, "字符串断言不该永远挂"


def test_observation_args_must_be_literals(a, j):
    """★★★★ 意图: 观测的入参必须是**字面量**（R26 的契约洞）。"""
    r = execute_task(a, j, "code_fix_001")
    for call in r["observation"]["sum_first_n"]:
        assert isinstance(call[0], int), \
            "入参应归一成字面量（否则 judge 匹配不上）"
    v = j.evaluate("code_fix_001", "dev", observed=r["observation"])
    assert v.success is True


def test_execute_task_covers_all_checks(a, j):
    """★★★ 意图: 一个任务要跑完**全部**断言（R26 的根因修复）。"""
    r = execute_task(a, j, "code_fix_004")       # 3 条断言
    assert r["n_checks"] == 3
    assert len(r["observation"]["fibonacci"]) == 3
    assert r["traces"], "每条断言都应留痕"


def test_execute_task_rejects_keyword_kind(a, j):
    """★★ 意图: keyword 形态不许走确定性执行器。"""
    with pytest.raises(ActorError):
        execute_task(a, j, "reasoning_001")


# ══════════════════════════════════════════════════════════
# 真套件与统计
# ══════════════════════════════════════════════════════════

def test_dev_suite_produces_real_observations(a, j):
    """★★★★ 意图: 真套件产出**真**观测（不是自造的）。"""
    res = run_dev_suite(a, j)
    sc = res["score"]
    assert res["n_actor_traces"] > 0
    assert sc["pass"] == 6, "6 条 behavior 任务应全过"
    assert sc["fail"] == 0
    # ★ 关键: 覆盖全部断言，不是每条只跑一个
    for tid, obs in res["observations"].items():
        for fn, calls in obs.items():
            n_checks = len(j.anchors[tid]["checks"])
            assert len(calls) == n_checks, \
                "%s 只跑了 %d/%d 条断言" % (tid, len(calls), n_checks)


def test_pass_rate_uses_only_graded(a, j):
    """★★★★ 意图: 分母只算判过的（not_evaluated 不进分母）。"""
    sc = run_dev_suite(Actor(), j)["score"]
    # ★ R199: dev 13 条（+3 rung3; run_dev_suite 只跑 behavior ⇒ pass+fail 仍 6）
    assert sc["n_tasks"] == 13
    assert sc["pass"] + sc["fail"] == 6
    # ★ R199: not_evaluated 4→7（+3 expected_values — run_dev_suite 只跑
    #   behavior; 13 = 6 graded + 7 未评, 分母只算判过的意图不变）
    assert sc["not_evaluated"] == 7
    assert sc["pass_rate"] == 1.0
    # ★ 若把 not_evaluated 当 fail ⇒ 0.6；这里必须是 1.0


def test_actor_stats_reports_three_numbers(a):
    """★★ 意图: actor 统计三数分开（None 不许当 False 也不许当 True）。"""
    ex = PureFunctionExecutor("sum_first_n")
    a.act(_task(), ex, expected={"value": 6})          # success
    a.act(_task(), lambda t: Receipt(True, {}, False))  # None
    st = a.stats()
    assert st["n_traces"] == 2
    assert st["passed"] == 1
    assert st["not_evaluated"] == 1
    assert st["failed"] == 0


def test_not_evaluated_queryable(a):
    """★★ 意图: 未评价的痕迹可查（§3.3③ 的审计出口）。"""
    a.act(_task(), lambda t: Receipt(True, {}, False))
    assert len(a.not_evaluated()) == 1


def test_trace_hook_failure_does_not_record(a):
    """★★★ 意图: hook 抛异常 ⇒ 痕迹**不进**（判据 S5 的落地）。"""
    def boom(t):
        raise RuntimeError("落库失败")
    ex = PureFunctionExecutor("sum_first_n")
    with pytest.raises(RuntimeError):
        a.act(_task(), ex, trace_hook=boom)
    assert a.traces == [], "hook 失败 ⇒ 痕迹不该被记下"


def test_trace_hook_sees_trace_before_persist(a):
    """★★ 意图: hook 拿到的是落库**前**的痕迹（S5: trace_before_persist）。"""
    seen = []
    ex = PureFunctionExecutor("sum_first_n")
    a.act(_task(), ex, trace_hook=lambda t: seen.append(t))
    assert len(seen) == 1 and a.traces[0] is seen[0]


# ══════════════════════════════════════════════════════════
# 沙箱纪律
# ══════════════════════════════════════════════════════════

def test_executor_whitelist():
    """★★★ 意图: 沙箱白名单限定（不许任意 exec）。"""
    with pytest.raises(ActorError):
        PureFunctionExecutor("os")
    with pytest.raises(ActorError):
        PureFunctionExecutor("__import__")


def test_success_sources_restricted():
    """★★ 意图: 合法 success_source 只有三个。"""
    assert SUCCESS_SOURCES == ("judge_verdict", "tool_receipt",
                               NOT_EVALUATED)
    with pytest.raises(ActorError):
        Trace(action="x", decision={"source": "h"},
              success_source="self_reported")


def _bare_executor(fn):
    """绕开 __init__（白名单）造一个只测 __call__ 解包逻辑的 executor。"""
    ex = PureFunctionExecutor.__new__(PureFunctionExecutor)
    ex.fn = fn
    ex.calls = []
    ex.source_from = "test"
    return ex


def test_executor_multiargs_unpacks_tuple():
    """★ R65 修复锁（hard 任务逮住的承重件 bug）:
    多参字面量 "2, 3" → literal_eval 得 tuple ⇒ 必须**解包**传入。

    此前 `self.fn(args)` 把整个 tuple 当一个参数 ⇒ TypeError:
    missing 1 required positional argument —— dev 6 任务全是单参
    ⇒ 从未暴露; 这条测试是 RED 锁（破坏: 去掉 * 即红）。
    """
    ex = _bare_executor(lambda a, b: a + b)
    rc = ex({"args": "2, 3"})
    assert rc.ok and rc.detail["value"] == 5
    assert rc.verified
    ex2 = _bare_executor(lambda s, k: s * k)
    rc2 = ex2({"args": "'ab', 3"})
    assert rc2.detail["value"] == "ababab"


def test_executor_single_arg_unchanged():
    """★★ 零回归锁: 单标量 / 单列表 / 解析失败(None) 与旧行为一致。"""
    ex = _bare_executor(lambda n: n * 2)
    assert ex({"args": "4"}).detail["value"] == 8
    ex2 = _bare_executor(lambda xs: list(xs))
    assert ex2({"args": "[1, 2]"}).detail["value"] == [1, 2]
    ex3 = _bare_executor(lambda v: v)
    # literal_eval 失败 ⇒ None（旧行为: fn(None) 不崩）
    assert ex3({"args": "not a literal"}).detail["value"] is None