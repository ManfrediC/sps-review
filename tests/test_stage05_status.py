from __future__ import annotations

import csv
import json
from pathlib import Path

from src.autoresearch.stage_05 import status


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_results(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "iteration",
                "status",
                "exact_match_count",
                "case_count",
                "exact_match_rate",
                "regression_failed_count",
                "kept_commit",
                "description",
            ],
            delimiter="\t",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_build_status_snapshot_detects_baseline_startup(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    run_root = tmp_path / "run"
    write_json(manifest_path, {"paper_count": 3, "entries": []})
    write_json(
        run_root / "loop_config.json",
        {
            "run_root": str(run_root),
            "run_tag": "demo-run",
            "manifest_path": str(manifest_path),
        },
    )
    (run_root / "baseline" / "gold" / "command_stderr.log").parent.mkdir(parents=True, exist_ok=True)
    (run_root / "baseline" / "gold" / "command_stderr.log").write_text(
        "Proceedings trim:   0%|          | 0/3 [00:00<?, ?it/s]\n",
        encoding="utf-8",
    )

    snapshot = status.build_status_snapshot(run_root)

    assert snapshot["status"] == "running"
    assert snapshot["phase"] == "baseline_gold_running"
    assert snapshot["expected_case_count"] == 3
    assert snapshot["baseline_gold_output_count"] == 0
    assert snapshot["iteration_count"] == 0


def test_build_status_snapshot_uses_latest_payload_and_results(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    run_root = tmp_path / "run"
    write_json(manifest_path, {"paper_count": 3, "entries": []})
    write_json(
        run_root / "loop_config.json",
        {
            "run_root": str(run_root),
            "run_tag": "demo-run",
            "manifest_path": str(manifest_path),
        },
    )
    write_results(
        run_root / "results.tsv",
        [
            {
                "iteration": "baseline",
                "status": "baseline",
                "exact_match_count": "1",
                "case_count": "3",
                "exact_match_rate": "0.333333",
                "regression_failed_count": "2",
                "kept_commit": "abc1234",
                "description": "initial baseline",
            },
            {
                "iteration": "001",
                "status": "accepted",
                "exact_match_count": "2",
                "case_count": "3",
                "exact_match_rate": "0.666667",
                "regression_failed_count": "1",
                "kept_commit": "def5678",
                "description": "improved exact_match_rate",
            },
        ],
    )
    (run_root / "iteration_001").mkdir(parents=True, exist_ok=True)
    latest_payload = {
        "run_root": str(run_root),
        "run_tag": "demo-run",
        "status": "running",
        "current_iteration": "001",
        "best_exact_match_count": 2,
        "best_case_count": 3,
        "best_exact_match_rate": 0.666667,
        "best_regression_failed_count": 1,
    }

    snapshot = status.build_status_snapshot(run_root, latest_payload=latest_payload)

    assert snapshot["status"] == "running"
    assert snapshot["phase"] == "iteration_loop_running"
    assert snapshot["current_iteration"] == "001"
    assert snapshot["best_exact_match_count"] == 2
    assert snapshot["best_case_count"] == 3
    assert snapshot["best_regression_failed_count"] == 1
    assert snapshot["latest_result"]["status"] == "accepted"


def test_write_status_snapshot_updates_run_and_latest_files(tmp_path: Path, monkeypatch) -> None:
    run_root = tmp_path / "run"
    latest_status_path = tmp_path / "latest_status_snapshot.json"
    monkeypatch.setattr(status, "LATEST_STATUS_PATH", latest_status_path)
    payload = {"run_root": str(run_root), "status": "running"}

    status.write_status_snapshot(run_root, payload)

    assert json.loads((run_root / "status_snapshot.json").read_text(encoding="utf-8"))["status"] == "running"
    assert json.loads(latest_status_path.read_text(encoding="utf-8"))["run_root"] == str(run_root)
