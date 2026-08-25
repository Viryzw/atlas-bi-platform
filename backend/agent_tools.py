"""Analysis Agent and its deterministic BI tools.

The Analysis Agent is the only product-level orchestrator. It calls SQL Agent
first, executes the generated SQL second, then analyses the returned data and
optionally produces a chart, anomaly result, attribution and report section.
"""

import json
import math
import re
from typing import Any, Callable, Dict, List, Optional

from llm_config import get_llm
from query_engine import execute_sql
from sql_agent import create_attribution_query, create_query_plan, repair_query_after_execution_error


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
        raise ValueError("分析 Agent 没有返回 JSON 对象")
    return parsed


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _compact_data(data: Dict[str, Any], max_rows: int = 80) -> Dict[str, Any]:
    rows = list(data.get("rows") or [])
    return {
        "columns": list(data.get("columns") or []),
        "rows": rows[:max_rows],
        "row_count": data.get("row_count", len(rows)),
        "truncated_for_analysis": len(rows) > max_rows,
    }


def generate_chart_tool(
    data: Dict[str, Any],
    chart_type: str = "auto",
    title: str = "分析结果",
    analysis_type: str = "summary",
) -> Optional[Dict[str, Any]]:
    """Build an ECharts option from actual SQL result rows."""

    columns = list(data.get("columns") or [])
    rows = list(data.get("rows") or [])
    if len(columns) < 2 or not rows or chart_type == "none":
        return None

    numeric_indexes = [
        index
        for index in range(1, len(columns))
        if any(index < len(row) and _is_number(row[index]) for row in rows)
    ]
    if not numeric_indexes:
        return None

    selected_type = chart_type
    if selected_type == "auto":
        selected_type = {
            "trend": "line",
            "share": "pie",
            "comparison": "bar",
        }.get(analysis_type, "bar")

    colors = ["#3157d5", "#0f9f9a", "#e0a53b", "#805ad5", "#e15b64"]
    if selected_type == "pie":
        value_index = numeric_indexes[0]
        return {
            "title": {"text": title, "left": "center"},
            "color": colors,
            "tooltip": {"trigger": "item", "formatter": "{b}: {c} ({d}%)"},
            "legend": {"bottom": 0},
            "series": [{
                "name": columns[value_index],
                "type": "pie",
                "radius": ["42%", "68%"],
                "data": [
                    {"name": str(row[0]), "value": row[value_index]}
                    for row in rows
                    if len(row) > value_index and _is_number(row[value_index])
                ],
            }],
        }

    return {
        "title": {"text": title, "left": "center"},
        "color": colors,
        "tooltip": {"trigger": "axis"},
        "legend": {"top": 28},
        "grid": {"left": 24, "right": 24, "top": 70, "bottom": 20, "containLabel": True},
        "xAxis": {"type": "category", "data": [str(row[0]) for row in rows]},
        "yAxis": {"type": "value"},
        "series": [
            {
                "name": columns[index],
                "type": selected_type if selected_type in {"line", "bar"} else "bar",
                "smooth": selected_type == "line",
                "data": [row[index] if len(row) > index else None for row in rows],
            }
            for index in numeric_indexes[:4]
        ],
    }


def detect_anomaly_tool(data: Dict[str, Any], threshold: float = 0.3) -> Dict[str, Any]:
    """Compare the latest two periods; no random data is introduced."""

    columns = list(data.get("columns") or [])
    rows = list(data.get("rows") or [])
    if len(rows) < 2 or len(columns) < 2:
        return {"available": False, "message": "至少需要两个周期的数据才能进行异常检测"}

    value_index = next(
        (
            index
            for index in range(1, len(columns))
            if _is_number(rows[-1][index]) and _is_number(rows[-2][index])
        ),
        None,
    )
    if value_index is None:
        return {"available": False, "message": "结果中没有可比较的连续数值指标"}

    previous = float(rows[-2][value_index])
    current = float(rows[-1][value_index])
    if previous == 0:
        change = None
        is_anomaly = current != 0
    else:
        change = (current - previous) / abs(previous)
        is_anomaly = abs(change) > threshold

    change_percent = None if change is None else round(change * 100, 2)
    period = str(rows[-1][0])
    direction = "变化" if change is None else ("上升" if change >= 0 else "下降")
    message = (
        f"{columns[value_index]} 在 {period} 较上一期{direction}"
        f"{abs(change_percent):.2f}%" if change_percent is not None
        else f"{columns[value_index]} 上一期为 0，当前值为 {current:g}"
    )
    return {
        "available": True,
        "metric": columns[value_index],
        "period": period,
        "current": current,
        "previous": previous,
        "change_percent": change_percent,
        "threshold_percent": threshold * 100,
        "is_anomaly": is_anomaly,
        "message": message,
    }


def analyse_result_tool(
    question: str,
    plan: Dict[str, Any],
    data: Dict[str, Any],
    anomaly: Optional[Dict[str, Any]],
    user_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Ground the written conclusion strictly in query results."""

    if not data.get("rows"):
        return {"summary": "查询执行成功，但当前条件下没有匹配数据。", "insights": []}

    prompt = f"""
你是智能 BI 平台中的分析 Agent。SQL Agent 和数据查询工具已经完成工作。
请只依据给出的查询计划和真实数据写分析结论，禁止补充数据中不存在的事实。
比例请计算准确；如果样本有限，要明确说明。仅返回 JSON。

JSON 格式：
{{"summary": "2-4 句核心结论", "insights": ["洞察1", "洞察2", "洞察3"]}}

用户问题：{question}
查询计划：{json.dumps(plan, ensure_ascii=False)}
查询数据：{json.dumps(_compact_data(data), ensure_ascii=False)}
异常检测：{json.dumps(anomaly, ensure_ascii=False) if anomaly else "未请求"}
"""
    response = get_llm(user_id).invoke(prompt)
    parsed = _extract_json(response.content)
    return {
        "summary": str(parsed.get("summary") or "分析完成。"),
        "insights": [str(item) for item in list(parsed.get("insights") or [])[:5]],
    }


def attribute_analysis_tool(
    question: str,
    plan: Dict[str, Any],
    data: Dict[str, Any],
    anomaly: Optional[Dict[str, Any]],
    attribution_data: Optional[Dict[str, Any]] = None,
    user_id: Optional[int] = None,
) -> List[str]:
    """Return evidence-aware possible causes instead of fabricated facts."""

    prompt = f"""
你是 BI 归因分析工具。请基于给定数据列出 3-5 条可能原因。
数据能够直接支持的标记为“数据证据”，不能直接验证的标记为“待验证假设”。
禁止把假设写成确定事实。仅返回 JSON：{{"causes": ["..."]}}。

问题：{question}
计划：{json.dumps(plan, ensure_ascii=False)}
数据：{json.dumps(_compact_data(data), ensure_ascii=False)}
下钻维度数据：{json.dumps(_compact_data(attribution_data), ensure_ascii=False) if attribution_data else "无"}
异常：{json.dumps(anomaly, ensure_ascii=False) if anomaly else "无"}
"""
    parsed = _extract_json(get_llm(user_id).invoke(prompt).content)
    return [str(item) for item in list(parsed.get("causes") or [])[:5]]


def generate_report_section_tool(
    question: str,
    analysis: Dict[str, Any],
    attribution: List[str],
    user_id: Optional[int] = None,
) -> str:
    prompt = f"""
你是 BI 报告片段生成工具。根据以下已验证分析写一个 120-180 字的中文报告片段，
结构为“结论—证据—建议”，不要编造额外数字。只返回报告正文。

主题：{question}
分析：{json.dumps(analysis, ensure_ascii=False)}
归因：{json.dumps(attribution, ensure_ascii=False)}
"""
    return get_llm(user_id).invoke(prompt).content.strip()


def _compose_answer(
    analysis: Dict[str, Any],
    anomaly: Optional[Dict[str, Any]],
    attribution: List[str],
    report_section: Optional[str],
) -> str:
    parts = [analysis.get("summary", "分析完成。")]
    insights = analysis.get("insights") or []
    if insights:
        parts.append("关键洞察：\n" + "\n".join(f"• {item}" for item in insights))
    if anomaly:
        parts.append("异常检测：" + anomaly.get("message", "已完成"))
    if attribution:
        parts.append("归因分析：\n" + "\n".join(f"• {item}" for item in attribution))
    if report_section:
        parts.append("报告片段：\n" + report_section)
    return "\n\n".join(parts)


def _wants(question: str, plan: Dict[str, Any], capability: str) -> bool:
    keyword_map = {
        "anomaly": ("异常", "波动", "骤升", "骤降"),
        "attribution": ("为什么", "原因", "归因"),
        "report": ("报告", "摘要", "汇报"),
    }
    plan_key = f"needs_{capability}"
    return bool(plan.get(plan_key)) or any(word in question for word in keyword_map[capability])


def run_agent(
    question: str,
    user_id: Optional[int] = None,
    data_source_id: Optional[int] = None,
    conversation_context: Optional[List[Dict[str, str]]] = None,
    progress_callback: Optional[Callable[[str, Dict[str, Any]], None]] = None,
) -> Dict[str, Any]:
    """Run the fixed SQL Agent -> query -> analysis tool chain."""

    clean_question = (question or "").strip()
    if not clean_question:
        return {"status": "error", "stage": "input", "message": "问题不能为空"}

    def progress(stage: str, **payload: Any) -> None:
        if progress_callback:
            progress_callback(stage, payload)

    progress("planning", message="正在匹配指标口径并生成查询计划")
    plan_kwargs = {}
    if user_id is not None:
        plan_kwargs["user_id"] = user_id
    if data_source_id is not None:
        plan_kwargs["data_source_id"] = data_source_id
    if conversation_context:
        plan_kwargs["conversation_context"] = conversation_context
    planned = create_query_plan(clean_question, **plan_kwargs)
    if planned.get("status") != "success":
        return planned

    plan = planned["plan"]
    sql = planned["sql"]
    progress("querying", message="正在执行只读 SQL", sql=sql)
    data = (
        execute_sql(sql)
        if data_source_id is None
        else execute_sql(sql, data_source_id=data_source_id)
    )
    if "error" in data:
        progress("repairing", message="SQL 执行失败，正在结合真实表结构修复一次")
        repaired = repair_query_after_execution_error(
            clean_question,
            plan,
            data["error"],
            user_id=user_id,
            data_source_id=data_source_id,
        )
        if repaired.get("status") != "success":
            return {
                "status": "error", "stage": "data_query", "plan": plan, "sql": sql,
                "message": f"{data['error']}；自动修复失败：{repaired.get('message', '未知错误')}",
            }
        plan, sql = repaired["plan"], repaired["sql"]
        data = execute_sql(sql) if data_source_id is None else execute_sql(sql, data_source_id=data_source_id)
        if "error" in data:
            return {"status": "error", "stage": "data_query", "plan": plan, "sql": sql, "message": data["error"]}

    chart_config = generate_chart_tool(
        data,
        chart_type=plan.get("chart_type", "auto"),
        title=plan.get("chart_title", "分析结果"),
        analysis_type=plan.get("analysis_type", "summary"),
    )
    anomaly = None
    if _wants(clean_question, plan, "anomaly"):
        anomaly = detect_anomaly_tool(data)

    try:
        progress("analysing", message="正在分析真实查询结果")
        analysis = (
            analyse_result_tool(clean_question, plan, data, anomaly)
            if user_id is None
            else analyse_result_tool(clean_question, plan, data, anomaly, user_id=user_id)
        )
        attribution: List[str] = []
        attribution_data = None
        attribution_sql = None
        if _wants(clean_question, plan, "attribution") or bool(anomaly and anomaly.get("is_anomaly")):
            progress("attributing", message="正在进行异常归因")
            drilldown = create_attribution_query(
                clean_question, plan, user_id=user_id, data_source_id=data_source_id
            )
            if drilldown.get("status") == "success":
                attribution_sql = drilldown["sql"]
                queried = execute_sql(attribution_sql) if data_source_id is None else execute_sql(attribution_sql, data_source_id=data_source_id)
                if "error" not in queried:
                    attribution_data = queried
            attribution = (
                attribute_analysis_tool(clean_question, plan, data, anomaly, attribution_data)
                if user_id is None
                else attribute_analysis_tool(
                    clean_question,
                    plan,
                    data,
                    anomaly,
                    attribution_data,
                    user_id=user_id,
                )
            )

        report_section = None
        if _wants(clean_question, plan, "report"):
            progress("reporting", message="正在生成报告片段")
            report_section = (
                generate_report_section_tool(clean_question, analysis, attribution)
                if user_id is None
                else generate_report_section_tool(
                    clean_question,
                    analysis,
                    attribution,
                    user_id=user_id,
                )
            )
    except Exception as exc:
        return {
            "status": "error",
            "stage": "analysis_agent",
            "plan": plan,
            "sql": sql,
            "data": data,
            "chart_config": chart_config,
            "message": str(exc),
        }

    result = {
        "status": "success",
        "question": clean_question,
        "data_source_id": data_source_id,
        "plan": plan,
        "sql": sql,
        "data": data,
        "analysis": analysis,
        "answer": _compose_answer(analysis, anomaly, attribution, report_section),
        "chart_config": chart_config,
        "anomaly": anomaly,
        "attribution": attribution,
        "attribution_sql": attribution_sql,
        "attribution_data": attribution_data,
        "report_section": report_section,
    }
    progress("complete", message="分析已完成")
    return result
