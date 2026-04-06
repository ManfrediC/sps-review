from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


REPO_ROOT = Path(__file__).resolve().parents[1]
SCORE_SCRIPT = REPO_ROOT / "src" / "validation" / "stage04_model_benchmark" / "score_models.py"
RUN_SCRIPT = REPO_ROOT / "src" / "validation" / "stage04_model_benchmark" / "run_models.py"
REVIEW_HELPER_SCRIPT = REPO_ROOT / "src" / "validation" / "stage04_model_benchmark" / "_review.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestStage04ModelBenchmarkScoring(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.score_mod = _load_module("stage04_model_benchmark_score_module", SCORE_SCRIPT)
        cls.run_mod = _load_module("stage04_model_benchmark_run_module", RUN_SCRIPT)
        cls.review_helper_mod = _load_module("stage04_model_benchmark_review_helper_module", REVIEW_HELPER_SCRIPT)

    def test_compute_model_metrics_handles_partial_and_evidence_scoring(self) -> None:
        benchmark_rows = [
            {
                "paper_id": "1",
                "gold_source_category": "single_case_report",
                "gold_original_sps_data": "yes",
                "gold_contains_individual_level_data": "true",
                "gold_contains_group_level_data": "false",
                "gold_ambiguity_tier": "clear",
            },
            {
                "paper_id": "2",
                "gold_source_category": "review_article",
                "gold_original_sps_data": "no",
                "gold_contains_individual_level_data": "false",
                "gold_contains_group_level_data": "false",
                "gold_ambiguity_tier": "ambiguous",
            },
        ]
        predictions = {
            "1": {
                "result": {
                    "source_type": "single_case_report",
                    "original_sps_spectrum_data": "yes",
                    "contains_individual_level_data": "true",
                    "contains_group_level_data": "false",
                    "confidence": "high",
                    "manual_review_required": "false",
                    "count_manual_review_required": "false",
                    "evidence": [
                        {"quote": "Case report of one patient.", "page": 1},
                        {"quote": "The patient improved.", "page": 2},
                    ],
                }
            },
            "2": {
                "result": {
                    "source_type": "review_article",
                    "original_sps_spectrum_data": "",
                    "contains_individual_level_data": "false",
                    "contains_group_level_data": "false",
                    "confidence": "medium",
                    "manual_review_required": "true",
                    "count_manual_review_required": "false",
                    "evidence": None,
                }
            },
        }

        metrics = self.score_mod.compute_model_metrics(benchmark_rows, predictions)

        self.assertAlmostEqual(metrics["source_category_accuracy"], 1.0)
        self.assertAlmostEqual(metrics["original_data_yes_no_accuracy"], 1.0)
        self.assertEqual(metrics["original_data_available_rows"], 1)
        self.assertAlmostEqual(metrics["appropriate_abstention_rate"], 1.0)
        self.assertAlmostEqual(metrics["escalation_manual_review_rate"], 0.5)
        self.assertIsNotNone(metrics["evidence_quality"])
        self.assertGreater(metrics["evidence_quality"]["evidence_quality_score"], 0.9)

    def test_parse_models_requires_explicit_opt_in_for_gpt41(self) -> None:
        args = self.run_mod.parse_args.__globals__["argparse"].Namespace(
            model=["gpt-4.1"],
            allow_baseline_regeneration=False,
        )
        with self.assertRaises(SystemExit):
            self.run_mod.parse_models(args)

        args.allow_baseline_regeneration = True
        self.assertEqual(self.run_mod.parse_models(args), ["gpt-4.1"])

    def test_scoring_prefers_raw_gpt41_outputs_when_present(self) -> None:
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            model_root = root / "model_outputs" / "gpt-4.1"
            model_root.mkdir(parents=True)
            predictions_path = model_root / "predictions.jsonl"
            predictions_path.write_text(
                '{"paper_id":"1","result":{"source_type":"review_article","original_sps_spectrum_data":"no","contains_individual_level_data":"false","contains_group_level_data":"false","confidence":"medium","manual_review_required":"false","count_manual_review_required":"false","evidence":[{"quote":"review article","page":1}]}}\n',
                encoding="utf-8",
            )
            paths = self.score_mod.shared.BenchmarkPaths(
                benchmark_dir=root,
                benchmark_set_path=root / "benchmark_set.csv",
                manifest_path=root / "benchmark_manifest.json",
                frozen_payload_dir=root / "frozen_payloads",
                frozen_payload_manifest_path=root / "frozen_payload_manifest.json",
                model_output_root=root / "model_outputs",
                report_root=root / "reports",
            )
            predictions = self.score_mod.model_predictions_by_name(paths)
            self.assertIn("gpt-4.1", predictions)
            self.assertEqual(
                predictions["gpt-4.1"]["1"]["result"]["source_type"],
                "review_article",
            )

    def test_note_status_counts_defaults_missing_rows_to_pending(self) -> None:
        benchmark_rows = [{"paper_id": "1"}, {"paper_id": "2"}, {"paper_id": "3"}]
        notes_by_id = {
            "1": {"review_status": "reviewed"},
            "2": {"review_status": "flagged"},
        }
        counts = self.review_helper_mod.note_status_counts(benchmark_rows, notes_by_id)
        self.assertEqual(counts["reviewed"], 1)
        self.assertEqual(counts["flagged"], 1)
        self.assertEqual(counts["pending"], 1)


if __name__ == "__main__":
    unittest.main()
