# -*- coding: utf-8 -*-
"""step_judge · 决策效果判别（规则版）+ State Revision 轻量校验 — 2609.28416（R255）。

定位声明 · **DWC-AUTO**（自我强化 · 判据 G1 定位门）
  ★ 服务执行核的事前判别（EditAct 的规则版落地）— 非 DWC-MEM。
  ★ 不抢位: 不声明 REPLACES; R247 复读熔断保留为第二防线。

★★★ TRUTH_SOURCE（判据 G2）
  本模块**不判任务成败**（成败永远在 judge）— 噪声判别是**动作推进性启发式**,
  非评分。校准锚（②）: AEWM-Action-Judge-Bench 的 gold label（agent 外真值源,
  scripts/calibrate_step_judge.py）—— 规则版阈值有外部依据, 不是自评。

=== 论文机制 → 规则版映射（2609.28416 §2.2 · 深读报告 §5①）===
  论文: 专训 35B 模型执行前判 critical/exploratory/noisy, noisy 直接替换。
  DWC 无训练条件 ⇒ 规则版三分类:
    noisy 规则族（全部来自 DWC 实测事故）:
      R1  同 (op,target) 连续 ≥2 且后续无新信息（17:12 read 同段 3 连案）
      R2  run 同 cmd 连续失败 ≥2（17:13 wsl rc=1 案）
      R3  read 目标路径不存在（17:13 幻觉路径 docs/world_model.py 案 —
          **本地规则版独有优势**: 判别器可查文件系统, 论文 LLM judge 不能）
      R4  run 空命令 / op 非法形状
    exploratory（**显式保留** — 论文教训: 不设该类会把信息收集当噪声砍掉）
    critical: ask 授权链步 / delegate（推进主干）
  ★ final 不判（论文: finish 不判 — 同款语义）。

=== 修订（State Revision 轻量版）的纪律（revision.py 逐条对齐）===
  · 每步**最多 1 次**修订; 修订失败/校验不过 ⇒ **fallback 保留原提案**
    （绝不因修订器故障卡任务 — EditAct _fallback 同款）
  · 连续两次修订产出同签名 ⇒ fallback（duplicate_replacement 纪律）
  · 修订必须过动作校验（validate_step — 参数形状/路径/工具白名单）
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any, Dict, List, Optional, Tuple

#: 修订可用动作（白名单 — 与执行契约同集; final 由原提案自己给）
VALID_OPS = ("read", "write", "run", "delegate", "ask", "web_read", "final")


class JudgeError(ValueError):
    """判别/校验违规必须大声报错（G7 静默门同族）。"""


def _tgt(step: Dict[str, Any]) -> str:
    return str(step.get("path") or step.get("cmd") or step.get("task")
               or step.get("reason") or "")


def judge_step(step: Dict[str, Any],
               recent_obs: List[Dict[str, Any]]) -> Tuple[str, str, str]:
    """★ 事前判别（§2.2 — 动作执行前; 只用历史与提案, 不看本轮结果）。

    recent_obs: 历史轮的 phase:obs 行（含 op/target/ok/obs）——
      **结构化留痕（R247）是规则版可判的前提**（论文用自然语言历史, 规则版用结构化）。
    返回 (verdict, why, rule_id); verdict ∈ critical|exploratory|noisy。
    """
    if not isinstance(step, dict) or not step.get("op"):
        return "noisy", "提案缺 op（形状非法）", "R4"
    op = str(step["op"])
    if op not in VALID_OPS:
        return "noisy", "op=%r 不在契约集" % op, "R4"
    if op == "final":
        return "critical", "final 不判（论文: finish 不判）", "-"
    tgt = _tgt(step)
    hist = [e for e in recent_obs
            if isinstance(e, dict) and e.get("op") == op]
    # R1: 同 (op,target) 连续重复且无新信息
    same = [e for e in hist if str(e.get("target", "")) == tgt]
    if len(same) >= 2:
        return "noisy", ("同 (%s,%s) 已执行 %d 次且无新推进 — 重复"
                         % (op, tgt[:40], len(same) + 1)), "R1"
    # R2: run 同 cmd 连续失败
    if op == "run":
        if not tgt.strip():
            return "noisy", "run 空命令", "R4"
        fails = [e for e in hist
                 if str(e.get("target", "")) == tgt and e.get("ok") is False]
        if fails:
            return "noisy", ("同命令已失败 %d 次（rc!=0）— 换命令/换参数"
                             % len(fails)), "R2"
    # R3: read 路径不存在（本地可查 — 论文 LLM judge 做不到的规则）
    if op == "read" and tgt:
        root = os.environ.get("DWC_ROOT", "") or os.getcwd()
        cand = tgt if os.path.isabs(tgt) else os.path.join(root, tgt)
        if not os.path.exists(cand):
            return "noisy", "read 目标不存在（幻觉路径）: %s" % tgt[:60], "R3"
    # critical: ask / delegate 推进主干
    if op in ("ask", "delegate"):
        return "critical", "%s 步（主干推进）" % op, "-"
    return "exploratory", "常规探索步", "-"


def validate_step(step: Any, *, root: Optional[str] = None,
                  allow_final: bool = True) -> Optional[str]:
    """★ 修订动作校验（revision.py validate_code 纪律 — 过不了就 fallback）。

    返回 None=合法, 否则错误串。
    ★ allow_final=False（judge 路径）: 修订不可产 final — final 分支在判别
      之前已结算, 二次终局无处安放（修订只许换路径/参数/动作形态）。"""
    if not isinstance(step, dict):
        return "修订产出非 dict"
    op = step.get("op")
    if op not in VALID_OPS:
        return "修订 op=%r 不在契约集" % (op,)
    if op in ("read", "write") and not step.get("path"):
        return "修订缺 path"
    if op == "run" and not str(step.get("cmd", "")).strip():
        return "修订 run 空 cmd"
    if op == "web_read" and not str(step.get("url", "")).startswith(
            ("http://", "https://")):
        return "修订 web_read 非法 url"
    if op == "read" and step.get("path"):
        base = root or os.environ.get("DWC_ROOT", "") or os.getcwd()
        tgt = step["path"]
        cand = tgt if os.path.isabs(tgt) else os.path.join(base, tgt)
        if not os.path.exists(cand):
            return "修订 read 路径仍不存在: %s" % str(tgt)[:60]
    if op == "final":
        if not allow_final:
            return "修订不可产 final（终局分支已过 — 换路径/参数/动作）"
        if not step.get("answer"):
            return "修订 final 缺 answer"
    return None


def step_signature(step: Dict[str, Any]) -> str:
    """修订签名（revision.py signature 纪律 — 连续同签名 ⇒ fallback）。"""
    core = json.dumps({k: v for k, v in step.items() if k != "analysis"},
                      sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(core.encode("utf-8", "replace")).hexdigest()[:16]
