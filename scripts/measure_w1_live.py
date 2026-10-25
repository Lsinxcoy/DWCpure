"""一次性真实测量探针：使用真实配置与真实 LLM，不输出凭证或 prompt。"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from dwc.llm.client import LLMClient
import dwc.llm.client as lc
from dwc.llm.task_exec import execute_user_task
from dwc.observability.context import configure_store
from dwc.observability.evidence_store import EvidenceStore

out = Path(os.environ["DWC_MEASURE_OUT"])
out.mkdir(parents=True, exist_ok=True)
store = EvidenceStore(out / "measure.sqlite")
configure_store(store)
lc._OBS_SINK = __import__("dwc.observability.context", fromlist=["emit_llm_observation"]).emit_llm_observation
result = execute_user_task(
    "请只回答一个字：好。不要解释。",
    llm=LLMClient(), task_id="T_W1_REAL_002", max_rounds=2, retry_on_fail=False,
)
events = store.query()
report = {
    "task": {k: v for k, v in result.items() if k not in {"actions_log", "answer"}},
    "answer_chars": len(result.get("answer") or ""),
    "n_events": len(events),
    "kinds": {k: sum(1 for e in events if e["kind"] == k) for k in sorted({e["kind"] for e in events})},
    "attempts": [{k: e["payload"].get(k) for k in (
        "task_id", "call_role", "transport", "attempt_index", "usage_status",
        "model_requested", "model_reported", "finish_reason", "ok")}
        | {"usage": (e["payload"].get("usage") or {})} for e in events if e["kind"] == "llm_attempt"],
    "task_metrics": [e["payload"] for e in events if e["kind"] == "task_metrics"],
}
(out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
store.close()
