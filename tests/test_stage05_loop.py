from __future__ import annotations

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


def test_candidate_does_not_beat_best_on_exact_tie_and_equal_regressions(tmp_path: Path) -> None:
    best = loop.BenchmarkState(9, 10, 0.9, 1, 0.91, tmp_path / "gold_best.json", tmp_path / "reg_best.json")
    candidate = loop.BenchmarkState(9, 10, 0.9, 1, 0.95, tmp_path / "gold_new.json", tmp_path / "reg_new.json")

    assert loop.candidate_beats_best(candidate, best) is False
