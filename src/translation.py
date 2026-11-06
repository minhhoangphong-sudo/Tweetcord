"""Per-server translation settings for FixupX / FxTwitter links.

Translation works by adding the language code to the end of the link
(https://fixupx.com/user/status/123/fr). Codes are written in lowercase, the
same way FxEmbed's own examples and src.utils.validate_and_normalize_language do.

Everything about "is this notifier translated, and into what?" lives here so
the notifier, /list users and the /translation commands always agree.
"""

from __future__ import annotations

from configs.load_configs import configs, IS_TRANSLATION_ENABLED
from src.utils import validate_and_normalize_language

# Shown in this order in /translation language.
TRANSLATION_LANGUAGES: dict[str, str] = {
    "en": "English",
    "fr": "French",
    "ja": "Japanese",
    "zh-cn": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)",
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

# Only FxTwitter / FixupX links (and the built-in embeds, which read from the
# FxTwitter API) can translate. vxtwitter / fixvx links can't.
TRANSLATION_SUPPORTED: bool = (
    configs['embed']['type'] == 'built_in'
    or configs['embed']['proxy']['service'] == 'fx'
)


def _default_language() -> str:
    """English, unless `embed.trans_default_lang` in the configs names another supported language."""
    code = validate_and_normalize_language(configs['embed'].get('trans_default_lang'))
    return code if code in TRANSLATION_LANGUAGES else 'en'


DEFAULT_LANGUAGE: str = _default_language()


def normalize_language_code(code: str | None) -> str:
    """Lowercase code used in the link. Missing or unusable values mean the default language."""
    return validate_and_normalize_language(code) or DEFAULT_LANGUAGE


def get_translation_language_name(code: str | None) -> str:
    """Display name of a language code (the code itself when it isn't one of ours)."""
    normalized = normalize_language_code(code)
    return TRANSLATION_LANGUAGES.get(normalized, normalized)


def resolve_translation(enabled_override: int | bool | None, language: str | None) -> str | None:
    """Language code a notifier translates into, or None when translation is off.

    enabled_override is the per-account on/off switch from /translation toggle;
    None means "follow the auto_translation setting in the configs".
    """
    if not TRANSLATION_SUPPORTED:
        return None
    enabled = IS_TRANSLATION_ENABLED if enabled_override is None else bool(enabled_override)
    return normalize_language_code(language) if enabled else None
