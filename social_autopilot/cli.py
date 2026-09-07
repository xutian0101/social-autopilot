"""Typer CLI for Social Autopilot."""

from __future__ import annotations

import logging
import sys

import typer

from social_autopilot.config import load_settings
from social_autopilot.services.engage import run_engage
from social_autopilot.services.publish import run_publish
from social_autopilot.services.review import run_review

app = typer.Typer(
    name="social-autopilot",
    help="Cloud-ready daily social automation for beauty-brand marketing.",
    add_completion=False,
)


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


@app.command("publish")
def publish_cmd(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Publish today's content calendar items to selected platforms."""
    _setup_logging(verbose)
    settings = load_settings()
    typer.echo(f"DRY_RUN={settings.dry_run}  timezone={settings.timezone}")
    results = run_publish(settings)
    if not results:
        typer.echo("No publish results (no content for today?).")
        raise typer.Exit(code=0)
    for r in results:
        status = "OK" if r.success else "FAIL"
        detail = r.error or r.message or r.post_id or ""
        typer.echo(f"[{status}] {r.platform}: {detail}")
    if any(not r.success for r in results):
        raise typer.Exit(code=1)


@app.command("engage")
def engage_cmd(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Reply to comments on OUR posts only (templates / optional LLM)."""
    _setup_logging(verbose)
    settings = load_settings()
    typer.echo(f"DRY_RUN={settings.dry_run}  engage_cap={settings.daily_engage_cap}")
    results = run_engage(settings)
    for r in results:
        if r.error:
            typer.echo(f"[FAIL] {r.platform} comment={r.comment_id}: {r.error}")
        else:
            mode = "DRY" if r.dry_run else "OK"
            typer.echo(f"[{mode}] {r.platform} reply -> {r.comment_id}: {r.reply_text[:80]}")


@app.command("review")
def review_cmd(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Write today's retrospective markdown report under reports/."""
    _setup_logging(verbose)
    settings = load_settings()
    report = run_review(settings)
    typer.echo(f"Report written: {report.path}")


@app.command("run-daily")
def run_daily_cmd(
    verbose: bool = typer.Option(False, "--verbose", "-v"),
) -> None:
    """Publish → engage → review (typical cron / GitHub Actions entry)."""
    _setup_logging(verbose)
    settings = load_settings()
    typer.echo("=" * 60)
    typer.echo(f"Social Autopilot daily run  DRY_RUN={settings.dry_run}")
    typer.echo("=" * 60)

    publish_results = run_publish(settings)
    for r in publish_results:
        status = "OK" if r.success else "FAIL"
        typer.echo(f"[publish {status}] {r.platform}: {r.error or r.message}")

    engage_results = run_engage(settings)
    for r in engage_results:
        status = "FAIL" if r.error else ("DRY" if r.dry_run else "OK")
        typer.echo(f"[engage {status}] {r.platform}: {r.reply_text[:60]}")

    report = run_review(settings, publish_results, engage_results)
    typer.echo(f"[review] {report.path}")
    typer.echo("Done.")
