"""Unit tests for risk scoring — no DB required."""

import pytest
from app.ml.models import risk_model


def test_model_loads_without_error():
    risk_model.load()
    assert risk_model._model is not None
    assert risk_model._scaler is not None


def test_low_risk_prediction():
    features = {
        "adherence_7d": 0.95, "adherence_14d": 0.94, "adherence_30d": 0.93,
        "avg_response_time_seconds": 120.0,
        "side_effect_reports_14d": 0, "missed_visits_30d": 0,
    }
    score, level = risk_model.predict(features)
    assert 0 <= score <= 100
    assert level in ("LOW", "MODERATE")


def test_critical_risk_prediction():
    features = {
        "adherence_7d": 0.10, "adherence_14d": 0.12, "adherence_30d": 0.15,
        "avg_response_time_seconds": 8.0,
        "side_effect_reports_14d": 4, "missed_visits_30d": 4,
    }
    score, level = risk_model.predict(features)
    assert score >= 60
    assert level in ("HIGH", "CRITICAL")


def test_score_is_bounded():
    for adh in [0.0, 0.5, 1.0]:
        features = {
            "adherence_7d": adh, "adherence_14d": adh, "adherence_30d": adh,
            "avg_response_time_seconds": 60.0,
            "side_effect_reports_14d": 0, "missed_visits_30d": 0,
        }
        score, _ = risk_model.predict(features)
        assert 0.0 <= score <= 100.0
