"""
Monitors population-level adherence to detect early warning patterns.

Geographic clustering  — >= 3 HIGH/CRITICAL patients in the same village/sector
CHW-level clustering   — a single CHW has >= 3 HIGH/CRITICAL patients
Temporal clustering    — facility-wide adherence dropped >= 20% in 7 days
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from collections import defaultdict
from app.models.patient import Patient
from app.models.ai_risk_score import AiRiskScore
from app.utils import alert_utils
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)

HIGH_RISK_LEVELS = ("HIGH", "CRITICAL")


def _latest_high_risk(db: Session):
    cutoff = datetime.now() - timedelta(hours=48)
    subq = (
        db.query(AiRiskScore.patient_id,
                 func.max(AiRiskScore.calculated_at).label("latest"))
        .filter(AiRiskScore.calculated_at >= cutoff)
        .group_by(AiRiskScore.patient_id)
        .subquery()
    )
    return (
        db.query(AiRiskScore)
        .join(subq, (AiRiskScore.patient_id == subq.c.patient_id) &
                    (AiRiskScore.calculated_at == subq.c.latest))
        .filter(AiRiskScore.risk_level.in_(HIGH_RISK_LEVELS))
        .all()
    )


def detect(db: Session) -> dict:
    high_risk_scores = _latest_high_risk(db)
    clusters: list[dict] = []

    # ── Geographic clustering ─────────────────────────────────────────────────
    village_map = defaultdict(list)
    for s in high_risk_scores:
        patient = db.query(Patient).filter(Patient.id == s.patient_id).first()
        if patient and patient.village:
            village_map[patient.village].append(str(patient.id))

    for village, ids in village_map.items():
        if len(ids) >= settings.cluster_min_patients:
            clusters.append({
                "cluster_type":  "GEOGRAPHIC",
                "description":   f"{len(ids)} high-risk patients in {village} — possible community-level barrier",
                "affected_count": len(ids),
                "severity":      "WARNING",
                "affected_ids":  ids,
            })
            alert_utils.create_alert(
                db,
                alert_type = "EARLY_WARNING",
                severity   = "WARNING",
                title      = f"Geographic Cluster — {village}",
                message    = f"{len(ids)} patients with HIGH/CRITICAL risk detected in {village}.",
            )

    # ── CHW-level clustering ──────────────────────────────────────────────────
    chw_map = defaultdict(list)
    for s in high_risk_scores:
        patient = db.query(Patient).filter(Patient.id == s.patient_id).first()
        if patient:
            chw_map[str(patient.chw_id)].append(str(patient.id))

    for chw_id, ids in chw_map.items():
        if len(ids) >= settings.cluster_min_patients:
            clusters.append({
                "cluster_type":  "CHW_LEVEL",
                "description":   f"CHW {chw_id} has {len(ids)} high-risk patients — review caseload",
                "affected_count": len(ids),
                "severity":      "WARNING",
                "affected_ids":  ids,
            })
            alert_utils.create_alert(
                db,
                alert_type = "EARLY_WARNING",
                severity   = "WARNING",
                title      = "CHW Caseload Alert",
                message    = f"CHW has {len(ids)} patients at HIGH/CRITICAL risk simultaneously.",
                chw_id     = chw_id,
            )

    # ── Temporal clustering ───────────────────────────────────────────────────
    cutoff_7d  = datetime.now() - timedelta(days=7)
    cutoff_14d = datetime.now() - timedelta(days=14)

    def avg_score(cutoff_from, cutoff_to):
        rows = (
            db.query(AiRiskScore.risk_score)
            .filter(AiRiskScore.calculated_at.between(cutoff_from, cutoff_to))
            .all()
        )
        if not rows:
            return None
        return sum(float(r.risk_score) for r in rows) / len(rows)

    avg_recent = avg_score(cutoff_7d, datetime.now())
    avg_prior  = avg_score(cutoff_14d, cutoff_7d)

    if avg_recent and avg_prior and avg_prior > 0:
        pct_change = ((avg_recent - avg_prior) / avg_prior) * 100
        if pct_change >= settings.cluster_decline_percentage:
            clusters.append({
                "cluster_type":  "TEMPORAL",
                "description":   f"Population risk score rose {pct_change:.1f}% over 7 days",
                "affected_count": len(high_risk_scores),
                "severity":      "CRITICAL",
                "affected_ids":  [],
            })
            alert_utils.create_alert(
                db,
                alert_type = "EARLY_WARNING",
                severity   = "CRITICAL",
                title      = "System-Wide Risk Increase",
                message    = f"Average patient risk score increased by {pct_change:.1f}% in the last 7 days.",
            )

    return {
        "generated_at":      datetime.now(),
        "clusters_detected": len(clusters),
        "alerts":            clusters,
    }
