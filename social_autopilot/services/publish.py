"""Publish today's calendar items to configured platforms."""

from __future__ import annotations

import logging
from pathlib import Path

from social_autopilot.calendar_loader import load_for_date, today_in_tz
from social_autopilot.clients.http_utils import APIError
from social_autopilot.clients.meta_facebook import FacebookPageClient
from social_autopilot.clients.meta_instagram import InstagramBusinessClient
from social_autopilot.clients.x_twitter import XTwitterClient
from social_autopilot.config import Settings
from social_autopilot.models import ContentItem, PublishResult

logger = logging.getLogger(__name__)

PLATFORM_ALIASES = {
    "fb": "facebook",
    "facebook": "facebook",
    "ig": "instagram",
    "instagram": "instagram",
    "x": "x",
    "twitter": "x",
    "x/twitter": "x",
}


def normalize_platform(name: str) -> str:
    return PLATFORM_ALIASES.get(name.lower().strip(), name.lower().strip())


def _publish_facebook(settings: Settings, item: ContentItem) -> PublishResult:
    if not settings.has_meta_page() and not settings.dry_run:
        return PublishResult(
            platform="facebook",
            success=False,
            error="META_ACCESS_TOKEN / META_PAGE_ID not configured",
        )
    # Allow dry-run without credentials
    client = FacebookPageClient(settings)
    try:
        if item.media and Path(item.media).exists():
            data = client.publish_photo(item.full_text, Path(item.media))
        else:
            data = client.publish_text(item.full_text, link=item.link)
        post_id = data.get("post_id") or data.get("id")
        if settings.dry_run:
            post_id = post_id or "dry-run-fb"
        return PublishResult(
            platform="facebook",
            success=True,
            post_id=str(post_id) if post_id else None,
            dry_run=settings.dry_run,
            message="Published" if not settings.dry_run else "DRY_RUN: would publish to Facebook",
        )
    except APIError as exc:
        logger.error("Facebook publish failed: %s", exc)
        return PublishResult(platform="facebook", success=False, error=str(exc))
    finally:
        client.close()


def _publish_instagram(settings: Settings, item: ContentItem) -> PublishResult:
    if not settings.has_instagram() and not settings.dry_run:
        return PublishResult(
            platform="instagram",
            success=False,
            error="META_ACCESS_TOKEN / META_IG_USER_ID not configured",
        )
    client = InstagramBusinessClient(settings)
    try:
        image_url = None
        if item.raw.get("image_url"):
            image_url = str(item.raw["image_url"])
        elif item.link and str(item.link).startswith("http"):
            # optional: treat link as image host only if explicitly tagged
            image_url = None

        media_path = Path(item.media) if item.media else None
        if not image_url and not media_path and not settings.dry_run:
            return PublishResult(
                platform="instagram",
                success=False,
                error="Instagram requires image_url (public) or media path for dry-run",
            )
        if settings.dry_run and not media_path and not image_url:
            # Still demonstrate the call chain
            media_path = Path("content/samples/placeholder.jpg")

        data = client.publish_image(
            item.full_text,
            image_url=image_url,
            image_path=media_path,
        )
        post_id = data.get("id")
        if settings.dry_run:
            post_id = post_id or "dry-run-ig"
        return PublishResult(
            platform="instagram",
            success=True,
            post_id=str(post_id) if post_id else None,
            dry_run=settings.dry_run,
            message="Published" if not settings.dry_run else "DRY_RUN: would publish to Instagram",
        )
    except APIError as exc:
        logger.error("Instagram publish failed: %s", exc)
        return PublishResult(platform="instagram", success=False, error=str(exc))
    finally:
        client.close()


def _publish_x(settings: Settings, item: ContentItem) -> PublishResult:
    if not settings.has_x() and not settings.dry_run:
        return PublishResult(
            platform="x",
            success=False,
            error="X credentials not configured (OAuth1 or Bearer)",
        )
    client = XTwitterClient(settings)
    try:
        text = item.full_text
        # X hard limit 280 for standard; truncate gracefully
        if len(text) > 280:
            text = text[:277] + "..."
        data = client.create_tweet(text)
        post_id = (data.get("data") or {}).get("id") or data.get("id")
        if settings.dry_run:
            post_id = post_id or "dry-run-x"
        return PublishResult(
            platform="x",
            success=True,
            post_id=str(post_id) if post_id else None,
            dry_run=settings.dry_run,
            message="Published" if not settings.dry_run else "DRY_RUN: would publish to X",
        )
    except APIError as exc:
        logger.error("X publish failed: %s", exc)
        return PublishResult(platform="x", success=False, error=str(exc))
    finally:
        client.close()


PUBLISHERS = {
    "facebook": _publish_facebook,
    "instagram": _publish_instagram,
    "x": _publish_x,
}


def publish_item(settings: Settings, item: ContentItem) -> list[PublishResult]:
    results: list[PublishResult] = []
    for raw_platform in item.platforms:
        platform = normalize_platform(raw_platform)
        publisher = PUBLISHERS.get(platform)
        if not publisher:
            results.append(
                PublishResult(
                    platform=platform,
                    success=False,
                    error=f"Unsupported platform: {raw_platform}",
                )
            )
            continue
        results.append(publisher(settings, item))
    return results


def run_publish(settings: Settings) -> list[PublishResult]:
    """Load today's content and publish within daily_post_cap."""
    target = today_in_tz(settings.timezone)
    items = load_for_date(settings.content_dir, target, settings.timezone)
    if not items:
        logger.warning("No content found for %s under %s", target, settings.content_dir)
        return []

    results: list[PublishResult] = []
    posts_done = 0
    for item in items:
        if posts_done >= settings.daily_post_cap:
            logger.warning(
                "Daily post cap (%d) reached — skipping remaining items",
                settings.daily_post_cap,
            )
            break
        item_results = publish_item(settings, item)
        results.extend(item_results)
        posts_done += sum(1 for r in item_results if r.success)
    return results
