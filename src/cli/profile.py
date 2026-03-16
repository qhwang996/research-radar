"""Profile management CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

import click

from src.cli.main import AppContext, handle_command_errors, pass_app_context
from src.models.profile import Profile
from src.repositories.profile_repository import ProfileRepository

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SEED_PROFILE_PATH = PROJECT_ROOT / "data" / "seed_profile.json"
SEED_PROFILE_V2_PATH = PROJECT_ROOT / "data" / "seed_profile_v2.json"


@click.group("profile")
def profile_command() -> None:
    """Manage user profile snapshots."""


@profile_command.command("seed")
@pass_app_context
@handle_command_errors
def profile_seed_command(app: AppContext) -> None:
    """Seed one default active profile when none exists."""

    session = app.session_factory()
    try:
        repository = ProfileRepository(session)
        if repository.get_latest_active() is not None:
            click.echo("Active profile already exists, skipping.")
            return

        payload = _load_seed_profile_payload(SEED_PROFILE_PATH)
        profile = repository.save(Profile(**payload))
    finally:
        session.close()

    click.echo(f"Seeded profile: {profile.profile_version}")


@profile_command.command("seed-v2")
@pass_app_context
@handle_command_errors
def profile_seed_v2_command(app: AppContext) -> None:
    """Seed the v2 broad profile, deactivating any existing active profile."""

    session = app.session_factory()
    try:
        repository = ProfileRepository(session)
        existing = repository.get_latest_active()
        if existing is not None:
            existing.is_active = False
            repository.save(existing)

        payload = _load_seed_profile_payload(SEED_PROFILE_V2_PATH)
        profile = repository.save(Profile(**payload))
    finally:
        session.close()

    click.echo(f"Seeded v2 profile: {profile.profile_version}")


@profile_command.command("show")
@pass_app_context
@handle_command_errors
def profile_show_command(app: AppContext) -> None:
    """Print the currently active profile fields as JSON."""

    session = app.session_factory()
    try:
        profile = ProfileRepository(session).get_latest_active()
    finally:
        session.close()

    if profile is None:
        raise click.ClickException("No active profile found.")

    click.echo(
        json.dumps(
            {
                "profile_version": profile.profile_version,
                "current_research_area": profile.current_research_area,
                "interests": profile.interests,
                "domain_scope": profile.domain_scope,
                "preferred_topics": profile.preferred_topics,
                "avoided_topics": profile.avoided_topics,
                "direction_preferences": profile.direction_preferences,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def _load_seed_profile_payload(path: Path) -> dict[str, object]:
    """Load and validate the seed profile payload from disk."""

    return json.loads(path.read_text(encoding="utf-8"))
