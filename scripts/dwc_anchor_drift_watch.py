# -*- coding: utf-8 -*-
"""DWC anchor drift 监控（no_agent cron · 脚本自持飞书投递）。

★ 对应审计 P1-1 裁决（用户令"全部执行推荐"= 推荐③接入常驻）:
  drift_signals 此前**仅测试接线** — 信号触发无常驻报告路径; 本脚本 =
  生产消费方（cron 每 2h 跑, 有建议即飞书推送, 无建议日度心跳）。

★ 投递契约（hermes-cron-feishu skill 纪律）:
  · deliver: local（no_agent 的 stdout→feishu 转发不可靠 — silent 陷阱）
  · 脚本直连 Feishu API（config.yaml feishu block + open_id 私聊）
  · exit 0 + 空 stdout = 健康静默; 有建议/心跳 = print + 投递
  · YELLOW 节流: 同一建议 key 24h 内不重发（防轰炸）
  · 日度 HEALTHY 心跳: 证明监视器活着（静默=死 与 静默=健康 必须可分）

★ CRON RUNS THE COPY: cron 的 script 字段解析到 %LOCALAPPDATA%/hermes/
  scripts/ — 仓库改完必须同步副本（本文件是真源）。
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

import glob
import json
import os
import sys
import time
import urllib.request


def _ensure_runtime():
    """★★★ R428 · cron 跑的是 hermes 内置 python（**没有 pyyaml**），
    而本脚本 import dwc ⇒ dwc 依赖 yaml ⇒ 连续 19 次
    `ModuleNotFoundError: No module named 'yaml'`，cron 一直是 error。

    根因不是脚本坏了，是**跑它的解释器不是装依赖的那个**。
    启动时自我切换到带依赖的解释器（不写死盘符/用户名）。
    """
    try:
        import yaml  # noqa: F401
        return
    except ModuleNotFoundError:
        pass
    _root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    _la = os.environ.get("LOCALAPPDATA", "")
    _cands = [
        os.path.join(_root, "hermes-agent", "venv", "Scripts", "python.exe"),
        os.path.join(_root, "hermes-agent", "venv", "bin", "python"),
        os.path.join(_root, "venv", "Scripts", "python.exe"),
        os.path.join(_root, ".venv", "Scripts", "python.exe"),
    ]
    if _la:   # 仓库副本场景：venv 在 hermes 根下，不在仓库里
        _cands.insert(0, os.path.join(
            _la, "hermes", "hermes-agent", "venv", "Scripts", "python.exe"))
    for _cand in _cands:
        if (os.path.isfile(_cand)
                and os.path.abspath(sys.executable) != os.path.abspath(_cand)):
            # ★ Windows 的 os.execv **不引号化参数** —— 路径含空格
            #   （`E:\Divine Wisdom Core`）会被拆成 `E:\Divine` ⇒ 报
            #   `can't open file 'E:\Divine'`。subprocess 的列表形式才会
            #   正确加引号（现场：R428 自测）。
            import subprocess as _sp
            raise SystemExit(_sp.call(
                [_cand, os.path.abspath(__file__)] + sys.argv[1:]))
    sys.stderr.write("缺少 pyyaml 且找不到带依赖的解释器\n")
    raise SystemExit(2)


_ensure_runtime()

# ★ 以脚本位置定位仓库根（cron 副本在 hermes/scripts 下 ⇒ 用固定仓库路径）
REPO = _dwc_root()
sys.path.insert(0, os.path.join(REPO, "src"))

from dwc.harness.anchor_drift import drift_signals  # noqa: E402

STATE_PATH = os.path.join(os.environ.get("LOCALAPPDATA", "~"),
                          "hermes", "scripts", ".dwc_drift_watch_state.json")
THROTTLE_S = 86400          # 同 key 建议 24h 节流
FEISHU_API = "https://open.feishu.cn/open-apis"


def _load_state() -> dict:
    try:
        with open(STATE_PATH, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:                          # noqa: BLE001 — 缺/坏 = 全新状态
        return {}


def _save_state(st: dict) -> None:
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as fh:
        json.dump(st, fh, ensure_ascii=False)


def _feishu_cfg() -> dict:
    """从 hermes config.yaml 读 feishu block（Case A — skill 语料的已知好形态）。"""
    import yaml
    path = os.path.join(os.environ.get("LOCALAPPDATA", "~"),
                        "hermes", "config.yaml")
    with open(path, encoding="utf-8") as fh:
        cfg = yaml.safe_load(fh) or {}
    fs = cfg.get("feishu") or {}
    need = ("app_id", "app_secret", "home_channel_id")
    missing = [k for k in need if not fs.get(k)]
    if missing:
        raise RuntimeError("config.yaml feishu 缺字段: %s" % missing)
    return fs


def _send(text: str) -> str:
    """直连飞书 API 发文本; 返回 message_id（真投递证明）。"""
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
    if rid.startswith("ou_"):                   # open_id 私聊（skill 2026-08-19 方案）
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


def main() -> int:
    sig = drift_signals(REPO)
    sugg = list(sig.get("suggestions") or [])
    today = time.strftime("%Y-%m-%d")
    st = _load_state()

    key = json.dumps(sorted(sugg), ensure_ascii=False)   # R202: 无建议也定义
    if sugg:
        last = st.get("sugg") or {}
        if last.get("key") == key and time.time() - last.get("t", 0) < THROTTLE_S:
            return 0                            # 同建议 24h 内 ⇒ 静默节流
        lines = ["🪝 DWC anchor drift 信号（epoch %s）" % sig.get("epoch")]
        lines.append("rung_mix: %s" % json.dumps(sig.get("rung_mix"),
                                                 ensure_ascii=False))
        lines.append("dev_pass_rate: %s (n=%s)" % (
            sig.get("dev_pass_rate"), sig.get("n_dev")))
        for s_ in sugg:
            lines.append("· 建议: %s" % s_)
        lines.append("处置入口: drift_signals(REPO) / docs/AUDIT_R197_R200.html")
        text = "\n".join(lines)
        mid = _send(text)
        st["sugg"] = {"key": key, "t": time.time(), "message_id": mid}
        _save_state(st)
        print(text)                              # print = 投递留痕（deliver local）
        return 1                                 # 有建议 ⇒ exit 1（输出被记）

    # 无建议 ⇒ 静默 exit 0（cron 2h tick 不轰炸 — 空 stdout = 健康）
    # 日度存活心跳: 只有当天首次 tick 且**无建议**时才发一条（证明活着）;
    # 次日 0 点后再次发。非当日 ⇒ 静默。
    if st.get("heartbeat") != today:
        text = ("✅ DWC anchor drift 健康心跳 · %s · epoch %s · "
                "rung_mix=%s · 无漂移建议" % (
                    today, sig.get("epoch"),
                    json.dumps(sig.get("rung_mix"), ensure_ascii=False)))
        mid = _send(text)
        st["heartbeat"] = today
        st["last_heartbeat_mid"] = mid
        _save_state(st)
        print(text)                    # print = 投递（deliver local 存档）
    st.pop("sugg", None)               # 建议消失 ⇒ 清节流缓存（下次触发可重报）
    _save_state(st)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:                    # noqa: BLE001 — 异常必须可见
        print("dwc_drift_watch 异常: %r" % exc)
        sys.exit(2)
