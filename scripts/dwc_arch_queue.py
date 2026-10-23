# -*- coding: utf-8 -*-
"""架构提案审批 CLI（R438 · #7）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）

用法:
  python scripts/dwc_arch_queue.py --list [--status pending]
  python scripts/dwc_arch_queue.py --approve A_xxx --by 用户 --note "同意"
  python scripts/dwc_arch_queue.py --reject  A_xxx --why "影响判据"

★ 为什么单独一个 CLI：架构改动是**人的决定**，agent 只负责把候选排好、
  把状态记清楚。这里不做"自动批准"，也不替人补理由。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs import arch_queue as AQ   # noqa: E402


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--status", default="", help="pending/approved/rejected")
    ap.add_argument("--approve", default="")
    ap.add_argument("--reject", default="")
    ap.add_argument("--by", default="user")
    ap.add_argument("--note", default="")
    ap.add_argument("--why", default="")
    ap.add_argument("--queue", default="", help="队列文件（缺省 var/...）")
    a = ap.parse_args(argv)

    if a.approve or a.reject:
        pid = a.approve or a.reject
        out = AQ.decide(pid, approve=bool(a.approve), by=a.by,
                        note=(a.note or a.why), p=a.queue)
        print(json.dumps(out, ensure_ascii=False))
        return 0 if out["outcome"] in ("approved", "rejected",
                                       "already_decided") else 1

    rows = AQ.list_items(a.status or None, p=a.queue)
    if not rows:
        print("（队列为空%s）" % ((" · status=%s" % a.status) if a.status else ""))
        return 0
    for r in rows:
        print("[%s] %s  %s → %s" % (r.get("status"), r.get("id"),
                                    r.get("component"), r.get("target")))
        if r.get("patch"):
            print("     patch: %s" % str(r["patch"])[:160])
        if r.get("decided_by"):
            print("     决定: %s @%s" % (r.get("decided_by"), r.get("decided_ts")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
