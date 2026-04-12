from __future__ import annotations

import argparse
import csv
import json
import os
import re
import signal
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
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
    "kept_commit",
    "description",
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


@dataclass(frozen=True)
class DiffStat:
    changed_paths: tuple[str, ...]
    insertions: int
    deletions: int

    @property
    def files_changed(self) -> int:
        return len(self.changed_paths)

    @property
    def net_line_delta(self) -> int:
        return self.insertions - self.deletions


@dataclass(frozen=True)
class BranchContext:
    run_tag: str
    current_branch: str
    expected_branch: str
    matches_expected: bool


@dataclass(frozen=True)
class CommandResult:
    command: tuple[str, ...]
    stdout_path: Path
    stderr_path: Path
    returncode: int | None
    timed_out: bool
    timeout_seconds: int | None

    @property
    def ok(self) -> bool:
        return not self.timed_out and self.returncode == 0


@dataclass(frozen=True)
class BenchmarkRun:
    state: BenchmarkState
    gold_command: CommandResult
    regression_command: CommandResult


@dataclass(frozen=True)
class AgentRun:
    iteration_dir: Path
    prompt_path: Path
    last_message_path: Path
    command_result: CommandResult


class CommandFailed(RuntimeError):
    def __init__(self, step: str, result: CommandResult) -> None:
        self.step = step
        self.result = result
        super().__init__(failure_reason(step, result))


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


def run_command(command: list[str], *, input_text: str | None = None) -> None:
    subprocess.run(
        command,
        check=True,
        cwd=str(gold.REPO_ROOT),
        input=input_text,
        text=True,
    )


def run_logged_command(
    command: list[str],
    *,
    stdout_path: Path,
    stderr_path: Path,
    timeout_seconds: int,
    input_text: str | None = None,
) -> CommandResult:
    stdout_path.parent.mkdir(parents=True, exist_ok=True)
    stderr_path.parent.mkdir(parents=True, exist_ok=True)
    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_handle:
        popen_kwargs: dict[str, Any] = {
            "cwd": str(gold.REPO_ROOT),
            "text": True,
            "stdout": stdout_handle,
            "stderr": stderr_handle,
        }
        if input_text is not None:
            popen_kwargs["stdin"] = subprocess.PIPE
        if os.name == "nt":
            popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            popen_kwargs["start_new_session"] = True
        process = subprocess.Popen(command, **popen_kwargs)
        try:
            process.communicate(input=input_text, timeout=max(1, timeout_seconds))
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/T", "/F", "/PID", str(process.pid)],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except PermissionError:
                    process.kill()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            stderr_handle.write(f"[stage05 autoresearch] command timed out after {timeout_seconds} seconds.\n")
            stderr_handle.flush()
            return CommandResult(
                command=tuple(command),
                stdout_path=stdout_path,
                stderr_path=stderr_path,
                returncode=None,
                timed_out=True,
                timeout_seconds=timeout_seconds,
            )
    return CommandResult(
        command=tuple(command),
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        returncode=process.returncode,
        timed_out=False,
        timeout_seconds=timeout_seconds,
    )


def capture_command(command: list[str]) -> str:
    return subprocess.run(
        command,
        check=True,
        cwd=str(gold.REPO_ROOT),
        text=True,
        capture_output=True,
    ).stdout


def default_run_tag(now: datetime | None = None) -> str:
    timestamp = now or datetime.now(timezone.utc)
    return f"stage05-{timestamp.strftime('%b%d').lower()}"


def normalise_run_tag(raw: str) -> str:
    tag = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    if not tag:
        raise SystemExit("Run tag must contain at least one letter or digit.")
    return tag


def resolve_run_tag(raw: str, run_root: Path | None = None) -> str:
    if raw:
        return normalise_run_tag(raw)
    if run_root is not None:
        return normalise_run_tag(run_root.name)
    return default_run_tag()


def next_run_root(run_tag: str, root_dir: Path = RUNS_DIR) -> Path:
    root_dir.mkdir(parents=True, exist_ok=True)
    base = root_dir / run_tag
    if not base.exists():
        return base
    suffix = 2
    while True:
        candidate = root_dir / f"{base.name}_{suffix:02d}"
        if not candidate.exists():
            return candidate
        suffix += 1


def current_branch_name() -> str:
    return capture_command(["git", "rev-parse", "--abbrev-ref", "HEAD"]).strip()


def expected_branch_name(run_tag: str) -> str:
    return f"autoresearch/{run_tag}"


def head_commit_short() -> str:
    return capture_command(["git", "rev-parse", "--short", "HEAD"]).strip()


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


def build_branch_context(run_tag: str) -> BranchContext:
    current_branch = current_branch_name()
    expected_branch = expected_branch_name(run_tag)
    return BranchContext(
        run_tag=run_tag,
        current_branch=current_branch,
        expected_branch=expected_branch,
        matches_expected=current_branch == expected_branch,
    )


def changed_paths_since_initial(initial_status: dict[str, str]) -> list[str]:
    current = git_status_map()
    return sorted(
        path
        for path in set(initial_status) | set(current)
        if initial_status.get(path, "") != current.get(path, "")
    )


def editable_diff_exists() -> bool:
    diff_output = capture_command(["git", "status", "--porcelain=v1", "--", *relative_repo_paths()])
    return bool(diff_output.strip())


def restore_editable_files() -> None:
    run_command(["git", "restore", "--staged", "--worktree", "--source=HEAD", "--", *relative_repo_paths()])


def commit_editable_files(message: str) -> str:
    run_command(["git", "add", "--", *relative_repo_paths()])
    run_command(["git", "commit", "-m", message])
    return head_commit_short()


def diff_stats_for_editable_files(iteration_dir: Path) -> DiffStat:
    numstat_output = capture_command(["git", "diff", "--numstat", "--", *relative_repo_paths()])
    patch_output = capture_command(["git", "diff", "--", *relative_repo_paths()])
    (iteration_dir / "candidate_numstat.tsv").write_text(numstat_output, encoding="utf-8")
    (iteration_dir / "candidate.patch").write_text(patch_output, encoding="utf-8")

    changed_paths: list[str] = []
    insertions = 0
    deletions = 0
    for raw_line in numstat_output.splitlines():
        parts = raw_line.split("\t")
        if len(parts) < 3:
            continue
        inserted_text, deleted_text, path = parts[0], parts[1], parts[2]
        changed_paths.append(path.replace("\\", "/"))
        if inserted_text.isdigit():
            insertions += int(inserted_text)
        if deleted_text.isdigit():
            deletions += int(deleted_text)

    return DiffStat(changed_paths=tuple(sorted(changed_paths)), insertions=insertions, deletions=deletions)


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


def run_benchmarks(run_root: Path, manifest_path: Path, timeout_seconds: int) -> BenchmarkRun:
    gold_dir = run_root / "gold"
    regression_dir = run_root / "regression"
    gold_command = [
        sys.executable,
        str(Path(benchmark.__file__).resolve()),
        "--mode",
        "gold",
        "--output-dir",
        str(gold_dir),
        "--manifest-path",
        str(manifest_path),
    ]
    regression_command = [
        sys.executable,
        str(Path(benchmark.__file__).resolve()),
        "--mode",
        "regression",
        "--output-dir",
        str(regression_dir),
        "--manifest-path",
        str(manifest_path),
    ]

    gold_result = run_logged_command(
        gold_command,
        stdout_path=gold_dir / "command_stdout.log",
        stderr_path=gold_dir / "command_stderr.log",
        timeout_seconds=timeout_seconds,
    )
    if not gold_result.ok:
        raise CommandFailed("gold benchmark", gold_result)

    regression_result = run_logged_command(
        regression_command,
        stdout_path=regression_dir / "command_stdout.log",
        stderr_path=regression_dir / "command_stderr.log",
        timeout_seconds=timeout_seconds,
    )
    if not regression_result.ok:
        raise CommandFailed("regression benchmark", regression_result)

    return BenchmarkRun(
        state=benchmark_state_from_paths(gold_dir / "summary.json", regression_dir / "summary.json"),
        gold_command=gold_result,
        regression_command=regression_result,
    )


def goal_reached(state: BenchmarkState) -> bool:
    return state.case_count > 0 and state.exact_match_count == state.case_count and state.regression_failed_count == 0


def change_is_simpler(diff_stat: DiffStat) -> bool:
    return diff_stat.deletions > diff_stat.insertions


def candidate_decision(
    candidate: BenchmarkState,
    best: BenchmarkState,
    diff_stat: DiffStat,
) -> tuple[str, str]:
    if candidate.exact_match_rate > best.exact_match_rate:
        return "accepted", "improved exact_match_rate"
    if candidate.exact_match_rate == best.exact_match_rate and candidate.regression_failed_count < best.regression_failed_count:
        return "accepted", "tied exact_match_rate and reduced regression failures"
    if (
        candidate.exact_match_rate == best.exact_match_rate
        and candidate.regression_failed_count == best.regression_failed_count
        and change_is_simpler(diff_stat)
    ):
        return "accepted", "tied keep metrics and simplified editable code"
    return "discarded", "candidate did not improve keep metrics"


def candidate_beats_best(candidate: BenchmarkState, best: BenchmarkState, diff_stat: DiffStat | None = None) -> bool:
    status, _ = candidate_decision(candidate, best, diff_stat or DiffStat((), 0, 0))
    return status == "accepted"


def failure_reason(step: str, result: CommandResult) -> str:
    if result.timed_out and result.timeout_seconds is not None:
        return f"{step} timed out after {result.timeout_seconds} seconds"
    if result.returncode is None:
        return f"{step} failed without a return code"
    return f"{step} exited with code {result.returncode}"


def run_root_metadata(
    *,
    run_root: Path,
    manifest_path: Path,
    max_iterations: int,
    codex_bin: str,
    model: str,
    run_tag: str,
    branch_context: BranchContext,
    agent_timeout_seconds: int,
    benchmark_timeout_seconds: int,
) -> dict[str, Any]:
    return {
        "generated_at_utc": benchmark.now_utc_iso(),
        "run_root": gold.display_path(run_root),
        "run_tag": run_tag,
        "manifest_path": gold.display_path(manifest_path),
        "editable_files": [gold.display_path(path) for path in EDITABLE_FILES],
        "program_path": gold.display_path(PROGRAM_PATH),
        "results_header": RESULTS_HEADER,
        "max_iterations": max_iterations,
        "codex_bin": codex_bin,
        "model": model,
        "agent_timeout_seconds": agent_timeout_seconds,
        "benchmark_timeout_seconds": benchmark_timeout_seconds,
        "recommended_branch": branch_context.expected_branch,
        "current_branch": branch_context.current_branch,
        "branch_matches_recommended": branch_context.matches_expected,
    }


def latest_run_payload(
    *,
    run_root: Path,
    manifest_path: Path,
    max_iterations: int,
    codex_bin: str,
    model: str,
    run_tag: str,
    branch_context: BranchContext,
    agent_timeout_seconds: int,
    benchmark_timeout_seconds: int,
    status: str,
    best_state: BenchmarkState | None = None,
    current_iteration: str | None = None,
    stop_reason: str | None = None,
) -> dict[str, Any]:
    payload = run_root_metadata(
        run_root=run_root,
        manifest_path=manifest_path,
        max_iterations=max_iterations,
        codex_bin=codex_bin,
        model=model,
        run_tag=run_tag,
        branch_context=branch_context,
        agent_timeout_seconds=agent_timeout_seconds,
        benchmark_timeout_seconds=benchmark_timeout_seconds,
    )
    payload["status"] = status
    payload["results_path"] = gold.display_path(run_root / "results.tsv")
    if current_iteration is not None:
        payload["current_iteration"] = current_iteration
    if stop_reason is not None:
        payload["stop_reason"] = stop_reason
    if best_state is not None:
        payload["best_exact_match_count"] = best_state.exact_match_count
        payload["best_case_count"] = best_state.case_count
        payload["best_exact_match_rate"] = best_state.exact_match_rate
        payload["best_regression_failed_count"] = best_state.regression_failed_count
        payload["best_mean_overlap_score"] = best_state.mean_overlap_score
        payload["best_gold_summary_path"] = gold.display_path(best_state.gold_summary_path)
        payload["best_regression_summary_path"] = gold.display_path(best_state.regression_summary_path)
    return payload


def write_iteration_record(iteration_dir: Path, payload: dict[str, Any]) -> None:
    write_json(iteration_dir / "decision.json", payload)


def build_agent_prompt(*, iteration: int, best_state: BenchmarkState, run_tag: str, branch_context: BranchContext) -> str:
    return f"""You are working inside the repository at {gold.display_path(gold.REPO_ROOT)}.

Follow the optimisation intent in {gold.display_path(PROGRAM_PATH)} with these outer-loop overrides:
- Run tag: {run_tag}
- Recommended branch for this run: {branch_context.expected_branch}
- Current branch: {branch_context.current_branch}
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
2. Choose one extraction hypothesis only.
3. Make one bounded extraction change in the editable files only. Touch one file if possible.
4. Prefer the simplest plausible change that could increase exact matches without creating regression failures.
5. Stop as soon as that single edit is complete.

Do not add dependencies. Do not touch production stage-05 files. Do not touch gold JSONs or regression fixtures.
"""


def run_agent_iteration(
    *,
    codex_bin: str,
    model: str,
    run_root: Path,
    iteration: int,
    best_state: BenchmarkState,
    run_tag: str,
    branch_context: BranchContext,
    timeout_seconds: int,
) -> AgentRun:
    iteration_dir = run_root / f"iteration_{iteration:03d}"
    iteration_dir.mkdir(parents=True, exist_ok=True)
    prompt = build_agent_prompt(
        iteration=iteration,
        best_state=best_state,
        run_tag=run_tag,
        branch_context=branch_context,
    )
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
    command_result = run_logged_command(
        command,
        stdout_path=iteration_dir / "agent_stdout.log",
        stderr_path=iteration_dir / "agent_stderr.log",
        timeout_seconds=timeout_seconds,
        input_text=prompt,
    )
    return AgentRun(
        iteration_dir=iteration_dir,
        prompt_path=prompt_path,
        last_message_path=output_last_message_path,
        command_result=command_result,
    )


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
        help="Optional explicit run directory. Defaults to qa/trimming/gold_standard/autoresearch/runs/<run_tag>.",
    )
    parser.add_argument(
        "--run-tag",
        default="",
        help="Human-readable run tag used for the output directory and recommended branch name.",
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
    parser.add_argument(
        "--agent-timeout-seconds",
        type=int,
        default=1200,
        help="Timeout for each `codex exec` iteration.",
    )
    parser.add_argument(
        "--benchmark-timeout-seconds",
        type=int,
        default=14400,
        help="Timeout for each gold or regression benchmark command.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_tag = resolve_run_tag(args.run_tag, args.run_root)
    branch_context = build_branch_context(run_tag)
    ensure_editable_files_clean()
    initial_status = git_status_map()
    gold.sync_manifest(gold_papers_dir=args.gold_papers_dir, manifest_path=args.manifest_path)

    run_root = args.run_root or next_run_root(run_tag)
    run_root.mkdir(parents=True, exist_ok=True)
    write_json(
        run_root / "loop_config.json",
        run_root_metadata(
            run_root=run_root,
            manifest_path=args.manifest_path,
            max_iterations=args.max_iterations,
            codex_bin=args.codex_bin,
            model=args.model,
            run_tag=run_tag,
            branch_context=branch_context,
            agent_timeout_seconds=args.agent_timeout_seconds,
            benchmark_timeout_seconds=args.benchmark_timeout_seconds,
        ),
    )

    baseline_dir = run_root / "baseline"
    try:
        baseline_run = run_benchmarks(baseline_dir, args.manifest_path, args.benchmark_timeout_seconds)
    except CommandFailed as exc:
        payload = latest_run_payload(
            run_root=run_root,
            manifest_path=args.manifest_path,
            max_iterations=args.max_iterations,
            codex_bin=args.codex_bin,
            model=args.model,
            run_tag=run_tag,
            branch_context=branch_context,
            agent_timeout_seconds=args.agent_timeout_seconds,
            benchmark_timeout_seconds=args.benchmark_timeout_seconds,
            status="blocked",
            current_iteration="baseline",
            stop_reason="baseline_failed",
        )
        payload["failure_reason"] = str(exc)
        payload["failed_step"] = exc.step
        payload["failed_stdout_path"] = gold.display_path(exc.result.stdout_path)
        payload["failed_stderr_path"] = gold.display_path(exc.result.stderr_path)
        write_json(run_root / "loop_summary.json", payload)
        write_json(LATEST_RUN_PATH, payload)
        print("Loop status: blocked")
        print(f"Run root: {gold.display_path(run_root)}")
        print(f"Loop summary: {gold.display_path(run_root / 'loop_summary.json')}")
        return

    best_state = baseline_run.state
    baseline_record = {
        "generated_at_utc": benchmark.now_utc_iso(),
        "iteration": "baseline",
        "status": "baseline",
        "description": "initial baseline",
        "run_tag": run_tag,
        "kept_commit": head_commit_short(),
        "exact_match_count": best_state.exact_match_count,
        "case_count": best_state.case_count,
        "exact_match_rate": best_state.exact_match_rate,
        "regression_failed_count": best_state.regression_failed_count,
        "mean_overlap_score": best_state.mean_overlap_score,
        "gold_summary_path": gold.display_path(best_state.gold_summary_path),
        "regression_summary_path": gold.display_path(best_state.regression_summary_path),
        "gold_stdout_path": gold.display_path(baseline_run.gold_command.stdout_path),
        "gold_stderr_path": gold.display_path(baseline_run.gold_command.stderr_path),
        "regression_stdout_path": gold.display_path(baseline_run.regression_command.stdout_path),
        "regression_stderr_path": gold.display_path(baseline_run.regression_command.stderr_path),
    }
    write_iteration_record(baseline_dir, baseline_record)
    append_results_row(
        run_root / "results.tsv",
        {
            "iteration": "baseline",
            "status": "baseline",
            "exact_match_count": best_state.exact_match_count,
            "case_count": best_state.case_count,
            "exact_match_rate": f"{best_state.exact_match_rate:.6f}",
            "regression_failed_count": best_state.regression_failed_count,
            "kept_commit": baseline_record["kept_commit"],
            "description": "initial baseline",
        },
    )
    write_json(
        LATEST_RUN_PATH,
        latest_run_payload(
            run_root=run_root,
            manifest_path=args.manifest_path,
            max_iterations=args.max_iterations,
            codex_bin=args.codex_bin,
            model=args.model,
            run_tag=run_tag,
            branch_context=branch_context,
            agent_timeout_seconds=args.agent_timeout_seconds,
            benchmark_timeout_seconds=args.benchmark_timeout_seconds,
            status="running",
            best_state=best_state,
            current_iteration="baseline",
        ),
    )

    if goal_reached(best_state):
        payload = latest_run_payload(
            run_root=run_root,
            manifest_path=args.manifest_path,
            max_iterations=args.max_iterations,
            codex_bin=args.codex_bin,
            model=args.model,
            run_tag=run_tag,
            branch_context=branch_context,
            agent_timeout_seconds=args.agent_timeout_seconds,
            benchmark_timeout_seconds=args.benchmark_timeout_seconds,
            status="completed",
            best_state=best_state,
            current_iteration="baseline",
            stop_reason="baseline_already_clean",
        )
        write_json(run_root / "loop_summary.json", payload)
        write_json(LATEST_RUN_PATH, payload)
        print("Loop status: completed")
        print(f"Run root: {gold.display_path(run_root)}")
        print(f"Loop summary: {gold.display_path(run_root / 'loop_summary.json')}")
        return

    iteration = 1
    allowed_paths = set(relative_repo_paths())
    while args.max_iterations <= 0 or iteration <= args.max_iterations:
        agent_run = run_agent_iteration(
            codex_bin=args.codex_bin,
            model=args.model,
            run_root=run_root,
            iteration=iteration,
            best_state=best_state,
            run_tag=run_tag,
            branch_context=branch_context,
            timeout_seconds=args.agent_timeout_seconds,
        )
        changed_paths = changed_paths_since_initial(initial_status)
        out_of_scope = [path for path in changed_paths if path.replace("\\", "/") not in allowed_paths]

        if out_of_scope:
            description = "agent touched out-of-scope files"
            write_iteration_record(
                agent_run.iteration_dir,
                {
                    "generated_at_utc": benchmark.now_utc_iso(),
                    "iteration": f"{iteration:03d}",
                    "status": "blocked",
                    "description": description,
                    "run_tag": run_tag,
                    "prompt_path": gold.display_path(agent_run.prompt_path),
                    "agent_last_message_path": gold.display_path(agent_run.last_message_path),
                    "agent_stdout_path": gold.display_path(agent_run.command_result.stdout_path),
                    "agent_stderr_path": gold.display_path(agent_run.command_result.stderr_path),
                    "out_of_scope_paths": out_of_scope,
                },
            )
            append_results_row(
                run_root / "results.tsv",
                {
                    "iteration": f"{iteration:03d}",
                    "status": "blocked",
                    "description": description,
                },
            )
            payload = latest_run_payload(
                run_root=run_root,
                manifest_path=args.manifest_path,
                max_iterations=args.max_iterations,
                codex_bin=args.codex_bin,
                model=args.model,
                run_tag=run_tag,
                branch_context=branch_context,
                agent_timeout_seconds=args.agent_timeout_seconds,
                benchmark_timeout_seconds=args.benchmark_timeout_seconds,
                status="blocked",
                best_state=best_state,
                current_iteration=f"{iteration:03d}",
                stop_reason="out_of_scope_changes",
            )
            payload["out_of_scope_paths"] = out_of_scope
            write_json(run_root / "loop_summary.json", payload)
            write_json(LATEST_RUN_PATH, payload)
            raise SystemExit(f"Autoresearch iteration touched out-of-scope files: {', '.join(out_of_scope)}")

        if not agent_run.command_result.ok:
            description = failure_reason("agent edit", agent_run.command_result)
            write_iteration_record(
                agent_run.iteration_dir,
                {
                    "generated_at_utc": benchmark.now_utc_iso(),
                    "iteration": f"{iteration:03d}",
                    "status": "blocked",
                    "description": description,
                    "run_tag": run_tag,
                    "prompt_path": gold.display_path(agent_run.prompt_path),
                    "agent_last_message_path": gold.display_path(agent_run.last_message_path),
                    "agent_stdout_path": gold.display_path(agent_run.command_result.stdout_path),
                    "agent_stderr_path": gold.display_path(agent_run.command_result.stderr_path),
                },
            )
            append_results_row(
                run_root / "results.tsv",
                {
                    "iteration": f"{iteration:03d}",
                    "status": "agent_failed",
                    "description": description,
                },
            )
            payload = latest_run_payload(
                run_root=run_root,
                manifest_path=args.manifest_path,
                max_iterations=args.max_iterations,
                codex_bin=args.codex_bin,
                model=args.model,
                run_tag=run_tag,
                branch_context=branch_context,
                agent_timeout_seconds=args.agent_timeout_seconds,
                benchmark_timeout_seconds=args.benchmark_timeout_seconds,
                status="blocked",
                best_state=best_state,
                current_iteration=f"{iteration:03d}",
                stop_reason="agent_failed",
            )
            payload["failed_stdout_path"] = gold.display_path(agent_run.command_result.stdout_path)
            payload["failed_stderr_path"] = gold.display_path(agent_run.command_result.stderr_path)
            payload["failure_reason"] = description
            write_json(run_root / "loop_summary.json", payload)
            write_json(LATEST_RUN_PATH, payload)
            print("Loop status: blocked")
            print(f"Run root: {gold.display_path(run_root)}")
            print(f"Loop summary: {gold.display_path(run_root / 'loop_summary.json')}")
            return

        if not editable_diff_exists():
            description = "agent returned without editable-file changes"
            write_iteration_record(
                agent_run.iteration_dir,
                {
                    "generated_at_utc": benchmark.now_utc_iso(),
                    "iteration": f"{iteration:03d}",
                    "status": "blocked",
                    "description": description,
                    "run_tag": run_tag,
                    "prompt_path": gold.display_path(agent_run.prompt_path),
                    "agent_last_message_path": gold.display_path(agent_run.last_message_path),
                    "agent_stdout_path": gold.display_path(agent_run.command_result.stdout_path),
                    "agent_stderr_path": gold.display_path(agent_run.command_result.stderr_path),
                },
            )
            append_results_row(
                run_root / "results.tsv",
                {
                    "iteration": f"{iteration:03d}",
                    "status": "no_change",
                    "description": description,
                },
            )
            payload = latest_run_payload(
                run_root=run_root,
                manifest_path=args.manifest_path,
                max_iterations=args.max_iterations,
                codex_bin=args.codex_bin,
                model=args.model,
                run_tag=run_tag,
                branch_context=branch_context,
                agent_timeout_seconds=args.agent_timeout_seconds,
                benchmark_timeout_seconds=args.benchmark_timeout_seconds,
                status="blocked",
                best_state=best_state,
                current_iteration=f"{iteration:03d}",
                stop_reason="no_editable_changes",
            )
            write_json(run_root / "loop_summary.json", payload)
            write_json(LATEST_RUN_PATH, payload)
            print("Loop status: blocked")
            print(f"Run root: {gold.display_path(run_root)}")
            print(f"Loop summary: {gold.display_path(run_root / 'loop_summary.json')}")
            return

        diff_stat = diff_stats_for_editable_files(agent_run.iteration_dir)
        try:
            benchmark_run = run_benchmarks(agent_run.iteration_dir, args.manifest_path, args.benchmark_timeout_seconds)
        except CommandFailed as exc:
            restore_editable_files()
            description = failure_reason(exc.step, exc.result)
            write_iteration_record(
                agent_run.iteration_dir,
                {
                    "generated_at_utc": benchmark.now_utc_iso(),
                    "iteration": f"{iteration:03d}",
                    "status": "crash",
                    "description": description,
                    "run_tag": run_tag,
                    "prompt_path": gold.display_path(agent_run.prompt_path),
                    "agent_last_message_path": gold.display_path(agent_run.last_message_path),
                    "agent_stdout_path": gold.display_path(agent_run.command_result.stdout_path),
                    "agent_stderr_path": gold.display_path(agent_run.command_result.stderr_path),
                    "changed_paths": list(diff_stat.changed_paths),
                    "insertions": diff_stat.insertions,
                    "deletions": diff_stat.deletions,
                    "candidate_patch_path": gold.display_path(agent_run.iteration_dir / "candidate.patch"),
                    "failed_step": exc.step,
                    "failed_stdout_path": gold.display_path(exc.result.stdout_path),
                    "failed_stderr_path": gold.display_path(exc.result.stderr_path),
                },
            )
            append_results_row(
                run_root / "results.tsv",
                {
                    "iteration": f"{iteration:03d}",
                    "status": "crash",
                    "description": description,
                },
            )
            write_json(
                LATEST_RUN_PATH,
                latest_run_payload(
                    run_root=run_root,
                    manifest_path=args.manifest_path,
                    max_iterations=args.max_iterations,
                    codex_bin=args.codex_bin,
                    model=args.model,
                    run_tag=run_tag,
                    branch_context=branch_context,
                    agent_timeout_seconds=args.agent_timeout_seconds,
                    benchmark_timeout_seconds=args.benchmark_timeout_seconds,
                    status="running",
                    best_state=best_state,
                    current_iteration=f"{iteration:03d}",
                ),
            )
            iteration += 1
            continue

        decision, description = candidate_decision(benchmark_run.state, best_state, diff_stat)
        kept_commit = ""
        if decision == "accepted":
            kept_commit = commit_editable_files(
                f"stage05 autoresearch iter {iteration:03d} "
                f"{benchmark_run.state.exact_match_count}of{benchmark_run.state.case_count} "
                f"regressions{benchmark_run.state.regression_failed_count}"
            )
            best_state = benchmark_run.state
        else:
            restore_editable_files()

        write_iteration_record(
            agent_run.iteration_dir,
            {
                "generated_at_utc": benchmark.now_utc_iso(),
                "iteration": f"{iteration:03d}",
                "status": decision,
                "description": description,
                "run_tag": run_tag,
                "kept_commit": kept_commit,
                "prompt_path": gold.display_path(agent_run.prompt_path),
                "agent_last_message_path": gold.display_path(agent_run.last_message_path),
                "agent_stdout_path": gold.display_path(agent_run.command_result.stdout_path),
                "agent_stderr_path": gold.display_path(agent_run.command_result.stderr_path),
                "changed_paths": list(diff_stat.changed_paths),
                "insertions": diff_stat.insertions,
                "deletions": diff_stat.deletions,
                "net_line_delta": diff_stat.net_line_delta,
                "gold_summary_path": gold.display_path(benchmark_run.state.gold_summary_path),
                "regression_summary_path": gold.display_path(benchmark_run.state.regression_summary_path),
                "gold_stdout_path": gold.display_path(benchmark_run.gold_command.stdout_path),
                "gold_stderr_path": gold.display_path(benchmark_run.gold_command.stderr_path),
                "regression_stdout_path": gold.display_path(benchmark_run.regression_command.stdout_path),
                "regression_stderr_path": gold.display_path(benchmark_run.regression_command.stderr_path),
                "exact_match_count": benchmark_run.state.exact_match_count,
                "case_count": benchmark_run.state.case_count,
                "exact_match_rate": benchmark_run.state.exact_match_rate,
                "regression_failed_count": benchmark_run.state.regression_failed_count,
                "mean_overlap_score": benchmark_run.state.mean_overlap_score,
                "candidate_patch_path": gold.display_path(agent_run.iteration_dir / "candidate.patch"),
            },
        )
        append_results_row(
            run_root / "results.tsv",
            {
                "iteration": f"{iteration:03d}",
                "status": decision,
                "exact_match_count": benchmark_run.state.exact_match_count,
                "case_count": benchmark_run.state.case_count,
                "exact_match_rate": f"{benchmark_run.state.exact_match_rate:.6f}",
                "regression_failed_count": benchmark_run.state.regression_failed_count,
                "kept_commit": kept_commit,
                "description": description,
            },
        )

        if goal_reached(best_state):
            payload = latest_run_payload(
                run_root=run_root,
                manifest_path=args.manifest_path,
                max_iterations=args.max_iterations,
                codex_bin=args.codex_bin,
                model=args.model,
                run_tag=run_tag,
                branch_context=branch_context,
                agent_timeout_seconds=args.agent_timeout_seconds,
                benchmark_timeout_seconds=args.benchmark_timeout_seconds,
                status="completed",
                best_state=best_state,
                current_iteration=f"{iteration:03d}",
                stop_reason="goal_reached",
            )
            write_json(run_root / "loop_summary.json", payload)
            write_json(LATEST_RUN_PATH, payload)
            print("Loop status: completed")
            print(f"Run root: {gold.display_path(run_root)}")
            print(f"Loop summary: {gold.display_path(run_root / 'loop_summary.json')}")
            return

        write_json(
            LATEST_RUN_PATH,
            latest_run_payload(
                run_root=run_root,
                manifest_path=args.manifest_path,
                max_iterations=args.max_iterations,
                codex_bin=args.codex_bin,
                model=args.model,
                run_tag=run_tag,
                branch_context=branch_context,
                agent_timeout_seconds=args.agent_timeout_seconds,
                benchmark_timeout_seconds=args.benchmark_timeout_seconds,
                status="running",
                best_state=best_state,
                current_iteration=f"{iteration:03d}",
            ),
        )
        iteration += 1

    payload = latest_run_payload(
        run_root=run_root,
        manifest_path=args.manifest_path,
        max_iterations=args.max_iterations,
        codex_bin=args.codex_bin,
        model=args.model,
        run_tag=run_tag,
        branch_context=branch_context,
        agent_timeout_seconds=args.agent_timeout_seconds,
        benchmark_timeout_seconds=args.benchmark_timeout_seconds,
        status="stopped",
        best_state=best_state,
        stop_reason="max_iterations_reached",
    )
    write_json(run_root / "loop_summary.json", payload)
    write_json(LATEST_RUN_PATH, payload)
    print("Loop status: stopped")
    print(f"Run root: {gold.display_path(run_root)}")
    print(f"Loop summary: {gold.display_path(run_root / 'loop_summary.json')}")


if __name__ == "__main__":
    main()
