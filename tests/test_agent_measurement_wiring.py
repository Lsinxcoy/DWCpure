"""DWC-AUTO · W1 agent 启动挂载测试。"""
from pathlib import Path


def test_agent_mounts_shared_measurement_store_and_preserves_read_driver():
    src = Path("scripts/dwc_agent.py").read_text(encoding="utf-8")
    assert "configure_store" in src
    assert "emit_llm_observation" in src
    assert "dwc_metrics.sqlite" in src
    assert "_te._OBS_SINK = _PARAM_DRIVER.observe_read" in src


def test_measurement_store_path_isolated_from_test_var(monkeypatch, tmp_path):
    from dwc.observability import context as mc
    from dwc.observability.evidence_store import EvidenceStore
    store = EvidenceStore(tmp_path / "agent.sqlite")
    previous = mc._STORE
    try:
        mc.configure_store(store)
        store.append("boot", {"status": "ok"}, idempotency_key="boot-1")
        assert len(store.query("boot")) == 1
    finally:
        mc.configure_store(previous)
        store.close()
