"""Instagram Business Content Publishing API via Meta Graph."""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx

from social_autopilot.clients.http_utils import APIError, dry_run_log, request_with_retry
from social_autopilot.config import Settings

logger = logging.getLogger(__name__)


class InstagramBusinessClient:
    """
    Instagram Content Publishing:
      1. POST /{ig-user-id}/media  (create container)
      2. GET  /{creation-id}?fields=status_code  (poll)
      3. POST /{ig-user-id}/media_publish
    """

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

    def __enter__(self) -> InstagramBusinessClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    @property
    def ig_user_id(self) -> str:
        return self.settings.meta_ig_user_id or ("{ig-user-id}" if self.settings.dry_run else "")

    def _token_params(self) -> dict[str, str]:
        return {"access_token": self.settings.meta_access_token}

    def create_image_container(
        self,
        caption: str,
        *,
        image_url: str | None = None,
        image_path: Path | None = None,
    ) -> dict[str, Any]:
        """
        Create a media container.
        Graph Content Publishing requires a publicly reachable image_url.
        Local paths are logged in DRY_RUN; live mode needs image_url.
        """
        url = f"{self.settings.graph_base}/{self.ig_user_id}/media"
        payload: dict[str, Any] = {
            "caption": caption,
            **self._token_params(),
        }

        if image_url:
            payload["image_url"] = image_url
        elif image_path:
            # Official API does not accept local file upload for IG publishing;
            # callers should host the image. We still accept path for dry-run demos.
            payload["image_url"] = f"file://{image_path}"
        else:
            raise APIError("Instagram publish requires image_url or image_path")

        if self.settings.dry_run:
            return dry_run_log(
                "POST",
                url,
                json={**payload, "access_token": "***"},
            )

        if image_path and not image_url:
            raise APIError(
                "Live Instagram publishing requires a public image_url "
                "(Graph Content Publishing API). Host the media and set media URL."
            )
        if image_url and urlparse(image_url).scheme not in {"http", "https"}:
            raise APIError(f"Invalid image_url scheme: {image_url}")

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
        logger.info("IG media container created: %s", data.get("id"))
        return data

    def wait_for_container(self, creation_id: str, timeout_s: float = 60.0) -> dict[str, Any]:
        """Poll GET /{creation-id}?fields=status_code until FINISHED."""
        url = f"{self.settings.graph_base}/{creation_id}"
        params = {**self._token_params(), "fields": "status_code,status"}

        if self.settings.dry_run:
            return dry_run_log("GET", url, params={**params, "access_token": "***"})

        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            resp = request_with_retry(
                "GET",
                url,
                client=self._http(),
                params=params,
                max_retries=self.settings.http_max_retries,
                backoff_base=self.settings.http_backoff_base,
                timeout=self.settings.http_timeout,
            )
            data = resp.json()
            status = (data.get("status_code") or "").upper()
            if status == "FINISHED":
                return data
            if status == "ERROR":
                raise APIError(f"IG container error: {data}", payload=data)
            time.sleep(2.0)
        raise APIError(f"IG container {creation_id} not ready within {timeout_s}s")

    def publish_container(self, creation_id: str) -> dict[str, Any]:
        """POST /{ig-user-id}/media_publish"""
        url = f"{self.settings.graph_base}/{self.ig_user_id}/media_publish"
        payload = {"creation_id": creation_id, **self._token_params()}

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
        logger.info("IG media published: %s", data.get("id"))
        return data

    def publish_image(
        self,
        caption: str,
        *,
        image_url: str | None = None,
        image_path: Path | None = None,
    ) -> dict[str, Any]:
        """Full create → wait → publish flow."""
        container = self.create_image_container(
            caption, image_url=image_url, image_path=image_path
        )
        if self.settings.dry_run:
            return {
                "dry_run": True,
                "container": container,
                "publish": dry_run_log(
                    "POST",
                    f"{self.settings.graph_base}/{self.ig_user_id}/media_publish",
                    json={"creation_id": "<dry-run>", "access_token": "***"},
                ),
            }
        creation_id = container["id"]
        self.wait_for_container(creation_id)
        return self.publish_container(creation_id)

    def list_media(self, limit: int = 10) -> list[dict[str, Any]]:
        """GET /{ig-user-id}/media"""
        url = f"{self.settings.graph_base}/{self.ig_user_id}/media"
        params = {
            **self._token_params(),
            "limit": str(limit),
            "fields": "id,caption,timestamp,permalink",
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

    def list_comments(self, media_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """GET /{ig-media-id}/comments — comments on OUR media only."""
        url = f"{self.settings.graph_base}/{media_id}/comments"
        params = {
            **self._token_params(),
            "limit": str(limit),
            "fields": "id,text,username,timestamp,from",
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
        """POST /{ig-comment-id}/replies"""
        url = f"{self.settings.graph_base}/{comment_id}/replies"
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
        logger.info("IG reply created: %s", data.get("id"))
        return data

    def insights(self, media_id: str, metrics: list[str] | None = None) -> dict[str, Any]:
        metrics = metrics or ["impressions", "reach", "engagement"]
        url = f"{self.settings.graph_base}/{media_id}/insights"
        params = {**self._token_params(), "metric": ",".join(metrics)}

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
