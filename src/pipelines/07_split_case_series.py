from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from _source_routing import load_csv_rows_by_id
from _stage07_units import (
    DEFAULT_ADJUDICATION_MODEL,
    DEFAULT_CANDIDATE_GENERATION_MODE,
    SOURCE_CASE_COUNT_PATH,
    SOURCE_CATEGORISATION_PATH,
    SOURCE_MANUAL_REVIEW_PATH,
    STAGE07_MANIFEST_DIR,
    STAGE07_REGISTRY_PATH,
    STAGE07_UNITS_DIR,
    build_manifest_run_id,
    collect_candidate_ids,
    process_paper,
    write_manifest,
    write_registry,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_REGISTRY_SCRIPT = REPO_ROOT / "src" / "pipelines" / "12_build_paper_artifact_registry.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Publish stage-07 patient and group units for case-series papers."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=STAGE07_UNITS_DIR,
        help="Directory for canonical or run-scoped stage-07 per-paper JSON outputs.",
    )
    parser.add_argument(
        "--registry-path",
        type=Path,
        default=STAGE07_REGISTRY_PATH,
        help="Stage-07 CSV registry output path.",
    )
    parser.add_argument(
        "--manifest-dir",
        type=Path,
        default=STAGE07_MANIFEST_DIR,
        help="Directory for derived stage-07 JSONL manifests.",
    )
    parser.add_argument(
        "--manifest-run-id",
        default="",
        help="Optional run id override for the derived manifest file.",
    )
    parser.add_argument(
        "--source-categorisation-path",
        type=Path,
        default=SOURCE_CATEGORISATION_PATH,
        help="Stage-04 source categorisation registry.",
    )
    parser.add_argument(
        "--source-manual-review-path",
        type=Path,
        default=SOURCE_MANUAL_REVIEW_PATH,
        help="Manual source categorisation overrides.",
    )
    parser.add_argument(
        "--stage06-path",
        type=Path,
        default=SOURCE_CASE_COUNT_PATH,
        help="Canonical stage-06 SPS case-count registry.",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Specific paper ID to process. Repeat for multiple IDs.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Maximum number of candidate papers to process.")
    parser.add_argument(
        "--candidate-generation-mode",
        default=DEFAULT_CANDIDATE_GENERATION_MODE,
        help="Label recorded in stage07_method.candidate_generation_mode.",
    )
    parser.add_argument(
        "--adjudication-model",
        default=DEFAULT_ADJUDICATION_MODEL,
        help="Adjudication model label recorded in stage07_method.adjudication_model.",
    )
    parser.add_argument(
        "--skip-registry-refresh",
        action="store_true",
        help="Do not rebuild paper_artifact_registry.csv after writing outputs.",
    )
    return parser.parse_args()


def refresh_artifact_registry(skip_refresh: bool) -> None:
    if skip_refresh:
        return
    subprocess.run(
        [sys.executable, str(ARTIFACT_REGISTRY_SCRIPT)],
        check=True,
        cwd=str(REPO_ROOT),
    )


def main() -> None:
    args = parse_args()
    if args.adjudication_model != DEFAULT_ADJUDICATION_MODEL:
        raise SystemExit(
            "OpenAI adjudication is not wired in this rewrite yet. "
            "Rerun with --adjudication-model disabled."
        )

    source_rows = load_csv_rows_by_id(args.source_categorisation_path, "paper_id")
    manual_rows = load_csv_rows_by_id(args.source_manual_review_path, "paper_id")
    stage06_rows = load_csv_rows_by_id(args.stage06_path, "paper_id")
    candidate_ids = collect_candidate_ids(
        source_rows=source_rows,
        paper_ids=args.paper_id,
        limit=args.limit,
    )
    if not candidate_ids:
        raise SystemExit("No stage-07 candidate papers matched the current filters.")

    manifest_run_id = args.manifest_run_id or build_manifest_run_id()
    manifest_path = args.manifest_dir / f"{manifest_run_id}.jsonl"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    args.manifest_dir.mkdir(parents=True, exist_ok=True)

    registry_rows: list[dict[str, str]] = []
    manifest_records: list[dict[str, object]] = []
    for paper_id in candidate_ids:
        result = process_paper(
            paper_id=paper_id,
            source_row=source_rows.get(paper_id, {}),
            manual_row=manual_rows.get(paper_id, {}),
            stage06_row=stage06_rows.get(paper_id, {}),
            paper_output_dir=args.output_dir,
            manifest_run_id=manifest_run_id,
            candidate_generation_mode=args.candidate_generation_mode,
            adjudication_model=args.adjudication_model,
        )
        paper_output_path = args.output_dir / f"{paper_id}.json"
        paper_output_path.write_text(
            json.dumps(result.paper_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        registry_rows.append(result.registry_row)
        manifest_records.extend(result.manifest_records)

    write_registry(registry_rows, args.registry_path)
    write_manifest(manifest_records, manifest_path)
    refresh_artifact_registry(args.skip_registry_refresh)

    published_papers = sum(1 for row in registry_rows if row["publication_status"] != "manual_review_required")
    print(
        f"Wrote {len(registry_rows)} stage-07 rows to {args.registry_path} "
        f"and {len(manifest_records)} manifest records to {manifest_path}. "
        f"Published papers={published_papers} manual_review={len(registry_rows) - published_papers}"
    )


if __name__ == "__main__":
    main()
