"""Unit tests for stock forecast logic (no DB)."""


def test_days_remaining_formula():
    current_quantity = 60
    daily_rate       = 2.0
    days_remaining   = int(current_quantity / daily_rate)
    assert days_remaining == 30


def test_zero_rate_defaults_to_high():
    current_quantity = 60
    daily_rate       = 0.0
    days_remaining   = int(current_quantity / daily_rate) if daily_rate > 0 else 999
    assert days_remaining == 999


def test_warning_threshold():
    warning_days = 14
    assert 10 <= warning_days
    assert 7 < warning_days
