from sqlalchemy import text
from app.core.database import engine

CODES = ["PT-BD5C2489", "PT-EEF83CCE", "PT-F952B170"]

with engine.begin() as conn:
    rows = conn.execute(
        text("SELECT id, patient_code, full_name, fhir_patient_id, sync_status FROM patients WHERE patient_code = ANY(:codes)"),
        {"codes": CODES},
    ).fetchall()
    for r in rows:
        print("patient", r.patient_code, r.full_name, "fhir_patient_id=", r.fhir_patient_id, "sync_status=", r.sync_status)

    ids = [r.id for r in rows]

    conn.execute(text("UPDATE patients SET sync_status='PENDING', fhir_patient_id=NULL WHERE id = ANY(:ids)"), {"ids": ids})
    r1 = conn.execute(text("UPDATE home_visits SET sync_status='PENDING', fhir_observation_id=NULL WHERE patient_id = ANY(:ids)"), {"ids":   
ids})
    r2 = conn.execute(text("UPDATE treatment_plans SET sync_status='PENDING', fhir_care_plan_id=NULL WHERE patient_id = ANY(:ids)"), {"ids": 
ids})
    r3 = conn.execute(text("UPDATE medication_records SET sync_status='PENDING' WHERE patient_id = ANY(:ids)"), {"ids": ids})

    print("home_visits reset:", r1.rowcount)
    print("treatment_plans reset:", r2.rowcount)
    print("medication_records reset:", r3.rowcount)

print("done")