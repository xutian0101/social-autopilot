"""Configuration loaded from environment / .env."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load .env from CWD (and parents) without overriding existing env vars.
load_dotenv(override=False)


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _path(name: str, default: str) -> Path:
    return Path(os.getenv(name, default)).expanduser()


@dataclass(frozen=True)
class Settings:
    """Runtime settings for Social Autopilot."""

    dry_run: bool = True
    timezone: str = "Asia/Shanghai"
    content_dir: Path = Path("content")
    reports_dir: Path = Path("reports")

    # Daily safety caps
    daily_post_cap: int = 5
    daily_engage_cap: int = 20
    max_replies_per_post: int = 5

    # Meta / Facebook / Instagram
    meta_access_token: str = ""
    meta_page_id: str = ""
    meta_ig_user_id: str = ""
    meta_graph_version: str = "v19.0"
    meta_api_base: str = "https://graph.facebook.com"

    # X / Twitter — prefer OAuth 1.0a user context for posting
    x_bearer_token: str = ""
    x_api_key: str = ""
    x_api_secret: str = ""
    x_access_token: str = ""
    x_access_token_secret: str = ""
    x_api_base: str = "https://api.twitter.com/2"

    # Optional LLM for reply drafting
    openai_api_base: str = ""
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"

    # HTTP / rate limits
    http_timeout: float = 30.0
    http_max_retries: int = 3
    http_backoff_base: float = 1.5

    # Engagement templates (comma-separated keys or use defaults in templates.py)
    engage_tone: str = "friendly"

    @property
    def graph_base(self) -> str:
        return f"{self.meta_api_base.rstrip('/')}/{self.meta_graph_version}"

    def has_meta_page(self) -> bool:
        return bool(self.meta_access_token and self.meta_page_id)

    def has_instagram(self) -> bool:
        return bool(self.meta_access_token and self.meta_ig_user_id)

    def has_x_oauth1(self) -> bool:
        return all(
            [
                self.x_api_key,
                self.x_api_secret,
                self.x_access_token,
                self.x_access_token_secret,
            ]
        )

    def has_x_bearer(self) -> bool:
        return bool(self.x_bearer_token)

    def has_x(self) -> bool:
        return self.has_x_oauth1() or self.has_x_bearer()

    def has_openai(self) -> bool:
        return bool(self.openai_api_key)


def load_settings() -> Settings:
    """Build Settings from environment variables."""
    return Settings(
        dry_run=_bool("DRY_RUN", True),
        timezone=os.getenv("TIMEZONE", "Asia/Shanghai"),
        content_dir=_path("CONTENT_DIR", "content"),
        reports_dir=_path("REPORTS_DIR", "reports"),
        daily_post_cap=_int("DAILY_POST_CAP", 5),
        daily_engage_cap=_int("DAILY_ENGAGE_CAP", 20),
        max_replies_per_post=_int("MAX_REPLIES_PER_POST", 5),
        meta_access_token=os.getenv("META_ACCESS_TOKEN", ""),
        meta_page_id=os.getenv("META_PAGE_ID", ""),
        meta_ig_user_id=os.getenv("META_IG_USER_ID", ""),
        meta_graph_version=os.getenv("META_GRAPH_VERSION", "v19.0"),
        meta_api_base=os.getenv("META_API_BASE", "https://graph.facebook.com"),
        x_bearer_token=os.getenv("X_BEARER_TOKEN", ""),
        x_api_key=os.getenv("X_API_KEY", ""),
        x_api_secret=os.getenv("X_API_SECRET", ""),
        x_access_token=os.getenv("X_ACCESS_TOKEN", ""),
        x_access_token_secret=os.getenv("X_ACCESS_TOKEN_SECRET", ""),
        x_api_base=os.getenv("X_API_BASE", "https://api.twitter.com/2"),
        openai_api_base=os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        http_timeout=float(os.getenv("HTTP_TIMEOUT", "30")),
        http_max_retries=_int("HTTP_MAX_RETRIES", 3),
        http_backoff_base=float(os.getenv("HTTP_BACKOFF_BASE", "1.5")),
        engage_tone=os.getenv("ENGAGE_TONE", "friendly"),
    )
