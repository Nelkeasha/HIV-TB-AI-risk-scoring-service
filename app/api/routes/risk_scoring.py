from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import require_api_key
from app.schemas.risk_scoring import RiskScoreRequest, RiskScoreResponse
from app.services import risk_scoring_service
from app.models.patient import Patient
from uuid import UUID
import logging

logger = logging.getLogger(__name__)
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


@router.post("/run-all", summary="Score all active patients (use to trigger manually or via external cron)")
def run_all(
    _key: str = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    patients = db.query(Patient).filter(Patient.is_active == True).all()
    ok, errors = [], []
    for p in patients:
        try:
            risk_scoring_service.calculate(p.id, db)
            ok.append(str(p.id))
        except Exception as e:
            logger.warning("Scoring failed for %s: %s", p.full_name, e)
            errors.append({"patient_id": str(p.id), "name": p.full_name, "error": str(e)})
    return {"scored": len(ok), "errors": len(errors), "error_details": errors}
