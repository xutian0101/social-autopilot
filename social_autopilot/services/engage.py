"""Light engagement: reply to comments on OUR posts only."""

from __future__ import annotations

import logging

from social_autopilot.clients.http_utils import APIError
from social_autopilot.clients.meta_facebook import FacebookPageClient
from social_autopilot.clients.meta_instagram import InstagramBusinessClient
from social_autopilot.clients.x_twitter import XTwitterClient
from social_autopilot.config import Settings
from social_autopilot.models import EngageResult
from social_autopilot.services.templates import craft_reply

logger = logging.getLogger(__name__)


def _engage_facebook(settings: Settings, remaining: int) -> list[EngageResult]:
    results: list[EngageResult] = []
    if remaining <= 0:
        return results
    if not settings.has_meta_page() and not settings.dry_run:
        logger.warning("Skip Facebook engage: credentials missing")
        return results

    client = FacebookPageClient(settings)
    try:
        if settings.dry_run:
            # Demonstrate intended flow without network
            logger.info(
                "[DRY_RUN] Would list Page posts + comments and reply "
                "(cap=%d, max_per_post=%d)",
                remaining,
                settings.max_replies_per_post,
            )
            results.append(
                EngageResult(
                    platform="facebook",
                    post_id="dry-run-fb-post",
                    comment_id="dry-run-fb-comment",
                    reply_id="dry-run-fb-reply",
                    dry_run=True,
                    reply_text=craft_reply(settings, "Love this serum!"),
                )
            )
            return results

        posts = client.list_recent_posts(limit=5)
        for post in posts:
            if remaining <= 0:
                break
            post_id = post["id"]
            comments = client.list_comments(post_id)
            replied_on_post = 0
            for comment in comments:
                if remaining <= 0 or replied_on_post >= settings.max_replies_per_post:
                    break
                # Skip our own comments if identifiable
                from_id = (comment.get("from") or {}).get("id")
                if from_id and from_id == settings.meta_page_id:
                    continue
                text = comment.get("message") or ""
                reply = craft_reply(settings, text)
                try:
                    data = client.reply_to_comment(comment["id"], reply)
                    results.append(
                        EngageResult(
                            platform="facebook",
                            post_id=post_id,
                            comment_id=comment["id"],
                            reply_id=str(data.get("id")),
                            reply_text=reply,
                        )
                    )
                    remaining -= 1
                    replied_on_post += 1
                except APIError as exc:
                    results.append(
                        EngageResult(
                            platform="facebook",
                            post_id=post_id,
                            comment_id=comment["id"],
                            reply_text=reply,
                            error=str(exc),
                        )
                    )
    finally:
        client.close()
    return results


def _engage_instagram(settings: Settings, remaining: int) -> list[EngageResult]:
    results: list[EngageResult] = []
    if remaining <= 0:
        return results
    if not settings.has_instagram() and not settings.dry_run:
        logger.warning("Skip Instagram engage: credentials missing")
        return results

    client = InstagramBusinessClient(settings)
    try:
        if settings.dry_run:
            logger.info("[DRY_RUN] Would list IG media comments and reply")
            results.append(
                EngageResult(
                    platform="instagram",
                    post_id="dry-run-ig-media",
                    comment_id="dry-run-ig-comment",
                    reply_id="dry-run-ig-reply",
                    dry_run=True,
                    reply_text=craft_reply(settings, "This packing is so cute!"),
                )
            )
            return results

        media_list = client.list_media(limit=5)
        for media in media_list:
            if remaining <= 0:
                break
            media_id = media["id"]
            comments = client.list_comments(media_id)
            replied_on_post = 0
            for comment in comments:
                if remaining <= 0 or replied_on_post >= settings.max_replies_per_post:
                    break
                text = comment.get("text") or comment.get("message") or ""
                reply = craft_reply(settings, text)
                try:
                    data = client.reply_to_comment(comment["id"], reply)
                    results.append(
                        EngageResult(
                            platform="instagram",
                            post_id=media_id,
                            comment_id=comment["id"],
                            reply_id=str(data.get("id")),
                            reply_text=reply,
                        )
                    )
                    remaining -= 1
                    replied_on_post += 1
                except APIError as exc:
                    results.append(
                        EngageResult(
                            platform="instagram",
                            post_id=media_id,
                            comment_id=comment["id"],
                            reply_text=reply,
                            error=str(exc),
                        )
                    )
    finally:
        client.close()
    return results


def _engage_x(settings: Settings, remaining: int) -> list[EngageResult]:
    results: list[EngageResult] = []
    if remaining <= 0:
        return results
    if not settings.has_x() and not settings.dry_run:
        logger.warning("Skip X engage: credentials missing")
        return results

    client = XTwitterClient(settings)
    try:
        if settings.dry_run:
            logger.info("[DRY_RUN] Would search replies to our tweets and reply")
            results.append(
                EngageResult(
                    platform="x",
                    post_id="dry-run-x-tweet",
                    comment_id="dry-run-x-reply-tweet",
                    reply_id="dry-run-x-our-reply",
                    dry_run=True,
                    reply_text=craft_reply(settings, "Need this in my routine!"),
                )
            )
            return results

        tweets = client.list_recent_tweets(max_results=5)
        for tweet in tweets:
            if remaining <= 0:
                break
            tweet_id = tweet["id"]
            replies = client.search_replies_to_tweet(tweet_id)
            replied_on_post = 0
            for reply_tweet in replies:
                if remaining <= 0 or replied_on_post >= settings.max_replies_per_post:
                    break
                # Do not reply to ourselves
                if reply_tweet.get("author_id") and client._user_id:
                    if reply_tweet["author_id"] == client._user_id:
                        continue
                text = reply_tweet.get("text") or ""
                reply = craft_reply(settings, text)
                # Keep X replies short
                if len(reply) > 280:
                    reply = reply[:277] + "..."
                try:
                    data = client.reply_to_tweet(reply_tweet["id"], reply)
                    rid = (data.get("data") or {}).get("id")
                    results.append(
                        EngageResult(
                            platform="x",
                            post_id=tweet_id,
                            comment_id=reply_tweet["id"],
                            reply_id=str(rid) if rid else None,
                            reply_text=reply,
                        )
                    )
                    remaining -= 1
                    replied_on_post += 1
                except APIError as exc:
                    results.append(
                        EngageResult(
                            platform="x",
                            post_id=tweet_id,
                            comment_id=reply_tweet["id"],
                            reply_text=reply,
                            error=str(exc),
                        )
                    )
    finally:
        client.close()
    return results


def run_engage(settings: Settings) -> list[EngageResult]:
    """
    Reply to comments on OUR posts only.
    No mass-follow, mass-DM, or engagement pods — by design.
    """
    remaining = settings.daily_engage_cap
    results: list[EngageResult] = []
    results.extend(_engage_facebook(settings, remaining))
    remaining = settings.daily_engage_cap - len(
        [r for r in results if r.error is None]
    )
    results.extend(_engage_instagram(settings, remaining))
    remaining = settings.daily_engage_cap - len(
        [r for r in results if r.error is None]
    )
    results.extend(_engage_x(settings, remaining))
    logger.info("Engage finished: %d action(s)", len(results))
    return results
