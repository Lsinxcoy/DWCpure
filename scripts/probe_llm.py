# -*- coding: utf-8 -*-
"""R34 · LLM 真实端点自检（**用户配了 key 才会发请求**）。

═══════════════════════════════════════════════════════════
 ★★★ 为什么这个脚本单独存在（而不是写进测试）
   测试里的 14 条**全是 mock**（本地 HTTP server / 假对象）
   ⇒⇒ 它们证明的是**协议与纪律**（降级路径、凭证护栏、证据字段）
     **不等于**"真实端点能用"
   ⇒⇒ ⇒★ 而真端点要花钱、要有 key ⇒ 不该进默认测试
     （否则 CI/他人克隆会因缺 key 而红 —— 那是**测试污染**）
   ⇒ ⇒★ 所以: 真端点验证是**显式动作**，由你跑
═══════════════════════════════════════════════════════════

用法:
    # ① 环境变量方式
    set DWC_LLM_BASE_URL=https://api.openai.com/v1
    set DWC_LLM_API_KEY=sk-...
    set DWC_LLM_MODEL=gpt-4o-mini
    python scripts/probe_llm.py

    # ② 只想看"配没配"，不发请求
    python scripts/probe_llm.py --dry

退出码: 0 = 真通 · 1 = 未配置/失败
"""
from __future__ import annotations

import argparse
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from dwc.llm import LLMClient  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="DWC LLM 端点自检")
    ap.add_argument("--dry", action="store_true",
                    help="只报告配置状态，**不发请求**")
    ap.add_argument("--json", action="store_true", help="机器可读输出")
    args = ap.parse_args()

    c = LLMClient()
    out = {
        "configured": c.configured,
        "model": c._model,          # ★ model 名可看（不是凭证）
        "host": c._host_only(),     # ★ 只 host（不含 key、不含路径）
        "timeout": c.timeout,
        "unavailable_reason": c.unavailable_reason,
    }
    if args.dry:
        out["mode"] = "dry"
        out["★"] = "未发任何请求"
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 0 if c.configured else 1

    if not c.configured:
        out["mode"] = "live"
        out["result"] = "not_configured"
        out["★"] = ("要真跑请配 %s / %s / %s"
                    % ("DWC_LLM_BASE_URL", "DWC_LLM_API_KEY",
                       "DWC_LLM_MODEL"))
        print(json.dumps(out, ensure_ascii=False, indent=1))
        return 1

    # ★ 真发一次（小 token，省配额）
    r = c.complete("Return the single word: ok", max_tokens=16)
    out.update({
        "mode": "live",
        "ok": r.ok,
        "source": r.source,
        "error": r.error,
        "text_head": r.text[:80],
        "degraded": r.degraded,
        "stats": c.stats(),
    })
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0 if r.ok else 1


if __name__ == "__main__":
    sys.exit(main())
