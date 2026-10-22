# -*- coding: utf-8 -*-
"""R428 · 任务级超时 + cron 脚本自举解释器。

═══ ① 任务级超时（R414 遗留的最后一环）═══

并发只有 2 个槽位（`_INBOX_SEMA`）。之前只有 R398 的**心跳**
（防止被误判 stale 重取），**没有任何上限** —— 一单卡住就永久占掉
一半产能，收件箱其它单只能排队。

★ Python 线程不能强杀，所以设计是：任务体跑在 daemon 线程里，
  超时后**归还槽位**（线程自己跑完就消失）。安全性来自
  "任务体不写任何文件" —— 落盘都在 `run_user_task` 里、槽位归还之后。

═══ ② cron 脚本自举解释器 ═══

现场：`DWC bench daily` / `DWC anchor drift watch` 连续 9 / 19 次
`ModuleNotFoundError: No module named 'yaml'`。

根因不是脚本坏了 —— 是 **cron 用 hermes 内置 python 跑脚本，
而那个解释器没装 pyyaml**（venv 里有）。两个 cron 因此长期 error。

修法：脚本启动时检测 `import yaml`，失败就切到带依赖的解释器重跑。
★ Windows 的 `os.execv` **不给参数加引号** —— 仓库路径含空格
  （`E:\\Divine Wisdom Core`）会被拆成 `E:\\Divine`，必须用
  `subprocess.call([...])`（现场实测）。
"""
from __future__ import annotations

import io
import os
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def _agent():
    import dwc_agent as A
    return A


# ═══ ① 任务级超时 ═══

def test_timeout_returns_incomplete_and_frees_slot():
    """★★★ 核心：超时必须**立刻**返回，不能等任务体跑完。"""
    A = _agent()
    t0 = time.time()

    def _slow():
        time.sleep(5)
        return {"status": "done"}

    rep = A._run_with_deadline(_slow, 0.3, "慢任务")
    elapsed = time.time() - t0
    assert rep["status"] == "incomplete"
    assert "任务级超时" in rep["why"]
    assert rep["task"] == "慢任务"
    assert elapsed < 2.0, "超时后必须马上归还槽位，实际 %.1fs" % elapsed


def test_success_returns_rep_unchanged():
    """★★ 正常路径不许被包装改坏。"""
    A = _agent()
    rep = A._run_with_deadline(lambda: {"status": "done", "answer": "x"},
                               30, "快任务")
    assert rep == {"status": "done", "answer": "x"}


def test_exception_propagates_to_caller():
    """★★ 任务体抛异常必须抛给调用方（那里才会写 incomplete 报告）。"""
    A = _agent()

    def _boom():
        raise ValueError("炸了")

    with pytest.raises(ValueError):
        A._run_with_deadline(_boom, 30, "异常任务")


def test_zero_timeout_means_inline_no_wrapper():
    """★★ `DWC_TASK_TIMEOUT_S=0` = 关闭（回归兜底：有人要跑超长单）。"""
    A = _agent()
    import threading
    got = A._run_with_deadline(
        lambda: {"status": "done", "thread": threading.current_thread().name},
        0, "内联")
    assert got["status"] == "done"
    assert not got["thread"].startswith("task-body-"), "0 不该起线程"


def test_default_timeout_is_positive_and_generous():
    """★★ 缺省必须 > 全池单均（5–8 分钟），否则会误杀正常单。"""
    A = _agent()
    assert A._TASK_TIMEOUT_S >= 600


# ═══ ② cron 脚本自举 ═══

@pytest.mark.parametrize("name", ["dwc_bench_cron.py",
                                  "dwc_anchor_drift_watch.py"])
def test_cron_script_bootstraps_runtime(name):
    """★★★ 脚本必须在**用 yaml / import dwc 之前**自举解释器。"""
    p = os.path.join(ROOT, "scripts", name)
    with io.open(p, encoding="utf-8") as fh:
        src = fh.read()
    assert "def _ensure_runtime()" in src, "缺自举函数"
    call_at = src.index("_ensure_runtime()")
    # 自举调用必须早于真正的 yaml 依赖点
    for dep in ("from dwc.", "import yaml as", "import yaml\n"):
        i = src.find(dep)
        if i >= 0:
            assert call_at < i, "%s 在自举之前就用了 %s" % (name, dep)
    # Windows 上 execv 不引号化 ⇒ 必须用 subprocess
    assert "subprocess" in src and "os.execv(" not in src.split(
        "def _ensure_runtime")[1][:1200], \
        "os.execv 在 Windows 上会拆掉含空格的路径"
