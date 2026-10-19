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
    """凭据: 环境变量优先, 其次 ~/.dwc_llm_key（仓库外）。绝不写死。"""
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


def get_config():
    return {
        "api_url": os.environ.get("DWC_LLM_API_URL", "https://opencode.ai/zen/go/v1/chat/completions"),
        "model": os.environ.get("DWC_LLM_MODEL", "minimax-m2.5"),
        "api_key": _load_key(),
        "max_tokens": int(os.environ.get("DWC_LLM_MAX_TOKENS", "2000")),
        "timeout": int(os.environ.get("DWC_LLM_TIMEOUT", "120")),
    }


def call_llm(system_prompt, user_prompt, max_tokens=None):
    """Call LLM with retry. Returns content string or ''."""
    cfg = get_config()
    url = cfg["api_url"]
    model = cfg["model"]
    key = cfg["api_key"]
    if not key:
        note_miss("缺 DWC_LLM_API_KEY 且无 ~/.dwc_llm_key")
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
