"""Offline Stage 07 XML benchmark runner.

The runner compares candidate Stage 07 behaviour with reviewed gold annotations
without making live LLM calls. It writes scratch Stage 07 outputs inside the
benchmark run directory only, then stores compact scores under the configured
QA evaluation root.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from stage07_XML import core
from stage07_benchmarking.manifest import (
    DEFAULT_EVALUATION_ROOT,
    RUN_CONFIG_SCHEMA_VERSION,
    benchmark_paths,
    load_model_matrix,
    load_promotion_gates,
    now_run_id,
    write_benchmark_artifacts,
)
from stage07_benchmarking.metrics import score_segments_payloads, summarise_paper_scores
from stage07_benchmarking.telemetry import load_telemetry_rows


DEFAULT_REVIEWED_GOLD_DIR = (
    core.REPO_ROOT
    / "qa"
    / "validation"
    / "stage07_xml"
    / "gold_standard"
    / "stage07_xml_live_test10_20260425"
    / "reviewed_annotations"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offline Stage 07 XML benchmark against reviewed gold annotations."
    )
    parser.add_argument(
        "--reviewed-gold-dir",
        type=Path,
        default=DEFAULT_REVIEWED_GOLD_DIR,
        help="Directory containing reviewed {paper_id}.json annotations used as gold.",
    )
    parser.add_argument(
        "--candidate-annotation-dir",
        type=Path,
        default=None,
        help=(
            "Optional directory containing candidate {paper_id}.json annotations. "
            "If omitted, the current deterministic/no-model Stage 07 path is scored."
        ),
    )
    parser.add_argument(
        "--candidate-stage07-root",
        type=Path,
        default=None,
        help="Optional existing Stage 07 output root to rescore instead of recompiling candidate annotations.",
    )
    parser.add_argument(
        "--candidate-registry-path",
        type=Path,
        default=None,
        help="Optional registry CSV for --candidate-stage07-root readiness/manual-review metadata.",
    )
    parser.add_argument(
        "--gold-stage07-root",
        type=Path,
        default=None,
        help="Optional existing gold Stage 07 output root, such as a DOCX-import regenerated gold root.",
    )
    parser.add_argument(
        "--gold-registry-path",
        type=Path,
        default=None,
        help="Optional registry CSV for --gold-stage07-root readiness metadata.",
    )
    parser.add_argument(
        "--docx-round-dir",
        type=Path,
        default=None,
        help="Use reviewed_annotations and regenerated gold outputs from an imported DOCX review round.",
    )
    parser.add_argument(
        "--evaluation-root",
        type=Path,
        default=DEFAULT_EVALUATION_ROOT,
        help="Root for non-canonical benchmark artefacts.",
    )
    parser.add_argument("--run-id", default="", help="Optional benchmark run id.")
    parser.add_argument("--paper-id", action="append", default=[], help="Paper ID to score. Repeatable.")
    parser.add_argument(
        "--model-matrix",
        type=Path,
        default=None,
        help="Optional JSON model/config matrix to record with the run.",
    )
    parser.add_argument(
        "--promotion-gates",
        type=Path,
        default=None,
        help="Optional promotion-gate JSON. Defaults to the packaged precision-first gates.",
    )
    parser.add_argument(
        "--matrix-config-name",
        default="",
        help="Configuration name to attach to candidate scores when scoring a single candidate.",
    )
    parser.add_argument(
        "--api-telemetry-path",
        type=Path,
        default=None,
        help="Optional CSV or JSONL telemetry file to merge into benchmark reports.",
    )
    parser.add_argument(
        "--max-block-chars",
        type=int,
        default=core.DEFAULT_MAX_BLOCK_CHARS,
        help="Maximum prepared source characters per paragraph block.",
    )
    return parser.parse_args()


def selected_paper_ids(reviewed_gold_dir: Path, requested_ids: list[str]) -> list[str]:
    """Return requested IDs or all reviewed gold IDs in paper-number order."""

    def sort_key(paper_id: str) -> tuple[int, int | str]:
        text = str(paper_id or "").strip()
        if text.isdigit():
            return (0, int(text))
        return (1, text)

    if requested_ids:
        return sorted({str(item).strip() for item in requested_ids if str(item).strip()}, key=sort_key)
    return sorted(
        (path.stem for path in reviewed_gold_dir.glob("*.json")),
        key=sort_key,
    )


def load_annotation_payload(path: Path, prepared_source: core.PreparedSource) -> dict[str, Any]:
    """Load either reviewed anchors or already-compiled span metadata.

    This lets the same benchmark path compare the current deterministic pipeline,
    reviewed gold, or a directory of saved candidate model responses.
    """

    payload = json.loads(path.read_text(encoding="utf-8"))
    if str(payload.get("stage07_reviewed_annotation_schema_version") or "").strip():
        return core.compile_reviewed_annotation_payload(
            reviewed_payload=payload,
            prepared_source=prepared_source,
        )
    if any("selections" in segment for segment in payload.get("segments") or []):
        return core.compile_reviewed_annotation_payload(
            reviewed_payload=payload,
            prepared_source=prepared_source,
        )
    return payload


def reviewed_annotation_to_segments_payload(payload: dict[str, Any], paper_id: str) -> dict[str, Any]:
    """Build a scoreable segments payload from reviewed source-offset selections."""

    segments: list[dict[str, Any]] = []
    segment_index = 1
    for logical_index, segment in enumerate(payload.get("segments") or [], start=1):
        targets = [str(target) for target in segment.get("targets") or []]
        role = str(segment.get("role") or "")
        confidence = str(segment.get("confidence") or "reviewed")
        evidence = str(segment.get("evidence") or "reviewed_annotation")
        for selection in segment.get("selections") or []:
            try:
                start = int(selection.get("source_start"))
                end = int(selection.get("source_end"))
            except (TypeError, ValueError):
                continue
            if start >= end:
                continue
            segments.append(
                {
                    "segment_id": f"s{segment_index:04d}",
                    "logical_segment_id": str(segment.get("review_segment_id") or f"l{logical_index:04d}"),
                    "targets": targets,
                    "role": role,
                    "text": str(selection.get("text") or ""),
                    "source_offsets": {"start": start, "end": end},
                    "source_block_id": "",
                    "confidence": confidence,
                    "evidence": evidence,
                }
            )
            segment_index += 1
    return {
        "paper_id": paper_id,
        "entities": [
            {
                "id": str(target.get("id") or ""),
                "kind": str(target.get("kind") or ""),
                "label": str(target.get("label") or ""),
                "source": str(target.get("evidence") or "reviewed_annotation"),
            }
            for target in payload.get("targets") or []
        ],
        "segments": segments,
        "validation": {"status": "passed", "roundtrip_status": "not_run"},
    }


def load_stage07_segments(root: Path, paper_id: str) -> dict[str, Any]:
    path = core.output_paths(root).segments_dir / f"{paper_id}.segments.json"
    if not path.exists():
        raise FileNotFoundError(f"Missing Stage 07 segments payload: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_registry_rows(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None or not path.exists():
        return {}
    return core.load_csv_rows_by_id(path, "paper_id")


def process_with_annotation(
    *,
    paper_id: str,
    annotation_payload: dict[str, Any] | None,
    output_root: Path,
    source_rows: dict[str, dict[str, str]],
    manual_rows: dict[str, dict[str, str]],
    stage06_rows: dict[str, dict[str, str]],
    max_block_chars: int,
) -> core.ProcessResult:
    """Run the normal Stage 07 compiler against one annotation payload.

    The benchmark scores post-validation Stage 07 outputs rather than raw
    annotations, so failures in target recovery, table trimming, readiness, and
    manual-review flags are all represented in the same shape used downstream.
    """

    paths = core.output_paths(output_root)
    prior = core.parse_stage06_prior(stage06_rows.get(paper_id, {}))
    source_path = core.resolve_source_json_path(
        paper_id=paper_id,
        source_row=source_rows.get(paper_id, {}),
        stage06_prior=prior,
    )
    return core.process_paper(
        paper_id=paper_id,
        source_row=source_rows.get(paper_id, {}),
        manual_row=manual_rows.get(paper_id, {}),
        stage06_row=stage06_rows.get(paper_id, {}),
        paths=paths,
        manifest_run_id="stage07_benchmark",
        annotation_model="offline",
        annotation_payload=annotation_payload,
        max_block_chars=max_block_chars,
    )


def benchmark_paper(
    *,
    paper_id: str,
    reviewed_gold_dir: Path,
    candidate_annotation_dir: Path | None,
    candidate_stage07_root: Path | None,
    candidate_registry_rows: dict[str, dict[str, str]],
    gold_stage07_root: Path | None,
    gold_registry_rows: dict[str, dict[str, str]],
    output_root: Path,
    source_rows: dict[str, dict[str, str]],
    manual_rows: dict[str, dict[str, str]],
    stage06_rows: dict[str, dict[str, str]],
    max_block_chars: int,
    matrix_config_name: str,
) -> dict[str, Any]:
    """Score one paper by compiling gold and candidate annotations side by side."""

    prepared_source: core.PreparedSource | None = None
    source_error: Exception | None = None
    try:
        prior = core.parse_stage06_prior(stage06_rows.get(paper_id, {}))
        source_path = core.resolve_source_json_path(
            paper_id=paper_id,
            source_row=source_rows.get(paper_id, {}),
            stage06_prior=prior,
        )
        prepared_source = core.prepare_source(
            paper_id=paper_id,
            source_path=source_path,
            max_block_chars=max_block_chars,
        )
    except FileNotFoundError as exc:
        source_error = exc
    reviewed_gold_payload = json.loads((reviewed_gold_dir / f"{paper_id}.json").read_text(encoding="utf-8"))
    gold_annotation = (
        load_annotation_payload(reviewed_gold_dir / f"{paper_id}.json", prepared_source)
        if prepared_source is not None
        else reviewed_gold_payload
    )
    candidate_annotation = None
    if candidate_annotation_dir is not None:
        if prepared_source is None:
            raise source_error or FileNotFoundError(f"Cannot compile candidate annotation for {paper_id}")
        candidate_path = candidate_annotation_dir / f"{paper_id}.json"
        if candidate_path.exists():
            candidate_annotation = load_annotation_payload(candidate_path, prepared_source)
    if gold_stage07_root is None:
        if prepared_source is None:
            gold_payload = reviewed_annotation_to_segments_payload(reviewed_gold_payload, paper_id)
            gold_registry_row = {"ready_for_langextract": "true"}
        else:
            gold_result = process_with_annotation(
                paper_id=paper_id,
                annotation_payload=gold_annotation,
                output_root=output_root,
                source_rows=source_rows,
                manual_rows=manual_rows,
                stage06_rows=stage06_rows,
                max_block_chars=max_block_chars,
            )
            gold_payload = gold_result.segments_payload
            gold_registry_row = gold_result.registry_row
    else:
        gold_payload = load_stage07_segments(gold_stage07_root, paper_id)
        gold_registry_row = gold_registry_rows.get(paper_id, {})
    if candidate_stage07_root is None:
        if prepared_source is None:
            raise source_error or FileNotFoundError(f"Cannot compile deterministic candidate for {paper_id}")
        # Gold and candidate runs share the same scratch root. Filenames may overlap,
        # but the benchmark keeps the returned in-memory payloads and writes only the
        # final score artefacts for comparison.
        candidate_result = process_with_annotation(
            paper_id=paper_id,
            annotation_payload=candidate_annotation,
            output_root=output_root,
            source_rows=source_rows,
            manual_rows=manual_rows,
            stage06_rows=stage06_rows,
            max_block_chars=max_block_chars,
        )
        predicted_payload = candidate_result.segments_payload
        registry_row = candidate_result.registry_row
    else:
        predicted_payload = load_stage07_segments(candidate_stage07_root, paper_id)
        registry_row = candidate_registry_rows.get(paper_id, {})
    return score_segments_payloads(
        gold_payload=gold_payload,
        predicted_payload=predicted_payload,
        paper_id=paper_id,
        registry_row=registry_row,
        gold_registry_row=gold_registry_row,
        matrix_config_name=matrix_config_name,
    )


def resolve_gold_inputs(args: argparse.Namespace) -> tuple[Path, Path | None, Path | None]:
    reviewed_gold_dir = args.reviewed_gold_dir
    gold_stage07_root = args.gold_stage07_root
    gold_registry_path = args.gold_registry_path
    if args.docx_round_dir is not None:
        reviewed_gold_dir = args.docx_round_dir / "reviewed_annotations"
        if gold_stage07_root is None and (args.docx_round_dir / "gold_stage07_xml").exists():
            gold_stage07_root = args.docx_round_dir / "gold_stage07_xml"
        if gold_registry_path is None and (args.docx_round_dir / "gold_stage07_xml_registry.csv").exists():
            gold_registry_path = args.docx_round_dir / "gold_stage07_xml_registry.csv"
    return reviewed_gold_dir, gold_stage07_root, gold_registry_path


def main() -> None:
    args = parse_args()
    reviewed_gold_dir, gold_stage07_root, gold_registry_path = resolve_gold_inputs(args)
    paper_ids = selected_paper_ids(reviewed_gold_dir, args.paper_id)
    if not paper_ids:
        raise SystemExit("No reviewed gold annotations matched the benchmark request.")

    run_id = args.run_id or now_run_id()
    paths = benchmark_paths(args.evaluation_root, run_id)
    # Scratch Stage 07 outputs are intentionally nested under this benchmark run.
    # They are non-canonical intermediates and should not be consumed by the main
    # pipeline or paper artefact registry.
    scratch_output_root = paths.run_dir / "scratch_stage07_xml"
    source_rows = core.load_csv_rows_by_id(core.SOURCE_CATEGORISATION_PATH, "paper_id")
    manual_rows = core.load_csv_rows_by_id(core.SOURCE_MANUAL_REVIEW_PATH, "paper_id")
    stage06_rows = core.load_csv_rows_by_id(core.SOURCE_CASE_COUNT_PATH, "paper_id")
    candidate_registry_rows = load_registry_rows(args.candidate_registry_path)
    gold_registry_rows = load_registry_rows(gold_registry_path)
    paper_scores = [
        benchmark_paper(
            paper_id=paper_id,
            reviewed_gold_dir=reviewed_gold_dir,
            candidate_annotation_dir=args.candidate_annotation_dir,
            candidate_stage07_root=args.candidate_stage07_root,
            candidate_registry_rows=candidate_registry_rows,
            gold_stage07_root=gold_stage07_root,
            gold_registry_rows=gold_registry_rows,
            output_root=scratch_output_root,
            source_rows=source_rows,
            manual_rows=manual_rows,
            stage06_rows=stage06_rows,
            max_block_chars=args.max_block_chars,
            matrix_config_name=args.matrix_config_name,
        )
        for paper_id in paper_ids
    ]
    telemetry_rows = load_telemetry_rows(args.api_telemetry_path)
    promotion_gates = load_promotion_gates(args.promotion_gates)
    summary = summarise_paper_scores(paper_scores)
    summary["estimated_cost_usd"] = sum(float(row.get("estimated_cost_usd") or 0.0) for row in telemetry_rows)
    summary["latency_ms"] = sum(int(float(row.get("latency_ms") or 0.0)) for row in telemetry_rows)
    run_config = {
        "schema_version": RUN_CONFIG_SCHEMA_VERSION,
        "run_id": run_id,
        "reviewed_gold_dir": str(reviewed_gold_dir),
        "candidate_annotation_dir": str(args.candidate_annotation_dir or ""),
        "candidate_stage07_root": str(args.candidate_stage07_root or ""),
        "candidate_registry_path": str(args.candidate_registry_path or ""),
        "gold_stage07_root": str(gold_stage07_root or ""),
        "gold_registry_path": str(gold_registry_path or ""),
        "docx_round_dir": str(args.docx_round_dir or ""),
        "paper_ids": paper_ids,
        "max_block_chars": args.max_block_chars,
        "matrix_config_name": args.matrix_config_name,
        "model_matrix": load_model_matrix(args.model_matrix),
        "promotion_gates_path": str(args.promotion_gates or ""),
        "promotion_gate_profile": str(promotion_gates.get("profile_name") or ""),
        # This runner is intentionally offline. Future live benchmarks should
        # make paid execution explicit in a separate command path.
        "paid_api_calls": False,
        "api_telemetry_path": str(args.api_telemetry_path or ""),
    }
    write_benchmark_artifacts(
        paths=paths,
        run_config=run_config,
        paper_scores=paper_scores,
        summary=summary,
        telemetry_rows=telemetry_rows,
        promotion_gates=promotion_gates,
    )
    print(f"Wrote Stage 07 benchmark artefacts to {paths.run_dir}")


if __name__ == "__main__":
    main()
