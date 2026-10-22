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
    # ★ R381 · 跑全池（52 单），并从 0 开始不旋转
    ap.add_argument("--all", action="store_true",
                    help="跑全部任务（覆盖 --n，从第 0 条开始）")
    # ★ R381 · agent 轮询间隔（看门狗拉起时用）
    ap.add_argument("--interval", type=int, default=20)
    # ★ R381 · 禁用"连续 3 单全过就提前收工"（跑全池要完整样本）
    ap.add_argument("--no-saturate", action="store_true",
                    help="不因连续 3 单全过而提前收工")
    # ★ R421 · 只跑指定单（复跑被基础设施故障打断的那批）
    ap.add_argument("--only", default="",
                    help="只跑指定 id（逗号分隔），如 an09,wr01,hs01")
    args = ap.parse_args()
    tasks = [json.loads(l) for l in io.open(TASKS, encoding="utf-8")]
    if args.only:
        want = [x.strip() for x in args.only.split(",") if x.strip()]
        tasks = [t for t in tasks if str(t.get("id", "")) in want]
        if not tasks:
            print("--only 没匹配到任何任务: %s" % args.only)
            return 2
        args.n = len(tasks)
    st = {"rot": 0}
    if os.path.exists(STATE):
        try:
            st = json.load(io.open(STATE, encoding="utf-8"))
        except (ValueError, OSError):
            pass
    rot = int(st.get("rot", 0))
    if args.all:
        args.n = len(tasks)
        rot = 0                       # 全池从第 0 条开始，保证覆盖
    picks = [tasks[(rot + i) % len(tasks)] for i in range(args.n)]
    st["rot"] = (rot + args.n) % len(tasks)
    _sd = os.path.dirname(STATE)  # ★ R276c · 新机 var/eval 不存在则建（否则首跑必炸）
    if _sd and not os.path.exists(_sd):
        os.makedirs(_sd)
    with io.open(STATE, "w", encoding="utf-8") as fh:
        json.dump(st, fh)

    day = time.strftime("%m%d")
    n_ok = 0
    n_infra = 0     # ★ R422 · 基础设施故障单数（不计入通过率分母）
    done = 0
    order = list(picks)   # ★ R269-③: 加练单可追加（至多 +2）
    hist: list = []
    seen: set = set()
    bonus_used = 0
    i = 0
    rows_all: list = []   # ★ R381 · 收集全部行，末尾做失败分类
    while i < len(order):
        t = order[i]
        i += 1
        tid = make_tid(i)
        # ★★★ R381 · 投单前确保 agent 活着（今天已静默死 2 次：
        #   无 traceback / 无冻结 / 预算未到 / pid 残留 ⇒ 死因未明，
        #   只能"死了就发现并拉起"，否则整轮结果被 timeout 污染）。
        try:
            import dwc_watchdog as _WD
            _w = _WD.ensure(interval=max(10, args.interval))
            if _w.get("action") not in ("none",):
                print("  ⚠ agent 看门狗: %s" % _w.get("action"), flush=True)
        except Exception as _exc:                    # noqa: BLE001
            print("  ⚠ 看门狗不可用: %s" % str(_exc)[:60], flush=True)
        _inbox_push(t["task"], tid)
        print("[投单 %d/%d] %s (%s)" % (i, len(order), tid, t["kind"]),
              flush=True)
        # ★★★ R378 · 记投单时刻 —— _wait_report 只认此后写的报告
        _t_push = time.time()
        rep = _wait_report(tid, args.wait_min, since=_t_push)
        # ★★★ R422 · **基础设施故障不算模型失败** ——
        #   现场：2026-10-21 23:41–23:48 端点连续 502，最后 12 单
        #   全部「零动作 + answer=None」，被当成 12 个模型失败记进通过率。
        #   处理：带 `[infra]` 标记的失败**重投一次**（换新 tid，等 30s）；
        #   仍失败 ⇒ 记 infra_skip，**从分母剔除**，不进 lessons/episodes。
        _infra_retries = 0
        while (rep and "[infra]" in str(rep.get("why", ""))
               and _infra_retries < 1):
            _infra_retries += 1
            print("  ⚠ 基础设施故障，30s 后重投一次：%s"
                  % str(rep.get("why"))[:60], flush=True)
            time.sleep(30)
            tid = make_tid(i)
            _inbox_push(t["task"], tid)
            _t_push = time.time()
            rep = _wait_report(tid, args.wait_min, since=_t_push)
        ok = False
        how = "timeout/no-report"
        infra_skip = False
        if rep:
            if "[infra]" in str(rep.get("why", "")):
                infra_skip = True
                n_infra += 1
                how = "infra: %s" % str(rep.get("why"))[:50]
            else:
                # ★★★ R378 · 传 since ⇒ 文件类判据只认本轮写的文件
                ok, how = B2.verify(t["check"], str(rep.get("answer", "")),
                                    since=_t_push, report=rep)
            done += 1
        n_ok += 1 if ok else 0
        row = {"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "tid": tid,
               "task_id": t["id"], "kind": t["kind"], "ok": ok, "verify": how,
               "status": rep.get("status"), "rounds": rep.get("rounds")}
        if infra_skip:
            row["infra"] = True
        row["lesson"] = None if infra_skip else _promote_row(
            {**row, "task": t["task"]})
        row["terminal"] = _terminal_state(ok, rep, tid=tid, task=t["task"])
        if not infra_skip:
            try:  # ★ R270-⑥ · episode 链（失败不阻断主链）
                import dwc_episodes as _EP
                _EP.append_episode(t["id"], t["kind"], ok)
            except Exception:                        # noqa: BLE001
                pass
        with io.open(CURVE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print("  → %s (%s)" % ("✓" if ok else "✗", how[:60]), flush=True)
        rows_all.append(row)
        hist.append({"ok": ok, "verify": how})  # ★ R269-③
        if (not infra_skip) and _unseen_fail(ok, how, seen, bonus_used):
            seen.add(_fail_sig(how))
            order.append(tasks[(rot + len(order)) % len(tasks)])
            bonus_used += 1
            print("  ★ 新失败类，加练一单（+%d/2）" % bonus_used, flush=True)
        else:
            seen.add(_fail_sig(how))
        stop, reason = _should_stop(hist)
        if stop and not args.no_saturate:
            st["saturated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            with io.open(STATE, "w", encoding="utf-8") as fh:
                json.dump(st, fh)
            print("  ★ %s：连续 3 单全过，提前收工" % reason, flush=True)
            break
        time.sleep(10)      # 单间隔（端点限流教训）
    print("\n本轮: %d/%d（%d 单等到报告）" % (n_ok, len(order), done))
    if n_infra:
        _den = max(1, len(order) - n_infra)
        print("★ 基础设施故障 %d 单（已剔除，不计入通过率）：%d/%d = %.1f%%"
              % (n_infra, n_ok, _den, 100.0 * n_ok / _den))
    _print_breakdown(rows_all)
    return 0


def _print_breakdown(rows: list) -> None:
    """★ R381 · 失败分类汇总 —— 跑全池时最需要的是"哪类任务失败在哪"，
    而不只是一个通过率数字。

    分三个维度：
      ① kind（任务类型）
      ② 失败归因（timeout / 答案不对 / 状态未完成 / 旧文件）
      ③ 状态分布（done / incomplete）
    """
    if not rows:
        return
    import collections
    print("\n" + "=" * 66)
    print("失败分类")
    print("=" * 66)

    # ① 按 kind
    by_kind = collections.defaultdict(lambda: [0, 0])
    for r in rows:
        k = r.get("kind") or "?"
        by_kind[k][1] += 1
        if r.get("ok"):
            by_kind[k][0] += 1
    print("%-16s %-10s %s" % ("任务类型", "通过", "通过率"))
    print("-" * 66)
    for k in sorted(by_kind, key=lambda x: -by_kind[x][1]):
        ok, n = by_kind[k]
        print("%-16s %-10s %d/%d = %.0f%%" % (
            k, "%d/%d" % (ok, n), ok, n, 100.0 * ok / n if n else 0))

    # ② 失败归因
    def _cause(r):
        if r.get("ok"):
            return None
        v = str(r.get("verify") or "")
        st = r.get("status")
        if "timeout" in v or "no-report" in v:
            return "A. 没等到报告（agent 死/超时）"
        if "stale" in v:
            return "B. 旧文件（不是本轮产出）"
        if st == "incomplete":
            return "C. 任务未完成（模型中途放弃）"
        if st == "done":
            return "D. 答完了但答案不对"
        return "E. 其它"

    causes = collections.Counter(_cause(r) for r in rows if not r.get("ok"))
    print("\n失败归因:")
    if not causes:
        print("  （无失败）")
    for c, n in causes.most_common():
        print("  %-32s %d" % (c, n))

    # ③ 状态分布
    sts = collections.Counter(str(r.get("status")) for r in rows)
    print("\n报告状态:", dict(sts))

    # ④ 逐条失败明细（便于定向下钻）
    fails = [r for r in rows if not r.get("ok")]
    if fails:
        print("\n失败明细:")
        for r in fails:
            print("  %-6s %-14s %-12s %s" % (
                r.get("task_id"), r.get("kind"), r.get("status"),
                str(r.get("verify"))[:52]))
    print("=" * 66)


if __name__ == "__main__":
    raise SystemExit(main())
