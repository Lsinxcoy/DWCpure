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
  ★ 判据分层（E1 重述 · 设计稿④ R112 · 用户裁决②: 做 — 逐字对齐稿 §④）:
    "**锚与判分执行**（golden 对值比对 / TRUTH_SOURCE / SPLIT_TEST）
     不进递归; **验收门外部化**（patch admission + 三层验证）不可自改;
     **评估策略层**（dev 权重/门槛/口径/challenger 评估器）可经『epoch 内
     冻结 + 点界 challenger 对锚比对 + 平票在位者 + dep(z) 抹除』共演化
     — 依据: RQGM 2606.26294 四件套 + Recuris 2608.24876 三性质的
     作用域拆分（设计稿④ R112, 用户裁决: 做）。"
    ★ 旧判据（"判分器不进递归。递归改记忆,判分器不动"）的作用域收窄为
      "锚与判分执行/验收门"两层 — 验收门外部化照旧（Recuris 三性质①③
      全保: agent 仍不可改判分, 换代只能走 epoch 点界流程）;

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
import re
import os
import sys as _sys
from dwc.foundation.paths import find_root as _fr
ROOT = _fr()
import time
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from dwc.foundation.version import dw_version as _git_version

# ══════════════════════════════════════════════════════════
# 契约
# ══════════════════════════════════════════════════════════


#: ★★★ R34 · **diffs 的字段真源**（judge 产 · candidates 读 · evolver 看）
#:   ★★★ 为什么必须收敛成一个常量:
#:     我 R34 写 `_llm_generate` 时凭记忆用了 `got`/`want`
#:     ⇒ 而 judge 产的是 `actual`/`expected`
#:     ⇒⇒ ⇒★ 于是 LLM prompt 里的证据**恒为 None**
#:       （LLM 收到空证据 ⇒ 生成 = 凭空编造）
#:     ⇒⇒ ⇒★★ 这与我 R30 吃过的亏是**同一族**:
#:       字段名/值域各写一份，必然漂移
#:   ⇒ ⇒★ 三处共用本常量，改字段只改一处
DIFF_FIELDS = ("index", "kind", "fn", "kw", "args",
               "expected", "actual", "ok", "reason")

def _append_line(path: str, text: str) -> None:
    """★★★ R395 · 用**单次 `os.write`** 追加一行（不要 TextIOWrapper 缓冲）。

    现场（2026-10-20 21:12）：`config/anchors/task_scores.jsonl` 里出现

        …"recorded_at": "2026-10-20T21:1        ← 第 46 行（半行）
        7:51"}                                  ← 第 47 行（尾巴）

    一条记录被拆成两行 ⇒ 读侧 `json.loads` 抛 ⇒ 每次构造 `Loop()` 都崩
    ⇒ 全量测试 59 failed + 37 errors。

    原因：`io.open(path, "a")` 是**带缓冲的文本流**，`f.write()` 不保证
    一次落到文件；多进程/异常中断时就会写出半行。
    `os.write` 到 O_APPEND fd 对 ≤4KB 的小写入是单次原子追加。
    """
    data = (text.rstrip("\n") + "\n").encode("utf-8")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
    try:
        n = os.write(fd, data)
        while n < len(data):          # 极少见的部分写：补完
            n += os.write(fd, data[n:])
    finally:
        os.close(fd)


class JudgeError(Exception):
    """违反 judge 契约。★ 承重代码不许吞异常（判据 E2/E3）。"""


#: ★★★ 本模块的系统外真值源（判据 G2 的硬要求）
#:   形式: (类别, 路径) —— 路径必须是**真实存在**的文件
TRUTH_SOURCE: Tuple[str, ...] = (
    # ★★ dev: 已落地（10 条 · 6 behavior + 4 keyword_match）
    ("dev_anchors", os.path.join(ROOT, "config", "anchors", "dev.json")),
    # ★★ test: **未落地**。2607.12790 §2.2 原文 test 是 locked split，
    #   「no part of metric evolution reads it」
    #   ⇒⇒ JUDGE_DESIGN §4.5 也写明「test 锁定任务: **必须另建**」
    # ⇒⇒ ★★ 绝不能用 dev 的副本冒充 —— 那会让回归检测形同虚设
    #     （分子分母同源，改了哪边都算过）
    ("test_sealed", os.path.join(ROOT, "config", "anchors", "test_sealed.json")),
    # ★★ R184 · train: 2607.12790 的"无标注大集合"（A_train 共识面）
    #   — train.json 落了（R184: 6 条同族新题, 无 expected）; 与 dev/
    #   test 互不相交（前缀 train_ + 题面不同 — 已验 dev∩train=∅）
    ("train_unlabeled", os.path.join(ROOT, "config", "anchors", "train.json")),
)

#: ★★ 未落地的真值源（判据: 声明了但文件不存在 ⇒ 启动必须 raise）
#:   这是"诚实"的一部分 —— 而不是留空文件假装合法
#: ★★ R169 清算: test_sealed **已落地**（R28 · config/anchors/test_sealed.json
#:   11 条 locked split — eval_built 在场核验过）⇒ 从白名单**移除**;
#:   白名单机制保留（声明了却丢 ⇒ raise 的纪律不减）, 只是当前无未落地项。
TRUTH_NOT_BUILT: set = set()

#: ★ judge 的三 split（2607.12790 §2.2: 三个互不相交的 split）
SPLIT_DEV = "dev"        # 锚点集，恒小，每条带 golden reference
SPLIT_TEST = "test"      # 锁定集，metric 演化不许读
SPLIT_TRAIN = "train"    # 无标签大集合  ★ 当前不存在（诚实边界④）
#: ★ R330/N2 · fresh 独立验证面（Eq.8 V_k 专用 —— DWC 自有第 4 面，
#:   非论文三元组：TRUTH_SOURCE 三元不动；与 dev/sealed 零交集由
#:   tests/test_a1b_fresh.py 静态锁，不在 _load 里跨文件校验）
SPLIT_FRESH = "fresh"


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
    # ★★★ R30: 失败签名 —— 由**规则**填 c/q（2609.06396 原文分工）
    #   ⇒ 此前 judge 完全不产签名，而 actor 只在**异常**时产
    #     ⇒⇒ 于是"值错误"这条路径上**三端都不产签名**
    #       ⇒⇒ ⇒★ 被迫手填 ⇒ 与 RULES 键不匹配 ⇒ 端到端断
    #   ⇒ ⇒★ 所以这是补**根因**，不是加功能
    failure_signature: Optional[Dict[str, str]] = None
    #: ★★★ R197 · **多失败签名清单**（① 数据面改进 — 不是新接口）
    #:   failure_signature = 首个 notok check 的签名（R30 原口径, 不变）;
    #:   sigs = 该 verdict 上**全部** notok check 的签名（去重; 单失败时相同）
    #:   ⇒ Loop→evolver.diagnose 可一次拿全簇; diagnose 已按 (c,q,m) 聚类
    #     ⇒ 传多个不会重复提案（约束 4 逐字）。
    #:   ★ fail 时非空 / pass 时 []（pass 无签名可产 — 不造空签名）。
    sigs: Optional[List[Dict[str, str]]] = None
    #: ★★★★ R54 · **k/n 的分母/分子**（细粒度分数的原料）
    #:   ⚠ 背景: `diffs` 字段存的是 **失败条目**（`bad`，成功时 = []）
    #:     ⇒ 我第一版 `pass_rate` 拿 `len(v.diffs)` 当分母 = **完全错**
    #:     （把「失败数」当「总数」）—— 我核了 `_diff` 却**没核 Verdict
    #:     到底存了什么**（先读再写没做到）
    #:   ⇒ ⇒★ 所以 judge 在 evaluate 时就把 k/n 存进来（它手里有全部 diffs）
    #:   ★ None = 未评价（observed 缺 / 早期 return）—— 不许当 0/1
    n_checks: Optional[int] = None
    k_passed: Optional[int] = None
    #: ★ 逐条差异（judge 判 fail 时必须说**哪条**、差在哪）
    #:   ⇒ 此前 reason 是通用文案（"按 golden reference 比较实测"）
    #:     ⇒⇒ 那等于没说 ⇒ c 的原料根本没有
    diffs: Optional[List[Dict[str, Any]]] = None

    def is_pass(self) -> bool:
        """★ 只有显式 True 才算通过（None 不算）。"""
        return self.success is True

    def to_dict(self) -> Dict[str, Any]:
        """★ Verdict 的**完整**序列化（R72 修正）。

        ★★★ 缺陷史（R72 抓的存量洞）:
          原来只序列化 6 字段 ⇒ failure_signature / n_checks / k_passed /
          diffs 全丢 ⇒ evidence.jsonl 里失败签名落成 null（R71 活证据 6 条
          false 全 null 实锤）⇒ 约定④「查时才取」取回的是**残缺证据**。
        ⇒ 修法 = 把 Verdict **已有**字段全部序列化（不发明新字段）。
        ⇒ 消费面已核: judge 外无读 verdict dict 字段的代码; score() 的
          details 与 unevaluated() 是唯二外部出口。
        """
        return {"task_id": self.task_id, "split": self.split,
                "success": self.success, "reason": self.reason,
                "truth_category": self.truth_category,
                "missing": self.missing,
                # ★ R72 补齐 —— 否则 z 投影 / k-n 审计在 evidence 侧全断
                "failure_signature": self.failure_signature,
                "sigs": self.sigs,
                "n_checks": self.n_checks,
                "k_passed": self.k_passed,
                "diffs": self.diffs}


# ══════════════════════════════════════════════════════════
# 判分器
# ══════════════════════════════════════════════════════════




# ══════════════════════════════════════════════════════════
# 失败签名 phi(r) = (c, q, m) —— 两篇原文收敛的三段式
# ══════════════════════════════════════════════════════════
# 2606.09498 §3.3: c = terminal verifier-level cause
#                  q = causal status of agent behavior
#                  m = abstract agent mechanism exposed by trace
# 2609.06396 Eq.10: chi terminal cause / psi causal role / mu reusable
#
# ★★ 分工（2609.06396 原文）: **前两段由规则分配，第三段由模型假设**
#   ⇒ 所以 c/q 必须是**规则**（代码），m 才归 LLM
#   ⇒⇒ ★ 于是 judge 是**唯一**该产出 c/q 的位置 ——
#     因为 c 是 "verifier-level cause"，而 judge 就是 verifier
#
# ★★★ R30 端到端实测的根因:
#   actor   只在**异常**时产签名（L287/L309）⇒ 值错误时 signature=None
#   judge   此前**不产签名**、也不说哪条失败、差在哪
#   evolver.diagnose 收签名（不收 TraceRecord）
#   ⇒⇒ ★★★ 三端都不产 ⇒ 手填 ⇒ 与 RULES 键不匹配 ⇒ 闭环断在 step4
#   ⇒⇒ ⇒★ 而**此前所有分段测试都绿** —— 因为分段里签名也是手填的
#     ⇒⇒ ⇒★★ 手填把接口不匹配完全遮蔽（"分段绿 != 链路通"最强证据）


# ═══════════════════════════════════════════════════════════
# ★★★★★ R54 · **细粒度分数**（用户裁决「甲」: 多任务 pass_rate = k/n）
#   ★ 背景: R50 我实测分数 ∈ {0,1} ⇒ δ 的可行域只剩 {0}（δ∈[0,1) 全等价、
#     δ≥1 退化）⇒ **δ 没有调节空间**（且与 R41 量化阶梯同根）
#   ⇒ 用户选**甲**: 多任务 pass_rate（论文原意）⇒ 分数连续 ⇒ δ 有意义
#
# === 为什么分母**已经存在**（不是新建数据集）===
#   `_diff` 对每个 check 产一条 ⇒ `len(diffs)` 就是 n（11 task / 26 check）
#   而 `success = all(ok)` 是**二值投影**（k==n ⇒ True）
#   ⇒ ⇒★ 所以 pass_rate = k/n 是**同一批数据的另一种读法**
#     （不改判据、不加检查 —— 只是不再把 k/n 压成 0/1）
#
# === 三个层级（每层都说清语义）===
#   ① `pass_rate(v)` —— **单 task**: k/n over checks
#   ② `overall_score(vs)` —— **聚合**（论文 Ŝ_t = overall）: sum(k)/sum(n)
#      ★ 用 **micro 平均**（总 k / 总 n）而非 mean(ratio):
#        后者会让 1-check 任务与 4-check 任务**等权** ⇒ 4 个 check 的
#        任务信息量更大, 等权会放大单点噪声
#   ③ 未评价（success=None）**排除**在分母外 —— 对齐「None 不许当 0/1」
#
# ★★ 硬要求（每条对应一个我犯过的坑）:
#   ① `success is None` ⇒ 返回 **None**（未评价, 不许当 0 或 1）
#   ② `diffs` 空 ⇒ 返回 **None**（无判据可算, 除零/当 1.0 都是编造）
#   ③ 分母 0（全都没评价）⇒ 返回 **None**（不许 0/0 或默认满分）
# ═══════════════════════════════════════════════════════════


def pass_rate(v) -> Optional[float]:
    """★ 单 task 的通过率 **k/n**（细粒度, 不再压成 0/1）。

    ★ 输入 `Verdict`（judge 的产物）；返回 float ∈ [0,1] 或 **None**
    ★ None 的两种含义（**都表示"没测出来"**, 不许当分数用）:
        · `success is None` —— 未评价（observed 缺 / 无 checks / 未跑）
        · `diffs` 空        —— 没有判据可算
    ★★ 为什么 None 不当 0: R44/R50 的纪律 —— 「没测」与「测了是 0」
      是两回事（None=诚实未测, 0=实测失败）；混起来会让
      「未评价的 task」凭空拉低分数
    """
    if v is None:
        return None
    if getattr(v, "success", None) is None:
        return None                     # ① 未评价 ⇒ 不是 0/1
    # ★★★ R54 修: 分子分母取 **n_checks/k_passed**（judge 记的真值）
    #   ⚠ 不许用 `v.diffs` —— 那是**只含失败**的条目（成功时 = []）
    #     拿它当分母 = 把「失败数」当「总数」（我第一版就错了）
    n = getattr(v, "n_checks", None)
    k = getattr(v, "k_passed", None)
    if n is None or k is None or n <= 0:
        return None                     # ② 没记 k/n（早期 return/旧对象）
    return k / n


def overall_score(verdicts) -> Optional[float]:
    """★★ 聚合分数 **Σk / Σn**（论文式13 的 `Ŝ_t` = overall score）。

    ★ 输入: `Verdict` 的**可迭代**（一轮里所有 task 的判定）
    ★ ★ 用 **micro 平均**: 总通过数 / 总 check 数
      · 不用 mean(pass_rate): 那会让 1-check 任务与 4-check 任务**等权**
      · 依据: 4-check 的任务携带更多信息, 等权会放大单点噪声
    ★ 硬要求:
      ① 空输入 / 全部未评价 ⇒ **None**（不许 0/0, 也不许默认满分）
      ② 未评价的 task **排除在分母外**（对齐「None 不当 0/1」）
      ③ 返回值带上 (k, n) 可复核（否则「0.5」看不出是 1/2 还是 5/10）
    """
    if not verdicts:
        return None                     # ① 空
    k_tot = n_tot = 0
    n_skipped = 0
    for v in verdicts:
        if v is None or getattr(v, "success", None) is None:
            n_skipped += 1               # ② 未评价 ⇒ 不进分母
            continue
        # ★ R54: 用 n_checks/k_passed（不是 v.diffs —— 那只含失败）
        n = getattr(v, "n_checks", None)
        k = getattr(v, "k_passed", None)
        if not n or n <= 0 or k is None:
            n_skipped += 1
            continue
        k_tot += k
        n_tot += n
    if n_tot == 0:
        return None                     # ① 全都没评价 ⇒ None, 不是 0.0
    return {
        "score": k_tot / n_tot,
        "k": k_tot, "n": n_tot,
        "n_skipped": n_skipped,         # ③ 可复核
        "basis": "Σk/Σn = %d/%d（未评价 %d 个 task 不进分母）"
                 % (k_tot, n_tot, n_skipped),
    }


def classify_c(expected: Any, actual: Any) -> str:
    """c: 终止原因（verifier 拒绝了什么）—— **规则**分类，非 LLM。

    ★★ 只从「期望 vs 实测」的**差异形态**分类
      ⇒ 不按任务、不按函数 —— 那些属于 q/m
    """
    if actual is None:
        return "E_NO_RESULT"
    both_num = (isinstance(expected, (int, float))
                and isinstance(actual, (int, float))
                and not isinstance(expected, bool)
                and not isinstance(actual, bool))
    if not both_num and type(expected) is not type(actual):
        return "E_TYPE"
    if both_num:
        d = abs(float(expected) - float(actual))
        if d == 1.0:
            return "E_OFF_BY_ONE"
        if d == 0.0:
            return "E_NONE"
        return "E_VALUE"
    if isinstance(expected, bool) and isinstance(actual, bool):
        if expected is False and actual is True:
            return "E_FALSE_POSITIVE"
        if expected is True and actual is False:
            return "E_FALSE_NEGATIVE"
        return "E_NONE"
    return "E_MISMATCH"


def classify_q(expected: Any, actual: Any) -> str:
    """q: 因果角色（agent 行为如何促成该拒绝）—— **规则**分类，非 LLM。

    ★★ 2606.09498 的警示原文:
      "两个 run 可能共享同一个 verifier 结果（如 timeout 或缺失产物），
       却需要**不同的** harness 改动"
    ⇒ 所以 q 不能是"发生了什么"（那已归 c），要问**行为模式**
    """
    if actual is None:
        return "abstained_or_missing"
    if isinstance(actual, bool) and isinstance(expected, bool):
        return "consistent" if actual == expected else "wrong_polarity"
    if (isinstance(expected, (int, float))
            and isinstance(actual, (int, float))
            and not isinstance(expected, bool)
            and not isinstance(actual, bool)):
        try:
            if float(expected) != 0.0 and abs(
                    float(expected) - float(actual)) == 1.0:
                return "off_by_one_in_range"
        except (TypeError, ValueError) as e:
            # ★★★ G7 静默门抓到我这处 `except: pass`（本轮）
            #   ⇒ 我 R29 刚写过「不许静默」，转头在 judge 里又犯
            #   ⇒⇒ ★ 同族第三次（memory 里"大声报错"那条）
            #   ⇒ ⇒★ 修: 把异常**反映进结果**，不吞
            #     （否则排查时分不出"真有差 1"还是"算不出来"）
            return "non_numeric_diff:%s" % type(e).__name__
        return "wrong_magnitude"
    if isinstance(expected, str) and isinstance(actual, str):
        if len(actual) < len(expected):
            return "truncated_or_missing_tail"
        if len(actual) > len(expected):
            return "extra_content"
        return "wrong_content"
    return "value_mismatch"


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


# ★ R277b-7 · 执行通道数值宽松开关（evaluate 开/关，默认关 =
#   规则时代严格；_diff/_eq 签名零改，用模块开关透传通道上下文）。
_NUM_LOOSE = [False]


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
    # ★ R277b-7 · 例外: 执行通道（LLM/JSON）数值只比值不比类型 ——
    #   JSON 不区分 int/float（0 与 0.0 是同一个数），类型是传输
    #   artifact 不是语义；规则时代仍严格（防 "6" 冒充 6，R30 纪律）。
    #   布尔永远严格（True≠1，两种通道一致）。
    if isinstance(a, (int, float, bool)) or isinstance(b, (int, float, bool)):
        if isinstance(a, bool) != isinstance(b, bool):
            return False
        if isinstance(a, (int, float)) and isinstance(b, (int, float)):
            if _NUM_LOOSE[0] and not isinstance(a, bool) \
                    and not isinstance(b, bool):
                return a == b
            return type(a) is type(b) and a == b
        # ★★★★ R30 实测抓到的**严重判分 bug**:
        #   此前这里是 `return str(a) == str(b)`（我 R28 加的兜底）
        #   ⇒ _eq("6", 6) ⇒ str("6")=="6"、str(6)=="6" ⇒ **True**
        #   ⇒⇒ ★★ 于是"值是字符串 6"被判成**通过**（期望是 int 6）
        #   ⇒⇒ ⇒★★ 而 judge 是**真值源** —— 让类型错通过 = 真值门失效
        #   ⇒ ⇒★ 根因: 我把 str 比当成万能兜底，却没注意它会跨类型
        #   ⇒ ⇒★ 同族已犯三次（R26 字面量 / R28 容器空格 / 现在跨类型）
        # ⇒ 修: **一方是数字而另一方不是 ⇒ 类型不匹配，直接 False**
        return False
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


# ══════════════════════════════════════════════════════════
# C3' · 逐任务分数序列（docs/TASK_SCORE_TRACKING.md §三 设计定稿 · R71 落地）
#   落点 = judge 的**内部存储**（设计 §3.1: 高基数时序不进 State ——
#   约定④ 只传 ID + P2 State 是快照不是流水）
# ══════════════════════════════════════════════════════════

@dataclass(frozen=True)
class TaskScorePoint:
    """单任务单轮的评测点。★ 一个任务一轮一条, 不覆盖（设计 §三 11 字段）。

    ★ 三个关键字段的理由（TS1/TS2 依据, 逐字来设计文档）:
      n_assertions —— 没有它, "0.67 跌到 0.33" 无法区分掉几个断言
        ⇒ 分辨率不可审计
      dw_version —— 换版本即换坐标系（TS2）; 版本源 = git 真实状态
        （foundation/version.py —— run_term T3 原锁的是两个空串=假锁）
      split —— 守卫①与回归约束读的都是 split 内的分数, 不能混
    ★ 全部 11 字段**必填无默认**（G11 同款: 缺字段事后不可解释）。
    """

    task_id: str
    group_id: str
    round_index: int
    split: str
    wm_version: str
    dw_version: str
    score: float                # ★ 连续分 [0,1] = k_passed / n_checks
    n_assertions: int           # ★★ 分辨率审计字段（TS1）
    rung: int
    evidence_ref: str           # 指向 evidence, 不内嵌（约定④: 只传 ID）
    recorded_at: str


class TaskScoreStore:
    """TS3 存储（judge 内部 · 设计 §3.1）。

    ★ 双模式:
      path=None ⇒ **内存模式**（缺省 —— 测试零污染, 重启丢）
      path=…   ⇒ 落盘模式: 构造载回 + 判分即 append（重启不丢）
    ★ 落盘模式要求 score 与 evidence **成对**（path/evidence_path 同给或同
      不给）—— 单边落盘会产生悬空 ref 或孤儿证据, 构造时直接 raise。
    ★ 聚合口径: group_scores 无条目的组**不出现**（不装 0 —— X2 同族）。
    """

    def __init__(self, path: Optional[str] = None,
                 evidence_path: Optional[str] = None, *,
                 dw_version: Optional[str] = None,
                 wm_version: str = ""):
        if (path is None) != (evidence_path is None):
            raise JudgeError(
                "path/evidence_path 必须同给或同不给（单边落盘 ⇒ 悬空 "
                "evidence_ref 或孤儿证据）, 实得 %r/%r"
                % (path, evidence_path))
        self.path = path
        self.evidence_path = evidence_path
        #: TS2 版本坐标系: 注入优先, 缺省取 git 真源（foundation/version）
        self.dw_version = (dw_version if dw_version is not None
                           else _git_version())
        #: world_model 当前**无版本机制** —— 占位字段如实空串（诚实边界）
        self.wm_version = wm_version
        self._points: List[TaskScorePoint] = []
        self._evidence: Dict[str, Dict[str, Any]] = {}
        self._n_mem_evi = 0
        if path and os.path.exists(path):
            self._load_jsonl_tolerant(path, self._points, TaskScorePoint)
        if evidence_path and os.path.exists(evidence_path):
            self._load_evidence_tolerant(evidence_path)

    # ── 容忍式装载（R395）──────────────────────────────────
    def _load_jsonl_tolerant(self, path: str, sink: list, cls) -> None:
        """逐行装载 JSONL；**坏行跳过但计数并大声报**（不许静默吞）。

        ★★★ R395 现场（2026-10-20 21:12）：
          `config/anchors/task_scores.jsonl` 第 46 行被写成半行
          （`…"recorded_at": "2026-10-20T21:1` + 下一行 `7:51"}`），
          旧实现 `json.loads` 直接抛 ⇒ **每次构造 Loop() 都崩**
          ⇒ 全量测试 59 failed + 37 errors。

          一条半行不该让整个系统起不来：跳过 + 计数 + 打警告，
          把损坏暴露出来（`self.n_corrupt`），而不是假装没事。
        """
        n_bad = 0
        try:
            lines = io.open(path, encoding="utf-8").read().splitlines()
        except Exception as exc:                       # noqa: BLE001
            _sys.stderr.write("judge store 读取失败 %s: %s\n" % (path, exc))
            self.n_corrupt = getattr(self, "n_corrupt", 0)
            return
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            try:
                sink.append(cls(**json.loads(line)))
            except Exception:                          # noqa: BLE001
                n_bad += 1
                _sys.stderr.write(
                    "judge store 坏行已跳过 %s:%d %r\n"
                    % (path, i, line[:80]))
        self.n_corrupt = getattr(self, "n_corrupt", 0) + n_bad

    def _load_evidence_tolerant(self, path: str) -> None:
        """同 `_load_jsonl_tolerant`（evidence 版本）。"""
        n_bad = 0
        try:
            lines = io.open(path, encoding="utf-8").read().splitlines()
        except Exception as exc:                       # noqa: BLE001
            _sys.stderr.write("evidence 读取失败 %s: %s\n" % (path, exc))
            return
        for i, line in enumerate(lines, 1):
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
                ref = d.pop("_ref")
                self._evidence[ref] = d
            except Exception:                          # noqa: BLE001
                n_bad += 1
                _sys.stderr.write(
                    "evidence 坏行已跳过 %s:%d %r\n" % (path, i, line[:80]))
        self.n_corrupt = getattr(self, "n_corrupt", 0) + n_bad

    # ── 写入（判分点 → 分数点）────────────────────────────
    def record(self, verdict: "Verdict", *, group_id: str,
               rung: int) -> Optional[TaskScorePoint]:
        """★ 判分点即记录点。

        ★ 未评价（success=None）或零分母（n_checks=0）⇒ **不记** ——
          score 是 float, None 不许冒充 0/1（Verdict §4.5 同族纪律）。
        """
        n = verdict.n_checks
        k = verdict.k_passed
        if verdict.success is None or not n:
            return None
        ri = sum(1 for p in self._points
                 if p.task_id == verdict.task_id
                 and p.split == verdict.split) + 1
        pt = TaskScorePoint(
            task_id=verdict.task_id,
            group_id=group_id,
            round_index=ri,
            split=verdict.split,
            wm_version=self.wm_version,
            dw_version=self.dw_version,
            score=k / float(n),
            n_assertions=n,
            rung=rung,
            evidence_ref=self._store_evidence(verdict),
            recorded_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        self._points.append(pt)
        if self.path:
            # ★ R395 · 原子追加（单次 os.write，避免半行）
            _append_line(self.path,
                         json.dumps(asdict(pt), ensure_ascii=False))
        return pt

    def _store_evidence(self, verdict: "Verdict") -> str:
        d = verdict.to_dict()
        if self.evidence_path:
            n = 0
            if os.path.exists(self.evidence_path):
                n = sum(1 for line in io.open(self.evidence_path,
                                              encoding="utf-8")
                        if line.strip())
            ref = "%s#%d" % (os.path.basename(self.evidence_path), n + 1)
            # ★ R395 · 原子追加（单次 os.write，避免半行）
            _append_line(self.evidence_path,
                         json.dumps(dict(d, _ref=ref), ensure_ascii=False))
        else:
            self._n_mem_evi += 1
            ref = "mem#%d" % self._n_mem_evi
        self._evidence[ref] = d
        return ref

    def evidence(self, ref: str) -> Dict[str, Any]:
        """按 ref 拉回 evidence 全文（约定④: 点里只有 ID, 查时才取）。"""
        if ref not in self._evidence:
            raise JudgeError(
                "evidence_ref=%r 不可解析 —— 点与证据必须成对存储" % (ref,))
        return self._evidence[ref]

    # ── TS3 双查询口 ─────────────────────────────────────
    def task_scores(self, split: Optional[str] = None,
                    wm_version: Optional[str] = None
                    ) -> List[TaskScorePoint]:
        """TS3 口①: 逐任务分数序列（第⑦步 / δ_θ 的数据源）。"""
        return [p for p in self._points
                if (split is None or p.split == split)
                and (wm_version is None or p.wm_version == wm_version)]

    def group_scores(self, split: str,
                     round_index: Optional[int] = None
                     ) -> Dict[str, float]:
        """TS3 口②: 按能力组聚合（均值）。

        ★ 无条目的组**不出现** —— 不装 0（"没观测过"≠"组 0 分"）。
        """
        buckets: Dict[str, List[float]] = {}
        for p in self._points:
            if p.split != split:
                continue
            if round_index is not None and p.round_index != round_index:
                continue
            buckets.setdefault(p.group_id, []).append(p.score)
        return {g: sum(v) / len(v) for g, v in buckets.items()}


class Judge:
    """DWC 判分器。★ 只读 agent 可见面，不进递归。"""

    def __init__(self, anchors_path: Optional[str] = None,
                 sealed_path: Optional[str] = None,
                 train_path: Optional[str] = None,
                 fresh_path: Optional[str] = None,
                 store_path: Optional[str] = None,
                 evidence_path: Optional[str] = None,
                 dw_version: Optional[str] = None):
        self.anchors = self._load(anchors_path
                                  or TRUTH_SOURCE[0][1], SPLIT_DEV)
        # ★ HCE 拆分（稿⑥§③ · 裁决①"拆"）: dev 内 D_search/D_val 两子集
        #   缺 "_split"（旧锚源）⇒ 两集为空 = 不屏蔽（诚实缺席, 零装数）
        _raw_split = self.anchors.get("_split") if isinstance(
            self.anchors, dict) else None
        if isinstance(_raw_split, dict) and _raw_split.get("val"):
            self.d_val = set(_raw_split.get("val") or ())
            self.d_search = set(_raw_split.get("search") or ())
        else:
            self.d_val, self.d_search = set(), set()
        # ★★ test split 未落地 ⇒ 显式标记为 None，不假装有
        #   （2607.12790 §2.2 的 test 语义要求它与 dev 互不相交 ⇒
        #     拿 dev 顶替等于把"测试集"变成"训练可见集"）
        # ★★ 关键: 未落地**不该让启动失败** —— dev 可用是事实，
        #   test 缺席也是事实 ⇒ 两者都如实报告，用到 test 时才 raise
        #   （与 R14 那条「未采用 ≠ 失败」同族：不同状态要能区分）
        # ★★ R184 · train split（2607.12790 的"无标注大集合" — A_train 的
        #   共识面）。三条纪律逐条对齐论文:
        #   ① train.json 在档才载入 — **缺席不失败**（诚实边界④的同款:
        #      dev 可用与 train 缺席都是事实, 用到 train 时才响）
        #   ② train 面**无 golden** ⇒ _load 的字段校验对它放宽: 它只提供
        #      "题面+验证器配置"供跑, 不提供 expected（拿不到 label = 设计
        #      如此, 不是缺数据 — 论文"A_train = 与 opining pool 在*无标注*
        #      train 输出上的共识判定的一致度"）
        #   ③ evaluate(split="train") **恒 raise**（无标签判不了分 — 保持
        #      L717 纪律; train 面只能被 "跑+opine", 不能被判分）
        p_train = train_path or TRUTH_SOURCE[2][1]
        self.train_anchors = (self._load_unlabeled(p_train, SPLIT_TRAIN)
                              if os.path.exists(p_train) else None)
        if sealed_path:
            self.sealed = self._load(sealed_path, SPLIT_TEST)
        else:
            p_test = TRUTH_SOURCE[1][1]
            self.sealed = (self._load(p_test, SPLIT_TEST)
                           if os.path.exists(p_test) else None)
        # ★ R330/N2 · fresh 面（同 sealed 纪律：文件在才载，缺席=None；
        #   用到才 raise，不许拿 dev/sealed 顶替 —— 顶替即污染独立验证面）。
        _p_fresh = (fresh_path or os.path.join(
            ROOT, "config", "anchors", "fresh.json"))
        self.fresh = (self._load(_p_fresh, SPLIT_FRESH)
                      if os.path.exists(_p_fresh) else None)
        self._fallbacks: Dict[str, Callable] = {}
        # ★★ 记住每一次判定，用于"未评价不许悄悄变 True"的审计
        self._log: List[Verdict] = []
        # ★★★ C3' · TS3: 逐任务分数序列存储（judge 内部存储 — 设计 §3.1）
        #   ⇒ path 缺省 None = **内存模式**（测试零污染; 生产由 core 注入路径）
        self.store = TaskScoreStore(path=store_path,
                                    evidence_path=evidence_path,
                                    dw_version=dw_version)

    # ── 真值源加载与自检 ──
    @staticmethod
    def _load_unlabeled(path: str, split: str) -> Dict[str, Dict[str, Any]]:
        """★★ R184 · train split 专用装载（无标签大集合 — 论文逐字）。

        ★ 与 _load 的差别只有一条且只有一条: **不要求 golden 字段**
          （无 expected / expected_keywords ⇒ 拿不到 label）。其余全同:
          文件不存在 raise、非 dict raise、条目须 dict。
        ★ 反过来的收紧: 条目若**带了 golden**（expected 出现）⇒ 显式报
          错 — train 面带 label 就变成了第二个 dev（论文"train = 大、
          无标签"; dev/test 才带 anchor）。宁可 raise 不放水。
        ★ _provenance 元数据不算条目。
        """
        if not os.path.exists(path):
            raise JudgeError("train split 文件不存在: %s" % path)
        data = json.loads(io.open(path, encoding="utf-8").read())
        if not isinstance(data, dict) or not data:
            raise JudgeError("train split 为空: %s" % path)
        n = 0
        for tid, rec in data.items():
            if tid.startswith("_"):
                continue
            if not isinstance(rec, dict):
                raise JudgeError("train 条目须 dict: %r" % tid)
            # ★★★ R189-B 补齐的隐藏口径（R189-B 测试抓到的真漏）:
            #   旧版只查**顶层** expected — 但 label 可以藏在 checks[].expected
            #   里（behavior 题的断言级期望）⇒ train 面带 label 而校验看不见。
            #   修法: 顶层 + checks 逐层都查（宁可 raise 不放水）
            _leak = []
            if "expected" in rec or "expected_keywords" in rec:
                _leak.append("顶层 expected/expected_keywords")
            for _c in (rec.get("checks") or []):
                if isinstance(_c, dict) and (
                        "expected" in _c or "expected_keywords" in _c):
                    _leak.append("checks[].expected")
            if _leak:
                raise JudgeError(
                    "train 条目 %r 带了 golden（%s）⇒ 变成第二个 dev —"
                    " 拒（2607.12790: train = 大、无标签）"
                    % (tid, "; ".join(_leak)))
            n += 1
        if not n:
            raise JudgeError("train split 零条目（只有元数据）⇒ 无共识面")
        return data

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
            # ★★★ R199: 第三种判据形态 expected_values（rung3 · 数值容差
            #   比对 — ACTOR_TASK_SOURCE L85-86 逐字: "rung=3 数值容差比对
            #   最强, 有唯一正确答案"）。ARSI 源 reproduce_001-003 即此形态。
            #   ★ 它的"可执行判据"= expected_values + tolerance（**不是**
            #     checks 字段）⇒ checks 必填对它豁免（原则 1 不破: 判据仍
            #     在系统外的文件里且可自动执行）。
            if kind == "expected_values":
                ev = rec.get("expected_values")
                tol = rec.get("tolerance")
                if not isinstance(ev, dict) or not ev:
                    raise JudgeError(
                        "真值源 %s 的 %r 没有 expected_values 判据"
                        " —— 判不了就别混进真值源（原则 1）" % (path, tid))
                if not isinstance(tol, (int, float)) or isinstance(tol, bool) \
                        or tol <= 0:
                    raise JudgeError(
                        "真值源 %s 的 %r 的 tolerance=%r 必须为正数"
                        "（容差比对无容差 = 判据不可执行）" % (path, tid, tol))
                for k, v in ev.items():
                    try:
                        float(v)
                    except (TypeError, ValueError):
                        raise JudgeError(
                            "真值源 %s 的 %r 的 expected_values[%r]=%r 非数值"
                            "（数值容差比对要数值）" % (path, tid, k, v))
                continue                      # ★ 跳过 checks 必填检查
            if kind not in ("behavior", "keyword_match"):
                raise JudgeError(
                    "真值源 %s 的 %r 判据形态 %r 不合法"
                    "（应为 behavior / keyword_match / expected_values）"
                    % (path, tid, kind))
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
                 predicted: Optional[Any] = None, *,
                 split_mode: str = "legacy") -> Verdict:
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
        if split not in (SPLIT_DEV, SPLIT_TEST, SPLIT_FRESH):
            raise JudgeError("split=%r 不在 %r 内" % (split, (SPLIT_DEV,
                                                             SPLIT_TEST,
                                                             SPLIT_FRESH)))
        if split == SPLIT_TEST and self.sealed is None:
            #★★★ test 未落地时必须 raise，不许"用 dev 顶替"
            #   （用 dev 顶替 ⇒ 回归检测形同虚设：分子分母同源）
            raise JudgeError(
                "test split **未落地**（JUDGE_DESIGN §4.5: 必须另建）"
                " ⇒ 不许用 dev 顶替 —— 那会让保护组回归检测形同虚设")
        if split == SPLIT_FRESH and self.fresh is None:
            # ★ R330/N2 · fresh 未落地同样 raise（同 test 纪律 ——
            #   拿 dev/sealed 顶替即污染 Eq.8 独立验证面）。
            raise JudgeError(
                "fresh split **未落地** ⇒ 不许用 dev/sealed 顶替 —— "
                "那会让 Eq.8 独立验证面形同虚设")
        src = {SPLIT_DEV: self.anchors, SPLIT_TEST: self.sealed,
               SPLIT_FRESH: self.fresh}[split]
        cat = {SPLIT_DEV: "dev_anchors", SPLIT_TEST: "test_sealed",
               SPLIT_FRESH: "fresh"}[split]
        if split == SPLIT_TEST and self.sealed is None:
            raise JudgeError(
                "test split **未落地**（JUDGE_DESIGN §4.5: 必须另建）"
                " ⇒ 不许用 dev 顶替")
        if task_id not in src:
            raise JudgeError(
                "task %r 不在 %s split 里（真值源 %s）"
                % (task_id, split, cat))
        golden = src[task_id]

        # ★★★ HCE 标签隐藏（稿⑥§④ · 2603.26499 §3.3「D_search 标签对
        #   agent 隐藏」）: search 模式下 D_val 任务不读反馈 —
        #   success=None 复用「未评价不当 0/1」纪律（隐藏=未评价, 不是失败）
        if split_mode not in ("legacy", "search", "select"):
            raise JudgeError(
                "split_mode=%r 非法（legacy/search/select）" % (split_mode,))
        if split_mode == "search" and split == SPLIT_DEV \
                and task_id in self.d_val:
            v = Verdict(task_id, split, None,
                        "未评价：D_val 标签隐藏 — 搜索期不可读"
                        "（HCE 2603.26499 §3.3 / 稿⑥§④）",
                        cat, "d_val_hidden")
            self._log.append(v)
            return v

        if observed is None:
            v = Verdict(task_id, split, None,
                        "未评价：observed 为 None（根本没跑）",
                        cat, "observed")
            self._log.append(v)
            return v

        # ★★★★ R30: 比较走 _diff（唯一真源）⇒ _compare 与签名同源
        # ★ R277b · envelope 拆包（_build_observations 真执行通道包
        #   {observed, ★_executed}；此处是唯一拆包点 —— _diff/_compare
        #   零改。非 envelope 输入逐字节旧行为）。
        _executed = False
        if isinstance(observed, dict) and "observed" in observed \
                and "★_executed" in observed:
            _executed = bool(observed.get("★_executed"))
            observed = observed.get("observed") or {}
        # ★ R277b-9 · 执行体故障（{error_code} 无 observed）⇒ 未评价
        #   None（R126 原意"该任务弃"；outage 不当失败 —— 否则一次
        #   端点抖动就 6 连 False 触发 collapse 自停，本轮实证）。
        if isinstance(observed, dict) and "observed" not in observed \
                and "error_code" in observed:
            v = Verdict(task_id, split, None,
                        "未评价：执行体故障（%s），不当失败"
                        % (observed.get("error_code"),),
                        cat, "executor_outage")
            self._log.append(v)
            return v
        # ★ R277b-6 · LLM 弃权（全 null 回声 = 模型一个数都没断言）⇒
        #   未评价 None（Verdict 纪律：None 跳过），不当失败。
        #   部分 null 仍正常走 _diff（残疾对子该挂就挂）—— _diff 零改。
        if _executed and isinstance(observed, dict) and observed:
            _vals = [p[1] for pairs in observed.values()
                     if isinstance(pairs, list) for p in pairs
                     if isinstance(p, list) and len(p) == 2]
            if _vals and all(v is None for v in _vals):
                v = Verdict(task_id, split, None,
                            "未评价：LLM 弃权（执行通道全 null 回声，"
                            "无断言值可比）",
                            cat, "llm_abstained")
                self._log.append(v)
                return v
        # ★ R277b-7 · 执行通道开数值宽松（关回默认，防泄漏到规则判分）。
        _NUM_LOOSE[0] = bool(_executed)
        try:
            diffs = self._diff(golden, observed)
        finally:
            _NUM_LOOSE[0] = False
        ok = all(d["ok"] for d in diffs)
        note = ""
        if predicted is not None:
            agree = (bool(predicted) == ok)
            #★ 用条件取值，不在字符串里嵌 %s 再套 %（R24 踩过两次）
            verdict = "一致" if agree else "**不一致**"
            note = "｜agent 自报与实测" + verdict

        sig: Optional[Dict[str, str]] = None
        bad = [d for d in diffs if not d["ok"]]
        if not ok:
            # ★★★ 产出失败签名（c/q 由**规则**分配 —— 2609.06396 原文）
            #   ⇒ 这是**根因修复**: 此前三端都不产签名（judge 不产、
            #     actor 只在异常时产、evolver 只收）⇒ 闭环断
            # ⇒ ★ c = 第一条失败的「verifier 级终止原因」
            # ⇒ ★ q = 由「期望 vs 实测」的**行为模式**推（不按任务/函数 ——
            #     那些属于 m，而 m 按原文归 LLM，第一版留空）
            first = bad[0]
            # ★★ R30: **target 不在三元组里** —— 三元组是聚类语义
            #   （什么失败 / 什么行为 / 什么机制），
            #   而"要改哪个"是**定位**维度 ⇒ 必须显式带 fn
            #   ⇒⇒ 我此前把 fn 塞进 q 位置 ⇒ 「定位碰巧对、语义错」
            fn = first.get("fn") or first.get("kw") or ""
            sig = {"c": classify_c(first.get("expected"),
                                   first.get("actual")),
                   "q": classify_q(first.get("expected"),
                                   first.get("actual")),
                   # ★ 定位维度（非三元组成员，但查询要用）
                   "fn": fn,
                   # ★ 第一版确定性 ⇒ 无 LLM ⇒ m 留空并**显式标注**
                   #   （不许拿规则编一个 m 冒充"模型假设"）
                   # ★ R277b · LLM 时代（envelope 真执行通道）⇒ m = 模型
                   #   断言值（actual 就是 LLM 声称正确的数 —— 不是编的，
                   #   是本轮执行体亲口给的）；规则时代仍 ""。
                   "m": ("llm_asserted:%r" % (first.get("actual"),)
                         if _executed else ""),
                   "q_note": first.get("reason", ""),
                   "n_failed": str(len(bad)),
                   "split": split, "task": task_id}
        # ★★★ R197 · sigs = bad 全量签名（① 数据面改进）
        #   · 主签名（上）保持 R30 原口径 = **首个** notok check —— 不变
        #   · 其余 notok checks 各产一条签名（同构造逻辑, 逐条产）
        #   · 去重（同 (c,q,fn) 多条 check 撞车 = 同签名族, 只留一条）
        #   ⇒ 消费者按需取用; failure_signature 的行为**逐字节不变**
        # ★★★ R199 冒烟抓的真 bug: pass 路径 sig=None ⇒ 原 [sig] 变
        #   [None] — 违反 R197 契约"pass 时 []（不造空签名）"。
      #   实测害处: evidence 的 sigs 长度统计把 pass 算成 1 条（[None]
        #   len=1 ⇒ 污染 drift 信号的簇计数）; Loop 现流程 pass 不进
        #   diagnose 所以没炸 — 但契约就是契约（R197 docstring 逐字
        #   "pass 时 []"）。
        #   ★ R197 测试为何没逮到: `if v2.success:` 守卫 — 那次实测
        #     verdict 恰为 fail ⇒ 断言从未执行（弱断言, G4 族）。
        _sigs: List[Dict[str, str]] = [sig] if sig is not None else []
        if len(bad) > 1:
            _seen = {(sig.get("c"), sig.get("q"), sig.get("fn"))}
            for d in bad[1:]:
                _fn = d.get("fn") or d.get("kw") or ""
                _key = (classify_c(d.get("expected"), d.get("actual")),
                        classify_q(d.get("expected"), d.get("actual")), _fn)
                if _key in _seen:
                    continue
                _seen.add(_key)
                _sigs.append({
                    "c": _key[0], "q": _key[1], "fn": _fn,
                    "m": ("llm_asserted:%r" % (d.get("actual"),)  # ★ R277b
                          if _executed else ""),
                    "q_note": d.get("reason", ""),
                    "n_failed": str(len(bad)), "split": split,
                    "task": task_id})
        v = Verdict(task_id, split, ok,
                    "按 %s 的 golden reference 比较实测%s" % (cat, note),
                    cat,
                    failure_signature=sig,
                    sigs=_sigs,
                    # ★ 逐条差异（判 fail 时**必须**说哪条、差在哪）
                    #   ⇒ 此前 reason 是通用文案 ⇒ 等于没说
                    diffs=[{k: d.get(k) for k in DIFF_FIELDS}
                           for d in bad] if not ok else [],
                    # ★★★★ R54: k/n —— `diffs` 只存**失败**的(成功=[]),
                    #   所以分母必须在**这里**记(手里有全部 `diffs`)
                    #   ⇒ 否则调用方会把「失败数」当「总数」(我第一版就错了)
                    n_checks=len(diffs),
                    k_passed=sum(1 for d in diffs if d.get("ok")))
        self._log.append(v)
        # ★★★★ C3' · 判分点即记录点（TS3 —— score()/外部调用都经这里,
        #   单点全覆盖; 未评价/零分母由 record 内部拒, None 不许冒充 0/1）
        self.store.record(v,
                          group_id=src[task_id].get("category") or "unknown",
                          rung=int(src[task_id].get("verifier_rung") or 0))
        return v

    def held_out_score(self, task_id: str,
                       observed: Optional[Dict[str, Any]]) -> Optional[float]:
        """★ R291-P4 Task 1 · held_out 分数口（读 sealed，不读 dev）。

        success True→1.0 / False→0.0 / None→None（未评价不当 0/1）。
        任务不在 sealed（含 dev 任务）/observed None/判不出 ⇒ None
        （未判，不编分；采不采纳是 accept 门的事，本口只管"判了几分"）。
        ★ locked 纪律：本口只许 accept 门调（测试静态 pin 其余路径）。
        """
        if not isinstance(self.sealed, dict) or task_id not in self.sealed:
            return None
        try:
            v = self.evaluate(task_id, SPLIT_TEST, observed=observed)
        except JudgeError:
            return None
        if v.success is True:
            return 1.0
        if v.success is False:
            return 0.0
        return None

    def cross(self, task_id: str,
              observed: Optional[Dict[str, Any]] = None,
              predicted: Optional[Any] = None) -> Dict[str, Any]:
        """★ D3 · crossed evaluation 单版本内 cross（companion §6.3.3）。

        同 task × 双 split（dev＋sealed）：换 anchor/换模型时对任务集跑
        全集 cross，漂移矩阵＝两次运行 diff。版本间 cross 靠 git 历史＋
        task_scores ledger（旧版可检出重跑 —— 规程见注记，不在本方法内）。
        sealed 未落地/无配对 ⇒ sealed 记 None（诚实缺席，不拿 dev 顶替 ——
        evaluate 同款纪律）。agree＝双非 None 时 dev==sealed。
        """
        _dev = self.evaluate(task_id, SPLIT_DEV, observed=observed,
                             predicted=predicted)
        # ★ D3 · 配对走 held_out_peer 单真源（不手读 pairing 文件）。
        try:
            _sealed_task = self.held_out_peer(task_id)
        except (JudgeError, KeyError, TypeError):
            _sealed_task = None
        _sealed: Optional[bool] = None
        if _sealed_task is not None and self.sealed is not None:
            try:
                _sealed = self.evaluate(
                    _sealed_task, SPLIT_TEST, observed=observed,
                    predicted=predicted).success
            except JudgeError:
                _sealed = None        # noqa: BLE001 — 判不了记缺席
        _d = _dev.success
        return {"task": task_id, "sealed_task": _sealed_task,
                "dev": _d, "sealed": _sealed,
                "agree": ((_d == _sealed)
                          if (_d is not None and _sealed is not None)
                          else None)}

    def held_out_peer(self, task_id: str) -> Optional[str]:
        """★ R291-P4 Task 4 · dev→sealed 配对查询（同族按序号，显式表）。

        表 `config/anchors/dev_sealed_pairing.json`（新文件=增非改）：
        code 前 7＋knowledge 前 3，共 10 对；paper 族/超额无配对⇒None。
        表缺失/坏⇒None（配对是增强非门槛，不抛 —— 门管 blocked）。
        """
        try:
            _p = os.path.join(ROOT, "config", "anchors",
                              "dev_sealed_pairing.json")
            if not os.path.exists(_p):
                return None
            _m = json.loads(io.open(_p, encoding="utf-8").read())
            _peer = _m.get(task_id)
            if not isinstance(_peer, str):
                return None
            if not isinstance(self.sealed, dict) or _peer not in self.sealed:
                return None  # ★ 表里有但 sealed 无 ⇒ 不认（防表漂）
            return _peer
        except Exception:                   # noqa: BLE001 — 表坏不断判分
            return None

    @staticmethod
    def _diff(golden: Dict[str, Any],
              observed: Dict[str, Any]) -> List[Dict[str, Any]]:
        """★ 逐条差异 —— **_compare 的唯一真源**。

        ★★★★ R30: 我原本要「另写一个 diff 版本」给签名用
          ⇒ 但那会让两份比较逻辑各写一遍
          ⇒⇒ ★★ 两份必然漂移（这是评审最常见的真 bug）
          ⇒⇒ ⇒★ 所以: diff 是真源，compare 调它 ⇒ 口径**必然**一致
            compare = not any(未通过的条目)

        ★ 返回每条的: {index, kind, fn, args, expected, actual, ok, reason}
          ⇒ reason 是**c 的原料**（"verifier 拒绝了什么"）
        """
        kind = golden.get("verifier_kind")
        # ★★★ R199: expected_values 分支（rung3）— 观测=答案文本,
        #   解析 key=value 数值对, 逐 key 与 expected 比, |差| <= tolerance
        #   ⇒ 过。缺 key / 非数值 ⇒ fail（fail-closed, 不许判通过）。
        #   ★ 必须在 checks 空判**之前**: 该形态的判据在 expected_values
        #     字段里, 无 checks — 否则会先撞"无 checks ⇒ 不许判通过"。
        #   ★ fn=key 名 ⇒ 失败签名定位维度直接可用（classify_c 同源）。
        if kind == "expected_values":
            text = str(observed.get("answer", observed.get("text", "")))
            tol = float(golden.get("tolerance") or 0.0)
            parsed: Dict[str, float] = {}
            for _m in re.finditer(r"(\w+)\s*=\s*(-?\d+(?:\.\d+)?)", text):
                try:
                    parsed[_m.group(1)] = float(_m.group(2))
                except ValueError:            # 理论不可达（正则已限数值）
                    continue
            out2: List[Dict[str, Any]] = []
            for i, (key, want_raw) in enumerate(
                    sorted((golden.get("expected_values") or {}).items())):
                want = float(want_raw)
                if key not in parsed:
                    out2.append({"index": i, "kind": kind, "fn": key,
                                 "expected": want, "actual": None,
                                 "ok": False,
                                 "reason": "答案里缺 %r= 数值对" % key})
                    continue
                got = parsed[key]
                okk = abs(got - want) <= tol
                out2.append({"index": i, "kind": kind, "fn": key,
                             "expected": want, "actual": got, "ok": okk,
                             "reason": "命中" if okk else
                             "差 %.6g > tolerance %.6g" % (abs(got - want),
                                                           tol)})
            return out2

        checks = golden.get("checks") or []
        if not checks:
            # ★ 没有可执行判据 ⇒ 不许判通过（原则 1）
            return [{"index": -1, "kind": kind, "ok": False,
                     "reason": "无 checks ⇒ 按原则 1 不许判通过"}]

        out: List[Dict[str, Any]] = []
        if kind == "keyword_match":
            text = str(observed.get("answer", observed.get("text", "")))
            for i, c in enumerate(checks):
                kw = c.get("kw")
                hit = (kw in text) if kw else False
                out.append({"index": i, "kind": kind, "kw": kw,
                            "expected": kw, "actual": text[:80] if not hit else kw,
                            "ok": hit,
                            "reason": "关键词 %r 未出现在答案中" % kw
                            if not hit else "命中"})
            return out

        if kind == "behavior":
            for i, c in enumerate(checks):
                fn = c.get("fn")
                want_txt = str(c.get("expected", ""))
                args_txt = str(c.get("args", ""))
                want = _as_literal(want_txt)
                args = _as_literal(args_txt)
                calls = observed.get(fn)
                if calls is None:
                    out.append({"index": i, "kind": kind, "fn": fn,
                                "args": args, "expected": want, "actual": None,
                                "ok": False,
                                "reason": "压根没跑这个函数 %r" % fn})
                    continue
                hit = False
                for call in calls:
                    if not isinstance(call, (list, tuple)) or len(call) < 2:
                        continue
                    if _eq(call[0], args):
                        hit = True
                        if not _eq(call[1], want):
                            out.append({"index": i, "kind": kind, "fn": fn,
                                        "args": args, "expected": want,
                                        "actual": call[1], "ok": False,
                                        "reason": "值不匹配"})
                            break
                        out.append({"index": i, "kind": kind, "fn": fn,
                                    "args": args, "expected": want,
                                    "actual": call[1], "ok": True,
                                    "reason": "命中"})
                        break
                else:
                    # ★ for-else: 没有一条命中这个入参
                    out.append({"index": i, "kind": kind, "fn": fn,
                                "args": args, "expected": want,
                                "actual": None, "ok": False,
                                "reason": "压根没调这个入参 %r" % args})
                if not hit:
                    # 已在上面 add 过（命中但值错 / 没调）
                    if not any(d["index"] == i for d in out):
                        out.append({"index": i, "kind": kind, "fn": fn,
                                    "args": args, "expected": want,
                                    "actual": None, "ok": False,
                                    "reason": "未命中"})
            return out

        # ★ 未知形态 ⇒ 不许判通过（保守）
        return [{"index": -1, "kind": kind, "ok": False,
                 "reason": "未知 verifier_kind %r ⇒ 不许判通过" % kind}]

    @staticmethod
    def _compare(golden: Dict[str, Any],
                 observed: Dict[str, Any]) -> bool:
        """★ 比较口径: 按 verifier_kind 分别处理两种形态。

        ★★★★ R24 实测修正: 初版只按 dict 迭代 checks
          ⇒ 而 dev.json 的 checks 是 **list** ⇒ 直接 AttributeError
          ⇒⇒ ★ 原因: 我写了 _compare 从没喂过真实数据
            ⇒⇒ ⇒★ 这是我自己的老毛病: 「实现了就以为能用」

        ★★★★ R30: 实现改为**委托给 _diff**（不再自己写比较）
          ⇒ 否则 diff 与 compare 两份逻辑必然漂移
          ⇒⇒ 而签名与判定若不同源，会给出矛盾结论

        ★ 两种形态（JUDGE_DESIGN 的判据分流）:
          behavior       —— fn(args) == expected，结构化断言
          keyword_match  —— 答案文本里含 expected_keywords 全部
        ⇒⇒ 而两者都**不许**用 agent 自报当判据（三分离）
        """
        return all(d["ok"] for d in Judge._diff(golden, observed))

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
    # ── ★ C3' · TS3 双查询口（判据原文: 只有聚合没有逐条 = 等于没做）──
    def task_scores(self, split: Optional[str] = None,
                    wm_version: Optional[str] = None):
        """TS3 口①: 逐任务分数序列（第⑦步 / δ_θ 的数据源）。"""
        return self.store.task_scores(split=split, wm_version=wm_version)

    def evidence(self, ref: str) -> Dict[str, Any]:
        """★★ R180: TS3 口③ evidence 委派（store.evidence 的 Judge 面）。

        ★ 补缺口的动因（实测 — 不是发明新面）: R180 Metric Loop 接真数据
          面时发现 Judge 委派了 task_scores 但**没委派 evidence** ⇒
          metric_loop.dev_points_from_store 拿 Judge 用时 evidence(ref)
          全抛 JudgeError（落盘模式下 store._evidence 内存表是空的 —
          证据在 evidence.jsonl 里, record() 的 else 分支才进内存表）
          ⇒ R179 的"点+证据成对"纪律在 Judge 面断了半边。
        ★ 委派 = 同 task_scores 模式的一行（不重载/不改 store 语义）。
        """
        return self.store.evidence(ref)

    def group_scores(self, split: str, round_index: Optional[int] = None):
        """TS3 口②: 按能力组聚合（均值; 无条目组不出现 — 不装 0）。"""
        return self.store.group_scores(split=split, round_index=round_index)

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
        if split not in (SPLIT_DEV, SPLIT_TEST):
            # ★ R330/N2 · task_scores 暂只管 dev/test（fresh 批量另轮）——
            #   不 raise 会静默走 sealed（旧 else 分支），错得无声。
            raise JudgeError("task_scores split=%r 仅支持 dev/test" % (split,))
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
                         current: Dict[str, Any], *,
                         epsilon: float = 0.0) -> Dict[str, Any]:
        """★ 保护组回归检测（终止条件③ 的实现基础）。

        ★★★★ R24 实测修正: 初版用「两侧 not_evaluated 都为 0」当可比条件
          ⇒ 而 dev 有 10 条、只跑 2 条时 not_evaluated=8 ⇒ 永远 not_comparable
          ⇒⇒ ★★ 那是错的判据 —— 保护组回归的本质是**同一批任务**上分数下降，
            不是"全部任务都跑过"
          ⇒⇒⇒ 正确判据: **两边判过的任务集合必须相同**
            （不同 ⇒ not_comparable，因为分子分母不可比）
            （相同 ⇒ 可比，哪怕只覆盖了 20%）

        ★★ 口径（ERROR_AND_TERM §2.3 条件③: r̂ ≤ ε 不满足即触发）:
          ⇒ delta < -ε ⇒ regression；delta ≥ -ε ⇒ ok
          ★ E2（设计稿④ §④ 评估策略层:「回归判据的参数」明列可演化）:
            ε = regression_check 的**策略键** — 默认 0.0 = 现行行为
            （delta<0 同式, 向后兼容零破坏）; ε>0 = 容忍小回退的
            challenger 提案, 走 epoch 点界对拍（challenger_duel）。
          ★ 分层归属: ε 是**策略参数**不是判分执行 — diff 对值比对不受 ε
            影响（锚层不动, 分层表 L-inner/L-mid 之别在这一行实现）。
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
        if not (isinstance(epsilon, (int, float))
                and not isinstance(epsilon, bool) and epsilon >= 0):
            raise JudgeError(
                "★ epsilon 须 ≥0 数值（r̂≤ε 口径 — 负容忍=反向放水非法）, "
                "实为 %r" % (epsilon,))
        eps = b_pass / len(b_ids)
        cur = c_pass / len(c_ids)
        delta = cur - eps
        return {
            # ★ E2 策略键: delta ≥ -ε ⇒ ok（ε=0 ⇒ delta≥0 现行同式零破坏）
            "verdict": "ok" if delta >= -float(epsilon) else "regression",
            "baseline_pass_rate": eps,
            "current_pass_rate": cur,
            "delta": delta,
            "epsilon": float(epsilon),   # ★ 判定所用容忍度（可审计）
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