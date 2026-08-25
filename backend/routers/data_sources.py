from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Literal
import crud, schemas
from database import get_db
from data_source_import import (
    DataSourceImportError,
    decode_sql_upload,
    parse_data_source_import_filename,
    prepare_sql_import,
    process_data_source_import,
    request_cancel_data_source_import,
)
from knowledge_base import build_knowledge_base
from llm_config import LLMConfigurationError, get_llm
from data_source_provisioning import (
    DataSourceProvisioningError,
    drop_data_source_database,
    validate_and_provision_data_source,
)
from models import User
from security import get_current_user

router = APIRouter(prefix="/api/admin/data_sources", tags=["data_sources"], dependencies=[Depends(get_current_user)])
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


def _validate_enterprise(db: Session, enterprise_id: int) -> None:
    if crud.get_enterprise(db, enterprise_id) is None:
        raise HTTPException(
            status_code=400,
            detail={"message": f"企业 ID {enterprise_id} 不存在，请先在企业管理中创建企业"},
        )


def _sync_schema_knowledge() -> None:
    try:
        build_knowledge_base()
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={"message": f"数据源已写入，但表结构知识同步失败：{exc}"},
        ) from exc


def _shares_physical_database(first, second) -> bool:
    first_host = (first.host or "").strip().casefold()
    second_host = (second.host or "").strip().casefold()
    same_host = first_host == second_host or (
        first_host in LOCAL_HOSTS and second_host in LOCAL_HOSTS
    )
    return (
        same_host
        and int(first.port or 3306) == int(second.port or 3306)
        and (first.db_type or "mysql").casefold() == (second.db_type or "mysql").casefold()
        and (first.database or "").strip().casefold() == (second.database or "").strip().casefold()
    )

@router.get("/", response_model=List[schemas.DataSourceResponse])
def read_data_sources(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return crud.get_data_sources(db, skip=skip, limit=limit)


@router.post("/import", response_model=schemas.DataSourceImportJobResponse, status_code=202)
async def import_data_source_sql(
    background_tasks: BackgroundTasks,
    sql_file: bytes = Body(..., media_type="application/sql"),
    file_name: str = Query(..., min_length=1, max_length=255),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accept one SQL initialization package and start durable background onboarding."""

    safe_file_name = Path(file_name.replace("\\", "/")).name
    try:
        enterprise_name, data_source_name = parse_data_source_import_filename(safe_file_name)
    except DataSourceImportError as exc:
        raise HTTPException(
            status_code=400,
            detail={"stage": "file_name_validation", "message": str(exc)},
        ) from exc
    try:
        get_llm(current_user.id)
    except LLMConfigurationError as exc:
        raise HTTPException(
            status_code=400,
            detail={"stage": "metric_generation", "message": f"请先在智能问数中配置 DeepSeek API：{exc}"},
        ) from exc
    latest = crud.get_latest_data_source_import_job(db, current_user.id)
    if latest and latest.status in {"queued", "processing"}:
        raise HTTPException(
            status_code=409,
            detail={"message": "当前已有数据源接入任务正在处理，请等待完成后再上传"},
        )
    try:
        sql_text = decode_sql_upload(sql_file, safe_file_name)
        prepared = prepare_sql_import(sql_text)
    except DataSourceImportError as exc:
        raise HTTPException(
            status_code=400,
            detail={"stage": "sql_upload_validation", "message": str(exc)},
        ) from exc
    enterprise = crud.get_enterprise_by_name(db, enterprise_name)
    if enterprise is None:
        enterprise = crud.create_enterprise(db, schemas.EnterpriseCreate(name=enterprise_name))
    job = crud.create_data_source_import_job(
        db,
        user_id=current_user.id,
        enterprise_id=enterprise.id,
        data_source_name=data_source_name,
        file_name=safe_file_name,
    )
    job = crud.update_data_source_import_job(
        db,
        job.id,
        database_name=prepared.database_name,
        message="SQL 文件上传完成，等待建设数据源",
    )
    background_tasks.add_task(process_data_source_import, job.id, sql_text)
    return job


@router.get("/import-jobs/latest", response_model=schemas.DataSourceImportJobResponse)
def read_latest_import_job(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = crud.get_latest_data_source_import_job(db, current_user.id)
    if job is None:
        raise HTTPException(status_code=404, detail={"message": "暂无数据源接入任务"})
    return job


@router.post("/import-jobs/{job_id}/cancel", response_model=schemas.DataSourceImportJobResponse)
def cancel_import_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = crud.get_data_source_import_job(db, job_id)
    if job is None or int(job.user_id) != int(current_user.id):
        raise HTTPException(status_code=404, detail={"message": "数据源接入任务不存在"})
    return request_cancel_data_source_import(db, job_id)


@router.get("/import-jobs/{job_id}", response_model=schemas.DataSourceImportJobResponse)
def read_import_job(
    job_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    job = crud.get_data_source_import_job(db, job_id)
    if job is None or int(job.user_id) != int(current_user.id):
        raise HTTPException(status_code=404, detail={"message": "数据源接入任务不存在"})
    return job

@router.get("/{ds_id}", response_model=schemas.DataSourceResponse)
def read_data_source(ds_id: int, db: Session = Depends(get_db)):
    db_ds = crud.get_data_source(db, ds_id)
    if db_ds is None:
        raise HTTPException(status_code=404, detail="DataSource not found")
    return db_ds

@router.post("/", response_model=schemas.DataSourceResponse)
def create_data_source(ds: schemas.DataSourceCreate, db: Session = Depends(get_db)):
    _validate_enterprise(db, ds.enterprise_id)
    try:
        provisioning = validate_and_provision_data_source(ds)
    except DataSourceProvisioningError as exc:
        raise HTTPException(
            status_code=400,
            detail={"stage": "data_source_provisioning", "message": str(exc)},
        ) from exc
    record = crud.create_data_source(db, ds)
    _sync_schema_knowledge()
    response = schemas.DataSourceResponse.model_validate(record)
    return response.model_copy(update={
        "provisioning_status": provisioning.status,
        "provisioning_message": provisioning.message,
    })

@router.put("/{ds_id}", response_model=schemas.DataSourceResponse)
def update_data_source(ds_id: int, ds: schemas.DataSourceUpdate, db: Session = Depends(get_db)):
    _validate_enterprise(db, ds.enterprise_id)
    db_ds = crud.update_data_source(db, ds_id, ds)
    if db_ds is None:
        raise HTTPException(status_code=404, detail="DataSource not found")
    _sync_schema_knowledge()
    return db_ds

@router.delete("/{ds_id}", response_model=dict)
def delete_data_source(
    ds_id: int,
    mode: Literal["disconnect", "full"] = "disconnect",
    db: Session = Depends(get_db),
):
    source = crud.get_data_source(db, ds_id, include_inactive=True)
    if source is None:
        raise HTTPException(status_code=404, detail="DataSource not found")
    if mode == "disconnect":
        crud.disconnect_data_source(db, ds_id)
        detail = {"detail": "disconnected", "database_deleted": False, "metrics_deleted": 0}
    else:
        shared_by = [
            item.name
            for item in crud.get_all_data_sources(db)
            if int(item.id) != int(ds_id) and _shares_physical_database(source, item)
        ]
        if shared_by:
            raise HTTPException(
                status_code=409,
                detail={
                    "stage": "data_source_deletion",
                    "message": "该数据库仍被其他数据源连接使用："
                    + "、".join(shared_by)
                    + "。请先取消这些连接，系统已拒绝删除实际数据库",
                },
            )
        try:
            drop_data_source_database(source)
        except DataSourceProvisioningError as exc:
            raise HTTPException(
                status_code=400,
                detail={"stage": "data_source_deletion", "message": str(exc)},
            ) from exc
        result = crud.delete_data_source(db, ds_id)
        detail = {
            "detail": "deleted",
            "database_deleted": True,
            **result,
        }
    try:
        build_knowledge_base()
    except Exception as exc:
        detail["knowledge_warning"] = f"数据源操作已完成，但知识索引刷新失败：{exc}"
    return detail
