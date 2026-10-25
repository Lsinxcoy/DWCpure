"""memory_policy · 条件扩展的显式 feature gate（M3.4）。

定位声明 · **DWC-MEM**（记忆底座）
  ★ 向量/混合检索、MemPO、RL 导航、外部 notebook 默认全部关闭。
  ★ 关闭不是“没实现”，是**没有证据前不许启用**；启用必须走显式开关。

为什么需要
----------
Ultra/Nexus 有 50+ 记忆模块，但多数没有真实消费者。DWC 的纪律是：
没有 hit rate/effect 对照数据，不引向量库、不启 RL、不搬外部 notebook。
本模块只提供可测试的开关，不实现这些重机制。
"""
from __future__ import annotations

FEATURES = {
    "vector_retrieval": False,
    "hybrid_retrieval": False,
    "mempo": False,
    "rl_navigator": False,
    "external_notebook": False,
}


def enabled(name: str) -> bool:
    """未登记/未开启一律 False（fail-closed）。"""
    return bool(FEATURES.get(str(name), False))


def require(name: str) -> None:
    if not enabled(name):
        raise RuntimeError("memory feature disabled: %s" % name)
