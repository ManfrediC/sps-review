from __future__ import annotations

import json
from pathlib import Path

from src.autoresearch.stage_05 import gold as stage05_gold


def write_trimmed_json(path: Path, lines: list[str], **extra_fields: object) -> None:
    payload: dict[str, object] = {
        "paper_id": path.stem,
        "pages": [{"page_index": 0, "text": "\n".join(lines)}],
    }
    payload.update(extra_fields)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def test_sync_manifest_reads_direct_gold_jsons_and_provenance(tmp_path: Path) -> None:
    gold_papers_dir = tmp_path / "gold_standard" / "papers"
    gold_path = gold_papers_dir / "991001.json"
    write_trimmed_json(
        gold_path,
        ["Poster 1", "Abstract body", "Conclusions: Accepted ending."],
        source_text_path="data/extraction_json/text/991001.json",
        reviewer="mf",
        notes="good gold fixture",
    )

    payload = stage05_gold.sync_manifest(
        gold_papers_dir=gold_papers_dir,
        manifest_path=tmp_path / "gold_standard" / "manifest.json",
    )

    assert payload["paper_count"] == 1
    entry = payload["entries"][0]
    assert entry["paper_id"] == "991001"
    assert entry["gold_status"] == "active"
    assert entry["source_text_path"] == "data/extraction_json/text/991001.json"
    assert entry["reviewer"] == "mf"
    assert entry["notes"] == "good gold fixture"
    assert entry["gold_first_line"] == "Poster 1"
    assert entry["gold_last_line"] == "Conclusions: Accepted ending."
    assert entry["raw_text_hash"]
    assert entry["normalised_text_hash"]


def test_sync_manifest_falls_back_to_source_text_json_path(tmp_path: Path) -> None:
    gold_papers_dir = tmp_path / "gold_standard" / "papers"
    gold_path = gold_papers_dir / "991002.json"
    write_trimmed_json(
        gold_path,
        ["Poster 2", "Body", "Conclusion: End."],
        source_text_json_path="data/extraction_json/text/991002.json",
        reviewer_id="reviewer-2",
        review_notes="fallback fields",
    )

    payload = stage05_gold.sync_manifest(
        gold_papers_dir=gold_papers_dir,
        manifest_path=tmp_path / "gold_standard" / "manifest.json",
    )

    entry = payload["entries"][0]
    assert entry["source_text_path"] == "data/extraction_json/text/991002.json"
    assert entry["reviewer"] == "reviewer-2"
    assert entry["notes"] == "fallback fields"


def test_sync_manifest_marks_invalid_json(tmp_path: Path) -> None:
    gold_papers_dir = tmp_path / "gold_standard" / "papers"
    bad_path = gold_papers_dir / "991003.json"
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_text("{not valid json", encoding="utf-8")

    payload = stage05_gold.sync_manifest(
        gold_papers_dir=gold_papers_dir,
        manifest_path=tmp_path / "gold_standard" / "manifest.json",
    )

    entry = payload["entries"][0]
    assert entry["paper_id"] == "991003"
    assert entry["gold_status"] == "invalid_json"
    assert entry["raw_text_hash"] == ""
    assert entry["normalised_text_hash"] == ""


def test_active_entries_by_id_returns_only_active_rows(tmp_path: Path) -> None:
    manifest_path = tmp_path / "gold_standard" / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "generated_at_utc": "2026-04-11T00:00:00+00:00",
                "paper_count": 1,
                "entries": [
                    {"paper_id": "10", "gold_status": "active", "gold_json_path": "qa/trimming/gold_standard/papers/10.json"},
                    {"paper_id": "11", "gold_status": "invalid_json", "gold_json_path": "qa/trimming/gold_standard/papers/11.json"},
                ],
            }
        ),
        encoding="utf-8",
    )

    active = stage05_gold.active_entries_by_id(manifest_path)

    assert list(active) == ["10"]


def test_strict_normalise_text_is_minimal(tmp_path: Path) -> None:
    text = "Poster\u00ad 1\r\nLine   two\n\nLine three"

    normalized = stage05_gold.strict_normalise_text(text)

    assert normalized == "Poster 1 Line two Line three"
