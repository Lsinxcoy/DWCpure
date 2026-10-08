# -*- coding: utf-8 -*-
"""★ grown 终局判读（R67 · 事前规则 —— 规则写死在跑数据之前）。

判读规则（事前, 不看结果调）:
  n = 4 任务 × 4 重复 = 16 trial/臂
  口径A 保守: LLM 挂的 trial 计 fail（与实验 pass_rate 一致）
  口径B 端点剔除: 挂的 trial 不入分母（R66 教训: 端点故障污染 none）
  差值规则（两口径同规则）:
    Δ = (臂X − 臂Y) 的 trial 数差（16 为分母）
    Δ ≥ +4 且 臂X ≥ none   → ★ 方向初步成立
    |Δ| ≤ 2                 → 噪声（四轮信号不成立）
    3 ≤ |Δ| < 4             → 方向但强度不足
  检验对: (replay, guidance)=论文方向 · (guidance, none)=V1
"""
import json
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PATH = os.path.join(ROOT, "archive", "experiments",
                    "mem_guidance_vs_replay_grown_r4.json")
ARMS = ("none", "guidance", "replay")


def trials(records, arm):
    """(task, rep) → {'pass': bool|None, 'hung': bool}"""
    out = {}
    for r in records:
        if r.get("arm") != arm or r.get("rep", -1) < 0:
            continue
        key = (r["task"], r["rep"])
        t = out.setdefault(key, {"pass": None, "hung": False})
        if r.get("pass_") is True:
            t["pass"] = True
        elif r.get("pass_") is False and t["pass"] is not True:
            t["pass"] = False
        if not r.get("llm_ok") or "llm:" in str(r.get("error", "")):
            t["hung"] = True          # 端点故障（超时/空返回/失败）
    return out


def verdict(delta, x_rate_ge_none=None):
    if abs(delta) <= 2:
        return "噪声"
    if delta >= 4 and x_rate_ge_none:
        return "★ 方向初步成立"
    if delta >= 4 and x_rate_ge_none is False:
        return "X 高但低于 none ⇒ 不算"
    return "方向但强度不足"


def main():
    d = json.load(io.open(PATH, encoding="utf-8"))
    recs = d["records"]
    print("=" * 66)
    print("★ grown 终局判读（事前规则 · %s · repeat=%s）"
          % (d.get("at", "?"), d.get("repeat")))
    print("=" * 66)
    data = {a: trials(recs, a) for a in ARMS}
    hdr = "%-10s %6s %10s %14s %12s %14s"
    print(hdr % ("arm", "trials", "口径A pass", "A rate",
                 "口径B pass", "B rate(剔挂)"))
    stats = {}
    for a in ARMS:
        ts = data[a]
        n = len(ts)
        pA = sum(1 for t in ts.values() if t["pass"] is True)
        ok = [t for t in ts.values() if not t["hung"]]
        pB = sum(1 for t in ok if t["pass"] is True)
        stats[a] = {"n": n, "pA": pA, "nB": len(ok), "pB": pB,
                    "hung": n - len(ok)}
        print(hdr % (a, n, "%d/%d" % (pA, n),
                     "%.3f" % (pA / n) if n else "-",
                     "%d/%d" % (pB, len(ok)),
                     "%.3f" % (pB / len(ok)) if ok else "-"))

    def delta(x, y, key):
        return stats[x][key] - stats[y][key]

    print("\n（判读规则: Δ≥+4 且 X≥none → 初步成立; |Δ|≤2 → 噪声; 3≤|Δ|<4 → 强度不足）")
    for x, y, tag in (("replay", "guidance", "论文方向 replay>guidance"),
                      ("guidance", "none", "V1 记忆增益")):
        dA = delta(x, y, "pA")
        dB = delta(x, y, "pB")
        geA = stats[x]["pA"] >= stats[y]["pA"]
        geB = stats[x]["pB"] >= stats[y]["pB"]
        print("  %-32s 口径A Δ=%+d → %s | 口径B Δ=%+d → %s"
              % (tag, dA, verdict(dA, geA), dB, verdict(dB, geB)))
    h = {a: stats[a]["hung"] for a in ARMS}
    print("\n★ 端点挂（不入口径B 分母）: %s" % h)
    print("★ 逐任务×臂 原始记录: %s" % os.path.relpath(PATH, ROOT))
    # 逐 task 分解（钉死信号来源）
    print("\n%-14s %-16s %-16s %-16s" % ("task", "none", "guidance", "replay"))
    tasks = sorted({r["task"] for r in recs if r.get("arm") in ARMS})
    for t in tasks:
        row = []
        for a in ARMS:
            ts = [(rep, v["pass"], v["hung"]) for (tk, rep), v
                  in sorted(data[a].items()) if tk == t]
            row.append(" ".join("%s" % ("P" if p else ("H" if h2 else "F"))
                                for _, p, h2 in ts))
        print("%-14s %-16s %-16s %-16s" % (t, row[0], row[1], row[2]))
    print("（P=pass F=fail H=挂）")


if __name__ == "__main__":
    sys.exit(main())
