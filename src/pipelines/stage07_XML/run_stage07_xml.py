"""Command-line entry point for Stage 07 XML target-view generation.

The runner wires together canonical registries, reviewed/mock annotations,
optional live model annotation, and output writing. Policy decisions that matter
for reproducibility live here: paid API calls are opt-in, reviewed annotations
take precedence over model output, and generated artefacts are written through
the core Stage 07 output helpers.
"""

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
    compile_unit_selection_payload,
    compile_reviewed_annotation_payload,
    collect_candidate_ids,
    collect_single_case_candidate_ids,
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
    single_case_passthrough_annotation,
    write_manifest,
    write_process_result,
    write_registry,
)
from stage07_XML.deepseek_client import (
    DEFAULT_DEEPSEEK_MAX_OUTPUT_TOKENS,
    DEFAULT_DEEPSEEK_MODEL,
    DEFAULT_DEEPSEEK_REQUEST_TIMEOUT_SECONDS,
    annotate_with_deepseek_units,
)
from stage07_XML.openai_client import (
    DEFAULT_OPENAI_MAX_OUTPUT_TOKENS,
    DEFAULT_OPENAI_REASONING_EFFORT,
    annotate_with_openai,
)
from stage07_XML.openai_unit_reviewer import (
    DEFAULT_OPENAI_REVIEW_MAX_OUTPUT_TOKENS,
    DEFAULT_OPENAI_REVIEW_MODEL,
    DEFAULT_OPENAI_REVIEW_REASONING_EFFORT,
    annotate_with_deepseek_openai_reviewed_units,
)
from stage07_benchmarking.telemetry import load_telemetry_rows, write_telemetry_csv, write_telemetry_jsonl
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
        "--single-case-only",
        action="store_true",
        help="Process Stage 06 high-confidence count-1 sources as Stage 07 single-case v1 units.",
    )
    parser.add_argument(
        "--single-case-start-index",
        type=int,
        default=0,
        help="Zero-based offset into the sorted Stage 06 single-case candidate list.",
    )
    parser.add_argument(
        "--single-case-audit-provider",
        choices=["none", "deepseek"],
        default="none",
        help="Optional advisory audit provider for uncertain single-case outputs.",
    )
    parser.add_argument(
        "--deepseek-api-key",
        default="",
        help="Explicit DeepSeek API key for advisory review.",
    )
    parser.add_argument(
        "--deepseek-model",
        default=DEFAULT_DEEPSEEK_MODEL,
        help="DeepSeek model for advisory review when requested.",
    )
    parser.add_argument(
        "--openai-fallback-call-limit",
        type=int,
        default=20,
        help="Maximum OpenAI fallback calls allowed during single-case advisory review.",
    )
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
        "--mock-unit-selection-dir",
        type=Path,
        default=None,
        help="Directory containing compact {paper_id}.json unit-id selection responses.",
    )
    parser.add_argument(
        "--mock-review-patch-dir",
        type=Path,
        default=None,
        help="Directory containing mocked {paper_id}.json GPT reviewer patch responses.",
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
        "--annotation-provider",
        choices=["openai", "deepseek"],
        default="openai",
        help="Provider for live annotation calls.",
    )
    parser.add_argument(
        "--annotation-architecture",
        choices=["block_offsets", "unit_ids", "unit_ids_reviewed"],
        default="block_offsets",
        help="Live annotation architecture. Defaults to the existing block-offset path.",
    )
    parser.add_argument(
        "--reasoning-effort",
        default=DEFAULT_OPENAI_REASONING_EFFORT,
        choices=["none", "minimal", "low", "medium", "high", "xhigh"],
        help="OpenAI reasoning effort for live annotation calls.",
    )
    parser.add_argument(
        "--max-output-tokens",
        type=int,
        default=DEFAULT_OPENAI_MAX_OUTPUT_TOKENS,
        help="Maximum OpenAI output token budget, including reasoning tokens.",
    )
    parser.add_argument(
        "--deepseek-max-output-tokens",
        type=int,
        default=DEFAULT_DEEPSEEK_MAX_OUTPUT_TOKENS,
        help="Maximum DeepSeek output token budget for unit-id selection.",
    )
    parser.add_argument(
        "--deepseek-request-timeout-seconds",
        type=float,
        default=DEFAULT_DEEPSEEK_REQUEST_TIMEOUT_SECONDS,
        help="DeepSeek request timeout for long-running Pro unit-id selection calls. Use 0 for SDK default.",
    )
    parser.add_argument(
        "--openai-review-model",
        default=DEFAULT_OPENAI_REVIEW_MODEL,
        help="OpenAI model for GPT reviewer-patcher calls in unit_ids_reviewed mode.",
    )
    parser.add_argument(
        "--openai-review-reasoning-effort",
        default=DEFAULT_OPENAI_REVIEW_REASONING_EFFORT,
        choices=["none", "minimal", "low", "medium", "high", "xhigh"],
        help="Reasoning effort for GPT reviewer-patcher calls in unit_ids_reviewed mode.",
    )
    parser.add_argument(
        "--openai-review-max-output-tokens",
        type=int,
        default=DEFAULT_OPENAI_REVIEW_MAX_OUTPUT_TOKENS,
        help="OpenAI output token budget for GPT reviewer-patcher calls.",
    )
    parser.add_argument(
        "--max-paid-api-cost-usd",
        type=float,
        default=0.0,
        help="Stop further paid annotation calls after this estimated batch cost. Use 0 to disable.",
    )
    parser.add_argument(
        "--relaxed-json-schema",
        action="store_true",
        help="Use non-strict JSON schema output for compatibility experiments.",
    )
    parser.add_argument(
        "--benchmark-run-id",
        default="",
        help="Optional benchmark run id to attach to live API telemetry.",
    )
    parser.add_argument(
        "--matrix-config-name",
        default="",
        help="Optional optimisation matrix configuration name for live API telemetry.",
    )
    parser.add_argument(
        "--architecture-variant",
        default="block_offsets",
        help="Architecture variant label for live API telemetry.",
    )
    parser.add_argument(
        "--telemetry-jsonl-path",
        type=Path,
        default=None,
        help="Optional JSONL path for live API telemetry rows.",
    )
    parser.add_argument(
        "--telemetry-csv-path",
        type=Path,
        default=None,
        help="Optional CSV path for live API telemetry rows.",
    )
    parser.add_argument(
        "--openai-api-key",
        default="",
        help="Explicit OpenAI API key for live OpenAI annotation or reviewer calls.",
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
    """Load a raw mocked model response for a paper, when supplied."""

    if mock_dir is None:
        return None
    path = mock_dir / f"{paper_id}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_mock_unit_selection(
    mock_dir: Path | None,
    paper_id: str,
    prepared_source: Any,
) -> dict[str, Any] | None:
    """Load a compact mocked unit-id response and compile it to spans."""

    payload = load_mock_unit_selection_payload(mock_dir, paper_id)
    if payload is None:
        return None
    return compile_unit_selection_payload(
        selection_payload=payload,
        prepared_source=prepared_source,
    )


def load_mock_unit_selection_payload(mock_dir: Path | None, paper_id: str) -> dict[str, Any] | None:
    """Load a raw mocked unit-id response for direct replay or GPT review."""

    if mock_dir is None:
        return None
    for path in (
        mock_dir / f"{paper_id}.json",
        mock_dir / f"{paper_id}.unit_selection.response.txt",
        mock_dir / f"{paper_id}.reviewed_primary.response.txt",
    ):
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def load_mock_review_patch(mock_dir: Path | None, paper_id: str) -> dict[str, Any] | None:
    """Load a mocked GPT reviewer patch response, when supplied."""

    if mock_dir is None:
        return None
    for path in (
        mock_dir / f"{paper_id}.json",
        mock_dir / f"{paper_id}.gpt54_review_low.response.txt",
        mock_dir / f"{paper_id}.gpt54_review_medium.response.txt",
        mock_dir / f"{paper_id}.gpt54_review_high.response.txt",
        mock_dir / f"{paper_id}.gpt54_review_xhigh.response.txt",
    ):
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return None


def load_reviewed_annotation(
    *,
    reviewed_dir: Path | None,
    paper_id: str,
    prepared_source: Any,
) -> dict[str, Any] | None:
    """Load reviewer-approved anchors and compile them to span metadata.

    Reviewed annotations use text anchors rather than block offsets so that a
    human can edit them safely. The core compiler resolves those anchors against
    the prepared source before normal Stage 07 validation runs.
    """

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
    """Resolve the OpenAI key only when the caller has allowed paid execution."""

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


def resolve_deepseek_api_key(explicit_key: str) -> str:
    if explicit_key.strip():
        return explicit_key.strip()
    env_path = REPO_ROOT / "env" / "deepseek_api_key.env"
    if not env_path.exists():
        raise RuntimeError("A live Stage 07 XML DeepSeek run needs DEEPSEEK_API_KEY in env/deepseek_api_key.env.")
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped and stripped.startswith(("ds-", "sk-")):
            return stripped
        if stripped.startswith("DEEPSEEK_API_KEY="):
            return stripped.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("No usable DEEPSEEK_API_KEY was found in env/deepseek_api_key.env.")


def refresh_artifact_registry(skip_refresh: bool, paper_ids: list[str]) -> None:
    """Refresh cross-stage provenance after canonical Stage 07 outputs change."""

    if skip_refresh or not paper_ids:
        return
    command = [sys.executable, str(ARTIFACT_REGISTRY_SCRIPT)]
    for paper_id in paper_ids:
        command.extend(["--paper-id", paper_id])
    subprocess.run(
        command,
        cwd=str(REPO_ROOT),
        check=True,
    )


def update_telemetry_validation(
    telemetry_rows: list[dict[str, str]],
    result: Any,
) -> None:
    """Attach Stage 07 validation outcomes to the latest API row for a paper."""

    for row in reversed(telemetry_rows):
        if row.get("paper_id") != result.paper_id:
            continue
        if row.get("validation_status"):
            return
        validation = result.validation_payload
        row["validation_status"] = str(validation.get("status") or "")
        row["validation_errors"] = "|".join(str(item) for item in validation.get("errors") or [])
        row["manual_review_reasons"] = str(result.registry_row.get("manual_review_reasons") or "")
        return


def load_initial_telemetry_rows(
    telemetry_jsonl_path: Path | None,
    telemetry_csv_path: Path | None,
) -> list[dict[str, str]]:
    """Load one existing telemetry ledger when resuming a capped paid run."""

    for path in (telemetry_jsonl_path, telemetry_csv_path):
        rows = load_telemetry_rows(path)
        if rows:
            return rows
    return []


def estimated_paid_cost(telemetry_rows: list[dict[str, str]]) -> float:
    return sum(float(row.get("estimated_cost_usd") or 0.0) for row in telemetry_rows)


def budget_cap_reached(max_cost_usd: float, telemetry_rows: list[dict[str, str]]) -> bool:
    return max_cost_usd > 0 and estimated_paid_cost(telemetry_rows) >= max_cost_usd


def budget_cap_annotation(route: str) -> dict[str, Any]:
    return {
        "annotation_mode": "budget_cap_exceeded",
        "route_mode": route,
        "targets": [],
        "segments": [],
        "manual_review_reasons": ["budget_cap_exceeded"],
    }


def annotation_model_label(args: argparse.Namespace) -> str:
    if args.annotation_provider == "deepseek" and args.annotation_architecture == "unit_ids_reviewed":
        return f"{args.deepseek_model}+{args.openai_review_model}"
    if args.annotation_provider == "deepseek":
        return args.deepseek_model
    return args.annotation_model


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
    if args.single_case_only:
        candidate_ids = collect_single_case_candidate_ids(
            stage06_rows=stage06_rows,
            paper_ids=args.paper_id,
            limit=args.limit,
            start_index=args.single_case_start_index,
        )
    else:
        candidate_ids = collect_candidate_ids(
            source_rows=source_rows,
            manual_rows=manual_rows,
            paper_ids=args.paper_id,
            limit=args.limit,
            route_filter=args.route_mode,
        )
    if not candidate_ids:
        raise SystemExit("No Stage 07 XML candidate papers matched the current filters.")

    # Live annotation is the only path that needs a secret. Reviewed and mocked
    # runs remain fully offline, which keeps validation and benchmarking cheap
    # and reproducible. Provider keys are resolved lazily immediately before
    # the first paid call, so offline replays never touch secret files.
    openai_api_key = ""
    deepseek_api_key = ""

    registry_rows: list[dict[str, str]] = []
    manifest_records: list[dict[str, Any]] = []
    telemetry_rows: list[dict[str, str]] = load_initial_telemetry_rows(
        args.telemetry_jsonl_path,
        args.telemetry_csv_path,
    )
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
        if args.single_case_only:
            annotation_payload = single_case_passthrough_annotation(
                prepared_source=prepared_source,
            )
            primary_unit_selection_payload = None
            review_patch_payload = None
        else:
            primary_unit_selection_payload = None
            review_patch_payload = None
            annotation_payload = load_reviewed_annotation(
                reviewed_dir=args.reviewed_annotation_dir,
                paper_id=paper_id,
                prepared_source=prepared_source,
            )
            if annotation_payload is None:
                annotation_payload = load_mock_annotation(args.mock_annotation_dir, paper_id)
            if annotation_payload is None:
                if args.annotation_architecture == "unit_ids_reviewed":
                    primary_unit_selection_payload = load_mock_unit_selection_payload(
                        args.mock_unit_selection_dir,
                        paper_id,
                    )
                    review_patch_payload = load_mock_review_patch(args.mock_review_patch_dir, paper_id)
                    if primary_unit_selection_payload is not None and review_patch_payload is not None and not args.allow_paid_run:
                        annotation_payload = annotate_with_deepseek_openai_reviewed_units(
                            prepared_source=prepared_source,
                            targets=[],
                            openai_api_key="mocked",
                            primary_selection_payload=primary_unit_selection_payload,
                            review_patch_payload=review_patch_payload,
                        )
                else:
                    annotation_payload = load_mock_unit_selection(
                        args.mock_unit_selection_dir,
                        paper_id,
                        prepared_source,
                    )
        if (
            annotation_payload is None
            and args.allow_paid_run
            and not args.single_case_only
        ):
            # Reconstruct the route and target inventory before calling the
            # model. This mirrors process_paper so the model sees only the
            # targets that Stage 07 is prepared to validate.
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

            def live_annotation() -> dict[str, Any]:
                nonlocal openai_api_key, deepseek_api_key
                if budget_cap_reached(args.max_paid_api_cost_usd, telemetry_rows):
                    return budget_cap_annotation(route)
                architecture_variant = (
                    args.annotation_architecture
                    if args.architecture_variant == "block_offsets" and args.annotation_architecture != "block_offsets"
                    else args.architecture_variant
                )
                telemetry_context = {
                    "benchmark_run_id": args.benchmark_run_id or manifest_run_id,
                    "matrix_config_name": args.matrix_config_name,
                    "architecture_variant": architecture_variant,
                }
                if args.annotation_provider == "deepseek":
                    if args.annotation_architecture not in {"unit_ids", "unit_ids_reviewed"}:
                        raise SystemExit(
                            "DeepSeek annotation supports --annotation-architecture unit_ids or unit_ids_reviewed."
                        )
                    if args.annotation_architecture == "unit_ids" and not deepseek_api_key:
                        deepseek_api_key = resolve_deepseek_api_key(args.deepseek_api_key)
                    if args.annotation_architecture == "unit_ids_reviewed":
                        if primary_unit_selection_payload is None and not deepseek_api_key:
                            deepseek_api_key = resolve_deepseek_api_key(args.deepseek_api_key)
                        if not openai_api_key:
                            openai_api_key = resolve_api_key(args.openai_api_key)
                        return annotate_with_deepseek_openai_reviewed_units(
                            prepared_source=prepared_source,
                            targets=targets,
                            deepseek_model=args.deepseek_model,
                            deepseek_api_key=deepseek_api_key,
                            openai_model=args.openai_review_model,
                            openai_api_key=openai_api_key,
                            openai_reasoning_effort=args.openai_review_reasoning_effort,
                            trace_dir=trace_dir,
                            deepseek_max_output_tokens=args.deepseek_max_output_tokens,
                            openai_max_output_tokens=args.openai_review_max_output_tokens,
                            telemetry_rows=telemetry_rows,
                            telemetry_jsonl_path=args.telemetry_jsonl_path,
                            telemetry_csv_path=args.telemetry_csv_path,
                            telemetry_context=telemetry_context,
                            deepseek_request_timeout_seconds=args.deepseek_request_timeout_seconds,
                            max_paid_api_cost_usd=args.max_paid_api_cost_usd,
                            primary_selection_payload=primary_unit_selection_payload,
                            review_patch_payload=review_patch_payload,
                        )
                    return annotate_with_deepseek_units(
                        prepared_source=prepared_source,
                        targets=targets,
                        model=args.deepseek_model,
                        api_key=deepseek_api_key,
                        trace_dir=trace_dir,
                        max_output_tokens=args.deepseek_max_output_tokens,
                        telemetry_rows=telemetry_rows,
                        telemetry_jsonl_path=args.telemetry_jsonl_path,
                        telemetry_csv_path=args.telemetry_csv_path,
                        telemetry_context=telemetry_context,
                        request_timeout_seconds=args.deepseek_request_timeout_seconds,
                    )
                if args.annotation_architecture != "block_offsets":
                    raise SystemExit("OpenAI annotation currently supports only --annotation-architecture block_offsets.")
                if not openai_api_key:
                    openai_api_key = resolve_api_key(args.openai_api_key)
                return annotate_with_openai(
                    prepared_source=prepared_source,
                    targets=targets,
                    model=args.annotation_model,
                    api_key=openai_api_key,
                    trace_dir=trace_dir,
                    max_output_tokens=args.max_output_tokens,
                    reasoning_effort=args.reasoning_effort,
                    strict_json_schema=not args.relaxed_json_schema,
                    telemetry_rows=telemetry_rows,
                    telemetry_jsonl_path=args.telemetry_jsonl_path,
                    telemetry_csv_path=args.telemetry_csv_path,
                    telemetry_context=telemetry_context,
                )

            if route_decision.manual_review_reasons:
                annotation_payload = None
            elif route == "individual":
                # Confident single-patient papers stay deterministic. The model
                # is used only when the clinical window could not be isolated.
                deterministic_payload = deterministic_annotation_for_route(
                    prepared_source=prepared_source,
                    targets=targets,
                    route=route,
                )
                if deterministic_payload.get("manual_review_reasons"):
                    annotation_payload = live_annotation()
            elif route in {"individual_case_split", "group"}:
                # Multi-target and group papers are the attribution-heavy cases
                # where deterministic pass-through is too risky.
                annotation_payload = live_annotation()

        result = process_paper(
            paper_id=paper_id,
            source_row=source_rows.get(paper_id, {}),
            manual_row=manual_rows.get(paper_id, {}),
            stage06_row=stage06_rows.get(paper_id, {}),
            paths=paths,
            manifest_run_id=manifest_run_id,
            annotation_model=annotation_model_label(args),
            annotation_payload=annotation_payload,
            max_block_chars=args.max_block_chars,
        )
        write_process_result(result)
        update_telemetry_validation(telemetry_rows, result)
        registry_rows.append(result.registry_row)
        manifest_records.extend(result.manifest_records)
        write_registry(registry_rows, args.registry_path)
        write_manifest(manifest_records, manifest_path)

    write_registry(registry_rows, args.registry_path)
    write_manifest(manifest_records, manifest_path)
    telemetry_jsonl_path = args.telemetry_jsonl_path or (
        trace_dir / "api_telemetry.jsonl" if telemetry_rows else None
    )
    telemetry_csv_path = args.telemetry_csv_path or (
        trace_dir / "api_telemetry.csv" if telemetry_rows else None
    )
    if telemetry_rows and telemetry_jsonl_path is not None:
        write_telemetry_jsonl(telemetry_jsonl_path, telemetry_rows)
    if telemetry_rows and telemetry_csv_path is not None:
        write_telemetry_csv(telemetry_csv_path, telemetry_rows)
    refreshed_paper_ids = [
        str(row.get("paper_id") or "").strip()
        for row in registry_rows
        if str(row.get("paper_id") or "").strip()
    ]
    refresh_artifact_registry(args.skip_artifact_registry_refresh, refreshed_paper_ids)

    ready_records = sum(1 for record in manifest_records if record.get("ready_for_langextract"))
    print(
        f"Wrote {len(registry_rows)} Stage 07 XML registry rows to {args.registry_path}; "
        f"manifest records={len(manifest_records)} ready={ready_records} skipped_existing={skipped}."
    )


if __name__ == "__main__":
    main()
