# -*- coding: utf-8 -*-
"""R438 · 策略产物层：白名单 / 原子写 / 备份 / 回滚 / 消费者。

★ 锁的是"产物真的被消费者读到"：
  改前这些维度连产物文件都没有（context_mgmt / output_plumbing /
  client_tool / config），起草了也无处可写。

锁：
1. 缺文件 ⇒ 返回 defaults（不写盘）。
2. 白名单：未知键 / 越界 / bool 冒充 int 一律拒绝。
3. apply：备份 + 原子写 + 读回一致。
4. rollback：整份还原。
5. 消费者：`read_default_lines()` / `_cap_answer()` 跟着产物变。
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs import evo_targets as ET   # noqa: E402


@pytest.fixture()
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(ET, "ROOT", str(tmp_path))
    return tmp_path


def test_missing_file_returns_defaults(sandbox):
    got = ET.read("context_mgmt")
    assert got["read_default_lines"] == 200
    assert not (sandbox / "config" / "context_policy.json").exists()


def test_unknown_key_rejected(sandbox):
    with pytest.raises(ET.TargetError) as ei:
        ET.apply("context_mgmt", {"nope": 1})
    assert "未知键" in str(ei.value)


def test_out_of_bounds_rejected(sandbox):
    with pytest.raises(ET.TargetError) as ei:
        ET.apply("context_mgmt", {"read_default_lines": 99999})
    assert "上界" in str(ei.value)


def test_bool_is_not_int(sandbox):
    with pytest.raises(ET.TargetError):
        ET.apply("context_mgmt", {"read_default_lines": True})


def test_apply_writes_and_backs_up(sandbox):
    p = sandbox / "config" / "context_policy.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"read_default_lines": 200}), encoding="utf-8")
    out = ET.apply("context_mgmt", {"read_default_lines": 300})
    assert out["outcome"] == "applied"
    assert json.loads(p.read_text(encoding="utf-8"))["read_default_lines"] == 300
    assert out["backup"] and os.path.isfile(out["backup"])


def test_rollback_restores(sandbox):
    p = sandbox / "config" / "context_policy.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"read_default_lines": 200}), encoding="utf-8")
    out = ET.apply("context_mgmt", {"read_default_lines": 300})
    ET.rollback("context_mgmt", out["backup"])
    assert json.loads(p.read_text(encoding="utf-8"))["read_default_lines"] == 200


def test_consumer_read_default_lines(sandbox):
    from dwc.llm import task_exec as T
    p = sandbox / "config" / "context_policy.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"read_default_lines": 333}), encoding="utf-8")
    assert T.read_default_lines() == 333
    p.write_text(json.dumps({"read_default_lines": 120}), encoding="utf-8")
    assert T.read_default_lines() == 120, "mtime 变了必须重读（不许吃旧缓存）"


def test_consumer_answer_cap(sandbox):
    from dwc.llm import task_exec as T
    p = sandbox / "config" / "output_policy.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"max_answer_chars": 10}), encoding="utf-8")
    assert T._cap_answer("x" * 100) == "x" * 10


def test_smoke_context_mgmt(sandbox):
    from dwc.llm import task_exec as T
    p = sandbox / "config" / "context_policy.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"read_default_lines": 150}), encoding="utf-8")
    out = ET.smoke("context_mgmt")
    assert out["ok"] is True and out["consumer_saw"] == 150


def test_unregistered_component_is_loud(sandbox):
    with pytest.raises(ET.TargetError):
        ET.read("skill")


def test_subagent_override_reaches_cap_limit(sandbox):
    """subagent 维度：产物存在 ⇒ cap_limit 读到新值（不必重启）。"""
    from dwc.caps.registry import cap_limit
    p = sandbox / "config" / "subagent_policy.json"
    p.parent.mkdir(parents=True)
    p.write_text(json.dumps({"timeout_s": 900}), encoding="utf-8")
    assert cap_limit("delegate", "timeout_s", 600) == 900


def test_subagent_absent_keeps_old_default(sandbox):
    """产物不存在 ⇒ 走老路：capabilities.yaml 的值（600），
    而不是调用方传的 default（123）—— 覆盖层不许改变既有优先级。"""
    from dwc.caps.registry import cap_limit
    assert cap_limit("delegate", "timeout_s", 123) == 600


def test_root_is_repo_root_not_src():
    """★ 守卫：ROOT 必须是仓库根（曾少算一层 ⇒ 产物写进 src/config/）。"""
    assert os.path.isdir(os.path.join(ET.ROOT, "src", "dwc"))
    assert os.path.basename(ET.ROOT) != "src"
    assert ET.path_of("context_mgmt").startswith(ET.ROOT)
