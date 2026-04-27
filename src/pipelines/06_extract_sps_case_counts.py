from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
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
    build_case_count_record as _build_case_count_record,
    build_case_count_candidate_package,
    relative_to_repo,
    write_count_rows,
)
from src.pipelines.stage06_counting.classify import DEFAULT_MODEL
from src.pipelines.stage06_counting.controller import adjudicated_count_row, heuristic_count_row


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

# Backwards-compatible script-level export used by legacy tests and notebooks.
build_case_count_record = _build_case_count_record


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_run_id() -> str:
    return datetime.now(timezone.utc).strftime("stage06_count_%Y%m%dT%H%M%SZ")


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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _verification_needed(*, verification_mode: str, count_eligible: bool, llm_routing_recommended: bool) -> bool:
    if verification_mode == "heuristic_only":
        return False
    if verification_mode == "always":
        return True
    if verification_mode == "strict":
        return count_eligible
    return llm_routing_recommended


def _estimate_summary(packages: list[tuple[Path, object, object, object]]) -> None:
    total = len(packages)
    llm_recommended = sum(1 for _, package, _, _ in packages if package.llm_routing_recommended)
    count_eligible = sum(1 for _, package, _, _ in packages if package.count_eligible)
    print(f"Stage 06 estimate-only summary at {now_utc_iso()}")
    print(f"Selected papers: {total}")
    print(f"Count-eligible papers: {count_eligible}")
    print(f"Packages recommending LLM adjudication: {llm_recommended}")


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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Hybrid extractable SPS case-count stage with heuristic candidates and optional LLM adjudication."
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
    parser.add_argument(
        "--verification-mode",
        choices=("heuristic_only", "targeted", "strict", "always"),
        default="always",
        help="Whether to use only heuristics or route candidate packages to the LLM adjudicator.",
    )
    parser.add_argument("--estimate-only", action="store_true", help="Estimate the run without making any LLM calls.")
    parser.add_argument(
        "--allow-paid-run",
        action="store_true",
        help="Required before any paid LLM adjudication call is made.",
    )
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI model for count adjudication.")
    parser.add_argument(
        "--skip-registry-refresh",
        action="store_true",
        help="Do not rebuild paper_artifact_registry.csv after writing the count registry.",
    )
    parser.add_argument(
        "--allow-unresolved-export",
        action="store_true",
        help="Allow writing the output CSV even when stage 06 leaves manual-review rows unresolved.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    run_id = args.run_id or default_run_id()
    run_dir = args.run_root / run_id

    reference_rows = load_reference_rows(args.references_csv)
    source_rows = load_csv_rows_by_id(args.source_registry_path, "paper_id")
    ready_rows = load_ready_rows_by_id(TEXT_PROCEEDINGS_READY_REGISTRY_PATH)

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
        _estimate_summary(packages)
        return

    if args.verification_mode != "heuristic_only":
        needs_llm = any(
            _verification_needed(
                verification_mode=args.verification_mode,
                count_eligible=package.count_eligible,
                llm_routing_recommended=package.llm_routing_recommended,
            )
            for _, package, _, _ in packages
        )
        if needs_llm and not args.allow_paid_run:
            raise SystemExit(
                "Refusing to start a paid LLM run without --allow-paid-run. "
                "Re-run with --estimate-only first if you want to inspect the candidate mix."
            )

    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        run_dir / "run_manifest.json",
        {
            "run_id": run_id,
            "created_at_utc": now_utc_iso(),
            "verification_mode": args.verification_mode,
            "model": args.model,
            "paper_ids": [path.stem for path, _, _, _ in packages],
        },
    )

    rows: list[dict[str, str]] = []
    for text_path, package, text_record, preferred_record in packages:
        candidate_path = run_dir / "candidate_packages" / f"{package.paper_id}.json"
        _write_json(candidate_path, package.to_dict())
        candidate_json_path = relative_to_repo(candidate_path)

        use_llm = _verification_needed(
            verification_mode=args.verification_mode,
            count_eligible=package.count_eligible,
            llm_routing_recommended=package.llm_routing_recommended,
        )
        if use_llm:
            row = adjudicated_count_row(
                package,
                model=args.model,
                run_dir=run_dir,
                count_version=f"hybrid_v1_{args.model}",
                candidate_json_path=candidate_json_path,
            )
        else:
            row = heuristic_count_row(
                package,
                count_version=HEURISTIC_VERSION,
                candidate_json_path=candidate_json_path,
            )
        rows.append(row)
        _write_json(
            run_dir / "results" / f"{package.paper_id}.json",
            {
                "paper_id": package.paper_id,
                "count_row": row,
                "source_text_json_path": relative_to_repo(text_path),
                "preferred_text_json_path": package.preferred_text_json_path,
            },
        )

    unresolved_paper_ids = _unresolved_paper_ids(rows)
    if unresolved_paper_ids and not args.allow_unresolved_export:
        unresolved_preview = ", ".join(unresolved_paper_ids[:12])
        if len(unresolved_paper_ids) > 12:
            unresolved_preview += ", ..."
        raise SystemExit(
            "Refusing to write the stage 06 registry because unresolved manual-review rows remain: "
            f"{unresolved_preview}. Review the run artefacts under {relative_to_repo(run_dir)} or "
            "re-run with --allow-unresolved-export for a non-canonical QA export."
        )

    write_count_rows(rows, args.output_path)
    refresh_artifact_registry(args.skip_registry_refresh)
    print(f"Wrote {len(rows)} rows to {args.output_path}")


if __name__ == "__main__":
    main()
