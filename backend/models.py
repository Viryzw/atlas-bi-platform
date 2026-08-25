from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class Enterprise(Base):
    __tablename__ = "enterprises"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=False, index=True)
    parent_id = Column(Integer, ForeignKey("departments.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DepartmentTask(Base):
    """A task owned directly by one department, never by its descendants."""

    __tablename__ = "department_tasks"

    id = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=True)
    progress = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class DepartmentEmployee(Base):
    """An employee belongs to one department and can own at most one task."""

    __tablename__ = "department_employees"

    id = Column(Integer, primary_key=True, index=True)
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=False, index=True)
    task_id = Column(Integer, ForeignKey("department_tasks.id"), nullable=True, index=True)
    name = Column(String(100), nullable=False)
    title = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    db_type = Column(String(20), default="mysql")
    host = Column(String(100))
    port = Column(Integer)
    database = Column(String(64))
    username = Column(String(50))
    password = Column(Text)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="1", index=True)


class DataSourceImportJob(Base):
    """Persistent progress for asynchronous SQL-file onboarding."""

    __tablename__ = "data_source_import_jobs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    enterprise_id = Column(Integer, ForeignKey("enterprises.id"), nullable=False, index=True)
    data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=True, index=True)
    data_source_name = Column(String(100), nullable=False)
    database_name = Column(String(64), nullable=True)
    file_name = Column(String(255), nullable=False)
    status = Column(String(20), nullable=False, default="queued", index=True)
    stage = Column(String(30), nullable=False, default="uploaded")
    progress = Column(Integer, nullable=False, default=10)
    message = Column(String(500), nullable=False, default="SQL 文件上传完成")
    error_message = Column(Text, nullable=True)
    metrics_created = Column(Integer, nullable=False, default=0)
    knowledge_documents_created = Column(Integer, nullable=False, default=0)
    database_created = Column(Boolean, nullable=False, default=False, server_default="0")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )

class MetricDefinition(Base):
    """One reusable business concept shared by data-source bindings."""

    __tablename__ = "metric_definitions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    description = Column(Text)
    topic = Column(String(50), nullable=False, default="未分类")
    aliases = Column(String(255), nullable=True)
    unit = Column(String(20), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    bindings = relationship("Metric", back_populates="definition", cascade="all, delete-orphan")


class Metric(Base):
    """Physical SQL implementation of a logical metric for one data source."""

    __tablename__ = "metric_bindings"
    __table_args__ = (
        UniqueConstraint("definition_id", "data_source_id", name="uq_metric_binding_definition_source"),
    )

    id = Column(Integer, primary_key=True, index=True)
    definition_id = Column(Integer, ForeignKey("metric_definitions.id"), nullable=False, index=True)
    data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=False, index=True)
    sql_expr = Column(Text, nullable=False)
    base_table = Column(String(100), nullable=True)
    time_field = Column(String(100), nullable=True)
    dimension_field = Column(String(100), nullable=True)
    dashboard_enabled = Column(Boolean, nullable=False, default=True)
    definition = relationship("MetricDefinition", back_populates="bindings", lazy="joined")

    @property
    def name(self):
        return self.definition.name

    @property
    def description(self):
        return self.definition.description

    @property
    def topic(self):
        return self.definition.topic

    @property
    def aliases(self):
        return self.definition.aliases

    @property
    def unit(self):
        return self.definition.unit

class KnowledgeDocument(Base):
    """Business dictionary/rule content used to enrich the RAG index."""

    __tablename__ = "knowledge_documents"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(20), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    content = Column(Text, nullable=False)
    data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password = Column(String(100), nullable=False)  # PBKDF2 哈希；兼容旧明文并在登录后升级
    role = Column(String(20), default="analyst")

class UserLLMConfig(Base):
    """Per-user DeepSeek configuration; the API key is never serialized."""

    __tablename__ = "user_llm_configs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    provider = Column(String(20), nullable=False, default="deepseek")
    api_key = Column(Text, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class Conversation(Base):
    """A user-owned smart-query conversation."""

    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )


class ConversationMessage(Base):
    """Persisted user/assistant message plus structured BI artifacts."""

    __tablename__ = "conversation_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        Integer,
        ForeignKey("conversations.id"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    payload_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ReportDraft(Base):
    """A user-owned editable management report."""

    __tablename__ = "report_drafts"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(200), nullable=False)
    data_source_id = Column(Integer, ForeignKey("data_sources.id"), nullable=True)
    period = Column(String(20), nullable=False, default="year")
    content_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        index=True,
    )


class ReportVersion(Base):
    """Immutable content snapshot created whenever a report is saved."""

    __tablename__ = "report_versions"

    id = Column(Integer, primary_key=True, index=True)
    report_id = Column(Integer, ForeignKey("report_drafts.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    content_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuditLog(Base):
    """Immutable metadata for state-changing API operations."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    method = Column(String(10), nullable=False)
    path = Column(String(255), nullable=False, index=True)
    status_code = Column(Integer, nullable=False)
    client_ip = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
