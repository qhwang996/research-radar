"""Crawl-related CLI commands."""

from __future__ import annotations

from datetime import date
import logging
from pathlib import Path

import click

from src.cli.main import handle_command_errors
from src.crawlers.registry import BLOG_CRAWLER_REGISTRY, PAPER_CRAWLER_REGISTRY

logger = logging.getLogger(__name__)


@click.command("crawl")
@click.option("--source", type=str, default=None, help="Specific source slug to crawl.")
@click.option("--years", type=str, default=None, help='Comma-separated years, e.g. "2025,2026".')
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True, writable=True),
    default=Path("data/raw"),
    show_default=True,
    help="Output directory for raw JSON files.",
)
@handle_command_errors
def crawl_command(source: str | None, years: str | None, output_dir: Path) -> None:
    """Run one or more crawlers and persist raw JSON."""

    target_output_dir = output_dir.resolve()
    target_output_dir.mkdir(parents=True, exist_ok=True)
    year_list = _parse_years(years)

    if source is None:
        _crawl_all_sources(year_list, target_output_dir)
        return

    normalized_source = source.strip().lower()
    if normalized_source in PAPER_CRAWLER_REGISTRY:
        crawler = PAPER_CRAWLER_REGISTRY[normalized_source]()
        items = crawler.fetch_papers(year_list)
        output_path = crawler.save_raw(items, target_output_dir / "papers", metadata={"years": year_list})
        click.echo(f"Crawled {normalized_source}: {len(items)} items -> {output_path}")
        return

    if normalized_source in BLOG_CRAWLER_REGISTRY:
        crawler = BLOG_CRAWLER_REGISTRY[normalized_source]()
        items = crawler.fetch_articles(limit=20)
        output_path = crawler.save_raw(items, target_output_dir / "blogs", metadata={"limit": 20})
        click.echo(f"Crawled {normalized_source}: {len(items)} items -> {output_path}")
        return

    raise click.ClickException(f"Unknown source: {source}")


def _parse_years(raw_years: str | None) -> list[int]:
    """Parse a comma-separated year list or default to the current year."""

    if raw_years is None:
        return [date.today().year]

    values = [item.strip() for item in raw_years.split(",") if item.strip()]
    if not values:
        return [date.today().year]

    try:
        return list(dict.fromkeys(int(value) for value in values))
    except ValueError as exc:
        raise click.ClickException(f"Invalid year list: {raw_years}") from exc


def _crawl_all_sources(years: list[int], output_dir: Path) -> None:
    """Run all registered crawlers."""

    for name, crawler_cls in PAPER_CRAWLER_REGISTRY.items():
        crawler = crawler_cls()
        items = crawler.fetch_papers(years)
        output_path = crawler.save_raw(items, output_dir / "papers", metadata={"years": years})
        logger.info("Crawled %s -> %s", name, output_path)
        click.echo(f"Crawled {name}: {len(items)} items -> {output_path}")

    for name, crawler_cls in BLOG_CRAWLER_REGISTRY.items():
        crawler = crawler_cls()
        items = crawler.fetch_articles(limit=20)
        output_path = crawler.save_raw(items, output_dir / "blogs", metadata={"limit": 20})
        logger.info("Crawled %s -> %s", name, output_path)
        click.echo(f"Crawled {name}: {len(items)} items -> {output_path}")
