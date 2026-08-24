"""Small idempotent migrations for the existing deployment.

The project historically used ``create_all``. These migrations preserve that
installation while adding explicit, versioned alterations for existing tables.
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from models import DepartmentEmployee, DepartmentTask


MIGRATIONS = [
    (
        "001_metric_dashboard_configuration",
        {
            "aliases": "VARCHAR(255) NULL",
            "unit": "VARCHAR(20) NULL",
            "base_table": "VARCHAR(100) NULL",
            "time_field": "VARCHAR(100) NULL",
            "dimension_field": "VARCHAR(100) NULL",
            "dashboard_enabled": "BOOLEAN NOT NULL DEFAULT TRUE",
        },
    ),
]


def run_schema_migrations(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text(
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version VARCHAR(100) PRIMARY KEY, applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
        ))
    inspector = inspect(engine)
    existing_versions = set()
    with engine.connect() as connection:
        existing_versions = {row[0] for row in connection.execute(text("SELECT version FROM schema_migrations"))}
    for version, columns in MIGRATIONS:
        if version in existing_versions:
            continue
        has_legacy_metrics = "metrics" in inspector.get_table_names()
        existing_columns = (
            {column["name"] for column in inspector.get_columns("metrics")}
            if has_legacy_metrics else set()
        )
        with engine.begin() as connection:
            if has_legacy_metrics:
                for name, definition in columns.items():
                    if name not in existing_columns:
                        connection.execute(text(f"ALTER TABLE metrics ADD COLUMN `{name}` {definition}"))
            connection.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                {"version": version},
            )

    secret_version = "002_expand_encrypted_data_source_password"
    with engine.connect() as connection:
        applied = connection.execute(
            text("SELECT 1 FROM schema_migrations WHERE version = :version"),
            {"version": secret_version},
        ).first()
    if not applied:
        dialect = engine.dialect.name
        with engine.begin() as connection:
            if dialect in {"mysql", "mariadb"}:
                connection.execute(text("ALTER TABLE data_sources MODIFY COLUMN password TEXT"))
            elif dialect == "postgresql":
                connection.execute(text("ALTER TABLE data_sources ALTER COLUMN password TYPE TEXT"))
            # SQLite already stores VARCHAR values dynamically and needs no table rewrite.
            connection.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                {"version": secret_version},
            )

    enterprise_version = "003_require_data_source_enterprise"
    with engine.connect() as connection:
        applied = connection.execute(
            text("SELECT 1 FROM schema_migrations WHERE version = :version"),
            {"version": enterprise_version},
        ).first()
    if not applied:
        dialect = engine.dialect.name
        with engine.begin() as connection:
            # The catalog bootstrap runs before migrations, so an existing
            # installation always has a safe enterprise for legacy NULL rows.
            connection.execute(text(
                "UPDATE data_sources SET enterprise_id = "
                "(SELECT id FROM enterprises ORDER BY id LIMIT 1) "
                "WHERE enterprise_id IS NULL"
            ))
            if dialect in {"mysql", "mariadb"}:
                connection.execute(text(
                    "ALTER TABLE data_sources MODIFY COLUMN enterprise_id INT NOT NULL"
                ))
            elif dialect == "postgresql":
                connection.execute(text(
                    "ALTER TABLE data_sources ALTER COLUMN enterprise_id SET NOT NULL"
                ))
            # SQLite create_all already applies NOT NULL to new databases. Its
            # legacy tables are protected by API validation without a rebuild.
            connection.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                {"version": enterprise_version},
            )

    metric_catalog_version = "004_metric_definitions_and_bindings"
    with engine.connect() as connection:
        applied = connection.execute(
            text("SELECT 1 FROM schema_migrations WHERE version = :version"),
            {"version": metric_catalog_version},
        ).first()
    if not applied:
        table_names = set(inspect(engine).get_table_names())
        with engine.begin() as connection:
            if "metrics" in table_names:
                legacy_rows = list(connection.execute(text(
                    "SELECT id, name, description, sql_expr, topic, data_source_id, "
                    "aliases, unit, base_table, time_field, dimension_field, dashboard_enabled "
                    "FROM metrics ORDER BY id"
                )).mappings())
                definition_by_name = {
                    str(row["name"]).strip().casefold(): int(row["id"])
                    for row in connection.execute(
                        text("SELECT id, name FROM metric_definitions ORDER BY id")
                    ).mappings()
                }
                existing_binding_ids = {
                    int(row[0]) for row in connection.execute(text("SELECT id FROM metric_bindings"))
                }
                existing_pairs = {
                    (int(row[0]), int(row[1]))
                    for row in connection.execute(text(
                        "SELECT definition_id, data_source_id FROM metric_bindings"
                    ))
                }
                for row in legacy_rows:
                    name = str(row["name"] or "").strip()
                    if not name or row["data_source_id"] is None:
                        continue
                    normalized_name = name.casefold()
                    definition_id = definition_by_name.get(normalized_name)
                    if definition_id is None:
                        connection.execute(text(
                            "INSERT INTO metric_definitions "
                            "(name, description, topic, aliases, unit) "
                            "VALUES (:name, :description, :topic, :aliases, :unit)"
                        ), {
                            "name": name,
                            "description": row["description"],
                            "topic": row["topic"] or "未分类",
                            "aliases": row["aliases"],
                            "unit": row["unit"],
                        })
                        definition_id = int(connection.execute(
                            text("SELECT id FROM metric_definitions WHERE name = :name"),
                            {"name": name},
                        ).scalar_one())
                        definition_by_name[normalized_name] = definition_id
                    pair = (definition_id, int(row["data_source_id"]))
                    if pair in existing_pairs:
                        continue
                    values = {
                        "id": int(row["id"]),
                        "definition_id": definition_id,
                        "data_source_id": int(row["data_source_id"]),
                        "sql_expr": row["sql_expr"] or "",
                        "base_table": row["base_table"],
                        "time_field": row["time_field"],
                        "dimension_field": row["dimension_field"],
                        "dashboard_enabled": bool(row["dashboard_enabled"]),
                    }
                    if values["id"] in existing_binding_ids:
                        connection.execute(text(
                            "INSERT INTO metric_bindings "
                            "(definition_id, data_source_id, sql_expr, base_table, time_field, "
                            "dimension_field, dashboard_enabled) VALUES "
                            "(:definition_id, :data_source_id, :sql_expr, :base_table, :time_field, "
                            ":dimension_field, :dashboard_enabled)"
                        ), values)
                    else:
                        connection.execute(text(
                            "INSERT INTO metric_bindings "
                            "(id, definition_id, data_source_id, sql_expr, base_table, time_field, "
                            "dimension_field, dashboard_enabled) VALUES "
                            "(:id, :definition_id, :data_source_id, :sql_expr, :base_table, :time_field, "
                            ":dimension_field, :dashboard_enabled)"
                        ), values)
                        existing_binding_ids.add(values["id"])
                    existing_pairs.add(pair)
            connection.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                {"version": metric_catalog_version},
            )

    lifecycle_version = "005_data_source_lifecycle"
    with engine.connect() as connection:
        applied = connection.execute(
            text("SELECT 1 FROM schema_migrations WHERE version = :version"),
            {"version": lifecycle_version},
        ).first()
    if not applied:
        table_names = set(inspect(engine).get_table_names())
        source_columns = (
            {column["name"] for column in inspect(engine).get_columns("data_sources")}
            if "data_sources" in table_names else set()
        )
        with engine.begin() as connection:
            if "data_sources" in table_names and "is_active" not in source_columns:
                connection.execute(text(
                    "ALTER TABLE data_sources ADD COLUMN is_active "
                    "BOOLEAN NOT NULL DEFAULT TRUE"
                ))
            # Keep the legacy metrics table intact for conservative upgrades.
            # Full source deletion removes only rows belonging to that source.
            connection.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                {"version": lifecycle_version},
            )

    import_version = "006_sql_file_data_source_import"
    with engine.connect() as connection:
        applied = connection.execute(
            text("SELECT 1 FROM schema_migrations WHERE version = :version"),
            {"version": import_version},
        ).first()
    if not applied:
        dialect = engine.dialect.name
        with engine.begin() as connection:
            if dialect in {"mysql", "mariadb"}:
                connection.execute(text(
                    "ALTER TABLE data_sources MODIFY COLUMN `database` VARCHAR(64)"
                ))
            elif dialect == "postgresql":
                connection.execute(text(
                    "ALTER TABLE data_sources ALTER COLUMN \"database\" TYPE VARCHAR(64)"
                ))
            connection.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                {"version": import_version},
            )

    cancellation_version = "007_cancel_data_source_import"
    with engine.connect() as connection:
        applied = connection.execute(
            text("SELECT 1 FROM schema_migrations WHERE version = :version"),
            {"version": cancellation_version},
        ).first()
    if not applied:
        table_names = set(inspect(engine).get_table_names())
        job_columns = (
            {column["name"] for column in inspect(engine).get_columns("data_source_import_jobs")}
            if "data_source_import_jobs" in table_names else set()
        )
        with engine.begin() as connection:
            if "data_source_import_jobs" in table_names and "database_created" not in job_columns:
                connection.execute(text(
                    "ALTER TABLE data_source_import_jobs ADD COLUMN database_created "
                    "BOOLEAN NOT NULL DEFAULT FALSE"
                ))
            connection.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                {"version": cancellation_version},
            )

    generated_knowledge_version = "008_import_generated_knowledge_documents"
    with engine.connect() as connection:
        applied = connection.execute(
            text("SELECT 1 FROM schema_migrations WHERE version = :version"),
            {"version": generated_knowledge_version},
        ).first()
    if not applied:
        table_names = set(inspect(engine).get_table_names())
        job_columns = (
            {column["name"] for column in inspect(engine).get_columns("data_source_import_jobs")}
            if "data_source_import_jobs" in table_names else set()
        )
        with engine.begin() as connection:
            if "data_source_import_jobs" in table_names and "knowledge_documents_created" not in job_columns:
                connection.execute(text(
                    "ALTER TABLE data_source_import_jobs ADD COLUMN knowledge_documents_created "
                    "INT NOT NULL DEFAULT 0"
                ))
            connection.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                {"version": generated_knowledge_version},
            )

    department_workspace_version = "009_department_workspace"
    with engine.connect() as connection:
        applied = connection.execute(
            text("SELECT 1 FROM schema_migrations WHERE version = :version"),
            {"version": department_workspace_version},
        ).first()
    if not applied:
        # ``create_all`` normally creates these first. Explicit check-first
        # creation keeps direct migration usage safe for existing deployments.
        DepartmentTask.__table__.create(bind=engine, checkfirst=True)
        DepartmentEmployee.__table__.create(bind=engine, checkfirst=True)
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO schema_migrations (version) VALUES (:version)"),
                {"version": department_workspace_version},
            )
