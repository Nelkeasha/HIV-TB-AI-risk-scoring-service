from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import require_api_key
from app.schemas.cluster_detection import EarlyWarningResponse
from app.services import cluster_detection_service

router = APIRouter()


@router.get("/early-warning", response_model=EarlyWarningResponse,
            summary="Detect population-level risk clusters and early warnings")
def get_early_warnings(
    _key: str = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    try:
        return cluster_detection_service.detect(db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
