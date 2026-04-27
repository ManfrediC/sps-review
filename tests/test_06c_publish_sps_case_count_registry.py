from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

from src.pipelines._sps_case_count_registry import count_row_fieldnames


REPO_ROOT = Path(__file__).resolve().parents[1]
PUBLISH_SCRIPT = REPO_ROOT / "src" / "pipelines" / "06c_publish_sps_case_count_registry.py"


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


class TestStage06PublishSpsCaseCountRegistry(unittest.TestCase):
    def test_publish_rows_applies_precedence_and_flags_reference_fallbacks(self) -> None:
        mod = _load_module("stage06_publish_registry", PUBLISH_SCRIPT)
        with tempfile.TemporaryDirectory() as tmp_dir_text:
            root = Path(tmp_dir_text)
            count_fields = count_row_fieldnames()
            input_registry_path = root / "source_sps_case_count_registry.csv"
            source_registry_path = root / "source_categorisation_registry.csv"
            references_csv = root / "sps_references_export.csv"
            manual_review_path = root / "source_sps_case_count_manual_review.csv"
            source_manual_review_path = root / "source_categorisation_manual_review.csv"
            hybrid_path = root / "stage06_backfill_combined.csv"
            gold_root = root / "stage06_count_gold"
            gold_papers_dir = gold_root / "papers"
            gold_manifest_path = gold_root / "manifest.json"

            def row(paper_id: str, count: str, *, category: str = "single_case_report") -> dict[str, str]:
                return {
                    **{fieldname: "" for fieldname in count_fields},
                    "paper_id": paper_id,
                    "covidence_id": paper_id,
                    "title": f"Paper {paper_id}",
                    "authors": "Example",
                    "source_category": category,
                    "source_subtype": "case_report",
                    "preferred_text_json_path": f"data/extraction_json/text/{paper_id}.json",
                    "preferred_text_source": "full_text",
                    "count_eligible": "true",
                    "likely_sps_case_count": count,
                    "count_confidence": "low",
                    "count_basis": "old",
                    "count_manual_review_required": "false",
                    "count_version": "old_v1",
                }

            _write_csv(
                input_registry_path,
                count_fields,
                [
                    row("1", "2"),
                    row("2", ""),
                    row("3", "4"),
                    row("4", "9", category="conference_abstract"),
                ],
            )
            _write_csv(
                source_registry_path,
                [
                    "paper_id",
                    "source_category",
                    "source_subtype",
                    "preferred_text_json_path",
                    "text_json_path",
                    "title",
                    "authors",
                ],
                [
                    {
                        "paper_id": "1",
                        "source_category": "single_case_report",
                        "source_subtype": "case_report",
                        "preferred_text_json_path": "data/extraction_json/text/1.json",
                        "text_json_path": "data/extraction_json/text/1.json",
                        "title": "Paper 1",
                        "authors": "Example",
                    },
                    {
                        "paper_id": "2",
                        "source_category": "single_case_report",
                        "source_subtype": "case_report",
                        "preferred_text_json_path": "data/extraction_json/text/2.json",
                        "text_json_path": "data/extraction_json/text/2.json",
                        "title": "Paper 2",
                        "authors": "Example",
                    },
                    {
                        "paper_id": "3",
                        "source_category": "single_case_report",
                        "source_subtype": "case_report",
                        "preferred_text_json_path": "data/extraction_json/text/3.json",
                        "text_json_path": "data/extraction_json/text/3.json",
                        "title": "Paper 3",
                        "authors": "Example",
                    },
                    {
                        "paper_id": "4",
                        "source_category": "conference_abstract",
                        "source_subtype": "group_conference_abstract",
                        "preferred_text_json_path": "data/extraction_json/text/4.json",
                        "text_json_path": "data/extraction_json/text/4.json",
                        "title": "Paper 4",
                        "authors": "Example",
                    },
                ],
            )
            _write_csv(
                references_csv,
                ["Covidence", "Title", "Authors", "Abstract"],
                [
                    {
                        "Covidence": "1",
                        "Title": "Paper 1",
                        "Authors": "Example",
                        "Abstract": "We report one patient with stiff-person syndrome.",
                    },
                    {
                        "Covidence": "2",
                        "Title": "Paper 2",
                        "Authors": "Example",
                        "Abstract": "We report a patient with stiff-person syndrome.",
                    },
                    {
                        "Covidence": "3",
                        "Title": "Paper 3",
                        "Authors": "Example",
                        "Abstract": "We report seven patients with stiff-person syndrome.",
                    },
                    {
                        "Covidence": "4",
                        "Title": "Paper 4",
                        "Authors": "Example",
                        "Abstract": "Bad source linkage.",
                    },
                ],
            )
            _write_csv(
                hybrid_path,
                count_fields,
                [
                    {
                        **row("1", "5"),
                        "count_confidence": "high",
                        "count_basis": "llm_candidate_exact",
                        "count_version": "hybrid_v2_gpt-5.4",
                        "count_audit_status": "hybrid_local_gpt",
                        "count_verification_status": "llm_candidate_exact",
                        "counted_at_utc": "2026-04-20T00:00:00+00:00",
                    }
                ],
            )
            _write_csv(
                manual_review_path,
                [
                    "source_scope_id",
                    "source_scope_label",
                    "paper_id",
                    "title",
                    "predicted_count",
                    "predicted_original_cohort_provenance_uncertain",
                    "predicted_verification_status",
                    "prediction_correct",
                    "reviewed_count",
                    "reviewed_original_cohort_provenance_uncertain",
                    "review_status",
                    "reviewer_notes",
                    "reviewer_id",
                    "reviewed_at_utc",
                    "updated_at_utc",
                ],
                [
                    {
                        "source_scope_id": "scope",
                        "source_scope_label": "scope",
                        "paper_id": "1",
                        "title": "Paper 1",
                        "predicted_count": "5",
                        "predicted_original_cohort_provenance_uncertain": "false",
                        "predicted_verification_status": "llm_candidate_exact",
                        "prediction_correct": "false",
                        "reviewed_count": "6",
                        "reviewed_original_cohort_provenance_uncertain": "false",
                        "review_status": "reviewed",
                        "reviewer_notes": "",
                        "reviewer_id": "tester",
                        "reviewed_at_utc": "2026-04-20T01:00:00+00:00",
                        "updated_at_utc": "2026-04-20T01:00:00+00:00",
                    }
                ],
            )
            _write_csv(
                source_manual_review_path,
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
                        "paper_id": "4",
                        "title": "Paper 4",
                        "final_source_category": "unclear_manual_review",
                        "final_source_subtype": "incorrect_reference",
                        "review_decision_notes": "Wrong abstract attached.",
                        "reviewed_at_utc": "2026-04-20T02:00:00+00:00",
                        "pdf_content_alignment_tag": "incorrect_reference",
                    }
                ],
            )
            gold_papers_dir.mkdir(parents=True)
            (gold_papers_dir / "3.json").write_text(
                json.dumps(
                    {
                        "count_row": {
                            **row("3", "7"),
                            "count_basis": "manual_gold_review",
                            "count_confidence": "high",
                            "count_manual_review_required": "false",
                            "count_version": "gold_reviewed_stage06_v1",
                        }
                    }
                ),
                encoding="utf-8",
            )
            gold_manifest_path.write_text(
                json.dumps(
                    {
                        "entries": [
                            {
                                "paper_id": "3",
                                "gold_status": "active",
                                "gold_json_path": "",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            rows, report = mod.publish_rows(
                input_registry_path=input_registry_path,
                references_csv=references_csv,
                source_registry_path=source_registry_path,
                source_manual_review_path=source_manual_review_path,
                manual_review_path=manual_review_path,
                gold_manifest_path=gold_manifest_path,
                gold_papers_dir=gold_papers_dir,
                hybrid_output_globs=[str(hybrid_path)],
            )

        rows_by_id = {row["paper_id"]: row for row in rows}
        self.assertEqual(rows_by_id["1"]["likely_sps_case_count"], "6")
        self.assertEqual(rows_by_id["1"]["count_verification_status"], "manual_review_override")
        self.assertEqual(rows_by_id["2"]["likely_sps_case_count"], "1")
        self.assertEqual(rows_by_id["2"]["count_manual_review_required"], "true")
        self.assertEqual(rows_by_id["2"]["count_verification_status"], "reference_heuristic_manual_review_required")
        self.assertEqual(rows_by_id["3"]["likely_sps_case_count"], "7")
        self.assertEqual(rows_by_id["3"]["count_verification_status"], "manual_gold_review")
        self.assertEqual(rows_by_id["4"]["likely_sps_case_count"], "0")
        self.assertEqual(rows_by_id["4"]["count_verification_status"], "excluded_bad_source_alignment")
        self.assertEqual(report["validation"]["blank_count_paper_ids"], [])
        self.assertEqual(report["validation"]["silent_wrong_gold_paper_ids"], [])


if __name__ == "__main__":
    unittest.main()
