#!/usr/bin/env python3
"""
FHIR Sync Script
Reads PENDING records from PostgreSQL, pushes them to a HAPI FHIR R4 server,
then reports the assigned FHIR IDs back to Spring Boot so records are marked SYNCED.

Usage:
  python fhir_sync.py               # live run
  python fhir_sync.py --dry-run     # builds FHIR JSON, skips all HTTP calls

Required .env vars (beyond the AI service defaults):
  FHIR_SERVER_URL       — e.g. http://localhost:8090/fhir
  SPRING_ADMIN_EMAIL    — SYSTEM_ADMIN account email
  SPRING_ADMIN_PASSWORD — SYSTEM_ADMIN account password

How it works:
  1. Reads all rows where sync_status = 'PENDING' directly from PostgreSQL
  2. Opens a FhirSyncLog session row in the DB
  3. Builds FHIR R4 resources (Patient → Observation → MedicationStatement → CarePlan)
  4. POSTs each resource to the HAPI FHIR server; records the returned FHIR ID
  5. Calls PUT /api/internal/sync/logs/{logId}/complete on Spring Boot
  6. Spring Boot stores FHIR IDs on each entity and flips sync_status → SYNCED
"""

import argparse
import logging
import sys
import uuid
from datetime import datetime, date
from typing import Optional

import httpx
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey, Date, Boolean
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal, Base
from app.models.patient import Patient
from app.models.home_visit import HomeVisit
from app.models.medication_record import MedicationRecord
from app.models.confirmation_log import ConfirmationLog
from app.models.ai_risk_score import AiRiskScore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("fhir_sync")


# ── Extra ORM models used only by this script ─────────────────────────────────

class TreatmentPlan(Base):
    __tablename__ = "treatment_plans"
    __table_args__ = {"extend_existing": True}

    id               = Column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id       = Column(PgUUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    medication_name  = Column(String(100), nullable=False)
    dosage           = Column(String(50), nullable=False)
    frequency        = Column(String(50), nullable=False)
    start_date       = Column(Date)
    end_date         = Column(Date)
    is_active        = Column(Boolean, default=True)
    fhir_care_plan_id = Column(String(100))
    sync_status      = Column(String(20), default="PENDING")


class FhirSyncLog(Base):
    __tablename__ = "fhir_sync_logs"
    __table_args__ = {"extend_existing": True}

    id                = Column(PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chw_id            = Column(PgUUID(as_uuid=True), nullable=True)
    sync_started_at   = Column(DateTime, nullable=False)
    sync_completed_at = Column(DateTime)
    records_synced    = Column(Integer, default=0)
    records_failed    = Column(Integer, default=0)
    sync_status       = Column(String(20), nullable=False)
    error_log         = Column(Text)
    created_at        = Column(DateTime)


# ── Spring Boot auth ───────────────────────────────────────────────────────────

def get_spring_jwt() -> str:
    if not settings.spring_admin_email or not settings.spring_admin_password:
        raise ValueError(
            "SPRING_ADMIN_EMAIL and SPRING_ADMIN_PASSWORD must be set in .env"
        )
    resp = httpx.post(
        f"{settings.spring_boot_base_url}/api/auth/login",
        json={"email": settings.spring_admin_email, "password": settings.spring_admin_password},
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    token = data.get("accessToken") or data.get("token") or data.get("access_token")
    if not token:
        raise ValueError(f"No token field in auth response: {list(data.keys())}")
    log.info("Spring Boot auth OK (SYSTEM_ADMIN)")
    return token


# ── FHIR resource builders ────────────────────────────────────────────────────

def _fhir_gender(sex: Optional[str]) -> str:
    if not sex:
        return "unknown"
    return {"MALE": "male", "FEMALE": "female", "M": "male", "F": "female"}.get(
        sex.upper(), "unknown"
    )


def _iso(d) -> Optional[str]:
    if d is None:
        return None
    if isinstance(d, (datetime, date)):
        return d.isoformat()
    return str(d)


def build_fhir_patient(p: Patient) -> dict:
    resource: dict = {
        "resourceType": "Patient",
        "identifier": [
            {"system": "urn:hivtb:patient-code", "value": p.patient_code}
        ],
        "name": [{"use": "official", "text": p.full_name}],
        "gender": _fhir_gender(p.sex),
    }
    if p.date_of_birth:
        resource["birthDate"] = _iso(p.date_of_birth)
    if p.national_id:
        resource["identifier"].append(
            {"system": "urn:rwanda:national-id", "value": p.national_id}
        )
    if p.phone_number:
        resource["telecom"] = [
            {"system": "phone", "value": p.phone_number, "use": "mobile"}
        ]
    if p.district or p.sector or p.village:
        resource["address"] = [
            {
                "use": "home",
                "text": ", ".join(
                    x for x in [p.village, p.sector, p.district] if x
                ),
                "country": "RW",
            }
        ]
    return resource


def build_fhir_observation(visit: HomeVisit, patient_fhir_id: str) -> dict:
    notes = []
    if visit.symptoms_reported:
        notes.append({"text": f"Symptoms: {visit.symptoms_reported}"})
    if visit.side_effects_reported:
        notes.append({"text": f"Side effects: {visit.side_effects_reported}"})
    if visit.psychosocial_notes:
        notes.append({"text": f"Psychosocial: {visit.psychosocial_notes}"})
    if visit.pill_count_recorded is not None:
        notes.append({
            "text": (
                f"Pill count: {visit.pill_count_recorded}"
                f"/{visit.pill_count_expected or '?'}"
                + (" (discrepancy)" if visit.pill_count_discrepancy else "")
            )
        })

    resource: dict = {
        "resourceType": "Observation",
        "status": "final",
        "code": {
            "coding": [{
                "system": "http://loinc.org",
                "code": "45755-6",
                "display": "Adherence to medication regimen — home visit",
            }]
        },
        "subject": {"reference": f"Patient/{patient_fhir_id}"},
        "valueString": visit.adherence_status,
    }
    if visit.visit_date:
        resource["effectiveDateTime"] = _iso(visit.visit_date)
    if notes:
        resource["note"] = notes
    return resource


def build_fhir_medication_statement(record: MedicationRecord, patient_fhir_id: str) -> dict:
    return {
        "resourceType": "MedicationStatement",
        "status": "active",
        "subject": {"reference": f"Patient/{patient_fhir_id}"},
        "medicationCodeableConcept": {"text": "HIV/TB Antiretroviral / TB Treatment"},
        "effectivePeriod": {
            "start": _iso(record.period_start),
            "end":   _iso(record.period_end),
        },
        "note": [{
            "text": (
                f"Scheduled: {record.doses_scheduled}, "
                f"confirmed: {record.doses_confirmed}, "
                f"verified: {record.doses_verified}, "
                f"adherence: {record.adherence_pct}%"
                + (" — BELOW THRESHOLD" if record.below_threshold else "")
                + (" — FALSE CONFIRMATION FLAG" if record.false_confirmation_flag else "")
            )
        }],
    }


def build_fhir_care_plan(plan: TreatmentPlan, patient_fhir_id: str) -> dict:
    resource: dict = {
        "resourceType": "CarePlan",
        "status": "active" if plan.is_active else "completed",
        "intent": "plan",
        "subject": {"reference": f"Patient/{patient_fhir_id}"},
        "title": plan.medication_name,
        "description": f"{plan.medication_name} — {plan.dosage} — {plan.frequency}",
    }
    period: dict = {}
    if plan.start_date:
        period["start"] = _iso(plan.start_date)
    if plan.end_date:
        period["end"] = _iso(plan.end_date)
    if period:
        resource["period"] = period
    return resource


# ── FHIR HTTP helper ──────────────────────────────────────────────────────────

def post_to_fhir(
    client: httpx.Client, resource_type: str, body: dict, dry_run: bool
) -> str:
    """POST a FHIR resource, return the assigned FHIR ID."""
    if dry_run:
        fake_id = str(uuid.uuid4())[:8]
        log.info("    [dry-run] %s → fake-id: %s", resource_type, fake_id)
        return fake_id

    url = f"{settings.fhir_server_url}/{resource_type}"
    resp = client.post(
        url,
        json=body,
        headers={"Content-Type": "application/fhir+json", "Accept": "application/fhir+json"},
        timeout=20,
    )
    resp.raise_for_status()
    fhir_id = resp.json().get("id")
    if not fhir_id:
        raise ValueError(f"HAPI FHIR returned no id: {resp.text[:300]}")
    return fhir_id


# ── Main sync ─────────────────────────────────────────────────────────────────

def run_sync(dry_run: bool = False) -> None:
    db: Session = SessionLocal()
    errors: list[str] = []

    try:
        # 1. Load PENDING records
        pending_patients = db.query(Patient).filter(Patient.sync_status == "PENDING").all()
        pending_visits   = db.query(HomeVisit).filter(HomeVisit.sync_status == "PENDING").all()
        pending_records  = db.query(MedicationRecord).filter(MedicationRecord.sync_status == "PENDING").all()
        pending_plans    = db.query(TreatmentPlan).filter(TreatmentPlan.sync_status == "PENDING").all()

        total = len(pending_patients) + len(pending_visits) + len(pending_records) + len(pending_plans)
        log.info(
            "Pending → patients=%d  visits=%d  medication_records=%d  treatment_plans=%d  total=%d",
            len(pending_patients), len(pending_visits), len(pending_records), len(pending_plans), total,
        )

        if total == 0:
            log.info("Nothing to sync. Exiting.")
            return

        # 2. Open a sync session row directly in the DB
        log_id = uuid.uuid4()
        if not dry_run:
            sync_log = FhirSyncLog(
                id=log_id,
                sync_started_at=datetime.utcnow(),
                sync_status="IN_PROGRESS",
                created_at=datetime.utcnow(),
            )
            db.add(sync_log)
            db.commit()
            log.info("Sync session opened: logId=%s", log_id)
        else:
            log.info("[dry-run] logId=%s (not persisted)", log_id)

        # 3. Push resources to HAPI FHIR
        patient_fhir_ids: dict[str, str] = {}
        visit_fhir_ids:   dict[str, str] = {}
        record_fhir_ids:  dict[str, str] = {}
        plan_fhir_ids:    dict[str, str] = {}
        synced = 0

        with httpx.Client() as fhir_client:
            # Patients must come first — other resources reference their FHIR IDs
            for p in pending_patients:
                try:
                    fhir_id = post_to_fhir(fhir_client, "Patient", build_fhir_patient(p), dry_run)
                    patient_fhir_ids[str(p.id)] = fhir_id
                    synced += 1
                    log.info("  Patient %-15s → Patient/%s", p.patient_code, fhir_id)
                except Exception as exc:
                    errors.append(f"Patient {p.patient_code}: {exc}")
                    log.error("  Patient %s FAILED: %s", p.patient_code, exc)

            # Build full patient_id → FHIR ID map (includes already-synced patients)
            already_synced = {
                str(row.id): row.fhir_patient_id
                for row in db.query(Patient).filter(Patient.fhir_patient_id.isnot(None)).all()
            }
            patient_fhir_lookup = {**already_synced, **patient_fhir_ids}

            for v in pending_visits:
                pfhir = patient_fhir_lookup.get(str(v.patient_id))
                if not pfhir:
                    errors.append(f"HomeVisit {v.id}: patient not yet synced to FHIR, skipping")
                    log.warning("  HomeVisit %s skipped (patient FHIR id unknown)", v.id)
                    continue
                try:
                    fhir_id = post_to_fhir(fhir_client, "Observation", build_fhir_observation(v, pfhir), dry_run)
                    visit_fhir_ids[str(v.id)] = fhir_id
                    synced += 1
                    log.info("  HomeVisit  %s → Observation/%s", v.id, fhir_id)
                except Exception as exc:
                    errors.append(f"HomeVisit {v.id}: {exc}")
                    log.error("  HomeVisit %s FAILED: %s", v.id, exc)

            for r in pending_records:
                pfhir = patient_fhir_lookup.get(str(r.patient_id))
                if not pfhir:
                    errors.append(f"MedicationRecord {r.id}: patient not yet synced, skipping")
                    log.warning("  MedicationRecord %s skipped (patient FHIR id unknown)", r.id)
                    continue
                try:
                    fhir_id = post_to_fhir(
                        fhir_client, "MedicationStatement",
                        build_fhir_medication_statement(r, pfhir), dry_run,
                    )
                    record_fhir_ids[str(r.id)] = fhir_id
                    synced += 1
                    log.info("  MedicationRecord %s → MedicationStatement/%s", r.id, fhir_id)
                except Exception as exc:
                    errors.append(f"MedicationRecord {r.id}: {exc}")
                    log.error("  MedicationRecord %s FAILED: %s", r.id, exc)

            for tp in pending_plans:
                pfhir = patient_fhir_lookup.get(str(tp.patient_id))
                if not pfhir:
                    errors.append(f"TreatmentPlan {tp.id}: patient not yet synced, skipping")
                    log.warning("  TreatmentPlan %s skipped (patient FHIR id unknown)", tp.id)
                    continue
                try:
                    fhir_id = post_to_fhir(
                        fhir_client, "CarePlan",
                        build_fhir_care_plan(tp, pfhir), dry_run,
                    )
                    plan_fhir_ids[str(tp.id)] = fhir_id
                    synced += 1
                    log.info("  TreatmentPlan %s → CarePlan/%s", tp.id, fhir_id)
                except Exception as exc:
                    errors.append(f"TreatmentPlan {tp.id}: {exc}")
                    log.error("  TreatmentPlan %s FAILED: %s", tp.id, exc)

        # 4. Determine final status
        failed = len(errors)
        if failed == 0:
            final_status = "COMPLETED"
        elif synced == 0:
            final_status = "FAILED"
        else:
            final_status = "PARTIAL_FAILURE"

        error_log_text = "\n".join(errors) if errors else None

        # 5. Tell Spring Boot to store FHIR IDs and mark records as SYNCED
        if not dry_run:
            _notify_spring_boot(
                log_id=log_id,
                final_status=final_status,
                synced=synced,
                failed=failed,
                error_log=error_log_text,
                patient_fhir_ids=patient_fhir_ids,
                visit_fhir_ids=visit_fhir_ids,
                record_fhir_ids=record_fhir_ids,
                plan_fhir_ids=plan_fhir_ids,
                db=db,
            )
        else:
            log.info(
                "[dry-run] would PUT /api/internal/sync/logs/%s/complete — "
                "status=%s  synced=%d  failed=%d",
                log_id, final_status, synced, failed,
            )

        log.info("Done. synced=%d  failed=%d  status=%s", synced, failed, final_status)
        if errors:
            log.warning("Errors:\n  %s", "\n  ".join(errors))

    finally:
        db.close()


def _notify_spring_boot(
    log_id: uuid.UUID,
    final_status: str,
    synced: int,
    failed: int,
    error_log: Optional[str],
    patient_fhir_ids: dict,
    visit_fhir_ids: dict,
    record_fhir_ids: dict,
    plan_fhir_ids: dict,
    db: Session,
) -> None:
    try:
        token = get_spring_jwt()
        payload = {
            "syncStatus":              final_status,
            "recordsSynced":           synced,
            "recordsFailed":           failed,
            "errorLog":                error_log,
            "patientFhirIds":          patient_fhir_ids,
            "homeVisitFhirIds":        visit_fhir_ids,
            "medicationRecordFhirIds": record_fhir_ids,
            "treatmentPlanFhirIds":    plan_fhir_ids,
        }
        resp = httpx.put(
            f"{settings.spring_boot_base_url}/api/internal/sync/logs/{log_id}/complete",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
            timeout=90,
        )
        resp.raise_for_status()
        log.info(
            "Spring Boot notified: status=%s  synced=%d  failed=%d",
            final_status, synced, failed,
        )
    except Exception as exc:
        log.error("Failed to notify Spring Boot (%s). Updating sync log directly in DB.", exc)
        # Fallback: update the sync log row we created directly
        row = db.query(FhirSyncLog).filter(FhirSyncLog.id == log_id).first()
        if row:
            row.sync_status       = final_status
            row.records_synced    = synced
            row.records_failed    = failed
            row.sync_completed_at = datetime.utcnow()
            row.error_log         = (error_log or "") + f"\n[notify_error] {exc}"
            db.commit()


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Push PENDING records to HAPI FHIR R4 and mark them SYNCED in Spring Boot"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Read DB and build FHIR JSON without making any HTTP calls",
    )
    args = parser.parse_args()
    run_sync(dry_run=args.dry_run)
