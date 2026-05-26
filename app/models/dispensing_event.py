from sqlalchemy import Column, String, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid


class DispensingEvent(Base):
    __tablename__ = "dispensing_events"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    stock_id            = Column(UUID(as_uuid=True), ForeignKey("stock_records.id"), nullable=False)
    patient_id          = Column(UUID(as_uuid=True), ForeignKey("patients.id"), nullable=False)
    chw_id              = Column(UUID(as_uuid=True), ForeignKey("chws.id"), nullable=False)
    medication_name     = Column(String(100), nullable=False)
    quantity_dispensed  = Column(Integer, nullable=False)
    dispensed_at        = Column(DateTime)
    visit_id            = Column(UUID(as_uuid=True), ForeignKey("home_visits.id"))
    sync_status         = Column(String(20), default="PENDING")

    stock               = relationship("StockRecord", back_populates="dispensing_events")
