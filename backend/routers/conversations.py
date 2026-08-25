import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

import crud
import schemas
from database import get_db
from models import Conversation, ConversationMessage, User
from security import get_current_user, require_same_user_or_admin


router = APIRouter(prefix="/api/conversations", tags=["conversations"])


def _require_user(db: Session, user_id: int) -> None:
    if crud.get_user(db, user_id) is None:
        raise HTTPException(status_code=404, detail={"message": f"用户 ID {user_id} 不存在"})


def _owned_conversation(db: Session, conversation_id: int, user_id: int) -> Conversation:
    conversation = (
        db.query(Conversation)
        .filter(Conversation.id == conversation_id, Conversation.user_id == user_id)
        .first()
    )
    if conversation is None:
        raise HTTPException(status_code=404, detail={"message": "会话不存在或不属于当前用户"})
    return conversation


def _message_response(message: ConversationMessage) -> schemas.ConversationMessageResponse:
    try:
        payload = json.loads(message.payload_json or "{}")
    except json.JSONDecodeError:
        payload = {}
    return schemas.ConversationMessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        payload=payload if isinstance(payload, dict) else {},
        created_at=message.created_at,
    )


def _summary(db: Session, conversation: Conversation) -> schemas.ConversationSummary:
    message_count = (
        db.query(func.count(ConversationMessage.id))
        .filter(ConversationMessage.conversation_id == conversation.id)
        .scalar()
        or 0
    )
    return schemas.ConversationSummary(
        id=conversation.id,
        user_id=conversation.user_id,
        title=conversation.title,
        data_source_id=conversation.data_source_id,
        message_count=int(message_count),
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
    )


@router.get("/", response_model=List[schemas.ConversationSummary])
def list_conversations(
    user_id: int = Query(gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if isinstance(current_user, User):
        require_same_user_or_admin(current_user, user_id)
    _require_user(db, user_id)
    records = (
        db.query(Conversation)
        .filter(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        .all()
    )
    return [_summary(db, record) for record in records]


@router.post("/", response_model=schemas.ConversationSummary)
def create_conversation(
    payload: schemas.ConversationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if isinstance(current_user, User):
        require_same_user_or_admin(current_user, payload.user_id)
    _require_user(db, payload.user_id)
    if payload.data_source_id is not None and crud.get_data_source(db, payload.data_source_id) is None:
        raise HTTPException(status_code=400, detail={"message": f"数据源 ID {payload.data_source_id} 不存在"})
    record = Conversation(**payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return _summary(db, record)


@router.get("/{conversation_id}", response_model=schemas.ConversationDetail)
def get_conversation(
    conversation_id: int,
    user_id: int = Query(gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if isinstance(current_user, User):
        require_same_user_or_admin(current_user, user_id)
    record = _owned_conversation(db, conversation_id, user_id)
    messages = (
        db.query(ConversationMessage)
        .filter(ConversationMessage.conversation_id == record.id)
        .order_by(ConversationMessage.id.asc())
        .all()
    )
    summary = _summary(db, record).model_dump()
    return schemas.ConversationDetail(
        **summary,
        messages=[_message_response(message) for message in messages],
    )


@router.put("/{conversation_id}", response_model=schemas.ConversationSummary)
def update_conversation(
    conversation_id: int,
    payload: schemas.ConversationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if isinstance(current_user, User):
        require_same_user_or_admin(current_user, payload.user_id)
    record = _owned_conversation(db, conversation_id, payload.user_id)
    record.title = payload.title.strip()
    record.updated_at = func.now()
    db.commit()
    db.refresh(record)
    return _summary(db, record)


@router.delete("/{conversation_id}")
def delete_conversation(
    conversation_id: int,
    user_id: int = Query(gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if isinstance(current_user, User):
        require_same_user_or_admin(current_user, user_id)
    record = _owned_conversation(db, conversation_id, user_id)
    db.query(ConversationMessage).filter(
        ConversationMessage.conversation_id == record.id
    ).delete()
    db.delete(record)
    db.commit()
    return {"detail": "deleted"}


@router.post(
    "/{conversation_id}/messages",
    response_model=schemas.ConversationMessageResponse,
)
def append_message(
    conversation_id: int,
    payload: schemas.ConversationMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if isinstance(current_user, User):
        require_same_user_or_admin(current_user, payload.user_id)
    conversation = _owned_conversation(db, conversation_id, payload.user_id)
    message = ConversationMessage(
        conversation_id=conversation.id,
        role=payload.role,
        content=payload.content,
        payload_json=json.dumps(payload.payload, ensure_ascii=False, default=str),
    )
    conversation.updated_at = func.now()
    db.add(message)
    db.commit()
    db.refresh(message)
    return _message_response(message)
