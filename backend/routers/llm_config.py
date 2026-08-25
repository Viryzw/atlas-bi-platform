from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import crud
import schemas
from database import get_db
from llm_config import reset_llm_cache
from models import User
from security import get_current_user, require_same_user_or_admin


router = APIRouter(prefix="/api/llm-config", tags=["llm-config"])


def _require_user(db: Session, user_id: int) -> None:
    if crud.get_user(db, user_id) is None:
        raise HTTPException(
            status_code=404,
            detail={"message": f"用户 ID {user_id} 不存在"},
        )


@router.get("/status", response_model=schemas.LLMConfigStatus)
def get_config_status(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if isinstance(current_user, User):
        require_same_user_or_admin(current_user, user_id)
    _require_user(db, user_id)
    config = crud.get_user_llm_config(db, user_id)
    return schemas.LLMConfigStatus(
        user_id=user_id,
        configured=bool(config and config.api_key.strip()),
        updated_at=config.updated_at if config else None,
    )


@router.put("/", response_model=schemas.LLMConfigStatus)
def configure_llm(
    payload: schemas.LLMConfigUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if isinstance(current_user, User):
        require_same_user_or_admin(current_user, payload.user_id)
    _require_user(db, payload.user_id)
    api_key = payload.api_key.strip()
    if not api_key:
        raise HTTPException(status_code=400, detail={"message": "API Key 不能为空"})

    config = crud.upsert_user_llm_config(db, payload.user_id, api_key)
    # The next Agent call builds a DeepSeek client with the new key; FastAPI
    # does not need to restart and the secret is never returned to the client.
    reset_llm_cache(payload.user_id)
    return schemas.LLMConfigStatus(
        user_id=payload.user_id,
        configured=True,
        updated_at=config.updated_at,
    )
