"""R271 · 记忆看板纯函数（只读不判定 — G1 DWC-AUTO 用户界面层数据口）。

DWC-MEM(记忆底座)-可视化：lessons 分层/episodes 链/workflows 模板/
night 终态，全从 var/ JSONL 现场数出来。文件缺席记"—"不炸。
"""
from __future__ import annotations

import json
import os
import sys

from dwc.foundation.paths import find_root

ROOT = find_root()
VAR = os.path.join(ROOT, "var")
LESSONS_PATH = os.path.join(VAR, "dwc_lessons.jsonl")
ARCHIVE_PATH = os.path.join(VAR, "dwc_lessons_archive.jsonl")
CURVE_PATH = os.path.join(VAR, "eval", "success_curve.jsonl")
EPISODES_PATH = os.path.join(VAR, "dwc_episodes.jsonl")
WORKFLOWS_PATH = os.path.join(VAR, "dwc_workflows.jsonl")


def _read(path: str) -> list:
    if not os.path.exists(path):
        return []
    out = []
    for ln in open(path, encoding="utf-8").read().splitlines():
        if ln.strip():
            try:
                out.append(json.loads(ln))
            except ValueError as exc:
                sys.stderr.write("memview 坏行跳过 [%s] %s\n" % (path, exc))
    return out


def lessons_panel(path: str | None = None,
                  archive: str | None = None) -> str:
    """★ lessons 分层看板：三层计数＋top5＋quality 均值＋效用门。"""
    rows = _read(path or LESSONS_PATH)
    if not rows:
        return "── 记忆 lessons ──\n—（无数据）"
    tiers: dict = {}
    for r in rows:
        tiers[r.get("tier", "short")] = tiers.get(
            r.get("tier", "short"), 0) + 1
    top = sorted(rows, key=lambda r: -int(r.get("use_count", 0) or 0))[:5]
    q = [float(r.get("quality", 0.5) or 0.5) for r in rows]
    n_arch = len(_read(archive or ARCHIVE_PATH))
    n_used = sum(1 for r in rows if int(r.get("use_count", 0) or 0) > 0)
    lines = ["── 记忆 lessons（%d 行·归档 %d）──" % (len(rows), n_arch),
             "分层 short %d · medium %d · long %d" % (
                 tiers.get("short", 0), tiers.get("medium", 0),
                 tiers.get("long", 0)),
             "quality 均值 %.2f" % (sum(q) / len(q)),
             "多用 top5： " + " / ".join(
                 "%s×%s(%s)" % (r.get("task_id"), r.get("use_count", 0),
                                r.get("tier", "short")) for r in top),
             "效用门：%s（use>0 行 %d/20）" % (
                 "激活" if n_used >= 20 else "休眠", n_used)]
    return "\n".join(lines)


def episode_panel(task_id: str | None = None,
                  path: str | None = None) -> str:
    """★ episode 链看板：无参看最近 3 链尾巴；有参看全链（复用 BFS）。"""
    if task_id is not None and not isinstance(task_id, str):
        raise TypeError("task_id 须为 str（实收 %s）" % type(task_id).__name__)
    rows = _read(path or EPISODES_PATH)
    if not rows:
        return "── episode 链 ──\n暂无数据"
    if task_id:
        try:
            _scripts = os.path.join(ROOT, "scripts")
            if _scripts not in sys.path:
                sys.path.insert(0, _scripts)
            import dwc_episodes as _EP
            chain = _EP.related(task_id, 2, path=(path or EPISODES_PATH))
        except Exception as exc:                 # noqa: BLE001
            return "── episode 链 ──\n查询失败：%s" % exc
        if not chain:
            return "── episode 链 ──\n无此任务"
        shape = "→".join("✓" if r.get("ok") else "✗" for r in chain)
        return "── episode 链（%s）──\n%s\n%s" % (
            task_id, shape,
            " / ".join(str(r.get("task_id")) for r in chain))
    tails: dict = {}
    for r in rows:
        tails[r.get("kind", "?")] = r
    lines = ["── episode 链（最近 %d 链）──" % min(3, len(tails))]
    for kind in sorted(tails)[-3:]:
        sub = [r for r in rows if r.get("kind") == kind][-4:]
        shape = "→".join("✓" if r.get("ok") else "✗" for r in sub)
        lines.append("%s：%s" % (kind, shape))
    return "\n".join(lines)


def workflow_panel(path: str | None = None) -> str:
    """★ workflow 模板看板：name/kind/use/success；空库明示。"""
    rows = _read(path or WORKFLOWS_PATH)
    if not rows:
        return "── workflow 模板 ──\n暂无模板（planner 自动沉淀）"
    lines = ["── workflow 模板（%d 个）──" % len(rows)]
    for r in rows:
        lines.append("%s [%s] 用%d·胜率%.2f" % (
            r.get("name"), r.get("kind"), r.get("use_count", 0),
            float(r.get("success", 0.5) or 0.5)))
    return "\n".join(lines)


def sparkline(path: str | None = None, width: int = 24) -> str:
    """★ R272-⑤ · 成功率 sparkline（最近 width 单，✓▇/✗▁＋滚动成功率）。

    n<2 →"点太少"（诚实门）；缺 ok 键行跳过并注数。
    """
    rows = _read(path or CURVE_PATH)
    known = [r for r in rows if "ok" in r]
    skipped = len(rows) - len(known)
    if len(known) < 2:
        return "走势：点太少（n<2）"
    sub = known[-width:]
    bars = "".join("▇" if r.get("ok") else "▁" for r in sub)
    rate = round(sum(1 for r in sub if r.get("ok")) * 100 / len(sub))
    tail = "" if not skipped else "（跳过 %d 行）" % skipped
    return "走势：%s %d%%%s" % (bars, rate, tail)


def night_panel(path: str | None = None, limit: int = 8) -> str:
    """★ night 终态看板：DONE/FAIL/STALLED＋成功率＋早停。"""
    rows = _read(path or CURVE_PATH)
    if not rows:
        return "── 夜跑 nightbench ──\n暂无数据"
    terms: dict = {}
    for r in rows:
        terms[r.get("terminal", "?")] = terms.get(
            r.get("terminal", "?"), 0) + 1
    n_ok = sum(1 for r in rows if r.get("ok"))
    n_stop = sum(1 for r in rows if r.get("saturated_early_stop"))
    lines = ["── 夜跑 nightbench（%d 单）──" % len(rows),
             "DONE %d · FAIL %d · STALLED %d" % (
                 terms.get("DONE", 0), terms.get("FAIL", 0),
                 terms.get("STALLED", 0)),
             "成功率 %d%% · 早停 %d" % (
                 round(n_ok * 100 / len(rows)), n_stop),
             sparkline(path=path),
             "最近： " + " / ".join(
                 ("✓" if r.get("ok") else "✗") + str(r.get("tid", "?"))
                 for r in rows[-limit:])]
    return "\n".join(lines)
