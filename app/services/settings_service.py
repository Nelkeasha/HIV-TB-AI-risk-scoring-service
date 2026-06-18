"""Reads the single global system_settings row written by Spring Boot's
admin settings endpoint (shared-DB read, same pattern used everywhere else
in this service)."""

from sqlalchemy.orm import Session
from app.models.system_settings import SystemSettings

_DEFAULTS = {"high_risk_threshold": 70, "critical_risk_threshold": 85}


def get_thresholds(db: Session) -> dict:
    row = db.query(SystemSettings).first()
    if row is None:
        return dict(_DEFAULTS)
    return {
        "high_risk_threshold": row.high_risk_threshold,
        "critical_risk_threshold": row.critical_risk_threshold,
    }
