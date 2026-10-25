# -*- coding: utf-8 -*-
"""R453 · L3 新函数族供给（唯一需要 LLM 的一级）。

用法：
    python scripts/supply_l3.py            # 产 1 道，入队
    python scripts/supply_l3.py --n 3      # 产 3 道
    python scripts/supply_l3.py --dry      # 只生成不入队

★ 为什么单独成脚本而不塞进 agent：
  生产 agent 是 `use_llm=false`（不调 LLM）。把 LLM 塞进主循环会
  让 tick 被网络阻塞、成本不可控。L3 是低频动作，按需跑。

★ 收题纪律（fail-closed）：
  两份独立实现必须逐输入一致；不一致/跑挂/样本不足 ⇒ 一道都不收。
  判分器的真值不能是"可能对"。
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

LAST_REL = os.path.join(_ROOT, "var", "supply_l3_last.json")


def _write_last(row: dict) -> None:
    try:
        with io.open(LAST_REL, "w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as e:                      # noqa: BLE001 — 台账写不了不影响出题
        sys.stderr.write("supply_l3_last 写盘失败: %r\n" % (e,))


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=None,
                    help="生成几道（默认：有升级请求按请求量，否则 1）")
    ap.add_argument("--dry", action="store_true", help="只生成不入队")
    ap.add_argument("--max-tokens", type=int, default=700)
    ap.add_argument("--from-request", dest="from_request",
                    action="store_true", default=True,
                    help="消费 agent 写的升级请求（默认开）")
    ap.add_argument("--no-request", dest="from_request", action="store_false")
    args = ap.parse_args(argv)

    from dwc.llm.client import LLMClient
    from dwc.organs import task_supply as TS

    req = None
    if args.from_request and not args.dry:
        req = TS.take_escalation()
        if req:
            print("消费升级请求：n=%d why=%s" % (req["n"], req.get("why")),
                  flush=True)
    n_want = args.n if args.n is not None else (req["n"] if req else 1)

    llm = LLMClient()

    def _ask(p: str) -> str:
        r = llm.complete(p, max_tokens=args.max_tokens)
        return r.text if getattr(r, "ok", False) else ""

    made = []
    for i in range(max(1, int(n_want))):
        diag = {}
        t = TS.generate_family(_ask, seed=i, diag=diag)
        if t is None:
            print("L3 未产出 #%d：%s" % (i, diag.get("why", "unknown")),
                  flush=True)
            continue
        made.append(t)
        print("L3 收题: %s | checks=%d | %s"
              % (t["task_id"], len(t["anchor"]["checks"]),
                 t["anchor"]["prompt"][:40]), flush=True)

    if args.dry:
        print(json.dumps(made, ensure_ascii=False, indent=1)[:1500])
        return 0 if made else 1
    n = TS.admit(made)
    print("入队: %d 道（队列共 %d 道）"
          % (n, len(TS.load_queue())), flush=True)
    _write_last({"ts": time.time(), "wanted": n_want, "made": len(made),
                 "admitted": n, "from_request": bool(req),
                 "task_ids": [t["task_id"] for t in made]})
    return 0 if made else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
