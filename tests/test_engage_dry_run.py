from social_autopilot.config import load_settings
from social_autopilot.services.engage import run_engage


def test_engage_dry_run_emits_template_replies() -> None:
    settings = load_settings()
    assert settings.dry_run is True
    results = run_engage(settings)
    assert len(results) >= 3  # fb + ig + x placeholders
    assert all(r.dry_run for r in results)
    assert all(r.reply_text for r in results)
    assert all(r.error is None for r in results)
