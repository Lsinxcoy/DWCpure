# -*- coding: utf-8 -*-
"""R400 · 留痕参数被截断 ⇒ judge 回读崩 ⇒ 动作被判失败。

★★★ 现场（2026-10-21 00:41 第二轮全池，code-locate 5 单全灭中的 4 单）：
  cl02 / cl04 / cl07 / cl08 的动作日志里都有同一条：

      {"ok": false,
       "error": "JSONDecodeError: Unterminated string starting at:
                 line 1 column 101 (char 100)"}

  但命令本身是好的（第一轮 rc=0、搜到了目标行）。

★ 根因链：
  ① `task_exec` 写留痕：`json.dumps({...})[:160]`
     ⇒ 长命令（`python -c "<脚本>"`）被**从中间切断**，留下非法 JSON
  ② `step_judge.judge_step` 回读该字段做去重签名：
         json.loads(e.get("args") or "{}")
     ⇒ 抛 JSONDecodeError（char 100 正是切点附近）
  ③ 异常冒到主循环 ⇒ 观察变成 `{"ok": false, "error": "JSONDecodeError..."}`
     ⇒ 模型以为自己命令写错了，重试同一个脚本 ⇒ 再崩 ⇒ 最后放弃/答错

★ 修法：
  ① 写侧：值可截断，**JSON 必须完整**；另存 `_h`（全量参数指纹），
     保证长命令即使值被截断也能区分（否则不同命令会被误判为重复）
  ② 读侧：`json.loads` 容错（坏留痕 ⇒ {}），签名优先用 `_h`
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import task_exec as T  # noqa: E402
from dwc.llm import step_judge as J  # noqa: E402


LONG = "import os,sys,re\npat=sys.argv[1]\n" + "x = 1\n" * 60


# ───────────────────── ① 写侧：快照必须是合法 JSON


def test_snapshot_is_valid_json_for_long_cmd():
    """★★★ 长命令的快照必须能被 json.loads 解析（现场就是这里断的）。"""
    step = {"op": "run", "cmd": ["python", "-c", LONG]}
    s = T._args_snapshot(step)
    assert isinstance(s, str) and s
    obj = json.loads(s)                      # 不许抛
    assert isinstance(obj, dict)


def test_snapshot_is_bounded():
    """★★ 快照必须有长度上限（日志不能无限膨胀）。"""
    step = {"op": "run", "cmd": ["python", "-c", LONG * 20]}
    s = T._args_snapshot(step)
    assert len(s) <= 240, len(s)
    json.loads(s)


def test_snapshot_hash_distinguishes_long_commands():
    """★★★ 两条长命令**前 160 字符相同**，指纹必须不同。

    否则截断后签名一样 ⇒ 不同命令被判"重复"（R301-A 的翻页误判同族）。
    """
    a = {"op": "run", "cmd": ["python", "-c", LONG + "\nprint('A')"]}
    b = {"op": "run", "cmd": ["python", "-c", LONG + "\nprint('B')"]}
    ha = json.loads(T._args_snapshot(a))["_h"]
    hb = json.loads(T._args_snapshot(b))["_h"]
    assert ha != hb, (ha, hb)


def test_snapshot_same_command_same_hash():
    """★★ 同一条命令 ⇒ 同指纹（去重要靠它）。"""
    a = {"op": "run", "cmd": ["python", "-c", LONG]}
    b = {"op": "run", "cmd": ["python", "-c", LONG]}
    assert (json.loads(T._args_snapshot(a))["_h"]
            == json.loads(T._args_snapshot(b))["_h"])


def test_snapshot_empty_when_no_args():
    """★★ 无参数 ⇒ 空串（与旧行为一致，不写垃圾）。"""
    assert T._args_snapshot({"op": "final"}) == ""


# ───────────────────── ② 读侧：坏留痕不许炸 judge


def _obs(target, args, ok=True):
    return {"round": 1, "phase": "obs", "op": "run",
            "target": target, "args": args, "ok": ok, "obs": "{}"}


def test_judge_survives_truncated_args_in_history():
    """★★★ 现场复现：历史里存着被截断的 args ⇒ judge 不许抛异常。"""
    bad = json.dumps({"cmd": ["python", "-c", LONG]})[:160]   # 现场形态
    with pytest.raises(Exception):
        json.loads(bad)                     # 先证明它确实是坏的
    step = {"op": "run", "cmd": ["python", "-c", "ls"]}
    # 不许抛
    verdict, why, rule = J.judge_step(step, recent_obs=[_obs("x", bad)])
    assert isinstance(verdict, str)


def test_judge_reads_hash_when_values_truncated():
    """★★ 值被截断但有 `_h` ⇒ 签名仍能区分不同命令（不许误判重复）。"""
    a = {"op": "run", "cmd": ["python", "-c", LONG + "\nprint('A')"]}
    b = {"op": "run", "cmd": ["python", "-c", LONG + "\nprint('B')"]}
    sa = T._args_snapshot(a)
    sb = T._args_snapshot(b)
    ta = str(a["cmd"])[:160]      # 真实留痕里 target 就是 cmd 的字符串
    # R1 规则：同签名历史命中 ≥2 次才判重复 ⇒ 给两条 a + 一条 b
    hist = [_obs(ta, sa), _obs(ta, sa), _obs(str(b["cmd"])[:160], sb)]
    verdict, why, rule = J.judge_step(a, recent_obs=hist)
    assert verdict == "noisy", (verdict, why)


def test_judge_distinct_hash_not_repeat():
    """★★ 指纹不同 ⇒ 不是重复（长命令改一个字符也要放行）。"""
    a = {"op": "run", "cmd": ["python", "-c", LONG + "\nprint('A')"]}
    b = {"op": "run", "cmd": ["python", "-c", LONG + "\nprint('B')"]}
    hist = [_obs("t", T._args_snapshot(a)), _obs("t", T._args_snapshot(b))]
    verdict, why, rule = J.judge_step(a, recent_obs=hist)
    assert verdict != "noisy", (verdict, why)


def test_judge_sig_args_uses_hash():
    """★★ 同前 160 字符、不同尾巴 ⇒ 签名不同。"""
    a = {"op": "run", "cmd": ["python", "-c", LONG + "\nprint('A')"]}
    b = {"op": "run", "cmd": ["python", "-c", LONG + "\nprint('B')"]}
    assert J._sig_args(a) != J._sig_args(b)
