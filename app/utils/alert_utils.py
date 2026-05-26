"""Creates alert rows directly in the database."""

from datetime import datetime
from sqlalchemy.orm import Session
from app.models.alert import Alert


def create_alert(
    db: Session,
    alert_type: str,
    severity: str,
    title: str,
    message: str,
    patient_id=None,
    chw_id=None,
    supervisor_id=None,
) -> Alert:
    alert = Alert(
        patient_id=patient_id,
        chw_id=chw_id,
        supervisor_id=supervisor_id,
        alert_type=alert_type,
        severity=severity,
        title=title,
        message=message,
        is_read=False,
        is_resolved=False,
        created_at=datetime.now(),
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert
