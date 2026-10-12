# -*- coding: utf-8 -*-
"""R206 · 生产备份（P1-6: 备份/回滚为 0 → 真值源+db 定期快照）。

★ 备份对象: 真值源 config/anchors/(dev.json·broken_dev.json·epoch_ledger
  jsonl) + config/iron_laws.yaml + 生产库 var/dwc_prod.sqlite
★ 落点: var/backup/<YYYYmmdd_HHMMSS>/ · 保留最近 KEEP 份滚动
★ 契约: rc0 空 stdout（cron health=silence）; 任何对象缺失 ⇒ rc1+stderr
★ CRON RUNS THE COPY: 仓库改完须同步 %LOCALAPPDATA%/hermes/scripts/。
"""
from __future__ import annotations

import os
import shutil
import sys
import time

REPO = r"E:/Divine Wisdom Core"
VAR = os.path.join(REPO, "var")
BACKUP = os.path.join(VAR, "backup")
KEEP = 7
#: (源绝对路径, 备份内相对名) — 真值源不可写, 只读拷贝
OBJECTS = [
    (os.path.join(REPO, "config", "anchors", "dev.json"), "anchors/dev.json"),
    (os.path.join(REPO, "config", "anchors", "broken_dev.json"),
     "anchors/broken_dev.json"),
    (os.path.join(REPO, "archive", "anchor_epochs.jsonl"),
     "anchors/anchor_epochs.jsonl"),   # ★ R198 归档位在 archive/ 不在 anchors/
    (os.path.join(REPO, "config", "iron_laws.yaml"), "iron_laws.yaml"),
    (os.path.join(VAR, "dwc_prod.sqlite"), "dwc_prod.sqlite"),
]


def main() -> int:
    ts = time.strftime("%Y%m%d_%H%M%S")
    dst = os.path.join(BACKUP, ts)
    missing = []
    for src, rel in OBJECTS:
        if not os.path.exists(src):
            missing.append(src)
            continue
        out = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        shutil.copy2(src, out)
    # 滚动: 只留最近 KEEP 份
    try:
        dirs = sorted(x for x in os.listdir(BACKUP)
                      if os.path.isdir(os.path.join(BACKUP, x)))
        for old in dirs[:-KEEP]:
            shutil.rmtree(os.path.join(BACKUP, old), ignore_errors=True)
    except Exception:                          # noqa: BLE001 — 滚动失败不挡备份
        pass
    if missing:
        print("备份对象缺失: %s" % missing, file=sys.stderr)
        return 1                               # 缺失要响（真值源丢了是大事）
    return 0


if __name__ == "__main__":
    sys.exit(main())
