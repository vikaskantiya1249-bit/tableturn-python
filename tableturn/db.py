"""Engine and sessions. SQLite; the schema is created at start-up. The request-scoped session
dependency lives in routers/__init__.py, so this module imports nothing from FastAPI."""
"""Engine and sessions. SQLite; the schema is created
at start-up. The request-scoped session dependency
lives in routers/__init__.py, so this module
imports nothing from FastAPI."""

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .models import Base

# The events table is append-only. These triggers make the database refuse an UPDATE or DELETE,
# so immutability is enforced, not assumed.
EVENT_TRIGGERS = [
    ("CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events "
     "BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;"),
    ("CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events "
     "BEGIN SELECT RAISE(ABORT, 'events are append-only'); END;"),
]


def make_engine(database_url: str) -> Engine:
    connect_args = (
        {"check_same_thread": False}
        if database_url.startswith("sqlite")
        else {}
    )

    engine = create_engine(
        database_url,
        connect_args=connect_args,
    )

    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _record):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")

    return engine


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)

    with engine.begin() as conn:
        for ddl in EVENT_TRIGGERS:
            conn.execute(text(ddl))


def make_sessionmaker(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine,
        expire_on_commit=False,
    )


def ping(session: Session) -> None:
    """Health: a round trip through the session. A database that cannot be reached raises, and the one 500
    handler answers."""
    session.execute(text("SELECT 1"))