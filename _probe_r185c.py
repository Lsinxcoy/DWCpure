import sys, json
sys.path.insert(0, 'src')
from dwc.harness.loop import Loop
from dwc.llm.client import LLMClient

lp = Loop(planner_live=True)
lp.round(1)
tr = lp._last_planner_trace
print("full trace json:")
print(json.dumps(tr, ensure_ascii=False, indent=1)[:1500])
c = LLMClient()
r = c.complete("回复 OK 两个字符即可", max_tokens=16)
print("LLM ping:", getattr(r, "text", None))
