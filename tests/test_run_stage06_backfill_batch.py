from __future__ import annotations

import csv
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from src.pipelines.stage06_counting import overrides
from src.validation import _stage06_backfill as backfill
from src.validation import _stage06_review as review
from src.validation import run_stage06_backfill_batch as runner


class TestRunStage06BackfillBatch(unittest.TestCase):
    def test_main_reports_resume_summary_after_failed_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            text_dir = root / "text"
            run_root = root / "results"
            qa_output_dir = root / "qa"
            campaign_root = root / "campaigns"
            gold_manifest_path = root / "gold_manifest.json"
            manual_review_path = root / "source_sps_case_count_manual_review.csv"
            artifact_registry_path = root / "paper_artifact_registry.csv"
            batch_manifest_path = campaign_root / "stage06_backfill_demo" / "batches" / "b002.json"
            campaign_manifest_path = campaign_root / "stage06_backfill_demo" / "manifest.json"

            text_dir.mkdir()
            for paper_id in ["1", "2"]:
                (text_dir / f"{paper_id}.json").write_text("{}", encoding="utf-8")

            gold_manifest_path.write_text(json.dumps({"entries": []}), encoding="utf-8")
            with manual_review_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=overrides.OVERRIDE_FIELDNAMES)
                writer.writeheader()
            with artifact_registry_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["paper_id", "pdf_paths_relative", "text_json_path"])
                writer.writeheader()
                for paper_id in ["1", "2"]:
                    writer.writerow(
                        {
                            "paper_id": paper_id,
                            "pdf_paths_relative": rf"data\pdf_original\{paper_id}.pdf",
                            "text_json_path": rf"data\extraction_json\text\{paper_id}.json",
                        }
                    )

            backfill.write_json(
                batch_manifest_path,
                {
                    "campaign_id": "stage06_backfill_demo",
                    "batch_index": 2,
                    "batch_id": "b002",
                    "paper_count": 2,
                    "paper_ids": ["1", "2"],
                    "run_id_base": "stage06_backfill_b002_n2_20260419",
                    "combined_output_csv_path": backfill.display_path(
                        qa_output_dir / "stage06_backfill_b002_n2_20260419_combined.csv"
                    ),
                    "inspection_md_path": backfill.display_path(
                        qa_output_dir / "stage06_backfill_b002_n2_20260419_inspection.md"
                    ),
                    "review_comments_csv_path": backfill.display_path(
                        qa_output_dir / "stage06_backfill_b002_n2_20260419_review_comments.csv"
                    ),
                    "review_notes_md_path": backfill.display_path(
                        qa_output_dir / "stage06_backfill_b002_n2_20260419_review_notes.md"
                    ),
                },
            )
            backfill.write_json(
                campaign_manifest_path,
                {
                    "campaign_id": "stage06_backfill_demo",
                    "batch_size": 2,
                    "batches": [
                        {
                            "batch_index": 2,
                            "batch_id": "b002",
                            "run_id_base": "stage06_backfill_b002_n2_20260419",
                            "batch_manifest_path": backfill.display_path(batch_manifest_path),
                        }
                    ],
                },
            )

            def fake_run_hybrid_batch_command(command: list[str]) -> None:
                del command
                run_dir = run_root / "stage06_backfill_b002_n2_20260419"
                (run_dir / "results").mkdir(parents=True, exist_ok=True)
                (run_dir / "results" / "1.json").write_text(
                    json.dumps(
                        {
                            "paper_id": "1",
                            "count_row": {
                                "paper_id": "1",
                                "title": "Paper 1",
                                "likely_sps_case_count": "1",
                                "count_verification_status": "llm_manual_review_required",
                                "count_manual_review_required": "true",
                                "count_reason": "verification_status=llm_manual_review_required",
                            },
                            "source_text_json_path": r"data\extraction_json\text\1.json",
                            "preferred_text_json_path": r"data\extraction_json\text\1.json",
                        }
                    ),
                    encoding="utf-8",
                )
                raise RuntimeError("simulated stop")

            actual_write_batch_qa_pack = backfill.write_batch_qa_pack
            actual_write_campaign_outputs = backfill.write_campaign_outputs
            actual_write_rollup = backfill.write_campaign_high_risk_review_rollup
            original_artifact_registry_path = review.ARTIFACT_REGISTRY_PATH
            stdout = io.StringIO()
            argv = [
                "run_stage06_backfill_batch.py",
                "--batch-manifest",
                str(batch_manifest_path),
                "--run-root",
                str(run_root),
                "--qa-output-dir",
                str(qa_output_dir),
                "--campaign-root",
                str(campaign_root),
                "--allow-paid-run",
            ]
            try:
                review.ARTIFACT_REGISTRY_PATH = artifact_registry_path
                with mock.patch.object(sys, "argv", argv):
                    with mock.patch.object(runner, "run_stage06_dependency_preflight", return_value=None):
                        with mock.patch.object(
                            runner.backfill,
                            "run_hybrid_batch_command",
                            side_effect=fake_run_hybrid_batch_command,
                        ):
                            with mock.patch.object(
                                runner.backfill,
                                "write_batch_qa_pack",
                                side_effect=lambda **kwargs: actual_write_batch_qa_pack(
                                    manual_review_path=manual_review_path,
                                    **kwargs,
                                ),
                            ):
                                with mock.patch.object(
                                    runner.backfill,
                                    "write_campaign_outputs",
                                    side_effect=lambda **kwargs: actual_write_campaign_outputs(
                                        batch_size=2,
                                        text_dir=text_dir,
                                        gold_manifest_path=gold_manifest_path,
                                        manual_review_path=manual_review_path,
                                        **kwargs,
                                    ),
                                ):
                                    with mock.patch.object(
                                        runner.backfill,
                                        "write_campaign_high_risk_review_rollup",
                                        side_effect=lambda **kwargs: actual_write_rollup(
                                            manual_review_path=manual_review_path,
                                            **kwargs,
                                        ),
                                    ):
                                        with self.assertRaisesRegex(RuntimeError, "simulated stop"):
                                            with redirect_stdout(stdout):
                                                runner.main()
            finally:
                review.ARTIFACT_REGISTRY_PATH = original_artifact_registry_path

            payload = json.loads(stdout.getvalue())

            self.assertEqual(payload["run_status"], "interrupted_or_failed")
            self.assertEqual(payload["resume_summary"]["completed_count"], 1)
            self.assertEqual(payload["resume_summary"]["remaining_count"], 1)
            self.assertEqual(payload["resume_summary"]["remaining_paper_ids"], ["2"])
            self.assertTrue((qa_output_dir / "stage06_backfill_b002_n2_20260419_combined.csv").exists())
            self.assertTrue((campaign_root / "stage06_backfill_demo" / "high_risk_review_rollup.md").exists())


if __name__ == "__main__":
    unittest.main()
