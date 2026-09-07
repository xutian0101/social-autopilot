"""Daily retrospective: write reports/YYYY-MM-DD.md."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from social_autopilot.calendar_loader import today_in_tz
from social_autopilot.clients.http_utils import APIError
from social_autopilot.clients.meta_facebook import FacebookPageClient
from social_autopilot.clients.meta_instagram import InstagramBusinessClient
from social_autopilot.config import Settings
from social_autopilot.models import DailyReport, EngageResult, PublishResult

logger = logging.getLogger(__name__)


def _try_facebook_insights(settings: Settings, notes: list[str]) -> str:
    if settings.dry_run:
        notes.append("DRY_RUN: skipped live Facebook insights fetch.")
        return "_DRY_RUN — insights not fetched._\n"
    if not settings.has_meta_page():
        notes.append("Facebook insights skipped: credentials missing.")
        return "_Not configured._\n"
    client = FacebookPageClient(settings)
    try:
        data = client.page_insights()
        lines = ["```json", str(data)[:2000], "```", ""]
        return "\n".join(lines)
    except APIError as exc:
        notes.append(
            "Facebook insights failed — ensure the token has "
            "`pages_read_engagement` / `read_insights` permissions. "
            f"Detail: {exc}"
        )
        return (
            "_Insights unavailable (permissions or API error). "
            "Actions below are still summarized._\n"
        )
    finally:
        client.close()


def _try_instagram_note(settings: Settings, notes: list[str]) -> str:
    if settings.dry_run:
        notes.append("DRY_RUN: skipped live Instagram insights fetch.")
        return "_DRY_RUN — insights not fetched._\n"
    if not settings.has_instagram():
        notes.append("Instagram insights skipped: credentials missing.")
        return "_Not configured._\n"
    client = InstagramBusinessClient(settings)
    try:
        media = client.list_media(limit=1)
        if not media:
            return "_No recent IG media to inspect._\n"
        data = client.insights(media[0]["id"])
        return "\n".join(["```json", str(data)[:2000], "```", ""])
    except APIError as exc:
        notes.append(
            "Instagram insights failed — need `instagram_manage_insights` "
            f"or equivalent. Detail: {exc}"
        )
        return "_Insights unavailable; see notes._\n"
    finally:
        client.close()


def render_report(
    report_date: date,
    publish_results: list[PublishResult],
    engage_results: list[EngageResult],
    notes: list[str],
    fb_section: str,
    ig_section: str,
    dry_run: bool,
) -> str:
    lines = [
        f"# Social Autopilot Daily Report — {report_date.isoformat()}",
        "",
        f"- Mode: **{'DRY_RUN' if dry_run else 'LIVE'}**",
        f"- Generated timezone: Asia/Shanghai (content calendar day)",
        "",
        "## Publish",
        "",
    ]
    if not publish_results:
        lines.append("_No publish actions._")
        lines.append("")
    else:
        lines.append("| Platform | Success | Post ID | Message / Error |")
        lines.append("|---|---|---|---|")
        for r in publish_results:
            msg = r.error or r.message
            lines.append(
                f"| {r.platform} | {r.success} | {r.post_id or '-'} | {msg} |"
            )
        lines.append("")

    lines.extend(["## Engage (own posts only)", ""])
    if not engage_results:
        lines.append("_No engage actions._")
        lines.append("")
    else:
        lines.append("| Platform | Post | Comment | Reply | Error |")
        lines.append("|---|---|---|---|---|")
        for r in engage_results:
            preview = (r.reply_text or "")[:60].replace("|", "/")
            lines.append(
                f"| {r.platform} | {r.post_id} | {r.comment_id} | "
                f"{preview} | {r.error or '-'} |"
            )
        lines.append("")

    lines.extend(
        [
            "## Insights",
            "",
            "### Facebook Page",
            "",
            fb_section,
            "### Instagram",
            "",
            ig_section,
            "## Notes",
            "",
        ]
    )
    if notes:
        for n in notes:
            lines.append(f"- {n}")
    else:
        lines.append("- None.")
    lines.append("")
    lines.append(
        "> Reminder: comply with Meta Platform Terms and X Developer Agreement. "
        "This tool only uses official APIs and replies on your own content."
    )
    lines.append("")
    return "\n".join(lines)


def run_review(
    settings: Settings,
    publish_results: list[PublishResult] | None = None,
    engage_results: list[EngageResult] | None = None,
) -> DailyReport:
    report_date = today_in_tz(settings.timezone)
    publish_results = publish_results or []
    engage_results = engage_results or []
    notes: list[str] = []

    fb_section = _try_facebook_insights(settings, notes)
    ig_section = _try_instagram_note(settings, notes)

    body = render_report(
        report_date,
        publish_results,
        engage_results,
        notes,
        fb_section,
        ig_section,
        settings.dry_run,
    )

    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    path = settings.reports_dir / f"{report_date.isoformat()}.md"
    path.write_text(body, encoding="utf-8")
    logger.info("Wrote daily report: %s", path)

    return DailyReport(
        report_date=report_date,
        path=path,
        publish_results=publish_results,
        engage_results=engage_results,
        notes=notes,
    )
