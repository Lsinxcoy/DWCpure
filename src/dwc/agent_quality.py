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

import hashlib
import json
import os
import re
import sys
import time
from typing import Any, Dict, List

from dwc.foundation.paths import find_root
ROOT = find_root()
VAR = os.path.join(ROOT, "var")
LESSONS = os.path.join(VAR, "dwc_lessons.jsonl")
# ★ R266B · 任务知识（信源/论文/发现）检索 — lessons 同族管线
SOURCES = os.path.join(VAR, "dwc_sources.jsonl")


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


def memory_snapshot_hash() -> str:
    """★ R269-④ · 记忆快照（md5 <lessons 字节><skills 文件名排序>）。

    跑批 summary 存它，"哪次记忆赢的"可归因。文件缺席记 "empty" 不炸。
    """
    if not os.path.exists(LESSONS):
        return "empty"
    h = hashlib.md5()
    with open(LESSONS, "rb") as fh:
        h.update(fh.read())
    names: list = []
    if os.path.isdir(SKILLS_DIR):
        for f in sorted(os.listdir(SKILLS_DIR)):
            names.append(f)
    h.update("\n".join(names).encode("utf-8"))
    return h.hexdigest()[:16]


def lesson_contrast(task_id: str) -> bool:
    """★ R234 · 调整C 落点: 该任务的教训有无「成败对照」。

    对照源（按强度序）: ① predictor 台账 bench:{task_id} 键成+败都有
    ② 世界树组键 — 同 group 下谱系有成有败（读树, predictor 树族口径）。
    只见过失败的教训可能是噪声; 有对照 ⇒ 信息量高（incumbent.py contrast
    同构）。读取失败静默降级 False（对照是排序加分项, 不是门）。"""
    try:
        from dwc.organs.predictor import OutcomePredictor
        r = OutcomePredictor().predict("bench:" + str(task_id))
        # ★ Layer 22 判据校准: p̂∈(0,1) 在 Laplace 平滑下恒真（无信息量）——
        #   真对照 = 两侧都有**先验外**观测: succ>0 且 fail>0。
        #   还原: p=(1+succ)/(2+n) ⇒ succ=p·(n+2)−1; fail=n−succ。
        n, pp = r["n"], r["p"]
        succ = pp * (n + 2) - 1
        return bool(succ > 1e-9 and (n - succ) > 1e-9)
    except Exception:                        # noqa: BLE001 — 加分项不许拖垮检索
        return False


def recall_lessons(task: str, k: int = 3) -> List[Dict[str, Any]]:
    """★ 接单检索: 任务文本 token 重叠打分 top-k（历史失败教训优先）。
    ★ R234: 同 overlap 分下 contrast（有成败对照）优先 —— 强证据先注入。"""
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
    def _contrast(tid):
        try:
            return lesson_contrast(tid)
        except Exception:                    # noqa: BLE001 — 加分项绝不炸检索
            return False
    scored.sort(key=lambda x: (-x[0],            # 主键: overlap 降序
                               not _contrast(x[1].get("task_id", ""))))
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
        if os.path.exists(path):
            # ★ R258: 已修订的规矩不覆盖（修订版由 outcome 驱动, 更优 —
            #   ReHarness §3.3: 修订是 forward-write 的上游）
            continue
        ex = [l for l in load_lessons() if l.get("fail_mode") == mode][:3]
        # ★ R258 ③: 修订示范注入（消融 0.217→0.191 — 新规矩写法向修订对看齐）
        _demo_note = ""
        _demo_p = os.path.join(SKILLS_DIR, "_revision_demo.md")
        if os.path.exists(_demo_p):
            try:
                _demo_note = ("\n修订示范（写规矩时参考 — 有条件加限定, "
                              "过时改写）:\n"
                              + open(_demo_p, encoding="utf-8").read()[:400])
            except OSError as exc:
                sys.stderr.write("demo 读取失败: %s\n" % exc)
        body = ("# 规矩（%s 教训 ×%d 固化）\n\n%s\n%s\n\n例证:\n%s\n" % (
            mode, n, _TEMPLATES.get(mode, "同类失败已多次发生, 更谨慎规划。"),
            _demo_note,
            "\n".join("- %s: %s" % (e.get("task_id"), e.get("detail"))
                       for e in ex)))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
        made[mode] = n
    return made


def revision_lessons(task: str, *, status: str, fail_why: str = "",
                     llm: Any = None) -> Dict[str, Any]:
    """★ R258 · 规矩文件的后向修订（ReHarness 2610.12668 §3.2 — 文件轨）。

    ★ diagnostic gate（§6 poker 教训）: status ∉ {done, failed} ⇒ 跳过
      —— incomplete/超时是噪声反馈, 不修订。
    ★ 修订对象 = dwc_skills/{fail_mode}.md（规矩 = 可修订的解读）;
      lessons JSONL 事件流**不动**（失败是事实 — R104 同族纪律）。
    ★ 版本链: 旧版存 dwc_skills/.hist/{mode}.{ts}.md（可回滚）。
    ★ ③ demo 环: 修订对写 _revision_demo.md — consolidate_skills 固化新
      规矩时读它当示范（ReHarness 消融: 修订做 forward-write demo
      0.217→0.191 的证据）。
    """
    if status not in ("done", "failed"):
        return {"revised": [], "skipped": "nondiagnostic"}
    if llm is None:
        return {"revised": [], "skipped": "no_llm"}
    hits = recall_lessons(task, 2)
    revised: List[str] = []
    for h in hits:
        fm = str(h.get("fail_mode") or "").strip()
        sp = os.path.join(SKILLS_DIR, "%s.md" % fm) if fm else ""
        if not sp or not os.path.exists(sp):
            continue
        try:
            old_txt = open(sp, encoding="utf-8").read()
        except OSError:
            continue
        prompt = (
            "固化规矩曾用于任务。按结局**修订**它（有条件加限定, 过时改写; "
            "不许编造新要求）。\n任务: %s\n结局: %s\n%s\n"
            "原规矩:\n%s\n\n只输出修订后的规矩全文（≤200字）。"
            % (task[:300], status,
               ("失败原因: " + fail_why[:200]) if fail_why else "", old_txt[:600]))
        try:
            r = llm.complete(prompt)
            new_txt = (r.text or "").strip() if getattr(r, "ok", False) else ""
        except Exception as exc:                # noqa: BLE001 — 修订失败不阻断
            sys.stderr.write("lesson_revise LLM 失败: %s\n" % exc)
            continue
        if not new_txt or new_txt == old_txt or len(new_txt) > 1200:
            continue
        hist = os.path.join(SKILLS_DIR, ".hist")
        os.makedirs(hist, exist_ok=True)
        ts = time.strftime("%m%d_%H%M%S")
        with open(os.path.join(hist, "%s.%s.md" % (fm, ts)), "w",
                  encoding="utf-8") as fh:      # 版本链: 旧版存档
            fh.write(old_txt)
        body = ("> 修订于 %s（任务%s）\n\n%s\n" % (ts, status, new_txt))
        with open(sp, "w", encoding="utf-8") as fh:
            fh.write(body)
        # ★ ③ demo 环（最近 2 条修订对 — 固化新规矩时读）
        try:                                   # ★ ③ demo 环（G7: 失败计数）
            demo_p = os.path.join(SKILLS_DIR, "_revision_demo.md")
            line = "- [%s] 旧: %s… → 新: %s…（任务%s）" % (
                fm, old_txt.replace("\n", " ")[:80],
                new_txt.replace("\n", " ")[:80], status)
            prev = []
            if os.path.exists(demo_p):
                prev = [l for l in open(demo_p, encoding="utf-8").read()
                        .splitlines() if l.startswith("- ")]
            body = "最近修订示范:\n" + "\n".join(([line] + prev)[:2])
            with open(demo_p, "w", encoding="utf-8") as fh:
                fh.write(body + "\n")
        except OSError as exc:
            sys.stderr.write("revision demo 落盘失败: %s\n" % exc)
        revised.append(fm)
    return {"revised": revised, "skipped": None}


def lessons_context(task: str, k: int = 3) -> str:
    """★ 注入用文本块: 检索到的教训 + 已固化技能 → 上下文（零命中零开销）。"""
    hits = recall_lessons(task, k)
    lines = []
    fails = [h for h in hits
             if not str(h.get("fail_mode", "")).startswith(
                 "success_pattern")]
    wins = [h for h in hits
            if str(h.get("fail_mode", "")).startswith("success_pattern")]
    if fails:
        lines.append("历史教训（同类任务曾失败, 请规避）:")
        lines.extend("- [%s] %s" % (h.get("fail_mode"), h.get("detail"))
                     for h in fails[:k])
    if wins:
        lines.append("历史成功做法（可复用）:")
        lines.extend("- [%s] %s" % (h.get("task_id"), h.get("detail"))
                     for h in wins[:k])
    # ★ 技能注入: 检索命中的 fail_mode 若已固化 ⇒ 规矩全文注入
    modes = {h.get("fail_mode") for h in hits}
    if os.path.isdir(SKILLS_DIR):
        for m in modes:
            sp = os.path.join(SKILLS_DIR, "%s.md" % m)
            if os.path.exists(sp):
                lines.append("已固化规矩（务必遵守）: "
                             + open(sp, encoding="utf-8").read()[:500])
    return "\n".join(lines)


# ═══ R266B · 任务知识（信源/知识/论文）检索注入 ══════════════════
# 用户 2026-10-14: "任务执行的记忆包括搜索到的信源/知识/论文是驱动系统
# 进化的重要组成部分" — A 层沉淀, 本层检索; lessons 同款 _tokens overlap。

def load_sources() -> List[Dict[str, Any]]:
    if not os.path.exists(SOURCES):
        return []
    out = []
    for ln in open(SOURCES, encoding="utf-8").read().splitlines():
        ln = ln.strip()
        if ln:
            try:
                out.append(json.loads(ln))
            except (ValueError, TypeError):
                continue
    return out


def recall_sources(task: str, k: int = 3) -> List[Dict[str, Any]]:
    """★ 接单检索: 任务文本 vs 历史任务/queries/urls/findings 重叠 top-k。"""
    qt = set(_tokens(task))
    if not qt:
        return []
    scored = []
    for rec in load_sources():
        hay = " ".join([str(rec.get("task", "")),
                        " ".join(str(q) for q in rec.get("queries", [])),
                        " ".join(u.get("url", "") for u in rec.get("urls", [])),
                        str(rec.get("findings", ""))])
        overlap = len(qt & set(_tokens(hay)))
        if overlap:
            scored.append((overlap, rec))
    scored.sort(key=lambda x: -x[0])
    return [x[1] for x in scored[:k]]


def sources_context(task: str, k: int = 3) -> str:
    """★ 注入用文本块: 此前任务找到的相关信源+发现（零命中零开销）。"""
    hits = recall_sources(task, k)
    if not hits:
        return ""
    lines = ["历史任务找到的相关材料（可复用, 不必重搜）:"]
    for r in hits[:k]:
        for u in (r.get("urls") or [])[:3]:
            lines.append("- [%s] %s" % (u.get("kind", "doc"), u.get("url", "")))
        if r.get("queries"):
            lines.append("  检索词: %s" % " / ".join(r["queries"][:3]))
        if r.get("findings"):
            lines.append("  发现: %s" % str(r["findings"])[:260])
    return "\n".join(lines)[:2500]
