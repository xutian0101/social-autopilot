import httpx
import pytest
import respx

from social_autopilot.clients.http_utils import APIError, dry_run_log, request_with_retry


def test_dry_run_log_redacts_tokens() -> None:
    entry = dry_run_log(
        "POST",
        "https://graph.facebook.com/v19.0/123/feed",
        json={"message": "hi", "access_token": "secret"},
    )
    assert entry["dry_run"] is True
    assert entry["json"]["access_token"] == "***REDACTED***"
    assert entry["json"]["message"] == "hi"


@respx.mock
def test_request_with_retry_succeeds() -> None:
    route = respx.get("https://example.com/ok").mock(
        return_value=httpx.Response(200, json={"ok": True})
    )
    resp = request_with_retry("GET", "https://example.com/ok", max_retries=1)
    assert resp.status_code == 200
    assert route.called


@respx.mock
def test_request_with_retry_raises_on_400() -> None:
    respx.post("https://example.com/bad").mock(
        return_value=httpx.Response(400, json={"error": "nope"})
    )
    with pytest.raises(APIError) as ei:
        request_with_retry("POST", "https://example.com/bad", max_retries=0)
    assert ei.value.status_code == 400
