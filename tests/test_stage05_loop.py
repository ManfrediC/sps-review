from __future__ import annotations

import sys
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


def test_run_benchmarks_keeps_regression_as_a_separate_step(tmp_path: Path, monkeypatch) -> None:
    commands: list[list[str]] = []
    state = loop.BenchmarkState(
        exact_match_count=1,
        case_count=1,
        exact_match_rate=1.0,
        regression_failed_count=0,
        mean_overlap_score=1.0,
        gold_summary_path=tmp_path / "gold.json",
        regression_summary_path=tmp_path / "regression.json",
    )

    def fake_run_logged_command(
        command: list[str],
        *,
        stdout_path: Path,
        stderr_path: Path,
        timeout_seconds: int,
        input_text: str | None = None,
    ) -> loop.CommandResult:
        commands.append(command)
        return loop.CommandResult(tuple(command), stdout_path, stderr_path, 0, False, timeout_seconds)

    monkeypatch.setattr(loop, "run_logged_command", fake_run_logged_command)
    monkeypatch.setattr(loop, "benchmark_state_from_paths", lambda gold_path, regression_path: state)

    run = loop.run_benchmarks(tmp_path / "run", tmp_path / "manifest.json", 90)

    assert run.state == state
    assert len(commands) == 2
    assert "--include-regression" not in commands[0]
    assert commands[0][commands[0].index("--mode") + 1] == "gold"
    assert commands[1][commands[1].index("--mode") + 1] == "regression"


def test_run_logged_command_marks_timeout_and_writes_note(tmp_path: Path) -> None:
    stdout_path = tmp_path / "stdout.log"
    stderr_path = tmp_path / "stderr.log"

    result = loop.run_logged_command(
        [sys.executable, "-c", "import time; time.sleep(5)"],
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        timeout_seconds=1,
    )

    assert result.timed_out is True
    assert result.returncode is None
    assert "timed out after 1 seconds" in stderr_path.read_text(encoding="utf-8")
