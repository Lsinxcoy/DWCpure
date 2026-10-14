# -*- coding: utf-8 -*-
"""★★★ R274 · 聊天跨任务记忆（读口 chat_ctx＋写口 record_chat_outcome）。

★ 隔离：LESSONS/ARCHIVE 全 monkeypatch 到 tmp，禁碰生产 12 行。
★ 零真 LLM：只调纯函数＋record_lesson（gate=True），无网络。
"""
import io
import json as _json
import os as _os

import pytest

import dwc.agent_quality as AQ


@pytest.fixture()
def _iso(tmp_path, monkeypatch):
    lp = tmp_path / "lessons.jsonl"
    lp.write_text("", encoding="utf-8")
    monkeypatch.setattr(AQ, "LESSONS", str(lp))
    monkeypatch.setattr(AQ, "LESSONS_ARCHIVE", str(tmp_path / "arc.jsonl"))
    return lp


def _rows(lp):
    return [ _json.loads(l) for l in
             io.open(str(lp), encoding="utf-8") if l.strip()]


class TestChatRead:
    def test_empty_library_returns_prev_untouched(self, _iso):
        assert AQ.chat_ctx("修 TUI", None) is None
        assert AQ.chat_ctx("修 TUI", "上轮摘要") == "上轮摘要"

    def test_fail_lesson_merges_with_prev(self, _iso, tmp_path):
        _iso.write_text(
            _json.dumps({"task_id": "c1", "fail_mode": "chat_fail",
                         "task": "修 TUI 顶栏", "detail": "顶栏拼接忘包 surface，见报错 E1。",
                         "use_count": 0, "last_used": "", "utility": 0.0,
                         "tier": "short", "quality": 0.7},
                        ensure_ascii=False) + "\n", encoding="utf-8")
        out = AQ.chat_ctx("修 TUI 顶栏错位", "上轮摘要")
        assert "上轮摘要" in out and "历史教训" in out

    def test_broken_file_does_not_break_chat(self, tmp_path, monkeypatch):
        monkeypatch.setattr(AQ, "LESSONS", str(tmp_path))  # 目录非文件
        assert AQ.chat_ctx("任何任务", "摘要") == "摘要"


class TestChatWrite:
    def test_done_records_success_pattern(self, _iso):
        mode = AQ.record_chat_outcome(
            "修顶栏", {"status": "done", "answer": "已修复顶栏拼接，补 surface 包裹。见 diff 三处。"})
        assert mode == "success_pattern:chat"
        rows = _rows(_iso)
        assert len(rows) == 1 and rows[0]["fail_mode"] == mode

    def test_fail_records_chat_fail(self, _iso):
        mode = AQ.record_chat_outcome(
            "修顶栏", {"status": "timeout", "why": "LLM 60s 未回：重试三次仍空。"})
        assert mode == "chat_fail"
        assert _rows(_iso)[0]["fail_mode"] == "chat_fail"

    def test_empty_answer_dropped_by_gate(self, _iso):
        mode = AQ.record_chat_outcome("修顶栏", {"status": "done", "answer": ""})
        assert mode == "" and _rows(_iso) == []

    def test_broken_file_never_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(AQ, "LESSONS", str(tmp_path))
        assert AQ.record_chat_outcome("t", {"status": "done",
                                            "answer": "x"}) == ""


class TestDestructive:
    def test_direct_record_on_dir_raises(self, tmp_path, monkeypatch):
        monkeypatch.setattr(AQ, "LESSONS", str(tmp_path))
        with pytest.raises(OSError):
            AQ.record_lesson("c", "chat_fail", "t", "细节ndef。见日志。")
