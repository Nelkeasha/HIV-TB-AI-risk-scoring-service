from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:12345@localhost:5432/hivtb_db"
    internal_api_key: str = "hivtb-internal-key-2026"
    spring_boot_base_url: str = "http://localhost:8080"

    risk_score_threshold_high: int = 70
    risk_score_threshold_critical: int = 85
    cluster_min_patients: int = 3
    cluster_decline_percentage: int = 20

    nightly_risk_score_hour: int = 23
    morning_priority_list_hour: int = 6

    # FHIR sync
    fhir_server_url: str = "http://localhost:8090/fhir"
    spring_admin_email: str = ""
    spring_admin_password: str = ""

    # FHIR lab-result correlation (REQ-13) — LOINC codes polled per patient.
    # Defaults are standard LOINC codes; override if your FHIR test data uses different ones.
    loinc_viral_load: str = "25836-8"   # HIV 1 RNA [#/volume] (viral load) in Plasma
    loinc_cd4_count: str = "24467-3"    # CD4 cells [#/volume] in Blood
    lab_sync_lookback_days: int = 90    # how far back to look for Observations on first poll

    model_config = {"env_file": ".env"}


settings = Settings()
