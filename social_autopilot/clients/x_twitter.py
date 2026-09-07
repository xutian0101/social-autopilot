"""X (Twitter) API v2 client — official endpoints only."""

from __future__ import annotations

import logging
from typing import Any

import httpx

from social_autopilot.clients.http_utils import APIError, dry_run_log, request_with_retry
from social_autopilot.config import Settings

logger = logging.getLogger(__name__)


class XTwitterClient:
    """
    Post tweets and reply to comments (mentions / replies) on OUR tweets.
    Prefers OAuth 1.0a user context for write operations; Bearer for reads when available.
    """

    def __init__(self, settings: Settings, client: httpx.Client | None = None) -> None:
        self.settings = settings
        self._client = client
        self._owns_client = client is None
        self._user_id: str | None = None

    def _http(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=self.settings.http_timeout)
            self._owns_client = True
        return self._client

    def close(self) -> None:
        if self._owns_client and self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> XTwitterClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _auth(self) -> httpx.Auth | None:
        if self.settings.has_x_oauth1():
            from requests_oauthlib import OAuth1  # type: ignore[import-untyped]

            # httpx does not ship OAuth1; use a lightweight header builder below.
            # We keep requests-oauthlib optional — fall through to manual signing helper.
            _ = OAuth1  # silence unused if present
        return None

    def _oauth1_headers(
        self, method: str, url: str, extra: dict[str, str] | None = None
    ) -> dict[str, str]:
        """Build OAuth1 Authorization header via oauthlib if available."""
        try:
            from oauthlib.oauth1 import Client as OAuth1Client
        except ImportError as exc:
            raise APIError(
                "oauthlib is required for X OAuth1 posting. "
                "Install with: pip install oauthlib"
            ) from exc

        oauth = OAuth1Client(
            self.settings.x_api_key,
            client_secret=self.settings.x_api_secret,
            resource_owner_key=self.settings.x_access_token,
            resource_owner_secret=self.settings.x_access_token_secret,
        )
        uri, headers, _ = oauth.sign(url, http_method=method.upper(), headers=extra or {})
        return {"Authorization": headers["Authorization"]}

    def _bearer_headers(self) -> dict[str, str]:
        if not self.settings.x_bearer_token:
            raise APIError("X_BEARER_TOKEN is not configured")
        return {"Authorization": f"Bearer {self.settings.x_bearer_token}"}

    def _write_headers(self, method: str, url: str) -> dict[str, str]:
        if self.settings.has_x_oauth1():
            return {
                **self._oauth1_headers(method, url),
                "Content-Type": "application/json",
            }
        # Some apps allow Bearer for managed tweets; prefer OAuth1 for user posts.
        headers = self._bearer_headers()
        headers["Content-Type"] = "application/json"
        return headers

    def create_tweet(
        self,
        text: str,
        *,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        """POST /2/tweets"""
        url = f"{self.settings.x_api_base.rstrip('/')}/tweets"
        body: dict[str, Any] = {"text": text}
        if reply_to:
            body["reply"] = {"in_reply_to_tweet_id": reply_to}

        if self.settings.dry_run:
            return dry_run_log("POST", url, json=body)

        headers = self._write_headers("POST", url)
        resp = request_with_retry(
            "POST",
            url,
            client=self._http(),
            headers=headers,
            json=body,
            max_retries=self.settings.http_max_retries,
            backoff_base=self.settings.http_backoff_base,
            timeout=self.settings.http_timeout,
        )
        data = resp.json()
        tweet_id = (data.get("data") or {}).get("id")
        logger.info("X tweet created: %s", tweet_id)
        return data

    def get_me(self) -> dict[str, Any]:
        """GET /2/users/me"""
        url = f"{self.settings.x_api_base.rstrip('/')}/users/me"
        if self.settings.dry_run:
            return dry_run_log("GET", url)

        if self.settings.has_x_oauth1():
            headers = self._oauth1_headers("GET", url)
        else:
            headers = self._bearer_headers()

        resp = request_with_retry(
            "GET",
            url,
            client=self._http(),
            headers=headers,
            max_retries=self.settings.http_max_retries,
            backoff_base=self.settings.http_backoff_base,
            timeout=self.settings.http_timeout,
        )
        data = resp.json()
        self._user_id = (data.get("data") or {}).get("id")
        return data

    def list_recent_tweets(self, max_results: int = 10) -> list[dict[str, Any]]:
        """GET /2/users/:id/tweets — our own tweets."""
        if self.settings.dry_run:
            dry_run_log(
                "GET",
                f"{self.settings.x_api_base.rstrip('/')}/users/:id/tweets",
                params={"max_results": max_results},
            )
            return []

        me = self.get_me()
        user_id = (me.get("data") or {}).get("id")
        if not user_id:
            raise APIError("Could not resolve X user id via /users/me", payload=me)

        url = f"{self.settings.x_api_base.rstrip('/')}/users/{user_id}/tweets"
        params = {
            "max_results": str(max(5, min(max_results, 100))),
            "tweet.fields": "id,text,created_at,conversation_id",
        }
        if self.settings.has_x_oauth1():
            headers = self._oauth1_headers("GET", url)
        else:
            headers = self._bearer_headers()

        resp = request_with_retry(
            "GET",
            url,
            client=self._http(),
            headers=headers,
            params=params,
            max_retries=self.settings.http_max_retries,
            backoff_base=self.settings.http_backoff_base,
            timeout=self.settings.http_timeout,
        )
        return list(resp.json().get("data") or [])

    def search_replies_to_tweet(self, tweet_id: str, max_results: int = 20) -> list[dict[str, Any]]:
        """
        GET /2/tweets/search/recent — replies in our conversation.
        Scoped to conversation_id of OUR tweet (no mass engagement).
        """
        url = f"{self.settings.x_api_base.rstrip('/')}/tweets/search/recent"
        query = f"conversation_id:{tweet_id} is:reply"
        params = {
            "query": query,
            "max_results": str(max(10, min(max_results, 100))),
            "tweet.fields": "id,text,author_id,created_at,in_reply_to_user_id,conversation_id",
        }

        if self.settings.dry_run:
            dry_run_log("GET", url, params=params)
            return []

        headers = (
            self._bearer_headers()
            if self.settings.has_x_bearer()
            else self._oauth1_headers("GET", url)
        )
        resp = request_with_retry(
            "GET",
            url,
            client=self._http(),
            headers=headers,
            params=params,
            max_retries=self.settings.http_max_retries,
            backoff_base=self.settings.http_backoff_base,
            timeout=self.settings.http_timeout,
        )
        return list(resp.json().get("data") or [])

    def reply_to_tweet(self, tweet_id: str, text: str) -> dict[str, Any]:
        """Reply to a comment/reply on our own post."""
        return self.create_tweet(text, reply_to=tweet_id)
