"""Unit tests for cluster detection thresholds."""

from app.core.config import settings


def test_cluster_min_patients_setting():
    assert settings.cluster_min_patients >= 2


def test_cluster_decline_percentage_setting():
    assert settings.cluster_decline_percentage > 0


def test_pct_change_formula():
    avg_prior  = 50.0
    avg_recent = 65.0
    pct_change = ((avg_recent - avg_prior) / avg_prior) * 100
    assert pct_change == 30.0
    assert pct_change >= settings.cluster_decline_percentage
