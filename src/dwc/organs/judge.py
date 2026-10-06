# -*- coding: utf-8 -*-
"""DWC judge —— 判分器（器官 2/7）。

★★★ 这个器官为什么是当前最要紧的
  R23 的 run_term 已把孤岛连起来，但实测暴露三处因judge 缺位而失效:
    ① 五元盘点 π/V/U 全是 None（V = judge）
    ② change 环 judge=None ⇒「回到判分器」是空话
    ③ 终止条件③（保护组回归）无法判定
  ⇒⇒ judge 是唯一能同时解这三处的地方。

定位声明（DWC-MEM · 记忆底座 · 判据 G1 定位门）
  ★ judge = 记忆底座（原则 3: 单一真值源）
  ★ 它**只读** agent 可见面，绝不读 r_priv（判据 JUDGE_DESIGN §4.4）
  ★ 它**不进递归**（2608.24876 §5.1.1 硬要求: "𝒢_fixed 不能进递归。
    递归改记忆，判分器不动。"）

★★★ TRUTH_SOURCE · 本模块的系统外真值源（判据 G2 要求必须声明）
  真值源 = (dev 集的 golden reference) + (sealed 集的全锁定标签)
  ⇒ 两者都在**文件**里（config/anchors/），agent 不可写
  ⇒ 这满足 GAI grounded 的双条件（§2.2 原文）:
      ① 内容来自系统外（世界与目标）—— golden reference 是人写的
      ② base 本身在 agent 外 —— 文件不在 agent 可写面内
  ⚠★★ 若这个字段指不到真实存在的文件，本模块会在 _check_truth_source
     启动时 raise —— 不许"声明了但其实没有"（原则 1）

★★★ 三条硬约束（JUDGE_DESIGN 逐条核过）
  ① fallback 必须满足**同一条契约**（§3.3）
     —— ARSI 的 fallback 是"结构检查"（有 def/return 就给分），
        那不满足"判定任务是否解决"⇒ DWC 不许注册那种 fallback
  ② grounded 双条件缺一不可（GAI §2.2）
  ③ 三 split 互不相交（2607.12790 §2.2）
     —— 当前只有 dev(anchors) 与 test(sealed)；train 暂无（诚实边界④）
"""
from __future__ import annotations

import ast
import io
import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

# ══════════════════════════════════════════════════════════
# 契约
# ══════════════════════════════════════════════════════════


class JudgeError(Exception):
    """违反 judge 契约。★ 承重代码不许吞异常（判据 E2/E3）。"""


#: ★★★ 本模块的系统外真值源（判据 G2 的硬要求）
#:   形式: (类别, 路径) —— 路径必须是**真实存在**的文件
TRUTH_SOURCE: Tuple[str, ...] = (
    # ★★ dev: 已落地（10 条 · 6 behavior + 4 keyword_match）
    ("dev_anchors", r"E:/Divine Wisdom Core/config/anchors/dev.json"),
    # ★★ test: **未落地**。2607.12790 §2.2 原文 test 是 locked split，
    #   「no part of metric evolution reads it」
    #   ⇒⇒ JUDGE_DESIGN §4.5 也写明「test 锁定任务: **必须另建**」
    # ⇒⇒ ★★ 绝不能用 dev 的副本冒充 —— 那会让回归检测形同虚设
    #     （分子分母同源，改了哪边都算过）
    ("test_sealed", r"E:/Divine Wisdom Core/config/anchors/test_sealed.json"),
)

#: ★★ 未落地的真值源（判据: 声明了但文件不存在 ⇒ 启动必须 raise）
#:   这是"诚实"的一部分 —— 而不是留空文件假装合法
TRUTH_NOT_BUILT = {"test_sealed"}

#: ★ judge 的三 split（2607.12790 §2.2: 三个互不相交的 split）
SPLIT_DEV = "dev"        # 锚点集，恒小，每条带 golden reference
SPLIT_TEST = "test"      # 锁定集，metric 演化不许读
SPLIT_TRAIN = "train"    # 无标签大集合  ★ 当前不存在（诚实边界④）


# ══════════════════════════════════════════════════════════
# 判定结果
# ══════════════════════════════════════════════════════════


@dataclass(frozen=True)
class Verdict:
    """一次判定。★ success=None 表示**未评价**，不许当 False 也不许当 True。

    ★★★ 这是 ACTOR_DESIGN 的核心纪律之一:
      ARSI 的 exec_ok 是 bool 且被硬编码 ⇒ DWC 允许 None
      ⇒ 规则: None 不许当 False 也不许当 True（§4.5）
    """
    task_id: str
    split: str
    #: ★ None = 未评价（缺 golden reference / fallback 不合规 / 未跑）
    success: Optional[bool]
    #: 为什么是这个结论（含 None 的原因）
    reason: str
    #: 真值源类别（可审计: 结论从哪来）
    truth_category: Optional[str] = None
    #: 若 success 是 None，缺什么
    missing: Optional[str] = None

    def is_pass(self) -> bool:
        """★ 只有显式 True 才算通过（None 不算）。"""
        return self.success is True

    def to_dict(self) -> Dict[str, Any]:
        return {"task_id": self.task_id, "split": self.split,
                "success": self.success, "reason": self.reason,
                "truth_category": self.truth_category,
                "missing": self.missing}


# ══════════════════════════════════════════════════════════
# 判分器
# ══════════════════════════════════════════════════════════


def _as_literal(txt: str) -> Any:
    """★ 把文本归一成 python 字面量（失败则原样返回）。

    ★★ 为什么需要它（R26 实测）: golden 里的 expected 是**字面量文本**
      （"'cba'" / "True" / "0.0"），而实测值是 python 对象
      ⇒ 不归一就 str 比 ⇒ 字符串型断言永远不等
    ★ 安全: 只用 ast.literal_eval（不执行任意代码）
    """
    t = str(txt).strip()
    try:
        return ast.literal_eval(t)
    except (ValueError, SyntaxError):
        return t


def _eq(a: Any, b: Any) -> bool:
    """★ 值相等判定（按类型分层，不靠 str 比）。

    ★★★★ R28 实测修正（这是 R26 那个洞的**第三种形态**）:
      R26 修的是「字面量文本 vs python 对象」（值侧 + 入参侧）
      ⇒⇒ ★★ 而 test split 出现了**容器类型**入参（list），
        那时 str 比就失效了:
          a='[3,7,2]'（观测侧字符串） b=[3,7,2]（golden 侧 list）
          str(a)='[3,7,2]'  str(b)='[3, 7, 2]'   ← ★ 有空格差异 ⇒ 不等
        ⇒⇒⇒ 而那会让**完全正确的实现**被判 fail
      ⇒⇒⇒ ⇒★ ⇒★ 教训: str 比只在两侧都解析失败时才可用；
        能解析的一律走对象比较
    """
    # ── 数值/布尔: 类型必须一致（1 与 1.0 不算同一个）──
    if isinstance(a, (int, float, bool)) or isinstance(b, (int, float, bool)):
        if isinstance(a, bool) != isinstance(b, bool):
            return False
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            return type(a) is type(b) and a == b
        return str(a) == str(b)
    # ★ 容器: 逐元素比（不做 str 比 —— 那会被空白差异骗）
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        if len(a) != len(b):
            return False
        return all(_eq(x, y) for x, y in zip(a, b))
    # ★ str 与「看起来像容器的字符串」: 先尝试归一再比
    if isinstance(a, str) and isinstance(b, (list, tuple, dict)):
        return _as_literal(a) == b
    if isinstance(b, str) and isinstance(a, (list, tuple, dict)):
        return _as_literal(b) == a
    if isinstance(a, str) and isinstance(b, str):
        return a == b
    # ★ dict: 键值逐对
    if isinstance(a, dict) and isinstance(b, dict):
        return set(a) == set(b) and all(_eq(a[k], b[k]) for k in a)
    return a == b


class Judge:
    """DWC 判分器。★ 只读 agent 可见面，不进递归。"""

    def __init__(self, anchors_path: Optional[str] = None,
                 sealed_path: Optional[str] = None):
        self.anchors = self._load(anchors_path
                                  or TRUTH_SOURCE[0][1], SPLIT_DEV)
        # ★★ test split 未落地 ⇒ 显式标记为 None，不假装有
        #   （2607.12790 §2.2 的 test 语义要求它与 dev 互不相交 ⇒
        #     拿 dev 顶替等于把"测试集"变成"训练可见集"）
        # ★★ 关键: 未落地**不该让启动失败** —— dev 可用是事实，
        #   test 缺席也是事实 ⇒ 两者都如实报告，用到 test 时才 raise
        #   （与 R14 那条「未采用 ≠ 失败」同族：不同状态要能区分）
        if sealed_path:
            self.sealed = self._load(sealed_path, SPLIT_TEST)
        else:
            p_test = TRUTH_SOURCE[1][1]
            self.sealed = (self._load(p_test, SPLIT_TEST)
                           if os.path.exists(p_test) else None)
        self._fallbacks: Dict[str, Callable] = {}
        # ★★ 记住每一次判定，用于"未评价不许悄悄变 True"的审计
        self._log: List[Verdict] = []

    # ── 真值源加载与自检 ──
    @staticmethod
    def _load(path: str, split: str) -> Dict[str, Dict[str, Any]]:
        """加载真值源。★ 文件不存在必须 raise（不许返回空 dict 假装合法）。"""
        if not os.path.exists(path):
            raise JudgeError(
                "真值源不存在: %s（split=%s）"
                " —— ★ 声明了 TRUTH_SOURCE 却没有真实文件"
                " ⇒ 违反原则 1（判据必须在系统之外）" % (path, split))
        data = json.loads(io.open(path, encoding="utf-8").read())
        if not isinstance(data, dict) or not data:
            raise JudgeError("真值源为空: %s" % path)
        for tid, rec in data.items():
            if tid.startswith("_"):
                continue                      # _provenance 等元数据（不数进任务）
            if not isinstance(rec, dict):
                raise JudgeError(
                    "真值源 %s 的 %r 不是字典" % (path, tid))
            #★★ 校验口径（R24 实测修正）:
            #   初版要求每条有 success 字段 ⇒ 但 dev.json 的判据是
            #   checks / expected_keywords（黄金断言），没有 success
            #   ⇒⇒ 而 success 是**判分结果**，不是真值源的一部分
            #   ⇒⇒ 真值源该有的是"可执行的判据"，我要求错了
            kind = rec.get("verifier_kind")
            checks = rec.get("checks")
            if kind not in ("behavior", "keyword_match"):
                raise JudgeError(
                    "真值源 %s 的 %r 判据形态 %r 不合法"
                    "（应为 behavior / keyword_match）" % (path, tid, kind))
            if not checks:
                raise JudgeError(
                    "真值源 %s 的 %r 没有可执行判据"
                    " —— 判不了就别混进真值源（原则 1）" % (path, tid))
            if kind == "behavior":
                for c in checks:
                    e = str(c.get("expected", ""))
                    #★ 引号数为奇数 ⇒ 字符串残缺（上游数据缺陷）
                    if e.count("'") % 2 == 1 or e.count('"') % 2 == 1:
                        raise JudgeError(
                            "真值源 %s 的 %r 有残缺断言 expected=%r"
                            "（引号未闭合）⇒ 该断言不可执行"
                            % (path, tid, e))
        return data

    @staticmethod
    def _task_ids(src: Dict[str, Dict[str, Any]]) -> Set[str]:
        """★ 任务 id 集合（**排除**元数据键）。

        ★★★★ R28: 我 R24 修过一次「_provenance 被当任务」的 bug
          （n_tasks=11 而实际 10），但 self_check 那条路径漏了
          ⇒⇒ ⇒★ 结果 splits_disjoint 恒为 False（两个 split
            的 _provenance 键必然相交）⇒ 一个永远错的断言
          ⇒⇒ ⇒★ 元数据过滤必须收敛成**一个**函数，否则到处漏
        """
        return {k for k in src if not k.startswith("_")}

    def _check_truth_source(self) -> Dict[str, List[str]]:
        """★ 启动自检: 已落地的真值源必须存在；未落地的要显式列名。

        ★★★★ R24 实测修正: 初版要求 TRUTH_SOURCE 里**每一个**文件都存在
          ⇒ 而 test_sealed 是**故意未落地**的（JUDGE_DESIGN §4.5「必须另建」，
            而 DWC 还没另建）⇒ 于是启动就死
          ⇒⇒ ★★ 而"故意未落地"与"声明了却丢了"是**两件事**:
            前者是诚实的设计缺口，后者是事故
          ⇒⇒ 所以未落地项走 TRUTH_NOT_BUILT 白名单并**列在报告里**，
            不许静默，也不许当成缺失
        """
        missing, not_built = [], []
        for cat, path in TRUTH_SOURCE:
            if os.path.exists(path):
                continue
            if cat in TRUTH_NOT_BUILT:
                not_built.append(cat)
            else:
                missing.append(cat)
        if missing:
            raise JudgeError(
                "TRUTH_SOURCE 声明的 %s 不存在且**不在**未落地白名单里 "
                "⇒ 声明与实况不符（这可能是事故，不是设计缺口）" % missing)
        return {"verified": [c for c, _ in TRUTH_SOURCE
                             if c not in not_built],
                "not_built": not_built}

    # ══════════════════════════════════════════════
    # 判分主路径
    # ══════════════════════════════════════════════
    def evaluate(self, task_id: str, split: str = SPLIT_DEV,
                 observed: Optional[Dict[str, Any]] = None,
                 predicted: Optional[Any] = None) -> Verdict:
        """★ 判一次。★ 三个 split 互不相交，跨 split 用错要 raise。

        ★★ 判分口径（不许自评）:
          success = (observed 与 golden reference 的比较结果)
          ⇒ agent 给的 predicted **只用于对比，不用于判定**
            （这是"被实际服务的东西不能当训练标签"的三分离）
        """
        if split == SPLIT_TRAIN:
            raise JudgeError(
                "train split 不存在（诚实边界④）—— 而它按设计是"
                "『无标签大集合』⇒ 无标签可拿来判分")
        if split not in (SPLIT_DEV, SPLIT_TEST):
            raise JudgeError("split=%r 不在 %r 内" % (split, (SPLIT_DEV,
                                                             SPLIT_TEST)))
        if split == SPLIT_TEST and self.sealed is None:
            #★★★ test 未落地时必须 raise，不许"用 dev 顶替"
            #   （用 dev 顶替 ⇒ 回归检测形同虚设：分子分母同源）
            raise JudgeError(
                "test split **未落地**（JUDGE_DESIGN §4.5: 必须另建）"
                " ⇒ 不许用 dev 顶替 —— 那会让保护组回归检测形同虚设")
        if split == SPLIT_TEST and self.sealed is None:
            raise JudgeError(
                "test split **未落地**（JUDGE_DESIGN §4.5: 必须另建）"
                " ⇒ 不许用 dev 顶替")
        src = self.anchors if split == SPLIT_DEV else self.sealed
        cat = "dev_anchors" if split == SPLIT_DEV else "test_sealed"
        if task_id not in src:
            raise JudgeError(
                "task %r 不在 %s split 里（真值源 %s）"
                % (task_id, split, cat))
        golden = src[task_id]

        if observed is None:
            v = Verdict(task_id, split, None,
                        "未评价：observed 为 None（根本没跑）",
                        cat, "observed")
            self._log.append(v)
            return v

        ok = self._compare(golden, observed)
        note = ""
        if predicted is not None:
            agree = (bool(predicted) == ok)
            #★ 用条件取值，不在字符串里嵌 %s 再套 %（R24 踩过两次）
            verdict = "一致" if agree else "**不一致**"
            note = "｜agent 自报与实测" + verdict
        v = Verdict(task_id, split, ok,
                    "按 %s 的 golden reference 比较实测%s" % (cat, note),
                    cat)
        self._log.append(v)
        return v

    @staticmethod
    def _compare(golden: Dict[str, Any],
                 observed: Dict[str, Any]) -> bool:
        """★ 比较口径: 按 verifier_kind 分别处理两种形态。

        ★★★★ R24 实测修正: 初版只按 dict 迭代 checks
          ⇒ 而 dev.json 的 checks 是 **list** ⇒ 直接 AttributeError
          ⇒⇒ ★ 原因: 我写了 _compare 但从没喂过真实数据
            ⇒⇒ ⇒★ 这是我自己的老毛病: 「实现了就以为能用」

        ★★ 两种形态（JUDGE_DESIGN 的判据分流）:
          behavior       —— fn(args) == expected，结构化断言
          keyword_match  —— 答案文本里含 expected_keywords 全部
        ⇒⇒ 而两者都**不许**用 agent 自报当判据（三分离）
        """
        kind = golden.get("verifier_kind")
        checks = golden.get("checks") or []
        if not checks:
            #★ 没有可执行判据 ⇒ 不许判通过（原则 1）
            return False

        if kind == "keyword_match":
            text = str(observed.get("answer", observed.get("text", "")))
            missing = [c["kw"] for c in checks
                       if c.get("kw") and c["kw"] not in text]
            return not missing

        if kind == "behavior":
            # observed 形态: {fn_name: [[args, actual_value], ...]}
            #★★★★ R26 实测修正（真跑 actor 才暴露的契约缺口）:
            #   初版把 expected 当**字符串**比（str(c["expected"])）
            #   ⇒ 而 golden 里的 expected 是**字面量文本**
            #     "reverse_string('abc')=='cba'" ⇒ expected = "'cba'"（带引号）
            #   ⇒⇒ 而实测值是 python 对象 'cba'（str，无引号）
            #     str('cba') == "'cba'" ⇒ ★ 永远不等 ⇒ 字符串型断言全挂
            #   ⇒⇒★★ 而实测表现: 5 pass / 1 fail，fail 的正是字符串那条
            #     ⇒⇒ 那不是 actor 的错，是**契约两侧对不上**
            # ⇒★ 正确做法: 两侧都归一到 **python 字面量** 再比
            for c in checks:
                fn = c.get("fn")
                want_txt = str(c.get("expected", ""))
                args_txt = str(c.get("args", ""))
                want = _as_literal(want_txt)     # ★ 字面量归一
                args = _as_literal(args_txt)
                calls = observed.get(fn)
                if calls is None:
                    return False
                hit = False
                for call in calls:
                    if not isinstance(call, (list, tuple)) or len(call) < 2:
                        continue
                    if _eq(call[0], args):
                        if not _eq(call[1], want):
                            return False
                        hit = True
                        break
                if not hit:
                    return False        # ★ 压根没调这个入参 ⇒ fail
            return True

        # ★ 未知形态 ⇒ 不许判通过（保守）
        return False

    # ══════════════════════════════════════════════
    # fallback（★ 必须同契约 —— JUDGE_DESIGN §3.3）
    # ══════════════════════════════════════════════
    def register_fallback(self, name: str,
                          fn: Callable[[str, Dict[str, Any]],
                                      Optional[bool]],
                          contract: Dict[str, Any]) -> str:
        """★ 注册 fallback。★ 必须提供**可被自动判定**的契约。

        ★★★ 硬要求（JUDGE_DESIGN §3.3 原文的直译）:
          "任何 fallback 若不满足同契约，不许注册"
          ⇒ contract 必须是结构化的、能被 validate 检出的
          ⇒★ 而 ARSI 的 fallback 是「结构检查」（有 def/return 就给分）——
            那不满足"判定任务是否解决" ⇒ 我在 validate 里显式拒绝它
        """
        if not isinstance(contract, dict) or not contract:
            raise JudgeError(
                "fallback %r 必须提供契约（JUDGE_DESIGN §3.3）" % name)
        # ★★ 拒接"结构检查"型 fallback（ARSI 同款）
        mode = contract.get("mode")
        if mode == "structure_only":
            raise JudgeError(
                "fallback %r 的契约是 structure_only —— "
                "那不满足『判定任务是否解决』（ARSI 的缺陷 3）"
                " ⇒ 不许注册（JUDGE_DESIGN §3.3）" % name)
        if mode != "contract_equivalent":
            raise JudgeError(
                "fallback %r 的 mode=%r 不合法 —— 只能是 "
                "contract_equivalent（JUDGE_DESIGN §3.3）" % (name, mode))
        self._fallbacks[name] = fn
        return name

    def evaluate_with_fallback(self, task_id: str,
                               split: str = SPLIT_DEV,
                               observed: Optional[Dict] = None
                               ) -> Verdict:
        """★ 用 fallback 判（仅当 fallback 已注册且合规）。"""
        v = self.evaluate(task_id, split, observed)
        if v.success is None and self._fallbacks:
            fn = next(iter(self._fallbacks.values()))
            r = fn(task_id, observed or {})
            vv = Verdict(task_id, split, r,
                         "由合规 fallback 判（契约 mode=contract_equivalent）",
                         v.truth_category)
            self._log.append(vv)
            return vv
        return v

    # ══════════════════════════════════════════════
    # 批量与统计（★ 供 run_term 的终止条件③ 用）
    # ══════════════════════════════════════════════
    def score(self, split: str = SPLIT_DEV,
              observations: Optional[Dict[str, Dict]] = None
              ) -> Dict[str, Any]:
        """★ 给一个 split 打分。

        ★★★ 关键: 未评价**单独计数**，不混进通过率
          ⇒ 因为 success=None 若被当 False，分数会虚低
          ⇒ 而若被当 True，分数会虚高（R14 那条假通过的同族）
        ⇒⇒ 所以这里同时报 pass / fail / **not_evaluated** 三个数
        """
        if split == SPLIT_TRAIN:
            raise JudgeError("train split 不存在")
        # ★★ test 未落地 ⇒ 返回"无法判分"，不是 0 分（R24 修正）
        if split == SPLIT_TEST and self.sealed is None:
            return {"split": split, "n_tasks": 0, "pass": 0, "fail": 0,
                    "not_evaluated": 0, "pass_rate": None,
                    "★": "test split 未落地 ⇒ 无法判分（不是 0 分）",
                    "details": []}
        src = self.anchors if split == SPLIT_DEV else self.sealed
        obs = observations or {}
        n_pass = n_fail = n_none = 0
        details: List[Dict[str, Any]] = []
        for tid in src:
            if tid.startswith("_"):
                continue        # ★ 元数据不是任务
            v = self.evaluate(tid, split, obs.get(tid))
            if v.success is True:
                n_pass += 1
            elif v.success is False:
                n_fail += 1
            else:
                n_none += 1
            details.append(v.to_dict())
        # ★★★ R24 修正: src 含 _provenance 等元数据键 ⇒ 之前被当任务数
        #   ⇒ 实测 dev_tasks=11 而实际只有 10 条
        total = len([k for k in src if not k.startswith("_")])
        graded = n_pass + n_fail
        return {
            "split": split,
            "n_tasks": total,
            "pass": n_pass, "fail": n_fail, "not_evaluated": n_none,
            # ★ 分母只算真正判过的（未评价不进分母）
            "pass_rate": (n_pass / graded) if graded else None,
            "★": "not_evaluated 单独计（None 不许当 False 也不许当 True）",
            "details": details,
        }

    def regression_check(self, baseline: Dict[str, Any],
                         current: Dict[str, Any]) -> Dict[str, Any]:
        """★ 保护组回归检测（终止条件③ 的实现基础）。

        ★★★★ R24 实测修正: 初版用「两侧 not_evaluated 都为 0」当可比条件
          ⇒ 而 dev 有 10 条、只跑 2 条时 not_evaluated=8 ⇒ 永远 not_comparable
          ⇒⇒ ★★ 那是错的判据 —— 保护组回归的本质是**同一批任务**上分数下降，
            不是"全部任务都跑过"
          ⇒⇒⇒ 正确判据: **两边判过的任务集合必须相同**
            （不同 ⇒ not_comparable，因为分子分母不可比）
            （相同 ⇒ 可比，哪怕只覆盖了 20%）

        ★★ 口径（ERROR_AND_TERM §2.3 条件③: r̂ ≤ ε 不满足即触发）:
          ⇒ delta < 0 ⇒ regression；delta ≥ 0 ⇒ ok
        """
        def graded_set(d):
            return {x["task_id"] for x in d.get("details", [])
                    if x.get("success") is not None}

        b_ids, c_ids = graded_set(baseline), graded_set(current)
        if not b_ids or not c_ids:
            return {"verdict": "not_comparable",
                    "why": "有一侧没有任何未评价=已判的任务 ⇒ 未评价不足以比较"}
        if b_ids != c_ids:
            only_b = sorted(b_ids - c_ids)
            only_c = sorted(c_ids - b_ids)
            return {"verdict": "not_comparable",
                    "why": "两边判过的任务集不同 ⇒ 分子分母不可比",
                    "only_in_baseline": only_b, "only_in_current": only_c}

        # ★ 同一批 ⇒ 可比。注意只在这批上比，不掺未判的
        b_pass = sum(1 for x in baseline["details"]
                     if x.get("success") is True and x["task_id"] in b_ids)
        c_pass = sum(1 for x in current["details"]
                     if x.get("success") is True and x["task_id"] in c_ids)
        eps = b_pass / len(b_ids)
        cur = c_pass / len(c_ids)
        delta = cur - eps
        return {
            "verdict": "ok" if delta >= 0 else "regression",
            "baseline_pass_rate": eps,
            "current_pass_rate": cur,
            "delta": delta,
            "n_compared": len(b_ids),
            "★": ("只在这批判过的任务上比；未判的不进比较"
                  "（未评价不许当 False 也不许当 True）"),
        }

    # ══════════════════════════════════════════════
    # 审计
    # ══════════════════════════════════════════════
    def unevaluated(self) -> List[Dict[str, Any]]:
        """★ 所有"未评价"的判定（供门检与报告）。"""
        return [v.to_dict() for v in self._log if v.success is None]

    def self_check(self) -> Dict[str, Any]:
        """★ 启动自检。已落地真值源缺失就 raise；未落地的显式列出。"""
        ts = self._check_truth_source()
        return {
            "truth_source": ts,
            "dev_tasks": len([k for k in self.anchors
                              if not k.startswith("_")]),
            "test_tasks": (len(self._task_ids(self.sealed))
                           if self.sealed is not None else None),
            "test_built": self.sealed is not None,
            #★★★ R28 修正（又是元数据被当任务·同 R24 那次）:
            #   set(self.anchors) 含 _provenance ⇒ 与 test 的 _provenance
            #   **必然相交** ⇒ splits_disjoint 永远是 False
            #   ⇒⇒ 而我 R24 修过一次同类 bug（n_tasks=11），
            #     却在 self_check 这条路径上漏了 ⇒ ⇒ 同族第二次
            "splits_disjoint": (
                None if self.sealed is None
                else not (self._task_ids(self.anchors)
                          & self._task_ids(self.sealed))),
            "fallbacks": sorted(self._fallbacks),
            "★": ("真值源已验证存在（G2/原则 1）；未落地项在 not_built 里"),
        }


if __name__ == "__main__":
    try:
        j = Judge()
    except JudgeError as e:
        print("★★ 启动失败（这是预期的 —— 真值源还没建）: %s" % e)
        raise SystemExit(1)
    print("自检: %s" % j.self_check())
    sc = j.score(SPLIT_DEV, {})
    print("dev 打分: pass=%d fail=%d not_evaluated=%d pass_rate=%s"
          % (sc["pass"], sc["fail"], sc["not_evaluated"], sc["pass_rate"]))