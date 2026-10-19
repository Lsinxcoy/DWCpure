# -*- coding: utf-8 -*-
"""R208 · DWC agent watchdog（守夜人: 死 → 拉活 + 告警; 不喂食）。

★ 判活: var/dwc_agent.pid（进程在?）+ var/dwc_agent_heartbeat.json
  （心跳 ts 新鲜? 阈值 = 3×interval + 缓冲）。
★ 冻结豁免: var/dwc_agent_frozen 存在 ⇒ agent 本就该停 — 不拉活不告警
  （人工门最高优先级, 与母巢"禁手动重启"同源: 人要停就让它停着）。
★ 拉活: 后台启动 dwc_agent.py 副本（CRON RUNS THE COPY — 与本文件同目录）;
  拉活后飞书告警留痕。正常静默 rc0（health=silence）。
"""
from __future__ import annotations


def _dwc_root():
    """R228: 仓库根发现（env DWC_ROOT > 本文件上溯 — 不写死盘符/用户名）。"""
    _e = os.environ.get("DWC_ROOT", "").strip()
    if _e and os.path.isdir(_e):
        return os.path.abspath(_e)
    _c = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    while not (os.path.isdir(os.path.join(_c, "src", "dwc"))
               and os.path.isdir(os.path.join(_c, "config"))):
        _p = os.path.dirname(_c)
        if _p == _c:
            break
        _c = _p
    else:
        return _c
    # ③ 副本场景（cron 跑 hermes/scripts 下的拷贝 — 上溯找不到仓库）:
    #    同目录 .dwc_repo 标记（同步时写入一行仓库路径）
    _mk = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       ".dwc_repo")
    if os.path.isfile(_mk):
        with open(_mk, encoding="utf-8") as _f:
            _r = _f.readline().strip()
        if _r and os.path.isdir(_r):
            return _r
    raise RuntimeError("找不到 DWC 根 — 设 DWC_ROOT 或同步副本(写 .dwc_repo)")

import json
import os
import subprocess
import sys
import time
import urllib.request

#: ★ 固定仓库路径 —— 副本在 hermes/scripts 下, 按 __file__ 定位会探错 var
#:   （CRON RUNS THE COPY 的路径坑, drift watch 同款处置）
HERE = _dwc_root() + "//scripts"      # agent 与本脚本同目录（仓库版）
VAR = _dwc_root() + "//var"
PID = os.path.join(VAR, "dwc_agent.pid")
HB = os.path.join(VAR, "dwc_agent_heartbeat.json")
FROZEN = os.path.join(VAR, "dwc_agent_frozen")
STALL_S = 3 * 600 + 300          # 3×默认interval(600s)+5min 缓冲
FEISHU_API = "https://open.feishu.cn/open-apis"
STATE_PATH = os.path.join(os.environ.get("LOCALAPPDATA", "~"),
                          "hermes", "scripts", ".dwc_agent_watch_state.json")


def _agent_python() -> str:
    """★ R243a: 拉活解释器 — cron 的 sys.executable 缺 yaml/psutil,
    agent 拉起即崩(14:15 实测: 拉活进程无心跳)。DWC 真身必须用
    hermes venv(全依赖); env DWC_PY 可覆盖; 降级 sys.executable(留痕)。"""
    _p = os.environ.get("DWC_PY", "").strip()
    if _p and os.path.isfile(_p):
        return _p
    _v = os.path.join(os.environ.get("LOCALAPPDATA", "~"), "hermes",
                      "hermes-agent", "venv", "Scripts", "python.exe")
    if os.path.isfile(_v):
        return _v
    print("watchdog: venv 缺失 — 降级 sys.executable(agent 可能缺依赖)")
    return sys.executable


def _alive() -> bool:
    # ★ R369: 以真实进程为准，避免 stale 心跳/锁误判
    try:
        import psutil
        for _p in psutil.process_iter(['cmdline']):
            _c = _p.info.get('cmdline') or []
            if len(_c) >= 2 and 'dwc_agent.py' in str(_c[1]):
                return True
    except Exception:  # noqa: BLE001
        pass
    if not os.path.exists(PID):
        return False
    try:
        pid = int(open(PID, encoding="utf-8").read().strip())
    except Exception:  # noqa: BLE001
        return False
    try:
        import psutil
        return psutil.pid_exists(pid) and psutil.Process(
            pid).status() != psutil.STATUS_ZOMBIE
    except Exception:  # noqa: BLE001
        return False


def _fresh() -> bool:
    try:
        hb = json.load(open(HB, encoding="utf-8"))
        t0 = time.mktime(time.strptime(hb["ts"][:19], "%Y-%m-%dT%H:%M:%S"))
        return time.time() - t0 < STALL_S
    except Exception:                          # noqa: BLE001
        return False


def _feishu_cfg() -> dict:
    """★ R243a: 配置解析 — cron 的 python 无 yaml(14:15 实测告警崩),
    正则 fallback 保告警必达(降级留痕)。"""
    cfg_path = os.path.join(os.environ.get("LOCALAPPDATA", "~"),
                            "hermes", "config.yaml")
    raw = open(cfg_path, encoding="utf-8").read()
    try:
        import yaml
        return (yaml.safe_load(raw) or {}).get("feishu") or {}
    except Exception as exc:                    # noqa: BLE001 — 降级留痕
        print("watchdog: yaml 不可用(%s) — 正则解析 feishu 配置" % exc)
        import re as _re
        def _grab(k):
            m = _re.search(r"^\s*%s\s*:\s*[\"']?([^\"'\n]+)" % k,
                           raw, _re.MULTILINE)
            return m.group(1).strip() if m else ""
        return {"app_id": _grab("app_id"),
                "app_secret": _grab("app_secret"),
                "home_channel_id": _grab("home_channel_id"),
                "home_channel_type": _grab("home_channel_type")}


def _send(text: str) -> str:
    fs = _feishu_cfg()
    req = urllib.request.Request(
        FEISHU_API + "/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": fs["app_id"],
                         "app_secret": fs["app_secret"]}).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        tok = json.loads(resp.read().decode("utf-8"))
    rid, rid_type = fs["home_channel_id"], "chat_id"
    if rid.startswith("ou_"):
        rid_type = "open_id"
    body = {"receive_id": rid, "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False)}
    req2 = urllib.request.Request(
        FEISHU_API + "/im/v1/messages?receive_id_type=" + rid_type,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + tok["tenant_access_token"]})
    with urllib.request.urlopen(req2, timeout=30) as resp:
        out = json.loads(resp.read().decode("utf-8"))
    return out.get("data", {}).get("message_id", "")


def main() -> int:
    if os.path.exists(FROZEN):
        return 0                              # 人工冻结中: 守夜人不干预
    reason = None
    if not _alive():
        reason = "进程不在（pid 丢失或已死）"
    elif not _fresh():
        reason = "心跳停滞（> %d 分钟无心跳）" % (STALL_S // 60)
    if reason is None:
        return 0                              # 活着且新鲜 = 静默
    # ★ R369: 清理 stale 锁文件（进程死但 .lock 残留）—— 仅在可加锁时删
    try:
        _lfd = os.open(os.path.join(os.path.dirname(PID), os.path.basename(PID) + ".lock"),
                       os.O_RDWR)
        import msvcrt
        msvcrt.locking(_lfd, msvcrt.LK_NBLCK, 1)
        msvcrt.locking(_lfd, msvcrt.LK_UNLCK, 1)
        os.close(_lfd)
        os.remove(os.path.join(os.path.dirname(PID), os.path.basename(PID) + ".lock"))
    except (OSError, FileNotFoundError):   # noqa: BLE001 — 活锁或无文件，不删
        pass
    # 拉活: 后台启动 agent（与 watchdog 同目录的副本）
    agent = os.path.join(HERE, "dwc_agent.py")
    py = _agent_python()
    _flags = (getattr(subprocess, "DETACHED_PROCESS", 0x00000008)
              | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
              | getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000))
    # ★ G7: stderr 留痕（07:04 无痕死亡后 — 崩溃必须有尸检材料）
    _errf = open(os.path.join(os.path.dirname(HERE), "var",
                              "dwc_agent_stderr.log"), "a",
                 encoding="utf-8", errors="replace")
    _errf.write("\n===== 拉活 %s (%s) =====\n"
                % (time.strftime("%Y-%m-%dT%H:%M:%S"), reason))
    _errf.flush()
    subprocess.Popen([py, agent], cwd=os.path.dirname(HERE),
                     stdout=subprocess.DEVNULL, stderr=_errf,
                     creationflags=_flags, close_fds=True)
    ts = time.strftime("%Y-%m-%d %H:%M")
    try:
        mid = _send("🟡 DWC agent 已拉活（%s）\n原因: %s" % (ts, reason))
        with open(STATE_PATH, "w", encoding="utf-8") as fh:
            json.dump({"last_restart_ts": time.time(),
                       "reason": reason, "msg_id": mid}, fh)
        print("restarted: %s msg=%s" % (reason, mid))
    except Exception as exc:                    # noqa: BLE001
        print("拉活告警发送失败: %s" % exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
