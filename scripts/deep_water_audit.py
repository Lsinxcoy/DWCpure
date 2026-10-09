# -*- coding: utf-8 -*-
"""深水六欠账机器盘点 —— R136 · 防"凭旧记忆判缺口"(2026-07-26 教训)。

盘点对象(旧记忆的六项): Z4 · Z5 · δ_θ · ECE · Appendix D · coupling
      · 动作分发全路由（实为 7 项 — 逐项列, 不漏不多）

方法(逐项机器可复算, 禁抽样):
  每项输出 status ∈ {live, partial, absent} + **代码证据**(文件:行号:
  命中计数) + **判定依据**(实现存在 ≠ 接入主链, 双重检)
    ① code_hits  : 源码命中（grep 等价, 在 src/ 全树）
    ② wired_hits : 是否被主链调用（core.py/organs 间的引用）
  依据不足 ⇒ absent（不装"实现过"）; 部分接入 ⇒ partial。
输出: docs/deep_water_audit.json（机器计数 + 逐项证据 + 汇总裁决）
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any, Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")


def scan(pattern: str, sub: str = "src", *,
         exclude_rx: str = r"not_dispatched|未做|未路由|不路由|TODO"
         ) -> List[str]:
    """机器计数: 匹配行, 空 list=未命中。

    ★ exclude_rx 默认排除自陈/否决行 — 源码里的"未做/不路由"字样
      是**诚实边界声明**, 不是功能接线; 不排除会把 absent 误判 partial
      （R136 实测: core.py 的 not_dispatched 字样曾把 routing 抬高）。
    """
    rx = re.compile(pattern)
    ex = re.compile(exclude_rx)
    hits = []
    for dirpath, _dirs, files in os.walk(os.path.join(ROOT, sub)):
        for fn in files:
            if not fn.endswith(".py"):
                continue
            p = os.path.join(dirpath, fn)
            try:
                for i, line in enumerate(open(p, encoding="utf-8"), 1):
                    if rx.search(line) and not ex.search(line):
                        hits.append("%s:%d:%s" % (
                            os.path.relpath(p, ROOT), i,
                            line.strip()[:70]))
            except (UnicodeDecodeError, OSError):
                continue
    return hits


# 七项逐一定义（含 grep 正则可机器复算 + 主链接线检查点）
ITEMS: List[Dict[str, Any]] = [
    {"id": "Z4", "name": "候选持久化+lineage",
     "code_rx": r"Z4|candidates\.persist|candidates\.lineage",
     "wire_rx": r"cand_persist|candidates_persist|lineage",
     "doc_note": "dial_config.py L104-110 实现过（旧轮 R56/R68 系列）"},
    {"id": "Z5", "name": "merge 三条件+发生率日志",
     "code_rx": r"Z5|merge\.require_all|log_rate",
     "wire_rx": r"merge_occurs|log_rate|require_all",
     "doc_note": "dial_config.py L112-116 实现过"},
    {"id": "delta_theta", "name": "δ_θ 残差难度（weakness 器官⑥）",
     # ★ R137 修正: 首版正则只扫 "delta_theta" 字样 ⇒ 漏掉真实现
     #   weakness.py 用 task_delta_map/delta_group/Difficulty 命名
     #   （δ_θ 只在模块 docstring/锁名出现）⇒ partial 误判, 实为 live。
     "code_rx": r"delta_theta|task_delta_map|delta_group|Difficulty"
                r"|δ_θ|Laplace",
     "wire_rx": r"task_delta_map|_task_deltas",
     "doc_note": (" weakness.py 332 行(器官⑥探索, 路线丙组内基线: "
                  "δⁱ=[−log r]₊, Laplace k=1) + core._task_deltas "
                  "L331/356 已接进 step = LIVE(R136 误判 partial, "
                  "R137 修正)")},
    {"id": "ECE", "name": "校准误差(Expected Calibration Error)",
     "code_rx": r"\bECE\b|expected_calibration|calibration_error",
     "wire_rx": r"ece\s*=|compute_ece|expected_calibration",
     "doc_note": "eq10.py 有 CALIBRATION 常量(同名不同物?)"},
    # ★ R139 修正: R136 的"Appendix D（2609.11873 附录算法）"描述有误
    #   — 论文实测: 2609.11873.txt 全文 0 个编号 Algorithm; 附录只有
    #   A(RSI Landscape)/B(Industry Landscape) 是综述名录非算法;
    #   2607.25675(DecoEvo/Eq.10 源) 也无附录算法 ⇒ **该欠账不存在**
    #   ⇒ 保留条目但改成"不存在的欠账"留档（防旧记忆复发）, 判定 absent
    {"id": "AppendixD", "name": "论文附录编号算法（不存在项 — R139 核实）",
     # code_rx 只认**算法实现名**（不认"附录/AppD"字样 — 那些是注释
     #   讨论, R139 实测 6 处全是 docstring ⇒ 讨论≠实现的纪律）
     "code_rx": r"def\s+appendix|class\s+Appendix|APPENDIX_ALGO",
     "wire_rx": r"appendix_algo",
     "doc_note": ("R139 核实: 2609.11873 全文 0 编号 Algorithm, 附录 A/B "
                  "是综述名录非算法; 2607.25675 无附录 ⇒ 欠账不存在; "
                  "留档防旧记忆复发")},
    {"id": "coupling", "name": "器官间耦合机制",
     "code_rx": r"coupl|couplings|organ_coupl",
     "wire_rx": r"coupling_|couple\(",
     "doc_note": "七器官间是否有显式耦合通道"},
    # ★ R139 修正: R138 实现了 remember+dream 真路由（dispatch dict 契
    #   约）⇒ wire_rx 旧只认 dispatch_action/_route 漏了新分发面
    {"id": "routing", "name": "动作分发全路由",
     "code_rx": r"routing|dispatch|route\(|action_dispatched",
     "wire_rx": r"dispatch|action_dispatched",
     "doc_note": ("R138 后: remember+dream 真路由, learn/evolve/maintain "
                  "/未知显式 not_dispatched（逐动作理由）⇒ **未全覆盖** "
                  "（有 dispatch 面≠全路由 — 判据用 dispatched=True 分支"
                  "数 / ACTIONS 数, 不靠字样）"),
     # ★ 语义判据（不靠 grep 字样）: 从源码数 dispatched=True 分支与
     #   ACTIONS 全集比对（注释/自陈行排除）
     "semantic_check": "routing_coverage"},
]


def routing_coverage() -> Dict[str, Any]:
    """★ 真语义判据（不靠字样）: core.py 的 ACTIONS 全集 vs step() 内
    dispatched=True 的实际分支 — 未全覆盖 ⇒ partial（有分发面≠全路由）。"""
    import ast
    core = os.path.join(SRC, "dwc", "core.py")
    tree = ast.parse(open(core, encoding="utf-8").read(),
                     filename=core)
    actions = None
    for node in ast.walk(tree):
        if (isinstance(node, ast.AnnAssign) and
                getattr(node.target, "id", "") == "ACTIONS"):
            actions = [e.value for e in node.value.elts]
    n_true_branch = 0
    step_src = ""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "step":
            step_src = ast.get_source_segment(
                open(core, encoding="utf-8").read(), node) or ""
    # dispatched": True 的分支（源码字面）— 排除 not_dispatched 自陈行
    for line in step_src.splitlines():
        if 'dispatched": True' in line and "not_dispatched" not in line:
            n_true_branch += 1
    return {"actions_total": len(actions) if actions else None,
            "dispatched_true_branches": n_true_branch,
            "uncovered": (len(actions) - n_true_branch
                          if actions else None),
            "fully_routed": (actions is not None and
                             n_true_branch >= len(actions))}


def audit() -> Dict[str, Any]:
    out: List[Dict[str, Any]] = []
    for item in ITEMS:
        code = scan(item["code_rx"])
        wire = scan(item["wire_rx"])
        semantic = None
        if item.get("semantic_check") == "routing_coverage":
            semantic = routing_coverage()
            # 未全覆盖 ⇒ partial（覆盖 grep 的 live 误判）
            if not semantic["fully_routed"]:
                wire = []   # 强制降级: 语义判据优先于字样计数
        # 判定: 主链有调用=live; 只声明/只常量=partial; 零命中=absent
        if wire:
            status = "live"
        elif code:
            status = "partial"
        else:
            status = "absent"
        out.append({
            "id": item["id"], "name": item["name"],
            "status": status,
            "semantic": semantic,
            "code_hits": len(code), "wire_hits": len(wire),
            "code_evidence": code[:6],
            "wire_evidence": wire[:6],
            "doc_note": item["doc_note"],
        })
    counts = {"live": 0, "partial": 0, "absent": 0}
    for o in out:
        counts[o["status"]] += 1
    return {"items": out, "summary": counts, "n_items": len(out)}


def main() -> int:
    ap = __import__("argparse").ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "docs",
                                                  "deep_water_audit.json"))
    args = ap.parse_args()
    res = audit()
    doc = {
        "probe": ("R136: 深水六欠账机器盘点（实 7 项）— 逐项 status + "
                  "代码证据(文件:行号) + 主链接线双重检; 依据不足⇒absent "
                  "不装『实现过』；防凭旧记忆判缺口(2026-07-26 教训)"),
        "method": ("code_rx 全 src/ 树扫 + wire_rx 主链接线扫; "
                   "wire_hits>0=live; 仅 code>0=partial(声明/常量/锁名); "
                   "双 0=absent。机器可复算, 禁抽样"),
        "items": res["items"],
        "summary": res["summary"],
        "n_items": res["n_items"],
        "verdict": {
            "next_rounds": [o["id"] for o in res["items"]
                            if o["status"] != "live"],
            "reading": ("深水项 %d/7 已 live; %s 待办 — %s"
                        % (res["summary"]["live"],
                           ([o["id"] for o in res["items"]
                             if o["status"] != "live"] or "无"),
                           "partial 项须逐项判『实现存在但未接主链』→ 接线; "
                           "absent 项须从论文原文起建")),
        },
        "caveats": [
            "grep 计数 = 存在性证据, 不等于行为正确性（行为须专项测试）",
            "wire_rx 是启发式主链标志 — 误判风险存在, 逐项人工复核在下一轮",
            "本盘点不改任何源码（只读）",
        ],
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    for o in res["items"]:
        print("%-12s %-8s code=%2d wire=%2d  %s"
              % (o["id"], o["status"], o["code_hits"], o["wire_hits"],
                 o["name"]))
    print("汇总裁决: live=%d partial=%d absent=%d / 共 %d"
          % (res["summary"]["live"], res["summary"]["partial"],
             res["summary"]["absent"], res["n_items"]))
    print("待办:", doc["verdict"]["next_rounds"])
    print("写出:", args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
