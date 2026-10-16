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
VALID_OPS = ("read", "write", "run", "delegate", "ask", "web_read", "web_search", "final")


class JudgeError(ValueError):
    """判别/校验违规必须大声报错（G7 静默门同族）。"""


def _tgt(step: Dict[str, Any]) -> str:
    return str(step.get("path") or step.get("cmd") or step.get("task")
               or step.get("reason") or "")


#: ★ R301-C · 纯问句启发式（规则先筛零 LLM 成本；边界任务走执行路）。
_QA_Q = ("觉得", "是否", "为什么", "是什么", "介绍", "有没有", "多少",
         "吗", "?", "？", "何为", "啥")
_QA_X = ("执行", "跑", "修", "查", "写", "落盘", "搜", "读", "改", "删",
         "建", "起草", "试跑", "重启", "备份")


def is_qa_task(task: str) -> bool:
    """★ R301-C · 纯问句⇒True（问答直答通道；执行路零变）。

    ★ fail-closed：含任一执行动词⇒False（边界走执行，老路零变）。
    """
    t = str(task or "")
    return any(q in t for q in _QA_Q) and not any(x in t for x in _QA_X)


def _sig_args(step: Dict[str, Any]) -> str:
    """★ R301-A · 去重签名（含 args 指纹）：同 target 不同参数≠重复。

    ★ 翻页（同 path 不同 offset/limit）必须放行——R247 修了翻页，
      去重没跟上致 62 轮僵尸循环（T_1016_170342 现场）。
    """
    op = str(step.get("op", ""))
    tgt = _tgt(step)
    if op == "read":
        _o, _l = step.get("offset", ""), step.get("limit", "")
        # ★ 空参归一（无 offset/limit ⇔ 历史无 args 快照 ⇔ extra=""）
        extra = "" if (_o in ("", None) and _l in ("", None)) else             "o=%s|l=%s" % (_o, _l)
    elif op == "run":
        extra = json.dumps(step.get("cmd"), ensure_ascii=False,
                           sort_keys=True, default=str)[:160]
    else:
        extra = ""
    return "%s|%s|%s" % (op, tgt[:160], extra)


def judge_step(step: Dict[str, Any],
               recent_obs: List[Dict[str, Any]],
               qa_mode: bool = False) -> Tuple[str, str, str]:
    """★ 事前判别（§2.2 — 动作执行前; 只用历史与提案, 不看本轮结果）。

    recent_obs: 历史轮的 phase:obs 行（含 op/target/ok/obs）——
      **结构化留痕（R247）是规则版可判的前提**（论文用自然语言历史, 规则版用结构化）。
    返回 (verdict, why, rule_id); verdict ∈ critical|exploratory|noisy。
    ★ R301-D · qa_mode：问答只许 read 取证/final/ask，其余 R5（硬约束——
      prompt 建议管不住真模型，T_R301V 现场 qa 下连 run 4 轮）。
    """
    if not isinstance(step, dict) or not step.get("op"):
        return "noisy", "提案缺 op（形状非法）", "R4"
    op = str(step["op"])
    if op not in VALID_OPS:
        return "noisy", "op=%r 不在契约集" % op, "R4"
    if op == "final":
        return "critical", "final 不判（论文: finish 不判）", "-"
    # ★ R301-D · qa 硬约束（final 已在上分支放行；ask 归主干 critical）。
    if qa_mode and op not in ("read", "ask"):
        return "noisy", ("qa 问答只许 read 取证或 final（op=%s 须走执行任务）"
                         % op), "R5"
    tgt = _tgt(step)
    hist = [e for e in recent_obs
            if isinstance(e, dict) and e.get("op") == op]
    # R1: 同签名（op|target|args）连续重复且无新信息
    # ★ R301-A · 旧注"同 (op,target)"太粗——翻页（同 path 不同 offset）
    #   被误判重复致 62 轮僵尸循环。签名含 args（留痕 args 快照）；
    #   recent_obs 限近 6 轮 ⇒ 连续性隐含（超 6 轮的旧账不翻）。
    _me = _sig_args(step)
    same = [e for e in hist if _sig_args({
        "op": e.get("op"), "path": e.get("target"),
        "offset": (json.loads(e.get("args") or "{}").get("offset")
                   if isinstance(e.get("args"), str) else
                   (e.get("args") or {}).get("offset")),
        "limit": (json.loads(e.get("args") or "{}").get("limit")
                  if isinstance(e.get("args"), str) else
                  (e.get("args") or {}).get("limit")),
        "cmd": (json.loads(e.get("args") or "{}").get("cmd")
                if isinstance(e.get("args"), str) else
                (e.get("args") or {}).get("cmd"))}) == _me]
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
        # ★ R301-D · 连败熔断（不限同 cmd）：近史 run 失败≥3⇒硬出口。
        #   现场：换参连败 4 轮，obs 哈希各异绕过 R247 熔断，耗尽轮数。
        streak = [e for e in recent_obs
                  if isinstance(e, dict) and e.get("op") == "run"
                  and e.get("ok") is False][-3:]
        if len(streak) >= 3:
            return "noisy", ("run 连败 %d 次（换参也败）— 此路不通，"
                             "基于已有信息尽快 final" % len(streak)), "R2"
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
                  allow_final: bool = True,
                  qa_mode: bool = False) -> Optional[str]:
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
        # ★ R301-C · qa 直答防空交差（只保非空不保对，真实性由调用方判）。
        if qa_mode and len(str(step.get("answer") or "").strip()) < 10:
            return "qa final 空交差（answer<10 字）"
    return None


def verify_final_refs(answer: str,
                      root: Optional[str] = None) -> Optional[str]:
    """★ R302 · qa final 引用校验（ALCE 本地版：路径+行号+引文三验）。

    只验有引用的句子（纯观点放行，不强制引用）；URL 跳过；
    裸数字不验（只认"第N行/line N"）。
    返回 None=通过，否则错误串。零 LLM 成本纯规则。
    """
    import re
    if not str(answer or "").strip():
        return "final 空 answer"
    base = root or os.environ.get("DWC_ROOT", "") or os.getcwd()
    # 1) 路径 token（含 / + 后缀；跳过 http）
    pats = re.findall(
        r"[\w\-. /\\]*[\w\-.]/[\w\-. /\\]*\.(?:py|md|json|yaml|yml|txt|jsonl)",
        answer)
    lived: List[str] = []
    for t in pats:
        t = t.strip()
        # ★ \w 含汉字（"见 src/a.py"整体命中）⇒ 从首个 ASCII 路径字符切起
        m = re.search(r"[A-Za-z0-9_./\\]", t)
        t = t[m.start():] if m else ""
        if not t or "http" in t:
            continue
        cand = t if os.path.isabs(t) else os.path.join(base, t)
        if not os.path.exists(cand):
            return "引用路径不存在: %s" % t[:60]
        lived.append(cand)
    # 2) 行号（只认 第N行/line N；冒号型不验防误伤）
    for num in re.findall(r"(?:第\s*(\d+)\s*行|[Ll]ine\s*(\d+))", answer):
        n = int(num[0] or num[1])
        if not lived:
            continue
        cand = lived[-1]
        try:
            with open(cand, encoding="utf-8", errors="replace") as fh:
                total = sum(1 for _ in fh)
        except OSError:
            continue
        if total < n:
            return "引用行号超界: %s 第 %d 行（实 %d 行）" % (
                os.path.basename(cand), n, total)
    # 3) 引文片段（中/英文引号，4-60 字；有路径才验）
    for q in re.findall(r"[“\"']([^“\"']{4,60})[”\"']", answer):
        if not lived:
            continue
        cand = lived[-1]
        try:
            with open(cand, encoding="utf-8", errors="replace") as fh:
                body = fh.read()
        except OSError:
            continue
        if q not in body:
            return "引文失配: “%s” 在 %s 未找到" % (
                q[:30], os.path.basename(cand))
    return None


def step_signature(step: Dict[str, Any]) -> str:
    """修订签名（revision.py signature 纪律 — 连续同签名 ⇒ fallback）。"""
    core = json.dumps({k: v for k, v in step.items() if k != "analysis"},
                      sort_keys=True, ensure_ascii=False)
    return hashlib.sha1(core.encode("utf-8", "replace")).hexdigest()[:16]
