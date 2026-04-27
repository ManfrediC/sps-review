from __future__ import annotations

import importlib.util
import argparse
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
CASE_COUNT_HYBRID_SCRIPT = REPO_ROOT / "src" / "pipelines" / "06_extract_sps_case_counts_hybrid.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TestStage06ExtractSpsCaseCountsHybrid(unittest.TestCase):
    def test_cleanup_failed_attempt_preserves_failed_run_and_removes_new_output(self) -> None:
        mod = _load_module("stage06_count_hybrid_cleanup", CASE_COUNT_HYBRID_SCRIPT)
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            run_dir = root / "stage06_demo"
            output_path = root / "qa_output.csv"
            run_dir.mkdir()
            output_path.write_text("paper_id\n71\n", encoding="utf-8")

            mod._cleanup_failed_attempt(
                run_dir=run_dir,
                run_dir_created=True,
                output_path=output_path,
                output_preexisting=False,
                total_paper_count=2,
                error=RuntimeError("boom"),
            )
            manifest = mod._load_json_if_valid(run_dir / "run_manifest.json")
            self.assertTrue(run_dir.exists())
            self.assertFalse(output_path.exists())
            self.assertEqual(manifest["run_status"], "failed")
            self.assertEqual(manifest["completed_result_count"], 0)
            self.assertEqual(manifest["failure_type"], "RuntimeError")

    def test_cleanup_failed_attempt_preserves_preexisting_output(self) -> None:
        mod = _load_module("stage06_count_hybrid_cleanup_existing", CASE_COUNT_HYBRID_SCRIPT)
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            run_dir = root / "stage06_demo"
            output_path = root / "source_sps_case_count_registry.csv"
            run_dir.mkdir()
            output_path.write_text("paper_id\n71\n", encoding="utf-8")

            mod._cleanup_failed_attempt(
                run_dir=run_dir,
                run_dir_created=True,
                output_path=output_path,
                output_preexisting=True,
                total_paper_count=1,
                error=KeyboardInterrupt(),
            )

            manifest = mod._load_json_if_valid(run_dir / "run_manifest.json")
            self.assertTrue(run_dir.exists())
            self.assertTrue(output_path.exists())
            self.assertEqual(manifest["run_status"], "interrupted")

    def test_cleanup_failed_attempt_records_completed_partial_results(self) -> None:
        mod = _load_module("stage06_count_hybrid_cleanup_partial", CASE_COUNT_HYBRID_SCRIPT)
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            run_dir = root / "stage06_demo"
            results_dir = run_dir / "results"
            output_path = root / "qa_output.csv"
            results_dir.mkdir(parents=True)
            (results_dir / "71.json").write_text(
                '{"paper_id": "71", "count_row": {"paper_id": "71"}}',
                encoding="utf-8",
            )

            mod._cleanup_failed_attempt(
                run_dir=run_dir,
                run_dir_created=True,
                output_path=output_path,
                output_preexisting=False,
                total_paper_count=3,
                error=RuntimeError("network lost"),
            )

            manifest = mod._load_json_if_valid(run_dir / "run_manifest.json")
            self.assertEqual(manifest["completed_result_count"], 1)
            self.assertEqual(manifest["completed_paper_ids"], ["71"])
            self.assertEqual(manifest["total_paper_count"], 3)

    def test_apply_review_override_if_present_uses_tracked_override(self) -> None:
        mod = _load_module("stage06_count_hybrid_override", CASE_COUNT_HYBRID_SCRIPT)
        row = mod._apply_review_override_if_present(
            {
                "paper_id": "214",
                "likely_sps_case_count": "2",
                "count_confidence": "medium",
                "count_basis": "llm_bounded_alternative",
                "count_manual_review_required": "true",
                "count_reason": "verification_status=llm_manual_review_required",
                "count_version": "hybrid_v2_gpt-5.4",
                "count_audit_status": "hybrid_local_gpt",
                "count_verification_status": "llm_manual_review_required",
                "counted_at_utc": "2026-04-16T10:00:00+00:00",
            },
            override_rows={
                "214": {
                    "source_scope_id": "all_runs",
                    "source_scope_label": "all_runs",
                    "paper_id": "214",
                    "title": "Paper 214",
                    "predicted_count": "2",
                    "predicted_verification_status": "llm_manual_review_required",
                    "prediction_correct": "false",
                    "reviewed_count": "3",
                    "review_status": "reviewed",
                    "reviewer_notes": "Three original cases.",
                    "reviewer_id": "tester",
                    "reviewed_at_utc": "2026-04-16T10:05:00+00:00",
                    "updated_at_utc": "2026-04-16T10:06:00+00:00",
                }
            },
        )
        self.assertEqual(row["likely_sps_case_count"], "3")
        self.assertEqual(row["count_verification_status"], "manual_review_override")
        self.assertEqual(row["count_manual_review_required"], "false")

    def test_unresolved_paper_ids_ignore_manual_review_override(self) -> None:
        mod = _load_module("stage06_count_hybrid_unresolved", CASE_COUNT_HYBRID_SCRIPT)
        unresolved_ids = mod._unresolved_paper_ids(
            [
                {
                    "paper_id": "214",
                    "count_manual_review_required": "false",
                    "count_verification_status": "manual_review_override",
                },
                {
                    "paper_id": "525",
                    "count_manual_review_required": "true",
                    "count_verification_status": "llm_semantic_conflict_manual_review_required",
                },
            ]
        )
        self.assertEqual(unresolved_ids, ["525"])

    def test_validate_output_scope_refuses_partial_canonical_export(self) -> None:
        mod = _load_module("stage06_count_hybrid_output_scope", CASE_COUNT_HYBRID_SCRIPT)
        args = argparse.Namespace(
            paper_id=["71"],
            limit=0,
            output_path=mod.OUTPUT_PATH,
            allow_partial_canonical_export=False,
        )
        with self.assertRaises(SystemExit):
            mod._validate_output_scope(args)

    def test_validate_output_scope_allows_partial_qa_export(self) -> None:
        mod = _load_module("stage06_count_hybrid_output_scope_qa", CASE_COUNT_HYBRID_SCRIPT)
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            args = argparse.Namespace(
                paper_id=["71"],
                limit=0,
                output_path=Path(tmp_dir_text) / "stage06_subset.csv",
                allow_partial_canonical_export=False,
            )
            mod._validate_output_scope(args)


if __name__ == "__main__":
    unittest.main()
