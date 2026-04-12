from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.autoresearch.stage_05 import benchmark
from src.autoresearch.stage_05 import gold
from src.autoresearch.stage_05 import loop


READY_FILE = gold.GOLD_STANDARD_DIR / "COMPLETE"
TRIGGER_RUNS_DIR = benchmark.AUTORESEARCH_ROOT / "trigger_runs"
LATEST_RUN_PATH = benchmark.AUTORESEARCH_ROOT / "latest_trigger_run.json"


@dataclass(frozen=True)
class ManifestSnapshot:
    paper_count: int
    entry_count: int
    invalid_count: int
    signature: str


def build_manifest_snapshot(payload: dict[str, Any]) -> ManifestSnapshot:
    entries = payload.get("entries") or []
    active_count = sum(1 for entry in entries if str(entry.get("gold_status") or "").strip() == "active")
    invalid_count = sum(1 for entry in entries if str(entry.get("gold_status") or "").strip() == "invalid_json")
    signature = json.dumps(entries, ensure_ascii=False, sort_keys=True)
    return ManifestSnapshot(
        paper_count=active_count,
        entry_count=len(entries),
        invalid_count=invalid_count,
        signature=signature,
    )


def completion_signals(
    snapshot: ManifestSnapshot,
    *,
    target_paper_count: int,
    ready_file: Path | None,
) -> list[str]:
    signals: list[str] = []
    if target_paper_count > 0 and snapshot.paper_count >= target_paper_count:
        signals.append(f"paper_count>={target_paper_count}")
    if ready_file is not None and ready_file.exists():
        signals.append(f"ready_file:{gold.display_path(ready_file)}")
    return signals


def benchmark_command(
    *,
    mode: str,
    output_dir: Path,
    manifest_path: Path,
    include_regression: bool = False,
) -> list[str]:
    command = [
        sys.executable,
        str(Path(benchmark.__file__).resolve()),
        "--mode",
        mode,
        "--output-dir",
        str(output_dir),
        "--manifest-path",
        str(manifest_path),
    ]
    if include_regression and mode == "gold":
        command.append("--include-regression")
    return command


def loop_command(
    *,
    run_root: Path,
    manifest_path: Path,
    codex_bin: str,
    model: str,
    max_iterations: int,
) -> list[str]:
    command = [
        sys.executable,
        str(Path(loop.__file__).resolve()),
        "--run-root",
        str(run_root),
        "--manifest-path",
        str(manifest_path),
        "--codex-bin",
        codex_bin,
    ]
    if model:
        command.extend(["--model", model])
    if max_iterations != 0:
        command.extend(["--max-iterations", str(max_iterations)])
    return command


def run_command(command: list[str]) -> None:
    subprocess.run(command, check=True, cwd=str(gold.REPO_ROOT))


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def next_run_root(root_dir: Path = TRIGGER_RUNS_DIR) -> Path:
    root_dir.mkdir(parents=True, exist_ok=True)
    base = root_dir / timestamp_slug()
    if not base.exists():
        return base
    suffix = 2
    while True:
        candidate = root_dir / f"{base.name}_{suffix:02d}"
        if not candidate.exists():
            return candidate
        suffix += 1


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def sync_manifest_and_snapshot(
    *,
    gold_papers_dir: Path,
    manifest_path: Path,
) -> tuple[dict[str, Any], ManifestSnapshot]:
    payload = gold.sync_manifest(gold_papers_dir=gold_papers_dir, manifest_path=manifest_path)
    return payload, build_manifest_snapshot(payload)


def wait_until_ready(
    *,
    gold_papers_dir: Path,
    manifest_path: Path,
    target_paper_count: int,
    ready_file: Path | None,
    poll_seconds: int,
    stable_polls: int,
) -> tuple[dict[str, Any], ManifestSnapshot, list[str]]:
    if target_paper_count <= 0 and ready_file is None:
        raise SystemExit("Provide --target-paper-count, --ready-file, or both so the trigger knows when to launch.")

    last_ready_key = ""
    ready_streak = 0

    while True:
        payload, snapshot = sync_manifest_and_snapshot(
            gold_papers_dir=gold_papers_dir,
            manifest_path=manifest_path,
        )
        signals = completion_signals(
            snapshot,
            target_paper_count=target_paper_count,
            ready_file=ready_file,
        )
        ready = bool(signals) and snapshot.invalid_count == 0
        ready_key = ""
        if ready:
            ready_key = f"{snapshot.signature}|{'|'.join(signals)}"
            ready_streak = ready_streak + 1 if ready_key == last_ready_key else 1
            last_ready_key = ready_key
        else:
            ready_streak = 0
            last_ready_key = ""

        signal_text = ", ".join(signals) if signals else "waiting"
        print(
            f"[trigger] active={snapshot.paper_count} entries={snapshot.entry_count} "
            f"invalid={snapshot.invalid_count} ready={ready_streak}/{stable_polls} signals={signal_text}",
            flush=True,
        )
        if ready_streak >= stable_polls:
            return payload, snapshot, signals
        time.sleep(max(1, poll_seconds))


def launch_baseline_run(
    *,
    run_root: Path,
    manifest_path: Path,
    snapshot: ManifestSnapshot,
    signals: list[str],
    dry_run: bool,
) -> dict[str, Any]:
    gold_output_dir = run_root / "gold_baseline"
    regression_output_dir = run_root / "regression_baseline"
    gold_command = benchmark_command(
        mode="gold",
        output_dir=gold_output_dir,
        manifest_path=manifest_path,
        include_regression=True,
    )
    regression_command = benchmark_command(
        mode="regression",
        output_dir=regression_output_dir,
        manifest_path=manifest_path,
    )

    payload = {
        "generated_at_utc": gold.now_utc_iso(),
        "status": "planned" if dry_run else "started",
        "run_root": gold.display_path(run_root),
        "manifest_path": gold.display_path(manifest_path),
        "paper_count": snapshot.paper_count,
        "entry_count": snapshot.entry_count,
        "invalid_count": snapshot.invalid_count,
        "completion_signals": signals,
        "commands": {
            "gold_baseline": gold_command,
            "regression_baseline": regression_command,
        },
        "summary_paths": {
            "gold_baseline": gold.display_path(gold_output_dir / "summary.json"),
            "regression_baseline": gold.display_path(regression_output_dir / "summary.json"),
        },
    }
    write_json(run_root / "trigger_summary.json", payload)
    write_json(LATEST_RUN_PATH, payload)

    if not dry_run:
        run_command(gold_command)
        run_command(regression_command)
        payload["generated_at_utc"] = gold.now_utc_iso()
        payload["status"] = "completed"
        write_json(run_root / "trigger_summary.json", payload)
        write_json(LATEST_RUN_PATH, payload)
    return payload


def launch_loop_run(
    *,
    run_root: Path,
    manifest_path: Path,
    snapshot: ManifestSnapshot,
    signals: list[str],
    codex_bin: str,
    model: str,
    max_iterations: int,
    dry_run: bool,
) -> dict[str, Any]:
    command = loop_command(
        run_root=run_root,
        manifest_path=manifest_path,
        codex_bin=codex_bin,
        model=model,
        max_iterations=max_iterations,
    )
    payload = {
        "generated_at_utc": gold.now_utc_iso(),
        "status": "planned" if dry_run else "started",
        "launch_mode": "loop",
        "run_root": gold.display_path(run_root),
        "manifest_path": gold.display_path(manifest_path),
        "paper_count": snapshot.paper_count,
        "entry_count": snapshot.entry_count,
        "invalid_count": snapshot.invalid_count,
        "completion_signals": signals,
        "command": command,
        "loop_summary_path": gold.display_path(run_root / "loop_summary.json"),
        "results_path": gold.display_path(run_root / "results.tsv"),
    }
    write_json(run_root / "trigger_summary.json", payload)
    write_json(LATEST_RUN_PATH, payload)
    if not dry_run:
        run_command(command)
        loop_summary_path = run_root / "loop_summary.json"
        loop_summary = json.loads(loop_summary_path.read_text(encoding="utf-8")) if loop_summary_path.exists() else {}
        payload["generated_at_utc"] = gold.now_utc_iso()
        payload["status"] = "completed"
        payload["loop_status"] = str(loop_summary.get("status") or "")
        payload["loop_stop_reason"] = str(loop_summary.get("stop_reason") or "")
        write_json(run_root / "trigger_summary.json", payload)
        write_json(LATEST_RUN_PATH, payload)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wait for the stage-05 gold set to be complete, then launch the stage-05 autoresearch workflow."
    )
    parser.add_argument(
        "--gold-papers-dir",
        type=Path,
        default=gold.GOLD_PAPERS_DIR,
        help="Directory containing gold-standard per-paper JSONs.",
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=gold.MANIFEST_PATH,
        help="Manifest path to keep synced while waiting.",
    )
    parser.add_argument(
        "--ready-file",
        type=Path,
        default=READY_FILE,
        help="Explicit completion marker. The trigger launches when this file exists.",
    )
    parser.add_argument(
        "--target-paper-count",
        type=int,
        default=0,
        help="Optional automatic launch threshold based on active gold manifest count.",
    )
    parser.add_argument(
        "--poll-seconds",
        type=int,
        default=60,
        help="Polling interval while waiting for completion.",
    )
    parser.add_argument(
        "--stable-polls",
        type=int,
        default=2,
        help="Require the ready condition to hold for this many consecutive manifest syncs before launching.",
    )
    parser.add_argument(
        "--run-root",
        type=Path,
        default=None,
        help="Optional explicit output directory. Defaults to a timestamped folder under qa/trimming/gold_standard/autoresearch/trigger_runs/.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Wait for readiness and write the planned launch summary without starting the selected workflow.",
    )
    parser.add_argument(
        "--launch-mode",
        choices=("baseline", "loop"),
        default="loop",
        help="Workflow to start once the gold set is ready.",
    )
    parser.add_argument(
        "--codex-bin",
        default="codex",
        help="Codex CLI executable to use when --launch-mode loop.",
    )
    parser.add_argument(
        "--model",
        default="",
        help="Optional model override passed through to the stage-05 loop.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=0,
        help="Maximum loop iterations after baseline when --launch-mode loop. Use 0 for no fixed limit.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    _, snapshot, signals = wait_until_ready(
        gold_papers_dir=args.gold_papers_dir,
        manifest_path=args.manifest_path,
        target_paper_count=args.target_paper_count,
        ready_file=args.ready_file,
        poll_seconds=args.poll_seconds,
        stable_polls=max(1, args.stable_polls),
    )
    run_root = args.run_root or next_run_root()
    if args.launch_mode == "baseline":
        payload = launch_baseline_run(
            run_root=run_root,
            manifest_path=args.manifest_path,
            snapshot=snapshot,
            signals=signals,
            dry_run=args.dry_run,
        )
    else:
        payload = launch_loop_run(
            run_root=run_root,
            manifest_path=args.manifest_path,
            snapshot=snapshot,
            signals=signals,
            codex_bin=args.codex_bin,
            model=args.model,
            max_iterations=args.max_iterations,
            dry_run=args.dry_run,
        )
    print(f"Trigger status: {payload['status']}")
    print(f"Run root: {payload['run_root']}")
    print(f"Trigger summary: {gold.display_path(run_root / 'trigger_summary.json')}")


if __name__ == "__main__":
    main()
