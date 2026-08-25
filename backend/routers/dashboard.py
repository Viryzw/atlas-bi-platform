import json
import re
from typing import Annotated, Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from database import SessionLocal
from llm_config import LLMConfigurationError, get_llm
from models import Metric
from models import User
from security import get_current_user, require_same_user_or_admin
from query_engine import execute_sql, get_data_source, get_schema_catalog


router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])
DashboardPeriod = Literal["year", "six_months", "quarter", "all"]
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
FORBIDDEN_FRAGMENT = re.compile(
    r";|--|/\*|\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE)\b",
    re.IGNORECASE,
)


def _identifier(value: str) -> str:
    clean = (value or "").strip()
    if not IDENTIFIER.fullmatch(clean):
        raise ValueError(f"指标看板配置包含非法标识符：{value}")
    return f"`{clean}`"


def _metric_expression(value: str) -> str:
    clean = (value or "").strip()
    if not clean or FORBIDDEN_FRAGMENT.search(clean):
        raise ValueError("指标 SQL 表达式为空或包含非只读内容")
    return clean


def _period_condition(period: DashboardPeriod, time_field: Optional[str]) -> str:
    if not time_field or period == "all":
        return "1 = 1"
    field = _identifier(time_field)
    return {
        "year": f"{field} >= DATE_FORMAT(CURDATE(), '%Y-01-01')",
        "six_months": f"{field} >= DATE_SUB(DATE_FORMAT(CURDATE(), '%Y-%m-01'), INTERVAL 5 MONTH)",
        "quarter": f"{field} >= DATE_SUB(DATE_FORMAT(CURDATE(), '%Y-%m-01'), INTERVAL MOD(MONTH(CURDATE()) - 1, 3) MONTH)",
        "all": "1 = 1",
    }[period]


def _query_rows(sql: str, label: str, data_source_id: int, parameters: Optional[Dict[str, Any]] = None) -> List[List[Any]]:
    result = execute_sql(sql, data_source_id=data_source_id, parameters=parameters) if parameters else execute_sql(sql, data_source_id=data_source_id)
    if result.get("error"):
        raise HTTPException(
            status_code=503,
            detail={"stage": "data_query", "message": f"读取{label}失败：{result['error']}"},
        )
    rows = result.get("rows")
    if not isinstance(rows, list):
        raise HTTPException(status_code=503, detail={"stage": "data_query", "message": f"读取{label}失败：返回格式不完整"})
    return rows


def _load_metrics(data_source_id: int) -> List[Metric]:
    db = SessionLocal()
    try:
        return (
            db.query(Metric)
            .filter(Metric.data_source_id == data_source_id, Metric.dashboard_enabled.is_(True))
            .order_by(Metric.id.asc())
            .limit(8)
            .all()
        )
    finally:
        db.close()


def _column_names(table: Dict[str, Any]) -> set[str]:
    return {column["name"] for column in table.get("columns", [])}


def _resolve_table(metric: Metric, tables: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    configured = (metric.base_table or "").strip()
    if configured:
        return next((table for table in tables if table["table_name"] == configured), None)
    tokens = set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", metric.sql_expr or ""))
    ranked = sorted(tables, key=lambda table: len(tokens & _column_names(table)), reverse=True)
    return ranked[0] if ranked else None


def _resolve_field(configured: Optional[str], table: Dict[str, Any], kind: str) -> Optional[str]:
    names = _column_names(table)
    if configured and configured in names:
        return configured
    columns = table.get("columns", [])
    if kind == "time":
        name_pattern = re.compile(r"date|time|created|month|year|日期|时间", re.IGNORECASE)
        return next((column["name"] for column in columns if name_pattern.search(column["name"]) or re.search(r"DATE|TIME", column["type"], re.IGNORECASE)), None)
    priorities = ("customer_name", "vendor_name", "company_name", "region", "category", "name")
    for candidate in priorities:
        if candidate in names:
            return candidate
    return next((column["name"] for column in columns if re.search(r"CHAR|TEXT|STRING", column["type"], re.IGNORECASE) and column["name"] not in {"status"}), None)


def _configured_metrics(data_source_id: int) -> List[Dict[str, Any]]:
    tables = get_schema_catalog(data_source_id)
    configured = []
    for metric in _load_metrics(data_source_id):
        table = _resolve_table(metric, tables)
        if table is None:
            continue
        configured.append({
            "record": metric,
            "table": table["table_name"],
            "time_field": _resolve_field(metric.time_field, table, "time"),
            "dimension_field": _resolve_field(metric.dimension_field, table, "dimension"),
        })
    return configured


def _display_value(value: Any, name: str, unit: str) -> Any:
    if value is None:
        return 0
    if unit == "%" or (not unit and "率" in name):
        try:
            numeric = float(value)
            return round(numeric * 100, 2) if abs(numeric) <= 1 else round(numeric, 2)
        except (TypeError, ValueError):
            return value
    return value


def _percent_delta(current: Any, previous: Any) -> Optional[float]:
    try:
        current_value, previous_value = float(current), float(previous)
        if previous_value == 0:
            return None
        return round(100 * (current_value - previous_value) / abs(previous_value), 2)
    except (TypeError, ValueError):
        return None


def _parse_json_object(content: str) -> Dict[str, Any]:
    value = (content or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", value, re.DOTALL | re.IGNORECASE)
    if fenced:
        value = fenced.group(1)
    else:
        start, end = value.find("{"), value.rfind("}")
        if start >= 0 and end > start:
            value = value[start:end + 1]
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("经营洞察模型没有返回 JSON 对象")
    return parsed


def _generate_insights(user_id: Optional[int], data_source_id: int, kpis: list, trend_rows: list, breakdown_rows: list) -> Dict[str, Any]:
    if user_id is None:
        return {"status": "unconfigured", "message": "前往智能问数模块配置API", "items": []}
    try:
        llm = get_llm(user_id)
    except LLMConfigurationError:
        return {"status": "unconfigured", "message": "前往智能问数模块配置API", "items": []}
    prompt = f"""
你是经营驾驶舱的数据分析助手。仅根据真实指标结果生成 3 条简洁经营洞察，禁止编造。
每条包含标题、说明和可执行建议。只返回 JSON：
{{"insights":[{{"title":"...","content":"...","recommendation":"..."}}]}}。
数据源 ID：{data_source_id}
指标：{json.dumps(kpis, ensure_ascii=False)}
趋势：{json.dumps(trend_rows, ensure_ascii=False)}
维度分布：{json.dumps(breakdown_rows, ensure_ascii=False)}
"""
    try:
        parsed = _parse_json_object(llm.invoke(prompt).content)
        items = []
        for item in list(parsed.get("insights") or [])[:3]:
            if isinstance(item, dict) and str(item.get("content") or "").strip():
                items.append({
                    "title": str(item.get("title") or "经营洞察").strip(),
                    "content": str(item.get("content") or "").strip(),
                    "recommendation": str(item.get("recommendation") or "").strip(),
                })
        if not items:
            raise ValueError("经营洞察模型未返回有效内容")
        return {"status": "ready", "message": "", "items": items}
    except Exception as exc:
        return {"status": "error", "message": f"经营洞察生成失败：{exc}", "items": []}


@router.get("/")
def dashboard(
    data_source_id: Annotated[Optional[int], Query(gt=0)] = None,
    user_id: Annotated[Optional[int], Query(gt=0)] = None,
    include_insights: bool = True,
    period: DashboardPeriod = "year",
    dimension_value: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    if isinstance(current_user, User):
        if user_id is not None:
            require_same_user_or_admin(current_user, user_id)
        user_id = int(current_user.id)
    source = get_data_source(data_source_id)
    if source is None:
        raise HTTPException(status_code=404, detail={"message": "没有可用数据源"})
    source_id = int(source.id)
    metrics = _configured_metrics(source_id)
    if not metrics:
        raise HTTPException(status_code=409, detail={"message": "当前数据源尚未配置可用于驾驶舱的业务指标"})

    primary = next((item for item in metrics[:4] if item["time_field"]), metrics[0])
    primary_dimension = primary["dimension_field"]
    kpis = []
    for item in metrics[:4]:
        metric = item["record"]
        condition = _period_condition(period, item["time_field"])
        parameters = None
        if dimension_value and item["dimension_field"] == primary_dimension:
            condition += f" AND {_identifier(item['dimension_field'])} = :dimension_value"
            parameters = {"dimension_value": dimension_value}
        sql = f"SELECT {_metric_expression(metric.sql_expr)} AS metric_value FROM {_identifier(item['table'])} WHERE {condition}"
        rows = _query_rows(sql, metric.name, source_id, parameters)
        value = rows[0][0] if rows and rows[0] else 0
        kpis.append({
            "id": metric.id,
            "name": metric.name,
            "topic": metric.topic or "未分类",
            "value": _display_value(value, metric.name, metric.unit or ""),
            "unit": metric.unit or ("%" if "率" in metric.name else ""),
            "delta": None,
        })

    metric = primary["record"]
    trend_rows: List[List[Any]] = []
    if primary["time_field"]:
        condition = _period_condition(period, primary["time_field"])
        parameters = None
        if dimension_value and primary_dimension:
            condition += f" AND {_identifier(primary_dimension)} = :dimension_value"
            parameters = {"dimension_value": dimension_value}
        trend_sql = (
            f"SELECT DATE_FORMAT({_identifier(primary['time_field'])}, '%Y-%m') AS period, "
            f"{_metric_expression(metric.sql_expr)} AS metric_value "
            f"FROM {_identifier(primary['table'])} WHERE {condition} GROUP BY period ORDER BY period"
        )
        trend_rows = _query_rows(trend_sql, f"{metric.name}趋势", source_id, parameters)
        trend_rows = [[row[0], _display_value(row[1], metric.name, metric.unit or "")] for row in trend_rows]
        if len(trend_rows) >= 2:
            kpis[metrics.index(primary)]["delta"] = _percent_delta(trend_rows[-1][1], trend_rows[-2][1])

    breakdown_rows: List[List[Any]] = []
    if primary_dimension:
        condition = _period_condition(period, primary["time_field"])
        breakdown_sql = (
            f"SELECT {_identifier(primary_dimension)} AS dimension_value, "
            f"{_metric_expression(metric.sql_expr)} AS metric_value "
            f"FROM {_identifier(primary['table'])} WHERE {condition} "
            "GROUP BY dimension_value ORDER BY metric_value DESC LIMIT 12"
        )
        breakdown_rows = _query_rows(breakdown_sql, f"{metric.name}维度分布", source_id)
        breakdown_rows = [[row[0], _display_value(row[1], metric.name, metric.unit or "")] for row in breakdown_rows]

    insights = _generate_insights(user_id, source_id, kpis, trend_rows, breakdown_rows) if include_insights else {"status": "pending", "message": "正在生成经营洞察", "items": []}
    by_name = {item["name"]: item["value"] for item in kpis}
    return {
        "dataSourceId": source_id,
        "period": period,
        "kpis": kpis,
        "primaryMetric": {"id": metric.id, "name": metric.name, "unit": metric.unit or ""},
        "dimension": {"field": primary_dimension, "selected": dimension_value},
        "trendData": {"x": [row[0] for row in trend_rows], "y": [row[1] for row in trend_rows]},
        "pieData": [{"name": row[0], "value": row[1]} for row in breakdown_rows],
        "totalSales": by_name.get("销售额", kpis[0]["value"] if kpis else 0),
        "orderCount": by_name.get("订单量", 0),
        "customerCount": by_name.get("客户数", 0),
        "completionRate": by_name.get("订单完成率", by_name.get("完成率", 0)),
        "deltas": {"totalSales": kpis[0].get("delta") if kpis else None},
        "insights": insights,
    }
