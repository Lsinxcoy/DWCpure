# -*- coding: utf-8 -*-
"""取具体清单: 12层 / 15变异 / 4门 / 9维 / 四轨。"""
import io, os, re
ROOT = ros.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".cache", "gh_clones")
def rd(p):
    try: return io.open(p,encoding="utf-8",errors="replace").read()
    except Exception: return ""

def grab(repo, rel, pat, ctx=700, n=2, label=""):
    p=os.path.join(ROOT,repo,rel)
    if not os.path.exists(p): print("!! 缺 %s/%s"%(repo,rel)); return
    t=rd(p); print("\n"+"="*80); print("### %s — %s" % (label or rel, repo))
    for m in list(re.finditer(pat,t,re.S))[:n]:
        print("   " + " ".join(t[m.start():m.start()+ctx].split())[:760])

# 1) 12 层清单
grab("Prometheus-X","src/prometheus_x/evolution/layers.py", r'class L0MetaParams', 260, 1, "12 层清单(类名)")
print("   " + "\n   ".join("L%d: %s"%(i,n) for i,n in enumerate(
  ["MetaParams","Strategy","Skill","Config","Code","MetaEvolution","Prompt","Tool","Memory","Knowledge","Collaboration","Architecture"])))
# 2) MSTAR 15 变异
grab("hermes-mstar","evolution/mutator.py", r'15种变异|分类:', 900, 1, "MSTAR 15 种变异")
# 3) MSTAR 4 门
grab("hermes-mstar","evolution/quality_gates.py", r'四门检查', 400, 1, "MSTAR 4 门")
# 4) Ultra 四轨 T1-T4
for f in ["src/prometheus_ultra/evolution/evolution_state.py",
          "src/prometheus_ultra/evolution/t1_4_track.py"]:
    p=os.path.join(ROOT,"Prometheus-Ultra-MultiTypeKB",f)
    if os.path.exists(p):
        t=rd(p); print("\n"+"="*80); print("### 四轨 %s [%d]" % (f,len(t)))
        for m in list(re.finditer(r'(T1|T2|T3|T4)[^\n]{0,120}',t))[:10]:
            print("   "+" ".join(m.group(0).split())[:150])
# 5) ARSI 9 维 + 双 Omega
grab("ARSI","src/arsi/harness/taxonomy.py", r'DIMENSIONS\s*=\s*\{', 900, 1, "ARSI 9 维")
# 6) Prometheus-Z compile_to_rule 阈值
grab("Prometheus-Z","src/prometheus_z/evolution/compile_to_rule.py", r'0\.95|def compile', 500, 2, "compile_to_rule 固化阈值")
