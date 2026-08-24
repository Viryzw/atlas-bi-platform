from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import AuditLog
from security import require_admin


router = APIRouter(
    prefix="/api/admin/audit-logs",
    tags=["audit"],
    dependencies=[Depends(require_admin)],
)


class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    method: str
    path: str
    status_code: int
    client_ip: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


@router.get("/", response_model=List[AuditLogResponse])
def list_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    return db.query(AuditLog).order_by(AuditLog.id.desc()).limit(limit).all()
