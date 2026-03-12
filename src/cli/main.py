"""Top-level click CLI entrypoint."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import wraps
import logging
from pathlib import Path
from typing import Any, Callable, TypeVar, cast

import click
from dotenv import load_dotenv
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.db.session import create_all_tables, create_database_engine, create_session_factory, get_database_url

load_dotenv()

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AppContext:
    """Shared runtime context for CLI commands."""

    engine: Engine
    session_factory: sessionmaker[Session]
    database_url: str
    verbose: bool = False


pass_app_context = click.make_pass_decorator(AppContext, ensure=True)
CommandFunc = TypeVar("CommandFunc", bound=Callable[..., Any])


def configure_logging(verbose: bool) -> None:
    """Configure project logging for CLI usage."""

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )


def parse_date_option(raw_value: str | None) -> date:
    """Parse an ISO date string or return today if omitted."""

    if raw_value is None:
        return date.today()
    try:
        return date.fromisoformat(raw_value)
    except ValueError as exc:
        raise click.ClickException(f"Invalid date format: {raw_value}. Expected YYYY-MM-DD.") from exc


def handle_command_errors(func: CommandFunc) -> CommandFunc:
    """Convert unexpected exceptions into click-friendly failures."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except click.ClickException:
            raise
        except Exception as exc:  # pragma: no cover - defensive boundary
            logger.debug("CLI command failed", exc_info=True)
            logger.error("%s", exc)
            raise click.ClickException(str(exc)) from exc

    return cast(CommandFunc, wrapper)


@click.group(name="research-radar")
@click.option(
    "--database-url",
    default=None,
    envvar="DATABASE_URL",
    help="Database URL. Defaults to the configured project database.",
)
@click.option("--verbose", is_flag=True, help="Enable debug logging.")
@click.pass_context
def cli(ctx: click.Context, database_url: str | None, verbose: bool) -> None:
    """Research Radar command-line interface."""

    configure_logging(verbose)
    resolved_database_url = database_url or get_database_url()
    engine = create_database_engine(resolved_database_url)
    create_all_tables(engine)
    ctx.obj = AppContext(
        engine=engine,
        session_factory=create_session_factory(engine),
        database_url=resolved_database_url,
        verbose=verbose,
    )


from src.cli.crawl import crawl_command  # noqa: E402
from src.cli.feedback import feedback_command  # noqa: E402
from src.cli.maintenance import cleanup_ccs_command  # noqa: E402
from src.cli.profile import profile_command  # noqa: E402
from src.cli.process import enrich_command, llm_relevance_command, normalize_command, run_command, score_command  # noqa: E402
from src.cli.report import report_command  # noqa: E402

cli.add_command(crawl_command)
cli.add_command(cleanup_ccs_command)
cli.add_command(normalize_command)
cli.add_command(enrich_command)
cli.add_command(llm_relevance_command)
cli.add_command(score_command)
cli.add_command(report_command)
cli.add_command(feedback_command)
cli.add_command(profile_command)
cli.add_command(run_command)
