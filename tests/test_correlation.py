"""Unit tests for clinical correlation pattern logic."""


def _detect_pattern(adherence_pct: float, false_flag: bool,
                    doses_verified: int, doses_confirmed: int) -> str:
    if adherence_pct >= 80 and false_flag:
        return "A"
    if adherence_pct < 60 and doses_verified >= doses_confirmed:
        return "B"
    return "NONE"


def test_pattern_a_high_adherence_with_suspicion():
    assert _detect_pattern(85.0, True, 20, 22) == "A"


def test_pattern_b_low_digital_but_verified():
    assert _detect_pattern(45.0, False, 25, 10) == "B"


def test_no_pattern_normal_case():
    assert _detect_pattern(75.0, False, 20, 20) == "NONE"


def test_no_pattern_boundary():
    assert _detect_pattern(80.0, False, 20, 20) == "NONE"
