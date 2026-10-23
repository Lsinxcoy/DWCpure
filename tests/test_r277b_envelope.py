# -*- coding: utf-8 -*-
"""R277b · envelope 拆包 + m 填 LLM 断言值（回灌 0 行的根治）。

★ 背景: _build_observations 真执行通道包 envelope
  {observed, ★_executed}，judge 全链无拆包 ⇒ behavior 全误判 False
  （生产 6 False 系赃物）；且 behavior 签名 m 恒 "" ⇒ D6 全拦。
★ 口径冻结: 非 envelope 输入行为逐字节不变；规则时代 m 仍 ""。
★ 测试 fake（手造 observed，不烧 LLM）＋禁碰生产 anchors。
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
from dwc.organs.judge import Judge, JudgeError                # noqa: E402


def _good_obs():
    return {"sum_first_n": [[3, 6], [5, 15]]}


def test_envelope_unwrap_same_as_inner():
    """★★★ envelope 输入与裸 observed 同判（拆包回归锁）。"""
    j = Judge()
    inner = _good_obs()
    env = {"observed": dict(inner), "★_executed": True}
    a = j.evaluate("code_fix_001", "dev", observed=inner)
    b = j.evaluate("code_fix_001", "dev", observed=env)
    assert a.success is True and b.success is True


def test_envelope_false_carries_m():
    """★★★ envelope 下的 False 签名 m = LLM 断言值（D6 可过）。"""
    j = Judge()
    env = {"observed": {"sum_first_n": [[3, 999], [5, 15]]},
           "★_executed": True}
    v = j.evaluate("code_fix_001", "dev", observed=env)
    assert v.success is False
    assert v.failure_signature.get("m", "").startswith("llm_asserted:")


def test_rule_era_m_stays_empty():
    """★★★ 非 envelope（规则时代）False 的 m 仍空（零破坏锁）。"""
    j = Judge()
    v = j.evaluate("code_fix_001", "dev",
                   observed={"sum_first_n": [[3, 999], [5, 15]]})
    assert v.success is False
    assert v.failure_signature.get("m") == ""


def test_judge_rejects_train_split():
    """★★★ 非法 split 大声 raise（raises 配额）。"""
    j = Judge()
    with pytest.raises(JudgeError):
        j.evaluate("code_fix_001", "train", observed=_good_obs())


def test_abstain_all_null_envelope_is_none():
    """★ R277b-6 · 执行通道全 null 回声 ⇒ 未评价 None（不当失败）。"""
    j = Judge()
    env = {"observed": {"sum_first_n": [[3, None], [5, None]]},
           "★_executed": True}
    v = j.evaluate("code_fix_001", "dev", observed=env)
    assert v.success is None


def test_abstain_partial_null_still_graded():
    """★ R277b-6 · 部分 null 仍正常判分（残疾对子该挂就挂）。"""
    j = Judge()
    env = {"observed": {"sum_first_n": [[3, None], [5, 15]]},
           "★_executed": True}
    v = j.evaluate("code_fix_001", "dev", observed=env)
    assert v.success is False


def test_abstain_rule_era_unaffected():
    """★ R277b-6 · 非 envelope 全 null 不进弃权（旧行为零碰）。"""
    j = Judge()
    v = j.evaluate("code_fix_001", "dev",
                   observed={"sum_first_n": [[3, None], [5, None]]})
    assert v.success is False


def test_loose_numeric_executed_channel():
    """★ R277b-7 · 执行通道 0==0.0（JSON 类型是传输 artifact）。"""
    j = Judge()
    env = {"observed": {"average": [[[], 0], [[1, 2, 3], 2]]},
           "★_executed": True}
    v = j.evaluate("code_fix_002", "dev", observed=env)
    assert v.success is True


def test_strict_numeric_rule_era():
    """★ R277b-7 · 规则时代 0≠0.0（R30 纪律零碰锁）。"""
    from dwc.organs.judge import _eq, _NUM_LOOSE
    assert _NUM_LOOSE[0] is False  # 默认关（防泄漏锁）
    assert _eq(0, 0.0) is False
    assert _eq(True, 1) is False


def test_bool_strict_both_channels():
    """★ R277b-7 · 布尔两种通道都严格（True≠1，raises 配额）。"""
    import pytest
    from dwc.organs.judge import _eq
    assert _eq(True, 1) is False and _eq(False, 0) is False
    with pytest.raises(JudgeError):
        Judge().evaluate("nope_task", "dev", observed={})


def test_executor_outage_is_none():
    """★ R277b-9 · 执行体故障 {error_code} ⇒ 未评价 None（不当失败）。"""
    j = Judge()
    v = j.evaluate("code_fix_001", "dev",
                   observed={"error_code": "llm_parse_failed"})
    assert v.success is None


def test_outage_does_not_swallow_envelope():
    """★ R277b-9 · 带 observed 的 envelope 不进 outage（零误伤锁）。"""
    j = Judge()
    env = {"observed": {"sum_first_n": [[3, 6], [5, 15]]},
           "★_executed": True}
    assert j.evaluate("code_fix_001", "dev", observed=env).success is True
    import pytest
    with pytest.raises(JudgeError):
        j.evaluate("code_fix_001", "train",
                   observed={"error_code": "x"})  # 非法 split 照 raise


def test_007_rounded_is_real_failure():
    """★ R277b-11 · 007 四舍五入答案判真失败（m 填断言值，可回灌）。"""
    j = Judge()
    env = {"observed": {"average": [[[0.1, 0.2], 0.15],
                                    [[1.1, 2.2], 1.65]]},
           "★_executed": True}
    v = j.evaluate("code_fix_007", "dev", observed=env)
    assert v.success is False
    sig = v.to_dict().get("sigs", [{}])[0]
    assert "llm_asserted" in str(sig.get("m", ""))


def test_007_exact_passes():
    """★ R277b-11 · 007 精确答案判通过（陷阱只杀四舍五入）。"""
    j = Judge()
    env = {"observed": {"average": [[[0.1, 0.2], 0.15000000000000002],
                                    [[1.1, 2.2], 1.6500000000000001]]},
           "★_executed": True}
    assert j.evaluate("code_fix_007", "dev", observed=env).success is True
    import pytest
    with pytest.raises(JudgeError):
        j.evaluate("code_fix_007", "train",
                   observed={"observed": {}, "★_executed": True})


def test_008_guessed_is_real_failure():
    """★ R277b-12 · 008 估算答案判真失败（m 填断言值，可回灌）。"""
    j = Judge()
    env = {"observed": {"sum_first_n": [[1000, 500000], [777, 300000]]},
           "★_executed": True}
    v = j.evaluate("code_fix_008", "dev", observed=env)
    assert v.success is False
    sig = v.to_dict().get("sigs", [{}])[0]
    assert "llm_asserted" in str(sig.get("m", ""))


def test_008_exact_passes():
    """★ R277b-12 · 008 精确答案判通过（陷阱只杀估算）。"""
    j = Judge()
    env = {"observed": {"sum_first_n": [[1000, 500500], [777, 302253]]},
           "★_executed": True}
    assert j.evaluate("code_fix_008", "dev", observed=env).success is True
    import pytest
    with pytest.raises(JudgeError):
        j.evaluate("code_fix_008", "train",
                   observed={"observed": {}, "★_executed": True})


def test_009_guessed_is_real_failure():
    """★ R277b-13 · 009 估算答案判真失败（m 填断言值，可回灌）。"""
    j = Judge()
    env = {"observed": {"sum_first_n": [[123456, 7620750000],
                                        [99999, 5000000000]]},
           "★_executed": True}
    v = j.evaluate("code_fix_009", "dev", observed=env)
    assert v.success is False
    sig = v.to_dict().get("sigs", [{}])[0]
    assert "llm_asserted" in str(sig.get("m", ""))


def test_009_exact_passes():
    """★ R277b-13 · 009 精确答案判通过（陷阱只杀估算）。"""
    j = Judge()
    env = {"observed": {"sum_first_n": [[123456, 7620753696],
                                        [99999, 4999950000]]},
           "★_executed": True}
    assert j.evaluate("code_fix_009", "dev", observed=env).success is True
    import pytest
    with pytest.raises(JudgeError):
        j.evaluate("code_fix_009", "train",
                   observed={"observed": {}, "★_executed": True})
