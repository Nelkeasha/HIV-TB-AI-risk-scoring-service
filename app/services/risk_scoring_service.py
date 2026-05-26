from datetime import datetime
from sqlalchemy.orm import Session
from app.models.patient import Patient
from app.models.ai_risk_score import AiRiskScore
from app.models.home_visit import HomeVisit
from app.ml.features import risk_features
from app.ml.models import risk_model
from app.utils import alert_utils
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


def _recommended_action(risk_level: str, features: dict) -> str:
    if risk_level == "CRITICAL":
        return "Immediate home visit required. Notify facility provider and supervisor."
    if risk_level == "HIGH":
        return "Schedule home visit within 24 hours. Review treatment plan."
    if risk_level == "MODERATE":
        if features["adherence_7d"] < 0.7:
            return "Phone patient today. Reinforce dosing schedule."
        return "Monitor closely. Call patient if no confirmation by tomorrow."
    return "Patient is stable. Routine follow-up applies."


def _pill_discrepancy_detected(patient_id, db: Session) -> bool:
    last_visit = (
        db.query(HomeVisit)
        .filter(HomeVisit.patient_id == patient_id)
        .order_by(HomeVisit.visit_date.desc())
        .first()
    )
    return bool(last_visit and last_visit.pill_count_discrepancy)


def calculate(patient_id, db: Session) -> dict:
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if not patient:
        raise ValueError(f"Patient {patient_id} not found")

    features    = risk_features.extract(patient_id, db)
    counts      = risk_features.missed_counts(patient_id, db)
    score, level = risk_model.predict(features)
    pill_disc   = _pill_discrepancy_detected(patient_id, db)

    recommended = _recommended_action(level, features)

    entry = AiRiskScore(
        patient_id                      = patient_id,
        risk_level                      = level,
        risk_score                      = score,
        suspicion_score                 = 0,
        missed_doses_7d                 = counts["missed_7d"],
        missed_doses_14d                = counts["missed_14d"],
        missed_doses_30d                = counts["missed_30d"],
        avg_response_time_seconds       = int(features["avg_response_time_seconds"]),
        side_effect_reports_14d         = features["side_effect_reports_14d"],
        missed_visits_30d               = features["missed_visits_30d"],
        timestamp_anomaly_detected      = False,
        pill_count_discrepancy_detected = pill_disc,
        window_violation_detected       = False,
        recommended_action              = recommended,
        calculated_at                   = datetime.now(),
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)

    if level in ("HIGH", "CRITICAL"):
        alert_utils.create_alert(
            db,
            alert_type  = "HIGH_RISK" if level == "HIGH" else "EARLY_WARNING",
            severity    = "WARNING" if level == "HIGH" else "CRITICAL",
            title       = f"{level} Risk — {patient.full_name}",
            message     = f"Risk score {score:.1f}/100. {recommended}",
            patient_id  = patient_id,
            chw_id      = patient.chw_id,
        )

    logger.info("Scored %s: %.1f (%s)", patient.full_name, score, level)
    return {
        "patient_id":                    str(patient_id),
        "patient_name":                  patient.full_name,
        "risk_score":                    score,
        "risk_level":                    level,
        "features":                      features,
        "missed_doses_7d":               counts["missed_7d"],
        "missed_doses_14d":              counts["missed_14d"],
        "missed_doses_30d":              counts["missed_30d"],
        "suspicion_score":               0,
        "timestamp_anomaly_detected":    False,
        "pill_count_discrepancy_detected": pill_disc,
        "window_violation_detected":     False,
        "recommended_action":            recommended,
        "calculated_at":                 entry.calculated_at,
    }
