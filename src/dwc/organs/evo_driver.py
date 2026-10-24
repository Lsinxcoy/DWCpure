# -*- coding: utf-8 -*-
"""evo_driver · 产物参数进化驱动器（R审计-P2 · 补 R438-P1 缺口）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ R438 落地总案 §二写了「驱动器：src/dwc/organs/evo_driver.py
    run_component_round(component, signals)」，但产物注册表
    （evo_targets.py）+ 消费者全接线后，**驱动层一直没实现**——
    产物参数「能读能写有人读，但没人触发写」＝半活通路。
  ★ 本模块补上「触发写」的那半边：从产线自带的真实观测里判参数压力，
    有据地调参（白名单内、有界步进、24h 防抖、原子写、可回滚、台账三态）。

★★★ 三条硬纪律（对应项目铁律，缺一则不做）：
  1. **不发明信号**（G2 真值源）: 只认 task_exec read 观测里产线自带的
     `truncated` 字段——那是真实发生的「默认行数读不完」，不是猜。
     失败签名（judge 判分结果）不携带参数压力信息，**不拿来映射参数**。
  2. **有界调整**（evo_targets schema 白名单）: 只调登记过的键，值有类型
     上下界（ET.validate 已拦），每次步进温和（50 行），到 schema 上限为止。
  3. **防抖 + 可回滚 + 台账三态**（G7 不许静默）:
     同参数 24h 只调一次（防震荡）；apply 失败即留痕不假装成功；
     台账每行 {ts, component, key, decision, before, after, backup}，
     decision ∈ {adjusted, skipped_no_signal, skipped_cooldown, error}。

★ 信号口径（防止误报）: 只统计 **offset==0** 且 truncated 的读取——
  offset>0 的截断是正常翻页（大文件本来就该翻页），不是默认行数不够。
  只有「第一页都没读完」才是 read_default_lines 不足的真实压力。

★ 接入: task_exec 已在 read 返回处挂可选 `_OBS_SINK`（默认 None 零开销）；
  调用方（dwc_evo_round / daemon）把 `driver.observe_read` 挂上去，
  在进化轮尾部调 `driver.run("context_mgmt")`。

★ 诚实边界（不夸大）:
  · 本 driver 只接**有真实产线信号**的参数（当前: read_default_lines）。
    client_tool/subagent/output_plumbing/config 没暴露可判定的压力信号，
    就不动——不为「看起来在进化」而发明信号（G2）。
  · 调整效果由**下一窗口**的截断率自然验证（数据驱动，不猜好坏）。
"""
from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional


def _ledger_default() -> str:
    """台账路径（与 dwc_evo_round 共用 var/evolution_ledger.jsonl）。"""
    here = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(here, "var", "evolution_ledger.jsonl")


#: 防抖窗口（秒）——同参数 24h 只调一次，防震荡
COOLDOWN_S = 24 * 3600

#: 压力阈值——窗口内「第一页读取」的截断率 ≥ 此值才动手
TRUNC_RATIO_THRESHOLD = 0.5

#: 温和步进——每次最多 +50 行（200→250→…），上限由 schema 白名单拦
STEP = 50


def _read_ledger_last(path: str, component: str, key: str) -> Optional[float]:
    """读台账找该参数最后一次调整的 ts（None = 从没调过）。

    只认 decision=adjusted 的行——skipped/error 不算「已调整」。
    """
    if not os.path.isfile(path):
        return None
    last: Optional[float] = None
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except ValueError:
                    continue
                if (rec.get("component") == component
                        and rec.get("key") == key
                        and rec.get("decision") == "adjusted"):
                    ts = rec.get("ts")
                    if isinstance(ts, (int, float)):
                        last = float(ts)
    except OSError:
        return None
    return last


def _append_ledger(path: str, rec: Dict[str, Any]) -> None:
    """台账追加一行（crash 不丢已做 —— 与 dwc_evo_round 同款）。"""
    global _LEDGER_FAIL
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        # ★ R审计-P2 · G7 静默门: 台账写不了不许静默 pass —— 计数 + stderr
        _LEDGER_FAIL[0] += 1
        if _LEDGER_FAIL[0] <= 3:       # 前 3 次留痕（不刷屏）
            import sys as _sys
            _sys.stderr.write("参数进化台账写失败×%d\n" % _LEDGER_FAIL[0])


#: G7 静默门: 台账写失败计数（进程级，可观测）
_LEDGER_FAIL: List[int] = [0]


class EvoParamDriver:
    """产物参数驱动器：观测累积 → 压力判定 → 有界调参 → 台账。

    用法:
        driver = EvoParamDriver()
        task_exec._OBS_SINK = driver.observe_read      # 挂信号
        ...
        rep = driver.run("context_mgmt")                # 进化轮尾部
    """

    def __init__(self, ledger_path: Optional[str] = None,
                 cooldown_s: float = COOLDOWN_S,
                 threshold: float = TRUNC_RATIO_THRESHOLD,
                 step: int = STEP, now: Optional[float] = None):
        self.ledger_path = ledger_path or _ledger_default()
        self.cooldown_s = cooldown_s
        self.threshold = threshold
        self.step = step
        self._now = now or time.time
        #: 窗口内观测（run 后清空；不落盘 —— 信号是瞬时的）
        self._reads: List[Dict[str, Any]] = []

    # ── 信号侧 ─────────────────────────────────────────────

    def observe_read(self, obs: Dict[str, Any]) -> None:
        """task_exec `_OBS_SINK` 挂这个。只收最小字段（op/truncated/offset）。"""
        if isinstance(obs, dict) and obs.get("op") == "read":
            self._reads.append(obs)

    def _pressure_stats(self) -> Dict[str, Any]:
        """窗口统计：只计 offset==0 的读取（第一页没读完才算压力）。"""
        first_page = [r for r in self._reads
                      if not (r.get("offset") or 0)]
        n = len(first_page)
        n_trunc = sum(1 for r in first_page if r.get("truncated"))
        return {"n_first_page_reads": n, "n_truncated": n_trunc,
                "ratio": (n_trunc / n) if n else 0.0}

    # ── 决策侧 ─────────────────────────────────────────────

    def run(self, component: str = "context_mgmt",
            key: str = "read_default_lines",
            max_value: int = 2000) -> Dict[str, Any]:
        """一轮参数进化判定。返回台账同构的 decision 记录。

        decision:
          skipped_no_signal  — 窗口无压力（截断率低于阈值）或无可判定信号
          skipped_cooldown   — 24h 内刚调过（防震荡）
          adjusted           — 已调参（ET.apply 原子写 + 备份 + 读回）
          error              — 调参失败（大声留痕，不假装成功）
        """
        now = float(self._now())
        stats = self._pressure_stats()

        # ① 压力判定（不发明信号: 无第一页读取 ⇒ 无从判定 ⇒ 跳过）
        if stats["n_first_page_reads"] < 1 \
                or stats["ratio"] < self.threshold:
            rec = {"ts": now, "component": component, "key": key,
                   "decision": "skipped_no_signal",
                   "reason": ("第一页截断率 %.0f%%（n=%d）低于阈值 %.0f%%"
                              % (stats["ratio"] * 100,
                                 stats["n_first_page_reads"],
                                 self.threshold * 100))}
            _append_ledger(self.ledger_path, rec)
            self._reads = []
            return rec

        # ② 防抖: 24h 内刚调过 ⇒ 跳过（防震荡）
        last = _read_ledger_last(self.ledger_path, component, key)
        if last is not None and (now - last) < self.cooldown_s:
            rec = {"ts": now, "component": component, "key": key,
                   "decision": "skipped_cooldown",
                   "reason": ("%.1f 小时前刚调过（防抖窗口 %.1f 小时）"
                              % ((now - last) / 3600, self.cooldown_s / 3600))}
            _append_ledger(self.ledger_path, rec)
            self._reads = []
            return rec

        # ③ 有界调参: 当前值 + 步进，不超过 max_value（schema 上界）
        try:
            from dwc.organs import evo_targets as ET
            current = (ET.read(component).get(key) or 0)
            new_val = min(int(current) + self.step, max_value)
            res = ET.apply(component, {key: new_val})
            rec = {"ts": now, "component": component, "key": key,
                   "decision": "adjusted",
                   "before": res["before"].get(key),
                   "after": res["after"].get(key),
                   "backup": res.get("backup") or "",
                   "reason": ("第一页截断率 %.0f%%（n=%d）⇒ 调大 %s"
                              % (stats["ratio"] * 100,
                                 stats["n_first_page_reads"], key))}
            _append_ledger(self.ledger_path, rec)
            self._reads = []
            return rec
        except Exception as exc:                     # noqa: BLE001
            rec = {"ts": now, "component": component, "key": key,
                   "decision": "error",
                   "reason": "%s: %s" % (type(exc).__name__, exc)}
            _append_ledger(self.ledger_path, rec)
            self._reads = []
            return rec
