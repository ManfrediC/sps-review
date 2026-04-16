from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_COUNT_LLM_SCRIPT = REPO_ROOT / "src" / "pipelines" / "06_extract_sps_case_counts_LLM.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestStage06ExtractSpsCaseCountsLlm(unittest.TestCase):
    def test_default_output_path_uses_run_id(self) -> None:
        mod = _load_module("stage06_count_llm_default_output", CASE_COUNT_LLM_SCRIPT)
        output_path = mod.default_output_path("stage06_count_llm_test")
        self.assertEqual(
            output_path,
            REPO_ROOT / "qa" / "validation" / "stage06_llm" / "stage06_count_llm_test.csv",
        )

    def test_build_local_adviser_notes_includes_local_summary(self) -> None:
        mod = _load_module("stage06_count_llm_adviser_notes", CASE_COUNT_LLM_SCRIPT)
        parsed_output = mod.json.loads(
            """{
                "n_spsd_patients": 2,
                "evidence_span": "We report on the use of plasma exchange in 2 patients with stiff-man syndrome.",
                "data_granularity": "individual-level",
                "confidence": "high",
                "needs_review": false,
                "reasoning_short": "The abstract explicitly reports two original SPS patients.",
                "possibilities": []
            }"""
        )
        parsed = mod.sys.modules["src.pipelines.stage06_counting.local_models"].LocalCountDecisionOutput.model_validate(parsed_output)
        notes = mod.build_local_adviser_notes(
            local_model_name="gemma4:e4b",
            local_model_status="parsed_ok",
            local_model_error="",
            local_flags=[],
            parsed_output=parsed,
        )
        self.assertIn("local_n_spsd_patients: 2", notes)
        self.assertIn("local_data_granularity: individual-level", notes)
        self.assertIn("local_possibility_count: 0", notes)

    def test_compare_local_to_final_row_reports_agreement(self) -> None:
        mod = _load_module("stage06_count_llm_compare", CASE_COUNT_LLM_SCRIPT)
        parsed_output = mod.sys.modules["src.pipelines.stage06_counting.local_models"].LocalCountDecisionOutput.model_validate(
            {
                "n_spsd_patients": 1,
                "evidence_span": "Case report of one patient.",
                "data_granularity": "individual-level",
                "confidence": "high",
                "needs_review": False,
                "reasoning_short": "Single-case report.",
                "possibilities": [],
            }
        )
        status = mod.compare_local_to_final_row(
            parsed_output,
            {
                "likely_sps_case_count": "1",
                "count_manual_review_required": "false",
            },
            "parsed_ok",
        )
        self.assertEqual(status, "agree")

    def test_augment_calibration_row_adds_local_fields(self) -> None:
        mod = _load_module("stage06_count_llm_augment", CASE_COUNT_LLM_SCRIPT)
        parsed_output = mod.sys.modules["src.pipelines.stage06_counting.local_models"].LocalCountDecisionOutput.model_validate(
            {
                "n_spsd_patients": 3,
                "evidence_span": "Three patients were identified.",
                "data_granularity": "group-level",
                "confidence": "medium",
                "needs_review": True,
                "reasoning_short": "Mixed cohort requires review.",
                "possibilities": [],
            }
        )
        row = mod.augment_calibration_row(
            {"likely_sps_case_count": "3", "count_manual_review_required": "true"},
            gpt_ran=True,
            local_model_name="gemma4:e4b",
            local_model_status="parsed_with_flags",
            local_duration_seconds=1.234,
            local_model_error="",
            local_flags=["LOCAL_NON_HIGH_CONFIDENCE_NO_REVIEW"],
            local_result_json_path="results/stage06_count_llm_runs/test/local_model_results/214.json",
            local_parsed=parsed_output,
        )
        self.assertEqual(row["local_model_name"], "gemma4:e4b")
        self.assertEqual(row["local_model_status"], "parsed_with_flags")
        self.assertEqual(row["local_n_spsd_patients"], "3")
        self.assertEqual(row["local_vs_gpt_status"], "agree")

    def test_augment_calibration_row_marks_local_only_when_gpt_not_run(self) -> None:
        mod = _load_module("stage06_count_llm_augment_local_only", CASE_COUNT_LLM_SCRIPT)
        parsed_output = mod.sys.modules["src.pipelines.stage06_counting.local_models"].LocalCountDecisionOutput.model_validate(
            {
                "n_spsd_patients": 1,
                "evidence_span": "Case 10 ... stiff-person syndrome.",
                "data_granularity": "group-level",
                "confidence": "medium",
                "needs_review": True,
                "reasoning_short": "Local-only advisory count.",
                "possibilities": [],
            }
        )
        row = mod.augment_calibration_row(
            {"likely_sps_case_count": "1", "count_manual_review_required": "true"},
            gpt_ran=False,
            local_model_name="gemma4:e4b",
            local_model_status="parsed_ok",
            local_duration_seconds=1.0,
            local_model_error="",
            local_flags=[],
            local_result_json_path="results/stage06_count_llm_runs/test/local_model_results/22.json",
            local_parsed=parsed_output,
        )
        self.assertEqual(row["gpt_ran"], "false")
        self.assertEqual(row["local_vs_gpt_status"], "not_run")


if __name__ == "__main__":
    unittest.main()
