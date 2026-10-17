# -*- coding: utf-8 -*-
"""R303-① PR级Security Review（对标 Cursor Security Review 轻量版）。

纯规则、零 LLM。只报可利用漏洞六类：SQL/命令/模板注入、鉴权绕过、
密钥入库、SSRF/开放重定向、反序列化、问题依赖。风格质量不管。
宁宽勿严（漏报比误报贵），降噪只做三条：注释行、tests/ 路径、参数化查询。

定位声明（DWC-AUTO · 自我强化）：审执行动作的漏洞 ⇒ 属进化执行侧 DWC-AUTO。
"""
from __future__ import annotations

import re
from typing import Dict, List

# (cls, sev, re) —— 约15条
_RULES = [
    ("SQL注入", "high", r"execute\s*\(\s*[\"'].*%s.*[\"']\s*%\s"),
    ("SQL注入", "high", r"execute\s*\(\s*f[\"'].*SELECT", ),
    ("SQL注入", "high", r"%s.*[\"']\s*%\s+\w+"),
    ("命令注入", "high", r"os\.system\s*\([^)]*\+\s*\w+"),
    ("命令注入", "high", r"subprocess\.\w+\([^)]*shell\s*=\s*True"),
    ("命令注入", "high", r"\beval\s*\(\s*\w+"),
    ("命令注入", "high", r"\bexec\s*\(\s*\w+"),
    ("模板注入", "high", r"render_template_string\s*\([^)]*\+"),
    ("鉴权绕过", "high", r"verify\s*=\s*False"),
    ("鉴权绕过", "medium", r"auth\s*=\s*None"),
    ("密钥入库", "high", r"(api_key|secret|password|passwd|token)\s*=\s*[\"'][A-Za-z0-9\-_]{8,}[\"']"),
    ("密钥入库", "high", r"sk-(live|test)-[A-Za-z0-9]+"),
    ("SSRF", "medium", r"requests\.\w+\(\s*[a-zA-Z_]\w*\s*[,)]"),
    ("SSRF", "medium", r"urlopen\(\s*[a-zA-Z_]\w*\s*[,)]"),
    ("反序列化", "high", r"pickle\.loads?\s*\("),
    ("反序列化", "high", r"yaml\.load\s*\("),
    ("问题依赖", "medium", r"^(?!#)([a-zA-Z0-9_\-]+)\s*$"),
]

_NOISE_COMMENT = re.compile(r"^\s*#")


def review_diff(diff_text: str, path: str = "") -> List[Dict[str, object]]:
    """返回 [{"cls","sev","line","why"}]；无问题 []。永不抛错（坏输入返回 []）。"""
    try:
        lines = str(diff_text).splitlines()
    except Exception:
        return []
    if (path or "").replace("\\", "/").startswith("tests/"):
        return []
    # requirements.txt：只查未 pin 行
    only_pin = (path or "").replace("\\", "/").endswith("requirements.txt")
    out: List[Dict[str, object]] = []
    for i, ln in enumerate(lines, 1):
        if _NOISE_COMMENT.match(ln):
            continue
        s = ln.strip()
        if not s:
            continue
        # 参数化查询降噪：execute(..., (params)) 形跳过 SQL 规则
        parameterized = bool(re.search(r"execute\s*\(.*,", s))
        for cls, sev, pat in _RULES:
            if only_pin and cls != "问题依赖":
                continue
            if not only_pin and cls == "问题依赖":
                continue
            if parameterized and cls == "SQL注入":
                continue
            try:
                rx = re.compile(pat)
            except re.error:
                continue
            if rx.search(ln):
                out.append({"cls": cls, "sev": sev, "line": i, "why": "命中 %s 模式" % cls})
                break
    return out
