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


def test_prepare_batch_screens_forward_until_it_collects_candidate_packages(
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
    candidate_package_ids = {"1002", "1004"}
    command_log: list[list[str]] = []

    def fake_run_command(command: list[str]) -> None:
        command_log.append(command)
        script_name = Path(command[1]).name
        if script_name == "05_trim_proceedings_text_LLM.py":
            paper_id = command[command.index("--paper-id") + 1]
            registry_path = Path(command[command.index("--candidate-registry-path") + 1])
            existing_rows = []
            if registry_path.exists():
                with registry_path.open(encoding="utf-8-sig", newline="") as handle:
                    existing_rows = list(csv.DictReader(handle))
            existing_by_id = {row["paper_id"]: row for row in existing_rows}
            existing_by_id[paper_id] = {
                "paper_id": paper_id,
                "trim_status": "candidate_package_created" if paper_id in candidate_package_ids else "not_needed",
                "candidate_count": "2" if paper_id in candidate_package_ids else "0",
                "source_text_json_path": f"data/extraction_json/text/{paper_id}.json",
                "candidate_heuristics": "fixture",
            }
            write_csv(
                registry_path,
                ["paper_id", "trim_status", "candidate_count", "source_text_json_path", "candidate_heuristics"],
                list(existing_by_id.values()),
            )
            candidate_dir = Path(command[command.index("--candidate-output-dir") + 1])
            if paper_id in candidate_package_ids:
                candidate_dir.mkdir(parents=True, exist_ok=True)
                (candidate_dir / f"{paper_id}.json").write_text(json.dumps({"paper_id": paper_id}), encoding="utf-8")
        elif script_name == "05b_validate_proceedings_text_LLM.py":
            registry_path = Path(command[command.index("--registry-path") + 1])
            paper_id = command[command.index("--paper-id") + 1]
            existing_rows = []
            if registry_path.exists():
                with registry_path.open(encoding="utf-8-sig", newline="") as handle:
                    existing_rows = list(csv.DictReader(handle))
            existing_by_id = {row["paper_id"]: row for row in existing_rows}
            existing_by_id[paper_id] = {
                "paper_id": paper_id,
                "trim_status": "trimmed_auto_llm_candidate_exact",
                "llm_validation_passed": "true",
                "llm_validation_reason": "fixture",
                "heuristic_fallback_used": "false",
            }
            write_csv(
                registry_path,
                ["paper_id", "trim_status", "llm_validation_passed", "llm_validation_reason", "heuristic_fallback_used"],
                list(existing_by_id.values()),
            )
            llm_dir = Path(command[command.index("--output-dir") + 1])
            llm_dir.mkdir(parents=True, exist_ok=True)
            (llm_dir / f"{paper_id}.json").write_text(json.dumps({"paper_id": paper_id}), encoding="utf-8")
        elif script_name == "05c_publish_proceedings_ready.py":
            output_path = Path(command[command.index("--output-path") + 1])
            paper_id = command[command.index("--paper-id") + 1]
            existing_rows = []
            if output_path.exists():
                with output_path.open(encoding="utf-8-sig", newline="") as handle:
                    existing_rows = list(csv.DictReader(handle))
            existing_by_id = {row["paper_id"]: row for row in existing_rows}
            existing_by_id[paper_id] = {
                "paper_id": paper_id,
                "ready_source_kind": "llm_validated",
                "ready_text_mode": "trimmed_abstract",
                "ready_reason": "fixture",
            }
            write_csv(
                output_path,
                ["paper_id", "ready_source_kind", "ready_text_mode", "ready_reason"],
                list(existing_by_id.values()),
            )
            ready_dir = Path(command[command.index("--output-dir") + 1])
            ready_dir.mkdir(parents=True, exist_ok=True)
            (ready_dir / f"{paper_id}.json").write_text(json.dumps({"paper_id": paper_id}), encoding="utf-8")

    monkeypatch.setattr(manage_trimming_batches, "resolved_conference_rows", lambda *args, **kwargs: candidates)
    monkeypatch.setattr(manage_trimming_batches, "reviewed_paper_ids", lambda *args, **kwargs: set())
    monkeypatch.setattr(manage_trimming_batches, "run_command", fake_run_command)
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
    assert [Path(command[1]).name for command in command_log].count("05_trim_proceedings_text_LLM.py") == 4
    assert [Path(command[1]).name for command in command_log].count("05b_validate_proceedings_text_LLM.py") == 2
    assert [Path(command[1]).name for command in command_log].count("05c_publish_proceedings_ready.py") == 2

    manifest = json.loads((tmp_path / "batches" / "batch_001.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "awaiting_review"
    assert manifest["paper_ids"] == ["1002", "1004"]
    assert manifest["batch_size_target"] == 2
    assert manifest["llm_completed_paper_ids"] == ["1002", "1004"]
    assert manifest["published_paper_ids"] == ["1002", "1004"]
    assert "ready_registry_path" in manifest["output_paths"]


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
    candidate_package_ids = {"1002", "1004"}
    report_dir = tmp_path / "reports" / "batch_001"
    (report_dir / "text_trimmed_llm_candidates").mkdir(parents=True)
    (report_dir / "text_trimmed_llm").mkdir()
    (report_dir / "text_proceedings_ready").mkdir()
    write_csv(
        report_dir / "text_trim_llm_candidate_registry.csv",
        ["paper_id", "trim_status", "candidate_count", "source_text_json_path", "candidate_heuristics"],
        [
            {
                "paper_id": "1001",
                "trim_status": "not_needed",
                "candidate_count": "0",
                "source_text_json_path": "data/extraction_json/text/1001.json",
                "candidate_heuristics": "fixture",
            },
            {
                "paper_id": "1002",
                "trim_status": "candidate_package_created",
                "candidate_count": "2",
                "source_text_json_path": "data/extraction_json/text/1002.json",
                "candidate_heuristics": "fixture",
            },
        ],
    )

    manifest = {
        "batch_id": "batch_001",
        "status": "candidate_generation_running",
        "batch_size_target": 2,
        "paper_ids": ["1002"],
        "screened_candidate_ids": ["1001", "1002"],
        "screened_candidate_count": 2,
        "llm_completed_paper_ids": [],
        "published_paper_ids": [],
        "output_paths": {
            "report_dir": str(report_dir),
            "report_path": str(report_dir / "batch_report.json"),
            "candidate_registry_path": str(report_dir / "text_trim_llm_candidate_registry.csv"),
            "llm_registry_path": str(report_dir / "text_trim_llm_registry.csv"),
            "ready_registry_path": str(report_dir / "text_proceedings_ready_registry.csv"),
        },
    }
    batches_dir = tmp_path / "batches"
    batches_dir.mkdir()
    (batches_dir / "batch_001.json").write_text(json.dumps(manifest), encoding="utf-8")

    command_log: list[list[str]] = []

    def fake_run_command(command: list[str]) -> None:
        command_log.append(command)
        script_name = Path(command[1]).name
        if script_name == "05_trim_proceedings_text_LLM.py":
            paper_id = command[command.index("--paper-id") + 1]
            registry_path = Path(command[command.index("--candidate-registry-path") + 1])
            existing_rows = list(csv.DictReader(registry_path.open(encoding="utf-8-sig", newline="")))
            existing_by_id = {row["paper_id"]: row for row in existing_rows}
            existing_by_id[paper_id] = {
                "paper_id": paper_id,
                "trim_status": "candidate_package_created" if paper_id in candidate_package_ids else "not_needed",
                "candidate_count": "2" if paper_id in candidate_package_ids else "0",
                "source_text_json_path": f"data/extraction_json/text/{paper_id}.json",
                "candidate_heuristics": "fixture",
            }
            write_csv(
                registry_path,
                ["paper_id", "trim_status", "candidate_count", "source_text_json_path", "candidate_heuristics"],
                list(existing_by_id.values()),
            )
            if paper_id in candidate_package_ids:
                (report_dir / "text_trimmed_llm_candidates" / f"{paper_id}.json").write_text(
                    json.dumps({"paper_id": paper_id}),
                    encoding="utf-8",
                )
        elif script_name == "05b_validate_proceedings_text_LLM.py":
            output_path = Path(command[command.index("--registry-path") + 1])
            paper_id = command[command.index("--paper-id") + 1]
            existing_rows = []
            if output_path.exists():
                with output_path.open(encoding="utf-8-sig", newline="") as handle:
                    existing_rows = list(csv.DictReader(handle))
            existing_by_id = {row["paper_id"]: row for row in existing_rows}
            existing_by_id[paper_id] = {
                "paper_id": paper_id,
                "trim_status": "trimmed_auto_llm_candidate_exact",
                "llm_validation_passed": "true",
                "llm_validation_reason": "fixture",
                "heuristic_fallback_used": "false",
            }
            write_csv(
                output_path,
                ["paper_id", "trim_status", "llm_validation_passed", "llm_validation_reason", "heuristic_fallback_used"],
                list(existing_by_id.values()),
            )
            (report_dir / "text_trimmed_llm" / f"{paper_id}.json").write_text(json.dumps({"paper_id": paper_id}), encoding="utf-8")
        elif script_name == "05c_publish_proceedings_ready.py":
            output_path = Path(command[command.index("--output-path") + 1])
            paper_id = command[command.index("--paper-id") + 1]
            existing_rows = []
            if output_path.exists():
                with output_path.open(encoding="utf-8-sig", newline="") as handle:
                    existing_rows = list(csv.DictReader(handle))
            existing_by_id = {row["paper_id"]: row for row in existing_rows}
            existing_by_id[paper_id] = {
                "paper_id": paper_id,
                "ready_source_kind": "llm_validated",
                "ready_text_mode": "trimmed_abstract",
                "ready_reason": "fixture",
            }
            write_csv(
                output_path,
                ["paper_id", "ready_source_kind", "ready_text_mode", "ready_reason"],
                list(existing_by_id.values()),
            )
            (report_dir / "text_proceedings_ready" / f"{paper_id}.json").write_text(json.dumps({"paper_id": paper_id}), encoding="utf-8")

    monkeypatch.setattr(manage_trimming_batches, "resolved_conference_rows", lambda *args, **kwargs: candidates)
    monkeypatch.setattr(manage_trimming_batches, "reviewed_paper_ids", lambda *args, **kwargs: set())
    monkeypatch.setattr(manage_trimming_batches, "run_command", fake_run_command)
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
    assert [Path(command[1]).name for command in command_log].count("05_trim_proceedings_text_LLM.py") == 2
    manifest_after = json.loads((batches_dir / "batch_001.json").read_text(encoding="utf-8"))
    assert manifest_after["status"] == "awaiting_review"
    assert manifest_after["paper_ids"] == ["1002", "1004"]


def test_prepare_batch_raises_when_not_enough_candidate_packages_remain(
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
        if Path(command[1]).name != "05_trim_proceedings_text_LLM.py":
            return
        paper_id = command[command.index("--paper-id") + 1]
        registry_path = Path(command[command.index("--candidate-registry-path") + 1])
        existing_rows = []
        if registry_path.exists():
            with registry_path.open(encoding="utf-8-sig", newline="") as handle:
                existing_rows = list(csv.DictReader(handle))
        existing_by_id = {row["paper_id"]: row for row in existing_rows}
        existing_by_id[paper_id] = {
            "paper_id": paper_id,
            "trim_status": "candidate_package_created" if paper_id == "1002" else "not_needed",
            "candidate_count": "2" if paper_id == "1002" else "0",
            "source_text_json_path": f"data/extraction_json/text/{paper_id}.json",
            "candidate_heuristics": "fixture",
        }
        write_csv(
            registry_path,
            ["paper_id", "trim_status", "candidate_count", "source_text_json_path", "candidate_heuristics"],
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
        assert "found 1 candidate packages after screening 3 conference abstracts" in str(error)
    else:
        raise AssertionError("Expected prepare_batch to fail when too few candidate packages remain.")

    manifest = json.loads((tmp_path / "batches" / "batch_001.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "candidate_generation_running"
    assert manifest["screened_candidate_ids"] == ["1001", "1002", "1003"]
