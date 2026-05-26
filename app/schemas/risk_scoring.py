from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class RiskScoreRequest(BaseModel):
    patient_id: UUID


class RiskFeatures(BaseModel):
    adherence_7d: float
    adherence_14d: float
    adherence_30d: float
    avg_response_time_seconds: float
    side_effect_reports_14d: int
    missed_visits_30d: int


class RiskScoreResponse(BaseModel):
    patient_id: UUID
    patient_name: str
    risk_score: float
    risk_level: str
    features: RiskFeatures
    missed_doses_7d: int
    missed_doses_14d: int
    missed_doses_30d: int
    suspicion_score: int
    timestamp_anomaly_detected: bool
    pill_count_discrepancy_detected: bool
    window_violation_detected: bool
    recommended_action: str
    calculated_at: datetime
