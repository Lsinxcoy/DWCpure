# -*- coding: utf-8 -*-
"""calibration · ECE 期望校准误差度量（R140 · 深水待办最后一项）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 服务环节⑤ 防漂移的**质检端度量**: 度量 iwm 自报 trust 的**校准
    度**（说了 0.8 的信任, 实际是否真有 0.8 的改进率）—— 补 iwm.py
     L351 自陈"ECE 过置信惩罚未做"的欠账（唯一真欠账, R136 盘点坐实）。
  ★ 不抢位: 不声明 REPLACES; **不碰 Advice 四字段契约**
    （ORGAN_INTERFACES §六原文四字段 — iwm.self_trust() 的 trust 输出
     就是现成置信代理, R140 只消费不改接口 ⇒ B 方案, 不与设计稿冲突）。

★★★ TRUTH_SOURCE（判据 G2）
  本模块**不产生**任何成功判定 — conf/outcome 序列由调用方注入
  （iwm.record_round 的两臂历史投影; 成功率 = 改进轮/总轮, 不含
  自评）; ECE 是**分布距离度量**, 不是"是否成功"的判断。

=== 论文口径（ECE 经典定义, 无需外部论文即可推导）===
  ECE = Σ_b (n_b/N) · |acc(b) − conf(b)|
    · 按 conf（信任值）分 b 桶 · acc(b)=桶内实际改进率 · conf(b)=桶内
      平均信任值 · 桶空则跳过（不静默计 0 — X 纪律: 缺席≠0）。
  与 iwm 的 trust 的关系: trust 是**单点置信**（iwm 臂改进率）;
    ECE 度量的是"信任值作为预测器"的校准度 —— 信任 0.8 而实际改进
    率 0.5 ⇒ 过置信 ⇒ ECE=0.3。
  ★ 分桶数/桶边界由 CALIBRATION_BINS 给（默认 10 等宽, 与文献同款
    无量纲 — 不引入新超参语义）; n_bins ≤ max_bins 显式拒绝（防过拟合
    小样本）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

#: 分桶口径（默认 10 等宽 [0,1] — ECE 文献标准口径）
CALIBRATION_BINS: int = 10
#: 单桶最少样本（低于此该桶不参与 — 防 1/1=100% 的过拟合噪声）
MIN_BIN_COUNT: int = 1
#: 最大分桶数（超过 ⇒ DialError 式显式拒绝 — ECE 不是玄学调参）
MAX_BINS: int = 50


class CalibrationError(Exception):
    """ECE 计算的显式拒绝（空序列/非数值/分桶非法）。"""


@dataclass(frozen=True)
class CalibrationPoint:
    """一个校准观测: 预测置信 conf + 实际结果 outcome。

    ★ conf 须在 [0,1]（值域枚举; 0/1 也合法 — 不是"开放区间"）;
      outcome 只有二值 True/False（bool 显式 — 不接受 0/1 int 混入,
      X1 同族: 同一字段两义事后不可解释）。
    """

    conf: float
    outcome: bool

    def __post_init__(self) -> None:
        c = self.conf
        if isinstance(c, bool) or not isinstance(c, (int, float)) \
                or math.isnan(c) or math.isinf(c):
            raise CalibrationError("conf 须为有限数值, 实为 %r" % (c,))
        if not (0.0 <= float(c) <= 1.0):
            raise CalibrationError(
                "conf 须在 [0,1]（置信是概率）, 实为 %r" % (c,))
        if not isinstance(self.outcome, bool):
            raise CalibrationError(
                "outcome 须为 bool（改进/未改进, 不接受 int 混入）, "
                "实为 %r" % (self.outcome,))


def expected_calibration_error(points: Sequence[CalibrationPoint], *,
                               n_bins: int = CALIBRATION_BINS,
                               min_bin_count: int = MIN_BIN_COUNT
                               ) -> Dict[str, Any]:
    """★ ECE = Σ (n_b/N)|acc(b)−conf(b)|（经典定义, 见模块头口径）。

    ★ 缺席≠0（X2 纪律）: 空桶跳过不计项; 少于 min_bin_count 的桶
      同样跳过（1/1=100% 是噪声不是校准证据）。
    ★ 空序列 ⇒ CalibrationError（不是 0.0 — "没数据"≠"完美校准"）。
    ★ 单调性自检: ECE ≥ 0 且 ≤ 1（每项 |acc−conf| ∈[0,1], 权重和 1）。
    """
    if not isinstance(n_bins, int) or isinstance(n_bins, bool) \
            or n_bins < 1 or n_bins > MAX_BINS:
        raise CalibrationError(
            "n_bins 须为 1..%d 整数, 实为 %r" % (MAX_BINS, n_bins))
    if not isinstance(min_bin_count, int) or isinstance(min_bin_count, bool) \
            or min_bin_count < 1:
        raise CalibrationError(
            "min_bin_count 须为 ≥1 整数, 实为 %r" % (min_bin_count,))
    pts = list(points)
    if not pts:
        raise CalibrationError("空序列 ⇒ ECE 不可计算（没数据≠校准好）")

    n_total = len(pts)
    bins: List[List[CalibrationPoint]] = [[] for _ in range(n_bins)]
    for p in pts:
        # 边界语义: conf=1.0 归最末桶（等宽右闭）
        idx = min(int(p.conf * n_bins), n_bins - 1)
        bins[idx].append(p)

    buckets: List[Dict[str, Any]] = []
    ece = 0.0
    used = 0
    for b in bins:
        if len(b) < min_bin_count:
            continue                      # ★ 缺席/低样本桶跳过（不静默计 0）
        n_b = len(b)
        acc_b = sum(1 for p in b if p.outcome) / n_b
        conf_b = sum(p.conf for p in b) / n_b
        gap = abs(acc_b - conf_b)
        ece += (n_b / n_total) * gap
        used += 1
        buckets.append({"n": n_b, "acc": acc_b, "conf": conf_b,
                        "gap": gap, "weight": n_b / n_total})

    # ★ 单调性自检（结构断言, 不是测试专属 — 调用方拿到的 ECE 必有界）
    if not (0.0 <= ece <= 1.0 + 1e-12):
        raise CalibrationError(
            "ECE 越界 [0,1]: %r（实现缺陷, 不是输入问题）" % (ece,))
    return {"ece": ece, "n_total": n_total, "n_bins_used": used,
            "n_bins_requested": n_bins,
            "buckets": buckets,
            "note": ("%d/%d 桶参与（空前/min_bin_count 跳过）"
                     % (used, n_bins))}


def from_trust_history(trust_series: Sequence[Tuple[float, bool]]
                       ) -> List[CalibrationPoint]:
    """★ iwm 两臂历史的投影入口: (trust, improved) 序列 ⇒ 校准点。

    TRUTH_SOURCE 落点: trust/improved 都来自调用方（iwm.record_round
    的 (adopted, improved) 与 iwm.self_trust() 的 trust 输出）—— 本函
    函数只做形态转换, 不改写数值。
    ★ 二值强制: improved 须 bool（iwm 语义就是 bool — 见 Point 契约;
      **不静默 bool() 转换**: int 1/0 混入会被 Point 的契约拒绝 ⇒ 显式
      失败而非悄悄当真）。
    """
    out: List[CalibrationPoint] = []
    for t, imp in trust_series:
        out.append(CalibrationPoint(conf=float(t), outcome=imp))
    return out


def overconfidence_penalty(ece_result: Dict[str, Any], *,
                           threshold: float = 0.1) -> Dict[str, Any]:
    """★ iwm 自陈"ECE 过置信惩罚未做"的落地件 — 对 degrade 决策的**输入
    侧补一个校准维度**（不改 Advice 四字段契约, 不进 governor_advice
    签名 — 调用方自愿消费）。

    规则（显式管理口径, 不是论文报值）: ECE > threshold ⇒
    penalty=True + 建议把 trust 打折 (1−ECE)（过置信 ⇒ 信任缩水）;
    ECE ≤ threshold ⇒ penalty=False（校准良好, 不动 trust）。
    ★ threshold 默认 0.1 = 管理口径（文献常用 0.05/0.1 区间, DWC 取
      保守端 ⇒ CALIBRATION 标注来源, 不冒充论文值）。
    """
    if not (0.0 <= threshold <= 1.0):
        raise CalibrationError("threshold 须在 [0,1], 实为 %r" % (threshold,))
    ece = float(ece_result["ece"])
    penalized = ece > threshold
    return {"penalized": penalized, "ece": ece, "threshold": threshold,
            "trust_scale": (1.0 - ece) if penalized else 1.0,
            "note": ("ECE=%.3f > %.2f ⇒ 过置信, trust 建议 ×%.3f"
                     % (ece, threshold, (1.0 - ece) if penalized else 1.0))
            if penalized else
            ("ECE=%.3f ≤ %.2f ⇒ 校准良好, trust 不动"
             % (ece, threshold))}


CALIBRATION: Dict[str, str] = {
    "ece_definition": "ECE=Σ(n_b/N)|acc−conf| 经典定义（分桶加权差）",
    "bins_default": "10 等宽（文献标准口径, 无量纲 — 非新超参语义）",
    "penalty_threshold": "0.1 = 管理口径（文献 0.05/0.1 区间保守端, 非论文报值）",
    "trust_source": "iwm.self_trust() 输出的 trust（单点置信代理, 不碰 Advice 契约）",
    "route_decision": "B 方案: ECE 建在 iwm 外侧的独立度量（R140 裁决记录）",
}
