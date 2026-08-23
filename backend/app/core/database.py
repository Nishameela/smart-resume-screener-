"""
SQLAlchemy engine/session setup.

SQLite is used deliberately (see README architecture section) for
zero-friction local setup while still exercising real relational
modeling (foreign keys, one-to-many relationships). The data directory
is created on import so a fresh checkout "just works".
"""
from collections.abc import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings

# Ensure the data/ directory exists for the SQLite file (no-op for other DBs).
if settings.database_url.startswith("sqlite"):
    from pathlib import Path

    from app.core.config import BACKEND_ROOT

    db_path = settings.database_url.replace("sqlite:///", "")
    if db_path.startswith("./"):
        (BACKEND_ROOT / db_path[2:]).parent.mkdir(parents=True, exist_ok=True)
    else:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)


@event.listens_for(engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
    """SQLite does not enforce FOREIGN KEY constraints unless told to per-connection."""
    if settings.database_url.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
