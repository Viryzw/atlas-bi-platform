"""Safe SQL-file onboarding and DeepSeek-driven metric generation.

The upload endpoint intentionally accepts *new-schema initialization packages*,
not arbitrary MySQL administration scripts.  Database creation and the reader
account are owned by the backend; browser users never submit database secrets.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import re
import secrets
from threading import RLock
from types import SimpleNamespace
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.exc import SQLAlchemyError
from langchain_core.messages import HumanMessage, SystemMessage

import crud
import schemas
from data_source_provisioning import (
    DataSourceProvisioningError,
    LOCAL_HOSTS,
    _admin_engine_for,
    _quoted_mysql_identifier,
    _verify_connection,
    drop_data_source_database,
)
from database import SessionLocal, engine as platform_engine
from knowledge_base import build_knowledge_base
from llm_config import LLMConfigurationError, get_llm
from query_engine import build_data_source_url, get_schema_catalog


MAX_SQL_UPLOAD_BYTES = int(os.getenv("DATA_SOURCE_SQL_MAX_BYTES", str(5 * 1024 * 1024)))
DATABASE_NAME_PATTERN = re.compile(
    r"\bCREATE\s+DATABASE\s+(?:IF\s+NOT\s+EXISTS\s+)?`?([A-Za-z][A-Za-z0-9_]{1,63})`?",
    re.IGNORECASE,
)
MYSQL_VERSION_COMMENT_PATTERN = re.compile(r"/\*!\d{5,6}\s*(.*?)\*/", re.IGNORECASE | re.DOTALL)
SAFE_DATABASE_NAME_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{1,63}$")
PROTECTED_DATABASES = {
    "mysql",
    "information_schema",
    "performance_schema",
    "sys",
    "bi_platform",
}

IGNORED_STATEMENT_PREFIXES = (
    "CREATE DATABASE",
    "USE ",
    "DROP TABLE",
    "DROP VIEW",
    "CREATE USER",
    "ALTER USER",
    "GRANT ",
    "REVOKE ",
    "FLUSH ",
    "SELECT ",
    "WITH ",
    "SHOW ",
)
ALLOWED_STATEMENT_PREFIXES = (
    "CREATE TABLE",
    "CREATE VIEW",
    "CREATE OR REPLACE VIEW",
    "CREATE PROCEDURE",
    "INSERT INTO",
    "CALL ",
    "DROP PROCEDURE",
)
DANGEROUS_SQL = re.compile(
    r"\b(DROP\s+DATABASE|TRUNCATE|UPDATE|DELETE|REPLACE|CREATE\s+USER|"
    r"ALTER\s+USER|GRANT|REVOKE|LOAD\s+DATA|INTO\s+OUTFILE|INTO\s+DUMPFILE|"
    r"SET\s+GLOBAL|INSTALL\s+PLUGIN|UNINSTALL\s+PLUGIN|SHUTDOWN)\b",
    re.IGNORECASE,
)
PROCEDURE_NAME_PATTERN = re.compile(
    r"^CREATE\s+PROCEDURE\s+`?([A-Za-z][A-Za-z0-9_]*)`?",
    re.IGNORECASE,
)
CALL_NAME_PATTERN = re.compile(r"^CALL\s+`?([A-Za-z][A-Za-z0-9_]*)`?\s*\(", re.IGNORECASE)


METRIC_GENERATION_SYSTEM_PROMPT = """
你是企业级智能 BI 平台的指标建模专家。你的输入只有一个已创建数据源的真实 MySQL 表结构，
你的任务是生成可以直接保存到指标知识库的业务指标定义。你必须以真实表名、字段名、字段类型和
字段注释为唯一事实来源，禁止臆造字段、状态值、表之间的关系或业务口径。

严格规则：
1. 仅返回一个 JSON 对象，不要 Markdown、解释或代码围栏。
2. JSON 格式必须为 {"metrics": [...]}，生成 4 至 12 个有明确经营价值且不重复的指标。
3. 每个指标必须包含：name、description、topic、aliases、unit、sql_expr、base_table、
   time_field、dimension_field、dashboard_enabled。
4. sql_expr 只能是针对 base_table 单表计算的 MySQL 聚合表达式，例如 SUM(...)、COUNT(...)、
   AVG(...) 或带 NULLIF 的比率；禁止出现 SELECT、FROM、JOIN、分号、注释和数据库名。
5. base_table、time_field、dimension_field 必须逐字来自输入表结构；没有合适字段时填 null。
6. 如果字段注释或枚举显示状态含义，应把有效业务状态写入 CASE WHEN 内，不能把它假设成外层 WHERE。
7. 百分比表达式必须乘以 100，unit 填 "%"；金额统一优先填 "元"，数量使用合适的“单/个/家”。
8. 最多 4 个 dashboard_enabled=true，优先选择销售/收入、订单量、客户数、完成率等核心指标；
   其余指标必须为 false。无法从结构可靠推导的指标不要生成。
9. name 使用简洁、跨企业可复用的中文逻辑指标名；同一含义不要因字段名不同而改名。
10. description 必须说明统计范围、状态口径和分母；aliases 用英文逗号分隔，没有则填空字符串。
11. 禁止输出个人敏感信息类指标，禁止生成明细查询，禁止使用当前日期等不稳定常量。
""".strip()


KNOWLEDGE_GENERATION_SYSTEM_PROMPT = """
你是企业级智能 BI 平台的数据字典和分析规则建模专家。输入包含当前数据源的真实
MySQL 表结构和已通过校验的指标口径。你的任务是生成将与当前数据源绑定的数据字典、
分析规则和常见分析问题，供 RAG 和 Text-to-SQL 使用。真实表名、字段名、类型、注释和已校验
指标是唯一事实来源，禁止臆造字段、枚举值、外键关系、业务状态或计算口径。

严格规则：
1. 仅返回一个 JSON 对象，不要 Markdown、解释或代码围栏。
2. JSON 格式必须为 {"documents": [...]}，生成 8 至 24 条不重复知识。
3. 每条必须包含 category、title、content、related_tables。category 只能是
   "table"、"field"、"rule"、"question"之一；related_tables 必须是真实表名数组。
4. 必须同时包含 table、field、rule 三类，并至少生成 2 条 rule；应生成有价值的
   question，帮助模型理解常见问数意图。
5. table 内容说明表粒度、主键、时间字段和适用分析；表粒度无法确认时必须明确写
   “需业务确认”，不得推测。
6. field 内容必须写出“表名.字段名”、类型、可空性和注释含义；可将同表中高度相关
   的字段合并为一条，但不得遗漏影响指标口径的状态、金额、时间和维度字段。
7. rule 内容必须是可执行的分析约束，包括时间字段选择、状态口径、空值处理、去重粒度、
   维度分组和指标表达式保持规则。如果结构不足以确认 JOIN，必须禁止自动 JOIN。
8. question 内容应写明用户问法、建议指标、时间字段、分组维度和适用表；不得给出
   依赖不存在字段的 SQL。
9. 标题使用简洁中文，content 使用可检索的完整句子，并保留真实英文表名和字段名。
10. 不得输出密码、连接串、个人敏感信息、DDL/DML 操作建议或任何将修改数据的指令。
""".strip()


class DataSourceImportError(RuntimeError):
    """An actionable SQL upload/import error safe to return to an admin."""


class DataSourceImportCancelled(DataSourceImportError):
    """Raised cooperatively when the user or a backend restart cancels a job."""


_active_job_ids = set()
_active_job_lock = RLock()


@dataclass(frozen=True)
class PreparedSQLImport:
    database_name: str
    statements: Tuple[str, ...]


@dataclass(frozen=True)
class ImportedDatabase:
    database_name: str
    host: str
    port: int
    username: str
    password: str


def parse_data_source_import_filename(file_name: str) -> Tuple[str, str]:
    """Return ``(enterprise_name, data_source_name)`` from 企业名-数据源名.sql."""

    safe_name = re.split(r"[/\\\\]", str(file_name or ""))[-1].strip()
    if not safe_name.lower().endswith(".sql"):
        raise DataSourceImportError("仅支持上传 .sql 文件")
    stem = safe_name[:-4].strip()
    separator = stem.find("-")
    if separator <= 0 or separator >= len(stem) - 1:
        raise DataSourceImportError(
            "SQL 文件名必须为“企业名-数据源名.sql”，并使用英文半角减号 - 分隔"
        )
    enterprise_name = stem[:separator].strip()
    data_source_name = stem[separator + 1 :].strip()
    if not enterprise_name or not data_source_name:
        raise DataSourceImportError("SQL 文件名中的企业名和数据源名均不能为空")
    if len(enterprise_name) > 100 or len(data_source_name) > 100:
        raise DataSourceImportError("企业名和数据源名均不能超过 100 个字符")
    return enterprise_name, data_source_name


def decode_sql_upload(content: bytes, file_name: str) -> str:
    if not (file_name or "").lower().endswith(".sql"):
        raise DataSourceImportError("仅支持上传 .sql 文件")
    if not content:
        raise DataSourceImportError("SQL 文件为空")
    if len(content) > MAX_SQL_UPLOAD_BYTES:
        raise DataSourceImportError(
            f"SQL 文件不能超过 {MAX_SQL_UPLOAD_BYTES // (1024 * 1024)} MB"
        )
    try:
        value = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise DataSourceImportError("SQL 文件必须使用 UTF-8 编码") from exc
    if "\x00" in value:
        raise DataSourceImportError("SQL 文件包含无效字符")
    return value


def _strip_leading_comments(statement: str) -> str:
    value = statement.strip()
    while value:
        if value.startswith("--") or value.startswith("#"):
            _, separator, value = value.partition("\n")
            if not separator:
                return ""
            value = value.lstrip()
            continue
        if value.startswith("/*"):
            end = value.find("*/", 2)
            if end < 0:
                return ""
            value = value[end + 2 :].lstrip()
            continue
        break
    return value.strip()


def split_mysql_script(script: str) -> List[str]:
    """Split regular MySQL and ``DELIMITER`` procedure blocks safely enough for execution."""

    delimiter = ";"
    buffer: List[str] = []
    statements: List[str] = []
    for line in script.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.upper().startswith("DELIMITER "):
            if _strip_leading_comments("".join(buffer)):
                raise DataSourceImportError("DELIMITER 指令必须位于独立行")
            buffer = []
            delimiter = stripped.split(None, 1)[1].strip()
            if not delimiter or len(delimiter) > 8:
                raise DataSourceImportError("SQL 文件中的 DELIMITER 无效")
            continue
        buffer.append(line)
        if stripped.endswith(delimiter):
            joined = "".join(buffer).rstrip()
            joined = joined[: -len(delimiter)].strip()
            if _strip_leading_comments(joined):
                statements.append(joined)
            buffer = []
    tail = "".join(buffer).strip()
    if _strip_leading_comments(tail):
        raise DataSourceImportError("SQL 文件末尾存在未完成的语句或缺少分隔符")
    return statements


def _statement_prefix(statement: str) -> str:
    return re.sub(r"\s+", " ", _strip_leading_comments(statement)).strip().upper()


def _expand_mysql_version_comments(statement: str) -> str:
    """Expose SQLyog/mysqldump executable comments for validation.

    MySQL treats ``/*!32312 IF NOT EXISTS*/`` as executable SQL, while a
    regular SQL parser sees a comment. Validation must understand the same
    effective statement without executing the version directive itself.
    """

    # Add boundaries because SQLyog commonly emits ``... EXISTS*/`name```.
    return MYSQL_VERSION_COMMENT_PATTERN.sub(lambda match: f" {match.group(1).strip()} ", statement)


def _dangerous_sql_match(statement: str):
    """Return a real dangerous operation, ignoring safe DDL clauses/literals."""

    candidate = _expand_mysql_version_comments(statement)
    # Comments and quoted values/identifiers cannot introduce a SQL operation.
    candidate = re.sub(r"/\*(?!\!).*?\*/", " ", candidate, flags=re.DOTALL)
    candidate = re.sub(r"(?:--|#)[^\r\n]*", " ", candidate)
    candidate = re.sub(r"'(?:''|\\.|[^'])*'", "''", candidate, flags=re.DOTALL)
    candidate = re.sub(r'"(?:""|\\.|[^"])*"', '""', candidate, flags=re.DOTALL)
    candidate = re.sub(r"`(?:``|[^`])*`", "``", candidate, flags=re.DOTALL)
    # UPDATE and DELETE are valid tokens inside these CREATE TABLE clauses.
    candidate = re.sub(
        r"\bON\s+UPDATE\s+CURRENT_TIMESTAMP(?:\s*\(\s*\))?",
        " ",
        candidate,
        flags=re.IGNORECASE,
    )
    candidate = re.sub(
        r"\bON\s+DELETE\s+(?:CASCADE|RESTRICT|SET\s+NULL|NO\s+ACTION)",
        " ",
        candidate,
        flags=re.IGNORECASE,
    )
    return DANGEROUS_SQL.search(candidate)


def prepare_sql_import(script: str) -> PreparedSQLImport:
    parsed = split_mysql_script(script)
    database_names: List[str] = []
    for statement in parsed:
        effective = _expand_mysql_version_comments(_strip_leading_comments(statement))
        if re.match(r"^\s*CREATE\s+DATABASE\b", effective, re.IGNORECASE):
            database_names.extend(match.group(1) for match in DATABASE_NAME_PATTERN.finditer(effective))
    if not database_names:
        raise DataSourceImportError(
            "SQL 文件中未找到可识别的 CREATE DATABASE 目标库；请确认建库语句包含合法英文数据库名"
        )
    if len(database_names) != 1:
        raise DataSourceImportError(
            f"SQL 文件包含 {len(database_names)} 个 CREATE DATABASE 目标库，只允许创建一个数据库"
        )
    database_name = database_names[0]
    if not SAFE_DATABASE_NAME_PATTERN.fullmatch(database_name):
        raise DataSourceImportError("数据库名只能使用英文字母、数字和下划线，且必须以字母开头")
    protected = set(PROTECTED_DATABASES)
    protected.add((platform_engine.url.database or "").casefold())
    if database_name.casefold() in protected:
        raise DataSourceImportError(f"数据库 {database_name} 是系统保留库，禁止导入")

    allowed: List[str] = []
    declared_procedures = {
        match.group(1).casefold()
        for statement in parsed
        if (match := PROCEDURE_NAME_PATTERN.match(_strip_leading_comments(statement)))
    }
    for statement in parsed:
        clean = _strip_leading_comments(statement)
        prefix = _statement_prefix(statement)
        if not prefix:
            continue
        if prefix.startswith(IGNORED_STATEMENT_PREFIXES):
            continue
        if not prefix.startswith(ALLOWED_STATEMENT_PREFIXES):
            raise DataSourceImportError(f"SQL 文件包含不支持的语句：{prefix[:80]}")
        if _dangerous_sql_match(clean):
            raise DataSourceImportError(f"SQL 文件包含危险操作，已拒绝执行：{prefix[:80]}")
        for protected_name in protected:
            if protected_name and re.search(
                rf"`?{re.escape(protected_name)}`?\s*\.", clean, re.IGNORECASE
            ):
                raise DataSourceImportError("初始化语句不得访问 BI 平台或 MySQL 系统数据库")
        if prefix.startswith("CALL "):
            match = CALL_NAME_PATTERN.match(clean)
            if not match or match.group(1).casefold() not in declared_procedures:
                raise DataSourceImportError("只允许调用同一上传文件内声明的存储过程")
        allowed.append(clean)
    if not any(_statement_prefix(statement).startswith("CREATE TABLE") for statement in allowed):
        raise DataSourceImportError("SQL 文件至少需要创建一张业务表")
    return PreparedSQLImport(database_name=database_name, statements=tuple(allowed))


def _import_connection_settings(database_name: str) -> Tuple[SimpleNamespace, Engine, bool]:
    configured_admin_url = os.getenv("DATA_SOURCE_ADMIN_URL", "").strip()
    admin_url = make_url(configured_admin_url) if configured_admin_url else platform_engine.url
    host = os.getenv("DATA_SOURCE_IMPORT_HOST", "").strip() or admin_url.host or "127.0.0.1"
    port = int(os.getenv("DATA_SOURCE_IMPORT_PORT", "") or admin_url.port or 3306)
    configured_username = os.getenv("DATA_SOURCE_READER_USERNAME", "").strip()
    configured_password = os.getenv("DATA_SOURCE_READER_PASSWORD", "")
    if configured_username:
        username = configured_username
        password = configured_password
        if not password:
            raise DataSourceImportError(
                "配置 DATA_SOURCE_READER_USERNAME 时必须同时配置非空的 DATA_SOURCE_READER_PASSWORD"
            )
        generated_reader = False
    else:
        digest = hashlib.sha256(database_name.casefold().encode("utf-8")).hexdigest()[:18]
        username = f"atlasbi_{digest}"
        password = secrets.token_urlsafe(32)
        generated_reader = True
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{1,31}", username):
        raise DataSourceImportError("后端 DATA_SOURCE_READER_USERNAME 配置无效")
    source = SimpleNamespace(
        db_type="mysql",
        host=host,
        port=port,
        database=database_name,
        username=username,
        password=password,
        generated_reader=generated_reader,
    )
    try:
        admin_engine, should_dispose = _admin_engine_for(source)
    except DataSourceProvisioningError as exc:
        raise DataSourceImportError(str(exc)) from exc
    return source, admin_engine, should_dispose


def _reader_account_host(source) -> str:
    if (source.host or "").casefold() in LOCAL_HOSTS:
        return "localhost"
    account_host = os.getenv("DATA_SOURCE_READER_HOST", "").strip()
    if not account_host:
        raise DataSourceImportError(
            "远程 MySQL 导入需要在后端配置 DATA_SOURCE_READER_HOST，禁止自动创建 '%' 通配账号"
        )
    return account_host


def _database_exists(admin_engine: Engine, database_name: str) -> bool:
    with admin_engine.connect() as connection:
        return connection.exec_driver_sql(
            "SELECT 1 FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = %s",
            (database_name,),
        ).first() is not None


def _drop_new_database(admin_engine: Engine, database_name: str) -> None:
    database = _quoted_mysql_identifier(database_name)
    with admin_engine.begin() as connection:
        connection.exec_driver_sql(f"DROP DATABASE IF EXISTS {database}")


def _drop_generated_reader(admin_engine: Engine, source, account_host: str) -> None:
    if not getattr(source, "generated_reader", False):
        return
    with admin_engine.begin() as connection:
        connection.exec_driver_sql(
            "DROP USER IF EXISTS %s@%s",
            (source.username, account_host),
        )


def _raise_if_cancelled(cancel_check: Optional[Callable[[], bool]]) -> None:
    if cancel_check and cancel_check():
        raise DataSourceImportCancelled("用户已取消数据源接入")


def _execute_uploaded_statement(connection, statement: str) -> None:
    """Execute uploaded SQL without letting DBAPI treat MySQL '%' literals as placeholders."""

    paramstyle = getattr(getattr(connection, "dialect", None), "paramstyle", "")
    if not paramstyle:
        paramstyle = getattr(getattr(getattr(connection, "engine", None), "dialect", None), "paramstyle", "")
    driver_statement = (
        statement.replace("%", "%%")
        if paramstyle in {"format", "pyformat"}
        else statement
    )
    connection.exec_driver_sql(driver_statement)


def import_new_database(
    prepared: PreparedSQLImport,
    *,
    cancel_check: Optional[Callable[[], bool]] = None,
    database_created_callback: Optional[Callable[[], None]] = None,
) -> ImportedDatabase:
    """Create and seed one brand-new schema, then provision a managed reader."""

    source, admin_engine, should_dispose = _import_connection_settings(prepared.database_name)
    database = _quoted_mysql_identifier(prepared.database_name)
    account_host = _reader_account_host(source)
    created = False
    reader_created = False
    try:
        _raise_if_cancelled(cancel_check)
        if _database_exists(admin_engine, prepared.database_name):
            raise DataSourceImportError(
                f"数据库 {prepared.database_name} 已存在。为避免覆盖业务数据，请先更换 SQL 中的数据库名，"
                "或在确认备份后通过数据源管理删除原库"
            )
        with admin_engine.begin() as connection:
            connection.exec_driver_sql(
                f"CREATE DATABASE {database} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        created = True
        if database_created_callback:
            database_created_callback()
        _raise_if_cancelled(cancel_check)
        # Never issue USE on the shared platform engine. MySQL preserves the
        # selected schema on a pooled connection, which can otherwise redirect
        # later authentication queries to the newly imported business database.
        target_engine = create_engine(
            admin_engine.url.set(database=prepared.database_name),
            pool_pre_ping=True,
            hide_parameters=True,
        )
        try:
            with target_engine.begin() as connection:
                for statement in prepared.statements:
                    _raise_if_cancelled(cancel_check)
                    _execute_uploaded_statement(connection, statement)
        finally:
            target_engine.dispose()
        _raise_if_cancelled(cancel_check)
        with admin_engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE USER IF NOT EXISTS %s@%s IDENTIFIED BY %s",
                (source.username, account_host, source.password),
            )
            reader_created = True
            if source.generated_reader:
                # This hash-derived account belongs exclusively to the target
                # schema, so a retry may safely rotate its generated password.
                connection.exec_driver_sql(
                    "ALTER USER %s@%s IDENTIFIED BY %s",
                    (source.username, account_host, source.password),
                )
            connection.exec_driver_sql(
                f"GRANT SELECT ON {database}.* TO %s@%s",
                (source.username, account_host),
            )
        _raise_if_cancelled(cancel_check)
        _verify_connection(source)
        return ImportedDatabase(
            database_name=prepared.database_name,
            host=source.host,
            port=source.port,
            username=source.username,
            password=source.password,
        )
    except DataSourceImportError:
        if created:
            try:
                _drop_new_database(admin_engine, prepared.database_name)
            except Exception:
                pass
        if reader_created:
            try:
                _drop_generated_reader(admin_engine, source, account_host)
            except Exception:
                pass
        raise
    except Exception as exc:
        if created:
            try:
                _drop_new_database(admin_engine, prepared.database_name)
            except Exception:
                pass
        if reader_created:
            try:
                _drop_generated_reader(admin_engine, source, account_host)
            except Exception:
                pass
        raise DataSourceImportError(f"数据库建设失败：{exc}") from exc
    finally:
        if should_dispose:
            admin_engine.dispose()


def drop_imported_database(database: ImportedDatabase) -> None:
    source, admin_engine, should_dispose = _import_connection_settings(database.database_name)
    account_host = _reader_account_host(source)
    try:
        _drop_new_database(admin_engine, source.database)
        _drop_generated_reader(admin_engine, source, account_host)
    finally:
        if should_dispose:
            admin_engine.dispose()


def _extract_json_object(content: str, list_key: str = "metrics") -> Dict[str, Any]:
    value = (content or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", value, re.DOTALL | re.IGNORECASE)
    if fenced:
        value = fenced.group(1)
    else:
        start, end = value.find("{"), value.rfind("}")
        if start >= 0 and end > start:
            value = value[start : end + 1]
    parsed = json.loads(value)
    if not isinstance(parsed, dict) or not isinstance(parsed.get(list_key), list):
        raise ValueError(f"模型没有返回 {list_key} JSON 数组")
    return parsed


def _schema_prompt(catalog: Sequence[Dict[str, Any]]) -> str:
    return json.dumps(
        [
            {
                "table_name": table["table_name"],
                "columns": [
                    {
                        "name": column["name"],
                        "type": column["type"],
                        "nullable": column["nullable"],
                        "comment": column.get("comment") or "",
                    }
                    for column in table["columns"]
                ],
            }
            for table in catalog
        ],
        ensure_ascii=False,
    )


def _clean_optional_identifier(value: Any, valid_values: Iterable[str]) -> Optional[str]:
    clean = str(value or "").strip()
    if not clean:
        return None
    if clean not in set(valid_values):
        raise ValueError(f"模型返回了不存在的字段：{clean}")
    return clean


def _normalise_generated_metric(
    raw: Dict[str, Any],
    catalog_by_table: Dict[str, Dict[str, Any]],
    dashboard_slots_left: int,
) -> schemas.MetricCreate:
    name = str(raw.get("name") or "").strip()
    expression = str(raw.get("sql_expr") or "").strip()
    base_table = str(raw.get("base_table") or "").strip()
    if not name or len(name) > 100:
        raise ValueError("模型返回了无效指标名")
    if base_table not in catalog_by_table:
        raise ValueError(f"模型返回了不存在的基础表：{base_table}")
    if not expression or len(expression) > 2000:
        raise ValueError(f"指标“{name}”缺少 SQL 表达式")
    if re.search(
        r"(;|--|/\*|\bSELECT\b|\bFROM\b|\bJOIN\b|\bINSERT\b|\bUPDATE\b|"
        r"\bDELETE\b|\bDROP\b|\bALTER\b|\bCREATE\b|\bGRANT\b|\bCALL\b|"
        r"\bSLEEP\s*\(|\bBENCHMARK\s*\(|\bLOAD_FILE\s*\(|\bGET_LOCK\s*\()",
        expression,
        re.IGNORECASE,
    ):
        raise ValueError(f"指标“{name}”包含不允许的 SQL")
    column_names = {column["name"] for column in catalog_by_table[base_table]["columns"]}
    time_field = _clean_optional_identifier(raw.get("time_field"), column_names)
    dimension_field = _clean_optional_identifier(raw.get("dimension_field"), column_names)
    topic = str(raw.get("topic") or "未分类").strip()[:50] or "未分类"
    unit = str(raw.get("unit") or "").strip()[:20] or None
    description = str(raw.get("description") or "").strip()[:2000] or None
    aliases = str(raw.get("aliases") or "").strip()[:255] or None
    dashboard_enabled = bool(raw.get("dashboard_enabled")) and dashboard_slots_left > 0
    return schemas.MetricCreate(
        name=name,
        description=description,
        topic=topic,
        aliases=aliases,
        unit=unit,
        sql_expr=expression,
        base_table=base_table,
        time_field=time_field,
        dimension_field=dimension_field,
        dashboard_enabled=dashboard_enabled,
        data_source_id=1,  # replaced by the caller after validation
    )


def generate_metrics_for_data_source(
    db,
    *,
    user_id: int,
    data_source_id: int,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> int:
    _raise_if_cancelled(cancel_check)
    catalog = get_schema_catalog(data_source_id)
    if not catalog:
        raise DataSourceImportError("数据库中没有可用于生成指标的业务表")
    messages = [
        SystemMessage(content=METRIC_GENERATION_SYSTEM_PROMPT),
        HumanMessage(content="【当前数据源真实表结构】\n" + _schema_prompt(catalog)),
    ]
    try:
        response = get_llm(user_id).invoke(messages)
        _raise_if_cancelled(cancel_check)
        raw_metrics = _extract_json_object(response.content)["metrics"]
    except LLMConfigurationError as exc:
        raise DataSourceImportError(f"指标生成失败：{exc}") from exc
    except Exception as exc:
        raise DataSourceImportError(f"DeepSeek 指标生成失败：{exc}") from exc

    catalog_by_table = {table["table_name"]: table for table in catalog}
    data_source = crud.get_data_source(db, data_source_id)
    if data_source is None:
        raise DataSourceImportError("指标生成时数据源记录不存在")
    reader_engine = create_engine(build_data_source_url(data_source), pool_pre_ping=True)
    candidates: List[schemas.MetricCreate] = []
    seen_names = set()
    dashboard_count = 0
    try:
        for raw in raw_metrics[:12]:
            _raise_if_cancelled(cancel_check)
            if not isinstance(raw, dict):
                continue
            try:
                candidate = _normalise_generated_metric(raw, catalog_by_table, 4 - dashboard_count)
                candidate.data_source_id = data_source_id
                normalized_name = candidate.name.casefold()
                if normalized_name in seen_names:
                    continue
                table_name = _quoted_mysql_identifier(candidate.base_table or "")
                with reader_engine.connect() as connection:
                    connection.exec_driver_sql(
                        f"SELECT {candidate.sql_expr} AS metric_value FROM {table_name} WHERE 1 = 0"
                    )
                seen_names.add(normalized_name)
                if candidate.dashboard_enabled:
                    dashboard_count += 1
                candidates.append(candidate)
            except (ValueError, SQLAlchemyError, DataSourceProvisioningError):
                continue
    finally:
        reader_engine.dispose()
    if not candidates:
        raise DataSourceImportError("DeepSeek 未生成任何可通过真实数据库校验的指标")

    created = 0
    for candidate in candidates:
        _raise_if_cancelled(cancel_check)
        try:
            crud.create_metric(db, candidate)
            created += 1
        except ValueError:
            # A shared logical definition may already exist.  Only an existing
            # binding for this brand-new source should be skipped.
            db.rollback()
    if not created:
        raise DataSourceImportError("生成的指标均已存在，未创建新的数据源指标绑定")
    return created


def _generated_metric_context(db, data_source_id: int) -> str:
    metrics = [
        metric for metric in crud.get_metrics(db, limit=10000)
        if int(metric.data_source_id) == int(data_source_id)
    ]
    return json.dumps(
        [
            {
                "name": metric.name,
                "description": metric.description or "",
                "sql_expr": metric.sql_expr or "",
                "base_table": metric.base_table,
                "time_field": metric.time_field,
                "dimension_field": metric.dimension_field,
            }
            for metric in metrics
        ],
        ensure_ascii=False,
    )


def generate_knowledge_documents_for_data_source(
    db,
    *,
    user_id: int,
    data_source_id: int,
    cancel_check: Optional[Callable[[], bool]] = None,
) -> int:
    """Generate grounded dictionary/rule documents and bind them to one source."""

    _raise_if_cancelled(cancel_check)
    catalog = get_schema_catalog(data_source_id)
    if not catalog:
        raise DataSourceImportError("数据库中没有可用于生成数据字典的业务表")
    table_names = {table["table_name"] for table in catalog}
    messages = [
        SystemMessage(content=KNOWLEDGE_GENERATION_SYSTEM_PROMPT),
        HumanMessage(content=(
            "【当前数据源真实表结构】\n"
            + _schema_prompt(catalog)
            + "\n\n【已通过真实数据库校验的指标】\n"
            + _generated_metric_context(db, data_source_id)
        )),
    ]
    try:
        response = get_llm(user_id).invoke(messages)
        _raise_if_cancelled(cancel_check)
        raw_documents = _extract_json_object(response.content, "documents")["documents"]
    except LLMConfigurationError as exc:
        raise DataSourceImportError(f"数据字典与分析规则生成失败：{exc}") from exc
    except DataSourceImportCancelled:
        raise
    except Exception as exc:
        raise DataSourceImportError(f"DeepSeek 数据字典与分析规则生成失败：{exc}") from exc

    documents: List[schemas.KnowledgeDocumentCreate] = []
    seen = set()
    category_counts = {"table": 0, "field": 0, "rule": 0, "question": 0}
    for raw in raw_documents[:24]:
        _raise_if_cancelled(cancel_check)
        if not isinstance(raw, dict):
            continue
        category = str(raw.get("category") or "").strip().casefold()
        title = str(raw.get("title") or "").strip()
        content = str(raw.get("content") or "").strip()
        related_tables = raw.get("related_tables")
        if category not in category_counts or not title or len(title) > 200:
            continue
        if not content or len(content) > 6000:
            continue
        if not isinstance(related_tables, list) or not related_tables:
            continue
        clean_tables = [str(table).strip() for table in related_tables if str(table).strip()]
        if not clean_tables or any(table not in table_names for table in clean_tables):
            continue
        # Keep real table names in every document so retrieval remains
        # inspectable even when the model uses a fully Chinese title.
        if not all(table in content for table in clean_tables):
            content = f"适用表：{', '.join(clean_tables)}。{content}"
        duplicate_key = (category, title.casefold())
        if duplicate_key in seen:
            continue
        seen.add(duplicate_key)
        category_counts[category] += 1
        documents.append(schemas.KnowledgeDocumentCreate(
            category=category,
            title=title,
            content=content,
            data_source_id=data_source_id,
        ))

    required_categories = {"table", "field", "rule"}
    missing = [category for category in required_categories if category_counts[category] == 0]
    if missing or category_counts["rule"] < 2 or len(documents) < 6:
        raise DataSourceImportError(
            "DeepSeek 返回的数据字典与分析规则覆盖不完整，未写入知识库"
        )
    _raise_if_cancelled(cancel_check)
    return len(crud.create_knowledge_documents(db, documents))


def _job_is_cancelled(db, job_id: int) -> bool:
    db.expire_all()
    job = crud.get_data_source_import_job(db, job_id)
    return job is None or job.status == "cancelled"


def _set_database_created(db, job_id: int) -> None:
    crud.update_data_source_import_job(db, job_id, database_created=True)


def _rollback_import_job(db, job_id: int) -> None:
    """Remove only resources proven to have been created by this import job."""

    db.expire_all()
    job = crud.get_data_source_import_job(db, job_id)
    if job is None:
        return
    source = (
        crud.get_data_source(db, job.data_source_id, include_inactive=True)
        if job.data_source_id
        else None
    )
    cleanup_errors = []
    if source is not None:
        try:
            drop_data_source_database(source)
        except Exception as exc:
            cleanup_errors.append(str(exc))
        try:
            crud.delete_data_source(db, source.id)
        except Exception as exc:
            db.rollback()
            cleanup_errors.append(str(exc))
    elif job.database_created and job.database_name:
        try:
            drop_imported_database(ImportedDatabase(
                database_name=job.database_name,
                host="",
                port=3306,
                username="",
                password="",
            ))
        except Exception as exc:
            cleanup_errors.append(str(exc))
    message = "数据源接入已取消，未完成内容已回退"
    if cleanup_errors:
        message += "；部分资源清理失败，请检查后端日志"
    crud.update_data_source_import_job(
        db,
        job_id,
        status="cancelled",
        stage="cancelled",
        progress=0,
        message=message,
        error_message="；".join(cleanup_errors) or None,
        data_source_id=None,
        database_created=bool(cleanup_errors),
    )


def request_cancel_data_source_import(db, job_id: int):
    job = crud.get_data_source_import_job(db, job_id)
    if job is None:
        return None
    if job.status in {"completed", "failed", "cancelled"}:
        return job
    job = crud.update_data_source_import_job(
        db,
        job_id,
        status="cancelled",
        stage="cancelled",
        progress=0,
        message="正在取消数据源接入并回退未完成内容",
        error_message=None,
    )
    with _active_job_lock:
        active = job_id in _active_job_ids
    if not active:
        _rollback_import_job(db, job_id)
        job = crud.get_data_source_import_job(db, job_id)
    return job


def abort_unfinished_data_source_imports() -> int:
    """Backend-startup recovery: stale work cannot survive a process restart."""

    db = SessionLocal()
    try:
        from models import DataSourceImportJob

        jobs = (
            db.query(DataSourceImportJob)
            .filter(DataSourceImportJob.status.in_(["queued", "processing"]))
            .order_by(DataSourceImportJob.id.asc())
            .all()
        )
        job_ids = [job.id for job in jobs]
        for job_id in job_ids:
            crud.update_data_source_import_job(
                db,
                job_id,
                status="cancelled",
                stage="cancelled",
                progress=0,
                message="后端重新启动，未完成的数据源接入已中止",
            )
            _rollback_import_job(db, job_id)
        return len(job_ids)
    finally:
        db.close()


def process_data_source_import(job_id: int, sql_text: str) -> None:
    """Background-task entry point. Progress is durable and pollable by the UI."""

    with _active_job_lock:
        _active_job_ids.add(job_id)
    db = SessionLocal()
    imported: Optional[ImportedDatabase] = None
    source_created = False
    try:
        job = crud.get_data_source_import_job(db, job_id)
        if job is None:
            return
        if job.status == "cancelled":
            _rollback_import_job(db, job_id)
            return
        cancel_check = lambda: _job_is_cancelled(db, job_id)
        crud.update_data_source_import_job(
            db,
            job_id,
            status="processing",
            stage="building",
            progress=25,
            message="数据源建设中",
            error_message=None,
        )
        prepared = prepare_sql_import(sql_text)
        imported = import_new_database(
            prepared,
            cancel_check=cancel_check,
            database_created_callback=lambda: _set_database_created(db, job_id),
        )
        _raise_if_cancelled(cancel_check)
        source_payload = schemas.DataSourceCreate(
            name=job.data_source_name,
            db_type="mysql",
            host=imported.host,
            port=imported.port,
            database=imported.database_name,
            username=imported.username,
            password=imported.password,
            enterprise_id=job.enterprise_id,
        )
        source = crud.create_data_source(db, source_payload)
        source_created = True
        crud.update_data_source_import_job(
            db,
            job_id,
            data_source_id=source.id,
            database_name=imported.database_name,
            database_created=True,
            stage="metrics",
            progress=70,
            message="数据源已建成，正在生成指标",
        )
        metrics_created = generate_metrics_for_data_source(
            db,
            user_id=job.user_id,
            data_source_id=source.id,
            cancel_check=cancel_check,
        )
        _raise_if_cancelled(cancel_check)
        crud.update_data_source_import_job(
            db,
            job_id,
            stage="metrics",
            progress=84,
            message="指标已生成，正在生成数据字典与分析规则",
            metrics_created=metrics_created,
        )
        knowledge_documents_created = generate_knowledge_documents_for_data_source(
            db,
            user_id=job.user_id,
            data_source_id=source.id,
            cancel_check=cancel_check,
        )
        _raise_if_cancelled(cancel_check)
        try:
            build_knowledge_base()
        except Exception as exc:
            raise DataSourceImportError(f"指标已生成，但知识库同步失败：{exc}") from exc
        _raise_if_cancelled(cancel_check)
        crud.update_data_source_import_job(
            db,
            job_id,
            status="completed",
            stage="completed",
            progress=100,
            message="数据源接入成功",
            metrics_created=metrics_created,
            knowledge_documents_created=knowledge_documents_created,
            database_created=True,
            error_message=None,
        )
    except Exception as exc:
        db.rollback()
        current_job = crud.get_data_source_import_job(db, job_id)
        cancelled = isinstance(exc, DataSourceImportCancelled) or getattr(current_job, "status", None) == "cancelled"
        if cancelled:
            _rollback_import_job(db, job_id)
            return
        cleanup_error = None
        current_job = crud.get_data_source_import_job(db, job_id)
        created_source = (
            crud.get_data_source(db, current_job.data_source_id, include_inactive=True)
            if current_job and current_job.data_source_id
            else None
        )
        # Every database in this workflow was created exclusively from the
        # uploaded package. A failed metric/dictionary/RAG stage therefore
        # rolls the whole onboarding attempt back instead of leaving an
        # unusable source that blocks a retry with the same database name.
        if created_source is not None:
            try:
                drop_data_source_database(created_source)
                crud.delete_data_source(db, created_source.id)
                source_created = False
            except Exception as cleanup_exc:
                db.rollback()
                cleanup_error = str(cleanup_exc)
        elif imported is not None:
            try:
                drop_imported_database(imported)
            except Exception as cleanup_exc:
                cleanup_error = str(cleanup_exc)
        current_job = crud.get_data_source_import_job(db, job_id)
        failed_progress = max(10, int(getattr(current_job, "progress", 10) or 10))
        error_message = str(exc)
        if cleanup_error:
            error_message += f"；自动回退失败：{cleanup_error}"
        crud.update_data_source_import_job(
            db,
            job_id,
            status="failed",
            stage="failed",
            progress=failed_progress,
            message="数据源接入失败",
            error_message=error_message,
            data_source_id=getattr(current_job, "data_source_id", None) if cleanup_error else None,
            database_created=bool(cleanup_error),
        )
    finally:
        db.close()
        with _active_job_lock:
            _active_job_ids.discard(job_id)
