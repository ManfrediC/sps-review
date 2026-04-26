from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stage07_XML.core import (
    DEFAULT_ANNOTATION_MODEL,
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_REGISTRY_PATH,
    REPO_ROOT,
    SOURCE_CASE_COUNT_PATH,
    SOURCE_CATEGORISATION_PATH,
    SOURCE_MANUAL_REVIEW_PATH,
    build_manifest_run_id,
    compile_reviewed_annotation_payload,
    collect_candidate_ids,
    deterministic_annotation_for_route,
    ensure_output_dirs,
    initial_targets,
    load_csv_rows_by_id,
    output_paths,
    parse_stage06_prior,
    process_paper,
    prepare_source,
    resolve_source_json_path,
    resolve_route_decision,
    route_mode,
    write_manifest,
    write_process_result,
    write_registry,
)
from stage07_XML.openai_client import annotate_with_openai
from _source_routing import resolve_source_row


ARTIFACT_REGISTRY_SCRIPT = REPO_ROOT / "src" / "pipelines" / "12_build_paper_artifact_registry.py"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Stage 07 XML-style patient/group views for LangExtract."
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Root directory for Stage 07 XML canonical JSON and annotated text outputs.",
    )
    parser.add_argument(
        "--registry-path",
        type=Path,
        default=DEFAULT_REGISTRY_PATH,
        help="Stage 07 XML registry CSV path.",
    )
    parser.add_argument(
        "--source-categorisation-path",
        type=Path,
        default=SOURCE_CATEGORISATION_PATH,
        help="Stage 04 source categorisation registry.",
    )
    parser.add_argument(
        "--source-manual-review-path",
        type=Path,
        default=SOURCE_MANUAL_REVIEW_PATH,
        help="Manual source categorisation override ledger.",
    )
    parser.add_argument(
        "--stage06-path",
        type=Path,
        default=SOURCE_CASE_COUNT_PATH,
        help="Canonical Stage 06 SPS case-count registry.",
    )
    parser.add_argument(
        "--paper-id",
        action="append",
        default=[],
        help="Specific paper ID to process. Repeat for multiple IDs.",
    )
    parser.add_argument("--limit", type=int, default=0, help="Maximum candidate papers to process.")
    parser.add_argument(
        "--route-mode",
        choices=["all", "individual", "individual_case_split", "group"],
        default="all",
        help="Restrict processing to one reviewed LangExtract route.",
    )
    parser.add_argument(
        "--manifest-run-id",
        default="",
        help="Optional manifest run id override.",
    )
    parser.add_argument(
        "--mock-annotation-dir",
        type=Path,
        default=None,
        help="Directory containing {paper_id}.json mocked span-metadata responses.",
    )
    parser.add_argument(
        "--reviewed-annotation-dir",
        type=Path,
        default=None,
        help="Directory containing {paper_id}.json reviewed source-backed annotation specs.",
    )
    parser.add_argument(
        "--annotation-model",
        default=DEFAULT_ANNOTATION_MODEL,
        help="OpenAI model used when live annotation is needed.",
    )
    parser.add_argument(
        "--openai-api-key",
        default="",
        help="Explicit OpenAI API key for live GPT-5.5 annotation.",
    )
    parser.add_argument(
        "--allow-paid-run",
        action="store_true",
        help="Required before any live GPT annotation call is made.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing per-paper Stage 07 XML outputs.",
    )
    parser.add_argument(
        "--max-block-chars",
        type=int,
        default=3500,
        help="Maximum prepared source characters per paragraph block.",
    )
    parser.add_argument(
        "--skip-artifact-registry-refresh",
        action="store_true",
        help="Do not refresh the master paper artefact registry after writing outputs.",
    )
    return parser.parse_args()


def load_mock_annotation(mock_dir: Path | None, paper_id: str) -> dict[str, Any] | None:
    if mock_dir is None:
        return None
    path = mock_dir / f"{paper_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_reviewed_annotation(
    *,
    reviewed_dir: Path | None,
    paper_id: str,
    prepared_source: Any,
) -> dict[str, Any] | None:
    if reviewed_dir is None:
        return None
    path = reviewed_dir / f"{paper_id}.json"
    if not path.exists():
        return None
    reviewed_payload = json.loads(path.read_text(encoding="utf-8"))
    return compile_reviewed_annotation_payload(
        reviewed_payload=reviewed_payload,
        prepared_source=prepared_source,
    )


def resolve_api_key(explicit_key: str) -> str:
    if explicit_key.strip():
        return explicit_key.strip()
    env_path = REPO_ROOT / "env" / "openai_api_key.env"
    if not env_path.exists():
        raise RuntimeError("A live Stage 07 XML annotation run needs OPENAI_API_KEY in env/openai_api_key.env.")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("OPENAI_API_KEY="):
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("No usable OPENAI_API_KEY was found in env/openai_api_key.env.")


def refresh_artifact_registry(skip_refresh: bool) -> None:
    if skip_refresh:
        return
    subprocess.run(
        [sys.executable, str(ARTIFACT_REGISTRY_SCRIPT)],
        cwd=str(REPO_ROOT),
        check=True,
    )


def main() -> None:
    args = parse_args()
    paths = output_paths(args.output_root)
    ensure_output_dirs(paths)
    manifest_run_id = args.manifest_run_id or build_manifest_run_id()
    manifest_path = paths.manifests_dir / f"{manifest_run_id}.jsonl"
    trace_dir = REPO_ROOT / "results" / "stage07_xml_runs" / manifest_run_id

    source_rows = load_csv_rows_by_id(args.source_categorisation_path, "paper_id")
    manual_rows = load_csv_rows_by_id(args.source_manual_review_path, "paper_id")
    stage06_rows = load_csv_rows_by_id(args.stage06_path, "paper_id")
    candidate_ids = collect_candidate_ids(
        source_rows=source_rows,
        manual_rows=manual_rows,
        paper_ids=args.paper_id,
        limit=args.limit,
        route_filter=args.route_mode,
    )
    if not candidate_ids:
        raise SystemExit("No Stage 07 XML candidate papers matched the current filters.")

    api_key = ""
    if args.mock_annotation_dir is None and args.allow_paid_run:
        api_key = resolve_api_key(args.openai_api_key)

    registry_rows: list[dict[str, str]] = []
    manifest_records: list[dict[str, Any]] = []
    skipped = 0
    for paper_id in candidate_ids:
        paper_json_path = paths.papers_dir / f"{paper_id}.json"
        if paper_json_path.exists() and not args.force:
            skipped += 1
            continue

        source_row = source_rows.get(paper_id, {})
        prior = parse_stage06_prior(stage06_rows.get(paper_id, {}))
        source_path = resolve_source_json_path(
            paper_id=paper_id,
            source_row=source_row,
            stage06_prior=prior,
        )
        prepared_source = prepare_source(
            paper_id=paper_id,
            source_path=source_path,
            max_block_chars=args.max_block_chars,
        )
        annotation_payload = load_reviewed_annotation(
            reviewed_dir=args.reviewed_annotation_dir,
            paper_id=paper_id,
            prepared_source=prepared_source,
        )
        if annotation_payload is None:
            annotation_payload = load_mock_annotation(args.mock_annotation_dir, paper_id)
        if annotation_payload is None and args.mock_annotation_dir is None and args.allow_paid_run:
            resolved = resolve_source_row(
                paper_id=paper_id,
                heuristic_row=source_row,
                manual_row=manual_rows.get(paper_id, {}),
            )
            route = route_mode(source_row, resolved)
            route_decision = resolve_route_decision(
                route=route,
                stage06_prior=prior,
                prepared_source=prepared_source,
            )
            route = route_decision.route
            targets = initial_targets(
                route=route,
                stage06_prior=prior,
                recovered_target_labels=route_decision.recovered_target_labels,
            )
            if route_decision.manual_review_reasons:
                annotation_payload = None
            elif route == "individual":
                deterministic_payload = deterministic_annotation_for_route(
                    prepared_source=prepared_source,
                    targets=targets,
                    route=route,
                )
                if deterministic_payload.get("manual_review_reasons"):
                    annotation_payload = annotate_with_openai(
                        prepared_source=prepared_source,
                        targets=targets,
                        model=args.annotation_model,
                        api_key=api_key,
                        trace_dir=trace_dir,
                    )
            elif route in {"individual_case_split", "group"}:
                annotation_payload = annotate_with_openai(
                    prepared_source=prepared_source,
                    targets=targets,
                    model=args.annotation_model,
                    api_key=api_key,
                    trace_dir=trace_dir,
                )

        result = process_paper(
            paper_id=paper_id,
            source_row=source_rows.get(paper_id, {}),
            manual_row=manual_rows.get(paper_id, {}),
            stage06_row=stage06_rows.get(paper_id, {}),
            paths=paths,
            manifest_run_id=manifest_run_id,
            annotation_model=args.annotation_model,
            annotation_payload=annotation_payload,
            max_block_chars=args.max_block_chars,
        )
        write_process_result(result)
        registry_rows.append(result.registry_row)
        manifest_records.extend(result.manifest_records)

    write_registry(registry_rows, args.registry_path)
    write_manifest(manifest_records, manifest_path)
    refresh_artifact_registry(args.skip_artifact_registry_refresh)

    ready_records = sum(1 for record in manifest_records if record.get("ready_for_langextract"))
    print(
        f"Wrote {len(registry_rows)} Stage 07 XML registry rows to {args.registry_path}; "
        f"manifest records={len(manifest_records)} ready={ready_records} skipped_existing={skipped}."
    )


if __name__ == "__main__":
    main()
