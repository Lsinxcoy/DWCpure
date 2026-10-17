"""R306 · prompt OTA：版本化基线 + 本地缓存 + 灰度 + 缺失降级。"""
import hashlib
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(_HERE), "src"))


def _ver(name, manifest, key):
    m = manifest.get(name, {})
    stable, cand, pct = m.get("stable"), m.get("candidate"), m.get("pct", 0)
    if cand and pct and key:
        h = int(hashlib.md5(key.encode()).hexdigest(), 16) % 100
        if h < pct:
            return cand
    return stable


def test_loader_reads_file(tmp_path):
    from dwc.llm.prompt_ota import get_prompt
    (tmp_path / "task_exec.v1.md").write_text("基线甲", encoding="utf-8")
    t = get_prompt("task_exec", root=tmp_path,
                   manifest={"task_exec": {"stable": "v1"}})
    assert t == "基线甲"


def test_loader_missing_returns_none(tmp_path):
    from dwc.llm.prompt_ota import get_prompt
    assert get_prompt("nope", root=tmp_path, manifest={}) is None


def test_loader_appends_context(tmp_path):
    from dwc.llm.prompt_ota import get_prompt
    (tmp_path / "task_exec.v1.md").write_text("基线甲", encoding="utf-8")
    t = get_prompt("task_exec", root=tmp_path,
                   manifest={"task_exec": {"stable": "v1"}},
                   append="现场乙")
    assert t == "基线甲\n\n现场乙"


def test_canary_hash_pinned(tmp_path):
    from dwc.llm.prompt_ota import get_prompt
    (tmp_path / "task_exec.v1.md").write_text("稳", encoding="utf-8")
    (tmp_path / "task_exec.v2.md").write_text("候", encoding="utf-8")
    mf = {"task_exec": {"stable": "v1", "candidate": "v2", "pct": 100}}
    assert get_prompt("task_exec", root=tmp_path, manifest=mf,
                      key="k1") == "候"
    mf0 = {"task_exec": {"stable": "v1", "candidate": "v2", "pct": 0}}
    assert get_prompt("task_exec", root=tmp_path, manifest=mf0,
                      key="k1") == "稳"


def test_canary_missing_candidate_falls_back(tmp_path):
    from dwc.llm.prompt_ota import get_prompt
    (tmp_path / "task_exec.v1.md").write_text("稳", encoding="utf-8")
    mf = {"task_exec": {"stable": "v1", "candidate": "v9", "pct": 100}}
    assert get_prompt("task_exec", root=tmp_path, manifest=mf,
                      key="k1") == "稳"


def test_bad_input_never_raises(tmp_path):
    from dwc.llm.prompt_ota import get_prompt
    assert get_prompt("", root=tmp_path, manifest=None) is None
    assert get_prompt("x", root="不存在", manifest={}) is None


def test_with_fallback_hits_file(tmp_path):
    from dwc.llm.prompt_ota import with_fallback
    (tmp_path / "task_exec.v1.md").write_text("基线甲", encoding="utf-8")
    assert with_fallback("task_exec", "内嵌乙", root=tmp_path,
                         manifest={"task_exec": {"stable": "v1"}},
                         key="k") == "基线甲"


def test_with_fallback_misses_uses_inline(tmp_path):
    from dwc.llm.prompt_ota import with_fallback
    assert with_fallback("task_exec", "内嵌乙", root=tmp_path,
                         manifest={}) == "内嵌乙"


def test_find_root_walks_up(tmp_path):
    from dwc.llm.prompt_ota import prompts_root
    (tmp_path / "prompts").mkdir()
    deep = tmp_path / "src" / "dwc" / "llm"
    deep.mkdir(parents=True)
    assert prompts_root(str(deep / "x.py")) == str(tmp_path / "prompts")
    import sys as _sys
    import tempfile as _tf
    assert prompts_root(_tf.gettempdir() + "/x.py") is None


def test_note_miss_counts():
    from dwc.llm import prompt_ota as P
    before = P.miss_count()
    P.note_miss()
    assert P.miss_count() == before + 1


def test_render_basic(tmp_path):
    from dwc.llm.prompt_ota import render
    (tmp_path / "demo.v1.md").write_text("头@@x@@尾", encoding="utf-8")
    t = render("demo", {"x": "中"}, root=tmp_path,
               manifest={"demo": {"stable": "v1"}})
    assert t == "头中尾"


def test_render_missing_field_is_none(tmp_path):
    from dwc.llm.prompt_ota import render
    (tmp_path / "demo.v1.md").write_text("头@@x@@尾", encoding="utf-8")
    assert render("demo", {}, root=tmp_path,
                  manifest={"demo": {"stable": "v1"}}) is None


def test_render_no_template_is_none(tmp_path):
    from dwc.llm.prompt_ota import render
    assert render("demo", {"x": "1"}, root=tmp_path, manifest={}) is None


def test_render_here_finds_root(tmp_path):
    from dwc.llm.prompt_ota import render_here
    proot = tmp_path / "prompts"
    proot.mkdir()
    (proot / "demo.v1.md").write_text("头@@x@@尾", encoding="utf-8")
    import json as _js
    (proot / "manifest.json").write_text(
        _js.dumps({"demo": {"stable": "v1"}}), encoding="utf-8")
    deep = tmp_path / "src" / "dwc"
    deep.mkdir(parents=True)
    caller = str(deep / "m.py")
    assert render_here("demo", {"x": "中"}, caller) == "头中尾"
    assert render_here("demo", {}, caller) is None


def test_planner_render_matches_oldpath():
    from dwc.organs import planner as P
    from dwc.llm import prompt_ota as OTA
    for tv in ({"kind": "probe",
                "quantity": {"name": "n", "value": 3}},
               {"kind": "probe"}):
        new = P.compose_prompt(tv)
        orig = OTA.render
        OTA.render = lambda *a, **k: None
        try:
            old = P.compose_prompt(tv)
        finally:
            OTA.render = orig
        assert new == old and len(new) > 100


class _CapLLM:
    def __init__(self):
        self.prompts = []

    def complete(self, prompt, **kw):
        self.prompts.append(prompt)
        from types import SimpleNamespace
        return SimpleNamespace(ok=True, text='{"patches": []}',
                               source="fake", error="")


def test_fixer_render_matches_oldpath():
    from dwc.organs.candidates import CandidateGenerator as CG
    from dwc.llm import prompt_ota as OTA
    sig = {"c": "E_TYPE", "q": "q1"}
    diffs = [{"index": 0, "fn": "f", "args": [],
              "expected": 1, "actual": 2}]
    src = "def f():\n    return 1\n"
    cap = _CapLLM()
    CG(llm=cap)._llm_generate(sig, diffs, src, "f")
    new = cap.prompts[-1]
    cap2 = _CapLLM()
    orig = OTA.render
    OTA.render = lambda *a, **k: None
    try:
        CG(llm=cap2)._llm_generate(sig, diffs, src, "f")
    finally:
        OTA.render = orig
    old = cap2.prompts[-1]
    assert new == old and len(new) > 500


def test_drafter_render_matches_oldpath():
    from dwc.organs.evolver import LLMMutator as LM
    from dwc.llm import prompt_ota as OTA
    sigs = [{"c": "E", "q": "q", "fn": "f", "m": "mm",
             "task": "t"}]
    kw = {"context": "ctx", "want_code": True,
          "learned_hint": "hint"}
    new = LM()._prompt(sigs, **kw)
    orig = OTA.render
    OTA.render = lambda *a, **k: None
    try:
        old = LM()._prompt(sigs, **kw)
    finally:
        OTA.render = orig
    assert new == old and len(new) > 300
    new2 = LM()._prompt(sigs)
    OTA.render = lambda *a, **k: None
    try:
        old2 = LM()._prompt(sigs)
    finally:
        OTA.render = orig
    assert new2 == old2 and len(new2) > 200


def _serve_dir(tmp_path):
    import functools
    import http.server
    import threading
    (tmp_path / "demo.v1.md").write_text("远端甲", encoding="utf-8")
    h = functools.partial(http.server.SimpleHTTPRequestHandler,
                          directory=str(tmp_path))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    return srv


def test_fetch_remote_hits_http(tmp_path):
    from dwc.llm.prompt_ota import fetch_remote
    srv = _serve_dir(tmp_path)
    try:
        base = "http://127.0.0.1:%d" % srv.server_port
        assert fetch_remote(base, "demo", "v1") == "远端甲"
    finally:
        srv.shutdown()
        srv.server_close()


def test_fetch_remote_bad_url_is_none_fast():
    import time as _t
    from dwc.llm.prompt_ota import fetch_remote
    t0 = _t.time()
    assert fetch_remote("http://127.0.0.1:9", "demo", "v1",
                        timeout=2) is None
    assert fetch_remote("", "demo", "v1") is None
    assert _t.time() - t0 < 10


def test_get_prompt_remote_first(tmp_path):
    from dwc.llm.prompt_ota import get_prompt
    (tmp_path / "demo.v1.md").write_text("本地乙", encoding="utf-8")
    (tmp_path / "demo2.v1.md").write_text("本地丙", encoding="utf-8")
    (tmp_path / "r").mkdir()
    srv = _serve_dir(tmp_path / "r")
    try:
        base = "http://127.0.0.1:%d" % srv.server_port
        mf = {"demo": {"stable": "v1"}, "demo2": {"stable": "v1"}}
        t = get_prompt("demo", root=tmp_path, manifest=mf, remote=base)
        assert t == "远端甲"
        srv.shutdown()
        srv.server_close()
        # 远端挂了但 demo 已缓存⇒仍用缓存（bootstrap 语义，重启才刷新）
        assert get_prompt("demo", root=tmp_path, manifest=mf,
                          remote=base) == "远端甲"
        # 从未缓存的 demo2⇒落本地文件
        assert get_prompt("demo2", root=tmp_path, manifest=mf,
                          remote=base) == "本地丙"
    finally:
        try:
            srv.shutdown()
        except Exception:
            pass
        try:
            srv.server_close()
        except Exception:
            pass


def test_env_switch_off_by_default(tmp_path, monkeypatch):
    import os as _os
    from dwc.llm.prompt_ota import get_prompt
    (tmp_path / "demo.v1.md").write_text("本地乙", encoding="utf-8")
    (tmp_path / "r").mkdir()
    srv = _serve_dir(tmp_path / "r")
    try:
        base = "http://127.0.0.1:%d" % srv.server_port
        mf = {"demo": {"stable": "v1"}}
        monkeypatch.delenv("DWC_PROMPT_URL", raising=False)
        assert get_prompt("demo", root=tmp_path,
                          manifest=mf) == "本地乙"
        monkeypatch.setenv("DWC_PROMPT_URL", base)
        assert get_prompt("demo", root=tmp_path,
                          manifest=mf) == "远端甲"
    finally:
        try:
            srv.shutdown()
        except Exception:
            pass
        try:
            srv.server_close()
        except Exception:
            pass
