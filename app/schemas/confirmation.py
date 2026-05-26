from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class ConfirmationAnalysisRequest(BaseModel):
    patient_id: UUID
    schedule_id: UUID
    response_time_seconds: int
    confirmed_at: datetime
    window_open_time: datetime
    window_close_time: datetime


class ConfirmationAnalysisResponse(BaseModel):
    patient_id: UUID
    schedule_id: UUID
    is_suspicious: bool
    suspicion_score: int        # 0–3 (one point per signal triggered)
    signals_triggered: list[str]
    recommended_action: str
    ai_suspicion_flag_set: bool
