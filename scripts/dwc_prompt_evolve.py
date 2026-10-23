# -*- coding: utf-8 -*-
"""prompt 维度的驱动层（R438 · 对象 #8）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）

★★★ 存在理由
  提示词维度改前是"三件套齐、无人开车"：
    · `dwc_prompt_candidate.py` 能出候选（v1 → v2）
    · `dwc_prompt_ab.py` 能跑 A/B 并判定 promote/reject
    · `prompts/manifest.json` 能晋升
  但**没有任何东西定时把这三步串起来** ⇒ 提示词永远停在 v1。

★★★ 闭环
  ① 从 `config/anchors/rules.json` 的**已学规则**取硬规则
     （学到的策略 = 下一版提示词的候选约束；这是"学到→说给模型听"的桥）
  ② 生成候选版本（candidate 脚本，自动 next_ver）
  ③ A/B（ab 脚本，stable vs candidate，同题对照）
  ④ 判定 promote ⇒ 调 ab 的 `--promote` 写 manifest（带 .bak）
  ⑤ 无论结果都落 `var/prompt_evo_ledger.jsonl`（可审计）

★ 纪律
  · 没有学到规则 ⇒ 明确 skipped（不生成空候选去烧 A/B）
  · A/B 基础设施故障 ⇒ 不晋升（ab 脚本已按"不计分母"处理，这里只认 verdict）
  · 晋升前 manifest 由 ab 脚本备份（.bak_<ts>），可回滚
"""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES_PATH = os.path.join(ROOT, "config", "anchors", "rules.json")
CAND_SCRIPT = os.path.join(ROOT, "scripts", "dwc_prompt_candidate.py")
AB_SCRIPT = os.path.join(ROOT, "scripts", "dwc_prompt_ab.py")
LEDGER = os.path.join(ROOT, "var", "prompt_evo_ledger.jsonl")


def rules_from_learned(path: str = "", max_rules: int = 3,
                       max_chars: int = 300) -> list:
    """已学规则 → 候选硬规则文本（按 component 优先 prompt/control_flow）。"""
    p = path or RULES_PATH
    if not os.path.isfile(p):
        return []
    try:
        with io.open(p, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as exc:
        sys.stderr.write("rules 读取失败: %r\n" % (exc,))
        return []
    rows = []
    for key, r in (data.get("learned") or {}).items():
        if not isinstance(r, dict):
            continue
        txt = (r.get("patch") or r.get("m") or "").strip()
        if not txt:
            continue
        comp = str(r.get("component") or "")
        rows.append((0 if comp in ("prompt", "control_flow") else 1, key, txt))
    rows.sort(key=lambda x: (x[0], x[1]))
    out = []
    for _, _, txt in rows[:max_rules]:
        out.append(txt[:max_chars])
    return out


def _newest_ab_report(name: str, candidate: str, out_dir: str = "") -> str:
    d = out_dir or os.path.join(ROOT, "var")
    if not os.path.isdir(d):
        return ""
    pre = "prompt_ab_%s_%s_" % (name, candidate)
    hits = [os.path.join(d, f) for f in os.listdir(d)
            if f.startswith(pre) and f.endswith(".json")]
    if not hits:
        return ""
    return max(hits, key=os.path.getmtime)


def _ver_from_stdout(out: str, name: str) -> str:
    """从 candidate 脚本输出里抠版本号（'已生成 prompts/task_exec.v2.md'）。"""
    import re
    m = re.search(r"prompts[/\\]%s\.(v\d+)\.md" % re.escape(name), out or "")
    return m.group(1) if m else ""


def evolve(name: str = "task_exec", rules=None, min_tasks: int = 6,
           min_wins: int = 2, promote: bool = True, dry_run: bool = False,
           runner=None, out_dir: str = "", ledger: str = "") -> dict:
    """跑一轮提示词进化。返回可审计报告（也写 ledger）。"""
    py = sys.executable
    rules = list(rules) if rules is not None else rules_from_learned()
    rep = {"ts": time.strftime("%Y%m%d_%H%M%S"), "name": name,
           "rules": rules, "candidate": "", "verdict": "", "wins": [],
           "losses": [], "promoted": False, "outcome": "", "cmds": []}
    if not rules:
        rep["outcome"] = "skipped"
        rep["why"] = "没有已学规则可转成提示词约束"
        _log(rep, ledger)
        return rep

    _run = runner or (lambda cmd, timeout: subprocess.run(
        cmd, capture_output=True, timeout=timeout))

    cmd1 = [py, CAND_SCRIPT, "--name", name]
    for r in rules:
        cmd1 += ["--rule", r]
    if dry_run:
        cmd1.append("--dry-run")
    rep["cmds"].append(cmd1)
    if dry_run:
        rep["outcome"] = "dry_run"
        _log(rep, ledger)
        return rep

    try:
        r1 = _run(cmd1, 300)
    except Exception as exc:  # noqa: BLE001 — 起不来就记账，不吞
        rep["outcome"] = "candidate_failed"
        rep["why"] = repr(exc)
        _log(rep, ledger)
        return rep
    out1 = (r1.stdout or b"").decode("utf-8", "replace")
    ver = _ver_from_stdout(out1, name)
    if getattr(r1, "returncode", 0) != 0 or not ver:
        rep["outcome"] = "candidate_failed"
        rep["why"] = (out1 + (r1.stderr or b"").decode("utf-8", "replace"))[-400:]
        _log(rep, ledger)
        return rep
    rep["candidate"] = ver

    cmd2 = [py, AB_SCRIPT, "--name", name, "--candidate", ver,
            "--min-tasks", str(int(min_tasks)),
            "--min-wins", str(int(min_wins))]
    if promote:
        cmd2.append("--promote")
    rep["cmds"].append(cmd2)
    try:
        r2 = _run(cmd2, 4 * 3600)
    except Exception as exc:  # noqa: BLE001
        rep["outcome"] = "ab_failed"
        rep["why"] = repr(exc)
        _log(rep, ledger)
        return rep
    rep["ab_rc"] = getattr(r2, "returncode", 0)

    jp = _newest_ab_report(name, ver, out_dir)
    if not jp:
        rep["outcome"] = "ab_no_report"
        rep["why"] = (r2.stdout or b"").decode("utf-8", "replace")[-400:]
        _log(rep, ledger)
        return rep
    with io.open(jp, encoding="utf-8") as f:
        ab = json.load(f)
    rep["verdict"] = ab.get("verdict", "")
    rep["wins"] = ab.get("wins", [])
    rep["losses"] = ab.get("losses", [])
    rep["ab_report"] = jp
    rep["promoted"] = bool(promote and rep["verdict"] == "promote")
    rep["outcome"] = "promoted" if rep["promoted"] else "kept_stable"
    _log(rep, ledger)
    return rep


def _log(rep: dict, ledger: str = "") -> None:
    p = ledger or LEDGER
    try:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with io.open(p, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(rep, ensure_ascii=False) + "\n")
    except OSError as exc:  # noqa: BLE001 — 台账坏了不掀轮，但必须留痕
        sys.stderr.write("prompt ledger 写入失败: %r\n" % (exc,))


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", default="task_exec")
    ap.add_argument("--rule", action="append", default=[])
    ap.add_argument("--from-learned", action="store_true",
                    help="从 rules.json 已学规则生成候选（默认）")
    ap.add_argument("--min-tasks", type=int, default=6)
    ap.add_argument("--min-wins", type=int, default=2)
    ap.add_argument("--no-promote", action="store_true",
                    help="只跑 A/B，不写 manifest")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    rules = list(a.rule) or rules_from_learned()
    rep = evolve(name=a.name, rules=rules, min_tasks=a.min_tasks,
                 min_wins=a.min_wins, promote=not a.no_promote,
                 dry_run=a.dry_run)
    print(json.dumps(rep, ensure_ascii=False, indent=1))
    return 0 if rep.get("outcome") not in ("candidate_failed", "ab_failed") else 1


if __name__ == "__main__":
    sys.exit(main())
