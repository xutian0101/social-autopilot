from datetime import date
from pathlib import Path
import os

from social_autopilot.calendar_loader import item_from_dict, load_for_date


def test_item_from_dict_builds_full_text(tmp_path: Path) -> None:
    item = item_from_dict(
        {
            "date": "2026-09-07",
            "platforms": ["facebook", "x"],
            "text": "Hello glow",
            "hashtags": ["Beauty", "#Skincare"],
        },
        tmp_path,
    )
    assert item.date == date(2026, 9, 7)
    assert "Hello glow" in item.full_text
    assert "#Beauty" in item.full_text
    assert "#Skincare" in item.full_text


def test_load_for_date_finds_sample() -> None:
    content = Path(os.environ["CONTENT_DIR"])
    items = load_for_date(content, date(2026, 9, 7))
    assert len(items) >= 1
    assert items[0].supports("instagram")
