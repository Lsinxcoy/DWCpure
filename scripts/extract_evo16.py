# -*- coding: utf-8 -*-
"""提取 16 篇(进化相关)报告的 §2 核心机制 + §5 可迁移点。"""
import io, os, re

D = r"E:/Divine Wisdom Core/docs/papers"
EVO16 = ["2603.06333","2603.25111","2606.09498","2606.14249","2607.12790","2608.10299",
         "2608.24876","2609.04128","2609.06396","2609.08183","2609.11873","2609.13406",
         "2609.14857","2609.14858","2609.24972","2609.26457"]

def section(t, num_pat, next_pat):
    """取 ## N. xxx 到下一个 ## 之间"""
    m = re.search(r'(?m)^#{1,3}\s*' + num_pat + r'[^\n]*$', t)
    if not m: return ""
    rest = t[m.end():]
    m2 = re.search(r'(?m)^#{1,3}\s*' + next_pat, rest)
    return rest[:m2.start()] if m2 else rest

for pid in EVO16:
    p = os.path.join(D, pid + ".md")
    if not os.path.exists(p):
        print("!! 缺 %s" % pid); continue
    t = io.open(p, encoding="utf-8", errors="replace").read()
    title = ""
    m = re.search(r'(?m)^#\s*(.+)$', t)
    if m: title = m.group(1).strip()
    core = section(t, r'2\.', r'3\.')
    mig  = section(t, r'5\.', r'6\.')
    print("\n" + "="*94)
    print("### %s  %s" % (pid, title[:90]))
    print("-"*94)
    print("【§2 核心机制】")
    print(" ".join(core.split())[:2300] if core else "(未找到)")
    print("\n【§5 可迁移/不可迁移】")
    print(" ".join(mig.split())[:1800] if mig else "(未找到)")
