from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.autoresearch.stage_05 import benchmark
from src.autoresearch.stage_05 import gold


EDITABLE_FILES = (
    gold.REPO_ROOT / "src" / "pipelines" / "_proceedings_text_autoresearch.py",
    gold.REPO_ROOT / "src" / "pipelines" / "05_trim_proceedings_text_autoresearch.py",
)
PROGRAM_PATH = gold.REPO_ROOT / "src" / "autoresearch" / "stage_05" / "program.md"
RUNS_DIR = benchmark.AUTORESEARCH_ROOT / "runs"
LATEST_RUN_PATH = benchmark.AUTORESEARCH_ROOT / "latest_loop_run.json"
RESULTS_HEADER = [
    "iteration",
    "status",
    "exact_match_count",
    "case_count",
    "exact_match_rate",
    "regression_failed_count",
    "mean_overlap_score",
    "gold_summary_path",
    "regression_summary_path",
    "changed_paths",
    "notes",
]


@dataclass(frozen=True)
class BenchmarkState:
    exact_match_count: int
    case_count: int
    exact_match_rate: float
    regression_failed_count: int
    mean_overlap_score: float
    gold_summary_path: Path
    regression_summary_path: Path


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_results_row(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=RESULTS_HEADER, delimiter="\t")
        if not exists:
            writer.writeheader()
        writer.writerow({field: row.get(field, "") for field in RESULTS_HEADER})


def timestamp_slug() -> str:
    return benchmark.now_utc_iso().replace(":", "").replace("-", "").replace("+00:00", "Z")


def next_run_root(root_dir: Path = RUNS_DIR) -> Path:
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


def run_command(command: list[str], *, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        cwd=str(gold.REPO_ROOT),
        input=input_text,
        text=True,
        capture_output=False,
    )


def capture_command(command: list[str]) -> str:
    return subprocess.run(
        command,
        check=True,
        cwd=str(gold.REPO_ROOT),
        text=True,
        capture_output=True,
    ).stdout


def git_status_map() -> dict[str, str]:
    output = capture_command(["git", "status", "--porcelain=v1"])
    status_map: dict[str, str] = {}
    for raw_line in output.splitlines():
        if len(raw_line) < 4:
            continue
        status = raw_line[:2]
        path = raw_line[3:]
        status_map[path] = status
    return status_map


def relative_repo_paths(paths: tuple[Path, ...] = EDITABLE_FILES) -> list[str]:
    return [str(path.relative_to(gold.REPO_ROOT)).replace("\\", "/") for path in paths]


def ensure_editable_files_clean() -> None:
    output = capture_command(["git", "status", "--porcelain=v1", "--", *relative_repo_paths()])
    if output.strip():
        raise SystemExit(
            "Editable autoresearch files are already dirty. Clean or commit them before starting the stage-05 loop."
        )


def changed_paths_since_initial(initial_status: dict[str, str]) -> list[str]:
    current = git_status_map()
    changed = sorted(
        path
        for path in set(initial_status) | set(current)
        if initial_status.get(path, "") != current.get(path, "")
    )
    return changed


def editable_diff_exists() -> bool:
    diff_output = capture_command(["git", "status", "--porcelain=v1", "--", *relative_repo_paths()])
    return bool(diff_output.strip())


def restore_editable_files() -> None:
    run_command(["git", "restore", "--staged", "--worktree", "--source=HEAD", "--", *relative_repo_paths()])


def commit_editable_files(message: str) -> None:
    run_command(["git", "add", "--", *relative_repo_paths()])
    run_command(["git", "commit", "-m", message])


def benchmark_state_from_paths(gold_summary_path: Path, regression_summary_path: Path) -> BenchmarkState:
    gold_summary = json.loads(gold_summary_path.read_text(encoding="utf-8"))
    regression_summary = json.loads(regression_summary_path.read_text(encoding="utf-8"))
    label_counts = gold_summary.get("label_counts") or {}
    return BenchmarkState(
        exact_match_count=int(label_counts.get("exact_match") or 0),
        case_count=int(gold_summary.get("case_count") or 0),
        exact_match_rate=float(gold_summary.get("exact_match_rate") or 0.0),
        regression_failed_count=int(regression_summary.get("failed_count") or 0),
        mean_overlap_score=float(gold_summary.get("mean_overlap_score") or 0.0),
        gold_summary_path=gold_summary_path,
        regression_summary_path=regression_summary_path,
    )


def run_benchmarks(run_root: Path, manifest_path: Path) -> BenchmarkState:
    gold_dir = run_root / "gold"
    regression_dir = run_root / "regression"
    run_command(
        [
            sys.executable,
            str(Path(benchmark.__file__).resolve()),
            "--mode",
            "gold",
            "--include-regression",
            "--output-dir",
            str(gold_dir),
            "--manifest-path",
            str(manifest_path),
        ]
    )
    run_command(
        [
            sys.executable,
            str(Path(benchmark.__file__).resolve()),
            "--mode",
            "regression",
            "--output-dir",
            str(regression_dir),
            "--manifest-path",
            str(manifest_path),
        ]
    )
    return benchmark_state_from_paths(gold_dir / "summary.json", regression_dir / "summary.json")


def goal_reached(state: BenchmarkState) -> bool:
    return state.case_count > 0 and state.exact_match_count == state.case_count and state.regression_failed_count == 0


def candidate_beats_best(candidate: BenchmarkState, best: BenchmarkState) -> bool:
    if candidate.exact_match_rate > best.exact_match_rate:
        return True
    if candidate.exact_match_rate == best.exact_match_rate and candidate.regression_failed_count < best.regression_failed_count:
        return True
    return False


def run_root_metadata(run_root: Path, manifest_path: Path, max_iterations: int, codex_bin: str, model: str) -> dict[str, Any]:
    return {
        "generated_at_utc": benchmark.now_utc_iso(),
        "run_root": gold.display_path(run_root),
        "manifest_path": gold.display_path(manifest_path),
        "editable_files": [gold.display_path(path) for path in EDITABLE_FILES],
        "program_path": gold.display_path(PROGRAM_PATH),
        "max_iterations": max_iterations,
        "codex_bin": codex_bin,
        "model": model,
    }


def build_agent_prompt(*, run_root: Path, iteration: int, best_state: BenchmarkState) -> str:
    return f"""You are working inside the repository at {gold.display_path(gold.REPO_ROOT)}.

Follow the optimisation intent in {gold.display_path(PROGRAM_PATH)} with these outer-loop overrides:
- The outer loop will run benchmarks, decide keep/discard, and make commits.
- Do not run the benchmark scripts yourself.
- Do not commit, revert, or reset anything.
- Do not modify files outside this editable surface:
  - {gold.display_path(EDITABLE_FILES[0])}
  - {gold.display_path(EDITABLE_FILES[1])}

There may be unrelated dirty files elsewhere in the worktree. Ignore them and do not touch them.

Current best metrics:
- exact_match_count: {best_state.exact_match_count}/{best_state.case_count}
- exact_match_rate: {best_state.exact_match_rate:.6f}
- regression_failed_count: {best_state.regression_failed_count}
- mean_overlap_score: {best_state.mean_overlap_score:.6f}

Read these benchmark outputs before editing:
- gold summary: {gold.display_path(best_state.gold_summary_path)}
- regression summary: {gold.display_path(best_state.regression_summary_path)}

Task for iteration {iteration:03d}:
1. Inspect the current benchmark failures.
2. Make one bounded extraction improvement in the editable files only.
3. Prefer the simplest plausible change that could increase exact matches without creating regression failures.
4. Stop after the code edit is complete.

Do not add dependencies. Do not touch production stage-05 files. Do not touch gold JSONs or regression fixtures.
"""


def run_agent_iteration(
    *,
    codex_bin: str,
    model: str,
    run_root: Path,
    iteration: int,
    best_state: BenchmarkState,
) -> Path:
    iteration_dir = run_root / f"iteration_{iteration:03d}"
    iteration_dir.mkdir(parents=True, exist_ok=True)
    prompt = build_agent_prompt(run_root=run_root, iteration=iteration, best_state=best_state)
    prompt_path = iteration_dir / "agent_prompt.md"
    prompt_path.write_text(prompt, encoding="utf-8")
    output_last_message_path = iteration_dir / "agent_last_message.txt"
    command = [
        codex_bin,
        "exec",
        "--full-auto",
        "-C",
        str(gold.REPO_ROOT),
        "-o",
        str(output_last_message_path),
    ]
    if model:
        command.extend(["-m", model])
    command.append("-")
    run_command(command, input_text=prompt)
    return iteration_dir


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the stage-05 autoresearch loop until the gold benchmark is fully clean or the loop hits a stop condition."
    )
    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=gold.MANIFEST_PATH,
        help="Gold manifest path.",
    )
    parser.add_argument(
        "--gold-papers-dir",
        type=Path,
        default=gold.GOLD_PAPERS_DIR,
        help="Gold JSON directory. The loop syncs the manifest once at startup.",
    )
    parser.add_argument(
        "--run-root",
        type=Path,
        default=None,
        help="Optional explicit run directory. Defaults to a timestamped folder under qa/trimming/gold_standard/autoresearch/runs/.",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=0,
        help="Maximum agent iterations after the baseline. Use 0 for no fixed limit.",
    )
    parser.add_argument(
        "--codex-bin",
        default="codex",
        help="Codex CLI executable to use for non-interactive edit iterations.",
    )
    parser.add_argument(
        "--model",
        default="",
        help="Optional model override passed to `codex exec`.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_editable_files_clean()
    initial_status = git_status_map()
    gold.sync_manifest(gold_papers_dir=args.gold_papers_dir, manifest_path=args.manifest_path)

    run_root = args.run_root or next_run_root()
    run_root.mkdir(parents=True, exist_ok=True)
    write_json(run_root / "loop_config.json", run_root_metadata(run_root, args.manifest_path, args.max_iterations, args.codex_bin, args.model))

    baseline_dir = run_root / "baseline"
    best_state = run_benchmarks(baseline_dir, args.manifest_path)
    append_results_row(
        run_root / "results.tsv",
        {
            "iteration": "baseline",
            "status": "baseline",
            "exact_match_count": best_state.exact_match_count,
            "case_count": best_state.case_count,
            "exact_match_rate": f"{best_state.exact_match_rate:.6f}",
            "regression_failed_count": best_state.regression_failed_count,
            "mean_overlap_score": f"{best_state.mean_overlap_score:.6f}",
            "gold_summary_path": gold.display_path(best_state.gold_summary_path),
            "regression_summary_path": gold.display_path(best_state.regression_summary_path),
            "changed_paths": "",
            "notes": "initial baseline",
        },
    )
    write_json(
        LATEST_RUN_PATH,
        {
            **run_root_metadata(run_root, args.manifest_path, args.max_iterations, args.codex_bin, args.model),
            "status": "running",
            "best_exact_match_count": best_state.exact_match_count,
            "best_case_count": best_state.case_count,
            "best_regression_failed_count": best_state.regression_failed_count,
        },
    )

    if goal_reached(best_state):
        payload = {
            "generated_at_utc": benchmark.now_utc_iso(),
            "status": "completed",
            "stop_reason": "baseline_already_clean",
            "run_root": gold.display_path(run_root),
            "results_path": gold.display_path(run_root / "results.tsv"),
        }
        write_json(run_root / "loop_summary.json", payload)
        write_json(LATEST_RUN_PATH, payload)
        print("Loop status: completed")
        print(f"Run root: {gold.display_path(run_root)}")
        print(f"Loop summary: {gold.display_path(run_root / 'loop_summary.json')}")
        return

    iteration = 1
    while args.max_iterations <= 0 or iteration <= args.max_iterations:
        iteration_dir = run_agent_iteration(
            codex_bin=args.codex_bin,
            model=args.model,
            run_root=run_root,
            iteration=iteration,
            best_state=best_state,
        )
        changed_paths = changed_paths_since_initial(initial_status)
        out_of_scope = [
            path for path in changed_paths if path.replace("\\", "/") not in set(relative_repo_paths())
        ]
        if out_of_scope:
            payload = {
                "generated_at_utc": benchmark.now_utc_iso(),
                "status": "blocked",
                "stop_reason": "out_of_scope_changes",
                "run_root": gold.display_path(run_root),
                "out_of_scope_paths": out_of_scope,
                "results_path": gold.display_path(run_root / "results.tsv"),
            }
            write_json(run_root / "loop_summary.json", payload)
            write_json(LATEST_RUN_PATH, payload)
            raise SystemExit(f"Autoresearch iteration touched out-of-scope files: {', '.join(out_of_scope)}")

        if not editable_diff_exists():
            append_results_row(
                run_root / "results.tsv",
                {
                    "iteration": f"{iteration:03d}",
                    "status": "no_change",
                    "exact_match_count": best_state.exact_match_count,
                    "case_count": best_state.case_count,
                    "exact_match_rate": f"{best_state.exact_match_rate:.6f}",
                    "regression_failed_count": best_state.regression_failed_count,
                    "mean_overlap_score": f"{best_state.mean_overlap_score:.6f}",
                    "gold_summary_path": gold.display_path(best_state.gold_summary_path),
                    "regression_summary_path": gold.display_path(best_state.regression_summary_path),
                    "changed_paths": "",
                    "notes": "agent returned without editable-file changes",
                },
            )
            payload = {
                "generated_at_utc": benchmark.now_utc_iso(),
                "status": "blocked",
                "stop_reason": "no_editable_changes",
                "run_root": gold.display_path(run_root),
                "results_path": gold.display_path(run_root / "results.tsv"),
            }
            write_json(run_root / "loop_summary.json", payload)
            write_json(LATEST_RUN_PATH, payload)
            print("Loop status: blocked")
            print(f"Run root: {gold.display_path(run_root)}")
            print(f"Loop summary: {gold.display_path(run_root / 'loop_summary.json')}")
            return

        candidate_state = run_benchmarks(iteration_dir, args.manifest_path)
        decision = "discarded"
        notes = "candidate did not beat current best"
        if candidate_beats_best(candidate_state, best_state):
            decision = "accepted"
            notes = "candidate improved keep metrics"
            commit_editable_files(
                f"stage05 autoresearch iter {iteration:03d} "
                f"{candidate_state.exact_match_count}of{candidate_state.case_count} "
                f"regressions{candidate_state.regression_failed_count}"
            )
            best_state = candidate_state
        else:
            restore_editable_files()

        append_results_row(
            run_root / "results.tsv",
            {
                "iteration": f"{iteration:03d}",
                "status": decision,
                "exact_match_count": candidate_state.exact_match_count,
                "case_count": candidate_state.case_count,
                "exact_match_rate": f"{candidate_state.exact_match_rate:.6f}",
                "regression_failed_count": candidate_state.regression_failed_count,
                "mean_overlap_score": f"{candidate_state.mean_overlap_score:.6f}",
                "gold_summary_path": gold.display_path(candidate_state.gold_summary_path),
                "regression_summary_path": gold.display_path(candidate_state.regression_summary_path),
                "changed_paths": ";".join(changed_paths),
                "notes": notes,
            },
        )

        if goal_reached(best_state):
            payload = {
                "generated_at_utc": benchmark.now_utc_iso(),
                "status": "completed",
                "stop_reason": "goal_reached",
                "run_root": gold.display_path(run_root),
                "results_path": gold.display_path(run_root / "results.tsv"),
                "best_exact_match_count": best_state.exact_match_count,
                "best_case_count": best_state.case_count,
                "best_regression_failed_count": best_state.regression_failed_count,
            }
            write_json(run_root / "loop_summary.json", payload)
            write_json(LATEST_RUN_PATH, payload)
            print("Loop status: completed")
            print(f"Run root: {gold.display_path(run_root)}")
            print(f"Loop summary: {gold.display_path(run_root / 'loop_summary.json')}")
            return
        iteration += 1

    payload = {
        "generated_at_utc": benchmark.now_utc_iso(),
        "status": "stopped",
        "stop_reason": "max_iterations_reached",
        "run_root": gold.display_path(run_root),
        "results_path": gold.display_path(run_root / "results.tsv"),
        "best_exact_match_count": best_state.exact_match_count,
        "best_case_count": best_state.case_count,
        "best_regression_failed_count": best_state.regression_failed_count,
    }
    write_json(run_root / "loop_summary.json", payload)
    write_json(LATEST_RUN_PATH, payload)
    print("Loop status: stopped")
    print(f"Run root: {gold.display_path(run_root)}")
    print(f"Loop summary: {gold.display_path(run_root / 'loop_summary.json')}")


if __name__ == "__main__":
    main()
