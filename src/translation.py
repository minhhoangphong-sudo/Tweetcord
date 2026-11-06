"""Supported per-server translation languages for FixupX/FxTwitter links."""

TRANSLATION_LANGUAGES: dict[str, str] = {
    "en": "English",
    "fr": "French",
    "ja": "Japanese",
    "zh-CN": "Chinese (Simplified)",
    "zh-TW": "Chinese (Traditional)",
    "es": "Spanish",
    "ar": "Arabic",
    "th": "Thai",
    "tl": "Tagalog",
    "ko": "Korean",
    "de": "German",
    "pl": "Polish",
    "sv": "Swedish",
    "ru": "Russian",
    "it": "Italian",
    "el": "Greek",
    "tr": "Turkish",
}


def get_translation_language_name(code: str | None) -> str:
    """Return a display name, defaulting to English for missing/unknown values."""
    if not code:
        return TRANSLATION_LANGUAGES["en"]

    normalized = code.strip().casefold()
    for language_code, language_name in TRANSLATION_LANGUAGES.items():
        if language_code.casefold() == normalized:
            return language_name
    return code
