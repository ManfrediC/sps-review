from __future__ import annotations

from pathlib import Path

from src.validation import _stage05_review as review


def test_build_feedback_payload_uses_workflow_stage_and_reviewed_fields() -> None:
    queue_rows = [
        {
            "batch_id": "batch_050",
            "paper_id": "1001",
            "title": "A",
            "workflow_stage": "stage05_trimming",
        },
        {
            "batch_id": "batch_050",
            "paper_id": "1002",
            "title": "B",
            "workflow_stage": "stage05_not_needed",
        },
    ]
    responses_by_id = {
        "1001": {
            "paper_id": "1001",
            "review_status": "reviewed",
            "extraction_correct": "false",
            "reviewed_correct": "false",
            "corrected_start_text": "Poster 237",
            "corrected_end_text": "important conclusion",
            "reviewer_comments": "Shared spillover failure.",
            "updated_at_utc": "2026-04-10T12:00:00+00:00",
        },
        "1002": {
            "paper_id": "1002",
            "review_status": "reviewed",
            "extraction_correct": "true",
            "reviewed_correct": "true",
            "corrected_start_text": "",
            "corrected_end_text": "",
            "reviewer_comments": "This should stay untrimmed.",
            "updated_at_utc": "2026-04-10T12:05:00+00:00",
        },
    }

    payload = review.build_feedback_payload("batch_050", queue_rows, responses_by_id)

    assert payload["feedback_round_id"] == "batch_050_feedback"
    assert payload["received_at_utc"] == "2026-04-10T12:05:00+00:00"
    assert payload["cases"] == [
        {
            "paper_id": "1001",
            "workflow_stage": "stage05_trimming",
            "expected_verdict": "wrong_abstract",
            "expected_manual_review": False,
            "expected_start_first_line": "Poster 237",
            "expected_end_contains": "important conclusion",
            "notes": "Shared spillover failure.",
        },
        {
            "paper_id": "1002",
            "workflow_stage": "stage05_not_needed",
            "expected_verdict": "should_manual_review",
            "expected_manual_review": True,
            "notes": "This should stay untrimmed.",
        },
    ]


def test_sync_manual_overrides_keeps_only_reviewed_incorrect_cases(tmp_path: Path) -> None:
    report_dir = tmp_path / "batch_050"
    report_dir.mkdir()
    queue_rows = [
        {"batch_id": "batch_050", "paper_id": "1001"},
        {"batch_id": "batch_050", "paper_id": "1002"},
    ]
    responses_by_id = {
        "1001": {
            "paper_id": "1001",
            "reviewed_correct": "false",
            "corrected_start_text": "Start",
            "corrected_end_text": "End",
            "reviewer_comments": "Needs fallback.",
        },
        "1002": {
            "paper_id": "1002",
            "reviewed_correct": "true",
            "corrected_start_text": "",
            "corrected_end_text": "",
            "reviewer_comments": "",
        },
    }

    rows = review.sync_manual_overrides(report_dir, queue_rows, responses_by_id)

    assert rows == [
        {
            "batch_id": "batch_050",
            "paper_id": "1001",
            "override_enabled": "false",
            "corrected_start_text": "Start",
            "corrected_end_text": "End",
            "reviewer_comments": "Needs fallback.",
            "override_status": "pending_review",
            "override_applied_at_utc": "",
        }
    ]
    written_rows = review.load_csv_rows(review.manual_overrides_path(report_dir))
    assert [row["paper_id"] for row in written_rows] == ["1001"]


def test_apply_acceptance_to_responses_sets_corrected_successfully_for_failed_and_passed_cases() -> None:
    queue_rows = [
        {"paper_id": "1001"},
        {"paper_id": "1002"},
    ]
    responses_by_id = {
        "1001": {"paper_id": "1001", "reviewed_correct": "false", "corrected_successfully": "false"},
        "1002": {"paper_id": "1002", "reviewed_correct": "false", "corrected_successfully": "false"},
    }
    acceptance_report = {
        "results": [
            {"paper_id": "1001", "passed": True},
            {"paper_id": "1002", "passed": False},
        ]
    }

    updated = review.apply_acceptance_to_responses(queue_rows, responses_by_id, acceptance_report)

    assert updated["1001"]["corrected_successfully"] == "true"
    assert updated["1002"]["corrected_successfully"] == "false"


def test_save_response_row_persists_row_in_queue_order(tmp_path: Path) -> None:
    report_dir = tmp_path / "batch_050"
    report_dir.mkdir()
    review.write_csv_rows(
        review.review_queue_path(report_dir),
        [
            {"batch_id": "batch_050", "paper_id": "1002", "title": "B"},
            {"batch_id": "batch_050", "paper_id": "1001", "title": "A"},
        ],
        review.review_queue_fieldnames(),
    )

    review.save_response_row(
        report_dir,
        {
            "batch_id": "batch_050",
            "paper_id": "1001",
            "title": "A",
            "extraction_correct": "true",
            "corrected_start_text": "",
            "corrected_end_text": "",
            "reviewer_comments": "",
            "reviewed_correct": "true",
            "corrected_successfully": "false",
            "review_status": "reviewed",
            "reviewer_id": "tester",
            "reviewed_at_utc": "2026-04-10T12:00:00+00:00",
            "updated_at_utc": "2026-04-10T12:00:00+00:00",
        },
    )
    review.save_response_row(
        report_dir,
        {
            "batch_id": "batch_050",
            "paper_id": "1002",
            "title": "B",
            "extraction_correct": "false",
            "corrected_start_text": "Start",
            "corrected_end_text": "End",
            "reviewer_comments": "Needs patch.",
            "reviewed_correct": "false",
            "corrected_successfully": "false",
            "review_status": "reviewed",
            "reviewer_id": "tester",
            "reviewed_at_utc": "2026-04-10T12:05:00+00:00",
            "updated_at_utc": "2026-04-10T12:05:00+00:00",
        },
    )

    saved_rows = review.load_csv_rows(review.responses_path(report_dir))
    assert [row["paper_id"] for row in saved_rows] == ["1002", "1001"]
