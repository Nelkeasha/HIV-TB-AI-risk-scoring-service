from pydantic import BaseModel
from datetime import datetime


class ClusterAlert(BaseModel):
    cluster_type: str       # GEOGRAPHIC | CHW_LEVEL | TEMPORAL
    description: str
    affected_count: int
    severity: str
    affected_ids: list[str]


class EarlyWarningResponse(BaseModel):
    generated_at: datetime
    clusters_detected: int
    alerts: list[ClusterAlert]
