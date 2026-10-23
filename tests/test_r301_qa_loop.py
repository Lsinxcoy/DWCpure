# -*- coding: utf-8 -*-
"""R301 · 问答死循环三修（A 去重指纹＋B 平台感知＋C qa 直答）。fake llm 零真成本。"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm.step_judge import judge_step, validate_step


def _obs(op, target, ok=True):
    return {"phase": "obs", "op": op, "target": target, "ok": ok, "obs": "{}"}


def test_r301a_page_turn_allowed():
    """★ A：同 path 不同 offset⇒放行 exploratory（翻页不是重复）。"""
    hist = [_obs("read", "src/dwc/llm/task_exec.py"),
            _obs("read", "src/dwc/llm/task_exec.py")]
    v, _, rule = judge_step({"op": "read", "path": "src/dwc/llm/task_exec.py",
                             "offset": 800}, hist)
    assert v == "exploratory", (v, rule)


def test_r301a_same_args_still_noisy():
    """★ A：同 path 同参第 3 次⇒R1 noisy（真复读仍砍）。"""
    hist = [_obs("read", "src/dwc/llm/task_exec.py"),
            _obs("read", "src/dwc/llm/task_exec.py")]
    v, _, rule = judge_step({"op": "read", "path": "src/dwc/llm/task_exec.py"},
                            hist)
    assert (v, rule) == ("noisy", "R1"), (v, rule)


def test_r301d_qa_only_read_or_final():
    """★ D：qa 下 run⇒noisy R5（问答只许 read 取证或 final，硬约束）。"""
    v, _, rule = judge_step({"op": "run",
                             "cmd": ["python", "-c", "print(1)"]}, [],
                            qa_mode=True)
    assert (v, rule) == ("noisy", "R5"), (v, rule)
    v2, _, _ = judge_step({"op": "read", "path": "src/dwc/llm/task_exec.py"},
                          [], qa_mode=True)
    assert v2 == "exploratory"


def test_r301d_losing_streak_breaker():
    """★ D：run 近史 3 败（不限同 cmd）⇒noisy R2-连败（逼 final 硬出口）。"""
    hist = [_obs("run", "cmd%d" % i, ok=False) for i in range(3)]
    v, why, rule = judge_step({"op": "run", "cmd": ["python", "-c", "x"]},
                              hist)
    assert (v, rule) == ("noisy", "R2"), (v, why, rule)
    assert "连败" in why


def test_r301b_revise_platform_clause():
    """★ B：revise prompt 在 Windows 下明示无 grep/ls＋argv 列表。"""
    import dwc.llm.task_exec as T
    src = open(T.__file__, encoding="utf-8").read()
    assert "grep" in src  # ★ 修后 prompt 必须出现平台子句（下断言实现见下）
    # ★ 直接调 _revise_step（fake llm 收 prompt）：子句必须进 prompt
    box = []

    class _R:
        ok = True
        text = '{"op": "run", "cmd": ["python", "-c", "print(1)"], '\
               '"analysis": "x"}'

    def _fake(prompt, **kw):
        box.append(prompt)
        return _R()

    class _LLM:
        def complete(self, prompt, **kw):
            box.append(prompt)
            return _R()

    T._revise_step(llm=_LLM(), task="t",
                   step={"op": "read", "path": "a.py"},
                   why="R1", recent=[])
    needle = "grep" if os.name == "nt" else "换一条路径"
    assert needle in box[0], box[0][:300]


def test_r301c_qa_first_round_final():
    """★ C：纯问句首轮 final⇒done（零工具步，qa 分流）。"""
    import dwc.llm.task_exec as T

    class _R:
        ok = True
        text = '{"op": "final", "answer": "自进化通过夜 Damn 轮迭代，有影响：规则会进起草上下文", "analysis": "问答直答"}'

    calls = {"n": 0}

    class _LLM:
        def complete(self, prompt, **kw):
            calls["n"] += 1
            return _R()

    r = T.execute_user_task("我给你设计了自进化的功能你觉得对你有影响吗",
                            llm=_LLM(), task_id="T_R301QA",
                            retry_on_fail=False)
    assert r["status"] == "done" and calls["n"] == 1, (r, calls)


def test_r301c_exec_still_r4():
    """★ C：执行任务首轮空 op⇒仍 R4（老路零变，非问句不分流）。"""
    import dwc.llm.task_exec as T

    class _R:
        ok = True
        text = '{"analysis": "坏形状"}'  # ★ 无 op

    class _R2:
        ok = True
        text = '{"op": "final", "answer": "修好了，落盘三条规则", "analysis": "x"}'

    seq = [_R(), _R2()]
    box = {"n": 0}

    class _LLM2:
        def complete(self, prompt, **kw):
            r = seq[min(box["n"], 1)]
            box["n"] += 1
            return r

    r = T.execute_user_task("去把 var 下的失败签名修了并落盘", llm=_LLM2(),
                            task_id="T_R301EX", retry_on_fail=False)
    # ★ 3 次 complete=首轮空 op＋revision 重写＋重跑 final（R4 纪律工作证据）
    assert r["status"] == "done" and box["n"] == 3, (r, box)


def test_r301e_r5_blocked_no_exec():
    """★ E：qa 下连出**改状态**命令⇒R5 短路（不执行真命令，≤3 轮 final）。

    ★ R386 重锚：原测试用 `grep -rn x src/` 当"违禁动作"，但 grep 是
      **只读**的 —— qa 的本意是「只读、不许改状态」，不是「不许用命令」。
      现场：cl01 的 search_code→grep 被 R5 连拦 4 轮 ⇒ 答不出定义文件
      （而 grep 一行就能定位）。故这里改用真·改状态命令（pip install）
      来验证 R5 短路，另加一条锁"只读命令必须放行"。
    """
    import dwc.llm.task_exec as T

    class _R:
        ok = True
        text = ('{"op": "run", "cmd": ["pip", "install", "requests"], '
                '"analysis": "装个包"}')

    class _F:
        ok = True
        text = '{"op": "final", "answer": "问答经拦截后直接回答，不跑命令", "analysis": "从善"}'

    seq = [_R(), _R(), _F()]
    box = {"n": 0, "exec": 0}
    orig = T._do_action

    class _LLM:
        def complete(self, prompt, **kw):
            r = seq[min(box["n"], 2)]
            box["n"] += 1
            return r

    def _spy(op, step):
        box["exec"] += 1
        return orig(op, step)

    T._do_action = _spy
    try:
        r = T.execute_user_task("自进化功能对你有影响吗", llm=_LLM(),
                                task_id="T_R301E", retry_on_fail=False)
    finally:
        T._do_action = orig
    assert r["status"] == "done", r
    assert box["exec"] == 0, box  # ★ R5 短路：改状态命令零执行


def test_r386_readonly_grep_is_allowed_in_qa():
    """★★★ R386 新语义：qa 下**只读**命令必须放行（grep 不是写操作）。

    现场：cl01「execute_user_task 定义在哪个文件？」被判 qa_mode，
    `search_code`→`run(grep)` 被 R5 连拦 4 轮 ⇒ 答"未能确认"。
    修后实测 2 轮 41 秒答出 `src/dwc/llm/task_exec.py`。
    """
    import dwc.llm.task_exec as T

    class _R:
        ok = True
        text = ('{"op": "run", "cmd": ["grep", "-rn", "x", "src/"], '
                '"analysis": "搜一下"}')

    class _F:
        ok = True
        text = '{"op": "final", "answer": "基于搜索结果回答", "analysis": "收"}'

    seq = [_R(), _F()]
    box = {"n": 0, "exec": 0}
    orig = T._do_action

    class _LLM:
        def complete(self, prompt, **kw):
            r = seq[min(box["n"], 1)]
            box["n"] += 1
            return r

    def _spy(op, step):
        box["exec"] += 1
        return {"ok": True, "rc": 0, "out": "src/x.py:1:hit", "err": ""}

    T._do_action = _spy
    try:
        r = T.execute_user_task("execute_user_task 定义在哪个文件",
                                llm=_LLM(), task_id="T_R386",
                                retry_on_fail=False)
    finally:
        T._do_action = orig
    assert box["exec"] >= 1, "只读 grep 仍被拦（R5 把查证本身禁了）"


def test_r301f_qa_read_cap_forces_final():
    """★ F：qa 下 read×3 仍不答⇒第 4 轮 prompt 硬推收敛（取证上限）。"""
    import dwc.llm.task_exec as T

    class _RD:
        ok = True
        # ★ 递增 offset（模拟翻页真行为，避开 R247 同段熔断，专验 F 硬推）
        text = ('{"op": "read", "path": "src/dwc/llm/task_exec.py", '
                '"offset": %d, "analysis": "再读"}')

    class _F:
        ok = True
        text = '{"op": "final", "answer": "取证三次后收敛作答", "analysis": "收"}'

    seen = {"prompts": []}

    class _LLM:
        def complete(self, prompt, **kw):
            seen["prompts"].append(prompt)
            n = len(seen["prompts"])
            if n >= 5:
                return _F()
            r = _RD()
            r.text = _RD.text % (n * 100)
            return r

    r = T.execute_user_task("轮数上限为什么这样设", llm=_LLM(),
                            task_id="T_R301F", retry_on_fail=False,
                            max_rounds=8)
    assert r["status"] == "done", r
    assert any("已取证" in p for p in seen["prompts"]), seen["prompts"][-1][:150]


def test_r301c_raises_quota_qa_empty_answer():
    """★ raises①：qa final 空 answer⇒validate 非法（防空交差）。"""
    err = validate_step({"op": "final", "answer": "  "}, qa_mode=True)
    assert err is not None, "空 answer 必须拦"


def test_r301_raises_quota_validate_bad_op():
    """★ raises②：非法 op⇒validate 报错（老纪律 intact）。"""
    assert validate_step({"op": "rm_rf"}) is not None
