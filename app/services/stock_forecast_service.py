from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from app.models.stock_record import StockRecord
from app.models.dispensing_event import DispensingEvent
from app.utils import alert_utils
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


def _daily_rate(stock_id, db: Session) -> float:
    cutoff = datetime.now() - timedelta(days=30)
    events = (
        db.query(DispensingEvent)
        .filter(
            DispensingEvent.stock_id == stock_id,
            DispensingEvent.dispensed_at >= cutoff,
        )
        .all()
    )
    if not events:
        return 1.0
    total_dispensed = sum(e.quantity_dispensed for e in events)
    return max(total_dispensed / 30.0, 0.1)


def forecast(chw_id, db: Session) -> dict:
    stocks = db.query(StockRecord).filter(StockRecord.chw_id == chw_id).all()
    forecasts  = []
    items_at_risk = 0

    for stock in stocks:
        rate          = _daily_rate(stock.id, db)
        days_left     = int(stock.current_quantity / rate) if rate > 0 else 999

        if days_left <= settings.stock_warning_days:
            alert_level = "CRITICAL" if days_left <= 7 else "WARNING"
            items_at_risk += 1
            alert_utils.create_alert(
                db,
                alert_type = "LOW_STOCK",
                severity   = alert_level,
                title      = f"Low Stock — {stock.medication_name}",
                message    = (
                    f"Only {stock.current_quantity} {stock.unit} remaining "
                    f"({days_left} days at current dispensing rate). Resupply needed."
                ),
                chw_id = chw_id,
            )
        else:
            alert_level = "OK"

        stock.days_remaining = days_left
        db.commit()

        forecasts.append({
            "stock_id":              str(stock.id),
            "medication_name":       stock.medication_name,
            "current_quantity":      stock.current_quantity,
            "daily_dispensing_rate": round(rate, 2),
            "days_remaining":        days_left,
            "alert_level":           alert_level,
        })

    return {
        "chw_id":        str(chw_id),
        "generated_at":  datetime.now(),
        "forecasts":     forecasts,
        "items_at_risk": items_at_risk,
    }
