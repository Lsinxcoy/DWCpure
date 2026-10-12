# -*- coding: utf-8 -*-
"""R206 · 生产备份（P1-6: 备份/回滚为 0 → 真值源+db 定期快照）。

★ 备份对象: 真值源 config/anchors/(dev.json·broken_dev.json·epoch_ledger
  jsonl) + config/iron_laws.yaml + 生产库 var/dwc_prod.sqlite
★ 落点: var/backup/<YYYYmmdd_HHMMSS>/ · 保留最近 KEEP 份滚动
★ 契约: rc0 空 stdout（cron health=silence）; 任何对象缺失 ⇒ rc1+stderr
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

import os
import shutil
import sys
import time

REPO = _dwc_root()
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
