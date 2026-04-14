from __future__ import annotations

from pathlib import Path

from src.validation import build_source_categorisation_review_sample as review_sample


def test_resolve_repo_path_accepts_legacy_backslash_relative_paths(tmp_path: Path) -> None:
    target_path = tmp_path / "data" / "extraction_json" / "text" / "123.json"
    target_path.parent.mkdir(parents=True)
    target_path.write_text("{}", encoding="utf-8")
    original_root = review_sample.REPO_ROOT
    try:
        review_sample.REPO_ROOT = tmp_path
        resolved_path = review_sample.resolve_repo_path(r"data\extraction_json\text\123.json")
    finally:
        review_sample.REPO_ROOT = original_root

    assert resolved_path == target_path
    assert resolved_path.exists()
