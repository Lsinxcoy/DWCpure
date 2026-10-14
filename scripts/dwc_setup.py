# -*- coding: utf-8 -*-
"""R229 · 首次配置向导（头部 agent 惯例: goose configure / opencode auth login）。

★★★ 定位（G1）: **DWC-AUTO** —— 新使用者的三步引导。
★★★ TRUTH_SOURCE: 无判定面 —— 只写配置（llm.json 等）+ 冒烟验证。
★★★ 安全: key 用 getpass 遮蔽输入, **不回显不打印**（落 config/llm.json）。

★ 流程: ① LLM 端点/key（写 config/llm.json）→ ② 通知渠道（可选飞书/跳过）
       → ③ 冒烟（LLM probe + 模块导入 + 配置校验器）→ ④ 结果报告
★ 非交互: --yes 走默认值（CI/测试用）; --check 只跑冒烟不写配置。
"""
from __future__ import annotations

import getpass
import io
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))
from dwc.foundation.paths import find_root                    # noqa: E402

ROOT = find_root()
LLM_JSON = os.path.join(ROOT, "config", "llm.json")


def _ask(prompt, default=""):
    try:
        v = input("%s%s: " % (prompt, "（回车=%s）" % default if default else "")
                  ).strip()
        return v or default
    except EOFError:
        return default


def step_llm(non_interactive: bool) -> bool:
    """① LLM 端点 + key（遮蔽输入; 写 config/llm.json）。"""
    print("\n── ① LLM 通道 ──")
    cur = {}
    if os.path.exists(LLM_JSON):
        try:
            cur = json.load(io.open(LLM_JSON, encoding="utf-8"))
            print("  已有配置: base=%s model=%s（回车保留）"
                  % (cur.get("base_url", "?"), cur.get("model", "?")))
        except (ValueError, OSError):
            print("  旧 llm.json 坏了 — 将重建")
    if non_interactive:
        base = cur.get("base_url", "")
        model = cur.get("model", "")
        key = cur.get("api_key", "")
    else:
        base = _ask("  OpenAI 兼容端点 base_url", cur.get(
            "base_url", "https://api.openai.com/v1"))
        model = _ask("  模型名", cur.get("model", "gpt-4o-mini"))
        key = getpass.getpass("  API key（遮蔽输入, 不回显）: ").strip()
        if not key:
            key = cur.get("api_key", "")
            print("  （留空=沿用旧 key）" if key else "  （无 key — 冒烟将报未配置）")
    if not base:
        print("  ✗ 缺 base_url"); return False
    cfg = {"base_url": base, "model": model, "api_key": key}
    os.makedirs(os.path.dirname(LLM_JSON), exist_ok=True)
    with io.open(LLM_JSON, "w", encoding="utf-8") as fh:
        json.dump(cfg, fh, ensure_ascii=False, indent=1)
    try:
        os.chmod(LLM_JSON, 0o600)          # 凭据文件收紧权限（POSIX 生效）
    except OSError:
        pass
    print("  ✓ 已写 config/llm.json（key 不回显; 文件权限 600）")
    return True


def step_notify(non_interactive: bool) -> None:
    """② 通知渠道（可选 — 跳过不影响核心功能）。"""
    print("\n── ② 飞书通知（可选, 回车跳过）──")
    if non_interactive:
        print("  跳过（非交互模式）"); return
    want = _ask("  配置飞书通知? (y/N)", "N")
    if want.lower() != "y":
        print("  跳过 — 之后可用 RPC doctor 检查, 或手动编辑通知配置"); return
    # 复用 Hermes feishu 配置（本机已有 ⇒ 直接提示检测结果）
    from dwc.foundation.paths import hermes_config_path
    hp = hermes_config_path()
    if hp:
        print("  检测到本机 Hermes 飞书配置 — agent 任务结果将经它推送。")
    else:
        print("  未检测到 Hermes 配置 — 通知将不可用（核心功能不受影响）。")


def step_smoke() -> bool:
    """③ 冒烟: 模块导入 + 配置校验器 + LLM probe（真实一发小请求）。"""
    print("\n── ③ 冒烟自检 ──")
    ok = True
    try:
        from dwc.foundation import dial_config
        dial_config.load_world_tree(); dial_config.load_drift()
        print("  配置校验器: OK")
    except Exception as exc:                    # noqa: BLE001
        print("  ✗ 配置校验: %s: %s" % (type(exc).__name__, exc)); ok = False
    try:
        from dwc.llm.client import LLMClient
        r = LLMClient().probe()
        # ★ 修(2026-10-14 用户实测): probe 返回 **LLMResult 对象**不是 dict —
        #   原 r.get("ms") 直接 AttributeError("没有 attribute 'get'")被
        #   except 兜成"probe 异常"（冒烟从未真跑通过）。字段: ok/error/meta,
        #   **无 ms**（耗时不存在 ⇒ 不显示 — 如实）。
        print("  LLM probe: %s" % ("OK" if r.ok else "未通过 — %s" % r.error))
        ok = ok and bool(r.ok)
    except Exception as exc:                    # noqa: BLE001
        print("  ✗ LLM probe 异常: %s" % exc); ok = False
    return ok


def main() -> int:
    non_interactive = "--yes" in sys.argv
    check_only = "--check" in sys.argv
    print("DWC 首次配置向导（key 全程遮蔽不回显）")
    if check_only:
        return 0 if step_smoke() else 1
    if not step_llm(non_interactive):
        return 1
    step_notify(non_interactive)
    smoke_ok = step_smoke()
    print("\n── ④ 完成 ──")
    print("  配置: config/llm.json ✓" if smoke_ok else "  冒烟未全过 — 修好后跑: dwc_setup --check")
    print("  下一步: python scripts/dwc_cli.py doctor  →  dwc_chat.py 或 dwc_agent.py --llm")
    return 0 if smoke_ok else 1


if __name__ == "__main__":
    sys.exit(main())
