"""DWC 实现包 · 定位声明（DWC-MEM · 记忆底座）

★ 本包承载「配置加载与校验 + 七器官 + 三入口」，属记忆底座职责 ⇒ 判据 G1 定位门。
★ 现有层: foundation/ · organs/（七器官全齐）· harness/ · llm/ · core.py（主类）。
★ 主类 DWC 的实现在 dwc.core（ARCHITECTURE §11.2「core.py 器官在此组装」）；
  本文件只做**惰性导出** —— 直接 `from dwc.core import …` 放在包初始化里会把
  全部器官拉进加载链, 在「子模块导入途中」造成循环导入（风险实测存在, 故不用）。
"""
from __future__ import annotations

__all__ = ["DWC"]


def __getattr__(name: str):
    """PEP 562 惰性导出: `from dwc import DWC` 可用, 且不触发循环导入。"""
    if name == "DWC":
        from dwc.core import DWC as _DWC
        return _DWC
    raise AttributeError("module %r has no attribute %r" % (__name__, name))