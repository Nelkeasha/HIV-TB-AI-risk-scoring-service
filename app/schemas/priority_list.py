from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class PatientPriority(BaseModel):
    patient_id: UUID
    patient_name: str
    patient_code: str
    risk_score: float
    risk_level: str
    priority_group: str   # VISIT_TODAY | CALL_TODAY | STABLE
    recommended_action: str


class PriorityListResponse(BaseModel):
    chw_id: UUID
    generated_at: datetime
    visit_today: list[PatientPriority]
    call_today: list[PatientPriority]
    stable: list[PatientPriority]
    total_patients: int
