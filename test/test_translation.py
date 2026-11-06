import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.translation import TRANSLATION_LANGUAGES, get_translation_language_name


class TestTranslationLanguages(unittest.TestCase):
    def test_requested_languages_are_available(self):
        expected = {
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
        self.assertEqual(TRANSLATION_LANGUAGES, expected)

    def test_language_names_are_case_insensitive(self):
        self.assertEqual(get_translation_language_name("zh-cn"), "Chinese (Simplified)")
        self.assertEqual(get_translation_language_name("ZH-tw"), "Chinese (Traditional)")

    def test_missing_language_defaults_to_english(self):
        self.assertEqual(get_translation_language_name(None), "English")
        self.assertEqual(get_translation_language_name(""), "English")


if __name__ == "__main__":
    unittest.main()
