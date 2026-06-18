from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base
import uuid


class SystemSettings(Base):
    """Mirrors the Java entity of the same name — single global row,
    seeded by Spring Boot's V15 migration. Admin-configurable thresholds
    live here instead of this service's own static .env values."""

    __tablename__ = "system_settings"

    id                      = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    missed_dose_threshold   = Column(Integer, nullable=False, default=2)
    low_stock_days          = Column(Integer, nullable=False, default=14)
    confirm_window_minutes  = Column(Integer, nullable=False, default=45)
    high_risk_threshold     = Column(Integer, nullable=False, default=70)
    critical_risk_threshold = Column(Integer, nullable=False, default=85)
    updated_at              = Column(DateTime)
