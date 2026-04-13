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


def test_launch_baseline_run_keeps_gold_and_regression_separate(tmp_path: Path) -> None:
    payload = trigger.launch_baseline_run(
        run_root=tmp_path / "run",
        manifest_path=tmp_path / "manifest.json",
        snapshot=trigger.ManifestSnapshot(paper_count=83, entry_count=83, invalid_count=0, signature="abc"),
        signals=["ready_file:test"],
        run_tag="stage05-apr12",
        benchmark_timeout_seconds=14400,
        dry_run=True,
    )

    assert "--include-regression" not in payload["commands"]["gold_baseline"]
    assert payload["commands"]["gold_baseline"][payload["commands"]["gold_baseline"].index("--mode") + 1] == "gold"
    assert payload["commands"]["regression_baseline"][payload["commands"]["regression_baseline"].index("--mode") + 1] == "regression"


def test_loop_command_includes_run_tag_and_timeouts(tmp_path: Path) -> None:
    command = trigger.loop_command(
        run_root=tmp_path / "run",
        manifest_path=tmp_path / "manifest.json",
        codex_bin="codex",
        model="gpt-5.4",
        run_tag="stage05-apr12",
        max_iterations=12,
        agent_timeout_seconds=900,
        benchmark_timeout_seconds=1200,
    )

    assert "--run-tag" in command
    assert "stage05-apr12" in command
    assert "--codex-bin" in command
    assert "codex" in command
    assert "--model" in command
    assert "gpt-5.4" in command
    assert "--max-iterations" in command
    assert "--agent-timeout-seconds" in command
    assert "--benchmark-timeout-seconds" in command


def test_next_run_root_uses_loop_tagged_naming(tmp_path: Path) -> None:
    first = trigger.next_run_root("stage05-apr12", tmp_path)
    first.mkdir(parents=True)

    second = trigger.next_run_root("stage05-apr12", tmp_path)

    assert second.name == "stage05-apr12_02"
