from datetime import date
from unittest.mock import patch

from typer.testing import CliRunner

from social_autopilot.cli import app

runner = CliRunner()


def test_run_daily_dry_run_exit_zero() -> None:
    with patch(
        "social_autopilot.services.publish.today_in_tz",
        return_value=date(2026, 9, 7),
    ), patch(
        "social_autopilot.services.review.today_in_tz",
        return_value=date(2026, 9, 7),
    ):
        result = runner.invoke(app, ["run-daily"])
    assert result.exit_code == 0, result.output
    assert "DRY_RUN=True" in result.output or "DRY_RUN=true" in result.output.lower() or "Done." in result.output
