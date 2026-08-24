"""Best-effort audit logging for state-changing API calls."""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from database import SessionLocal
from models import AuditLog
from security import decode_access_token


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and request.url.path.startswith("/api/"):
            user_id = None
            authorization = request.headers.get("authorization", "")
            if authorization.lower().startswith("bearer "):
                try:
                    user_id = int(decode_access_token(authorization.split(" ", 1)[1])["sub"])
                except Exception:
                    user_id = None
            db = SessionLocal()
            try:
                db.add(AuditLog(
                    user_id=user_id,
                    method=request.method,
                    path=request.url.path[:255],
                    status_code=response.status_code,
                    client_ip=request.client.host if request.client else None,
                ))
                db.commit()
            except Exception:
                db.rollback()
            finally:
                db.close()
        return response
