# -*- coding: utf-8 -*-
"""migrate_memory_scene · 存量失败签名补 scene（一次性迁移）。

★★★ 为什么:
  P0-1 只对**新写入**的失败签名补 scene/detail。存量 129 条 payload
  仍是 {c,q,m,task} ⇒ 自然语言场景词仍召不回。
  ★ 补法（不发明）: failure_sig.payload["task"] 是任务 ID（code_fix_002），
    config/anchors/*.json 里有同名键的 "prompt"（任务描述原文）
    ⇒ 反查映射，把 prompt 写进 scene。查不到就**留空**（不编）。
  ★ 幂等: 已有 scene 的节点跳过；可重复跑。
  ★ 触发 FTS update trigger ⇒ 索引自动同步。

用法:
  python scripts/migrate_memory_scene.py [--db var/dwc_prod.sqlite] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.organs.memory import MemoryKernel  # noqa: E402


def load_anchors() -> dict:
    """合并 config/anchors/*.json（dev.json 为主）。"""
    out: dict = {}
    adir = os.path.join(ROOT, "config", "anchors")
    if not os.path.isdir(adir):
        return out
    for fn in sorted(os.listdir(adir)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(adir, fn), encoding="utf-8") as fh:
                d = json.load(fh)
            if isinstance(d, dict):
                out.update(d)
        except (OSError, ValueError) as exc:
            sys.stderr.write("anchors 读失败 %s: %s\n" % (fn, exc))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.path.join(ROOT, "var", "dwc_prod.sqlite"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    anchors = load_anchors()
    print("anchors 条目: %d" % len(anchors))
    m = MemoryKernel(args.db)
    rows = m._conn.execute(
        "SELECT node_id, payload FROM memory_node"
        " WHERE kind='failure_sig' AND archived_at IS NULL").fetchall()
    n_total = len(rows)
    n_fill = 0
    n_skip_has = 0
    n_no_task = 0
    n_no_anchor = 0
    for r in rows:
        try:
            pl = json.loads(r["payload"] or "{}")
        except ValueError:
            continue
        if pl.get("scene"):
            n_skip_has += 1
            continue
        tid = str(pl.get("task") or "")
        if not tid:
            n_no_task += 1
            continue
        prompt = ""
        _a = anchors.get(tid)
        if isinstance(_a, dict):
            prompt = str(_a.get("prompt") or "")
        if not prompt:
            n_no_anchor += 1
            continue
        pl["scene"] = prompt
        if not args.dry_run:
            m._conn.execute(
                "UPDATE memory_node SET payload=? WHERE node_id=?",
                (json.dumps(pl, ensure_ascii=False), r["node_id"]))
        n_fill += 1
    if not args.dry_run:
        m._conn.commit()
    m.close()
    print("失败签名总数: %d" % n_total)
    print("  补 scene: %d%s" % (n_fill, "（dry-run 未写）" if args.dry_run else ""))
    print("  已有 scene 跳过: %d" % n_skip_has)
    print("  无 task 字段: %d" % n_no_task)
    print("  任务 ID 在 anchors 查不到: %d" % n_no_anchor)
    return 0


if __name__ == "__main__":
    sys.exit(main())
