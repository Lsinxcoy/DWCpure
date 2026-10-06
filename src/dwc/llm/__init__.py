# -*- coding: utf-8 -*-
"""DWC · LLM 接入层（R34 新增）。

定位声明 · **DWC-AUTO**（自我强化）—— 详见 client.py 顶部。
★ 本包不含记忆读写（不是 DWC-MEM），也不替代任何已有模块。
"""
from .client import LLMClient, LLMResult

__all__ = ["LLMClient", "LLMResult"]
