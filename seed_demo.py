#!/usr/bin/env python3
"""
Seed demo data for the HIV/TB monitoring system thesis presentation.

Creates 3 additional patients via the Spring Boot REST API (screen, confirm,
treatment plan, dose schedule), then backfills realistic confirmation_logs
and home_visits history directly in Postgres so the AI risk-scoring service
produces a varied, demo-friendly spread of risk levels:

  - Marie Uwimana       -> ACTIVE, near-perfect adherence  -> LOW
  - Pierre Hakizimana   -> PROVISIONAL (left for clinical confirmation demo)
  - Immaculee Nyiraneza -> ACTIVE, partial adherence       -> MODERATE
  - Jean Damascene      -> existing smoke-test patient, backfilled with a
                           week of mostly-missed doses     -> HIGH/CRITICAL

Usage:
  python seed_demo.py
"""

import os
import uuid
from datetime import date, datetime, time, timedelta

import httpx
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv(".env.seed")

SPRING_URL = os.environ["SPRING_BOOT_BASE_URL"]
AI_URL = os.environ["AI_SERVICE_URL"]
INTERNAL_API_KEY = os.environ["INTERNAL_API_KEY"]
DATABASE_URL = os.environ["SEED_DATABASE_URL"]

CHW_EMAIL = os.environ["CHW_EMAIL"]
CHW_PASSWORD = os.environ["CHW_PASSWORD"]
PROVIDER_EMAIL = os.environ["PROVIDER_EMAIL"]
PROVIDER_PASSWORD = os.environ["PROVIDER_PASSWORD"]

JEAN_DAMASCENE_PATIENT_ID = "9034f0b1-8d54-4d8a-83c3-f723077062b2"
JEAN_DAMASCENE_PLAN_ID = "a2b3f1d6-65ca-4d9a-bbcd-7a3a9e1ce95e"
JEAN_DAMASCENE_SCHEDULE_ID = "e5b65fc3-f221-4d13-be59-d7d53f7204b7"
JEAN_DAMASCENE_CHW_ID = "1dd0bb68-cd37-4945-846c-8309613c438a"
JEAN_DAMASCENE_CONFIRMATION_ID = "ca55e9f0-91d3-4c65-be27-16af53f2b10e"

engine = create_engine(DATABASE_URL)


# ── Spring Boot API helpers ────────────────────────────────────────────────

def login(email: str, password: str) -> str:
    r = httpx.post(f"{SPRING_URL}/api/auth/login",
                    json={"email": email, "password": password}, timeout=90)
    r.raise_for_status()
    data = r.json()
    token = data.get("accessToken") or data.get("token")
    if not token:
        raise RuntimeError(f"No token in login response: {data}")
    return token


def api_post(path: str, token: str, payload: dict) -> dict:
    r = httpx.post(f"{SPRING_URL}{path}", json=payload,
                    headers={"Authorization": f"Bearer {token}"}, timeout=90)
    r.raise_for_status()
    return r.json()


def api_put(path: str, token: str, payload: dict) -> dict:
    r = httpx.put(f"{SPRING_URL}{path}", json=payload,
                   headers={"Authorization": f"Bearer {token}"}, timeout=90)
    r.raise_for_status()
    return r.json()


def trigger_risk_score(patient_id: str) -> dict:
    r = httpx.post(f"{AI_URL}/ai/risk-score/{patient_id}",
                    headers={"X-Internal-API-Key": INTERNAL_API_KEY}, timeout=90)
    r.raise_for_status()
    return r.json()


# ── DB seeding helpers ─────────────────────────────────────────────────────

def seed_confirmation_logs(conn, patient_id, plan_id, schedule_id, dose_time: time,
                            window_minutes: int, entries: list[dict]):
    """entries: [{days_ago, missed, response_seconds}]"""
    for e in entries:
        sched_date = date.today() - timedelta(days=e["days_ago"])
        window_open = datetime.combine(sched_date, dose_time)
        window_close = window_open + timedelta(minutes=window_minutes)
        if e["missed"]:
            confirmed_at = None
            response_seconds = None
            within_window = False
        else:
            response_seconds = e["response_seconds"]
            confirmed_at = window_open + timedelta(seconds=response_seconds)
            within_window = response_seconds <= window_minutes * 60

        conn.execute(text("""
            INSERT INTO confirmation_logs
              (id, patient_id, plan_id, schedule_id, scheduled_date, confirmed_at,
               confirmation_method, response_time_seconds, window_open_time, window_close_time,
               is_within_window, is_missed, ai_suspicion_flag, created_at)
            VALUES
              (:id, :patient_id, :plan_id, :schedule_id, :scheduled_date, :confirmed_at,
               'APP', :response_time_seconds, :window_open_time, :window_close_time,
               :is_within_window, :is_missed, false, :created_at)
        """), {
            "id": str(uuid.uuid4()),
            "patient_id": patient_id,
            "plan_id": plan_id,
            "schedule_id": schedule_id,
            "scheduled_date": sched_date,
            "confirmed_at": confirmed_at,
            "response_time_seconds": response_seconds,
            "window_open_time": window_open,
            "window_close_time": window_close,
            "is_within_window": within_window,
            "is_missed": e["missed"],
            "created_at": datetime.now(),
        })


def seed_home_visit(conn, patient_id, chw_id, days_ago, adherence_status,
                     pill_recorded=None, pill_expected=None, discrepancy=False,
                     side_effects=None, symptoms=None):
    visit_dt = datetime.now() - timedelta(days=days_ago)
    conn.execute(text("""
        INSERT INTO home_visits
          (id, patient_id, chw_id, visit_date, adherence_status,
           pill_count_recorded, pill_count_expected, pill_count_discrepancy,
           symptoms_reported, side_effects_reported, sync_status, created_at)
        VALUES
          (:id, :patient_id, :chw_id, :visit_date, :adherence_status,
           :pill_recorded, :pill_expected, :discrepancy,
           :symptoms, :side_effects, 'PENDING', :created_at)
    """), {
        "id": str(uuid.uuid4()),
        "patient_id": patient_id,
        "chw_id": chw_id,
        "visit_date": visit_dt,
        "adherence_status": adherence_status,
        "pill_recorded": pill_recorded,
        "pill_expected": pill_expected,
        "discrepancy": discrepancy,
        "symptoms": symptoms,
        "side_effects": side_effects,
        "created_at": visit_dt,
    })


def build_entries(days: int, missed_days_ago: set[int], response_base: int, response_jitter: int):
    entries = []
    for d in range(1, days + 1):
        missed = d in missed_days_ago
        entries.append({
            "days_ago": d,
            "missed": missed,
            "response_seconds": None if missed else response_base + (d % 6) * response_jitter,
        })
    return entries


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    print("Logging in as CHW and Facility Provider...")
    chw_token = login(CHW_EMAIL, CHW_PASSWORD)
    provider_token = login(PROVIDER_EMAIL, PROVIDER_PASSWORD)

    # ── Patient 1: Marie Uwimana — ACTIVE, near-perfect adherence -> LOW ────
    print("\n[1/3] Screening Marie Uwimana...")
    marie = api_post("/api/v1/patients/screen", chw_token, {
        "fullName": "Marie Uwimana",
        "dateOfBirth": "1990-05-20",
        "sex": "FEMALE",
        "phoneNumber": "+250788111222",
        "hasSmartphone": True,
        "province": "Kigali", "district": "Gasabo", "sector": "Remera",
        "cell": "Nyabisindu", "village": "Amahoro",
        "householdLocation": "Near Amahoro Stadium, Plot 12",
        "suspectedCondition": "HIV",
        "symptoms": ["Fatigue"],
        "screeningNotes": "Routine community follow-up screening.",
    })
    print(f"  -> {marie['patientCode']}  ({marie['patientId']})")

    marie_confirm = api_put(f"/api/v1/patients/{marie['patientId']}/confirm", provider_token, {
        "nationalPatientId": "1199050012345671",
        "diagnosisType": "HIV",
        "artStartDate": str(date.today() - timedelta(days=180)),
        "labResultNotes": "CD4 count: 520 cells/mm3. HIV rapid test: reactive, confirmed by ELISA. Viral load suppressed.",
    })
    print(f"  -> registrationStatus: {marie_confirm['registrationStatus']}")

    marie_plan = api_post("/api/treatment-plans", provider_token, {
        "patientId": marie["patientId"],
        "medicationName": "Tenofovir/Lamivudine/Dolutegravir (TLD)",
        "dosage": "1 tablet",
        "frequency": "Once daily",
        "startDate": str(date.today() - timedelta(days=180)),
    })
    marie_schedule = api_post(f"/api/treatment-plans/{marie_plan['id']}/schedules", provider_token, {
        "doseTime": "08:00:00",
        "doseLabel": "Morning dose",
        "windowDurationMinutes": 60,
        "prescriptionSource": "Dream Medical Center pharmacy",
    })
    print(f"  -> plan {marie_plan['id']}  schedule {marie_schedule['id']}")

    # ── Patient 2: Pierre Hakizimana — left PROVISIONAL ─────────────────────
    print("\n[2/3] Screening Pierre Hakizimana (left PROVISIONAL)...")
    pierre = api_post("/api/v1/patients/screen", chw_token, {
        "fullName": "Pierre Hakizimana",
        "dateOfBirth": "1985-11-02",
        "sex": "MALE",
        "phoneNumber": "+250788333444",
        "hasSmartphone": False,
        "province": "Kigali", "district": "Gasabo", "sector": "Remera",
        "cell": "Nyabisindu", "village": "Amahoro",
        "householdLocation": "Amahoro Stadium area, Plot 88",
        "suspectedCondition": "TB",
        "symptoms": ["Persistent cough", "Night sweats", "Weight loss"],
        "screeningNotes": "Reports cough lasting over 4 weeks with night sweats. Awaiting clinical confirmation.",
    })
    print(f"  -> {pierre['patientCode']}  ({pierre['patientId']})  status={pierre['status']}")
    print(f"  -> referralId: {pierre['referralId']}")

    # ── Patient 3: Immaculee Nyiraneza — ACTIVE, partial adherence -> MODERATE
    print("\n[3/3] Screening Immaculee Nyiraneza...")
    immaculee = api_post("/api/v1/patients/screen", chw_token, {
        "fullName": "Immaculee Nyiraneza",
        "dateOfBirth": "1978-08-14",
        "sex": "FEMALE",
        "phoneNumber": "+250788555666",
        "hasSmartphone": True,
        "province": "Kigali", "district": "Gasabo", "sector": "Remera",
        "cell": "Nyabisindu", "village": "Amahoro",
        "householdLocation": "Amahoro Stadium area, Plot 45",
        "suspectedCondition": "TB",
        "symptoms": ["Persistent cough", "Fever"],
        "screeningNotes": "Household contact of confirmed TB patient. Sputum test positive.",
    })
    print(f"  -> {immaculee['patientCode']}  ({immaculee['patientId']})")

    immaculee_confirm = api_put(f"/api/v1/patients/{immaculee['patientId']}/confirm", provider_token, {
        "nationalPatientId": "1197808012345672",
        "diagnosisType": "TB",
        "tbTreatmentStartDate": str(date.today() - timedelta(days=60)),
        "labResultNotes": "GeneXpert: MTB detected, rifampicin sensitive. Sputum smear positive.",
    })
    print(f"  -> registrationStatus: {immaculee_confirm['registrationStatus']}")

    immaculee_plan = api_post("/api/treatment-plans", provider_token, {
        "patientId": immaculee["patientId"],
        "medicationName": "Rifafour (RHZE)",
        "dosage": "3 tablets",
        "frequency": "Once daily",
        "startDate": str(date.today() - timedelta(days=60)),
    })
    immaculee_schedule = api_post(f"/api/treatment-plans/{immaculee_plan['id']}/schedules", provider_token, {
        "doseTime": "07:30:00",
        "doseLabel": "Morning dose",
        "windowDurationMinutes": 60,
        "prescriptionSource": "Dream Medical Center pharmacy",
    })
    print(f"  -> plan {immaculee_plan['id']}  schedule {immaculee_schedule['id']}")

    # ── Backfill historical confirmation_logs + home_visits directly in DB ──
    print("\nBackfilling 30-day confirmation history...")
    with engine.begin() as conn:
        # Marie — 28/30 confirmed within window, fast normal response -> LOW
        marie_entries = build_entries(30, missed_days_ago={7, 19}, response_base=90, response_jitter=8)
        seed_confirmation_logs(conn, marie["patientId"], marie_plan["id"], marie_schedule["id"],
                                time(8, 0), 60, marie_entries)
        seed_home_visit(conn, marie["patientId"], JEAN_DAMASCENE_CHW_ID, days_ago=10,
                         adherence_status="GOOD", pill_recorded=28, pill_expected=28, discrepancy=False)
        seed_home_visit(conn, marie["patientId"], JEAN_DAMASCENE_CHW_ID, days_ago=24,
                         adherence_status="GOOD", pill_recorded=14, pill_expected=14, discrepancy=False)
        print("  Marie: 30 confirmation_logs (2 missed), 2 home visits")

        # Immaculee — ~22/30 confirmed, mixed timing -> MODERATE
        immaculee_entries = build_entries(30, missed_days_ago={2, 5, 9, 13, 18, 22, 26, 29},
                                           response_base=70, response_jitter=12)
        seed_confirmation_logs(conn, immaculee["patientId"], immaculee_plan["id"], immaculee_schedule["id"],
                                time(7, 30), 60, immaculee_entries)
        seed_home_visit(conn, immaculee["patientId"], JEAN_DAMASCENE_CHW_ID, days_ago=8,
                         adherence_status="FAIR", pill_recorded=20, pill_expected=24, discrepancy=True,
                         side_effects="Mild nausea reported, advised to take with food.")
        seed_home_visit(conn, immaculee["patientId"], JEAN_DAMASCENE_CHW_ID, days_ago=22,
                         adherence_status="FAIR", pill_recorded=14, pill_expected=14, discrepancy=False)
        print("  Immaculee: 30 confirmation_logs (8 missed), 2 home visits (1 with discrepancy)")

        # Jean Damascene — backfill last 6 days mostly missed -> HIGH/CRITICAL
        jean_entries = build_entries(6, missed_days_ago={1, 2, 3, 4, 6}, response_base=18, response_jitter=2)
        seed_confirmation_logs(conn, JEAN_DAMASCENE_PATIENT_ID, JEAN_DAMASCENE_PLAN_ID, JEAN_DAMASCENE_SCHEDULE_ID,
                                time(8, 0), 60, jean_entries)
        seed_home_visit(conn, JEAN_DAMASCENE_PATIENT_ID, JEAN_DAMASCENE_CHW_ID, days_ago=4,
                         adherence_status="POOR", pill_recorded=18, pill_expected=30, discrepancy=True,
                         side_effects="Patient reports persistent nausea and dizziness.",
                         symptoms="Cough still present, appears fatigued.")
        seed_home_visit(conn, JEAN_DAMASCENE_PATIENT_ID, JEAN_DAMASCENE_CHW_ID, days_ago=11,
                         adherence_status="POOR", pill_recorded=22, pill_expected=30, discrepancy=True,
                         side_effects="Patient reports loss of appetite.")

        # Tighten the original smoke-test confirmation so avg response time
        # also lands in the "implausibly fast" range for the CRITICAL story.
        conn.execute(text("""
            UPDATE confirmation_logs
            SET confirmed_at = window_open_time + interval '18 seconds',
                response_time_seconds = 18,
                is_within_window = true,
                ai_suspicion_flag = true,
                suspicion_reason = 'Implausibly fast response time (<30s) - possible third-party confirmation'
            WHERE id = :id
        """), {"id": JEAN_DAMASCENE_CONFIRMATION_ID})
        print("  Jean Damascene: +6 confirmation_logs (5 missed), 2 home visits, tightened existing log")

    # ── Trigger AI risk scoring for all ACTIVE patients ─────────────────────
    print("\nTriggering AI risk scoring...")
    for name, pid in [
        ("Marie Uwimana", marie["patientId"]),
        ("Immaculee Nyiraneza", immaculee["patientId"]),
        ("Jean Damascene", JEAN_DAMASCENE_PATIENT_ID),
    ]:
        result = trigger_risk_score(pid)
        print(f"  {name}: risk_score={result['risk_score']}  risk_level={result['risk_level']}")

    print("\nDone. Demo dataset:")
    print(f"  Marie Uwimana       (ACTIVE)      patientId={marie['patientId']}")
    print(f"  Pierre Hakizimana   (PROVISIONAL) patientId={pierre['patientId']}  referralId={pierre['referralId']}")
    print(f"  Immaculee Nyiraneza (ACTIVE)      patientId={immaculee['patientId']}")
    print(f"  Jean Damascene      (ACTIVE)      patientId={JEAN_DAMASCENE_PATIENT_ID}")


if __name__ == "__main__":
    main()
