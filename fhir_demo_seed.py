"""
Seed a throwaway Postgres with the minimal schema + demo rows for an OFFLINE
FHIR-sync demonstration (no dependency on the production database).

Use this when the live database is unreachable from the demo machine (e.g. the
venue's IP is not on the Render database allowlist). Together with a local
HAPI FHIR container it demonstrates the complete pipeline:

    read PENDING → build FHIR R4 resources → conditional create on HAPI →
    write FHIR ids + SYNCED statuses back.

Defense-day recipe (three containers, one network namespace via host):

    1. docker run -d --name hapi-fhir    -p 8090:8080 hapiproject/hapi:latest
    2. docker run -d --name fhir-demo-db -p 5433:5432 \
         -e POSTGRES_PASSWORD=demo -e POSTGRES_DB=hivtb_demo postgres:16
    3. (from python-ai-service/)
       docker run --rm -v "%CD%:/app" -w /app \
         --add-host=host.docker.internal:host-gateway \
         -e DATABASE_URL=postgresql://postgres:demo@host.docker.internal:5433/hivtb_demo \
         -e FHIR_SERVER_URL=http://host.docker.internal:8090/fhir \
         -e SPRING_BOOT_BASE_URL=http://127.0.0.1:9 \
         python:3.11-slim bash -c \
         "pip install -q -r requirements.txt && python fhir_demo_seed.py && python fhir_sync.py"
    4. Show the synced resource in a browser:
       http://localhost:8090/fhir/Patient?identifier=urn:hivtb:patient-code|PT-DEMO-A

SPRING_BOOT_BASE_URL points at a dead port on purpose: the completion callback
fails, which exercises the script's write-statuses-directly-to-DB fallback so
the whole demo works without the production backend.
"""
import uuid
from datetime import datetime, date

from sqlalchemy import text

from app.core.database import engine, SessionLocal, Base

# Register every mapped table on Base before create_all.
import app.models.patient            # noqa: F401
import app.models.home_visit         # noqa: F401
import app.models.medication_record  # noqa: F401
import app.models.confirmation_log   # noqa: F401
import app.models.ai_risk_score      # noqa: F401
import app.models.alert              # noqa: F401
import app.models.lab_result         # noqa: F401
import app.models.system_settings    # noqa: F401
import fhir_sync                     # noqa: F401  (MedicationFormulary, TreatmentPlan, FhirSyncLog)

from app.models.patient import Patient
from app.models.home_visit import HomeVisit
from app.models.medication_record import MedicationRecord
from fhir_sync import MedicationFormulary, TreatmentPlan

# FK-target stub tables (facilities, chws, system_users, dose_schedules) are
# registered on Base.metadata by the fhir_sync import above, so create_all can
# resolve every constraint and create them alongside the mapped tables.

FACILITY_ID = uuid.uuid4()
CHW_ID      = uuid.uuid4()


def main() -> None:
    Base.metadata.create_all(engine)

    db = SessionLocal()
    try:
        if db.query(Patient).filter(Patient.patient_code == "PT-DEMO-A").first():
            print("Demo patient already seeded — nothing to do.")
            return

        db.execute(text("INSERT INTO facilities (id) VALUES (:i)"), {"i": str(FACILITY_ID)})
        db.execute(text("INSERT INTO chws (id) VALUES (:i)"), {"i": str(CHW_ID)})

        patient = Patient(
            id=uuid.uuid4(),
            patient_code="PT-DEMO-A",
            full_name="FHIR Demo Uwase",
            date_of_birth=date(1992, 3, 14),
            sex="FEMALE",
            national_id="1199270099999999",
            phone_number="0788000111",
            diagnosis_type="TB",
            tb_treatment_start_date=date(2026, 7, 10),
            village="Gatsibo", sector="Niboye", district="Gasabo",
            chw_id=CHW_ID, facility_id=FACILITY_ID,
            sync_status="PENDING", is_active=True,
            registration_status="CONFIRMED",
            created_at=datetime.utcnow(), updated_at=datetime.utcnow(),
        )
        db.add(patient); db.flush()

        db.add(HomeVisit(
            id=uuid.uuid4(), patient_id=patient.id, chw_id=CHW_ID,
            visit_date=datetime.utcnow(), adherence_status="GOOD",
            sync_status="PENDING",
        ))
        db.add(MedicationRecord(  # id is a bigint autoincrement — let the DB assign it
            patient_id=patient.id,
            period_start=date.today(), period_end=date.today(),
            doses_scheduled=1, doses_confirmed=1, doses_verified=1,
            adherence_pct=100.0, sync_status="PENDING",
        ))

        med = MedicationFormulary(id=uuid.uuid4(), name="Isoniazid (INH)")
        db.add(med); db.flush()
        db.add(TreatmentPlan(
            id=uuid.uuid4(), patient_id=patient.id, medication_id=med.id,
            dosage="1 tablet", frequency="Once daily",
            start_date=date.today(), is_active=True, sync_status="PENDING",
        ))

        db.commit()
        print("Seeded demo data: 1 patient (PT-DEMO-A), 1 home visit, "
              "1 medication record, 1 treatment plan — all sync_status=PENDING.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
