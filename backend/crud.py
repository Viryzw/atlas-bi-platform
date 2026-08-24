from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from models import (
    Conversation,
    ConversationMessage,
    DataSource,
    DataSourceImportJob,
    Department,
    DepartmentEmployee,
    DepartmentTask,
    Enterprise,
    KnowledgeDocument,
    Metric,
    MetricDefinition,
    ReportDraft,
    ReportVersion,
    User,
    UserLLMConfig,
)
import schemas
from secret_store import encrypt_secret
from security import hash_password

# ---------- Enterprise ----------
def get_enterprise(db: Session, enterprise_id: int):
    return db.query(Enterprise).filter(Enterprise.id == enterprise_id).first()

def get_enterprises(db: Session, skip: int = 0, limit: int = 100):
    return db.query(Enterprise).order_by(Enterprise.id.asc()).offset(skip).limit(limit).all()

def get_enterprise_by_name(db: Session, name: str):
    normalized = str(name or "").strip().casefold()
    return next(
        (item for item in get_enterprises(db, limit=10000) if item.name.strip().casefold() == normalized),
        None,
    )

def create_enterprise(db: Session, enterprise: schemas.EnterpriseCreate):
    db_enterprise = Enterprise(**enterprise.model_dump())
    db.add(db_enterprise)
    db.commit()
    db.refresh(db_enterprise)
    return db_enterprise

def update_enterprise(db: Session, enterprise_id: int, enterprise: schemas.EnterpriseUpdate):
    db_enterprise = get_enterprise(db, enterprise_id)
    if db_enterprise:
        for key, value in enterprise.model_dump().items():
            setattr(db_enterprise, key, value)
        db.commit()
        db.refresh(db_enterprise)
    return db_enterprise

def delete_enterprise(db: Session, enterprise_id: int):
    db_enterprise = get_enterprise(db, enterprise_id)
    if db_enterprise:
        try:
            # A failed/cancelled import can outlive its placeholder enterprise.
            # Once the enterprise has no source or department, these job rows
            # are operational history only and must not make the empty catalog
            # record undeletable.
            db.query(DataSourceImportJob).filter(
                DataSourceImportJob.enterprise_id == enterprise_id
            ).delete(synchronize_session=False)
            db.delete(db_enterprise)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
    return False

# ---------- Department ----------
def get_department(db: Session, department_id: int):
    return db.query(Department).filter(Department.id == department_id).first()

def get_departments(db: Session, skip: int = 0, limit: int = 200):
    return db.query(Department).order_by(Department.id.asc()).offset(skip).limit(limit).all()

def create_department(db: Session, department: schemas.DepartmentCreate):
    record = Department(**department.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record

def update_department(db: Session, department_id: int, department: schemas.DepartmentUpdate):
    record = get_department(db, department_id)
    if record:
        for key, value in department.model_dump().items():
            setattr(record, key, value)
        db.commit()
        db.refresh(record)
    return record

def delete_department(db: Session, department_id: int):
    record = get_department(db, department_id)
    if record:
        try:
            # Keep descendants instead of deleting them implicitly. They become
            # first-level departments; only the selected department's own
            # employees and tasks are removed.
            db.query(Department).filter(Department.parent_id == department_id).update(
                {Department.parent_id: None}, synchronize_session=False
            )
            db.query(DepartmentEmployee).filter(
                DepartmentEmployee.department_id == department_id
            ).delete(synchronize_session=False)
            db.query(DepartmentTask).filter(
                DepartmentTask.department_id == department_id
            ).delete(synchronize_session=False)
            db.delete(record)
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
    return False


def get_department_tasks(db: Session, department_id: int):
    return (
        db.query(DepartmentTask)
        .filter(DepartmentTask.department_id == department_id)
        .order_by(DepartmentTask.id.asc())
        .all()
    )


def get_department_task(db: Session, department_id: int, task_id: int):
    return db.query(DepartmentTask).filter(
        DepartmentTask.id == task_id,
        DepartmentTask.department_id == department_id,
    ).first()


def create_department_task(db: Session, department_id: int, payload: schemas.DepartmentTaskCreate):
    record = DepartmentTask(department_id=department_id, **payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_department_task(
    db: Session,
    department_id: int,
    task_id: int,
    payload: schemas.DepartmentTaskUpdate,
):
    record = get_department_task(db, department_id, task_id)
    if record:
        for key, value in payload.model_dump().items():
            setattr(record, key, value)
        db.commit()
        db.refresh(record)
    return record


def delete_department_task(db: Session, department_id: int, task_id: int):
    record = get_department_task(db, department_id, task_id)
    if not record:
        return False
    try:
        db.query(DepartmentEmployee).filter(
            DepartmentEmployee.department_id == department_id,
            DepartmentEmployee.task_id == task_id,
        ).update({DepartmentEmployee.task_id: None}, synchronize_session=False)
        db.delete(record)
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise


def get_department_employees(db: Session, department_id: int):
    return (
        db.query(DepartmentEmployee)
        .filter(DepartmentEmployee.department_id == department_id)
        .order_by(DepartmentEmployee.id.asc())
        .all()
    )


def get_department_employee(db: Session, department_id: int, employee_id: int):
    return db.query(DepartmentEmployee).filter(
        DepartmentEmployee.id == employee_id,
        DepartmentEmployee.department_id == department_id,
    ).first()


def create_department_employee(
    db: Session,
    department_id: int,
    payload: schemas.DepartmentEmployeeCreate,
):
    record = DepartmentEmployee(department_id=department_id, **payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def update_department_employee(
    db: Session,
    department_id: int,
    employee_id: int,
    payload: schemas.DepartmentEmployeeUpdate,
):
    record = get_department_employee(db, department_id, employee_id)
    if record:
        for key, value in payload.model_dump().items():
            setattr(record, key, value)
        db.commit()
        db.refresh(record)
    return record


def delete_department_employee(db: Session, department_id: int, employee_id: int):
    record = get_department_employee(db, department_id, employee_id)
    if not record:
        return False
    db.delete(record)
    db.commit()
    return True

# ---------- DataSource ----------
def get_data_source(db: Session, ds_id: int, include_inactive: bool = False):
    query = db.query(DataSource).filter(DataSource.id == ds_id)
    if not include_inactive:
        query = query.filter(DataSource.is_active.is_(True))
    return query.first()

def get_data_sources(db: Session, skip: int = 0, limit: int = 100):
    return (
        db.query(DataSource)
        .filter(DataSource.is_active.is_(True))
        .order_by(DataSource.id.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )


def get_all_data_sources(db: Session):
    return db.query(DataSource).order_by(DataSource.id.asc()).all()

def get_enterprise_data_sources(db: Session, enterprise_id: int):
    return (
        db.query(DataSource)
        .filter(
            DataSource.enterprise_id == enterprise_id,
            DataSource.is_active.is_(True),
        )
        .order_by(DataSource.id.asc())
        .all()
    )

def create_data_source(db: Session, ds: schemas.DataSourceCreate):
    values = ds.model_dump()
    values["password"] = encrypt_secret(values.get("password") or "")
    db_ds = DataSource(**values)
    db.add(db_ds)
    db.commit()
    db.refresh(db_ds)
    return db_ds


def create_data_source_import_job(
    db: Session,
    *,
    user_id: int,
    enterprise_id: int,
    data_source_name: str,
    file_name: str,
):
    job = DataSourceImportJob(
        user_id=user_id,
        enterprise_id=enterprise_id,
        data_source_name=data_source_name,
        file_name=file_name,
        status="queued",
        stage="uploaded",
        progress=10,
        message="SQL 文件上传完成",
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def get_data_source_import_job(db: Session, job_id: int):
    return db.query(DataSourceImportJob).filter(DataSourceImportJob.id == job_id).first()


def get_latest_data_source_import_job(db: Session, user_id: int):
    return (
        db.query(DataSourceImportJob)
        .filter(DataSourceImportJob.user_id == user_id)
        .order_by(DataSourceImportJob.id.desc())
        .first()
    )


def update_data_source_import_job(db: Session, job_id: int, **values):
    job = get_data_source_import_job(db, job_id)
    if job:
        for key, value in values.items():
            if hasattr(job, key):
                setattr(job, key, value)
        db.commit()
        db.refresh(job)
    return job

def update_data_source(db: Session, ds_id: int, ds: schemas.DataSourceUpdate):
    db_ds = get_data_source(db, ds_id)
    if db_ds:
        values = ds.model_dump()
        # Editing connection metadata must not erase an existing secret when
        # the UI intentionally leaves the password field blank.
        if not values.get("password"):
            values.pop("password", None)
        elif "password" in values:
            values["password"] = encrypt_secret(values["password"])
        for key, value in values.items():
            setattr(db_ds, key, value)
        db.commit()
        db.refresh(db_ds)
    return db_ds

def disconnect_data_source(db: Session, ds_id: int):
    """Stop platform access while retaining metadata and metric bindings."""

    db_ds = get_data_source(db, ds_id, include_inactive=True)
    if not db_ds:
        return None
    db_ds.is_active = False
    db.commit()
    db.refresh(db_ds)
    return db_ds


def delete_data_source(db: Session, ds_id: int):
    """Remove a source and every platform-owned object that requires it."""

    db_ds = get_data_source(db, ds_id, include_inactive=True)
    if not db_ds:
        return None
    definition_ids = [
        row[0]
        for row in db.query(Metric.definition_id)
        .filter(Metric.data_source_id == ds_id)
        .distinct()
        .all()
    ]
    metrics_deleted = 0
    knowledge_deleted = 0
    try:
        # Some installations may be running before migration 005 has removed
        # the old table. Delete those rows as a compatibility safeguard.
        if inspect(db.get_bind()).has_table("metrics"):
            db.execute(text("DELETE FROM metrics WHERE data_source_id = :source_id"), {"source_id": ds_id})
        metrics_deleted = (
            db.query(Metric)
            .filter(Metric.data_source_id == ds_id)
            .delete(synchronize_session=False)
        )
        knowledge_deleted = (
            db.query(KnowledgeDocument)
            .filter(KnowledgeDocument.data_source_id == ds_id)
            .delete(synchronize_session=False)
        )
        db.query(Conversation).filter(Conversation.data_source_id == ds_id).update(
            {Conversation.data_source_id: None}, synchronize_session=False
        )
        db.query(ReportDraft).filter(ReportDraft.data_source_id == ds_id).update(
            {ReportDraft.data_source_id: None}, synchronize_session=False
        )
        db.query(DataSourceImportJob).filter(DataSourceImportJob.data_source_id == ds_id).update(
            {DataSourceImportJob.data_source_id: None}, synchronize_session=False
        )
        db.flush()
        for definition_id in definition_ids:
            has_binding = db.query(Metric.id).filter(Metric.definition_id == definition_id).first()
            if not has_binding:
                db.query(MetricDefinition).filter(MetricDefinition.id == definition_id).delete(
                    synchronize_session=False
                )
        db.delete(db_ds)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "metrics_deleted": metrics_deleted,
        "knowledge_deleted": knowledge_deleted,
    }

# ---------- Metric ----------
def get_metric(db: Session, metric_id: int):
    return db.query(Metric).filter(Metric.id == metric_id).first()

def get_metrics(db: Session, skip: int = 0, limit: int = 100):
    return (
        db.query(Metric)
        .join(DataSource, Metric.data_source_id == DataSource.id)
        .filter(DataSource.is_active.is_(True))
        .order_by(Metric.id.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )

def get_metric_definitions(db: Session):
    return db.query(MetricDefinition).order_by(MetricDefinition.id.asc()).all()

def _metric_definition_by_name(db: Session, name: str):
    normalized = name.strip().casefold()
    return next(
        (item for item in get_metric_definitions(db) if item.name.strip().casefold() == normalized),
        None,
    )

def _definition_values(values: dict):
    return {
        "name": str(values["name"]).strip(),
        "description": values.get("description"),
        "topic": values.get("topic") or "未分类",
        "aliases": values.get("aliases"),
        "unit": values.get("unit"),
    }

def _binding_values(values: dict):
    keys = {
        "data_source_id", "sql_expr", "base_table", "time_field",
        "dimension_field", "dashboard_enabled",
    }
    return {key: value for key, value in values.items() if key in keys}

def create_metric(db: Session, metric: schemas.MetricCreate):
    values = metric.model_dump()
    definition = _metric_definition_by_name(db, values["name"])
    if definition is None:
        definition = MetricDefinition(**_definition_values(values))
        db.add(definition)
        db.flush()
    duplicate = (
        db.query(Metric)
        .filter(
            Metric.definition_id == definition.id,
            Metric.data_source_id == values["data_source_id"],
        )
        .first()
    )
    if duplicate:
        raise ValueError(f"指标“{definition.name}”已绑定该数据源，请直接编辑现有绑定")
    db_metric = Metric(definition_id=definition.id, **_binding_values(values))
    db.add(db_metric)
    db.commit()
    db.refresh(db_metric)
    return db_metric

def update_metric(db: Session, metric_id: int, metric: schemas.MetricUpdate):
    db_metric = get_metric(db, metric_id)
    if db_metric:
        values = metric.model_dump()
        requested_definition = _metric_definition_by_name(db, values["name"])
        target_definition = requested_definition or db_metric.definition
        duplicate = (
            db.query(Metric)
            .filter(
                Metric.definition_id == target_definition.id,
                Metric.data_source_id == values["data_source_id"],
                Metric.id != metric_id,
            )
            .first()
        )
        if duplicate:
            raise ValueError(f"指标“{target_definition.name}”已绑定该数据源")
        if requested_definition and requested_definition.id != db_metric.definition_id:
            db_metric.definition = requested_definition
            db_metric.definition_id = requested_definition.id
        definition = db_metric.definition
        for key, value in _definition_values(values).items():
            setattr(definition, key, value)
        for key, value in _binding_values(values).items():
            setattr(db_metric, key, value)
        db.commit()
        db.refresh(db_metric)
    return db_metric


def update_metric_dashboard_enabled(db: Session, metric_id: int, dashboard_enabled: bool):
    db_metric = get_metric(db, metric_id)
    if db_metric:
        db_metric.dashboard_enabled = dashboard_enabled
        db.commit()
        db.refresh(db_metric)
    return db_metric

def delete_metric(db: Session, metric_id: int):
    db_metric = get_metric(db, metric_id)
    if db_metric:
        definition = db_metric.definition
        db.delete(db_metric)
        db.flush()
        remaining = db.query(Metric).filter(Metric.definition_id == definition.id).first()
        if remaining is None:
            db.delete(definition)
        db.commit()
        return True
    return False

# ---------- User ----------
def get_user(db: Session, user_id: int):
    return db.query(User).filter(User.id == user_id).first()

def get_users(db: Session, skip: int = 0, limit: int = 100):
    return db.query(User).offset(skip).limit(limit).all()

def create_user(db: Session, user: schemas.UserCreate):
    values = user.model_dump()
    values["password"] = hash_password(values["password"])
    db_user = User(**values)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def update_user(db: Session, user_id: int, user: schemas.UserUpdate):
    db_user = get_user(db, user_id)
    if db_user:
        values = user.model_dump()
        if not values.get("password"):
            values.pop("password", None)
        elif "password" in values:
            values["password"] = hash_password(values["password"])
        for key, value in values.items():
            setattr(db_user, key, value)
        db.commit()
        db.refresh(db_user)
    return db_user

def delete_user(db: Session, user_id: int):
    db_user = get_user(db, user_id)
    if db_user:
        conversation_ids = [
            row[0]
            for row in db.query(Conversation.id).filter(Conversation.user_id == user_id).all()
        ]
        if conversation_ids:
            db.query(ConversationMessage).filter(
                ConversationMessage.conversation_id.in_(conversation_ids)
            ).delete(synchronize_session=False)
            db.query(Conversation).filter(Conversation.id.in_(conversation_ids)).delete(
                synchronize_session=False
            )
        report_ids = [
            row[0]
            for row in db.query(ReportDraft.id).filter(ReportDraft.user_id == user_id).all()
        ]
        if report_ids:
            db.query(ReportVersion).filter(ReportVersion.report_id.in_(report_ids)).delete(
                synchronize_session=False
            )
            db.query(ReportDraft).filter(ReportDraft.id.in_(report_ids)).delete(
                synchronize_session=False
            )
        db.query(UserLLMConfig).filter(UserLLMConfig.user_id == user_id).delete()
        db.query(DataSourceImportJob).filter(DataSourceImportJob.user_id == user_id).delete()
        db.delete(db_user)
        db.commit()
        return True
    return False

# ---------- User LLM configuration ----------
def get_user_llm_config(db: Session, user_id: int):
    return db.query(UserLLMConfig).filter(UserLLMConfig.user_id == user_id).first()

def upsert_user_llm_config(db: Session, user_id: int, api_key: str):
    encrypted_key = encrypt_secret(api_key)
    config = get_user_llm_config(db, user_id)
    if config:
        config.api_key = encrypted_key
        config.provider = "deepseek"
    else:
        config = UserLLMConfig(user_id=user_id, provider="deepseek", api_key=encrypted_key)
        db.add(config)
    db.commit()
    db.refresh(config)
    return config

# ---------- Knowledge document ----------
def get_knowledge_document(db: Session, document_id: int):
    return db.query(KnowledgeDocument).filter(KnowledgeDocument.id == document_id).first()

def get_knowledge_documents(db: Session, skip: int = 0, limit: int = 200):
    return (
        db.query(KnowledgeDocument)
        .order_by(KnowledgeDocument.category.asc(), KnowledgeDocument.id.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )

def create_knowledge_document(db: Session, document: schemas.KnowledgeDocumentCreate):
    record = KnowledgeDocument(**document.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record

def create_knowledge_documents(db: Session, documents: list[schemas.KnowledgeDocumentCreate]):
    records = [KnowledgeDocument(**document.model_dump()) for document in documents]
    db.add_all(records)
    db.commit()
    for record in records:
        db.refresh(record)
    return records

def update_knowledge_document(db: Session, document_id: int, document: schemas.KnowledgeDocumentUpdate):
    record = get_knowledge_document(db, document_id)
    if record:
        for key, value in document.model_dump().items():
            setattr(record, key, value)
        db.commit()
        db.refresh(record)
    return record

def delete_knowledge_document(db: Session, document_id: int):
    record = get_knowledge_document(db, document_id)
    if record:
        db.delete(record)
        db.commit()
        return True
    return False
