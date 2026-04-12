from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from src.autoresearch.stage_05 import loop


def test_goal_reached_requires_full_exact_match_and_zero_regressions(tmp_path: Path) -> None:
    state = loop.BenchmarkState(
        exact_match_count=12,
        case_count=12,
        exact_match_rate=1.0,
        regression_failed_count=0,
        mean_overlap_score=1.0,
        gold_summary_path=tmp_path / "gold.json",
        regression_summary_path=tmp_path / "regression.json",
    )

    assert loop.goal_reached(state) is True


def test_goal_reached_rejects_partial_exact_match(tmp_path: Path) -> None:
    state = loop.BenchmarkState(
        exact_match_count=11,
        case_count=12,
        exact_match_rate=0.916667,
        regression_failed_count=0,
        mean_overlap_score=0.95,
        gold_summary_path=tmp_path / "gold.json",
        regression_summary_path=tmp_path / "regression.json",
    )

    assert loop.goal_reached(state) is False


def test_candidate_beats_best_on_exact_match_rate(tmp_path: Path) -> None:
    best = loop.BenchmarkState(8, 10, 0.8, 0, 0.8, tmp_path / "gold_best.json", tmp_path / "reg_best.json")
    candidate = loop.BenchmarkState(9, 10, 0.9, 1, 0.82, tmp_path / "gold_new.json", tmp_path / "reg_new.json")

    assert loop.candidate_beats_best(candidate, best) is True


def test_candidate_beats_best_on_regression_tiebreak_only(tmp_path: Path) -> None:
    best = loop.BenchmarkState(9, 10, 0.9, 2, 0.91, tmp_path / "gold_best.json", tmp_path / "reg_best.json")
    candidate = loop.BenchmarkState(9, 10, 0.9, 1, 0.90, tmp_path / "gold_new.json", tmp_path / "reg_new.json")

    assert loop.candidate_beats_best(candidate, best) is True


def test_candidate_beats_best_on_simplification_tie(tmp_path: Path) -> None:
    best = loop.BenchmarkState(9, 10, 0.9, 1, 0.91, tmp_path / "gold_best.json", tmp_path / "reg_best.json")
    candidate = loop.BenchmarkState(9, 10, 0.9, 1, 0.90, tmp_path / "gold_new.json", tmp_path / "reg_new.json")
    diff_stat = loop.DiffStat(changed_paths=("src/pipelines/_proceedings_text_autoresearch.py",), insertions=2, deletions=5)

    assert loop.candidate_beats_best(candidate, best, diff_stat) is True


def test_candidate_does_not_beat_best_on_exact_tie_without_simplification(tmp_path: Path) -> None:
    best = loop.BenchmarkState(9, 10, 0.9, 1, 0.91, tmp_path / "gold_best.json", tmp_path / "reg_best.json")
    candidate = loop.BenchmarkState(9, 10, 0.9, 1, 0.95, tmp_path / "gold_new.json", tmp_path / "reg_new.json")
    diff_stat = loop.DiffStat(changed_paths=("src/pipelines/_proceedings_text_autoresearch.py",), insertions=5, deletions=2)

    assert loop.candidate_beats_best(candidate, best, diff_stat) is False


def test_default_run_tag_uses_stage05_date_slug() -> None:
    timestamp = datetime(2026, 4, 12, tzinfo=timezone.utc)

    assert loop.default_run_tag(timestamp) == "stage05-apr12"


def test_resolve_run_tag_uses_run_root_name_when_missing(tmp_path: Path) -> None:
    run_root = tmp_path / "Stage 05 Apr12"

    assert loop.resolve_run_tag("", run_root) == "stage-05-apr12"


def test_next_run_root_suffixes_duplicate_tags(tmp_path: Path) -> None:
    first = loop.next_run_root("stage05-apr12", tmp_path)
    first.mkdir(parents=True)

    second = loop.next_run_root("stage05-apr12", tmp_path)

    assert second.name == "stage05-apr12_02"
