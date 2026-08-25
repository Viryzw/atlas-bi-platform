"""SQL Agent: natural language -> query plan -> safe SQL.

SQL Agent never executes SQL. The Analysis Agent owns orchestration and calls
the data-query layer after this module has produced a validated plan.
"""

import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from llm_config import get_llm
from query_engine import get_table_info, normalize_read_only_sql


DEFAULT_ROW_LIMIT = 500


def _knowledge_context(
    question: str,
    data_source_id: Optional[int] = None,
) -> Tuple[str, List[Dict[str, Any]]]:
    text_value = "无匹配的知识"
    metric_bindings: List[Dict[str, Any]] = []
    try:
        # Lazy import avoids loading the local embedding model for endpoints
        # that do not use SQL Agent and keeps test/startup time predictable.
        from knowledge_base import retrieve_knowledge

        documents: Iterable[Any] = retrieve_knowledge(
            question,
            k=6,
            data_source_id=data_source_id,
        )
        text_value = "\n\n".join(document.page_content for document in documents) or text_value
    except Exception:
        # Missing/empty vector data must not prevent schema-grounded querying.
        pass
    try:
        # Hard metric enforcement is sourced from the canonical relational
        # table and therefore remains active even if the vector index is down.
        from knowledge_base import get_exact_metric_bindings

        metric_bindings = get_exact_metric_bindings(
            question,
            data_source_id=data_source_id,
        )
    except Exception:
        pass
    return text_value, metric_bindings


def _knowledge_text(question: str) -> str:
    """Compatibility helper used by tests and diagnostics."""

    return _knowledge_context(question)[0]


def _normalise_sql_fragment(value: str) -> str:
    return re.sub(r"\s+", "", (value or "").replace("`", "").strip()).casefold()


def validate_metric_sql(sql: str, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Require named metric expressions to appear unchanged in generated SQL."""

    normalized_sql = _normalise_sql_fragment(sql)
    checked = []
    reference_only = []
    violations = []
    for metric in metrics:
        expression = (metric.get("sql_expr") or "").strip()
        item = {"metric_id": metric["metric_id"], "name": metric["name"]}
        if not expression or re.match(r"^(SELECT|WITH)\b", expression, re.IGNORECASE):
            reference_only.append(item)
            continue
        checked.append(item)
        if _normalise_sql_fragment(expression) not in normalized_sql:
            violations.append({**item, "required_expression": expression})

    if violations:
        status = "failed"
    elif checked:
        status = "passed"
    elif reference_only:
        status = "reference_only"
    else:
        status = "not_matched"
    return {
        "status": status,
        "passed": not violations,
        "checked": checked,
        "reference_only": reference_only,
        "violations": violations,
    }


def _extract_json(content: str) -> Dict[str, Any]:
    text_value = (content or "").strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text_value, re.DOTALL | re.IGNORECASE)
    if fenced:
        text_value = fenced.group(1)
    else:
        start = text_value.find("{")
        end = text_value.rfind("}")
        if start >= 0 and end > start:
            text_value = text_value[start:end + 1]
    parsed = json.loads(text_value)
    if not isinstance(parsed, dict):
        raise ValueError("SQL Agent 没有返回 JSON 对象")
    return parsed


def _with_limit(sql: str) -> str:
    normalized = normalize_read_only_sql(sql)
    if not re.search(r"\bLIMIT\s+\d+\b", normalized, re.IGNORECASE):
        normalized = f"{normalized}\nLIMIT {DEFAULT_ROW_LIMIT}"
    return normalize_read_only_sql(normalized)


def _normalise_plan(raw: Dict[str, Any], question: str) -> Dict[str, Any]:
    sql = _with_limit(str(raw.get("sql", "")))
    request_type = raw.get("request_type")
    if request_type not in {"sql", "metric"}:
        request_type = "metric" if raw.get("metrics") else "sql"

    chart_type = str(raw.get("chart_type", "auto")).lower()
    if chart_type not in {"auto", "none", "line", "bar", "pie"}:
        chart_type = "auto"

    return {
        "question": question,
        "intent": str(raw.get("intent") or "业务数据查询"),
        "request_type": request_type,
        "metrics": list(raw.get("metrics") or []),
        "dimensions": list(raw.get("dimensions") or []),
        "filters": list(raw.get("filters") or []),
        "analysis_type": str(raw.get("analysis_type") or "summary"),
        "chart_type": chart_type,
        "chart_title": str(raw.get("chart_title") or raw.get("intent") or "分析结果"),
        "needs_anomaly": bool(raw.get("needs_anomaly", False)),
        "needs_attribution": bool(raw.get("needs_attribution", False)),
        "needs_report": bool(raw.get("needs_report", False)),
        "sql": sql,
        "steps": [
            "理解问题并匹配指标口径",
            "根据业务表结构生成只读 SQL",
            "执行查询并将结果交给分析 Agent",
        ],
    }


def create_query_plan(
    question: str,
    user_id: Optional[int] = None,
    data_source_id: Optional[int] = None,
    conversation_context: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """Translate one business question into a validated structured plan."""

    clean_question = (question or "").strip()
    if not clean_question:
        return {"status": "error", "stage": "sql_agent", "message": "问题不能为空"}

    try:
        table_info = get_table_info(data_source_id)
        knowledge, metric_bindings = _knowledge_context(clean_question, data_source_id)
        metric_requirements = "\n".join(
            f"- ID {metric['metric_id']} {metric['name']}: {metric['sql_expr']}"
            for metric in metric_bindings
        ) or "无显式命中的指标"
        prompt = f"""
你是智能 BI 平台中的 SQL Agent。你的职责仅是把用户问题转换成查询计划和一条可执行的 MySQL 只读 SQL，不能分析查询结果。

严格要求：
1. 只能使用下方给出的表和字段，禁止臆造字段。
2. SQL 只能是单条 SELECT 或 WITH 查询，禁止任何写入、建表或删除操作。
3. 如果问题对应已有指标口径，request_type 使用 metric，否则使用 sql。
4. 显式命中的指标必须原样使用其“权威计算表达式”，只能在外层增加维度、时间和用户明确提出的过滤条件；禁止把指标 CASE 内的条件移到 WHERE。
5. 时间、状态等额外过滤条件必须体现在 filters 和 SQL 中。
6. 根据结果形态选择 chart_type：趋势用 line，占比用 pie，分类比较用 bar，单值用 none。
7. 仅返回 JSON，不要 Markdown，不要解释。

JSON 格式：
{{
  "intent": "对问题的简短理解",
  "request_type": "sql 或 metric",
  "metrics": ["指标或计算表达式"],
  "matched_metric_ids": [1],
  "dimensions": ["分析维度"],
  "filters": ["过滤条件"],
  "analysis_type": "summary/trend/comparison/share/anomaly/attribution/report",
  "chart_type": "auto/none/line/bar/pie",
  "chart_title": "图表标题",
  "needs_anomaly": false,
  "needs_attribution": false,
  "needs_report": false,
  "sql": "SELECT ..."
}}

【业务数据库结构】
{table_info}

【指标口径知识】
{knowledge}

【必须遵守的命中指标】
{metric_requirements}

【用户问题】
{clean_question}

【最近对话上下文】
{json.dumps(list(conversation_context or [])[-6:], ensure_ascii=False)}
仅用于解析“它、这些、上一个”等指代，不得把历史回答当作数据库事实。
"""
        llm = get_llm(user_id)
        response = llm.invoke(prompt)
        raw_plan = _extract_json(response.content)
        plan = _normalise_plan(raw_plan, clean_question)
        plan["matched_metrics"] = [
            {
                "metric_id": metric["metric_id"],
                "name": metric["name"],
                "sql_expr": metric["sql_expr"],
            }
            for metric in metric_bindings
        ]
        validation = validate_metric_sql(plan["sql"], metric_bindings)

        if validation["violations"]:
            repair_prompt = f"""
你是 SQL 口径修复器。下面 SQL 没有严格使用已命中的权威指标表达式。
请保持原查询意图、维度和合理的额外筛选，但必须把每个权威表达式原样放入 SELECT。
禁止把 CASE 内的条件改写到 WHERE。只能返回修复后的完整 JSON 查询计划。

用户问题：{clean_question}
业务表结构：{table_info}
权威指标表达式：{metric_requirements}
当前计划：{json.dumps(plan, ensure_ascii=False)}
校验失败：{json.dumps(validation['violations'], ensure_ascii=False)}
"""
            repaired_raw = _extract_json(llm.invoke(repair_prompt).content)
            repaired_plan = _normalise_plan(repaired_raw, clean_question)
            repaired_plan["matched_metrics"] = plan["matched_metrics"]
            repaired_validation = validate_metric_sql(repaired_plan["sql"], metric_bindings)
            if repaired_validation["violations"]:
                names = "、".join(item["name"] for item in repaired_validation["violations"])
                raise ValueError(f"指标口径校验失败：生成 SQL 未严格使用 {names} 的权威表达式")
            plan = repaired_plan
            validation = {**repaired_validation, "repaired": True}
        else:
            validation = {**validation, "repaired": False}

        plan["metric_validation"] = validation
        plan["data_source_id"] = data_source_id
        return {"status": "success", "plan": plan, "sql": plan["sql"]}
    except Exception as exc:
        return {"status": "error", "stage": "sql_agent", "message": str(exc)}


def repair_query_after_execution_error(
    question: str,
    plan: Dict[str, Any],
    execution_error: str,
    user_id: Optional[int] = None,
    data_source_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Repair one failed generated query while preserving matched metric expressions."""

    try:
        table_info = get_table_info(data_source_id)
        matched_metrics = list(plan.get("matched_metrics") or [])
        requirements = "\n".join(
            f"- {metric['name']}: {metric['sql_expr']}" for metric in matched_metrics
        ) or "无"
        prompt = f"""
你是 SQL 执行错误修复器。根据真实表结构修复查询，只允许返回单条 MySQL SELECT/WITH。
保持原问题的指标、维度和过滤意图；已命中指标表达式必须原样使用。仅返回与原计划相同格式的 JSON。

用户问题：{question}
真实表结构：{table_info}
指标要求：{requirements}
失败计划：{json.dumps(plan, ensure_ascii=False)}
执行错误：{execution_error}
"""
        raw = _extract_json(get_llm(user_id).invoke(prompt).content)
        repaired = _normalise_plan(raw, question)
        repaired["matched_metrics"] = matched_metrics
        validation = validate_metric_sql(repaired["sql"], matched_metrics)
        if validation["violations"]:
            raise ValueError("修复后 SQL 违反指标口径")
        repaired["metric_validation"] = {**validation, "execution_repaired": True}
        repaired["data_source_id"] = data_source_id
        return {"status": "success", "plan": repaired, "sql": repaired["sql"]}
    except Exception as exc:
        return {"status": "error", "stage": "sql_repair", "message": str(exc)}


def create_attribution_query(
    question: str,
    plan: Dict[str, Any],
    user_id: Optional[int] = None,
    data_source_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Create a second, dimension-level query only when attribution is requested."""

    try:
        table_info = get_table_info(data_source_id)
        matched_metrics = list(plan.get("matched_metrics") or [])
        requirements = "\n".join(
            f"- {metric['name']}: {metric['sql_expr']}" for metric in matched_metrics
        ) or "无"
        prompt = f"""
你是 BI 归因下钻 SQL 工具。根据原问题和原计划，选择一个真实存在、最能解释变化的分类维度，
生成一条只读汇总 SQL。必须保留原计划的时间和业务过滤，指标表达式必须原样使用。
只返回 JSON：{{"dimension":"字段名","sql":"SELECT ..."}}。

问题：{question}
原计划：{json.dumps(plan, ensure_ascii=False)}
数据库结构：{table_info}
指标口径：{requirements}
"""
        raw = _extract_json(get_llm(user_id).invoke(prompt).content)
        sql = _with_limit(str(raw.get("sql") or ""))
        validation = validate_metric_sql(sql, matched_metrics)
        if validation["violations"]:
            raise ValueError("归因下钻 SQL 违反指标口径")
        return {"status": "success", "dimension": str(raw.get("dimension") or ""), "sql": sql}
    except Exception as exc:
        return {"status": "error", "stage": "attribution_query", "message": str(exc)}
