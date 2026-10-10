import sys, io, json
sys.path.insert(0, 'src')
from dwc.harness.loop import Loop
from dwc.harness import gates

lp = Loop(planner_live=True)
print("planner_live:", lp.planner_live)
r = lp.round(1)
print("injection after round restored:", gates.planner_layer_injection())
# 从最近一轮 chain 的 per_contract 里找 planner_live 痕迹
lk = r.get("ledger") or {}
print("round keys:", sorted(r.keys())[:10])
