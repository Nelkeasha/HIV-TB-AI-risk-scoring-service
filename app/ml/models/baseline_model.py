"""
Per-patient confirmation behaviour baseline.
Calculates mean and std dev of response_time_seconds for a patient.
Used by false_confirmation_service to detect timestamp anomalies.
"""

import numpy as np
from sqlalchemy.orm import Session
from app.models.confirmation_log import ConfirmationLog
from datetime import date, timedelta


def build(patient_id, db: Session) -> dict:
    cutoff = date.today() - timedelta(days=60)
    times = [
        row.response_time_seconds
        for row in db.query(ConfirmationLog).filter(
            ConfirmationLog.patient_id == patient_id,
            ConfirmationLog.confirmed_at.isnot(None),
            ConfirmationLog.response_time_seconds.isnot(None),
            ConfirmationLog.scheduled_date >= cutoff,
        ).all()
    ]

    if len(times) < 3:
        return {"mean": 90.0, "std": 60.0, "n": len(times), "reliable": False}

    mean = float(np.mean(times))
    std  = float(np.std(times))
    return {"mean": mean, "std": std, "n": len(times), "reliable": True}


def is_anomalous(response_time_seconds: int, baseline: dict) -> bool:
    """True if response time is suspiciously fast vs the patient's own history."""
    if not baseline["reliable"]:
        return response_time_seconds < 15

    lower_bound = baseline["mean"] - 2 * baseline["std"]
    return response_time_seconds < max(lower_bound, 10)
