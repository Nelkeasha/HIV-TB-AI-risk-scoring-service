from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class MedicationForecast(BaseModel):
    stock_id: UUID
    medication_name: str
    current_quantity: int
    daily_dispensing_rate: float
    days_remaining: int
    alert_level: str    # OK | WARNING | CRITICAL


class StockForecastResponse(BaseModel):
    chw_id: UUID
    generated_at: datetime
    forecasts: list[MedicationForecast]
    items_at_risk: int
