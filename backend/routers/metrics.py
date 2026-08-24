from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import crud, schemas
from database import get_db
from knowledge_base import build_knowledge_base
from security import get_current_user

router = APIRouter(prefix="/api/admin/metrics", tags=["metrics"], dependencies=[Depends(get_current_user)])


def _validate_data_source(db: Session, data_source_id: int) -> None:
    if crud.get_data_source(db, data_source_id) is None:
        raise HTTPException(
            status_code=400,
            detail={"message": f"数据源 ID {data_source_id} 不存在，请先接入数据源"},
        )


def _sync_knowledge_base() -> None:
    try:
        build_knowledge_base()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"message": f"指标已写入数据库，但知识库同步失败：{exc}"},
        ) from exc

@router.get("/", response_model=List[schemas.MetricResponse])
def read_metrics(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_metrics(db, skip=skip, limit=limit)


@router.get("/catalog", response_model=List[schemas.MetricCatalogItem])
def read_metric_catalog(db: Session = Depends(get_db)):
    data_sources = {item.id: item for item in crud.get_data_sources(db, limit=10000)}
    enterprises = {item.id: item for item in crud.get_enterprises(db, limit=10000)}
    result = []
    for definition in crud.get_metric_definitions(db):
        bindings = []
        for binding in definition.bindings:
            source = data_sources.get(binding.data_source_id)
            if source is None:
                continue
            enterprise = enterprises.get(source.enterprise_id)
            payload = schemas.MetricResponse.model_validate(binding).model_dump()
            bindings.append({
                **payload,
                "data_source_name": source.name,
                "enterprise_id": source.enterprise_id,
                "enterprise_name": enterprise.name if enterprise else "未知企业",
            })
        result.append({
            "id": definition.id,
            "name": definition.name,
            "description": definition.description,
            "topic": definition.topic or "未分类",
            "aliases": definition.aliases,
            "unit": definition.unit,
            "bindings": bindings,
        })
    return result

@router.get("/{metric_id}", response_model=schemas.MetricResponse)
def read_metric(metric_id: int, db: Session = Depends(get_db)):
    db_metric = crud.get_metric(db, metric_id)
    if db_metric is None:
        raise HTTPException(status_code=404, detail="Metric not found")
    return db_metric

@router.post("/", response_model=schemas.MetricResponse)
def create_metric(metric: schemas.MetricCreate, db: Session = Depends(get_db)):
    _validate_data_source(db, metric.data_source_id)
    try:
        db_metric = crud.create_metric(db, metric)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc)}) from exc
    _sync_knowledge_base()
    return db_metric

@router.put("/{metric_id}", response_model=schemas.MetricResponse)
def update_metric(metric_id: int, metric: schemas.MetricUpdate, db: Session = Depends(get_db)):
    _validate_data_source(db, metric.data_source_id)
    try:
        db_metric = crud.update_metric(db, metric_id, metric)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"message": str(exc)}) from exc
    if db_metric is None:
        raise HTTPException(status_code=404, detail="Metric not found")
    _sync_knowledge_base()
    return db_metric


@router.patch("/{metric_id}/dashboard-enabled", response_model=schemas.MetricResponse)
def update_metric_dashboard_enabled(
    metric_id: int,
    payload: schemas.MetricDashboardUpdate,
    db: Session = Depends(get_db),
):
    db_metric = crud.update_metric_dashboard_enabled(
        db,
        metric_id,
        payload.dashboard_enabled,
    )
    if db_metric is None:
        raise HTTPException(status_code=404, detail="Metric not found")
    return db_metric

@router.delete("/{metric_id}", response_model=dict)
def delete_metric(metric_id: int, db: Session = Depends(get_db)):
    success = crud.delete_metric(db, metric_id)
    if not success:
        raise HTTPException(status_code=404, detail="Metric not found")
    _sync_knowledge_base()
    return {"detail": "deleted"}
