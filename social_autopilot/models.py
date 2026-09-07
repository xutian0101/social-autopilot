"""Data models for content calendar entries and run results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any


@dataclass
class ContentItem:
    """A single day's scheduled post loaded from YAML."""

    date: date
    platforms: list[str]
    text: str
    media: Path | None = None
    hashtags: list[str] = field(default_factory=list)
    title: str | None = None
    link: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def full_text(self) -> str:
        """Caption / tweet body including hashtags."""
        tags = " ".join(
            h if h.startswith("#") else f"#{h}" for h in self.hashtags
        )
        if tags:
            return f"{self.text.rstrip()}\n\n{tags}"
        return self.text

    def supports(self, platform: str) -> bool:
        return platform.lower() in {p.lower() for p in self.platforms}


@dataclass
class PublishResult:
    platform: str
    success: bool
    post_id: str | None = None
    dry_run: bool = False
    message: str = ""
    error: str | None = None


@dataclass
class EngageResult:
    platform: str
    post_id: str
    comment_id: str
    reply_id: str | None = None
    dry_run: bool = False
    reply_text: str = ""
    error: str | None = None


@dataclass
class DailyReport:
    report_date: date
    path: Path
    publish_results: list[PublishResult] = field(default_factory=list)
    engage_results: list[EngageResult] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
