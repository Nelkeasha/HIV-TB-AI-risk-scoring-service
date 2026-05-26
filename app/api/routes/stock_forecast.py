from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import require_api_key
from app.schemas.stock_forecast import StockForecastResponse
from app.services import stock_forecast_service
from uuid import UUID

router = APIRouter()


@router.get("/stock-forecast/{chw_id}", response_model=StockForecastResponse,
            summary="Forecast medication stock levels for a CHW")
def get_stock_forecast(
    chw_id: UUID,
    _key: str = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    try:
        return stock_forecast_service.forecast(chw_id, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
