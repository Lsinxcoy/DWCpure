# -*- coding: utf-8 -*-
"""DWC applier —— 落地器（器官 5/7）。★ 把闭环最后一段接上。

★★★ 这个器官为什么现在最要紧（APPLIER_DESIGN §一 实测结论）
  四个项目里只有一个真正的落地器（母巢 GeneChampion），其余三个的形态是:
    ARSI  · 无落地器（evolver 明说 "Does not auto-edit core"）
           ⇒ 860 accepted → **2 applied**     ★ 这是实测
    Ultra · 无落地器（evolve 0 条）
    Nexus · 无落地器（8 行常量）
  ⇒⇒ ★★ 四项目**没有一个**把"提案能生成"变成"提案真的落地"
  ⇒⇒ ⇒★ 而 DWC 现在正好走到同一处断点:
    R27 实测: 失败签名 → 提案 → 过门 → 采纳判定 ⇒ 断了
    ⇒⇒ ⇒★★ ⇒★ 所以 APPLIER 是闭环的最后缺口

定位声明（DWC-MEM · 记忆底座 · 判据 G1 定位门）
  ★ applier 属记忆底座 —— 它把 gated 的提案应用到**可写面**
  ★ 它**不判分**（judge 判分）、**不生成提案**（evolver 生成）
  ★ ★★ 它是唯一写可写面的器官 ⇒ 所以"可读回/可回滚"全在这里强制

★★★ 三条判据（APPLIER_DESIGN §五 原文，逐条落地）
  判据 1 · 应用必须可读回（原则 4）
    ⇒ setattr 后读回，读回值 ≠ 候选值 ⇒ **报错，不许静默计成功**
       （★ 这治母巢 P0-3：返回 ok:True 但零副作用）
  判据 2 · 应用必须有回滚路径
    ⇒ 每次应用前存旧值；回退 = 写回 + **读回确认**
       ★ 而 ARSI 的 inverse_op 862/862 全非空 —— 这点 ARSI 做对了
  判据 3 · 应用必须有**窗口**（不是立即生效）
    ⇒ 母巢的窗口 = 5 tick；窗口末比对，不达标回退
       ★ 理由: 立即生效 = 无法判断"是它带来的改变吗"

★★★★ 落地顺序（2606.09498 Algorithm 1 原文伪代码，16 篇无一例外）
  line 9  h_t^(j) ← Δ_j(h_t)          ← 在**候选副本**上应用
  line 10 Evaluate(M, h_t^(j), ...)    ← 评估候选
  line 13 if Δ_in ≥ 0 ∧ Δ_ho ≥ 0 ∧ max(...) > 0
  line 15 Accept(Δ_j)
  line 23 h_{t+1} ← MergeAccepted(...) ← **最后才**合并进主干
  ⇒⇒ ★★ 生产主干在 line 23 之前未被触碰
  ⇒⇒ ★ 而母巢的影子方向相反（先 _apply 落生产 → 等 window → 才结算）

★★★ 母巢三次失败的修正（APPLIER_DESIGN §三 逐条核过）
  失败 1 · 结算时 base 打了**新配置**
    ⇒ `_base_metric = _m` 而 `_m` 此刻已是 challenger 的分
    ⇒ ⇒ gain = 自己减自己 = 0.0 ⇒ 100% 回退
    ⇒★ ⇒★ 本实现的修正: `settle()` 显式收 base 与 current
       且**要求 base 来自评估前的读取**（由 source 字段标注）
  失败 2 · `min_gain` 降门槛无效，因为 **scorer 是量化阶梯**
    ⇒ 同一台阶内 gain 恒 0 ⇒ 4/7 轮回退
    ⇒★ ⇒★ 本实现的修正: settle() 里先验**分辨率**
       —— 两个不同配置必须产出不同分，否则明确报 `no_resolution`
       ⇒⇒ ★★★ 分辨率是前提，门槛是调节（原文原话）
  失败 3 · 立即生效 ⇒ 无法归因
    ⇒★ ⇒★ 修正: 强制窗口（window）+ 窗口末比对

"""

from __future__ import annotations
import datetime
# ★★★ R44: 我加 `_record_liquidity` 时用了 os/io 却**没 import**
#   （同族第 5 次「用了没引」—— 前 4 次: evolver 的 os ×2、
#    os.path→os.join、applier 这次）
#   ⇒ ⇒★ 教训: 加函数时先 grep 它用的模块在不在 import 区
import io
import os
# ★★★★ TRUTH_SOURCE（判据 G2）
#   ★★ 本模块**不判分** ⇒ 它没有真值源
#   ★★ 它产出的是「是否落地 / 是否回滚」的状态，而**分数**由 judge 算
TRUTH_SOURCE = {
    "本模块不自判": "分数与采纳与否由 judge/evolver 决定；applier 只管写与读回",
    "本模块的产出": "AppliedResult（写入成功/读回校验/回滚记录），不是判分",
    "判读位置": "dwc.organs.judge.Judge（真值源 config/anchors/*.json）",
    "★ 分辨率前置": "若 scorer 无分辨率 ⇒ settle 报 no_resolution，不判胜负",
}

#: ★★ 消费点声明（APPLIER_DESIGN §4.2 · 比母巢多 verify 字段）
#:   母巢只有 consumer/path/attr，DWC 加 verify = 回读函数
TARGETS = {
    "mutation_rule": {
        "consumer": "evolver.Mutator.RULES 的一条变异规则",
        "path": "dwc.organs.evolver.Mutator.RULES",
        "attr": "<签名键>",            # 动态：目标规则的键
        "verify": "读回该键存在且 patch 一致",
        "★ 属可写面": True,
    },
}

#: ★★ 窗口长度（母巢 = 5 tick）
DEFAULT_WINDOW = 5

import copy
import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple


def _now() -> str:
    """★ 时间戳（可审计 —— 但**不承重**：判据不依赖它）。"""
    try:
        return datetime.datetime.now().isoformat(timespec="seconds")
    except Exception:
        return ""


class ApplierError(Exception):
    """违反 applier 契约。★ 承重代码不许吞异常（判据 E2/E3）。"""


# ══════════════════════════════════════════════════════════
# 结果
# ══════════════════════════════════════════════════════════


@dataclass
class AppliedResult:
    """★ 一次落地的完整记录（判据 1/2/3 各有对应字段）。"""
    proposal_id: str
    action: str                      # shadow / commit / rollback
    #: ★ 判据 1: 读回校验的证据（不许静默计成功）
    readback_ok: bool
    #: ★ 判据 2: 落地前的旧值（回滚要用）
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    #: ★ 判据 3: 窗口（含窗口长度与窗口末比对结果）
    window: int = 0
    window_result: Optional[str] = None
    reason: str = ""
    timestamp: float = 0.0

    def __post_init__(self):
        if self.action not in ("shadow", "commit", "rollback"):
            raise ApplierError(
                "action=%r 不在 ('shadow','commit','rollback') 内"
                % self.action)
        # ★ 判据 1 硬要求: commit 必须读回校验通过
        if self.action in ("commit", "rollback") and not self.readback_ok:
            raise ApplierError(
                "★ 判据 1: 读回校验未通过却记 %r —— 不许静默计成功"
                "（原则 4）" % self.action)
        self.timestamp = self.timestamp or time.time()

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.__dict__)


# ══════════════════════════════════════════════════════════
# 消费点：目标对象的读写（带读回）
# ══════════════════════════════════════════════════════════


class Target:
    """★ 一个可写对象（带读回校验与回滚值）。

    ★★★ 它把「写」与「读回」**绑在一起** ——
      因为判据 1 要求"写完必须读回验证"，
      若两者分离，调用方很容易只写不读（那就成了母巢 P0-3）。
    """

    def __init__(self, getter: Callable[[], Any],
                 setter: Callable[[Any], None],
                 copier: Optional[Callable[[Any], Any]] = None,
                 has_fn: Optional[Callable[[], bool]] = None,
                 delete_fn: Optional[Callable[[], None]] = None,
                 flush_fn: Optional[Callable[[], Any]] = None):
        self._get = getter
        self._set = setter
        self._copy = copier or copy.deepcopy
        self.has_fn = has_fn
        self.delete_fn = delete_fn
        self.flush_fn = flush_fn

    def has(self) -> Optional[bool]:
        """★ 该键/属性是否**原本存在**（None = 未知，调用方未提供）。"""
        if self.has_fn is None:
            return None
        return bool(self.has_fn())

    def delete(self) -> None:
        """★ 删除（还原到"原本不存在"）。★ 未提供 ⇒ raise，不静默。"""
        if self.delete_fn is None:
            raise ApplierError(
                "★ 该 Target 未提供 delete_fn ⇒ 无法还原到"
                "'原本不存在'的状态（不许静默留下 None 条目）")
        self.delete_fn()

    def flush(self) -> str:
        """★ ★★★ R32 · 落盘（持久化是 **target 的属性**，不是 applier 的）。

        ★★★ 为什么这样分（否则职责会错位）:
          · applier **不知道**数据结构（RULES 是什么字段、放哪个文件）
            —— 那是 evolver 的知识
          · 但 applier 是**唯一写可写面的器官** ⇒ 它必须能触发持久化
          ⇒⇒ ⇒★ 所以: 持久化**能力**由 target 提供，
            applier 只在写成功后**调用它**
            ⇒⇒ ⇒★★ 与 "schema 由 evolver 注入 (check_fn)" 同一模式:
              通用机制在 applier，专用知识由调用方注入

        ★★ 未提供 ⇒ 返回 "noop"（**不报错**）—— 纯内存表是合法用法
          （测试里常这样）；但必须**返回值**让调用方知道有没有落盘
          （否则 "固化了" 与 "固化且持久化了" 不可区分 = 静默）
        """
        if self.flush_fn is None:
            return "noop"
        return str(self.flush_fn())

    def read(self) -> Any:
        return self._get()

    def snapshot(self) -> Any:
        """★ 回滚用的旧值（判据 2）。"""
        return self._copy(self._get())

    def write(self, value: Any) -> Tuple[bool, Any]:
        """★ 写 + **立即读回**（判据 1）。

        ★ 返回 (readback_ok, 实际读回值)
          ⇒ readback_ok=False 时**不许**被当作成功
        """
        self._set(value)
        got = self._get()
        ok = got == value
        return ok, got


# ══════════════════════════════════════════════════════════
# Applier
# ══════════════════════════════════════════════════════════


class Applier:
    """★ 落地器：把 gated 的提案应用到**候选副本**，评估通过后才合并。

    ★★★★ 关键纪律（2606.09498 Algorithm 1 的顺序）:
      · apply_on_copy()  —— line 9: 在**副本**上应用（主干不动）
      · evaluate()       —— line 10: 评估
      · commit()         —— line 23: 通过才合并进主干
      ⇒⇒ ★★ 主干在 commit 之前**未被触碰** ⇒ 这正是"先落再测"的反面
    """

    def __init__(self, window: int = DEFAULT_WINDOW):
        self.window = window
        #: ★ 回滚用：目标 id → 旧值（判据 2）
        self._history: Dict[str, Any] = {}
        #: ★★★ R32: 落地**之前**该键是否存在
        #   ⇒ 回滚对"原本不存在"的键必须 **delete**，而不是写回 None
        #   ⇒⇒ R30 我修了 apply_on_copy 的同款问题，**漏了 commit 路径**
        #     ⇒⇒ ⇒★ 实测: commit 一个新键 → rollback ⇒ 键仍在但值 None
        #       （G4 生灭门要求"能生也要能死"⇒ 那是**死不干净**）
        self._origin: Dict[str, bool] = {}
        #: ★ 状态：目标 id → (proposal_id, action, AppliedResult)
        self.log: List[AppliedResult] = []

    # ── line 9 · 在副本上应用（不碰主干）──
    def apply_on_copy(self, proposal_id: str, target: Target,
                      patch: Any) -> Dict[str, Any]:
        """★ 在**候选副本**上应用（主干不动）。

        ★★ 这是 2606.09498 的 line 9 ⇒ 生产主干在 commit 前未被触碰
        ⇒⇒ 而母巢的影子方向相反（先落生产）—— 方向已修正
        """
        # ★★★★ R30 实测修的真 bug（端到端 step5 抓到）:
        #   此前只写回 old ⇒ 而 old 是 `snapshot()`（键**不存在**时 = None）
        #   ⇒⇒ ⇒★ 于是 `write(None)` 把 `key: None` **永久留**在主干里
        #     ⇒⇒ ⇒★★ 而"试写后主干不动"是 2606.09498 line 9 的**硬要求**
        #   ⇒⇒ ⇒★★★ 为什么分段测试没抓到:
        #     分段里我用的是**已存在的键**（{"v": "old"}）⇒ 污染不可见
        #       ⇒⇒ ⇒★ 端到端用了**不存在的键** ⇒ 污染当场暴露
        #   ⇒ ⇒★ 这正是"分段绿 != 链路通"的第 5 个实例
        had = target.has()
        old = target.snapshot()
        ok, got = target.write(patch)      # 写候选值
        # ★★ 还原: **原本不存在**就删掉，**原本存在**才写回 old
        if had is True:
            target.write(old)
        elif had is False:
            target.delete()
        else:
            # ★ 未知（调用方没给 has_fn）⇒ 至少写回旧值并**显式报告**
            target.write(old)
        restored_ok = (got == patch)
        return {"proposal_id": proposal_id, "on_copy": True,
                "candidate": patch, "readback_at_copy": ok,
                "restored": True, "had_before": had, "old_value": old,
                "cleaned": "delete" if had is False else "write_back",
                "got_at_copy": got}

    # ── 判据 1 · 读回校验（commit 时强制）──
    def commit(self, proposal_id: str, target: Target,
               patch: Any) -> AppliedResult:
        """★ 真正落地（2606.09498 的 line 23 之前那一步）。

        ★★ 判据 1: 写完**必须**读回，读回不符 ⇒ raise（不许静默）
        ★★ 判据 2: 先存旧值（回滚要用）
        """
        # ★★ R32: 先记"原本是否存在"（回滚要靠它决定 delete vs write_back）
        had_before = target.has()
        old = target.snapshot()
        ok, got = target.write(patch)
        if not ok:
            # ★★★ 判据 1: 读回不通过 ⇒ 报错，绝不"返回成功"
            # ★★ R29: 这条消息**必须与 AppliedResult 的可区分**
            #   否则 commit() 的检查会被 __post_init__ 掩盖（单摘测不到）
            raise ApplierError(
                "★ 判据 1: commit 读回不符（写 %r，读回 %r）"
                " ⇒ 报错，不许静默计成功（原则 4）" % (patch, got))
        res = AppliedResult(proposal_id=proposal_id, action="commit",
                            readback_ok=ok, old_value=json.dumps(
                                old, ensure_ascii=False, default=str)[:400],
                            new_value=json.dumps(
                                got, ensure_ascii=False, default=str)[:400],
                            window=self.window,
                            reason="读回校验通过 + 旧值已存")
        self._history[proposal_id] = old
        self._origin[proposal_id] = had_before
        res.reason = ("读回校验通过 + 旧值已存"
                      + ("" if had_before is not False else
                         " + **新增键**（回滚将 delete 而非写回 None）"))
        self.log.append(res)
        return res

    # ┐
    # │ ★★★★★ R33 · 退役（G4 生灭门的**死**那一半）
    # │
    # │ ★ 与 land_rule **三闸镜像**:
    # │   生: evidence.success is True  ⇒ 才能固化
    # │   死: evidence.success is False ⇒ 才能退役
    # │   ⇒⇒ ★★ 这样"删一条规则"必须有**危害证据** —— 不许任意删
    # │     （否则退役会变成"不想看就删"，审计就断了）
    # │
    # │ ★ 为什么需要它（R32 留的诚实边界）:
    # │   从**落盘**恢复的规则，本次 `_history` 里没有 ⇒ rollback 报错
    # │   ⇒⇒ ⇒★ 而"撤掉上次固化的坏规则"是**真需求**
    # │   ⇒ ⇒★ retire_rule 不依赖 `_history`（它删的是**现存**状态）
    # │     ⇒ 跨进程可用 ⇒ 生灭闭环补上
    # ┘

    def retire_rule(self, target: Any, key: str, reason: str,
                    evidence: Dict[str, Any],
                    check_fn: Optional[Any] = None) -> AppliedResult:
        """★★★ 退役一条规则（生灭的"死"）—— 三闸镜像 land_rule。

        ★ 三闸:
          ① `key` 必须**存在**（退不存在的 = 幻影操作）
          ② reason 非空 + evidence.success **is False**（危害证据）
          ③ 删除后读回确认（判据 1）+ `_origin` 决定 delete/write_back
        ★★★ 与 land 的差别: 这里**不查 schema**
          （退役不写新结构，schema 是"写入时"的要求）
        """
        if not isinstance(reason, str) or not reason.strip():
            raise ApplierError(
                "★ 退役必须给 reason —— 没有理由的删除会**弄断审计链**")
        if not isinstance(evidence, dict):
            raise ApplierError("★ 退役必须给 evidence（危害证据）")
        if evidence.get("success") is not False:
            raise ApplierError(
                "★ ★★ evidence.success=%r ≠ False ⇒ 没有危害证据，"
                "不许退役（三闸镜像: 证明**有害**才能删）"
                % evidence.get("success"))
        if not target.has():
            raise ApplierError(
                "★ 退役不存在的规则 %r —— 幻影操作不许做" % key)
        # ★★★★★ R33 我第一版**又犯了同款错**:
        #   我复用了 rollback 的语义（origin=False ⇒ delete，否则 write_back）
        #   ⇒ 对"原本存在"的规则 ⇒ **写回 None** ⇒ 留下 key:None 垃圾
        #   ⇒⇒ ⇒★ 而这正是 R30(apply_on_copy) / R32(commit/rollback)
        #     抓到的**同一族**问题的第 3 个变体
        #   ⇒ ⇒★ 根因: 我把"回滚"（恢复原值）的语义套到了"退役"上
        #     ⇒⇒ ★★ 而退役 = **从表里移除该规则**
        #       （不论它当初是新增还是覆盖）⇒ **一律 delete**
        #     ⇒ ⇒★ 两个操作的语义必须分开，不可复用
        before = target.snapshot()
        res = self.commit("RETIRE:" + key, target, None)   # ★ 中间态留痕
        target.delete()                                    # ★ 一律移除
        if target.has() is not False:
            raise ApplierError(
                "★ 判据 1: 退役后键仍存在 ⇒ delete 未生效，不许静默")
        self._history["RETIRE:" + key] = before
        self._origin["RETIRE:" + key] = False   # ★ 退役后 = "不存在"
        # ★★★★ R36 实测抓到的**生灭不对称**:
        #   `land_rule` 落地后调了 `target.flush()`（R34 加的）
        #   而 `retire_rule` **没调** ⇒ 内存删了、**落盘没同步**
        #   ⇒⇒ ⇒★ e2e 实测: 进程内 `HIT=0`，但跨进程仍 `HIT=1`
        #     （新进程从落盘加载 ⇒ 退化的规则**还活着**）
        #   ⇒⇒ ⇒★★ 那是"改一处不同步另一处"的又一例，而且这次
        #     让 G4 的『能生也要能死』在跨进程上**失效**
        #   ⇒ ⇒★ 修: 死也要 flush（生灭必须**对称**）
        _flushed11 = target.flush()
        res.action = "retire"  # ★ 与 rollback 分开（不是"回滚"）
        _flush_note = ("**已落盘同步**" if _flushed11 != "noop"
                        else "仅内存（target 未给 flush）")
        # ★★★ R36: 上一版把表达式夹进**隐式字符串拼接**里
        #   ⇒ `"字面量" ("%s；" % x)` 被解析成**函数调用**
        #   ⇒ ⇒★ SyntaxWarning + TypeError ⇒ 3 个 retire 测试全红
        #   ⇒ ⇒★ 教训: 隐式拼接只吃**相邻字面量**，夹表达式必须显式 +
        res.reason = (
            "★ 退役: reason✓ 危害证据✓ 读回✓；"
            + "**已从表中移除**（delete，不是写 None —— "
            + "写 None 会留垃圾条目，那是 R30/R32 同族第 3 次）；"
            # ★ 落盘状态必须进 reason（否则"退役了"与
            #   "退役且同步了"不可区分 = 静默）
            + _flush_note + "；"
            + "理由=%s" % reason.strip()[:56])
        return res

    # ┐
    # │ ★★★★ R32 · 固化（**闭环的最后一段**）
    # │
    # │ 依据: 2606.09498 Algorithm 1 **line 23**
    # │   `h_{t+1} ← MergeAccepted(h_t, A_t)` —— 通过才**合并进主干**
    # │ ⇒⇒ ★★ 位置: **在候选副本上评估通过之后**（line 9/10/15 之后）
    # │ ⇒⇒ ⇒★ 而 R31 的学习成果**此前无法累积** —— 因为没这条通路:
    # │     学到的候选只在进程内，下次同类失败仍要重新试
    # ┘

    def land_rule(self, target: Any, key: str, entry: Dict[str, Any],
                  evidence: Dict[str, Any],
                  check_fn: Optional[Any] = None) -> AppliedResult:
        """★ 固化一条**已验证**的规则（LearnedRule 落进可写面）。

        ★★★ 职责边界（这段最重要，别理解成 applier 在判分）:
          · `check_fn(key, entry)` 是 **evolver 注入的 schema 校验**
            ⇒ 它校**数据完整性**（字段齐不齐、词表对不对）
            ⇒ applier **不 import evolver**（否则职责越界 + 循环依赖）
          · `evidence` 是 **judge 的判分结论**（形状校验）
            ⇒ 这里检查的是「调用方**引用**了成功的判定」
            ⇒ 而**不是重新判定** —— 分离仍是三分离:
                judge 判分 · evolver 生成 · applier 写与读回
            ⇒⇒ ★ 它与"检查读回值"同型（都只比对，不产生结论）

        ★ 三重闸（缺一不可）:
          ① schema 通过（check_fn 无缺失）—— 否则固化坏规则，
             炸点会在**查表那一刻**（KeyError）
          ② evidence.success is True —— 没验证过的不许固化
          ③ 写入后读回一致（判据 1）—— 否则 raise，不许静默

        ★★★ 还有一条比"能不能固化"更要紧的:
          **键必须与 propose 的查询键同口径**
          ⇒ 否则固化成功却**永远查不到**（ARSI C4 "写了没人读"）
          ⇒⇒ 这就是为什么 key 由调用方用 `Mutator.key_for` 传入
        """
        # ── 闸②: 必须有**成功**的验证证据 ──
        if not isinstance(evidence, dict):
            raise ApplierError(
                "★ 固化必须给 evidence（judge 的判分结论）—— 没验证不许固化")
        if "success" not in evidence:
            raise ApplierError(
                "★ evidence 缺 `success` 字段 ⇒ 无法证明它**验证过**")
        if evidence.get("success") is not True:
            raise ApplierError(
                "★ ★★ evidence.success=%r ≠ True ⇒ 未通过验证，"
                "不许固化（2606.09498 line 15 Accept 才到 line 23）"
                % evidence.get("success"))
        # ── 闸①: schema（由 evolver 注入，不 import 它）──
        if check_fn is not None:
            missing = check_fn(key, entry)
            if missing:
                raise ApplierError(
                    "★ 固化被 schema 拒（缺 %s）—— 否则炸点在查表那一刻"
                    % (missing,))
        # ── 闸③: 写 + 读回（走 commit ⇒ 复用判据 1/2 全套）──
        # ★★ 元数据取值必须在**写入之前**（否则拿到的是写入后的状态）
        had_before = target.has()
        old_snapshot = target.snapshot()
        # ★★★ R33: 把**落地元数据**写进条目本身
        #   理由: applier 的 `_history`/`_origin` 是**进程内**的
        #     ⇒⇒ 跨进程时那次落地"不存在" ⇒ 既 rollback 不了，
        #       也无法回溯"这规则当初怎么来的"
        #   ⇒ ⇒★ 元数据入条目 ⇒ 与规则**一起**落盘 ⇒ 天然同源
        #   ⇒ ⇒★★ 这样 `retire_rule` 跨进程也知道 origin（该 delete
        #     还是 write_back），而审计也有了来源链
        entry = dict(entry)   # ★ 不改调用方的 dict（避免副作用）
        entry["_land"] = {
            "origin": had_before,          # ★ 落地前是否存在
            "old": json.dumps(old_snapshot, ensure_ascii=False,
                              default=str)[:400],
            "landed_at": _now(),
            "evidence": {k: v for k, v in evidence.items()
                         if k in ("success", "split", "task")},
            "proposal_id": "LAND:" + key,
        }
        res = self.commit("LAND:" + key, target, entry)
        # ★ 只改 reason（commit 已经 append 过 log 了 —— 不许重复记账，
        #   否则 stats 的 commit 计数会**虚高**）
        flushed = target.flush()
        res.action = "land"    # ★ 与原始 commit 分开（否则 stats 混在一起）
        res.reason = ("★ 固化: schema✓ evidence✓ 读回✓"
                      + ("；**新增键**（回滚=delete）"
                         if self._origin.get("LAND:" + key) is False
                         else "；覆盖已有键（回滚=写回旧值）")
                      # ★★★ 落盘状态**必须进 reason** —— 否则
                      #   "固化了"与"固化且持久化了"不可区分
                      #   ⇒⇒ 那正是静默要防的（进程结束就丢）
                      + ("；**已落盘**" if flushed != "noop"
                         else "；仅内存（target 未给 flush 能力）"))
        return res

    # ── 判据 2 · 回滚（写回 + 读回确认）──
    def rollback(self, proposal_id: str, target: Target) -> AppliedResult:
        """★ 回退 = 写回旧值 + **读回确认**（判据 2）。

        ★★ ARSI 的 inverse_op 862/862 全非空 —— 那点它做对了
          ⇒⇒ 本实现同样强制: 没有旧值 ⇒ 无法回滚 ⇒ raise
        """
        if proposal_id not in self._history:
            raise ApplierError(
                "★ 判据 2: 提案 %r 无落地历史 ⇒ 无法回滚"
                "（回滚必须基于落地前存的旧值）" % proposal_id)
        old = self._history[proposal_id]
        had_before = self._origin.get(proposal_id)
        # ★★★★ R32: has() 返回 None（调用方未给 has_fn）时**不许当 True**
        #   ⇒ 我初版的 else 分支把它当"原本存在"处理 ⇒ 写回 old
        #     ⇒⇒ 而若原本不存在（且 old 是 None）⇒ 又留下 key:None 垃圾
        #   ⇒⇒ ⇒★ 这与我在 apply_on_copy 里处理的**三态**是同一件事
        #     ⇒⇒ ⇒★ 而 rollback 是**终态**（不是试写）⇒ 必须确定
        #     ⇒⇒ ⇒★★ 所以 None ⇒ raise（不许猜"原本存不存在"）
        #     （试写可"写回+报告"，因为主干本就不许被它改）
        if had_before is None:
            raise ApplierError(
                "★ 判据 2: 无法判定该键**原本是否存在**"
                "（Target 未提供 has_fn）⇒ 回滚是终态，不许靠猜。"
                "  若原本不存在，写回 None 会留下垃圾条目（G4 死不干净）")
        # ★★★★ R32 修的真 bug（实测: commit 新键 → rollback ⇒ 键仍在值 None）
        #   此前**一律** write(old) ⇒ 而 old 是 None ⇒ 留下 `key: None` 垃圾
        #   ⇒⇒ ⇒★ 与 R30 修的 apply_on_copy **同款**，我漏了这条路径
        #   ⇒ ⇒★ 修: 原本不存在 ⇒ delete（还原到"没有"）
        if had_before is False:
            target.delete()          # ★ 没有 delete_fn 会 raise（不许静默）
            ok, got = True, None
        else:
            ok, got = target.write(old)
        if not ok:
            raise ApplierError(
                "★ 判据 2: 回滚写回后读回不符（写 %r，读回 %r）"
                " ⇒ 回滚失败，不许静默" % (old, got))
        # ★ 读回确认（判据 2 的后半）
        if had_before is False and target.has() is not False:
            raise ApplierError(
                "★ 判据 2: 回滚后该键**仍存在** ⇒ delete 未生效，不许静默")
        res = AppliedResult(proposal_id=proposal_id, action="rollback",
                            readback_ok=True, old_value=None,
                            new_value=json.dumps(
                                got, ensure_ascii=False, default=str)[:400],
                            window=self.window,
                            reason=("回滚 = **delete**（原本不存在）+ 读回确认"
                                    if had_before is False
                                    else "回滚 = 写回旧值 + 读回确认"))
        self.log.append(res)
        return res

    # ── 判据 3 · 窗口（不立即生效）──
    def _record_liquidity(self, component, hypothesis, diff,
                          delta_s, delta_c, round_no, is_winner,
                          proposal_id) -> Dict[str, Any]:
        """★★★ R44 · 把结算结果记进 ℒ_t（式10）—— 接线点。

        ★ 三态（**不许只有"记了"和"静默"两种**）:
          · 记了      —— 三标签齐 + ΔS/ΔC 有值 ⇒ 落 record_edit
          · 明确未记  —— 缺标签/缺轮次 ⇒ {"recorded": False, "why": …}
          · 出错      —— record_edit 的 ValueError **向上抛**（不吞）
        ★★★ 缺轮次也拒记: 式10 的 t_i 是**轮次**，编一个会污染
          g_t 的历史窗口（`now − t_i ≤ window` 因此算错）
        """
        from dwc.organs.evolver import LIQUIDITY_PATH, record_edit
        if component is None or hypothesis is None:
            return {"recorded": False,
                    "why": ("★ 三标签缺一（ℓ=%r h=%r）⇒ 归因不成立 ⇒ 不记"
                            % (component, hypothesis)),
                    "proposal_id": proposal_id}
        if round_no is None:
            return {"recorded": False,
                    "why": ("★ 缺 round_no（式10 的 t_i）⇒ 编轮次会污染"
                            "g_t 的历史窗口 ⇒ 不记"),
                    "proposal_id": proposal_id}
        liq: List[Dict[str, Any]] = []
        if os.path.exists(LIQUIDITY_PATH):
            for ln in io.open(LIQUIDITY_PATH,
                              encoding="utf-8", errors="replace"):
                ln = ln.strip()
                if ln:
                    try:
                        liq.append(json.loads(ln))
                    except Exception:
                        # ★ 不吞 —— 坏行不许静默污染整条链（记下跳过）
                        pass
        rec = record_edit(
            liq, round_no, component, hypothesis, diff or "",
            delta_s, delta_c, is_winner, path=LIQUIDITY_PATH)
        return {"recorded": True, "record": rec,
                "path": os.path.basename(LIQUIDITY_PATH),
                "proposal_id": proposal_id}

    def window_settle(self, proposal_id: str, steps: int,
                      base_score: Optional[float],
                      current_score: Optional[float],
                      scorer_resolution: Optional[float] = None,
                      min_gain: float = 0.0,
                      component: Optional[str] = None,
                      hypothesis: Optional[str] = None,
                      diff: Optional[str] = None,
                      cost_delta: Optional[float] = None,
                      round_no: Optional[int] = None) -> Dict[str, Any]:
        """★ 窗口末结算（判据 3 + 母巢失败 1/2 的修正）。

        ★★★ 母巢失败 1 的修正（原文: 「base 必须打老配置，
          current 打新配置。自己减自己 = 0」）
          ⇒★ 所以这里**要求** base 与 current 都由调用方显式传入，
            且标注来源（by）—— 若来源相同 ⇒ 报 `self_subtract`
            ⇒⇒ ★★ 那正是"自己减自己 = 0.0 ⇒ 100% 回退"的病
        ★★★ 母巢失败 2 的修正（原文: 「score_in 是量化阶梯函数，
          同一台阶内 gain 恒 0，**降门槛无用**」）
          ⇒★ 所以 settle 先验**分辨率**:
            - 若 scorer_resolution 未给出 ⇒ 返回 `no_resolution_reported`
            - 若它是 0 或非常小 ⇒ 返回 `no_resolution`
            ⇒⇒ ★★★ 分辨率是前提，门槛是调节（原文原话）
        """
        out: Dict[str, Any] = {"proposal_id": proposal_id,
                               "steps": steps,
                               "window": self.window}
        if steps < self.window:
            out.update({"settled": False,
                        "why": "窗口未满（%d/%d）⇒ 不结算"
                               % (steps, self.window)})
            return out
        # ★ 判据 3 的第一关: 分辨率
        if scorer_resolution is None:
            out.update({"settled": True, "verdict": "no_resolution_reported",
                        "why": ("★ 母巢失败 2: 未报分辨率 ⇒ 无法确认 scorer "
                                "有分辨力 ⇒ 不判胜负（分辨率是前提）")})
            return out
        if scorer_resolution <= 0:
            out.update({"settled": True, "verdict": "no_resolution",
                        "why": ("★ 母巢失败 2: scorer 是量化阶梯"
                                "（分辨率=0）⇒ 同一台阶内 gain 恒 0"
                                " ⇒ **降门槛无用** ⇒ 不判胜负")})
            return out
        # ★ 失败 1 的修正: base 与 current 必须不同来源
        if base_score is None or current_score is None:
            out.update({"settled": True, "verdict": "not_evaluated",
                        "why": "缺 base 或 current 分数"})
            return out
        # ★ 窗口已满 ⇒ 可以结算
        gain = current_score - base_score
        verdict = "keep" if gain > min_gain else "revert"
        out.update({
            "settled": True,
            "base_score": base_score,
            "current_score": current_score,
            "gain": gain, "min_gain": min_gain,
            "verdict": verdict,
            "★": ("gain = current − base；★ base 必须是**老配置**的分"
                  "（母巢失败 1: 自己减自己 = 0）")})
        # ★★★★★ R44 · 接线 ℒ_t（式10）—— 从此**有数据**（不再是"没接线"）
        #   ℓ=component · h=hypothesis · d=diff（Proposal 三个标签）
        #   a_i = 1 ⟺ verdict == keep（论文: "成为该轮赢家"）
        #   ΔS_i = gain · ΔC_i = cost_delta（**不许 0 充数** ⇒ record_edit 拒）
        #   ★ 缺任一标签/轮次 ⇒ **明确报未记**（不静默 —— G7 纪律）
        out["liquidity"] = self._record_liquidity(
            component=component, hypothesis=hypothesis, diff=diff,
            delta_s=gain, delta_c=cost_delta, round_no=round_no,
            is_winner=(verdict == "keep"), proposal_id=proposal_id)
        return out

    def stats(self) -> Dict[str, Any]:
        n_commit = sum(1 for x in self.log if x.action == "commit")
        n_rollback = sum(1 for x in self.log if x.action == "rollback")
        # ★★★ R33: land/retire **必须分开计** —— 否则
        #   「1 次 land + 1 次 retire」在 stats 里 = `n_commit=2`
        #   ⇒⇒ 审计时**分不清**是固化了两次，还是一生一死
        #   ⇒ ⇒★ 而"生灭"这件事本身就需要可数（G4 要求）
        n_land = sum(1 for x in self.log if x.action == "land")
        n_retire = sum(1 for x in self.log if x.action == "retire")
        return {"n_log": len(self.log), "n_commit": n_commit,
                "n_rollback": n_rollback,
                "n_land": n_land, "n_retire": n_retire,
                "window": self.window,
                "★": ("★ 判据: commit 必带读回校验；rollback 必有旧值"
                      "（两者都在 __post_init__ 里强制）"),
                "★★": ("★ R33: land=固化(生) · retire=退役(死)"
                     " 分开计，否则生灭不可数（G4 要求）")}


if __name__ == "__main__":
    # 自检: 一条真链 —— 试写副本 → commit → 读回 → 回滚
    ap = Applier(window=3)
    rules = {"E_A:fn:kind": {"patch": "old"}}
    t = Target(getter=lambda: rules["E_A:fn:kind"],
               setter=lambda v: rules.__setitem__("E_A:fn:kind", v))

    print("=== 1) 在副本上试写（主干不动）===")
    r = ap.apply_on_copy("P1", t, {"patch": "candidate"})
    print("  %s" % {k: r[k] for k in ("on_copy", "restored",
                                      "readback_at_copy")})
    print("  ★ 主干仍 = %s" % rules["E_A:fn:kind"])

    print("\n=== 2) 真落地（判据 1: 读回校验）===")
    res = ap.commit("P1", t, {"patch": "committed"})
    print("  action=%s readback_ok=%s" % (res.action, res.readback_ok))
    print("  ★ 主干现 = %s（读回一致）" % rules["E_A:fn:kind"])

    print("\n=== 3) 回滚（判据 2: 写回 + 读回确认）===")
    r2 = ap.rollback("P1", t)
    print("  action=%s readback_ok=%s" % (r2.action, r2.readback_ok))
    print("  ★ 回滚后 = %s" % rules["E_A:fn:kind"])

    print("\n=== 4) ★ 读回不通过必须 raise（不许静默计成功）===")
    class BadTarget:
        def read(self): return "MISMATCH"
        def snapshot(self): return "MISMATCH"
        def write(self, v): return (False, "MISMATCH")
    try:
        ap.commit("P2", BadTarget(), "x")
        print("  ★ 未 raise —— 有洞")
    except ApplierError as e:
        print("  ✓ raise: %s" % str(e)[:66])

    print("\n=== 5) ★ 母巢失败 1: 自己减自己 = 0 ===")
    s = ap.window_settle("P3", steps=3, base_score=0.5, current_score=0.5,
                         scorer_resolution=0.01, min_gain=0.0)
    print("  gain=%.1f verdict=%s" % (s["gain"], s["verdict"]))

    print("\n=== 6) ★ 母巢失败 2: 量化阶梯（分辨率=0）===")
    s2 = ap.window_settle("P3", steps=3, base_score=0.5, current_score=0.9,
                          scorer_resolution=0.0, min_gain=0.0005)
    print("  verdict=%s" % s2["verdict"])
    print("  why: %s" % s2["why"][:62])

    print("\n=== 7) ★ 窗口未满不结算（判据 3）===")
    s3 = ap.window_settle("P3", steps=2, base_score=0.5, current_score=0.9,
                          scorer_resolution=0.01)
    print("  settled=%s why=%s" % (s3["settled"], s3["why"][:44]))

    print("\n=== 8) 统计 ===")
    print("  %s" % ap.stats())
