# -*- coding: utf-8 -*-
"""DWC 质量门 —— 可执行版。

母巢的反面教材 (docs/QUALITY_GATE.md §封底):
    门判了 12,717 次 promote/hold/prune, 实际停用 5 个机制,
    mechanism_prune_shadow 建议 56,963 条 / applied=0。
**门存在 ≠ 门被执行。**

所以本文件的首要设计目标是: **门跑一次就留一次痕**,
让"门存在但没人跑"这个病在 DWC 不可能悄悄发生。

七道门对应母巢七条教训 L1-L7:
    G1 定位门   新模块服务哪两件事之一?  有无重复抢位?
    G2 真值门   成功判定有无系统外真值源? 有无硬编码成功?
    G3 活性门   六层是否齐全且单调?  never_called 是否单列?
    G4 生灭门   生成能力是否配套淘汰判据 + 上限?
    G5 声称门   进度文档是否双栏且实测可复现?
    G6 加减门   本月是否有减法记录?
    G7 静默门   except 降级是否可观测? 是否伪装 ok=True?

用法:
    python scripts/gate.py# 跑全部
    python scripts/gate.py --gate 2         # 只跑 G2
    python scripts/gate.py --json           # 机器可读
"""
from __future__ import annotations

import argparse
import ast
import datetime as _dt
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src", "dwc")
TESTS = os.path.join(ROOT, "tests")
DOCS = os.path.join(ROOT, "docs")
TRACE = os.path.join(ROOT, "archive", "gate_trace.jsonl")


# ---------------------------------------------------------------- 基础设施

def _py_files(root: str) -> list[str]:
    out = []
    if not os.path.isdir(root):
        return out
    for dp, dn, fns in os.walk(root):
        dn[:] = [d for d in dn if d != "__pycache__"]
        for fn in fns:
            if fn.endswith(".py"):
                out.append(os.path.join(dp, fn))
    return out


def _read(p: str) -> str:
    try:
        return io.open(p, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


# ---------------------------------------------------------------- G1 定位门

def gate1_locality() -> dict:
    """新模块必须声明服务哪件事, 且无重复抢位。"""
    files = _py_files(SRC)
    violations = []
    declared, replaces = {}, {}

    for fp in files:
        rel = os.path.relpath(fp, ROOT)
        s = _read(fp)
        tree = None
        try:
            tree = ast.parse(s)
        except (SyntaxError, UnicodeDecodeError):
            violations.append({"file": rel, "rule": "语法错误, 无法解析",
                               "detail": ""})
            continue

        # 规则: 模块级 docstring 必须含定位声明
        doc = ast.get_docstring(tree) or ""
        if not re.search(r"DWC-(MEM|AUTO)", doc):
            violations.append({
                "file": rel, "rule": "缺定位声明",
                "detail": "模块 docstring 必须写明 DWC-MEM(记忆底座) "
                          "或 DWC-AUTO(自我强化)"})
            continue

        m = re.search(r"DWC-(MEM|AUTO)", doc)
        declared[rel] = m.group(1)

        # 规则: 替代声明不得冲突
        for rm in re.finditer(r"REPLACES\s*=\s*['\"]([^'\"]+)['\"]", s):
            tgt = rm.group(1)
            replaces.setdefault(tgt, []).append(rel)

    for tgt, owners in replaces.items():
        if len(owners) > 1:
            violations.append({
                "file": ",".join(owners), "rule": "抢位冲突",
                "detail": "REPLACES=%r 被 %d 个模块同时声明"
                          % (tgt, len(owners))})

    return {
        "gate": 1, "name": "定位门", "lesson": "L1",
        "files": len(files), "declared": declared,
        "violations": violations,
        "pass": not violations,
    }


# ---------------------------------------------------------------- G2 真值门

# 母巢原样反例 (取自 P0-4 / P0-5)
_MOTHERNODE_ANTI = [
    (r"def\s+_?probe\w*\s*\([^)]*\)\s*(?:->[^:]+)?:\s*(?:#[^\n]*)?\n\s+return\s+True",
     "P0-4 熔断 probe 恒 True"),
    (r"return\s+0\.7\b", "P0-5 ScoreChannel 恒 0.7"),
    (r"return\s+[\"']ok[\"']\s*,\s*[\"']stored[\"']", "P0-3 零副作用却报已存"),
]


def gate2_truth() -> dict:
    """成功判定必须有系统外真值源; 禁硬编码成功。"""
    files = _py_files(SRC)
    violations = []

    for fp in files:
        rel = os.path.relpath(fp, ROOT)
        s = _read(fp)
        try:
            tree = ast.parse(s)
        except (SyntaxError, UnicodeDecodeError):
            continue

        # 规则 A: 无条件 return True / 常量的函数 (真在函数体内, 非注释)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            body = [x for x in node.body
                    if not (isinstance(x, ast.Expr)
                            and isinstance(x.value, ast.Constant))]
            if not body:
                violations.append({"file": rel,
                                   "rule": "空函数体",
                                   "detail": "%s 无任何语句"
                                             % node.name})
                continue
            # 单条 return 常量 True 且函数名像探针
            if len(body) == 1 and isinstance(body[0], ast.Return):
                v = body[0].value
                if isinstance(v, ast.Constant) and v.value is True:
                    nm = node.name.lower()
                    if any(k in nm for k in ("probe", "check", "verify",
                                             "alive", "healthy", "test")):
                        violations.append({
                            "file": rel, "rule": "探针恒 True",
                            "detail": "%s() 恒返回 True (母巢 P0-4)" % node.name})

        # 规则 B: 母巢同款反模式
        for pat, why in _MOTHERNODE_ANTI:
            if re.search(pat, s):
                violations.append({"file": rel, "rule": why, "detail": ""})

        # 规则 C: 判定能力必须声明真值源
        if re.search(r"\b(score|evaluate|judge|verdict|rate)\w*\s*\(", s):
            if "TRUTH_SOURCE" not in s:
                violations.append({
                    "file": rel, "rule": "缺 TRUTH_SOURCE 声明",
                    "detail": "含评分/判定能力, 必须声明系统外真值源"})

    return {
        "gate": 2, "name": "真值门", "lesson": "L2 + L7",
        "files": len(files), "violations": violations,
        "pass": not violations,
    }


# ---------------------------------------------------------------- G3 活性门

LAYERS = ("present", "registered", "called", "succeeded",
          "produced_effect", "feedback_closed")

# ★★ R15: 六层的正确载体是 Γ（因果链）事件，不是 Python 文件。
#   QUALITY_GATE §门3 已于 2026-10-05 由用户裁决"采用"，
#   映射见 2608.24876 §5.1.2:
#     present ← 文件/注册表 · registered ← 登记表 · called ← Γ 事件
#     succeeded ← 外部回执 · produced_effect ← 下游产物
#     feedback_closed ← 回到判分器
#   ⇒ 因 Γ 尚未落地，G3 需要第五种状态表达「已采纳但未实现」。
# ★★ R15 更正: 原先只认 causal_chain / chain_record / gamma / trace 四个文件名，
#   而六层事件层我命名为 activity.py ⇒ 门报"Γ 尚未落地"，但它其实已落地。
#   ⇒★ 正确的判据是: **六层字段是否被实际定义/使用**，而不是文件名叫什么。
#   ⇒★ 改法: 找定义六层枚举的那处（class Layer / ORDER），
#   文件名只作为线索 ⇒ 避免"改名就误判未实现"。
GAMMA_NAME_HINTS = ("activity", "causal_chain", "chain_record", "gamma", "trace")
#: ★ 六层的定义特征（文件名无关）—— 必须出现六层名中的若干 + 层序结构
GAMMA_MARKERS = ("class Layer", "ORDER", "Layer.PRESENT", "FEEDBACK_CLOSED")


def _gamma_present(files) -> bool:
    """Γ（六层事件层）是否已落地。

    ★★ 判据（2026-10-05 R15 修正）: 看**六层的定义特征**，不看文件名。
      起因: 第一版只认文件名（causal_chain/gamma/trace…），
      而实现命名为 activity.py ⇒ 门误报"Γ 尚未落地"。
      ⇒★ 教训: 用文件名当判据 = 改名即误判（同 M2 代理指标）
    """
    for fp in files:
        s = _read(fp)
        hits = sum(1 for m in GAMMA_MARKERS if m in s)
        name_hint = any(h in os.path.basename(fp).lower()
                        for h in GAMMA_NAME_HINTS)
        # ★ 两个线索都算落地: 要么有定义特征，要么文件名明确
        if hits >= 2 or (name_hint and hits >= 1):
            return True
    return False


def gate3_activity() -> dict:
    """六层齐全单调; never_called 单列; 弱判据不越级。

    ★★ 2026-10-05 R14 修正: 六层检查此前**无条件强制**。
      而 QUALITY_GATE.md §门3 自己写着「六层模型是候选，不是必然」
      「DWC 可能用别的分层，也可能根本不需要分层」
      ⇒⇒ 门把"候选"当成了硬要求 ⇒ 第一份实现代码落盘就报红
      ⇒⇒ 修法（选方案乙 + 补充判据）:
         零个文件声明六层 ⇒ 状态 not_adopted（未采用，**不是通过也不是失败**）
         任一文件声明 ⇒ 立刻转强制（部分声明也触发，避免"半套分层"）
         全都声明 ⇒ 六层完整性 + 另两条规则照旧
      ⇒ 缺口: 无法区分「本项目不用六层」与「有人忘了写」
        ⇒ 已如实登记，该缺口要靠 G3 之外的机制补（如 organs 实现时显式声明）
    """
    files = _py_files(SRC)
    violations = []
    adopted_by = []

    if files:
        blob = "\n".join(_read(f) for f in files)
        # ★ 谁声明了六层（逐文件统计，不只看全局 blob）
        for fp in files:
            s_one = _read(fp)
            hits = [lay for lay in LAYERS if lay in s_one]
            if hits:
                adopted_by.append((os.path.relpath(fp, ROOT), len(hits)))
        if not adopted_by:
            # ★ 零声明 ⇒ 未采用。跳过六层完整性检查，但另两条规则仍跑。
            pass
        else:
            for layer in LAYERS:
                if layer not in blob:
                    violations.append({"file": "-", "rule": "缺活性层",
                                       "detail": "无 %r 字段" % layer})
        # 规则: "从未调用"不得混入 stale
        for fp in files:
            rel = os.path.relpath(fp, ROOT)
            s = _read(fp)
            for m in re.finditer(r"stale\.append\(\s*(\w+)\s*\)", s):
                var = m.group(1)
                seg = s[max(0, m.start() - 260):m.start()]
                # 看它所在条件是否用了 call_count == 0
                if re.search(r"%s\.call_count\s*==\s*0" % re.escape(var), seg):
                    violations.append({
                        "file": rel, "rule": "never_called 混入 stale",
                        "detail": "母巢 P2-3 同款: 未调用≠曾经活跃"})
        # 规则: 弱判据越级
        for fp in files:
            rel = os.path.relpath(fp, ROOT)
            s = _read(fp)
            for m in re.finditer(
                    r"def\s+record_call\w*\s*\([^)]*\)[^:]*:(.*?)(?=\n    def |\Z)",
                    s, re.S):
                body = m.group(1)
                for strong in ("succeeded", "produced_effect", "feedback_closed"):
                    if re.search(r"%s\w*_layer\s*=\s*True" % strong, body):
                        violations.append({
                            "file": rel, "rule": "弱判据越级",
                            "detail": "record_call 点亮了 %s" % strong})
    return {
        "gate": 3, "name": "活性门", "lesson": "L4",
        "files": len(files), "violations": violations,
        # ★ 六层是否被任何文件声明过（R14 新增）
        "six_layer_adopted": bool(adopted_by),
        "six_layer_adopters": [rel for rel, _ in adopted_by],
        "gamma_present": _gamma_present(files),
        "pass": not violations,
    }


# ---------------------------------------------------------------- G4 生灭门

_GEN_HINTS = (r"def\s+(compile|generate|synthes\w+|evolve|produce)\w*\s*\(",
              r"def\s+_?\w*compile\w*\s*\(")


def gate4_life_cycle() -> dict:
    """生成能力必须配套淘汰判据 + 池子上限。"""
    files = _py_files(SRC)
    violations = []
    has_gen = False

    for fp in files:
        rel = os.path.relpath(fp, ROOT)
        s = _read(fp)
        gen = any(re.search(p, s) for p in _GEN_HINTS)
        if not gen:
            continue
        has_gen = True
        need = []
        if not re.search(r"(EVICT|evict\w*|淘汰)", s):
            need.append("淘汰判据")
        if not re.search(r"(POOL_LIMIT|MAX_POOL|pool_limit|max_pool)", s):
            need.append("池子上限")
        if not re.search(r"(OVERFLOW|overflow|超限|reject_new)", s):
            need.append("超限行为")
        for n in need:
            violations.append({
                "file": rel, "rule": "生成能力缺配套",
                "detail": "缺 %s (母巢 L3: 1,447 生 / 5 死)" % n})

    return {
        "gate": 4, "name": "生灭门", "lesson": "L3",
        "files": len(files), "generation_found": has_gen,
        "violations": violations, "pass": not violations,
    }


# ---------------------------------------------------------------- G5 声称门

def gate5_claims() -> dict:
    """进度文档必须双栏且实测可复现。"""
    prog = os.path.join(DOCS, "PROGRESS.md")
    violations = []
    if not os.path.exists(prog):
        return {"gate": 5, "name": "声称门", "lesson": "L5",
                "violations": [{"file": "docs/PROGRESS.md",
                                "rule": "缺文件", "detail": ""}],
                "pass": False}
    s = _read(prog)
    if "声称" not in s or "实测" not in s:
        violations.append({"file": "docs/PROGRESS.md",
                           "rule": "缺双栏", "detail": "须含'声称'与'实测'"})
    if "取数" not in s:
        violations.append({"file": "docs/PROGRESS.md",
                           "rule": "实测不可复现",
                           "detail": "须给取数命令"})
    return {"gate": 5, "name": "声称门", "lesson": "L5",
            "violations": violations, "pass": not violations}


# ---------------------------------------------------------------- G6 加减门

def gate6_subtraction() -> dict:
    """ADR 存在性 + 本月减法记录。"""
    adr_dir = os.path.join(DOCS, "adr")
    adrs = [f for f in os.listdir(adr_dir)] if os.path.isdir(adr_dir) else []
    # 减法记录: docs/adr/ 里含 SUBTRACT 的记录, 或 docs/ 下任何 reduc/减法/subtract 文件.
    # 修 (2026-10-03): 原实现把**文件名**收进 subs, 却用 adr_dir 拼路径取 mtime ——
    # 一旦命中文件在 adr_dir 之外 (如 docs/lessons/V8PRO_TO_V9_SUBTRACTION.md),
    # 生成器为空 ⇒ max() 抛 ValueError ⇒ 整个 gate.py 崩溃 (不是判红, 是门失效).
    # 改为全程持有**完整路径**, 且路径不存在时安全跳过.
    subs = [os.path.join(adr_dir, a) for a in adrs if "SUBTRACT" in a.upper()]
    if not subs:
        for dp, dn, fns in os.walk(DOCS):
            for fn in fns:
                if re.search(r"reduc|减法|subtract", fn, re.I):
                    subs.append(os.path.join(dp, fn))
    now = _dt.date.today()
    stale = []
    if subs:
        _mtimes = [os.path.getmtime(p) for p in subs if os.path.exists(p)]
        if _mtimes:
            newest = max(_mtimes)
            days = (now - _dt.date.fromtimestamp(newest)).days
            if days > 62:            # 两个月
                stale.append(days)
    violations = []
    if stale:
        violations.append({"file": "docs/adr", "rule": "减法记录过期",
                           "detail": "最近减法记录距今 %d 天 (>62)" % stale[0]})
    return {"gate": 6, "name": "加减门", "lesson": "L6",
            "adr_count": len(adrs), "subtraction_records": len(subs),
            "violations": violations, "pass": not violations}


# ---------------------------------------------------------------- G7 静默门

def gate7_silent() -> dict:
    """except 降级必须可观测, 且不得伪装 ok=True。"""
    files = _py_files(SRC)
    violations = []
    silent = total_exc = 0
    for fp in files:
        rel = os.path.relpath(fp, ROOT)
        s = _read(fp)
        for m in re.finditer(r"(?m)^\s*except\b[^:]*:", s):
            total_exc += 1
            seg = s[m.end():m.end() + 200]
            if re.match(r"\s*pass\b", seg):
                silent += 1
                if not re.search(r"(logger|warning|counter|record_failure|audit)",
                                 seg[:400]):
                    violations.append({
                        "file": rel, "rule": "静默 except",
                        "detail": "except: pass 且无计数/日志"})
        # 伪装 ok=True  —— ★★ 2026-10-05 R10 改用 AST
        #   原判据要求 `return` 后紧跟行尾或 `-> dict`, 于是**最常见的**
        #   `return {"ok": True}` 反而检不出, 只有写了类型注解的才报红
        #   ⇒ 阳性测试实测抓到: 三种样例里只有带注解的那种被检出。
        #   字符窗口/正则窗口两版都试过, 都错(多行 dict 漏检、豁免的误报)
        #   ⇒ 根因: 用文本判"这个 dict 是不是被返回的"本质不可靠。
        try:
            tree2 = ast.parse(s)
        except (SyntaxError, UnicodeDecodeError):
            tree2 = None
        if tree2 is not None:
            for fnode in ast.walk(tree2):
                if not isinstance(fnode, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                for sub in ast.walk(fnode):
                    if not (isinstance(sub, ast.Return)
                            and isinstance(sub.value, ast.Dict)):
                        continue
                    pairs = list(zip(sub.value.keys, sub.value.values))
                    for k, v in pairs:
                        if not (isinstance(k, ast.Constant) and k.value == "ok"):
                            continue
                        if not (isinstance(v, ast.Constant) and v.value is True):
                            continue
                        # 函数体里有没有真副作用
                        has_effect = any(
                            isinstance(x, (ast.Assign, ast.AugAssign, ast.AnnAssign))
                            for x in ast.walk(fnode))
                        has_call = any(
                            isinstance(x, ast.Call)
                            and not (isinstance(x.func, ast.Name)
                                     and x.func.id in ("len", "str", "int",
                                                        "float", "bool", "list",
                                                        "dict", "set", "tuple"))
                            for x in ast.walk(fnode))
                        has_named = bool(re.search(
                            r"(TRUTH_SOURCE|actually_written|side_effect|"
                            r"readback|read_back|verify|persisted)", s))
                        if not (has_effect or has_call or has_named):
                            violations.append({
                                "file": rel, "rule": "疑似伪装成功",
                                "detail": "%s() 返回 {ok: True} 但无任何副作用"
                                          % fnode.name})
    return {
        "gate": 7, "name": "静默门", "lesson": "L5(延伸)",
        "files": len(files),
        "silent_except": silent, "except_total": total_exc,
        "violations": violations, "pass": not violations,
    }


# ---------------------------------------------------------------- 执行 + 留痕

def gate8_contract() -> dict:
    """★ R37 · 契约门 —— 设计定的 **K2/K3/K4** 是否落到代码里。

    ★★★ 依据: docs/COMPONENT_VOCABULARY.md §五「可机械检查的判据」
      设计已经写了 K1-K6，而**代码里一个都没有**（我实测 `target_layer`
      在 src 出现 0 次、`𝒦_meta` 0 次）⇒ 那正是「设计定了判据但没人
      实现」的缺口 —— 与母巢「门存在但没被执行」是同一族病。

    ★★ 为什么是**静态查存在性**而不是跑断言:
      G1-G7 全是静态扫描（gate 不 import src —— 门本身不能依赖被门对象）
      ⇒ 运行时对错交给 **pytest**（测试有真断言）
      ⇒⇒ 分工: gate 查「有没有实现」· pytest 查「对不对」

    ★★ 不查 K1（21 对象映射）—— 文档诚实边界⑧ 说「须先补对象清单，
      K1 目前无法验证」⇒ 我**不假装能查**（已知缺口，标 not_adopted）
    """
    files = _py_files(SRC)
    violations = []
    src_all = "".join(_read(f) for f in files)
    ev = os.path.join(SRC, "organs", "evolver.py")
    ca = os.path.join(SRC, "organs", "candidates.py")
    ev_s = _read(ev) if os.path.isfile(ev) else ""
    ca_s = _read(ca) if os.path.isfile(ca) else ""

    # ── K2: component ↔ target_layer 的**判据函数必须存在且被调用** ──
    if "def check_pairing" not in ev_s:
        violations.append({"file": "organs/evolver.py",
                           "rule": "K2 缺失",
                           "detail": "check_pairing 未定义（§四① 的一致性判据）"})
    else:
        # 调用方: 固化(evolver) + 生成(candidates) —— 两侧都要用
        if "check_pairing" not in ca_s.replace("from .evolver import", "", 1):
            violations.append({"file": "organs/candidates.py",
                               "rule": "K2 未被使用",
                               "detail": "生成侧没调 check_pairing ⇒ 形同虚设"})
        if "check_pairing(comp" not in ev_s and "check_pairing(_comp" not in ev_s:
            violations.append({"file": "organs/evolver.py",
                               "rule": "K2 未被使用",
                               "detail": "固化侧没调 check_pairing"})

    # ── K3: evaluator / external_source 必须 editable: False，且**在表里** ──
    # ★★★ R193 · 𝒦_meta 的真源已收口至 foundation/vocabulary.py（债 X4,
    #   单一真源 — evolver.py 只 import 同一对象）。门的正则若继续盯
    #   evolver.py 会把"收口"误报成"无表"（门跟着落后代码走 ⇒ 报假红）。
    #   ⇒ 改盯 vocabulary.py; 兜底再查 evolver.py（防将来又搬回去）。
    _voc_s = ""
    for _f in ("foundation/vocabulary.py", "organs/evolver.py"):
        _p = os.path.join(SRC, _f)
        if os.path.exists(_p):
            _t = io.open(_p, encoding="utf-8").read()
            if re.search(r"K_META\s*[:=]\s*", _t):
                _voc_s = _t
                break
    m = re.search(r"K_META\s*:\s*Dict\[str, bool\]\s*=\s*\{(.*?)\n\}",
                  _voc_s, re.S)
    if not m:
        m = re.search(r"K_META\s*=\s*\{(.*?)\n\}", _voc_s, re.S)
    if not m:
        violations.append({"file": "foundation/vocabulary.py",
                           "rule": "K3 无表",
                           "detail": "𝒦_meta 定义找不到（vocabulary.py 与 "
                                     "evolver.py 都没有）⇒ 5 个系统层对象无登记"})
    else:
        body = m.group(1)
        for name in ("evaluator", "external_source"):
            mm = re.search(r'"%s"\s*:\s*([^,\n]+)' % name, body)
            if not mm:
                violations.append({"file": "organs/evolver.py",
                                   "rule": "K3 缺项",
                                   "detail": "%s 不在 𝒦_meta 里（§3.4: 要求**在表里**但禁改）" % name})
            elif mm.group(1).strip() not in ("False",):
                violations.append({"file": "organs/evolver.py",
                                   "rule": "K3 可编辑",
                                   "detail": "%s: editable=%s（应为 False ⇒ evaluator 可被改就是破坏 grounded）"
                                            % (name, mm.group(1).strip())})

    # ── K4: 𝒦_meta 每项必须**显式**标 editable（无默认值）──
    if m:
        body = m.group(1)
        names = re.findall(r'"(\w+)"\s*:', body)
        vals = re.findall(r'"\w+"\s*:\s*([^,\n]+)', body)
        if any(v.strip() in ("", "None") for v in vals):
            violations.append({"file": "organs/evolver.py",
                               "rule": "K4 有默认值",
                               "detail": "𝒦_meta 存在空/None 的 editable 标志（必填无默认）"})
        if len(names) != 5:
            violations.append({"file": "organs/evolver.py",
                               "rule": "K4 项数",
                               "detail": "𝒦_meta 应 5 项，实得 %d: %s"
                                         % (len(names), names)})

    # ── §四① 的第二个字段: target_layer 必须在**两侧**都存在 ──
    # ★ 精确: 查 dataclass 字段定义（不是任何出现）
    _mca = re.search(r"\n\s{4}target_layer\s*:\s*str", ca_s)
    if not _mca:
        violations.append({"file": "organs/candidates.py",
                           "rule": "§四① 字段缺失",
                           "detail": "Candidate dataclass 无 target_layer ⇒ "
                                    "proposer 没声明第 2 个字段"})
    # ★★★ R37 破坏性测试抓到我这判据是**假的**:
    #   我原本写 `"target_layer" not in ev_s` —— 而 ev_s 里
    #   entry_from_candidate **到处**有 target_layer ⇒ 恒 False
    #   ⇒⇒ ⇒★ 破坏 RULE_ENTRY_FIELDS 却**抓不到**（4 类破坏漏 1）
    #     —— 这正是「断言必须精确到来源」（我 memory 里记着的）
    #   ⇒ ⇒★ 修: 只查 RULE_ENTRY_FIELDS **那一行**
    _mref = re.search(r"RULE_ENTRY_FIELDS\s*=\s*\([^)]*\)", ev_s, re.S)
    if not _mref:
        violations.append({"file": "organs/evolver.py",
                           "rule": "§四① 无 schema",
                           "detail": "RULE_ENTRY_FIELDS 找不到 ⇒ 固化不校验字段"})
    elif "target_layer" not in _mref.group(0):
        violations.append({"file": "organs/evolver.py",
                           "rule": "§四① 未进 schema",
                           "detail": "RULE_ENTRY_FIELDS 不含 target_layer ⇒ 固化不校验它"
                                    "（§四①: 第 2 个字段必须被检查）"})
    # ★ 精确: 查 prompt 字面量里**要求模型返回** target_layer
    if '"target_layer": "<' not in ca_s:  # ★ R37 改了占位符（自带映射）
        violations.append({"file": "organs/candidates.py",
                           "rule": "prompt 未要求",
                           "detail": "prompt 的 JSON 格式没让模型声明 "
                                    "target_layer（§四①『必须声明』）"})

    # ── K1: **不查**（文档诚实边界⑧: 需先补对象清单）──
    n_a = []
    if not files:
        n_a.append("src/dwc 无 .py")
    # ── K5: J 不可改（★ A4 · 18813 §2：判据在可写面之外）──
    #   evo 侧（evolver/candidates/evo_round）不许**写**判据面文件：
    #   judge.py（判分代码）· dev/test 真值 · 判分史（task_scores/evidence/
    #   score_history，judge.record 专属）。
    #   放行：rules.json（RULES 落盘合法）· ledger（evo 自家账本）· 纯读。
    #   静态近似：open/io.open 行内同时出现禁写名＋写标志才红。
    _J_GUARDED = ("judge.py", "dev.json", "test_sealed.json",
                  "dev_sealed_pairing.json", "train.json", "broken_dev.json",
                  "task_scores.jsonl", "evidence.jsonl",
                  "score_history.jsonl")
    _evo_side = {
        "organs/evolver.py": ev_s,
        "organs/candidates.py": ca_s,
    }
    _er = os.path.join(os.path.dirname(SRC), "scripts", "dwc_evo_round.py")
    try:
        _evo_side["scripts/dwc_evo_round.py"] = (
            io.open(_er, encoding="utf-8").read() if os.path.isfile(_er)
            else "")
    except OSError:
        _evo_side["scripts/dwc_evo_round.py"] = ""
    for _fn, _src in _evo_side.items():
        for _i, _ln in enumerate(_src.splitlines(), 1):
            _s = _ln.strip()
            if "open(" not in _s or _s.startswith("#"):
                continue
            _hit = [g for g in _J_GUARDED if g in _s]
            if not _hit:
                continue
            if ("\"w\"" in _s or "\"a\"" in _s or
                    "'w'" in _s or "'a'" in _s):
                violations.append({"file": _fn, "line": _i,
                                   "rule": "K5 J 被写",
                                   "detail": ("evo 侧写判据面 %s ⇒ 判据在可写面内"
                                            "（18813 §2 禁）" % _hit)})
    # ★ lesson: 七门对应母巢七条教训（L1-L7）
    #   G8 对应 **L1「设计定了但没人实现」** —— 文档里 K1-K6 写得
    #   一字不差，而 `target_layer` 在 src 出现 0 次
    #   ⇒⇒ 与母巢「门存在但没被执行」是同一族病（QUALITY_GATE 封底）
    #   ★ A4 · K5 对应 18813 §2「J 不可改」—— 判据在可写面之外。
    return {
        "gate": 8, "name": "契约门", "lesson": "L1",
        "files": len(files), "violations": violations,
        "pass": not violations,
        "n_a": n_a,
        "k1": "not_adopted（须先补 21 对象清单，见文档诚实边界⑧）",
    }




GATES = {
    1: gate1_locality, 2: gate2_truth, 3: gate3_activity,
    4: gate4_life_cycle, 5: gate5_claims, 6: gate6_subtraction,
    7: gate7_silent, 8: gate8_contract,
}


def record(results: list[dict]) -> None:
    """★ 门跑一次就留一次痕 —— 治"门存在但没人跑"。"""
    os.makedirs(os.path.dirname(TRACE), exist_ok=True)
    row = {"at": _dt.datetime.now().isoformat(timespec="seconds"),
           "gates": [{"gate": r["gate"], "name": r["name"],
                      "pass": r["pass"],
                      "violations": len(r.get("violations", []))}
                     for r in results]}
    with io.open(TRACE, "a", encoding="utf-8", newline="") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ★★ R10 (2026-10-05) · 第三种状态: 无可检对象 (n_a)
#   起因: 实测 src/dwc 为空时, G1/G2/G3/G4/G7 的循环体根本不执行,
#         violations 恒空 ⇒ 报 pass=True 而输出是 "[✓ PASS]"
#         ⇒ 【什么都能通过】与【什么都没检到】在输出里无法区分
#   修法: 这五道门扫 src/dwc 的 .py, files==0 时状态必须是 n_a,
#         不计入通过, 且退出码非 0。
#   ★ 与 G11「门通过 ≠ 系统安全」同族但更基础: 连"门是否真的检过东西"
#     此前都无法表达。
#   ★ NEED_FILES 由通读 420 行源码得出; 新增扫源码的门必须同步加进来。
NEED_FILES = {1, 2, 3, 4, 7}


def _status(r: dict) -> str:
    """四态: pass / fail / n_a（无可检对象）/ not_adopted（判据未被采纳）。

    ★★ n_a 与 not_adopted 的区别（R14 新增，勿混）:
        n_a         —— 这道门**要**检的东西不存在（如 src/dwc 下没有 .py）
        not_adopted —— 这道门要检的东西**尚未被项目采纳**（如六层活性模型）
      ⇒ 两者都不计入通过，但原因不同，排查时要能区分。
    ★★ not_adopted 只给 G3 用，因为只有它的判据基础是"候选而非必然"
      （QUALITY_GATE.md §门3 原文:「六层模型是候选，不是必然」）。
    """
    if r["gate"] in NEED_FILES and r.get("files", 0) == 0:
        return "n_a"
    # ★★★ R14 修正: fail 必须**优先于** not_adopted。
    #   原顺序(not_adopted 在前)会让真违规被"未采用"掩盖 —— 而那正是
    #   R10 修掉的假通过同族问题（该报的没报 / 报错了原因）。
    if not r["pass"]:
        return "fail"
    if r["gate"] == 3:
        # ★ 六层已由用户裁决采用（2026-10-05）⇒ not_adopted 不再是合法状态。
        #   但 Γ 尚未落地 ⇒ 也不能报 pass。⇒ 第五态: adopted_not_implemented
        #   ★★ 三态的关系（勿混）:
        #     not_adopted            —— 声明不用六层（已裁决采用，当前不应出现）
        #     adopted_not_implemented —— 采用已裁决，但六层/Γ 还没写出来（★ 当前）
        #     pass                   —— 采用且齐备
        if not r.get("six_layer_adopted", True):
            return "not_adopted"
        if not r.get("gamma_present", False):
            return "adopted_not_implemented"
    return "pass"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", type=int, choices=sorted(GATES))
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    keys = [args.gate] if args.gate else sorted(GATES)
    results = [GATES[k]() for k in keys]

    # ★★ 先算 status, 两条输出路径共用 —— 否则 --json 会缺这个字段
    for r in results:
        r["status"] = _status(r)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2, default=str))
    else:
        print("DWC 质量门  (%s)" % _dt.datetime.now().strftime("%Y-%m-%d %H:%M"))
        print("=" * 68)
        for r in results:
            mark = {"pass": "[✓ PASS]", "fail": "[✗ FAIL]",
                    "n_a":  "[○ N/A ]", "not_adopted": "[◐ 未采用]",
                    "adopted_not_implemented": "[◑ 待实现]"}[r["status"]]
            nv = len(r.get("violations", []))
            print("%s G%d %-8s (%s)  files=%-3s 违规 %d" % (
                mark, r["gate"], r["name"], r["lesson"],
                r.get("files", "—"), nv))
            if r["status"] == "n_a":
                print("        ★ 无可检对象（src/dwc 下无 .py）⇒ 本门**未被检验**"
                      " ⇒ 不计为通过")
            elif r["status"] == "not_adopted":
                print("        ★ 六层活性模型**尚未被项目采纳**"
                      " ⇒ 本门本项**未被检验** ⇒ 不计为通过")
            elif r["status"] == "adopted_not_implemented":
                print("        ★★ 六层活性模型**已裁决采用**（2026-10-05）"
                      " 但 Γ 尚未落地（无 causal_chain 实现）"
                      " ⇒ 本门本项**未被检验** ⇒ 不计为通过"
                      " ⇒ 待办: organs/ + foundation/causal_chain.py")
            for v in r.get("violations", [])[:8]:
                print("        · %s | %s | %s" % (
                    v.get("file", "")[:34], v.get("rule", ""),
                    str(v.get("detail", ""))[:52]))
            if nv > 8:
                print("        … 另 %d 条" % (nv - 8))
        real_fail = [r for r in results if r["status"] == "fail"]
        n_a = [r for r in results if r["status"] == "n_a"]
        n_ad = [r for r in results if r["status"] == "not_adopted"]
        n_ai = [r for r in results if r["status"] == "adopted_not_implemented"]
        unchecked = n_a + n_ad + n_ai
        print("=" * 68)
        if real_fail:
            print("总结: 有门未过（%d 道）—— 不许合入 src/dwc/" % len(real_fail))
        elif unchecked:
            parts = []
            if n_a:
                parts.append("%d 道无可检对象" % len(n_a))
            if n_ad:
                parts.append("%d 道判据未采纳" % len(n_ad))
            if n_ai:
                parts.append("%d 道已采纳待实现" % len(n_ai))
            print("总结: %d 道通过 / %s（均未计入通过）"
                  % (len(results) - len(unchecked), " + ".join(parts)))
        else:
            print("总结: 全部通过")
        print("痕迹: %s" % os.path.relpath(TRACE, ROOT))

    record(results)
    # ★★ n_a 也算非 0 —— "没检查到任何东西"不许被当成"通过"
    for r in results:
        r.setdefault("status", _status(r))
    return 0 if all(r["status"] == "pass" for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())