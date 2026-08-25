import unittest
from unittest.mock import patch

import agent_tools
from security import hash_password, verify_password
from routers.auth import LoginRequest
from query_engine import normalize_read_only_sql
from sql_agent import _normalise_plan


class ReadOnlySQLTests(unittest.TestCase):
    def test_select_and_cte_are_allowed(self):
        self.assertEqual(normalize_read_only_sql("SELECT * FROM orders;"), "SELECT * FROM orders")
        self.assertTrue(normalize_read_only_sql("WITH paid AS (SELECT 1) SELECT * FROM paid").startswith("WITH"))

    def test_write_and_multiple_statements_are_rejected(self):
        for statement in (
            "DELETE FROM orders",
            "DROP TABLE orders",
            "SELECT * FROM orders; DELETE FROM orders",
        ):
            with self.subTest(statement=statement), self.assertRaises(ValueError):
                normalize_read_only_sql(statement)

    def test_sql_agent_adds_a_result_limit(self):
        plan = _normalise_plan(
            {
                "intent": "查询订单",
                "request_type": "sql",
                "sql": "SELECT * FROM orders",
            },
            "查询订单",
        )
        self.assertIn("LIMIT 500", plan["sql"])


class PasswordCompatibilityTests(unittest.TestCase):
    def test_short_legacy_password_can_be_upgraded(self):
        encoded = hash_password("123")
        valid, needs_rehash = verify_password("123", encoded)
        self.assertTrue(valid)
        self.assertFalse(needs_rehash)

    def test_long_password_has_no_request_length_cap(self):
        value = "x" * 1000
        self.assertEqual(LoginRequest(username="admin", password=value).password, value)
        encoded = hash_password(value)
        self.assertTrue(verify_password(value, encoded)[0])


class AnalysisToolTests(unittest.TestCase):
    def test_pie_chart_uses_real_rows(self):
        data = {
            "columns": ["customer", "orders"],
            "rows": [["A", 6], ["B", 4]],
            "row_count": 2,
        }
        option = agent_tools.generate_chart_tool(data, chart_type="pie", title="客户占比")
        self.assertEqual(option["series"][0]["type"], "pie")
        self.assertEqual(option["series"][0]["data"][0], {"name": "A", "value": 6})

    def test_anomaly_is_deterministic(self):
        data = {
            "columns": ["month", "sales"],
            "rows": [["2026-07", 100], ["2026-08", 150]],
        }
        anomaly = agent_tools.detect_anomaly_tool(data)
        self.assertEqual(anomaly["change_percent"], 50.0)
        self.assertTrue(anomaly["is_anomaly"])


class AnalysisAgentPipelineTests(unittest.TestCase):
    @patch.object(agent_tools, "analyse_result_tool")
    @patch.object(agent_tools, "execute_sql")
    @patch.object(agent_tools, "create_query_plan")
    def test_analysis_agent_calls_sql_agent_then_query_and_returns_artifacts(
        self,
        create_query_plan,
        execute_sql,
        analyse_result,
    ):
        create_query_plan.return_value = {
            "status": "success",
            "sql": "SELECT customer_name, COUNT(*) AS orders FROM orders GROUP BY customer_name LIMIT 500",
            "plan": {
                "intent": "客户订单量占比",
                "request_type": "metric",
                "analysis_type": "share",
                "chart_type": "pie",
                "chart_title": "客户订单量占比",
                "needs_anomaly": False,
                "needs_attribution": False,
                "needs_report": False,
            },
        }
        execute_sql.return_value = {
            "columns": ["customer_name", "orders"],
            "rows": [["A", 6], ["B", 4]],
            "row_count": 2,
        }
        analyse_result.return_value = {
            "summary": "A 客户订单量占 60%。",
            "insights": ["A 高于 B"],
        }

        result = agent_tools.run_agent("各客户订单量占比是多少？")

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["plan"]["intent"], "客户订单量占比")
        self.assertEqual(result["data"]["row_count"], 2)
        self.assertEqual(result["chart_config"]["series"][0]["type"], "pie")
        self.assertNotIn("tool_trace", result)
        create_query_plan.assert_called_once_with("各客户订单量占比是多少？")
        execute_sql.assert_called_once_with(create_query_plan.return_value["sql"])

    @patch.object(agent_tools, "execute_sql")
    @patch.object(agent_tools, "create_query_plan")
    def test_query_failure_stops_before_analysis(self, create_query_plan, execute_sql):
        create_query_plan.return_value = {
            "status": "success",
            "sql": "SELECT * FROM orders LIMIT 500",
            "plan": {"intent": "订单查询"},
        }
        execute_sql.return_value = {"error": "table not found"}

        result = agent_tools.run_agent("查询订单")

        self.assertEqual(result["status"], "error")
        self.assertEqual(result["stage"], "data_query")
        self.assertNotIn("tool_trace", result)

    @patch.object(agent_tools, "analyse_result_tool")
    @patch.object(agent_tools, "execute_sql")
    @patch.object(agent_tools, "create_query_plan")
    def test_selected_data_source_flows_through_planning_and_execution(
        self, create_query_plan, execute_sql, analyse_result
    ):
        create_query_plan.return_value = {
            "status": "success",
            "sql": "SELECT COUNT(*) AS orders FROM orders LIMIT 500",
            "plan": {
                "intent": "订单量",
                "analysis_type": "summary",
                "chart_type": "none",
            },
        }
        execute_sql.return_value = {
            "columns": ["orders"],
            "rows": [[36]],
            "row_count": 1,
        }
        analyse_result.return_value = {"summary": "共 36 单。", "insights": []}

        result = agent_tools.run_agent(
            "订单量是多少？",
            user_id=1,
            data_source_id=2,
        )

        self.assertEqual(result["data_source_id"], 2)
        create_query_plan.assert_called_once_with(
            "订单量是多少？",
            user_id=1,
            data_source_id=2,
        )
        execute_sql.assert_called_once_with(
            create_query_plan.return_value["sql"],
            data_source_id=2,
        )


if __name__ == "__main__":
    unittest.main()
