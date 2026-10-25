# -*- coding: utf-8 -*-
"""R444 · P2 按任务选档（规则优先，不引 LLM 分类器当默认路径）。

为什么：DWC 现在全局一个 `reasoning_effort` + 一个固定预算档。
简单题用牛刀（浪费），难题省子弹（掉分）。

借 HarnessPro 的 profile 形状，但阈值按 DWC 实测重定：
  R411 实测「推理档越高越差」⇒ 所有 profile 默认**继承全局**（None），
  不在这一步偷偷调推理力度。
"""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from dwc.llm import profile as P


def test_short_simple_task_is_compact():
    assert P.choose("读一下 config/llm.json 的 model 字段").name == "compact"


def test_medium_task_is_lean():
    assert P.choose("在 docs 目录下统计 md 文件数量并给出每个文件的行数").name == "lean"


def test_long_task_is_deep():
    t = ("请审计 src/dwc 下的调用链，逐个核对函数签名与实现是否一致，"
         "并列出所有没有消费者的产物文件。") * 6
    assert P.choose(t).name == "deep"


def test_research_keywords_pick_research():
    assert P.choose("调研最近三篇关于 KV cache 的论文并对比它们的做法").name == "research"


def test_choose_is_deterministic():
    t = "把 tests 下失败的用例逐个修好并回归"
    assert P.choose(t).name == P.choose(t).name


def test_choose_never_returns_none():
    for t in ("", "x", "a" * 5000, "分析 设计 审计 搜索 重构"):
        assert P.choose(t) is not None


def test_explain_names_the_matched_rule():
    e = P.explain("调研最近的论文")
    assert e["profile"] == "research"
    assert e["rule"]                    # 命中的规则名非空
    assert "signals" in e


def test_every_profile_has_budget():
    for p in P.PROFILES.values():
        assert p.budget.economy_after <= p.budget.strict_after <= p.budget.finalize_after


def test_profiles_inherit_reasoning_by_default():
    """★ R411：推理档越高越差 ⇒ 默认继承全局，不在选档时偷偷改。"""
    for p in P.PROFILES.values():
        assert p.reasoning_effort in (None, ""), p


def test_deep_has_more_room_than_compact():
    assert (P.PROFILES["deep"].budget.finalize_after
            > P.PROFILES["compact"].budget.finalize_after)


# ------------------------------------------------------------ 客户端按调用覆盖

def _capture_client():
    seen = {}

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
            seen["body"] = json.loads(raw.decode("utf-8"))
            body = json.dumps({"choices": [{"message": {"content": "ok"},
                                            "finish_reason": "stop"}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    from dwc.llm import LLMClient
    c = LLMClient(base_url="http://127.0.0.1:%d/v1" % srv.server_address[1],
                  api_key="k", model="m1", timeout=8,
                  reasoning_effort="none")
    return c, srv, seen


def test_complete_per_call_override_wins():
    c, srv, seen = _capture_client()
    try:
        c.complete("x", reasoning_effort="low")
        assert seen["body"].get("reasoning_effort") == "low"
    finally:
        srv.shutdown()


def test_complete_without_override_uses_instance_value():
    c, srv, seen = _capture_client()
    try:
        c.complete("x")
        assert seen["body"].get("reasoning_effort") == "none"
    finally:
        srv.shutdown()


# ------------------------------------------------------- 优先级：进化值 > 档位 > 默认

def test_profile_prior_used_when_policy_silent(monkeypatch):
    from dwc.llm import task_exec as TE
    monkeypatch.setattr(TE, "_policy", lambda c, k, d: d)
    tb = TE.tool_budget(P.PROFILES["compact"])
    assert (tb.economy_after, tb.strict_after, tb.finalize_after) == (3, 5, 8)


def test_evolution_override_beats_profile(monkeypatch):
    from dwc.llm import task_exec as TE
    vals = {"budget_economy_after": 4}
    monkeypatch.setattr(TE, "_policy", lambda c, k, d: vals.get(k, d))
    tb = TE.tool_budget(P.PROFILES["compact"])
    assert tb.economy_after == 4      # 进化改过的赢
    assert tb.strict_after == 5       # 没改过的用档位
    assert tb.finalize_after == 8


def test_no_profile_keeps_r441_defaults(monkeypatch):
    from dwc.llm import task_exec as TE
    monkeypatch.setattr(TE, "_policy", lambda c, k, d: d)
    tb = TE.tool_budget()
    assert (tb.economy_after, tb.strict_after, tb.finalize_after) == (6, 10, 15)


def test_finalize_never_exceeds_round_cap(monkeypatch):
    """★ 硬上限只有 15 —— 档位不许承诺永远不会到来的轮次。"""
    from dwc.llm import task_exec as TE
    monkeypatch.setattr(TE, "_policy", lambda c, k, d: d)
    for p in P.PROFILES.values():
        assert TE.tool_budget(p).finalize_after <= TE.NATIVE_TOOLS_MAX_ROUNDS
