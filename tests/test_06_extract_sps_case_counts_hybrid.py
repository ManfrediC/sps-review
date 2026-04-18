from __future__ import annotations

import importlib.util
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
    def test_cleanup_failed_attempt_removes_new_outputs_only(self) -> None:
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
            )
            self.assertFalse(run_dir.exists())
            self.assertFalse(output_path.exists())

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
            )

            self.assertFalse(run_dir.exists())
            self.assertTrue(output_path.exists())

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


if __name__ == "__main__":
    unittest.main()
