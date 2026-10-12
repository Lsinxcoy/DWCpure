# -*- coding: utf-8 -*-
"""R213 · 任务质量回路（DWC 缺的执行引擎 — 用户 2026-10-12 诊断拍板）。

★★★ 定位（G1）: **DWC-AUTO** —— 任务执行经验的评估/沉淀/检索层。
★★ TRUTH_SOURCE: 无 —— 不产评分进 epoch; 只沉淀"失败模式+教训"供接单时
  注入上下文（judge 三分离兼容: 本层评"任务做得好不好", 不评"机制变更值不值"）。

★ 缺口根因（为什么建）: judge/anchor 管"变什么"不管"做得好不好"; 用户任务
  失败无沉淀 ⇒ 第 N+1 次重复同样错误。本层闭合: 失败 → 分类 → 落 lessons
  → 下次接单按任务文本检索注入（"被纠一次永久记住"的等价引擎）。
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, List

from dwc.foundation.paths import find_root
ROOT = find_root()
VAR = os.path.join(ROOT, "var")
LESSONS = os.path.join(VAR, "dwc_lessons.jsonl")


def _tokens(text: str) -> List[str]:
    """中英混排粗分词（2-gram 汉字 + 单词）—— 检索用, 不追求精度。"""
    text = (text or "").lower()
    toks = re.findall(r"[a-z_][a-z0-9_\.]*", text)
    han = re.findall(r"[\u4e00-\u9fff]{2,}", text)
    for h in han:
        toks.extend(h[i:i + 2] for i in range(len(h) - 1))
    return toks


def classify_fail(report: Dict[str, Any], passed) -> str:
    """失败模式分类（bench 与收件箱共用的判据表）。"""
    if passed:
        return "ok"
    status = report.get("status")
    if status == "incomplete" and "LLM 失败" in str(report.get("why", "")):
        return "llm_reject"
    if status == "incomplete" and "JSON" in str(report.get("why", "")):
        return "llm_format"
    if not report.get("artifacts") and status == "done":
        return "no_artifact"
    if status == "incomplete":
        return "exhausted"
    return "wrong_result"


def record_lesson(task_id: str, fail_mode: str, task: str,
                  detail: str) -> None:
    os.makedirs(VAR, exist_ok=True)
    with open(LESSONS, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(
            {"at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
             "task_id": task_id, "fail_mode": fail_mode,
             "task": str(task)[:200], "detail": str(detail)[:300],
             "gen": 213}, ensure_ascii=False) + "\n")


def load_lessons() -> List[Dict[str, Any]]:
    if not os.path.exists(LESSONS):
        return []
    out = []
    for ln in open(LESSONS, encoding="utf-8").read().splitlines():
        if ln.strip():
            try:
                out.append(json.loads(ln))
            except Exception:                  # noqa: BLE001
                pass
    return out


def recall_lessons(task: str, k: int = 3) -> List[Dict[str, Any]]:
    """★ 接单检索: 任务文本 token 重叠打分 top-k（历史失败教训优先）。"""
    qt = set(_tokens(task))
    if not qt:
        return []
    scored = []
    for les in load_lessons():
        lt = set(_tokens(les.get("task", ""))) | set(
            _tokens(les.get("fail_mode", "")))
        overlap = len(qt & lt)
        if overlap:
            scored.append((overlap, les))
    scored.sort(key=lambda x: -x[0])
    return [x[1] for x in scored[:k]]


#: R214 · 技能固化阈值: 同 fail_mode ≥ N 条教训 ⇒ 固化成规避技能
SKILL_MIN = 3
SKILLS_DIR = os.path.join(VAR, "dwc_skills")

#: 固化模板（判据表 — 每种失败模式的规避指令）
_TEMPLATES = {
    "exhausted": "轮数常在 6 轮内耗尽仍未 final ⇒ 精简步骤: 优先一次性"
                 " write 产物再 run 验证, 少探查; 信息不足时先 read 一个最"
                 "关键文件就够",
    "llm_format": "曾因响应非 JSON 被判失败 ⇒ 每轮务必只输出一个紧凑 JSON"
                  " 对象, 先想清参数再写, 避免 markdown 代码块包裹",
    "llm_reject": "LLM 通道曾瞬时拒绝 ⇒ 若第一轮失败, 简化任务为最小可完"
                  "成子步骤再试",
    "no_artifact": "宣称完成但产物缺失 ⇒ final 前必须确认 artifacts 里的文"
                   "件真实写出（write 成功后才 final）",
    "wrong_result": "产物内容曾判错 ⇒ 写产物前先 read 输入源文件取真值, 禁"
                    "止凭记忆/猜测编造输入数字",
}


def consolidate_skills() -> Dict[str, int]:
    """★ R214: 同 fail_mode 教训 ≥ SKILL_MIN 条 ⇒ 固化规避技能文件。
    （把"被纠 N 次"变成可注入的永久规矩 — 技能库本体）"""
    os.makedirs(SKILLS_DIR, exist_ok=True)
    from collections import Counter
    dist = Counter(l.get("fail_mode") for l in load_lessons()
                   if l.get("fail_mode") != "ok")
    made = {}
    for mode, n in dist.items():
        if n < SKILL_MIN:
            continue
        path = os.path.join(SKILLS_DIR, "%s.md" % mode)
        ex = [l for l in load_lessons() if l.get("fail_mode") == mode][:3]
        body = ("# 规矩（%s 教训 ×%d 固化）\n\n%s\n\n例证:\n%s\n" % (
            mode, n, _TEMPLATES.get(mode, "同类失败已多次发生, 更谨慎规划。"),
            "\n".join("- %s: %s" % (e.get("task_id"), e.get("detail"))
                       for e in ex)))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        made[mode] = n
    return made


def lessons_context(task: str, k: int = 3) -> str:
    """★ 注入用文本块: 检索到的教训 + 已固化技能 → 上下文（零命中零开销）。"""
    hits = recall_lessons(task, k)
    lines = []
    if hits:
        lines.append("历史教训（同类任务曾失败, 请规避）:")
        lines.extend("- [%s] %s" % (h.get("fail_mode"), h.get("detail"))
                     for h in hits[:k])
    # ★ 技能注入: 检索命中的 fail_mode 若已固化 ⇒ 规矩全文注入
    modes = {h.get("fail_mode") for h in hits}
    if os.path.isdir(SKILLS_DIR):
        for m in modes:
            sp = os.path.join(SKILLS_DIR, "%s.md" % m)
            if os.path.exists(sp):
                lines.append("已固化规矩（务必遵守）: "
                             + open(sp, encoding="utf-8").read()[:500])
    return "\n".join(lines)
