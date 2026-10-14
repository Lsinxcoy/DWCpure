# -*- coding: utf-8 -*-
"""R255-R257 · EditAct 规则版三件套锁（判别 · 修订 · 证伪标记 · 修订重试 · 校准）。

★ 起因: 2609.28416 深读 — 事前判别+直接替换优于事后检测（消融证据）;
  DWC 的 17:12/17:13 两单失败全部落入 noisy 三型。
"""
import io
import json
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from dwc.llm import step_judge as SJ  # noqa: E402
from dwc.llm import task_exec as TE  # noqa: E402


# ════ ① judge 规则族 ════

def test_judge_r1_repeat():
    """★★★ R1: 同 (op,target) 已执行 2 次 ⇒ noisy（17:12 read 同段案）。"""
    v, why, rule = SJ.judge_step(
        {"op": "read", "path": "config/drift.yaml"},
        [{"op": "read", "target": "config/drift.yaml", "ok": True},
         {"op": "read", "target": "config/drift.yaml", "ok": True}])
    assert (v, rule) == ("noisy", "R1")
    assert "已执行 3 次" in why


def test_judge_r2_failed_cmd():
    """★★★ R2: 同 run cmd 已失败 ⇒ noisy（wsl rc=1 案）。"""
    v, why, rule = SJ.judge_step(
        {"op": "run", "cmd": "wsl ls"},
        [{"op": "run", "target": "wsl ls", "ok": False}])
    assert (v, rule) == ("noisy", "R2")
    assert "失败 1 次" in why


def test_judge_r3_ghost_path():
    """★★★ R3: read 幻觉路径（不存在）⇒ noisy（17:13 案; 本地可查=规则版独有）。"""
    v, why, rule = SJ.judge_step(
        {"op": "read", "path": "docs/no_such_ghost.py"}, [])
    assert (v, rule) == ("noisy", "R3")
    assert "幻觉路径" in why


def test_judge_keeps_exploratory_and_critical():
    """★★★ 显式保留探索类（论文教训: 不设会误砍信息收集）+ ask/delegate=critical。"""
    v, _, rule = SJ.judge_step({"op": "read", "path": "config/drift.yaml"}, [])
    assert v == "exploratory" and rule == "-"
    v2, _, _ = SJ.judge_step({"op": "ask", "reason": "危险命令"}, [])
    assert v2 == "critical"
    v3, _, _ = SJ.judge_step({"op": "final", "answer": "完"}, [])
    assert v3 == "critical"          # final 不判（论文同款）


def test_judge_r4_bad_shape():
    """★★★ R4: 缺 op / 非法 op / 空 run cmd ⇒ noisy。"""
    assert SJ.judge_step({}, [])[0] == "noisy"
    assert SJ.judge_step({"op": "fly"}, [])[2] == "R4"
    assert SJ.judge_step({"op": "run", "cmd": "  "}, [])[0] == "noisy"


# ════ 修订校验与签名 ════

def test_validate_step():
    """★★★ 修订校验锁（revision.py 纪律）: 形状/路径/禁 final。"""
    assert SJ.validate_step({"op": "read", "path": "config/drift.yaml"}) is None
    assert "非 dict" in SJ.validate_step("x")
    assert "契约集" in SJ.validate_step({"op": "fly"})
    assert "缺 path" in SJ.validate_step({"op": "read"})
    assert "空 cmd" in SJ.validate_step({"op": "run", "cmd": " "})
    assert "不存在" in SJ.validate_step({"op": "read", "path": "no/gg.py"})
    assert "不可产 final" in SJ.validate_step(
        {"op": "final", "answer": "x"}, allow_final=False)


def test_signature_ignores_analysis():
    """★★★ 签名锁: analysis 不参与（同动作不同措辞=同签名, 连续 ⇒ fallback）。"""
    a = {"op": "read", "path": "a.py", "analysis": "看a"}
    b = {"op": "read", "path": "a.py", "analysis": "换个说法"}
    c = {"op": "read", "path": "b.py", "analysis": "看a"}
    assert SJ.step_signature(a) == SJ.step_signature(b)
    assert SJ.step_signature(a) != SJ.step_signature(c)


# ════ 集成: judge→revision→fallback 链 ════

class _FakeLLM:
    def __init__(self, steps):
        self._steps = list(steps)
        self.calls = []

    def complete(self, prompt, *, system=None, max_tokens=1200,
                 json_mode=False, images=None):
        """★ 契约对齐真 LLMClient.complete（曾因 **kw 吞掉 tag= 的
        TypeError — B 臂 46 次修订全灭的根因没被测试抓到）。"""
        self.calls.append("complete")
        step = (self._steps.pop(0) if self._steps
                else {"analysis": "done", "op": "final", "answer": "完"})
        return SimpleNamespace(ok=True, text=json.dumps(step, ensure_ascii=False),
                               error="", meta={})


def _dwc_sess(monkey_tmp=None):
    old = os.environ.get("DWC_SESS_DIR")
    return TE


def test_noisy_triggers_revision(monkeypatch):
    """★★★ 集成锁: noisy 提案 ⇒ 修订 LLM 被调（tag=revise）且执行修订版。"""
    steps = [
        {"analysis": "读", "op": "read", "path": "config/no_ghost_a.py"},  # R3 noisy
        {"analysis": "修订后", "op": "read", "path": "config/drift.yaml"},  # 修订产物
        {"analysis": "完", "op": "final", "answer": "好"},
    ]
    llm = _FakeLLM(steps)
    rep = TE.execute_user_task("t", llm=llm, retry_on_fail=False)
    assert rep["status"] == "done"
    # ★ tag 参数已除（真接口无）— 修订被调 = complete 多出 1 次:
    #   read(noisy步) + 修订 + final = 3 次
    assert len(llm.calls) == 3, llm.calls
    # 执行的是修订版（drift.yaml 真读）而非幻觉路径
    obs_lines = [e for e in rep["actions_log"]
                 if isinstance(e, dict) and e.get("phase") == "obs"]
    assert obs_lines and obs_lines[0]["ok"] is True


def test_revision_fallback_on_invalid(monkeypatch):
    """★★★ fallback 锁: 修订产物非法（空 cmd run）⇒ 保留原提案执行。"""
    steps = [
        {"analysis": "坏run", "op": "run", "cmd": "definitely_fail_cmd_xyz"},  # R2 首次无历史 ⇒ exploratory 执行
        {"analysis": "再坏run", "op": "run", "cmd": "definitely_fail_cmd_xyz"},  # R2 noisy
        {"analysis": "修订-非法", "op": "run", "cmd": ""},   # 修订产物非法
        {"analysis": "完", "op": "final", "answer": "好"},
    ]
    llm = _FakeLLM(steps)
    rep = TE.execute_user_task("t", llm=llm, retry_on_fail=False)
    # 修订非法 ⇒ fallback 原 step（含 cmd）执行, 失败也继续; 最终 final
    assert rep["status"] == "done"
    obs_lines = [e for e in rep["actions_log"]
                 if isinstance(e, dict) and e.get("phase") == "obs"]
    # 第 2 轮 obs 的 target 仍是原 cmd（修订被拒）
    assert obs_lines[1]["target"] == "definitely_fail_cmd_xyz"


def test_env_switch_off():
    """★★★ env 开关锁: DWC_STEP_JUDGE=0 ⇒ 不判别不修订。"""
    os.environ["DWC_STEP_JUDGE"] = "0"
    try:
        steps = [
            {"analysis": "读", "op": "read", "path": "config/no_ghost_b.py"},
            {"analysis": "完", "op": "final", "answer": "好"},
        ]
        llm = _FakeLLM(steps)
        rep = TE.execute_user_task("t", llm=llm, retry_on_fail=False)
        assert rep["status"] == "done"
        assert "revise" not in llm.calls
    finally:
        os.environ.pop("DWC_STEP_JUDGE", None)


# ════ ③ compaction 证伪标记 ════

def test_compaction_marks_falsified():
    """★★★ 证伪标记锁: ok=False 轮在前情摘要带 [✗证伪—结论勿引用]。"""
    captured = {}

    _steps = [{"analysis": "读A", "op": "run", "cmd": "no_such_cmd_c"},   # 失败
              {"analysis": "读B", "op": "read", "path": "README.md"},
              {"analysis": "完", "op": "final", "answer": "好"}]

    class FakeC:
        def complete(self, prompt, **kw):
            captured.setdefault("prompts", []).append(prompt)
            step = (_steps.pop(0) if _steps else
                    {"analysis": "d", "op": "final", "answer": "完"})
            return SimpleNamespace(ok=True,
                                   text=json.dumps(step, ensure_ascii=False),
                                   error="", meta={})
    rep = TE.execute_user_task("t", llm=FakeC(), max_rounds=999,
                               retry_on_fail=False)
    assert rep["status"] == "done"
    # 第 3 轮 prompt（读 README 那轮）应含第 1 轮失败的证伪标
    joined = "\n".join(captured.get("prompts", []))
    assert "✗证伪—结论勿引用" in joined, joined[-400:]
    fails = [e for e in rep["actions_log"]
             if isinstance(e, dict) and e.get("phase") == "obs"
             and e.get("ok") is False]
    assert fails


# ════ ④ 任务级修订重试 ════

def test_task_revision_retry():
    """★★★ 修订重试锁: 首跑达上限 ⇒ 修订任务重跑; revision_pair 落盘。"""
    calls = {"n": 0}

    class FakeC2:
        def complete(self, prompt, **kw):
            if "重写任务" in prompt:
                return SimpleNamespace(
                    ok=True,
                    text=json.dumps({"revised_task": "读 README 的第一行"},
                                    ensure_ascii=False), error="", meta={})
            # 首跑: 一直 read 幻觉 ⇒ 上限; 二跑: 直接 final
            calls["n"] += 1
            if calls["n"] <= 1:
                return SimpleNamespace(
                    ok=True,
                    text=json.dumps({"analysis": "读", "op": "read",
                                     "path": "no_ghost_xx.py"},
                                    ensure_ascii=False), error="", meta={})
            return SimpleNamespace(
                ok=True,
                text=json.dumps({"analysis": "答", "op": "final",
                                 "answer": "第一行是标题"}, ensure_ascii=False),
                error="", meta={})

    rep = TE.execute_user_task("读 README 第一行", llm=FakeC2(), max_rounds=1)
    assert rep.get("revised") is True
    assert rep["status"] == "done"
    assert rep["revision_pair"]["original_task"] == "读 README 第一行"
    assert rep["revision_pair"]["retried_ok"] is True
    # 修订对已落盘
    pair_p = os.path.join(TE.SESSIONS, "..", "dwc_pairs.jsonl")
    assert os.path.exists(pair_p)
    last = json.loads(io.open(pair_p, encoding="utf-8").read().splitlines()[-1])
    assert last["retried_ok"] is True


# ════ ② 校准脚本 ════

def test_calibrator_present_and_bench():
    """★★★ 校准锚锁: 脚本存在 + bench 数据在 + 判别器有 agent 外真值源。"""
    import subprocess
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    assert os.path.exists(os.path.join(root, "scripts",
                                       "calibrate_step_judge.py"))
    bench = os.path.join(root, "var", "aewm_bench",
                         "action_judge_benchmark_3000.jsonl")
    if not os.path.exists(bench):
        import pytest
        pytest.skip("bench 未下载（var/aewm_bench/ — hf-mirror）")
    py = sys.executable
    r = subprocess.run([py, os.path.join(root, "scripts",
                                         "calibrate_step_judge.py"),
                        "--limit", "40"], capture_output=True, text=True,
                       timeout=300, cwd=root, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stderr[-300:]
    assert "macro-F1" in r.stdout
