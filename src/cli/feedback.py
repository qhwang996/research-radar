"""Feedback CLI command."""

from __future__ import annotations

import click

from src.cli.main import AppContext, handle_command_errors, pass_app_context
from src.feedback import FeedbackCollector
from src.models.enums import FeedbackType


@click.command("feedback")
@click.option("--artifact-id", type=int, required=True, help="Target artifact DB id.")
@click.option(
    "--type",
    "feedback_type_raw",
    type=click.Choice(["like", "dislike", "note", "read"], case_sensitive=False),
    required=True,
    help="Feedback type.",
)
@click.option("--note", type=str, default=None, help="Optional note text.")
@pass_app_context
@handle_command_errors
def feedback_command(
    app: AppContext,
    artifact_id: int,
    feedback_type_raw: str,
    note: str | None,
) -> None:
    """Provide feedback on one artifact."""

    feedback_type = FeedbackType(feedback_type_raw.lower())
    if feedback_type == FeedbackType.NOTE and not (note or "").strip():
        raise click.ClickException("--note is required when --type=note")

    event = FeedbackCollector(session_factory=app.session_factory).collect_artifact_feedback(
        artifact_id,
        feedback_type,
        note=note,
    )
    click.echo(f"Saved feedback event {event.event_id} for artifact {artifact_id}")
