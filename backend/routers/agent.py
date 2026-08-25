import asyncio
import json
import queue
import threading
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent_tools import run_agent
from database import SessionLocal
from models import Conversation, ConversationMessage, User
from security import get_current_user, require_same_user_or_admin


router = APIRouter(prefix="/api/agent", tags=["analysis-agent"])


class AgentRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    user_id: int = Field(gt=0)
    data_source_id: Optional[int] = Field(default=None, gt=0)
    conversation_id: Optional[int] = Field(default=None, gt=0)


class AgentResponse(BaseModel):
    status: str
    question: Optional[str] = None
    data_source_id: Optional[int] = None
    plan: Optional[Dict[str, Any]] = None
    sql: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    analysis: Optional[Dict[str, Any]] = None
    answer: Optional[str] = None
    chart_config: Optional[Dict[str, Any]] = None
    anomaly: Optional[Dict[str, Any]] = None
    attribution: List[str] = Field(default_factory=list)
    attribution_sql: Optional[str] = None
    attribution_data: Optional[Dict[str, Any]] = None
    report_section: Optional[str] = None
    message: Optional[str] = None


def _conversation_context(request: AgentRequest) -> List[Dict[str, str]]:
    if request.conversation_id is None:
        return []
    db = SessionLocal()
    try:
        conversation = db.query(Conversation).filter(
            Conversation.id == request.conversation_id,
            Conversation.user_id == request.user_id,
        ).first()
        if conversation is None:
            raise HTTPException(status_code=404, detail={"message": "会话不存在或不属于当前用户"})
        if conversation.data_source_id and request.data_source_id != conversation.data_source_id:
            raise HTTPException(status_code=409, detail={"message": "当前会话的数据源与请求不一致，请新建会话"})
        messages = db.query(ConversationMessage).filter(
            ConversationMessage.conversation_id == conversation.id,
        ).order_by(ConversationMessage.id.desc()).limit(6).all()
        return [{"role": item.role, "content": item.content[:1200]} for item in reversed(messages)]
    finally:
        db.close()


@router.post("/", response_model=AgentResponse)
def handle_agent(request: AgentRequest, current_user: User = Depends(get_current_user)):
    if isinstance(current_user, User):
        require_same_user_or_admin(current_user, request.user_id)
    context = _conversation_context(request)
    result = run_agent(
        request.question,
        user_id=request.user_id,
        data_source_id=request.data_source_id,
        conversation_context=context,
    )
    if result.get("status") == "error":
        stage = result.get("stage", "analysis_agent")
        status_code = 400 if stage in {"input", "sql_agent", "data_query"} else 502
        raise HTTPException(
            status_code=status_code,
            detail={
                "stage": stage,
                "message": result.get("message", "智能分析失败"),
                "plan": result.get("plan"),
                "sql": result.get("sql"),
            },
        )
    return AgentResponse(**result)


@router.post("/stream")
async def stream_agent(request: AgentRequest, current_user: User = Depends(get_current_user)):
    """Stream real orchestration stages and finish with the normal response payload."""

    if isinstance(current_user, User):
        require_same_user_or_admin(current_user, request.user_id)
    context = _conversation_context(request)
    events: queue.Queue = queue.Queue()

    def publish(stage: str, payload: Dict[str, Any]) -> None:
        events.put({"event": "stage", "stage": stage, **payload})

    def worker() -> None:
        try:
            result = run_agent(
                request.question,
                user_id=request.user_id,
                data_source_id=request.data_source_id,
                conversation_context=context,
                progress_callback=publish,
            )
            events.put({"event": "result", "data": result})
        except Exception as exc:
            events.put({"event": "error", "message": str(exc)})
        finally:
            events.put(None)

    threading.Thread(target=worker, daemon=True).start()

    async def generate():
        while True:
            item = await asyncio.to_thread(events.get)
            if item is None:
                break
            yield f"data: {json.dumps(item, ensure_ascii=False, default=str)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
