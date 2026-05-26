from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import require_api_key
from app.schemas.correlation import ClinicalCorrelationRequest, ClinicalCorrelationResponse
from app.services import clinical_correlation_service

router = APIRouter()


@router.post("/clinical-correlation", response_model=ClinicalCorrelationResponse,
             summary="Correlate reported adherence with CHW-verified pill counts")
def clinical_correlation(
    request: ClinicalCorrelationRequest,
    _key: str = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    try:
        return clinical_correlation_service.correlate(request.patient_id, db)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
