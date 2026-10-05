# -*- coding: utf-8 -*-
"""提取 39 仓库的进化模块结构: 目录/文件/核心类名/关键设计符号。"""
import io, os, re, json

ROOT = r"E:/Divine Wisdom Core/.cache/gh_clones"
OUT  = r"E:/Divine Wisdom Core/.cache/evolution_struct.json"

EVO_DIR = re.compile(r'(evolution|evol|harness|world_model|self_improve|rsi|meta|gene)', re.I)

def read(p):
    try: return io.open(p, encoding="utf-8", errors="replace").read()
    except Exception: return ""

rows = []
for repo in sorted(os.listdir(ROOT)):
    rp = os.path.join(ROOT, repo)
    if not os.path.isdir(rp): continue
    evo_files = []      # 进化相关文件
    for dp, dn, fns in os.walk(rp):
        dn[:] = [x for x in dn if x not in ("__pycache__", ".git", "node_modules", ".venv", "venv", "tests", "test")]
        for f in fns:
            if not f.endswith(".py"): continue
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, rp).replace("\\", "/")
            if EVO_DIR.search(rel):
                evo_files.append((rel, p))
    # 每仓库: 类名 + 关键函数 + docstring 首行
    classes, funcs, notes = [], [], []
    for rel, p in evo_files:
        t = read(p)
        for m in re.finditer(r'(?m)^class (\w+)', t):
            classes.append(m.group(1))
        for m in re.finditer(r'(?m)^def (\w+)', t):
            funcs.append(m.group(1))
        d = re.search(r'"""(.*?)"""', t, re.S)
        if d:
            first = " ".join(d.group(1).split())[:150]
            if first: notes.append((rel, first))
    rows.append({
        "repo": repo,
        "n_evo_files": len(evo_files),
        "evo_files": [r for r, _ in evo_files][:40],
        "classes": sorted(set(classes))[:60],
        "funcs": sorted(set(funcs))[:60],
        "notes": notes[:14],
    })
    print("=" * 78)
    print("### %s   (进化相关文件 %d)" % (repo, len(evo_files)))
    for r, _ in evo_files[:18]:
        print("     %s" % r)

json.dump(rows, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n已存:", OUT)
