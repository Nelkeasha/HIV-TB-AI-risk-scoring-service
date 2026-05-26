from sqlalchemy import Column, String, Boolean, Date, DateTime, ForeignKey, Enum as PgEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid


class Patient(Base):
    __tablename__ = "patients"

    id                    = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    patient_code          = Column(String(20), unique=True, nullable=False)
    full_name             = Column(String(100), nullable=False)
    date_of_birth         = Column(Date, nullable=False)
    sex                   = Column(String(10), nullable=False)
    national_id           = Column(String(16), unique=True)
    phone_number          = Column(String(20))
    has_smartphone        = Column(Boolean, default=False)
    diagnosis_type        = Column(String(30), nullable=False)
    art_start_date        = Column(Date)
    tb_treatment_start_date = Column(Date)
    household_location    = Column(String(255))
    village               = Column(String(100))
    sector                = Column(String(100))
    district              = Column(String(100))
    chw_id                = Column(UUID(as_uuid=True), ForeignKey("chws.id"), nullable=False)
    facility_id           = Column(UUID(as_uuid=True), ForeignKey("facilities.id"), nullable=False)
    user_id               = Column(UUID(as_uuid=True), ForeignKey("system_users.id"))
    fhir_patient_id       = Column(String(100), unique=True)
    sync_status           = Column(String(20), default="PENDING")
    is_active             = Column(Boolean, default=True)
    created_at            = Column(DateTime)
    updated_at            = Column(DateTime)

    confirmation_logs     = relationship("ConfirmationLog", back_populates="patient")
    home_visits           = relationship("HomeVisit", back_populates="patient")
    medication_records    = relationship("MedicationRecord", back_populates="patient")
    risk_scores           = relationship("AiRiskScore", back_populates="patient")
