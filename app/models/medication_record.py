from sqlalchemy import Column, String, Boolean, Date, DateTime, Integer, Numeric, BigInteger, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base


class MedicationRecord(Base):
    __tablename__ = "medication_records"

    id                      = Column(BigInteger, primary_key=True, autoincrement=True)
    patient_id              = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    plan_id                 = Column(UUID(as_uuid=True), ForeignKey("treatment_plans.id"))
    period_start            = Column(Date, nullable=False)
    period_end              = Column(Date, nullable=False)
    doses_scheduled         = Column(Integer, nullable=False)
    doses_confirmed         = Column(Integer, nullable=False)
    doses_verified          = Column(Integer, nullable=False)
    adherence_pct           = Column(Numeric(5, 2), nullable=False)
    below_threshold         = Column(Boolean, default=False)
    false_confirmation_flag = Column(Boolean, default=False)
    fhir_statement_id       = Column(String(100))
    sync_status             = Column(String(20), default="PENDING")
    updated_at              = Column(DateTime)

    patient                 = relationship("Patient", back_populates="medication_records")
