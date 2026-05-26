"""Unit tests for baseline model and anomaly detection."""

from app.ml.models.baseline_model import is_anomalous


def test_fast_response_flagged_with_reliable_baseline():
    baseline = {"mean": 90.0, "std": 30.0, "n": 20, "reliable": True}
    assert is_anomalous(5, baseline) is True


def test_normal_response_not_flagged():
    baseline = {"mean": 90.0, "std": 30.0, "n": 20, "reliable": True}
    assert is_anomalous(80, baseline) is False


def test_unreliable_baseline_uses_fallback_threshold():
    baseline = {"mean": 90.0, "std": 30.0, "n": 1, "reliable": False}
    assert is_anomalous(10, baseline) is True
    assert is_anomalous(20, baseline) is False
