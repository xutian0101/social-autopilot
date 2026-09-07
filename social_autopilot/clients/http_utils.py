"""Shared HTTP helpers: retries, backoff, rate-limit handling."""

from __future__ import annotations

import logging
import random
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class APIError(Exception):
    """Raised when an upstream API returns a non-success response."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        payload: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def _should_retry(status: int) -> bool:
    return status in {408, 409, 425, 429, 500, 502, 503, 504}


def request_with_retry(
    method: str,
    url: str,
    *,
    client: httpx.Client | None = None,
    max_retries: int = 3,
    backoff_base: float = 1.5,
    timeout: float = 30.0,
    **kwargs: Any,
) -> httpx.Response:
    """Issue an HTTP request with exponential backoff + jitter on 429/5xx."""
    owns_client = client is None
    if owns_client:
        client = httpx.Client(timeout=timeout)

    assert client is not None
    last_exc: Exception | None = None
    try:
        for attempt in range(max_retries + 1):
            try:
                resp = client.request(method, url, **kwargs)
            except httpx.TransportError as exc:
                last_exc = exc
                if attempt >= max_retries:
                    raise APIError(f"Transport error talking to {url}: {exc}") from exc
                sleep_for = backoff_base**attempt + random.uniform(0, 0.5)
                logger.warning(
                    "Transport error (attempt %d/%d): %s — sleeping %.1fs",
                    attempt + 1,
                    max_retries + 1,
                    exc,
                    sleep_for,
                )
                time.sleep(sleep_for)
                continue

            if resp.status_code < 400:
                return resp

            if _should_retry(resp.status_code) and attempt < max_retries:
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    sleep_for = float(retry_after)
                else:
                    sleep_for = backoff_base**attempt + random.uniform(0, 0.5)
                logger.warning(
                    "%s %s -> %s (attempt %d/%d) — sleeping %.1fs",
                    method.upper(),
                    url,
                    resp.status_code,
                    attempt + 1,
                    max_retries + 1,
                    sleep_for,
                )
                time.sleep(sleep_for)
                continue

            try:
                payload = resp.json()
            except Exception:  # noqa: BLE001
                payload = resp.text
            raise APIError(
                f"{method.upper()} {url} failed with {resp.status_code}: {payload}",
                status_code=resp.status_code,
                payload=payload,
            )
    finally:
        if owns_client:
            client.close()

    if last_exc:
        raise APIError(str(last_exc)) from last_exc
    raise APIError(f"Request to {url} failed after retries")


def dry_run_log(method: str, url: str, **kwargs: Any) -> dict[str, Any]:
    """Return a structured description of an intended API call (no network)."""
    safe_kwargs = {
        k: v
        for k, v in kwargs.items()
        if k not in {"files"}  # skip binary bodies in logs
    }
    # Redact tokens in params/headers/json
    for key in ("params", "headers", "json", "data"):
        if key in safe_kwargs and isinstance(safe_kwargs[key], dict):
            redacted = {}
            for k, v in safe_kwargs[key].items():
                lk = str(k).lower()
                if any(s in lk for s in ("token", "secret", "authorization", "password", "key")):
                    redacted[k] = "***REDACTED***"
                else:
                    redacted[k] = v
            safe_kwargs[key] = redacted
    entry = {"dry_run": True, "method": method.upper(), "url": url, **safe_kwargs}
    logger.info("[DRY_RUN] %s %s %s", method.upper(), url, safe_kwargs)
    return entry
