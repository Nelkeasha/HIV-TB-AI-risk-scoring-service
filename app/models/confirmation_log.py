from sqlalchemy import Column, String, Boolean, Date, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid


class ConfirmationLog(Base):
    __tablename__ = "confirmation_logs"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id          = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    plan_id             = Column(UUID(as_uuid=True), ForeignKey("treatment_plans.id"))
    schedule_id         = Column(UUID(as_uuid=True), ForeignKey("dose_schedules.id"))
    scheduled_date      = Column(Date, nullable=False)
    confirmed_at        = Column(DateTime)
    confirmation_method = Column(String(10))
    response_time_seconds = Column(Integer)
    window_open_time    = Column(DateTime, nullable=False)
    window_close_time   = Column(DateTime, nullable=False)
    is_within_window    = Column(Boolean, default=False)
    raw_sms_response    = Column(String(20))
    is_missed           = Column(Boolean, nullable=False, default=False)
    ai_suspicion_flag   = Column(Boolean, nullable=False, default=False)
    suspicion_reason    = Column(String(100))
    created_at          = Column(DateTime)

    patient             = relationship("Patient", back_populates="confirmation_logs")
