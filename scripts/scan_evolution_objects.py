# -*- coding: utf-8 -*-
"""每个仓库的进化对象清单 (能改什么) —— 从类名/常量/枚举机械抽取。"""
import io, os, re, json
ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache", "gh_clones")

def read(p):
    try: return io.open(p, encoding="utf-8", errors="replace").read()
    except Exception: return ""

PATS = [
 (r'L(\d)\s*[:：]?\s*(MetaParams|Strategy|Skill|Config|Behavior|Code|Prompt|Memory|Knowledge|Tool|Architecture|Meta\w*|Reasoning\w*)', "L层"),
 (r'class\s+(L\d\w*)\s*\(', "L层类"),
 (r'"c(\d)"\s*:\s*"([^"]+)"', "c维"),
 (r'(FROZEN_DIMS\s*=\s*[^\n]+)', "冻结维"),
 (r'(GENE_TARGETS\s*=\s*\{)', "基因目标"),
 (r'(DIMENSIONS\s*=\s*[\[\(][^\n]{0,200})', "维度表"),
 (r'(LAYER_\w+\s*=\s*\d+)', "层常量"),
 (r'(EvolutionDirection\.[A-Z_]+)', "方向"),
]

rows=[]
for repo in sorted(os.listdir(ROOT)):
    rp=os.path.join(ROOT,repo)
    if not os.path.isdir(rp): continue
    evo=[]
    for dp,dn,fns in os.walk(rp):
        dn[:]=[x for x in dn if x not in ("__pycache__",".git","node_modules",".venv","venv","tests")]
        for f in fns:
            if f.endswith(".py"):
                p=os.path.join(dp,f); rel=os.path.relpath(p,rp).replace("\\","/")
                if re.search(r'(evolution|evolv|harness|mutator|gene|accept|gates|layers|rsi)', rel, re.I):
                    evo.append(read(p))
    t="\n".join(evo)
    if not t: rows.append({"repo":repo,"objects":[]}); continue
    objs=set()
    for pat,lab in PATS:
        for m in re.finditer(pat,t):
            g=[x for x in m.groups() if x]
            objs.add("%s: %s" % (lab, " ".join(g)[:60]))
    rows.append({"repo":repo,"objects":sorted(objs)})

for r in rows:
    print("="*80)
    print("### %s   (%d 个对象标记)" % (r["repo"], len(r["objects"])))
    for o in r["objects"][:22]: print("    %s" % o)
json.dump(rows, io.open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache", "evolution_objects.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n已存 .cache/evolution_objects.json")
