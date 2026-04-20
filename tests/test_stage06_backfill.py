from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from src.pipelines.stage06_counting import overrides
from src.validation import _stage06_backfill as backfill
from src.validation import _stage06_review as review


class TestStage06Backfill(unittest.TestCase):
    def test_compute_coverage_snapshot_deduplicates_manual_and_hybrid_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            text_dir = root / "text"
            run_root = root / "stage06_count_runs"
            gold_manifest_path = root / "gold_manifest.json"
            manual_review_path = root / "source_sps_case_count_manual_review.csv"

            text_dir.mkdir()
            run_root.mkdir()
            for paper_id in ["1", "2", "3", "4", "5"]:
                (text_dir / f"{paper_id}.json").write_text("{}", encoding="utf-8")

            gold_manifest_path.write_text(
                json.dumps(
                    {
                        "entries": [
                            {"paper_id": "1", "gold_status": "active"},
                            {"paper_id": "2", "gold_status": "active"},
                            {"paper_id": "99", "gold_status": "excluded"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            with manual_review_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["paper_id", "review_status"])
                writer.writeheader()
                writer.writerow({"paper_id": "2", "review_status": "reviewed"})
                writer.writerow({"paper_id": "3", "review_status": "reviewed"})
                writer.writerow({"paper_id": "4", "review_status": "pending"})

            hybrid_run = run_root / "stage06_demo"
            (hybrid_run / "results").mkdir(parents=True)
            (hybrid_run / "results" / "3.json").write_text(
                json.dumps({"paper_id": "3", "count_row": {"count_version": "hybrid_v2_gpt-5.4"}}),
                encoding="utf-8",
            )
            (hybrid_run / "results" / "4.json").write_text(
                json.dumps({"paper_id": "4", "model_count_row": {"count_version": "hybrid_v2_gpt-5.4"}}),
                encoding="utf-8",
            )
            (hybrid_run / "results" / "5.json").write_text(
                json.dumps({"paper_id": "5", "count_row": {"count_version": "llm_v1_gpt4.1"}}),
                encoding="utf-8",
            )

            snapshot = backfill.compute_coverage_snapshot(
                text_dir=text_dir,
                gold_manifest_path=gold_manifest_path,
                manual_review_path=manual_review_path,
                run_root=run_root,
            )

        self.assertEqual(snapshot.manual_gold_ids, ["1", "2", "3"])
        self.assertEqual(snapshot.hybrid_processed_ids, ["3", "4"])
        self.assertEqual(snapshot.covered_ids, ["1", "2", "3", "4"])
        self.assertEqual(snapshot.uncovered_ids, ["5"])
        self.assertEqual(snapshot.summary_counts()["both"], 1)
        self.assertEqual(snapshot.summary_counts()["remaining"], 1)

    def test_build_campaign_payload_chunks_batches_deterministically(self) -> None:
        paper_ids = [str(index) for index in range(1, 111)]
        snapshot = backfill.CoverageSnapshot(
            all_text_ids=paper_ids,
            gold_manual_ids=[],
            override_manual_ids=[],
            manual_gold_ids=[],
            hybrid_processed_ids=[],
            covered_ids=[],
            uncovered_ids=paper_ids,
        )
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            campaign_payload, batch_payloads = backfill.build_campaign_payload(
                snapshot=snapshot,
                campaign_id="stage06_backfill_20260418",
                batch_size=50,
                campaign_root=root,
                qa_output_dir=root / "qa",
                run_root=root / "results",
            )

        self.assertEqual(campaign_payload["coverage"]["summary_counts"]["remaining"], 110)
        self.assertEqual(campaign_payload["batch_count"], 3)
        self.assertEqual(len(batch_payloads), 3)
        self.assertEqual(batch_payloads[0][1]["paper_ids"][0], "1")
        self.assertEqual(batch_payloads[0][1]["paper_ids"][-1], "50")
        self.assertEqual(batch_payloads[2][1]["paper_count"], 10)
        self.assertEqual(batch_payloads[2][1]["run_id_base"], "stage06_backfill_b003_n10_20260418")

    def test_write_campaign_outputs_removes_stale_batch_manifests(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            text_dir = root / "text"
            run_root = root / "stage06_count_runs"
            campaign_root = root / "campaigns"
            qa_output_dir = root / "qa"
            gold_manifest_path = root / "gold_manifest.json"
            manual_review_path = root / "source_sps_case_count_manual_review.csv"

            text_dir.mkdir()
            run_root.mkdir()
            for paper_id in ["1", "2", "3", "4", "5"]:
                (text_dir / f"{paper_id}.json").write_text("{}", encoding="utf-8")

            gold_manifest_path.write_text(json.dumps({"entries": []}), encoding="utf-8")
            with manual_review_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["paper_id", "review_status"])
                writer.writeheader()

            stale_manifest = campaign_root / "stage06_backfill_20260418" / "batches" / "b003.json"
            stale_manifest.parent.mkdir(parents=True, exist_ok=True)
            stale_manifest.write_text("{}", encoding="utf-8")

            manifest_path = backfill.write_campaign_outputs(
                campaign_id="stage06_backfill_20260418",
                batch_size=3,
                campaign_root=campaign_root,
                qa_output_dir=qa_output_dir,
                text_dir=text_dir,
                gold_manifest_path=gold_manifest_path,
                manual_review_path=manual_review_path,
                run_root=run_root,
            )

            batch_dir = manifest_path.parent / "batches"
            self.assertFalse((batch_dir / "b003.json").exists())
            self.assertTrue((batch_dir / "b001.json").exists())
            self.assertTrue((batch_dir / "b002.json").exists())

    def test_write_campaign_outputs_preserves_existing_batch_definitions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            text_dir = root / "text"
            run_root = root / "stage06_count_runs"
            campaign_root = root / "campaigns"
            qa_output_dir = root / "qa"
            gold_manifest_path = root / "gold_manifest.json"
            manual_review_path = root / "source_sps_case_count_manual_review.csv"

            text_dir.mkdir()
            run_root.mkdir()
            for paper_id in ["1", "2", "3", "4", "5", "6"]:
                (text_dir / f"{paper_id}.json").write_text("{}", encoding="utf-8")

            gold_manifest_path.write_text(json.dumps({"entries": []}), encoding="utf-8")
            with manual_review_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["paper_id", "review_status"])
                writer.writeheader()

            manifest_path = backfill.write_campaign_outputs(
                campaign_id="stage06_backfill_20260418",
                batch_size=3,
                campaign_root=campaign_root,
                qa_output_dir=qa_output_dir,
                text_dir=text_dir,
                gold_manifest_path=gold_manifest_path,
                manual_review_path=manual_review_path,
                run_root=run_root,
            )
            original_b001 = backfill.load_json(manifest_path.parent / "batches" / "b001.json")
            original_b002 = backfill.load_json(manifest_path.parent / "batches" / "b002.json")

            completed_run = run_root / "stage06_backfill_b001_n3_20260418" / "results"
            completed_run.mkdir(parents=True)
            for paper_id in ["1", "2", "3"]:
                (completed_run / f"{paper_id}.json").write_text(
                    json.dumps(
                        {
                            "paper_id": paper_id,
                            "count_row": {"count_version": "hybrid_v2_gpt-5.4"},
                        }
                    ),
                    encoding="utf-8",
                )

            manifest_path = backfill.write_campaign_outputs(
                campaign_id="stage06_backfill_20260418",
                batch_size=3,
                campaign_root=campaign_root,
                qa_output_dir=qa_output_dir,
                text_dir=text_dir,
                gold_manifest_path=gold_manifest_path,
                manual_review_path=manual_review_path,
                run_root=run_root,
            )

            refreshed_manifest = backfill.load_json(manifest_path)
            refreshed_b001 = backfill.load_json(manifest_path.parent / "batches" / "b001.json")
            refreshed_b002 = backfill.load_json(manifest_path.parent / "batches" / "b002.json")

            self.assertEqual(refreshed_manifest["coverage"]["summary_counts"]["remaining"], 3)
            self.assertEqual(refreshed_manifest["batch_count"], 2)
            self.assertEqual(refreshed_b001["paper_ids"], original_b001["paper_ids"])
            self.assertEqual(refreshed_b002["paper_ids"], original_b002["paper_ids"])
            self.assertEqual(refreshed_b001["run_id_base"], original_b001["run_id_base"])
            self.assertEqual(refreshed_b002["run_id_base"], original_b002["run_id_base"])

    def test_repair_campaign_outputs_restores_completed_batch_and_batch_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            text_dir = root / "text"
            run_root = root / "stage06_count_runs"
            campaign_root = root / "campaigns"
            qa_output_dir = root / "qa"
            gold_manifest_path = root / "gold_manifest.json"
            manual_review_path = root / "source_sps_case_count_manual_review.csv"
            campaign_path = campaign_root / "stage06_backfill_20260418"
            batch_dir = campaign_path / "batches"

            text_dir.mkdir()
            run_root.mkdir()
            for paper_id in [str(index) for index in range(1, 13)]:
                (text_dir / f"{paper_id}.json").write_text("{}", encoding="utf-8")

            gold_manifest_path.write_text(json.dumps({"entries": []}), encoding="utf-8")
            with manual_review_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["paper_id", "review_status"])
                writer.writeheader()

            batch_dir.mkdir(parents=True)
            (campaign_path / "manifest.json").write_text(
                json.dumps(
                    {
                        "campaign_id": "stage06_backfill_20260418",
                        "batch_size": 5,
                        "batch_count": 2,
                        "batches": [
                            {
                                "batch_index": 1,
                                "batch_id": "b001",
                                "paper_count": 5,
                                "run_id_base": "stage06_backfill_b001_n5_20260418",
                                "batch_manifest_path": "campaigns/stage06_backfill_20260418/batches/b001.json",
                            },
                            {
                                "batch_index": 2,
                                "batch_id": "b002",
                                "paper_count": 2,
                                "run_id_base": "stage06_backfill_b002_n2_20260418",
                                "batch_manifest_path": "campaigns/stage06_backfill_20260418/batches/b002.json",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            for path, payload in [
                (
                    batch_dir / "b001.json",
                    {
                        "batch_index": 1,
                        "batch_id": "b001",
                        "paper_count": 5,
                        "paper_ids": ["1", "2", "3", "4", "5"],
                        "run_id_base": "stage06_backfill_b001_n5_20260418",
                    },
                ),
                (
                    batch_dir / "b002.json",
                    {
                        "batch_index": 2,
                        "batch_id": "b002",
                        "paper_count": 2,
                        "paper_ids": ["11", "12"],
                        "run_id_base": "stage06_backfill_b002_n2_20260418",
                    },
                ),
                (
                    batch_dir / "b003.json",
                    {
                        "batch_index": 3,
                        "batch_id": "b003",
                        "paper_count": 2,
                        "paper_ids": ["11", "12"],
                        "run_id_base": "stage06_backfill_b003_n2_20260418",
                    },
                ),
            ]:
                path.write_text(json.dumps(payload), encoding="utf-8")

            completed_run_dir = run_root / "stage06_backfill_b001_n5_20260418" / "results"
            completed_run_dir.mkdir(parents=True)
            for paper_id in ["6", "7", "8", "9", "10"]:
                (completed_run_dir / f"{paper_id}.json").write_text(
                    json.dumps(
                        {
                            "paper_id": paper_id,
                            "count_row": {"count_version": "hybrid_v2_gpt-5.4"},
                        }
                    ),
                    encoding="utf-8",
                )

            manifest_path = backfill.repair_campaign_outputs(
                campaign_id="stage06_backfill_20260418",
                batch_size=5,
                campaign_root=campaign_root,
                qa_output_dir=qa_output_dir,
                text_dir=text_dir,
                gold_manifest_path=gold_manifest_path,
                manual_review_path=manual_review_path,
                run_root=run_root,
            )

            repaired_manifest = backfill.load_json(manifest_path)
            repaired_b001 = backfill.load_json(batch_dir / "b001.json")
            repaired_b002 = backfill.load_json(batch_dir / "b002.json")
            repaired_b003 = backfill.load_json(batch_dir / "b003.json")
            repaired_batch_files = sorted(path.name for path in batch_dir.glob("*.json"))

        self.assertEqual(repaired_manifest["batch_count"], 3)
        self.assertEqual(repaired_b001["paper_ids"], ["6", "7", "8", "9", "10"])
        self.assertEqual(repaired_b002["paper_ids"], ["1", "2", "3", "4", "5"])
        self.assertEqual(repaired_b003["paper_ids"], ["11", "12"])
        self.assertEqual(repaired_batch_files, ["b001.json", "b002.json", "b003.json"])

    def test_repair_campaign_outputs_preserves_completed_batch_run_id_and_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            text_dir = root / "text"
            run_root = root / "stage06_count_runs"
            campaign_root = root / "campaigns"
            qa_output_dir = root / "qa"
            gold_manifest_path = root / "gold_manifest.json"
            manual_review_path = root / "source_sps_case_count_manual_review.csv"
            campaign_path = campaign_root / "stage06_backfill_20260418"
            batch_dir = campaign_path / "batches"

            text_dir.mkdir()
            run_root.mkdir()
            for paper_id in [str(index) for index in range(1, 8)]:
                (text_dir / f"{paper_id}.json").write_text("{}", encoding="utf-8")

            gold_manifest_path.write_text(json.dumps({"entries": []}), encoding="utf-8")
            with manual_review_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["paper_id", "review_status"])
                writer.writeheader()

            batch_dir.mkdir(parents=True)
            (campaign_path / "manifest.json").write_text(
                json.dumps({"campaign_id": "stage06_backfill_20260418", "batch_size": 5}),
                encoding="utf-8",
            )
            batch_dir.joinpath("b001.json").write_text(
                json.dumps(
                    {
                        "batch_index": 1,
                        "batch_id": "b001",
                        "paper_count": 5,
                        "paper_ids": ["1", "2", "3", "4", "5"],
                        "run_id_base": "stage06_backfill_b001_n5_20260418",
                        "combined_output_csv_path": "qa/stage06_backfill_b001_n5_20260418_combined.csv",
                        "inspection_md_path": "qa/stage06_backfill_b001_n5_20260418_inspection.md",
                        "review_comments_csv_path": "qa/stage06_backfill_b001_n5_20260418_review_comments.csv",
                        "review_notes_md_path": "qa/stage06_backfill_b001_n5_20260418_review_notes.md",
                    }
                ),
                encoding="utf-8",
            )
            batch_dir.joinpath("b002.json").write_text(
                json.dumps(
                    {
                        "batch_index": 2,
                        "batch_id": "b002",
                        "paper_count": 2,
                        "paper_ids": ["6", "7"],
                        "run_id_base": "stage06_backfill_b002_n2_20260418",
                    }
                ),
                encoding="utf-8",
            )

            completed_run_dir = run_root / "stage06_backfill_b001_n5_20260418" / "results"
            completed_run_dir.mkdir(parents=True)
            for paper_id in ["3", "4", "5", "6", "7"]:
                (completed_run_dir / f"{paper_id}.json").write_text(
                    json.dumps(
                        {
                            "paper_id": paper_id,
                            "count_row": {"count_version": "hybrid_v2_gpt-5.4"},
                        }
                    ),
                    encoding="utf-8",
                )

            manifest_path = backfill.repair_campaign_outputs(
                campaign_id="stage06_backfill_20260418",
                batch_size=5,
                campaign_root=campaign_root,
                qa_output_dir=qa_output_dir,
                text_dir=text_dir,
                gold_manifest_path=gold_manifest_path,
                manual_review_path=manual_review_path,
                run_root=run_root,
            )

            repaired_b001 = backfill.load_json(manifest_path.parent / "batches" / "b001.json")

        self.assertEqual(repaired_b001["run_id_base"], "stage06_backfill_b001_n5_20260418")
        self.assertEqual(
            repaired_b001["combined_output_csv_path"],
            "qa/stage06_backfill_b001_n5_20260418_combined.csv",
        )
        self.assertEqual(
            repaired_b001["inspection_md_path"],
            "qa/stage06_backfill_b001_n5_20260418_inspection.md",
        )
        self.assertEqual(
            repaired_b001["review_comments_csv_path"],
            "qa/stage06_backfill_b001_n5_20260418_review_comments.csv",
        )
        self.assertEqual(
            repaired_b001["review_notes_md_path"],
            "qa/stage06_backfill_b001_n5_20260418_review_notes.md",
        )

    def test_repair_campaign_outputs_fails_for_partial_completed_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            text_dir = root / "text"
            run_root = root / "stage06_count_runs"
            campaign_root = root / "campaigns"
            qa_output_dir = root / "qa"
            gold_manifest_path = root / "gold_manifest.json"
            manual_review_path = root / "source_sps_case_count_manual_review.csv"
            campaign_path = campaign_root / "stage06_backfill_20260418"
            batch_dir = campaign_path / "batches"

            text_dir.mkdir()
            run_root.mkdir()
            for paper_id in [str(index) for index in range(1, 8)]:
                (text_dir / f"{paper_id}.json").write_text("{}", encoding="utf-8")

            gold_manifest_path.write_text(json.dumps({"entries": []}), encoding="utf-8")
            with manual_review_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["paper_id", "review_status"])
                writer.writeheader()

            batch_dir.mkdir(parents=True)
            (campaign_path / "manifest.json").write_text(
                json.dumps({"campaign_id": "stage06_backfill_20260418", "batch_size": 5}),
                encoding="utf-8",
            )
            batch_dir.joinpath("b001.json").write_text(
                json.dumps(
                    {
                        "batch_index": 1,
                        "batch_id": "b001",
                        "paper_count": 5,
                        "paper_ids": ["1", "2", "3", "4", "5"],
                        "run_id_base": "stage06_backfill_b001_n5_20260418",
                    }
                ),
                encoding="utf-8",
            )

            completed_run_dir = run_root / "stage06_backfill_b001_n5_20260418" / "results"
            completed_run_dir.mkdir(parents=True)
            for paper_id in ["3", "4", "5", "6"]:
                (completed_run_dir / f"{paper_id}.json").write_text(
                    json.dumps(
                        {
                            "paper_id": paper_id,
                            "count_row": {"count_version": "hybrid_v2_gpt-5.4"},
                        }
                    ),
                    encoding="utf-8",
                )

            with self.assertRaisesRegex(ValueError, "fully completed batch"):
                backfill.repair_campaign_outputs(
                    campaign_id="stage06_backfill_20260418",
                    batch_size=5,
                    campaign_root=campaign_root,
                    qa_output_dir=qa_output_dir,
                    text_dir=text_dir,
                    gold_manifest_path=gold_manifest_path,
                    manual_review_path=manual_review_path,
                    run_root=run_root,
                )

    def test_next_run_id_for_batch_uses_resume_suffixes(self) -> None:
        batch_manifest = {"run_id_base": "stage06_backfill_b001_n50_20260418"}
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            run_root = Path(tmp_dir_text)
            (run_root / "stage06_backfill_b001_n50_20260418").mkdir()
            (run_root / "stage06_backfill_b001_n50_20260418_resume01").mkdir()
            (run_root / "stage06_backfill_b001_n50_20260418_resume03").mkdir()

            next_run_id = backfill.next_run_id_for_batch(batch_manifest, run_root)

        self.assertEqual(next_run_id, "stage06_backfill_b001_n50_20260418_resume04")

    def test_completed_paper_ids_for_batch_ignores_invalid_result_payloads(self) -> None:
        batch_manifest = {
            "run_id_base": "stage06_backfill_b001_n3_20260419",
            "paper_ids": ["1", "2", "3"],
        }
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            run_root = Path(tmp_dir_text)
            run_dir = run_root / "stage06_backfill_b001_n3_20260419"
            results_dir = run_dir / "results"
            results_dir.mkdir(parents=True)
            (results_dir / "1.json").write_text(
                json.dumps({"paper_id": "1", "count_row": {"paper_id": "1"}}),
                encoding="utf-8",
            )
            (results_dir / "2.json").write_text("{", encoding="utf-8")
            (results_dir / "3.json").write_text(
                json.dumps({"paper_id": "999", "count_row": {"paper_id": "999"}}),
                encoding="utf-8",
            )

            completed_ids = backfill.completed_paper_ids_for_batch(batch_manifest, run_root)
            remaining_ids = backfill.remaining_paper_ids_for_batch(batch_manifest, run_root)
            count_rows = backfill.load_count_rows_from_run_dir(run_dir)

        self.assertEqual(completed_ids, {"1"})
        self.assertEqual(remaining_ids, ["2", "3"])
        self.assertEqual([row["paper_id"] for row in count_rows], ["1"])

    def test_build_hybrid_command_uses_subset_run_defaults(self) -> None:
        batch_manifest = {"qa_output_dir": "qa/validation/stage06_llm"}
        command = backfill.build_hybrid_command(
            batch_manifest=batch_manifest,
            paper_ids=["71", "214"],
            run_id="stage06_backfill_b001_n2_20260418",
            allow_paid_run=True,
        )
        self.assertIn("--allow-paid-run", command)
        self.assertIn("--allow-unresolved-export", command)
        self.assertIn("--skip-registry-refresh", command)
        self.assertEqual(command[-4:], ["--paper-id", "71", "--paper-id", "214"])

    def test_write_batch_qa_pack_generates_combined_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            qa_output_dir = root / "qa"
            run_root = root / "results"
            run_dir = run_root / "stage06_backfill_b001_n2_20260418"
            manual_review_path = root / "source_sps_case_count_manual_review.csv"
            qa_output_dir.mkdir(parents=True)
            (run_dir / "results").mkdir(parents=True)
            (run_dir / "count_decisions").mkdir()
            (run_dir / "count_evidence").mkdir()
            (run_dir / "local_model_results").mkdir()

            batch_manifest = {
                "batch_id": "b001",
                "run_id_base": run_dir.name,
                "combined_output_csv_path": "qa/stage06_backfill_b001_n2_20260418_combined.csv",
                "inspection_md_path": "qa/stage06_backfill_b001_n2_20260418_inspection.md",
                "review_comments_csv_path": "qa/stage06_backfill_b001_n2_20260418_review_comments.csv",
                "review_notes_md_path": "qa/stage06_backfill_b001_n2_20260418_review_notes.md",
                "paper_ids": ["71", "214"],
            }

            with (qa_output_dir / f"{run_dir.name}.csv").open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=backfill.count_row_fieldnames())
                writer.writeheader()
                writer.writerow(
                    {
                        "paper_id": "71",
                        "title": "Paper 71",
                        "likely_sps_case_count": "3",
                        "count_basis": "abstract_count_signal",
                        "count_manual_review_required": "false",
                        "count_verification_status": "llm_candidate_exact",
                        "count_reason": "reason one",
                        "count_candidate_json_path": r"results\stage06_count_runs\stage06_backfill_b001_n2_20260418\candidate_packages\71.json",
                        "count_evidence_json_path": r"results\stage06_count_runs\stage06_backfill_b001_n2_20260418\count_evidence\71.json",
                        "count_original_cohort_provenance_uncertain": "false",
                    }
                )
                writer.writerow(
                    {
                        "paper_id": "214",
                        "title": "Paper 214",
                        "likely_sps_case_count": "1",
                        "count_basis": "source_single_case_default",
                        "count_manual_review_required": "true",
                        "count_verification_status": "llm_manual_review_required",
                        "count_reason": "reason two",
                        "count_candidate_json_path": r"results\stage06_count_runs\stage06_backfill_b001_n2_20260418\candidate_packages\214.json",
                        "count_evidence_json_path": r"results\stage06_count_runs\stage06_backfill_b001_n2_20260418\count_evidence\214.json",
                        "count_original_cohort_provenance_uncertain": "true",
                    }
                )

            for paper_id, count_value, reasoning, verification_status, manual_review_required in [
                ("71", "3", "Exact cohort.", "llm_candidate_exact", False),
                ("214", "1", "Single case.", "llm_manual_review_required", True),
            ]:
                (run_dir / "results" / f"{paper_id}.json").write_text(
                    json.dumps(
                        {
                            "paper_id": paper_id,
                            "count_row": {
                                "paper_id": paper_id,
                                "title": f"Paper {paper_id}",
                                "likely_sps_case_count": count_value,
                                "count_basis": "source_single_case_default",
                                "count_verification_status": verification_status,
                                "count_manual_review_required": str(manual_review_required).lower(),
                                "count_reason": reasoning,
                                "count_candidate_json_path": rf"results\stage06_count_runs\{run_dir.name}\candidate_packages\{paper_id}.json",
                                "count_evidence_json_path": rf"results\stage06_count_runs\{run_dir.name}\count_evidence\{paper_id}.json",
                            },
                            "source_text_json_path": rf"data\extraction_json\text\{paper_id}.json",
                            "preferred_text_json_path": rf"data\extraction_json\text\{paper_id}.json",
                        }
                    ),
                    encoding="utf-8",
                )
                (run_dir / "count_decisions" / f"{paper_id}.json").write_text(
                    json.dumps(
                        {
                            "decision": {
                                "decision_type": "candidate_exact",
                                "selected_candidate_id": "cand01",
                                "alternative_count": None,
                                "count_confidence": "high",
                                "count_manual_review_required": manual_review_required,
                                "count_reasoning_summary": reasoning,
                                "evidence": [{"quote": f"Quote for {paper_id}", "page": None}],
                            }
                        }
                    ),
                    encoding="utf-8",
                )
                (run_dir / "count_evidence" / f"{paper_id}.json").write_text(
                    json.dumps(
                        {
                            "paper_id": paper_id,
                            "evidence": [{"quote": f"Quote for {paper_id}", "page": None}],
                            "local_result_json_path": rf"results\stage06_count_runs\{run_dir.name}\local_model_results\{paper_id}.json",
                        }
                    ),
                    encoding="utf-8",
                )
                (run_dir / "local_model_results" / f"{paper_id}.json").write_text(
                    json.dumps(
                        {
                            "parsed_output": {
                                "n_spsd_patients": int(count_value),
                                "confidence": "medium",
                                "needs_review": paper_id == "214",
                                "reasoning_short": f"Local reasoning for {paper_id}",
                            }
                        }
                    ),
                    encoding="utf-8",
                )

            original_run_root = backfill.RUN_ROOT
            original_qa_output_dir = backfill.QA_OUTPUT_DIR
            original_artifact_registry_path = review.ARTIFACT_REGISTRY_PATH
            artifact_registry_path = root / "paper_artifact_registry.csv"
            with artifact_registry_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=["paper_id", "pdf_paths_relative", "text_json_path"])
                writer.writeheader()
                writer.writerow({"paper_id": "71", "pdf_paths_relative": r"data\pdf_original\71.pdf", "text_json_path": r"data\extraction_json\text\71.json"})
                writer.writerow({"paper_id": "214", "pdf_paths_relative": r"data\pdf_original\214.pdf", "text_json_path": r"data\extraction_json\text\214.json"})
            with manual_review_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=overrides.OVERRIDE_FIELDNAMES)
                writer.writeheader()
                writer.writerow(
                    {
                        "source_scope_id": "stage06_backfill_b001_n2_20260418",
                        "source_scope_label": "stage06_backfill_b001_n2_20260418",
                        "paper_id": "214",
                        "title": "Paper 214",
                        "predicted_count": "1",
                        "predicted_original_cohort_provenance_uncertain": "true",
                        "predicted_verification_status": "llm_manual_review_required",
                        "prediction_correct": "false",
                        "reviewed_count": "4",
                        "reviewed_original_cohort_provenance_uncertain": "false",
                        "review_status": "reviewed",
                        "reviewer_notes": "Table 1 supports four SPS patients.",
                        "reviewer_id": "tester",
                        "reviewed_at_utc": "2026-04-18T10:00:00Z",
                        "updated_at_utc": "2026-04-18T10:00:00Z",
                    }
                )
            try:
                backfill.RUN_ROOT = run_root
                backfill.QA_OUTPUT_DIR = qa_output_dir
                review.RUN_ROOT = run_root
                review.ARTIFACT_REGISTRY_PATH = artifact_registry_path
                pack_paths = backfill.write_batch_qa_pack(
                    batch_manifest=batch_manifest,
                    run_root=run_root,
                    qa_output_dir=qa_output_dir,
                    manual_review_path=manual_review_path,
                )
            finally:
                backfill.RUN_ROOT = original_run_root
                backfill.QA_OUTPUT_DIR = original_qa_output_dir
                review.RUN_ROOT = original_run_root
                review.ARTIFACT_REGISTRY_PATH = original_artifact_registry_path

            combined_rows = backfill.load_csv_rows(review.resolve_repo_path(pack_paths["combined_output_csv_path"]))
            comments_rows = backfill.load_csv_rows(review.resolve_repo_path(pack_paths["review_comments_csv_path"]))
            inspection_text = review.resolve_repo_path(pack_paths["inspection_md_path"]).read_text(encoding="utf-8")
            notes_text = review.resolve_repo_path(pack_paths["review_notes_md_path"]).read_text(encoding="utf-8")

        self.assertEqual(len(comments_rows), 2)
        combined_rows_by_id = {row["paper_id"]: row for row in combined_rows}
        self.assertEqual(combined_rows_by_id["214"]["likely_sps_case_count"], "4")
        self.assertEqual(combined_rows_by_id["214"]["count_verification_status"], "manual_review_override")
        self.assertEqual(comments_rows[0]["paper_id"], "71")
        self.assertIn("## 71 - Paper 71", inspection_text)
        self.assertIn("batch_artifacts_status: complete", inspection_text)
        self.assertIn("Quote for 71", inspection_text)
        self.assertIn("Must review: None", notes_text)
        self.assertIn("Should review: None", notes_text)
        self.assertIn("Resolved Manual Overrides", notes_text)
        self.assertIn("`214 -> 4`", notes_text)
        self.assertIn("Table 1 supports four SPS patients.", notes_text)
        self.assertIn("None remaining in the highest-risk tier after applying reviewed overrides.", notes_text)
        self.assertIn("None remaining in the secondary-review tier.", notes_text)

    def test_write_campaign_high_risk_review_rollup_filters_to_high_risk_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            campaign_root = root / "campaigns"
            run_root = root / "results"
            manual_review_path = root / "source_sps_case_count_manual_review.csv"
            campaign_path = campaign_root / "stage06_backfill_demo"
            batch_manifest_path = campaign_path / "batches" / "b001.json"
            run_dir = run_root / "stage06_backfill_b001_n2_20260419"

            (run_dir / "results").mkdir(parents=True)
            (run_dir / "candidate_packages").mkdir()
            (run_dir / "count_decisions").mkdir()
            with manual_review_path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=overrides.OVERRIDE_FIELDNAMES)
                writer.writeheader()

            backfill.write_json(
                campaign_path / "manifest.json",
                {
                    "campaign_id": "stage06_backfill_demo",
                    "campaign_root": "campaigns/stage06_backfill_demo",
                    "coverage": {"summary_counts": {"remaining": 1}},
                    "batches": [
                        {
                            "batch_id": "b001",
                            "batch_manifest_path": backfill.display_path(batch_manifest_path),
                        }
                    ],
                },
            )
            backfill.write_json(
                batch_manifest_path,
                {
                    "campaign_id": "stage06_backfill_demo",
                    "batch_id": "b001",
                    "run_id_base": run_dir.name,
                    "paper_ids": ["71", "214"],
                },
            )
            for paper_id, verification_status, manual_review_required, count_reason in [
                ("71", "llm_candidate_exact", "false", "verification_status=llm_candidate_exact"),
                (
                    "214",
                    "llm_manual_review_required",
                    "true",
                    "verification_status=llm_manual_review_required | explicit_sps_subgroup_conflict=4 vs 1",
                ),
            ]:
                (run_dir / "results" / f"{paper_id}.json").write_text(
                    json.dumps(
                        {
                            "paper_id": paper_id,
                            "count_row": {
                                "paper_id": paper_id,
                                "title": f"Paper {paper_id}",
                                "likely_sps_case_count": "1" if paper_id == "214" else "3",
                                "count_verification_status": verification_status,
                                "count_manual_review_required": manual_review_required,
                                "count_reason": count_reason,
                                "count_candidate_json_path": backfill.display_path(
                                    run_dir / "candidate_packages" / f"{paper_id}.json"
                                ),
                                "count_decision_json_path": backfill.display_path(
                                    run_dir / "count_decisions" / f"{paper_id}.json"
                                ),
                            },
                            "source_text_json_path": rf"data\extraction_json\text\{paper_id}.json",
                            "preferred_text_json_path": rf"data\extraction_json\text\{paper_id}.json",
                        }
                    ),
                    encoding="utf-8",
                )
            (run_dir / "candidate_packages" / "71.json").write_text(
                json.dumps({"candidates": [{"proposed_count": 3, "count_basis": "single_case_report"}]}),
                encoding="utf-8",
            )
            (run_dir / "candidate_packages" / "214.json").write_text(
                json.dumps(
                    {
                        "candidates": [
                            {"proposed_count": 1, "count_basis": "source_single_case_default"},
                            {"proposed_count": 4, "count_basis": "table_count_signal"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            (run_dir / "count_decisions" / "214.json").write_text(
                json.dumps({"decision": {"decision_type": "candidate_exact", "count_confidence": "medium"}}),
                encoding="utf-8",
            )

            rollup_path = backfill.write_campaign_high_risk_review_rollup(
                campaign_id="stage06_backfill_demo",
                campaign_root=campaign_root,
                run_root=run_root,
                manual_review_path=manual_review_path,
            )
            rollup_text = rollup_path.read_text(encoding="utf-8")

        self.assertIn("## Must Review", rollup_text)
        self.assertIn("`214` (b001)", rollup_text)
        self.assertNotIn("`71` (b001)", rollup_text)


if __name__ == "__main__":
    unittest.main()
