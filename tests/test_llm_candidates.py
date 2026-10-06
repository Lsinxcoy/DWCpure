# -*- coding: utf-8 -*-
"""candidates 的 **LLM 形态**契约测试（R34）。

★★★ 这一层为什么值得单独测（R34 的实测教训）
  `need_llm` 此前只**报**不**跑** ⇒ 候选生成只有确定性退化形态
  ⇒ 而两篇原文一致: 候选该由**模型**生成（2606.14249 §3 / 2609.06396 Eq.10）
  ⇒⇒ 补上这一层后，必须把**降级路径**一起锁死 —— 因为降级是常态:
     未注入 / 端点不通 / 返回垃圾 / 非 JSON，**四条都得如实报**
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = r"E:/Divine Wisdom Core"
sys.path.insert(0, os.path.join(ROOT, "src"))  # noqa: E402

from dwc.llm import LLMClient, LLMResult
from dwc.organs.candidates import CandidateGenerator

SIG = {"c": "E_VALUE", "q": "wrong_magnitude", "fn": "mystery"}
DIFFS = [{"args": 1, "actual": 7, "expected": 100},
         {"args": 2, "actual": 9, "expected": 200},
         {"args": 3, "actual": 11, "expected": 400}]
BASE = "def mystery(x):\n    return 2 * x + 5"


def _mock(result):
    """★ 注入一个"只回一条结果"的假 LLM。"""
    class M:
        def complete(self, *a, **k):
            return result
    return M()


def _ok(patches, m="offset_calibration"):
    return LLMResult(ok=True, source="llm",
                     text=json.dumps({"patches": patches, "m": m}))


# ══════════════════════════════════════════════════════════
# ① 降级路径（**常态** —— 必须四条都如实报）
# ══════════════════════════════════════════════════════════

def test_no_llm_injection_reports_need_llm():
    """★ 未注入 ⇒ need_llm=True 且说明是"本进程未注入"。"""
    g = CandidateGenerator()
    r = g.generate(SIG, DIFFS, BASE, fn_name="mystery")
    assert r["need_llm"] is True and r["n"] == 0
    assert "未注入" in r["why"], "★ 要分清『没接 LLM』与『接了但失败』"
    assert g.n_llm_calls == 0, "★ 没注入就不该有调用账"


def test_llm_error_surfaces_cause():
    """★★ LLM 失败 ⇒ **原因必须透出来**（否则 = 静默）。"""
    g = CandidateGenerator(llm=_mock(
        LLMResult(ok=False, source="error", error="URLError: timeout")))
    r = g.generate(SIG, DIFFS, BASE, fn_name="mystery")
    assert r["need_llm"] is True
    assert "URLError: timeout" in r["why"], "LLM 错误被吞"
    assert "接了但失败" in r["why"] or "source=error" in r["why"]
    assert "source=error" in r["why"]


def test_llm_bad_json_surfaces_cause():
    """★★ 返回非 JSON ⇒ 透出解析原因。"""
    g = CandidateGenerator(llm=_mock(
        LLMResult(ok=True, source="llm", text="这不是 JSON")))
    r = g.generate(SIG, DIFFS, BASE, fn_name="mystery")
    assert "不是合法 JSON" in r["why"]


def test_llm_uncompilable_patches_rejected():
    """★★★ 不可编译的候选**必须拒**（LLM 说的不等于对）。"""
    g = CandidateGenerator(llm=_mock(_ok(["def mystery(:", "  return ??? "])))
    r = g.generate(SIG, DIFFS, BASE, fn_name="mystery")
    assert r["n"] == 0 and r["need_llm"] is True
    assert "不可编译" in r["why"]


def test_llm_cannot_bypass_discipline1():
    """★★★★★ LLM **不能绕过**纪律①（无 diffs ⇒ 不产候选）。

    ★★ 这是最要紧的一条: 有模型之后最容易发生的事就是
      "反正模型能编，就不看证据了"
      ⇒⇒ 那正是 2606.14249 明确否定的『pre-enumerated/凭空』
    """
    g = CandidateGenerator(llm=_mock(_ok(["return 1"])))
    r = g.generate(SIG, [], BASE, fn_name="mystery")
    assert r["n"] == 0, "★★★ 无 diffs 时 LLM 不许产候选"
    assert "纪律①" in r["why"]
    assert g.n_llm_calls == 0, "★ 连调用都不该发（省配额且不留痕误区）"


# ══════════════════════════════════════════════════════════
# ② 正向（真产出 + 纪律不放松）
# ══════════════════════════════════════════════════════════

def test_llm_produces_candidates_with_all_disciplines():
    """★★★★ 正向: 产出候选，且**四条纪律**都在。"""
    g = CandidateGenerator(llm=_mock(_ok(["return 2 * x + 95",
                                          "return x * 2 + 98"])))
    r = g.generate(SIG, DIFFS, BASE, fn_name="mystery")
    assert r["n"] == 2 and r["need_llm"] is False
    assert r["source"] == "llm"
    for c in r["candidates"]:
        assert c.source == "llm", "★ 来源必须可区分（可审计）"
        assert len(c.grounding) > 0, "★ 纪律②: 必带 grounding"
        assert c.patch == c.patch.lstrip(), "★ 首行缩进必须归零"
        compile("def mystery(x):\n    " + c.patch, "<t>", "exec")
    assert g.n_llm_calls == 1 and g.n_llm_ok == 2, "★ 调用账本要准"


def test_llm_candidate_carries_m_and_m_source():
    """★★★★★ m（机制假设）**必须**被模型填上并标来源。

    ★★ 依据: EVOLUTION_CORE_DESIGN §9 第 4 项「m 由模型填」
      + 2609.06396 Eq.10
      ⇒⇒ ⇒★ 而 R34 之前 `Candidate` **没有 m 字段**
        （确定性形态的 m 从 RULES 读 ⇒ 生成器不需要带它）
      ⇒ ⇒★ 于是**那条分工在代码里落不了地** —— 本测试锁它
    """
    g = CandidateGenerator(llm=_mock(_ok(["return 1"], m="loop_bound")))
    r = g.generate(SIG, DIFFS, BASE, fn_name="mystery")
    assert r["n"] >= 1
    c = r["candidates"][0]
    assert c.m == "loop_bound"
    assert c.m_source == "llm", "★★ 必须标 source（与 rule 来源区分）"
    assert r.get("m_hint") == "loop_bound"


def test_llm_prompt_contains_real_evidence():
    """★★★★ prompt 必须含**真实证据**（否则 = 凭空生成）。

    ★★ R34 实测抓到的真 bug: 我第一版在 prompt 里用
      `d.get("got")` / `d.get("want")`
      而 judge 产的字段是 `actual` / `expected`
      ⇒⇒ ⇒★★ 于是 **prompt 里的证据恒为 None**
        LLM 收到空证据 = 让它凭空编 —— 那正是原文否定的形态
      ⇒⇒ ⇒★★ 这是「字段名各写一份必然漂移」的同族（R30 的 c/q）
      ⇒ ⇒★ 已收敛成 `judge.DIFF_FIELDS` 单一真源，本测试锁它
    """
    seen = {}

    class Spy:
        def complete(self, prompt, **k):
            seen["prompt"] = prompt
            return _ok(["return 1"])

    g = CandidateGenerator(llm=Spy())
    g.generate(SIG, DIFFS, BASE, fn_name="mystery")
    p = seen["prompt"]
    for token in ("actual", "expected", "E_VALUE", "mystery",
                  '"args": 1', "7", "100"):
        assert token in p, "★ prompt 缺证据字段/值: %r" % token
    # ★ 不许出现旧的错字段名
    assert '"got"' not in p and '"want"' not in p, "★★ 用回了与 judge 不一致的字段名"


def test_diff_fields_is_single_source():
    """★★★★★ DIFF_FIELDS 是**唯一真源**，且 judge 用的就是它。

    ★★ 没有这条锁，字段名会再次漂移（我已经错过一次）
    """
    from dwc.organs.judge import DIFF_FIELDS
    assert "actual" in DIFF_FIELDS and "expected" in DIFF_FIELDS
    assert "got" not in DIFF_FIELDS and "want" not in DIFF_FIELDS
    # ★ 与 judge.evaluate 产出的 diffs 键一致
    from dwc.organs.judge import Judge
    src = open(os.path.join(ROOT, "src", "dwc", "organs", "judge.py"),
               encoding="utf-8").read()
    assert "{k: d.get(k) for k in DIFF_FIELDS}" in src, "★★ judge 没用这个常量 ⇒ 真源形同虚设"


def test_llm_result_never_raises():
    """★★ 返回值模式（纪律②）: LLM 层**不抛异常**。

    ★★ 为什么: 调用方最常见的写法是
      `try: ... except: pass` ⇒ 那正是 G7 静默门要防的
    """
    g = CandidateGenerator(llm=_mock(None))   # ★ complete 返 None

    class Boom:
        def complete(self, *a, **k):
            raise RuntimeError("boom")

    g2 = CandidateGenerator(llm=Boom())
    for gg in (g, g2):
        r = gg.generate(SIG, DIFFS, BASE, fn_name="mystery")
        assert isinstance(r, dict), "★ 必须返回结构而不是抛"
        assert r["need_llm"] is True


# ══════════════════════════════════════════════════════════
# ③ LLM 客户端（凭证护栏 + 降级）
# ══════════════════════════════════════════════════════════

SECRET = "sk-TEST-SECRET-KEY-ABCDEFG123"


def test_client_no_config_is_degraded_not_error():
    """★ 无配置 ⇒ 静态降级（**不发网络请求**）。"""
    c = LLMClient(base_url="", api_key="", model="")
    assert c.configured is False
    assert c.unavailable_reason, "★ 不可用原因必须非空（可查）"
    r = c.complete("hi")
    assert r.ok is False and r.source == "not_configured"
    assert r.error, "★ 要有原因"
    assert c.n_calls == 0, "★★ 没配置就不该发请求"


def test_client_never_leaks_credentials():
    """★★★★★ 凭证**绝不外流**: repr / str / stats / pickle 全无 key。"""
    c = LLMClient(base_url="https://example.invalid/v1",
                  api_key=SECRET, model="m")
    for tag, s in (("repr", repr(c)), ("stats", str(c.stats())),
                   ("getstate", str(c.__getstate__())),
                   ("result", str(LLMResult(ok=False, source="error",
                                            error="x")))):
        assert SECRET not in s, "★ 凭证泄漏于 %s" % tag
    import pickle
    blob = pickle.dumps(c)
    assert SECRET.encode() not in blob, "★★★ pickle 出去（可能落盘/进缓存）⇒ 密钥泄露"


def test_client_4xx_does_not_read_body(tmp_path):
    """★★★★ 4xx **只取 code/reason**，不读 body（防 key 回显）。

    ★★ 真实服务端可能把请求头回显进 body
      ⇒ 若我读了 body 放进 error ⇒ key 就进了**可记录**的字符串
    """
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            self.send_response(401)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(("leak " + SECRET).encode())

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        c = LLMClient(base_url="http://127.0.0.1:%d/v1"
                      % srv.server_address[1],
                      api_key=SECRET, model="m", timeout=8)
        r = c.complete("x")
        assert r.ok is False and r.source == "error"
        assert SECRET not in r.error, "★★★ key 被读进 error"
        assert "HTTP 401" in r.error, "★ 但错误要有 HTTP 语义"
    finally:
        srv.shutdown()


def test_client_transport_error_is_degraded():
    """★ 连不上 ⇒ degraded=True（调用方据此走 heuristic）。"""
    c = LLMClient(base_url="http://127.0.0.1:1/v1",
                  api_key=SECRET, model="m", timeout=3)
    r = c.complete("x")
    assert r.ok is False and r.degraded is True and r.error
    assert r.source == "error"
