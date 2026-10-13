# -*- coding: utf-8 -*-
"""R257 · step_judge 规则版 × AEWM-Action-Judge-Bench 校准报告（外部锚, grounded②）。

★ 数据: HF RUC-AIBOX/AEWM-Action-Judge-Bench（3,000 决策, gold 三分类）。
★ 适配（诚实标注）: bench 输入是**自然语言 judge prompt**（history+candidate 文本）;
  DWC 规则版吃**结构化** (recent_obs, step) —— 适配器从文本抽命令序列/失败信号/
  editor path, 映射 R1/R2/R3。R3 在 bench 上语义变形为"历史内已证伪路径"
  （本机文件系统不可查, 环境不同）。**适配损失必然存在** — 报告的是
  "规则版可判规则子集在 bench 语料上的表现", 不是 DWC 在线判别的表现。
★ 不调 LLM — 纯规则, 零成本可复跑。

用法: python scripts/calibrate_step_judge.py [--domain terminal] [--limit N]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
from collections import Counter

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "src"))

BENCH = os.path.join(_ROOT, "var", "aewm_bench",
                     "action_judge_benchmark_3000.jsonl")

#: 失败信号（Terminal 域 bash 输出特征）
_FAIL_SIG = re.compile(
    r"(No such file or directory|command not found|Traceback \(most recent"
    r" call last\)|Permission denied|SyntaxError|IndentationError|"
    r"cannot open|does not exist|bash: line \d+|Error:|FAILED|"
    r"AssertionError)", re.I)

#: 从 user prompt 抽 candidate 工具调用（execute_bash / str_replace_editor）
_CAND_BASH = re.compile(r"execute_bash\(\s*\{.*?\"command\"\s*:\s*\"((?:[^\"\\\\]|\\\\.)*)\"",
                        re.S)
_CAND_EDITOR = re.compile(
    r"str_replace_editor\(\s*\{.*?\"command\"\s*:\s*\"(view|create|str_replace|insert)\".*?"
    r"\"path\"\s*:\s*\"([^\"]+)\"",
    re.S)


def _unesc(s: str) -> str:
    try:
        return json.loads('"%s"' % s.replace('"', '\\"')[-min(len(s) + 2, 10**6):]) \
            if False else bytes(s, "utf-8").decode("unicode_escape", "replace")
    except Exception:                             # noqa: BLE001
        return s


def parse_terminal(text: str):
    """(hist_cmds, hist_fail_cmds, hist_bad_paths, cand_op, cand_key)

    ★ bench 渲染格式（实测）: `- bash({"command": "..."})` + `tool_observation:`
      段; candidate 在 <current_action> 内同形态。"""
    m_cur = re.search(r"<current_action>(.*)$", text, re.S)
    if m_cur:
        cand_zone, hist_zone = m_cur.group(1), text[: m_cur.start()]
    else:
        cand_zone, hist_zone = text, ""
    cmd_re = re.compile(r'bash\(\s*\{"command"\s*:\s*"((?:[^"\\]|\\.)*)"\s*\}')
    hist_cmds, hist_fail_cmds = [], []
    for m in cmd_re.finditer(hist_zone):
        cmd = _unesc(m.group(1)).strip()
        hist_cmds.append(cmd)
        # 观测段: 到下一次 tool_calls / message_index / history 尾
        seg = hist_zone[m.end(): m.end() + 2500]
        cut = re.search(r"(tool_calls:|\[message_index)", seg)
        obs_zone = seg[: cut.start()] if cut else seg
        if _FAIL_SIG.search(obs_zone) or "cannot open" in obs_zone.lower():
            hist_fail_cmds.append(cmd)
    hist_bad_paths = set()
    for m in re.finditer(r'path"\s*:\s*"([^"]+)".{0,600}?(No such file|'
                         r'does not exist|cannot open)', hist_zone, re.S):
        hist_bad_paths.add(m.group(1))
    mb = cmd_re.search(cand_zone)
    if mb:
        return hist_cmds, hist_fail_cmds, hist_bad_paths, "run", _unesc(mb.group(1)).strip()
    me = _CAND_EDITOR.search(cand_zone)
    if me:
        return hist_cmds, hist_fail_cmds, hist_bad_paths, "editor", me.group(2)
    return hist_cmds, hist_fail_cmds, hist_bad_paths, "other", ""


def judge_adapted(hist_cmds, hist_fail_cmds, hist_bad_paths, op, key) -> str:
    """★ R1/R2/R3 的 bench 适配版（对齐 step_judge 语义, 见模块 docstring）。"""
    if op == "run" and key:
        if key in hist_fail_cmds:
            return "noisy"                      # R2: 同命令已失败仍重发
        if hist_cmds.count(key) >= 2:
            return "noisy"                      # R1: 同命令已重复
    if op == "editor" and key in hist_bad_paths:
        return "noisy"                          # R3b: 历史内已证伪路径
    return "exploratory"                        # 显式保留探索类（论文教训）


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", default="terminal",
                    choices=("terminal", "search", "swe", "all"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    if not os.path.exists(BENCH):
        print("✗ bench 缺: %s（hf-mirror 下载 README 见文件头）" % BENCH)
        return 1
    cm = Counter()
    per_label = Counter()
    n = 0
    with io.open(BENCH, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            d = json.loads(line)
            if args.domain != "all" and d["domain"] != args.domain:
                continue
            if d["domain"] != "terminal":
                continue     # 首版只适配 Terminal（bash/editor 与 DWC 动作同构）
            text = "\n".join(m.get("content", "") for m in d["messages"]
                             if m.get("role") == "user")
            parsed = parse_terminal(text)
            pred = judge_adapted(*parsed)
            gold = d["gold_action_type"]
            cm[(gold, pred)] += 1
            per_label[gold] += 1
            n += 1
            if args.limit and n >= args.limit:
                break
    labels = ("critical", "exploratory", "noisy")
    print("==== step_judge 规则版 × AEWM Bench（terminal, n=%d）====" % n)
    print("%-12s %7s %7s %7s" % ("gold\\pred", *labels))
    f1s = []
    for g in labels:
        row = [cm[(g, p)] for p in labels]
        print("%-12s %7d %7d %7d" % (g, *row))
        tp = cm[(g, g)]
        fp = sum(cm[(x, g)] for x in labels if x != g)
        fn = sum(cm[(g, x)] for x in labels if x != g)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        f1s.append(f1)
        print("  P=%.3f R=%.3f F1=%.3f (n=%d)" % (prec, rec, f1, per_label[g]))
    macro = sum(f1s) / len(f1s)
    acc = sum(cm[(x, x)] for x in labels) / max(1, n)
    print("macro-F1=%.3f  acc=%.3f" % (macro, acc))
    print("★ 对照（论文 §4.2, 同 bench 真值）: GPT-5.5 55.3 / DeepSeek-V4-Pro 59.9"
          " / AEWM 70.5（macro-F1, 全域池化）")
    print("★ 适配损失: 规则版只见 Terminal 文本可抽信号（R1/R2/R3b）, "
          "critical/无信号 exploratory 全部归一 — F1 低是预期内, "
          "校准对象是 R1-R3 的**触发精度**, 非全域分类")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
