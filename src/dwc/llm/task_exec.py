# -*- coding: utf-8 -*-
"""R209 · LLM 用户任务执行器（独立 agent 的接单能力 — 用户 2026-10-12 拍板）。

★★★ 定位（G1 定位门）: **DWC-AUTO（自我强化）** —— 本模块让 agent 能消费
  用户委托的任务（inbox），是 agent 对外能力面而非记忆底座。

★★★ TRUTH_SOURCE: 本模块**不做判定**（判分永远在 judge — 三分离纪律）;
  它只执行 LLM 给的动作并回传观察。无真值源判定面（G2 语义: 非评分模块）。

★ 执行契约（收敛的 ARSI 路子 — actor 诚实边界④的接单版）:
  LLM 每轮返回 JSON: {"analysis": str, "op": "read|write|run|final", ...}
  · read  {"path"}            读文件（ROOT 内任意）
  · write {"path","content"}  写文件（**只许 var/inbox_work/ 下** — 工作区隔离）
  · run   {"cmd":[argv...]}   跑命令（列表参数非 shell; cwd=ROOT; timeout 60s;
                              危险词黑名单: rm -rf/mkfs/format/del /s 等）
  · final {"answer","artifacts"}  产出结论（终轮）
  多轮循环（默认 ≤4 轮）; 每轮动作结果回喂 LLM。超轮/LLM 失败 ⇒
  status=incomplete 带原因（不静默装完成）。

★ LLMClient 纪律: complete() 不抛异常（失败带 error 返回）——本模块把
  LLM 失败当**正常分支**处理（incomplete + why），不是 try/except 吞。
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import time
from typing import Any, Dict, List, Optional

ROOT = r"E:/Divine Wisdom Core"
WORK = os.path.join(ROOT, "var", "inbox_work")
#: 危险命令黑名单（子串匹配; run 动作的护栏之一 — 不是完备沙箱, 是护栏）
_FORBIDDEN = ("rm -rf", "mkfs", "format ", "del /s", "rd /s",
              "shutdown", "reg delete", ":(){", "dd if=")


class TaskExecError(Exception):
    pass


def _guard_path(path: str, *, write: bool) -> str:
    """路径护栏: 读限 ROOT 内; 写只许 var/inbox_work/。"""
    p = os.path.normpath(os.path.join(ROOT, path) if not os.path.isabs(path)
                         else path)
    if write:
        w = os.path.normpath(WORK)
        if not (p == w or p.startswith(w + os.sep)):
            raise TaskExecError("写只许 var/inbox_work/ 下: %s" % path)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        return p
    if not os.path.normpath(p).startswith(os.path.normpath(ROOT)):
        raise TaskExecError("读限仓库内: %s" % path)
    return p


def _do_action(op: str, args: Dict[str, Any]) -> Dict[str, Any]:
    """执行一个白名单动作 → 观察（回喂 LLM 的材料）。"""
    if op == "read":
        p = _guard_path(str(args.get("path", "")), write=False)
        with io.open(p, encoding="utf-8", errors="replace") as fh:
            txt = fh.read()
        n = txt.count("\n") + 1
        return {"ok": True, "n_lines": n,
                "content": txt[:8000] + ("\n…(截断)" if len(txt) > 8000 else "")}
    if op == "write":
        p = _guard_path(str(args.get("path", "")), write=True)
        content = str(args.get("content", ""))
        with io.open(p, "w", encoding="utf-8") as fh:
            fh.write(content)
        return {"ok": True, "path": os.path.relpath(p, ROOT),
                "bytes": len(content.encode("utf-8"))}
    if op == "run":
        cmd = args.get("cmd")
        if not isinstance(cmd, list) or not cmd:
            raise TaskExecError("cmd 必须是非空 argv 列表: %r" % (cmd,))
        joined = " ".join(str(x) for x in cmd).lower()
        hit = [w for w in _FORBIDDEN if w in joined]
        if hit:
            raise TaskExecError("危险命令黑名单命中 %s: %s" % (hit, joined[:120]))
        try:
            r = subprocess.run([str(x) for x in cmd], cwd=ROOT,
                               capture_output=True, text=True, timeout=60,
                               errors="replace")
            return {"ok": r.returncode == 0, "rc": r.returncode,
                    "out": (r.stdout or "")[:6000],
                    "err": (r.stderr or "")[:1500]}
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "timeout 60s"}
    raise TaskExecError("未知动作 op=%r（白名单: read/write/run/final）" % op)


def execute_user_task(task: str, *, llm: Any, max_rounds: int = 4,
                      ctx: Optional[str] = None) -> Dict[str, Any]:
    """★ 接单执行: 任务描述 → 多轮 LLM+白名单动作 → final 结果。

    返回报告 dict: {task_id?/task, status, rounds, answer, artifacts,
    actions_log, why} — status ∈ {done, incomplete}。
    """
    os.makedirs(WORK, exist_ok=True)
    system = (
        "你是 DWC 独立 agent 的任务执行体。完成用户的任务。每轮只输出一个"
        " JSON 对象（无多余文本）: {\"analysis\": \"本步思考\", \"op\":"
        " \"read|write|run|final\", ...参数}。"
        " · 读文件: {\"op\":\"read\",\"path\":\"相对路径\"}"
        " · 写文件(只许 var/inbox_work/ 下): {\"op\":\"write\",\"path\":"
        "\"var/inbox_work/x.md\",\"content\":\"...\"}"
        " · 跑命令(argv列表,60s超时): {\"op\":\"run\",\"cmd\":[\"python\",\"-c\",\"...\"]}"
        " · 任务完成时: {\"op\":\"final\",\"answer\":\"结论(中文)\","
        "\"artifacts\":[\"写出的文件相对路径\"]}"
        " 有充分信息就尽快 final；不确定就先 read 探查。禁止越权写路径。")
    log: List[Dict[str, Any]] = []
    prompt = "任务: %s\n%s" % (task, ("\n上下文: " + ctx) if ctx else "")
    for rnd in range(1, max_rounds + 1):
        res = llm.complete(prompt, system=system, max_tokens=1600,
                           json_mode=True)
        if not getattr(res, "ok", False):
            return {"task": task, "status": "incomplete", "rounds": rnd,
                    "why": "LLM 失败: %s" % getattr(res, "error", "?"),
                    "actions_log": log}
        try:
            step = json.loads(res.text.strip().splitlines()[-1])
        except Exception as exc:               # noqa: BLE001 — 解析失败如实报
            return {"task": task, "status": "incomplete", "rounds": rnd,
                    "why": "LLM 响应非 JSON: %s / %s"
                           % (exc, str(res.text)[:120]),
                    "actions_log": log}
        op = step.get("op")
        log.append({"round": rnd, "analysis": str(step.get("analysis", ""))[:300],
                    "op": op})
        if op == "final":
            return {"task": task, "status": "done", "rounds": rnd,
                    "answer": str(step.get("answer", "")),
                    "artifacts": list(step.get("artifacts") or []),
                    "actions_log": log}
        try:
            obs = _do_action(op, step)
        except TaskExecError as exc:
            obs = {"ok": False, "error": str(exc)}
        except Exception as exc:               # noqa: BLE001
            obs = {"ok": False, "error": "%s: %s" % (type(exc).__name__, exc)}
        prompt = ("任务: %s\n上一步动作观察(JSON): %s\n请继续（下一步 op）"
                  % (task, json.dumps(obs, ensure_ascii=False)[:8000]))
    return {"task": task, "status": "incomplete", "rounds": max_rounds,
            "why": "达轮数上限未 final", "actions_log": log}
