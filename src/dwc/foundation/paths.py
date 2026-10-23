"""R228 · 路径真源（发布级: 新机器可装 — 不再写死 E:/ 与用户名）。

★★★ 定位（G1）: **DWC-AUTO** —— 路径发现的单一实现。
★★★ TRUTH_SOURCE: 无判定面（纯定位）。

★ 发现序（头部 agent 惯例: 环境变量 > 位置推导）:
  ① DWC_ROOT 环境变量（显式指定; 覆盖一切）
  ② 从本文件向上找标志（config/dials.yaml + src/dwc 同时在 ⇒ 仓库根）
  ③ 都失败 ⇒ Dw cRootError 大声报错（不猜不装有 — G7 同族）

★ hermes 依赖集中（飞书通知读 Hermes 配置 — 用户名从 env 取, 不写死）:
  hermes_config_path() = %LOCALAPPDATA%/hermes/config.yaml
"""
from __future__ import annotations

import os

#: 仓库根的判定标志（必须同时存在 — 单标志会被子目录误认）
_FLAGS = ("config", "src")


class DwcRootError(Exception):
    pass


def find_root(start: str | None = None) -> str:
    """★ 仓库根发现（唯一实现 — src 与 scripts 都用它）。"""
    env = os.environ.get("DWC_ROOT", "").strip()
    if env:
        if os.path.isdir(env):
            return os.path.abspath(env)
        raise DwcRootError("DWC_ROOT=%r 不是目录（显式指定必须有效）" % env)
    cur = os.path.abspath(start or os.path.dirname(os.path.abspath(__file__)))
    while True:
        if (all(os.path.isdir(os.path.join(cur, d)) for d in _FLAGS)
                and os.path.isdir(os.path.join(cur, "src", "dwc"))):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            raise DwcRootError(
                "找不到 DWC 仓库根（从 %s 向上无标志 config/+src/dwc/）——"
                "设 DWC_ROOT 环境变量或在仓库内运行" % (start or __file__))
        cur = parent


def hermes_config_path() -> str | None:
    """Hermes 配置（飞书通知用 — LOCALAPPDATA 从 env, 不写死用户名）。"""
    base = os.environ.get("LOCALAPPDATA", "")
    if not base:
        return None
    p = os.path.join(base, "hermes", "config.yaml")
    return p if os.path.exists(p) else None
