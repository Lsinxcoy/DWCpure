# -*- coding: utf-8 -*-
"""dep(z) 定向失效扫描 —— R113 · E1（设计稿④ §⑥, 与裁决① HCE 合流的那份记录）。

语义（RQGM selective erasure + Metis invalidate 同型 — RUMINATE 探针③:
文献已知做法）: 换评估器 ⇒ **只标记依赖旧评估器的档**, 其余历史不动;
**不物理删**（Humanlaya 版本化 — 历史可审计）只改有效性状态。

分栏（设计稿④ §⑦ 弃置三态的 E1 面）:
  active                     — 六段档且 judge_fingerprint == 当前 judge.py 指纹
  deprecated_by_evaluator    — **换代判决已发生**(E2 regime_change) 且档指纹
                               属换代前（R119 修正: 字节漂移本身不触发 —
                               无换代则 fp≠当前仍 active+drift 标注）
  pre_depz_legacy            — 无 inheritance 字段的旧档（依赖记录建立前,
                               不可判定 — 显式栏, 不冒充 active）
★ 本脚本**只读不改档** — deprecated 的真正置位动作在换代轮（E2）按本报告执行。

读:  archive/knowledge3_*.json · src/dwc/organs/judge.py（当前指纹）
写:  docs/dep_scan.json
用法: python scripts/dep_scan.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.foundation.inheritance import judge_fingerprint  # noqa: E402

JUDGE_PATH = os.path.join(ROOT, "src", "dwc", "organs", "judge.py")


def split_fingerprint(root: str) -> str | None:
    """★ 当前 split 指纹 = dev.json _split 分组 sha8（稿⑥§⑥）。
    缺 _split ⇒ None = 拆分未启用 ⇒ split 栏全 0 如实（不装）。"""
    import hashlib
    dev = json.load(open(os.path.join(root, "config", "anchors",
                                      "dev.json"), encoding="utf-8"))
    sp = dev.get("_split")
    if not (isinstance(sp, dict) and sp.get("val")):
        return None
    blob = json.dumps({"search": sorted(sp.get("search", [])),
                       "val": sorted(sp.get("val", []))},
                      ensure_ascii=False).encode()
    return hashlib.sha256(blob).hexdigest()[:8]


def scan(archive_dir: str, current_fp: str,
         cur_split: str | None = None,
         regime_change: bool = False) -> Dict[str, Any]:
    """★ R119 语义修正（选项3 · 稿④§⑥字面「换评估器只抹依赖记录」）:
    deprecated_by_evaluator 的触发源 = **换代判决**（E2 对拍 regime_change）,
    不是字节哈希本身 — 兼容性扩展（加默认 kwarg 等）造成 fp 漂移但无换代
    ⇒ 保持 active + rows.drift 标注漂移事实（不静默, 不误弃）。
    regime_change=True 时 fp≠当前的档进 deprecated（换代前旧档）。"""
    rows: List[Dict[str, Any]] = []
    bucket = {"active": [], "deprecated_by_evaluator": [],
              "deprecated_by_split_change": [], "pre_depz_legacy": []}
    for fn in sorted(os.listdir(archive_dir)):
        if not (fn.startswith("knowledge3_") and fn.endswith(".json")):
            continue
        with open(os.path.join(archive_dir, fn), encoding="utf-8") as f:
            rec = json.load(f)
        if not isinstance(rec, dict):
            continue                       # 历史 list 形态档（inheritance 同款）
        inh = rec.get("inheritance")
        if not isinstance(inh, dict):
            bucket["pre_depz_legacy"].append(fn)
            rows.append({"file": fn, "status": "pre_depz_legacy",
                         "judge_fingerprint": None,
                         "why": "无六段/无依赖字段（dep(z) 建立前）"})
            continue
        ec = inh.get("evaluation_config") or {}
        fp = ec.get("judge_fingerprint")
        sfp = ec.get("split_fingerprint")
        # ★ 判定树（稿⑥§⑥ 第二触发源激活 · 优先级: pre > 换代 > 拆分 > active）
        drift = bool(fp) and fp != current_fp
        if not fp:
            status = "pre_depz_legacy"
            why = "字段缺失（E1 依赖字段建立前）"
        elif regime_change and drift:
            # ★ 只有**换代判决发生**才弃置（字节漂移本身不触发 — R119）
            status = "deprecated_by_evaluator"
            why = "★ 换代已发生 且 档指纹属换代前 ⇒ 置 deprecated"
        elif cur_split is not None and (sfp is None or sfp != cur_split):
            # 拆分启用后: 无 split 指纹 = 拆分前档; 有但不同 = 拆分改过
            status = "deprecated_by_split_change"
            why = ("★ 拆分前档（无 split_fingerprint）" if sfp is None
                   else "★ split 指纹 ≠ 当前 ⇒ 拆分触发")
        else:
            status = "active"
            why = ("judge + split 指纹与当前一致" if not drift else
                   "字节漂移(fp≠当前)但**无换代判决** ⇒ 保持 active"
                   "（R119: dep(z) 触发源=换代判决 not 字节哈希）")
        bucket[status].append(fn)
        rows.append({"file": fn, "status": status,
                     "judge_fingerprint": fp, "split_fingerprint": sfp,
                     "drift": drift, "why": why})
    return {
        "protocol": ("dep(z): 只标记依赖旧评估器的档, 不物理删; 本报告只读, "
                     "置位动作在换代轮(E2)按此执行"),
        "current_judge_fingerprint": current_fp,
        "counts": {k: len(v) for k, v in bucket.items()},
        "rows": rows,
        "note": ("deprecated_by_evaluator=0 属正常（E2 首次换代前无换代）"
                 " — 不装数不造档"),
        "current_split_fingerprint": cur_split,
        "split_change": ("★ 第二触发源已激活（裁决① HCE: 拆, R117 执行轮）: "
                         "拆分前档进 deprecated_by_split_change, "
                         "不物理删（版本化）"),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", default=os.path.join(ROOT, "archive"))
    ap.add_argument("--out", default=os.path.join(ROOT, "docs",
                                                  "dep_scan.json"))
    args = ap.parse_args()
    fp = judge_fingerprint(JUDGE_PATH)
    # ★ 换代判决 = E2 对拍的 regime_change 记录（不存在/未换代 ⇒ False）
    duel_path = os.path.join(ROOT, "docs", "challenger_duel.json")
    regime = False
    if os.path.exists(duel_path):
        regime = bool(json.load(open(duel_path, encoding="utf-8"))
                      .get("regime_change_happened"))
    rep = scan(args.archive, fp, split_fingerprint(ROOT),
               regime_change=regime)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1)
    print("judge fp:", fp, "| 分栏:", rep["counts"])
    print("写出:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
