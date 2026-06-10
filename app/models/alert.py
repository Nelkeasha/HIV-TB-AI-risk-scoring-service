from sqlalchemy import Column, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid


class Alert(Base):
    __tablename__ = "alerts"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id      = Column(UUID(as_uuid=True), ForeignKey("patients.id"))
    chw_id          = Column(UUID(as_uuid=True))
    provider_id     = Column(UUID(as_uuid=True))
    supervisor_id   = Column(UUID(as_uuid=True))
    alert_type      = Column(String(30), nullable=False)
    severity        = Column(String(20), nullable=False)
    title           = Column(String(200), nullable=False)
    message         = Column(Text, nullable=False)
    is_read         = Column(Boolean, default=False)
    is_resolved     = Column(Boolean, default=False)
    resolved_at     = Column(DateTime)
    created_at      = Column(DateTime)
