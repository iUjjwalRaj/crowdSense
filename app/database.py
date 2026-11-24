from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker


Base = declarative_base()


def default_database_url() -> str:
    configured = os.getenv("CROWDSENSE_DATABASE_URL")
    if configured:
        return configured
    data_dir = Path(os.getenv("CROWDSENSE_DATA_DIR", ".crowdsense"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{(data_dir / 'crowdsense.db').resolve()}"


DATABASE_URL = default_database_url()
engine: Engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    future=True,
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


def create_tables() -> None:
    import app.persistence_models  # register models
    Base.metadata.create_all(bind=engine)


@contextmanager
def db_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def database_health() -> dict:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {"configured": True, "healthy": True, "provider": "sql", "database_url_configured": bool(os.getenv("CROWDSENSE_DATABASE_URL"))}
    except Exception as error:
        return {
            "configured": True,
            "healthy": False,
            "provider": "sql",
            "database_url_configured": bool(os.getenv("CROWDSENSE_DATABASE_URL")),
            "blocking_error": type(error).__name__,
        }
