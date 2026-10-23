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
# ★ R438 · 尊重 DWC_VAR_DIR（与 agent_rpc 同口径）。
#   现场：本模块写死 <repo>/var ⇒ 测试里每个任务都去读**生产** 1205 条教训
#   并 touch 改写它（既拖慢全量 4 倍，又污染生产 use_count）。
VAR = os.environ.get("DWC_VAR_DIR") or os.path.join(ROOT, "var")
LESSONS = os.path.join(VAR, "dwc_lessons.jsonl")
LESSONS_ARCHIVE = os.path.join(VAR, "dwc_lessons_archive.jsonl")
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
                  detail: str, gate: bool = True) -> None:
    quality = 0.5
    if gate:  # ★ R270-③ · 写门（drop 只计数写 stderr，不落盘）
        try:
            hist = [r.get("detail", "") for r in load_lessons()
                    if r.get("fail_mode") == fail_mode]
            scored = score_lesson_quality(str(detail), hist)
            quality = scored["quality"]
            if scored["verdict"] == "drop":
                sys.stderr.write("lesson 门 drop [%s] %s\n"
                                 % (fail_mode, str(detail)[:60]))
                return
        except Exception:                            # noqa: BLE001
            pass  # 门自坏不阻断记录
    os.makedirs(VAR, exist_ok=True)
    with open(LESSONS, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(
            {"at": time.strftime("%Y-%m-%dT%H:%M:%S+08:00"),
             "task_id": task_id, "fail_mode": fail_mode,
             "task": str(task)[:200], "detail": str(detail)[:300],
             "gen": 213, "use_count": 0, "last_used": "",
             "utility": 0.5, "tier": "short", "quality": quality},
            ensure_ascii=False) + "\n")


def _trigrams(text: str) -> set:
    if len(text) < 3:
        return {text} if text else set()
    return {text[i:i + 3] for i in range(len(text) - 2)}


_EVIDENCE_WORDS = ("verdict=", "answer contains", "rc=", "status=",
                   "0x", ".py", "EMU", "http")


def score_lesson_quality(detail: str, history: list) -> dict:
    """★ R270-③ · 写门四因子（母巢 knowledge_scorer 同款思想，DWC 口径）。

    format=动作句＋长度；factuality=证据词三档；consistency=1−trigram
    最大相似；realism=建议长度。verdict∈pass/review/drop。
    """
    text = str(detail or "").strip()
    if not text:
        return {"factors": {"format": 0.0, "factuality": 0.0,
                            "consistency": 0.0, "realism": 0.0},
                "quality": 0.0, "verdict": "drop"}
    f_format = (0.4 if len(text) >= 8 else 0.0) \
        + (0.3 if len(text) <= 300 else 0.0) \
        + (0.3 if any(s in text for s in ("。", ".", "：", ":")) else 0.0)
    low = text.lower()
    if any(w.lower() in low for w in _EVIDENCE_WORDS):
        f_fact = 1.0
    elif "http" in low or "见" in text or "据" in text:
        f_fact = 0.8
    else:
        f_fact = 0.5
    cur = _trigrams(text)
    max_sim = 0.0
    for h in (history or []):
        prev = _trigrams(str(h or ""))
        if prev and cur and (cur | prev):
            max_sim = max(max_sim, len(cur & prev) / len(cur | prev))
    f_cons = round(1.0 - max_sim, 4)
    f_real = 1.0 if len(text) >= 10 else (0.6 if len(text) >= 4 else 0.0)
    q = round((f_format + f_fact + f_cons + f_real) / 4.0, 4)
    # ★ 去重与计数并存：纯重复（cons==0）但底子可用 ⇒ review 留行
    #   （重复出现本身是"被纠 N 次"的固化信号 — SKILL_MIN 靠它计数）；
    #   底子也差 ⇒ drop。
    q_base = round((f_format + f_fact + f_real) / 3.0, 4)
    if q >= 0.6:
        verdict = "pass"
    elif q >= 0.4 or (f_cons == 0.0 and q_base >= 0.4):
        verdict = "review"
    else:
        verdict = "drop"
    return {"factors": {"format": f_format, "factuality": f_fact,
                        "consistency": f_cons, "realism": f_real},
            "quality": q, "verdict": verdict}


#: ★ R438 · 教训表 mtime 缓存（sources_context 现在每单都读 ⇒ 1205 行
#   重复解析会成为任务路径的热点；文件被 touch_lessons 改写 ⇒ mtime 变 ⇒ 重读）
_LESSONS_CACHE: Dict[str, Any] = {"key": None, "rows": []}


def load_lessons() -> List[Dict[str, Any]]:
    try:
        _st = os.stat(LESSONS)
        _key = (LESSONS, _st.st_mtime, _st.st_size)
    except OSError:
        _LESSONS_CACHE["key"] = None
        _LESSONS_CACHE["rows"] = []
        return []
    if _LESSONS_CACHE.get("key") == _key:
        return list(_LESSONS_CACHE["rows"])
    out = []
    for ln in open(LESSONS, encoding="utf-8").read().splitlines():
        if ln.strip():
            try:
                row = json.loads(ln)
            except Exception:                  # noqa: BLE001
                continue
            # ★ R270-① · 旧行兼容：缺席字段补默认
            row.setdefault("use_count", 0)
            row.setdefault("last_used", "")
            row.setdefault("utility", 0.5)
            row.setdefault("tier", "short")
            row.setdefault("quality", 0.5)
            out.append(row)
    _LESSONS_CACHE["key"] = _key
    _LESSONS_CACHE["rows"] = out
    return list(out)


def touch_lessons(ids: list) -> int:
    """★ R270-① · 命中即 touch（母巢 facade 同款语义）。

    use_count+1、last_used=now，原子写回；返回 touch 数。
    不存在的 id 忽略不炸。
    """
    if not os.path.exists(LESSONS):
        return 0
    try:
        lines = open(LESSONS, encoding="utf-8").read().splitlines()
    except OSError:
        return 0
    want = set(str(i) for i in (ids or []))
    n = 0
    now = time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    out = []
    for ln in lines:
        if ln.strip():
            try:
                row = json.loads(ln)
            except Exception:                  # noqa: BLE001
                out.append(ln)
                continue
            if str(row.get("task_id")) in want:
                row["use_count"] = int(row.get("use_count", 0) or 0) + 1
                row["last_used"] = now
                n += 1
                ln = json.dumps(row, ensure_ascii=False)
        out.append(ln)
    if not n:
        return 0
    tmp = LESSONS + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write("\n".join(out) + "\n")
        os.replace(tmp, LESSONS)
    except OSError:
        return 0
    return n


def _rewrite_lessons(rows: list) -> bool:
    """原子写回全表（晋升/归档/效用共用）。"""
    tmp = LESSONS + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        os.replace(tmp, LESSONS)
    except OSError:
        return False
    return True


def promote_lessons(use_threshold: int = 5) -> dict:
    """★ R270-② · 三层晋升（Protogonos 同款阈值）。

    use_count≥阈值 short→medium；同 fail_mode≥3 条给 long 提示
    （只提示不自动建 skill——建 skill 是进化面的事）。
    """
    rows = load_lessons()
    to_medium = 0
    for row in rows:
        if row.get("tier", "short") == "short" and int(
                row.get("use_count", 0) or 0) >= use_threshold:
            row["tier"] = "medium"
            to_medium += 1
    modes: dict = {}
    for row in rows:
        modes.setdefault(str(row.get("fail_mode", "?")), []).append(row)
    long_hints = sum(1 for items in modes.values() if len(items) >= 3)
    _rewrite_lessons(rows)
    return {"to_medium": to_medium, "long_hints": long_hints,
            "n": len(rows)}


def enforce_tier_capacity(short: int = 300, medium: int = 1000) -> int:
    """★ R270-② · 超容归档（末位移入 dwc_lessons_archive.jsonl）。

    short 层按 use_count 保前 N，其余进归档；medium 层同理。
    返回归档行数。
    """
    rows = load_lessons()
    keep: list = []
    arch: list = []
    for tier, cap in (("short", short), ("medium", medium)):
        sub = [r for r in rows if r.get("tier", "short") == tier]
        # ★ R270-⑦ · 次级键 utility（主键 use_count 不动 — 排序冻结延续）
        sub.sort(key=lambda r: (-int(r.get("use_count", 0) or 0),
                                -float(r.get("utility", 0.5) or 0.5)))
        keep.extend(sub[:cap])
        arch.extend(sub[cap:])
    keep.extend(r for r in rows if r.get("tier") not in ("short", "medium"))
    if arch:
        try:
            os.makedirs(VAR, exist_ok=True)
            with open(LESSONS_ARCHIVE, "a", encoding="utf-8") as fh:
                for row in arch:
                    fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        except OSError:
            return 0
    _rewrite_lessons(keep)
    return len(arch)


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
    # ★ R438 · 层级权重：晋升过的教训（medium/long）同 overlap 下优先
    #   —— 这是 `promote_lessons()` 唯一有意义的消费点（否则晋升=白晋）
    _w = {"short": 1.0, "medium": 2.0, "long": 3.0}
    scored = []
    for les in load_lessons():
        lt = set(_tokens(les.get("task", ""))) | set(
            _tokens(les.get("fail_mode", "")))
        overlap = len(qt & lt)
        if overlap:
            scored.append((overlap * _w.get(str(les.get("tier", "short")),
                                            1.0), les))
    def _contrast(tid):
        try:
            return lesson_contrast(tid)
        except Exception:                    # noqa: BLE001 — 加分项绝不炸检索
            return False
    scored.sort(key=lambda x: (-x[0],            # 主键: overlap 降序
                               not _contrast(x[1].get("task_id", ""))))
    hits = [x[1] for x in scored[:k]]
    try:  # ★ R270-① · 命中即 touch（失败降级不阻断召回）
        touch_lessons([h.get("task_id") for h in hits])
    except Exception:                            # noqa: BLE001
        pass
    return hits


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


def chat_ctx(task, prev=None):
    """★ R274-① · 聊天记忆读口：上轮摘要＋lessons_context 合并。

    空库/坏文件 ⇒ 原样回 prev（聊天永不因记忆崩）。mode 口径：
    chat_fail 进规避段，success_pattern:chat 进成功做法段（见 lessons_context）。
    """
    try:
        lc = lessons_context(str(task))
    except Exception:                            # noqa: BLE001 — 读坏不炸
        return prev
    if lc:
        return (prev + "\n" + lc) if prev else lc
    return prev


def record_chat_outcome(task, rep):
    """★ R274-② · 聊天记忆写口：done→success_pattern:chat，其余→chat_fail。

    走 record_lesson 写门（垃圾进不来）；空答案直接返 "" 不记；
    任何异常 stderr 留痕返 ""（交互永不因记崩）。
    """
    try:
        rep = rep or {}
        if rep.get("status") == "done":
            mode = "success_pattern:chat"
            detail = str(rep.get("answer", "") or "").strip()
        else:
            mode = "chat_fail"
            detail = "%s | %s" % (rep.get("status", "?"),
                                  str(rep.get("why", ""))[:200])
        if not detail.strip():
            return ""
        record_lesson("chat", mode, str(task), detail)
        return mode
    except Exception as exc:                     # noqa: BLE001
        sys.stderr.write("chat 记忆写口跳过: %s\n" % exc)
        return ""


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


def _sources_off() -> bool:
    """★★★ R436 · A/B 期间关掉「任务记忆」注入。

    为什么必须关：`recall_sources` 按**任务文本词元重叠**召回历史发现，
    而 A/B 的两臂用的是**同一句任务原文** ⇒ stable 臂刚写下的 findings
    （含答案）会被 candidate 臂召回注入 —— **跨臂泄漏**，且方向恒定偏向
    后跑的那一臂。现场：探针任务的分析里直接出现「任务记忆已明确：…是
    一个并不存在的路由文件名 / 历史失败是因为答成了真实入口名」。

    开关：env `DWC_SOURCES=off`，或文件 `var/sources_off`（A/B 脚本按需
    创建/删除，无需重启 agent）。生产默认关不掉（两个都不设 = 正常注入）。
    """
    try:
        if (os.environ.get("DWC_SOURCES") or "").strip().lower() == "off":
            return True
        here = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))          # src/dwc/agent_quality.py
        # ★ R438 · 与 VAR 同源（改前算成 src/dwc/var，生产永远找不到开关）
        var = (os.environ.get("DWC_VAR_DIR") or "").strip() \
            or VAR
        return os.path.exists(os.path.join(var, "sources_off"))
    except Exception:
        return False


def sources_context(task: str, k: int = 3) -> str:
    """★ 注入用文本块: 此前任务找到的相关信源+发现（零命中零开销）。"""
    if _sources_off():
        return ""
    parts = []
    hits = recall_sources(task, k)
    if hits:
        lines = ["历史任务找到的相关材料（可复用, 不必重搜）:"]
        for r in hits[:k]:
            for u in (r.get("urls") or [])[:3]:
                lines.append("- [%s] %s" % (u.get("kind", "doc"),
                                            u.get("url", "")))
            if r.get("queries"):
                lines.append("  检索词: %s" % " / ".join(r["queries"][:3]))
            if r.get("findings"):
                lines.append("  发现: %s" % str(r["findings"])[:260])
        parts.append("\n".join(lines))
    # ★ R438 · 记忆维度：已晋升教训（medium/long）
    _lc = lessons_context(task, k=k)
    if _lc:
        parts.append(_lc)
    return "\n\n".join(parts)[:2500]
