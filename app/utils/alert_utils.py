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


def upsert_patient_alert(
    db: Session,
    alert_type: str,
    severity: str,
    title: str,
    message: str,
    patient_id,
    chw_id=None,
) -> Alert:
    """Update-in-place "living alert": one unresolved alert per (patient, type).

    Re-scoring refreshes the existing row (severity/title/message, flagged
    unread again) instead of stacking a new alert per run. Any older unresolved
    duplicates left over from before this dedup existed are auto-resolved.
    """
    open_alerts = (
        db.query(Alert)
        .filter(
            Alert.patient_id == patient_id,
            Alert.alert_type == alert_type,
            Alert.is_resolved == False,  # noqa: E712
        )
        .order_by(Alert.created_at.desc())
        .all()
    )
    if not open_alerts:
        return create_alert(db, alert_type, severity, title, message,
                            patient_id=patient_id, chw_id=chw_id)

    current = open_alerts[0]
    current.severity = severity
    current.title = title
    current.message = message
    current.is_read = False
    if chw_id is not None:
        current.chw_id = chw_id
    for stale in open_alerts[1:]:
        stale.is_resolved = True
        stale.resolved_at = datetime.now()
    db.commit()
    db.refresh(current)
    return current


def resolve_patient_alerts(db: Session, alert_type: str, patient_id) -> int:
    """Auto-resolve unresolved alerts of this type once the condition clears."""
    open_alerts = (
        db.query(Alert)
        .filter(
            Alert.patient_id == patient_id,
            Alert.alert_type == alert_type,
            Alert.is_resolved == False,  # noqa: E712
        )
        .all()
    )
    for a in open_alerts:
        a.is_resolved = True
        a.resolved_at = datetime.now()
    if open_alerts:
        db.commit()
    return len(open_alerts)
