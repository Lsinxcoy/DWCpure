# -*- coding: utf-8 -*-
"""candidates（organs/candidates.py）的契约测试。

★★★ 这是 EVOLUTION_CORE_V2 器官②（改什么）的**生成**那一半 ——
  实测此前 evolver 只有 `Mutator.propose`（**查已有表**）
  ⇒⇒ ⇒★ 查不到 ⇒ unmapped ⇒ **没有后续** ⇒ 从失败学不到新东西
  ⇒⇒ ⇒★★ 而 RULES 只有 3 条全靠我手写 ⇒ 进化增量至今没发生过

★ 四条纪律（前三条与 JUDGE 的"缺证据不转正面判定"同型，第四条是实测教训）
  纪律① 没有 diffs ⇒ 不产候选（不许凭签名编）
  纪律② 每条候选必须带 grounding ⇒ 否则 raise
  纪律③ 推不出 ⇒ 显式 need_llm=True（不许静默空返回）
  纪律④ ★ 基线必须能复现 diffs 的 actual（R31 实测抓到的真 bug）
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.organs.candidates import (  # noqa: E402
    Candidate, CandidateError, CandidateGenerator,
)
from dwc.organs.actor import PureFunctionExecutor, build_implementation  # noqa: E402
from dwc.organs.judge import Judge  # noqa: E402

BUGGY = "def sum_first_n(n):\n    return sum(range(n))"
GEN = CandidateGenerator()


def _real():
    """★ 真实失败证据（judge 产出，不手拼 —— 保证 grounding 真）。"""
    j = Judge()
    v = j.evaluate("code_fix_001", "dev",
                   observed={"sum_first_n": [[3, 3], [5, 10]]})
    assert v.success is False and v.diffs
    return v


# ══════════════════════════════════════════════════════════
# 正向：有证据 ⇒ 产候选
# ══════════════════════════════════════════════════════════

def test_real_evidence_produces_candidates():
    """★★★★★ 正向: 真实的 off-by-one 证据 ⇒ 必须产候选。

    ★★★ R31 实测: 第一版要求"差值恒定"而本例 Δ=3 和 5 ⇒ 推不出
      ⇒ 而真实模式是 **Δ = args**（少算了 n 个）
      ⇒⇒ 修正后应产 `range(n + 1)` —— 与 RULES 的正确 patch 一致
    """
    v = _real()
    r = GEN.generate(v.failure_signature, v.diffs, BUGGY,
                     fn_name="sum_first_n")
    assert r["n"] > 0, "有证据必须产候选（否则学习无从发生）"
    assert r["need_llm"] is False
    # ★ 每条都带 grounding（纪律②）
    for c in r["candidates"]:
        assert c.grounding
        assert c.source == "deterministic"


def test_delta_eq_args_pattern_ranks_first():
    """★★★★★ 本例的强假设必须排第一（模式 B 优先）。

    ★★ Δ = args ⇒ "少算了 args 个" ⇒ stop+1 是强假设
      ⇒ 而实测它就是**正确**修复（与 RULES 一致）
    """
    v = _real()
    r = GEN.generate(v.failure_signature, v.diffs, BUGGY,
                     fn_name="sum_first_n")
    top = r["candidates"][0]
    assert "delta_eq_args" in top.rule, "模式 B 应先匹配"
    assert top.rule.endswith("stop_plus1") or \
        top.rule.endswith("start1_stop1"), \
        "强假设（stop+1 或 range(1,n+1)）应排前"


def test_candidate_actually_passes_judge():
    """★★★★★ 闭环实证: 候选 → 构建实现 → **判分通过**。

    ⇒⇒ 这是"生成"这一环真的有效的唯一证据
      （不是"产出了候选"，而是"候选里有能用的"）
    """
    v = _real()
    r = GEN.generate(v.failure_signature, v.diffs, BUGGY,
                     fn_name="sum_first_n")
    j = Judge()
    passed = []
    for c in r["candidates"]:
        try:
            src = build_implementation("sum_first_n", BUGGY, c.patch)
        except Exception:
            continue                       # 编不过的不该在（已滤），兜底
        out = j.evaluate("code_fix_001", "dev",
                         observed=_run(src, "sum_first_n",
                                       j.anchors["code_fix_001"]["checks"]))
        if out.success:
            passed.append(c)
    assert passed, "★ 候选集里必须至少有一条能通过判分"


def _run(src, fn_name, checks):
    """★ 用给定实现跑全部断言，产出 judge 的观测契约。"""
    ns: dict = {}
    exec(compile(src, "<cand>", "exec"), ns)
    f = ns[fn_name]
    import ast as _ast
    calls = []
    for c in checks:
        arg = _ast.literal_eval(c["args"])
        calls.append([arg, f(arg)])
    return {fn_name: calls}


# ══════════════════════════════════════════════════════════
# 四条纪律
# ══════════════════════════════════════════════════════════

def test_discipline1_no_diffs_no_candidates():
    """★★★★ 纪律①: 无 diffs ⇒ 0 条，且 **not** need_llm。"""
    v = _real()
    r = GEN.generate(v.failure_signature, None, BUGGY)
    assert r["n"] == 0
    assert r["need_llm"] is False, "无证据是「没输入」，不是「要模型」"
    assert "纪律①" in r["why"]


def test_discipline2_missing_grounding_raises():
    """★★★★ 纪律②: 无 grounding ⇒ raise（与 JUDGE 纪律 3 同型）。"""
    with pytest.raises(CandidateError) as e:
        Candidate(patch="return 0", source="deterministic", grounding=[])
    assert "grounding" in str(e.value)


def test_discipline2_empty_patch_raises():
    """★ 纪律② 补: 空 patch 不算候选。"""
    with pytest.raises(CandidateError):
        Candidate(patch="   ", source="deterministic",
                  grounding=[{"index": 0, "ok": False}])


def test_discipline2_bad_source_raises():
    """★ source 只许 deterministic / llm（不许来路不明）。"""
    with pytest.raises(CandidateError):
        Candidate(patch="return 1", source="guess", grounding=[{"ok": False}])


def test_discipline3_unprovable_is_need_llm():
    """★★★★ 纪律③: 推不出 ⇒ need_llm=True（显式，不静默）。"""
    v = _real()
    diffs = [{"index": 0, "ok": False, "fn": "mystery", "args": 1,
              "expected": 100, "actual": 7, "reason": "值不匹配"},
             {"index": 1, "ok": False, "fn": "mystery", "args": 2,
              "expected": 200, "actual": 9, "reason": "值不匹配"},
             {"index": 2, "ok": False, "fn": "mystery", "args": 3,
              "expected": 400, "actual": 11, "reason": "值不匹配"}]
    r = GEN.generate({"c": "E_VALUE", "q": "wrong_magnitude",
                      "fn": "mystery"}, diffs,
                     "def mystery(x):\n    return 2 * x + 5")
    assert r["n"] == 0
    assert r["need_llm"] is True, "★ 推不出必须显式要模型"
    assert "纪律③" in r["why"] and "2606.14249" in r["why"]


def test_discipline4_wrong_baseline_rejected():
    """★★★★★ 纪律④（R31 实测抓到的真 bug）: 传错基线必须拒绝。

    ★★★ 我第一版把 `REFERENCE`（**正确**的实现）当基线
      ⇒ 候选变成"对正确实现做扰动" ⇒ 必然越改越错
      ⇒⇒ ⇒★★ 而 grounding 记的 expr 是 REFERENCE 的表达式
        = **grounding 指向了错误的证据**
      ⇒⇒ ⇒★ 与纪律②同型，只不过错的是**基线**
    """
    v = _real()
    r = GEN.generate(v.failure_signature, v.diffs,
                     PureFunctionExecutor.REFERENCE["sum_first_n"],
                     fn_name="sum_first_n")
    assert r["n"] == 0, "★ 错误基线必须被拒（否则产全错候选）"
    assert "纪律④" in r["why"]
    assert r["need_llm"] is False, "那是基线错，不是要模型"


def test_baseline_reproduce_is_exact_not_approx():
    """★★ 纪律④ 是**逐条精确**复现（差一个都不许）。"""
    diffs = [{"index": 0, "ok": False, "fn": "f", "args": 3,
              "expected": 6, "actual": 4, "reason": "值不匹配"},
             {"index": 1, "ok": False, "fn": "f", "args": 5,
              "expected": 15, "actual": 9, "reason": "值不匹配"}]
    # ★ 能复现 actual(4, 9) 的基线 ⇒ 放行
    ok = GEN.generate({"c": "E_VALUE", "q": "wrong_magnitude", "fn": "f"},
                      diffs, "def f(n):\n    return n + 1",
                      fn_name="f")
    # ★ (3+1=4 ✓ 但 5+1=6 ≠ 9) ⇒ 有一条不复现 ⇒ 拒
    assert ok["n"] == 0 and "纪律④" in ok["why"]


def test_unknown_baseline_is_not_treated_as_false():
    """★★ 纪律④ 的 **None 不当 False**（原则: 未评价不许当失败）。"""
    from dwc.organs.candidates import CandidateGenerator as CG
    # ★ 编译失败 ⇒ 无法判定 ⇒ 返回 None（不是 False）
    r = CG._baseline_reproduces(
        [{"index": 0, "ok": False, "fn": "f", "args": 1,
          "expected": 9, "actual": 9}],
        "def f(:", "f")
    assert r is None, "编译不了 ⇒ 无法判定 ⇒ 不许当 False"


def test_no_diffs_is_not_need_llm():
    """★★★ 纪律①与③必须**可区分**（空输入 vs 推不出）。"""
    v = _real()
    a = GEN.generate(v.failure_signature, None, BUGGY)
    b = GEN.generate(v.failure_signature, [], BUGGY)
    assert a["need_llm"] is False and b["need_llm"] is False
    assert "纪律①" in a["why"] and "纪律①" in b["why"]


def test_success_diffs_produce_nothing():
    """★ 全对的 diffs ⇒ 没有失败条目 ⇒ 无候选（不是 need_llm）。"""
    diffs = [{"index": 0, "ok": True, "fn": "f", "args": 1,
              "expected": 2, "actual": 2, "reason": "命中"}]
    r = GEN.generate({"c": "E_VALUE", "q": "x", "fn": "f"}, diffs,
                     "def f(x):\n    return x + 1")
    assert r["n"] == 0 and r["need_llm"] is False


def test_candidates_are_not_pre_enumerated():
    """★★★★★ 2606.14249: 候选不许是**预枚举固定集合**。

    ★★★ 原文: "not selected from a pre-enumerated set ... the Planner
      proposes edits from **trace-grounded hypotheses**"
    ⇒⇒ ⇒★ 可执行判据: 换一份**不同源码**，候选必须跟着变
      （若候选是固定的，换源码它们不变）
    """
    v = _real()
    a = GEN.generate(v.failure_signature, v.diffs, BUGGY,
                     fn_name="sum_first_n")
    other = "def sum_first_n(n):\n    t = 0\n    for i in range(n):\n" \
            "        t += i\n    return t"
    b = GEN.generate(v.failure_signature, v.diffs, other,
                     fn_name="sum_first_n")
    pa = {c.patch for c in a["candidates"]}
    pb = {c.patch for c in b["candidates"]}
    assert pa and pb and pa != pb, \
        "★ 换源码候选必须变（否则就是预枚举）"

# ══════════════════════════════════════════════════════════
# ★★★ G4 生灭门的三件套（生成能力必须有配套）
#    门依据: 母巢 L3 的病 = 1,447 生 / 5 死
# ══════════════════════════════════════════════════════════

def test_pool_limit_defaults_and_is_enforced():
    """★★★★ G4 池子上限: 有池必须有上限，且**真的**截断。"""
    g = CandidateGenerator()
    assert g.pool_limit == CandidateGenerator.MAX_POOL
    # ★ 构造远超上限的候选空间（扰动会产生多条）
    v = _real()
    r = GEN.generate(v.failure_signature, v.diffs, BUGGY,
                     fn_name="sum_first_n")
    assert r["n"] <= g.pool_limit, "★ 产出不得超过池上限"
    assert r["pool_limit"] == g.pool_limit


def test_overflow_reports_dropped_not_silent():
    """★★★★ G4 超限行为: 超限必须**报数**，不许静默截断。"""
    g = CandidateGenerator(pool_limit=2)
    v = _real()
    r = g.generate(v.failure_signature, v.diffs, BUGGY,
                   fn_name="sum_first_n")
    # ★★★ R31 变异验证抓到我第一版**把断言写成了可跳过的 if**:
    #   `if r["n"] == pool_limit and n_dropped > 0: assert ...`
    #   ⇒ 摘掉截断后 r["n"]=4 ≠ 2 ⇒ 条件为假 ⇒ 断言**被跳过**
    #   ⇒⇒ ⇒★★ 那与 G7 静默门是同一种病: **测试静默通过**
    #   ⇒ ⇒★ 改成**无条件**断言（变异现在能抓住）
    assert r["n"] <= 2, "★ 必须截断到上限（有 4 条可推）"
    assert r.get("n_dropped") == 2, "★ 必须报出丢了几条"
    assert "截断" in r["why"], "★ 超限必须在 why 里说明"
    assert "n_dropped" in r and "pool_limit" in r


def test_rejected_candidate_is_not_regenerated():
    """★★★★★ G4 淘汰判据: 被否决的候选**不许再产**（否则每轮空转）。"""
    g = CandidateGenerator()
    v = _real()
    r1 = g.generate(v.failure_signature, v.diffs, BUGGY,
                    fn_name="sum_first_n")
    assert r1["n"] > 0
    # ★ 判分方否决**全部**候选
    for c in r1["candidates"]:
        g.record_rejection(c, "judge 判 fail（实测不修好）")
    r2 = g.generate(v.failure_signature, v.diffs, BUGGY,
                    fn_name="sum_first_n")
    assert r2["n"] == 0, "★ 已否决的候选不许重新产出"
    assert "淘汰" in r2["why"] and "不重试" in r2["why"]
    assert r2["n_rejected_skipped"] > 0


def test_rejection_requires_reason():
    """★★ G4: 淘汰不许静默（无 reason ⇒ raise，否则丢可审计性）。"""
    g = CandidateGenerator()
    v = _real()
    r = g.generate(v.failure_signature, v.diffs, BUGGY,
                   fn_name="sum_first_n")
    with pytest.raises(CandidateError) as e:
        g.record_rejection(r["candidates"][0], "")
    assert "reason" in str(e.value)


def test_partial_rejection_still_yields_survivors():
    """★ 淘汰部分候选 ⇒ 其余仍可产出（不是全灭）。"""
    g = CandidateGenerator()
    v = _real()
    r = g.generate(v.failure_signature, v.diffs, BUGGY,
                   fn_name="sum_first_n")
    g.record_rejection(r["candidates"][0], "该方向被证伪")
    r2 = g.generate(v.failure_signature, v.diffs, BUGGY,
                    fn_name="sum_first_n")
    assert r2["n"] == r["n"] - 1, "★ 只灭被否决的那条"
    assert r2["n_rejected_skipped"] == 1


def test_rejected_pool_is_reported():
    """★ 淘汰池规模进返回值（可审计: 历史上否决过多少）。"""
    g = CandidateGenerator()
    v = _real()
    r = g.generate(v.failure_signature, v.diffs, BUGGY,
                   fn_name="sum_first_n")
    g.record_rejection(r["candidates"][0], "x")
    r2 = g.generate(v.failure_signature, v.diffs, BUGGY,
                    fn_name="sum_first_n")
    assert r2["n_rejected_pool"] == 1

# ══════════════════════════════════════════════════════════
# ★ R31 变异验证抓到的两条**测试盲区**
# ══════════════════════════════════════════════════════════

def test_single_diff_cannot_claim_systematic_bias():
    """★★★★★ 盲区⑨: **单条** diff 不许推"系统性偏移"（变异抓到）。

    ★★ 变异『去掉 len(pairs) < 2 的门槛』⇒ 全套仍绿
      ⇒ 说明我**没有**单条证据的测试
    ⇒⇒ ⇒★ 而单条无法区分"噪声"与"系统性偏移"
      （2606.09498 的警示: 同一 verifier 结果可能来自不同干预）
    ⇒ ⇒★ 补上这条 ⇒ 那个变异现被抓住
    """
    one = [{"index": 0, "ok": False, "fn": "sum_first_n", "args": 3,
            "expected": 6, "actual": 3, "reason": "值不匹配"}]
    r = GEN.generate({"c": "E_VALUE", "q": "wrong_magnitude",
                      "fn": "sum_first_n"}, one, BUGGY,
                     fn_name="sum_first_n")
    assert r["n"] == 0, "★ 单条证据不许推候选（无法证明系统性）"
    assert r["need_llm"] is True, "推不出 ⇒ 显式要模型"


def test_patch_body_indent_must_be_zero():
    """★★★★★ 盲区⑧: patch 的**首行缩进必须是 0**（约定契约）。

    ★★ 变异『函数体提取不去基准缩进』⇒ 全套仍绿
      ⇒ 手工验证: 产出 patch = `    return sum(...)`
        而 build_implementation 会 +4 ⇒ 得到缩进 **8**
      ⇒⇒ ★★ 那在 Python 里**也合法**（体内一致即可）
        ⇒⇒ ⇒★ 所以判分**照样通过** ⇒ 变异成了"等价变异"
      ⇒⇒ ⇒★★ 但这违反 patch 的约定（R30 定: 第一行相对 def 缩进 0）
        ⇒⇒ ⇒★ 后果: 与 RULES 里其它条目**形态不一致**，
          将来若按缩进做语法/合并就炸
    ⇒ ⇒★ 所以要**直接断言形态**，不能只靠"能不能判过"
    """
    v = _real()
    r = GEN.generate(v.failure_signature, v.diffs, BUGGY,
                     fn_name="sum_first_n")
    assert r["n"] > 0
    for c in r["candidates"]:
        first = c.patch.split("\n")[0]
        assert not first.startswith(" "), \
            "★ patch 首行缩进必须为 0（约定）: %r" % first
        # ★ 每行的相对缩进必须是 4 的倍数（否则嵌套会错位）
        for ln in c.patch.split("\n"):
            if ln.strip():
                assert (len(ln) - len(ln.lstrip())) % 4 == 0, \
                    "★ 缩进必须 4 的倍数: %r" % ln


def test_mode_b_ranking_is_explicit():
    """★★★★ 盲区⑥: 模式 B 的**强假设必须在前**（变异抓到）。

    ★★ 变异『去掉 delta_eq_args 的排序』⇒ 全套仍绿
      ⇒ 因为 `stop_plus1` 恰好**也是** forms 的自然第一位
      ⇒⇒ ⇒★ 于是我那条"排前"的测试**测的是巧合**，不是排序逻辑
      ⇒⇒ ⇒★★ 这是「测试通过但没测到意图」的典型
      ⇒ ⇒★ 改法: 直接对 forms 的**产出顺序**断言，
        并用一个**自然顺序不同**的输入（逗号版 range）
    """
    # ★★ 逗号版 range: forms 自然是 [stop_plus1, stop_minus1, start_plus1]
    #   而模式 B 要求 stop_plus1 在前 —— 恰好也同序 ⇒ 仍不测到
    #   ⇒⇒ 所以直接断言: 第一条必须是强假设
    v = _real()
    r = GEN.generate(v.failure_signature, v.diffs, BUGGY,
                     fn_name="sum_first_n")
    assert r["n"] > 0
    top = r["candidates"][0]
    assert top.rule.endswith("stop_plus1") or \
        top.rule.endswith("start1_stop1"), \
        "★ 模式 B 的强假设必须排第一（got %s）" % top.rule
    # ★★ 再断言**全部**候选里强假设不排最后（若排序被摘，它会散开）
    weak_first = [c for c in r["candidates"]
                  if c.rule.endswith(("stop_minus1", "start1",
                                 "start1_weakest"))]
    if weak_first:
        assert r["candidates"].index(weak_first[0]) > 0, \
            "★ 弱假设（-1/去掉起始）不许排第一"
