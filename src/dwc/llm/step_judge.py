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

#: ★★★ R386 · 只读命令白名单（qa_mode 下放行 —— 只读不等于禁用命令）。
#:   现场：cl01「execute_user_task 定义在哪个文件？」被判 qa_mode ⇒
#:   `search_code` 转成的 `run(grep ...)` 被 R5 连拦 4 轮 ⇒ 答不出。
#:   而 grep 一行就能定位（实测 task_exec.py:914）⇒ code-locate 30%。
#:   只收**纯读**命令；任何可能改状态的都不进这张表。
READONLY_CMDS = frozenset((
    "grep", "egrep", "fgrep", "rg", "ag",
    "ls", "dir", "find", "tree",
    "cat", "head", "tail", "wc", "stat", "file",
    "pwd", "echo", "which", "type", "where", "du", "df",
))

#: 只读命令里也不许出现的东西（夹带写操作 / 管道到解释器 / 重定向写）
_READONLY_BREAKERS = (
    ">", ">>", "|", "&&", "||", ";", "`", "$(",
    " rm ", " mv ", " cp ", " del ", " touch ", " tee ",
    "-exec", "-delete", "-execdir", "python", "node", "bash", "sh -c",
)


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


def _args_of(e: Any) -> Dict[str, Any]:
    """★★★ R400 · 容错读取留痕参数。

    现场：留痕里的 `args` 曾被 `json.dumps(...)[:160]` 从中间切断，
    `json.loads` 抛 `JSONDecodeError: Unterminated string`（char 100），
    异常冒到主循环 ⇒ 整个动作被判失败（命令其实成功了）。
    历史数据里可能还有这种坏行 ⇒ 读侧必须容错（坏 ⇒ 空 dict，不炸）。
    """
    if not isinstance(e, dict):
        return {}
    a = e.get("args")
    if isinstance(a, dict):
        return a
    if isinstance(a, str) and a.strip():
        try:
            v = json.loads(a)
            return v if isinstance(v, dict) else {}
        except Exception:                  # noqa: BLE001 — 坏留痕不阻断判别
            return {}
    return {}


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
        # ★★★ R400 · 优先用 `_h` 全量指纹：长命令按 160 字符截断后，
        #   前 160 相同的两条不同命令会被误判"重复"。
        _h = step.get("_h")
        if _h:
            extra = "h=%s" % _h
        else:
            # ★ 与 `_args_snapshot` 完全同构：同样取 (offset,limit,cmd) 打包、
            #   同样 sort_keys ⇒ 两处指纹才会相等（否则历史与当前永不匹配）
            _payload = {k: step.get(k) for k in ("offset", "limit", "cmd")
                        if step.get(k) is not None}
            extra = "h=%s" % hashlib.sha1(
                json.dumps(_payload, ensure_ascii=False,
                           sort_keys=True, default=str).encode("utf-8")
            ).hexdigest()[:12]
    else:
        extra = ""
    return "%s|%s|%s" % (op, tgt[:160], extra)


def _is_readonly_run(step: Dict[str, Any]) -> bool:
    """★★★ R386 · 该 run 是否**只读**（不改仓库/系统状态）。

    现场（2026-10-20 cl01）：qa_mode 的 R301-D 硬约束只许
    `read`/`ask`/`web_read`，`search_code` 转成的 `run(grep ...)` 每轮都被
    R5 拦（`target: "R5_blocked"` ×4），最后答"未能确认定义文件"。
    而 grep 一行就能定位 —— **拦 grep 等于把"查证"本身禁了**。

    qa_mode 的本意是「只读、不许改状态」，不是「不许用命令」。
    """
    if step.get("op") != "run":
        return False
    # ★★★ R393 · 工具层生成的只读命令（list_dir / search_code / find_files）
    #   自带 `readonly: True` 标记 —— 它们由 `_tool_calls_to_step` 构造，
    #   **不是模型手写的 shell 串**，安全性由工具层保证。
    #   现场（R391 回归）：`find` 转成 `python -c <os.walk 脚本>` 后，
    #   head=`python.exe` 不在白名单 ⇒ qa_mode 下 **R5 全拦**
    #   ⇒ code-locate 的 find_files/search_code 全废（13/14 两单全 R5_blocked）。
    if step.get("readonly") is True:
        return True
    cmd = step.get("cmd")
    if not isinstance(cmd, list) or not cmd:
        return False
    head = str(cmd[0]).replace("\\", "/").rsplit("/", 1)[-1].lower()
    if head.endswith(".exe"):
        head = head[:-4]
    if head not in READONLY_CMDS:
        return False
    joined = " ".join(str(x) for x in cmd).lower()
    # ★ 双重保险：只读命令也不许夹带写操作/管道到解释器
    for bad in _READONLY_BREAKERS:
        if bad in joined:
            return False
    return True


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
    # ★★★ R386 · 但**只读命令**必须放行：qa 的本意是「只读、不许改状态」，
    #   不是「不许用命令」。现场 cl01 的 `search_code`→`run(grep)` 被 R5
    #   连拦 4 轮 ⇒ 答不出定义文件；而 grep 一行就能定位。
    if qa_mode and op not in ("read", "ask", "web_read"):
        if _is_readonly_run(step):
            pass                      # 只读命令放行（继续走后面的重复判定）
        else:
            return "noisy", ("qa 问答只许 read/web_read/只读命令 取证或 final"
                             "（op=%s 须走执行任务）" % op), "R5"
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
        "offset": _args_of(e).get("offset"),
        "limit": _args_of(e).get("limit"),
        "cmd": _args_of(e).get("cmd"),
        "_h": _args_of(e).get("_h")}) == _me]
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
    # ★ R302补 · revision 亦受 qa 硬约束（R5 只在 judge 事前判别，
    #   revision 产 run 绕过执行——T_R302W 现场 revision 建议 run 即执行）。
    if qa_mode and op not in ("read", "ask", "final", "web_read"):
        return ("qa 问答只许 read/web_read 取证或 final（revision 产 op=%s 驳回）"
                % op)
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
                      root: Optional[str] = None,
                      obs_urls: tuple = ()) -> Optional[str]:
    """★ R302 · qa final 引用校验（ALCE 本地版：路径+行号+引文三验）。

    只验有引用的句子（纯观点放行，不强制引用）；URL 跳过；
    裸数字不验（只认"第N行/line N"）。
    返回 None=通过，否则错误串。零 LLM 成本纯规则。
    """
    import re
    if not str(answer or "").strip():
        return "final 空 answer"
    base = root or os.environ.get("DWC_ROOT", "") or os.getcwd()
    # 1) 路径 token（含 / 全路径 或 裸文件名 xxx.后缀；跳过 http；
    #   裸文件名须含字母——防 "v1.3"/"e.g." 误伤，后缀白名单限代码/文档）
    pats = re.findall(
        r"[\w\-. /\\]*[\w\-.]/[\w\-. /\\]*\.(?:py|md|json|yaml|yml|txt|jsonl)"
        r"|(?<![\w/])[\w\-.]*[A-Za-z][\w\-.]*"
        r"\.(?:py|md|json|yaml|yml|txt|jsonl)(?![\w])",
        answer)
    lived: List[str] = []
    for t in pats:
        t = t.strip()
        # ★ \w 含汉字（"见 <路径>"整体命中）⇒ 从首个 ASCII 路径字符切起
        m = re.search(r"[A-Za-z0-9_./\\]", t)
        t = t[m.start():] if m else ""
        if not t or "http" in t:
            continue
        cand = t if os.path.isabs(t) else os.path.join(base, t)
        if not os.path.exists(cand):
            return "引用路径不存在: %s" % t[:60]
        lived.append(cand)
    # ★ R303-⑥ · 4) URL（final 含 http 串 ⇒ 须在取证 obs_urls 出现过，防编 URL）
    for u in re.findall(r"https?://[^\s\"'”]+", str(answer or "")):
        if u not in (obs_urls or ()):
            return "引用URL未取证: %s" % u[:80]
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
