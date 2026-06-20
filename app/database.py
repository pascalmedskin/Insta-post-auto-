"""Configuration SQLAlchemy (SQLite par défaut)."""

from collections.abc import Generator

import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)
engine = create_engine(settings.database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _add_column_if_missing(conn, table: str, column: str, col_type: str = "TEXT DEFAULT ''") -> None:
    try:
        conn.execute(sqlalchemy.text(f"SELECT {column} FROM {table} LIMIT 0"))
    except Exception:
        conn.execute(sqlalchemy.text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))


def init_db() -> None:
    # Import des modèles pour les enregistrer sur Base avant create_all.
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    with engine.connect() as conn:
        for col in ("ig_access_token", "ig_user_id", "ig_username"):
            _add_column_if_missing(conn, "brands", col, "VARCHAR(500) DEFAULT ''")
        _add_column_if_missing(conn, "brands", "user_id", "INTEGER")
        conn.commit()
