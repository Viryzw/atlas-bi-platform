import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import crud
import data_source_import
import data_source_provisioning
import enterprise_catalog
import knowledge_base
import schemas
import sql_agent
from routers import dashboard as dashboard_router
from routers import data_sources as data_source_router
from routers import enterprises as enterprise_router
from routers import knowledge as knowledge_router
from routers import llm_config as llm_config_router
from routers import metrics as metric_router
from routers import conversations as conversation_router
from routers import reports as report_router
from routers import departments as department_router
from models import Base, Conversation, DataSource, DataSourceImportJob, Department, DepartmentEmployee, DepartmentTask, Enterprise, KnowledgeDocument, Metric, MetricDefinition, ReportDraft, User
from schema_migrations import run_schema_migrations


class KnowledgeBaseTests(unittest.TestCase):
    def test_metric_document_contains_business_definition_and_source(self):
        metric = SimpleNamespace(
            id=7,
            name="销售额",
            topic="销售经营",
            description="只统计已支付订单",
            sql_expr="SUM(CASE WHEN status='paid' THEN amount ELSE 0 END)",
            data_source_id=1,
        )

        text, metadata = knowledge_base.metric_to_document(metric)

        self.assertIn("指标名称: 销售额", text)
        self.assertIn("只统计已支付订单", text)
        self.assertIn("数据源 ID: 1", text)
        self.assertEqual(metadata["metric_id"], 7)

    def test_empty_rebuild_creates_a_valid_empty_collection(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(
            knowledge_base, "PERSIST_DIR", Path(directory) / "index"
        ), patch.object(
            knowledge_base, "_load_metrics", return_value=[]
        ), patch.object(
            knowledge_base, "_load_knowledge_documents", return_value=[]
        ), patch.object(
            knowledge_base, "_load_schema_documents", return_value=[]
        ):
            result = knowledge_base.build_knowledge_base()

        self.assertEqual(result["metric_count"], 0)
        self.assertEqual(result["indexed_count"], 0)
        self.assertTrue(result["synchronized"])

    def test_dictionary_document_contains_category_and_content(self):
        document = SimpleNamespace(
            id=3,
            category="field",
            title="orders.status 字段含义",
            content="paid 表示已支付，cancelled 表示已取消",
            data_source_id=1,
        )

        text, metadata = knowledge_base.knowledge_document_to_document(document)

        self.assertIn("字段含义", text)
        self.assertIn("paid 表示已支付", text)
        self.assertEqual(metadata["source_type"], "dictionary")


class MetricGuardTests(unittest.TestCase):
    def setUp(self):
        self.metric = {
            "metric_id": 1,
            "name": "销售额",
            "sql_expr": "SUM(CASE WHEN status='paid' THEN amount ELSE 0 END)",
        }

    def test_exact_metric_expression_passes(self):
        validation = sql_agent.validate_metric_sql(
            "SELECT customer_name, SUM(CASE WHEN status='paid' THEN amount ELSE 0 END) AS sales FROM orders GROUP BY customer_name",
            [self.metric],
        )

        self.assertTrue(validation["passed"])
        self.assertEqual(validation["status"], "passed")

    def test_semantic_rewrite_is_rejected_by_metric_guard(self):
        validation = sql_agent.validate_metric_sql(
            "SELECT customer_name, SUM(amount) AS sales FROM orders WHERE status='paid' GROUP BY customer_name",
            [self.metric],
        )

        self.assertFalse(validation["passed"])
        self.assertEqual(validation["violations"][0]["name"], "销售额")

    @patch.object(sql_agent, "get_table_info", return_value="TABLE orders (...)" )
    @patch.object(sql_agent, "_knowledge_context")
    @patch.object(sql_agent, "get_llm")
    def test_noncompliant_sql_is_repaired_once(self, get_llm, knowledge_context, _table_info):
        knowledge_context.return_value = ("销售额口径", [self.metric])
        wrong = {
            "intent": "各厂商销售额",
            "request_type": "metric",
            "sql": "SELECT customer_name, SUM(amount) AS 销售额 FROM orders WHERE status='paid' GROUP BY customer_name",
        }
        repaired = {
            "intent": "各厂商销售额",
            "request_type": "metric",
            "sql": "SELECT customer_name, SUM(CASE WHEN status='paid' THEN amount ELSE 0 END) AS 销售额 FROM orders GROUP BY customer_name",
        }
        get_llm.return_value.invoke.side_effect = [
            SimpleNamespace(content=__import__("json").dumps(wrong, ensure_ascii=False)),
            SimpleNamespace(content=__import__("json").dumps(repaired, ensure_ascii=False)),
        ]

        result = sql_agent.create_query_plan("各厂商销售额", user_id=1)

        self.assertEqual(result["status"], "success")
        self.assertTrue(result["plan"]["metric_validation"]["repaired"])
        self.assertIn(self.metric["sql_expr"], result["sql"])
        self.assertEqual(get_llm.return_value.invoke.call_count, 2)

    @patch.object(knowledge_router, "build_knowledge_base", side_effect=RuntimeError("disk full"))
    def test_rebuild_endpoint_reports_real_failure(self, _build):
        with self.assertRaises(HTTPException) as context:
            knowledge_router.rebuild_knowledge()

        self.assertEqual(context.exception.status_code, 500)
        self.assertIn("disk full", context.exception.detail["message"])


class MetricSynchronizationTests(unittest.TestCase):
    @patch.object(metric_router, "build_knowledge_base")
    @patch.object(metric_router.crud, "create_metric")
    @patch.object(metric_router.crud, "get_data_source", return_value=SimpleNamespace(id=1))
    def test_create_metric_rebuilds_index(self, _data_source, create_metric, rebuild):
        payload = schemas.MetricCreate(
            name="订单量",
            description="全部订单数量",
            sql_expr="COUNT(*)",
            topic="销售经营",
            data_source_id=1,
        )
        saved = SimpleNamespace(id=1, **payload.model_dump())
        create_metric.return_value = saved

        result = metric_router.create_metric(payload, db=MagicMock())

        self.assertIs(result, saved)
        rebuild.assert_called_once_with()

    @patch.object(metric_router.crud, "get_data_source", return_value=None)
    def test_metric_rejects_unknown_data_source(self, _data_source):
        payload = schemas.MetricCreate(
            name="订单量",
            sql_expr="COUNT(*)",
            data_source_id=99,
        )

        with self.assertRaises(HTTPException) as context:
            metric_router.create_metric(payload, db=MagicMock())

        self.assertEqual(context.exception.status_code, 400)


class MetricCatalogModelTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        enterprise = Enterprise(name="指标测试企业")
        self.db.add(enterprise)
        self.db.flush()
        self.first_source = DataSource(
            name="订单库 A", db_type="mysql", host="localhost", port=3306,
            database="orders_a", username="reader", password="", enterprise_id=enterprise.id,
        )
        self.second_source = DataSource(
            name="订单库 B", db_type="mysql", host="localhost", port=3306,
            database="orders_b", username="reader", password="", enterprise_id=enterprise.id,
        )
        self.db.add_all([self.first_source, self.second_source])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _payload(self, source_id, expression):
        return schemas.MetricCreate(
            name="销售额", description="已支付订单金额", topic="销售经营",
            sql_expr=expression, data_source_id=source_id, unit="元",
        )

    def test_same_metric_uses_one_definition_and_multiple_bindings(self):
        first = crud.create_metric(self.db, self._payload(self.first_source.id, "SUM(amount)"))
        second = crud.create_metric(self.db, self._payload(self.second_source.id, "SUM(pay_amount)"))

        self.assertEqual(first.definition_id, second.definition_id)
        self.assertEqual(self.db.query(MetricDefinition).count(), 1)
        self.assertEqual(self.db.query(Metric).count(), 2)
        self.assertEqual({first.sql_expr, second.sql_expr}, {"SUM(amount)", "SUM(pay_amount)"})

    def test_duplicate_binding_for_one_source_is_rejected(self):
        self.db.add(MetricDefinition(name="销售额", topic="销售经营"))
        self.db.commit()
        crud.create_metric(self.db, self._payload(self.first_source.id, "SUM(amount)"))

        with self.assertRaises(ValueError):
            crud.create_metric(self.db, self._payload(self.first_source.id, "SUM(total)"))

    def test_dashboard_status_can_be_updated_without_rewriting_metric_definition(self):
        metric = crud.create_metric(self.db, self._payload(self.first_source.id, "SUM(amount)"))
        original_definition_id = metric.definition_id

        updated = crud.update_metric_dashboard_enabled(self.db, metric.id, False)

        self.assertFalse(updated.dashboard_enabled)
        self.assertEqual(updated.definition_id, original_definition_id)
        self.assertEqual(updated.sql_expr, "SUM(amount)")

    def test_dashboard_loader_excludes_disabled_metrics(self):
        disabled = crud.create_metric(self.db, self._payload(self.first_source.id, "SUM(amount)"))
        enabled = crud.create_metric(
            self.db,
            schemas.MetricCreate(
                name="订单量",
                description="全部订单数量",
                topic="销售经营",
                sql_expr="COUNT(*)",
                data_source_id=self.first_source.id,
                unit="单",
            ),
        )
        crud.update_metric_dashboard_enabled(self.db, disabled.id, False)

        with patch.object(dashboard_router, "SessionLocal", side_effect=self.Session):
            loaded = dashboard_router._load_metrics(self.first_source.id)

        self.assertEqual([metric.id for metric in loaded], [enabled.id])

    def test_legacy_metrics_are_migrated_into_catalog(self):
        legacy_engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(legacy_engine)
        with legacy_engine.begin() as connection:
            connection.execute(text("INSERT INTO enterprises (id, name) VALUES (99, '迁移企业')"))
            connection.execute(text(
                "INSERT INTO data_sources (id, name, db_type, host, port, database, username, password, enterprise_id) "
                "VALUES (99, '迁移库', 'mysql', 'localhost', 3306, 'legacy', 'reader', '', 99)"
            ))
            connection.execute(text(
                "CREATE TABLE metrics (id INTEGER PRIMARY KEY, name VARCHAR(100) NOT NULL, "
                "description TEXT, sql_expr TEXT, topic VARCHAR(50), data_source_id INTEGER)"
            ))
            connection.execute(text(
                "INSERT INTO metrics (id, name, description, sql_expr, topic, data_source_id) "
                "VALUES (99, '销售额', '旧指标', 'SUM(amount)', '销售经营', 99)"
            ))

        run_schema_migrations(legacy_engine)

        with legacy_engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT COUNT(*) FROM metric_definitions")).scalar(), 1)
            self.assertEqual(connection.execute(text("SELECT COUNT(*) FROM metric_bindings")).scalar(), 1)
            self.assertEqual(connection.execute(text("SELECT sql_expr FROM metric_bindings")).scalar(), "SUM(amount)")
        legacy_engine.dispose()


class DepartmentWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = sessionmaker(bind=self.engine)()
        enterprise = Enterprise(name="组织测试企业")
        self.db.add(enterprise)
        self.db.flush()
        self.parent = Department(name="经营中心", enterprise_id=enterprise.id)
        self.db.add(self.parent)
        self.db.flush()
        self.child = Department(name="分析组", enterprise_id=enterprise.id, parent_id=self.parent.id)
        self.db.add(self.child)
        self.db.flush()
        parent_task = DepartmentTask(department_id=self.parent.id, name="年度规划", progress=40)
        child_task = DepartmentTask(department_id=self.child.id, name="周报分析", progress=70)
        self.db.add_all([parent_task, child_task])
        self.db.flush()
        self.db.add_all([
            DepartmentEmployee(department_id=self.parent.id, task_id=parent_task.id, name="张敏", title="经理"),
            DepartmentEmployee(department_id=self.child.id, task_id=child_task.id, name="李晨", title="分析师"),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_parent_workspace_excludes_all_descendant_records(self):
        result = department_router.read_department_workspace(self.parent.id, db=self.db)

        self.assertEqual([item.name for item in result["tasks"]], ["年度规划"])
        self.assertEqual([item.name for item in result["employees"]], ["张敏"])

    def test_employee_can_only_select_a_task_from_the_same_department(self):
        child_task = crud.get_department_tasks(self.db, self.child.id)[0]
        with self.assertRaises(HTTPException) as context:
            department_router.create_department_employee(
                self.parent.id,
                schemas.DepartmentEmployeeCreate(name="王蕾", task_id=child_task.id),
                db=self.db,
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("不属于当前部门", context.exception.detail["message"])

    def test_deleting_task_unassigns_its_multiple_employees(self):
        task = crud.get_department_tasks(self.db, self.parent.id)[0]
        crud.create_department_employee(
            self.db,
            self.parent.id,
            schemas.DepartmentEmployeeCreate(name="王蕾", task_id=task.id),
        )

        self.assertTrue(crud.delete_department_task(self.db, self.parent.id, task.id))
        employees = crud.get_department_employees(self.db, self.parent.id)
        self.assertEqual(len(employees), 2)
        self.assertTrue(all(employee.task_id is None for employee in employees))


class DataSourceSafetyTests(unittest.TestCase):
    @patch.object(data_source_router.crud, "get_enterprise", return_value=None)
    def test_unknown_enterprise_returns_actionable_400(self, _enterprise):
        payload = schemas.DataSourceCreate(
            name="业务库",
            host="localhost",
            port=3306,
            database="business_db",
            username="reader",
            password="secret",
            enterprise_id=99,
        )

        with self.assertRaises(HTTPException) as context:
            data_source_router.create_data_source(payload, db=MagicMock())

        self.assertEqual(context.exception.status_code, 400)
        self.assertIn("企业 ID 99 不存在", context.exception.detail["message"])

    @patch.object(data_source_router, "_sync_schema_knowledge")
    @patch.object(data_source_router.crud, "create_data_source")
    @patch.object(data_source_router, "validate_and_provision_data_source")
    @patch.object(data_source_router.crud, "get_enterprise", return_value=SimpleNamespace(id=1))
    def test_create_data_source_verifies_access_before_persistence(
        self, _enterprise, provision, create_data_source, _sync
    ):
        payload = schemas.DataSourceCreate(
            name="新业务库",
            host="localhost",
            port=3306,
            database="atlas_bi_test",
            username="bi_reader",
            password="secret",
            enterprise_id=1,
        )
        provision.return_value = data_source_provisioning.DataSourceProvisioningResult(
            status="granted",
            message="已自动授权",
        )
        create_data_source.return_value = SimpleNamespace(id=8, **payload.model_dump())

        result = data_source_router.create_data_source(payload, db=MagicMock())

        provision.assert_called_once_with(payload)
        create_data_source.assert_called_once()
        self.assertEqual(result.provisioning_status, "granted")
        self.assertNotIn("password", result.model_dump())


    @patch.object(data_source_router.crud, "create_data_source")
    @patch.object(
        data_source_router,
        "validate_and_provision_data_source",
        side_effect=data_source_provisioning.DataSourceProvisioningError("grant denied"),
    )
    @patch.object(data_source_router.crud, "get_enterprise", return_value=SimpleNamespace(id=1))
    def test_failed_provisioning_prevents_broken_record_from_being_saved(
        self, _enterprise, _provision, create_data_source
    ):
        payload = schemas.DataSourceCreate(
            name="无权限业务库",
            host="localhost",
            port=3306,
            database="new_database",
            username="bi_reader",
            password="secret",
            enterprise_id=1,
        )

        with self.assertRaises(HTTPException) as context:
            data_source_router.create_data_source(payload, db=MagicMock())

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail["stage"], "data_source_provisioning")
        create_data_source.assert_not_called()

    @patch.object(data_source_provisioning, "_admin_engine_for")
    @patch.object(data_source_provisioning, "_verify_connection")
    def test_mysql_access_denied_triggers_select_grant_and_recheck(
        self, verify_connection, admin_engine_for
    ):
        denied = OperationalError(
            "connect",
            {},
            SimpleNamespace(args=(1044, "access denied")),
        )
        verify_connection.side_effect = [denied, None]
        admin_engine = MagicMock()
        connection = admin_engine.begin.return_value.__enter__.return_value
        admin_engine_for.return_value = (admin_engine, False)
        source = SimpleNamespace(
            db_type="mysql",
            host="localhost",
            port=3306,
            database="atlas_bi_test",
            username="bi_reader",
            password="secret",
        )

        result = data_source_provisioning.validate_and_provision_data_source(source)

        self.assertEqual(result.status, "granted")
        self.assertEqual(verify_connection.call_count, 2)
        sql, params = connection.exec_driver_sql.call_args.args
        self.assertEqual(sql, "GRANT SELECT ON `atlas_bi_test`.* TO %s@%s")
        self.assertEqual(params, ("bi_reader", "localhost"))

    @patch.object(data_source_provisioning, "_verify_connection")
    def test_non_permission_connection_error_never_attempts_grant(self, verify_connection):
        verify_connection.side_effect = OperationalError(
            "connect",
            {},
            SimpleNamespace(args=(1049, "unknown database")),
        )
        source = SimpleNamespace(
            db_type="mysql",
            host="localhost",
            port=3306,
            database="missing_database",
            username="bi_reader",
            password="secret",
        )

        with self.assertRaises(data_source_provisioning.DataSourceProvisioningError) as context:
            data_source_provisioning.validate_and_provision_data_source(source)

        self.assertIn("连接验证失败", str(context.exception))

    @patch.object(crud, "get_data_source")
    def test_metadata_edit_does_not_expose_or_erase_managed_secret(self, get_data_source):
        record = SimpleNamespace(
            id=1,
            name="旧名称",
            db_type="mysql",
            host="localhost",
            port=3306,
            database="business_db",
            username="reader",
            password="keep-me",
            enterprise_id=1,
        )
        get_data_source.return_value = record
        payload = schemas.DataSourceUpdate(
            name="新名称",
            host="localhost",
            port=3306,
            database="business_db",
            enterprise_id=1,
        )
        db = MagicMock()

        crud.update_data_source(db, 1, payload)

        self.assertEqual(record.password, "keep-me")
        self.assertEqual(record.username, "reader")
        self.assertEqual(record.name, "新名称")


class SQLFileImportSafetyTests(unittest.TestCase):
    def test_empty_installation_does_not_create_placeholder_enterprise(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)

        with patch.object(enterprise_catalog, "SessionLocal", Session):
            result = enterprise_catalog.ensure_enterprise_catalog()

        db = Session()
        self.assertIsNone(result)
        self.assertEqual(db.query(Enterprise).count(), 0)
        db.close()
        engine.dispose()

    def test_upload_filename_drives_enterprise_and_data_source_names(self):
        enterprise_name, data_source_name = data_source_import.parse_data_source_import_filename(
            "星辰智造有限公司-运营数据-生产环境.sql"
        )

        self.assertEqual(enterprise_name, "星辰智造有限公司")
        self.assertEqual(data_source_name, "运营数据-生产环境")

    def test_upload_filename_rejects_missing_enterprise_separator(self):
        with self.assertRaises(data_source_import.DataSourceImportError) as context:
            data_source_import.parse_data_source_import_filename("xingchen_manufacturing.sql")

        self.assertIn("企业名-数据源名.sql", str(context.exception))

    @patch.object(data_source_router, "get_llm", return_value=MagicMock())
    def test_upload_route_creates_or_reuses_enterprise_from_filename(self, _get_llm):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        db = sessionmaker(bind=engine)()
        user = User(username="filename-importer", password="secret", role="admin")
        db.add(user)
        db.commit()
        sql_file = b"CREATE DATABASE auto_enterprise_db;\nCREATE TABLE facts (id INT);\n"

        job = asyncio.run(data_source_router.import_data_source_sql(
            background_tasks=BackgroundTasks(),
            sql_file=sql_file,
            file_name="\u81ea\u52a8\u4f01\u4e1a-\u9500\u552e\u6570\u636e.sql",
            db=db,
            current_user=user,
        ))

        enterprise = crud.get_enterprise_by_name(db, "自动企业")
        self.assertIsNotNone(enterprise)
        self.assertEqual(job.enterprise_id, enterprise.id)
        self.assertEqual(job.data_source_name, "销售数据")
        db.close()
        engine.dispose()

    def test_sample_package_keeps_business_setup_but_removes_admin_and_validation_sql(self):
        sample_path = Path(__file__).resolve().parents[2] / "sql" / "星辰智造-运营数据.sql"

        prepared = data_source_import.prepare_sql_import(sample_path.read_text(encoding="utf-8"))
        statement_text = "\n".join(prepared.statements).upper()

        self.assertEqual(prepared.database_name, "xingchen_manufacturing")
        self.assertIn("CREATE TABLE `OPERATION_ORDERS`", statement_text)
        self.assertIn("CREATE PROCEDURE `SEED_XINGCHEN_OPERATIONS`", statement_text)
        self.assertIn("CALL `SEED_XINGCHEN_OPERATIONS`()", statement_text)
        self.assertNotIn("CREATE USER", statement_text)
        self.assertNotIn("GRANT SELECT", statement_text)
        self.assertNotIn("DROP TABLE", statement_text)
        self.assertNotIn("SHOW GRANTS", statement_text)

    def test_upload_rejects_destructive_or_multi_database_packages(self):
        destructive = """
        CREATE DATABASE safe_company;
        CREATE TABLE facts (id INT);
        DROP DATABASE bi_platform;
        """
        with self.assertRaises(data_source_import.DataSourceImportError):
            data_source_import.prepare_sql_import(destructive)

        multiple = """
        CREATE DATABASE company_a;
        CREATE DATABASE company_b;
        CREATE TABLE facts (id INT);
        """
        with self.assertRaises(data_source_import.DataSourceImportError):
            data_source_import.prepare_sql_import(multiple)

    def test_sqlyog_version_comments_and_on_update_ddl_are_supported(self):
        script = """
        /*!40101 SET NAMES utf8 */;
        CREATE DATABASE /*!32312 IF NOT EXISTS*/`agrinova`
          /*!40100 DEFAULT CHARACTER SET utf8 */;
        USE `agrinova`;
        CREATE TABLE `greenhouse` (
          `id` BIGINT NOT NULL AUTO_INCREMENT,
          `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
          PRIMARY KEY (`id`)
        ) ENGINE=InnoDB;
        """

        prepared = data_source_import.prepare_sql_import(script)

        self.assertEqual(prepared.database_name, "agrinova")
        self.assertEqual(len(prepared.statements), 1)
        self.assertIn("ON UPDATE CURRENT_TIMESTAMP", prepared.statements[0])

    def test_safe_foreign_key_on_delete_clause_does_not_allow_real_delete(self):
        safe = """
        CREATE DATABASE company_ops;
        CREATE TABLE parent (id INT PRIMARY KEY);
        CREATE TABLE child (
          id INT PRIMARY KEY,
          parent_id INT,
          CONSTRAINT fk_parent FOREIGN KEY (parent_id) REFERENCES parent(id) ON DELETE CASCADE
        );
        """
        prepared = data_source_import.prepare_sql_import(safe)
        self.assertEqual(prepared.database_name, "company_ops")

        dangerous = """
        CREATE DATABASE company_ops;
        CREATE TABLE facts (id INT);
        DELETE FROM facts;
        """
        with self.assertRaises(data_source_import.DataSourceImportError) as context:
            data_source_import.prepare_sql_import(dangerous)
        self.assertIn("不支持的语句", str(context.exception))

    def test_database_validation_distinguishes_missing_from_multiple(self):
        with self.assertRaises(data_source_import.DataSourceImportError) as missing:
            data_source_import.prepare_sql_import("CREATE TABLE facts (id INT);")
        self.assertIn("未找到", str(missing.exception))

        with self.assertRaises(data_source_import.DataSourceImportError) as multiple:
            data_source_import.prepare_sql_import(
                "CREATE DATABASE one_db;\nCREATE DATABASE two_db;\nCREATE TABLE facts (id INT);"
            )
        self.assertIn("包含 2 个", str(multiple.exception))

    def test_metric_system_prompt_requires_schema_grounded_expressions(self):
        prompt = data_source_import.METRIC_GENERATION_SYSTEM_PROMPT

        self.assertIn("禁止臆造字段", prompt)
        self.assertIn("sql_expr", prompt)
        self.assertIn("最多 4 个 dashboard_enabled=true", prompt)
        self.assertIn("禁止出现 SELECT、FROM、JOIN", prompt)

    def test_knowledge_system_prompt_requires_grounded_dictionary_and_rules(self):
        prompt = data_source_import.KNOWLEDGE_GENERATION_SYSTEM_PROMPT

        self.assertIn("数据字典", prompt)
        self.assertIn("分析规则", prompt)
        self.assertIn("禁止臆造字段", prompt)
        self.assertIn('"table"、"field"、"rule"、"question"', prompt)

    @patch.object(data_source_import.crud, "create_knowledge_documents")
    @patch.object(data_source_import, "_generated_metric_context", return_value="[]")
    @patch.object(data_source_import, "get_schema_catalog")
    @patch.object(data_source_import, "get_llm")
    def test_generated_dictionary_and_rules_are_bound_to_current_source(
        self,
        get_llm,
        get_schema_catalog,
        _metric_context,
        create_documents,
    ):
        get_schema_catalog.return_value = [{
            "table_name": "orders",
            "columns": [
                {"name": "id", "type": "BIGINT", "nullable": False, "comment": "主键"},
                {"name": "status", "type": "VARCHAR(20)", "nullable": False, "comment": "订单状态"},
            ],
        }]
        documents = [
            {"category": "table", "title": "订单表", "content": "orders 为订单表。", "related_tables": ["orders"]},
            {"category": "field", "title": "订单状态字段", "content": "orders.status 为订单状态。", "related_tables": ["orders"]},
            {"category": "rule", "title": "状态口径", "content": "orders.status 的枚举需业务确认。", "related_tables": ["orders"]},
            {"category": "rule", "title": "去重口径", "content": "orders 按 id 去重。", "related_tables": ["orders"]},
            {"category": "question", "title": "订单趋势", "content": "orders 缺少时间字段，需业务确认。", "related_tables": ["orders"]},
            {"category": "question", "title": "状态分布", "content": "orders 可按 status 分组。", "related_tables": ["orders"]},
        ]
        get_llm.return_value.invoke.return_value = SimpleNamespace(
            content=json.dumps({"documents": documents}, ensure_ascii=False)
        )
        create_documents.side_effect = lambda _db, payloads: payloads

        created = data_source_import.generate_knowledge_documents_for_data_source(
            MagicMock(), user_id=7, data_source_id=42
        )

        self.assertEqual(created, 6)
        payloads = create_documents.call_args.args[1]
        self.assertTrue(all(item.data_source_id == 42 for item in payloads))
        self.assertGreaterEqual(sum(item.category == "rule" for item in payloads), 2)

    @patch.object(data_source_import, "_verify_connection")
    @patch.object(data_source_import, "_database_exists", return_value=False)
    @patch.object(data_source_import, "create_engine")
    @patch.object(data_source_import, "_import_connection_settings")
    def test_import_never_changes_the_shared_platform_connection_schema(
        self,
        connection_settings,
        create_target_engine,
        _database_exists,
        _verify_connection,
    ):
        source = SimpleNamespace(
            db_type="mysql",
            host="localhost",
            port=3306,
            database="company_smoke",
            username="reader",
            password="secret",
            generated_reader=False,
        )
        admin_engine = MagicMock()
        admin_engine.url = make_url("mysql+pymysql://root@localhost/bi_platform")
        admin_connection = admin_engine.begin.return_value.__enter__.return_value
        target_engine = MagicMock()
        target_connection = target_engine.begin.return_value.__enter__.return_value
        target_connection.dialect.paramstyle = "pyformat"
        connection_settings.return_value = (source, admin_engine, False)
        create_target_engine.return_value = target_engine
        prepared = data_source_import.PreparedSQLImport(
            database_name="company_smoke",
            statements=(
                "CREATE TABLE facts (id INT, note VARCHAR(20) COMMENT '30%')",
                "INSERT INTO facts VALUES (1, DATE_FORMAT(NOW(), '%Y-%m'))",
            ),
        )

        result = data_source_import.import_new_database(prepared)

        self.assertEqual(result.database_name, "company_smoke")
        target_url = create_target_engine.call_args.args[0]
        self.assertEqual(target_url.database, "company_smoke")
        target_sql = [call.args[0] for call in target_connection.exec_driver_sql.call_args_list]
        self.assertEqual(target_sql, [statement.replace("%", "%%") for statement in prepared.statements])
        admin_sql = [str(call.args[0]).upper() for call in admin_connection.exec_driver_sql.call_args_list]
        self.assertFalse(any(statement.startswith("USE ") for statement in admin_sql))

    @patch.object(data_source_import, "_drop_new_database")
    @patch.object(data_source_import, "_database_exists", return_value=False)
    @patch.object(data_source_import, "create_engine")
    @patch.object(data_source_import, "_import_connection_settings")
    def test_unexpected_driver_failure_removes_the_partial_database(
        self,
        connection_settings,
        create_target_engine,
        _database_exists,
        drop_new_database,
    ):
        source = SimpleNamespace(
            db_type="mysql",
            host="localhost",
            port=3306,
            database="partial_company",
            username="reader",
            password="secret",
            generated_reader=False,
        )
        admin_engine = MagicMock()
        admin_engine.url = make_url("mysql+pymysql://root@localhost/bi_platform")
        target_engine = MagicMock()
        target_connection = target_engine.begin.return_value.__enter__.return_value
        target_connection.dialect.paramstyle = "pyformat"
        target_connection.exec_driver_sql.side_effect = ValueError("driver formatting failed")
        connection_settings.return_value = (source, admin_engine, False)
        create_target_engine.return_value = target_engine

        with self.assertRaises(data_source_import.DataSourceImportError) as context:
            data_source_import.import_new_database(
                data_source_import.PreparedSQLImport(
                    database_name="partial_company",
                    statements=("CREATE TABLE facts (note VARCHAR(20) COMMENT '30%')",),
                )
            )

        self.assertIn("数据库建设失败", str(context.exception))
        drop_new_database.assert_called_once_with(admin_engine, "partial_company")

    def test_backend_restart_cancels_stale_import_job(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        Session = sessionmaker(bind=engine)
        db = Session()
        user = User(username="importer", password="secret", role="admin")
        enterprise = Enterprise(name="恢复测试企业")
        db.add_all([user, enterprise])
        db.flush()
        job = DataSourceImportJob(
            user_id=user.id,
            enterprise_id=enterprise.id,
            data_source_name="未完成数据源",
            database_name="restart_smoke",
            file_name="restart.sql",
            status="processing",
            stage="building",
            progress=25,
            message="数据源建设中",
            database_created=False,
        )
        db.add(job)
        db.commit()
        job_id = job.id
        db.close()

        with patch.object(data_source_import, "SessionLocal", Session):
            aborted = data_source_import.abort_unfinished_data_source_imports()

        verify = Session()
        recovered = verify.get(DataSourceImportJob, job_id)
        self.assertEqual(aborted, 1)
        self.assertEqual(recovered.status, "cancelled")
        self.assertEqual(recovered.stage, "cancelled")
        self.assertEqual(recovered.progress, 0)
        verify.close()
        engine.dispose()

    def test_data_source_response_never_serializes_password(self):
        response = schemas.DataSourceResponse.model_validate(
            SimpleNamespace(
                id=1,
                name="业务库",
                db_type="mysql",
                host="localhost",
                port=3306,
                database="business_db",
                username="reader",
                password="must-not-leak",
                enterprise_id=1,
            )
        )

        self.assertNotIn("password", response.model_dump())

    def test_user_response_never_serializes_password(self):
        response = schemas.UserResponse.model_validate(
            SimpleNamespace(id=1, username="analyst", password="must-not-leak", role="analyst")
        )

        self.assertNotIn("password", response.model_dump())


class DataSourceLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        enterprise = Enterprise(name="删除流程测试企业")
        user = User(username="lifecycle-user", password="secret", role="admin")
        self.db.add_all([enterprise, user])
        self.db.flush()
        self.source = DataSource(
            name="待删除业务库", db_type="mysql", host="localhost", port=3306,
            database="lifecycle_db", username="reader", password="", enterprise_id=enterprise.id,
        )
        definition = MetricDefinition(name="生命周期销售额", topic="销售经营")
        self.db.add_all([self.source, definition])
        self.db.flush()
        self.binding = Metric(
            definition_id=definition.id,
            data_source_id=self.source.id,
            sql_expr="SUM(amount)",
        )
        self.document = KnowledgeDocument(
            category="rule",
            title="删除流程规则",
            content="测试内容",
            data_source_id=self.source.id,
        )
        self.conversation = Conversation(
            user_id=user.id,
            title="历史问数",
            data_source_id=self.source.id,
        )
        self.report = ReportDraft(
            user_id=user.id,
            title="历史报告",
            data_source_id=self.source.id,
            content_json="{}",
        )
        self.db.add_all([self.binding, self.document, self.conversation, self.report])
        self.db.commit()
        self.source_id = self.source.id
        self.definition_id = definition.id

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_disconnect_hides_source_but_preserves_database_metadata_and_metrics(self):
        crud.disconnect_data_source(self.db, self.source_id)

        stored = crud.get_data_source(self.db, self.source_id, include_inactive=True)
        self.assertFalse(stored.is_active)
        self.assertIsNone(crud.get_data_source(self.db, self.source_id))
        self.assertEqual(self.db.query(Metric).filter_by(data_source_id=self.source_id).count(), 1)
        self.assertEqual(stored.database, "lifecycle_db")

    def test_full_delete_cleans_bindings_and_preserves_history_without_source_link(self):
        result = crud.delete_data_source(self.db, self.source_id)

        self.assertEqual(result["metrics_deleted"], 1)
        self.assertEqual(result["knowledge_deleted"], 1)
        self.assertIsNone(crud.get_data_source(self.db, self.source_id, include_inactive=True))
        self.assertIsNone(self.db.get(MetricDefinition, self.definition_id))
        self.assertIsNone(self.db.get(Conversation, self.conversation.id).data_source_id)
        self.assertIsNone(self.db.get(ReportDraft, self.report.id).data_source_id)

    @patch.object(data_source_router, "build_knowledge_base", return_value={})
    @patch.object(data_source_router, "drop_data_source_database")
    @patch.object(data_source_router.crud, "delete_data_source", return_value={"metrics_deleted": 2, "knowledge_deleted": 1})
    @patch.object(data_source_router.crud, "get_data_source")
    def test_full_route_drops_database_only_after_explicit_mode(
        self, get_source, delete_source, drop_database, _rebuild
    ):
        get_source.return_value = self.source

        result = data_source_router.delete_data_source(self.source_id, mode="full", db=self.db)

        drop_database.assert_called_once_with(self.source)
        delete_source.assert_called_once_with(self.db, self.source_id)
        self.assertTrue(result["database_deleted"])
        self.assertEqual(result["metrics_deleted"], 2)

    @patch.object(data_source_router, "build_knowledge_base", return_value={})
    @patch.object(data_source_router, "drop_data_source_database")
    @patch.object(data_source_router.crud, "disconnect_data_source")
    @patch.object(data_source_router.crud, "get_data_source")
    def test_disconnect_route_never_drops_business_database(
        self, get_source, disconnect, drop_database, _rebuild
    ):
        get_source.return_value = self.source

        result = data_source_router.delete_data_source(self.source_id, mode="disconnect", db=self.db)

        disconnect.assert_called_once_with(self.db, self.source_id)
        drop_database.assert_not_called()
        self.assertFalse(result["database_deleted"])
        self.assertEqual(result["metrics_deleted"], 0)

    def test_platform_database_can_never_be_dropped(self):
        source = SimpleNamespace(
            db_type="mysql",
            host="localhost",
            port=3306,
            database=data_source_provisioning.platform_engine.url.database,
        )

        with self.assertRaises(data_source_provisioning.DataSourceProvisioningError) as context:
            data_source_provisioning.drop_data_source_database(source)

        self.assertIn("平台自身数据库", str(context.exception))


class MultiEnterpriseTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.db = self.Session()
        self.first = Enterprise(name="甲企业")
        self.second = Enterprise(name="乙企业")
        self.db.add_all([self.first, self.second])
        self.db.flush()
        self.db.add_all([
            DataSource(
                name="甲销售库", db_type="mysql", host="localhost", port=3306,
                database="a_sales", username="reader", password="", enterprise_id=self.first.id,
            ),
            DataSource(
                name="乙经营库", db_type="mysql", host="localhost", port=3306,
                database="b_ops", username="reader", password="", enterprise_id=self.second.id,
            ),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_enterprise_list_keeps_distinct_enterprises(self):
        records = enterprise_router.read_enterprises(db=self.db)

        self.assertEqual([record.name for record in records], ["甲企业", "乙企业"])

    def test_filename_enterprise_reuses_existing_catalog_record(self):
        matched = crud.get_enterprise_by_name(self.db, " 甲企业 ")

        self.assertEqual(matched.id, self.first.id)

    def test_enterprise_data_sources_only_returns_children(self):
        records = enterprise_router.read_enterprise_data_sources(self.first.id, db=self.db)

        self.assertEqual([record.name for record in records], ["甲销售库"])

    def test_duplicate_enterprise_name_is_rejected(self):
        with self.assertRaises(HTTPException) as context:
            enterprise_router.create_enterprise(schemas.EnterpriseCreate(name=" 甲企业 "), db=self.db)

        self.assertEqual(context.exception.status_code, 409)

    def test_empty_enterprise_deletion_removes_orphan_import_history(self):
        empty_enterprise = Enterprise(name="可删除测试企业")
        user = User(username="orphan-import-user", password="secret", role="admin")
        self.db.add_all([empty_enterprise, user])
        self.db.flush()
        job = DataSourceImportJob(
            user_id=user.id,
            enterprise_id=empty_enterprise.id,
            data_source_name="失败数据源",
            file_name="可删除测试企业-失败数据源.sql",
            status="failed",
            stage="failed",
            progress=25,
            message="接入失败",
        )
        self.db.add(job)
        self.db.commit()
        enterprise_id = empty_enterprise.id
        job_id = job.id

        deleted = enterprise_router.delete_enterprise(enterprise_id, db=self.db)

        self.assertEqual(deleted["detail"], "deleted")
        self.assertIsNone(self.db.get(Enterprise, enterprise_id))
        self.assertIsNone(self.db.get(DataSourceImportJob, job_id))


class UserLLMConfigurationTests(unittest.TestCase):
    @patch.object(llm_config_router, "reset_llm_cache")
    @patch.object(llm_config_router.crud, "upsert_user_llm_config")
    @patch.object(llm_config_router.crud, "get_user", return_value=SimpleNamespace(id=2))
    def test_key_update_hot_refreshes_only_that_user(self, _user, upsert, reset):
        upsert.return_value = SimpleNamespace(updated_at=None)
        payload = schemas.LLMConfigUpdate(user_id=2, api_key="sk-new-key-123")

        result = llm_config_router.configure_llm(payload, db=MagicMock())

        upsert.assert_called_once_with(unittest.mock.ANY, 2, "sk-new-key-123")
        reset.assert_called_once_with(2)
        self.assertTrue(result.configured)
        self.assertNotIn("api_key", result.model_dump())


class PersistenceWorkflowTests(unittest.TestCase):
    def setUp(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        self.db = sessionmaker(bind=engine)()
        enterprise = Enterprise(name="测试企业")
        user = User(username="history-user", password="secret", role="analyst")
        self.db.add_all([enterprise, user])
        self.db.flush()
        source = DataSource(
            name="测试业务库",
            db_type="mysql",
            host="localhost",
            port=3306,
            database="business_db",
            username="reader",
            password="",
            enterprise_id=enterprise.id,
        )
        self.db.add(source)
        self.db.commit()
        self.user_id = user.id
        self.source_id = source.id

    def tearDown(self):
        self.db.close()

    def test_conversation_round_trip_persists_structured_chart_payload(self):
        created = conversation_router.create_conversation(
            schemas.ConversationCreate(
                user_id=self.user_id,
                title="各厂商销售额",
                data_source_id=self.source_id,
            ),
            db=self.db,
        )
        conversation_router.append_message(
            created.id,
            schemas.ConversationMessageCreate(
                user_id=self.user_id,
                role="assistant",
                content="销售额分析完成",
                payload={"sql": "SELECT 1", "data": {"columns": ["厂商"], "rows": [["A"]]}},
            ),
            db=self.db,
        )

        detail = conversation_router.get_conversation(created.id, self.user_id, db=self.db)

        self.assertEqual(detail.message_count, 1)
        self.assertEqual(detail.messages[0].payload["sql"], "SELECT 1")
        self.assertEqual(len(conversation_router.list_conversations(self.user_id, db=self.db)), 1)
        conversation_router.delete_conversation(created.id, self.user_id, db=self.db)
        self.assertEqual(self.db.query(Conversation).count(), 0)

    def test_report_saves_an_immutable_version_on_each_update(self):
        created = report_router.create_report(
            schemas.ReportDraftCreate(
                user_id=self.user_id,
                title="月度经营报告",
                data_source_id=self.source_id,
                period="quarter",
                content={"findings": ["第一版"]},
            ),
            db=self.db,
        )
        updated = report_router.update_report(
            created.id,
            schemas.ReportDraftUpdate(
                user_id=self.user_id,
                title="月度经营报告",
                data_source_id=self.source_id,
                period="quarter",
                content={"findings": ["第二版"]},
            ),
            db=self.db,
        )

        self.assertEqual(updated.version_count, 2)
        self.assertEqual([version.version_number for version in updated.versions], [2, 1])
        self.assertEqual(updated.versions[1].content["findings"], ["第一版"])
        report_router.delete_report(created.id, self.user_id, db=self.db)
        self.assertEqual(self.db.query(ReportDraft).count(), 0)


class DashboardTests(unittest.TestCase):
    def configured_metrics(self):
        definitions = [
            (1, "销售额", "SUM(amount)", "¥"),
            (2, "订单量", "COUNT(*)", "单"),
            (3, "客户数", "COUNT(DISTINCT customer_name)", "人"),
            (4, "订单完成率", "SUM(status='paid') / COUNT(*)", "%"),
        ]
        return [
            {
                "record": SimpleNamespace(
                    id=metric_id, name=name, sql_expr=sql_expr, unit=unit, topic="经营"
                ),
                "table": "orders",
                "time_field": "created_at",
                "dimension_field": "customer_name",
            }
            for metric_id, name, sql_expr, unit in definitions
        ]

    def dashboard_patches(self):
        return (
            patch.object(dashboard_router, "get_data_source", return_value=SimpleNamespace(id=7)),
            patch.object(dashboard_router, "_configured_metrics", return_value=self.configured_metrics()),
        )

    @patch.object(dashboard_router, "execute_sql")
    def test_dashboard_uses_real_completion_rate(self, execute_sql):
        execute_sql.side_effect = [
            {"rows": [[1000]]}, {"rows": [[4]]}, {"rows": [[3]]}, {"rows": [[0.75]]},
            {"rows": [["2026-07", 800], ["2026-08", 1000]]},
            {"rows": [["客户A", 3], ["客户B", 1]]},
        ]
        source_patch, metric_patch = self.dashboard_patches()
        with source_patch, metric_patch:
            result = dashboard_router.dashboard(data_source_id=7)

        self.assertEqual(result["completionRate"], 75.0)
        self.assertEqual(result["trendData"]["x"], ["2026-07", "2026-08"])
        self.assertEqual(result["pieData"][0], {"name": "客户A", "value": 3})
        self.assertEqual(result["deltas"]["totalSales"], 25.0)
        self.assertEqual(result["insights"]["status"], "unconfigured")
        self.assertTrue(all(call.kwargs["data_source_id"] == 7 for call in execute_sql.call_args_list))

    @patch.object(dashboard_router, "execute_sql")
    def test_dashboard_period_is_applied_to_every_query(self, execute_sql):
        execute_sql.side_effect = [
            {"rows": [[1000]]}, {"rows": [[4]]}, {"rows": [[3]]}, {"rows": [[0.75]]},
            {"rows": [["2026-08", 1000]]},
            {"rows": [["客户A", 4]]},
        ]
        source_patch, metric_patch = self.dashboard_patches()
        with source_patch, metric_patch:
            result = dashboard_router.dashboard(data_source_id=3, include_insights=False, period="quarter")

        self.assertEqual(result["period"], "quarter")
        for call in execute_sql.call_args_list:
            self.assertIn("INTERVAL MOD(MONTH(CURDATE()) - 1, 3) MONTH", call.args[0])

    @patch.object(dashboard_router, "get_llm")
    @patch.object(dashboard_router, "execute_sql")
    def test_dashboard_uses_current_users_api_for_insights(self, execute_sql, get_llm):
        execute_sql.side_effect = [
            {"rows": [[1000]]}, {"rows": [[4]]}, {"rows": [[3]]}, {"rows": [[0.75]]},
            {"rows": [["2026-08", 1000]]},
            {"rows": [["客户A", 4]]},
        ]
        get_llm.return_value.invoke.return_value = SimpleNamespace(
            content='{"insights":[{"title":"订单集中","content":"客户A有4单。","recommendation":"持续跟踪。"}]}'
        )

        source_patch, metric_patch = self.dashboard_patches()
        with source_patch, metric_patch:
            result = dashboard_router.dashboard(data_source_id=3, user_id=2)

        self.assertEqual(result["insights"]["status"], "ready")
        self.assertEqual(result["insights"]["items"][0]["title"], "订单集中")
        get_llm.assert_called_once_with(2)

    @patch.object(dashboard_router, "get_llm")
    @patch.object(dashboard_router, "execute_sql")
    def test_dashboard_can_return_data_before_insights_finish(self, execute_sql, get_llm):
        execute_sql.side_effect = [
            {"rows": [[1000]]}, {"rows": [[4]]}, {"rows": [[3]]}, {"rows": [[0.75]]},
            {"rows": [["2026-08", 1000]]},
            {"rows": [["客户A", 4]]},
        ]
        source_patch, metric_patch = self.dashboard_patches()
        with source_patch, metric_patch:
            result = dashboard_router.dashboard(data_source_id=3, user_id=2, include_insights=False)

        self.assertEqual(result["totalSales"], 1000)
        self.assertEqual(result["insights"]["status"], "pending")
        get_llm.assert_not_called()

    @patch.object(dashboard_router, "execute_sql", return_value={"error": "no data source"})
    def test_dashboard_returns_503_instead_of_key_error(self, _execute_sql):
        source_patch, metric_patch = self.dashboard_patches()
        with source_patch, metric_patch, self.assertRaises(HTTPException) as context:
            dashboard_router.dashboard(data_source_id=9)

        self.assertEqual(context.exception.status_code, 503)
        self.assertIn("no data source", context.exception.detail["message"])


if __name__ == "__main__":
    unittest.main()
