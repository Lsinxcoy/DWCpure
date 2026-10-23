# -*- coding: utf-8 -*-
"""判决性: 每个仓库的落地是否"真写" —— 找 setattr / 真赋值 / 版本切换, 而非只生成提案。"""
import io, os, re, json

ROOT = ros.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache", "gh_clones")

def read(p):
    try: return io.open(p, encoding="utf-8", errors="replace").read()
    except Exception: return ""

# 真写符号 (会改变运行时状态)
REAL_WRITE = [
 (r'setattr\(', "setattr 真写"),
 (r'\bself\.\w+\s*=\s*(?!None\b)\w', "实例赋值"),
 (r'def (apply|apply_|apply_gene|apply_mutation|apply_suggested\w*|write_back|commit\w*|activate\w*|mount\w*)\s*\(', "apply/commit/mount 方法"),
 (r'\.(save|flush|persist|write_text|write_bytes|to_sql|execute)\s*\(', "落盘"),
 (r'(json\.dump|open\([^)]*[\'"]w)', "写文件"),
]
# 只提案符号 (不改变状态)
PROPOSAL = [
 (r'def (propose|suggest|plan|draft|render|report)\w*\s*\(', "propose/suggest/plan"),
 (r'reviewable|review_required|requires_review|人工审|待审', "需人工审"),
 (r'manifest\.jsonl|manifests\.jsonl', "manifest 台账"),
 (r'status\s*[:=]\s*[\'"]accepted[\'"]', "status=accepted"),
 (r'status\s*[:=]\s*[\'"]applied[\'"]', "status=applied"),
]

rows = []
for repo in sorted(os.listdir(ROOT)):
    rp = os.path.join(ROOT, repo)
    if not os.path.isdir(rp): continue
    evo = []
    for dp, dn, fns in os.walk(rp):
        dn[:] = [x for x in dn if x not in ("__pycache__", ".git", "node_modules", ".venv", "venv", "tests")]
        for f in fns:
            if not f.endswith(".py"): continue
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, rp).replace("\\", "/")
            if re.search(r'(evolution|evolv|harness|mutator|gene|accept|gates|manifest|rsi|five_gates|compile_to_rule)', rel, re.I):
                evo.append((rel, p))
    allt = "\n".join(read(p) for _, p in evo)
    rw = {lab: len(re.findall(pat, allt)) for pat, lab in REAL_WRITE}
    po = {lab: len(re.findall(pat, allt, re.I)) for pat, lab in PROPOSAL}
    rows.append({"repo": repo, "files": len(evo), "real_write": rw, "proposal": po})

print("%-34s %4s | %s | %s" % ("仓库", "文件", "真写符号", "只提案符号"))
print("-"*150)
for r in rows:
    rw = r["real_write"]; po = r["proposal"]
    print("%-34s %4d | %s | %s" % (
      r["repo"][:34], r["files"],
      " ".join("%s:%d" % (k.split()[0], v) for k, v in rw.items() if v),
      " ".join("%s:%d" % (k.split()[0], v) for k, v in po.items() if v)))

json.dump(rows, io.open(ros.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache", "write_vs_propose.json"),"w",encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n已存 .cache/write_vs_propose.json")
