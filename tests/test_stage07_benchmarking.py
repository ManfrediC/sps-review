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
from stage07_benchmarking.promotion import evaluate_gate_results, load_promotion_gates  # noqa: E402
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
        self.assertTrue(score["contamination_details"])
        self.assertIn("References", {detail["text_excerpt"] for detail in score["contamination_details"]})
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

    def test_contamination_ignores_method_mentions_in_case_text(self) -> None:
        gold_payload = {
            "paper_id": "9003",
            "entities": [{"id": "p1"}],
            "segments": [segment("g0001", ["p1"], 0, 10)],
        }
        predicted_payload = {
            "paper_id": "9003",
            "entities": [{"id": "p1"}],
            "segments": [
                {
                    **segment("p0001", ["p1"], 0, 10),
                    "text": "Autoantibodies were detected by the method of Solimena et al. (4).",
                },
                {
                    **segment("p0002", ["p1"], 20, 30),
                    "text": "Appropriate manipulation of the motor system (see Methods) reduced activity.",
                },
            ],
        }

        score = metrics.score_segments_payloads(
            gold_payload=gold_payload,
            predicted_payload=predicted_payload,
        )

        self.assertNotIn("unsafe_section_text:p0001", score["contamination_flags"])
        self.assertNotIn("unsafe_section_text:p0002", score["contamination_flags"])

    def test_contamination_flags_actual_methods_heading(self) -> None:
        gold_payload = {
            "paper_id": "9004",
            "entities": [{"id": "p1"}, {"id": "p2"}],
            "segments": [segment("g0001", ["p1"], 0, 10), segment("g0002", ["p2"], 20, 30)],
        }
        predicted_payload = {
            "paper_id": "9004",
            "entities": [{"id": "p1"}, {"id": "p2"}],
            "segments": [
                {
                    **segment("p0001", ["p1", "p2"], 0, 30, role="shared"),
                    "text": "Methods. We studied two women with stiff-person syndrome by immunocytochemistry.",
                }
            ],
        }

        score = metrics.score_segments_payloads(
            gold_payload=gold_payload,
            predicted_payload=predicted_payload,
        )

        self.assertIn("unsafe_section_text:p0001", score["contamination_flags"])

    def test_cross_target_label_guard_ignores_external_report_numbering(self) -> None:
        gold_payload = {
            "paper_id": "9005",
            "entities": [{"id": "p1", "label": "Patient 1"}, {"id": "p2", "label": "Patient 2"}],
            "segments": [segment("g0001", ["p1"], 0, 10), segment("g0002", ["p2"], 20, 30)],
        }
        predicted_payload = {
            "paper_id": "9005",
            "entities": [{"id": "p1", "label": "Patient 1"}, {"id": "p2", "label": "Patient 2"}],
            "segments": [
                {
                    **segment("p0001", ["p1"], 0, 10),
                    "text": "Patient 1 had been described previously by Piccolo et al. (Patient 2 in their report).",
                }
            ],
        }

        score = metrics.score_segments_payloads(
            gold_payload=gold_payload,
            predicted_payload=predicted_payload,
        )

        self.assertFalse(
            any(flag.startswith("cross_target_label_leak") for flag in score["contamination_flags"]),
            score["contamination_flags"],
        )

    def test_cross_target_label_guard_ignores_comparison_context(self) -> None:
        gold_payload = {
            "paper_id": "9006",
            "entities": [{"id": "p1", "label": "Patient 1"}, {"id": "p2", "label": "Patient 2"}],
            "segments": [segment("g0001", ["p1"], 0, 10), segment("g0002", ["p2"], 20, 30)],
        }
        predicted_payload = {
            "paper_id": "9006",
            "entities": [{"id": "p1", "label": "Patient 1"}, {"id": "p2", "label": "Patient 2"}],
            "segments": [
                {
                    **segment("p0001", ["p2"], 20, 30),
                    "text": "Muscle biopsy was similar to that of patient 1.",
                }
            ],
        }

        score = metrics.score_segments_payloads(
            gold_payload=gold_payload,
            predicted_payload=predicted_payload,
        )

        self.assertFalse(
            any(flag.startswith("cross_target_label_leak") for flag in score["contamination_flags"]),
            score["contamination_flags"],
        )

    def test_cross_target_label_guard_keeps_current_shared_patient_mix(self) -> None:
        gold_payload = {
            "paper_id": "9007",
            "entities": [{"id": "p1", "label": "Patient 1"}, {"id": "p2", "label": "Patient 2"}],
            "segments": [segment("g0001", ["p1"], 0, 10), segment("g0002", ["p2"], 20, 30)],
        }
        predicted_payload = {
            "paper_id": "9007",
            "entities": [{"id": "p1", "label": "Patient 1"}, {"id": "p2", "label": "Patient 2"}],
            "segments": [
                {
                    **segment("p0001", ["p1", "p2"], 0, 30, role="shared"),
                    "text": "Patient 1 had vitiligo; patient 2 had serum autoantibodies.",
                }
            ],
        }

        score = metrics.score_segments_payloads(
            gold_payload=gold_payload,
            predicted_payload=predicted_payload,
        )

        self.assertIn("cross_target_label_leak:p1:p2:p0001", score["contamination_flags"])

    def test_uncertain_segments_do_not_count_as_target_view_contamination(self) -> None:
        gold_payload = {
            "paper_id": "9008",
            "entities": [{"id": "p1", "label": "Patient 1"}, {"id": "p2", "label": "Patient 2"}],
            "segments": [segment("g0001", ["p1"], 0, 10), segment("g0002", ["p2"], 20, 30)],
        }
        predicted_payload = {
            "paper_id": "9008",
            "entities": [{"id": "p1", "label": "Patient 1"}, {"id": "p2", "label": "Patient 2"}],
            "segments": [
                {
                    **segment("p0001", ["p1", "p2"], 0, 30, role="uncertain"),
                    "text": "Patient 1 had vitiligo; patient 2 had serum autoantibodies.",
                }
            ],
        }

        score = metrics.score_segments_payloads(
            gold_payload=gold_payload,
            predicted_payload=predicted_payload,
        )

        self.assertEqual(score["contamination_flags"], [])

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
            self.assertTrue(paths.contamination_audit_csv_path.exists())
            self.assertTrue(paths.promotion_gates_path.exists())
            self.assertTrue(paths.gate_results_csv_path.exists())
            self.assertTrue(paths.pricing_table_path.exists())
            self.assertIn("Micro precision", paths.summary_md_path.read_text(encoding="utf-8"))
            self.assertEqual(load_telemetry_rows(paths.telemetry_jsonl_path)[0]["provider"], "openai")
            self.assertIn("promotion_status", paths.gate_results_csv_path.read_text(encoding="utf-8"))
            self.assertIn("text_excerpt", paths.contamination_audit_csv_path.read_text(encoding="utf-8"))

    def test_promotion_gates_fail_contamination_before_score_thresholds(self) -> None:
        gates = load_promotion_gates()
        gate_results = evaluate_gate_results(
            [
                {
                    "paper_id": "9001",
                    "matrix_config_name": "candidate_a",
                    "micro": {
                        "precision": 1.0,
                        "recall": 1.0,
                        "f1": 1.0,
                        "predicted_chars": 10,
                        "gold_chars": 10,
                        "overlap_chars": 10,
                    },
                    "target_inventory_exact": True,
                    "contamination_flags": ["unsafe_section_text:s0001"],
                    "role_attribution_errors": [],
                    "readiness_calibration": {"false_ready": False, "false_not_ready": False},
                    "xml_roundtrip_status": "passed",
                    "json_validation_status": "passed",
                }
            ],
            gates,
        )

        self.assertEqual(gate_results[0]["promotion_status"], "fail")
        self.assertIn("contaminated_papers:1>0", gate_results[0]["failed_gates"])

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
