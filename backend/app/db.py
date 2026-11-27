"""Database engine and sessions, including the tenant context used by PostgreSQL Row Level Security.

Every transaction re-applies `app.current_org` from `session.info["org_id"]` (transaction-local),
so RLS policies always see the organisation that the API layer has already authorised.
With no organisation set, RLS policies match no rows (fail closed).
"""
from collections.abc import Iterator
from uuid import UUID

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True, future=True)
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False, autoflush=True)
    return _engine


def reset_engine() -> None:
    """Used by tests after changing settings."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def new_session() -> Session:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal()


@event.listens_for(Session, "after_begin")
def _apply_tenant_context(session: Session, transaction, connection) -> None:  # noqa: ANN001
    org_id = session.info.get("org_id")
    connection.execute(
        text("SELECT set_config('app.current_org', :org, true)"),
        {"org": str(org_id) if org_id else ""},
    )


def set_tenant(session: Session, org_id: UUID | None) -> None:
    """Bind the session to an authorised organisation for RLS. Call only after membership checks."""
    session.info["org_id"] = org_id
    if session.in_transaction():
        session.execute(
            text("SELECT set_config('app.current_org', :org, true)"),
            {"org": str(org_id) if org_id else ""},
        )


def get_db() -> Iterator[Session]:
    session = new_session()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
