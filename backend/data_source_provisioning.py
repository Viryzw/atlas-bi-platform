"""Validate new business data sources and provision narrowly scoped read access.

The application never grants privileges through the reader connection itself.
For a local MySQL source it can reuse the platform database's administrative
connection. Remote servers require an explicit DATA_SOURCE_ADMIN_URL so that
privileged credentials are never accepted from or returned to the browser.
"""

import os
import hashlib
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from database import engine as platform_engine
from query_engine import build_data_source_url


LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
MYSQL_ACCESS_DENIED_CODES = {1044, 1045}
PROTECTED_MYSQL_DATABASES = {"mysql", "information_schema", "performance_schema", "sys"}


class DataSourceProvisioningError(RuntimeError):
    """Actionable validation/provisioning failure safe to show to an admin."""


@dataclass(frozen=True)
class DataSourceProvisioningResult:
    status: str
    message: str


def _mysql_error_code(exc: BaseException) -> Optional[int]:
    original = getattr(exc, "orig", None)
    args = getattr(original, "args", ())
    return args[0] if args and isinstance(args[0], int) else None


def _verify_connection(data_source) -> None:
    reader_engine = create_engine(
        build_data_source_url(data_source),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 8},
    )
    try:
        with reader_engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    finally:
        reader_engine.dispose()


def _same_local_mysql_server(data_source) -> bool:
    platform_host = (platform_engine.url.host or "localhost").lower()
    source_host = (data_source.host or "").lower()
    platform_port = platform_engine.url.port or 3306
    return (
        source_host in LOCAL_HOSTS
        and platform_host in LOCAL_HOSTS
        and int(data_source.port or 3306) == int(platform_port)
    )


def _admin_engine_for(data_source) -> tuple[Engine, bool]:
    configured_url = os.getenv("DATA_SOURCE_ADMIN_URL", "").strip()
    if configured_url:
        return create_engine(configured_url, pool_pre_ping=True, hide_parameters=True), True
    if _same_local_mysql_server(data_source):
        return platform_engine, False
    raise DataSourceProvisioningError(
        "数据源账号没有读取权限，且该数据库不是平台同机 MySQL。"
        "请在后端环境变量 DATA_SOURCE_ADMIN_URL 中配置目标服务器的管理员连接后重试"
    )


def _quoted_mysql_identifier(value: str) -> str:
    normalized = (value or "").strip()
    if not normalized or len(normalized) > 64 or "\x00" in normalized:
        raise DataSourceProvisioningError("数据库名称无效，无法执行自动只读授权")
    return f"`{normalized.replace('`', '``')}`"


def _same_mysql_server(admin_engine: Engine, data_source) -> bool:
    admin_host = (admin_engine.url.host or "localhost").lower()
    source_host = (data_source.host or "").lower()
    same_host = (
        admin_host == source_host
        or (admin_host in LOCAL_HOSTS and source_host in LOCAL_HOSTS)
    )
    return same_host and int(admin_engine.url.port or 3306) == int(data_source.port or 3306)


def _grant_mysql_select(admin_engine: Engine, data_source) -> None:
    database_name = _quoted_mysql_identifier(data_source.database)
    username = (data_source.username or "").strip()
    if not username or len(username) > 32 or "\x00" in username:
        raise DataSourceProvisioningError("数据源用户名无效，无法执行自动只读授权")
    if (data_source.host or "").lower() in LOCAL_HOSTS:
        account_host = "localhost"
    else:
        account_host = os.getenv("DATA_SOURCE_READER_HOST", "").strip()
        if not account_host:
            raise DataSourceProvisioningError(
                "远程 MySQL 自动授权还需要配置 DATA_SOURCE_READER_HOST，"
                "其值应为数据库服务器看到的后端来源主机，系统不会自动使用 '%' 通配账号"
            )
    try:
        with admin_engine.begin() as connection:
            # PyMySQL safely quotes the account values. Only the schema identifier
            # is interpolated, after strict length/NUL checks and backtick escaping.
            connection.exec_driver_sql(
                f"GRANT SELECT ON {database_name}.* TO %s@%s",
                (username, account_host),
            )
    except SQLAlchemyError as exc:
        raise DataSourceProvisioningError(
            "自动授权失败。请确认后端管理连接拥有 GRANT OPTION，"
            f"并且账号 '{username}'@'{account_host}' 已存在：{exc}"
        ) from exc


def validate_and_provision_data_source(data_source) -> DataSourceProvisioningResult:
    """Verify access, grant SELECT when safe, and verify again before persistence."""

    try:
        _verify_connection(data_source)
        return DataSourceProvisioningResult(
            status="verified",
            message="数据源连接和只读权限已验证",
        )
    except OperationalError as exc:
        if data_source.db_type != "mysql" or _mysql_error_code(exc) not in MYSQL_ACCESS_DENIED_CODES:
            raise DataSourceProvisioningError(f"数据源连接验证失败：{exc}") from exc
    except SQLAlchemyError as exc:
        raise DataSourceProvisioningError(f"数据源连接验证失败：{exc}") from exc

    admin_engine, should_dispose = _admin_engine_for(data_source)
    try:
        _grant_mysql_select(admin_engine, data_source)
    finally:
        if should_dispose:
            admin_engine.dispose()

    try:
        _verify_connection(data_source)
    except Exception as exc:
        raise DataSourceProvisioningError(
            f"已执行只读授权，但使用数据源账号重新连接仍然失败：{exc}"
        ) from exc
    return DataSourceProvisioningResult(
        status="granted",
        message=f"已自动授予 {data_source.username} 对 {data_source.database} 的 SELECT 权限",
    )


def drop_data_source_database(data_source) -> None:
    """Drop one explicitly selected business schema through an admin connection."""

    if (data_source.db_type or "").lower() != "mysql":
        raise DataSourceProvisioningError("当前仅支持自动删除 MySQL 完整数据源")
    database = (data_source.database or "").strip()
    if database.casefold() in PROTECTED_MYSQL_DATABASES:
        raise DataSourceProvisioningError(f"系统数据库 {database} 禁止删除")
    if (
        _same_local_mysql_server(data_source)
        and database.casefold() == (platform_engine.url.database or "").casefold()
    ):
        raise DataSourceProvisioningError("禁止删除 BI 平台自身数据库")

    database_name = _quoted_mysql_identifier(database)
    admin_engine, should_dispose = _admin_engine_for(data_source)
    try:
        if not _same_mysql_server(admin_engine, data_source):
            raise DataSourceProvisioningError(
                "DATA_SOURCE_ADMIN_URL 与待删除数据源不在同一 MySQL 服务器，已拒绝删除"
            )
        with admin_engine.begin() as connection:
            connection.exec_driver_sql(f"DROP DATABASE IF EXISTS {database_name}")
            expected_managed_username = (
                "atlasbi_"
                + hashlib.sha256(database.casefold().encode("utf-8")).hexdigest()[:18]
            )
            if (getattr(data_source, "username", "") or "") == expected_managed_username:
                account_host = (
                    "localhost"
                    if (data_source.host or "").lower() in LOCAL_HOSTS
                    else os.getenv("DATA_SOURCE_READER_HOST", "").strip()
                )
                if account_host:
                    connection.exec_driver_sql(
                        "DROP USER IF EXISTS %s@%s",
                        (expected_managed_username, account_host),
                    )
    except DataSourceProvisioningError:
        raise
    except SQLAlchemyError as exc:
        raise DataSourceProvisioningError(
            f"完整数据源删除失败，请确认后端管理连接拥有 DROP 权限：{exc}"
        ) from exc
    finally:
        if should_dispose:
            admin_engine.dispose()
