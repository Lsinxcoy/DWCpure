# -*- coding: utf-8 -*-
"""judge（organs/judge.py）的契约测试。

★★★ 为什么这个器官的测试最严
  judge 是**唯一**能给"成功"下定义的地方 ⇒ 它一旦塌缩，
  整套 DWC 的分数都是假的（2607.12790 实测: 评分器塌缩成 0.811 >
  认真 0.767 —— 而塌缩后的评分器比认真做还"好"）
  ⇒ 所以这里每个判据都配**阳性 + 阴性**两侧

★ 逐条:
  ① TRUTH_SOURCE 必须指向真实文件（原则 1 / 判据 G2）
  ② ★★ success=None 表示未评价，不许当 False 也不许当 True
  ③ 两种判据形态都能判（behavior / keyword_match）
  ④ ★ fallback 必须同契约 —— 拒 ARSI 的 structure_only
  ⑤ test split 未落地时必须 raise，不许用 dev 顶替
  ⑥ 保护组回归：未评价时返回 not_comparable 而非"通过"
  ⑦ agent 自报不许影响判定（三分离）
"""
from __future__ import annotations

import io
import json
import os
import sys
import tempfile

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.organs.judge import (  # noqa: E402
    SPLIT_DEV, SPLIT_TEST, SPLIT_TRAIN, TRUTH_NOT_BUILT, TRUTH_SOURCE,
    Judge, JudgeError, Verdict,
)


@pytest.fixture
def j():
    return Judge()


# ══════════════════════════════════════════════════════════
# ① TRUTH_SOURCE（判据 G2 / 原则 1）
# ══════════════════════════════════════════════════════════

def test_truth_source_dev_file_exists():
    """★★★ 意图: dev 真值源必须**真实存在**（声明了就得有）。"""
    cat, path = TRUTH_SOURCE[0]
    assert cat == "dev_anchors"
    assert os.path.exists(path), "dev 真值源不存在 ⇒ 违反原则 1"


def test_truth_source_declares_g2(j):
    """★★ 意图: 模块级 TRUTH_SOURCE 声明存在（G2 门靠它）。"""
    src = io.open(os.path.join(ROOT, "src/dwc/organs/judge.py"),
                  encoding="utf-8").read()
    assert "TRUTH_SOURCE" in src, "G2 真值门要求声明 TRUTH_SOURCE"


def test_test_split_declared_not_built():
    """★★★ 意图: test split 显式标记为**未落地**，不假装有。"""
    assert "test_sealed" in TRUTH_NOT_BUILT
    j = Judge()
    assert j.sealed is None, "test 未落地时不该有数据"


def test_missing_truth_source_raises(tmp_path):
    """★★ 意图: 真值源文件不存在必须 raise（不许返回空 dict）。"""
    with pytest.raises(JudgeError) as e:
        Judge(anchors_path=str(tmp_path / "nope.json"))
    assert "真值源" in str(e.value)


def test_self_check_lists_not_built(j):
    """★★ 意图: 自检必须区分"已验证"与"未落地"。"""
    sc = j.self_check()
    assert "dev_anchors" in sc["truth_source"]["verified"]
    assert "test_sealed" in sc["truth_source"]["not_built"]
    assert sc["test_built"] is False


# ══════════════════════════════════════════════════════════
# ②★★ 未评价 ≠ False / True
# ══════════════════════════════════════════════════════════

def test_not_run_gives_none_not_false(j):
    """★★★★ 意图: 没跑 ⇒ success=None，**不是** False。

    ★★★ ACTOR_DESIGN §4.5 的规则:「None 不许当 False 也不许当 True」
      ⇒ 若把 None 当 False，未跑的任务会被算成失败
      ⇒ 若当 True，未跑就是满分 —— 两种都错。
    """
    v = j.evaluate("code_fix_001", SPLIT_DEV, observed=None)
    assert v.success is None, "没跑必须是 None"
    assert v.missing == "observed"
    assert not v.is_pass()


def test_score_reports_pass_rate_none_when_all_unevaluated(j):
    """★★★★ 意图: 全未评价 ⇒ pass_rate=None（不是 0）。"""
    sc = j.score(SPLIT_DEV, {})
    assert sc["not_evaluated"] == sc["n_tasks"]
    assert sc["pass"] == 0 and sc["fail"] == 0
    assert sc["pass_rate"] is None, "未评价不许算成 0 分"


def test_none_not_counted_in_denominator(j):
    """★★★ 意图: 分母只算真正判过的（None 不进分母）。"""
    obs = {"reasoning_001": {"answer": "pivot 递归 最坏"}}
    sc = j.score(SPLIT_DEV, obs)
    assert sc["not_evaluated"] == sc["n_tasks"] - 1
    assert sc["pass_rate"] == 1.0, "只判了1条且通过 ⇒ 通过率 1.0"


def test_unevaluated_is_queryable(j):
    """★★ 意图: 未评价的判定可被查出（供门检）。"""
    j.evaluate("code_fix_001", SPLIT_DEV, observed=None)
    j.evaluate("reasoning_001", SPLIT_DEV,
               observed={"answer": "pivot 递归 最坏"})
    ue = j.unevaluated()
    assert len(ue) == 1
    assert ue[0]["task_id"] == "code_fix_001"


# ══════════════════════════════════════════════════════════
# ③ 两种判据形态
# ══════════════════════════════════════════════════════════

def test_keyword_match_all_keywords_required(j):
    """★★★ 意图: keyword_match 要求**全部**关键词命中。"""
    full = "快排最坏 O(n^2)：pivot 选到极值，递归深度达 n"
    v_ok = j.evaluate("reasoning_001", SPLIT_DEV, observed={"answer": full})
    assert v_ok.success is True
    missing = "快排最坏情况是 O(n^2)"
    v_no = j.evaluate("reasoning_001", SPLIT_DEV,
                      observed={"answer": missing})
    assert v_no.success is False, "缺关键词就该 fail"


def test_behavior_compares_actual_values(j):
    """★★★ 意图: behavior 形态比对**实测返回值**，不比对自报。"""
    obs = {"sum_first_n": [["3", "6"], ["5", "15"]]}
    v = j.evaluate("code_fix_001", SPLIT_DEV, observed=obs)
    assert v.success is True, "返回值与 golden 一致 ⇒ pass"
    obs_bad = {"sum_first_n": [["3", "5"], ["5", "14"]]}
    v2 = j.evaluate("code_fix_001", SPLIT_DEV, observed=obs_bad)
    assert v2.success is False, "返回值不符 ⇒ fail"


def test_behavior_missing_call_fails(j):
    """★★ 意图: 压根没调那个入参 ⇒ fail（不是未评价）。"""
    v = j.evaluate("code_fix_001", SPLIT_DEV,
                   observed={"sum_first_n": [["3", "6"]]})   # 缺 (5)
    assert v.success is False


def test_behavior_wrong_value_fails(j):
    """★★ 意图: 调了但值错 ⇒ fail。"""
    v = j.evaluate("code_fix_001", SPLIT_DEV,
                   observed={"sum_first_n": [["3", "6"], ["5", "WRONG"]]})
    assert v.success is False


def test_unknown_task_raises(j):
    """意图: 不在真值源里的任务必须 raise（不许凭空判）。"""
    with pytest.raises(JudgeError):
        j.evaluate("no_such_task", SPLIT_DEV, observed={})


# ══════════════════════════════════════════════════════════
# ④★★ fallback 必须同契约（JUDGE_DESIGN §3.3）
# ══════════════════════════════════════════════════════════

def test_fallback_structure_only_rejected(j):
    """★★★★ 意图: 拒接 ARSI 的 structure_only fallback。

    ★★★ JUDGE_DESIGN §3.3 原文:「任何 fallback 若不满足同契约，
      不许注册」⇒ 而 ARSI 的 fallback 是"结构检查"（有 def/return 就给分）
      ⇒⇒ 那不满足"判定任务是否解决" ⇒ 必须在注册处就拒。
    """
    with pytest.raises(JudgeError) as e:
        j.register_fallback("s", lambda t, o: True,
                            {"mode": "structure_only"})
    assert "structure_only" in str(e.value)


def test_fallback_without_contract_rejected(j):
    """★★ 意图: 无契约的 fallback 不许注册。"""
    with pytest.raises(JudgeError):
        j.register_fallback("s", lambda t, o: True, {})


def test_fallback_wrong_mode_rejected(j):
    """★★ 意图: mode 只能是 contract_equivalent。"""
    with pytest.raises(JudgeError):
        j.register_fallback("s", lambda t, o: True, {"mode": "whatever"})


def test_fallback_compliant_registers(j):
    """意图: 合规的 fallback 可注册。"""
    n = j.register_fallback("ok", lambda t, o: True,
                            {"mode": "contract_equivalent",
                             "covers": "task_actually_solved"})
    assert n in j.self_check()["fallbacks"]


# ══════════════════════════════════════════════════════════
# ⑤ test split 未落地
# ══════════════════════════════════════════════════════════

def test_test_split_raises(j):
    """★★★★ 意图: test 未落地时必须 raise，**不许用 dev 顶替**。

    ★★★ 若用 dev 顶替 ⇒ 保护组回归检测形同虚设
      （分子分母同源，改了哪边都算过）。
    """
    with pytest.raises(JudgeError) as e:
        j.evaluate("code_fix_001", SPLIT_TEST, observed={})
    assert "未落地" in str(e.value)


def test_test_split_score_reports_not_zero(j):
    """★★★ 意图: test 未落地时 score 返回"无法判分"而非 0 分。"""
    sc = j.score(SPLIT_TEST, {})
    assert sc["pass_rate"] is None
    assert sc["n_tasks"] == 0
    assert "未落地" in sc["★"]


def test_train_split_always_raises(j):
    """★★ 意图: train split 不存在（它按设计无标签）。"""
    with pytest.raises(JudgeError) as e:
        j.evaluate("code_fix_001", SPLIT_TRAIN, observed={})
    assert "train" in str(e.value)


# ══════════════════════════════════════════════════════════
# ⑥ 保护组回归（终止条件③ 的基础）
# ══════════════════════════════════════════════════════════

def test_regression_not_comparable_when_unevaluated(j):
    """★★★★ 意图: 任一侧有未评价 ⇒ not_comparable（不是"通过"）。"""
    base = j.score(SPLIT_DEV, {})
    r = j.regression_check(base, base)
    assert r["verdict"] == "not_comparable"
    assert "未评价" in r["why"], r["why"]


def test_regression_detected(j):
    """★★★ 意图: 实测分数下降 ⇒ 报 regression。"""
    ans = "pivot 递归 最坏"
    base_obs = {"reasoning_001": {"answer": ans},
                "reasoning_002": {"answer": "一致性 可用性 分区容错"}}
    base = j.score(SPLIT_DEV, base_obs)
    assert base["pass_rate"] == 1.0
    cur = j.score(SPLIT_DEV, {"reasoning_001": {"answer": ans},
                              "reasoning_002": {"answer": "不知道"}})
    r = j.regression_check(base, cur)
    assert r["verdict"] == "regression", "分数下降必须报回归"
    assert r["delta"] < 0


def test_regression_ok_when_equal(j):
    """意图: 分数持平 ⇒ ok。"""
    obs = {"reasoning_001": {"answer": "pivot 递归 最坏"}}
    base = j.score(SPLIT_DEV, obs)
    cur = j.score(SPLIT_DEV, obs)
    assert j.regression_check(base, cur)["verdict"] == "ok"


# ══════════════════════════════════════════════════════════
# ⑦ 三分离：agent 自报不影响判定
# ══════════════════════════════════════════════════════════

def test_agent_self_report_does_not_decide(j):
    """★★★★ 意图: agent 自报 False 而实测满足 ⇒ 仍判 pass。

    ★★★ 三分离（2607.12790 §3.4 / JUDGE_DESIGN §4.4）:
      "被实际服务的东西不能当训练标签"
      ⇒⇒ 判定只看实测；自报只用于**记录不一致**。
    """
    obs = {"answer": "pivot 递归 最坏"}
    v = j.evaluate("reasoning_001", SPLIT_DEV, observed=obs, predicted=False)
    assert v.success is True, "自报不许改判"
    assert "不一致" in v.reason, "但不一致要被记下来"


# ══════════════════════════════════════════════════════════
# 形态纪律
# ══════════════════════════════════════════════════════════

def test_verdict_is_frozen():
    """意图: Verdict 不可变（它是判分的最终产物）。"""
    v = Verdict("t", "dev", True, "r")
    with pytest.raises(Exception):
        v.success = False


def test_no_self_grading_interface(j):
    """★★ 意图: judge 不许有"给自己打分/置成功"的接口（原则 1）。"""
    for banned in ("set_truth", "force_pass", "mark_success",
                   "assume_pass", "override"):
        assert not hasattr(j, banned), "出现 %r —— 判分器必须不可被自己改判" % banned


def test_truth_source_records_no_broken_assertions():
    """★★★ 意图: 真值源里不得有残缺断言（引号未闭合）。"""
    data = json.loads(io.open(TRUTH_SOURCE[0][1], encoding="utf-8").read())
    for tid, rec in data.items():
        if tid.startswith("_"):
            continue
        assert rec["checks"], "%s 没有可执行判据" % tid
        for c in rec["checks"]:
            e = str(c.get("expected", c.get("kw", "")))
            assert e.count("'") % 2 == 0, "%s 有残缺断言 %r" % (tid, e)


def test_dev_has_no_metadata_counted_as_task(j):
    """★★ 意图: _provenance 等元数据不得被当成任务（R24 修的 bug）。"""
    sc = j.score(SPLIT_DEV, {})
    assert sc["n_tasks"] == 10, "实际 10 条任务（不是 11）"
    assert j.self_check()["dev_tasks"] == 10