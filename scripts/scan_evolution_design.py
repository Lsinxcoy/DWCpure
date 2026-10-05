# -*- coding: utf-8 -*-
"""深读 39 仓库的进化设计意图: 核心进化模块 docstring + 关键类 + 落地/应用符号。"""
import io, os, re, json

ROOT = r"E:/Divine Wisdom Core/.cache/gh_clones"
OUT  = r"E:/Divine Wisdom Core/.cache/evolution_design.json"

# 只看真正承载"进化设计"的文件
CORE = re.compile(r'(evolution|harness|world_model|self_improve|rsi|evolvemem|mutator|fitness|'
                  r'gene|manifest|accept|gates|anti_evolution|coevolve|iron_law|version_control|'
                  r'reflector|predictor|protocol|robustness|full_spectrum|north_star)', re.I)
SKIP = re.compile(r'(test|/tests?/|__pycache__|\.git|node_modules|venv)', re.I)

def read(p):
    try: return io.open(p, encoding="utf-8", errors="replace").read()
    except Exception: return ""

# 应用/落地类符号 (判据: 是否真写)
APPLY = re.compile(r'(def apply\w*|def promote\w*|def commit\w*|def write_back|def setattr|'
                   r'setattr\(|def _apply|def rollback|def revert)', re.I)

rows = []
for repo in sorted(os.listdir(ROOT)):
    rp = os.path.join(ROOT, repo)
    if not os.path.isdir(rp): continue
    mods = []
    for dp, dn, fns in os.walk(rp):
        dn[:] = [x for x in dn if x not in ("__pycache__", ".git", "node_modules", ".venv", "venv")]
        for f in fns:
            if not f.endswith(".py"): continue
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, rp).replace("\\", "/")
            if SKIP.search(rel) or not CORE.search(rel): continue
            t = read(p)
            if len(t) < 400: continue
            d = re.search(r'"""(.*?)"""', t, re.S)
            doc = " ".join(d.group(1).split())[:260] if d else ""
            classes = [m.group(1) for m in re.finditer(r'(?m)^class (\w+)', t)]
            applies = sorted(set(m.group(0) for m in APPLY.finditer(t)))[:8]
            mods.append({"file": rel, "chars": len(t), "doc": doc,
                         "classes": classes[:8], "apply_syms": applies})
    rows.append({"repo": repo, "n_mods": len(mods), "mods": mods})
    print("=" * 80)
    print("### %s  (进化核心模块 %d)" % (repo, len(mods)))
    for m in mods[:12]:
        print("  · %s  [%d 字符]" % (m["file"], m["chars"]))
        if m["doc"]: print("      说明: %s" % m["doc"][:230])
        if m["classes"]: print("      类: %s" % ", ".join(m["classes"]))
        if m["apply_syms"]: print("      落地符号: %s" % ", ".join(m["apply_syms"]))

json.dump(rows, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n已存:", OUT)
