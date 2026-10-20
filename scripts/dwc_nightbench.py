# -*- coding: utf-8 -*-
"""dwc_nightbench · 无人值守跑批（R260 · 短板 2 — 真实流量压测进化回路）。

★★★ 设计（深度思考定稿）:
  · 投 **inbox**（agent 真实消费路径 — lessons 注入/step_judge/修订全链在线），
    不直调 execute_user_task（那是 bench 的事）。这就是"无人值守水平"的语义。
  · 每日 N 单从 52 单池**轮换抽样**（rotation 记录防连续同单过拟合记忆）。
  · 验收复用 dwc_bench2.verify（机器判, agent 外 — G2）。
  · 成功判定读 agent 落盘报告 var/reports/{id}.json 的 answer → verify。
  · 曲线: var/eval/success_curve.jsonl（时间序列 — 短板 2 的收敛证据）。
  · 任务完成等待: 轮询 reports/INBOX_DONE 至超时（默认 40min/单）。

用法: python scripts/dwc_nightbench.py [--n 8] [--wait-min 40]
  cron: 每日 02:30（错开备份 03:00 / watchdog）。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time

def _find_root(start=None) -> str:
    """★ cron 拷贝跑时 __file__ 在 hermes/scripts — 向上找 .dwc_repo 标记。

    ★ R279 修：标记文件是**指针**（内容=仓库路径）不是路标 —— 旧版只认
      存在性不读内容 ⇒ cron 下永远指到 hermes/scripts/src（不存在）⇒
      ModuleNotFoundError: No module named 'dwc'（02:30 红两周实证）。
    """
    d = start or os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        _mk = os.path.join(d, ".dwc_repo")
        if os.path.isfile(_mk):
            try:
                with open(_mk, encoding="utf-8") as _f:
                    _r = _f.readline().strip()
                if _r and os.path.isdir(_r):
                    return _r
            except OSError:
                pass
            return d
        d = os.path.dirname(d)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_ROOT = _find_root()
sys.path.insert(0, os.path.join(_ROOT, "scripts"))
sys.path.insert(0, os.path.join(_ROOT, "src"))

TASKS = os.path.join(_ROOT, "config", "eval_tasks.jsonl")
# ★ 路径单源纪律（agent_rpc 为权威 — 自拼路径三处全错被抓: json/jsonl、
#   var/reports vs var/dwc_reports）:
from dwc.agent_rpc import INBOX, REPORTS   # noqa: E402
STATE = os.path.join(_ROOT, "var", "eval", "nightbench_state.json")
CURVE = os.path.join(_ROOT, "var", "eval", "success_curve.jsonl")

import importlib.util  # noqa: E402
_spec = importlib.util.spec_from_file_location(
    "dwc_bench2", os.path.join(_ROOT, "scripts", "dwc_bench2.py"))
B2 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(B2)


def _inbox_push(task: str, tid: str) -> None:
    """★ JSONL 逐行追加（agent take_inbox 读法 — 数组文件会被逐行跳过）。"""
    os.makedirs(os.path.dirname(INBOX), exist_ok=True)
    with io.open(INBOX, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"id": tid, "task": task,
                             "ts": time.strftime("%Y-%m-%dT%H:%M:%S")},
                            ensure_ascii=False) + "\n")


def make_tid(i: int) -> str:
    """★ R378 · 批次唯一 tid（`nb_<MMDD>_<HHMMSS>_<i>`）。

    旧实现 `nb_%s_%02d`（月日 + 轮内序号）**同一天第二次跑批必撞名**
    ⇒ `_wait_report` 命中上一批的 `var/dwc_reports/{tid}.json`
    ⇒ 判据验的是**上一批的答案**。2026-10-20 08:51 实跑实证：
    报告 mtime 是 02:35–04:01，却报"3/9 通过"。
    """
    return "nb_%s_%s_%02d" % (time.strftime("%m%d"),
                              time.strftime("%H%M%S"), i)


def _wait_report(tid: str, timeout_min: float, since=None) -> dict:
    """轮询 `var/dwc_reports/{tid}.json` 至超时。

    ★★★ R378 · `since`（投单时刻的 epoch）是**防旧报告**的关键：
      旧实现只看 `os.path.exists()` ⇒ 上一批同名报告让"等 12 分钟"
      瞬间变成"立刻拿到结果"，判据验的是昨天的答案。
      传 `since` ⇒ 只认 mtime ≥ since 的报告（本轮真产出）。
      不传 ⇒ 保持旧语义（兼容既有调用）。
    """
    p = os.path.join(REPORTS, "%s.json" % tid)
    deadline = time.time() + timeout_min * 60
    while time.time() < deadline:
        if os.path.exists(p):
            fresh = True
            if since is not None:
                try:
                    fresh = os.path.getmtime(p) >= float(since) - 1.0
                except OSError:
                    fresh = False
            if fresh:
                try:
                    return json.load(io.open(p, encoding="utf-8"))
                except (ValueError, OSError):
                    pass
        time.sleep(5 if timeout_min <= 1 else 30)
    return {}


def _promote_row(row: dict) -> dict:
    """★ R269-① · 跑批行 → lessons 记忆（成功经验也沉淀）。

    ok=True 记 fail_mode="success_pattern:<kind>"（recall 靠文本 overlap，
    渲染头区分成败）；ok=False 记 "nightbench_fail"。返回 lesson 摘要。
    """
    from dwc import agent_quality as Q
    if row.get("ok"):
        mode = "success_pattern:%s" % (row.get("kind") or "?")
        detail = "成功做法（%s）：%s" % (row.get("verify", "?")[:80],
                                        row.get("task", "")[:120])
    else:
        mode = "nightbench_fail"
        detail = "失败（%s）：%s" % (row.get("verify", "?")[:80],
                                    row.get("task", "")[:120])
    Q.record_lesson(str(row.get("task_id") or row.get("tid")),
                    mode, str(row.get("task", "")), detail)
    return {"mode": mode, "task_id": row.get("task_id")}


def _fail_sig(how: str) -> str:
    """★ R269-③ · 失败签名（机判）：verify 文本首 40 字符。"""
    return str(how or "")[:40]


def _should_stop(hist: list, k: int = 3) -> tuple:
    """★ R269-③ · 最近 k 单全 ok 即 SATURATED（期望价值不足即停）。"""
    if len(hist) >= k and all(r.get("ok") for r in hist[-k:]):
        return (True, "SATURATED")
    return (False, "")


def _unseen_fail(ok: bool, how: str, seen: set, bonus_used: int) -> bool:
    """★ R269-③ · 新失败类加练（整轮至多 +2，防发散）。"""
    return (not ok) and (_fail_sig(how) not in seen) and bonus_used < 2


def _terminal_state(ok: bool, rep: dict, tid: str = "",
                    task: str = "") -> str:
    """★ R269-⑤ · 终态三态机：DONE / FAIL / STALLED。

    STALLED（超时无报告）升级进 inbox（agent 真实消费路径），不再是
    沉默的一行 timeout。
    """
    if ok:
        return "DONE"
    if not rep:
        _inbox_push("【STALLED升级】%s 超时无报告，请人工查看：%s"
                    % (tid, task[:120]), "esc_" + tid)
        return "STALLED"
    return "FAIL"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--wait-min", type=int, default=40)
    args = ap.parse_args()
    tasks = [json.loads(l) for l in io.open(TASKS, encoding="utf-8")]
    st = {"rot": 0}
    if os.path.exists(STATE):
        try:
            st = json.load(io.open(STATE, encoding="utf-8"))
        except (ValueError, OSError):
            pass
    rot = int(st.get("rot", 0))
    picks = [tasks[(rot + i) % len(tasks)] for i in range(args.n)]
    st["rot"] = (rot + args.n) % len(tasks)
    _sd = os.path.dirname(STATE)  # ★ R276c · 新机 var/eval 不存在则建（否则首跑必炸）
    if _sd and not os.path.exists(_sd):
        os.makedirs(_sd)
    with io.open(STATE, "w", encoding="utf-8") as fh:
        json.dump(st, fh)

    day = time.strftime("%m%d")
    n_ok = 0
    done = 0
    order = list(picks)   # ★ R269-③: 加练单可追加（至多 +2）
    hist: list = []
    seen: set = set()
    bonus_used = 0
    i = 0
    while i < len(order):
        t = order[i]
        i += 1
        tid = make_tid(i)
        _inbox_push(t["task"], tid)
        print("[投单 %d/%d] %s (%s)" % (i, len(order), tid, t["kind"]),
              flush=True)
        # ★★★ R378 · 记投单时刻 —— _wait_report 只认此后写的报告
        _t_push = time.time()
        rep = _wait_report(tid, args.wait_min, since=_t_push)
        ok = False
        how = "timeout/no-report"
        if rep:
            # ★★★ R378 · 传 since ⇒ 文件类判据只认本轮写的文件
            ok, how = B2.verify(t["check"], str(rep.get("answer", "")),
                                since=_t_push)
            done += 1
        n_ok += 1 if ok else 0
        row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "tid": tid,
               "task_id": t["id"], "kind": t["kind"], "ok": ok, "verify": how,
               "status": rep.get("status"), "rounds": rep.get("rounds")}
        row["lesson"] = _promote_row({**row, "task": t["task"]})
        row["terminal"] = _terminal_state(ok, rep, tid=tid, task=t["task"])
        try:  # ★ R270-⑥ · episode 链（失败不阻断主链）
            import dwc_episodes as _EP
            _EP.append_episode(t["id"], t["kind"], ok)
        except Exception:                            # noqa: BLE001
            pass
        with io.open(CURVE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print("  → %s (%s)" % ("✓" if ok else "✗", how[:60]), flush=True)
        hist.append({"ok": ok, "verify": how})  # ★ R269-③
        if _unseen_fail(ok, how, seen, bonus_used):
            seen.add(_fail_sig(how))
            order.append(tasks[(rot + len(order)) % len(tasks)])
            bonus_used += 1
            print("  ★ 新失败类，加练一单（+%d/2）" % bonus_used, flush=True)
        else:
            seen.add(_fail_sig(how))
        stop, reason = _should_stop(hist)
        if stop:
            st["saturated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            with io.open(STATE, "w", encoding="utf-8") as fh:
                json.dump(st, fh)
            print("  ★ %s：连续 3 单全过，提前收工" % reason, flush=True)
            break
        time.sleep(10)      # 单间隔（端点限流教训）
    print("\n本轮: %d/%d（%d 单等到报告）" % (n_ok, len(order), done))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
