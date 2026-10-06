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
from dwc.organs.applier import Applier, Target
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


def _ok(patches, m="offset_calibration",
        component="control_flow", dimension="D7"):
    """★ R35: mock 必须带**契约值** —— 实现现在要求 component/dimension
      （RRSI 式12/15 的契约由模型在词表内选）
    ⇒ 不给 ⇒ 契约校验整批拒（**不猜默认值**）—— 那是预期行为
    """
    return LLMResult(ok=True, source="llm",
                     text=json.dumps({"patches": patches, "m": m,
                                      "component": component,
                                      "dimension": dimension}))


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

def test_llm_contract_values_out_of_vocab_rejected():
    """★★★★★ R35: 模型给的 component/dimension **不在契约内** ⇒ 整批拒。

    ★★★ 这条是"不编造"的实现:
      component 是 RRSI 式12 词表、dimension 是九维 —— 都是**契约**
      ⇒ 若模型给 `component="banana"`，我**不能**:
        a) 静默改用默认值（= 我替它编了 component）
        b) 放行（= 契约形同虚设）
      ⇒ ⇒★ 必须整批拒，且**原因透出来**
    """
    bad_cases = [
        dict(component="banana"),          # 词表外
        dict(dimension="D99"),             # 九维外
        dict(component=""),                # 缺失
        dict(dimension=""),
    ]
    for over in bad_cases:
        kwargs = dict(patches=["return 1"], m="x")
        kwargs.update(over)
        g = CandidateGenerator(llm=_mock(LLMResult(
            ok=True, source="llm", text=json.dumps(kwargs))))
        r = g.generate(SIG, DIFFS, BASE, fn_name="mystery")
        assert r["n"] == 0, "★ 词表外的值竟放行了: %r" % over
        assert "契约值不在范围内" in r["why"], \
            "★ 拒绝原因必须透出来（否则 = 静默拒）"
        assert str(over.get("component", over.get("dimension", "?"))) \
            in r["why"] or "component=" in r["why"]


def test_llm_candidate_has_provenance_fingerprint():
    """★★★★ m 的**调用指纹**（R35: m 由模型产 ⇒ 两次措辞不同）。

    ★★ 依据: 2603.25681 §6.4.3『报准确率必须同时报 test-time 配置』
      ⇒ 同理: 记一条 m 必须记**它哪次调用产的**
      ⇒ ⇒★ 否则固化后无法回溯，而且会被误读成"m 可复现"
    """
    g = CandidateGenerator(llm=_mock(_ok(["return 1"], m="loop_bound")))
    r = g.generate(SIG, DIFFS, BASE, fn_name="mystery")
    assert r["n"] >= 1
    pr = r["candidates"][0].provenance
    assert pr.get("prompt_ver") == CandidateGenerator.PROMPT_VER
    assert pr.get("n_diffs") == len(DIFFS), "★ 要能回溯用了几条证据"
    assert "raw_m" in pr, "★ 模型原话要留（措辞会变）"


def test_prompt_contains_contract_vocab():
    """★★★★ prompt 必须把**契约**给模型（否则它无从选起）。

    ★ R35: component/dimension 改由模型选 ⇒ 词表必须在 prompt 里
    """
    seen = {}

    class Spy:
        def complete(self, prompt, **k):
            seen["p"] = prompt
            return _ok(["return 1"])

    CandidateGenerator(llm=Spy()).generate(SIG, DIFFS, BASE,
                                           fn_name="mystery")
    p = seen["p"]
    assert "control_flow" in p and "subagent" in p, \
        "★ component 词表没进 prompt"
    assert "D1" in p and "D9" in p, "★ 九维没进 prompt"
    assert '"component"' in p and '"dimension"' in p, \
        "★ 返回格式里没要求这两项"

# ══════════════════════════════════════════════════════════
# ④ R35 · 固化（候选 → 规则条目）—— evolver 组装，applier 写
# ══════════════════════════════════════════════════════════

def _entry(**over):
    e = {"component": "control_flow", "dimension": "D7",
         "target_layer": "assets",
         "target": "f", "m": "m", "m_source": "rule",
         "patch": "p", "rationale": "r"}
    e.update(over)
    return e


def _check(key, entry):
    from dwc.organs.evolver import Mutator
    return Mutator.check_entry(key, entry)


def _mk_cand(**kw):
    from dwc.organs.candidates import Candidate
    base = dict(patch="return x", source="llm", rule="R_llm",
                grounding=[{"index": 0, "actual": 1, "expected": 2}],
                m="lower_case", m_source="llm",
                component="control_flow", dimension="D7",
                target_layer="assets",
                target="is_palindrome",
                provenance={"prompt_ver": "v2", "model": "MiMo",
                            "n_diffs": 1, "raw_m": "m"})
    base.update(kw)
    # ★★★ R37: layer **跟着 component 走**（与真实流水线一致）
    #   我原来默认写死 `target_layer="assets"` ⇒ 换 component 后
    #   K2 必然拒 ⇒ 测的就不是"component 合法性"而是我的手滑
    #   ⇒⇒ ⇒★ 测试数据要走**真实构造路径**（`layer_of` 是真源）
    if "target_layer" not in kw:
        try:
            from dwc.organs.evolver import layer_of
            base["target_layer"] = layer_of(base.get("component", ""))
        except ValueError:
            base["target_layer"] = ""
    return Candidate(**base)


def test_entry_from_candidate_full_schema():
    """★★★★★ 正向: 候选 → 7 字段全齐 + m 指纹（可过 check_entry）。"""
    from dwc.organs.evolver import Mutator
    e = Mutator.entry_from_candidate(_mk_cand())
    for f in Mutator.RULE_ENTRY_FIELDS:
        assert str(e.get(f, "")).strip(), "★ 缺字段 %s（炸点在查表那一刻）" % f
    assert e["m_source"] == "llm"
    assert e["_m_fingerprint"]["prompt_ver"] == "v2"
    assert e["_m_fingerprint"]["raw_m"] == "m", "★ 模型原话要留"
    assert Mutator.check_entry("E:q:f", e) == [], "★ schema 应合格"


def test_entry_rejects_out_of_contract_component():
    """★★★★ component 不在词表 ⇒ 拒绝（**不猜默认值** = 不编造）。"""
    from dwc.organs.evolver import Mutator
    with pytest.raises(ValueError) as ex:
        Mutator.entry_from_candidate(_mk_cand(component="banana"))
    # ★ R37: 措辞从「不在词表」改成「不在 𝒦∪𝒦_meta」（扩到两表）
    #   ⇒ 但**意图**没变: 原因要透出 + 明确"不猜默认值"
    #   ⇒ ⇒★ 断言**意图**而非字面（否则每次改措辞都红）
    assert "不猜默认值" in str(ex.value), "★ 拒绝必须说明不猜默认"
    assert "banana" in str(ex.value), "★ 原因要带出被拒的值"
    assert ("𝒦∪𝒦_meta" in str(ex.value) or "词表" in str(ex.value)), \
        "★ 原因要说清在哪张表里不合法"
    # ★ 指纹也不能被绕过（同一函数路径）
    for bad in (dict(dimension="D99"), dict(m=""),
                dict(component=""), dict(dimension="")):
        with pytest.raises(ValueError):
            Mutator.entry_from_candidate(_mk_cand(**bad))


def test_entry_rejects_llm_m_without_fingerprint():
    """★★★★ m_source=llm 但**无 provenance** ⇒ 拒绝（"无源的 m"）。

    ★★★ 依据: 2603.25681 §6.4.3『报准确率必须同时报 test-time 配置』
      ⇒ 同理: 记一条 m 必须记**哪次调用产的**
      ⇒ ⇒★ 否则固化后无法回溯，且会被误读成「m 可复现」
    """
    from dwc.organs.evolver import Mutator
    with pytest.raises(ValueError) as ex:
        Mutator.entry_from_candidate(
            _mk_cand(m_source="llm", provenance={}))
    assert "无源" in str(ex.value)


def test_entry_rejects_none_candidate():
    """★ 空候选 ⇒ 拒绝（不许空固化）。"""
    from dwc.organs.evolver import Mutator
    with pytest.raises(ValueError):
        Mutator.entry_from_candidate(None)


def test_entry_accepts_rule_sourced_m_without_fingerprint():
    """★ 对照: `m_source='rule'`（规则读来的）**不要求**指纹。"""
    from dwc.organs.evolver import Mutator
    e = Mutator.entry_from_candidate(
        _mk_cand(m_source="rule", provenance={}))
    assert "_m_fingerprint" not in e, "★ 规则来的 m 不该硬塞指纹"
    assert e["m"] == "lower_case"


def test_generation_sets_target_on_every_candidate():
    """★★★★★ R35 抓到的断点: LLM 候选**必须带 target**。

    ★★★ 实测: 我加了 component/dimension/provenance 却漏了 target
      ⇒ 于是 check_entry 报缺 target ⇒ **固化流水线断在 schema**
      ⇒⇒ ⇒★ 这是"加字段没同步构造"的又一次（R35 已是第 N 次）
      ⇒ ⇒★ 现在 generate() 里有**统一收口**（缺的从 fn 推），
        本测试锁它 —— 否则下次加字段还会漏
    """
    g = CandidateGenerator(llm=_mock(_ok(["return 1"])))
    r = g.generate(SIG, DIFFS, BASE, fn_name="mystery")
    assert r["n"] >= 1
    for c in r["candidates"]:
        assert c.target == "mystery", \
            "★ 候选无 target ⇒ 固化必被 schema 拒"
        # ★ 且能真过组装
        from dwc.organs.evolver import Mutator
        assert Mutator.check_entry(
            Mutator.key_for(dict(SIG)), Mutator.entry_from_candidate(c)) == []


def test_deterministic_candidates_also_get_target():
    """★ 确定性候选同样要有 target（统一收口覆盖两侧）。

    ★★ 我第一版用错了场景: `SIG/DIFFS/BASE`(mystery) 正是
      「确定性推不出」的场景（我选它就是为了测 LLM）
      ⇒⇒ 那条断言 `n >= 1` **必红** —— 是我把场景的前提搞反了
      ⇒ ⇒★ 换成含 range 的场景（R1 能命中的那类）
    """
    sig = {"c": "E_VALUE", "q": "wrong_magnitude", "fn": "sum_first_n"}
    diffs = [{"args": 3, "actual": 3, "expected": 6},
             {"args": 5, "actual": 10, "expected": 15}]
    buggy = "def sum_first_n(n):\n    return sum(range(n))"
    g = CandidateGenerator()          # ★ 无 LLM ⇒ 纯确定性
    r = g.generate(sig, diffs, buggy, fn_name="sum_first_n")
    assert r["n"] >= 1, "★ 该场景确定性应能推（R1 的 delta_eq_args 命中）"
    assert r.get("need_llm") is False
    for c in r["candidates"]:
        assert c.target == "sum_first_n", \
            "★ 确定性候选也必须有 target（统一收口要覆盖两侧）"
        from dwc.organs.evolver import Mutator
        assert Mutator.check_entry(
            Mutator.key_for(dict(sig)),
            Mutator.entry_from_candidate(c)) == []

def test_r1_contract_must_match_same_family_rules():
    """★★★★★ R1 的契约属性必须**与 RULES 同族条目一致**（我注释里承诺的锁）。

    ★★★ 我在 candidates.py 里写了:
      「RULES 那条若改，这里要跟着改（测试会锁）」
      ⇒ 本测试就是那把锁 —— 没它，注释就是**幻影承诺**

    ★★ 依据: R1 改的是 range 的 stop/start = 与
      `E_VALUE:wrong_magnitude:sum_first_n` **同一个机制**
      ⇒ 那条已固化条目是 component=control_flow/D7/m=range_bounds
      ⇒⇒ 三者若漂移 ⇒ R1 固化出来的规则会**与同族不一致**
        （查表/审计时看不出它们是同一件事）
    """
    from dwc.organs.evolver import Mutator
    ref_key = "E_VALUE:wrong_magnitude:sum_first_n"
    ref = Mutator.RULES.get(ref_key)
    assert ref, "★ 前置: 同族种子条目应该在（它一直是）"

    g = CandidateGenerator()
    sig = {"c": "E_VALUE", "q": "wrong_magnitude", "fn": "sum_first_n"}
    diffs = [{"args": 3, "actual": 3, "expected": 6},
             {"args": 5, "actual": 10, "expected": 15}]
    r = g.generate(sig, diffs,
                   "def sum_first_n(n):\n    return sum(range(n))",
                   fn_name="sum_first_n")
    assert r["n"] >= 1
    c = next(x for x in r["candidates"] if x.rule.startswith("R1_"))
    # ★★ 三个值逐个对齐同族条目
    assert c.component == ref["component"], \
        "R1.component 与同族条目漂移: %r vs %r" % (c.component, ref["component"])
    assert c.dimension == ref["dimension"], \
        "R1.dimension 与同族条目漂移: %r vs %r" % (c.dimension, ref["dimension"])
    assert c.m == ref["m"], \
        "R1.m 与同族条目漂移: %r vs %r" % (c.m, ref["m"])
    assert c.m_source == "rule", "★ 确定性的 m 来源是 rule 不是 llm"


def test_r2_has_no_contract_because_no_evidence():
    """★★ R2 诚实留空 ⇒ 固化被拒（**这是对的**，不是缺陷）。

    ★★ 我 R35 明确选择: RULES 里没有类型包装类条目 ⇒ 无依据 ⇒ 不填
      ⇒ ⇒★ 于是 R2 候选固化时被 check_entry 拒
        = 「没依据的规则先别固化」的实现
      ⇒⇒ 若哪天有人把 component 随手填上，**这条测试会红**
        —— 那正是要提醒: 你填的依据是什么?
    """
    from dwc.organs.candidates import CandidateGenerator as CG
    from dwc.organs.evolver import Mutator
    g = CG()
    # R2 只在"期望 int 实测 str"时触发
    diffs = [{"args": 1, "actual": "7", "expected": 7},
             {"args": 2, "actual": "9", "expected": 9}]
    sig = {"c": "E_TYPE", "q": "wrong_magnitude", "fn": "mystery"}
    r = g.generate(sig, diffs, "def mystery(x):\n    return str(x * 2)",
                   fn_name="mystery")
    r2s = [c for c in r["candidates"] if c.rule.startswith("R2_")]
    if not r2s:
        return   # ★ R2 没触发（形态变了就不是本测试的范围）
    c = r2s[0]
    assert c.component == "", "★ R2 不该有 component（无依据）"
    with pytest.raises(ValueError) as ex:
        Mutator.entry_from_candidate(c)
    assert "词表" in str(ex.value), \
        "★ 无依据的 R2 竟固化通过 ⇒ 有人偷偷填了 component"

# ══════════════════════════════════════════════════════════
# ⑤ R36 · 配置优先级 + 传输类重试
# ══════════════════════════════════════════════════════════

def test_timeout_param_beats_config_file(tmp_path, monkeypatch):
    """★★★★★ 配置优先级: **显式参数 > 环境变量 > config 文件**。

    ★★★ R36 实测抓到的 bug:
      docstring 写「参数 > env > 文件」，而 timeout 的实现是
        `env or 文件 or 参数` ⇒ **参数最低**
      ⇒⇒ 实测后果: 测试传 timeout=2 想造超时，
        却被 config 里的 60 **覆盖** ⇒ 永不超时
        ⇒⇒ 连带: 我的重试测试**测不到重试**（断言因此红）
      ⇒⇒ ⇒★★ 这是『名字与实现不对齐』（R34 立的规矩）
      ⇒ ⇒★ 本测试锁四个字段的优先级**必须一致**
    """
    from dwc.llm.client import _load_file_config
    cfg = {"base_url": "https://file.invalid/v1",
           "api_key": "FILE_KEY", "model": "file-model",
           "timeout": "60"}
    real = os.path.join(tmp_path, "llm.json")
    # ★ 临时把 LEARNED 式的路径换掉 ⇒ 简单法: monkeypatch loader
    import dwc.llm.client as L

    def fake_loader():
        return cfg
    old = L._load_file_config
    L._load_file_config = fake_loader
    monkeypatch.setenv("DWC_LLM_BASE_URL", "https://env.invalid/v1")
    monkeypatch.setenv("DWC_LLM_API_KEY", "ENV_KEY")
    monkeypatch.setenv("DWC_LLM_MODEL", "env-model")
    monkeypatch.setenv("DWC_LLM_TIMEOUT", "45")
    try:
        c = LLMClient(base_url="https://param.invalid/v1",
                      api_key="PARAM_KEY", model="param-model",
                      timeout=2)
        # ★ 参数应**全胜**
        assert c._base == "https://param.invalid/v1"
        assert c._model == "param-model"
        assert c.timeout == 2, \
            ("★★★ 显式 timeout 被文件/环境覆盖了（实测 %s）"
             " ⇒ 造超时场景失效、重试测试测不到" % c.timeout)
        # ★ 不传参数 ⇒ env 胜过文件
        c2 = LLMClient()
        assert c2._base == "https://env.invalid/v1"
        assert c2._model == "env-model"
        assert c2.timeout == 45, "★ env 应胜过文件"
    finally:
        L._load_file_config = old


def test_transport_error_retries_but_4xx_does_not(tmp_path):
    """★★★★ 重试**只对传输类**（4xx 重试必然再失败 ⇒ 浪费）。"""
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    hits = []

    class Slow(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            hits.append(1)
            if len(hits) == 1:
                import time as _t
                _t.sleep(3)          # ★ 第一次拖到超时

            out = {"choices": [{"message": {"content": "ok"}}]}
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(out).encode())

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Slow)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        c = LLMClient(base_url="http://127.0.0.1:%d/v1"
                      % srv.server_address[1],
                      api_key="k", model="m", timeout=2)
        r = c.complete("x")
        assert r.ok, "★ 重试后应成功"
        assert len(hits) == 2, "★ 超时应重试一次（实测 %d 次请求）" % len(hits)
        assert c.stats()["n_retries"] == 1, "★ 重试要进账本（可审计）"
    finally:
        srv.shutdown()

    hits.clear()

    class Unauthorized(BaseHTTPRequestHandler):
        def do_POST(self):
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            hits.append(1)
            self.send_response(401)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"bad")

        def log_message(self, *a):
            pass

    srv2 = HTTPServer(("127.0.0.1", 0), Unauthorized)
    threading.Thread(target=srv2.serve_forever, daemon=True).start()
    try:
        c2 = LLMClient(base_url="http://127.0.0.1:%d/v1"
                       % srv2.server_address[1],
                       api_key="k", model="m", timeout=3)
        r2 = c2.complete("x")
        assert not r2.ok and r2.source == "error"
        assert len(hits) == 1, "★★ 4xx 不该重试（key/配额错重试必然再失败）"
        assert c2.stats()["n_retries"] == 0
    finally:
        srv2.shutdown()


def test_retire_flushes_to_disk():
    """★★★★★ R36 抓到的**生灭不对称**: retire 也必须 flush。

    ★★★ 实测: land_rule 落地后 flush（R34 加的），
      而 retire_rule **没调** ⇒ 内存删了、落盘没同步
      ⇒⇒ e2e 实测: 进程内 `HIT=0`，跨进程仍 `HIT=1`
        （新进程从落盘加载 ⇒ 退化的规则**还活着**）
      ⇒⇒ ⇒★★ 让 G4『能生也要能死』在跨进程上**失效**
      ⇒ ⇒★ 生灭必须**对称**（本测试锁它）
    """
    ap = Applier(window=2)
    key = "E_FL:q:fl"
    calls = {"n": 0}

    def _flush():
        calls["n"] += 1
        return "written"

    st = {}
    t = Target(getter=lambda: st.get(key),
               setter=lambda v: st.__setitem__(key, v),
               has_fn=lambda: key in st,
               delete_fn=lambda: st.pop(key, None),
               flush_fn=_flush)
    ap.land_rule(t, key, _entry(), {"success": True}, _check)
    n_after_land = calls["n"]
    assert n_after_land == 1, "★ land 必须 flush"
    ap.retire_rule(t, key, "r", {"success": False}, _check)
    assert calls["n"] == 2, \
        ("★★★ retire **没 flush** ⇒ 内存删了但落盘还留着 ⇒ "
         "跨进程时退化规则复活（G4 生灭在跨进程失效）")
    assert "已落盘同步" in ap.log[-1].reason, \
        "★ reason 要报落盘状态（否则『退役了』与『退役且同步』不可区分）"

# ══════════════════════════════════════════════════════════
# ⑥ R37 · §四① 的契约（𝒦_meta / target_layer / K2）
#   真源: docs/COMPONENT_VOCABULARY.md §2.1 + §四① + §五
# ══════════════════════════════════════════════════════════

def test_meta_vocab_has_five_and_editable_no_default():
    """★★★★★ K4: 𝒦_meta 必须 5 项且每项**显式**标 editable（无默认）。"""
    from dwc.organs.evolver import K_META
    assert len(K_META) == 5, "𝒦_meta 应 5 项，实得 %d" % len(K_META)
    assert set(K_META) == {"code", "architecture", "meta_evolution",
                           "evaluator", "external_source"}
    for k, v in K_META.items():
        assert isinstance(v, bool), \
            "★ K4: %s 的 editable 必须是 bool（无默认值）" % k


def test_k3_evaluator_and_external_source_readonly():
    """★★★★ K3: evaluator/external_source 必须**在表里**且 editable=False。

    ★★★ 依据 §3.4: 「不在表里」与「在表里但禁止改」是**两种不同的保证**
      ⇒⇒ 若 evaluator 不在表里, grep 时看不出"是漏了还是有意排除"
        —— 那正是缺口 A3 本身的成因
    """
    from dwc.organs.evolver import K_META, K_META_READONLY
    for name in K_META_READONLY:
        assert name in K_META, \
            "★ K3: %s 必须**在表里**（不许靠缺席表达不可编辑）" % name
        assert K_META[name] is False, \
            "★ K3: %s 应 editable=False（改它 = 破坏 grounded 第二条件）" % name


def test_layer_of_covers_both_tables():
    """§四① 真值表: 𝒦 ⇒ assets · 𝒦_meta ⇒ architecture · 词表外 ⇒ raise。"""
    from dwc.organs.evolver import (COMPONENT_VOCAB, K_META, layer_of,
                                    LAYER_BY_ITEM)
    # ★★★ R38 裁决 D: **逐项映射** ⇒ 「𝒦_meta 全归 architecture」
    #   这个断言（写于 D 之前）已被 §3.1 证伪:
    #     §3.1 code 只要 b_t+回归 ⇒ 无批准 ⇒ 归 assets
    #   ⇒ ⇒★ 改成: 两表**都能归层**（层由 LAYER_BY_ITEM 逐项给）
    #   ⇒ ⇒★ 具体每项的期望值由 `test_layer_of_per_item_ruling_d` 锁
    for c in list(COMPONENT_VOCAB) + list(K_META):
        assert layer_of(c) in ("assets", "architecture"), \
            "★ %s 归不了层" % c
        assert LAYER_BY_ITEM.get(c) == layer_of(c)
    # ★ 反向索引也必须与逐项表一致（不许两张表各说各话）
    from dwc.organs.evolver import LAYER_BY_GROUP
    for lay, comps in LAYER_BY_GROUP.items():
        for c in comps:
            assert layer_of(c) == lay, \
                "★ LAYER_BY_GROUP[%s] 含 %s，但 layer_of 说 %s" % (
                    lay, c, layer_of(c))
    # ★ 词表外必须**不猜**（返回任何层 = 编造）
    with pytest.raises(ValueError) as ex:
        layer_of("banana")
    assert "无层可归" in str(ex.value)


def test_k2_rejects_mismatched_pairing():
    """★★★★★ K2: component 与 target_layer 不一致 ⇒ 拒（§四①）。"""
    from dwc.organs.evolver import check_pairing
    assert check_pairing("control_flow", "assets") == []
    assert check_pairing("meta_evolution", "architecture") == []
    # 不一致 ⇒ 必须报，且原因说清是哪两个值
    p1 = check_pairing("control_flow", "architecture")
    assert p1 and "K2" in p1[0] and "assets" in p1[0]
    p2 = check_pairing("evaluator", "assets")
    assert p2 and "architecture" in p2[0]
    # 词表外 ⇒ 也算问题（无层可归）
    assert check_pairing("banana", "assets")


def test_candidate_has_target_layer_field():
    """§四① 的第 2 个字段必须在 Candidate 里存在。"""
    import dataclasses
    from dwc.organs.candidates import Candidate
    names = {f.name for f in dataclasses.fields(Candidate)}
    assert "target_layer" in names, \
        "★ §四①: proposer 必须声明两个字段，缺 target_layer"
    assert "component" in names


def test_rule_entry_fields_requires_target_layer():
    """★★ RULE_ENTRY_FIELDS 必须含 target_layer（否则固化不校验它）。"""
    from dwc.organs.evolver import Mutator
    assert "target_layer" in Mutator.RULE_ENTRY_FIELDS, \
        "★ §四①: schema 必须检查第 2 个字段"


def test_prompt_requires_model_to_declare_layer():
    """prompt 必须让模型**显式**声明 target_layer（§四①『必须声明』）。"""
    g = CandidateGenerator(llm=_mock(_ok(["return 1"])))
    g.generate(SIG, DIFFS, BASE, fn_name="mystery")
    src = type(g).__init__
    import inspect
    body = inspect.getsource(CandidateGenerator._llm_generate)
    assert '"target_layer"' in body, "★ prompt 的 JSON 格式必须含 target_layer"
    assert "target_layer=assets" in body or "assets 或 architecture" in body \
        or "只能是 assets 或 architecture" in body, \
        "★ prompt 必须解释 𝒦/𝒦_meta 与 layer 的对应"


def test_entry_from_candidate_carries_layer_and_enforces_k2():
    """★★★★★ 固化侧: entry 要带 target_layer，且 K2 不一致 ⇒ 拒。"""
    from dwc.organs.evolver import Mutator
    c = _mk_cand()
    assert c.target_layer == "assets", "R1/control_flow 应归 assets"
    e = Mutator.entry_from_candidate(c)
    assert e["target_layer"] == "assets"
    assert Mutator.check_entry("E:q:f", e) == []
    # ★ K2 破坏: 把 layer 改成 architecture（与 component 矛盾）
    c2 = _mk_cand(target_layer="architecture")
    with pytest.raises(ValueError) as ex:
        Mutator.entry_from_candidate(c2)
    assert "K2" in str(ex.value), \
        "★ component 与 layer 矛盾竟固化通过 ⇒ 说一套做一套"


def test_generation_unifies_layer_on_deterministic_candidates():
    """统一收口: 确定性候选也要有 target_layer（缺的从 component 推）。"""
    g = CandidateGenerator()
    sig = {"c": "E_VALUE", "q": "wrong_magnitude", "fn": "sum_first_n"}
    diffs = [{"args": 3, "actual": 3, "expected": 6},
             {"args": 5, "actual": 10, "expected": 15}]
    r = g.generate(sig, diffs, "def sum_first_n(n):\n    return sum(range(n))",
                   fn_name="sum_first_n")
    assert r["n"] >= 1
    for c in r["candidates"]:
        assert c.target_layer == "assets", \
            "★ 确定性候选缺 target_layer（统一收口没覆盖到）"


def test_r2_layer_stays_empty_and_k2_rejects_it():
    """R2 无 component ⇒ layer 也空 ⇒ K2 拒（**诚实的拒绝**，同 R35）。"""
    from dwc.organs.evolver import check_pairing
    g = CandidateGenerator()
    sig = {"c": "E_TYPE", "q": "wrong_magnitude", "fn": "mystery"}
    diffs = [{"args": 1, "actual": "7", "expected": 7},
             {"args": 2, "actual": "9", "expected": 9}]
    r = g.generate(sig, diffs, "def mystery(x):\n    return str(x * 2)",
                   fn_name="mystery")
    r2s = [c for c in r["candidates"] if c.rule.startswith("R2_")]
    if not r2s:
        return
    c = r2s[0]
    assert c.component == "" and c.target_layer == "", \
        "R2 不该有 component/layer（无依据）"
    assert check_pairing(c.component, c.target_layer), \
        "★ 空 component/layer 应被 K2 拒"

def test_component_vocab_is_single_sourced_everywhere():
    """★★★★★ R37 核心教训: **一个判据不许有四个来源**。

    ★★★ 我本轮实测的漂移路径（每一步都真实发生）:
      ① prompt 给两表 ⇒ 模型真选了 `component='code'`
      ② 生成校验只认 𝒦 ⇒ 拒了**合法**组件 ⇒ e2e step9 卡死
      ③ 固化 `entry_from_candidate` 同款拒
      ④ schema `check_entry` 同款拒
    ⇒⇒ ⇒★★ 四处都写 `in COMPONENT_VOCAB` ⇒ 必然漂移
      （同 R30 的 c/q 值域、R34 的 DIFF_FIELDS —— 我一再踩）
      ⇒ ⇒★ 收敛点: `check_component`（真源 = `layer_of`）

    本测试锁:
      a) `𝒦_meta` 里的 component **四处全部接受**
      b) 词表外的 component **四处全部拒绝**
      ⇒ 少改任何一处，这里就红
    """
    from dwc.organs.evolver import (Mutator, check_component,
                                    check_pairing, K_META, layer_of)
    from dwc.organs.candidates import CandidateGenerator

    for comp in K_META:            # a) 𝒦_meta 合法项
        assert check_component(comp) == [], \
            "单源拒了合法组件 %s" % comp
        layer_of(comp)              # 必须能归层
        # 固化侧
        e = Mutator.entry_from_candidate(_mk_cand(component=comp))
        assert Mutator.check_entry("E:q:f", e) == [], \
            "schema 拒了合法组件 %s: %s" % (comp,
                                          Mutator.check_entry("E:q:f", e))
    for bad in ("banana", "", "Code", "CODE"):   # b) 词表外
        assert check_component(bad), "单源放行了 %r" % bad
        with pytest.raises(ValueError):
            Mutator.entry_from_candidate(_mk_cand(component=bad))
        e2 = {"component": bad, "dimension": "D7",
              "target_layer": "assets", "target": "f",
              "m": "m", "m_source": "rule",
              "patch": "p", "rationale": "r"}
        assert any("component" in x
                   for x in Mutator.check_entry("E:q:f", e2)), \
            "schema 放行了 component=%r" % bad

    # 生成侧（LLM 给 𝒦_meta 项 ⇒ 必须通过，不许拒）
    g = CandidateGenerator(llm=_mock(LLMResult(
        ok=True, source="llm", text=json.dumps({
            "patches": ["s = s.lower()\nreturn s == s[::-1]"],
            "m": "m", "component": "code", "dimension": "D1",
            "target_layer": "assets"}))))  # ★ R38/D
    r = g.generate(SIG, DIFFS, BASE, fn_name="mystery")
    assert r["n"] >= 1, \
        ("★ 生成侧拒了 𝒦_meta 合法组件（why=%s）"
         % str(r.get("why"))[:150])
    c = r["candidates"][0]
    # ★★★ R38 裁决 D: code ⇒ **assets**（§3.1 只要 b_t+回归，无批准）
    #   这三行原来锁的是「code=architecture」（旧的一刀切）
    assert c.component == "code" and c.target_layer == "assets"
    # K2 与单源同向（真值表变了，K2 自动跟）
    assert check_pairing("code", "assets") == []
    assert check_pairing("code", "architecture"), \
        "★ D 生效后 code+architecture 应被 K2 拒（§3.1 不要求批准）"


def test_meta_component_reaches_fully_end_to_end():
    """★ 一条 𝒦_meta 组件从**生成到固化**全通（漏哪一环都会红）。"""
    from dwc.organs.evolver import Mutator, check_component
    g = CandidateGenerator(llm=_mock(LLMResult(
        ok=True, source="llm", text=json.dumps({
            "patches": ["return 1"], "m": "m",
            "component": "meta_evolution", "dimension": "D9",
            "target_layer": "architecture"}))))
    r = g.generate(SIG, DIFFS, BASE, fn_name="mystery")
    assert r["n"] >= 1, "① 生成侧拒了 meta_evolution"
    c = r["candidates"][0]
    assert c.target_layer == "architecture"
    assert check_component(c.component) == [], "② 单源拒了"
    e = Mutator.entry_from_candidate(c)
    assert e["target_layer"] == "architecture"
    assert Mutator.check_entry("E:q:f", e) == [], \
        "④ schema 拒了: %s" % Mutator.check_entry("E:q:f", e)

def test_layer_of_per_item_ruling_d():
    """★★★★★ R38 裁决 D · **逐项映射**（真值表不许再按表一刀切）。

    ★★★ 依据（用户 2026-10-06 拍板 D）:
      §3.1 code 「仍须过 b_t + 保护组回归」⇒ **无人工批准要求**
      §3.2 architecture「门通过 ≠ 可落地 ⇒ 须批准」
      §四① 原来的「𝒦_meta ⇒ architecture」一刀切 ⇒ code 被迫要批准
      ⇒⇒ **与 §3.1 明文冲突**
      ⇒ ⇒★ 改成逐项: 只有 `code` 从 architecture → assets，
        其余 𝒦_meta 项与原表一致

    本测试锁**每一项**的层（少改任何一项这里就红）。
    """
    from dwc.organs.evolver import layer_of, LAYER_BY_ITEM, check_pairing
    # ★ 逐项期望（依据写在注释里，可复核）
    expect = {
        # 𝒦 9 项全 assets（§四① 原样）
        "prompt": "assets", "control_flow": "assets", "config": "assets",
        "output_plumbing": "assets", "context_mgmt": "assets",
        "client_tool": "assets", "skill": "assets", "memory": "assets",
        "subagent": "assets",
        # 𝒦_meta 5 项按 §三 处置
        "code": "assets",             # ★ D 的唯一变化（§3.1 无批准）
        "architecture": "architecture",  # §3.2 须批准
        "meta_evolution": "architecture",  # §3.3 系统层（保守）
        "evaluator": "architecture",       # §3.4 不可编辑
        "external_source": "architecture",  # §3.5 只读登记
    }
    assert set(LAYER_BY_ITEM) == set(expect), \
        "★ 逐项表项数变了: 多 %s 少 %s" % (
            set(LAYER_BY_ITEM) - set(expect), set(expect) - set(LAYER_BY_ITEM))
    for comp, lay in expect.items():
        assert layer_of(comp) == lay, \
            "★ %s 应归 %s，实得 %s（逐项处置被改回一刀切？）" % (
                comp, lay, layer_of(comp))
    # ★★ D 的关键断言: code 与 architecture **分在两层**
    assert layer_of("code") != layer_of("architecture"), \
        "★ D 没生效: code 又被一刀切回 architecture"
    # ★ K2 随真值表自动跟（不用改判据）
    assert check_pairing("code", "assets") == []
    assert check_pairing("code", "architecture"), \
        "★ K2 应拒 code+architecture（§3.1 不要求批准）"


def test_code_component_is_fully_acceptable_end_to_end():
    """★ code 组件从生成到固化全通（D 之前它在中途被拒）。"""
    from dwc.organs.evolver import Mutator, layer_of
    g = CandidateGenerator(llm=_mock(LLMResult(
        ok=True, source="llm", text=json.dumps({
            "patches": ["s = s.lower()\nreturn s == s[::-1]"],
            "m": "m", "component": "code", "dimension": "D1",
            "target_layer": "assets"}))))
    r = g.generate(SIG, DIFFS, BASE, fn_name="mystery")
    assert r["n"] >= 1, ("① 生成侧拒了 code（why=%s）"
                         % str(r.get("why"))[:140])
    c = r["candidates"][0]
    assert c.target_layer == "assets", \
        "② code 应归 assets（§3.1 无批准要求）"
    e = Mutator.entry_from_candidate(c)
    assert Mutator.check_entry("E:q:f", e) == [], \
        "③ schema 拒了: %s" % Mutator.check_entry("E:q:f", e)
