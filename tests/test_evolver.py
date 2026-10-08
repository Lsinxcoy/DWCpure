# -*- coding: utf-8 -*-
"""evolver（organs/evolver.py）的契约测试。

★★★ 为什么这个器官的测试以"约束"为纲
  EVOLUTION_CORE_DESIGN §九 的四条约束不是建议，是**硬边界**
  ⇒⇒ 而它们的共同特点是: 违反了也不会立刻爆炸，只是悄悄让进化失效
  ⇒⇒⇒ 所以每条约束都要有**阳性（挡住）**测试

★ 逐条约束:
  约束 1 · 禁止"先落再测"  ⇒ 状态机 gated → adopted（有中间态）
  约束 2 · 判据在可写面外  ⇒ 触及真值源的提案必被拒
  约束 3 · 必须两组 split  ⇒ 只有 in-sample ⇒ **blocked 而非采纳**
  约束 4 · 每轮可归因     ⇒ 一个提案只改一处 · 聚类按三元组精确一致
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.organs.evolver import (
    K_META,   # noqa: E402
    COMPONENT_VOCAB, DIMENSIONS, PROPOSAL_STATES, STRUCTURAL,
    Evolver, EvolverError, Mutator, Proposal, ProposalGate,
)


@pytest.fixture
def ev():
    return Evolver()


def _sig(c="E_VALUE", q="wrong_magnitude", fn="sum_first_n", m=""):
    """★★ R30: 签名格式随结构修正改版 —— 与 RULES 的**查询键**对齐。

    ★★ 变更（每条都有实测依据）:
      c: E_OFF_BY_ONE → **E_VALUE**
        ⇒ 实测差值是 3 和 5（n=3: 3 vs 6 · n=5: 10 vs 15）
          ⇒⇒ 不是 1 ⇒ classify_c 判 E_VALUE 正确
          ⇒⇒ 而 E_OFF_BY_ONE 是我 R27 **凭常识标的**（数据错误）
      q: sum_first_n → **wrong_magnitude**
        ⇒ 原文 q = causal role（因果状态），不是"被改对象"
          ⇒⇒ 我 R27 读原文后按直觉映射成函数名 ⇒ 语义错
      新增 **fn** —— 定位维度（查询键 = c:q:fn）
        ⇒ 三元组不含"要改哪" ⇒ 必须显式
      m: code_repair → **""**
        ⇒ 原文分工: m 由**模型**填 ⇒ 第一版无 LLM ⇒ 留空并由 RULES 补
    """
    return {"c": c, "q": q, "fn": fn, "m": m}


def _p(**kw):
    base = {"proposal_id": "P_x", "failure_signature": _sig(),
            "component": "control_flow", "target": "sum_first_n",
            "patch": "return 0", "rationale": "依据"}
    base.update(kw)
    return Proposal(**base)


# ══════════════════════════════════════════════════════════
# 提案的形态（约束 4：可归因）
# ══════════════════════════════════════════════════════════

def test_component_must_be_in_rrsi_vocab():
    """★★ 意图: 组件必须在 RRSI 词表内（2609.24972 式 12）。"""
    assert "control_flow" in COMPONENT_VOCAB and "skill" in COMPONENT_VOCAB
    with pytest.raises(EvolverError):
        _p(component="随便什么")


def test_structural_components_marked():
    """★★ 意图: 结构型组件自动标记（式 15: ν_str 新颖度奖励）。"""
    assert _p(component="skill").is_structural is True
    assert _p(component="prompt").is_structural is False
    assert STRUCTURAL == {"client_tool", "skill", "memory", "subagent"}


def test_rationale_required():
    """★★★ 意图: rationale 必填 —— 不许"看着办"。

    ★★ 依据约束 4: 变更必须可归因 ⇒ 必须说清为什么改
    """
    with pytest.raises(EvolverError) as e:
        _p(rationale="   ")
    assert "rationale" in str(e.value)


def test_dimension_must_be_nine_dims():
    """★★ 意图: 维度限定九维（2606.14249 §3.3）。"""
    assert len(DIMENSIONS) == 9
    with pytest.raises(EvolverError):
        _p(dimension="D99")


def test_state_restricted():
    """★★ 意图: 状态限定五种（含 R14 的第五态）。"""
    assert "adopted_not_implemented" in PROPOSAL_STATES
    with pytest.raises(EvolverError):
        _p(state="随便")


def test_proposal_key_is_stable_and_unique():
    """★★★ 意图: 提案指纹稳定且能区分不同变更（可归因的基础）。"""
    k1 = _p().key()
    assert k1 == _p().key(), "同提案指纹必须一致"
    assert k1 != _p(patch="return 1").key(), "不同 patch 必须不同指纹"
    assert k1 != _p(target="average").key(), "不同 target 必须不同指纹"


# ══════════════════════════════════════════════════════════
# 约束 4 · 聚类必须精确一致
# ══════════════════════════════════════════════════════════

def test_diagnose_dedups_identical_signatures(ev):
    """★★★ 意图: 三元组全同 ⇒ 只算一个提案（重复不新增）。"""
    sigs = [_sig()] * 5
    d = ev.diagnose(sigs)
    assert len(d["proposals"]) == 1
    assert d["n_clusters"] == 1


def test_diagnose_does_not_merge_on_c_alone(ev):
    """★★★★ 意图: **不按 c 单独合并**（2606.09498 原文）。

    ★★ 原文: "两个 run 可能共享同一个 verifier 结果（如 timeout）
      却需要不同的干预"⇒⇒⇒ 所以 (c,q,m) 必须全同才算一簇
    """
    d = ev.diagnose([_sig(c="E_X", q="a", m="code_repair"),
                     _sig(c="E_X", q="b", m="code_repair")])
    assert d["n_clusters"] == 2, "同 c 不同 q/m ⇒ 两个簇"


def test_incomplete_signature_raises(ev):
    """★★★ 意图: 缺 c/q/m 必须 raise（不许默默跳过）。"""
    with pytest.raises(EvolverError):
        ev.diagnose([{"c": "x", "q": "y"}])


def test_unmapped_signature_is_legal(ev):
    """★★★ 意图: 无规则的签名 ⇒ 不产生提案（这是**正确**行为）。"""
    d = ev.diagnose([_sig(c="E_NEVER_HEARD", q="zzz", m="zzz")])
    assert d["proposals"] == []
    assert d["n_unmapped"] == 1
    # ★★ 而"为改而改"是更坏的行为 ⇒ 返回 None 是对的


# ══════════════════════════════════════════════════════════
# 约束 2 · 判据在可写面之外
# ══════════════════════════════════════════════════════════

@pytest.mark.parametrize("target,patch", [
    ("config/anchors/dev.json", "pass_rate=1.0"),
    ("judge", "return True"),
    ("scripts/gate.py", "G2.pass()"),
    ("config/iron_laws.yaml", "删掉 G7"),
])
def test_proposal_touching_truth_is_rejected(ev, target, patch):
    """★★★★ 意图: 触及真值源/判据的提案必被拒（约束 2）。

    ★★ 依据 2609.13406 grounded 条件②: base 必须在 agent 外
    ⇒⇒⇒ 而能改判据的进化器，可以把自己的失败改成通过
    """
    p = _p(target=target, patch=patch)
    r = ev.gate.check(p)
    assert r["pass"] is False
    assert any(v["rule"] == "touches_truth" for v in r["violations"])


def test_gate_is_five_checks(ev):
    """★★ 意图: 门有五项检查（可审计）。"""
    r = ev.gate.check(_p())
    assert r["n_checks"] == 5
    assert set(r) >= {"gate", "pass", "violations", "proposal_id", "key"}


# ══════════════════════════════════════════════════════════
# 约束 1 · 先过门再采纳
# ══════════════════════════════════════════════════════════

def test_gate_all_splits_passed_and_rejected(ev):
    """★★★ 意图: 过门/被拒分流，且状态被更新。"""
    good = ev.diagnose([_sig()])["proposals"]
    bad = [_p(proposal_id="P_bad", target="config/anchors/dev.json")]
    r = ev.gate_all(good + bad)
    assert r["n_gated"] == 1
    assert r["n_rejected"] == 1
    assert good[0].state == "gated"
    assert bad[0].state == "rejected"


def test_draft_is_not_adopted():
    """★★★ 意图: draft 状态不叫采纳（状态机不是装饰）。"""
    p = _p()
    assert p.state == "draft"
    assert "adopted" not in p.state


def test_gated_is_not_implemented(ev):
    """★★★ 意图: gated ≠ 已落地（约束 1: 先过门后落地）。"""
    ev.gate_all(ev.diagnose([_sig()])["proposals"])
    p = ev.proposals[0]
    assert p.state == "gated"
    assert "implement" not in p.state


# ══════════════════════════════════════════════════════════
# ★★ 约束 3 · 必须两组 split
# ══════════════════════════════════════════════════════════

def test_in_only_is_blocked_not_adopted():
    """★★★★★ 核心测试: 只有 in-sample ⇒ **blocked**，绝不采纳。

    ★★★★ 依据 2606.09498 原文: Δ_in ≥ 0 ∧ Δ_ho ≥ 0
    ★★★ 而 2606.14249 记录: 只用一组数据曾导致 −14.0%
      （用自己的实验证伪了自己的门）⇒⇒⇒ 所以这里必须挡住
    """
    p = _p()
    r = Evolver.accept(p,
                       baseline={"in_score": 0.4, "held_out_score": None},
                       current={"in_score": 0.6, "held_out_score": None})
    assert r["decision"] == "blocked"
    assert "test split" in r["why"]
    assert r["delta_in"] == pytest.approx(0.2), "增量须由 accept 自己算"


def test_both_splits_passing_gives_fifth_state():
    """★★★ 意图: 两组都不退化 ⇒ adopted_not_implemented（第五态）。

    ★★ 不是 "adopted" —— 因为落地还没做（R14: 未采用 ≠ 通过）
    """
    p = _p()
    r = Evolver.accept(p,
                       baseline={"in_score": 0.4, "held_out_score": 0.3},
                       current={"in_score": 0.6, "held_out_score": 0.5})
    assert r["decision"] == "adopted_not_implemented"
    assert r["delta_in"] == pytest.approx(0.2)
    assert r["delta_ho"] == pytest.approx(0.2)


def test_regression_in_either_split_rejects():
    """★★★★ 意图: 任一 split 退化 ⇒ 拒（Δ_in ≥ 0 ∧ Δ_ho ≥ 0）。"""
    p = _p()
    # ★★ 两个方向各退化一次（Δ_in ≥ 0 ∧ Δ_ho ≥ 0 是「与」）
    r1 = Evolver.accept(p,
                        baseline={"in_score": 0.5, "held_out_score": 0.5},
                        current={"in_score": 0.6, "held_out_score": 0.4})
    r2 = Evolver.accept(p,
                        baseline={"in_score": 0.5, "held_out_score": 0.3},
                        current={"in_score": 0.4, "held_out_score": 0.5})
    assert r1["decision"] == "rejected", "held-out 退化 ⇒ 拒"
    assert r2["decision"] == "rejected", "in-sample 退化 ⇒ 拒"


def test_no_improvement_is_rejected():
    """★★★★ 意图: 两组都没退化但也**没改进** ⇒ 拒（空过不采纳）。

    ★★ 依据 2606.09498 Algorithm 1 第 13 行**原文**:
      `if Δ_in ≥ 0 and Δ_ho ≥ 0 and max(...) > 0`
    ⇒⇒ ★★ 我初版漏了第三个条件 —— 那正是本条测试抓到的
    """
    p = _p()
    r = Evolver.accept(p,
                       baseline={"in_score": 0.5, "held_out_score": 0.5},
                       current={"in_score": 0.5, "held_out_score": 0.5})
    assert r["decision"] == "rejected"
    assert "max" in r["why"]


def test_unevaluated_is_not_adopted():
    """★★★ 意图: 未评价 ≠ 通过。"""
    r = Evolver.accept(_p(),
                       baseline={"in_score": None, "held_out_score": 0.5},
                       current={"in_score": 0.5, "held_out_score": 0.5})
    assert r["decision"] == "not_evaluated"


def test_stats_reports_adopt_now_reachable():
    """★★★★ 意图: R28 起 adopt 可达（test split 已落地）。

    ★★★ R24/R27 时这里写的是「unreachable adopt」
      ⇒★ ⇒★ 那条测试若不改，就会在能力提升后**继续要求不可达**
        ⇒⇒ ⇒★ 过时的断言会阻止能力演进 —— 已按新事实重写
    """
    st = Evolver().stats()
    assert "unreachable" not in st["★"], "adopt 现已可达"
    assert "Δ_ho" in st["★"]


def test_adopt_is_reachable_with_real_splits():
    """★★★★★ 实证: 用真实 judge 的两组分数，adopt 真能发生。"""
    from dwc.organs.judge import Judge
    j = Judge()
    # ★★ 两组 split 各用自己的观测 —— 因为它们任务集不同
    #   ⇒ 而我第一版用 dev 的观测去判 test ⇒ 全未评价 ⇒ pass_rate=None
    #   ⇒⇒ ★ 那正是「不许用 dev 顶替 test」在起作用
    d_obs = {"reasoning_001": {"answer": "pivot 递归 最坏"},
             "reasoning_002": {"answer": "一致性 可用性 分区容错"}}
    t_obs = {"test_reasoning_001":
             {"answer": "哈希冲突可用链地址或开放寻址解决"},
             "test_reasoning_002":
             {"answer": "进程有独立地址空间，线程共享地址空间以实现并发"}}
    d = j.score("dev", d_obs)
    t = j.score("test", t_obs)
    assert d["pass_rate"] is not None and t["pass_rate"] is not None, \
        "两组都必须有真实分数才能谈约束 3"
    r = Evolver.accept(
        _p(),
        {"in_score": d["pass_rate"], "held_out_score": t["pass_rate"]},
        {"in_score": d["pass_rate"] + 0.1,
         "held_out_score": t["pass_rate"] + 0.1})
    assert r["decision"] == "adopted_not_implemented", \
        "两组都有分数且都改进 ⇒ 采纳（第五态）"
    assert r["delta_in"] > 0 and r["delta_ho"] > 0


def test_dev_observations_cannot_substitute_for_test(j=None):
    """★★★★★ 意图: dev 的观测**不能**拿来判 test（两组不可混用）。

    ★★★ 这是 locked split 的实际保护效果：
      若用 dev 的观测判 test ⇒ test 全未评价 ⇒ pass_rate=None
      ⇒⇒ ★★ 分子分母就不同源了 ⇒ 回归检测形同虚设
    """
    from dwc.organs.judge import Judge
    jj = Judge()
    t = jj.score("test", {"reasoning_001": {"answer": "pivot"}})
    assert t["not_evaluated"] == t["n_tasks"]
    assert t["pass_rate"] is None


# ══════════════════════════════════════════════════════════
# 职责边界
# ══════════════════════════════════════════════════════════

def test_evolver_does_not_judge_or_apply(ev):
    """★★★ 意图: evolver 不判分、不落地。"""
    for banned in ("score", "judge", "apply", "commit", "deploy",
                   "write_file", "land"):
        assert not hasattr(ev, banned), \
            "evolver 出现 %r —— 判分属 judge、落地属 APPLIER" % banned


def test_mutator_rules_are_data():
    """★★ 意图: 失败签名→提案的映射是**数据**（可门检/可审计）。"""
    m = Mutator()
    assert isinstance(m.RULES, dict)
    assert len(m.known_signatures()) == len(m.RULES)
    for k, v in m.RULES.items():
        # ★★★ R52 · 旧断言**锁死了具体签名集合** ⇒ 种子一改就该红,
        #   却被 `or True` 掩着（假绿）—— 实测差异:
        #   旧期望 E_OFF_BY_ONE/code_repair/average… 而实际是
        #     E_VALUE:wrong_magnitude:sum_first_n /
        #     E_ZERO_DIV:wrong_magnitude:average /
        #     E_NO_RESULT:abstained_or_missing:factorial
        #   ⇒ ⇒★ **断言方向错了**: docstring 本意是「映射是**数据**」
        #     （可门检/可审计）⇒ 该验**结构**, 不是锁可变的值
        #     （锁值 ⇒ 种子一变就红 ⇒ 有人会去改断言迁就 → 再加 or True）
        _parts = k.split(":")
        assert len(_parts) == 3 and all(_parts), (
            "★ key 必须是 `c:q:fn` 三段且每段非空, 实得 %r" % k)
        assert set(Mutator.RULE_ENTRY_FIELDS) <= set(v), (
            "★ value 必须含 Mutator.RULE_ENTRY_FIELDS 全部字段, 缺 %s"
            % sorted(set(Mutator.RULE_ENTRY_FIELDS) - set(v)))
        assert v["target_layer"] in ("assets", "architecture"), (
            "★ target_layer 只两值, 实得 %r" % v["target_layer"])
        assert (v["component"] in COMPONENT_VOCAB
             or v["component"] in K_META)
        assert v["rationale"].strip()


def test_mutator_returns_none_for_unknown():
    """★★★ 意图: 未知签名 ⇒ None（不硬编一个提案）。"""
    assert Mutator().propose(_sig(c="NOPE", q="nope", m="nope")) is None


# ══════════════════════════════════════════════════════════
# ★★★ 闭环实证：带 bug 的实现必须让分数掉下来
# ══════════════════════════════════════════════════════════

def test_broken_implementation_lowers_score():
    """★★★★★ 闭环实证: 真跑带 bug 的实现 ⇒ judge 判 fail。

    ★★★ 这是全套东西"能进化"的前提:
      若分数永远满分 ⇒ 进化闭环是空的
    """
    from dwc.organs.judge import Judge
    from dwc.organs.actor import Actor, Receipt

    j = Judge()
    a = Actor()
    ns = {}
    exec(compile("def sum_first_n(n):\n    return sum(range(1, n))",
                 "<broken>", "exec"), ns)
    fn = ns["sum_first_n"]
    calls = []

    def run(task):
        args = eval(task["args"], {"__builtins__": {}}, {})
        v = fn(args)
        calls.append([args, v])
        return Receipt(ok=True, detail={"value": v}, verified=True)

    for c in j.anchors["code_fix_001"]["checks"]:
        a.act({"task_id": "code_fix_001", "kind": "code_repair",
               "fn": "sum_first_n", "args": c["args"]}, run,
              expected={"value": c["expected"]},
              decision={"source": "heuristic", "why": "broken"})
    v = j.evaluate("code_fix_001", "dev",
                   observed={"sum_first_n": calls})
    assert v.success is False, "off-by-one 必须被判 fail"


def test_fixed_implementation_passes():
    """★ 对照组: 正确实现 ⇒ pass（证明上一条不是恒 fail）。"""
    from dwc.organs.judge import Judge
    from dwc.organs.actor import PureFunctionExecutor

    j = Judge()
    ex = PureFunctionExecutor("sum_first_n")
    calls = []
    for c in j.anchors["code_fix_001"]["checks"]:
        ex({"task_id": "x", "fn": "sum_first_n", "args": c["args"]})
        import dwc.organs.judge as J
        calls.append([J._as_literal(c["args"]), ex.calls[-1][1]])
    v = j.evaluate("code_fix_001", "dev", observed={"sum_first_n": calls})
    assert v.success is True


def test_failure_signature_q_is_the_changed_object():
    """★★★★ 意图: 失败签名的 q 是**被改对象**，不是 task_id。

    ★★★ R27 闭环实测暴露的契约不一致:
      actor 产出 q='code_fix_003'（任务编号）
      evolver 规则要 q='factorial'（函数名）⇒⇒ 提案匹配不上
    """
    from dwc.organs.actor import Actor, Receipt
    a = Actor()

    class Reject:
        def __call__(self, t):
            return Receipt(ok=False, detail={"error_code": "E_NO_BASE"},
                           verified=True)

    tr = a.act({"task_id": "code_fix_003", "kind": "code_repair",
                "fn": "factorial", "args": "5"}, Reject())
    assert tr.failure_signature["q"] == "factorial", \
        "q 必须是函数名（被改对象），不是任务编号"
    assert tr.failure_signature["m"] == "code_repair"


def test_proposal_matches_signature_from_trace():
    """★★★★★ 闭环: **judge 的**失败签名 ⇒ evolver 能提出提案。

    ★★★★ R30 方向修正（R27 那版测错了方向）:
      R27 版测的是 `actor 的签名 → evolver`，
      而原文 φ(r_i) 的 **r_i 是 verifier 结果**
        ⇒⇒ ⇒★ evolver 只该收 **verifier 层**的签名（judge 产）
          ⇒⇒ ⇒★★ actor 的签名 c 来自**回执 error_code**（执行层）
            ⇒ 那是 trace 里诊断执行问题用的，**不是** evolver 输入
      ⇒⇒ ⇒★★★ 而 R27 那版把 actor 签名喂给 diagnose
        ⇒ 它用 error_code 当 c ⇒ 与 RULES 的 verifier 值域对不上
          ⇒⇒ 一旦 RULES 改对（R30），它就**测不出真实契约**了

    ⇒ ⇒★ 本条现在测的是**真实闭环**方向，并显式锁住两层不混用
    """
    from dwc.organs.judge import Judge
    j = Judge()
    # ★ 真实闭环: 带 bug 的实现 → verifier 拒绝 → judge 产签名
    v = j.evaluate("code_fix_001", "dev",
                   observed={"sum_first_n": [[3, 3], [5, 10]]})
    assert v.success is False
    sig = v.failure_signature
    assert sig is not None, "judge 必须产签名（R30 的根因修复）"
    # ★ 签名是 verifier 层（fn 已带定位维度）
    assert sig["c"] == "E_VALUE" and sig["fn"] == "sum_first_n"
    # ★★ 它必须**查得到**规则（这是闭环的关键）
    d = Evolver().diagnose([dict(sig)])
    assert len(d["proposals"]) == 1, \
        "verifier 签名必须对上 evolver 的规则（R30: 键=c:q:fn）"
    assert d["proposals"][0].target == "sum_first_n"


def test_actor_signature_is_executor_layer_not_verifier():
    """★★★★★ 意图: actor 签名**不是** evolver 的输入（两层不混用）。

    ★★★★ 依据: 原文 c = "**verifier**-level cause"
      ⇒ actor 的 c 来自回执 error_code ⇒ 属**执行层**
      ⇒⇒ 而 evolver 收的是 verifier 层 ⇒ 两者 c 值域不同，不能互换
      ⇒⇒ ⇒★ 显式锁住，否则将来有人会把 actor 签名喂给 diagnose
        然后"修 RULES 键去迁就它" ⇒ 那会让真值分类被污染
    """
    from dwc.organs.actor import Actor, Receipt
    a = Actor()

    class Reject:
        def __call__(self, t):
            return Receipt(ok=False,
                           detail={"error_code": "E_EXEC_FAIL"},
                           verified=True)

    tr = a.act({"task_id": "code_fix_001", "kind": "code_repair",
                "fn": "sum_first_n", "args": "3"}, Reject())
    sig = tr.failure_signature
    assert sig["sig_layer"] == "executor", \
        "actor 签名必须标注为 executor 层"
    assert sig["fn"] == "sum_first_n", "定位维度必须有"
    # ★★ 它的 c 来自 error_code，而 verifier 层的 c 来自差异分类
    assert sig["c"] == "E_EXEC_FAIL"
    # ★ 而 judge 对同一任务给的是另一套 c（差异分类）
    from dwc.organs.judge import Judge
    v = Judge().evaluate("code_fix_001", "dev",
                         observed={"sum_first_n": [[3, 3], [5, 10]]})
    assert v.failure_signature["c"] == "E_VALUE"
    assert v.failure_signature.get("sig_layer") != "executor", \
        "judge 产的是 verifier 层（默认无 executor 标）"

def test_constraint4_single_change_is_enforced():
    """★★★★★ R44 · 约束 4「一个提案只改一处」**真的拦**。

    ★★ 背景（R44 核出的声称 vs 实现）:
      `Proposal` docstring 原写「所以我**加了** `_assert_single_change()`
      在构造时就拦」—— 而全库实测**只有那句 docstring**（函数不存在）
      ⇒⇒ ⇒★ 声称有、实现 0 ⇒ 约束 4 根本没被强制
      ⇒ 而它是**归因的前提**（2606.09498: 「一簇对应一处干预」，
        多处 ⇒ 测量无法归因）—— 所以接线 ℒ_t 前必须先补
    """
    import pytest
    from dwc.organs.evolver import Proposal, EvolverError
    base = dict(component="prompt", rationale="依据",
                failure_signature={"k": "v"})
    # ① 合法: 单 target + 单行 patch
    p = Proposal(proposal_id="ok", target="fibonacci",
                 patch="return 0", **base)
    assert p._assert_single_change() is None
    # ② target 含逗号 = 多目标 ⇒ 拒
    with pytest.raises(EvolverError) as e1:
        Proposal(proposal_id="a", target="foo,bar", patch="x", **base)
    assert "多处变更" in str(e1.value)
    # ③ target 含分号 = 多语句 ⇒ 拒
    with pytest.raises(EvolverError):
        Proposal(proposal_id="b", target="foo;bar", patch="x", **base)
    # ④ patch 含多个 @@ = 多 hunk ⇒ 拒
    with pytest.raises(EvolverError) as e2:
        Proposal(proposal_id="c", target="foo",
                 patch="@@ -1 +1 @@\na\n@@ -5 +5 @@\nb", **base)
    assert "hunk" in str(e2.value)
    # ⑤ 多行 patch **合法**（改一个函数多行 = 还是一处）
    Proposal(proposal_id="d", target="foo",
             patch="def foo():\n    return 0", **base)
    # ⑥ 空 target / 空 patch ⇒ 拒
    with pytest.raises(EvolverError):
        Proposal(proposal_id="e", target="", patch="x", **base)
    with pytest.raises(EvolverError):
        Proposal(proposal_id="f", target="foo", patch="   ", **base)



# ══════════════════════════════════════════════════════════
# R78 批3-D（裁决②: 加）· Proposal.direction 字段
# ══════════════════════════════════════════════════════════

def test_proposal_direction_field():
    """★ None 合法（未标注不冒充）· 三成员经 ensure_direction · 未知值拒。"""
    assert _p().direction is None                    # 默认未标注
    from dwc.organs.direction import EvolutionDirection
    for dname in (EvolutionDirection.FORWARD.value,
                  EvolutionDirection.LATERAL.value,
                  EvolutionDirection.REVERSE.value):
        assert _p(direction=dname).direction == dname
    with pytest.raises(Exception) as e:              # DirectionError
        _p(direction="lateral")                      # 大小写/变体拒
    assert "方向值" in str(e.value)
    with pytest.raises(Exception):
        _p(direction="sideways")                     # 未知值拒
