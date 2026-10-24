# -*- coding: utf-8 -*-
"""R439 · P0-a · token 记账与成本折算。

★★★ 定位（G1）: **DWC-AUTO** —— 自我强化的度量层：没有成本数据，就没有第二个目标函数。

为什么要有这个模块
------------------
v2 计划的第一条结论：**DWC 只有一个目标函数（过不过），没有第二个（花多少钱）**。
没有成本数据，P1-b 的双目标 fitness、P2 的选档、P3 的 Pareto 全都无从比较。

三条纪律（与计划 §2 对齐）
--------------------------
1. **无 usage ⇒ None，不猜 0** —— 0 会被下游当成"免费"，把"不知道"伪装成"知道"。
2. **模型不在价目表 ⇒ cost_usd=None，但 tokens 照记** ——
   不许拿别的模型的价格兜底（那是编造）。
3. **落盘失败不许掀翻 LLM 调用** —— 但要往 stderr 留痕（G7：不许静默吞异常）。

价目表从哪来
------------
`config/llm.json` 的可选 `pricing` 段：

    "pricing": {
      "deepseek-v4.1-flash": {"input": 0.5, "cached_input": 0.1, "output": 2.0}
    }

单位：**美元 / 1M token**。没配这一段 ⇒ cost_usd=None，token 照记
（P0-0 用 token 总量当成本代理，同一模型下与金额单调等价）。
"""
from __future__ import annotations

import io
import json
import os
import sys
import contextlib
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

#: 记账文件名（落在 var/ 下）
USAGE_REL = "llm_usage.jsonl"

#: 价目单位：每 1M token 的美元数
_PER = 1_000_000.0


@dataclass(frozen=True)
class Usage:
    """一次调用的 token 用量。三个数都是**服务端报的**，不是我们估的。"""

    prompt_tokens: int
    completion_tokens: int
    cached_tokens: int = 0

    def as_dict(self) -> Dict[str, int]:
        return {"prompt_tokens": self.prompt_tokens,
                "completion_tokens": self.completion_tokens,
                "cached_tokens": self.cached_tokens}


def _non_neg_int(v: Any) -> Optional[int]:
    """严格非负整数。bool 是 int 的子类 —— 必须排除（True 不是 1 个 token）。"""
    if isinstance(v, bool):
        return None
    if isinstance(v, int) and v >= 0:
        return v
    return None


def parse_usage(u: Any) -> Optional[Usage]:
    """解析**usage 对象本身**（`response["usage"]`）。

    缺失 / 畸形 / 负数 ⇒ None（**不猜**）。
    `prompt_tokens_details` 缺失 ⇒ cached=0（这是"确实没命中"，不是"不知道"）；
    但若它存在却是坏形状 ⇒ None（坏数据不能当成本）。
    """
    if not isinstance(u, dict):
        return None
    p = _non_neg_int(u.get("prompt_tokens"))
    c = _non_neg_int(u.get("completion_tokens"))
    if p is None or c is None:
        return None
    det = u.get("prompt_tokens_details")
    cached = 0
    if det is not None:
        if not isinstance(det, dict):
            return None
        cached = _non_neg_int(det.get("cached_tokens", 0))
        if cached is None:
            return None
    return Usage(prompt_tokens=p, completion_tokens=c, cached_tokens=cached)


def from_response(data: Any) -> Optional[Usage]:
    """从**完整响应体**里取 usage 再解析。没有 usage 段 ⇒ None。"""
    if not isinstance(data, dict):
        return None
    return parse_usage(data.get("usage"))


def cost_usd(model: str, usage: Usage,
             pricing: Optional[Dict[str, Any]]) -> Optional[float]:
    """按三档价目折算美元。未知模型 / 价目坏 ⇒ None（**不许 0 兜底**）。

    三档：未缓存输入、缓存输入、输出。缓存价通常比未缓存低一个数量级，
    所以两者必须分开算（HarnessPro 与 Cache Engineering 两篇独立论文都这么做）。
    """
    if not isinstance(pricing, dict) or not isinstance(model, str):
        return None
    p = pricing.get(model)
    if not isinstance(p, dict):
        return None
    try:
        in_rate = float(p["input"])
        out_rate = float(p["output"])
        cached_rate = float(p.get("cached_input", in_rate))
    except (KeyError, TypeError, ValueError):
        return None

    # 坏数据防御：cached 不能超过 prompt（否则会算出负的未缓存部分）
    cached = min(max(0, usage.cached_tokens), max(0, usage.prompt_tokens))
    uncached = max(0, usage.prompt_tokens - cached)
    total = (uncached * in_rate + cached * cached_rate
             + max(0, usage.completion_tokens) * out_rate)
    return total / _PER


def _config_path() -> str:
    """`config/llm.json` 的绝对路径（与 client._load_file_config 同一份文件）。"""
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(root, "config", "llm.json")


def load_pricing(path: Optional[str] = None) -> Dict[str, Any]:
    """读价目表。文件缺失 / 坏 / 没有 pricing 段 ⇒ {}（**没配是常态**）。

    注意：这里不经过 client 的白名单（那个白名单只收标量字符串，
    pricing 是嵌套 dict，混进去会被 str() 毁掉）。
    """
    try:
        with io.open(path or _config_path(), encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    p = data.get("pricing")
    return p if isinstance(p, dict) else {}


# ── 任务标签（R442 · 成本归因）──────────────────────────
#: 线程本地：同进程里任务串行执行，线程本地足够；子任务继承父任务的标签。
_TAG = threading.local()


def set_tag(tag: str) -> None:
    """给当前线程设任务标签（后续调用都记到它名下）。"""
    _TAG.value = str(tag or "")


def clear_tag() -> None:
    """清掉标签（任务结束）。没有标签的调用**不归因到任何任务**。"""
    _TAG.value = ""


def current_tag() -> str:
    return str(getattr(_TAG, "value", "") or "")


# ★ R447 · 档位标签（与 tag 同构：线程本地，任务期间有效）。
#   为什么要单独一列而不是拼进 tag：拼进去会毁掉按 task_id 的聚合。
_PROFILE = threading.local()


def set_profile(name: str) -> None:
    """给当前线程设档位名（后续调用都记到它名下）。"""
    _PROFILE.value = str(name or "")


def clear_profile() -> None:
    _PROFILE.value = ""


def current_profile() -> str:
    return str(getattr(_PROFILE, "value", "") or "")


@contextlib.contextmanager
def attribution(tag: Optional[str] = None, profile: Optional[str] = None):
    """★ R450 · 把"这次调用属于谁"圈进 with 块，**进出必还原**。

    为什么必须还原：起草一轮会连着调多次 LLM，异常一旦漏标签，
    下一次调用就会记到上一个任务名下 —— 归因数据会被污染且看不出来。
    None 表示"这一项不动"。
    """
    _t, _p = current_tag(), current_profile()
    if tag is not None:
        set_tag(tag)
    if profile is not None:
        set_profile(profile)
    try:
        yield
    finally:
        set_tag(_t)
        set_profile(_p)


def usage_log_path() -> str:
    """记账文件路径。测试靠 `DWC_USAGE_PATH` 指到 tmp（生产不设该 env）。"""
    p = os.environ.get("DWC_USAGE_PATH", "").strip()
    if p:
        return p
    var = os.environ.get("DWC_VAR_DIR", "").strip()
    if var:
        return os.path.join(var, USAGE_REL)
    root = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(root, "var", USAGE_REL)


def record(model: str, usage: Optional[Usage],
           cost: Optional[float], tag: str = "", **extra: Any) -> None:
    """追加一行记账。usage 为 None ⇒ 什么都不写（没有数据就没有行）。

    ★ 失败只留痕不抛：记账是旁路，不许因为磁盘满把整轮任务打断。
    """
    if usage is None:
        return
    row: Dict[str, Any] = {
        "ts": time.time(),
        "model": model,
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "cached_tokens": usage.cached_tokens,
        "cost_usd": cost,          # ★ None 保留（不写成 0）
    }
    # ★ R442 · 显式 tag 优先；否则用当前线程的任务标签
    _tag = tag or current_tag()
    if _tag:
        row["tag"] = _tag
    if extra:
        row.update(extra)
    # ★ R447 · 档位：显式传入优先，否则用线程标签；都没有就不写这个键
    _pf = str(row.get("profile") or current_profile()).strip()
    if _pf:
        row["profile"] = _pf
    try:
        path = usage_log_path()
        parent = os.path.dirname(path)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        with io.open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError as e:      # noqa: BLE001 — 旁路失败只留痕
        sys.stderr.write("usage 落盘失败: %r\n" % (e,))
