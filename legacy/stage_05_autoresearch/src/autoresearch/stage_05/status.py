from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.autoresearch.stage_05 import benchmark, gold

LATEST_LOOP_PATH = benchmark.AUTORESEARCH_ROOT / "latest_loop_run.json"
LATEST_STATUS_PATH = benchmark.AUTORESEARCH_ROOT / "latest_status_snapshot.json"
RUNS_DIR = benchmark.AUTORESEARCH_ROOT / "runs"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_json_if_exists(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    return load_json(path)


def load_results_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def repo_or_absolute_path(path_text: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        return path
    return gold.REPO_ROOT / path


def resolve_run_root(explicit_run_root: Path | None, latest_payload: dict[str, Any] | None) -> Path:
    if explicit_run_root is not None:
        return explicit_run_root
    if latest_payload:
        run_root_text = str(latest_payload.get("run_root") or "").strip()
        if run_root_text:
            return repo_or_absolute_path(run_root_text)
    run_dirs = [path for path in RUNS_DIR.iterdir() if path.is_dir()] if RUNS_DIR.exists() else []
    if not run_dirs:
        raise SystemExit("No stage-05 autoresearch run directory was found.")
    return max(run_dirs, key=lambda path: path.stat().st_mtime)


def payload_matches_run_root(payload: dict[str, Any] | None, run_root: Path) -> bool:
    if not payload:
        return False
    run_root_text = str(payload.get("run_root") or "").strip()
    if not run_root_text:
        return False
    return repo_or_absolute_path(run_root_text).resolve() == run_root.resolve()


def manifest_case_count(manifest_path: Path) -> int:
    if not manifest_path.exists():
        return 0
    payload = load_json(manifest_path)
    paper_count = payload.get("paper_count")
    if isinstance(paper_count, int):
        return paper_count
    entries = payload.get("entries")
    return len(entries) if isinstance(entries, list) else 0


def summary_exact_match_count(summary_payload: dict[str, Any] | None) -> int | None:
    if not summary_payload:
        return None
    value = summary_payload.get("exact_match_count")
    if isinstance(value, int):
        return value
    label_counts = summary_payload.get("label_counts")
    if isinstance(label_counts, dict):
        exact_match = label_counts.get("exact_match")
        if isinstance(exact_match, int):
            return exact_match
    return None


def count_json_files(directory: Path) -> int:
    if not directory.exists():
        return 0
    return sum(1 for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".json")


def latest_update_utc(run_root: Path) -> str:
    latest_timestamp = 0.0
    for path in run_root.rglob("*"):
        if path.is_file():
            latest_timestamp = max(latest_timestamp, path.stat().st_mtime)
    if latest_timestamp <= 0:
        latest_timestamp = run_root.stat().st_mtime
    return datetime.fromtimestamp(latest_timestamp, timezone.utc).isoformat()


def infer_phase(
    *,
    loop_summary: dict[str, Any] | None,
    latest_payload: dict[str, Any] | None,
    results_rows: list[dict[str, str]],
    baseline_gold_summary: dict[str, Any] | None,
    baseline_regression_summary: dict[str, Any] | None,
    gold_output_count: int,
    regression_output_count: int,
    baseline_gold_started: bool,
    baseline_regression_started: bool,
    loop_config_exists: bool,
) -> str:
    terminal_status = str((loop_summary or {}).get("status") or "").strip()
    if terminal_status in {"completed", "blocked", "stopped"}:
        return terminal_status
    if results_rows:
        return "iteration_loop_running"
    if baseline_regression_summary:
        return "baseline_complete"
    if baseline_gold_summary or regression_output_count > 0 or baseline_regression_started:
        return "baseline_regression_running"
    if gold_output_count > 0 or baseline_gold_started:
        return "baseline_gold_running"
    if loop_config_exists:
        return "starting"
    if latest_payload:
        return "running"
    return "unknown"


def build_status_snapshot(run_root: Path, *, latest_payload: dict[str, Any] | None = None) -> dict[str, Any]:
    loop_config = load_json_if_exists(run_root / "loop_config.json") or {}
    loop_summary = load_json_if_exists(run_root / "loop_summary.json")
    results_rows = load_results_rows(run_root / "results.tsv")
    baseline_gold_summary = load_json_if_exists(run_root / "baseline" / "gold" / "summary.json")
    baseline_regression_summary = load_json_if_exists(run_root / "baseline" / "regression" / "summary.json")

    baseline_gold_dir = run_root / "baseline" / "gold" / "text_trimmed"
    baseline_regression_dir = run_root / "baseline" / "regression" / "text_trimmed"
    baseline_gold_started = (run_root / "baseline" / "gold").exists()
    baseline_regression_started = (run_root / "baseline" / "regression").exists()
    gold_output_count = count_json_files(baseline_gold_dir)
    regression_output_count = count_json_files(baseline_regression_dir)

    active_latest_payload = latest_payload if payload_matches_run_root(latest_payload, run_root) else None
    active_payload = loop_summary or active_latest_payload or {}

    manifest_path_text = str(loop_config.get("manifest_path") or active_payload.get("manifest_path") or "").strip()
    manifest_path = repo_or_absolute_path(manifest_path_text) if manifest_path_text else gold.MANIFEST_PATH
    expected_case_count = manifest_case_count(manifest_path)

    best_exact_match_count = active_payload.get("best_exact_match_count")
    if not isinstance(best_exact_match_count, int):
        best_exact_match_count = summary_exact_match_count(baseline_gold_summary)
    best_case_count = active_payload.get("best_case_count")
    if not isinstance(best_case_count, int):
        best_case_count = baseline_gold_summary.get("case_count") if baseline_gold_summary else expected_case_count
    best_exact_match_rate = active_payload.get("best_exact_match_rate")
    if not isinstance(best_exact_match_rate, (int, float)) and baseline_gold_summary:
        best_exact_match_rate = baseline_gold_summary.get("exact_match_rate")
    best_regression_failed_count = active_payload.get("best_regression_failed_count")
    if not isinstance(best_regression_failed_count, int) and baseline_gold_summary:
        best_regression_failed_count = baseline_gold_summary.get("regression_failed_count")

    status_text = str(active_payload.get("status") or "").strip() or ("running" if loop_config else "unknown")
    current_iteration = str(active_payload.get("current_iteration") or "").strip()
    stop_reason = str(active_payload.get("stop_reason") or "").strip()
    phase = infer_phase(
        loop_summary=loop_summary,
        latest_payload=active_latest_payload,
        results_rows=results_rows,
        baseline_gold_summary=baseline_gold_summary,
        baseline_regression_summary=baseline_regression_summary,
        gold_output_count=gold_output_count,
        regression_output_count=regression_output_count,
        baseline_gold_started=baseline_gold_started,
        baseline_regression_started=baseline_regression_started,
        loop_config_exists=bool(loop_config),
    )

    iteration_dirs = sorted(
        path.name for path in run_root.iterdir() if path.is_dir() and path.name.startswith("iteration_")
    ) if run_root.exists() else []
    latest_result = results_rows[-1] if results_rows else {}

    snapshot = {
        "generated_at_utc": benchmark.now_utc_iso(),
        "run_root": gold.display_path(run_root),
        "run_tag": str(loop_config.get("run_tag") or active_payload.get("run_tag") or run_root.name),
        "status": status_text,
        "phase": phase,
        "current_iteration": current_iteration,
        "stop_reason": stop_reason,
        "manifest_path": gold.display_path(manifest_path),
        "expected_case_count": expected_case_count,
        "best_exact_match_count": best_exact_match_count if isinstance(best_exact_match_count, int) else None,
        "best_case_count": best_case_count if isinstance(best_case_count, int) else None,
        "best_exact_match_rate": round(float(best_exact_match_rate), 6)
        if isinstance(best_exact_match_rate, (int, float))
        else None,
        "best_regression_failed_count": best_regression_failed_count
        if isinstance(best_regression_failed_count, int)
        else None,
        "baseline_gold_output_count": gold_output_count,
        "baseline_regression_output_count": regression_output_count,
        "baseline_gold_summary_exists": baseline_gold_summary is not None,
        "baseline_regression_summary_exists": baseline_regression_summary is not None,
        "iteration_count": len(iteration_dirs),
        "latest_iteration_dir": iteration_dirs[-1] if iteration_dirs else "",
        "results_row_count": len(results_rows),
        "latest_result": latest_result,
        "last_update_utc": latest_update_utc(run_root),
        "status_snapshot_path": gold.display_path(run_root / "status_snapshot.json"),
    }
    if baseline_gold_summary and isinstance(baseline_gold_summary.get("label_counts"), dict):
        snapshot["baseline_gold_label_counts"] = baseline_gold_summary["label_counts"]
    return snapshot


def write_status_snapshot(run_root: Path, payload: dict[str, Any]) -> None:
    write_json(run_root / "status_snapshot.json", payload)
    write_json(LATEST_STATUS_PATH, payload)


def print_text_summary(snapshot: dict[str, Any]) -> None:
    print(f"Run root: {snapshot['run_root']}")
    print(f"Run tag: {snapshot['run_tag']}")
    print(f"Status: {snapshot['status']}")
    print(f"Phase: {snapshot['phase']}")
    if snapshot["current_iteration"]:
        print(f"Current iteration: {snapshot['current_iteration']}")
    if snapshot["best_case_count"]:
        best_exact_match_count = snapshot["best_exact_match_count"]
        exact_match_text = f"{best_exact_match_count if best_exact_match_count is not None else '?'}/{snapshot['best_case_count']}"
        if snapshot["best_exact_match_rate"] is not None:
            exact_match_text = f"{exact_match_text} ({snapshot['best_exact_match_rate']:.6f})"
        print(f"Best exact match: {exact_match_text}")
    if snapshot["best_regression_failed_count"] is not None:
        print(f"Best regression failed count: {snapshot['best_regression_failed_count']}")
    print(
        "Baseline outputs: "
        f"gold={snapshot['baseline_gold_output_count']}/{snapshot['expected_case_count']} "
        f"regression={snapshot['baseline_regression_output_count']}"
    )
    print(f"Iteration count: {snapshot['iteration_count']}")
    if snapshot["latest_result"]:
        print(
            "Latest ledger row: "
            f"{snapshot['latest_result'].get('iteration', '')} "
            f"{snapshot['latest_result'].get('status', '')} "
            f"{snapshot['latest_result'].get('description', '')}".strip()
        )
    print(f"Last update: {snapshot['last_update_utc']}")
    print(f"Status snapshot: {snapshot['status_snapshot_path']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarise a live or completed stage-05 autoresearch run.")
    parser.add_argument(
        "--run-root",
        type=Path,
        default=None,
        help="Optional explicit run directory. Defaults to the latest loop payload or newest run directory.",
    )
    parser.add_argument(
        "--latest-loop-json",
        type=Path,
        default=LATEST_LOOP_PATH,
        help="Path to the latest loop payload JSON.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full JSON snapshot instead of the concise text summary.",
    )
    parser.add_argument(
        "--no-write",
        action="store_true",
        help="Do not write status_snapshot.json files.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    latest_payload = load_json_if_exists(args.latest_loop_json)
    run_root = resolve_run_root(args.run_root, latest_payload)
    snapshot = build_status_snapshot(run_root, latest_payload=latest_payload)
    if not args.no_write:
        write_status_snapshot(run_root, snapshot)
    if args.json:
        print(json.dumps(snapshot, ensure_ascii=False, indent=2))
        return
    print_text_summary(snapshot)


if __name__ == "__main__":
    main()
