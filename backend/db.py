"""Database engine and session factory (build step 3).

The one place that knows how to reach Postgres. Everything else asks for a
Session and works with the models; this module owns the connection.

Two deliberate choices:

  * Lazy setup. We read DATABASE_URL on first use, not at import, because
    main.py calls load_dotenv() at startup and the .env values must be in place
    before we build the engine. This mirrors the lazy Groq client in agent/llm.py.

  * Optional. If DATABASE_URL is unset, is_enabled() is False and new_session()
    returns None. The /chat endpoint then runs the agent statelessly instead of
    crashing, so the app works before Neon is wired and history is a seam that
    simply turns on once the URL is present -- same idea as the trace.py no-op.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

_state = {"ready": False, "engine": None, "Session": None}


def _normalise(url: str) -> str:
    """Point a bare Neon URL at the psycopg 3 driver we actually ship.

    Neon hands out postgresql://... . SQLAlchemy maps that bare scheme to
    psycopg2, but our requirement is psycopg[binary] (v3), whose scheme is
    postgresql+psycopg. Rewriting the prefix lets you paste Neon's string into
    .env verbatim. An already-qualified URL (e.g. sqlite://) is left alone.
    """
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


def _ensure() -> None:
    if _state["ready"]:
        return
    _state["ready"] = True  # set first so a missing URL is not retried every call
    url = os.getenv("DATABASE_URL", "")
    if not url:
        return
    # pool_pre_ping checks a pooled connection is still alive before handing it
    # out. Neon scales to zero, so a connection can go stale between requests;
    # pre_ping quietly reconnects instead of surfacing a dead-connection error.
    engine = create_engine(_normalise(url), pool_pre_ping=True)
    _state["engine"] = engine
    # expire_on_commit=False so we can still read an object's attributes after
    # commit (e.g. return a saved row) without the ORM firing a fresh query.
    _state["Session"] = sessionmaker(bind=engine, expire_on_commit=False)


def is_enabled() -> bool:
    _ensure()
    return _state["Session"] is not None


def new_session() -> Session | None:
    _ensure()
    factory = _state["Session"]
    return factory() if factory is not None else None


def init_db() -> None:
    """Create any missing tables. Called once on startup.

    Wrapped so a database hiccup at boot (Neon asleep, a blocked port) logs a
    warning instead of taking the whole app down -- the agent can still serve
    stateless requests. Real projects use migrations (Alembic); create_all is
    the honest, dependency-light choice for a portfolio schema that only grows.
    """
    _ensure()
    engine = _state["engine"]
    if engine is None:
        return
    try:
        Base.metadata.create_all(engine)
    except Exception as exc:  # noqa: BLE001 - boot must survive a DB outage
        print(f"[db] table setup skipped ({exc}); running without persistence")
