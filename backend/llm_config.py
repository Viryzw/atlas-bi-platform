"""Shared, lazy DeepSeek configuration for every BI agent."""

from functools import lru_cache
import hashlib
import os
from threading import RLock
from typing import Dict, Optional, Tuple

from langchain_openai import ChatOpenAI

from database import SessionLocal
from models import UserLLMConfig
from secret_store import decrypt_secret


class LLMConfigurationError(RuntimeError):
    """Raised when the active user has no usable DeepSeek API key."""


_user_clients: Dict[int, Tuple[str, ChatOpenAI]] = {}
_client_lock = RLock()


def _build_llm(api_key: str) -> ChatOpenAI:
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL", "deepseek-v4-flash"),
        base_url="https://api.deepseek.com",
        api_key=api_key,
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.1")),
        max_tokens=int(os.getenv("LLM_MAX_TOKENS", "2048")),
        timeout=float(os.getenv("LLM_TIMEOUT", "90")),
        max_retries=int(os.getenv("LLM_MAX_RETRIES", "1")),
    )


@lru_cache(maxsize=1)
def _get_environment_llm() -> ChatOpenAI:
    """Compatibility client for debug calls that do not carry a user ID."""

    api_key = os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise LLMConfigurationError(
            "未配置 DeepSeek API Key，请在智能问数页面完成用户 API 配置"
        )
    return _build_llm(api_key)


def _load_user_api_key(user_id: int) -> str:
    db = SessionLocal()
    try:
        config = (
            db.query(UserLLMConfig)
            .filter(UserLLMConfig.user_id == user_id)
            .first()
        )
        api_key = decrypt_secret(config.api_key if config else "").strip()
    finally:
        db.close()
    if not api_key:
        raise LLMConfigurationError("请配置API：当前用户尚未配置 DeepSeek API Key")
    return api_key


def get_llm(user_id: Optional[int] = None) -> ChatOpenAI:
    """Return the current user's client and hot-reload it after key changes."""

    if user_id is None:
        return _get_environment_llm()

    api_key = _load_user_api_key(int(user_id))
    fingerprint = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
    with _client_lock:
        cached = _user_clients.get(int(user_id))
        if cached and cached[0] == fingerprint:
            return cached[1]
        client = _build_llm(api_key)
        _user_clients[int(user_id)] = (fingerprint, client)
        return client


def reset_llm_cache(user_id: Optional[int] = None) -> None:
    """Invalidate one user's client, or every cached client for tests/admin."""

    with _client_lock:
        if user_id is None:
            _user_clients.clear()
            _get_environment_llm.cache_clear()
        else:
            _user_clients.pop(int(user_id), None)
