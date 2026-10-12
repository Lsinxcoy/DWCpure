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
#: ★ R220 · ask 级（R218/R220 头部 agent 对标: OpenCode allow/deny/ask 三态）——
#:   不硬拒但**停下来要人工授权**: 外发网络/改动仓库外状态/删单文件/改 git 远端。
#:   形态: 动作拒 + obs 带 ask_required — LLM 换路或 final 说明; 报告留痕。
_ASK = ("git push", "git commit", "curl ", "wget ", "ssh ", "scp ",
        "pip install", "npm install", "del ", "rm ", "rmdir",
        "move ", "copy ", "shutdown", "reboot")
#: ★ R218 · 自我认知（维护者写入, agent 只读 — 结构性: write 白名单写不进 config）
SELF_MD = os.path.join(ROOT, "config", "dwc_self.md")
#: ★ R218 · 会话留痕（头部 agent 的 session 概念最小形态: 每任务一个 jsonl）
SESSIONS = os.path.join(ROOT, "var", "dwc_sessions")


def _ask_level(cmd_joined: str) -> Optional[str]:
    """run 命令的三态分级: 黑名单=None(调用方硬拒); ask 命中=该词; 都无=放行。"""
    for w in _ASK:
        if w in cmd_joined:
            return w
    return None


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
        ask = _ask_level(joined)
        if ask:
            # ★ R220 · ask 三态: 不执行但**明确告知需授权**（LLM 换路或
            #   final 说明; 报告 ask_required 留痕 — 不静默不硬吞）
            raise TaskExecError(
                "ask_required: %r 类操作需人工授权（当前模式不自动执行;"
                " 换个不用它的办法, 或在 final 里说明需要人工做哪步）"
                % ask)
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


def _extract_json(text: str):
    """★ R217 · LLM 响应 JSON 鲁棒提取（判据: 拿到能用的 dict, 不苛求纯净）。

    容错序（bench llm_format 失败实测形态）:
    ① 整体 json.loads
    ② 剥 ```json / ``` 代码块包裹
    ③ 从后往前逐行 json.loads（模型常在 JSON 后追加说明文本）
    ④ 首个 { 到最后一个 } 的子串
    全失败返回 None（不猜不编 — 提取的是模型给的, 不是造的）。
    """
    t = (text or "").strip()
    if not t:
        return None
    for cand in (t, t.strip("`"), t.replace("```json", "").replace("```", "").strip()):
        try:
            o = json.loads(cand)
            if isinstance(o, dict):
                return o
        except Exception:                      # noqa: BLE001
            pass
    for ln in reversed(t.splitlines()):
        ln2 = ln.strip().strip("`").strip()
        if not ln2:
            continue
        try:
            o = json.loads(ln2)
            if isinstance(o, dict):
                return o
        except Exception:                      # noqa: BLE001
            continue
    a, b = t.find("{"), t.rfind("}")
    if 0 <= a < b:
        try:
            o = json.loads(t[a:b + 1])
            if isinstance(o, dict):
                return o
        except Exception:                      # noqa: BLE001
            pass
    return None


def execute_user_task(task: str, *, llm: Any, max_rounds: int = 4,
                      ctx: Optional[str] = None,
                      task_id: Optional[str] = None) -> Dict[str, Any]:
    """★ 接单执行: 任务描述 → 多轮 LLM+白名单动作 → final 结果。

    返回报告 dict: {task_id?/task, status, rounds, answer, artifacts,
    actions_log, why} — status ∈ {done, incomplete}。
    """
    os.makedirs(WORK, exist_ok=True)
    # ★ R218 · 自我认知注入（每次接单加载, 跨任务存活 — CLAUDE.md 同款;
    #   文件缺席=空串不装有, 读失败不炸单）
    self_md = ""
    try:
        if os.path.exists(SELF_MD):
            self_md = io.open(SELF_MD, encoding="utf-8").read()[:4000]
    except OSError:
        self_md = ""
    # ★ R218 · 会话留痕（session 概念最小形态: 每任务一个 jsonl, 轮转可查）
    sid = (task_id or ("T_" + time.strftime("%m%d_%H%M%S")))
    sess_path = os.path.join(SESSIONS, sid + ".jsonl")

    _sess_fail = globals().setdefault("_SESS_FAIL", [0])   # G7: 静默必须计数

    def _sess(ev: Dict[str, Any]) -> None:
        try:
            os.makedirs(SESSIONS, exist_ok=True)
            with io.open(sess_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"at": time.strftime("%H:%M:%S"), **ev},
                                    ensure_ascii=False)[:2000] + "\n")
        except OSError as exc:               # 留痕失败不阻断主链, 但必须计数
            _sess_fail[0] += 1               # （G7: 记不了不许杀主链, 也不许无痕）
            if _sess_fail[0] <= 3:           # 前 3 次写 stderr（不刷屏）
                import sys as _sys
                _sys.stderr.write("session 留痕失败×%d: %s\n"
                                  % (_sess_fail[0], exc))
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
    if self_md:
        system += ("\n\n# 自我认知（你的持久记忆文件, 每单加载）\n" + self_md)
    log: List[Dict[str, Any]] = []
    prompt = "任务: %s\n%s" % (task, ("\n上下文: " + ctx) if ctx else "")
    for rnd in range(1, max_rounds + 1):
        res = llm.complete(prompt, system=system, max_tokens=1600,
                           json_mode=True)
        if not getattr(res, "ok", False):
            return {"task": task, "task_id": sid, "status": "incomplete",
                    "rounds": rnd,
                    "why": "LLM 失败: %s" % getattr(res, "error", "?"),
                    "actions_log": log}
        step = _extract_json(res.text)
        if step is None:
            # ★ R217 · 容错后仍失败才报 incomplete（bench 最大失败单点
            #   llm_format: 模型爱包 ```json 代码块/多行/前后缀文本）
            return {"task": task, "task_id": sid, "status": "incomplete",
                    "rounds": rnd,
                    "why": "LLM 响应非 JSON（容错提取后仍失败）: %s"
                           % str(res.text)[:120],
                    "actions_log": log}
        op = step.get("op")
        log.append({"round": rnd, "analysis": str(step.get("analysis", ""))[:300],
                    "op": op})
        _sess({"round": rnd, "op": op,
               "analysis": str(step.get("analysis", ""))[:200]})
        if op == "final":
            _sess({"round": rnd, "op": "final", "answer":
                   str(step.get("answer", ""))[:200]})
            return {"task": task, "task_id": sid, "status": "done",
                    "rounds": rnd,
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
    return {"task": task, "task_id": sid, "status": "incomplete",
            "rounds": max_rounds,
            "why": "达轮数上限未 final", "actions_log": log}
