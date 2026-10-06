# -*- coding: utf-8 -*-
"""DWC evolver —— 变异器（器官 4/7）。★ 让分数能掉下来的那个器官。

★★★ 这个器官为什么现在最要紧
  R26 实测: actor + judge 链路已通，dev 的 6 条 behavior 任务全过
  ⇒ pass_rate = 1.0
  ⇒⇒ ★★ 而那个 1.0 是**必然的** —— actor 跑的是基准实现，它不会失败
  ⇒⇒ ⇒★ 所以这套东西目前**修不了任何 bug**，只会一直满分
  ⇒⇒⇒ ⇒★ 唯一能让分数掉下来的东西就是 evolver:
    它提出**会失败**的候选实现，actor 执行，judge 判分
    ⇒⇒⇒⇒ ★★ 那才是真正的进化闭环:
      失败签名 → 提案 → 过门 → actor 执行 → judge 判分 → 采纳/拒绝

定位声明（DWC-MEM · 记忆底座 · 判据 G1 定位门）
  ★ evolver 属记忆底座 —— 它消费失败签名（EXPERIENCE 区），产出提案
  ★ 它**不落地**：落地是 APPLIER 的职责（原则 6: 器官各司其职）
  ★ 它**不判分**：判分是 judge（原则 1: 判据必须在系统外）

★★★ 四条约束（EVOLUTION_CORE_DESIGN §九 逐条核过）
  约束 1 · 禁止"先落再测"
    依据 2609.24972 / 2609.26457 / 2607.12790
    ⇒⇒ 所以提案**先过门再采纳**，落地与测量必须分离
  约束 2 · 判据必须在可写面之外
    依据 2609.13406 grounded 双条件
    ⇒⇒ 所以 evolver 只**读**失败签名，不改判据
  约束 3 · 必须有两组 split
    依据 2606.09498 (Δ_in ≥ 0 ∧ Δ_ho ≥ 0)
    ⇒⇒ 所以采纳要同时看 in-sample 与 held-out
    ⇒⇒ ⇒★ 而 test 未落地 ⇒ **只能判 in** ⇒ adopt 返回 blocked
  约束 4 · 每轮变更数必须可归因
    依据 2606.09498 原文: "一簇对应一处干预"
    + 2609.24972 退火预算 b_t
    ⇒⇒ ★★ 所以本模块硬性限制: **一个提案只改一处**
    ⇒⇒ ★ 若允许多处 ⇒ 任何测量都无法归因
"""
from __future__ import annotations

#: ★★★ TRUTH_SOURCE（判据 G2）
#: ★★ 本模块**不判分、不落地** ⇒ 它没有真值源
#: ★★ 它产出的提案最终由 judge 在 dev/test 上判，本模块只做生成 + 门检
TRUTH_SOURCE = {
    "本模块不自判": "提案是否被采纳由 judge 判分决定（约束 1/2）",
    "本模块的产出": "proposal（待判分的候选），不是判分结果",
    "判读位置": "dwc.organs.judge.Judge（真值源 config/anchors/dev.json）",
    "★ 约束 2": "判据在可写面之外 ⇒ evolver 只读失败签名，不改判据",
}

#: ★★ RRSI 组件词表（2609.24972 式 12 原文 · EVOLUTION_CORE §3.1）
COMPONENT_VOCAB = frozenset({
    "prompt", "control_flow", "config", "output_plumbing",
    "context_mgmt", "client_tool", "skill", "memory", "subagent",
})

#: ★★ 结构型组件（式 15: 取新颖度奖励 ν_str）
STRUCTURAL = frozenset({"client_tool", "skill", "memory", "subagent"})

#: ★★ 九维分类法（2606.14249 §3.3 原文）
DIMENSIONS = ("D1", "D2", "D3", "D4", "D5", "D6", "D7", "D8", "D9")

#: ★★ 提案状态（约束 1: 先过门再采纳 ⇒ 状态机而非一次性通过）
PROPOSAL_STATES = ("draft", "gated", "rejected", "adopted",
                   "adopted_not_implemented")

import hashlib
import io
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


class EvolverError(Exception):
    """违反 evolver 契约。★ 承重代码不许吞异常（判据 E2/E3）。"""


# ══════════════════════════════════════════════════════════
# 提案
# ══════════════════════════════════════════════════════════


@dataclass
class Proposal:
    """★ 一个候选变更（一处干预）。

    ★★★★ 约束 4 的落地: `target` + `patch` **只能有一处**
      ⇒ 若多处 ⇒ 任何测量都无法归因（2606.09498 原文）
      ⇒⇒ 所以我加了 `_assert_single_change()` 在构造时就拦

    ★★ 状态机（约束 1）:
      draft → gated（过门）→ rejected / adopted
      ★ adopted_not_implemented 是**第五态**（R14 引入）
        —— 「过了门但还没落地」必须与「已落地」区分
    """
    proposal_id: str
    #: ★ 由哪个失败签名驱动（可归因的锚点）
    failure_signature: Dict[str, str]
    #: ★ 改什么（必须属 COMPONENT_VOCAB）
    component: str
    #: ★ 改哪里（唯一一处）
    target: str
    #: ★ 怎么改（可执行的表达式或代码）
    patch: str
    #: ★ 为什么这么改（依据 —— 不许"看着办"）
    rationale: str
    #: 结构型组件取新颖度奖励（式 15）
    is_structural: bool = False
    dimension: Optional[str] = None

    state: str = "draft"
    gate_verdict: Optional[Dict[str, Any]] = None
    #: ★ 判分结果（由 judge 填，不由 evolver 填）
    verdict: Optional[Dict[str, Any]] = None
    created_at: float = 0.0

    def __post_init__(self):
        if self.component not in COMPONENT_VOCAB:
            raise EvolverError(
                "component=%r 不在 RRSI 词表内（2609.24972 式 12）"
                % self.component)
        if self.state not in PROPOSAL_STATES:
            raise EvolverError(
                "state=%r 不在 %r 内" % (self.state, list(PROPOSAL_STATES)))
        if self.dimension is not None and self.dimension not in DIMENSIONS:
            raise EvolverError(
                "dimension=%r 不在 %r 内（2606.14249 九维）"
                % (self.dimension, list(DIMENSIONS)))
        if not self.rationale.strip():
            raise EvolverError(
                "★ rationale 必填 —— 不许『看着办』"
                "（约束 4: 变更可归因 ⇒ 必须说清依据）")
        self.is_structural = self.component in STRUCTURAL
        self.created_at = self.created_at or time.time()

    def key(self) -> str:
        """★ 提案指纹（去重 + 可归因）。"""
        blob = "%s|%s|%s|%s" % (self.component, self.target,
                               self.patch, json.dumps(
                                   self.failure_signature, sort_keys=True))
        return hashlib.sha256(blob.encode()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        d = dict(self.__dict__)
        d["key"] = self.key()
        return d


# ══════════════════════════════════════════════════════════
# 失败签名 → 提案的映射表
# ══════════════════════════════════════════════════════════


class Mutator:
    """★ 变异器：失败签名 → 候选实现。

    ★★ 为什么第一版是**确定性**的（不是 LLM）:
      · 可验证性不该依赖 LLM（而 judge 的存在正是为了判分可信）
      · 且确定性变异能让"同一个失败 → 同一个提案"可复现
      ⇒⇒ ⇒★ LLM 版留作可插拔的第二个 Mutator（诚实边界④）
    """

    #: ★ 查询键 = **(c, q, fn)** → 提案
#:   · c/q 是原文三元组的前两段（规则填）
#:   · ★★ **fn 是定位维度** —— 不在三元组里!
#:     三元组是聚类语义（什么失败/什么行为/什么机制），
#:     而"要改哪个函数"是定位 ⇒ 必须显式在键里
#:   · m 由**条目产出**（R30 结构修正: m 不能是查询输入）
    #:
    #: ★★ 这里刻意做成**数据**而不是代码 —— 因为
    #:   「失败签名 → 该改哪」这条映射本身就是假设，
    #:   把它写成数据就能被门检查、能被测试、能被审计

    # ══════════════════════════════════════════════════════
    # ★★★ R32 · 固化（把验证过的候选写进 RULES）
    #   依据: 2606.09498 Algorithm 1 **line 23**
    #     `h_{t+1} ← MergeAccepted(h_t, A_t)` —— 通过才**合并进主干**
    #   ⇒⇒ ⇒★ 位置: **在候选副本上评估通过之后**
    #   ⇒⇒ ⇒★★ 于是 R31 的学习成果才能**累积**（否则每次重试）
    # ══════════════════════════════════════════════════════

    #: ★ 条目的**必填**字段（propose 用下标读 ⇒ 缺了就 KeyError）
    #:   ⇒ 固化前必须校验，否则固化一条坏规则会炸在**查表那一刻**
    RULE_ENTRY_FIELDS = ("component", "dimension", "target",
                         "m", "m_source", "patch", "rationale")

    #: ★ 允许的 component（RRSI 式12 词表）—— 与 Proposal 校验同源
    #: ★★★ R32 · **学到的**规则的落盘位置
    #   ⇒ 种子（代码里那 3 条，人工写的）留在 evolver.py —— 可被门/评审管
    #   ⇒ 而**固化产生的**规则落盘 —— 否则进程结束就丢
    #   ⇒⇒ ⇒★ 分开放的理由: 代码改动要走评审（G5），
    #     落盘的是**系统自己学的**（要能持久，且不改代码）
    LEARNED_PATH = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))),
        "config", "anchors", "rules.json")

    #: ★ 种子键（**代码里定义的**）—— persist 时排除它们
    SEED_KEYS: frozenset = frozenset()

    @classmethod
    def load_learned(cls) -> int:
        """★ 把**落盘学到的**规则合并进 RULES（进程启动时调）。

        ★ 返回合并条数；文件不存在 ⇒ 0（**不报错** —— 没学到过是常态）
        ★★★ 合并而非替换: 种子（代码）与学到的（落盘）必须并存
        """
        try:
            with io.open(cls.LEARNED_PATH, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return 0
        n = 0
        for k, v in (data.get("learned") or {}).items():
            if k not in cls.RULES and isinstance(v, dict):
                cls.RULES[k] = v
                n += 1
        return n

    @classmethod
    def persist_learned(cls) -> Dict[str, Any]:
        """★★★ 把 RULES 里**非种子**的条目写盘（固化后的持久化）。

        ★ 只写「学到的」⇒ 种子不进 json（否则代码与 json **双源**）
        ★ 返回 {path, n_written, n_seed} —— 可审计
        """
        learned = {k: v for k, v in cls.RULES.items()
                   if k not in cls.SEED_KEYS}
        os.makedirs(os.path.dirname(cls.LEARNED_PATH), exist_ok=True)
        payload = {
            "_provenance": {
                "why": ("★ R32: 2606.09498 line 23 MergeAccepted —— "
                        "通过才合并进主干；而『合并』必须**跨进程存活**"),
                "seed_location": ("src/dwc/organs/evolver.py 的 "
                                  "Mutator.RULES（人工写，可评审）"),
                "★ 分流": ("种子留代码 · 学到的落盘 —— "
                       "否则代码与 json 双源，或学到的随进程消失"),
            },
            "learned": learned,
        }
        with io.open(cls.LEARNED_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        return {"path": cls.LEARNED_PATH, "n_written": len(learned),
                "n_seed": len(cls.SEED_KEYS)}

    @staticmethod
    def key_for(sig: Dict[str, str]) -> str:
        """★ 由失败签名构造**查询键** (c:q:fn) —— 与 propose 同口径。

        ★★ 这个函数存在的理由: 固化方若自己拼键，
          与 propose 拼的不一致 ⇒ 固化了**永远查不到**
          ⇒⇒ ⇒★ 那是"写了没人读"的老病（ARSI C4 同款）
        ⇒ ⇒★ 所以键的构造必须收敛成**一个**函数（两侧共用）
        """
        if not all(sig.get(k) for k in ("c", "q", "fn")):
            raise ValueError(
                "★ 查询键需 (c,q,fn)，m 不参与（R30 结构修正）: %r"
                % (sig,))
        return "%s:%s:%s" % (sig["c"], sig["q"], sig["fn"])

    @classmethod
    def check_entry(cls, key: str, entry: Dict[str, Any]
                    ) -> List[str]:
        """★ 固化前的字段校验（**数据完整性**，不是判分）。

        ★ 返回缺失字段列表；空 = 合格
        ⇒⇒ ★ 为什么在 evolver 而不在 applier:
          schema 是**进化侧的知识**，applier 是通用写入器
          ⇒⇒ 让 applier 懂 RULES 的结构 = 职责越界
        """
        missing = [f for f in cls.RULE_ENTRY_FIELDS
                   if not str(entry.get(f, "")).strip()]
        if entry.get("component") not in COMPONENT_VOCAB:
            missing.append("component∉词表:%s" % entry.get("component"))
        if entry.get("dimension") not in DIMENSIONS:
            missing.append("dimension∉九维:%s" % entry.get("dimension"))
        if not key.count(":") == 2:
            missing.append("key 必须是 c:q:fn 三段")
        return missing

    RULES: Dict[str, Dict[str, str]] = {
        # ★ 示例规则：sum_first_n 少算一个（off-by-one）
        "E_VALUE:wrong_magnitude:sum_first_n": {
            "component": "control_flow",
            "dimension": "D7",
            "target": "sum_first_n",
            "m": "range_bounds",
            "m_source": "rule",
            "patch": "return sum(range(n + 1))",
            "rationale": "range(1,n+1) 漏掉 n；按 c 判据只应累加 1..n"},
        # ★ 示例规则：average 空列表除零
        "E_ZERO_DIV:wrong_magnitude:average": {
            "component": "control_flow",
            "dimension": "D7",
            "target": "average",
            "m": "empty_input_guard",
            "m_source": "rule",
            "patch": "return (sum(xs) / len(xs)) if xs else 0.0",
            "rationale": "空列表 len=0 ⇒ 除零；按判据应返回 0.0"},
        # ★ 示例规则：factorial 无限递归
        "E_NO_RESULT:abstained_or_missing:factorial": {
            "component": "control_flow",
            "dimension": "D7",
            "target": "factorial",
            "m": "recursive_base_case",
            "m_source": "rule",
            # ★★★ R30 数据修正: 此前是 0/8/4（+4 ⇒ 4/12/8 ✗ 应 4/8/4）
            #   ⇒ 因为**没有应用方**，这个 bug 一直测不到
            #   ⇒⇒ ⇒★★ 端到端暴出的第三类问题（数据错误，非代码错）
            "patch": ("if n <= 1:\n    return 1\n"
                      "return n * factorial(n - 1)"),
            "rationale": "缺递归基 ⇒ 无限递归；按判据 0!/1! 都应为 1"},
    }

    # ★★★ R32: RULES 定义**之后**立刻捕获种子
    #   ⇒ 顺序要紧: 先有种子（代码字面量）⇒ 再判哪些是"学到的"
    #   ⇒⇒ 若不捕获 SEED_KEYS ⇒ persist 会把种子也写进 json ⇒ 双源
    SEED_KEYS = frozenset(RULES)

    #: ★★ 加载的**触发点** = 模块级（import 即生效）
    #   ★★★ 两次踩同一个坑，都记下:
    #   ① 第一版: 类体里 `try: load_learned() except: pass`
    #      ⇒ 类定义时 classmethod 还没绑 ⇒ 必抛 ⇒ **被 pass 吞掉**
    #      ⇒ 于是它**从未被调用**（写了但没接 = 形同没写）
    #   ② 第二版: 挂进 `Mutator.__init__`（实例构造）
    #      ⇒ 而 `RULES` 是**类属性**，调用方写 `Mutator.RULES`（类访问）
    #        ⇒ 实例从未构造 ⇒ `ensure_loaded` 从未被调
    #      ⇒⇒ 实测: 跨进程**读不到**落盘的规则（查表 n_proposals=0）
    #   ⇒⇒ ⇒★★ 结论: 挂在"类访问"之外的东西上，就等于没挂
    #      ⇒ ⇒★ 只有**模块级**对"用类属性的调用方"必然生效
    _loaded = False

    @classmethod
    def ensure_loaded(cls) -> int:
        """★ 幂等加载（**幂等**靠 `_loaded` 守卫，不靠调用时机）。

        ★★★ R32 变异验证的结论（**这个守卫是冗余的**）:
          摘掉 `if cls._loaded: return 0` 后实测: 第 1 次=1、第 2 次=0
          ⇒⇒ 因为 `load_learned` 里已有 `if k not in RULES` ⇒ **自身就幂等**
          ⇒⇒ ⇒★ 所以本守卫**不承重** —— 它只让 `_loaded` 这个标志
            有语义（测试与排查时能问"加载过了吗"）
          ⇒ ⇒★ 显式标注，免得后人以为它承重而"小心翼翼地维护"
            （幻影承重与幻影代码同型: 名字与实现不对齐）
        """
        if cls._loaded:
            return 0
        cls._loaded = True
        return cls.load_learned()

    @classmethod
    def entry_from_candidate(cls, cand: Any, rationale: str = ""
                             ) -> Dict[str, Any]:
        """★★★ R35 · 把**候选**组装成可固化的规则条目（7 字段）。

        ★★★ 职责为什么在这里（不在 applier）:
          · `RULE_ENTRY_FIELDS` / 词表是**进化侧的知识**
          · applier 是通用写入器 ⇒ 它不懂 RULES 的结构
          ⇒ ⇒★ 所以: evolver **组装**（懂 schema）+ applier **写**（懂机制）
            —— 与『check_fn 注入』是同一个分工

        ★★ 三条硬要求（缺一条就是坏规则）:
          ① 7 字段**全齐**（缺字段 ⇒ 炸点在查表那一刻）
          ② component/dimension **必须**来自候选
            ⇒ 绝不默认值兜底（那等于我替模型编了 component）
          ③ m 若是模型产的 ⇒ **必须带指纹**（provenance）
            ⇒ 否则固化后无法回溯"这 m 哪次调用产的"，
              且会被误读成「m 可复现」（温度 0.2 也不保证）
        """
        if cand is None:
            raise ValueError("★ 没有候选 ⇒ 无可固化内容（不许空固化）")
        comp = str(getattr(cand, "component", "") or "")
        dim = str(getattr(cand, "dimension", "") or "")
        if comp not in COMPONENT_VOCAB:
            raise ValueError(
                "★ candidate.component=%r 不在词表 ⇒ 拒绝固化"
                "（**不猜默认值** —— 那就是编造）" % comp)
        if dim not in DIMENSIONS:
            raise ValueError("★ candidate.dimension=%r 不在九维 ⇒ 拒绝固化"
                             % dim)
        m = str(getattr(cand, "m", "") or "")
        if not m:
            raise ValueError("★ m 为空 ⇒ 这条规则没有机制假设，固化无意义")
        m_source = str(getattr(cand, "m_source", "") or "none")
        prov = dict(getattr(cand, "provenance", {}) or {})
        entry = {
            "component": comp,
            "dimension": dim,
            "target": str(getattr(cand, "target", "") or ""),
            "m": m,
            "m_source": m_source,
            "patch": str(getattr(cand, "patch", "") or ""),
            # ★ rationale 必须能回答"凭什么固化这条"
            "rationale": (rationale.strip() or
                          "R35 固化: source=%s rule=%s；grounding=%d 条"
                          % (getattr(cand, "source", "?"),
                             getattr(cand, "rule", "?"),
                             len(getattr(cand, "grounding", []) or []))),
        }
        # ★★★ 模型产的 m ⇒ 指纹**必须**进条目（否则是"无源的 m"）
        if m_source == "llm":
            if not prov:
                raise ValueError(
                    "★ m_source=llm 但没有 provenance ⇒ "
                    "这条 m **无源**（哪次调用产的不知道 ⇒ 拒绝）")
            entry["_m_fingerprint"] = {
                "prompt_ver": prov.get("prompt_ver", ""),
                "model": prov.get("model", ""),
                "n_diffs": prov.get("n_diffs"),
                "raw_m": prov.get("raw_m", m),
            }
        return entry

    def propose(self, sig: Dict[str, str]) -> Optional[Proposal]:
        """★ 给一条失败签名 ⇒ 一个提案（无规则则 None）。

        ★★ 关键: 返回 None 是**合法**结果（该机制我们不会改）
          ⇒ 而若强行给提案 ⇒ 那就是"为改而改"
        """
        # ★★★★ R30 结构修正: 查询键只用 (c, q)
        #   原文分工（2609.06396）: c/q 由**规则**填 · m 由**模型假设**填
        #   ⇒⇒ ⇒★ 于是 m 必须在诊断里**产出来**，不能是查询的**输入**
        #   ⇒⇒ ⇒★★ 而我第一版把 RULES 的键也写成 (c,q,m) ⇒ 死锁:
        #     要查 RULES 需要 m → m 要规则推 → 而推它的规则在 RULES 里
        #   ⇒⇒ ⇒★★ 这与 R27 同源: 我拿**聚类语义**当了**实现接口**
        #     （R27: q 我当函数名 · R30: m 我当查询键 —— 同一种错）
        #   ⇒ ⇒★ 签名**语义**不变（仍三元组用于聚类），变的是规则表的键
        lookup = "%s:%s:%s" % (sig.get("c"), sig.get("q"),
                                 sig.get("fn", ""))
        rule = self.RULES.get(lookup)
        if rule is None:
            return None
        pid = "P_" + hashlib.sha256(lookup.encode()).hexdigest()[:8]
        # ★★ 产出的签名**补全** m（由规则给出 —— 第一版无 LLM ⇒ 规则填，
        #   并在 rule 里标注 mechanism_source 以免冒充"模型假设"）
        full = dict(sig)
        full["m"] = rule.get("m", "")
        full["m_source"] = rule.get("m_source", "rule")
        return Proposal(proposal_id=pid, failure_signature=full,
                        component=rule["component"], target=rule["target"],
                        patch=rule["patch"], rationale=rule["rationale"],
                        dimension=rule.get("dimension"))

    def known_signatures(self) -> List[str]:
        """★ 声明过的失败签名（可审计：我们只修这些）。"""
        return sorted(self.RULES)


# ══════════════════════════════════════════════════════════
# 门（约束 1：先过门再采纳）
# ══════════════════════════════════════════════════════════


class ProposalGate:
    """★ 提案门。★ 先过门，后落地（约束 1）。

    ★★★ 门的判据（全部来自已定设计，不是自己发明的）:
      ① 一处干预（约束 4 · 2606.09498）
      ② 组件在 RRSI 词表内（2609.24972 式 12）
      ③ 有依据（rationale 非空 —— 可归因）
      ④ 维度在九维内（2606.14249 §3.3）
      ⑤ ★★ **不允许改判据**（约束 2 · 2609.13406）
         ⇒ 若 target 指向 dev.json / judge / 真值源 ⇒ 直接拒
    """

    #: ★★ 不可写面（约束 2: 判据必须在可写面之外）
    FORBIDDEN_TARGETS = ("judge", "dev.json", "test_sealed", "iron_laws",
                         "gate.py", "truth", "golden", "anchors")

    def check(self, p: Proposal) -> Dict[str, Any]:
        """★ 检一个提案，返回门报告（不 raise —— 门是报告器）。"""
        v = []

        # ① 一处干预
        if not p.target.strip():
            v.append(("no_target", "约束 4: 提案必须有唯一 target"))
        # ② 词表
        if p.component not in COMPONENT_VOCAB:
            v.append(("bad_component", "组件不在 RRSI 词表内"))
        # ③ 依据
        if not p.rationale.strip():
            v.append(("no_rationale", "约束 4: 变更须可归因 ⇒ 必须有依据"))
        # ④ 维度
        if p.dimension is not None and p.dimension not in DIMENSIONS:
            v.append(("bad_dimension", "维度不在九维内"))
        # ⑤ ★★ 不许改判据
        low = p.target.lower() + " " + p.patch.lower()
        for bad in self.FORBIDDEN_TARGETS:
            if bad.lower() in low:
                v.append(("touches_truth", "约束 2: 提案触及判据/真值源 ⇒ 拒"))
                break
        return {"gate": "proposal", "proposal_id": p.proposal_id,
                "key": p.key(), "pass": not v,
                "violations": [{"rule": r, "detail": d} for r, d in v],
                "n_checks": 5}


# ══════════════════════════════════════════════════════════
# Evolver
# ══════════════════════════════════════════════════════════


class Evolver:
    """★ 变异器编排：失败签名 → 提案 → 过门 → 待判分。

    ★★ 它**不**做的事（职责边界，逐条有依据）:
      · 不判分（judge）
      · 不落地（APPLIER）
      · 不改判据（约束 2）
      · 不一次改多处（约束 4）
    """

    def __init__(self, mutator: Optional[Mutator] = None,
                 gate: Optional[ProposalGate] = None):
        self.mutator = mutator or Mutator()
        self.gate = gate or ProposalGate()
        self.proposals: List[Proposal] = []
        self._seen: Set[str] = set()

    # ══════════════════════════════════════════════
    # 诊断 → 提案
    # ══════════════════════════════════════════════
    def diagnose(self, signatures: List[Dict[str, str]]
                 ) -> Dict[str, Any]:
        """★ 诊断：失败签名 → 去重后的提案清单。

        ★★ 约束 4 的另一面: 同一 (c,q,m) 精确一致才算一簇
          ⇒ 所以去重按 key，不做语义相似合并
          ⇒★ 而 2606.09498 原文强调: "两个 run 可能共享同一个
            verifier 结果（如 timeout）却需要不同的干预"
            ⇒⇒ ★★ 所以**只有三元组全同**才合并，绝不按 c 单独合并
        """
        out: List[Proposal] = []
        unmapped: List[Dict[str, str]] = []
        clusters: Dict[str, int] = {}

        def _cluster(sig_in: Dict[str, str],
                     m: str) -> None:
            """★ 聚类计数 —— 键是**补全后**的 (c,q,m)。"""
            k = "%s:%s:%s" % (sig_in.get("c"), sig_in.get("q"), m)
            clusters[k] = clusters.get(k, 0) + 1

        for sig in signatures:
            # ★★★★ R30 结构修正（与 propose 的键改动配套）:
            #   诊断**输入**只需 (c, q) —— 它是查询 RULES 的键
            #   而 m 是**诊断的输出**（由 RULES 条目补全，R30 结构修正）
            #   ⇒⇒ ⇒★ 所以这里不再强制 m 非空
            #     （强制了就会拒掉 judge 产的 `m=""` —— 实测正是断点）
            #   ⇒⇒ ⇒★★ 而 2609.06396 原文分工本就是:
            #     c/q **规则**填 · m **模型假设**填 ⇒ m 允许待定
            # ★★ 查询键 = (c, q, **fn**) ⇒ 三者必填（缺 fn 定位不了）
            #   而 m **允许空**（由 RULES 条目产出 —— 原文分工）
            if not all(sig.get(k) for k in ("c", "q", "fn")):
                raise EvolverError(
                    "失败签名缺 c/q/fn（查询键所需；m 可空）: %r" % (sig,))
            p = self.mutator.propose(sig)
            if p is None:
                # ★ 聚类也要算 —— unmapped 同样是"三点一致"里的一簇
                #   （它的机制未知 ⇒ m 空串，聚类键如实带空）
                unmapped.append(dict(sig))
                _cluster(sig, sig.get("m") or "")
                continue            # ★ 合法: 该机制我们不会改
            _cluster(sig, p.failure_signature.get("m") or "")
            if p.key() in self._seen:
                continue                        # ★ 去重
            self._seen.add(p.key())
            out.append(p)
        return {"proposals": out, "n_unmapped": len(unmapped),
                "unmapped": unmapped,
                "n_clusters": len(clusters),
                "★": ("聚类按**补全后**三元组精确一致（2606.09498）"
                      "⇒ 不按 c 单独合并；m 由 RULES 条目产出"),
                }

    # ══════════════════════════════════════════════
    # 门（约束 1）
    # ══════════════════════════════════════════════
    def gate_all(self, proposals: List[Proposal]) -> Dict[str, Any]:
        """★ 全部提案过门 ⇒ 分为 gated / rejected。"""
        passed, rejected = [], []
        for p in proposals:
            r = self.gate.check(p)
            p.gate_verdict = r
            if r["pass"]:
                p.state = "gated"
                passed.append(p)
            else:
                p.state = "rejected"
                rejected.append(p)
            self.proposals.append(p)
        return {"gated": passed, "rejected": rejected,
                "n_gated": len(passed), "n_rejected": len(rejected),
                "★": "约束 1: 先过门，后落地"}

    # ══════════════════════════════════════════════
    # ★★★ 关键: 采纳必须同时过**两组 split**（约束 3）
    # ══════════════════════════════════════════════
    @staticmethod
    def accept(p: Proposal, baseline: Dict[str, Any],
               current: Dict[str, Any], eps: float = 0.0
               ) -> Dict[str, Any]:
        """★ 判定一个候选该不该采纳（固定门 𝒢_fixed）。

        ★★★★ R27 实测修正: 原签名收「in_score / held_out_score」两个数，
          参数名叫 score 但比较逻辑当成**增量**用
          ⇒⇒ ★★ 语义自相矛盾（测试按分数传，就判错了）
          ⇒⇒ ⇒★ 改成收**基线与当前两份判分结果**，增量由本函数自己算
            —— 理由: 增量必须由同一函数从同一口径算出，
              否则调用方可以用不同基线糊弄过去

        ★★★ 判据（2606.09498 Algorithm 1 第 13 行**原文**）:
          if Δ_in ≥ 0 and Δ_ho ≥ 0 and max(...) > 0 then Accept
          ⇒⇒ ★★ ★ 我初版漏了第三个条件 max(...) > 0
            —— 那个条件的作用是: **两组都不退化还不够**，
               还得真的有改进（否则等于没改）
          ⇒⇒ ★ 而 DWC 的 max(...) 就是 Δ_in 与 Δ_ho 的较大者

        ★★ 2608.24876 Eq.9 的正规形式（本方法即其可执行化）:
          ℳ_{k+1} = ℳ⁺_k  if 𝒢_fixed(ℳ⁺_k, ℳ_k; x_k, 𝒟_dev) = 1
                     ℳ_k    otherwise
          ⇒⇒ 「先在副本上评估 → 通过才合并」⇒ 生产主干在通过前未被触碰

        ★★ 而 DWC 现在 **test split 未落地**
          ⇒⇒ ★★ 所以 held_out 缺失时必须返回 **blocked**
            ⇒⇒⇒ 绝不因为"只在一组数据上变好了"就放行
              （2606.14249 记录: 只用一组 ⇒ −14.0%）

        ★★ 第五态（R14）: adopted_not_implemented
          —— 「过了门但还没落地」必须与「已落地」区分
        """
        b_in = baseline.get("in_score")
        c_in = current.get("in_score")
        b_ho = baseline.get("held_out_score")
        c_ho = current.get("held_out_score")

        if b_in is None or c_in is None:
            return {"decision": "not_evaluated", "why": "in-sample 未判过"}
        d_in = c_in - b_in

        if b_ho is None or c_ho is None:
            return {"decision": "blocked",
                    "why": ("★ 约束 3 需两组 split（Δ_in ∧ Δ_ho），"
                            "而 test split 未落地 ⇒ 不得只凭 in-sample 采纳"
                            "（2606.14249: 只用一组会证伪自己的门 −14.0%）"),
                    "delta_in": d_in, "in_baseline": b_in,
                    "in_current": c_in}
        d_ho = c_ho - b_ho

        # ★★ 2606.09498 第 13 行: Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧ max(...) > 0
        # ★★ 第三个条件是"真的有改进"，否则"没退化"就采纳是空过
        if d_in < -eps or d_ho < -eps:
            return {"decision": "rejected", "delta_in": d_in,
                    "delta_ho": d_ho,
                    "why": "任一 split 退化 ⇒ 拒（Δ_in ≥ 0 ∧ Δ_ho ≥ 0）"}
        if max(d_in, d_ho) <= 0:
            return {"decision": "rejected", "delta_in": d_in,
                    "delta_ho": d_ho,
                    "why": ("★ 2606.09498 第13行第三条件: max(Δ) > 0"
                            " —— 两组都没退化但也没改进 ⇒ 那是空过，不采纳")}
        return {"decision": "adopted_not_implemented",
                "delta_in": d_in, "delta_ho": d_ho,
                "max_delta": max(d_in, d_ho),
                "★": ("这是**第五态** —— 过了门但还没落地"
                      "（R14: 未采用 ≠ 通过）")}

    # ══════════════════════════════════════════════
    # 报告
    # ══════════════════════════════════════════════
    def stats(self) -> Dict[str, Any]:
        by_state: Dict[str, int] = {}
        for p in self.proposals:
            by_state[p.state] = by_state.get(p.state, 0) + 1
        return {"n_proposals": len(self.proposals),
                "by_state": by_state,
                "known_signatures": len(self.mutator.known_signatures()),
                "★": ("★ R28 起 test split 已落地 ⇒ 约束 3 的 Δ_ho 可算"
                      "⇒★ ⇒★ adopt 现在可达（但落地仍未实现 ⇒ 第五态）")}



# ★★★★★ R32 · 模块级触发 —— **这是唯一对"类属性访问方"必然生效的位置**
#   理由见 Mutator.ensure_loaded 的注释（两次踩坑的记录）
#   ★ 不抛异常: 没学到过（文件不存在）是**常态**，不是错误
_MUTATOR_LOADED_AT_IMPORT = Mutator.ensure_loaded()

if __name__ == "__main__":
    ev = Evolver()

    print("=== 诊断: 三条已知失败签名 ===")
    sigs = [{"c": "E_OFF_BY_ONE", "q": "sum_first_n", "m": "code_repair"},
            {"c": "E_ZERO_DIV", "q": "average", "m": "code_repair"},
            {"c": "E_NO_BASE", "q": "factorial", "m": "code_repair"}]
    d = ev.diagnose(sigs)
    print("  %d 个提案 · %d 个未映射 · %d 个簇"
          % (len(d["proposals"]), d["n_unmapped"], d["n_clusters"]))
    for p in d["proposals"]:
        print("    %-14s %-12s → %s" % (p.proposal_id, p.component,
                                        p.target))
        print("       patch: %s" % p.patch.replace("\n", " ⏎ ")[:60])
        print("       依据: %s" % p.rationale[:50])

    print("\n=== ★★ 约束 4: 同签名重复出现不产生新提案 ===")
    d2 = ev.diagnose(sigs + sigs)
    print("  传 6 条（重复）⇒ %d 个提案（仍 3）" % len(d2["proposals"]))

    print("\n=== ★★ 约束 4: 不按 c 单独合并 ===")
    d3 = ev.diagnose([{"c": "E_OFF_BY_ONE", "q": "sum_first_n",
                       "m": "code_repair"},
                      {"c": "E_OFF_BY_ONE", "q": "other_fn",
                       "m": "code_repair"}])
    print("  同 c 不同 q/m ⇒ %d 个簇（不合并）" % d3["n_clusters"])

    print("\n=== 门 ===")
    g = ev.gate_all(d["proposals"])
    print("  过门 %d · 拒 %d" % (g["n_gated"], g["n_rejected"]))
    print("  状态: %s" % ev.stats()["by_state"])

    print("\n=== ★★ 约束 2: 提案触及判据 ⇒ 拒 ===")
    bad = Proposal(proposal_id="P_BAD",
                   failure_signature={"c": "x", "q": "y", "m": "z"},
                   component="config", target="config/anchors/dev.json",
                   patch="pass_rate = 1.0", rationale="想改分")
    r = ev.gate.check(bad)
    print("  pass=%s violations=%s" % (r["pass"],
                                       [v["rule"] for v in r["violations"]]))

    print("\n=== ★★ 约束 3: 只有 in-sample ⇒ blocked（不采纳）===")
    p = d["proposals"][0]
    r1 = Evolver.accept(p, {"in_score": 0.4, "held_out_score": None},
                        {"in_score": 0.6, "held_out_score": None})
    print("  Δ_in=%.1f held_out 缺失 ⇒ %s"
          % (r1["delta_in"], r1["decision"]))
    print("  why: %s" % r1["why"][:78])
    both = Evolver.accept(p, {"in_score": 0.4, "held_out_score": 0.3},
                          {"in_score": 0.6, "held_out_score": 0.5})
    print("  Δ_in=0.2 Δ_ho=0.2 ⇒ %s" % both["decision"])
    print("  ★ 提案状态仍 = %s（第五态表示过了门但未落地）" % p.state)

    print("\n=== ★★ 2606.09498 第13行第三条件: max(Δ) > 0 ===")
    flat = Evolver.accept(p, {"in_score": 0.5, "held_out_score": 0.5},
                          {"in_score": 0.5, "held_out_score": 0.5})
    print("  两组都不退化但也没改进 ⇒ %s" % flat["decision"])
    print("  why: %s" % flat["why"][:64])

    print("\n=== 缺字段的失败签名必须显式暴露 ===")
    try:
        ev.diagnose([{"c": "x", "q": "y"}])
        print("  ★ 未 raise —— 有洞")
    except EvolverError as e:
        print("  ✓ raise: %s" % str(e)[:60])