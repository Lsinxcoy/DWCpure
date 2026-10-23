# -*- coding: utf-8 -*-
"""深读设计最丰富的仓库: 实际代码片段 (门/顺序/落地)。"""
import io, os, re
ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache", "gh_clones")

def show(repo, rel, pats, ctx=340, limit=3):
    p = os.path.join(ROOT, repo, rel)
    if not os.path.exists(p): print("!! 缺 %s/%s" % (repo, rel)); return
    t = io.open(p, encoding="utf-8", errors="replace").read()
    print("\n" + "="*84)
    print("### %s / %s  [%d 字符]" % (repo, rel, len(t)))
    for pat in pats:
        ms = list(re.finditer(pat, t, re.S))
        if not ms: continue
        print("  ── /%s/  (%d 处)" % (pat[:52], len(ms)))
        for m in ms[:limit]:
            seg = " ".join(t[max(0,m.start()-90):m.start()+ctx].split())
            print("     … %s" % seg[:420])

# 1) Prometheus-Z: 反进化门 4 前置
show("Prometheus-Z", "src/prometheus_z/evolution/anti_evolution_gate.py",
     [r'def gate_check.*?(?=\n    def |\Z)', r'DEDUP|INSIGHT|APPLICATION|CONSECUTIVE'])
# 2) MSTAR: 4 门质量检查
show("hermes-mstar", "evolution/quality_gates.py",
     [r'四门检查.*?\n', r'def (check_all|check_compile|check_runtime|check_logic|check_quality)\w*\([^)]*\)'])
# 3) MSTAR: 版本控制 + rollback
show("MSTAR-Pro-V4.0", "mstar_core/evolution/version_control.py",
     [r'def verify_mutation.*?(?=\n    def )', r'def rollback_to.*?(?=\n    def )'])
# 4) prometheus: 5-organ pipeline
show("prometheus", "integration/guided_evolution.py",
     [r'五器官|taotie|nuwa|darwin|pool|guard', r'def (run|step|evolve|execute)\w*\([^)]*\)'])
# 5) Protogonos: 3-tier evolution memory + promote
show("Protogonos", "protogonos/memory/evolution_memory.py",
     [r'def promote.*?(?=\n    def )', r'class MemoryTier'])
# 6) Prometheus-Z: five gates
show("Prometheus-Z", "src/prometheus_z/store/five_gates.py",
     [r'def check_all.*?(?=\n    def )', r'GATE_\w+'])
