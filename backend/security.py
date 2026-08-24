"""Authentication, password hashing and role authorization helpers."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import os
import secrets
from typing import Optional

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database import get_db
from models import User


PASSWORD_ITERATIONS = 310_000
TOKEN_TTL_HOURS = int(os.getenv("AUTH_TOKEN_TTL_HOURS", "12"))
_bearer = HTTPBearer(auto_error=False)


def _secret() -> bytes:
    return os.getenv("AUTH_SECRET", "atlas-bi-development-secret-change-me").encode("utf-8")


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    clean = password or ""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", clean.encode("utf-8"), salt, PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, encoded: str) -> tuple[bool, bool]:
    """Return (valid, needs_rehash), accepting legacy plaintext once."""

    stored = encoded or ""
    if not stored.startswith("pbkdf2_sha256$"):
        return hmac.compare_digest(password or "", stored), True
    try:
        _, iterations, salt, expected = stored.split("$", 3)
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            (password or "").encode("utf-8"),
            _b64decode(salt),
            int(iterations),
        )
        return hmac.compare_digest(digest, _b64decode(expected)), int(iterations) < PASSWORD_ITERATIONS
    except (TypeError, ValueError):
        return False, False


def create_access_token(user: User) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": int(user.id),
        "role": user.role or "user",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=TOKEN_TTL_HOURS)).timestamp()),
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = _b64encode(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
    return f"{body}.{signature}"


def decode_access_token(token: str) -> dict:
    try:
        body, signature = token.split(".", 1)
        expected = _b64encode(hmac.new(_secret(), body.encode("ascii"), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid signature")
        payload = json.loads(_b64decode(body))
        if int(payload.get("exp", 0)) <= int(datetime.now(timezone.utc).timestamp()):
            raise ValueError("expired")
        return payload
    except Exception as exc:
        raise HTTPException(status_code=401, detail={"message": "登录状态无效或已过期"}) from exc


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail={"message": "请先登录"})
    payload = decode_access_token(credentials.credentials)
    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if user is None:
        raise HTTPException(status_code=401, detail={"message": "登录用户不存在"})
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail={"message": "仅管理员可以访问用户管理"})
    return current_user


def require_same_user_or_admin(current_user: User, user_id: int) -> None:
    if current_user.role != "admin" and int(current_user.id) != int(user_id):
        raise HTTPException(status_code=403, detail={"message": "不能访问其他用户的数据"})
