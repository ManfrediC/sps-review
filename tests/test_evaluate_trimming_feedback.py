from __future__ import annotations

import csv
import json
from pathlib import Path

from src.validation.evaluate_trimming_feedback import evaluate_feedback_files


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_evaluate_feedback_routes_out_non_proceedings_case(tmp_path: Path) -> None:
    source_registry = tmp_path / "source_categorisation_registry.csv"
    manual_review = tmp_path / "source_categorisation_manual_review.csv"
    feedback_path = tmp_path / "batch_001_feedback.json"
    reports_dir = tmp_path / "reports"

    write_csv(
        source_registry,
        [
            {
                "paper_id": "969",
                "source_category": "observational_group_study",
                "source_subtype": "",
                "classification_confidence": "high",
                "categorisation_reason": "Reviewed article.",
            }
        ],
    )
    write_csv(manual_review, [])
    feedback_path.write_text(
        json.dumps(
            {
                "feedback_round_id": "batch_001_feedback",
                "batch_id": "batch_001",
                "cases": [
                    {
                        "paper_id": "969",
                        "expected_verdict": "should_manual_review",
                        "expected_manual_review": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = evaluate_feedback_files(
        feedback_paths=[feedback_path],
        reports_dir=reports_dir,
        source_registry_path=source_registry,
        source_manual_review_path=manual_review,
    )

    assert report["passed_count"] == 1
    result = report["results"][0]
    assert result["workflow_stage"] == "routing_gate"
    assert result["checks"][0]["name"] == "resolved_source_category_not_conference_abstract"


def test_evaluate_feedback_accepts_not_needed_manual_review_case(tmp_path: Path) -> None:
    source_registry = tmp_path / "source_categorisation_registry.csv"
    manual_review = tmp_path / "source_categorisation_manual_review.csv"
    feedback_path = tmp_path / "batch_003_feedback.json"
    reports_dir = tmp_path / "reports"
    batch_dir = reports_dir / "batch_003"

    write_csv(
        source_registry,
        [
            {
                "paper_id": "1249",
                "source_category": "conference_abstract",
                "source_subtype": "multi_case_conference_abstract",
                "classification_confidence": "high",
                "categorisation_reason": "Conference abstract page.",
            }
        ],
    )
    write_csv(manual_review, [])
    write_csv(batch_dir / "text_trim_registry.csv", [{"paper_id": "1249", "trim_status": "not_needed"}])
    write_csv(
        batch_dir / "proceedings_text_qc_registry.csv",
        [{"paper_id": "1249", "qc_status": "untrimmed_localised", "manual_follow_up_required": "true"}],
    )
    feedback_path.write_text(
        json.dumps(
            {
                "feedback_round_id": "batch_003_feedback",
                "batch_id": "batch_003",
                "cases": [
                    {
                        "paper_id": "1249",
                        "expected_verdict": "should_manual_review",
                        "expected_manual_review": True,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = evaluate_feedback_files(
        feedback_paths=[feedback_path],
        reports_dir=reports_dir,
        source_registry_path=source_registry,
        source_manual_review_path=manual_review,
    )

    assert report["passed_count"] == 1
    result = report["results"][0]
    assert result["workflow_stage"] == "stage05_not_needed"
    assert result["checks"][0]["name"] == "trim_status_matches_not_needed"


def test_evaluate_feedback_checks_trimmed_text_expectations(tmp_path: Path) -> None:
    source_registry = tmp_path / "source_categorisation_registry.csv"
    manual_review = tmp_path / "source_categorisation_manual_review.csv"
    feedback_path = tmp_path / "batch_003_feedback.json"
    reports_dir = tmp_path / "reports"
    batch_dir = reports_dir / "batch_003"
    trimmed_dir = batch_dir / "text_trimmed"
    trimmed_dir.mkdir(parents=True)
    trimmed_path = trimmed_dir / "1245.json"

    write_csv(
        source_registry,
        [
            {
                "paper_id": "1245",
                "source_category": "conference_abstract",
                "source_subtype": "single_case_conference_abstract",
                "classification_confidence": "high",
                "categorisation_reason": "Proceedings abstract.",
            }
        ],
    )
    write_csv(manual_review, [])
    trimmed_path.write_text(
        json.dumps(
            {
                "pages": [
                    {
                        "page_index": 0,
                        "text": "\n".join(
                            [
                                "Poster 237",
                                "Bilateral Hip Fracture During Hospitalization for",
                                "Spasm Exacerbation in an Adult with Stiff Person Syndrome: A Case Report",
                                "Results: Participation in therapies was limited.",
                                "Conclusions: Refractory spasms may contribute to significant forces exerted on bony elements leading to fractures.",
                            ]
                        ),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    write_csv(
        batch_dir / "text_trim_registry.csv",
        [
            {
                "paper_id": "1245",
                "trim_status": "trimmed_auto",
                "trimmed_text_json_path": "",
            }
        ],
    )
    write_csv(
        batch_dir / "proceedings_text_qc_registry.csv",
        [{"paper_id": "1245", "qc_status": "confirmed_full", "manual_follow_up_required": "false"}],
    )
    feedback_path.write_text(
        json.dumps(
            {
                "feedback_round_id": "batch_003_feedback",
                "batch_id": "batch_003",
                "cases": [
                    {
                        "paper_id": "1245",
                        "expected_verdict": "correct",
                        "expected_manual_review": False,
                        "expected_start_first_line": "Poster 237",
                        "expected_end_contains": "forces exerted on bony elements leading to fractures.",
                        "expected_not_contains": ["Poster 238"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = evaluate_feedback_files(
        feedback_paths=[feedback_path],
        reports_dir=reports_dir,
        source_registry_path=source_registry,
        source_manual_review_path=manual_review,
    )

    assert report["passed_count"] == 1
    result = report["results"][0]
    check_names = [check["name"] for check in result["checks"]]
    assert "trimmed_output_present" in check_names
    assert "qc_confirmed_full" in check_names
    assert "start_line_matches" in check_names
    assert "expected_end_present" in check_names


def test_evaluate_feedback_tolerates_ocr_fragmentation_in_expected_end(tmp_path: Path) -> None:
    source_registry = tmp_path / "source_categorisation_registry.csv"
    manual_review = tmp_path / "source_categorisation_manual_review.csv"
    feedback_path = tmp_path / "batch_001_feedback.json"
    reports_dir = tmp_path / "reports"
    batch_dir = reports_dir / "batch_001"
    trimmed_dir = batch_dir / "text_trimmed"
    trimmed_dir.mkdir(parents=True)
    trimmed_path = trimmed_dir / "1011.json"

    write_csv(
        source_registry,
        [
            {
                "paper_id": "1011",
                "source_category": "conference_abstract",
                "source_subtype": "single_case_conference_abstract",
                "classification_confidence": "high",
                "categorisation_reason": "Proceedings abstract.",
            }
        ],
    )
    write_csv(manual_review, [])
    trimmed_path.write_text(
        json.dumps(
            {
                "pages": [
                    {
                        "page_index": 0,
                        "text": "\n".join(
                            [
                                "Poster 313",
                                "Two Cases of Stiff Person Syndrome Treated with Intrathecal Baclofen Pump",
                                "patients with SPS may bene t from intrathecal baclofen pumps or inpatient rehabilitation.",
                            ]
                        ),
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    write_csv(
        batch_dir / "text_trim_registry.csv",
        [
            {
                "paper_id": "1011",
                "trim_status": "trimmed_auto",
                "trimmed_text_json_path": "",
            }
        ],
    )
    write_csv(
        batch_dir / "proceedings_text_qc_registry.csv",
        [{"paper_id": "1011", "qc_status": "confirmed_full", "manual_follow_up_required": "false"}],
    )
    feedback_path.write_text(
        json.dumps(
            {
                "feedback_round_id": "batch_001_feedback",
                "batch_id": "batch_001",
                "cases": [
                    {
                        "paper_id": "1011",
                        "expected_verdict": "correct",
                        "expected_manual_review": False,
                        "expected_end_contains": "patients with SPS may benefit from intrathecal baclofen pumps or inpatient rehabilitation.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    report = evaluate_feedback_files(
        feedback_paths=[feedback_path],
        reports_dir=reports_dir,
        source_registry_path=source_registry,
        source_manual_review_path=manual_review,
    )

    assert report["passed_count"] == 1
    result = report["results"][0]
    end_check = next(check for check in result["checks"] if check["name"] == "expected_end_present")
    assert end_check["passed"] is True
