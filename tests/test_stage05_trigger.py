from __future__ import annotations

from pathlib import Path

from src.autoresearch.stage_05 import trigger


def test_build_manifest_snapshot_counts_active_and_invalid() -> None:
    snapshot = trigger.build_manifest_snapshot(
        {
            "entries": [
                {"paper_id": "1", "gold_status": "active"},
                {"paper_id": "2", "gold_status": "invalid_json"},
                {"paper_id": "3", "gold_status": "active"},
            ]
        }
    )

    assert snapshot.paper_count == 2
    assert snapshot.entry_count == 3
    assert snapshot.invalid_count == 1
    assert snapshot.signature


def test_completion_signals_accept_ready_file(tmp_path: Path) -> None:
    ready_file = tmp_path / "COMPLETE"
    ready_file.write_text("", encoding="utf-8")
    snapshot = trigger.ManifestSnapshot(paper_count=5, entry_count=5, invalid_count=0, signature="abc")

    signals = trigger.completion_signals(
        snapshot,
        target_paper_count=0,
        ready_file=ready_file,
    )

    assert signals == [f"ready_file:{trigger.gold.display_path(ready_file)}"]


def test_completion_signals_accept_target_count_without_ready_file() -> None:
    snapshot = trigger.ManifestSnapshot(paper_count=12, entry_count=12, invalid_count=0, signature="abc")

    signals = trigger.completion_signals(
        snapshot,
        target_paper_count=10,
        ready_file=None,
    )

    assert signals == ["paper_count>=10"]


def test_benchmark_command_adds_include_regression_only_for_gold(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    output_dir = tmp_path / "run"

    gold_command = trigger.benchmark_command(
        mode="gold",
        output_dir=output_dir,
        manifest_path=manifest_path,
        include_regression=True,
    )
    regression_command = trigger.benchmark_command(
        mode="regression",
        output_dir=output_dir,
        manifest_path=manifest_path,
        include_regression=True,
    )

    assert "--include-regression" in gold_command
    assert "--include-regression" not in regression_command


def test_loop_command_includes_codex_and_optional_iteration_limit(tmp_path: Path) -> None:
    command = trigger.loop_command(
        run_root=tmp_path / "run",
        manifest_path=tmp_path / "manifest.json",
        codex_bin="codex",
        model="gpt-5.4",
        max_iterations=12,
    )

    assert "--codex-bin" in command
    assert "codex" in command
    assert "--model" in command
    assert "gpt-5.4" in command
    assert "--max-iterations" in command
