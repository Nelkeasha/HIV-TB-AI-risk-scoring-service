"""
Extracts the 6 input features used by the risk model from database records.

Feature definitions:
  1. adherence_7d   — confirmed / scheduled in the last 7 days
  2. adherence_14d  — confirmed / scheduled in the last 14 days
  3. adherence_30d  — confirmed / scheduled in the last 30 days
  4. avg_response_time_seconds — mean response time of confirmed doses (last 30 days)
  5. side_effect_reports_14d   — home visits with side effects in last 14 days
  6. missed_visits_30d         — CHW visits missed in last 30 days
"""

from datetime import date, timedelta
from sqlalchemy.orm import Session
from app.models.confirmation_log import ConfirmationLog
from app.models.home_visit import HomeVisit
import numpy as np


def extract(patient_id, db: Session) -> dict:
    today      = date.today()
    cutoff_7d  = today - timedelta(days=7)
    cutoff_14d = today - timedelta(days=14)
    cutoff_30d = today - timedelta(days=30)

    logs_30d = (
        db.query(ConfirmationLog)
        .filter(
            ConfirmationLog.patient_id == patient_id,
            ConfirmationLog.scheduled_date >= cutoff_30d,
        )
        .all()
    )

    def adherence_in(cutoff):
        window = [l for l in logs_30d if l.scheduled_date >= cutoff]
        if not window:
            return 1.0
        confirmed = sum(1 for l in window if l.confirmed_at is not None)
        return confirmed / len(window)

    response_times = [
        l.response_time_seconds for l in logs_30d
        if l.response_time_seconds is not None and l.confirmed_at is not None
    ]
    avg_response = float(np.mean(response_times)) if response_times else 120.0

    visits_14d = (
        db.query(HomeVisit)
        .filter(
            HomeVisit.patient_id == patient_id,
            HomeVisit.visit_date >= cutoff_14d,
        )
        .all()
    )
    side_effect_reports_14d = sum(
        1 for v in visits_14d if v.side_effects_reported
    )

    visits_30d = (
        db.query(HomeVisit)
        .filter(
            HomeVisit.patient_id == patient_id,
            HomeVisit.visit_date >= cutoff_30d,
        )
        .count()
    )
    expected_visits_30d = 4
    missed_visits_30d = max(0, expected_visits_30d - visits_30d)

    return {
        "adherence_7d":             round(adherence_in(cutoff_7d),  4),
        "adherence_14d":            round(adherence_in(cutoff_14d), 4),
        "adherence_30d":            round(adherence_in(cutoff_30d), 4),
        "avg_response_time_seconds": round(avg_response, 1),
        "side_effect_reports_14d":  side_effect_reports_14d,
        "missed_visits_30d":        missed_visits_30d,
    }


def missed_counts(patient_id, db: Session) -> dict:
    today      = date.today()
    cutoff_7d  = today - timedelta(days=7)
    cutoff_14d = today - timedelta(days=14)
    cutoff_30d = today - timedelta(days=30)

    def count_missed(cutoff):
        return (
            db.query(ConfirmationLog)
            .filter(
                ConfirmationLog.patient_id == patient_id,
                ConfirmationLog.is_missed == True,
                ConfirmationLog.scheduled_date >= cutoff,
            )
            .count()
        )

    return {
        "missed_7d":  count_missed(cutoff_7d),
        "missed_14d": count_missed(cutoff_14d),
        "missed_30d": count_missed(cutoff_30d),
    }
