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
    assert prompts_root(_sys.executable) is None


def test_note_miss_counts():
    from dwc.llm import prompt_ota as P
    before = P.miss_count()
    P.note_miss()
    assert P.miss_count() == before + 1
