# -*- coding: utf-8 -*-
"""R434 · 提示词候选生成器（append-only，禁改历史版本）。

    python scripts/dwc_prompt_candidate.py \
        --name task_exec --base v1 \
        --rule "问标识符类问题（类名/变量名/文件名）时，必须先 search_code 取证再 final。"

产出 `prompts/task_exec.v2.md` = 基线原文 + 一段「硬规则」。

★ 为什么不是"让 LLM 重写整份提示词"：
  重写会让**所有**句子同时变化，A/B 赢了也不知道是哪句赢的。
  追加一条规则是**单变量**改动，归因干净 —— 这是能进闭环的前提。
★ 已存在的版本**拒绝覆盖**：历史版本是 A/B 的对照组，改了就回不去。
"""
from __future__ import annotations

import argparse
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPTS = os.path.join(ROOT, "prompts")


def next_ver(name: str) -> str:
    """下一个可用版本号（v1, v2, …）。"""
    vs = []
    for f in os.listdir(PROMPTS):
        m = re.fullmatch(re.escape(name) + r"\.v(\d+)\.md", f)
        if m:
            vs.append(int(m.group(1)))
    return "v%d" % (max(vs) + 1 if vs else 1)


def read_ver(name: str, ver: str) -> str:
    p = os.path.join(PROMPTS, "%s.%s.md" % (name, ver))
    if not os.path.isfile(p):
        raise SystemExit("找不到基线: %s" % p)
    return io.open(p, encoding="utf-8").read()


def build(base: str, rules: list) -> str:
    body = base.rstrip("\n")
    if not rules:
        raise SystemExit("至少给一条 --rule")
    block = ["", "★★★ 硬规则（必须遵守，违反即视为未完成任务）:"]
    for i, r in enumerate(rules, 1):
        block.append("%d. %s" % (i, r.strip()))
    return body + "\n" + "\n".join(block) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="提示词名（如 task_exec）")
    ap.add_argument("--base", default=None, help="基线版本（缺省=manifest stable）")
    ap.add_argument("--rule", action="append", default=[],
                    help="要追加的硬规则（可多次给）")
    ap.add_argument("--rule-file", default=None, help="从文件读规则（每行一条）")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    rules = list(a.rule)
    if a.rule_file:
        for line in io.open(a.rule_file, encoding="utf-8"):
            if line.strip() and not line.strip().startswith("#"):
                rules.append(line.strip())

    base_ver = a.base
    if not base_ver:
        import json
        mf = json.load(io.open(os.path.join(PROMPTS, "manifest.json"),
                               encoding="utf-8"))
        base_ver = (mf.get(a.name) or {}).get("stable") or "v1"

    base = read_ver(a.name, base_ver)
    new_ver = next_ver(a.name)
    out = build(base, rules)
    dest = os.path.join(PROMPTS, "%s.%s.md" % (a.name, new_ver))

    if a.dry_run:
        print("[dry-run] 将写 %s（%d 字节，基线 %s + %d 条规则）"
              % (dest, len(out.encode("utf-8")), base_ver, len(rules)))
        return 0

    if os.path.exists(dest):
        raise SystemExit("拒绝覆盖已存在版本: %s" % dest)
    tmp = dest + ".tmp"
    with io.open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(out)
    os.replace(tmp, dest)
    print("已生成 %s（基线 %s + %d 条规则，%d 字节）"
          % (os.path.relpath(dest, ROOT), base_ver, len(rules),
             len(out.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
