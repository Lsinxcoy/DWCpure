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
