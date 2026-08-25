"""Developer compatibility endpoint for inspecting SQL Agent output.

The product UI uses /api/agent/. This route remains available for debugging
and automated evaluation of natural-language-to-SQL quality.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from query_engine import text_to_sql


router = APIRouter(prefix="/api/query", tags=["sql-agent-debug"])


class QueryRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    user_id: Optional[int] = Field(default=None, gt=0)
    data_source_id: Optional[int] = Field(default=None, gt=0)


class QueryResponse(BaseModel):
    status: str
    plan: Optional[Dict[str, Any]] = None
    sql: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    message: Optional[str] = None


@router.post("/", response_model=QueryResponse)
def handle_query(request: QueryRequest):
    result = text_to_sql(
        request.question,
        user_id=request.user_id,
        data_source_id=request.data_source_id,
    )
    if result.get("status") == "error":
        raise HTTPException(
            status_code=400,
            detail={
                "stage": result.get("stage", "sql_agent"),
                "message": result.get("message", "查询失败"),
                "plan": result.get("plan"),
                "sql": result.get("sql"),
            },
        )
    return QueryResponse(**result)
