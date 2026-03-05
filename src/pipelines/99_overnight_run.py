from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results" / "overnight"
STAGE_LOG_DIR = RESULTS_DIR / "stage_logs"
LOG_PATH = RESULTS_DIR / "LOG.md"
STATUS_PATH = RESULTS_DIR / "stage_status.tsv"


# Define stage.
@dataclass(frozen=True)
class Stage:
    key: str
    label: str
    script_path: Path
    supports_dry_run: bool = False
    supports_force: bool = False
    supports_model_id: bool = False


STAGES = [
    Stage(
        key="extract_text",
        label="Text Extraction",
        script_path=REPO_ROOT / "src" / "pipelines" / "03_extract_text.py",
        supports_force=True,
    ),
    Stage(
        key="source_categorisation",
        label="Source Categorisation",
        script_path=REPO_ROOT / "src" / "pipelines" / "04_source_categorisation.py",
    ),
    Stage(
        key="proceedings_trim",
        label="Proceedings Trim",
        script_path=REPO_ROOT / "src" / "pipelines" / "05_trim_proceedings_text.py",
    ),
    Stage(
        key="proceedings_qc",
        label="Proceedings Text QC",
        script_path=REPO_ROOT / "src" / "pipelines" / "06_validate_proceedings_text.py",
    ),
    Stage(
        key="case_series_split",
        label="Case-Series Splitting",
        script_path=REPO_ROOT / "src" / "pipelines" / "07_split_case_series.py",
    ),
    Stage(
        key="build_langextract_examples",
        label="Build LangExtract Examples",
        script_path=REPO_ROOT / "src" / "pipelines" / "09_build_langextract_examples.py",
    ),
    Stage(
        key="langextract",
        label="LangExtract",
        script_path=REPO_ROOT / "src" / "pipelines" / "10_langextract.py",
        supports_dry_run=True,
        supports_force=True,
        supports_model_id=True,
    ),
    Stage(
        key="quality_assessment",
        label="Quality Assessment",
        script_path=REPO_ROOT / "src" / "pipelines" / "11_quality_assessment.py",
        supports_dry_run=True,
        supports_force=True,
        supports_model_id=True,
    ),
    Stage(
        key="model_comparison",
        label="Model Comparison",
        script_path=REPO_ROOT / "src" / "pipelines" / "04_model_comparison.py",
        supports_dry_run=True,
    ),
]


# Parse command-line arguments.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the SPS overnight pipeline with canonical outputs kept under data/."
    )
    parser.add_argument(
        "--from-stage",
        choices=[stage.key for stage in STAGES],
        default=STAGES[0].key,
        help="First stage to run.",
    )
    parser.add_argument(
        "--to-stage",
        choices=[stage.key for stage in STAGES],
        default=STAGES[-2].key,
        help="Last stage to run.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Optional per-stage file limit.")
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Restrict the run to one or more paper IDs.",
    )
    parser.add_argument("--force", action="store_true", help="Overwrite stage outputs where supported.")
    parser.add_argument("--dry-run", action="store_true", help="Use dry-run mode where supported.")
    parser.add_argument(
        "--model-id",
        default="gpt-4.1-mini",
        help="Model ID passed to stages that accept --model-id.",
    )
    return parser.parse_args()


# Append log.
def append_log(message: str) -> None:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    STAGE_LOG_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(f"- {timestamp} {message}\n")


# Build initialise status file.
def initialise_status_file() -> None:
    if STATUS_PATH.exists():
        return
    with STATUS_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                "started_at_utc",
                "finished_at_utc",
                "stage_key",
                "stage_label",
                "status",
                "exit_code",
                "script_path",
                "stdout_log",
                "stderr_log",
            ]
        )


# Append status row.
def append_status_row(
    *,
    started_at: datetime,
    finished_at: datetime,
    stage: Stage,
    status: str,
    exit_code: int,
    stdout_log: Path,
    stderr_log: Path,
) -> None:
    with STATUS_PATH.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        writer.writerow(
            [
                started_at.isoformat(),
                finished_at.isoformat(),
                stage.key,
                stage.label,
                status,
                str(exit_code),
                str(stage.script_path),
                str(stdout_log.relative_to(REPO_ROOT)),
                str(stderr_log.relative_to(REPO_ROOT)),
            ]
        )


# Build selected stages.
def selected_stages(args: argparse.Namespace) -> list[Stage]:
    start_index = next(i for i, stage in enumerate(STAGES) if stage.key == args.from_stage)
    end_index = next(i for i, stage in enumerate(STAGES) if stage.key == args.to_stage)
    if end_index < start_index:
        raise SystemExit("--to-stage must come after --from-stage.")
    return STAGES[start_index : end_index + 1]


# Build command.
def build_command(stage: Stage, args: argparse.Namespace) -> list[str]:
    command = [sys.executable, str(stage.script_path)]
    if args.limit > 0:
        command.extend(["--limit", str(args.limit)])
    for paper_id in args.paper_id:
        command.extend(["--paper-id", paper_id])
    if args.force and stage.supports_force:
        command.append("--force")
    if args.dry_run and stage.supports_dry_run:
        command.append("--dry-run")
    if stage.supports_model_id:
        command.extend(["--model-id", args.model_id])
    return command


# Run stage.
def run_stage(stage: Stage, args: argparse.Namespace) -> bool:
    started_at = datetime.now(timezone.utc)
    stdout_log = STAGE_LOG_DIR / f"{stage.key}.stdout.log"
    stderr_log = STAGE_LOG_DIR / f"{stage.key}.stderr.log"

    if not stage.script_path.exists():
        finished_at = datetime.now(timezone.utc)
        append_log(
            f"SKIPPED {stage.label}: missing script `{stage.script_path.relative_to(REPO_ROOT)}`."
        )
        stdout_log.write_text("", encoding="utf-8")
        stderr_log.write_text("", encoding="utf-8")
        append_status_row(
            started_at=started_at,
            finished_at=finished_at,
            stage=stage,
            status="skipped_missing_script",
            exit_code=0,
            stdout_log=stdout_log,
            stderr_log=stderr_log,
        )
        return True

    command = build_command(stage, args)
    append_log(f"START {stage.label}: `{' '.join(command)}`")
    completed = subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    stdout_log.write_text(completed.stdout or "", encoding="utf-8")
    stderr_log.write_text(completed.stderr or "", encoding="utf-8")

    finished_at = datetime.now(timezone.utc)
    status = "completed" if completed.returncode == 0 else "failed"
    append_status_row(
        started_at=started_at,
        finished_at=finished_at,
        stage=stage,
        status=status,
        exit_code=completed.returncode,
        stdout_log=stdout_log,
        stderr_log=stderr_log,
    )

    if completed.returncode == 0:
        append_log(f"OK {stage.label}: exit code 0.")
        return True

    append_log(
        f"FAILED {stage.label}: exit code {completed.returncode}. "
        f"See `{stdout_log.relative_to(REPO_ROOT)}` and `{stderr_log.relative_to(REPO_ROOT)}`."
    )
    return False


# Run the pipeline entrypoint.
def main() -> None:
    args = parse_args()
    initialise_status_file()
    append_log("Overnight pipeline run started.")

    for stage in selected_stages(args):
        if not run_stage(stage, args):
            append_log("Pipeline stopped after stage failure.")
            raise SystemExit(1)

    append_log("Overnight pipeline run finished.")


if __name__ == "__main__":
    main()
