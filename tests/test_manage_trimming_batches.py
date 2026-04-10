from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import src.validation.manage_trimming_batches as manage_trimming_batches
from src.validation.manage_trimming_batches import (
    next_batch_id,
    open_batches,
    reviewed_paper_ids,
    select_unreviewed_batch,
)


def test_reviewed_paper_ids_reads_feedback_and_regression(tmp_path: Path) -> None:
    feedback_dir = tmp_path / "feedback"
    regression_dir = tmp_path / "regression"
    feedback_dir.mkdir()
    regression_dir.mkdir()
    (feedback_dir / "reviewed_batch.json").write_text(
        json.dumps({"cases": [{"paper_id": "1597"}, {"paper_id": "6271"}]}),
        encoding="utf-8",
    )
    nested = regression_dir / "accepted"
    nested.mkdir()
    (nested / "boundary_cases.json").write_text(
        json.dumps({"paper_id": "8198", "cases": [{"paper_id": "8317"}]}),
        encoding="utf-8",
    )

    reviewed = reviewed_paper_ids(feedback_dir, regression_dir)

    assert reviewed == {"1597", "6271", "8198", "8317"}


def test_open_batches_detects_unresolved_manifests(tmp_path: Path) -> None:
    batches_dir = tmp_path / "batches"
    batches_dir.mkdir()
    (batches_dir / "batch_001.json").write_text(
        json.dumps({"batch_id": "batch_001", "status": "awaiting_review"}),
        encoding="utf-8",
    )
    (batches_dir / "batch_002.json").write_text(
        json.dumps({"batch_id": "batch_002", "status": "resolved"}),
        encoding="utf-8",
    )

    active = open_batches(batches_dir)

    assert [item["batch_id"] for item in active] == ["batch_001"]


def test_next_batch_id_increments_existing_manifests(tmp_path: Path) -> None:
    batches_dir = tmp_path / "batches"
    batches_dir.mkdir()
    (batches_dir / "batch_001.json").write_text("{}", encoding="utf-8")
    (batches_dir / "batch_007.json").write_text("{}", encoding="utf-8")

    assert next_batch_id(batches_dir) == "batch_008"


def test_select_unreviewed_batch_excludes_reviewed_ids() -> None:
    candidate_rows = [
        {"paper_id": "969", "title": "A"},
        {"paper_id": "980", "title": "B"},
        {"paper_id": "1001", "title": "C"},
    ]

    selected = select_unreviewed_batch(candidate_rows, {"980"}, batch_size=2)

    assert [row["paper_id"] for row in selected] == ["969", "1001"]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def fake_refresh_review_materials(**kwargs) -> dict[str, object]:
    report_dir = kwargs["report_dir"]
    (report_dir / "review_queue.csv").write_text("batch_id,paper_id\n", encoding="utf-8")
    (report_dir / "responses.csv").write_text("batch_id,paper_id\n", encoding="utf-8")
    (report_dir / "feedback.json").write_text(json.dumps({"cases": []}), encoding="utf-8")
    (report_dir / "manual_overrides.csv").write_text("batch_id,paper_id\n", encoding="utf-8")
    (report_dir / "acceptance_report.json").write_text(json.dumps({"results": []}), encoding="utf-8")
    (report_dir / "patch_review_summary.json").write_text(json.dumps({"incorrect_cases": []}), encoding="utf-8")
    return {
        "queue_rows": [],
        "responses_by_id": {},
        "acceptance_report": {"failed_count": 0},
        "completed_review_count": 0,
    }


def test_prepare_batch_screens_forward_until_it_collects_detected_cases(
    tmp_path: Path,
    monkeypatch,
) -> None:
    candidates = [
        {
            "paper_id": "1001",
            "title": "A",
            "authors": "Author A",
            "resolved_source_subtype": "",
            "resolved_source_route_source": "heuristic",
        },
        {
            "paper_id": "1002",
            "title": "B",
            "authors": "Author B",
            "resolved_source_subtype": "",
            "resolved_source_route_source": "heuristic",
        },
        {
            "paper_id": "1003",
            "title": "C",
            "authors": "Author C",
            "resolved_source_subtype": "",
            "resolved_source_route_source": "heuristic",
        },
        {
            "paper_id": "1004",
            "title": "D",
            "authors": "Author D",
            "resolved_source_subtype": "",
            "resolved_source_route_source": "heuristic",
        },
    ]
    detected_ids = {"1002", "1004"}
    command_log: list[list[str]] = []

    def fake_run_command(command: list[str]) -> None:
        command_log.append(command)
        script_name = Path(command[1]).name
        if script_name == "05_trim_proceedings_text.py":
            paper_id = command[command.index("--paper-id") + 1]
            registry_path = Path(command[command.index("--registry-path") + 1])
            existing_rows = []
            if registry_path.exists():
                with registry_path.open(encoding="utf-8-sig", newline="") as handle:
                    existing_rows = list(csv.DictReader(handle))
            existing_by_id = {row["paper_id"]: row for row in existing_rows}
            existing_by_id[paper_id] = {
                "paper_id": paper_id,
                "proceedings_detected": "true" if paper_id in detected_ids else "false",
                "trim_status": "trimmed_auto" if paper_id in detected_ids else "not_needed",
                "match_score": "0.95" if paper_id in detected_ids else "",
                "title_score": "0.95" if paper_id in detected_ids else "",
                "author_score": "0.70" if paper_id in detected_ids else "",
                "trim_reason": "fixture",
            }
            write_csv(
                registry_path,
                ["paper_id", "proceedings_detected", "trim_status", "match_score", "title_score", "author_score", "trim_reason"],
                list(existing_by_id.values()),
            )
            trimmed_dir = Path(command[command.index("--output-dir") + 1])
            if paper_id in detected_ids:
                trimmed_dir.mkdir(parents=True, exist_ok=True)
                (trimmed_dir / f"{paper_id}.json").write_text(json.dumps({"paper_id": paper_id}), encoding="utf-8")
        elif script_name == "05b_validate_proceedings_text.py":
            output_path = Path(command[command.index("--output-path") + 1])
            paper_id = command[command.index("--paper-id") + 1]
            existing_rows = []
            if output_path.exists():
                with output_path.open(encoding="utf-8-sig", newline="") as handle:
                    existing_rows = list(csv.DictReader(handle))
            existing_by_id = {row["paper_id"]: row for row in existing_rows}
            existing_by_id[paper_id] = {
                "paper_id": paper_id,
                "qc_status": "confirmed_full",
                "manual_follow_up_required": "false",
                "qc_note": "fixture",
                "combined_score": "0.91",
            }
            write_csv(
                output_path,
                ["paper_id", "qc_status", "manual_follow_up_required", "qc_note", "combined_score"],
                list(existing_by_id.values()),
            )

    monkeypatch.setattr(manage_trimming_batches, "resolved_conference_rows", lambda *args, **kwargs: candidates)
    monkeypatch.setattr(manage_trimming_batches, "reviewed_paper_ids", lambda *args, **kwargs: set())
    monkeypatch.setattr(manage_trimming_batches, "run_command", fake_run_command)
    monkeypatch.setattr(manage_trimming_batches.stage05_review, "refresh_review_materials", fake_refresh_review_materials)
    monkeypatch.setattr(manage_trimming_batches, "repo_relative", lambda path: str(path))

    args = argparse.Namespace(
        batch_size=2,
        source_registry_path=tmp_path / "source.csv",
        source_manual_review_path=tmp_path / "manual.csv",
        batches_dir=tmp_path / "batches",
        feedback_dir=tmp_path / "feedback",
        regression_dir=tmp_path / "regression",
        reports_dir=tmp_path / "reports",
    )

    report = manage_trimming_batches.prepare_batch(args)

    assert report["paper_ids"] == ["1002", "1004"]
    assert report["screened_candidate_ids"] == ["1001", "1002", "1003", "1004"]
    assert [Path(command[1]).name for command in command_log].count("05_trim_proceedings_text.py") == 4
    assert [Path(command[1]).name for command in command_log].count("05b_validate_proceedings_text.py") == 2

    manifest = json.loads((tmp_path / "batches" / "batch_001.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "awaiting_review"
    assert manifest["paper_ids"] == ["1002", "1004"]
    assert manifest["batch_size_target"] == 2
    assert manifest["qc_completed_paper_ids"] == ["1002", "1004"]
    assert "review_queue_path" in manifest["output_paths"]


def test_prepare_batch_resumes_existing_processing_batch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    candidates = [
        {
            "paper_id": "1001",
            "title": "A",
            "authors": "Author A",
            "resolved_source_subtype": "",
            "resolved_source_route_source": "heuristic",
        },
        {
            "paper_id": "1002",
            "title": "B",
            "authors": "Author B",
            "resolved_source_subtype": "",
            "resolved_source_route_source": "heuristic",
        },
        {
            "paper_id": "1003",
            "title": "C",
            "authors": "Author C",
            "resolved_source_subtype": "",
            "resolved_source_route_source": "heuristic",
        },
        {
            "paper_id": "1004",
            "title": "D",
            "authors": "Author D",
            "resolved_source_subtype": "",
            "resolved_source_route_source": "heuristic",
        },
    ]
    detected_ids = {"1002", "1004"}
    report_dir = tmp_path / "reports" / "batch_001"
    report_dir.mkdir(parents=True)
    (report_dir / "text_trimmed").mkdir()
    write_csv(
        report_dir / "text_trim_registry.csv",
        ["paper_id", "proceedings_detected", "trim_status", "match_score", "title_score", "author_score", "trim_reason"],
        [
            {
                "paper_id": "1001",
                "proceedings_detected": "false",
                "trim_status": "not_needed",
                "match_score": "",
                "title_score": "",
                "author_score": "",
                "trim_reason": "fixture",
            },
            {
                "paper_id": "1002",
                "proceedings_detected": "true",
                "trim_status": "trimmed_auto",
                "match_score": "0.95",
                "title_score": "0.95",
                "author_score": "0.70",
                "trim_reason": "fixture",
            },
        ],
    )

    manifest = {
        "batch_id": "batch_001",
        "status": "stage05_running",
        "batch_size_target": 2,
        "paper_ids": ["1002"],
        "screened_candidate_ids": ["1001", "1002"],
        "screened_candidate_count": 2,
        "qc_completed_paper_ids": [],
        "output_paths": {
            "report_dir": str(report_dir),
            "report_path": str(report_dir / "batch_report.json"),
            "trim_registry_path": str(report_dir / "text_trim_registry.csv"),
            "qc_registry_path": str(report_dir / "proceedings_text_qc_registry.csv"),
        },
    }
    batches_dir = tmp_path / "batches"
    batches_dir.mkdir()
    (batches_dir / "batch_001.json").write_text(json.dumps(manifest), encoding="utf-8")

    command_log: list[list[str]] = []

    def fake_run_command(command: list[str]) -> None:
        command_log.append(command)
        script_name = Path(command[1]).name
        if script_name == "05_trim_proceedings_text.py":
            paper_id = command[command.index("--paper-id") + 1]
            registry_path = Path(command[command.index("--registry-path") + 1])
            existing_rows = list(csv.DictReader(registry_path.open(encoding="utf-8-sig", newline="")))
            existing_by_id = {row["paper_id"]: row for row in existing_rows}
            existing_by_id[paper_id] = {
                "paper_id": paper_id,
                "proceedings_detected": "true" if paper_id in detected_ids else "false",
                "trim_status": "trimmed_auto" if paper_id in detected_ids else "not_needed",
                "match_score": "0.95" if paper_id in detected_ids else "",
                "title_score": "0.95" if paper_id in detected_ids else "",
                "author_score": "0.70" if paper_id in detected_ids else "",
                "trim_reason": "fixture",
            }
            write_csv(
                registry_path,
                ["paper_id", "proceedings_detected", "trim_status", "match_score", "title_score", "author_score", "trim_reason"],
                list(existing_by_id.values()),
            )
            if paper_id in detected_ids:
                (report_dir / "text_trimmed" / f"{paper_id}.json").write_text(json.dumps({"paper_id": paper_id}), encoding="utf-8")
        elif script_name == "05b_validate_proceedings_text.py":
            output_path = Path(command[command.index("--output-path") + 1])
            paper_id = command[command.index("--paper-id") + 1]
            existing_rows = []
            if output_path.exists():
                with output_path.open(encoding="utf-8-sig", newline="") as handle:
                    existing_rows = list(csv.DictReader(handle))
            existing_by_id = {row["paper_id"]: row for row in existing_rows}
            existing_by_id[paper_id] = {
                "paper_id": paper_id,
                "qc_status": "confirmed_full",
                "manual_follow_up_required": "false",
                "qc_note": "fixture",
                "combined_score": "0.91",
            }
            write_csv(
                output_path,
                ["paper_id", "qc_status", "manual_follow_up_required", "qc_note", "combined_score"],
                list(existing_by_id.values()),
            )

    monkeypatch.setattr(manage_trimming_batches, "resolved_conference_rows", lambda *args, **kwargs: candidates)
    monkeypatch.setattr(manage_trimming_batches, "reviewed_paper_ids", lambda *args, **kwargs: set())
    monkeypatch.setattr(manage_trimming_batches, "run_command", fake_run_command)
    monkeypatch.setattr(manage_trimming_batches.stage05_review, "refresh_review_materials", fake_refresh_review_materials)
    monkeypatch.setattr(manage_trimming_batches, "repo_relative", lambda path: str(path))

    args = argparse.Namespace(
        batch_size=2,
        source_registry_path=tmp_path / "source.csv",
        source_manual_review_path=tmp_path / "manual.csv",
        batches_dir=batches_dir,
        feedback_dir=tmp_path / "feedback",
        regression_dir=tmp_path / "regression",
        reports_dir=tmp_path / "reports",
    )

    report = manage_trimming_batches.prepare_batch(args)

    assert report["batch_id"] == "batch_001"
    assert report["paper_ids"] == ["1002", "1004"]
    assert [Path(command[1]).name for command in command_log].count("05_trim_proceedings_text.py") == 2
    manifest_after = json.loads((batches_dir / "batch_001.json").read_text(encoding="utf-8"))
    assert manifest_after["status"] == "awaiting_review"
    assert manifest_after["paper_ids"] == ["1002", "1004"]


def test_prepare_batch_raises_when_not_enough_detected_cases_remain(
    tmp_path: Path,
    monkeypatch,
) -> None:
    candidates = [
        {
            "paper_id": "1001",
            "title": "A",
            "authors": "Author A",
            "resolved_source_subtype": "",
            "resolved_source_route_source": "heuristic",
        },
        {
            "paper_id": "1002",
            "title": "B",
            "authors": "Author B",
            "resolved_source_subtype": "",
            "resolved_source_route_source": "heuristic",
        },
        {
            "paper_id": "1003",
            "title": "C",
            "authors": "Author C",
            "resolved_source_subtype": "",
            "resolved_source_route_source": "heuristic",
        },
    ]

    def fake_run_command(command: list[str]) -> None:
        if Path(command[1]).name != "05_trim_proceedings_text.py":
            return
        paper_id = command[command.index("--paper-id") + 1]
        registry_path = Path(command[command.index("--registry-path") + 1])
        existing_rows = []
        if registry_path.exists():
            with registry_path.open(encoding="utf-8-sig", newline="") as handle:
                existing_rows = list(csv.DictReader(handle))
        existing_by_id = {row["paper_id"]: row for row in existing_rows}
        existing_by_id[paper_id] = {
            "paper_id": paper_id,
            "proceedings_detected": "true" if paper_id == "1002" else "false",
            "trim_status": "trimmed_auto" if paper_id == "1002" else "not_needed",
            "match_score": "",
            "title_score": "",
            "author_score": "",
            "trim_reason": "fixture",
        }
        write_csv(
            registry_path,
            ["paper_id", "proceedings_detected", "trim_status", "match_score", "title_score", "author_score", "trim_reason"],
            list(existing_by_id.values()),
        )

    monkeypatch.setattr(manage_trimming_batches, "resolved_conference_rows", lambda *args, **kwargs: candidates)
    monkeypatch.setattr(manage_trimming_batches, "reviewed_paper_ids", lambda *args, **kwargs: set())
    monkeypatch.setattr(manage_trimming_batches, "run_command", fake_run_command)

    args = argparse.Namespace(
        batch_size=2,
        source_registry_path=tmp_path / "source.csv",
        source_manual_review_path=tmp_path / "manual.csv",
        batches_dir=tmp_path / "batches",
        feedback_dir=tmp_path / "feedback",
        regression_dir=tmp_path / "regression",
        reports_dir=tmp_path / "reports",
    )

    try:
        manage_trimming_batches.prepare_batch(args)
    except RuntimeError as error:
        assert "found 1 detected files after screening 3 candidates" in str(error)
    else:
        raise AssertionError("Expected prepare_batch to fail when too few proceedings-detected files remain.")

    manifest = json.loads((tmp_path / "batches" / "batch_001.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "stage05_running"
    assert manifest["screened_candidate_ids"] == ["1001", "1002", "1003"]
