"""Facebook Page publishing via Meta Graph API (official)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx

from social_autopilot.clients.http_utils import APIError, dry_run_log, request_with_retry
from social_autopilot.config import Settings

logger = logging.getLogger(__name__)


class FacebookPageClient:
    """Publish text/photo posts and read comments on a Facebook Page."""

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self._client = client
        self._owns_client = client is None

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.settings.http_timeout)
            self._owns_client = True
        return self._client

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> FacebookPageClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @property
    def page_id(self) -> str:
        return self.settings.meta_page_id or ("{page-id}" if self.settings.dry_run else "")

    def _token_params(self) -> dict[str, str]:
        return {"access_token": self.settings.meta_access_token}

    def publish_text(self, message: str, link: str | None = None) -> dict[str, Any]:
        """POST /{page-id}/feed — create a Page post."""
        url = f"{self.settings.graph_base}/{self.page_id}/feed"
        payload: dict[str, Any] = {"message": message, **self._token_params()}
        if link:
            payload["link"] = link

        if self.settings.dry_run:
            return dry_run_log("POST", url, json={**payload, "access_token": "***"})

        resp = request_with_retry(
            "POST",
            url,
            client=self._http(),
            data=payload,
            max_retries=self.settings.http_max_retries,
            backoff_base=self.settings.http_backoff_base,
            timeout=self.settings.http_timeout,
        )
        data = resp.json()
        logger.info("Facebook post created: %s", data.get("id"))
        return data

    def publish_photo(self, message: str, image_path: Path) -> dict[str, Any]:
        """POST /{page-id}/photos — publish a photo with caption."""
        url = f"{self.settings.graph_base}/{self.page_id}/photos"

        if self.settings.dry_run:
            return dry_run_log(
                "POST",
                url,
                data={"message": message, "access_token": "***"},
                files={"source": str(image_path)},
            )

        if not image_path.exists():
            raise APIError(f"Media file not found: {image_path}")

        with image_path.open("rb") as fh:
            resp = request_with_retry(
                "POST",
                url,
                client=self._http(),
                data={"caption": message, "access_token": self.settings.meta_access_token},
                files={"source": (image_path.name, fh, "image/jpeg")},
                max_retries=self.settings.http_max_retries,
                backoff_base=self.settings.http_backoff_base,
                timeout=self.settings.http_timeout,
            )
        data = resp.json()
        # photos endpoint returns {id, post_id}
        logger.info("Facebook photo published: %s", data.get("post_id") or data.get("id"))
        return data

    def list_recent_posts(self, limit: int = 10) -> list[dict[str, Any]]:
        """GET /{page-id}/posts"""
        url = f"{self.settings.graph_base}/{self.page_id}/posts"
        params = {**self._token_params(), "limit": str(limit), "fields": "id,message,created_time"}

        if self.settings.dry_run:
            dry_run_log("GET", url, params={**params, "access_token": "***"})
            return []

        resp = request_with_retry(
            "GET",
            url,
            client=self._http(),
            params=params,
            max_retries=self.settings.http_max_retries,
            backoff_base=self.settings.http_backoff_base,
            timeout=self.settings.http_timeout,
        )
        return list(resp.json().get("data") or [])

    def list_comments(self, post_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """GET /{post-id}/comments — comments on OUR post only."""
        url = f"{self.settings.graph_base}/{post_id}/comments"
        params = {
            **self._token_params(),
            "limit": str(limit),
            "fields": "id,from,message,created_time,can_comment",
            "filter": "toplevel",
        }

        if self.settings.dry_run:
            dry_run_log("GET", url, params={**params, "access_token": "***"})
            return []

        resp = request_with_retry(
            "GET",
            url,
            client=self._http(),
            params=params,
            max_retries=self.settings.http_max_retries,
            backoff_base=self.settings.http_backoff_base,
            timeout=self.settings.http_timeout,
        )
        return list(resp.json().get("data") or [])

    def reply_to_comment(self, comment_id: str, message: str) -> dict[str, Any]:
        """POST /{comment-id}/comments — reply on our own post's comment thread."""
        url = f"{self.settings.graph_base}/{comment_id}/comments"
        payload = {"message": message, **self._token_params()}

        if self.settings.dry_run:
            return dry_run_log("POST", url, json={**payload, "access_token": "***"})

        resp = request_with_retry(
            "POST",
            url,
            client=self._http(),
            data=payload,
            max_retries=self.settings.http_max_retries,
            backoff_base=self.settings.http_backoff_base,
            timeout=self.settings.http_timeout,
        )
        data = resp.json()
        logger.info("Facebook reply created: %s", data.get("id"))
        return data

    def page_insights(self, metrics: list[str] | None = None) -> dict[str, Any]:
        """GET /{page-id}/insights — may fail without pages_read_engagement."""
        metrics = metrics or ["page_impressions", "page_engaged_users"]
        url = f"{self.settings.graph_base}/{self.page_id}/insights"
        params = {
            **self._token_params(),
            "metric": ",".join(metrics),
            "period": "day",
        }

        if self.settings.dry_run:
            return dry_run_log("GET", url, params={**params, "access_token": "***"})

        resp = request_with_retry(
            "GET",
            url,
            client=self._http(),
            params=params,
            max_retries=self.settings.http_max_retries,
            backoff_base=self.settings.http_backoff_base,
            timeout=self.settings.http_timeout,
        )
        return resp.json()
