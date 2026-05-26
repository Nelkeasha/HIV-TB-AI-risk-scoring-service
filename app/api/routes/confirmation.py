from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import require_api_key
from app.schemas.confirmation import ConfirmationAnalysisRequest, ConfirmationAnalysisResponse
from app.services import false_confirmation_service

router = APIRouter()


@router.post("/confirmation/analyze", response_model=ConfirmationAnalysisResponse,
             summary="Analyze a dose confirmation for suspicious patterns")
def analyze_confirmation(
    request: ConfirmationAnalysisRequest,
    _key: str = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    try:
        return false_confirmation_service.analyze(
            patient_id            = request.patient_id,
            schedule_id           = request.schedule_id,
            response_time_seconds = request.response_time_seconds,
            confirmed_at          = request.confirmed_at,
            window_open           = request.window_open_time,
            window_close          = request.window_close_time,
            db                    = db,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
