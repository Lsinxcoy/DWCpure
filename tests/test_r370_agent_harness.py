# -*- coding: utf-8 -*-
"""R370 · AgentHarness 的 8-hook 接线锁（Phase B3）。

守三件事:
  1. 一次成功求解里 8 个 hook 全部 fire（顺序符合 HarnessX Table 1）
  2. step_end / task_end 是只读 hook（传 writes 即抛）
  3. Policy 变异面可枚举、非法字段显式拒

★ 用假 deps，不碰网络、不碰真实仓库。
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if os.path.join(_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "src"))

import pytest  # noqa: E402

from dwc.harness.agent_harness import (  # noqa: E402
    HOOKS, AgentHarness, HarnessDeps, Policy,
)
from dwc.organs.hook import HookRegistry, HookViolation, ProcessorSpec  # noqa: E402
from dwc.organs.processors import default_registry  # noqa: E402


class FakeFS:
    def __init__(self, files):
        self.files = dict(files)

    def list_files(self):
        return sorted(self.files)

    def read(self, path, n):
        c = self.files.get(path)
        return None if c is None else c[:n]

    def write(self, path, content):
        self.files[path] = content

    def apply(self, original, old, new):
        if old not in original:
            return None, "old_string not found"
        return original.replace(old, new, 1), "ok"


def _deps(fs, llm_reply, all_passed=True):
    return HarnessDeps(
        call_llm=lambda system, prompt, max_tokens: llm_reply,
        list_files=fs.list_files,
        read_file=fs.read,
        apply_edit=fs.apply,
        write_file=fs.write,
        check_syntax=lambda path: (True, ""),
        run_tests=lambda: {"all_passed": all_passed, "passed": 1 if all_passed else 0,
                           "total": 1},
        verify=lambda ps, diff, out: ("PASS", ""),
    )


def _registry_with_recorders(fired):
    """默认 5 个处理器 + 8 个记录器（每组名唯一）。"""
    reg = default_registry()
    for h in HOOKS:
        reg.register(ProcessorSpec(
            name="rec_" + h, hook=h, order="POST",
            singleton_group="rec_" + h,
            call=(lambda name: (lambda state: fired.append(name)))(h),
        ))
    return reg


SRC = "def f():\n    return 1\n"
REPLY = '{"file": "src/a.py", "old_string": "return 1", "new_string": "return 2"}'


def test_all_eight_hooks_fire_once_on_success():
    fs = FakeFS({"src/a.py": SRC})
    fired = []
    h = AgentHarness(_deps(fs, REPLY), _registry_with_recorders(fired),
                     Policy(max_rounds=3))

    res = h.solve("bug: f returns wrong value", ["tests/test_a.py::test_f"])

    assert res.success is True
    assert res.rounds == 1
    # 8 个 hook 全部 fire（记录器按 hook 名各记一次）
    assert set(fired) == set(HOOKS)
    # 顺序: task_start 最先, task_end 最后
    assert fired[0] == "task_start"
    assert fired[-1] == "task_end"
    # 一轮内的核心顺序
    seq = [f for f in fired if f not in ("task_start", "task_end")]
    assert seq.index("step_start") < seq.index("before_model")
    assert seq.index("before_model") < seq.index("after_model")
    assert seq.index("after_model") < seq.index("before_tool")
    assert seq.index("before_tool") < seq.index("after_tool")
    assert seq.index("after_tool") < seq.index("step_end")
    # 文件真的被改了
    assert fs.files["src/a.py"] == "def f():\n    return 2\n"


def test_read_only_hooks_reject_writes():
    reg = HookRegistry()
    with pytest.raises(HookViolation):
        reg.fire("step_end", {}, writes=["anything"])
    with pytest.raises(HookViolation):
        reg.fire("task_end", {}, writes=["anything"])


def test_failed_tests_roll_back_and_retry():
    fs = FakeFS({"src/a.py": SRC})
    fired = []
    h = AgentHarness(_deps(fs, REPLY, all_passed=False),
                     _registry_with_recorders(fired), Policy(max_rounds=2))

    res = h.solve("bug", ["tests/test_a.py::test_f"])

    assert res.success is False
    assert res.rounds == 2                     # 用满两轮
    assert fs.files["src/a.py"] == SRC          # 每轮都回滚
    assert "测试未通过" in res.previous_error
    # 8 个 hook 在每轮都 fire
    assert fired.count("step_start") == 2
    assert fired.count("task_start") == 1
    assert fired.count("task_end") == 1


def test_unparseable_response_does_not_crash():
    fs = FakeFS({"src/a.py": SRC})
    fired = []
    h = AgentHarness(_deps(fs, "I think the bug is in rewrite.py..."),
                     _registry_with_recorders(fired), Policy(max_rounds=2))

    res = h.solve("bug", [])

    assert res.success is False
    assert res.rounds == 2
    assert "未产出可解析的 action" in res.previous_error
    assert fs.files["src/a.py"] == SRC


def test_policy_mutate_and_reject_unknown_field():
    p = Policy()
    q = p.mutate("max_rounds", 5)
    assert q.max_rounds == 5 and p.max_rounds == 3   # frozen，不改原件
    with pytest.raises(KeyError):
        p.mutate("nope", 1)
