# -*- coding: utf-8 -*-
"""严格去重审计: 6 套体系的逐字清单 + 两两交叉比对矩阵。"""
import io, os, re, json
ROOT = r"E:/Divine Wisdom Core/.cache/gh_clones"
def rd(p):
    try: return io.open(p,encoding="utf-8",errors="replace").read()
    except Exception: return ""

# ---------- 逐字提取 ----------
# 1) 12 层
t = rd(os.path.join(ROOT,"Prometheus-X","src/prometheus_x/evolution/layers.py"))
layers12 = re.findall(r'name\s*=\s*"(L\d+_\w+)"', t)
# 2) 9 维
t = rd(os.path.join(ROOT,"ARSI","src/arsi/harness/taxonomy.py"))
dims9 = [b for _,b in re.findall(r'"(c\d)"\s*:\s*"([^"]+)"', t)]
# 3) 4 层
t = rd(os.path.join(ROOT,"hermes-collective-intelligence","evolution_layers/evolution_layers.py"))
layers4 = re.findall(r'class (L\d\w*Mutator)', t)
# 4) 4 轨 (两套)
tracksA = ["T1 参数","T2 语义","T3 提取","T4 编译"]
tracksB = ["T1 参数","T2 语义","T3 GitHub机制","T4 论文机制"]
# 5) 3 方向
dirs3 = ["FORWARD","LATERAL","REVERSE"]
# 6) 15 变异 (枚举名)
t = rd(os.path.join(ROOT,"hermes-mstar","evolution/mutator.py"))
mut15 = sorted(set(re.findall(r'MutationType\.([A-Z_]+)', t)))

print("="*84); print("【1】12 层逐字 (%d)" % len(layers12)); print("="*84)
for x in layers12: print("   %s" % x)
print("="*84); print("【2】9 维逐字 (%d)" % len(dims9)); print("="*84)
for x in dims9: print("   %s" % x)
print("="*84); print("【3】4 层逐字 (%d)" % len(layers4)); print("="*84)
for x in layers4: print("   %s" % x)
print("="*84); print("【4】4 轨 A/B 两套"); print("="*84)
print("   A: %s" % tracksA); print("   B: %s" % tracksB)
print("="*84); print("【5】3 方向"); print("="*84)
print("   %s" % dirs3)
print("="*84); print("【6】15 变异逐字 (%d)" % len(mut15)); print("="*84)
for x in mut15: print("   %s" % x)

# ---------- 语义归并 (人工判据表) ----------
# 把每套体系的每项映射到"统一对象"名
MAP = {
 # 12 层 → 统一名
 "L0_MetaParams":"标量参数/超参", "L1_Strategy":"策略", "L2_Skill":"技能", "L3_Config":"标量参数/超参",
 "L4_Code":"代码", "L5_MetaEvolution":"元进化", "L6_Prompt":"提示词", "L7_Tool":"工具",
 "L8_Memory":"记忆", "L9_Knowledge":"知识", "L10_Collaboration":"协作", "L11_Architecture":"架构",
 # 9 维
 "model_selection":"模型选择","context_assembly":"上下文","memory_management":"记忆",
 "tool_ecosystem":"工具","execution_environment":"执行环境","evaluation_and_reward":"评估器",
 "control_and_safety":"控制/安全","observability":"观测","training_bridge":"训练桥",
 # 4 层
 "L1ConfigMutator":"标量参数/超参","L2SkillMutator":"技能","L3BehaviorMutator":"行为/工作流","L4CodeMutator":"代码",
 # 4 轨 (A 版为准, B 版标注别名)
 "T1 参数":"标量参数/超参","T2 语义":"知识","T3 提取":"外部机制源(GitHub)","T4 编译":"外部机制源(论文)",
 # 3 方向
 "FORWARD":"方向:前进","LATERAL":"方向:横向","REVERSE":"方向:后退",
 # 15 变异
 "SCHEMA_FIELD_ADD":"变异:结构增","SCHEMA_FIELD_REMOVE":"变异:结构删","SCHEMA_FIELD_MODIFY":"变异:结构改",
 "LOGIC_READ_MODIFY":"变异:逻辑读改","LOGIC_WRITE_MODIFY":"变异:逻辑写改","LOGIC_QUERY_ADD":"变异:逻辑查询增",
 "KEYWORD_ADD":"变异:关键词增","KEYWORD_REMOVE":"变异:关键词删","KEYWORD_REPLACE":"变异:关键词替",
 "THRESHOLD_ADJUST":"变异:阈值调","PRIORITY_ADJUST":"变异:优先级调","GUIDANCE_MODIFY":"变异:指导改",
 "CROSSOVER":"变异:交叉","ENSEMBLE":"变异:集成","RANDOM_CHANGE":"变异:随机",
}

print("\n"+"="*84); print("★ 归并到统一对象后, 各体系覆盖数"); print("="*84)
def cover(items):
    return sorted(set(MAP.get(x, "?%s"%x) for x in items))
c12, c9, c4, cA, cB, c3, c15 = cover(layers12), cover(dims9), cover(layers4), cover(tracksA), cover(tracksB), cover(dirs3), cover(mut15)
for name, c in [("12层",c12),("9维",c9),("4层",c4),("4轨A",cA),("4轨B",cB),("3方向",c3),("15变异",c15)]:
    print("\n   【%s】→ %d 个统一对象" % (name, len(c)))
    print("      %s" % ", ".join(c))

# ---------- 并集 ----------
allobj = sorted(set(c12)|set(c9)|set(c4)|set(cA)|set(cB)|set(c3)|set(c15))
print("\n"+"="*84); print("★ 6 套体系并集 = %d 个统一对象" % len(allobj)); print("="*84)
for x in allobj: print("   %s" % x)

json.dump({"layers12":layers12,"dims9":dims9,"layers4":layers4,"tracksA":tracksA,"tracksB":tracksB,
           "dirs3":dirs3,"mut15":mut15,"union":allobj,
           "cover":{"12层":c12,"9维":c9,"4层":c4,"4轨A":cA,"4轨B":cB,"3方向":c3,"15变异":c15}},
          io.open(r"E:/Divine Wisdom Core/.cache/dedup_result.json","w",encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("\n已存 .cache/dedup_result.json")
