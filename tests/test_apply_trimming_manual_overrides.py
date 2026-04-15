from __future__ import annotations

import json
from pathlib import Path

from src.validation import apply_trimming_manual_overrides as overrides


def test_apply_override_for_row_builds_manual_llm_output(tmp_path: Path) -> None:
    report_dir = tmp_path / "batch_050"
    report_dir.mkdir()
    (report_dir / "text_trimmed_llm").mkdir()
    final_registry_path = report_dir / "text_trim_llm_registry.csv"
    final_registry_path.write_text(
        "\n".join(
            [
                "paper_id,trimmed_text_json_path,trim_status,trim_reason,trim_method,trim_mode,title_score,author_score,match_score,start_rule,end_rule,start_page_index,end_page_index,start_line_global_index,end_line_global_index_exclusive,end_selection_mode,llm_used,llm_model,llm_api_mode,llm_prompt_version,llm_decision_type,llm_selected_candidate_id,llm_last_abstract_line_global_index,llm_confidence,llm_end_reason,llm_explanation_short,llm_validation_passed,llm_validation_reason,heuristic_fallback_used,trimmed_at_utc",
                "1001,,manual_review_required_llm_uncertain,fixture,,,,,,,,,,,,,,,,,,,,,,,,,,",
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

    report_row = {
        "paper_id": "1001",
        "title": "Target title",
        "source_text_json_path": str(source_path),
        "candidate_json_path": "qa/trimming/reports/batch_050/text_trimmed_llm_candidates/1001.json",
    }
    override_row = {
        "corrected_start_text": "Poster 237",
        "corrected_end_text": "Correct ending sentence.",
    }
    candidate_row = {
        "matched_block_code": "Poster 237",
    }

    ok, error = overrides.apply_override_for_row(report_row, override_row, candidate_row, report_dir)

    assert ok is True
    assert error == ""
    trimmed_payload = json.loads((report_dir / "text_trimmed_llm" / "1001.json").read_text(encoding="utf-8"))
    page_text = trimmed_payload["pages"][0]["text"]
    assert "Poster 237" in page_text
    assert "Correct ending sentence." in page_text
    assert "Poster 238" not in page_text
    final_registry = final_registry_path.read_text(encoding="utf-8")
    assert "trimmed_manual_override" in final_registry
    assert "manual_override_applied" in final_registry
