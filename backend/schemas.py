from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

# Enterprise
class EnterpriseBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)

class EnterpriseCreate(EnterpriseBase):
    pass

class EnterpriseUpdate(EnterpriseBase):
    pass

class EnterpriseResponse(EnterpriseBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True

# Department
class DepartmentBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    enterprise_id: int = Field(gt=0)
    parent_id: Optional[int] = Field(default=None, gt=0)

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentUpdate(DepartmentBase):
    pass

class DepartmentResponse(DepartmentBase):
    id: int
    created_at: datetime

    class Config:
        from_attributes = True


class DepartmentTaskBase(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: Optional[str] = None
    progress: int = Field(default=0, ge=0, le=100)


class DepartmentTaskCreate(DepartmentTaskBase):
    pass


class DepartmentTaskUpdate(DepartmentTaskBase):
    pass


class DepartmentTaskResponse(DepartmentTaskBase):
    id: int
    department_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class DepartmentEmployeeBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    title: Optional[str] = Field(default=None, max_length=100)
    task_id: Optional[int] = Field(default=None, gt=0)


class DepartmentEmployeeCreate(DepartmentEmployeeBase):
    pass


class DepartmentEmployeeUpdate(DepartmentEmployeeBase):
    pass


class DepartmentEmployeeResponse(DepartmentEmployeeBase):
    id: int
    department_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class DepartmentWorkspaceResponse(BaseModel):
    department: DepartmentResponse
    employees: List[DepartmentEmployeeResponse] = Field(default_factory=list)
    tasks: List[DepartmentTaskResponse] = Field(default_factory=list)

# DataSource
class DataSourceBase(BaseModel):
    name: str
    db_type: Optional[str] = "mysql"
    host: str
    port: int
    database: str
    username: str
    password: str = ""
    enterprise_id: int = Field(gt=0)

class DataSourceCreate(DataSourceBase):
    pass

class DataSourceUpdate(BaseModel):
    """Editable metadata; managed reader credentials never return to the UI."""

    name: str
    db_type: Optional[str] = "mysql"
    host: str
    port: int
    database: str
    enterprise_id: int = Field(gt=0)

class DataSourceResponse(BaseModel):
    name: str
    db_type: Optional[str] = "mysql"
    host: str
    port: int
    database: str
    enterprise_id: int
    id: int
    is_active: bool = True
    provisioning_status: Optional[Literal["verified", "granted"]] = None
    provisioning_message: Optional[str] = None

    class Config:
        from_attributes = True


class DataSourceImportJobResponse(BaseModel):
    id: int
    user_id: int
    enterprise_id: int
    data_source_id: Optional[int] = None
    data_source_name: str
    database_name: Optional[str] = None
    file_name: str
    status: Literal["queued", "processing", "completed", "failed", "cancelled"]
    stage: Literal["uploaded", "building", "metrics", "completed", "failed", "cancelled"]
    progress: int
    message: str
    error_message: Optional[str] = None
    metrics_created: int = 0
    knowledge_documents_created: int = 0
    database_created: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# Metric
class MetricBase(BaseModel):
    name: str
    description: Optional[str] = None
    sql_expr: str
    topic: Optional[str] = None
    data_source_id: int
    aliases: Optional[str] = None
    unit: Optional[str] = None
    base_table: Optional[str] = None
    time_field: Optional[str] = None
    dimension_field: Optional[str] = None
    dashboard_enabled: bool = True

class MetricCreate(MetricBase):
    pass

class MetricUpdate(MetricBase):
    pass


class MetricDashboardUpdate(BaseModel):
    dashboard_enabled: bool

class MetricResponse(MetricBase):
    id: int
    definition_id: Optional[int] = None

    class Config:
        from_attributes = True


class MetricCatalogBinding(MetricResponse):
    data_source_name: str
    enterprise_id: int
    enterprise_name: str


class MetricCatalogItem(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    topic: str = "未分类"
    aliases: Optional[str] = None
    unit: Optional[str] = None
    bindings: List[MetricCatalogBinding] = Field(default_factory=list)

# Knowledge document
KnowledgeCategory = Literal["table", "field", "rule", "question"]

class KnowledgeDocumentBase(BaseModel):
    category: KnowledgeCategory
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    data_source_id: Optional[int] = None

class KnowledgeDocumentCreate(KnowledgeDocumentBase):
    pass

class KnowledgeDocumentUpdate(KnowledgeDocumentBase):
    pass

class KnowledgeDocumentResponse(KnowledgeDocumentBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

# User
class UserBase(BaseModel):
    username: str
    role: Optional[str] = "analyst"

class UserCreate(UserBase):
    password: str

class UserUpdate(UserBase):
    password: Optional[str] = None

class UserResponse(UserBase):
    id: int

    class Config:
        from_attributes = True

# User-level LLM configuration
class LLMConfigUpdate(BaseModel):
    user_id: int = Field(gt=0)
    api_key: str = Field(min_length=8, max_length=500)

class LLMConfigStatus(BaseModel):
    user_id: int
    provider: Literal["deepseek"] = "deepseek"
    configured: bool
    updated_at: Optional[datetime] = None


# Smart-query conversation history
class ConversationCreate(BaseModel):
    user_id: int = Field(gt=0)
    title: str = Field(default="新建问数会话", min_length=1, max_length=200)
    data_source_id: Optional[int] = Field(default=None, gt=0)


class ConversationUpdate(BaseModel):
    user_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)


class ConversationMessageCreate(BaseModel):
    user_id: int = Field(gt=0)
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1)
    payload: Dict[str, Any] = Field(default_factory=dict)


class ConversationMessageResponse(BaseModel):
    id: int
    conversation_id: int
    role: Literal["user", "assistant"]
    content: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ConversationSummary(BaseModel):
    id: int
    user_id: int
    title: str
    data_source_id: Optional[int] = None
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class ConversationDetail(ConversationSummary):
    messages: List[ConversationMessageResponse] = Field(default_factory=list)


# Editable management reports and immutable versions
ReportPeriod = Literal["year", "six_months", "quarter", "all"]


class ReportDraftCreate(BaseModel):
    user_id: int = Field(gt=0)
    title: str = Field(min_length=1, max_length=200)
    data_source_id: Optional[int] = Field(default=None, gt=0)
    period: ReportPeriod = "year"
    content: Dict[str, Any] = Field(default_factory=dict)


class ReportDraftUpdate(ReportDraftCreate):
    pass


class ReportVersionResponse(BaseModel):
    id: int
    version_number: int
    content: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ReportDraftSummary(BaseModel):
    id: int
    user_id: int
    title: str
    data_source_id: Optional[int] = None
    period: ReportPeriod
    version_count: int = 0
    created_at: datetime
    updated_at: datetime


class ReportDraftDetail(ReportDraftSummary):
    content: Dict[str, Any] = Field(default_factory=dict)
    versions: List[ReportVersionResponse] = Field(default_factory=list)
