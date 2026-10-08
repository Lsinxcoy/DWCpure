# -*- coding: utf-8 -*-
"""weakness · 残差难度 δ_θ（器官⑥ 探索 · 2609.04128 §2.1）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 服务环节⑥ 探索（往哪探索的难度排序偏置），不碰记忆读写 ⇒ 非 DWC-MEM。
  ★ 不抢位: 不声明 REPLACES（weakness.py 是 EVOLUTION_CORE_V2 ⑥ search/
    组件树里点名的新文件, 不替代谁）。

★★★ TRUTH_SOURCE（判据 G2: 含判定能力的模块必须声明）
  本模块**不产生**成功判定 —— history 序列由调用方从 judge 判分结果投影
  （TaskScorePoint 的 z 投影）; δ 是频率计算, 不是自评。

=== 路线裁决（ARCHITECTURE §4.7 ② · docs/RESIDUAL_DIFFICULTY §三）===
  论文原式 δ_θ = [d_θ − d_𝒯]₊（2609.04128 §2.1），DWC **两项都不可得**:
    · p_θ 需要 logits —— DWC actor 走云端 LLM API（§4.2）**物理上拿不到**
      ⇒ 省掉 p_θ 是必然, 不是取舍（ARCHITECTURE L1096-1099）
    · p_𝒯 需要外部知识源（deep-research 代理）—— 引入=扩判据面, 不划算
  ⇒ ★★ 裁决走**路线丙（组内基线）**:
       δ_θ^group(z|g,j) = [ −log r_group(z|g,j) ]₊，Laplace k=1
       r_group = (n_z + 1) / (n_group + 1)   （ARCHITECTURE 实测例 −log(12/55)）
  ★ 实测与论文**同序不同值** ⇒ ⇒ 只可作**排序偏置**, 不可混用绝对阈值
    （ARCHITECTURE L1105 —— 本模块不提供任何"阈值判定"接口, 与此一致）。

=== X 判据落点 ===
  X1 semantics 必填无默认（config/difficulty.yaml → load_difficulty 已校验;
     本模块的 Difficulty 再校验一次 —— 双保险, 同 Z4「检查不可关」两层守）
  X2 n_obs=0 ⇒ delta=**NaN**（"没观测过" ≠ "观测到频率0"）·
     config 的 zero_means:"NaN" 由 load_difficulty 把关
  X3 semantics=world_knowledge（路线甲）⇒ delta_group **raise** ——
     没有写掩码之外的 deep-research 代理就不假装能算（诚实边界②）
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence

from dwc.foundation.dial_config import load_difficulty

#: 系统外真值源（G2）
TRUTH_SOURCE = {
    "声明": "本模块不自判: history 由调用方从 judge 判分结果投影注入",
    "真值源位置": "dwc.organs.judge.TRUTH_SOURCE（config/anchors/dev.json）",
    "自判禁止": "δ 是组内观测频率的负对数（−log r_group），不含任何自评分；"
                "只输出排序偏置, 无阈值判定接口",
}

#: X1 语义枚举（与 dial_config.SEMANTICS 同值 —— 两处必须同源）
SEMANTICS = ("group_baseline", "world_knowledge")


class WeaknessError(Exception):
    """难度语义的违规必须大声报错（G7 静默门同族）。"""


@dataclass(frozen=True)
class Difficulty:
    """残差难度。★ 两种语义共用此类型, 由 semantics 区分（§3.2 原文）。

    ★ semantics / n_obs **必填无默认** —— G11 certification_limit /
      K4 editable 同款纪律: 同一字段两义事后不可解释; n=0 与"频率0"
      数值上不可区分 ⇒ 必须显式分开（X1/X2）。
    """

    delta: float
    semantics: str
    z_id: str
    group_id: str
    n_obs: int
    estimated_at: str

    def __post_init__(self) -> None:
        if self.semantics not in SEMANTICS:
            raise WeaknessError(
                "X1: semantics=%r 不在 %s 内（★ 值枚举, 别写字段名）"
                % (self.semantics, list(SEMANTICS)))
        if isinstance(self.n_obs, bool) or not isinstance(self.n_obs, int) \
                or self.n_obs < 0:
            raise WeaknessError(
                "n_obs 须为 ≥0 整数（0 ⇒ delta=NaN 的判据要靠它）, 实得 %r"
                % (self.n_obs,))


class DifficultyEstimator:
    """路线丙估计器: 组内基线稀有度（替代 p_𝒯）。

    ★ history: group_id -> 该组观测到的 z 序列（TaskScorePoint 的 z 投影）。
      ★★ 诚实边界: 真实数据链的 TaskScorePoint 落盘（TASK_SCORE_TRACKING
        TS3 查询口）**未做** ⇒ 当前唯一注入源是测试; 生产接线待 TS3。
    ★ semantics 读 config/difficulty.yaml（load_difficulty 已过 X1/X2/X3）。
    """

    def __init__(self, history: Mapping[str, Sequence[str]],
                 config_path: Optional[str] = None):
        cfg_all = (load_difficulty(config_path) if config_path
                   else load_difficulty())
        self.cfg = cfg_all["difficulty"]
        self.semantics: str = self.cfg["semantics"]   # X1 已在加载器校验
        #: 组 → z 序列（复制一层, 防调用方事后改列表污染估计）
        self._hist: Dict[str, List[str]] = {
            g: list(zs) for g, zs in history.items()}
        #: X4 报告字段的一致来源（门报告的 delta_semantics 从这里取）
        self.report_field = self.cfg["report_field"]

    def delta_group(self, z_id: str, group_id: str) -> Difficulty:
        """δ_θ^group = [ −log r ]₊ · r = (n_z + 1)/(n + 1)（Laplace k=1）。

        ★ [·]₊ 对本式恒等（r ≤ 1 ⇒ −log r ≥ 0）—— 保留是**忠实公式形状**
          + 防御（Laplace 之后若有人改分母规则, 截断仍按原式兜住）。
        ★ n（组内观测数）= 0 ⇒ delta = NaN（X2 —— 没观测过 ≠ 频率0）。
        ★ semantics=world_knowledge ⇒ raise（X3: 路线甲无代理不假装能算）。
        """
        if self.semantics != "group_baseline":
            raise WeaknessError(
                "路线甲（world_knowledge）未实现: 需要**写掩码之外**的 "
                "deep-research 代理, DWC 当前没有 ⇒ 不假装能算"
                "（difficulty.yaml 诚实边界②）")
        zs = self._hist.get(group_id, [])
        n = len(zs)
        n_z = zs.count(z_id)
        if n == 0:
            delta = math.nan                     # X2: 未观测 ⇒ NaN
        else:
            r = (n_z + 1.0) / (n + 1.0)
            delta = max(-math.log(r), 0.0)       # [·]₊ 按原式保留
        return Difficulty(delta=delta, semantics="group_baseline",
                          z_id=z_id, group_id=group_id, n_obs=n,
                          estimated_at=time.strftime("%Y-%m-%dT%H:%M:%S"))

    def delta_trajectory(self, z_seq: Sequence[str],
                         group_id: str) -> float:
        """Δ_θ(ξ) = Σ_t δ_θ(z_t)（2609.04128 原式, 轨迹和）。

        ★ 任一 z 的 n_obs=0（NaN）⇒ 整条 Δ 返回 NaN —— 不吞不跳
          （"没观测过"的轨迹不该有假精确的总分）。
        """
        total = 0.0
        for z in z_seq:
            d = self.delta_group(z, group_id)
            if math.isnan(d.delta):
                return math.nan
            total += d.delta
        return total

    def weak_ranking(self, group_id: str) -> List[Dict[str, object]]:
        """★ 组内 z 的稀有度排序（降序）—— 落点就是「只可作排序偏置」:
        不给阈值, 只给顺序（ARCHITECTURE L1105 的用法约束）。
        """
        zs = sorted(set(self._hist.get(group_id, [])))
        out = [{"z_id": z, "delta": self.delta_group(z, group_id).delta,
                "n_obs": len(self._hist[group_id])} for z in zs]
        return sorted(out, key=lambda d: (-d["delta"], d["z_id"]))


# ══════════════════════════════════════════════════════════
# 诚实边界（R69 的范围, 别把「能算」当「接上了」）
# ══════════════════════════════════════════════════════════
# ★ 已做: 路线丙 δ_θ^group + Δ_θ 轨迹和 + 排序偏置口 · X1 双保险 · X2 NaN
#         · X3 路线甲 raise · config 读取（load_difficulty 的 X1/X2/X3 已在）
# ★ 未做（下轮/依赖裁决）:
#   · **生产数据链**: TaskScorePoint 落盘（TASK_SCORE_TRACKING TS3 查询口）
#     未做 ⇒ 当前 history 只能由调用方手工注入（唯一调用方=测试）
#   · **z 的统一操作化**: z_id 语义由调用方定（候选: 失败签名族 (c,q) /
#     category）—— 本模块不锁, 因为设计文档没锁（RESIDUAL 也只写"稳定 id"）
#   · **接进收束**: select 加 δ_θ 偏置会动 W4（"收束只吃信息增益"已定判据）
#     ⇒ 需设计裁决, 不顺手改
#   · EL 调度器（B=8 τ=6/8）与三方向枚举 —— 器官⑥的其余两件
# ★ 路线丙的语义是"罕见于本组"而非"罕见于世界"（RESIDUAL §2.1 路线丙代价）
#   —— 语义变窄是裁决的一部分, 不是实现走样。
# ★ Laplace k=1 的 (n_z+1)/(n+1) 与 ARCHITECTURE 实测例 −log(12/55) 同构
#   （n=54, n_z=11 ⇒ 12/55）—— 数值已用测试锁死; 未与第二人复核。
