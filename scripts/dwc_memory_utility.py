# -*- coding: utf-8 -*-
"""R270-⑦ · 效用学习 MemPO（Nexus mempo.py 思想，规则版，休眠上线）。

被 recall 命中且下游 ok → utility＋0.1（上限 1.0）；全局 nightly ×0.99
衰减。下游 ok 归因：与 recall 同口径（任务文本 overlap 命中的 lesson
共享该单 ok，不发明新归因）。数据不足（use>0 行 <20）readiness 关门，
只写字段不参与决策。
"""
from __future__ import annotations

import io
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

from dwc.agent_quality import LESSONS as _DEFAULT_LESSONS  # noqa: E402

LESSONS_PATH = _DEFAULT_LESSONS
READY_MIN_ROWS = 20


def _tokens(s: str) -> set:
    return set(str(s or "").replace("，", " ").replace(",", " ").split())


def update_utility(eval_rows: list, lessons_path: str = LESSONS_PATH,
                   decay: float = 0.99) -> dict:
    """一轮效用更新 → {"updated": n, "path": ...}。纯文件操作，零 LLM。"""
    if not os.path.exists(lessons_path):
        return {"updated": 0, "path": lessons_path}
    rows = []
    for ln in io.open(lessons_path, encoding="utf-8").read().splitlines():
        if ln.strip():
            try:
                rows.append(json.loads(ln))
            except ValueError:
                pass
    n = 0
    for row in rows:
        qt = _tokens(row.get("task", ""))
        hit_ok = False
        for ev in eval_rows:
            if not ev.get("ok"):
                continue
            if qt and qt & _tokens(ev.get("task", "")):
                hit_ok = True
                break
        u = float(row.get("utility", 0.5) or 0.5)
        if hit_ok:
            u = min(1.0, u + 0.1)
            n += 1
        row["utility"] = round(u * decay, 4)
    tmp = lessons_path + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    os.replace(tmp, lessons_path)
    return {"updated": n, "path": lessons_path}


def readiness(lessons_path: str = LESSONS_PATH) -> tuple:
    """数据够开效用决策吗？use_count>0 的行 ≥20 才 True。"""
    if not os.path.exists(lessons_path):
        return (False, "无 lessons 文件")
    k = 0
    for ln in io.open(lessons_path, encoding="utf-8").read().splitlines():
        if not ln.strip():
            continue
        try:
            if int(json.loads(ln).get("use_count", 0) or 0) > 0:
                k += 1
        except ValueError:
            pass
    if k >= READY_MIN_ROWS:
        return (True, "use>0 行 %d≥%d" % (k, READY_MIN_ROWS))
    return (False, "use>0 行仅 %d（需≥%d，继续积累）" % (k, READY_MIN_ROWS))


def main() -> int:
    ok, why = readiness()
    print("utility readiness: %s（%s）" % (ok, why))
    if not ok:
        print("休眠：只写字段，不参与决策")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
