from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from openai import OpenAIError

from src.pipelines._sps_case_count_registry import build_case_count_candidate_package
from src.pipelines.stage06_counting.hybrid import hybrid_count_row
from src.pipelines.stage06_counting.local_models import LocalCountDecisionOutput, LocalModelCallResult
from src.pipelines.stage06_counting.runtime import Stage06DependencyError


REPO_ROOT = Path(__file__).resolve().parents[1]


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
        preferred_path=REPO_ROOT / "data" / "extraction_json" / "text" / "214.json",
        source_row={
            "source_category": "case_series_or_multi_case",
            "source_subtype": "case_series",
        },
    )


class TestStage06HybridFailFast(unittest.TestCase):
    def test_hybrid_count_row_raises_on_local_request_failure(self) -> None:
        package = make_package()
        with mock.patch(
            "src.pipelines.stage06_counting.hybrid.run_local_count_package",
            return_value=LocalModelCallResult(
                model_id="gemma4:e4b",
                status="request_failed",
                raw_output="",
                response_payload={},
                parsed=None,
                error="ConnectionError: local server down",
            ),
        ):
            with self.assertRaises(Stage06DependencyError):
                hybrid_count_row(package)

    def test_hybrid_count_row_raises_on_openai_dependency_failure(self) -> None:
        package = make_package()
        local_result = LocalModelCallResult(
            model_id="gemma4:e4b",
            status="parsed_ok",
            raw_output="{}",
            response_payload={},
            parsed=LocalCountDecisionOutput(
                n_spsd_patients=2,
                evidence_span="2 patients with stiff-man syndrome",
                data_granularity="group-level",
                confidence="high",
                needs_review=False,
                reasoning_short="The abstract explicitly reports two SPS patients.",
                possibilities=[],
            ),
        )
        with (
            mock.patch("src.pipelines.stage06_counting.hybrid.run_local_count_package", return_value=local_result),
            mock.patch(
                "src.pipelines.stage06_counting.hybrid.adjudicate_count_package",
                side_effect=OpenAIError("api connection dropped"),
            ),
        ):
            with self.assertRaises(Stage06DependencyError):
                hybrid_count_row(package)


if __name__ == "__main__":
    unittest.main()
