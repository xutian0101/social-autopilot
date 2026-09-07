"""Load daily content entries from YAML files under CONTENT_DIR."""

from __future__ import annotations

import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from social_autopilot.models import ContentItem

logger = logging.getLogger(__name__)


def today_in_tz(timezone: str = "Asia/Shanghai") -> date:
    return datetime.now(ZoneInfo(timezone)).date()


def _parse_date(value: Any) -> date:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    return date.fromisoformat(str(value))


def _resolve_media(raw: Any, base: Path) -> Path | None:
    if not raw:
        return None
    p = Path(str(raw))
    if not p.is_absolute():
        p = (base / p).resolve()
    return p


def item_from_dict(data: dict[str, Any], base_dir: Path) -> ContentItem:
    platforms = data.get("platforms") or []
    if isinstance(platforms, str):
        platforms = [p.strip() for p in platforms.split(",") if p.strip()]
    hashtags = data.get("hashtags") or []
    if isinstance(hashtags, str):
        hashtags = [h.strip() for h in hashtags.replace(",", " ").split() if h.strip()]
    return ContentItem(
        date=_parse_date(data["date"]),
        platforms=[str(p).lower() for p in platforms],
        text=str(data.get("text") or data.get("caption") or ""),
        media=_resolve_media(data.get("media") or data.get("image"), base_dir),
        hashtags=list(hashtags),
        title=data.get("title"),
        link=data.get("link"),
        raw=data,
    )


def discover_yaml_files(content_dir: Path) -> list[Path]:
    if not content_dir.exists():
        return []
    files: list[Path] = []
    for pattern in ("*.yaml", "*.yml"):
        files.extend(content_dir.rglob(pattern))
    return sorted(set(files))


def load_all(content_dir: Path) -> list[ContentItem]:
    items: list[ContentItem] = []
    for path in discover_yaml_files(content_dir):
        try:
            with path.open(encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to parse %s: %s", path, exc)
            continue
        if data is None:
            continue
        entries = data if isinstance(data, list) else [data]
        for entry in entries:
            if not isinstance(entry, dict) or "date" not in entry:
                logger.warning("Skipping invalid entry in %s", path)
                continue
            items.append(item_from_dict(entry, path.parent))
    return items


def load_for_date(
    content_dir: Path,
    target: date | None = None,
    timezone: str = "Asia/Shanghai",
) -> list[ContentItem]:
    """Return content items scheduled for *target* (default: today in timezone)."""
    if target is None:
        target = today_in_tz(timezone)
    matched = [i for i in load_all(content_dir) if i.date == target]
    # Prefer filename match YYYY-MM-DD.yaml when multiple
    if not matched:
        for name in (f"{target.isoformat()}.yaml", f"{target.isoformat()}.yml"):
            for candidate in (
                content_dir / name,
                content_dir / "samples" / name,
            ):
                if candidate.exists():
                    with candidate.open(encoding="utf-8") as f:
                        data = yaml.safe_load(f)
                    if isinstance(data, dict):
                        matched.append(item_from_dict(data, candidate.parent))
                    elif isinstance(data, list):
                        matched.extend(
                            item_from_dict(e, candidate.parent)
                            for e in data
                            if isinstance(e, dict)
                        )
    logger.info("Loaded %d content item(s) for %s", len(matched), target)
    return matched
