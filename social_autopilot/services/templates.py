"""Reply templates + optional OpenAI drafting for own-post comments."""

from __future__ import annotations

import logging
import random
from typing import Any

import httpx

from social_autopilot.config import Settings

logger = logging.getLogger(__name__)

FRIENDLY_TEMPLATES = [
    "谢谢你的留言！💕 很高兴你喜欢我们的产品～",
    "感谢支持！有任何护肤问题随时问我们哦 ✨",
    "爱你的反馈！期待继续陪你变美 🌸",
    "谢谢宝贝～今天也要元气满满呀！",
    "收到啦！你的喜欢是我们最大的动力 💖",
]

ENGLISH_TEMPLATES = [
    "Thank you so much for your kind words! 💕",
    "We're glad you love it — stay glowing! ✨",
    "Appreciate your support! Feel free to ask us anything about skincare.",
    "Thanks for stopping by! Have a beautiful day 🌸",
]

TEMPLATES_BY_TONE: dict[str, list[str]] = {
    "friendly": FRIENDLY_TEMPLATES,
    "english": ENGLISH_TEMPLATES,
    "bilingual": FRIENDLY_TEMPLATES + ENGLISH_TEMPLATES,
}


def pick_template(tone: str = "friendly", comment_text: str = "") -> str:
    pool = TEMPLATES_BY_TONE.get(tone.lower(), FRIENDLY_TEMPLATES)
    # Light heuristic: prefer English templates if comment is mostly ASCII letters
    ascii_ratio = (
        sum(1 for c in comment_text if c.isascii() and c.isalpha())
        / max(sum(1 for c in comment_text if c.isalpha()), 1)
    )
    if tone.lower() == "bilingual" and ascii_ratio > 0.7:
        pool = ENGLISH_TEMPLATES
    return random.choice(pool)


def draft_reply_with_llm(
    settings: Settings,
    comment_text: str,
    *,
    brand_hint: str = "beauty / skincare brand",
) -> str | None:
    """Optional OpenAI-compatible chat completion for reply drafting."""
    if not settings.has_openai():
        return None

    base = settings.openai_api_base.rstrip("/")
    url = f"{base}/chat/completions"
    system = (
        f"You are a helpful social-media community manager for a {brand_hint}. "
        "Write a short, warm reply (1-2 sentences) to a comment on OUR post. "
        "Do not invent discounts or medical claims. No hashtags spam."
    )
    payload: dict[str, Any] = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Comment:\n{comment_text}\n\nDraft a reply:"},
        ],
        "temperature": 0.7,
        "max_tokens": 120,
    }
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json",
    }

    if settings.dry_run:
        logger.info("[DRY_RUN] Would call OpenAI at %s for reply draft", url)
        return None

    try:
        with httpx.Client(timeout=settings.http_timeout) as client:
            resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"].strip()
            return content or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("OpenAI drafting failed, falling back to templates: %s", exc)
        return None


def craft_reply(settings: Settings, comment_text: str) -> str:
    drafted = draft_reply_with_llm(settings, comment_text)
    if drafted:
        return drafted
    return pick_template(settings.engage_tone, comment_text)
