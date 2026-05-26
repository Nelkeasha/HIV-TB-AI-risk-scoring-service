from sqlalchemy import Column, String, Boolean, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.core.database import Base
import uuid


class StockRecord(Base):
    __tablename__ = "stock_records"

    id                  = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chw_id              = Column(UUID(as_uuid=True), ForeignKey("chws.id"), nullable=False)
    medication_name     = Column(String(100), nullable=False)
    current_quantity    = Column(Integer, nullable=False, default=0)
    reorder_level       = Column(Integer, nullable=False, default=14)
    unit                = Column(String(20), default="tablets")
    last_restocked_at   = Column(DateTime)
    days_remaining      = Column(Integer)
    resupply_requested  = Column(Boolean, default=False)
    created_at          = Column(DateTime)
    updated_at          = Column(DateTime)

    dispensing_events   = relationship("DispensingEvent", back_populates="stock")
