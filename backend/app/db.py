"""Engine, session, WAL pragma, BEGIN IMMEDIATE helper (SPEC §4)."""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from . import config

# Resolve DB path relative to backend/ dir so `make seed` works from root.
_DB_URL = config.DATABASE_URL
if _DB_URL.startswith("sqlite:///") and not _DB_URL.startswith("sqlite:////"):
    rel = _DB_URL.replace("sqlite:///", "")
    # backend/app/db.py -> backend/<rel>
    db_path = (Path(__file__).resolve().parent.parent / rel).resolve()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    _DB_URL = f"sqlite:///{db_path.as_posix()}"


class Base(DeclarativeBase):
    pass


engine = create_engine(
    _DB_URL,
    connect_args={"check_same_thread": False, "timeout": 30},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@event.listens_for(engine, "connect")
def _set_sqlite_pragmas(dbapi_conn, _conn_record):
    cur = dbapi_conn.cursor()
    cur.execute("PRAGMA journal_mode=WAL;")
    cur.execute("PRAGMA busy_timeout=5000;")
    cur.execute("PRAGMA synchronous=NORMAL;")
    cur.close()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def immediate_txn(session):
    """Run a write txn under BEGIN IMMEDIATE so concurrent reservers serialise.

    SQLite deferred transactions allow two writers to both read stale state.
    BEGIN IMMEDIATE takes the write lock up-front; the second writer blocks
    (busy_timeout) instead of overselling. Caller must commit/rollback.
    """
    session.execute(text("BEGIN IMMEDIATE"))
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise


def init_db() -> None:
    from . import models  # noqa: F401  (register tables)

    Base.metadata.create_all(bind=engine)
