import logging
import os

import aiohttp


GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash-lite")
GEMINI_FALLBACK_MODELS = [
    model.strip()
    for model in os.environ.get(
        "GEMINI_FALLBACK_MODELS",
        "gemini-2.5-flash,gemini-2.0-flash,gemini-2.0-flash-lite",
    ).split(",")
    if model.strip()
]
GEMINI_GENERATE_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/{model}:generateContent"
)

logger = logging.getLogger(__name__)


def is_ai_enabled() -> bool:
    return bool(GEMINI_API_KEY)


def _extract_response_text(payload: dict) -> str:
    parts = []
    for candidate in payload.get("candidates", []):
        content = candidate.get("content", {})
        for part in content.get("parts", []):
            text = part.get("text")
            if text:
                parts.append(text)
    return "\n".join(parts).strip()


def _model_candidates() -> list[str]:
    candidates = [GEMINI_MODEL, *GEMINI_FALLBACK_MODELS]
    seen = set()
    return [model for model in candidates if not (model in seen or seen.add(model))]


async def explain_missing_word_with_ai(word: str) -> str | None:
    if not GEMINI_API_KEY:
        return None

    clean_word = word.strip()
    if not clean_word:
        return None

    prompt = (
        "You are an English vocabulary assistant for students studying technical "
        "and mining-related English. Answer in Russian, briefly. The word is not "
        "in the bot's local dictionary, so do not say it was found there.\n\n"
        "Return only this structure:\n"
        "Explanation: ...\n"
        "Synonyms: ...\n"
        "Example: ...\n\n"
        f"Explain the English word or phrase: {clean_word!r}. "
        "Give a simple meaning, 3-5 English synonyms if appropriate, and one "
        "clear English example sentence."
    )

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_API_KEY,
    }
    data = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 220,
            "temperature": 0.4,
        },
    }

    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for model in _model_candidates():
                url = GEMINI_GENERATE_URL.format(model=model)
                async with session.post(url, headers=headers, json=data) as resp:
                    if resp.status >= 400:
                        error_text = await resp.text()
                        logger.warning(
                            "Gemini request failed for %s: %s %s",
                            model,
                            resp.status,
                            error_text[:500],
                        )
                        continue

                    payload = await resp.json()
                    result = _extract_response_text(payload)
                    if result:
                        return result[:1200]
            return None
    except Exception:
        logger.exception("Gemini request error")
        return None
