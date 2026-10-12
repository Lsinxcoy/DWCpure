# -*- coding: utf-8 -*-
"""R206 · DWC 生产健康探针（P1-5: 监控面窄 → term 健康运行时探针）。

★ 判据（读生产台账 var/dwc_prod_log.jsonl + db + 真值源）:
  ① db 存在且非空 ② 台账可解析 ③ 最近 run 段无 error/stopped_collapse
  ④ 台账停滞（最后事件 > STALL_H）⑤ 真值源在位（dev.json + epoch 可读）
★ 投递契约（同 drift watch）: deliver=local · 直连飞书 API · 正常 rc0 空
  stdout（health=silence）· 异常 _send 后仍 rc0（推送即告警）· 24h 节流
★ CRON RUNS THE COPY: 仓库改完须同步 %LOCALAPPDATA%/hermes/scripts/。
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
import sys
import time
import urllib.request

REPO = _dwc_root()
sys.path.insert(0, os.path.join(REPO, "src"))
VAR = os.path.join(REPO, "var")
DB = os.path.join(VAR, "dwc_prod.sqlite")
LOG = os.path.join(VAR, "dwc_prod_log.jsonl")
STATE_PATH = os.path.join(os.environ.get("LOCALAPPDATA", "~"),
                          "hermes", "scripts", ".dwc_prod_health_state.json")
STALL_H = 6                     # 最后事件超过 6h 无新 ⇒ 停滞告警
THROTTLE_S = 86400
FEISHU_API = "https://open.feishu.cn/open-apis"


def _load(p, default):
    try:
        with open(p, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:                          # noqa: BLE001
        return default


def _feishu_cfg() -> dict:
    import yaml
    path = os.path.join(os.environ.get("LOCALAPPDATA", "~"),
                        "hermes", "config.yaml")
    with open(path, encoding="utf-8") as fh:
        fs = (yaml.safe_load(fh) or {}).get("feishu") or {}
    missing = [k for k in ("app_id", "app_secret", "home_channel_id")
               if not fs.get(k)]
    if missing:
        raise RuntimeError("config.yaml feishu 缺字段: %s" % missing)
    return fs


def _send(text: str) -> str:
    cfg = _feishu_cfg()
    req = urllib.request.Request(
        FEISHU_API + "/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": cfg["app_id"],
                         "app_secret": cfg["app_secret"]}).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        tok = json.loads(resp.read().decode("utf-8"))
    if tok.get("code") != 0:
        raise RuntimeError("token 失败: %s" % tok)
    rid, rid_type = cfg["home_channel_id"], "chat_id"
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
    if out.get("code") != 0:
        raise RuntimeError("发消息失败: %s" % out)
    return out["data"]["message_id"]


def check() -> list:
    """★ 五判据 → 问题清单（空 = 健康）。"""
    issues = []
    # ① db
    if not os.path.exists(DB) or os.path.getsize(DB) == 0:
        issues.append("生产 db 缺失或空: %s" % DB)
    # ②③ 台账可解析 + 最近段无 error/崩塌
    last_ts = None
    if not os.path.exists(LOG):
        issues.append("生产台账缺失: %s" % LOG)
    else:
        rows = []
        for ln in io_open_lines(LOG):
            try:
                rows.append(json.loads(ln))
            except Exception:                  # noqa: BLE001
                issues.append("台账行不可解析: %s" % ln[:80])
        # ★ 口径（首跑误报校准）: error/崩塌只判**最新 run 段** —— 台账
        #   append-only, 段由 event 行分隔; 历史段的 error 已修复, 不该复发
        ev_idx = [i for i, x in enumerate(rows) if "event" in x]
        latest = rows[(ev_idx[-1] + 1) if ev_idx else 0:]
        for row in latest:
            if "error" in row:
                issues.append("最新段 term%d 执行异常: %s"
                              % (row.get("term", -1), str(row["error"])[:90]))
            if row.get("event") == "stopped_collapse":
                issues.append("最新段触发退化崩塌护栏: %s" % row)
        if rows:
            last_ts = rows[-1].get("ts")
    # ④ 停滞
    if last_ts:
        try:
            t0 = time.mktime(time.strptime(
                last_ts[:19], "%Y-%m-%dT%H:%M:%S"))
            if time.time() - t0 > STALL_H * 3600:
                issues.append("台账停滞 %.1fh（最后事件 %s）"
                              % ((time.time() - t0) / 3600, last_ts))
        except Exception:                      # noqa: BLE001
            pass
    # ⑤ 真值源在位 + epoch 可读
    if not os.path.exists(os.path.join(REPO, "config", "anchors", "dev.json")):
        issues.append("真值源 dev.json 缺失")
    try:
        from dwc.harness.anchor_drift import epoch_of
        epoch_of(REPO)                          # 可读即过（不校验值）
    except Exception as exc:                    # noqa: BLE001
        issues.append("epoch_of 读失败: %s: %s" % (type(exc).__name__, exc))
    return issues


def io_open_lines(p):
    with open(p, encoding="utf-8") as fh:
        return [x for x in fh.read().splitlines() if x.strip()]


def main() -> int:
    issues = check()
    if not issues:
        return 0                              # 健康 = 静默（health=silence）
    st = _load(STATE_PATH, {})
    now = time.time()
    sig = "|".join(sorted(issues))[:180]
    if now - float(st.get("last_sent_ts", 0)) < THROTTLE_S \
            and st.get("last_sig") == sig:
        return 0                              # 24h 同签名节流
    ts = time.strftime("%Y-%m-%d %H:%M")
    try:
        mid = _send("🔴 DWC 生产健康告警（%s）\n%s"
                    % (ts, "\n".join("· " + x for x in issues[:8])))
        with open(STATE_PATH, "w", encoding="utf-8") as fh:
            json.dump({"last_sent_ts": now, "last_sig": sig,
                       "last_msg_id": mid}, fh)
        print("alert sent: %s" % mid)
    except Exception as exc:                    # noqa: BLE001
        print("告警发送失败: %s: %s" % (type(exc).__name__, exc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
