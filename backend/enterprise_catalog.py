"""Enterprise catalog lookup helpers.

An empty installation intentionally has no enterprise. Enterprises are created
explicitly by administration or inferred from a valid SQL import filename.
"""

from sqlalchemy.orm import Session

from database import SessionLocal
from models import Enterprise


def get_default_enterprise(db: Session) -> Enterprise | None:
    return db.query(Enterprise).order_by(Enterprise.id.asc()).first()


def ensure_enterprise_catalog() -> Enterprise | None:
    """Backward-compatible lookup that never inserts placeholder enterprises."""

    db = SessionLocal()
    try:
        return get_default_enterprise(db)
    finally:
        db.close()
