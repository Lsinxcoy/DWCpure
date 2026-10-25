# -*- coding: utf-8 -*-
"""全量扫描 39 仓库的进化设计 —— 只报实测, 不推断。"""
import io, os, re, json

ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache", "gh_clones")
OUT  = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache", "evolution_scan.json")

# 进化核心的判据维度 (每条都可机械查)
CRIT = {
  "selftest_before_apply": [r'不提升就不提交', r'不提升不提交', r'先测后落', r'测.{0,6}再.{0,6}(提交|落地|应用)',
                            r'progression.{0,20}(不|没).{0,10}(提升|提高)'],
  "shadow_mech":           [r'影子期', r'set_shadow', r'\bSHADOW\b', r'shadow_gate|ShadowGate', r'影子(候选|审计|模式|通路|登记|记账)'],
  "rollback":              [r'def rollback', r'inverse_op', r'revert', r'回滚'],
  "gate_apply":            [r'def (accept|admit|gate|apply|promote)\w*\(', r'acceptance', r'非补偿|non.?compensatory'],
  "genome_param":          [r'class .*(Genome|Chromosome|Gene)\b', r'GENE_TARGETS', r'def mutate', r'def crossover'],
  "effect_anchor":         [r'effect_anchor', r'EXTERNAL_SOURCES', r'INTERNAL_PLACEHOLDERS', r'grounding'],
  "world_model":           [r'world_model|WorldModel', r'predict_effect|predict_transition', r'world_evolver', r'world_pool'],
  "manifest":              [r'change_manifest|ChangeManifest', r'manifest\.jsonl', r'edit_type'],
  "selection":             [r'select_best', r'offline_replay', r'probe_tasks', r'tournament', r'elit'],
  "frozen":                [r'FROZEN_DIMS', r'iron_laws|IronLaw', r'INVARIANTS', r'冻结'],
}

def read(p):
    try: return io.open(p, encoding="utf-8", errors="replace").read()
    except Exception: return ""

rows = []
for repo in sorted(os.listdir(ROOT)):
    rp = os.path.join(ROOT, repo)
    if not os.path.isdir(rp): continue
    py = []
    for dp, dn, fns in os.walk(rp):
        dn[:] = [x for x in dn if x not in ("__pycache__", ".git", "node_modules", ".venv", "venv")]
        for f in fns:
            if f.endswith(".py"): py.append(os.path.join(dp, f))
    blob = {}
    for p in py:
        blob[p] = read(p)
    allpy = "\n".join(blob.values())
    # 进化相关文件
    evo_files = [p for p in py if re.search(r'evol|harness|world_model|gene|mutat|fitness|accept|manifest|shadow|replay',
                                            os.path.relpath(p, rp), re.I)]
    row = {"repo": repo, "py_files": len(py), "py_chars": len(allpy),
           "evo_files": len(evo_files),
           "crit": {}}
    for k, pats in CRIT.items():
        n = 0; files = set()
        for pat in pats:
            for m in re.finditer(pat, allpy, re.I):
                n += 1
                # 定位文件
                for fp, txt in blob.items():
                    if re.search(pat, txt, re.I):
                        files.add(os.path.relpath(fp, rp)); break
        row["crit"][k] = {"hits": n, "files": len(files)}
    rows.append(row)
    print("%-38s py=%-5d evo=%-4d %s" % (
        repo, len(py), len(evo_files),
        " ".join("%s:%d" % (k[:6], v["hits"]) for k, v in row["crit"].items() if v["hits"])))

os.makedirs(os.path.dirname(OUT), exist_ok=True)
json.dump(rows, io.open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("\n已存:", OUT)
