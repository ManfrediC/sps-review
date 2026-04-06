from __future__ import annotations

import json
from pathlib import Path

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
        json.dumps({"batch_id": "batch_001", "status": "awaiting_feedback"}),
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
