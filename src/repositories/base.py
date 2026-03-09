"""Shared repository helpers."""

from __future__ import annotations

import logging
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.db.base import Base
from src.exceptions import DatabaseError

ModelType = TypeVar("ModelType", bound=Base)

logger = logging.getLogger(__name__)


class BaseRepository(Generic[ModelType]):
    """Small SQLAlchemy repository wrapper for CRUD operations."""

    def __init__(self, session: Session, model_type: type[ModelType]) -> None:
        """Bind a repository to a SQLAlchemy session and model type."""

        self.session = session
        self.model_type = model_type

    def get_by_id(self, record_id: int) -> ModelType | None:
        """Return one record by integer primary key."""

        return self.session.get(self.model_type, record_id)

    def list_all(self) -> list[ModelType]:
        """Return all records for the repository model."""

        statement = select(self.model_type).order_by(self.model_type.id.asc())
        return list(self.session.scalars(statement))

    def save(self, instance: ModelType) -> ModelType:
        """Create or update a record and commit it."""

        try:
            self.session.add(instance)
            self.session.commit()
            self.session.refresh(instance)
            return instance
        except SQLAlchemyError as exc:
            self.session.rollback()
            logger.exception("Failed to save %s", self.model_type.__name__)
            raise DatabaseError(f"Failed to save {self.model_type.__name__}") from exc

    def delete(self, instance: ModelType) -> None:
        """Delete a record and commit the change."""

        try:
            self.session.delete(instance)
            self.session.commit()
        except SQLAlchemyError as exc:
            self.session.rollback()
            logger.exception("Failed to delete %s", self.model_type.__name__)
            raise DatabaseError(f"Failed to delete {self.model_type.__name__}") from exc
