from pydantic import BaseModel
from uuid import UUID


class ClinicalCorrelationRequest(BaseModel):
    patient_id: UUID


class ClinicalCorrelationResponse(BaseModel):
    patient_id: UUID
    patient_name: str
    pattern: str            # A | B | NONE
    pattern_description: str
    adherence_pct: float
    false_confirmation_flag: bool
    alert_created: bool
    recommended_action: str
