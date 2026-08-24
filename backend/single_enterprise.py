"""Backward-compatible enterprise helpers.

The platform now supports multiple enterprises. Keep these names for any old
imports, but never merge, reassign, or delete enterprise records here.
"""

from sqlalchemy.orm import Session

from enterprise_catalog import ensure_enterprise_catalog, get_default_enterprise
from models import Enterprise


def get_platform_enterprise(db: Session) -> Enterprise | None:
    return get_default_enterprise(db)


def ensure_single_enterprise() -> Enterprise | None:
    return ensure_enterprise_catalog()
