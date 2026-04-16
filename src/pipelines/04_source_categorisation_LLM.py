"""Canonical stage-04 LLM source categorisation and SPS case counting.

Safe execution model:
- estimate the selected run without making API calls
- require explicit approval before any paid LLM call
- checkpoint each completed paper to a durable run directory
- resume incomplete runs from disk
- publish canonical registries only after a complete run

Usage:
    python -m src.pipelines.04_source_categorisation_LLM --estimate-only
    python -m src.pipelines.04_source_categorisation_LLM --allow-paid-run --run-id my_run
    python -m src.pipelines.04_source_categorisation_LLM --resume --run-id my_run --allow-paid-run
    python -m src.pipelines.04_source_categorisation_LLM --publish-only --run-id my_run
"""

from __future__ import annotations

import argparse
import csv
import logging
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import TextIO

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.pipelines._proceedings_ready import (
    load_ready_rows_by_id,
    preferred_proceedings_text_path,
    preferred_proceedings_text_source,
)
from src.pipelines.source_categorisation.controller import (
    process_paper,
    result_to_count_registry_row,
    result_to_registry_row,
)
from src.pipelines.source_categorisation.io import load_csv_rows_by_id
from src.pipelines.source_categorisation.prepare import load_text_json
from src.pipelines.source_categorisation.run_state import (
    append_error_row,
    append_result_record,
    build_run_manifest,
    completed_paper_ids,
    default_run_id,
    initialise_run,
    load_error_rows,
    load_run_manifest,
    materialise_run_snapshots,
    now_utc_iso,
    publish_run_outputs,
    run_dir_for,
    write_progress,
)

REPO_ROOT = Path(__file__).resolve().parents[2]

# Input paths.
REFERENCES_CSV = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
TEXT_TRIMMED_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed"
TEXT_TRIM_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "text_trim_registry.csv"
TEXT_PROCEEDINGS_READY_DIR = REPO_ROOT / "data" / "extraction_json" / "text_proceedings_ready"
TEXT_PROCEEDINGS_READY_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "text_proceedings_ready_registry.csv"
MANUAL_REVIEW_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_manual_review.csv"

# Canonical outputs.
OUTPUT_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
COUNT_OUTPUT_PATH = REPO_ROOT / "data" / "references" / "source_sps_case_count_registry.csv"
ARTIFACT_REGISTRY_SCRIPT = REPO_ROOT / "src" / "pipelines" / "12_build_paper_artifact_registry.py"
RUN_ROOT = REPO_ROOT / "results" / "stage04_llm_runs"

DEFAULT_MODEL = "gpt-5.4"
CATEGORISATION_VERSION = "llm_v1_gpt5.4"
DEFAULT_CHECKPOINT_EVERY = 25

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class Stage04ProgressBar:
    """Render a lightweight terminal progress bar for the current invocation."""

    def __init__(
        self,
        *,
        total_pending: int,
        planned_total: int,
        completed_before_start: int,
        enabled: bool,
        stream: TextIO | None = None,
        now_fn=time.monotonic,
    ) -> None:
        self.total_pending = max(total_pending, 0)
        self.planned_total = max(planned_total, 0)
        self.completed_before_start = max(completed_before_start, 0)
        self.enabled = enabled and self.total_pending > 0
        self.stream = stream or sys.stderr
        self.now_fn = now_fn
        self.started_at = self.now_fn()
        self.last_line_length = 0

    def _bar_width(self) -> int:
        terminal_width = shutil.get_terminal_size((120, 20)).columns
        reserved = 70
        return max(10, min(30, terminal_width - reserved))

    def _render_line(
        self,
        *,
        attempted_count: int,
        durable_completed: int,
        error_count: int,
        last_paper_id: str,
        status: str,
    ) -> str:
        fraction = 1.0 if self.total_pending == 0 else min(max(attempted_count / self.total_pending, 0.0), 1.0)
        filled = int(round(self._bar_width() * fraction))
        bar = "#" * filled + "-" * (self._bar_width() - filled)
        elapsed = self.now_fn() - self.started_at
        elapsed_text = format_duration(elapsed)
        eta_text = "--:--:--"
        if attempted_count > 0 and attempted_count < self.total_pending:
            remaining = self.total_pending - attempted_count
            eta_seconds = elapsed / attempted_count * remaining
            eta_text = format_duration(eta_seconds)
        if attempted_count >= self.total_pending:
            eta_text = "00:00:00"

        line = (
            f"Stage 04 [{bar}] {attempted_count}/{self.total_pending} this pass "
            f"| durable {durable_completed}/{self.planned_total} | errors {error_count} "
            f"| elapsed {elapsed_text} | eta {eta_text} | {status}"
        )
        if last_paper_id:
            line += f" | last {last_paper_id}"
        return line

    def render(
        self,
        *,
        attempted_count: int,
        durable_completed: int,
        error_count: int,
        last_paper_id: str = "",
        status: str = "running",
    ) -> None:
        if not self.enabled:
            return
        line = self._render_line(
            attempted_count=attempted_count,
            durable_completed=durable_completed,
            error_count=error_count,
            last_paper_id=last_paper_id,
            status=status,
        )
        padded = line.ljust(self.last_line_length)
        self.stream.write("\r" + padded)
        self.stream.flush()
        self.last_line_length = len(line)

    def finish(
        self,
        *,
        attempted_count: int,
        durable_completed: int,
        error_count: int,
        last_paper_id: str = "",
        status: str = "done",
    ) -> None:
        if not self.enabled:
            return
        self.render(
            attempted_count=attempted_count,
            durable_completed=durable_completed,
            error_count=error_count,
            last_paper_id=last_paper_id,
            status=status,
        )
        self.stream.write("\n")
        self.stream.flush()


def load_reference_rows(path: Path) -> dict[str, dict[str, str]]:
    """Load reference rows keyed by Covidence ID."""
    if not path.exists():
        logger.error("References CSV not found: %s", path)
        return {}
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: dict[str, dict[str, str]] = {}
        for row in reader:
            key = (row.get("Covidence") or "").strip()
            if key:
                rows[key] = row
    return rows


def collect_text_paths(
    input_dir: Path,
    paper_ids: list[str],
    limit: int,
) -> list[Path]:
    """Collect text JSON paths, filtered by paper IDs and limit."""
    if paper_ids:
        paths = [input_dir / f"{paper_id}.json" for paper_id in paper_ids]
        return [path for path in paths if path.exists()]
    paths = sorted(input_dir.glob("*.json"), key=lambda path: path.stem)
    if limit > 0:
        paths = paths[:limit]
    return paths


def _relative_to_repo(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def refresh_artifact_registry(skip_refresh: bool) -> None:
    if skip_refresh:
        return
    subprocess.run(
        [sys.executable, str(ARTIFACT_REGISTRY_SCRIPT)],
        check=True,
        cwd=str(REPO_ROOT),
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="LLM-based source categorisation and SPS case counting for papers."
    )
    parser.add_argument("--references-csv", type=Path, default=REFERENCES_CSV)
    parser.add_argument("--input-dir", type=Path, default=TEXT_DIR)
    parser.add_argument("--trimmed-dir", type=Path, default=TEXT_TRIMMED_DIR)
    parser.add_argument("--trim-registry-path", type=Path, default=TEXT_TRIM_REGISTRY_PATH)
    parser.add_argument("--proceedings-ready-dir", type=Path, default=TEXT_PROCEEDINGS_READY_DIR)
    parser.add_argument(
        "--proceedings-ready-registry-path",
        type=Path,
        default=TEXT_PROCEEDINGS_READY_REGISTRY_PATH,
    )
    parser.add_argument("--manual-review-path", type=Path, default=MANUAL_REVIEW_PATH)
    parser.add_argument("--output-path", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--count-output-path", type=Path, default=COUNT_OUTPUT_PATH)
    parser.add_argument("--run-root", type=Path, default=RUN_ROOT)
    parser.add_argument("--run-id", type=str, default="", help="Explicit run ID for checkpointed runs.")
    parser.add_argument("--resume", action="store_true", help="Resume an existing checkpointed run.")
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Publish canonical registries after this invocation if the run is complete.",
    )
    parser.add_argument(
        "--publish-only",
        action="store_true",
        help="Publish a completed run without making any API calls.",
    )
    parser.add_argument(
        "--estimate-only",
        action="store_true",
        help="Summarise the selected run without creating a run directory or calling the API.",
    )
    parser.add_argument(
        "--allow-paid-run",
        action="store_true",
        help="Explicit approval flag required before any paid LLM calls are made.",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Paper ID(s) to process (repeatable). Omit to process all.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum papers for a new run, or maximum pending papers to process in this invocation when resuming.",
    )
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, help="OpenAI model ID.")
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=DEFAULT_CHECKPOINT_EVERY,
        help="Materialise CSV snapshots after this many newly completed papers.",
    )
    parser.add_argument(
        "--max-runtime-minutes",
        type=float,
        default=0.0,
        help="Optional soft runtime limit for this invocation (0 = unlimited).",
    )
    parser.add_argument(
        "--skip-manual-overrides",
        action="store_true",
        help="Ignore the manual review ledger (e.g. for benchmarking).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be processed, without creating a run directory or calling the API.",
    )
    parser.add_argument(
        "--skip-registry-refresh",
        action="store_true",
        help="Do not rebuild paper_artifact_registry.csv after publishing canonical outputs.",
    )
    parser.add_argument(
        "--show-progress",
        action="store_true",
        help="Force the interactive progress bar even when stderr is not detected as a terminal.",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.publish_only and args.resume:
        raise SystemExit("Use either --publish-only or --resume, not both.")
    if args.publish_only and not args.run_id:
        raise SystemExit("--publish-only requires --run-id.")
    if args.resume and not args.run_id:
        raise SystemExit("--resume requires --run-id.")
    if args.estimate_only and args.publish_only:
        raise SystemExit("--estimate-only cannot be combined with --publish-only.")
    if args.checkpoint_every < 1:
        raise SystemExit("--checkpoint-every must be at least 1.")
    if args.max_runtime_minutes < 0:
        raise SystemExit("--max-runtime-minutes cannot be negative.")


def selection_counts(
    paper_ids: list[str],
    *,
    manual_rows: dict[str, dict[str, str]],
    skip_manual_overrides: bool,
) -> tuple[int, int]:
    if skip_manual_overrides:
        return 0, len(paper_ids)
    manual_total = sum(1 for paper_id in paper_ids if paper_id in manual_rows)
    return manual_total, len(paper_ids) - manual_total


def print_selection_summary(
    *,
    run_id: str,
    paper_ids: list[str],
    pending_ids: list[str],
    manual_rows: dict[str, dict[str, str]],
    skip_manual_overrides: bool,
    resume: bool,
) -> None:
    planned_manual, planned_llm = selection_counts(
        paper_ids,
        manual_rows=manual_rows,
        skip_manual_overrides=skip_manual_overrides,
    )
    pending_manual, pending_llm = selection_counts(
        pending_ids,
        manual_rows=manual_rows,
        skip_manual_overrides=skip_manual_overrides,
    )
    print(f"run_id={run_id}")
    print(f"planned_total={len(paper_ids)}")
    print(f"planned_manual_overrides={planned_manual}")
    print(f"planned_llm_calls={planned_llm}")
    print(f"pending_total={len(pending_ids)}")
    print(f"pending_manual_overrides={pending_manual}")
    print(f"pending_llm_calls={pending_llm}")
    print(f"mode={'resume' if resume else 'new_run'}")


def apply_manifest_config(args: argparse.Namespace, manifest: dict[str, object]) -> None:
    config = dict(manifest.get("config") or {})
    args.references_csv = Path(str(config.get("references_csv") or args.references_csv))
    args.input_dir = Path(str(config.get("input_dir") or args.input_dir))
    args.trimmed_dir = Path(str(config.get("trimmed_dir") or args.trimmed_dir))
    args.trim_registry_path = Path(str(config.get("trim_registry_path") or args.trim_registry_path))
    args.proceedings_ready_dir = Path(str(config.get("proceedings_ready_dir") or args.proceedings_ready_dir))
    args.proceedings_ready_registry_path = Path(
        str(config.get("proceedings_ready_registry_path") or args.proceedings_ready_registry_path)
    )
    args.manual_review_path = Path(str(config.get("manual_review_path") or args.manual_review_path))
    args.model = str(config.get("model") or args.model)
    args.skip_manual_overrides = bool(config.get("skip_manual_overrides", args.skip_manual_overrides))


def publish_completed_run(args: argparse.Namespace, *, run_dir: Path, manifest: dict[str, object]) -> None:
    source_count, count_count = publish_run_outputs(
        run_dir=run_dir,
        manifest=manifest,
        output_path=args.output_path,
        count_output_path=args.count_output_path,
    )
    refresh_artifact_registry(args.skip_registry_refresh)
    completed_ids = completed_paper_ids(run_dir)
    error_rows = load_error_rows(run_dir)
    write_progress(
        run_dir,
        manifest=manifest,
        completed_paper_ids=completed_ids,
        error_count=len(error_rows),
        published_at_utc=now_utc_iso(),
    )
    logger.info(
        "Published %d source rows to %s and %d count rows to %s from run %s",
        source_count,
        args.output_path,
        count_count,
        args.count_output_path,
        run_dir.name,
    )


def main() -> None:
    args = parse_args()
    validate_args(args)

    if args.publish_only:
        run_dir = run_dir_for(args.run_root, args.run_id)
        manifest = load_run_manifest(run_dir)
        materialise_run_snapshots(run_dir, manifest=manifest)
        publish_completed_run(args, run_dir=run_dir, manifest=manifest)
        return

    manifest: dict[str, object]
    run_id = args.run_id or default_run_id()
    if args.resume:
        run_dir = run_dir_for(args.run_root, run_id)
        manifest = load_run_manifest(run_dir)
        apply_manifest_config(args, manifest)
        planned_ids = [str(paper_id) for paper_id in manifest.get("paper_ids", [])]
    else:
        planned_paths = collect_text_paths(args.input_dir, args.paper_id, args.limit)
        planned_ids = [path.stem for path in planned_paths]
        if not planned_ids:
            logger.warning("No text JSONs found to process.")
            sys.exit(0)
        manifest = {}

    reference_rows = load_reference_rows(args.references_csv)
    trim_rows = load_csv_rows_by_id(args.trim_registry_path, "paper_id")
    ready_rows = load_ready_rows_by_id(args.proceedings_ready_registry_path)
    manual_rows: dict[str, dict[str, str]] = {}
    if not args.skip_manual_overrides:
        manual_rows = load_csv_rows_by_id(args.manual_review_path, "paper_id")

    if args.resume:
        completed_ids = set(completed_paper_ids(run_dir))
    else:
        completed_ids = set()
    pending_ids = [paper_id for paper_id in planned_ids if paper_id not in completed_ids]
    if args.resume and args.limit > 0:
        pending_ids = pending_ids[: args.limit]

    if args.estimate_only:
        print_selection_summary(
            run_id=run_id,
            paper_ids=planned_ids,
            pending_ids=pending_ids,
            manual_rows=manual_rows,
            skip_manual_overrides=args.skip_manual_overrides,
            resume=args.resume,
        )
        return

    if args.dry_run:
        print_selection_summary(
            run_id=run_id,
            paper_ids=planned_ids,
            pending_ids=pending_ids,
            manual_rows=manual_rows,
            skip_manual_overrides=args.skip_manual_overrides,
            resume=args.resume,
        )
        for paper_id in pending_ids:
            source = "manual_override" if paper_id in manual_rows else "llm"
            logger.info("  [dry-run] %s -> %s", paper_id, source)
        logger.info("Dry run complete - %d papers would be processed.", len(pending_ids))
        return

    pending_manual, pending_llm = selection_counts(
        pending_ids,
        manual_rows=manual_rows,
        skip_manual_overrides=args.skip_manual_overrides,
    )
    if pending_llm > 0 and not args.allow_paid_run:
        raise SystemExit(
            "Refusing to start a paid LLM run without explicit approval. "
            "Re-run with --allow-paid-run after the user has approved the spend."
        )

    if args.resume:
        logger.info(
            "Resuming run %s with %d pending papers (%d manual overrides, %d LLM calls)",
            run_id,
            len(pending_ids),
            pending_manual,
            pending_llm,
        )
    else:
        planned_manual, planned_llm = selection_counts(
            planned_ids,
            manual_rows=manual_rows,
            skip_manual_overrides=args.skip_manual_overrides,
        )
        manifest = build_run_manifest(
            run_id=run_id,
            paper_ids=planned_ids,
            references_csv=args.references_csv,
            input_dir=args.input_dir,
            trimmed_dir=args.trimmed_dir,
            proceedings_ready_dir=args.proceedings_ready_dir,
            trim_registry_path=args.trim_registry_path,
            proceedings_ready_registry_path=args.proceedings_ready_registry_path,
            manual_review_path=args.manual_review_path,
            model=args.model,
            skip_manual_overrides=args.skip_manual_overrides,
            planned_manual_overrides=planned_manual,
            planned_llm_calls=planned_llm,
        )
        run_dir = initialise_run(args.run_root, manifest, resume=False)
        logger.info(
            "Created run %s with %d planned papers (%d manual overrides, %d LLM calls)",
            run_id,
            len(planned_ids),
            planned_manual,
            planned_llm,
        )

    if not pending_ids:
        logger.info("Run %s has no pending papers.", run_id)
        if args.publish:
            materialise_run_snapshots(run_dir, manifest=manifest)
            publish_completed_run(args, run_dir=run_dir, manifest=manifest)
        return

    invocation_start = time.monotonic()
    newly_completed = 0
    last_completed_paper_id = ""
    attempted_this_invocation = 0
    current_error_count = len(load_error_rows(run_dir))
    progress_bar = Stage04ProgressBar(
        total_pending=len(pending_ids),
        planned_total=len(planned_ids),
        completed_before_start=len(completed_ids),
        enabled=pending_llm > 0 and (args.show_progress or sys.stderr.isatty()),
    )
    progress_bar.render(
        attempted_count=0,
        durable_completed=len(completed_ids),
        error_count=current_error_count,
        status="starting",
    )

    for paper_id in pending_ids:
        if args.max_runtime_minutes > 0:
            elapsed_minutes = (time.monotonic() - invocation_start) / 60.0
            if elapsed_minutes >= args.max_runtime_minutes:
                logger.warning(
                    "Stopping run %s after %.2f minutes due to --max-runtime-minutes.",
                    run_id,
                    elapsed_minutes,
                )
                break

        text_path = args.input_dir / f"{paper_id}.json"
        if not text_path.exists():
            append_error_row(
                run_dir,
                paper_id=paper_id,
                error_type="missing_text_json",
                error_message=f"Missing text JSON: {text_path}",
            )
            attempted_this_invocation += 1
            current_error_count += 1
            progress_bar.render(
                attempted_count=attempted_this_invocation,
                durable_completed=len(completed_ids) + newly_completed,
                error_count=current_error_count,
                last_paper_id=paper_id,
                status="missing_text_json",
            )
            continue

        reference_row = reference_rows.get(paper_id, {})
        trim_row = trim_rows.get(paper_id, {})
        manual_row = manual_rows.get(paper_id)

        text_record = load_text_json(text_path)
        preferred_path = preferred_proceedings_text_path(
            text_path,
            ready_dir=args.proceedings_ready_dir,
            fallback_trimmed_dir=args.trimmed_dir,
        )
        preferred_record = None
        preferred_text_source = "full_text"
        if preferred_path != text_path and preferred_path.exists():
            preferred_record = load_text_json(preferred_path)
            if preferred_path.parent == args.proceedings_ready_dir:
                preferred_text_source = preferred_proceedings_text_source(
                    paper_id,
                    ready_rows=ready_rows,
                    ready_registry_path=args.proceedings_ready_registry_path,
                )
            else:
                preferred_text_source = "trimmed"

        try:
            result = process_paper(
                paper_id=paper_id,
                reference_row=reference_row,
                text_record=text_record,
                preferred_record=preferred_record,
                preferred_text_source=preferred_text_source,
                trim_row=trim_row,
                manual_row=manual_row,
                model=args.model,
            )
        except Exception as exc:
            append_error_row(
                run_dir,
                paper_id=paper_id,
                error_type=exc.__class__.__name__,
                error_message=str(exc),
            )
            attempted_this_invocation += 1
            current_error_count += 1
            logger.exception("Failed to classify %s - recorded error and continuing", paper_id)
            progress_bar.render(
                attempted_count=attempted_this_invocation,
                durable_completed=len(completed_ids) + newly_completed,
                error_count=current_error_count,
                last_paper_id=paper_id,
                status="error",
            )
            continue

        text_json_rel = _relative_to_repo(text_path)
        preferred_json_rel = _relative_to_repo(preferred_path if preferred_record else text_path)
        proceedings_detected = (trim_row.get("proceedings_detected") or "").strip().lower() == "true"
        trim_status = (trim_row.get("trim_status") or "").strip()
        version = CATEGORISATION_VERSION if args.model == DEFAULT_MODEL else f"llm_v1_{args.model}"

        source_row = result_to_registry_row(
            result,
            reference_row=reference_row,
            text_json_path=text_json_rel,
            preferred_text_json_path=preferred_json_rel,
            preferred_text_source=preferred_text_source,
            proceedings_detected=proceedings_detected,
            trim_status=trim_status,
            categorisation_version=version,
        )
        count_row = result_to_count_registry_row(
            result,
            reference_row=reference_row,
            preferred_text_json_path=preferred_json_rel,
            preferred_text_source=preferred_text_source,
            count_version=version,
        )
        if count_row.get("likely_sps_case_count", "").strip():
            source_row["likely_case_count"] = count_row["likely_sps_case_count"]

        append_result_record(
            run_dir,
            {
                "paper_id": paper_id,
                "classification_source": result.classification_source,
                "saved_at_utc": now_utc_iso(),
                "source_row": source_row,
                "count_row": count_row,
            },
        )

        newly_completed += 1
        attempted_this_invocation += 1
        last_completed_paper_id = paper_id
        logger.info(
            "  %s -> %s (%s, %s, count=%s)",
            paper_id,
            result.source_type.value,
            result.confidence.value,
            result.classification_source,
            count_row.get("likely_sps_case_count", "").strip() or "NA",
        )
        progress_bar.render(
            attempted_count=attempted_this_invocation,
            durable_completed=len(completed_ids) + newly_completed,
            error_count=current_error_count,
            last_paper_id=paper_id,
        )

        if newly_completed % args.checkpoint_every == 0:
            materialise_run_snapshots(run_dir, manifest=manifest)
            write_progress(
                run_dir,
                manifest=manifest,
                completed_paper_ids=completed_paper_ids(run_dir),
                error_count=len(load_error_rows(run_dir)),
                last_completed_paper_id=last_completed_paper_id,
            )

    materialise_run_snapshots(run_dir, manifest=manifest)
    completed_after_run = completed_paper_ids(run_dir)
    error_rows = load_error_rows(run_dir)
    write_progress(
        run_dir,
        manifest=manifest,
        completed_paper_ids=completed_after_run,
        error_count=len(error_rows),
        last_completed_paper_id=last_completed_paper_id,
    )
    progress_status = "done" if attempted_this_invocation == len(pending_ids) else "stopped"
    progress_bar.finish(
        attempted_count=attempted_this_invocation,
        durable_completed=len(completed_after_run),
        error_count=len(error_rows),
        last_paper_id=last_completed_paper_id,
        status=progress_status,
    )
    logger.info(
        "Run %s now has %d/%d completed papers and %d recorded errors",
        run_id,
        len(completed_after_run),
        len(planned_ids),
        len(error_rows),
    )

    if args.publish:
        publish_completed_run(args, run_dir=run_dir, manifest=manifest)
    else:
        logger.info(
            "Run artefacts saved under %s. Re-run with --publish-only --run-id %s to publish canonical outputs.",
            run_dir,
            run_id,
        )


if __name__ == "__main__":
    main()
