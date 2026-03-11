"""Normalization, enrichment, scoring, and full-run CLI commands."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import click

from src.cli.crawl import _crawl_all_sources
from src.cli.main import AppContext, handle_command_errors, parse_date_option, pass_app_context
from src.llm import LLMClient
from src.pipelines.enrichment import EnrichmentPipeline
from src.pipelines.normalization import NormalizationPipeline
from src.reporting.daily import DailyReportGenerator
from src.reporting.weekly import WeeklyReportGenerator
from src.scoring.engine import ScoringEngine


def build_llm_client(provider: str) -> LLMClient:
    """Build an LLM client for one provider name."""

    return LLMClient(provider=provider)


@click.command("normalize")
@click.option(
    "--input-dir",
    type=click.Path(path_type=Path),
    default=Path("data/raw"),
    show_default=True,
    help="Input raw JSON directory or file.",
)
@click.option("--recursive/--no-recursive", default=True, show_default=True, help="Scan subdirectories recursively.")
@pass_app_context
@handle_command_errors
def normalize_command(app: AppContext, input_dir: Path, recursive: bool) -> None:
    """Process raw JSON files into normalized artifacts."""

    target = _resolve_normalization_input(input_dir, recursive)
    pipeline = NormalizationPipeline(session_factory=app.session_factory, engine=app.engine)
    artifacts = pipeline.process(target)
    click.echo(f"Normalized {len(artifacts)} artifact entries")


@click.command("enrich")
@click.option(
    "--provider",
    type=click.Choice(["openai", "anthropic"], case_sensitive=False),
    default="openai",
    show_default=True,
    help="LLM provider to use for enrichment.",
)
@click.option("--artifact-id", type=int, default=None, help="Target a specific artifact by DB id.")
@pass_app_context
@handle_command_errors
def enrich_command(app: AppContext, provider: str, artifact_id: int | None) -> None:
    """Generate LLM summaries and tags."""

    llm_client = build_llm_client(provider)
    pipeline = EnrichmentPipeline(session_factory=app.session_factory, llm_client=llm_client)
    enriched = pipeline.process(artifact_id)
    click.echo(f"Enriched {len(enriched)} artifacts")


@click.command("score")
@pass_app_context
@handle_command_errors
def score_command(app: AppContext) -> None:
    """Score persisted artifacts."""

    artifacts = ScoringEngine(session_factory=app.session_factory).score_all()
    click.echo(f"Scored {len(artifacts)} artifacts")


@click.command("run")
@click.option("--skip-crawl", is_flag=True, help="Skip the crawl step.")
@click.option(
    "--provider",
    type=click.Choice(["openai", "anthropic"], case_sensitive=False),
    default="openai",
    show_default=True,
    help="LLM provider for enrichment.",
)
@click.option(
    "--report-type",
    type=click.Choice(["daily", "weekly"], case_sensitive=False),
    default="daily",
    show_default=True,
    help="Report type to generate.",
)
@click.option("--date", "target_date_raw", type=str, default=None, help="Target date in YYYY-MM-DD format.")
@pass_app_context
@handle_command_errors
def run_command(
    app: AppContext,
    skip_crawl: bool,
    provider: str,
    report_type: str,
    target_date_raw: str | None,
) -> None:
    """Run normalize → enrich → score → report sequentially."""

    target_date = parse_date_option(target_date_raw)
    raw_input_dir = Path("data/raw")

    if not skip_crawl:
        raw_input_dir.mkdir(parents=True, exist_ok=True)
        _crawl_all_sources([date.today().year], raw_input_dir.resolve())

    normalization_target = _resolve_normalization_input(raw_input_dir, recursive=True)
    normalized = NormalizationPipeline(session_factory=app.session_factory, engine=app.engine).process(normalization_target)
    click.echo(f"Normalized {len(normalized)} artifact entries")

    llm_client = build_llm_client(provider)
    enriched = EnrichmentPipeline(session_factory=app.session_factory, llm_client=llm_client).process(None)
    click.echo(f"Enriched {len(enriched)} artifacts")

    scored = ScoringEngine(session_factory=app.session_factory).score_all()
    click.echo(f"Scored {len(scored)} artifacts")

    report_path = _generate_report(app, report_type, target_date)
    click.echo(f"Generated {report_type} report: {report_path}")


def _resolve_normalization_input(input_dir: Path, recursive: bool) -> Path | list[Path]:
    """Resolve CLI normalize input into a pipeline-compatible target."""

    target = input_dir.resolve()
    if not target.exists():
        raise click.ClickException(f"Input path does not exist: {input_dir}")
    if target.is_file():
        return target
    if recursive:
        return target
    files = sorted(target.glob("*.json"))
    if not files:
        raise click.ClickException(f"No JSON files found in: {input_dir}")
    return files


def _generate_report(app: AppContext, report_type: str, target_date: date) -> Path:
    """Generate one report and return its output path."""

    normalized_report_type = report_type.lower()
    if normalized_report_type == "daily":
        return DailyReportGenerator(session_factory=app.session_factory).generate(target_date)
    if normalized_report_type == "weekly":
        return WeeklyReportGenerator(session_factory=app.session_factory).generate(target_date)
    raise click.ClickException(f"Unsupported report type: {report_type}")
