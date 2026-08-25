"""Business data access used by SQL Agent and Analysis Agent.

This module intentionally does not ask an LLM to generate SQL. SQL planning
lives in sql_agent.py; this layer only describes and queries the selected data
source. The legacy text_to_sql function remains as a compatibility endpoint.
"""

from datetime import date, datetime
from decimal import Decimal
import re
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, URL
from sqlalchemy.exc import SQLAlchemyError

from database import SessionLocal
from models import DataSource
from secret_store import decrypt_secret


READ_ONLY_START = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
FORBIDDEN_SQL = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|REPLACE|MERGE|"
    r"GRANT|REVOKE|CALL|LOAD\s+DATA|INTO\s+OUTFILE|INTO\s+DUMPFILE)\b",
    re.IGNORECASE,
)


def get_data_source(data_source_id: Optional[int] = None) -> Optional[DataSource]:
    """Return an explicitly selected source, or the first configured source."""

    db = SessionLocal()
    try:
        query = db.query(DataSource).filter(DataSource.is_active.is_(True))
        if data_source_id is not None:
            return query.filter(DataSource.id == int(data_source_id)).first()
        return query.order_by(DataSource.id.asc()).first()
    finally:
        db.close()


def get_first_data_source() -> Optional[DataSource]:
    """Compatibility helper for callers that do not choose a source."""

    return get_data_source()


def build_data_source_url(data_source: DataSource) -> URL:
    """Build a URL without manually interpolating credentials."""

    driver = "mysql+pymysql" if data_source.db_type == "mysql" else data_source.db_type
    return URL.create(
        drivername=driver,
        username=data_source.username,
        password=decrypt_secret(data_source.password or ""),
        host=data_source.host,
        port=data_source.port,
        database=data_source.database,
        query={"charset": "utf8mb4"} if data_source.db_type == "mysql" else {},
    )


def get_data_source_engine(data_source_id: Optional[int] = None) -> Engine:
    data_source = get_data_source(data_source_id)
    if not data_source:
        if data_source_id is not None:
            raise RuntimeError(f"数据源 ID {data_source_id} 不存在或已被删除")
        raise RuntimeError("未配置任何数据源，请先在数据源管理中添加业务数据库")
    return create_engine(build_data_source_url(data_source), pool_pre_ping=True)


def get_table_info(data_source_id: Optional[int] = None) -> str:
    """Return a compact schema description for SQL Agent grounding."""

    catalog = get_schema_catalog(data_source_id)
    blocks = []
    for table in catalog:
        column_text = ", ".join(
            f"{column['name']} {column['type']}"
            for column in table["columns"]
        )
        blocks.append(f"TABLE {table['table_name']} ({column_text})")
    if not blocks:
        raise RuntimeError("业务数据库中没有可查询的数据表")
    return "\n".join(blocks)


def get_schema_catalog(data_source_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """Return the selected data source's tables and columns as structured data."""

    data_source = get_data_source(data_source_id)
    if not data_source:
        if data_source_id is not None:
            raise RuntimeError(f"数据源 ID {data_source_id} 不存在或已被删除")
        raise RuntimeError("未配置任何数据源，请先在数据源管理中添加业务数据库")
    engine = create_engine(build_data_source_url(data_source), pool_pre_ping=True)
    try:
        inspector = inspect(engine)
        tables = []
        for table_name in inspector.get_table_names():
            columns = inspector.get_columns(table_name)
            tables.append({
                "data_source_id": data_source.id,
                "data_source_name": data_source.name,
                "table_name": table_name,
                "columns": [
                    {
                        "name": column["name"],
                        "type": str(column["type"]),
                        "nullable": bool(column.get("nullable", True)),
                        "comment": column.get("comment") or "",
                    }
                    for column in columns
                ],
            })
        return tables
    finally:
        engine.dispose()


def normalize_read_only_sql(sql: str) -> str:
    """Reject multi-statement or mutating SQL before touching the database."""

    normalized = (sql or "").strip()
    if normalized.endswith(";"):
        normalized = normalized[:-1].strip()
    if not normalized:
        raise ValueError("SQL 不能为空")
    if ";" in normalized:
        raise ValueError("仅允许执行单条 SQL 查询")
    if not READ_ONLY_START.match(normalized):
        raise ValueError("智能问数仅允许 SELECT 或 WITH 查询")
    if FORBIDDEN_SQL.search(normalized):
        raise ValueError("检测到非只读 SQL，已拒绝执行")
    return normalized


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def _convert_rows(rows: List[List[Any]]) -> List[List[Any]]:
    return [[_json_safe(value) for value in row] for row in rows]


def execute_sql(
    sql: str,
    data_source_id: Optional[int] = None,
    parameters: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Execute one read-only statement and return a JSON-safe data set."""

    try:
        safe_sql = normalize_read_only_sql(sql)
        engine = get_data_source_engine(data_source_id)
    except Exception as exc:
        return {"error": str(exc)}

    try:
        with engine.connect() as connection:
            result = connection.execute(text(safe_sql), parameters or {})
            columns = list(result.keys())
            rows = _convert_rows([list(row) for row in result.fetchall()])
            return {"columns": columns, "rows": rows, "row_count": len(rows)}
    except SQLAlchemyError as exc:
        return {"error": str(exc)}
    except Exception as exc:
        return {"error": f"未知错误: {exc}"}
    finally:
        engine.dispose()


def text_to_sql(
    question: str,
    user_id: Optional[int] = None,
    data_source_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Compatibility facade for /api/query/.

    Product traffic should use /api/agent/. This facade exposes SQL Agent plus
    data execution for developers who need to inspect the generated query.
    """

    from sql_agent import create_query_plan

    plan_kwargs = {}
    if user_id is not None:
        plan_kwargs["user_id"] = user_id
    if data_source_id is not None:
        plan_kwargs["data_source_id"] = data_source_id
    planned = create_query_plan(question, **plan_kwargs)
    if planned.get("status") != "success":
        return planned

    result = (
        execute_sql(planned["sql"])
        if data_source_id is None
        else execute_sql(planned["sql"], data_source_id=data_source_id)
    )
    if "error" in result:
        return {
            "status": "error",
            "stage": "data_query",
            "plan": planned.get("plan"),
            "sql": planned["sql"],
            "message": result["error"],
        }

    return {
        "status": "success",
        "plan": planned["plan"],
        "sql": planned["sql"],
        "data": result,
    }
