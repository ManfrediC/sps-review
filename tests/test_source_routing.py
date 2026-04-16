from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "src" / "pipelines" / "_source_routing.py"


def load_module():
    spec = importlib.util.spec_from_file_location("source_routing_module", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestSourceRouting(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module()

    def test_incorrect_reference_is_an_explicit_downstream_exclusion(self) -> None:
        resolved = self.module.resolve_source_row(
            paper_id="263",
            heuristic_row={
                "source_category": "single_case_report",
                "source_subtype": "case_report",
                "classification_confidence": "high",
            },
            manual_row={
                "final_source_category": "unclear_manual_review",
                "final_source_subtype": "incorrect_reference",
                "review_decision_notes": "Attached PDF belongs to another paper.",
                "pdf_content_alignment_tag": "incorrect_reference",
            },
        )

        self.assertEqual(resolved["resolved_source_subtype"], "incorrect_reference")
        self.assertEqual(resolved["resolved_langextract_mode"], "incorrect_reference")
        self.assertEqual(resolved["resolved_langextract_eligible"], "false")
        self.assertEqual(resolved["manual_override_present"], "true")

    def test_embedded_review_category_routes_to_manual_review_with_fixed_subtype(self) -> None:
        resolved = self.module.resolve_source_row(
            paper_id="184",
            heuristic_row={
                "source_category": "review_format_with_embedded_original_cohort",
                "source_subtype": "",
                "classification_confidence": "medium",
            },
            manual_row=None,
        )

        self.assertEqual(
            resolved["resolved_source_category"],
            "review_format_with_embedded_original_cohort",
        )
        self.assertEqual(resolved["resolved_source_subtype"], "embedded_original_cohort")
        self.assertEqual(resolved["resolved_langextract_mode"], "manual_review")
        self.assertEqual(resolved["resolved_langextract_eligible"], "false")
        self.assertEqual(resolved["resolved_case_series_split_candidate"], "false")


if __name__ == "__main__":
    unittest.main()
