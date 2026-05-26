from sqlalchemy import Column, String, Boolean, DateTime, Integer, Numeric, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid


class AiRiskScore(Base):
    __tablename__ = "ai_risk_scores"

    id                              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id                      = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    risk_level                      = Column(String(20), nullable=False)
    risk_score                      = Column(Numeric(5, 2), nullable=False)
    suspicion_score                 = Column(Integer, default=0)
    missed_doses_7d                 = Column(Integer, default=0)
    missed_doses_14d                = Column(Integer, default=0)
    missed_doses_30d                = Column(Integer, default=0)
    avg_response_time_seconds       = Column(Integer)
    side_effect_reports_14d         = Column(Integer, default=0)
    missed_visits_30d               = Column(Integer, default=0)
    timestamp_anomaly_detected      = Column(Boolean, default=False)
    pill_count_discrepancy_detected = Column(Boolean, default=False)
    window_violation_detected       = Column(Boolean, default=False)
    recommended_action              = Column(Text)
    calculated_at                   = Column(DateTime)

    patient                         = relationship("Patient", back_populates="risk_scores")
