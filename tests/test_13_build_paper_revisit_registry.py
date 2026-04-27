from __future__ import annotations

import csv
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REVISIT_SCRIPT = REPO_ROOT / "src" / "pipelines" / "13_build_paper_revisit_registry.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class TestBuildPaperRevisitRegistry(unittest.TestCase):
    def test_build_revisit_rows_collects_cross_stage_issues(self) -> None:
        mod = _load_module("paper_revisit_registry", REVISIT_SCRIPT)
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            artifact = root / "paper_artifact_registry.csv"
            pdf_queue = root / "pdf_acquisition_queue.csv"
            proceedings_queue = root / "proceedings_manual_review_queue.csv"
            text_trim = root / "text_trim_registry.csv"
            text_trim_llm = root / "text_trim_llm_registry.csv"
            qc = root / "proceedings_text_qc_registry.csv"
            source_manual = root / "source_categorisation_manual_review.csv"
            count_registry = root / "source_sps_case_count_registry.csv"
            split_registry = root / "case_series_split_registry.csv"

            _write_csv(
                artifact,
                [
                    "paper_id",
                    "covidence_id",
                    "title",
                    "authors",
                    "published_year",
                    "journal",
                    "source_manual_review_required",
                    "source_recommended_next_action",
                    "source_categorisation_reason",
                    "source_categorised_at_utc",
                ],
                [
                    {
                        "paper_id": "52",
                        "covidence_id": "52",
                        "title": "PDF failure",
                        "authors": "A",
                        "published_year": "1994",
                        "journal": "Neurology",
                        "source_manual_review_required": "false",
                        "source_recommended_next_action": "",
                        "source_categorisation_reason": "",
                        "source_categorised_at_utc": "",
                    },
                    {
                        "paper_id": "8182",
                        "covidence_id": "8182",
                        "title": "Wrong source",
                        "authors": "B",
                        "published_year": "2012",
                        "journal": "Journal",
                        "source_manual_review_required": "true",
                        "source_recommended_next_action": "review_source_category",
                        "source_categorisation_reason": "Needs source review.",
                        "source_categorised_at_utc": "2026-04-05T00:00:00Z",
                    },
                ],
            )
            _write_csv(
                pdf_queue,
                ["covidence_id", "title", "authors", "download_status", "manifest_status", "manifest_error", "queue_reason"],
                [
                    {
                        "covidence_id": "52",
                        "title": "PDF failure",
                        "authors": "A",
                        "download_status": "failed",
                        "manifest_status": "failed",
                        "manifest_error": "Timed out.",
                        "queue_reason": "Retry needed.",
                    }
                ],
            )
            _write_csv(
                source_manual,
                [
                    "paper_id",
                    "title",
                    "final_source_category",
                    "final_source_subtype",
                    "review_decision_notes",
                    "reviewed_at_utc",
                    "pdf_content_alignment_tag",
                ],
                [
                    {
                        "paper_id": "8182",
                        "title": "Wrong source",
                        "final_source_category": "unclear_manual_review",
                        "final_source_subtype": "incorrect_reference",
                        "review_decision_notes": "Wrong abstract.",
                        "reviewed_at_utc": "2026-04-20T00:00:00Z",
                        "pdf_content_alignment_tag": "incorrect_reference",
                    }
                ],
            )
            _write_csv(
                count_registry,
                [
                    "paper_id",
                    "covidence_id",
                    "title",
                    "authors",
                    "count_manual_review_required",
                    "count_verification_status",
                    "count_basis",
                    "count_reason",
                    "counted_at_utc",
                ],
                [
                    {
                        "paper_id": "8182",
                        "covidence_id": "8182",
                        "title": "Wrong source",
                        "authors": "B",
                        "count_manual_review_required": "true",
                        "count_verification_status": "excluded_bad_source_alignment",
                        "count_basis": "source_linkage_exclusion",
                        "count_reason": "source_linkage_blocked=true",
                        "counted_at_utc": "2026-04-26T00:00:00Z",
                    }
                ],
            )
            for path, fieldnames in (
                (proceedings_queue, ["paper_id", "manual_status", "trim_reason"]),
                (text_trim, ["paper_id", "trim_status", "trim_reason"]),
                (text_trim_llm, ["paper_id", "trim_status", "llm_validation_reason", "trim_reason"]),
                (qc, ["paper_id", "qc_status", "manual_follow_up_required", "qc_note", "trim_reason", "checked_at_utc"]),
                (split_registry, ["paper_id", "split_status", "manual_review_required", "split_reason", "split_at_utc"]),
            ):
                _write_csv(path, fieldnames, [])

            rows = mod.build_revisit_rows(
                artifact_registry_path=artifact,
                pdf_acquisition_queue_path=pdf_queue,
                proceedings_manual_review_queue_path=proceedings_queue,
                text_trim_registry_path=text_trim,
                text_trim_llm_registry_path=text_trim_llm,
                proceedings_qc_registry_path=qc,
                source_manual_review_path=source_manual,
                source_count_registry_path=count_registry,
                case_series_split_registry_path=split_registry,
            )

        issue_ids = {row["issue_id"] for row in rows}
        self.assertIn("52|01_pdf_acquisition|pdf_acquisition_failed|pdf_acquisition_queue.csv", issue_ids)
        self.assertIn("8182|02_source_linkage|source_alignment_failed|source_categorisation_manual_review.csv", issue_ids)
        self.assertIn("8182|04_source_categorisation|source_category_manual_review_required|paper_artifact_registry.csv", issue_ids)
        self.assertIn("8182|06_sps_case_count|source_linkage_exclusion|source_sps_case_count_registry.csv", issue_ids)
        linkage_row = next(row for row in rows if row["issue_type"] == "source_alignment_failed")
        self.assertEqual(linkage_row["severity"], "blocker")
        self.assertEqual(linkage_row["blocking_downstream"], "true")


if __name__ == "__main__":
    unittest.main()
