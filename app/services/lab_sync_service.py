"""
Polls the FHIR server for new lab Observations (HIV viral load, CD4 count)
for every patient already synced to FHIR, and stores them in lab_results.

This is a pull/poll design, not a push/webhook one — HAPI FHIR subscriptions
would require the FHIR server to call back into this service, which most
FHIR test servers don't support cleanly. So "a lab result arrives via FHIR"
in practice means "the next scheduled poll picks it up" (see nightly_jobs).
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.patient import Patient
from app.models.lab_result import LabResult

logger = logging.getLogger(__name__)

TRACKED_LOINC_CODES = [
    settings.loinc_viral_load,
    settings.loinc_cd4_count,
]


def _parse_observed_at(resource: dict) -> Optional[datetime]:
    raw = resource.get("effectiveDateTime") or resource.get("issued")
    if not raw:
        return None
    try:
        # FHIR datetimes are ISO 8601, sometimes with a trailing "Z"
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _parse_value(resource: dict) -> Optional[tuple]:
    quantity = resource.get("valueQuantity")
    if not quantity or "value" not in quantity:
        return None
    return quantity["value"], quantity.get("unit")


def fetch_observations(client: httpx.Client, fhir_patient_id: str, loinc_code: str,
                        since: Optional[datetime] = None) -> list[dict]:
    """Returns raw FHIR Observation resources for one patient/LOINC code, newest first."""
    params = {
        "subject": f"Patient/{fhir_patient_id}",
        "code": loinc_code,
        "_sort": "-date",
    }
    if since is not None:
        params["date"] = f"ge{since.date().isoformat()}"

    resp = client.get(f"{settings.fhir_server_url}/Observation", params=params, timeout=20)
    resp.raise_for_status()
    bundle = resp.json()
    return [entry["resource"] for entry in bundle.get("entry", []) if "resource" in entry]


def sync_patient_labs(patient: Patient, db: Session, client: httpx.Client) -> int:
    """Fetches new Observations for one patient and stores any not already
    recorded. Returns the number of new rows inserted."""
    if not patient.fhir_patient_id:
        return 0  # patient hasn't been synced to FHIR yet — nothing to look up

    inserted = 0
    for loinc_code in TRACKED_LOINC_CODES:
        latest = (
            db.query(LabResult)
            .filter(LabResult.patient_id == patient.id, LabResult.loinc_code == loinc_code)
            .order_by(LabResult.observed_at.desc())
            .first()
        )
        since = (
            latest.observed_at
            if latest
            else datetime.now() - timedelta(days=settings.lab_sync_lookback_days)
        )
        existing_dates = {
            row.observed_at
            for row in db.query(LabResult.observed_at)
            .filter(LabResult.patient_id == patient.id, LabResult.loinc_code == loinc_code)
            .all()
        }

        try:
            observations = fetch_observations(client, patient.fhir_patient_id, loinc_code, since)
        except Exception as exc:
            logger.warning("Lab fetch failed for patient=%s code=%s: %s",
                            patient.full_name, loinc_code, exc)
            continue

        for obs in observations:
            observed_at = _parse_observed_at(obs)
            parsed_value = _parse_value(obs)
            if observed_at is None or parsed_value is None or observed_at in existing_dates:
                continue
            value, unit = parsed_value
            db.add(LabResult(
                patient_id=patient.id,
                loinc_code=loinc_code,
                value=value,
                unit=unit,
                observed_at=observed_at,
                fhir_observation_id=obs.get("id"),
                created_at=datetime.now(),
            ))
            existing_dates.add(observed_at)
            inserted += 1

    if inserted:
        db.commit()
    return inserted


def sync_all(db: Session) -> int:
    """Runs sync_patient_labs for every active, FHIR-synced patient."""
    patients = (
        db.query(Patient)
        .filter(Patient.is_active == True, Patient.fhir_patient_id.isnot(None))  # noqa: E712
        .all()
    )
    total_inserted = 0
    with httpx.Client() as client:
        for patient in patients:
            try:
                total_inserted += sync_patient_labs(patient, db, client)
            except Exception as exc:
                logger.warning("Lab sync failed for patient=%s: %s", patient.full_name, exc)
    return total_inserted
