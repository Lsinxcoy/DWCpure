# -*- coding: utf-8 -*-
"""R438 · 技能维度：跨进程落盘 + 选择 + 注入。

★ 锁的是"技能真的存在过"：
  改前 `Mutator.SKILLS` 只是进程内 dict（无落盘、无消费者）
  ⇒ 技能维度在生产上等于不存在。

锁：
1. save → SKILL.md 真文件（frontmatter 可解析）。
2. load_all 能跨"进程"读回（新调用 = 新读盘）。
3. select 只在词元重叠 ≥2 时命中。
4. skill_register 落盘（不是只写内存）。
5. context 注入正文。
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs import skill_store as SS   # noqa: E402


def test_save_writes_real_file(tmp_path, monkeypatch):
    monkeypatch.setattr(SS, "SKILLS_DIR", str(tmp_path / "skills"))
    out = SS.save("read_fact_guard", description="读事实前先取证",
                  content="先 search_code 再回答。", trigger="读取 事实 取证",
                  version=2)
    assert out["ok"] and os.path.isfile(out["path"])
    text = open(out["path"], encoding="utf-8").read()
    assert text.startswith("---") and "version: 2" in text


def test_load_all_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(SS, "SKILLS_DIR", str(tmp_path / "skills"))
    SS.save("s1", description="d1", content="body1", trigger="alpha beta")
    got = SS.load_all()
    assert "s1" in got
    assert got["s1"]["body"].startswith("body1")
    assert got["s1"]["version"] == 1


def test_select_requires_overlap(tmp_path, monkeypatch):
    monkeypatch.setattr(SS, "SKILLS_DIR", str(tmp_path / "skills"))
    SS.save("s1", description="读取事实", content="先取证", trigger="读取 事实")
    assert SS.select("读取事实再回答")          # 重叠 ≥2
    assert not SS.select("完全无关的问题")       # 零重叠


def test_select_prefers_higher_version(tmp_path, monkeypatch):
    monkeypatch.setattr(SS, "SKILLS_DIR", str(tmp_path / "skills"))
    SS.save("s1", description="读取事实", content="v1", trigger="读取 事实",
            version=1)
    SS.save("s2", description="读取事实", content="v2", trigger="读取 事实",
            version=5)
    hits = SS.select("读取事实", k=1)
    assert hits and hits[0]["name"] == "s2"


def test_skill_register_persists(tmp_path, monkeypatch):
    from dwc.organs import evolver as EV
    monkeypatch.setattr(SS, "SKILLS_DIR", str(tmp_path / "skills"))
    out = EV.Mutator.skill_register("code_fix_004", description="斐波那契",
                                    content="按 0,1 起算累加", trigger="code_fix")
    assert out["registered"] is True
    assert out["path"] and os.path.isfile(out["path"])
    assert "code_fix_004" in SS.load_all()


def test_context_returns_body(tmp_path, monkeypatch):
    monkeypatch.setattr(SS, "SKILLS_DIR", str(tmp_path / "skills"))
    SS.save("s1", description="读取事实", content="BODY_MARKER 先取证",
            trigger="读取 事实")
    out = SS.context("读取事实再回答")
    assert "BODY_MARKER" in out


def test_empty_dir_is_not_an_error(tmp_path, monkeypatch):
    monkeypatch.setattr(SS, "SKILLS_DIR", str(tmp_path / "nope"))
    assert SS.load_all() == {}
    assert SS.context("任意任务") == ""


def test_skills_dir_is_repo_root_not_src():
    """★ 守卫：技能目录必须在仓库根（曾少算一层 ⇒ 写进 src/skills/）。"""
    assert SS.SKILLS_DIR == os.path.join(SS.ROOT, "skills")
    assert os.path.isdir(os.path.join(SS.ROOT, "src", "dwc"))
    assert os.path.basename(SS.ROOT) != "src"
