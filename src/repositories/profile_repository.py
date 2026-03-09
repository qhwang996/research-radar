"""Profile snapshot repository methods."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.models.profile import Profile
from src.repositories.base import BaseRepository


class ProfileRepository(BaseRepository[Profile]):
    """Repository for profile snapshots."""

    def __init__(self, session: Session) -> None:
        """Create a profile repository."""

        super().__init__(session, Profile)

    def get_by_profile_version(self, profile_version: str) -> Profile | None:
        """Return a profile snapshot by version."""

        statement = select(Profile).where(Profile.profile_version == profile_version)
        return self.session.scalar(statement)

    def get_latest(self) -> Profile | None:
        """Return the most recently created profile snapshot."""

        statement = select(Profile).order_by(Profile.created_at.desc(), Profile.id.desc())
        return self.session.scalar(statement)

    def get_latest_active(self) -> Profile | None:
        """Return the latest active profile snapshot."""

        statement = (
            select(Profile)
            .where(Profile.is_active.is_(True))
            .order_by(Profile.updated_at.desc(), Profile.id.desc())
        )
        return self.session.scalar(statement)
