"""meta_policy · 元进化：按观测压力调整**进化自己的旋钮**（R438 · #14）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）

★★★ 存在理由
  改前 `config/evolution.yaml` 只能人手改。系统每天跑进化轮，
  却从不根据"这一轮有多少候选被配额挤掉"调整自己的预算
  ⇒ meta_evolution 维度没有任何闭环。

★★★ 规则（确定性，不用模型）
  · 压力信号：本轮 `quota_exceeded` 条数 > 0（有候选够格但被 cap 挤掉）
    ⇒ `auto_apply_max_per_round` +1（上界 3）
  · 无压力 ⇒ 不动（不许为改而改）
  · 冷却：同一键 3 天内只调一次（避免抖动）
  · 改完立刻 `load_evolution()` 读回校验；读不回 ⇒ 从备份还原并报错

★ 为什么按行改而不是 yaml.dump：这份文件是**给人读的**，注释就是纪律
  说明。dump 会把注释全丢掉 ⇒ 只剩裸键值，等于把文档删了。
"""
from __future__ import annotations

import os
import shutil
import time
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
EVO_PATH = os.path.join(ROOT, "config", "evolution.yaml")
BACKUP_DIR = os.path.join(ROOT, "var", "backups")

#: 旋钮上下界（越界一律拒）
BOUNDS = {"auto_apply_max_per_round": (1, 3),
          "max_sigs_per_term": (10, 200)}

#: 冷却（秒）
COOLDOWN_S = 3 * 86400


def propose(report: dict[str, Any], current: dict[str, Any],
            last_ts: float = 0.0, now: float | None = None) -> dict | None:
    """按压力出**一条**调整建议；没有压力 ⇒ None（不许为改而改）。"""
    now = time.time() if now is None else now
    if last_ts and (now - last_ts) < COOLDOWN_S:
        return None
    results = (report or {}).get("results") or []
    quota = sum(1 for r in results
                if isinstance(r, dict) and r.get("adopt") == "quota_exceeded")
    if quota <= 0:
        return None
    key = "auto_apply_max_per_round"
    cur = int(current.get(key, 1))
    lo, hi = BOUNDS[key]
    nxt = min(hi, cur + 1)
    if nxt <= cur:
        return None
    return {"key": key, "old": cur, "new": nxt, "quota_exceeded": quota,
            "why": "本轮 %d 条候选被配额挤掉 ⇒ 提高单轮落地上限" % quota}


def apply(component_key: str, new_value: int, path: str = "",
          backup_dir: str = "") -> dict[str, Any]:
    """按行改 yaml（保留注释）+ 备份 + 读回校验；失败自动还原。"""
    p = path or EVO_PATH
    lo, hi = BOUNDS.get(component_key, (None, None))
    if lo is None:
        raise ValueError("未知旋钮 %r" % (component_key,))
    if not isinstance(new_value, int) or isinstance(new_value, bool):
        raise ValueError("值须为 int，实为 %r" % (new_value,))
    if not (lo <= new_value <= hi):
        raise ValueError("%s=%r 越界 [%d,%d]"
                         % (component_key, new_value, lo, hi))
    with open(p, encoding="utf-8") as f:
        lines = f.read().splitlines()
    hit = None
    for i, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith(component_key + ":"):
            hit = i
            break
    if hit is None:
        raise ValueError("%s 不在 %s 里" % (component_key, p))
    old_line = lines[hit]
    indent = old_line[:len(old_line) - len(old_line.lstrip())]
    lines[hit] = "%s%s: %d" % (indent, component_key, new_value)
    bd = backup_dir or BACKUP_DIR
    os.makedirs(bd, exist_ok=True)
    bak = os.path.join(bd, "evolution_%s.yaml"
                       % time.strftime("%Y%m%d_%H%M%S"))
    shutil.copy2(p, bak)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    os.replace(tmp, p)
    # 读回校验（配置坏了 = 没改成）
    try:
        from dwc.foundation.dial_config import load_evolution
        got = load_evolution(p)
        if int(got.get(component_key, -1)) != new_value:
            raise ValueError("读回不一致: %r" % (got.get(component_key),))
    except Exception:
        shutil.copy2(bak, p)
        raise
    return {"outcome": "applied", "key": component_key, "old_line": old_line,
            "new_line": lines[hit], "backup": bak, "path": p}
