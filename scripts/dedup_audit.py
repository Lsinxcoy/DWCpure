# -*- coding: utf-8 -*-
"""严格去重审计: 提取 6 套体系的逐字对象清单 + 交叉比对。"""
import io, os, re, json
ROOT = r"E:/Divine Wisdom Core/.cache/gh_clones"
OUT  = r"E:/Divine Wisdom Core/docs/DEDUP_AUDIT_6SYSTEMS.md"

def rd(p):
    try: return io.open(p,encoding="utf-8",errors="replace").read()
    except Exception: return ""

# ---------- 体系 1: 12 层 (Prometheus-X / Omega) ----------
layers12 = []
p = os.path.join(ROOT,"Prometheus-X","src/prometheus_x/evolution/layers.py")
t = rd(p)
for m in re.finditer(r'class (L\d+\w*)\(EvolutionLayer\):\s*"""(.*?)"""', t, re.S):
    layers12.append((m.group(1), " ".join(m.group(2).split())[:120]))
# 补: 若类名不全, 从 name = 常量取
if len(layers12) < 12:
    names = re.findall(r'name\s*=\s*"(L\d+_\w+)"', t)
    layers12 = [(n, "") for n in names]

# ---------- 体系 2: 9 维 (ARSI) ----------
p = os.path.join(ROOT,"ARSI","src/arsi/harness/taxonomy.py")
t = rd(p)
dims9 = re.findall(r'"(c\d)"\s*:\s*"([^"]+)"', t)
frozen = re.search(r'FROZEN_DIMS\s*=\s*frozenset\((\{[^}]*\})\)', t)

# ---------- 体系 3: 4 层 (CIP / hermes-CI) ----------
p = os.path.join(ROOT,"hermes-collective-intelligence","evolution_layers/evolution_layers.py")
t = rd(p)
layers4 = re.findall(r'class (L\d\w*Mutator)', t)

# ---------- 体系 4: 4 轨 (Ultra) ----------
p = os.path.join(ROOT,"Prometheus-Ultra-MultiTypeKB","docs/multi_type_kb_seven_pipe_evolution.md")
t1 = rd(p)
tracks_a = re.findall(r'\|\s*(T[1-4])\s*([^|]+?)\s*\|', t1)
p = os.path.join(ROOT,"Prometheus-Ultra-MultiTypeKB","docs/p7_handbook_behavior_localization.md")
t2 = rd(p)
tracks_b = re.search(r'\(T1[^)]+\)', t2)

# ---------- 体系 5: 3 方向 ----------
p = os.path.join(ROOT,"Prometheus-X","src/prometheus_x/evolution/strategies.py")
t = rd(p)
dirs3 = re.findall(r'class (\w+Direction)', t)
p2 = os.path.join(ROOT,"Prometheus-Y","prometheus_y/evolution/direction.py")
t2b = rd(p2)
dirs3b = re.findall(r'EvolutionDirection\.(\w+)', t2b)

# ---------- 体系 6: 15 变异 (MSTAR) ----------
p = os.path.join(ROOT,"hermes-mstar","evolution/mutator.py")
t = rd(p)
mut15 = re.search(r'15种变异操作(.*?)╚', t, re.S)
mut_names = re.findall(r'\b(field_add|field_remove|field_modify|read_modify|write_modify|query_add|'
                       r'keyword_add|keyword_remove|keyword_replace|threshold|priority|guidance|'
                       r'crossover|ensemble|random_change)\b', t)

print("="*80); print("【体系1】12 层 (Prometheus-X)"); print("="*80)
for n,d in layers12: print("   %-22s %s" % (n,d))
print("\n"+"="*80); print("【体系2】9 维 (ARSI)"); print("="*80)
for a,b in dims9: print("   %-5s %s" % (a,b))
print("   冻结: %s" % (frozen.group(1) if frozen else "?"))
print("\n"+"="*80); print("【体系3】4 层 (hermes-CI)"); print("="*80)
for x in layers4: print("   %s" % x)
print("\n"+"="*80); print("【体系4】4 轨 (Ultra) —— ★两套命名"); print("="*80)
print("   版本A (multi_type_kb_seven_pipe_evolution.md):")
for a,b in tracks_a[:6]: print("      %s = %s" % (a, b.strip()))
print("   版本B (p7_handbook_behavior_localization.md):")
print("      %s" % (tracks_b.group(0) if tracks_b else "?"))
print("\n"+"="*80); print("【体系5】3 方向"); print("="*80)
print("   Prometheus-X: %s" % dirs3)
print("   Prometheus-Y: %s" % sorted(set(dirs3b)))
print("\n"+"="*80); print("【体系6】15 变异 (MSTAR)"); print("="*80)
print("   源码命中: %s" % sorted(set(mut_names)))
print("   计数: %d" % len(set(mut_names)))

json.dump({"layers12":layers12,"dims9":dims9,"layers4":layers4,
           "tracks_a":tracks_a,"tracks_b":tracks_b.group(0) if tracks_b else "",
           "dirs3":dirs3,"dirs3b":sorted(set(dirs3b)),"mut15":sorted(set(mut_names))},
          io.open(r"E:/Divine Wisdom Core/.cache/dedup_raw.json","w",encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\n已存 .cache/dedup_raw.json")
