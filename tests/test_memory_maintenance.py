"""DWC-AUTO · M3.1 maintenance plan: no age-only delete, SELF protected."""
from __future__ import annotations

from dwc.organs.memory import MemoryKernel, MemoryKind
from dwc.organs.memory_maintenance import decide, plan


def test_never_recalled_is_keep_not_delete():
    d = decide(node_id="n", zone="proxy", access_count=0, effect_count=0,
               effect_samples=20)
    assert d["strategy"] == "KEEP" and d["delete_allowed"] is False


def test_self_is_always_keep():
    d = decide(node_id="s", zone="self", access_count=10, effect_count=0,
               effect_samples=20, explicit_delete=True)
    assert d["strategy"] == "KEEP" and d["delete_allowed"] is False


def test_archive_requires_effect_samples_and_zero_effect():
    assert decide(node_id="n", zone="proxy", access_count=1, effect_count=0,
                  effect_samples=9)["strategy"] == "KEEP"
    assert decide(node_id="n", zone="proxy", access_count=1, effect_count=0,
                  effect_samples=10)["strategy"] == "ARCHIVE"


def test_delete_requires_explicit_flag():
    base = dict(node_id="n", zone="proxy", access_count=1, effect_count=0,
                effect_samples=20)
    assert decide(**base)["strategy"] == "ARCHIVE"
    assert decide(**base, explicit_delete=True)["strategy"] == "DELETE"


def test_plan_does_not_write(tmp_path):
    mem = MemoryKernel(str(tmp_path / "m.db"))
    mem.remember(MemoryKind.TRACE, {"task": "t"})
    before = mem.usage_stats()
    out = plan(mem)
    assert out["n_evaluated"] >= 1
    assert mem.usage_stats() == before
