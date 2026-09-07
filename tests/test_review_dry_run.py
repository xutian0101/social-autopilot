from social_autopilot.config import load_settings
from social_autopilot.models import EngageResult, PublishResult
from social_autopilot.services.review import run_review


def test_review_writes_markdown(tmp_path_factory) -> None:
    settings = load_settings()
    publish = [
        PublishResult(
            platform="facebook",
            success=True,
            post_id="dry-run-fb",
            dry_run=True,
            message="DRY_RUN",
        )
    ]
    engage = [
        EngageResult(
            platform="facebook",
            post_id="p1",
            comment_id="c1",
            reply_id="r1",
            dry_run=True,
            reply_text="谢谢你的留言！",
        )
    ]
    report = run_review(settings, publish, engage)
    assert report.path.exists()
    text = report.path.read_text(encoding="utf-8")
    assert "Social Autopilot Daily Report" in text
    assert "facebook" in text
    assert "DRY_RUN" in text
