import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import translation
from src.translation import (
    TRANSLATION_LANGUAGES,
    get_translation_language_name,
    normalize_language_code,
    resolve_translation,
)


class TestTranslationLanguages(unittest.TestCase):
    def test_requested_languages_are_available(self):
        expected = {
            "en": "English",
            "fr": "French",
            "ja": "Japanese",
            "zh": "Chinese",
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
        self.assertEqual(TRANSLATION_LANGUAGES, expected)

    def test_codes_are_lowercase_and_fit_discord_choices(self):
        # codes go straight into the link (.../status/123/zh) and Discord allows 25 choices
        self.assertTrue(all(code == code.lower() for code in TRANSLATION_LANGUAGES))
        self.assertLessEqual(len(TRANSLATION_LANGUAGES), 25)

    def test_language_names_are_case_insensitive(self):
        self.assertEqual(get_translation_language_name("zh"), "Chinese")
        self.assertEqual(get_translation_language_name("ZH"), "Chinese")
        self.assertEqual(get_translation_language_name("FR"), "French")

    def test_chinese_traditional_is_no_longer_an_option(self):
        self.assertNotIn("zh-tw", TRANSLATION_LANGUAGES)
        self.assertNotIn("zh-cn", TRANSLATION_LANGUAGES)
        self.assertFalse(any("Traditional" in name or "Simplified" in name for name in TRANSLATION_LANGUAGES.values()))

    def test_old_simplified_code_now_means_chinese(self):
        self.assertEqual(get_translation_language_name("zh-cn"), "Chinese")
        self.assertEqual(get_translation_language_name("zh_CN"), "Chinese")

    def test_missing_language_defaults_to_english(self):
        self.assertEqual(get_translation_language_name(None), "English")
        self.assertEqual(get_translation_language_name(""), "English")

    def test_unknown_language_shows_its_code(self):
        self.assertEqual(get_translation_language_name("uk"), "uk")


class TestNormalizeLanguageCode(unittest.TestCase):
    def test_old_capitalised_codes_become_lowercase(self):
        self.assertEqual(normalize_language_code("ZH"), "zh")
        self.assertEqual(normalize_language_code("zh-CN"), "zh")
        self.assertEqual(normalize_language_code("cn"), "zh")
        self.assertEqual(normalize_language_code(" FR "), "fr")

    def test_missing_or_unusable_values_use_the_default(self):
        self.assertEqual(normalize_language_code(None), translation.DEFAULT_LANGUAGE)
        self.assertEqual(normalize_language_code(""), translation.DEFAULT_LANGUAGE)
        self.assertEqual(normalize_language_code("not a language!"), translation.DEFAULT_LANGUAGE)

    def test_default_language_is_one_we_support(self):
        self.assertIn(translation.DEFAULT_LANGUAGE, TRANSLATION_LANGUAGES)


class TestResolveTranslation(unittest.TestCase):
    def test_switch_on_translates_to_the_saved_language(self):
        with mock.patch.object(translation, 'TRANSLATION_SUPPORTED', True):
            self.assertEqual(resolve_translation(1, 'fr'), 'fr')
            self.assertEqual(resolve_translation(True, 'zh-CN'), 'zh')
            self.assertEqual(resolve_translation(True, 'zh'), 'zh')

    def test_switch_on_without_a_language_uses_the_default(self):
        with mock.patch.object(translation, 'TRANSLATION_SUPPORTED', True):
            self.assertEqual(resolve_translation(1, None), translation.DEFAULT_LANGUAGE)

    def test_switch_off_means_no_translation(self):
        with mock.patch.object(translation, 'TRANSLATION_SUPPORTED', True), \
             mock.patch.object(translation, 'IS_TRANSLATION_ENABLED', True):
            self.assertIsNone(resolve_translation(0, 'fr'))
            self.assertIsNone(resolve_translation(False, 'fr'))

    def test_no_switch_follows_the_config(self):
        with mock.patch.object(translation, 'TRANSLATION_SUPPORTED', True):
            with mock.patch.object(translation, 'IS_TRANSLATION_ENABLED', True):
                self.assertEqual(resolve_translation(None, 'ja'), 'ja')
            with mock.patch.object(translation, 'IS_TRANSLATION_ENABLED', False):
                self.assertIsNone(resolve_translation(None, 'ja'))

    def test_services_that_cannot_translate_never_translate(self):
        with mock.patch.object(translation, 'TRANSLATION_SUPPORTED', False), \
             mock.patch.object(translation, 'IS_TRANSLATION_ENABLED', True):
            self.assertIsNone(resolve_translation(1, 'fr'))
            self.assertIsNone(resolve_translation(None, 'fr'))


if __name__ == "__main__":
    unittest.main()
