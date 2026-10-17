# -*- coding: utf-8 -*-
"""DWC 机制目录（R303-③）：只读加载 config/mechanisms.yaml。
只读校验器（capability_groups.py 纪律）：校验失败 raise，绝不静默降级。"""
from __future__ import annotations

import importlib
from typing import Any, Dict, Optional

import yaml

from dwc.foundation.paths import find_root


def load(root: Optional[str] = None) -> Dict[str, dict]:
    """读 <root>/config/mechanisms.yaml → {name: 条目}。缺文件/坏格式 raise。"""
    r = root or str(find_root())
    import os
    p = os.path.join(r, "config", "mechanisms.yaml")
    with open(p, encoding="utf-8") as f:
        items = yaml.safe_load(f)
    if not isinstance(items, list) or not items:
        raise ValueError("mechanisms.yaml 为空或非列表: %s" % p)
    reg: Dict[str, dict] = {}
    for it in items:
        if not isinstance(it, dict) or not it.get("name") or not it.get("entry"):
            raise ValueError("机制条目缺 name/entry: %r" % (it,))
        reg[it["name"]] = it
    return reg


def is_enabled(reg: Dict[str, dict], name: str) -> bool:
    """未登记一律 False（默认关，不假设）。"""
    it = reg.get(name)
    return bool(it and it.get("enabled"))


def call(reg: Dict[str, dict], name: str, *args: Any, **kw: Any) -> Any:
    """按 entry "module:func" 动态调。未登记/禁用 raise KeyError（大声报错）。"""
    it = reg.get(name)
    if it is None or not it.get("enabled"):
        raise KeyError("机制未登记或未启用: %s" % name)
    mod_name, _, func_name = it["entry"].partition(":")
    if not mod_name or not func_name:
        raise KeyError("机制 entry 非 module:func 形: %r" % (it["entry"],))
    mod = importlib.import_module(mod_name)
    return getattr(mod, func_name)(*args, **kw)
