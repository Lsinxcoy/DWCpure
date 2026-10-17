# -*- coding: utf-8 -*-
"""R304-ABC：机制健康门+留痕统一+monitor计数校准。"""
import json

from dwc.foundation.mech_health import health, advise
from dwc.llm.mech_trace import emit, read_mech_events
from dwc.llm.monitor import record, calibrate


def test_health_rate():
    evs = [{"mech": "sec_review", "event": "review", "ok": True},
           {"mech": "sec_review", "event": "review", "ok": False}]
    h = health("sec_review", evs)
    assert h == {"n": 2, "ok_rate": 0.5}


def test_health_empty():
    assert health("sec_review", []) == {"n": 0, "ok_rate": None}


def test_advise_flags_low():
    evs = [{"mech": "monitor_skip", "event": "skip", "ok": False}] * 3
    out = advise(["monitor_skip", "sec_review"], evs, min_n=3, floor=0.9)
    assert any(a["mech"] == "monitor_skip" and a["action"] == "review"
               for a in out)
    assert not any(a["mech"] == "sec_review" for a in out)  # 无数据不立案


def test_emit_shape(tmp_path):
    p = str(tmp_path / "t.jsonl")
    emit({"mech": "monitor_skip", "event": "skip", "ok": True}, path=p)
    evs = read_mech_events(path=p)
    assert evs[0]["mech"] == "monitor_skip" and "ts" in evs[0]
    # 坏输入永不抛错
    emit(None, path=p)
    emit({"mech": "x"}, path=p)  # 缺字段不写
    assert len(read_mech_events(path=p)) == 1


def test_record_calibrate(tmp_path):
    p = str(tmp_path / "m.jsonl")
    for _ in range(40):
        record("skip", path=p)
    for _ in range(10):
        record("ran", path=p)
    c = calibrate(path=p)
    assert c["n"] == 50 and abs(c["skip_rate"] - 0.8) < 1e-9
    assert c["suggest"] in (1, 2, 3)
    # 空文件不崩
    c0 = calibrate(path=str(tmp_path / "none.jsonl"))
    assert c0["n"] == 0 and c0["suggest"] == 2
