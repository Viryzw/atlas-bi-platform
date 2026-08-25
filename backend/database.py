import os

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.orm import declarative_base, sessionmaker

# MySQL 连接 URL（请替换为你的实际用户名、密码、主机、端口、数据库名）
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://root:050429@localhost:3306/bi_platform?charset=utf8mb4",
)

engine = create_engine(
    DATABASE_URL,
    echo=os.getenv("DB_ECHO", "false").lower() in {"1", "true", "yes"},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def _mysql_error_code(exc: BaseException) -> int | None:
    """Extract the numeric MySQL error code from a SQLAlchemy exception."""
    original = getattr(exc, "orig", exc)
    args = getattr(original, "args", ())
    if not args:
        return None
    try:
        return int(args[0])
    except (TypeError, ValueError):
        return None


def ensure_database_exists() -> bool:
    """Create the configured MySQL management database on a first deployment.

    SQLAlchemy can create tables but cannot connect to a database that does not
    exist yet. We first try the configured connection and only fall back to a
    server-level connection when MySQL explicitly reports error 1049.

    Returns ``True`` when a missing database was created.
    """
    if engine.dialect.name != "mysql":
        return False

    try:
        with engine.connect():
            return False
    except OperationalError as exc:
        if _mysql_error_code(exc) != 1049:
            raise

    url = make_url(DATABASE_URL)
    database_name = url.database
    if not database_name:
        return False

    # An empty database component connects to the MySQL server without first
    # selecting the missing target database. Keep all credentials and options.
    server_url = url.set(database="")
    bootstrap_engine = create_engine(server_url, pool_pre_ping=True)
    escaped_name = database_name.replace("`", "``")
    try:
        with bootstrap_engine.connect() as connection:
            connection.execution_options(isolation_level="AUTOCOMMIT").execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{escaped_name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
    except SQLAlchemyError as exc:
        raise RuntimeError(
            f"管理数据库 {database_name!r} 不存在，且当前 MySQL 账号无权自动创建。"
            "请为 DATABASE_URL 配置具有 CREATE DATABASE 权限的账号，"
            "或先在 MySQL 中手动创建该数据库。"
        ) from exc
    finally:
        bootstrap_engine.dispose()

    # Clear the failed connection state before create_all connects again.
    engine.dispose()
    return True

# 依赖项：获取数据库会话
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
