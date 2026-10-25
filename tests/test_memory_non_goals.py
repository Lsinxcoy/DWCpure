"""DWC-AUTO · M3.4 conditional extensions stay off until evidence exists."""
from __future__ import annotations

import pytest

from dwc.organs.memory_policy import FEATURES, enabled, require


def test_all_heavy_features_default_off():
    assert FEATURES
    assert all(v is False for v in FEATURES.values())
    for name in FEATURES:
        assert enabled(name) is False


def test_unknown_feature_is_fail_closed():
    assert enabled("not_a_feature") is False
    with pytest.raises(RuntimeError):
        require("vector_retrieval")
