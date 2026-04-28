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
            ],
        }

        score = metrics.score_segments_payloads(
            gold_payload=gold_payload,
            predicted_payload=predicted_payload,
            registry_row={"ready_for_langextract": "false", "manual_review_reasons": "review"},
        )

        self.assertEqual(score["missing_targets"], ["p2"])
        self.assertEqual(score["extra_targets"], ["p3"])
        self.assertIn("targeted_background_segment:s0003", score["contamination_flags"])
        self.assertIn("extra_target_segment:p3:s0002", score["contamination_flags"])
        self.assertAlmostEqual(score["micro"]["precision"], 5 / 15)
        self.assertAlmostEqual(score["micro"]["recall"], 5 / 20)

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
            )

            self.assertTrue(paths.config_path.exists())
            self.assertTrue(paths.paper_scores_path.exists())
            self.assertTrue(paths.summary_csv_path.exists())
            self.assertTrue(paths.summary_json_path.exists())
            self.assertIn("Micro precision", paths.summary_md_path.read_text(encoding="utf-8"))

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


if __name__ == "__main__":
    unittest.main()
