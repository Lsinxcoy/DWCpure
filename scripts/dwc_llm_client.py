# -*- coding: utf-8 -*-
"""LLM client with configurable model and endpoint."""
import json, os, re, urllib.request, uuid

#: 静默门留痕（G7）：调用失败/缺凭据都记这里，不 `pass`
_MISS = {"n": 0, "last": ""}


def note_miss(why):
    _MISS["n"] += 1
    _MISS["last"] = str(why)[:300]


def miss_count():
    return _MISS["n"]


def _load_key():
    """★ 历史兜底凭据（~/.dwc_llm_key）。

    ★★ 2026-10-19 起 **不再是主源**：统一配置改为 `config/llm.json`
      （与 `src/dwc/llm/client.py` 同一份）。这里只在
      「环境变量没给 且 config/llm.json 没 key」时才被调用。
    """
    k = os.environ.get("DWC_LLM_API_KEY", "").strip()
    if k:
        return k
    path = os.path.join(os.path.expanduser("~"), ".dwc_llm_key")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return f.read().strip()
        except OSError as e:
            note_miss("读 ~/.dwc_llm_key 失败: %s" % e)
    return ""


#: ★★★ 统一配置源（唯一真源）: `config/llm.json`
#:   `src/dwc/llm/client.py` 与 本脚本 读的是**同一个文件** ——
#:   2026-10-19 之前两套配置各走各的（AMD/MiMo vs opencode/minimax），
#:   模型/key/端点全不同 ⇒ 排障时无法判断「是哪个模型的问题」。
_CFG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "config", "llm.json")


def _shared() -> dict:
    """读统一配置。文件缺失/坏掉 ⇒ {} 并留痕（不抛 —— 没配是常态）。"""
    try:
        with open(_CFG_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except OSError:
        return {}
    except ValueError as e:
        note_miss("config/llm.json 解析失败: %s" % e)
        return {}
    return data if isinstance(data, dict) else {}


def _api_url(base: str) -> str:
    """base_url → chat/completions 全 URL（已带后缀则不重复拼）。"""
    b = (base or "").strip().rstrip("/")
    if not b:
        return ""
    return b if b.endswith("/chat/completions") else b + "/chat/completions"


def get_config():
    """★ 优先级: 环境变量 > config/llm.json > ~/.dwc_llm_key（仅 key 兜底）。

    ★★ 不再有硬编码端点/模型兜底 —— 缺配置就 `note_miss` + 返回空，
      不偷偷指向一个可能已死的端点（那是「降级与成功不可区分」）。
    """
    s = _shared()
    base = (os.environ.get("DWC_LLM_API_URL")
            or os.environ.get("DWC_LLM_BASE_URL")
            or s.get("base_url") or "")
    return {
        "api_url": _api_url(base),
        "model": os.environ.get("DWC_LLM_MODEL") or s.get("model") or "",
        "api_key": (os.environ.get("DWC_LLM_API_KEY")
                    or s.get("api_key") or _load_key()),
        "max_tokens": int(os.environ.get("DWC_LLM_MAX_TOKENS")
                          or s.get("max_tokens") or 2000),
        "timeout": int(os.environ.get("DWC_LLM_TIMEOUT")
                       or s.get("timeout") or 120),
    }


def call_llm(system_prompt, user_prompt, max_tokens=None):
    """Call LLM with retry. Returns content string or ''."""
    cfg = get_config()
    url = cfg["api_url"]
    model = cfg["model"]
    key = cfg["api_key"]
    if not url or not model:
        note_miss("LLM 配置不全（config/llm.json 缺 base_url 或 model）"
                  " — 不偷偷回落到硬编码端点")
        return ""
    if not key:
        note_miss("缺 DWC_LLM_API_KEY / config/llm.json 的 api_key")
        return ""
    mt = max_tokens or cfg["max_tokens"]
    for attempt in range(5):
        body = {
            "model": model,
            "max_tokens": mt,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key}",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "x-opencode-session": str(uuid.uuid4()),
        })
        try:
            with urllib.request.urlopen(req, timeout=cfg["timeout"]) as resp:
                data = json.loads(resp.read())
            if "choices" in data:
                msg = data["choices"][0]["message"]
                content = msg.get("content")
                if content:
                    return content
                rc = msg.get("reasoning_content")
                if rc:
                    return rc
                rs = msg.get("reasoning")
                if rs:
                    return rs
        except (OSError, ValueError) as e:
            note_miss("attempt %d: %s: %s" % (attempt + 1, type(e).__name__, e))
    return ""


def parse_json(text):
    """Extract JSON from LLM response. Returns dict or None."""
    text = (text or "").strip()
    if not text:
        return None
    m = re.search(r'```(?:json)?\s*\n(.*?)\n```', text, re.DOTALL)
    if m:
        text = m.group(1).strip()
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            text = text[start:end+1]
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError) as e:
        note_miss("parse_json: %s" % e)
        return None
