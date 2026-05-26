from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid


class HomeVisit(Base):
    __tablename__ = "home_visits"

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id              = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    chw_id                  = Column(UUID(as_uuid=True), ForeignKey("chws.id"), nullable=False)
    visit_date              = Column(DateTime, nullable=False)
    adherence_status        = Column(String(20), nullable=False)
    pill_count_recorded     = Column(Integer)
    pill_count_expected     = Column(Integer)
    pill_count_discrepancy  = Column(Boolean, default=False)
    symptoms_reported       = Column(Text)
    side_effects_reported   = Column(Text)
    psychosocial_notes      = Column(Text)
    next_visit_date         = Column(DateTime)
    fhir_observation_id     = Column(String(100))
    sync_status             = Column(String(20), default="PENDING")
    created_at              = Column(DateTime)

    patient                 = relationship("Patient", back_populates="home_visits")
