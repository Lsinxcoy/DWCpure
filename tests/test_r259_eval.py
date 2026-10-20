# -*- coding: utf-8 -*-
"""R259/R261 · 测量层与 web_read 锁。

★ R259: 任务集完整性 + 验收器独立性（G2: 验收在 agent 外 — 不采信自述）。
★ R261: web_read 协议白名单 + html→text + 真抓（网络失败跳过）。
"""
import io
import json
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TASKS = os.path.join(ROOT, "config", "eval_tasks.jsonl")


# ════ R259 任务集 ════

def test_taskset_integrity():
    """★★★ 任务集锁: 52 单齐全, 分层分布, 每单带机器可验 check。"""
    tasks = [json.loads(l) for l in io.open(TASKS, encoding="utf-8")]
    assert len(tasks) >= 50
    kinds = {}
    for t in tasks:
        kinds[t["kind"]] = kinds.get(t["kind"], 0) + 1
        assert t["task"] and t["check"].get("type"), t["id"]
    for k in ("read-fact", "run-verify", "write", "analyze", "code-locate"):
        assert kinds.get(k, 0) >= 8, (k, kinds)


def test_taskset_no_llm_selfjudge():
    """★★★ G2 锁: check 类型全集在机器可验集合内（无 LLM 自评类型）。

    ★ R381 重锚：加入 `contains_equiv`（等价形式判据）。
      理由：`rf01` 原判据只认 `0xfeff`，模型答 `65279`（== 0xFEFF）
      被判 ✗ —— 判据验的是"写法"不是"答案"，系统性低估通过率。
      `contains_equiv` 仍是**纯字符串匹配**（无 LLM 参与），
      与 G2 的初衷（禁 LLM 自评）不冲突，故纳入白名单。
    """
    allowed = {"contains", "regex", "contains_any", "contains_all",
               "contains_equiv",
               "rc_and_contains", "file_contains", "file_contains_all",
               "file_lines"}
    for l in io.open(TASKS, encoding="utf-8"):
        t = json.loads(l)
        assert t["check"]["type"] in allowed, t["id"]


def test_verifier_independent_of_agent(tmp_path):
    """★★★ 验收器独立锁: run 类独立重跑不信 agent 自述; file 类独立读盘。"""
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "dwc_bench2", os.path.join(ROOT, "scripts", "dwc_bench2.py"))
    b2 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(b2)
    # run: 独立重跑真命令（agent 的 answer 说谎也不影响判定）
    ok, how = b2.verify({"type": "rc_and_contains", "cmd": "python -c \"print('ANCHOR')\"",
                         "target": "ANCHOR"}, answer="完全无关的答案")
    assert ok and "rerun" in how
    # file: 独立读盘（repo 内临时目录 — 跨盘 relpath 会炸）
    tmpd = os.path.join(ROOT, "var", "__test_r259__")
    os.makedirs(tmpd, exist_ok=True)
    fp = os.path.join(tmpd, "x.txt")
    with io.open(fp, "w", encoding="utf-8") as fh:
        fh.write("FILE_ANCHOR")
    ok2, _ = b2.verify({"type": "file_contains",
                        "path": os.path.relpath(fp, ROOT),
                        "target": "FILE_ANCHOR"}, answer="也是无关的")
    assert ok2
    # file 缺失 ⇒ 拒（不信 agent 说写了）
    ok3, how3 = b2.verify({"type": "file_contains",
                           "path": "var/inbox_work/no_such_eval.txt",
                           "target": "x"}, answer="我写了")
    assert not ok3


def test_self_md_current_facts():
    """★★★ 自我认知同步锁（跑批第一天抓到的真缺陷回归锁）:
      dwc_self.md 不许再出现旧的 6 轮上限表述。"""
    body = io.open(os.path.join(ROOT, "config", "dwc_self.md"),
                   encoding="utf-8").read()
    assert "6 轮未 final" not in body
    assert "999" in body


# ════ R261 web_read ════

def test_web_read_protocol_whitelist():
    """★★★ 协议白名单: file:// 与无 scheme 拒绝（G2 结构门）。"""
    from dwc.llm.task_exec import _do_action
    assert _do_action("web_read", {"url": "file:///etc/passwd"})["ok"] is False
    assert _do_action("web_read", {"url": "ftp://x"})["ok"] is False
    assert _do_action("web_read", {"url": ""})["ok"] is False


def test_html_to_text():
    """★★★ html→text: script/style 剥离, 正文保留。"""
    from dwc.llm.task_exec import _html_to_text
    out = _html_to_text("<html><script>evil()</script><style>c{}</style>"
                        "<body><h1>Title</h1><p>Para  one</p></body></html>")
    assert "Title" in out and "Para" in out
    assert "evil" not in out and "c{}" not in out


def test_web_read_valid_ops():
    """★★★ op 集与判别器同步: web_read 进 VALID_OPS 与修订校验。"""
    from dwc.llm.step_judge import VALID_OPS, validate_step
    assert "web_read" in VALID_OPS
    assert "非法 url" in validate_step({"op": "web_read", "url": "x"})
    assert validate_step({"op": "web_read", "url": "https://a.com"}) is None


def test_web_read_live():
    """★★★ 真抓锁（网络失败 skip — 不假装）: https://example.com。"""
    import pytest
    from dwc.llm.task_exec import _do_action
    r = _do_action("web_read", {"url": "https://example.com"})
    if not r.get("ok") and "失败" in str(r.get("error", "")):
        pytest.skip("网络不可达: %s" % r.get("error", "")[:60])
    assert r["ok"] and r["chars"] > 100
