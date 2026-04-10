from __future__ import annotations

import json
from pathlib import Path

from src.validation import apply_trimming_manual_overrides as overrides


def test_apply_override_for_row_builds_manual_trimmed_output(tmp_path: Path) -> None:
    report_dir = tmp_path / "batch_050"
    report_dir.mkdir()
    (report_dir / "text_trimmed").mkdir()
    trim_registry_path = report_dir / "text_trim_registry.csv"
    trim_registry_path.write_text(
        "\n".join(
            [
                "paper_id,trimmed_text_json_path,trim_status,trim_reason,trim_method,trim_mode,start_page_index,end_page_index,start_line_global_index,end_line_global_index_exclusive,trimmed_at_utc",
                "1001,,manual_review_required,fixture,,,,,,,",
            ]
        ),
        encoding="utf-8",
    )
    source_path = tmp_path / "1001.json"
    source_path.write_text(
        json.dumps(
            {
                "paper_id": "1001",
                "source_filename": "1001.pdf",
                "pages": [
                    {
                        "page_index": 0,
                        "text": "\n".join(
                            [
                                "Earlier abstract",
                                "Poster 237",
                                "Target title",
                                "Important result line",
                                "Correct ending sentence.",
                                "Poster 238",
                                "Next title",
                            ]
                        ),
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    queue_row = {
        "paper_id": "1001",
        "title": "Target title",
        "source_text_json_path": str(source_path),
    }
    override_row = {
        "corrected_start_text": "Poster 237",
        "corrected_end_text": "Correct ending sentence.",
    }

    ok, error = overrides.apply_override_for_row(queue_row, override_row, report_dir)

    assert ok is True
    assert error == ""
    trimmed_payload = json.loads((report_dir / "text_trimmed" / "1001.json").read_text(encoding="utf-8"))
    page_text = trimmed_payload["pages"][0]["text"]
    assert "Poster 237" in page_text
    assert "Correct ending sentence." in page_text
    assert "Poster 238" not in page_text
    trim_registry = trim_registry_path.read_text(encoding="utf-8")
    assert "trimmed_manual_override" in trim_registry
