from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import require_api_key
from app.schemas.priority_list import PriorityListResponse
from app.services import priority_list_service
from uuid import UUID

router = APIRouter()


@router.get("/priority-list/{chw_id}", response_model=PriorityListResponse,
            summary="Generate daily priority list for a CHW")
def get_priority_list(
    chw_id: UUID,
    _key: str = Depends(require_api_key),
    db: Session = Depends(get_db),
):
    try:
        return priority_list_service.generate(chw_id, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
