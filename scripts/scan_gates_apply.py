# -*- coding: utf-8 -*-
"""深读各仓库"过门→落地"的具体设计: 门有几步 + 落地怎么做 + 失败怎么办。"""
import io, os, re, json

ROOT = r"E:/Divine Wisdom Core/.cache/gh_clones"

TARGETS = [
 ("ARSI", "src/arsi/harness/accept.py"),
 ("ARSI", "src/arsi/harness/evolver.py"),
 ("ARSI", "src/arsi/harness/manifest.py"),
 ("MSTAR-Pro-V4.0", "mstar_core/evolution/quality_gates.py"),
 ("MSTAR-Pro-V4.0", "mstar_core/evolution/version_control.py"),
 ("MSTAR-Pro-V4.0", "mstar_core/evolution/engine.py"),
 ("Prometheus-Z", "src/prometheus_z/evolution/anti_evolution_gate.py"),
 ("Prometheus-Z", "src/prometheus_z/store/five_gates.py"),
 ("Prometheus-Z", "src/prometheus_z/evolution/compile_to_rule.py"),
 ("Prometheus-Omega-Genesis", "src/omega/evolution/anti_evolution_gate.py"),
 ("Prometheus-Omega-Genesis", "src/omega/evolution/iron_law.py"),
 ("Prometheus-Omega-Genesis", "src/omega/evolution/engine.py"),
 ("Prometheus-Y", "prometheus_y/evolution/extensions.py"),
 ("Protogonos", "protogonos/memory/evolution_memory.py"),
 ("hermes-collective-intelligence", "evolution_layers/evolution_layers.py"),
 ("CIP-Zhazhazhu", "hermes_cip/evolution/full_spectrum.py"),
 ("hermes-mstar", "evolution/quality_gates.py"),
 ("prometheus", "cip/layers/L5_meta_evolution.py"),
 ("prometheus", "integration/guided_evolution.py"),
 ("Prometheus-Ultra", "src/prometheus_ultra/evolution/evolution_engine.py"),
]

def read(p):
    try: return io.open(p, encoding="utf-8", errors="replace").read()
    except Exception: return ""

for repo, rel in TARGETS:
    p = os.path.join(ROOT, repo, rel)
    if not os.path.exists(p):
        print("!! 缺: %s / %s" % (repo, rel)); continue
    t = read(p)
    print("=" * 82)
    print("### %s / %s   [%d 字符]" % (repo, rel, len(t)))
    d = re.search(r'"""(.*?)"""', t, re.S)
    if d: print("说明: %s" % " ".join(d.group(1).split())[:500])
    # 门/步骤
    for pat, lab in [(r'(?m)^\s*#\s*(STEP|Step)\s*\d.*$', "步骤注释"),
                     (r'(?m)^\s*def (gate|check|verify|accept|admit|apply|promote|commit|rollback|revert)\w*\([^)]*\)', "关键方法"),
                     (r'(?m)^\s*(GATE|STEP|PHASE)_\w+\s*[:=].*$', "常量")]:
        ms = [m.group(0).strip() for m in re.finditer(pat, t)]
        if ms:
            print("  [%s]" % lab)
            for x in ms[:12]: print("     %s" % x[:130])
    print()
