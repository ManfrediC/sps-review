from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
PIPELINES_DIR = REPO_ROOT / "src" / "pipelines"
if str(PIPELINES_DIR) not in sys.path:
    sys.path.insert(0, str(PIPELINES_DIR))

from stage07_XML import run_stage07_xml as runner  # noqa: E402


class TestStage07XmlRunner(unittest.TestCase):
    def test_annotation_defaults_preserve_openai_block_offsets(self) -> None:
        with mock.patch.object(sys, "argv", ["run_stage07_xml.py", "--paper-id", "10"]):
            args = runner.parse_args()

        self.assertEqual(args.annotation_provider, "openai")
        self.assertEqual(args.annotation_architecture, "block_offsets")
        self.assertEqual(args.max_paid_api_cost_usd, 0.0)
        self.assertEqual(args.deepseek_max_output_tokens, 24000)
        self.assertEqual(args.deepseek_request_timeout_seconds, 3600.0)
        self.assertEqual(args.openai_review_model, "gpt-5.4")
        self.assertEqual(args.openai_review_reasoning_effort, "medium")
        self.assertEqual(args.openai_review_max_output_tokens, 20000)

    def test_budget_cap_annotation_marks_manual_review(self) -> None:
        payload = runner.budget_cap_annotation("individual_case_split")

        self.assertEqual(payload["annotation_mode"], "budget_cap_exceeded")
        self.assertEqual(payload["route_mode"], "individual_case_split")
        self.assertEqual(payload["segments"], [])
        self.assertEqual(payload["manual_review_reasons"], ["budget_cap_exceeded"])

    def test_budget_cap_reached_uses_estimated_telemetry_cost(self) -> None:
        rows = [
            {"estimated_cost_usd": "0.20"},
            {"estimated_cost_usd": "0.30"},
        ]

        self.assertTrue(runner.budget_cap_reached(0.50, rows))
        self.assertFalse(runner.budget_cap_reached(0.51, rows))
        self.assertFalse(runner.budget_cap_reached(0.0, rows))

    def test_load_initial_telemetry_rows_prefers_jsonl_when_resuming(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            jsonl_path = tmp_path / "api_telemetry.jsonl"
            csv_path = tmp_path / "api_telemetry.csv"
            jsonl_path.write_text('{"estimated_cost_usd":"0.10","paper_id":"10"}\n', encoding="utf-8")
            csv_path.write_text("estimated_cost_usd,paper_id\n0.20,19\n", encoding="utf-8")

            rows = runner.load_initial_telemetry_rows(jsonl_path, csv_path)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["paper_id"], "10")
        self.assertEqual(rows[0]["estimated_cost_usd"], "0.10")


if __name__ == "__main__":
    unittest.main()
