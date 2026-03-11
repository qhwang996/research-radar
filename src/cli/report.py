"""Report generation CLI command."""

from __future__ import annotations

import click

from src.cli.main import AppContext, handle_command_errors, parse_date_option, pass_app_context
from src.reporting.daily import DailyReportGenerator
from src.reporting.weekly import WeeklyReportGenerator


@click.command("report")
@click.option(
    "--type",
    "report_type",
    type=click.Choice(["daily", "weekly"], case_sensitive=False),
    required=True,
    help="Report type to generate.",
)
@click.option("--date", "target_date_raw", type=str, default=None, help="Target date in YYYY-MM-DD format.")
@pass_app_context
@handle_command_errors
def report_command(app: AppContext, report_type: str, target_date_raw: str | None) -> None:
    """Generate a daily or weekly report."""

    target_date = parse_date_option(target_date_raw)
    normalized_type = report_type.lower()
    if normalized_type == "daily":
        output_path = DailyReportGenerator(session_factory=app.session_factory).generate(target_date)
    else:
        output_path = WeeklyReportGenerator(session_factory=app.session_factory).generate(target_date)

    click.echo(f"Generated {normalized_type} report: {output_path}")
