from datetime import date
from unittest.mock import patch

from social_autopilot.config import load_settings
from social_autopilot.services.publish import run_publish


def test_publish_dry_run_succeeds_without_credentials() -> None:
    settings = load_settings()
    assert settings.dry_run is True

    with patch(
        "social_autopilot.services.publish.today_in_tz",
        return_value=date(2026, 9, 7),
    ):
        results = run_publish(settings)

    assert results, "expected at least one publish result for sample content"
    platforms = {r.platform for r in results}
    assert "facebook" in platforms
    assert "instagram" in platforms
    assert "x" in platforms
    assert all(r.success for r in results)
    assert all(r.dry_run for r in results)
