# -*- coding: utf-8 -*-
"""R455 · 供给队列检查点报告（no_agent cron 用，也可手动跑）。

用途：回答"造出来的题到底跑了没、跑了之后难不难"。

    python scripts/supply_checkpoint.py            # 算 + 推飞书
    python scripts/supply_checkpoint.py --no-send  # 只打印

★ 为什么要自己发飞书：no_agent 的 stdout 转发到飞书有静默丢消息的历史
  （见 skill integrations/hermes-cron-feishu），所以脚本自己调 API，
  用 message_id 作为投递证据。

★ 路径用固定常量，不从 __file__ 推导：cron 跑的是
  %LOCALAPPDATA%/hermes/scripts/ 下的副本，__file__ 会指到 hermes 目录。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import urllib.request
from typing import Any, Dict, List, Optional

REPO = r"E:/Divine Wisdom Core"
VAR = os.path.join(REPO, "var")
FEISHU_API = "https://open.feishu.cn/open-apis"


def _rows(name: str) -> List[Dict[str, Any]]:
    p = os.path.join(VAR, name)
    out = []
    try:
        with io.open(p, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        pass
    return out


def _json(name: str) -> Dict[str, Any]:
    try:
        with io.open(os.path.join(VAR, name), encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def build_report(now: Optional[float] = None) -> str:
    t = time.time() if now is None else float(now)
    queue = _rows("task_queue.jsonl")
    log = _rows("dwc_prod_log.jsonl")
    sel = _json("agent_sel.json")
    lvl = _json("supply_level.json")

    terms = [r for r in log if r.get("task") and r.get("pass_rate") is not None]
    ran: Dict[str, List[float]] = {}
    for r in terms:
        ran.setdefault(str(r["task"]), []).append(float(r["pass_rate"]))

    q_ids = [str(x.get("task_id") or "") for x in queue]
    q_ids = [x for x in q_ids if x]
    hit = [x for x in q_ids if x in ran]
    miss = [x for x in q_ids if x not in ran]
    by_lvl: Dict[int, List[str]] = {}
    for x in queue:
        by_lvl.setdefault(int(x.get("level") or 0), []).append(
            str(x.get("task_id") or ""))

    lines = ["📊 供给队列检查点 " + time.strftime("%m-%d %H:%M", time.localtime(t)),
             "",
             "队列 %d 道｜已跑 %d（%d%%）｜未跑 %d"
             % (len(q_ids), len(hit),
                int(round(100.0 * len(hit) / len(q_ids))) if q_ids else 0,
                len(miss))]
    for lv in sorted(by_lvl):
        ids = by_lvl[lv]
        n = sum(1 for x in ids if x in ran)
        lines.append("· L%d %d 道：已跑 %d" % (lv, len(ids), n))

    if hit:
        lines += ["", "已跑题的通过率"]
        for x in hit[:8]:
            v = ran[x]
            lines.append("  %-38s %s ×%d"
                         % (x[:38], " / ".join("%.2f" % p for p in v[-3:]),
                            len(v)))

    recent = terms[-10:]
    if recent:
        buckets = {"1.0": 0, "0.5–0.99": 0, "<0.5": 0}
        for r in recent:
            p = float(r["pass_rate"])
            buckets["1.0" if p >= 0.999 else ("0.5–0.99" if p >= 0.5 else "<0.5")] += 1
        lines += ["", "最近 %d 个 term：%s" % (
            len(recent), " / ".join("%s ×%d" % (k, v) for k, v in buckets.items()))]

    lines += ["", "难度阶梯：level=%s terms=%s why=%s"
              % (lvl.get("level", "?"), lvl.get("terms", "?"),
                 lvl.get("why", "") or "-")]
    s = sel.get("sel") or {}
    d = sel.get("day") or {}
    lines.append("选择状态：used=%d 当日 terms=%s"
                 % (len(s.get("used") or []), d.get("terms", "?")))

    if miss:
        lines += ["", "未跑（前 5）：" + "、".join(x[:26] for x in miss[:5])]
        lines.append("结论：覆盖未完成，还不能判断新题够不够难")
    else:
        hard = [x for x in hit if min(ran[x]) < 0.999]
        lines += ["", "结论：队列已全覆盖；%d/%d 道出现过失败"
                  % (len(hard), len(hit))]
    return "\n".join(lines)


def _feishu_cfg() -> Dict[str, str]:
    """配置解析：cron 的 python 可能没有 yaml ⇒ 正则 fallback（降级留痕）。"""
    p = os.path.join(os.environ.get("LOCALAPPDATA", ""), "hermes", "config.yaml")
    raw = io.open(p, encoding="utf-8").read()
    try:
        import yaml
        return (yaml.safe_load(raw) or {}).get("feishu") or {}
    except Exception as exc:                  # noqa: BLE001 — 降级留痕
        print("checkpoint: yaml 不可用(%r) — 正则解析" % (exc,))
        import re
        def _grab(k):
            m = re.search(r"^\s*%s\s*:\s*[\"']?([^\"'\n]+)" % k, raw, re.MULTILINE)
            return m.group(1).strip() if m else ""
        return {"app_id": _grab("app_id"), "app_secret": _grab("app_secret"),
                "home_channel_id": _grab("home_channel_id")}


def send(text: str) -> str:
    fs = _feishu_cfg()
    req = urllib.request.Request(
        FEISHU_API + "/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": fs["app_id"],
                         "app_secret": fs["app_secret"]}).encode("utf-8"),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        tok = json.loads(r.read().decode("utf-8"))
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
    with urllib.request.urlopen(req2, timeout=30) as r:
        out = json.loads(r.read().decode("utf-8"))
    return out.get("data", {}).get("message_id", "")


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-send", action="store_true")
    a = ap.parse_args(argv)
    text = build_report()
    print(text)
    if a.no_send:
        return 0
    try:
        mid = send(text)
    except Exception as exc:                  # noqa: BLE001 — 投递失败要可见
        print("飞书发送失败: %r" % (exc,))
        return 1
    if not mid:
        print("飞书返回空 message_id ⇒ 视为未送达")
        return 1
    print("message_id=%s" % mid)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
