from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINES_DIR = REPO_ROOT / "src" / "pipelines"
if str(PIPELINES_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINES_DIR))

from stage07_benchmarking import metrics  # noqa: E402
from stage07_benchmarking.manifest import (  # noqa: E402
    benchmark_paths,
    load_model_matrix,
    write_benchmark_artifacts,
)
from stage07_benchmarking.telemetry import load_telemetry_rows, telemetry_row  # noqa: E402


def segment(
    segment_id: str,
    targets: list[str],
    start: int,
    end: int,
    *,
    role: str = "patient_specific",
) -> dict[str, object]:
    return {
        "segment_id": segment_id,
        "logical_segment_id": segment_id,
        "targets": targets,
        "role": role,
        "source_offsets": {"start": start, "end": end},
    }


class TestStage07Benchmarking(unittest.TestCase):
    def test_scores_target_char_metrics_and_contamination(self) -> None:
        gold_payload = {
            "paper_id": "9001",
            "entities": [{"id": "p1"}, {"id": "p2"}],
            "segments": [
                segment("s0001", ["p1"], 0, 10),
                segment("s0002", ["p2"], 20, 30),
            ],
        }
        predicted_payload = {
            "paper_id": "9001",
            "entities": [{"id": "p1"}, {"id": "p3"}],
            "segments": [
                segment("s0001", ["p1"], 0, 5),
                segment("s0002", ["p3"], 40, 50),
                segment("s0003", ["p1"], 60, 70, role="background"),
                {
                    "segment_id": "s0004",
                    "logical_segment_id": "s0004",
                    "targets": ["p1"],
                    "role": "patient_specific",
                    "text": "References",
                    "source_offsets": {"start": 80, "end": 90},
                },
            ],
            "validation": {"status": "passed", "roundtrip_status": "passed"},
        }

        score = metrics.score_segments_payloads(
            gold_payload=gold_payload,
            predicted_payload=predicted_payload,
            registry_row={"ready_for_langextract": "false", "manual_review_reasons": "review"},
        )

        self.assertEqual(score["missing_targets"], ["p2"])
        self.assertEqual(score["extra_targets"], ["p3"])
        self.assertFalse(score["target_inventory_exact"])
        self.assertIn("targeted_background_segment:s0003", score["contamination_flags"])
        self.assertIn("extra_target_segment:p3:s0002", score["contamination_flags"])
        self.assertIn("unsafe_section_text:s0004", score["contamination_flags"])
        self.assertAlmostEqual(score["micro"]["precision"], 5 / 25)
        self.assertAlmostEqual(score["micro"]["recall"], 5 / 20)
        self.assertEqual(score["xml_roundtrip_status"], "passed")
        self.assertEqual(score["json_validation_status"], "passed")

    def test_scores_role_mismatch_and_false_ready(self) -> None:
        gold_payload = {
            "paper_id": "9002",
            "entities": [{"id": "p1"}],
            "segments": [segment("g0001", ["p1"], 0, 10, role="shared")],
        }
        predicted_payload = {
            "paper_id": "9002",
            "entities": [{"id": "p1"}],
            "segments": [segment("p0001", ["p1"], 0, 10, role="patient_specific")],
        }

        score = metrics.score_segments_payloads(
            gold_payload=gold_payload,
            predicted_payload=predicted_payload,
            registry_row={"ready_for_langextract": "true"},
            gold_registry_row={"ready_for_langextract": "true"},
        )

        self.assertIn("role_mismatch:p1:p0001:patient_specific:shared", score["role_attribution_errors"])
        self.assertTrue(score["readiness_calibration"]["false_ready"])

    def test_writes_contained_benchmark_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            paths = benchmark_paths(Path(tmp_dir), "run1")
            paper_scores = [
                {
                    "paper_id": "9001",
                    "micro": {
                        "precision": 1.0,
                        "recall": 0.5,
                        "f1": 2 / 3,
                        "predicted_chars": 5,
                        "gold_chars": 10,
                        "overlap_chars": 5,
                    },
                    "missing_targets": ["p2"],
                    "extra_targets": [],
                    "contamination_flags": [],
                    "ready_for_langextract": "false",
                    "manual_review_reasons": "missing_target_evidence:p2",
                }
            ]
            summary = metrics.summarise_paper_scores(paper_scores)

            write_benchmark_artifacts(
                paths=paths,
                run_config={"schema_version": "test", "paid_api_calls": False},
                paper_scores=paper_scores,
                summary=summary,
                telemetry_rows=[
                    telemetry_row(
                        benchmark_run_id="run1",
                        matrix_config_name="O1",
                        paper_id="9001",
                        provider="openai",
                        model="gpt-5.5",
                        endpoint="responses",
                        usage={"input_tokens": 1000, "output_tokens": 100},
                    )
                ],
            )

            self.assertTrue(paths.config_path.exists())
            self.assertTrue(paths.paper_scores_path.exists())
            self.assertTrue(paths.target_scores_csv_path.exists())
            self.assertTrue(paths.summary_csv_path.exists())
            self.assertTrue(paths.summary_json_path.exists())
            self.assertTrue(paths.telemetry_csv_path.exists())
            self.assertTrue(paths.telemetry_jsonl_path.exists())
            self.assertTrue(paths.pareto_summary_csv_path.exists())
            self.assertTrue(paths.pricing_table_path.exists())
            self.assertIn("Micro precision", paths.summary_md_path.read_text(encoding="utf-8"))
            self.assertEqual(load_telemetry_rows(paths.telemetry_jsonl_path)[0]["provider"], "openai")

    def test_load_model_matrix_normalises_configs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            matrix_path = Path(tmp_dir) / "matrix.json"
            matrix_path.write_text(
                json.dumps(
                    {
                        "configs": [
                            {
                                "name": "gpt55_medium",
                                "provider": "openai",
                                "model": "gpt-5.5",
                                "reasoning_effort": "medium",
                                "max_output_tokens": 25000,
                                "strict_json_schema": True,
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            configs = load_model_matrix(matrix_path)

            self.assertEqual(configs[0]["name"], "gpt55_medium")
            self.assertEqual(configs[0]["provider"], "openai")
            self.assertTrue(configs[0]["strict_json_schema"])

    def test_load_model_matrix_rejects_secret_like_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            matrix_path = Path(tmp_dir) / "matrix.json"
            matrix_path.write_text(
                json.dumps(
                    {
                        "configs": [
                            {
                                "name": "bad",
                                "provider": "openai",
                                "model": "gpt-5.5",
                                "api_key": "not-for-matrix",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "secret-like"):
                load_model_matrix(matrix_path)

    def test_telemetry_row_estimates_cost_and_normalises_usage(self) -> None:
        row = telemetry_row(
            benchmark_run_id="run1",
            matrix_config_name="O1",
            paper_id="9001",
            provider="openai",
            model="gpt-5.5",
            endpoint="responses",
            usage={
                "input_tokens": 1000,
                "output_tokens": 100,
                "output_tokens_details": {"reasoning_tokens": 25},
            },
            latency_ms=1234,
        )

        self.assertEqual(row["reasoning_tokens"], "25")
        self.assertEqual(row["latency_ms"], "1234")
        self.assertGreater(float(row["estimated_cost_usd"]), 0)
        self.assertNotIn("api_key", row)


if __name__ == "__main__":
    unittest.main()
