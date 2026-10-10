import sys, json
sys.path.insert(0, 'src')
from dwc.harness.loop import Loop
from dwc.harness import gates

lp = Loop(planner_live=True)
for i in (1, 2):
    r = lp.round(i)
    print("round", i, "| planner_live:", lp.planner_live,
          "| trace:", json.dumps(lp._last_planner_trace,
                                 ensure_ascii=False)[:220])
print("restored:", gates.planner_layer_injection())
