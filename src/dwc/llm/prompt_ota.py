"""R306 · prompt OTA loader：版本化基线文件 + 缓存 + 灰度 + 缺失降级。

定位: DWC-AUTO（自我强化 · 提示词版本治理：基线收归文件＋灰度可回滚）。
真值源=仓库 prompts/ 目录；缺文件/坏输入一律返 None（调用方走内嵌老路，
判分语义零改）。纯规则零 LLM。
"""
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional

_CACHE: Dict[str, Optional[str]] = {}
_OTA_MISS = [0]  # ★ G7 · OTA 降级计数（可观测，不静默）


def note_miss() -> int:
    """OTA 未命中/异常计数＋1，返当前值。永不抛错。"""
    try:
        _OTA_MISS[0] += 1
        return _OTA_MISS[0]
    except Exception:
        return -1


def miss_count() -> int:
    try:
        return _OTA_MISS[0]
    except Exception:
        return -1


def _ver(name: str, manifest: Dict[str, Any], key: str) -> Optional[str]:
    try:
        m = (manifest or {}).get(name, {}) or {}
    except Exception:
        return None
    stable, cand, pct = m.get("stable"), m.get("candidate"), m.get("pct", 0)
    try:
        if cand and pct and key:
            h = int(hashlib.md5(key.encode("utf-8")).hexdigest(), 16) % 100
            if h < int(pct):
                return cand
    except Exception:
        note_miss()
    return stable


def get_prompt(name: str, *, root=None, manifest=None, key: str = "",
               append: str = "") -> Optional[str]:
    try:
        if not name or root is None:
            return None
        ver = _ver(name, manifest or {}, key or "")
        if not ver:
            return None
        ck = "%s|%s|%s" % (Path(root).as_posix(), name, ver)
        if ck not in _CACHE:
            p = Path(root) / ("%s.%s.md" % (name, ver))
            try:
                _CACHE[ck] = p.read_text(encoding="utf-8")
            except Exception:
                # 灰度候选缺失⇒回 stable（append-only，不抛错）
                if ver != (manifest or {}).get(name, {}).get("stable"):
                    st = (manifest or {}).get(name, {}).get("stable")
                    try:
                        _CACHE[ck] = (Path(root) / ("%s.%s.md" % (name, st))
                                      ).read_text(encoding="utf-8")
                    except Exception:
                        _CACHE[ck] = None
                else:
                    _CACHE[ck] = None
        base = _CACHE.get(ck)
        if base is None:
            return None
        if (append or "").strip():
            return base + "\n\n" + append.strip()
        return base
    except Exception:
        return None


def with_fallback(name: str, inline: str, *, root=None, manifest=None,
                  key: str = "") -> str:
    """命中文件基线则用之，否则原样返内嵌串（老路零变）。永不抛错。"""
    try:
        t = get_prompt(name, root=root, manifest=manifest, key=key or "")
        return t if isinstance(t, str) and t else inline
    except Exception:
        return inline


def prompts_root(start_file: str):
    """从调用文件向上找 prompts/ 目录；找不到返 None。永不抛错。"""
    try:
        import os as _os
        d = _os.path.dirname(_os.path.abspath(start_file or ""))
        for _ in range(7):
            if _os.path.isdir(_os.path.join(d, "prompts")):
                return _os.path.join(d, "prompts")
            nd = _os.path.dirname(d)
            if nd == d:
                break
            d = nd
        return None
    except Exception:
        return None


def ota_system(name: str, inline: str, caller_file: str,
               key: str = "") -> str:
    """一站式：找根＋读 manifest＋with_fallback。全失败返内嵌。永不抛错。"""
    try:
        import json as _js
        import os as _os
        proot = prompts_root(caller_file)
        if not proot:
            return inline
        try:
            with open(_os.path.join(proot, "manifest.json"),
                      encoding="utf-8") as _fh:
                mf = _js.load(_fh)
        except Exception:
            mf = {}
        return with_fallback(name, inline, root=proot, manifest=mf, key=key)
    except Exception:
        return inline
