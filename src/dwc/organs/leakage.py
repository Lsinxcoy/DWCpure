# -*- coding: utf-8 -*-
"""leakage · 泄漏筛查（2609.24972 RRSI 第 0 步 · 必须在任何评估之前）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 服务门组的**第 0 步**: 候选 diff 在进评估前先过泄漏筛查 —— 否则
    "a leaking candidate never receives the inflated evolve-set score
    that could make it attractive to subsequent rounds"（原文: 泄漏候选
    会拿到虚高的 evolve 集分数, 诱后续轮选它）。
  ★ 不抢位: 本模块只判**内容泄漏**（字面 benchmark-specific 编码）——
    不判正确性（judge）· 不判收益（非补偿门）· 不判通用性优劣（那是
    proposer/critic 的语义面)。

★★★ TRUTH_SOURCE（判据 G2）
  ★★ 与论文的差距（诚实边界, 逐条有据）:
    原文 Leakage Screening 是 **LLM critic**（Claude Opus 4.8）读 diff
    判断; 论文自陈 A4: "critic 能可靠识别 benchmark-specific 内容"
    是**未检验假设**（未报漏检率/误检率, critic 与 proposer 同厂商 ⇒
    自评偏置未检, cf. 2607.12790 共谋塌缩实证）。
    ⇒ DWC 用**托管/免费模型**时更不能假定同等判别力 ⇒ 本模块只做
      **机械可判的子集**（字面匹配 task/entity/answer 串的出现）,
      LLM critic 角色**显式 not_instrumented**（不假装有 — X2 纪律）。

=== 判据（2609.24972 L123 原文逐字, 取可机械化的部分）===
  拒绝: "edits that explicitly encode task names, entity names,
        task-specific values, answers, or other logic specific to the
        evolve benchmark"
  拒绝: "edits that add inert machinery"（惰机添加 — 无输入输出的空转件）
  保留: "generic prompt or tool-description improvements remain valid"
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

#: 泄漏类别（原文五类 + 惰机 — 值枚举, 不自创类别）
LEAK_KINDS: Tuple[str, ...] = ("task_name", "entity_name",
                               "task_specific_value", "answer", "inert_machinery")

#: 与 critic 角色对应的缺口标记
CRITIC_STATUS = "not_instrumented"


class LeakError(Exception):
    """筛查输入的显式拒绝（空 candidate/非法权重/口径越界）。"""


@dataclass(frozen=True)
class Candidate:
    """一个待筛查候选（diff 内容 + 其引用的 split 词汇表）。

    ★ candidate_id 非空; diff 非空字符串（空 diff 无可筛 — 显式拒）;
      task_names/entity_names/answers = benchmark 侧词表（调用方给,
        通常来自 anchors/split 真值源 — 本模块不猜词表内容）。
    """

    candidate_id: str
    diff: str
    task_names: Tuple[str, ...] = ()
    entity_names: Tuple[str, ...] = ()
    answers: Tuple[str, ...] = ()
    task_specific_values: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise LeakError("candidate_id 非空")
        if not isinstance(self.diff, str) or not self.diff.strip():
            raise LeakError(
                "diff 须非空（空 diff 没内容可筛 — 不是'干净')")


@dataclass(frozen=True)
class LeakHit:
    """一处字面命中（类别 + 词 + 上下文片段 — 可审计, 可复核）。"""

    kind: str
    term: str
    context: str


@dataclass
class ScreenResult:
    """筛查结论（rejected ⇒ 该候选不许进评估 — 门属性: 一票否决）。"""

    candidate_id: str
    allowed: bool
    hits: List[LeakHit] = field(default_factory=list)
    inert_machinery: bool = False
    critic: str = CRITIC_STATUS

    def as_dict(self) -> Dict[str, Any]:
        return {"candidate_id": self.candidate_id, "allowed": self.allowed,
                "n_hits": len(self.hits),
                "hits": [{"kind": h.kind, "term": h.term,
                          "context": (h.context[:80] + "…"
                                      if len(h.context) > 80
                                      else h.context)}
                         for h in self.hits],
                "inert_machinery": self.inert_machinery,
                "critic_role": self.critic,
                "note": ("allowed 只表示机械子集未命中 + 惰机检查未触发 — "
                         "**不等于语义干净**(LLM critic 未接, A4 缺口在档)")}


def _find_word(diff: str, term: str) -> int:
    """★ 词边界查找（防"retry 里的 t"这类子串误报 — 判据对齐原文
    "explicitly encode task names"的**显式编码**语义, 不是任意子串）。

    ★ 规则: term 两侧在 diff 中不是 ASCII 标识符字符 ⇒ 视为整词出现
      （允许引号/空白/标点贴边 — task name 通常以字符串字面量出现）。
    """
    start = 0
    while True:
        i = diff.find(term, start)
        if i < 0:
            return -1
        before = diff[i - 1] if i > 0 else ""
        after = diff[i + len(term)] if i + len(term) < len(diff) else ""
        def _idch(ch: str) -> bool:
            return bool(ch) and ch.isascii() and (ch.isalnum() or ch == "_")
        if not _idch(before) and not _idch(after):
            return i
        start = i + 1


def _hit(kind: str, term: str, diff: str) -> LeakHit:
    i = _find_word(diff, term)
    lo = max(0, i - 30)
    return LeakHit(kind=kind, term=term, context=diff[lo:i + len(term) + 30])


def screen_candidate(c: Candidate, *, inert_probe: bool = True
                     ) -> ScreenResult:
    """★ 字面筛查（五类词表 + 惰机启发式）。

    ★ 判定: 任一类词表词出现在 diff 正文 ⇒ 该类别 hit ⇒ allowed=False
      （**一票否决** — 非补偿门同族: 泄漏不可以用"别的方面好"补偿）。
    ★ inert_machinery 启发式（原文拒"edits that add inert machinery" —
    可机械化的弱 proxy）: diff 非空但**去除空白/标点后全是注释与字符串
    字面量**（无标识符/运算符）⇒ 视为惰机嫌疑（标记, 不进 allowed 决策
    的硬否决 — 启发式误报代价高, 如实降级为标记 + caveat）。
    """
    if not isinstance(c, Candidate):
        raise LeakError("screen_candidate 要 Candidate, 实 %r"
                        % (type(c).__name__,))
    hits: List[LeakHit] = []
    for kind, vocab in (("task_name", c.task_names),
                        ("entity_name", c.entity_names),
                        ("answer", c.answers),
                        ("task_specific_value", c.task_specific_values)):
        for term in vocab:
            if term and _find_word(c.diff, term) >= 0:
                hits.append(_hit(kind, term, c.diff))

    inert = False
    if inert_probe:
        # 弱 proxy: 去掉空白与标点后, 剩余字符里**没有任何 ASCII 字母/
        # 数字/下划线**（即没有一处可执行 token — 纯注释+字符串字面量）
        # ⇒ 视为 inert machinery 嫌疑。中文注释当然不算可执行 token,
        #    所以判据只看 ASCII 标识符字符（python token 的最小面）。
        body = "".join(ch for ch in c.diff
                       if not ch.isspace() and ch not in "(){}[]<>=+-*/.,:;\"'")
        inert = bool(body) and not any(
            (ch.isascii() and (ch.isalnum() or ch == "_")) for ch in body)

    allowed = not hits                  # 惰机只标记不否决（见 docstring）
    return ScreenResult(candidate_id=c.candidate_id, allowed=allowed,
                        hits=hits, inert_machinery=inert)


def screen_batch(cands: Iterable[Candidate]) -> Dict[str, Any]:
    """批量筛查 + 汇总（顺序保序 — 评估按候选序进, 不许悄悄换序）。"""
    results = [screen_candidate(c) for c in cands]
    rejected = [r.candidate_id for r in results if not r.allowed]
    return {"results": [r.as_dict() for r in results],
            "n": len(results), "n_rejected": len(rejected),
            "rejected": rejected,
            "critic_role": CRITIC_STATUS,
            "note": ("第 0 步语义: 被拒候选**不进评估**（不拿 inflated "
                     "evolve 分数去诱后续轮 — 原文前置理由）")}


LEAKAGE: Dict[str, str] = {
    "order": "RRSI 第 0 步 — 必须在任何评估之前（顺序不可换）",
    "paper_criteria": "拒: task names/entity names/task-specific values/answers/benchmark-specific logic; 拒: inert machinery; 留: generic 改进",
    "dwc_subset": "只做字面五类词表匹配（机械可判）+ 惰机弱 proxy（只标记不否决）",
    "critic_gap": ("LLM critic 角色 not_instrumented — 原文 A4 假设未检验"
                   "（自评偏置; DWC 无同级模型条件）⇒ allowed≠语义干净"),
    "veto": "一票否决（非补偿同族 — 泄漏不可被别的项补偿）",
}
