from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid


class LabResult(Base):
    """A single lab Observation value pulled from the FHIR server (e.g. HIV
    viral load, CD4 count), one row per patient/LOINC code/observation date.
    Populated by lab_sync_service; compared against adherence trends in
    clinical_correlation_service (REQ-13)."""

    __tablename__ = "lab_results"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_id          = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    loinc_code          = Column(String(20), nullable=False)
    value               = Column(Numeric(12, 4), nullable=False)
    unit                = Column(String(30))
    observed_at         = Column(DateTime, nullable=False)
    fhir_observation_id = Column(String(100))
    created_at          = Column(DateTime)

    patient             = relationship("Patient")
