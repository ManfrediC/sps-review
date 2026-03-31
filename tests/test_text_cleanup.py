from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "src" / "lib" / "text_cleanup.py"


def load_module():
    spec = importlib.util.spec_from_file_location("text_cleanup_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestTextCleanup(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_clean_page_text_repairs_common_mojibake_and_ligatures(self) -> None:
        module = self.module
        raw_text = (
            "alpha \u00e2\u20ac\u201c beta \u00ef\u00ac\u0081le \u00c2\u00ae \u2425-aminobutyric"
        )

        result = module.clean_page_text(raw_text, profile="basic_mojibake")

        self.assertEqual(result.cleaned_text, "alpha - beta file \u00ae gamma-aminobutyric")
        self.assertIn("replace_common_mojibake", result.rules_applied)
        self.assertIn("repair_ligatures", result.rules_applied)
        self.assertTrue(result.changed)

    def test_clean_page_text_repairs_linebreak_hyphenation_and_spacing(self) -> None:
        module = self.module
        raw_text = "immuno-\ntherapy.TestCase"

        result = module.clean_page_text(raw_text, profile="basic_spacing")

        self.assertEqual(result.cleaned_text, "immunotherapy. Test Case")
        self.assertIn("repair_linebreak_hyphenation", result.rules_applied)
        self.assertIn("insert_punctuation_spaces", result.rules_applied)
        self.assertIn("split_camel_case", result.rules_applied)

    def test_clean_page_text_removes_zero_width_artifacts(self) -> None:
        module = self.module
        raw_text = "Christopher Connolly\u200d\u200d,\u200b connolch@\u200bmed.example"

        result = module.clean_page_text(raw_text, profile="combined_basic")

        self.assertEqual(result.cleaned_text, "Christopher Connolly, connolch@med.example")
        self.assertIn("normalize_spaces", result.rules_applied)

    def test_clean_document_pages_removes_boilerplate_and_repeated_boundary_lines(self) -> None:
        module = self.module
        pages = [
            {
                "page_index": 0,
                "text": "Repeat Header\nUseful first page\nDownloaded from example.com",
            },
            {
                "page_index": 1,
                "text": "Repeat Header\nUseful second page\nDownloaded from example.com",
            },
            {
                "page_index": 2,
                "text": "Repeat Header\nUseful third page\nDownloaded from example.com",
            },
        ]

        result = module.clean_document_pages(pages, profile="header_footer_light")

        self.assertEqual(result.pages[0]["text"], "Repeat Header\nUseful first page")
        self.assertEqual(result.pages[1]["text"], "Useful second page")
        self.assertEqual(result.pages[2]["text"], "Useful third page")
        self.assertIn("remove_known_boilerplate_lines", result.rules_applied)
        self.assertIn("drop_repeated_boundary_lines", result.rules_applied)
        self.assertEqual(result.changed_page_count, 3)

    def test_resolve_profile_rules_rejects_unknown_profile(self) -> None:
        module = self.module

        with self.assertRaises(ValueError):
            module.resolve_profile_rules("not_a_profile")


if __name__ == "__main__":
    unittest.main()
