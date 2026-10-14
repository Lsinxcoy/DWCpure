# -*- coding: utf-8 -*-
"""R266 · 任务知识回流闭环（ABC — 用户 2026-10-14 拍板 "完整执行ABC"）。

论断（用户）: 任务执行的记忆包括搜索到的信源/知识/论文是驱动系统进化的重要
组成部分。实测断路: web_read/web_read 结果只进 session 死档, 零进化消费。

A 沉淀: _extract_sources → dwc_sources.jsonl + 论文分拣 dwc_reading_list
B 检索: recall_sources/sources_context → task_exec 内部注入 system
C 进化: maybe_dispatch_reading → reading_list 未派发论文 → inbox 深读任务
"""
import io
import json
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))
sys.path.insert(0, os.path.join(_ROOT, "scripts"))

from dwc.llm import task_exec as TE  # noqa: E402
from dwc import agent_quality as Q  # noqa: E402


def _obs_row(op, target, obs, rnd=1):
    return {"round": rnd, "phase": "obs", "op": op, "target": target,
            "ok": True, "obs": json.dumps(obs, ensure_ascii=False)[:300]}


def test_extract_sources_writes_and_sorts(tmp_path, monkeypatch):
    """★★★ A 层: web_search/web_read 信源提取落 sources; arxiv 分拣
    reading_list 且同 url 去重; 零信源不写。"""
    src = tmp_path / "dwc_sources.jsonl"
    rd = tmp_path / "dwc_reading_list.jsonl"
    monkeypatch.setattr(TE, "SOURCES", str(src))
    monkeypatch.setattr(TE, "READING", str(rd))
    log = [
        {"round": 1, "analysis": "x"},                       # 非 obs 行跳过
        _obs_row("web_search", "arxiv RSI 自进化",
                 {"ok": True, "results": []}),
        _obs_row("web_read", "https://arxiv.org/abs/2610.12668",
                 {"ok": True, "content": "ReHarness 提出 0.240..."}),
        _obs_row("web_read", "https://example.com/guide",
                 {"ok": True, "content": "a doc"}),
    ]
    TE._extract_sources(log, task_id="T_x", task="研究 RSI 论文",
                        answer="ReHarness 可借鉴", artifacts=["var/inbox_work/x.md"])
    rows = [json.loads(l) for l in io.open(str(src), encoding="utf-8")]
    assert len(rows) == 1
    r = rows[0]
    assert r["queries"] == ["arxiv RSI 自进化"]
    assert len(r["urls"]) == 2
    assert r["findings"] == "ReHarness 可借鉴"
    rd_rows = [json.loads(l) for l in io.open(str(rd), encoding="utf-8")]
    assert [x["url"] for x in rd_rows] == ["https://arxiv.org/abs/2610.12668"]
    assert rd_rows[0]["dispatched_at"] is None
    # 去重: 再沉淀同 url 不重复进 reading_list
    TE._extract_sources(log, task_id="T_y", task="again")
    rd_rows2 = [json.loads(l) for l in io.open(str(rd), encoding="utf-8")]
    assert len(rd_rows2) == 1, "reading_list 应去重"
    # 零信源零发现不写
    TE._extract_sources([], task_id="T_z", task="nothing")   # 真·零信源
    rows2 = [json.loads(l) for l in io.open(str(src), encoding="utf-8")]
    assert len(rows2) == 2, "T_y(有信源)写了2行; 空 log 调用不该追加: %d" % len(rows2)
    assert all(r["task_id"] != "T_z" for r in rows2), "空 log 不该留行"


def test_sources_context_recall(tmp_path, monkeypatch):
    """★★ B 层检索: 相关任务的信源+发现 top-k 命中, 文本块含 url。"""
    src = tmp_path / "dwc_sources.jsonl"
    rec = {"task_id": "T_a", "at": "2026-10-14T10:00:00+08:00",
           "task": "研究 ReHarness 修订机制",
           "queries": ["recurrent harness arxiv"],
           "urls": [{"url": "https://arxiv.org/abs/2610.12668",
                     "kind": "paper", "snippet": "revision chain"}],
           "findings": "记忆修订的双轨设计", "artifacts": []}
    src.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(Q, "SOURCES", str(src))
    hits = Q.recall_sources("ReHarness 论文读一下", k=3)
    assert hits and hits[0]["task_id"] == "T_a"
    ctx = Q.sources_context("ReHarness 论文读一下")
    assert "https://arxiv.org/abs/2610.12668" in ctx
    assert "可复用" in ctx
    # 零命中零开销
    assert Q.sources_context("完全无关的烹饪话题") == ""


def test_system_injects_task_memory(tmp_path, monkeypatch):
    """★★★ B 层注入行为: execute_user_task 每单 system 含"任务记忆"段
    （从真 sources 文件检索 — 零命中时不注, 命中时注）。"""
    src = tmp_path / "dwc_sources.jsonl"
    rec = {"task_id": "T_a", "at": "2026-10-14T10:00:00+08:00",
           "task": "读 core.py 主类", "queries": [],
           "urls": [{"url": "https://example.com/core", "kind": "doc",
                     "snippet": "Core 主类"}],
           "findings": "core.py 720 行", "artifacts": []}
    src.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(Q, "SOURCES", str(src))
    monkeypatch.setattr(TE, "SOURCES", str(src))

    class FakeLLM:
        def __init__(self):
            self.calls = []
        def complete(self, prompt, *, system=None, max_tokens=None,
                     json_mode=False, images=None):
            self.calls.append({"prompt": prompt, "system": system})
            if len(self.calls) >= 2:
                return type("R", (), {"ok": True, "text":
                    '{"op": "final", "answer": "ok"}', "error": ""})()
            return type("R", (), {"ok": True, "text":
                '{"op": "final", "answer": "done"}', "error": ""})()

    llm = FakeLLM()
    TE.execute_user_task("读 core.py 看主类结构", llm=llm, max_rounds=3)
    sys0 = llm.calls[0]["system"] or ""
    assert "任务记忆" in sys0, "未注入任务记忆段"
    assert "https://example.com/core" in sys0 or "core.py" in sys0


def test_reading_dispatch(tmp_path, monkeypatch):
    """★★★ C 层投单: 未派发论文 → inbox 深读单 + 标 dispatched_at;
    同 url 查重不重投; 已全部派发返回 None。"""
    import dwc_agent as AG
    rd = tmp_path / "reading.jsonl"
    inbox = tmp_path / "inbox.jsonl"
    done = tmp_path / "done.json"
    done.write_text("{}", encoding="utf-8")
    rd.write_text(json.dumps(
        {"url": "https://arxiv.org/abs/2610.12668", "first_seen": "2026-10-14",
         "task_id": "T_a", "dispatched_at": None}) + "\n", encoding="utf-8")
    inbox.write_text("", encoding="utf-8")
    monkeypatch.setattr(TE, "READING", str(rd))
    monkeypatch.setattr(AG, "INBOX", str(inbox))
    monkeypatch.setattr(AG, "INBOX_DONE", str(done))

    out = AG.maybe_dispatch_reading()
    assert out and out["url"] == "https://arxiv.org/abs/2610.12668"
    rows = [json.loads(l) for l in io.open(str(inbox), encoding="utf-8")]
    assert len(rows) == 1 and "深读" in rows[0]["task"]
    assert "var/inbox_work/" in rows[0]["task"], "产出路径必须受白名单约束"
    rd_rows = [json.loads(l) for l in io.open(str(rd), encoding="utf-8")]
    assert rd_rows[0]["dispatched_at"], "投单后必须标 dispatched_at"
    # 已派发（inbox 有同 url + dispatched 标记）⇒ 不重投
    assert AG.maybe_dispatch_reading() is None
    rows2 = [json.loads(l) for l in io.open(str(inbox), encoding="utf-8")]
    assert len(rows2) == 1, "不该重投"


def test_reading_dispatch_daily_cap(tmp_path, monkeypatch):
    """★ C 层日限: 24h 内已有 3 单派发 ⇒ 不再投（防刷爆 LLM）。"""
    import dwc_agent as AG
    rd = tmp_path / "reading.jsonl"
    inbox = tmp_path / "inbox.jsonl"
    done = tmp_path / "done.json"
    done.write_text("{}", encoding="utf-8")
    inbox.write_text("", encoding="utf-8")
    now = time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    rows = [{"url": "https://arxiv.org/abs/%d" % i, "first_seen": now,
             "task_id": "T_%d" % i, "dispatched_at": now}
            for i in range(3)]
    rows.append({"url": "https://arxiv.org/abs/new", "first_seen": now,
                 "task_id": "T_new", "dispatched_at": None})
    rd.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    monkeypatch.setattr(TE, "READING", str(rd))
    monkeypatch.setattr(AG, "INBOX", str(inbox))
    monkeypatch.setattr(AG, "INBOX_DONE", str(done))
    assert AG.maybe_dispatch_reading() is None, "日限 3 单应拦住"


def test_g7_sources_failure_traces(tmp_path, monkeypatch, capsys):
    """★ G7: 沉淀写失败必须计数+stderr, 不阻断主链。"""
    monkeypatch.setattr(TE, "SOURCES", str(tmp_path / "sources.jsonl"))
    monkeypatch.setattr(TE, "READING", str(tmp_path / "reading.jsonl"))

    def _boom(*a, **kw):
        raise OSError("磁盘满(模拟)")
    monkeypatch.setattr(TE.os, "makedirs", _boom)
    before = TE._SRC_FAIL[0]
    TE._extract_sources([_obs_row("web_search", "q", {})],
                        task_id="T_f", task="t")   # 不许抛
    assert TE._SRC_FAIL[0] == before + 1, "失败必须计数"


def test_reading_dispatch_multi_source(tmp_path, monkeypatch):
    """★★★ R266C 多库: 用户链(.dwc)的 reading 候选必须被 E: agent 扫到并
    消费（双副本纪律 — 2026-10-14 活体发现的分裂）。"""
    import dwc_agent as AG
    own = tmp_path / "own_reading.jsonl"
    ext = tmp_path / "ext_reading.jsonl"
    inbox = tmp_path / "inbox.jsonl"
    done = tmp_path / "done.json"
    done.write_text("{}", encoding="utf-8")
    inbox.write_text("", encoding="utf-8")
    own.write_text("", encoding="utf-8")                    # 自己的空
    ext.write_text(json.dumps(
        {"url": "https://arxiv.org/abs/2609.28416", "first_seen": "x",
         "task_id": "T_ext", "dispatched_at": None}) + "\n", encoding="utf-8")
    monkeypatch.setattr(AG, "INBOX", str(inbox))
    monkeypatch.setattr(AG, "INBOX_DONE", str(done))
    monkeypatch.setattr(AG, "_reading_sources",
                        lambda: [str(own), str(ext)])
    out = AG.maybe_dispatch_reading()
    assert out and out["url"] == "https://arxiv.org/abs/2609.28416"
    # 回写目标=外部源（标 dispatched_at）
    ext_rows = [json.loads(l) for l in io.open(str(ext), encoding="utf-8")]
    assert ext_rows[0]["dispatched_at"], "外部源必须被标 dispatched"
    assert json.loads(own.read_text(encoding="utf-8") or "null") is None or \
        own.read_text(encoding="utf-8") == "", "空的自有源不被改写"
