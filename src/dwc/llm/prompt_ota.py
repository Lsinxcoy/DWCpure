"""R306 · prompt OTA loader：版本化基线文件 + 缓存 + 灰度 + 缺失降级。

定位: DWC-AUTO（自我强化 · 提示词版本治理：基线收归文件＋灰度可回滚）。
真值源=仓库 prompts/ 目录；缺文件/坏输入一律返 None（调用方走内嵌老路，
判分语义零改）。纯规则零 LLM。
"""
import hashlib
from pathlib import Path
from typing import Any

_CACHE: dict[str, str | None] = {}
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


def render(name: str, fields: dict[str, Any], *, root=None, manifest=None,
           key: str = "", remote: str = "") -> str | None:
    """模板渲染：@@field@@ 占位直换。缺模板/缺字段⇒None（调用方走老路）。
    永不抛错；降级一律 note_miss 计数。"""
    import re as _re
    try:
        base = get_prompt(name, root=root, manifest=manifest, key=key or "",
                          remote=remote or "")
        if not base:
            note_miss()
            return None
        slots = set(_re.findall(r"@@([A-Za-z0-9_]+)@@", base))
        fields = fields or {}
        if any(s not in fields or fields[s] is None for s in slots):
            note_miss()
            return None
        out = base
        for s in slots:
            out = out.replace("@@" + s + "@@", str(fields[s]))
        return out.rstrip("\n")
    except Exception:
        note_miss()
        return None


def fetch_remote(base_url: str, name: str, ver: str,
                 timeout: float = 3.0) -> str | None:
    """从远端 prompts 源取基线（如本地 bootstrap 服务）。
    任何失败⇒None（调用方走本地文件/内嵌老路）。永不抛错。"""
    import re as _re
    import urllib.request as _ul
    try:
        if not base_url or not name or not ver:
            return None
        if not _re.fullmatch(r"[A-Za-z0-9_]+", name):
            note_miss()
            return None
        if not _re.fullmatch(r"[A-Za-z0-9_.-]+", ver):
            note_miss()
            return None
        url = base_url.rstrip("/") + "/%s.%s.md" % (name, ver)
        req = _ul.Request(url, method="GET",
                          headers={"User-Agent": "dwc-prompt-ota/1"})
        to = max(0.5, min(10.0, timeout or 3.0))
        with _ul.urlopen(req, timeout=to) as _resp:
            if getattr(_resp, "status", 200) != 200:
                note_miss()
                return None
            data = _resp.read(1 << 20)
        try:
            return data.decode("utf-8")
        except Exception:
            note_miss()
            return None
    except Exception:
        note_miss()
        return None


def render_here(name: str, fields: dict[str, Any], caller_file: str,
                key: str = "", remote: str = "") -> str | None:
    """一站式渲染：找根＋读 manifest＋render。全失败返 None。永不抛错。"""
    try:
        import json as _js
        import os as _os
        proot = prompts_root(caller_file)
        if not proot:
            note_miss()
            return None
        try:
            with open(_os.path.join(proot, "manifest.json"),
                      encoding="utf-8") as _fh:
                mf = _js.load(_fh)
        except Exception:
            mf = {}
        return render(name, fields, root=proot, manifest=mf, key=key or "",
                      remote=remote or "")
    except Exception:
        note_miss()
        return None


#: ★★★ R434 · A/B 实验用的"钉版本"文件（`var/prompt_force.json`）。
#: 生产默认不存在；只在跑提示词 A/B 时由 `scripts/dwc_prompt_ab.py` 写入，
#: 跑完删除。缓存按 mtime 失效 —— 改一次文件立刻生效，不用重启 agent。
_FORCE = {"mtime": None, "map": {}}


def _force_path() -> str:
    """钉版本文件路径：env 优先，否则**按本文件定位仓库根**（不依赖 cwd）。

    ★ 用 cwd 会踩坑：拉活脚本的 cwd 可能是 Temp，agent 的 cwd 才是仓库根 ——
      同一个相对路径在两个进程里指向不同文件。
    """
    import os as _os
    env = (_os.environ.get("DWC_PROMPT_FORCE_FILE") or "").strip()
    if env:
        return env
    try:
        here = _os.path.dirname(_os.path.abspath(__file__))      # src/dwc/llm
        root = _os.path.dirname(_os.path.dirname(_os.path.dirname(here)))
        return _os.path.join(root, "var", "prompt_force.json")
    except Exception:
        return _os.path.join("var", "prompt_force.json")


def _forced(name: str) -> str | None:
    """读钉版本表；没有文件/坏文件 ⇒ None（走 manifest 灰度）。

    ★ 坏文件不静默：计数 + 当没钉（宁可跑灰度，不可把实验条件当生产）。
    """
    import json as _js
    import os as _os
    p = _force_path()
    try:
        st = _os.stat(p)
    except OSError:
        return None
    if _FORCE.get("mtime") == st.st_mtime_ns:
        return (_FORCE.get("map") or {}).get(name)
    try:
        raw = open(p, encoding="utf-8").read()
        m = _js.loads(raw)
        if not isinstance(m, dict):
            raise ValueError("force file 必须是 {name: ver}")
        _FORCE["map"] = {str(k): str(v) for k, v in m.items() if v}
        _FORCE["mtime"] = st.st_mtime_ns
    except Exception:
        note_miss()
        return None
    return (_FORCE.get("map") or {}).get(name)


def _ver(name: str, manifest: dict[str, Any], key: str) -> str | None:
    # ★ R434 · 钉版本优先（A/B 归因需要"同题两臂"）
    try:
        f = _forced(name)
        if f:
            return f
    except Exception:
        note_miss()
    try:
        m = (manifest or {}).get(name, {}) or {}
    except Exception:
        return None
    stable, cand, pct = m.get("stable"), m.get("candidate"), m.get("pct", 0)
    try:
        if cand and pct and key:
            h = int(hashlib.sha256(key.encode("utf-8")).hexdigest(), 16) % 100
            if h < int(pct):
                return cand
    except Exception:
        note_miss()
    return stable


def get_prompt(name: str, *, root=None, manifest=None, key: str = "",
               append: str = "", remote: str = "") -> str | None:
    try:
        if not name or root is None:
            return None
        ver = _ver(name, manifest or {}, key or "")
        if not ver:
            return None
        base_url = (remote or "").strip()
        if not base_url:
            try:
                import os as _os
                base_url = (_os.environ.get("DWC_PROMPT_URL") or "").strip()
            except Exception:
                base_url = ""
        ck = "%s|%s|%s|%s" % (base_url, Path(root).as_posix(), name, ver)
        if ck not in _CACHE:
            _CACHE[ck] = None
            if base_url:  # ★ R308 · 远端优先（bootstrap 语义），失败落本地
                _CACHE[ck] = fetch_remote(base_url, name, ver)
            if _CACHE[ck] is None:
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
                  key: str = "", remote: str = "") -> str:
    """命中文件基线则用之，否则原样返内嵌串（老路零变）。永不抛错。"""
    try:
        t = get_prompt(name, root=root, manifest=manifest, key=key or "",
                       remote=remote or "")
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
               key: str = "", remote: str = "") -> str:
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
        return with_fallback(name, inline, root=proot, manifest=mf, key=key,
                             remote=remote or "")
    except Exception:
        return inline
