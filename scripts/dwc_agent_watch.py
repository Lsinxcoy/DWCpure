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

import json
import os
import subprocess
import sys
import time
import urllib.request

#: ★ 固定仓库路径 —— 副本在 hermes/scripts 下, 按 __file__ 定位会探错 var
#:   （CRON RUNS THE COPY 的路径坑, drift watch 同款处置）
HERE = r"E:/Divine Wisdom Core/scripts"      # agent 与本脚本同目录（仓库版）
VAR = r"E:/Divine Wisdom Core/var"
PID = os.path.join(VAR, "dwc_agent.pid")
HB = os.path.join(VAR, "dwc_agent_heartbeat.json")
FROZEN = os.path.join(VAR, "dwc_agent_frozen")
STALL_S = 3 * 600 + 300          # 3×默认interval(600s)+5min 缓冲
FEISHU_API = "https://open.feishu.cn/open-apis"
STATE_PATH = os.path.join(os.environ.get("LOCALAPPDATA", "~"),
                          "hermes", "scripts", ".dwc_agent_watch_state.json")


def _alive() -> bool:
    if not os.path.exists(PID):
        return False
    try:
        pid = int(open(PID, encoding="utf-8").read().strip())
    except Exception:                          # noqa: BLE001
        return False
    try:
        import psutil
        return psutil.pid_exists(pid) and psutil.Process(
            pid).status() != psutil.STATUS_ZOMBIE
    except Exception:                          # noqa: BLE001
        return False


def _fresh() -> bool:
    try:
        hb = json.load(open(HB, encoding="utf-8"))
        t0 = time.mktime(time.strptime(hb["ts"][:19], "%Y-%m-%dT%H:%M:%S"))
        return time.time() - t0 < STALL_S
    except Exception:                          # noqa: BLE001
        return False


def _send(text: str) -> str:
    import yaml
    cfg_path = os.path.join(os.environ.get("LOCALAPPDATA", "~"),
                            "hermes", "config.yaml")
    with open(cfg_path, encoding="utf-8") as fh:
        fs = (yaml.safe_load(fh) or {}).get("feishu") or {}
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
    # 拉活: 后台启动 agent（与 watchdog 同目录的副本）
    agent = os.path.join(HERE, "dwc_agent.py")
    py = os.path.join(os.environ.get("LOCALAPPDATA", "~"), "..")  # placeholder
    py = sys.executable
    subprocess.Popen([py, agent], cwd=os.path.dirname(HERE),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))
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
