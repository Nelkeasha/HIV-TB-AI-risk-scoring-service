"""
Correlates self-reported adherence with CHW-verified pill counts and FHIR lab results.

Pattern A — High reported adherence (>= 80%) BUT false_confirmation_flag = True
            Suggests patient is confirming doses they did not take.

Pattern B — Low confirmed adherence (< 60%) BUT CHW pill count is consistent
            Suggests the patient is taking medication but not confirming digitally.

Pattern C — High reported adherence (>= 80%) BUT lab trend is worsening
            (rising HIV viral load, or falling CD4 count). Suggests possible
            treatment failure or drug resistance despite reported adherence —
            pill-count verification alone wouldn't catch this (REQ-13).
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.config import settings
from app.models.patient import Patient
from app.models.medication_record import MedicationRecord
from app.models.lab_result import LabResult
from app.utils import alert_utils
import logging

logger = logging.getLogger(__name__)

# For viral load, a rising value is worsening. For CD4 count, a falling
# value is worsening. Each entry: (loinc_code, label, "rising" | "falling").
_LAB_WORSENING_DIRECTION = [
    (settings.loinc_viral_load, "HIV viral load", "rising"),
    (settings.loinc_cd4_count, "CD4 count", "falling"),
]


def _worsening_lab_trend(patient_id, db: Session) -> str | None:
    """Returns a human-readable description of the first worsening lab trend
    found (comparing the two most recent readings per tracked code), or None
    if there isn't enough data or nothing is worsening."""
    for loinc_code, label, direction in _LAB_WORSENING_DIRECTION:
        readings = (
            db.query(LabResult)
            .filter(LabResult.patient_id == patient_id, LabResult.loinc_code == loinc_code)
            .order_by(LabResult.observed_at.desc())
            .limit(2)
            .all()
        )
        if len(readings) < 2:
            continue
        latest, previous = readings[0], readings[1]
        if direction == "rising" and latest.value > previous.value:
            return f"{label} rose from {previous.value} to {latest.value}"
        if direction == "falling" and latest.value < previous.value:
            return f"{label} fell from {previous.value} to {latest.value}"
    return None


def correlate(patient_id, db: Session) -> dict:
    """MedicationRecord rows are daily-granularity (one per patient per plan per
    day). Evaluating against a single day is noisy — one missed dose reads as
    0% adherence and would fire Pattern B every night. Aggregate the last 7
    daily rows into a rolling week instead, matching the 80%/60% thresholds
    these patterns were designed around."""
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise ValueError(f"Patient {patient_id} not found")

    records = (
        db.query(MedicationRecord)
        .filter(MedicationRecord.patient_id == patient_id)
        .order_by(MedicationRecord.period_end.desc())
        .limit(7)
        .all()
    )

    if not records:
        return {
            "patient_id":             str(patient_id),
            "patient_name":           patient.full_name,
            "pattern":                "NONE",
            "pattern_description":    "No medication records found.",
            "adherence_pct":          0.0,
            "false_confirmation_flag": False,
            "alert_created":          False,
            "recommended_action":     "Ensure CHW completes medication records.",
        }

    total_scheduled = sum(r.doses_scheduled for r in records)
    total_confirmed = sum(r.doses_confirmed for r in records)
    total_verified  = sum(r.doses_verified for r in records)
    adherence_pct   = (total_confirmed / total_scheduled * 100) if total_scheduled else 0.0
    false_flag      = any(r.false_confirmation_flag for r in records)
    pattern         = "NONE"
    description     = "Adherence and verification data are consistent."
    alert_created   = False
    recommended     = "No action required."

    # Pattern A: reports high adherence but AI flagged confirmations as suspicious
    if adherence_pct >= 80 and false_flag:
        pattern     = "A"
        description = (
            f"Patient reports {adherence_pct:.0f}% adherence, but confirmation "
            "data shows suspicious patterns. Possible false confirmation."
        )
        recommended = "CHW should conduct unannounced pill count visit."
        alert_utils.create_alert(
            db,
            alert_type = "CLINICAL_DISCREPANCY",
            severity   = "WARNING",
            title      = f"Pattern A — {patient.full_name}",
            message    = description,
            patient_id = patient_id,
            chw_id     = patient.chw_id,
        )
        alert_created = True

    # Pattern B: low digital adherence but verified doses show patient IS taking medication
    elif adherence_pct < 60 and total_verified >= total_confirmed:
        pattern     = "B"
        description = (
            f"Patient's digital adherence is {adherence_pct:.0f}%, but CHW pill "
            "count confirms doses are being taken. Patient may not be confirming digitally."
        )
        recommended = "Educate patient on app confirmation. Consider SMS as backup method."
        alert_utils.create_alert(
            db,
            alert_type = "CLINICAL_DISCREPANCY",
            severity   = "INFO",
            title      = f"Pattern B — {patient.full_name}",
            message    = description,
            patient_id = patient_id,
            chw_id     = patient.chw_id,
        )
        alert_created = True

    # Pattern C: reports high adherence but lab results are trending the wrong way —
    # only checked when neither A nor B already explains a discrepancy this cycle.
    else:
        worsening = _worsening_lab_trend(patient_id, db)
        if adherence_pct >= 80 and worsening:
            pattern     = "C"
            description = (
                f"Patient reports {adherence_pct:.0f}% adherence, but lab results show "
                f"{worsening}. Possible treatment failure or drug resistance despite reported adherence."
            )
            recommended = "Facility provider should review for resistance testing or regimen change."
            alert_utils.create_alert(
                db,
                alert_type = "CLINICAL_DISCREPANCY",
                severity   = "WARNING",
                title      = f"Pattern C — {patient.full_name}",
                message    = description,
                patient_id = patient_id,
                chw_id     = patient.chw_id,
            )
            alert_created = True

    logger.info("Correlation for %s: Pattern %s", patient.full_name, pattern)
    return {
        "patient_id":             str(patient_id),
        "patient_name":           patient.full_name,
        "pattern":                pattern,
        "pattern_description":    description,
        "adherence_pct":          adherence_pct,
        "false_confirmation_flag": false_flag,
        "alert_created":          alert_created,
        "recommended_action":     recommended,
    }
