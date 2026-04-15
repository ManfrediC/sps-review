from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from src.pipelines._sps_case_count_registry import build_case_count_candidate_package
from src.pipelines.stage06_counting.local_ollama import (
    ensure_ollama_model_available,
    parse_local_count_output,
    run_local_count_package,
)
from src.pipelines.stage06_counting.local_prepare import format_candidate_package_for_local_llm
from src.pipelines.stage06_counting.local_validate import validate_local_count_decision


def make_package():
    return build_case_count_candidate_package(
        reference_row={
            "Covidence": "214",
            "Title": "Plasma exchange in stiff-man syndrome.",
            "Authors": "Example, C",
            "Abstract": (
                "We report on the use of plasma exchange in 2 patients with stiff-man syndrome. "
                "One patient showed minimal clinical improvement while the second reported subjective improvement."
            ),
        },
        text_record={"paper_id": "214", "_path": "data/extraction_json/text/214.json"},
        preferred_record={"pages": [{"text": "Case 1 ... Case 2 ..."}]},
        preferred_path=Path("data/extraction_json/text/214.json"),
        source_row={
            "source_category": "case_series_or_multi_case",
            "source_subtype": "case_series",
        },
    )


def make_review_package():
    return build_case_count_candidate_package(
        reference_row={
            "Covidence": "12720",
            "Title": "STIFF-MAN SYNDROME",
            "Authors": "TORO, C; JACOBWITZ, DM; HALLETT, M",
            "Abstract": "",
        },
        text_record={"paper_id": "12720", "_path": "data/extraction_json/text/12720.json"},
        preferred_record={
            "pages": [
                {
                    "text": (
                        "Stiff-man syndrome is the term coined by Moersch and Woltmann. "
                        "A survey of the medical literature in 1967 identified 44 cases."
                    )
                }
            ]
        },
        preferred_path=Path("data/extraction_json/text/12720.json"),
        source_row={
            "source_category": "review_article",
            "source_subtype": "review",
        },
    )


def make_uncertain_package():
    return build_case_count_candidate_package(
        reference_row={
            "Covidence": "92",
            "Title": "Antiamphiphysin antibodies with small-cell lung carcinoma and paraneoplastic encephalomyelitis.",
            "Authors": "Dropcho, E J",
            "Abstract": (
                "Paraneoplastic encephalomyelitis developed as the presenting feature of small-cell lung carcinoma in 3 patients. "
                "The 3 patients described here all had SCLC, PEM, and antibodies against human amphiphysin, "
                "though only 1 patient had clinical rigidity."
            ),
        },
        text_record={"paper_id": "92", "_path": "data/extraction_json/text/92.json"},
        preferred_record={
            "pages": [
                {
                    "text": (
                        "The 3 patients described here all had SCLC, PEM, and antibodies against human amphiphysin, "
                        "though only 1 patient had clinical rigidity."
                    )
                }
            ]
        },
        preferred_path=Path("data/extraction_json/text/92.json"),
        source_row={
            "source_category": "case_series_or_multi_case",
            "source_subtype": "case_series",
        },
    )


class TestStage06LocalCounting(unittest.TestCase):
    def test_local_prompt_includes_evidence_and_candidates(self) -> None:
        prompt = format_candidate_package_for_local_llm(make_package())
        self.assertIn("## Evidence pack", prompt)
        self.assertIn("## Explicit subgroup signals", prompt)
        self.assertIn("## Deterministic candidate hints", prompt)
        self.assertIn("preferred_candidate_id", prompt)

    def test_parse_local_output_handles_fenced_json(self) -> None:
        parsed = parse_local_count_output(
            """```json
            {
              "n_spsd_patients": 2,
              "evidence_span": "We report on the use of plasma exchange in 2 patients with stiff-man syndrome.",
              "data_granularity": "individual-level",
              "confidence": "high",
              "needs_review": false,
              "reasoning_short": "The abstract explicitly reports two original SPS patients.",
              "possibilities": []
            }
            ```"""
        )
        self.assertEqual(parsed.n_spsd_patients, 2)
        self.assertEqual(parsed.data_granularity, "individual-level")
        self.assertFalse(parsed.needs_review)

    def test_validate_local_decision_flags_review_article_nonzero(self) -> None:
        parsed = parse_local_count_output(
            """{
              "n_spsd_patients": 44,
              "evidence_span": "A survey of the medical literature in 1967 identified 44 cases.",
              "data_granularity": "group-level",
              "confidence": "medium",
              "needs_review": true,
              "reasoning_short": "The paper discusses 44 cases.",
              "possibilities": []
            }"""
        )
        flags = validate_local_count_decision(make_review_package(), parsed)
        self.assertIn("LOCAL_SKIP_CATEGORY_NONZERO", flags)

    def test_validate_local_decision_flags_uncertain_positive_without_review(self) -> None:
        parsed = parse_local_count_output(
            """{
              "n_spsd_patients": 3,
              "evidence_span": "The 3 patients described here all had SCLC, PEM, and antibodies against human amphiphysin.",
              "data_granularity": "group-level",
              "confidence": "medium",
              "needs_review": false,
              "reasoning_short": "The series contains three original patients.",
              "possibilities": []
            }"""
        )
        flags = validate_local_count_decision(make_uncertain_package(), parsed)
        self.assertIn("LOCAL_SPS_STATUS_UNCERTAIN_NO_REVIEW", flags)

    def test_ensure_ollama_model_available_checks_model_list(self) -> None:
        with mock.patch("src.pipelines.stage06_counting.local_ollama.requests.get") as get_mock:
            get_mock.return_value.json.return_value = {"data": [{"id": "gemma4:e4b"}]}
            get_mock.return_value.raise_for_status.return_value = None
            ensure_ollama_model_available(model="gemma4:e4b", base_url="http://localhost:11434")

    def test_run_local_count_package_records_parse_failure(self) -> None:
        package = make_package()
        with mock.patch("src.pipelines.stage06_counting.local_ollama.requests.post") as post_mock:
            post_mock.return_value.json.return_value = {
                "model": "gemma4:e4b",
                "message": {"content": "not json"},
            }
            post_mock.return_value.raise_for_status.return_value = None
            result = run_local_count_package(package, base_url="http://localhost:11434", timeout_seconds=1)
        self.assertEqual(result.status, "parse_failed")
        self.assertIsNone(result.parsed)
        self.assertIn("Unable to parse", result.error)


if __name__ == "__main__":
    unittest.main()
