"""失败 obs 错误码（R310-④ · 抄 Capy {error:{code,message}}）。

定位: DWC-AUTO（自我强化 · 可观测）。只增 code 字段，message 原样。
"""

#: 码 → 说明（聚合查询只认码，不解析中文串）。
CODES: dict[str, str] = {
    "CAP_DISABLED": "能力被 capabilities.yaml 关闭",
    "DELEGATE_TIMEOUT": "子代理超 timeout_s 熔断",
    "DELEGATE_DEPTH": "子代理内再 delegate（深度上限）",
    "MCP_DOWN": "MCP server 探活不通",
    "MCP_TOOL_MISSING": "工具不在该 server 工具表",
    "LLM_BAD_JSON": "LLM 输出非 JSON/缺字段",
    "LLM_CALL_FAIL": "LLM 调用失败（超时/断连/配额）",
    "RUN_TIMEOUT": "run 命令超 60s",
    "ASK_DENIED": "人工审批被拒/未授权",
    "UNKNOWN_OP": "未知 op（不在白名单）",
}


def err(code: str, message: str) -> dict[str, str]:
    """组失败 obs：ok＋code＋error。永不抛错。"""
    try:
        c = code if code in CODES else "UNKNOWN_OP"
        return {"ok": False, "code": c, "error": message}
    except Exception:
        return {"ok": False, "code": "UNKNOWN_OP", "error": message}
