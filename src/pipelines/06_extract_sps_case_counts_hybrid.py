from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.pipelines._proceedings_ready import (
    TEXT_PROCEEDINGS_READY_DIR,
    TEXT_PROCEEDINGS_READY_REGISTRY_PATH,
    load_ready_rows_by_id,
    preferred_proceedings_text_path,
)
from src.pipelines._sps_case_count_registry import (
    HEURISTIC_VERSION,
    build_case_count_candidate_package,
    relative_to_repo,
    write_count_rows,
)
from src.pipelines.stage06_counting.classify import DEFAULT_MODEL as DEFAULT_GPT_MODEL
from src.pipelines.stage06_counting.controller import heuristic_count_row
from src.pipelines.stage06_counting.hybrid import gpt_adjudication_needed, hybrid_count_row
from src.pipelines.stage06_counting.local_ollama import (
    DEFAULT_OLLAMA_BASE_URL,
    DEFAULT_OLLAMA_MODEL,
    DEFAULT_OLLAMA_TIMEOUT_SECONDS,
)
from src.pipelines.stage06_counting.overrides import (
    MANUAL_REVIEW_LEDGER_PATH,
    apply_override_to_count_row,
    ensure_override_ledger,
    reviewed_override_rows_by_id,
)
from src.pipelines.stage06_counting.runtime import run_stage06_dependency_preflight


REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCES_CSV = REPO_ROOT / "data" / "references" / "sps_references_export.csv"
TEXT_DIR = REPO_ROOT / "data" / "extraction_json" / "text"
TEXT_TRIMMED_DIR = REPO_ROOT / "data" / "extraction_json" / "text_trimmed"
SOURCE_REGISTRY_PATH = REPO_ROOT / "data" / "references" / "source_categorisation_registry.csv"
OUTPUT_PATH = REPO_ROOT / "data" / "references" / "source_sps_case_count_registry.csv"
ARTIFACT_REGISTRY_SCRIPT = REPO_ROOT / "src" / "pipelines" / "12_build_paper_artifact_registry.py"
RUN_ROOT = REPO_ROOT / "results" / "stage06_count_runs"

UNRESOLVED_VERIFICATION_STATUSES = {
    "llm_invalid_manual_review_required",
    "llm_request_failed_manual_review_required",
    "llm_semantic_conflict_manual_review_required",
    "llm_manual_review_required",
    "llm_unable_to_determine",
}


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("stage06_hybrid_%Y%m%dT%H%M%SZ")


def load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def load_reference_rows(path: Path) -> dict[str, dict[str, str]]:
    rows = {}
    for row in load_csv_rows(path):
        key = (row.get("Covidence") or "").strip()
        if key:
            rows[key] = row
    return rows


def load_csv_rows_by_id(path: Path, key_column: str) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    rows = {}
    for row in load_csv_rows(path):
        key = (row.get(key_column) or "").strip()
        if key:
            rows[key] = row
    return rows


def load_text_record(path: Path) -> dict[str, object]:
    record = json.loads(path.read_text(encoding="utf-8"))
    record["_path"] = str(path)
    return record


def collect_text_paths(input_dir: Path, paper_ids: list[str], limit: int) -> list[Path]:
    paths = sorted(input_dir.glob("*.json"))
    if paper_ids:
        wanted = {paper_id.strip() for paper_id in paper_ids if paper_id.strip()}
        paths = [path for path in paths if path.stem in wanted]
    if limit and limit > 0:
        paths = paths[:limit]
    return paths


def _is_canonical_output_path(path: Path) -> bool:
    return path.resolve() == OUTPUT_PATH.resolve()


def _is_partial_selection(args: argparse.Namespace) -> bool:
    return bool(args.paper_id) or bool(args.limit and args.limit > 0)


def _validate_output_scope(args: argparse.Namespace) -> None:
    if not _is_partial_selection(args):
        return
    if not _is_canonical_output_path(args.output_path):
        return
    if args.allow_partial_canonical_export:
        return
    raise SystemExit(
        "Refusing to write a subset stage-06 run to the canonical registry. "
        "Use --output-path under qa/validation/ for partial QA exports, or rerun "
        "without --paper-id/--limit for a full canonical refresh."
    )


def refresh_artifact_registry(skip_refresh: bool) -> None:
    if skip_refresh:
        return
    subprocess.run(
        [sys.executable, str(ARTIFACT_REGISTRY_SCRIPT)],
        check=True,
        cwd=str(REPO_ROOT),
    )


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    json_text = json.dumps(payload, ensure_ascii=False, indent=2)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(json_text)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _load_json_if_valid(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _resolved_result_paper_id(payload: dict[str, object], fallback: str = "") -> str:
    count_row = payload.get("count_row") if isinstance(payload.get("count_row"), dict) else {}
    return str(payload.get("paper_id") or count_row.get("paper_id") or fallback).strip()


def _completed_result_paper_ids(run_dir: Path) -> list[str]:
    results_dir = run_dir / "results"
    if not results_dir.exists():
        return []
    completed_ids: list[str] = []
    for result_path in sorted(results_dir.glob("*.json")):
        payload = _load_json_if_valid(result_path)
        if not payload:
            continue
        paper_id = _resolved_result_paper_id(payload, fallback=result_path.stem)
        if paper_id and paper_id == result_path.stem:
            completed_ids.append(paper_id)
    return completed_ids


def _update_run_manifest(
    run_dir: Path,
    *,
    default_payload: dict[str, object] | None = None,
    **updates: object,
) -> None:
    manifest_path = run_dir / "run_manifest.json"
    payload = _load_json_if_valid(manifest_path)
    if not payload and default_payload:
        payload.update(default_payload)
    payload.update({key: value for key, value in updates.items() if value is not None})
    _write_json(manifest_path, payload)


def _estimate_summary(packages: list[tuple[Path, object, object, object]], override_rows: dict[str, dict[str, str]]) -> None:
    total = len(packages)
    count_eligible = sum(1 for _, package, _, _ in packages if package.count_eligible)
    gpt_planned = sum(1 for _, package, _, _ in packages if gpt_adjudication_needed(package))
    override_covered = sum(1 for _, package, _, _ in packages if package.paper_id in override_rows)
    print(f"Stage 06 hybrid estimate-only summary at {now_utc_iso()}")
    print(f"Selected papers: {total}")
    print(f"Count-eligible papers: {count_eligible}")
    print(f"Local Gemma calls planned: {total}")
    print(f"GPT calls planned: {gpt_planned}")
    print(f"Reviewed manual overrides available: {override_covered}")


def _row_requires_resolution(row: dict[str, str]) -> bool:
    if (row.get("count_manual_review_required") or "").strip().lower() == "true":
        return True
    return (row.get("count_verification_status") or "").strip() in UNRESOLVED_VERIFICATION_STATUSES


def _unresolved_paper_ids(rows: list[dict[str, str]]) -> list[str]:
    return [
        (row.get("paper_id") or "").strip()
        for row in rows
        if _row_requires_resolution(row)
    ]


def _apply_review_override_if_present(
    row: dict[str, str],
    *,
    override_rows: dict[str, dict[str, str]],
) -> dict[str, str]:
    paper_id = str(row.get("paper_id") or "").strip()
    override_row = override_rows.get(paper_id)
    if override_row is None:
        return row
    return apply_override_to_count_row(row, override_row)


def _cleanup_failed_attempt(
    *,
    run_dir: Path,
    run_dir_created: bool,
    output_path: Path,
    output_preexisting: bool,
    total_paper_count: int,
    error: BaseException | None = None,
) -> None:
    if run_dir_created and run_dir.exists():
        completed_ids = _completed_result_paper_ids(run_dir)
        failure_status = "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
        _update_run_manifest(
            run_dir,
            run_status=failure_status,
            finished_at_utc=now_utc_iso(),
            completed_result_count=len(completed_ids),
            total_paper_count=total_paper_count,
            completed_paper_ids=completed_ids,
            failure_type=type(error).__name__ if error is not None else "",
            failure_message=str(error or "").strip(),
        )
    if not output_preexisting and output_path.exists():
        output_path.unlink(missing_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Canonical hybrid stage-06 SPS case-count runner using deterministic guards, Gemma, GPT-5.4, and tracked reviewed overrides."
    )
    parser.add_argument("--references-csv", type=Path, default=REFERENCES_CSV)
    parser.add_argument("--input-dir", type=Path, default=TEXT_DIR)
    parser.add_argument("--trimmed-dir", type=Path, default=TEXT_TRIMMED_DIR)
    parser.add_argument("--source-registry-path", type=Path, default=SOURCE_REGISTRY_PATH)
    parser.add_argument("--output-path", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--run-root", type=Path, default=RUN_ROOT)
    parser.add_argument("--run-id", type=str, default="", help="Optional run ID for artefact output.")
    parser.add_argument("--paper-id", action="append", default=[], help="Paper ID to process.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of papers to process.")
    parser.add_argument("--estimate-only", action="store_true", help="Estimate the run without model calls.")
    parser.add_argument(
        "--allow-paid-run",
        action="store_true",
        help="Required before any paid GPT adjudication call is made.",
    )
    parser.add_argument("--local-model", default=DEFAULT_OLLAMA_MODEL, help="Ollama model for the local first pass.")
    parser.add_argument("--local-base-url", default=DEFAULT_OLLAMA_BASE_URL, help="Base URL for the local Ollama server.")
    parser.add_argument(
        "--local-timeout-seconds",
        type=float,
        default=DEFAULT_OLLAMA_TIMEOUT_SECONDS,
        help="Timeout in seconds for each local-model request.",
    )
    parser.add_argument("--gpt-model", default=DEFAULT_GPT_MODEL, help="OpenAI model for the adjudicator.")
    parser.add_argument(
        "--manual-review-path",
        type=Path,
        default=MANUAL_REVIEW_LEDGER_PATH,
        help="Path to the canonical reviewed stage-06 override ledger.",
    )
    parser.add_argument(
        "--skip-manual-overrides",
        action="store_true",
        help="Ignore the reviewed override ledger when building final output rows.",
    )
    parser.add_argument(
        "--skip-registry-refresh",
        action="store_true",
        help="Do not rebuild paper_artifact_registry.csv after writing the canonical count registry.",
    )
    parser.add_argument(
        "--allow-unresolved-export",
        action="store_true",
        help="Allow writing the output CSV even when manual-review rows remain unresolved and uncovered by overrides.",
    )
    parser.add_argument(
        "--allow-partial-canonical-export",
        action="store_true",
        help="Explicitly allow --paper-id/--limit runs to write the canonical registry. Intended only for supervised recovery.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_id = args.run_id or default_run_id()
    run_dir = args.run_root / run_id
    run_dir_created = False
    output_preexisting = args.output_path.exists()

    reference_rows = load_reference_rows(args.references_csv)
    source_rows = load_csv_rows_by_id(args.source_registry_path, "paper_id")
    ready_rows = load_ready_rows_by_id(TEXT_PROCEEDINGS_READY_REGISTRY_PATH)
    ensure_override_ledger(args.manual_review_path)
    override_rows = {} if args.skip_manual_overrides else reviewed_override_rows_by_id(args.manual_review_path)

    packages: list[tuple[Path, object, object, object]] = []
    for text_path in collect_text_paths(args.input_dir, args.paper_id, args.limit):
        preferred_path = preferred_proceedings_text_path(
            text_path,
            ready_dir=TEXT_PROCEEDINGS_READY_DIR,
            fallback_trimmed_dir=args.trimmed_dir,
        )
        text_record = load_text_record(text_path)
        preferred_record = load_text_record(preferred_path)
        package = build_case_count_candidate_package(
            reference_row=reference_rows.get(text_path.stem, {}),
            text_record=text_record,
            preferred_record=preferred_record,
            preferred_path=preferred_path,
            source_row=source_rows.get(text_path.stem, {}),
            ready_rows=ready_rows,
            heuristic_version=HEURISTIC_VERSION,
        )
        packages.append((text_path, package, text_record, preferred_record))

    if args.estimate_only:
        _estimate_summary(packages, override_rows)
        return
    _validate_output_scope(args)

    try:
        gpt_required = any(gpt_adjudication_needed(package) for _, package, _, _ in packages)
        if gpt_required and not args.allow_paid_run:
            raise SystemExit(
                "Refusing to start a paid hybrid run without --allow-paid-run. "
                "Re-run with --estimate-only first if you want to inspect the candidate mix."
            )

        if run_dir.exists():
            raise SystemExit(f"Run directory already exists: {run_dir}")

        preflight = run_stage06_dependency_preflight(
            ollama_model=args.local_model,
            ollama_base_url=args.local_base_url,
            gpt_model=args.gpt_model,
            require_openai=gpt_required,
        )

        run_dir.mkdir(parents=True, exist_ok=False)
        run_dir_created = True
        manifest_payload = {
            "run_id": run_id,
            "created_at_utc": now_utc_iso(),
            "run_status": "running",
            "started_at_utc": now_utc_iso(),
            "finished_at_utc": "",
            "local_model": args.local_model,
            "local_base_url": args.local_base_url,
            "gpt_model": args.gpt_model,
            "runtime_preflight": preflight.to_dict(),
            "manual_review_path": str(args.manual_review_path),
            "skip_manual_overrides": args.skip_manual_overrides,
            "output_path": str(args.output_path),
            "paper_ids": [path.stem for path, _, _, _ in packages],
            "total_paper_count": len(packages),
            "completed_result_count": 0,
            "completed_paper_ids": [],
            "failure_type": "",
            "failure_message": "",
            "last_completed_paper_id": "",
        }
        _write_json(run_dir / "run_manifest.json", manifest_payload)

        rows: list[dict[str, str]] = []
        for text_path, package, _, _ in packages:
            candidate_path = run_dir / "candidate_packages" / f"{package.paper_id}.json"
            _write_json(candidate_path, package.to_dict())
            candidate_json_path = relative_to_repo(candidate_path)

            if gpt_adjudication_needed(package):
                model_row = hybrid_count_row(
                    package,
                    model=args.gpt_model,
                    run_dir=run_dir,
                    count_version=f"hybrid_v2_{args.gpt_model}",
                    candidate_json_path=candidate_json_path,
                    local_model=args.local_model,
                    local_base_url=args.local_base_url,
                    local_timeout_seconds=args.local_timeout_seconds,
                )
            else:
                model_row = heuristic_count_row(
                    package,
                    count_version=f"hybrid_v2_{HEURISTIC_VERSION}",
                    candidate_json_path=candidate_json_path,
                )

            final_row = _apply_review_override_if_present(
                model_row,
                override_rows=override_rows,
            )
            rows.append(final_row)
            _write_json(
                run_dir / "results" / f"{package.paper_id}.json",
                {
                    "paper_id": package.paper_id,
                    "count_row": final_row,
                    "model_count_row": model_row,
                    "manual_override_row": override_rows.get(package.paper_id, {}),
                    "source_text_json_path": relative_to_repo(text_path),
                    "preferred_text_json_path": package.preferred_text_json_path,
                },
            )
            _update_run_manifest(
                run_dir,
                completed_result_count=len(rows),
                completed_paper_ids=[row["paper_id"] for row in rows if str(row.get("paper_id") or "").strip()],
                last_completed_paper_id=package.paper_id,
            )

        unresolved_paper_ids = _unresolved_paper_ids(rows)
        if unresolved_paper_ids and not args.allow_unresolved_export:
            unresolved_preview = ", ".join(unresolved_paper_ids[:12])
            if len(unresolved_paper_ids) > 12:
                unresolved_preview += ", ..."
            raise SystemExit(
                "Refusing to write the hybrid stage 06 registry because unresolved manual-review rows remain: "
                f"{unresolved_preview}. Review the run artefacts under {relative_to_repo(run_dir)} or "
                "re-run with --allow-unresolved-export for a non-canonical QA export."
            )

        write_count_rows(rows, args.output_path)
        refresh_artifact_registry(args.skip_registry_refresh)
        _update_run_manifest(
            run_dir,
            run_status="completed",
            finished_at_utc=now_utc_iso(),
            completed_result_count=len(rows),
            completed_paper_ids=[row["paper_id"] for row in rows if str(row.get("paper_id") or "").strip()],
            unresolved_paper_ids=unresolved_paper_ids,
            failure_type="",
            failure_message="",
        )
        print(f"Wrote {len(rows)} rows to {args.output_path}")
    except BaseException as error:
        _cleanup_failed_attempt(
            run_dir=run_dir,
            run_dir_created=run_dir_created,
            output_path=args.output_path,
            output_preexisting=output_preexisting,
            total_paper_count=len(packages),
            error=error,
        )
        raise


if __name__ == "__main__":
    main()
