# -*- coding: utf-8 -*-
"""能力注册表：读 config/capabilities.yaml，开关查询。纯规则零 LLM。

定位: DWC-AUTO（自我强化 · 能力治理：有名＋开关＋可审计）。
语义：未知名/坏文件⇒默认启用（fail-open，老路零变）；永不抛错。
"""
from typing import Any, Dict

_TABLE: Dict[str, Any] = {}
_LOADED = [""]


def _default_path() -> str:
    try:
        import os as _os
        env = (_os.environ.get("DWC_CAPS_PATH") or "").strip()
        if env and _os.path.isfile(env):
            return env
        d = _os.path.dirname(_os.path.abspath(__file__))
        for _ in range(5):
            c = _os.path.join(d, "config", "capabilities.yaml")
            if _os.path.isfile(c):
                return c
            nd = _os.path.dirname(d)
            if nd == d:
                break
            d = nd
    except Exception:
        return ""
    return ""


def load_table(path: str = "") -> Dict[str, Any]:
    """读 yaml 返 caps 表；失败返 {}。永不抛错。"""
    try:
        import os as _os
        p = path or _default_path()
        if not p or not _os.path.isfile(p):
            return {}
        try:
            import yaml as _yaml
        except Exception:
            return {}
        with open(p, encoding="utf-8") as _fh:
            doc = _yaml.safe_load(_fh)
        caps = (doc or {}).get("caps", {}) or {}
        return caps if isinstance(caps, dict) else {}
    except Exception:
        return {}


def is_enabled(name: str, path: str = "") -> bool:
    """开关查询：未知名/坏文件⇒True。永不抛错。"""
    try:
        if not name:
            return True
        if name == "final":
            return True
        if path:
            t = load_table(path)
        else:
            global _TABLE
            if _LOADED[0] != "y":
                _TABLE = load_table()
                _LOADED[0] = "y"
            t = _TABLE
        ent = (t or {}).get(name)
        if not isinstance(ent, dict):
            return True
        v = ent.get("enabled", True)
        return False if v is False else True
    except Exception:
        return True


def reload() -> None:
    """清缓存（测试/改配置后用）。永不抛错。"""
    global _TABLE
    _TABLE = {}
    _LOADED[0] = ""


def disabled_list(path: str = "") -> list:
    """关掉的能力名列表（给 R304 健康报告消费）。永不抛错。"""
    try:
        t = load_table(path) if path else load_table(_default_path())
        return sorted(k for k, v in (t or {}).items()
                      if isinstance(v, dict) and v.get("enabled") is False)
    except Exception:
        return []


def cap_limit(name: str, key: str, default, path: str = ""):
    """★ R309-① · 数值项（超时/TTL）：yaml 缺省回 default。永不抛错。

    ★ R438 · 先看进化产物 `config/subagent_policy.json`（subagent 维度）：
      delegate 的超时可以被进化改写，且**不必重启**（每次读文件 + mtime 缓存
      在 evo_targets 里）。产物坏 ⇒ 回落到 yaml/default，并留痕。
    """
    if name == "delegate":
        try:
            import os as _os
            from dwc.organs import evo_targets as _ET
            if _os.path.isfile(_ET.path_of("subagent")):
                _ov = _ET.read("subagent")
                if key in _ov:
                    return _ov[key]
        except Exception as _e:  # noqa: BLE001 — 产物坏不拦调用，但留痕
            import sys as _s
            _s.stderr.write("subagent 策略覆盖读取失败: %r\n" % (_e,))
    try:
        t = load_table(path) if path else (
            _TABLE if _LOADED[0] == "y" else load_table())
        ent = (t or {}).get(name)
        if not isinstance(ent, dict):
            return default
        v = ent.get(key, default)
        return v if isinstance(v, (int, float)) else default
    except Exception:
        return default
