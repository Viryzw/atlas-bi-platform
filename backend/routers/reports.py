import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

import crud
import schemas
from database import get_db
from models import ReportDraft, ReportVersion, User
from security import get_current_user, require_same_user_or_admin


router = APIRouter(prefix="/api/reports", tags=["reports"])


def _decode_content(raw: str) -> dict:
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _require_user(db: Session, user_id: int) -> None:
    if crud.get_user(db, user_id) is None:
        raise HTTPException(status_code=404, detail={"message": f"用户 ID {user_id} 不存在"})


def _owned_report(db: Session, report_id: int, user_id: int) -> ReportDraft:
    record = (
        db.query(ReportDraft)
        .filter(ReportDraft.id == report_id, ReportDraft.user_id == user_id)
        .first()
    )
    if record is None:
        raise HTTPException(status_code=404, detail={"message": "报告不存在或不属于当前用户"})
    return record


def _summary(db: Session, record: ReportDraft) -> schemas.ReportDraftSummary:
    version_count = (
        db.query(func.count(ReportVersion.id))
        .filter(ReportVersion.report_id == record.id)
        .scalar()
        or 0
    )
    return schemas.ReportDraftSummary(
        id=record.id,
        user_id=record.user_id,
        title=record.title,
        data_source_id=record.data_source_id,
        period=record.period,
        version_count=int(version_count),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _detail(db: Session, record: ReportDraft) -> schemas.ReportDraftDetail:
    versions = (
        db.query(ReportVersion)
        .filter(ReportVersion.report_id == record.id)
        .order_by(ReportVersion.version_number.desc())
        .all()
    )
    summary = _summary(db, record).model_dump()
    return schemas.ReportDraftDetail(
        **summary,
        content=_decode_content(record.content_json),
        versions=[
            schemas.ReportVersionResponse(
                id=version.id,
                version_number=version.version_number,
                content=_decode_content(version.content_json),
                created_at=version.created_at,
            )
            for version in versions
        ],
    )


@router.get("/", response_model=List[schemas.ReportDraftSummary])
def list_reports(user_id: int = Query(gt=0), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if isinstance(current_user, User):
        require_same_user_or_admin(current_user, user_id)
    _require_user(db, user_id)
    return [
        _summary(db, record)
        for record in (
            db.query(ReportDraft)
            .filter(ReportDraft.user_id == user_id)
            .order_by(ReportDraft.updated_at.desc(), ReportDraft.id.desc())
            .all()
        )
    ]


@router.post("/", response_model=schemas.ReportDraftDetail)
def create_report(payload: schemas.ReportDraftCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if isinstance(current_user, User):
        require_same_user_or_admin(current_user, payload.user_id)
    _require_user(db, payload.user_id)
    if payload.data_source_id is not None and crud.get_data_source(db, payload.data_source_id) is None:
        raise HTTPException(status_code=400, detail={"message": f"数据源 ID {payload.data_source_id} 不存在"})
    content_json = json.dumps(payload.content, ensure_ascii=False, default=str)
    record = ReportDraft(
        user_id=payload.user_id,
        title=payload.title.strip(),
        data_source_id=payload.data_source_id,
        period=payload.period,
        content_json=content_json,
    )
    db.add(record)
    db.flush()
    db.add(ReportVersion(report_id=record.id, version_number=1, content_json=content_json))
    db.commit()
    db.refresh(record)
    return _detail(db, record)


@router.get("/{report_id}", response_model=schemas.ReportDraftDetail)
def get_report(report_id: int, user_id: int = Query(gt=0), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if isinstance(current_user, User):
        require_same_user_or_admin(current_user, user_id)
    return _detail(db, _owned_report(db, report_id, user_id))


@router.put("/{report_id}", response_model=schemas.ReportDraftDetail)
def update_report(
    report_id: int,
    payload: schemas.ReportDraftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if isinstance(current_user, User):
        require_same_user_or_admin(current_user, payload.user_id)
    record = _owned_report(db, report_id, payload.user_id)
    if payload.data_source_id is not None and crud.get_data_source(db, payload.data_source_id) is None:
        raise HTTPException(status_code=400, detail={"message": f"数据源 ID {payload.data_source_id} 不存在"})
    next_version = (
        db.query(func.max(ReportVersion.version_number))
        .filter(ReportVersion.report_id == record.id)
        .scalar()
        or 0
    ) + 1
    content_json = json.dumps(payload.content, ensure_ascii=False, default=str)
    record.title = payload.title.strip()
    record.data_source_id = payload.data_source_id
    record.period = payload.period
    record.content_json = content_json
    record.updated_at = func.now()
    db.add(ReportVersion(report_id=record.id, version_number=next_version, content_json=content_json))
    db.commit()
    db.refresh(record)
    return _detail(db, record)


@router.delete("/{report_id}")
def delete_report(report_id: int, user_id: int = Query(gt=0), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if isinstance(current_user, User):
        require_same_user_or_admin(current_user, user_id)
    record = _owned_report(db, report_id, user_id)
    db.query(ReportVersion).filter(ReportVersion.report_id == record.id).delete()
    db.delete(record)
    db.commit()
    return {"detail": "deleted"}
