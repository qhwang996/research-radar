"""Maintenance and one-off data cleanup CLI commands."""

from __future__ import annotations

from sqlalchemy import select

import click

from src.cli.main import AppContext, handle_command_errors, pass_app_context
from src.crawlers.ccs_crawler import CCSCrawler
from src.models.artifact import Artifact
from src.models.enums import ArtifactStatus


@click.command("cleanup-ccs")
@pass_app_context
@handle_command_errors
def cleanup_ccs_command(app: AppContext) -> None:
    """Delete historical ACM CCS non-full-paper artifacts from the database."""

    session = app.session_factory()
    try:
        artifacts = list(
            session.scalars(
                select(Artifact)
                .where(Artifact.source_name == CCSCrawler.source_name)
                .order_by(Artifact.id.asc())
            )
        )

        removed_status = getattr(ArtifactStatus, "REMOVED", None)
        matches = [artifact for artifact in artifacts if CCSCrawler._is_non_paper_title(artifact.title)]
        sample_titles = [artifact.title for artifact in matches[:5]]

        for artifact in matches:
            if removed_status is not None:
                artifact.status = removed_status
            else:
                session.delete(artifact)

        session.commit()
    finally:
        session.close()

    click.echo(f"Cleaned {len(matches)} ACM CCS non-full-paper artifacts")
    if sample_titles:
        click.echo("Sample titles:")
        for title in sample_titles:
            click.echo(f"- {title}")
