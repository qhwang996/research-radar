"""SQLAlchemy engine and session helpers."""

from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.db.base import Base
from src.exceptions import DatabaseError

logger = logging.getLogger(__name__)

DEFAULT_DATABASE_URL = "sqlite:///data/research_radar.db"


def get_database_url() -> str:
    """Return the configured database URL."""

    return os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)


def create_database_engine(
    database_url: str | None = None,
    *,
    echo: bool = False,
) -> Engine:
    """Create a SQLAlchemy engine for the configured database."""

    resolved_url = database_url or get_database_url()
    connect_args: dict[str, object] = {}
    if resolved_url.startswith("sqlite"):
        connect_args["check_same_thread"] = False

    return create_engine(resolved_url, echo=echo, future=True, connect_args=connect_args)


def create_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    """Create a session factory bound to the provided engine."""

    bound_engine = engine or ENGINE
    return sessionmaker(
        bind=bound_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )


def create_all_tables(engine: Engine | None = None) -> None:
    """Create all registered ORM tables."""

    bound_engine = engine or ENGINE

    try:
        import src.models  # noqa: F401

        Base.metadata.create_all(bind=bound_engine)
        logger.info("Database tables created successfully")
    except Exception as exc:  # pragma: no cover - defensive boundary
        logger.exception("Failed to create database tables")
        raise DatabaseError("Failed to create database tables") from exc


@contextmanager
def session_scope(
    session_factory: sessionmaker[Session] | None = None,
) -> Iterator[Session]:
    """Yield a transactional session and handle rollback on failure."""

    factory = session_factory or SessionLocal
    session = factory()
    try:
        yield session
        session.commit()
    except Exception as exc:
        session.rollback()
        logger.exception("Database transaction failed")
        raise DatabaseError("Database transaction failed") from exc
    finally:
        session.close()


ENGINE = create_database_engine()
SessionLocal = create_session_factory(ENGINE)
