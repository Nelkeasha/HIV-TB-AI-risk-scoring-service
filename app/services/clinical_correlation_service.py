"""
Correlates self-reported adherence with CHW-verified pill counts.

Pattern A — High reported adherence (>= 80%) BUT false_confirmation_flag = True
            Suggests patient is confirming doses they did not take.

Pattern B — Low confirmed adherence (< 60%) BUT CHW pill count is consistent
            Suggests the patient is taking medication but not confirming digitally.
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.patient import Patient
from app.models.medication_record import MedicationRecord
from app.utils import alert_utils
import logging

logger = logging.getLogger(__name__)


def correlate(patient_id, db: Session) -> dict:
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise ValueError(f"Patient {patient_id} not found")

    record = (
        db.query(MedicationRecord)
        .filter(MedicationRecord.patient_id == patient_id)
        .order_by(MedicationRecord.period_end.desc())
        .first()
    )

    if not record:
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

    adherence_pct   = float(record.adherence_pct)
    false_flag      = bool(record.false_confirmation_flag)
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
    elif adherence_pct < 60 and record.doses_verified >= record.doses_confirmed:
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
