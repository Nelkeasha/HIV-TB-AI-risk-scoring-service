from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import require_api_key
from app.schemas.risk_scoring import RiskScoreRequest, RiskScoreResponse
from app.services import risk_scoring_service
from uuid import UUID

router = APIRouter()


@router.post("/risk-score/{patient_id}", response_model=RiskScoreResponse,
             summary="Calculate and store risk score for one patient")
def score_patient(
    patient_id: UUID,
    _key: str = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    try:
        result = risk_scoring_service.calculate(patient_id, db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
