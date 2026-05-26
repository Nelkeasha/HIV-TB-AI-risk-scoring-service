from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.patient import Patient
from app.models.ai_risk_score import AiRiskScore
import logging

logger = logging.getLogger(__name__)

PRIORITY_GROUPS = {
    "CRITICAL": "VISIT_TODAY",
    "HIGH":     "VISIT_TODAY",
    "MODERATE": "CALL_TODAY",
    "LOW":      "STABLE",
}


def _latest_scores_for_chw(chw_id, db: Session) -> list:
    subq = (
        db.query(
            AiRiskScore.patient_id,
            func.max(AiRiskScore.calculated_at).label("latest"),
        )
        .join(Patient, AiRiskScore.patient_id == Patient.id)
        .filter(Patient.chw_id == chw_id, Patient.is_active == True)
        .group_by(AiRiskScore.patient_id)
        .subquery()
    )
    return (
        db.query(AiRiskScore)
        .join(subq, (AiRiskScore.patient_id == subq.c.patient_id) &
                    (AiRiskScore.calculated_at == subq.c.latest))
        .all()
    )


def generate(chw_id, db: Session) -> dict:
    scores = _latest_scores_for_chw(chw_id, db)
    scores_sorted = sorted(scores, key=lambda s: float(s.risk_score), reverse=True)

    visit_today, call_today, stable = [], [], []

    for s in scores_sorted:
        patient = db.query(Patient).filter(Patient.id == s.patient_id).first()
        if not patient:
            continue
        group = PRIORITY_GROUPS.get(s.risk_level, "STABLE")
        entry = {
            "patient_id":        str(patient.id),
            "patient_name":      patient.full_name,
            "patient_code":      patient.patient_code,
            "risk_score":        float(s.risk_score),
            "risk_level":        s.risk_level,
            "priority_group":    group,
            "recommended_action": s.recommended_action or "Routine follow-up.",
        }
        if group == "VISIT_TODAY":
            visit_today.append(entry)
        elif group == "CALL_TODAY":
            call_today.append(entry)
        else:
            stable.append(entry)

    return {
        "chw_id":        str(chw_id),
        "generated_at":  datetime.now(),
        "visit_today":   visit_today,
        "call_today":    call_today,
        "stable":        stable,
        "total_patients": len(scores_sorted),
    }
