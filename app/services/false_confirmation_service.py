"""
Detects suspicious dose confirmation patterns.

Signal 1 — Timestamp anomaly  : response time is below the patient's personal baseline
Signal 2 — Window violation    : confirmed_at is outside the allowed dose window
Signal 3 — Pill count mismatch : CHW visit closest to confirmation shows discrepancy

If suspicion_score >= 2, the ai_suspicion_flag is set and an alert is created.
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.confirmation_log import ConfirmationLog
from app.models.home_visit import HomeVisit
from app.ml.models.baseline_model import build as build_baseline, is_anomalous
from app.utils import alert_utils
import logging

logger = logging.getLogger(__name__)

THRESHOLD = 2


def analyze(patient_id, schedule_id, response_time_seconds: int,
            confirmed_at: datetime, window_open: datetime,
            window_close: datetime, db: Session) -> dict:

    signals: list[str] = []

    # Signal 1 — Timestamp anomaly
    baseline = build_baseline(patient_id, db)
    if is_anomalous(response_time_seconds, baseline):
        signals.append(
            f"Response time {response_time_seconds}s is unusually fast "
            f"(patient baseline mean={baseline['mean']:.0f}s)"
        )

    # Signal 2 — Window violation
    if not (window_open <= confirmed_at <= window_close):
        signals.append(
            f"Confirmation at {confirmed_at.strftime('%H:%M')} is outside "
            f"the allowed window ({window_open.strftime('%H:%M')}–{window_close.strftime('%H:%M')})"
        )

    # Signal 3 — Pill count mismatch from most recent CHW visit
    last_visit = (
        db.query(HomeVisit)
        .filter(
            HomeVisit.patient_id == patient_id,
            HomeVisit.visit_date <= confirmed_at + timedelta(days=7),
        )
        .order_by(HomeVisit.visit_date.desc())
        .first()
    )
    if last_visit and last_visit.pill_count_discrepancy:
        signals.append(
            "Most recent CHW visit recorded a pill count discrepancy, "
            "inconsistent with reported adherence."
        )

    suspicion_score = len(signals)
    is_suspicious   = suspicion_score >= THRESHOLD

    # Write flag back to confirmation_log
    log = (
        db.query(ConfirmationLog)
        .filter(
            ConfirmationLog.patient_id == patient_id,
            ConfirmationLog.schedule_id == schedule_id,
        )
        .order_by(ConfirmationLog.created_at.desc())
        .first()
    )
    alert_created = False
    if log:
        log.ai_suspicion_flag = is_suspicious
        log.suspicion_reason  = "; ".join(signals) if signals else None
        db.commit()

        if is_suspicious:
            alert_utils.create_alert(
                db,
                alert_type = "FALSE_CONFIRMATION",
                severity   = "WARNING",
                title      = "Suspicious Dose Confirmation Detected",
                message    = f"{suspicion_score} signals triggered: {'; '.join(signals)}",
                patient_id = patient_id,
                chw_id     = last_visit.chw_id if last_visit else None,
            )
            alert_created = True

    recommended = (
        "Verify with CHW home visit." if is_suspicious
        else "Confirmation appears genuine."
    )

    return {
        "patient_id":           str(patient_id),
        "schedule_id":          str(schedule_id),
        "is_suspicious":        is_suspicious,
        "suspicion_score":      suspicion_score,
        "signals_triggered":    signals,
        "recommended_action":   recommended,
        "ai_suspicion_flag_set": alert_created,
    }
