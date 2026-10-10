# -*- coding: utf-8 -*-
"""dimension · 九维分类 + 三维声明校验（2606.14249 HarnessX §3.3 · V2 §4.2）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 服务环节②（对象）的**分类与查重面**: V2 原文用法"每个新增模块必
    须声明 dimension ∈ {D1..D9}, hook ∈ 八 hook, singleton_group" ——
    把"重复检测"从**语义理解**变成**属性冲突检测**（不需要读模块说
    什么, 只看它声明什么）。
  ★ 不抢位: 不实现具体模块（vocab/hook 各自独立）; 本模块只定义九维
    值枚举 + 三元组声明 + 冲突判定规则。
  ★ 与 hook.py 的合补: R145 落了 hook；本模块把 (dimension, hook,
    group) 三元组收口（三者同出处 — Table 1/§3.3 同一段论文原文）。

★★★ TRUTH_SOURCE（判据 G2）
  冲突判定只针对**声明属性**（同名/同位/同组抢位）—— 不判"模块逻辑
  是否重复"（那是语义面, 交给四量/人工; 属性查重是机械可判的底线)。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Tuple

#: 九维（HarnessX §3.3 原文 — 与 ARSI c1-c9 同构, DEDUP_AUDIT 已实测）
DIMENSIONS: Tuple[str, ...] = (
    ("D1", "model_selection", "模型选择"),
    ("D2", "context_assembly", "上下文组装"),
    ("D3", "memory_management", "记忆管理"),
    ("D4", "tool_ecosystem", "工具生态"),
    ("D5", "execution_env", "执行环境"),
    ("D6", "evaluation", "评估"),
    ("D7", "control_safety", "控制/安全"),
    ("D8", "observability", "可观测"),
    ("D9", "training_bridge", "训练桥"),
)

#: 维度 id 集合（值枚举 — 未知维度显式拒绝, 不猜）
DIMENSION_IDS: Tuple[str, ...] = tuple(d[0] for d in DIMENSIONS)


class DimensionError(Exception):
    """维度声明/冲突判定的显式拒绝（未知维度/三元组不全/同位同组冲突）。"""


@dataclass(frozen=True)
class ModuleDeclaration:
    """一个模块的**三维声明**（V2 原文口径: 每个新增模块必须声明）。

    ★ dimension ∈ DIMENSION_IDS（未知 ⇒ DimensionError — 拼写不宽容）;
      hook 名与 group 只做**非空 + 形式**校验（真枚举在 hook.HOOKS —
        跨模块复用不重抄, 引用它的校验见 declares_valid_hook()）。
    """

    module: str
    dimension: str
    hook: str
    singleton_group: str

    def __post_init__(self) -> None:
        if not self.module:
            raise DimensionError("module 名须非空")
        if self.dimension not in DIMENSION_IDS:
            raise DimensionError(
                "dimension 未知: %r（九维枚举外不猜: %s）"
                % (self.dimension, "/".join(DIMENSION_IDS)))
        if not self.hook:
            raise DimensionError("hook 须非空（八 hook 名 — 由 hook.HOOKS 收口）")
        if not self.singleton_group:
            raise DimensionError("singleton_group 须非空（互斥语义载体）")

    def as_dict(self) -> Dict[str, Any]:
        label = dict((d[0], d[2]) for d in DIMENSIONS)[self.dimension]
        return {"module": self.module, "dimension": self.dimension,
                "dimension_label": label,
                "hook": self.hook, "singleton_group": self.singleton_group}


def declares_valid_hook(decl: ModuleDeclaration, valid_hooks: Iterable[str]
                        ) -> bool:
    """★ 跨模块 hook 名校验（不重抄 HOOKS — 调用方传 hook.HOOKS 进来）。

    ★ 复用原则: hook 枚举的唯一真源是 hook.HOOKS; 本模块只做"声明里
      的 hook 名在不在调用方给的集合里"（重复定义枚举 = 两份真相）。
    """
    return decl.hook in set(valid_hooks)


def find_conflicts(decls: Iterable[ModuleDeclaration]) -> Dict[str, Any]:
    """★★ 属性冲突检测（把语义查重降成机械判定）。

    三类冲突（逐条有论文依据）:
      ① duplicate_module —— 同名模块重复声明（注册表主键冲突）
      ② duplicate_dimension_hook —— 同 (dimension, hook) 上两个模块
         且 singleton_group 相同 ⇒ **同位同组抢位**（V2 §4.2 的冲突形态:
         两个模块都想当同一维度同一钩子点的唯一处理器）
      ③ 单独同 group 不同 dimension ⇒ 不算冲突（组是跨维复用面 — 如
         "记忆底座"组被 D3 与 D1 都消费是设计允许, 论文只禁同组同钩子点）
    """
    items: List[ModuleDeclaration] = list(decls)
    conflicts: List[Dict[str, Any]] = []

    # ① 同名重复
    seen_mod: Dict[str, int] = {}
    for d in items:
        seen_mod[d.module] = seen_mod.get(d.module, 0) + 1
    for m, c in seen_mod.items():
        if c > 1:
            conflicts.append({"kind": "duplicate_module", "module": m,
                              "count": c,
                              "note": "同名模块重复声明（注册表主键冲突）"})

    # ② 同位同组（dimension ∧ hook ∧ group 三元全同才是抢位）
    triples: Dict[Tuple[str, str, str], List[str]] = {}
    for d in items:
        k = (d.dimension, d.hook, d.singleton_group)
        triples.setdefault(k, []).append(d.module)
    for (dim, hk, grp), mods in triples.items():
        if len(mods) > 1:
            conflicts.append({
                "kind": "duplicate_dimension_hook", "dimension": dim,
                "hook": hk, "singleton_group": grp, "modules": sorted(mods),
                "note": "同维度同 hook 点同互斥组 ⇒ 抢位（V2 §4.2 原文"
                        "冲突形态: 属性可判, 不需语义理解）"})

    # ③ 宽松面（跨维复用组）— 记录但**不算冲突**（论文不禁 — 防误伤）
    group_dims: Dict[str, set] = {}
    for d in items:
        group_dims.setdefault(d.singleton_group, set()).add(d.dimension)
    cross_dim_reuse = {g: sorted(ds) for g, ds in group_dims.items()
                       if len(ds) > 1}

    return {"n_declared": len(items), "conflicts": conflicts,
            "n_conflicts": len(conflicts),
            "ok": not conflicts,
            "cross_dimension_group_reuse": cross_dim_reuse,
            "note": ("cross_dimension_group_reuse 是**允许**的（组跨维复用"
                     " — 论文只禁同组同 hook 点抢位）")}


def dimension_index(decls: Iterable[ModuleDeclaration]) -> Dict[str, Any]:
    """九维索引（每个维度下挂了哪些模块 — 覆盖/空缺一目了然）。"""
    idx: Dict[str, List[str]] = {d: [] for d in DIMENSION_IDS}
    for d in decls:
        idx[d.dimension].append(d.module)
    return {"index": idx,
            "coverage": {d: len(idx[d]) for d in DIMENSION_IDS},
            "empty_dimensions": [d for d in DIMENSION_IDS if not idx[d]],
            "labels": {d[0]: d[2] for d in DIMENSIONS}}


DIMENSION_MECHANICS: Dict[str, str] = {
    "nine_dims": "HarnessX §3.3 D1-D9（与 ARSI c1-c9 同构 — DEDUP_AUDIT 实测）",
    "triple_declare": "V2 §4.2: 每模块声明 (dimension, hook, singleton_group)",
    "conflict_kinds": "重名 / 同位同组抢位（跨维复用组不算冲突）",
    "semantic_to_mechanical": "重复检测从语义理解降为属性冲突检测（原文用法）",
    "hook_enum_single_source": "hook 枚举唯一真源是 hook.HOOKS（本模块不重抄）",
}
