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
import threading
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
#: ★ R375 · 任务池 = judge.anchors 的**全部 16 个真任务**（旧池只有 11 个，
#:   漏掉 code_fix_007/008/009 —— 三个 behavior 任务从未被跑过）。
#:   behavior = LLM 唯一能接管的一类（`LLMExecutorFactory._enabled`），
#:   漏在池外 = 那一整片能力面永不执行。有测试锁
#:   `test_r375_task_selection::test_dev_pool_covers_all_anchor_tasks`。
DEV_POOL = (
    # behavior（LLM 可接管 —— 新失败类型的唯一来源）
    "code_fix_001", "code_fix_002", "code_fix_003", "code_fix_004",
    "code_fix_005", "code_fix_006", "code_fix_007", "code_fix_008",
    "code_fix_009",
    # keyword_match（答案文本执行器）
    "reasoning_001", "reasoning_002", "reasoning_003", "reasoning_004",
    # expected_values（答案文本 + 数值对）
    "reproduce_001", "reproduce_002", "reproduce_003",
)

#: ★★★ R375 · 逃逸阀阈值：同一任务**连续**被选中 N 次 ⇒ 强制换。
#:   为什么是 3：① 保留「同一失败重复 3 次」的簇频次信号（run_round 的
#:   item["n"] 靠它排序）；② 16 任务 × 3 = 48 轮覆盖一圈（600s/term ≈ 8h）。
#:   0 = 关闭逃逸（回到旧固定点行为，只给回滚/对照实验用）。
STUCK_LIMIT = 3

#: 选择态（进程内）。last/streak = 连续计数；used = LRU 历史（最近在尾部）；
#: cooldown = 卡住的任务 → 剩余让位轮数（逃逸后置为「池子扫完一圈」）。
_sel = {"last": None, "streak": 0, "used": [], "cooldown": {}}
_day = {"key": time.strftime("%Y-%m-%d"), "terms": 0, "cost": 0.0}
_stop = {"by": None}

#: ★★★ R382 · 收件箱互斥锁 —— 轮询线程与其它调用方并发读 INBOX 时，
#:   "读到未处理 → 返回" 不是原子的 ⇒ 同一单会被取两次（重复投递）。
_INBOX_LOCK = threading.Lock()

#: ★★★ R382 · 收件箱轮询间隔（秒）。
#:   现场（2026-10-20 全池跑批）：投单 13:47:29 → 接单 13:55:06
#:   （排队 7 分 37 秒），执行只用 5 秒。根因是 `take_inbox()` 在主循环
#:   里、每个 term 才轮询一次，而一个 term 实测 ~10 分钟。
#:   ⇒ 用户委托被排在自主循环后面，52 单要跑 6 小时。
INBOX_POLL_SEC = 3.0


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


#: ★★★ R398 · 同一单最多被"重取"几次（stale 恢复）。
#:   现场：一单被重跑 52 次，把收件箱堵死、端点打满。
MAX_REPICK = 3
#: 重取计数落盘（跨重启保持 —— 重启不该重置重试预算）
ATTEMPTS = os.path.join(VAR, "dwc_inbox_attempts.json")


def _bump_attempt(tid: str) -> int:
    """同一 task_id 的重取次数 +1（落盘，跨重启保持）。"""
    try:
        d = {}
        if os.path.exists(ATTEMPTS):
            try:
                d = json.loads(open(ATTEMPTS, encoding="utf-8").read()) or {}
            except Exception:                      # noqa: BLE001
                d = {}
        n = int(d.get(tid, 0)) + 1
        d[tid] = n
        os.makedirs(VAR, exist_ok=True)
        with open(ATTEMPTS, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False)
        return n
    except Exception:                              # noqa: BLE001
        return 1                                   # 计数失败不阻断取单


def take_inbox():
    """★ 取第一条未处理的收件箱任务（None = 空）。done 态落 INBOX_DONE。
    ★★★ R382 · 必须持锁（`_INBOX_LOCK`）：
      现场（2026-10-20 全池跑批）收件箱改成独立轮询线程后，轮询线程与
      其它调用方会并发读同一个 INBOX 文件；"读到未处理 → 返回"之间没有
      原子性 ⇒ 同一单被取两次（重复投递/重复计费）。
    """
    with _INBOX_LOCK:
        return _take_inbox_locked()


def _take_inbox_locked():
    """take_inbox 的实体（调用方必须已持 `_INBOX_LOCK`）。"""
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
                # ★★★ R398 · **重取次数上限** —— 现场（2026-10-21 00:09）：
                #   一单 analyze 跑了 45 分钟，会话日志里 **52 个 task_mode**
                #   （同一 task_id 被反复重跑，每 30~60 秒一次），把收件箱
                #   堵死、把端点打满，整轮跑批作废。
                #   根因是 `running:<ts>` 在长任务里不刷新 ⇒ 15 分钟后被判
                #   stale ⇒ 重取；重取的线程又写回旧标记 ⇒ 永远 stale。
                #   ⇒ 加硬上限：同一单最多重取 MAX_REPICK 次，超了标记
                #     `failed:too_many_attempts` 并**停止重试**（不许无限烧）。
                _n = _bump_attempt(tid)
                if _n > MAX_REPICK:
                    st[tid] = "failed:too_many_attempts"
                    with open(INBOX_DONE, "w", encoding="utf-8") as fh:
                        json.dump(st, fh, ensure_ascii=False)
                    _log({"event": "inbox_attempt_cap", "id": tid,
                          "attempts": _n})
                    continue
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
    # ★★★ R398 · **执行期间刷新 running 标记**（每 60s）。
    #   现场：一单 analyze 跑 45 分钟，标记停在起始时刻 ⇒ 15 分钟后
    #   被 `take_inbox()` 判 stale ⇒ 重取 ⇒ 同一单被重跑 52 次。
    #   心跳让它一直是"新鲜 running"，正常长任务不会被抢走。
    _hb_stop = threading.Event()

    def _hb_refresh():
        while not _hb_stop.wait(60):
            try:
                s = _done_state()
                s[item["id"]] = "running:%.0f" % time.time()
                with open(INBOX_DONE, "w", encoding="utf-8") as fh:
                    json.dump(s, fh, ensure_ascii=False)
            except Exception:          # noqa: BLE001 — 心跳失败不影响执行
                pass

    threading.Thread(target=_hb_refresh, daemon=True,
                     name="inbox-hb-" + item["id"]).start()
    try:
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
    except Exception as exc:          # noqa: BLE001
        # ★ R398 · 执行抛异常也必须**停心跳**，否则标记永远是 running
        #   ⇒ 这一单既不会完成也不会被重取（比崩溃更糟）。
        _hb_stop.set()
        rep = {"task": item.get("task"), "status": "incomplete",
               "why": "执行异常: %s: %s" % (type(exc).__name__, exc)}
    _hb_stop.set()                    # ★ R398 · 正常路径也停心跳
    rep = {"id": item["id"], **rep,
           "ts": time.strftime("%Y-%m-%dT%H:%M:%S+08:00")}
    os.makedirs(REPORTS, exist_ok=True)
    with open(os.path.join(REPORTS, item["id"] + ".json"), "w",
              encoding="utf-8") as fh:
        json.dump(rep, fh, ensure_ascii=False, indent=1)
    st = _done_state()
    st[item["id"]] = rep["status"]
    _hb_stop.set()                    # ★ R398 · 先停心跳，再写终态（防覆盖）
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


def _note_used(tid: str) -> None:
    """记录一次选择（LRU：最近用过的挪到尾部）。"""
    used = _sel.setdefault("used", [])
    if tid in used:
        used.remove(tid)
    used.append(tid)


def _lru_pick(pool, exclude=()) -> str:
    """池里**最久没用过**的任务（从未用过的优先）。

    ★ 为什么不用随机/顺序轮询：随机会让「刚失败的任务」很快被重选，
      顺序轮询会周期性回到固定点。LRU 保证逃逸后覆盖的是**最久没碰**的面。
    """
    skip = set(exclude)
    cand = [t for t in pool if t not in skip]
    if not cand:                        # 整池都在冷却（不该发生）⇒ 取池首
        return pool[0] if pool else ""
    used = _sel.get("used", [])
    for t in cand:                      # 从未用过 ⇒ 优先
        if t not in used:
            return t
    return min(cand, key=lambda t: used.index(t))


def _tick_cooldown() -> None:
    """每轮递减冷却计数，归零即解除。"""
    cd = _sel.setdefault("cooldown", {})
    for k in list(cd):
        cd[k] = int(cd[k]) - 1
        if cd[k] <= 0:
            del cd[k]


def select_task(prev_rep, pool=None) -> str:
    """★ agent 自主任务源: 上轮 next_task_source 优先（它的测量触发它的
    下一轮）; 无/空 ⇒ 池轮询（seed 语义）。

    ★★★ R375 · 逃逸阀: 同一任务**连续**选中超过 `STUCK_LIMIT` 次 ⇒ 强制
      切到池里最久没用过的任务，并让该任务**冷却一整圈**（直到池里其余
      任务都被跑过）—— 否则下轮 advice 又把任务拽回去，逃逸形同虚设
      （实测只给 25% 探索率）。
      病根: 取 `nodes[0]` 一旦收敛就永久卡住 —— 生产日志 1120 term 只跑过
      12 个任务, `reproduce_003` 占 949 次（85%）; 而 `Evolver._seen` 按
      key 去重 ⇒ 重复跑产 0 个新提案。**吞吐 ≠ 信号**。
    """
    pool = tuple(pool or DEV_POOL)
    _tick_cooldown()
    cd = _sel.setdefault("cooldown", {})

    tasks = ((prev_rep.next_task_source or {}).get("tasks")
             if prev_rep is not None else None) or []
    nodes = [t["node"] for t in tasks
             if t.get("kind") == "world_tree_action" and t.get("node")]
    cand = nodes[0] if nodes else pool[_day["terms"] % len(pool)]

    if cand in cd:                      # 冷却中 ⇒ 让位（advice 不是强制令）
        cand = _lru_pick(pool, list(cd))
        _sel["last"] = cand
        _sel["streak"] = 1
        _note_used(cand)
        return cand

    if cand == _sel.get("last"):
        _sel["streak"] = int(_sel.get("streak", 0)) + 1
    else:
        _sel["last"] = cand
        _sel["streak"] = 1

    if STUCK_LIMIT and _sel["streak"] > STUCK_LIMIT:
        stuck = cand
        # ★ 冷却一整圈：池里其余任务各跑一次之前不回来
        cd[stuck] = max(1, len(pool) - 1)
        cand = _lru_pick(pool, list(cd))
        _sel["last"] = cand
        _sel["streak"] = 1

    _note_used(cand)
    return cand


def collapse_triggered(best_pass, pr, collapse, synthetic=False):
    """★ Phase 1.3 · 塌陷判定纯函数（可测）。

    返回 (triggered, new_collapse)。synthetic=True 时永不触发且重置。
    """
    if synthetic:
        return False, 0
    if pr is not None and pr < 0.1 and best_pass > 0.1:
        collapse = int(collapse or 0) + 1
        return collapse >= 2, collapse
    return False, 0


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


def _dispatch_inbox(item: dict, use_llm: bool) -> None:
    """★ R382 · 把一单收件箱任务派给后台线程（Semaphore 限并发 2）。"""
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


def start_inbox_poller(interval: float = INBOX_POLL_SEC,
                       stop_event=None, use_llm: bool = True):
    """★★★ R382 · 独立的收件箱轮询线程（秒级，不等 term 间隙）。

    现场（2026-10-20 全池跑批）：投单 13:47:29 → 接单 13:55:06，
    **排队 7 分 37 秒**，而执行只用 5 秒。根因：`take_inbox()` 在主循环
    里，每个 term 才轮询一次，一个 term 实测 ~10 分钟。注释写着
    「收件箱优先（用户委托 > 自我改进锚任务）」，实现却是"收件箱每
    10 分钟才被看一次" —— 52 单要跑 6 小时。

    修法：轮询与自主 term **解耦**，独立 daemon 线程按秒轮询。
    用户委托不再排在自主循环后面。

    `stop_event` 为 `threading.Event`，置位即优雅退出（返回线程对象）。
    """
    stop_event = stop_event or threading.Event()

    def _loop():
        while not stop_event.is_set():
            try:
                item = take_inbox()      # 内部已持 _INBOX_LOCK
            except Exception as exc:     # noqa: BLE001 — 轮询不许死
                _log({"event": "inbox_poll_error",
                      "error": "%s: %s" % (type(exc).__name__, exc)})
                item = None
            if item is not None:
                try:
                    _dispatch_inbox(item, use_llm)
                except Exception as exc:  # noqa: BLE001
                    _log({"event": "inbox_dispatch_error", "id": item.get("id"),
                          "error": "%s: %s" % (type(exc).__name__, exc)})
            stop_event.wait(interval)    # ★ 可被 stop_event 立即唤醒

    t = threading.Thread(target=_loop, daemon=True, name="inbox-poller")
    t.start()
    return t


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
    # ★★★ R382 · 收件箱改**独立轮询线程**（秒级），不再等 term 间隙。
    #   现场：投单 13:47:29 → 接单 13:55:06（排队 7 分 37 秒），执行只用
    #   5 秒；一个 term 实测 ~10 分钟 ⇒ 52 单要跑 6 小时。
    #   用户委托不该排在自主循环后面。
    _inbox_stop = threading.Event()
    start_inbox_poller(INBOX_POLL_SEC, _inbox_stop, use_llm)
    _log({"event": "inbox_poller_started", "interval": INBOX_POLL_SEC})

    while _stop["by"] is None:
        if _freeze_check() or _budget_check(tpd, bpd):
            break
        # 日界滚动（次日自动复位计数）
        if _day["key"] != time.strftime("%Y-%m-%d"):
            _day.update(key=time.strftime("%Y-%m-%d"), terms=0, cost=0.0)
        # ★ R266C · 进化投单（每轮开头: 未派发论文 → 深读任务候选）
        maybe_dispatch_reading()
        # ── R209 · 收件箱已由 start_inbox_poller 独立消费（R382）──
        #   主循环不再同步取单（否则与轮询线程抢单）。
        item = None
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
        # ★★★ R375 · select_task 必须在 monitor 跳过判定**之后**调用 ——
        #   否则被跳过的 tick 也消耗「连续计数/冷却轮数」：生产实测
        #   interval=90 时 5 分钟里 2 次跳过 + 2 个 term，选择态空转了
        #   2 格，冷却会在池子扫完前就到期（逃逸保证被削弱）。
        #   有源码序测试锁（test_r375::test_select_task_after_monitor_skip）。
        task = select_task(prev)
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
              "synthetic": bool(getattr(rep, "synthetic", False)),
              "evo_feed": rep.evo_feed,
              "next": [t.get("kind") for t in
                       (rep.next_task_source or {}).get("tasks", [])]})
        _heartbeat(status="alive", terms=_day["terms"],
                   last_task=task, pass_rate=pr)
        if pr is not None and pr > best_pass:
            best_pass = pr
        triggered, collapse = collapse_triggered(
            best_pass, pr, collapse, bool(getattr(rep, "synthetic", False)))
        if triggered:
            _log({"event": "agent_stopped", "by": "collapse",
                  "best_pass": best_pass})
            _stop["by"] = "collapse"
            break
        if not (pr is not None and pr < 0.1 and best_pass > 0.1
                and not bool(getattr(rep, "synthetic", False))):
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
