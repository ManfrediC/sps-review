from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.pipelines._sps_case_count_registry import build_case_count_candidate_package
from src.pipelines.stage06_counting.hybrid import gpt_adjudication_needed, hybrid_count_row
from src.pipelines.stage06_counting.local_models import LocalCountDecisionOutput, LocalModelCallResult
from src.pipelines.stage06_counting.models import CountEvidenceItem, LLMCountDecisionOutput


REPO_ROOT = Path(__file__).resolve().parents[1]


def make_enumerated_subgroup_package():
    return build_case_count_candidate_package(
        reference_row={
            "Covidence": "1937",
            "Title": "Prevalence of neurological anti-GAD autoimmunity in Martinique",
            "Authors": "Duclos, S",
            "Abstract": (
                "Results: On January 1 2016, 21 patients had neurological syndromes associated with anti-GAD autoimmunity. "
                "Among those patients, 13 had SPS, 9 had CA, 6 had LOFE, 5 had LE, and 1 PERM."
            ),
        },
        text_record={"paper_id": "1937", "_path": "data/extraction_json/text/1937.json"},
        preferred_record={
            "pages": [
                {
                    "text": (
                        "Results: On January 1 2016, 21 patients had neurological syndromes associated with anti-GAD autoimmunity. "
                        "Among those patients, 13 had SPS, 9 had CA, 6 had LOFE, 5 had LE, and 1 PERM."
                    )
                }
            ]
        },
        preferred_path=REPO_ROOT / "data" / "extraction_json" / "text_proceedings_ready" / "1937.json",
        source_row={
            "source_category": "conference_abstract",
            "source_subtype": "group_conference_abstract",
        },
    )


def make_zero_review_package():
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
        preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "12720.json",
        source_row={
            "source_category": "review_article",
            "source_subtype": "review",
        },
    )


class TestStage06HybridCounting(unittest.TestCase):
    def test_gpt_adjudication_needed_skips_clear_zero_review_rows(self) -> None:
        self.assertFalse(gpt_adjudication_needed(make_zero_review_package()))

    def test_hybrid_count_row_runs_challenge_on_subgroup_conflict(self) -> None:
        package = make_enumerated_subgroup_package()
        local_parsed = LocalCountDecisionOutput.model_validate(
            {
                "n_spsd_patients": 14,
                "evidence_span": "Among those patients, 13 had SPS, 9 had CA, 6 had LOFE, 5 had LE, and 1 PERM.",
                "data_granularity": "group-level",
                "confidence": "high",
                "needs_review": True,
                "reasoning_short": "The explicit SPS-spectrum subtotal is 14.",
                "possibilities": [],
            }
        )
        local_call = LocalModelCallResult(
            model_id="gemma4:e4b",
            status="parsed_ok",
            raw_output="{}",
            response_payload={},
            parsed=local_parsed,
            duration_seconds=0.5,
        )
        primary_decision = LLMCountDecisionOutput(
            decision_type="candidate_exact",
            selected_candidate_id=package.preferred_candidate_id,
            alternative_count=None,
            count_confidence="high",
            count_manual_review_required=False,
            count_reasoning_summary="The broader anti-GAD cohort seems to be the count.",
            evidence=[
                CountEvidenceItem(
                    quote="21 patients had neurological syndromes associated with anti-GAD autoimmunity.",
                    page=1,
                    section="abstract",
                    supports="broader cohort size",
                ),
                CountEvidenceItem(
                    quote="Among those patients, 13 had SPS, 9 had CA, 6 had LOFE, 5 had LE, and 1 PERM.",
                    page=1,
                    section="abstract",
                    supports="diagnosis breakdown",
                ),
            ],
        )
        challenge_decision = LLMCountDecisionOutput(
            decision_type="bounded_alternative",
            selected_candidate_id=None,
            alternative_count=14,
            count_confidence="high",
            count_manual_review_required=False,
            count_reasoning_summary="The explicit SPS plus PERM subtotal is the correct SPS-spectrum count.",
            evidence=[
                CountEvidenceItem(
                    quote="Among those patients, 13 had SPS, 9 had CA, 6 had LOFE, 5 had LE, and 1 PERM.",
                    page=1,
                    section="abstract",
                    supports="explicit SPS-spectrum subtotal",
                ),
                CountEvidenceItem(
                    quote="21 patients had neurological syndromes associated with anti-GAD autoimmunity.",
                    page=1,
                    section="abstract",
                    supports="broader cohort that should not be used directly",
                ),
            ],
        )

        with tempfile.TemporaryDirectory() as tmp_dir_text:
            run_dir = Path(tmp_dir_text)
            with (
                mock.patch("src.pipelines.stage06_counting.hybrid.run_local_count_package", return_value=local_call),
                mock.patch(
                    "src.pipelines.stage06_counting.hybrid.adjudicate_count_package",
                    side_effect=[(primary_decision, "gpt-5.4-primary"), (challenge_decision, "gpt-5.4-challenge")],
                ),
            ):
                row = hybrid_count_row(
                    package,
                    run_dir=run_dir,
                    candidate_json_path="results/stage06_count_runs/test/candidate_packages/1937.json",
                )

        self.assertEqual(row["likely_sps_case_count"], "14")
        self.assertEqual(row["count_verification_status"], "llm_bounded_alternative")
        self.assertEqual(row["count_manual_review_required"], "false")
        self.assertIn("challenge_stage=challenge", row["count_reason"])
        self.assertIn("challenge_reasons=", row["count_reason"])


if __name__ == "__main__":
    unittest.main()
