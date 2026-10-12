# -*- coding: utf-8 -*-
"""R210 · DWC agent CLI 壳（指令核心的第二前端 — 与 HTTP RPC 共用单实现）。

用法:
  python scripts/dwc_cli.py status
  python scripts/dwc_cli.py submit "任务描述" [--ctx "..."] [--id T_x]
  python scripts/dwc_cli.py query T_x
  python scripts/dwc_cli.py list [--kind pending|done|all]
  python scripts/dwc_cli.py cancel T_x
  python scripts/dwc_cli.py freeze / unfreeze
  python scripts/dwc_cli.py history [--n 20]
  python scripts/dwc_cli.py doctor
  ★ 默认人类可读输出; --json 出机器可解析 JSON（程序消费口）
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc import agent_rpc as R                             # noqa: E402


def _arg(name, default=None, argv=None):
    argv = argv or sys.argv
    return argv[argv.index(name) + 1] if name in argv else default


def main(argv) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 1
    cmd, rest = argv[1], argv[2:]
    as_json = "--json" in argv
    out = None
    if cmd == "status":
        out = R.cmd_status()
    elif cmd == "submit":
        out = R.cmd_submit(rest[0], ctx=_arg("--ctx"),
                           id=_arg("--id"))
    elif cmd == "query":
        out = R.cmd_query(rest[0])
    elif cmd == "list":
        out = R.cmd_list(kind=_arg("--kind", "all"))
    elif cmd == "cancel":
        out = R.cmd_cancel(rest[0])
    elif cmd == "freeze":
        out = R.cmd_freeze()
    elif cmd == "unfreeze":
        out = R.cmd_unfreeze()
    elif cmd == "history":
        out = R.cmd_history(n=int(_arg("--n", "20")))
    elif cmd == "doctor":
        out = R.cmd_doctor()
    else:
        print("未知指令 %r — 可用: %s" % (cmd, sorted(R.METHODS)))
        return 1
    if as_json:
        print(json.dumps(out, ensure_ascii=False, indent=1))
    else:
        _pretty(cmd, out)
    return 0


def _pretty(cmd, out):
    if cmd == "status":
        print("agent: %s%s" % ("alive pid=" + str(out["pid"]) if out["pid"]
                               else "DOWN",
                               " [FROZEN]" if out["frozen"] else ""))
        hb = out.get("heartbeat") or {}
        print("心跳: %s terms=%s pass=%s" % (
            hb.get("ts", "-"), hb.get("terms", "-"), hb.get("pass_rate", "-")))
        q = out["queue"]
        print("队列: pending=%d done=%d | db=%dB"
              % (q["pending"], q["done"], out["db_bytes"]))
    elif cmd == "history":
        for x in out["tail"]:
            keys = {k: v for k, v in x.items() if k != "ts"}
            print(" %s %s" % (str(x.get("ts", ""))[11:19],
                              json.dumps(keys, ensure_ascii=False)[:120]))
    else:
        print(json.dumps(out, ensure_ascii=False, indent=1)[:2000])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
