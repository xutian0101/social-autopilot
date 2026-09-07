"""Shared fixtures — force DRY_RUN and isolated content/reports dirs."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("DRY_RUN", "true")
    monkeypatch.setenv("TIMEZONE", "Asia/Shanghai")
    content = tmp_path / "content"
    reports = tmp_path / "reports"
    content.mkdir()
    reports.mkdir()
    # Copy today's sample into the temp content dir (and samples/)
    sample_src = ROOT / "content" / "samples" / "2026-09-07.yaml"
    samples = content / "samples"
    samples.mkdir()
    if sample_src.exists():
        (samples / "2026-09-07.yaml").write_text(
            sample_src.read_text(encoding="utf-8"), encoding="utf-8"
        )
        (content / "2026-09-07.yaml").write_text(
            sample_src.read_text(encoding="utf-8"), encoding="utf-8"
        )
    monkeypatch.setenv("CONTENT_DIR", str(content))
    monkeypatch.setenv("REPORTS_DIR", str(reports))
    # Clear credentials so live paths are not accidentally taken
    for key in (
        "META_ACCESS_TOKEN",
        "META_PAGE_ID",
        "META_IG_USER_ID",
        "X_BEARER_TOKEN",
        "X_API_KEY",
        "X_API_SECRET",
        "X_ACCESS_TOKEN",
        "X_ACCESS_TOKEN_SECRET",
        "OPENAI_API_KEY",
    ):
        monkeypatch.delenv(key, raising=False)
    # Ensure dotenv does not override our test env from a developer .env
    monkeypatch.setenv("DRY_RUN", "true")
    return tmp_path
