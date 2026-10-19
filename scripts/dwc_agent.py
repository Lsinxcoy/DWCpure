# -*- coding: utf-8 -*-

"""R208 · DWC 独立 agent 常驻宿主（生产形态修正: 批处理 → 独立 agent）。

★★★ 定位（用户 2026-10-12 纠偏）: DWC 是独立 agent, 不是 cron 喂的批处理。
  本进程是 agent 的**宿主躯壳**: 常驻 + 自主循环 + 自己触发下一轮。
  ★ 任务源自主: 首轮 seed 轮询, 之后取**上轮 run_term 自己产的**
    next_task_source（world_tree_action.node = 真任务 id）——
    "Measurement thereby becomes the trigger of the next iteration"
    （bz 缺口原文）在进程级落地: 它的测量触发它的下一轮, 外部不喂。
  ★ cron 角色修正: watchdog 只守夜（死→拉活+告警）, 不喂食。

★ 节奏与护栏（agent 自治边界内）:
  · 休眠 interval（默认 600s）—— 存活期自主连续, 非批次
  · 日预算: terms/日 与 budget/日 超限 ⇒ 优雅停 + 告警（次日 watchdog 拉活）
  · 退化崩塌: 曾经 pass>0.1 后连续 2 轮 <0.1 ⇒ 停 + 告警
  · 冻结门（人工）: var/dwc_agent_frozen 存在 ⇒ 优雅停（G3 frozen 设置方）

★ 运行: python dwc_agent.py [--interval 600] [--steps 2] [--llm]
      [--terms-per-day 48] [--budget-day 40]
      python dwc_agent.py --freeze / --unfreeze / --status
"""
from __future__ import annotations

import os as _os
def _dwc_root():
    """R228: 仓库根发现（env DWC_ROOT > 本文件上溯 — 不写死盘符/用户名）。"""
    _e = _os.environ.get("DWC_ROOT", "").strip()
    if _e and _os.path.isdir(_e):
        return _os.path.abspath(_e)
    _c = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
    while not (_os.path.isdir(_os.path.join(_c, "src", "dwc"))
               and _os.path.isdir(_os.path.join(_c, "config"))):
        _p = _os.path.dirname(_c)
        if _p == _c:
            break
        _c = _p
    else:
        return _c
    # ③ 副本场景（cron 跑 hermes/scripts 拷贝 — 上溯找不到仓库）:
    #    同目录 .dwc_repo 标记（同步时写入一行仓库路径）
    _mk = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)),
                        ".dwc_repo")
    if _os.path.isfile(_mk):
        with open(_mk, encoding="utf-8") as _f:
            _r = _f.readline().strip()
        if _r and _os.path.isdir(_r):
            return _r
    raise RuntimeError("找不到 DWC 根 — 设 DWC_ROOT 或同步副本(写 .dwc_repo)")


import json
import os
import signal
import sys
import time

#: ★ 固定仓库路径（drift watch 同款）—— CRON RUNS THE COPY: 副本在
#:   %LOCALAPPDATA%/hermes/scripts 下, 按 __file__ 定位会找错 var/src
ROOT = _dwc_root()
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.core import DWC                                    # noqa: E402
from dwc.organs.actor import Actor, execute_task, Receipt   # noqa: E402

_LOCK_FD = None  # ★ R297-混沌真修 · 锁 fd 进程持有（不关；死即放）


def _try_lock(_fd) -> bool:
    try:
        import msvcrt
        msvcrt.locking(_fd, msvcrt.LK_NBLCK, 1)
        return True
    except OSError:
        return False


def acquire_singleton(pid_path: str) -> bool:
    """★ R297-Task1 · 单实例原子锁（O_EXCL 抢建＋msvcrt 持有锁＋stale 接管）。

    True=拿到锁（pid 已写＋lock fd 持有不放）；False=有活实例（拒双开）。
    语义：赢者持有 <pid_path>.lock 全程（进程死锁自动放）；pid 文件
    本身不加锁（watch/心跳照常读，不误判）。后来者 lock 加锁失败⇒
    有活持有者⇒False；加上了⇒前者已死⇒覆写接管。读-判-写/CAS
    双赢洞（2026-10-16 实测两轮）根治：锁是内核态，不靠时序。
    父目录缺席⇒抛 OSError 大声。全局 _LOCK_FD 防 GC 关 fd。
    """
    global _LOCK_FD
    _me = str(os.getpid())
    _lock_path = pid_path + ".lock"

    def _hold(_fd) -> bool:
        global _LOCK_FD
        if not _try_lock(_fd):
            os.close(_fd)
            return False
        _LOCK_FD = _fd  # ★ 持有不关——死即放（锁的是 .lock，pid 可读）
        # ★ O_EXCL 赢≠无活实例（pid 预写而 lock 缺席场景，R210 旧测）⇒
        #   读 pid 定夺：活着且非我⇒解锁拒；stale/无/坏⇒覆写 True。
        try:
            with open(pid_path, encoding="utf-8") as _fh:
                _old = _fh.read().strip()
        except OSError:
            _old = ""
        _refuse = False
        if _old:
            _alive = False
            try:
                import psutil as _ps
                _alive = _ps.pid_exists(int(_old))
            except Exception:                   # noqa: BLE001 — 坏内容当 stale
                _alive = False
            if (_alive and _old != _me) or _old == _me:
                _refuse = True
        if _refuse:
            try:
                import msvcrt
                msvcrt.locking(_fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            os.close(_fd)
            _LOCK_FD = None
            return False
        try:
            with open(pid_path, "w", encoding="utf-8") as _fh:
                _fh.write(_me)
        except OSError:
            pass
        return True

    # ★ 锁文件先行（父目录缺席在此大声；pid 写后，锁与 pid 同命运）
    try:
        _fd = os.open(_lock_path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
    except FileExistsError:
        pass
    except OSError:
        raise  # ★ 父目录缺席等——大声，不装拿到
    else:
        return _hold(_fd)
    try:
        _fd = os.open(_lock_path, os.O_RDWR)
    except OSError:
        raise
    if not _try_lock(_fd):
        os.close(_fd)
        return False  # ★ 有活持有者——拒
    # ★ 锁拿到了⇒前者已死（或同进程重抢）⇒读 pid 定夺
    try:
        with open(pid_path, encoding="utf-8") as _fh:
            _old = _fh.read().strip()
    except OSError:
        _old = ""
    _alive = False
    try:
        import psutil as _ps
        _alive = _ps.pid_exists(int(_old)) if _old else False
    except Exception:                           # noqa: BLE001 — 坏内容当 stale
        _alive = False
    if (_alive and _old != _me) or _old == _me:
        # ★ 活实例（别人）拒；同进程重抢（自己）也拒（R297 语义）
        _LOCK_FD = _fd  # ★ 先持有再放——避免同进程 fd 泄漏语义乱
        try:
            import msvcrt
            msvcrt.locking(_fd, msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        os.close(_fd)
        _LOCK_FD = None
        return False
    _LOCK_FD = _fd
    try:
        with open(pid_path, "w", encoding="utf-8") as _fh:
            _fh.write(_me)
    except OSError:
        pass
    return True


#: ★ R210: 路径常量单源 —— agent_rpc 为权威（指令核心与 agent 同一套文件
#:   协议面; 双处维护必漂移 ⇒ 从它导入）
from dwc.agent_rpc import (VAR, DB, LOG, PID, HB, FROZEN,   # noqa: E402
                           INBOX, INBOX_DONE, REPORTS, RPC_PORT)
DEV_POOL = ("code_fix_001", "code_fix_002", "code_fix_003", "code_fix_004",
            "code_fix_005", "code_fix_006",
            "reasoning_001", "reasoning_002",
            "reproduce_001", "reproduce_002", "reproduce_003")
_day = {"key": time.strftime("%Y-%m-%d"), "terms": 0, "cost": 0.0}
_stop = {"by": None}


def _log(entry: dict) -> None:
    entry["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _heartbeat(**kw) -> None:
    with open(HB, "w", encoding="utf-8") as fh:
        json.dump({"ts": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
                   "pid": os.getpid(), **kw}, fh, ensure_ascii=False)


def _feishu_notify(text: str) -> None:
    """★ 任务结果通知 — 委托 agent_rpc.send_feishu（R225 单实现化: ask 审批
    与任务结果共用一个发送器, 防双份实现漂移）。"""
    try:
        from dwc.agent_rpc import send_feishu
        send_feishu(text)
    except Exception:                           # noqa: BLE001 — 失败不阻塞循环
        _log({"event": "notify_failed", "via": "agent_rpc"})


def _done_state() -> dict:
    try:
        with open(INBOX_DONE, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:                          # noqa: BLE001
        return {}


def take_inbox():
    """★ 取第一条未处理的收件箱任务（None = 空）。done 态落 INBOX_DONE。"""
    st = _done_state()
    if not os.path.exists(INBOX):
        return None
    with open(INBOX, encoding="utf-8") as fh:
        for ln in fh.read().splitlines():
            if not ln.strip():
                continue
            try:
                item = json.loads(ln)
            except Exception:                  # noqa: BLE001
                continue
            tid = item.get("id") or ("T_" + str(abs(hash(ln)) % 10 ** 8))
            v = st.get(tid)
            if isinstance(v, str) and v.startswith("running:"):
                # ★ R219 · 执行中标记: 15min 内不重取（异步线程在跑）;
                #   超时=线程死了（崩溃/杀进程）⇒ 重取恢复, 标记覆盖留痕
                try:
                    if time.time() - float(v.split(":", 1)[1]) < 900:
                        continue
                except (ValueError, IndexError):
                    pass
                st[tid] = "stale_recovered"
                with open(INBOX_DONE, "w", encoding="utf-8") as fh:  # 留痕落盘
                    json.dump(st, fh, ensure_ascii=False)
            elif v:
                continue
            return {**item, "id": tid}
    return None


def _reading_sources() -> list:
    """★ R266C(多库): reading 候选源 — 自己 ROOT 的 + 用户安装副本 .dwc 的
    （双副本纪律: TUI 直驱跑 .dwc 沉淀在 .dwc/var, E: agent 必须能扫到,
    否则用户链找到的论文永远无人消费 — 2026-10-14 活体发现）。"""
    out = []
    try:
        from dwc.llm.task_exec import READING
        out.append(READING)
    except Exception:                          # noqa: BLE001 — 导入失败如实
        _log({"event": "reading_source_import_failed"})
    import os.path as _op
    _ext = _op.expanduser("~/.dwc/var/dwc_reading_list.jsonl")
    if _op.exists(_ext) and all(_op.abspath(_ext) != _op.abspath(x)
                                for x in out):
        out.append(_ext)
    return out


def maybe_dispatch_reading() -> dict:
    """★ R266C · 进化投单（用户 2026-10-14 ABC 拍板的 C 层）: reading_list
    里未派发的论文/资料 → 自产"深读找强化点"任务进 inbox。

    节律: 每轮最多 1 单; 24h 内深读投单 ≤3（防刷爆 LLM）; inbox 有同 url
    待办不重投; 派发即标 dispatched_at（一次投递）。G7: 全程 try 留痕。
    """
    try:
        from dwc.llm.task_exec import READING
        rows, rp = [], None
        for cand in _reading_sources():
            if not os.path.exists(cand):       # ★ 不存在的源跳过（E: 常无本文件）
                continue
            _r = []
            for ln in open(cand, encoding="utf-8"):
                ln = ln.strip()
                if ln:
                    try:
                        _r.append(json.loads(ln))
                    except Exception:          # noqa: BLE001 — 坏行跳过留痕
                        _log({"event": "reading_row_bad", "raw": ln[:80]})
            _t = next((x for x in _r if not x.get("dispatched_at")), None)
            if _t is not None:
                rows, rp = _r, cand             # 有 pending 的源胜出
                break
        if rp is None:
            return None
        READING = rp                            # 本单的回写目标=该源文件
        target = next((r for r in rows if not r.get("dispatched_at")), None)
        if target is None:
            return None
        # 24h 投单限
        day_ago = time.time() - 86400
        n_disp = 0
        for r in rows:
            da = r.get("dispatched_at")
            if da:
                try:
                    import datetime as _dt
                    ts = _dt.datetime.strptime(
                        str(da)[:19], "%Y-%m-%dT%H:%M:%S").timestamp()
                    if ts > day_ago:
                        n_disp += 1
                except Exception:              # noqa: BLE001
                    continue
        if n_disp >= 3:
            return None
        url = str(target.get("url", ""))
        if not url:
            return None
        # inbox 查重（pending 中已有同 url 深读单 ⇒ 不重投）
        if os.path.exists(INBOX):
            for ln in open(INBOX, encoding="utf-8"):
                if url in ln:
                    return None
        tid = "T_read_%06x" % (abs(hash(url)) % 10 ** 6)
        task = ("深读这份外部资料并提炼对 DWC 的强化点: %s\n"
                "要求: ①web_read 抓正文(超长用分页) ②提炼 3-5 个"
                "**可落地**的 DWC 强化点 ③详细笔记写 "
                "var/inbox_work/reading_notes_%s.md ④final 输出强化点清单"
                % (url, tid[-6:]))
        st = _done_state()
        if tid in st:
            return None                      # 曾投过并处理 ⇒ 不重投
        with open(INBOX, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": tid, "task": task,
                                 "by": "reading_dispatch",
                                 "ts": time.strftime("%Y-%m-%dT%H:%M:%S+08:00")},
                                ensure_ascii=False) + "\n")
        target["dispatched_at"] = time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
        tmp = READING + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            for r in rows:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        os.replace(tmp, READING)
        _log({"event": "reading_dispatched", "id": tid, "url": url[:100]})
        return {"id": tid, "url": url}
    except Exception as exc:                  # noqa: BLE001 — 不许炸主循环
        _log({"event": "reading_dispatch_failed",
              "error": "%s: %s" % (type(exc).__name__, exc)})
        return None


def run_user_task(item: dict, use_llm: bool, llm=None) -> dict:
    """★ 消费一单: LLMTaskExecutor 执行 → 报告落盘 + 台账 + 飞书通知。"""
    from dwc.llm.task_exec import execute_user_task
    from dwc.llm.client import LLMClient
    # ★ 收件箱任务总是自带 LLM 通道（config/llm.json 自读）—— 不依赖
    #   --llm 启动参数（watchdog 无参拉活的 agent 同样能接单）
    llm = llm or LLMClient()          # ★ llm 注入（测试可测性 — 依赖注入）
    _st = _done_state()               # ★ R219: 执行中标记（异步期间防重取）
    _st[item["id"]] = "running:%.0f" % time.time()
    with open(INBOX_DONE, "w", encoding="utf-8") as fh:
        json.dump(_st, fh, ensure_ascii=False)
    if not getattr(llm, "configured", False):
        rep = {"task": item.get("task"), "status": "incomplete",
               "why": "LLM 未配置（收件箱任务需要 LLM 通道; --llm 启动）"}
    else:
        # ★ R213: 历史教训检索注入（agent_quality 回路 — 同类失败不再重犯）
        from dwc.agent_quality import lessons_context
        ctx = item.get("ctx")
        lc = lessons_context(str(item.get("task", "")))
        if lc:
            ctx = (ctx + "\n" + lc) if ctx else lc
        rep = execute_user_task(str(item.get("task", "")), llm=llm,
                                ctx=ctx, task_id=item["id"])
    rep = {"id": item["id"], **rep,
           "ts": time.strftime("%Y-%m-%dT%H:%M:%S+08:00")}
    os.makedirs(REPORTS, exist_ok=True)
    with open(os.path.join(REPORTS, item["id"] + ".json"), "w",
              encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    st = _done_state()
    st[item["id"]] = rep["status"]
    with open(INBOX_DONE, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False)
    # ★ R231 接线: 任务结果回写预测器（视图层 — 台账族; 树族读树不写）
    try:
        from dwc.organs.predictor import OutcomePredictor
        OutcomePredictor().observe(
            "inbox:" + ("done" if rep["status"] == "done" else "not_done"),
            rep["status"] == "done", evidence_ref=item["id"])
    except Exception as _pe:                  # noqa: BLE001 — 预测器故障不拖垮任务
        import sys as _sy
        _sy.stderr.write("predictor observe 失败: %s\n" % _pe)
    # ★ R258 · ReHarness 后向修订（2610.12668 §3.2 — 任务成败明确时回修
    #   检索用过的规矩; diagnostic gate 在 revision_lessons 内）
    try:
        from dwc.agent_quality import revision_lessons
        _rv = revision_lessons(str(item.get("task", "")),
                               status=rep.get("status", ""),
                               fail_why=str(rep.get("why", ""))[:300],
                               llm=llm)
        if _rv.get("revised"):
            _log({"user_task": item["id"], "skills_revised": _rv["revised"]})
    except Exception as _re:               # noqa: BLE001 — 修订失败不拖垮任务
        import sys as _sy
        _sy.stderr.write("revision_lessons 失败: %s\n" % _re)
    _log({"user_task": item["id"], "status": rep["status"],
          "rounds": rep.get("rounds"),
          "why": rep.get("why", "")[:120]})
    _feishu_notify("✅ DWC 任务完成（%s）\n%s" % (item["id"], rep.get("answer", "")[:400])
                   if rep["status"] == "done" else
                   "⚠️ DWC 任务未完成（%s）\n原因: %s" % (item["id"], rep.get("why", "")))
    return rep


def select_task(prev_rep) -> str:
    """★ agent 自主任务源: 上轮 next_task_source 优先（它的测量触发它的
    下一轮）; 无/空 ⇒ DEV_POOL 轮询（seed 语义）。"""
    tasks = ((prev_rep.next_task_source or {}).get("tasks")
             if prev_rep is not None else None) or []
    nodes = [t["node"] for t in tasks
             if t.get("kind") == "world_tree_action" and t.get("node")]
    if nodes:
        return nodes[0]
    return DEV_POOL[(_day["terms"]) % len(DEV_POOL)]


def _freeze_check() -> bool:
    if os.path.exists(FROZEN):
        _log({"event": "agent_stopped", "by": "freeze_flag"})
        _stop["by"] = "freeze"
        return True
    return False


def _budget_check(terms_per_day: float, budget_day: float) -> bool:
    if _day["terms"] >= terms_per_day or _day["cost"] >= budget_day:
        _log({"event": "agent_stopped", "by": "daily_limit",
              "terms": _day["terms"], "cost": round(_day["cost"], 3)})
        _stop["by"] = "daily_limit"
        return True
    return False


def _maybe_skip(prev_ok, item, skips):
    """★ R305 · monitor 接线（纯函数：有委托/上轮失败/连跳≥2 ⇒ 跑；否则跳过串）。

    只增调用不改判分：返回 None=执行本轮；返回串=跳过本轮（省 LLM）。
    永不抛错（坏输入一律执行）。"""
    try:
        from dwc.llm.monitor import MAX_SKIPS, monitor_skip
        if item is not None:
            return None
        if not prev_ok:
            return None
        try:
            n = int(skips)
        except Exception:
            return None
        if n >= MAX_SKIPS:
            return None
        return monitor_skip(has_new_input=False, last_done_ok=True, skips=n)
    except Exception:
        return None


def _md5_file(p):
    import hashlib as _hl
    with open(p, "rb") as _fh:
        return _hl.md5(_fh.read()).hexdigest()


def startup_selfcheck(pairs=None):
    """★ R309-③ · 双副本自检：pairs=[(源, 副本)] md5 比对。

    异/缺只返告警串（""=全同），永不抛错、永不拦执行（R304 纪律）。
    pairs=None 时用内置白名单（E: 仓库 ↔ 生产 .dwc）。
    """
    try:
        if pairs is None:
            try:
                _here = os.path.dirname(os.path.abspath(__file__))
                _repo = os.path.dirname(_here)
                _dwc = os.path.join(os.path.expanduser("~"), ".dwc")
                pairs = [
                    (os.path.join(_repo, "scripts", "dwc_agent.py"),
                     os.path.join(_dwc, "scripts", "dwc_agent.py")),
                    (os.path.join(_repo, "scripts", "dwc_evo_round.py"),
                     os.path.join(_dwc, "scripts", "dwc_evo_round.py")),
                    (os.path.join(_repo, "scripts",
                                  "dwc_evo_round_cron.py"),
                     os.path.join(_dwc, "scripts",
                                  "dwc_evo_round_cron.py")),
                    (os.path.join(_repo, "config", "capabilities.yaml"),
                     os.path.join(_dwc, "config", "capabilities.yaml")),
                ]
            except Exception as _pe:
                return "自检配对失败：%r" % (_pe,)
        warns = []
        for _s, _d in pairs or []:
            try:
                if not os.path.isfile(_s):
                    warns.append("缺源 %s" % _s)
                elif not os.path.isfile(_d):
                    warns.append("缺副本 %s" % _d)
                elif _md5_file(_s) != _md5_file(_d):
                    warns.append("异 %s（源与副本不一致，先同步再跑）" % _d)
            except Exception as _ce:
                warns.append("查失败 %s：%r" % (_d, _ce))
        return "; ".join(warns)
    except Exception as _oe:
        return "自检异常：%r" % (_oe,)


def main(argv) -> int:
    # ── 控制子命令（人工门）──
    if "--freeze" in argv:
        open(FROZEN, "w", encoding="utf-8").write(time.strftime("%c"))
        print("frozen: agent 下轮优雅停")
        return 0
    if "--unfreeze" in argv:
        if os.path.exists(FROZEN):
            os.remove(FROZEN)
        print("unfrozen")
        return 0
    if "--submit" in argv:
        # 投单: python dwc_agent.py --submit "任务描述" [--id T_x] [--ctx "..."]
        text = argv[argv.index("--submit") + 1]
        tid = argv[argv.index("--id") + 1] if "--id" in argv else \
            "T_" + time.strftime("%m%d_%H%M%S")
        ctx = argv[argv.index("--ctx") + 1] if "--ctx" in argv else None
        os.makedirs(VAR, exist_ok=True)
        with open(INBOX, "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"id": tid, "task": text, "ctx": ctx,
                                 "by": "user",
                                 "ts": time.strftime("%Y-%m-%dT%H:%M:%S+08:00")},
                                ensure_ascii=False) + "\n")
        print("投单成功: %s（agent 下轮优先消费; 结果在 var/dwc_reports/%s.json"
              "+ 飞书通知）" % (tid, tid))
        return 0
    if "--status" in argv:
        for p in (PID, HB):
            print("%s: %s" % (os.path.basename(p),
                              open(p, encoding="utf-8").read().strip()
                              if os.path.exists(p) else "(无)"))
        print("frozen:", os.path.exists(FROZEN))
        return 0

    interval = float(argv[argv.index("--interval") + 1]) \
        if "--interval" in argv else 600.0
    steps = int(argv[argv.index("--steps") + 1]) if "--steps" in argv else 2
    tpd = float(argv[argv.index("--terms-per-day") + 1]) \
        if "--terms-per-day" in argv else 48.0
    bpd = float(argv[argv.index("--budget-day") + 1]) \
        if "--budget-day" in argv else 40.0
    use_llm = "--llm" in argv
    os.makedirs(VAR, exist_ok=True)
    # ★ R309-③ · 启动自检（只告警不拦；--no-selfcheck 可关）。
    if "--no-selfcheck" not in argv:
        _warn = startup_selfcheck()
        if _warn:
            print("自检告警：%s" % _warn, flush=True)
    # ── ★ R210 · 单例锁（R297 原子化：O_EXCL 抢建＋stale 接管；
    #    先查后写竞态可双过，2026-10-16 实测 8 同名进程）──
    try:
        _got = acquire_singleton(PID)
    except OSError as _exc:
        print("锁文件不可写（%r）— 拒启（不静默跑无锁实例）" % (_exc,),
              file=sys.stderr)
        return 1
    if not _got:
        print("已有 agent 在跑 — 拒绝双开", file=sys.stderr)
        return 1
    # ── ★ R369 · 心跳守护线程（防 watchdog 误判：sleep 期间心跳仍更新）──
    def _hb_loop():
        while _stop["by"] is None:
            try:
                _heartbeat(status="alive", thread=True)
            except Exception:  # noqa: BLE001 — 心跳失败不掀主循环
                pass
            time.sleep(60)
    import threading as _th
    _th.Thread(target=_hb_loop, daemon=True, name="heartbeat").start()

    # ── R210 · 指令面: HTTP RPC server（daemon 线程, 只走文件协议 ⇒ 线程安全）──
    rpc_port = int(argv[argv.index("--rpc-port") + 1]) \
        if "--rpc-port" in argv else RPC_PORT
    from dwc.agent_rpc import serve as rpc_serve
    try:
        rpc_serve(rpc_port)
    except Exception as exc:   # noqa: BLE001 — 端口被占等: agent 本体优先,
        # 指令面降级（留痕可查; 单例锁已防双 agent 主因）
        sys.stderr.write("RPC server 起失败(端口%s): %s\n"
                         % (rpc_port, exc))

    d = DWC(depth_limit=3, max_nodes=50, budget=bpd, db_path=DB)
    if use_llm:
        from dwc.llm.client import LLMClient
        from dwc.llm.executor import LLMExecutorFactory
        d.executor = LLMExecutorFactory(LLMClient()).make(memory=d.memory)
    else:
        actor = Actor()

        def exe(task):
            r = execute_task(actor, d.judge, task["task_id"])
            return Receipt(ok=bool(r["observation"]),
                           detail={"observed": r["observation"]},
                           verified=True)
        d.executor = exe
    d.runner.executor = d.executor

    def _sig(signum, _frame):          # 优雅停: SIGINT/SIGTERM
        _log({"event": "agent_stopped", "by": "signal%d" % signum})
        _stop["by"] = "signal"
    signal.signal(signal.SIGINT, _sig)
    signal.signal(signal.SIGTERM, _sig)

    prev = None
    collapse = 0
    best_pass = 0.0
    _log({"event": "agent_started", "pid": os.getpid(),
          "interval": interval, "use_llm": use_llm, "rpc_port": rpc_port})
    while _stop["by"] is None:
        if _freeze_check() or _budget_check(tpd, bpd):
            break
        # 日界滚动（次日自动复位计数）
        if _day["key"] != time.strftime("%Y-%m-%d"):
            _day.update(key=time.strftime("%Y-%m-%d"), terms=0, cost=0.0)
        # ★ R266C · 进化投单（每轮开头: 未派发论文 → 深读任务候选）
        maybe_dispatch_reading()
        # ── R209 · 收件箱优先（用户委托 > 自我改进锚任务 — 独立 agent 接单）──
        item = take_inbox()
        if item is not None:
            # ★ R219 · 异步接单（头部 agent 标配: 接单不阻塞自主循环 —
            #   旧同步形态一单 3-5min 全停; Semaphore 限并发 2 防打爆 LLM）
            import threading
            _sema = globals().setdefault("_INBOX_SEMA", threading.Semaphore(2))

            def _bg(it=item):
                with _sema:
                    try:
                        run_user_task(it, use_llm)
                    except Exception as exc:   # noqa: BLE001 — 线程内不许炸主循环
                        _log({"event": "user_task_crashed", "id": it["id"],
                              "error": "%s: %s" % (type(exc).__name__, exc)})
            threading.Thread(target=_bg, daemon=True,
                             name="inbox-" + item["id"]).start()
            _log({"event": "user_task_async_started", "id": item["id"]})
            _heartbeat(status="alive", last_user_task=item["id"],
                       result="async_started")
            # 主循环继续走自主 term —— 不阻塞不 sleep 不 continue
        task = select_task(prev)
        # ★ R305 · monitor 接线（三条件全 calm ⇒ 跳过本轮省 LLM；
        #   有委托/首轮/上轮崩/连跳≥2 ⇒ 照跑。跳过不计 term、不改判分）。
        _sk = _maybe_skip(prev is not None, item, globals().get("_SKIPS", 0))
        if _sk is not None:
            globals()["_SKIPS"] = int(globals().get("_SKIPS", 0)) + 1
            try:
                from dwc.llm.monitor import record as _mrec
                _mrec("skip", os.path.join(ROOT, "var", "monitor_counts.jsonl"))
                from dwc.llm.mech_trace import emit as _memit
                _memit({"mech": "monitor_skip", "event": "skip", "ok": True},
                       os.path.join(ROOT, "var", "mech_events.jsonl"))
            except Exception:
                pass
            _log({"event": "term_skipped", "why": _sk,
                  "skips": globals()["_SKIPS"]})
            _heartbeat(status="alive", skipped=True)
            time.sleep(interval)
            continue
        globals()["_SKIPS"] = 0
        try:
            rep = d.run_term(task, n_steps=steps)
        except Exception as exc:  # noqa: BLE001 — agent 边界: 留痕继续活
            _log({"event": "term_error", "task": task,
                  "error": "%s: %s" % (type(exc).__name__, exc)})
            _heartbeat(status="term_error", task=task)
            time.sleep(interval)
            continue
        pr = rep.score_delta
        cost = float((rep.cost_after or {}).get("term_cost", 0.0) or 0.0)
        _day["terms"] += 1
        _day["cost"] += cost
        ir = rep.iron_report or {}
        _log({"agent_term": _day["terms"], "task": task,
              "pass_rate": pr, "cost": round(cost, 3),
              "advice_consumed": (rep.iwm_advice or {}).get("consumed_action"),
              "iron_block": ir.get("block"), "iron_warn": ir.get("warn"),
              "drift": (rep.drift or {}).get("gdi"),
              "next": [t.get("kind") for t in
                       (rep.next_task_source or {}).get("tasks", [])]})
        _heartbeat(status="alive", terms=_day["terms"],
                   last_task=task, pass_rate=pr)
        if pr is not None and pr > best_pass:
            best_pass = pr
        if pr is not None and pr < 0.1 and best_pass > 0.1:
            collapse += 1
            if collapse >= 2:
                _log({"event": "agent_stopped", "by": "collapse",
                      "best_pass": best_pass})
                _stop["by"] = "collapse"
                break
        else:
            collapse = 0
        prev = rep
        if _stop["by"] is None:
            time.sleep(interval)
    if os.path.exists(PID):
        os.remove(PID)
    try:
        os.remove(PID + ".lock")
    except OSError:  # noqa: BLE001 — 锁文件可能已无，不掀退出
        pass
    return 0 if _stop["by"] in ("freeze", "daily_limit", "signal") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
